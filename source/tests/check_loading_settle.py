"""Check that the loading picture of a map load covers the map's first-use work (frame stall cause: map load frames).

Measured cause (INGAME-QS-10 P1, deployed build 2026-11-17): the loading picture ended in ModeManager::checkModeChange
right when the game mode opened, but the new map still created its tile entities, loaded first-use textures and built
shaders in the next frames. The procedure dry run (Brackenford save) logged them as game frames of 648, 205, 1507 and
608 ms (refreshVisibleTiles 801 ms, startGameMode follow-up, first CEGUI render), the owner's games 765, 190 and 1554 ms.

1. Wiring (read from the sources): both map-load mode changes call LoadingScreen::finishAfterSettling instead of
   finish(); every sampled frame goes to LoadingScreen::onFrame; a frame drawn while the picture covers the window is
   not counted as a game frame; LoadingScreen::finish() stops any wait.
2. Outcome (compiled probe of the production LoadingSettle.h): fed with the measured frame sequence of the dry run
   (648, 205 ms, 14 frames of 17 ms at the start turn, 1507 ms, 608 ms at the next turn, then 17 ms frames) the picture
   ends only after the 1507 and 608 ms frames, three quick frames after the first new turn; it ends exactly once; the
   editor and a paused game end after three quick frames without a turn; a game whose turn never advances ends after
   6 s of frames; a slow frame restarts the count of quick frames.

Fixed values: 3 quick frames, 50 ms quick limit, 6 s limit, the dry run frame sequence above. The probe compiles with
cl, so part 2 runs in the compile phase of the integration only; part 1 needs no compiler.
"""
from pathlib import Path
import subprocess
import sys
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


def wiring():
    """Part 1: the picture of a map load ends only through the settle wait, and its frames are not game frames."""
    modes = block(read('source/modes/ModeManager.cpp'), 'void ModeManager::checkModeChange()')
    assert 'LoadingScreen::finish();' not in modes
    assert modes.count('LoadingScreen::finishAfterSettling(mRequestedMode == GAME);') == 2
    listener = block(read('source/render/ODFrameListener.cpp'), 'bool ODFrameListener::frameStarted(')
    assert '!LoadingScreen::isShown()' in listener[:listener.index('mFrameStatistics.sampleFrame(')]
    assert listener.index('mFrameStatistics.sampleFrame(') < listener.index(
        'LoadingScreen::onFrame(frameSeconds, mGameMap->getTurnNumber(), mGameMap->getGamePaused());')
    screen = read('source/render/LoadingScreen.cpp')
    assert 'mapLoadSettle.stop();' in block(screen, 'void LoadingScreen::finish()')
    assert 'mapLoadSettle.start(waitForTurn);' in block(screen, 'void LoadingScreen::finishAfterSettling(')
    on_frame = block(screen, 'void LoadingScreen::onFrame(')
    assert 'if(mapLoadSettle.frame(seconds, turn, paused))' in on_frame and 'finish();' in on_frame


PROBE = r'''
#include "LoadingSettle.h"

#include <cassert>
#include <cstdio>
#include <vector>

struct Frame
{
    double mSeconds;
    long long mTurn;
};

//! Feeds frames until the picture ends; returns the index of the ending frame or -1.
static int run(LoadingSettle& settle, const std::vector<Frame>& frames, bool paused)
{
    int ended = -1;
    for(size_t i = 0; i < frames.size(); ++i)
    {
        if(settle.frame(frames[i].mSeconds, frames[i].mTurn, paused))
        {
            assert(ended == -1);
            ended = static_cast<int>(i);
        }
    }
    return ended;
}

int main()
{
    // The dry run of 2026-11-17: mode change frame, first CEGUI frame, 14 normal frames at the start turn,
    // refreshVisibleTiles 1507 ms, 608 ms at the next turn, then normal frames.
    std::vector<Frame> dryRun;
    dryRun.push_back(Frame{0.648, 1514});
    dryRun.push_back(Frame{0.205, 1514});
    for(int i = 0; i < 14; ++i)
        dryRun.push_back(Frame{0.017, 1514});
    dryRun.push_back(Frame{1.507, 1514});
    const int lastLoad = static_cast<int>(dryRun.size());
    dryRun.push_back(Frame{0.608, 1516});
    for(int i = 0; i < 20; ++i)
        dryRun.push_back(Frame{0.017, 1516});

    LoadingSettle game;
    game.start(true);
    const int ended = run(game, dryRun, false);
    assert(ended == lastLoad + 3);
    assert(!game.isActive());
    std::printf("game picture ends after frame %d, covering every frame over 100 ms\n", ended);

    // Editor and paused game: no turn needed, three quick frames after the mode change frame.
    std::vector<Frame> still;
    still.push_back(Frame{0.700, 0});
    still.push_back(Frame{0.300, 0});
    for(int i = 0; i < 10; ++i)
        still.push_back(Frame{0.017, 0});
    LoadingSettle editor;
    editor.start(false);
    assert(run(editor, still, false) == 4);
    LoadingSettle paused;
    paused.start(true);
    assert(run(paused, still, true) == 4);

    // A slow frame restarts the quick count.
    std::vector<Frame> jitter;
    jitter.push_back(Frame{0.500, 0});
    jitter.push_back(Frame{0.017, 0});
    jitter.push_back(Frame{0.017, 0});
    jitter.push_back(Frame{0.090, 0});
    for(int i = 0; i < 5; ++i)
        jitter.push_back(Frame{0.017, 0});
    LoadingSettle restart;
    restart.start(false);
    assert(run(restart, jitter, false) == 6);

    // A game whose turn never advances ends after 6 s of frames (360 frames of 1/60 s after the mode change frame).
    std::vector<Frame> stuck;
    stuck.push_back(Frame{0.500, 7});
    for(int i = 0; i < 400; ++i)
        stuck.push_back(Frame{1.0 / 60.0, 7});
    LoadingSettle limit;
    limit.start(true);
    const int limitEnd = run(limit, stuck, false);
    assert(limitEnd >= 359 && limitEnd <= 361);

    // Without start() nothing ends, and a stopped wait ends nothing.
    LoadingSettle idle;
    assert(run(idle, dryRun, false) == -1);
    LoadingSettle stopped;
    stopped.start(true);
    stopped.stop();
    assert(run(stopped, dryRun, false) == -1);
    std::printf("loading settle probe passed\n");
    return 0;
}
'''


def probe():
    """Part 2: compiles the production LoadingSettle.h into the probe and runs it."""
    vcvars = Path('C:/Program Files (x86)/Microsoft Visual Studio/18/BuildTools/VC/Auxiliary/Build/vcvars64.bat')
    with tempfile.TemporaryDirectory() as directory:
        directory = Path(directory)
        (directory / 'LoadingSettle.h').write_text(read('source/render/LoadingSettle.h'), encoding='utf-8')
        cpp = directory / 'probe.cpp'
        cpp.write_text(PROBE, encoding='utf-8')
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


def main():
    """Runs the wiring part and, unless --wiring-only is given, the compiled outcome probe."""
    wiring()
    print('loading settle wiring ok')
    if '--wiring-only' in sys.argv:
        return
    probe()
    print('loading settle passes the checks')


if __name__ == '__main__':
    main()
