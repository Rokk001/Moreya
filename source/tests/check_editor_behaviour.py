"""Check: the wrong behaviour of the level editor found by the audit is fixed (package 3).

    python source/tests/check_editor_behaviour.py        (cl must be on the path: run it under vcvars64)

Requirements checked (each reported on its own, expected values are fixed):
  B1  Mirror X is removed: no menu entry in ModeEditor.layout, no handler or subscription in EditorMode
  B2  the server drops editorAskCreateMapLight and editorAskDeleteDraggableTileContainer outside the editor mode
  B3  both New dialogs accept only sizes from 1 to 400 (compiled probe on the production header MapSizeInput.h,
      static wiring in EditorMode and MenuModeEditorNew) and evaluate the result of createNewMap
  B4  after a load or a new level the editor drops the copy block, the tile marker, the selected seat and the wave window
  B5  leaving the console restores the editor view without activate(): the selected seat and the file dialog paths stay
  B6  onPortalWaveRemoveWave reads the typed values (readPortalWaveWindow) before it removes the wave
  B7  the Back button of the New dialog of the editor closes the dialog like the X button
  B8  the messages of the New dialog stand in their own text field and no longer overwrite the "Level Type:" label
It compiles one small probe with cl for B3 and starts no game."""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

repo = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo / 'scripts'))
import content_packages  # noqa: E402
failures = []


def check(condition, message):
    if not condition:
        failures.append(message)


def strip_comments(text):
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    return re.sub(r'//[^\n]*', '', text)


def raw(path):
    return (repo / path).read_text(encoding='utf-8', errors='replace')


def read(path):
    return strip_comments(raw(path))


def function(text, start):
    end = text.index('{', start) + 1
    depth = 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


def before(text, first, second):
    a, b = text.find(first), text.find(second)
    return a != -1 and b != -1 and a < b


def func(text, signature):
    index = text.find(signature)
    return function(text, index) if index != -1 else ''


editor = read('source/modes/EditorMode.cpp')
editor_h = read('source/modes/EditorMode.h')
base = read('source/modes/GameEditorModeBase.cpp')
base_h = read('source/modes/GameEditorModeBase.h')
server = read('source/network/ODServer.cpp')
menu_new = read('source/modes/MenuModeEditorNew.cpp')
# The editor layouts as the game reads them, with their own rows from the content package core-gui; without the
# content the own rows (the LevelMessageText field) are not there and B8 of the layout is named as not checked
layout = content_packages.read_text(repo, 'gui/ModeEditor.layout')
new_layout = content_packages.read_text(repo, 'gui/EditorNew.layout')
if not content_packages.has_content(repo):
    content_packages.unchecked('check_editor_behaviour', ['gui/EditorNew.layout LevelMessageText (B8)'])

# B1
check('MirrorX' not in layout, 'B1 ModeEditor.layout has no MirrorX menu entry')
check('MirrorX' not in editor and 'MirrorX' not in editor_h, 'B1 EditorMode has no MirrorX handler or subscription')

# B2
mode_test = r'mServerMode\s*!=\s*ServerMode::ModeEditor'
for name, acts in (('editorAskCreateMapLight', 'new MapLight'),
                   ('editorAskDeleteDraggableTileContainer', 'delete mDraggableTileContainer')):
    body = function(server, server.index('case ClientNotificationType::%s:' % name))
    match = re.search(mode_test, body)
    check(match is not None and body.find(acts) > match.start() and 'break;' in body[match.start():body.find(acts)],
          'B2 %s is dropped outside the editor mode before it acts' % name)

# B3
header = repo / 'source/utils/MapSizeInput.h'
check(header.exists(), 'B3 source/utils/MapSizeInput.h exists')
probe = r"""
#include "utils/MapSizeInput.h"
#include <iostream>
#include <string>
static int failures = 0;
static void expect(const std::string& text, bool ok, int32_t value)
{
    int32_t size = -7;
    bool result = MapSizeInput::parse(text, size);
    if(result != ok || (ok && size != value))
    {
        std::cout << "case '" << text << "' gave " << result << "/" << size << std::endl;
        ++failures;
    }
}
int main()
{
    expect("1", true, 1);
    expect("100", true, 100);
    expect("400", true, 400);
    expect(" 25 ", true, 25);
    expect("0", false, 0);
    expect("401", false, 0);
    expect("", false, 0);
    expect("   ", false, 0);
    expect("abc", false, 0);
    expect("-5", false, 0);
    expect("+5", false, 0);
    expect("12x", false, 0);
    expect("1.5", false, 0);
    expect("99999999999999999999", false, 0);
    expect("4294967297", false, 0);
    expect("0400", true, 400);
    if(MapSizeInput::MAX_SIZE != 400)
        ++failures;
    std::cout << failures << " failures" << std::endl;
    return failures;
}
"""
if header.exists():
    with tempfile.TemporaryDirectory() as work:
        work = Path(work)
        (work / 'probe.cpp').write_text(probe)
        build = subprocess.run(['cl', '/nologo', '/EHsc', '/MD', '/std:c++14', '/I' + str(repo / 'source'),
                                str(work / 'probe.cpp'), '/Fe:' + str(work / 'probe.exe')], cwd=work,
                               capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=300)
        if build.returncode != 0:
            check(False, 'B3 the MapSizeInput probe compiles: ' + build.stdout[-400:])
        else:
            run = subprocess.run([str(work / 'probe.exe')], cwd=work, capture_output=True, text=True,
                                 stdin=subprocess.DEVNULL, timeout=60)
            check(run.returncode == 0, 'B3 MapSizeInput::parse accepts 1..400 only: ' + run.stdout.strip())
