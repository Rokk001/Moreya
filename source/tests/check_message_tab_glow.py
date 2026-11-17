"""Check that unread notification tabs glow calmly and never jump, and that read tabs show no glow.

A probe compiles the production GameMode::updateEventMessageIndicator together with the production message tab
constants and messageTabGlowColour, with stand-ins for the CEGUI windows that record every property the function
sets. It plays 10 seconds at 60 frames per second with one unread and one read tab, then marks the unread tab read,
and asserts the outcome on screen:
- the picture (NormalImage) of every tab is the same in every frame and the same for read and unread tabs, so the
  "i" never moves up or down;
- the unread tab glows in the warm gold colour with an opacity between 25 % and 80 % (noticeable, not intrusive),
  that changes by at most 3/255 per frame (no blinking) and swells and fades at most once per 1.5 seconds (calm),
  with a visible swing of at least 30 % opacity;
- a read tab, also the one read during the run, shows no glow.
The painted atlas cell of that one picture is also checked to be a full, opaque tab picture.

Fixed values of this branch: 600 frames, 1/60 s per frame. The probe compiles with cl, so this check runs in the
compile phase of the integration only.
"""
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def read(path):
    """Returns the text of a repository file."""
    return (ROOT / path).read_text(encoding='utf-8')


def block(source, signature):
    """Returns the production text from the signature to the end of its braces block, unchanged."""
    start = source.index(signature)
    end = source.index('{', start) + 1
    depth = 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


game_mode = read('source/modes/GameMode.cpp')
constants_start = game_mode.index('const float MESSAGE_QUEUE_DESIGN_HEIGHT')
glow_function = block(game_mode, 'static std::string messageTabGlowColour(')
constants = game_mode[constants_start:game_mode.index(glow_function)] + glow_function
update = block(game_mode, 'void GameMode::updateEventMessageIndicator(float elapsed)')

# The tab picture must be one complete painted cell of the icon atlas.
image = re.search(r'MESSAGE_TAB_IMAGE = "OpenDungeonsIcons/(\w+)";', constants)
assert image, 'message tab picture'
entry = re.search(r'<Image height="(\d+)" name="' + image.group(1) + r'" width="(\d+)" xPos="(\d+)" yPos="(\d+)" />',
                  read('gui/ODIcons.imageset'))
assert entry, image.group(1)
from PIL import Image  # noqa: E402
height, width, x, y = (int(v) for v in entry.groups())
cell = Image.open(ROOT / 'gui/ODIcons.png').convert('RGBA').crop((x, y, x + width, y + height))
alpha = cell.getchannel('A')
assert sum(1 for a in alpha.getdata() if a > 200) > 0.9 * width * height, 'tab picture not opaque'

# The glow is drawn by the SelectionColour layer of the tab look in its normal state.
looknfeel = read('gui/OD.looknfeel')
look = looknfeel[looknfeel.index('<WidgetLook name="OD/GameTabButton">'):]
look = look[:look.index('</WidgetLook>')]
selected = look[look.index('<ImagerySection name="selected">'):]
selected = selected[:selected.index('</ImagerySection>')]
assert '<ColourRectProperty name="SelectionColour" />' in selected
normal = look[look.index('<StateImagery name="Normal">'):]
normal = normal[:normal.index('</StateImagery>')]
assert '<Section section="selected" />' in normal

PREAMBLE = r'''
#include <algorithm>
#include <cassert>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <iomanip>
#include <map>
#include <sstream>
#include <string>
#include <vector>

namespace CEGUI
{
//! Stand-in for a unified dimension.
struct UDim { float scale, offset; UDim(float s, float o) : scale(s), offset(o) {} };
//! Stand-in for a pixel size.
struct Sizef { float d_width, d_height; };
//! Stand-in window that records its properties and visibility.
struct Window
{
    std::map<std::string, std::string> mProperties;
    std::map<std::string, Window*> mChildren;
    Sizef mSize = Sizef{0.0f, 0.0f};
    bool mVisible = true;
    float mLeft = 0.0f;
    int mSets = 0;
    Window* getChild(const std::string& name) { return mChildren[name]; }
    const Sizef& getPixelSize() const { return mSize; }
    void setArea(const UDim& x, const UDim&, const UDim&, const UDim&) { mLeft = x.offset; }
    std::string getProperty(const std::string& name) { return mProperties[name]; }
    void setProperty(const std::string& name, const std::string& value) { mProperties[name] = value; ++mSets; }
    void show() { mVisible = true; }
    void hide() { mVisible = false; }
};
}
'''

