"""Static check: the editor paths that used to crash on null pointers or file system exceptions are guarded.

Requirements checked (each reported on its own):
  A1  EditorMode::launchNewLevelPressed validates every input (title included) before it tears the level down;
      stopTileCulling and the minimap are used only after a null test (also in loadLevelFromFile and onMinimapClick)
  A2  onEditDelete clears mMouseDownOnDraggableTileContainer; the client ignores the rounded-position answer
      when no draggable tile container exists
  A3  editorAskChangeTile drops the packet when getTile gives nullptr
  A4  CopyRoom, CopyTrap, RevealTiles, RevealRooms and RevealTraps stop when mDraggableTileContainer is null
  A5  RoomManager::buildRoomEditor and TrapManager::buildTrapEditor return false for a missing factory;
      the failure log of the copy cases does not read the seat of the player unguarded
  A6  saving on the server uses error_code overloads and catches exceptions, and the player is told in the chat
It does not start a game and compiles nothing."""
from pathlib import Path
import re
import sys

repo = Path(__file__).resolve().parents[2]


def function(text, start):
    end = text.index('{', start) + 1
    depth = 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


def strip_comments(text):
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    return re.sub(r'//[^\n]*', '', text)


def read(path):
    return strip_comments((repo / path).read_text(encoding='utf-8', errors='replace'))


def case_body(text, name):
    start = text.index('case ClientNotificationType::%s:' % name)
    return function(text, start)


failures = []


def check(condition, message):
    if not condition:
        failures.append(message)


def before(text, first, second):
    a, b = text.find(first), text.find(second)
    return a != -1 and b != -1 and a < b


editor = read('source/modes/EditorMode.cpp')
base = read('source/modes/GameEditorModeBase.cpp')
client = read('source/network/ODClient.cpp')
server = read('source/network/ODServer.cpp')

# A1
launch = function(editor, editor.index('bool EditorMode::launchNewLevelPressed('))
check('levelTitle.empty()' in launch and before(launch, 'levelTitle.empty()', 'stopTileCulling'),
      'A1 launchNewLevelPressed checks the title before stopTileCulling')
check(before(launch, 'Invalid map size', 'stopTileCulling') and before(launch, 'exists(level)', 'stopTileCulling'),
      'A1 launchNewLevelPressed checks the filename, existence and size before stopTileCulling')
check(re.search(r'mMainCullingManager\s*!=\s*nullptr\s*\)\s*mMainCullingManager->stopTileCulling', launch) is not None,
      'A1 launchNewLevelPressed tests mMainCullingManager for nullptr before stopTileCulling')
load = function(editor, editor.index('bool EditorMode::loadLevelFromFile('))
check(re.search(r'mMainCullingManager\s*!=\s*nullptr\s*\)\s*mMainCullingManager->stopTileCulling', load) is not None,
      'A1 loadLevelFromFile tests mMainCullingManager for nullptr before stopTileCulling')
click = function(base, base.index('bool GameEditorModeBase::onMinimapClick('))
check('mMiniMap == nullptr' in click and before(click, 'mMiniMap == nullptr', 'mMiniMap->camera_2dPositionFromClick'),
      'A1 onMinimapClick tests mMiniMap for nullptr before it is used')

# A2
delete = function(editor, editor.index('void EditorMode::onEditDelete('))
check('mMouseDownOnDraggableTileContainer = false' in delete,
      'A2 onEditDelete clears mMouseDownOnDraggableTileContainer')
start = client.index('case ServerNotificationType::pingEditorAskSetRoundedPositionDraggableTileContainer:')
rounded = function(client, start)
check(before(rounded, 'draggableTileContainer == nullptr', 'setRoundedPosition'),
      'A2 the client ignores the rounded-position answer when the draggable tile container is null')

# A3
change = case_body(server, 'editorAskChangeTile')
check(re.search(r'selectedTile\s*==\s*nullptr', change) is not None
      and before(change, 'selectedTile == nullptr', 'selectedTile->'),
      'A3 editorAskChangeTile drops the packet when getTile gives nullptr')

# A4
for name in ('editorAskCopyRoom', 'editorAskCopyTrap', 'editorAskRevealTiles', 'editorAskRevealRooms',
             'editorAskRevealTraps'):
    body = case_body(server, name)
    first = body.find('mDraggableTileContainer')
    guard = re.match(r'mDraggableTileContainer\s*==\s*nullptr\s*\)\s*\{[^}]*break;', body[first:])
    check(guard is not None, 'A4 %s stops when mDraggableTileContainer is null (guard before any use)' % name)

# A5
for path, cls, fn, fac in (('source/rooms/RoomManager.cpp', 'RoomManager', 'buildRoomEditor', 'Room'),
                           ('source/traps/TrapManager.cpp', 'TrapManager', 'buildTrapEditor', 'Trap')):
    text = read(path)
    body = function(text, text.index('bool %s::%s(' % (cls, fn)))
    guard = re.search(r'factories\[index\]\s*==\s*nullptr\s*\)\s*\{[^}]*return false;', body)
    check(guard is not None and guard.start() < body.index('*factories[index]'),
          'A5 %s::%s returns false for a null factory' % (cls, fn))
copy_cases = ''.join(case_body(server, n) for n in ('editorAskCopyRoom', 'editorAskCopyTrap'))
check(re.search(r'toString\(player->getSeat\(\)->getId\(\)\)', copy_cases) is None,
      'A5 the failure logs of CopyRoom and CopyTrap do not read the seat of the player unguarded')

# A6 (since the atomic save of check_editor_save.py D5, the file system calls live in SafeSave.h)
ask = case_body(server, 'askSaveMap')
safe = read('source/utils/SafeSave.h')
check('error_code' in safe and re.search(r'status\(target,\s*\w+\)', safe) is not None
      and re.search(r'rename\(tempPath,\s*target,\s*\w+\)', safe) is not None
      and 'SafeSave::replaceFile(' in ask,
      'A6 askSaveMap saves through SafeSave, which uses the error_code overloads of status and rename')
check('catch' in safe and before(safe, 'try', 'writer(') and before(safe, 'writer(', 'catch'),
      'A6 SafeSave catches an exception of the writer')
check('catch' in ask and before(ask, 'try', 'levelSave =') and before(ask, 'levelSave =', 'catch'),
      'A6 askSaveMap catches an exception while it builds the path to save')
check(before(ask, 'saveOk', '"msg.map.failed"') and 'chatServer' in ask,
      'A6 a failed save tells the player in the chat')

if failures:
    print('FAIL: %d requirement(s) not met:' % len(failures))
    for failure in failures:
        print('  - ' + failure)
    sys.exit(1)
print('OK: all editor crash guards are in place')