launch = func(editor, 'bool EditorMode::launchNewLevelPressed(')
for label, text, sig in (('EditorMode', editor, 'bool EditorMode::launchNewLevelPressed('),
                         ('MenuModeEditorNew', menu_new, 'bool MenuModeEditorNew::launchSelectedButtonPressed(')):
    body = func(text, sig)
    check(body.count('MapSizeInput::parse(') == 2,
          'B3 %s parses width and height with MapSizeInput::parse' % label)
    check(re.search(r'if\s*\(\s*!\s*gameMap->createNewMap\(', body) is not None,
          'B3 %s evaluates the result of createNewMap' % label)
    check('toUInt32' not in body, 'B3 %s no longer reads the size with toUInt32' % label)
check(before(launch, 'MapSizeInput::parse(', 'stopTileCulling'),
      'B3 EditorMode validates the size before the level is torn down')

# B4
reset = func(editor, 'void EditorMode::resetStateAfterLevelChange(')
check(reset != '' and 'delete draggableTileContainer' in reset and 'draggableTileContainer = nullptr' in reset
      and 'mMouseDownOnDraggableTileContainer = false' in reset,
      'B4 resetStateAfterLevelChange drops the copy block of the client')
check('mTileMarker.isVisible = false' in reset, 'B4 resetStateAfterLevelChange hides the tile marker')
check('unselectAllTiles()' in reset, 'B4 resetStateAfterLevelChange clears the tile selection')
check(re.search(r'[sS]eatIdSelected\s*=', reset) is not None and 'getLocalPlayer()' in reset
      and 'updateFlagColor()' in reset and 'updateCursorText()' in reset,
      'B4 resetStateAfterLevelChange selects the seat of the local player and refreshes flag and cursor text')
stop = func(server, 'void ODServer::stopServer(')
check(before(stop, 'delete mDraggableTileContainer', 'clearAll()') and 'mDraggableTileContainer = nullptr' in stop,
      'B4 ODServer::stopServer deletes the server copy block (it holds seats of the old level) before clearAll')
check('getSeatById(seatIdSelected) == nullptr' in reset and 'getSeats().front()' in reset,
      'B4 resetStateAfterLevelChange falls back to an existing seat when there is no local seat')
flag = func(editor, 'void EditorMode::updateFlagColor(')
check(before(flag, 'seat == nullptr', 'getColorValue'),
      'B4 updateFlagColor returns when the selected seat does not exist')
check('hidePortalWaveWindow()' in reset, 'B4 resetStateAfterLevelChange closes the wave window')
load = func(editor, 'bool EditorMode::loadLevelFromFile(')
check('resetStateAfterLevelChange()' in load, 'B4 loadLevelFromFile resets the editor state')
check('resetStateAfterLevelChange()' in launch, 'B4 launchNewLevelPressed resets the editor state')

# B5
leave = func(base, 'void GameEditorModeBase::leaveConsole(')
check(leave != '' and re.search(r'(?<![\w:])activate\(\)', leave) is None,
      'B5 GameEditorModeBase::leaveConsole does not call activate()')
restore = func(editor, 'void EditorMode::restoreAfterConsole(')
check(restore != '' and 'loadGuiSheet' in restore and 'giveFocus()' in restore and 'updateFlagColor()' in restore
      and 'updateCursorText()' in restore,
      'B5 EditorMode::restoreAfterConsole restores sheet, focus, flag and cursor text')
check('mSeatIdSelected' not in restore and 'FilePath' not in restore,
      'B5 EditorMode::restoreAfterConsole leaves the selected seat and the file dialog paths alone')
check('restoreAfterConsole' in base_h and 'restoreAfterConsole' in editor_h and 'restoreAfterConsole' in leave,
      'B5 leaveConsole calls the virtual restoreAfterConsole')

# B6
remove = func(editor, 'bool EditorMode::onPortalWaveRemoveWave(')
check(before(remove, 'readPortalWaveWindow()', 'erase('), 'B6 onPortalWaveRemoveWave reads the typed values before erase')

# B7
check(re.search(r'getChild\("LevelWindowFrame/BackButton"\)->subscribeEvent\(\s*CEGUI::PushButton::EventClicked,'
                r'\s*CEGUI::Event::Subscriber\(&EditorMode::hideNewLevelDialog', editor) is not None,
      'B7 EditorMode closes the New dialog with its Back button')

# B8
check(not content_packages.has_content(repo) or 'type="OD/StaticText" name="LevelMessageText"' in new_layout,
      'B8 EditorNew.layout has a LevelMessageText static text')
check(re.search(r'LevelTypeText"\)\s*->\s*setText', launch) is None and 'LevelMessageText' in launch,
      'B8 launchNewLevelPressed writes its messages to LevelMessageText, not to the "Level Type:" label')

if failures:
    print('FAIL: %d requirement(s) not met:' % len(failures))
    for failure in failures:
        print('  - ' + failure)
    sys.exit(1)
print('OK: the editor behaviour fixes are in place')
