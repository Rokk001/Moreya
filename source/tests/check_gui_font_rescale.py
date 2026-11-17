"""Check that opening a menu screen or an in-game window no longer rebuilds every font (frame stall cause).

Measured cause (INGAME-QS-10 P1): Gui::registerWindowHierarchy, called by every loadGuiSheet (each menu screen change
and the game start) and by every new in-game window, calls Gui::applyScale and with it Gui::updateResourceScaling. That
set the native resolution of every font again and notified every font of the display size. In CEGUI 0.8 both calls
rebuild the font (all rendered glyphs thrown away) and make every window that uses it reformat its text. A sampled
profile of the deployed build put 53.5 % of a 357 ms menu change frame into Font::notifyDisplaySizeChanged under
Gui::updateResourceScaling; the owner's menu changes stalled 347, 447 and 558 ms ("mode-and-input-update").

The production Gui::updateResourceScaling is compiled unchanged into a probe with stand-ins for the CEGUI font and
image managers that keep CEGUI 0.8's behaviour (Font::setNativeResolution and Font::notifyDisplaySizeChanged recompute
the scaling for the current mode and rebuild an auto-scaled font; Font::setAutoScaled rebuilds it when the mode
changes). The probe requires:
- after the first call every font is rendered for the wanted native resolution, ASM_Min and the display size;
- ten more calls with the same display size and user scale rebuild no font at all;
- a new display size, a new user scale and a newly loaded font each end with every font rendered for the new
  wanted values, so nothing the player sees changes.

Fixed values: 3 fonts at the start, user scale 1.1 then 1.2, displays 1920x1200 and 1280x720, design size 800x600.
The probe compiles with cl, so this check runs in the compile phase of the integration only.
"""
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def block(source, signature):
    """Returns the production text from the signature to the end of its braces block, unchanged."""
    start = source.index(signature)
    end = source.index('{', start) + 1
    depth = 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


gui_cpp = (ROOT / 'source/render/Gui.cpp').read_text(encoding='utf-8')
production = block(gui_cpp, 'void Gui::updateResourceScaling(')
constants = '\n'.join(re.findall(r'^const float (?:FONT|LAYOUT)_DESIGN_(?:WIDTH|HEIGHT) = [\d.]+f;$', gui_cpp, re.M))
assert constants.count('const float') == 4, constants

PREAMBLE = r'''
#include <cassert>
#include <cstdio>
#include <map>
#include <string>
#include <utility>
#include <vector>

namespace CEGUI
{
enum AutoScaledMode { ASM_Disabled, ASM_Vertical, ASM_Horizontal, ASM_Min, ASM_Max, ASM_Both };
typedef std::string String;
struct Sizef
{
    Sizef(float width = 0.0f, float height = 0.0f) : d_width(width), d_height(height) {}
    bool operator==(const Sizef& other) const { return d_width == other.d_width && d_height == other.d_height; }
    bool operator!=(const Sizef& other) const { return !operator==(other); }
    float d_width;
    float d_height;
};
Sizef gDisplay;

//! What a font's glyphs were last rendered for: native resolution, scaling mode and display size.
struct FontState
{
    Sizef mNative;
    AutoScaledMode mMode;
    Sizef mDisplay;
};

//! CEGUI 0.8 Font: the scaling is computed in notifyDisplaySizeChanged, updateFont renders the glyphs with it.
class Font
{
public:
    Font(const Sizef& native, AutoScaledMode mode) : d_native(native), d_mode(mode), d_updates(0)
    {
        notifyDisplaySizeChanged(gDisplay);
    }
    void setNativeResolution(const Sizef& size)
    {
        d_native = size;
        notifyDisplaySizeChanged(gDisplay);
    }
    const Sizef& getNativeResolution() const { return d_native; }
    void setAutoScaled(AutoScaledMode mode)
    {
        if(mode == d_mode)
            return;
        d_mode = mode;
        updateFont();
    }
    AutoScaledMode getAutoScaled() const { return d_mode; }
    void notifyDisplaySizeChanged(const Sizef& size)
    {
        d_scaling.mNative = d_native;
        d_scaling.mMode = d_mode;
        d_scaling.mDisplay = size;
        if(d_mode != ASM_Disabled)
            updateFont();
    }
    void updateFont()
    {
        ++d_updates;
        d_rendered = d_scaling;
    }
    Sizef d_native;
    AutoScaledMode d_mode;
    FontState d_scaling;
    FontState d_rendered;
    int d_updates;
};

class FontManager
{
public:
    class FontIterator
    {
    public:
        explicit FontIterator(std::vector<Font*>& fonts) : mFonts(fonts), mIndex(0) {}
        bool isAtEnd() const { return mIndex >= mFonts.size(); }
        Font* getCurrentValue() const { return mFonts[mIndex]; }
        FontIterator& operator++() { ++mIndex; return *this; }
    private:
        std::vector<Font*>& mFonts;
        size_t mIndex;
    };
    static FontManager& getSingleton() { static FontManager manager; return manager; }
    FontIterator getIterator() { return FontIterator(mFonts); }
    void notifyDisplaySizeChanged(const Sizef& size)
    {
        for(Font* font : mFonts)
            font->notifyDisplaySizeChanged(size);
    }
    std::vector<Font*> mFonts;
};

class ImageFactory;
class Image { public: virtual ~Image() {} };
class BasicImage : public Image
{
public:
    void setNativeResolution(const Sizef&) {}
    void setAutoScaled(AutoScaledMode) {}
};
class ImageManager
{
public:
    typedef std::map<String, std::pair<Image*, ImageFactory*> > Map;
    class ImageIterator
    {
    public:
        explicit ImageIterator(Map& images) : mIt(images.begin()), mEnd(images.end()) {}
        bool isAtEnd() const { return mIt == mEnd; }
        const String& getCurrentKey() const { return mIt->first; }
        const std::pair<Image*, ImageFactory*>& getCurrentValue() const { return mIt->second; }
        ImageIterator& operator++() { ++mIt; return *this; }
    private:
        Map::iterator mIt;
        Map::iterator mEnd;
    };
    static ImageManager& getSingleton() { static ImageManager manager; return manager; }
    ImageIterator getIterator() { return ImageIterator(mImages); }
    void notifyDisplaySizeChanged(const Sizef&) { ++mNotifications; }
    Map mImages;
    int mNotifications = 0;
};
}

bool shouldScaleImage(const CEGUI::String&) { return true; }
float imagePixelDensity(const CEGUI::String&) { return 1.0f; }

class Gui
{
public:
    Gui() : mUserScale(1.0f), mFontScaledDisplaySize(0.0f, 0.0f), mFontsScaled(false) {}
    void updateResourceScaling(const CEGUI::Sizef& displaySize);
    float mUserScale;
    CEGUI::Sizef mFontScaledDisplaySize;
    bool mFontsScaled;
};
'''