GAME_MODE = r'''
//! The production game mode reduced to the message tab state.
struct GameMode
{
    struct MessageTab
    {
        void* message;
        CEGUI::Window* window;
        bool read;
        float position;
    };
    std::vector<MessageTab> mMessageTabs;
    float mEventMessageFlashTime = 0.0f;
    CEGUI::Window* mRootWindow = nullptr;
    void updateEventMessageIndicator(float elapsed);
};
'''

MAIN = r'''
//! Reads the alpha byte and the RGB part of a CEGUI ARGB hex colour.
static int alphaOf(const std::string& colour, std::string& rgb)
{
    assert(colour.size() == 8);
    rgb = colour.substr(2);
    return static_cast<int>(std::strtol(colour.substr(0, 2).c_str(), nullptr, 16));
}

//! Plays the message tabs for 10 seconds and checks picture and glow in every frame.
int main()
{
    CEGUI::Window root, queue, receiver, unread, read;
    root.mChildren["MessageQueue"] = &queue;
    queue.mChildren["Receiver"] = &receiver;
    queue.mSize = CEGUI::Sizef{400.0f, 52.0f};
    receiver.mSize = CEGUI::Sizef{40.0f, 52.0f};
    unread.mProperties["NormalImage"] = MESSAGE_TAB_IMAGE;
    read.mProperties["NormalImage"] = MESSAGE_TAB_IMAGE;
    GameMode mode;
    mode.mRootWindow = &root;
    mode.mMessageTabs.push_back(GameMode::MessageTab{nullptr, &unread, false, -1.0f});
    mode.mMessageTabs.push_back(GameMode::MessageTab{nullptr, &read, true, -1.0f});

    const float frame = 1.0f / 60.0f;
    const std::string picture = unread.mProperties["NormalImage"];
    int previous = -1, lowest = 255, highest = 0, peaks = 0, rising = 0;
    for(int i = 0; i < 600; ++i)
    {
        mode.updateEventMessageIndicator(frame);
        assert(unread.mVisible && read.mVisible);
        assert(unread.mProperties["NormalImage"] == picture);
        assert(read.mProperties["NormalImage"] == picture);
        std::string rgb;
        const int alpha = alphaOf(unread.mProperties["SelectionColour"], rgb);
        assert(rgb == "FFD060");
        assert(alpha >= static_cast<int>(0.25f * 255.0f) && alpha <= static_cast<int>(0.80f * 255.0f));
        std::string readRgb;
        assert(alphaOf(read.mProperties["SelectionColour"], readRgb) == 0);
        if(previous >= 0)
        {
            assert(std::abs(alpha - previous) <= 3);
            if(alpha > previous)
                rising = 1;
            else if(alpha < previous && rising == 1)
            {
                ++peaks;
                rising = 0;
            }
        }
        previous = alpha;
        lowest = std::min(lowest, alpha);
        highest = std::max(highest, alpha);
    }
    assert(highest - lowest >= static_cast<int>(0.30f * 255.0f));
    // 10 seconds hold at most 10 / 1.5 swells
    assert(peaks >= 1 && peaks <= 6);

    mode.mMessageTabs[0].read = true;
    mode.updateEventMessageIndicator(frame);
    std::string rgb;
    assert(alphaOf(unread.mProperties["SelectionColour"], rgb) == 0);
    assert(unread.mProperties["NormalImage"] == picture);
    std::printf("message tab glow probe passed (%d swells in 10 s, opacity %d..%d)\n", peaks, lowest, highest);
    return 0;
}
'''


def main():
    """Compiles and runs the probe of the production message tab update."""
    source = PREAMBLE + constants + '\n' + GAME_MODE + update + '\n' + MAIN
    vcvars = Path('C:/Program Files (x86)/Microsoft Visual Studio/18/BuildTools/VC/Auxiliary/Build/vcvars64.bat')
    with tempfile.TemporaryDirectory() as directory:
        directory = Path(directory)
        cpp = directory / 'probe.cpp'
        cpp.write_text(source, encoding='utf-8')
        batch = directory / 'run.cmd'
        batch.write_text(
            f'@echo off\ncall "{vcvars}" >nul\n'
            f'cl /nologo /EHsc /std:c++14 "{cpp}" /Fe:"{directory / "probe.exe"}" '
            f'/Fo:"{directory / "probe.obj"}"\n'
            'if errorlevel 1 exit /b 1\n'
            f'"{directory / "probe.exe"}"\nexit /b %errorlevel%\n',
            encoding='utf-8',
        )
        subprocess.run(['cmd', '/d', '/c', str(batch)], cwd=directory, check=True)
    print('message tab glow passes the checks')


if __name__ == '__main__':
    main()