MAIN = r'''
static int totalUpdates()
{
    int updates = 0;
    for(CEGUI::Font* font : CEGUI::FontManager::getSingleton().mFonts)
        updates += font->d_updates;
    return updates;
}

static void requireRendered(const Gui& gui, const CEGUI::Sizef& display)
{
    const CEGUI::Sizef native(FONT_DESIGN_WIDTH / gui.mUserScale, FONT_DESIGN_HEIGHT / gui.mUserScale);
    for(CEGUI::Font* font : CEGUI::FontManager::getSingleton().mFonts)
    {
        assert(font->d_rendered.mNative == native);
        assert(font->d_rendered.mMode == CEGUI::ASM_Min);
        assert(font->d_rendered.mDisplay == display);
    }
}

int main()
{
    CEGUI::FontManager& fonts = CEGUI::FontManager::getSingleton();
    CEGUI::gDisplay = CEGUI::Sizef(1920.0f, 1200.0f);
    fonts.mFonts.push_back(new CEGUI::Font(CEGUI::Sizef(800.0f, 600.0f), CEGUI::ASM_Disabled));
    fonts.mFonts.push_back(new CEGUI::Font(CEGUI::Sizef(1024.0f, 768.0f), CEGUI::ASM_Disabled));
    fonts.mFonts.push_back(new CEGUI::Font(CEGUI::Sizef(640.0f, 480.0f), CEGUI::ASM_Min));
    Gui gui;
    gui.mUserScale = 1.1f;

    gui.updateResourceScaling(CEGUI::gDisplay);
    requireRendered(gui, CEGUI::gDisplay);

    // The measured cause: every window registration rebuilt every font. Now repeated calls rebuild none.
    const int before = totalUpdates();
    for(int i = 0; i < 10; ++i)
        gui.updateResourceScaling(CEGUI::gDisplay);
    assert(totalUpdates() == before);
    requireRendered(gui, CEGUI::gDisplay);

    // A new window size still rescales every font.
    CEGUI::gDisplay = CEGUI::Sizef(1280.0f, 720.0f);
    gui.updateResourceScaling(CEGUI::gDisplay);
    requireRendered(gui, CEGUI::gDisplay);
    assert(totalUpdates() > before);

    // A new UI scale still rescales every font.
    gui.mUserScale = 1.2f;
    gui.updateResourceScaling(CEGUI::gDisplay);
    requireRendered(gui, CEGUI::gDisplay);

    // A font loaded later (its own native resolution, no auto scaling) gets the wanted scaling.
    fonts.mFonts.push_back(new CEGUI::Font(CEGUI::Sizef(1024.0f, 768.0f), CEGUI::ASM_Disabled));
    gui.updateResourceScaling(CEGUI::gDisplay);
    requireRendered(gui, CEGUI::gDisplay);

    const int settled = totalUpdates();
    for(int i = 0; i < 10; ++i)
        gui.updateResourceScaling(CEGUI::gDisplay);
    assert(totalUpdates() == settled);
    std::printf("gui font rescale probe passed (%d font rebuilds)\n", settled);
    return 0;
}
'''


def main():
    """Compiles the production Gui::updateResourceScaling with the CEGUI stand-ins and runs the probe."""
    source = PREAMBLE + constants + '\n\n' + production + '\n' + MAIN
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
    print('gui font rescale passes the checks')


if __name__ == '__main__':
    main()
