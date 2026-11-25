"""Cleanup of the level editor (package 4): layouts, menus, windows, console thread safety, wave condition.

Static text checks of the sources and layouts plus one small cl probe (the portal wave condition) and one run of
check_editor_headers.py without cl on the path. Every requirement is reported on its own with a fixed expected value.

Calls (from the repository root; cl must be on the path for C10, run it under vcvars64):
  python source/tests/check_editor_cleanup.py
"""
from pathlib import Path
import os
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

repo = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo / 'scripts'))
import content_packages  # noqa: E402

failures = []
#: True when the content packages are present: the layouts are read joined with their own rows
CONTENT = content_packages.has_content(repo)

# Fixed expected values
EXPECTED_SAVE_TITLE = 'Save Level'
EXPECTED_SAVE_AREA = (580, 535)           # absolute size of the save dialog: 290 + 290 by 267 + 268
EXPECTED_QUIT_SUBSCRIPTIONS = 1
EXPECTED_UNINSTALL_FUNCTIONS = ['uninstallCreaturesMenuButtons', 'uninstallRecentlyUsedFilesButtons',
                                'uninstallSeatsMenuButtons']


def read(path):
    """Returns the text of a repository file."""
    return (repo / path).read_text(encoding='utf-8')


def read_data(path):
    """Returns the text of a game data file as the game reads it (with its own rows from the content)."""
    return content_packages.read_text(repo, path)


def check(condition, message):
    """Reports one requirement and remembers a failure."""
    print(('OK   ' if condition else 'FAIL ') + message)
    if not condition:
        failures.append(message)


def function_body(text, signature):
    """Returns the body (from the signature to the closing brace in column 0) of a function, or ''."""
    start = text.find(signature)
    if start < 0:
        return ''
    end = text.find('\n}\n', start)
    return text[start:end + 3] if end >= 0 else text[start:]


# C1 and C2: the save dialog
if CONTENT:
    save = ET.fromstring(read_data('gui/EditorSave.layout'))
    frame = [w for w in save.iter('Window') if w.get('name') == 'LevelWindowFrame'][0]
    props = dict((p.get('name'), p.get('value')) for p in frame.findall('Property'))
    check(props.get('Text') == EXPECTED_SAVE_TITLE, 'C1 the save dialog title is "%s" (found "%s")'
          % (EXPECTED_SAVE_TITLE, props.get('Text')))
    numbers = [float(n) for n in re.findall(r'-?\d+(?:\.\d+)?', props['Area'])]
    area = (numbers[5] - numbers[1], numbers[7] - numbers[3])      # {{0.5,x1},{0.5,y1},{0.5,x2},{0.5,y2}}
    min_numbers = [float(n) for n in re.findall(r'-?\d+(?:\.\d+)?', props['MinSize'])]
    min_size = (min_numbers[1], min_numbers[3])
    check(area == EXPECTED_SAVE_AREA, 'C2 the save dialog area is %s (found %s)' % (EXPECTED_SAVE_AREA, area))
    check(min_size[0] <= area[0] and min_size[1] <= area[1],
          'C2 MinSize %s of the save dialog is not larger than its area %s' % (min_size, area))
else:
    content_packages.unchecked('check_editor_cleanup', ['C1 and C2 the save dialog of EditorSave.layout'])

editor = read('source/modes/EditorMode.cpp')
editor_h = read('source/modes/EditorMode.h')

# C3: QuitEditorButton is subscribed once
quit_count = editor.count('EditorOptionsWindow/QuitEditorButton')
check(quit_count == EXPECTED_QUIT_SUBSCRIPTIONS, 'C3 QuitEditorButton is subscribed %d time (found %d)'
      % (EXPECTED_QUIT_SUBSCRIPTIONS, quit_count))

# C4: every uninstall* destroys the windows it removes
for name in EXPECTED_UNINSTALL_FUNCTIONS:
    body = function_body(editor, 'void EditorMode::' + name + '()')
    check('destroyWindow' in body, 'C4 EditorMode::%s calls destroyWindow' % name)
all_uninstall = re.findall(r'void EditorMode::(uninstall\w+)\(', editor)
check(sorted(all_uninstall) == sorted(EXPECTED_UNINSTALL_FUNCTIONS),
      'C4 EditorMode has exactly the uninstall functions %s (found %s)' % (EXPECTED_UNINSTALL_FUNCTIONS, all_uninstall))

# C5: console output from the Python thread reaches CEGUI only on the main thread
console = read('source/modes/GameEditorModeConsole.cpp')
print_body = function_body(console, 'void GameEditorModeConsole::printToConsole(')
check(print_body != '' and 'CEGUI' not in print_body and 'mConsoleHistoryWindow' not in print_body
      and 'ListboxTextItem' not in print_body,
      'C5 printToConsole makes no CEGUI call itself')
check('lock_guard' in print_body and 'mOutputQueue' in print_body, 'C5 printToConsole queues the text under a mutex')
flush_body = function_body(console, 'void GameEditorModeConsole::flushConsoleOutput(')
check('addItem' in flush_body, 'C5 flushConsoleOutput adds the lines to the history window')
check(re.search(r'!\s*\w+\.empty\(\)\s*&&\s*\w+\[\w+\.length\(\)\s*-\s*1\]', flush_body) is not None,
      'C5 the last character is read only after an empty check')
base = read('source/modes/GameEditorModeBase.cpp')
check('mConsole->flushConsoleOutput()' in function_body(base, 'void GameEditorModeBase::onFrameStarted('),
      'C5 the main thread flushes the console output every frame')

# C6: Rotate, About and the three "Not implemented yet" entries are gone (F3)
if CONTENT:
    layout = read_data('gui/ModeEditor.layout')
    options = read_data('gui/WindowEditorOptions.layout')
    for name in ('Rotate', 'About'):
        check('name="%s"' % name not in layout, 'C6 the editor menu has no %s entry' % name)
    check('Not implemented yet' not in options, 'C6 the editor options window has no "Not implemented yet" entry')
    for name in ('NewLevelButton', 'LoadLevelButton', 'LevelPropertiesButton'):
        check(name not in options and name not in editor, 'C6 %s is gone from layout and code' % name)
else:
    for name in ('NewLevelButton', 'LoadLevelButton', 'LevelPropertiesButton'):
        check(name not in editor, 'C6 %s is gone from the code' % name)
    content_packages.unchecked('check_editor_cleanup', ['C6 the entries of ModeEditor.layout and '
                                                        'WindowEditorOptions.layout'])
check('"Rotate"' not in editor and '"About"' not in editor, 'C6 no handler subscribes to Rotate or About')

# C7: no spell leftovers
check_body = function_body(editor, 'void EditorMode::checkInputCommand(')
check(check_body != '' and 'castSpell' not in check_body, 'C7 checkInputCommand has no castSpell case')
check('castSpell' not in editor, 'C7 EditorMode.cpp has no castSpell')
check('Rooms, traps, spells' not in editor and 'room/trap/spell' not in editor,
      'C7 the two comments no longer mention spells')

# C8: the load dialog
load = read('source/modes/MenuModeEditorLoad.cpp')
check('SKM_' not in load, 'C8 MenuModeEditorLoad uses no SKM_ constant')
check('window->getChild(Gui::EDM_LIST_LEVELS)' in function_body(load, 'bool MenuModeEditorLoad::updateDescription('),
      'C8 updateDescription uses Gui::EDM_LIST_LEVELS')
gui_cpp = read('source/render/Gui.cpp')
constants = dict(re.findall(r'const std::string Gui::(\w+) = "([^"]*)";', gui_cpp))
used = set()
for constant in re.findall(r'Gui::(EDM_\w+)', load):
    if constant in constants:
        used.add(constants[constant])
for literal in re.findall(r'getChild\("([^"]+)"\)', load):
    used.add(literal)
paths = set()


def collect(node, prefix):
    """Collects the slash separated names of all windows below a layout node."""
    for child in node.findall('Window'):
        full = prefix + child.get('name')
        paths.add(full)
        collect(child, full + '/')


if CONTENT:
    load_layout = ET.fromstring(read_data('gui/MenuEditorLoad.layout'))
    collect(load_layout.find('Window'), '')
    missing = sorted(p for p in used if p not in paths)
    check(len(used) == 7 and not missing,
          'C8 every widget of MenuModeEditorLoad exists in MenuEditorLoad.layout (%d used, missing: %s)'
          % (len(used), missing))
else:
    content_packages.unchecked('check_editor_cleanup', ['C8 the widgets of MenuEditorLoad.layout'])

# C9: the bar layout check no longer looks at a spells page
bar = read('source/tests/check_editor_bar_layout.py')
check("'Spells'" not in bar and 'WindowTabSpells' not in bar, 'C9 check_editor_bar_layout.py checks no spells page')

# C10: the wave list condition, compiled from the source text
portal = read('source/rooms/RoomPortalWave.cpp')
add_body = function_body(portal, 'void RoomPortalWave::addRoomPortalWaveData(')
match = re.search(r'if\((.*?)\)\s*\{\s*mRoomPortalWaveDataSpawnable', add_body, re.S)
if match is None:
    check(False, 'C10 the spawnable condition of addRoomPortalWaveData was found')
elif shutil.which('cl') is None:
    check(False, 'C10 cl is not on the path: run this check under vcvars64')
else:
    condition = match.group(1).replace('roomPortalWaveData->', 'w.')
    probe = r"""
#include <cstdint>
#include <cstdio>
struct W { int64_t mSpawnTurnMin; int64_t mSpawnTurnMax; };
static bool spawnable(int64_t min, int64_t max, int64_t curTurn)
{
    W w = { min, max };
    return @@COND@@;
}
int main()
{
    // min, max, current turn, expected
    const int64_t cases[][4] = {
        {0, -1, 0, 1}, {0, -1, 5, 1}, {5, -1, 3, 0}, {5, -1, 5, 1}, {3, 10, 5, 1}, {3, 10, 2, 0}, {3, 10, 11, 0},
        {5, 5, 5, 1}, {0, 0, 0, 1}, {0, 3, 0, 1}, {1, 3, 0, 0}
    };
    int bad = 0;
    for(const int64_t* c : cases)
        if(spawnable(c[0], c[1], c[2]) != (c[3] != 0))
        {
            std::printf("case %lld %lld %lld expected %lld\n", (long long)c[0], (long long)c[1], (long long)c[2], (long long)c[3]);
            ++bad;
        }
    return bad;
}
""".replace('@@COND@@', condition)
    with tempfile.TemporaryDirectory(prefix='odp-cleanup-') as directory:
        work = Path(directory)
        (work / 'probe.cpp').write_text(probe)
        build = subprocess.run(['cl', '/nologo', '/EHsc', '/MD', 'probe.cpp', '/Feprobe.exe'], cwd=work,
                               capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=300)
        if build.returncode != 0:
            check(False, 'C10 the probe compiles: ' + build.stdout[-300:])
        else:
            run = subprocess.run([str(work / 'probe.exe')], cwd=work, capture_output=True, text=True,
                                 stdin=subprocess.DEVNULL, timeout=60)
            check(run.returncode == 0, 'C10 11 wave cases give the expected spawnable result ' + run.stdout.strip())

# C11: check_editor_headers.py reports a missing cl clearly
# Without the content check_editor_headers.py names its probe as not checked before it looks for cl
if CONTENT:
    headers = repo / 'source/tests/check_editor_headers.py'
    empty = tempfile.mkdtemp(prefix='odp-nopath-')
    env = dict(os.environ)
    env['PATH'] = empty
    run = subprocess.run([sys.executable, str(headers)], env=env, capture_output=True, text=True,
                         stdin=subprocess.DEVNULL, timeout=120)
    shutil.rmtree(empty, ignore_errors=True)
    output = run.stdout + run.stderr
    check(run.returncode != 0 and 'vcvars64' in output and 'Traceback' not in output,
          'C11 check_editor_headers.py without cl on the path fails with a message naming vcvars64, no traceback')
else:
    content_packages.unchecked('check_editor_cleanup', ['C11 the missing cl message of check_editor_headers.py'])

# D1-D5: small deferred items
loading = read('source/render/LoadingScreen.cpp')
check('"LevelMessageText"' in loading and '"LevelTypeText"' not in loading,
      'D1 findLoadingText looks for the New dialog status in LevelMessageText')
lines = editor.split('\n')
index = [i for i, l in enumerate(lines) if l.startswith('bool EditorMode::showNewLevelDialog(')][0]
check(lines[index - 1].startswith('//!'), 'D2 showNewLevelDialog has a Doxygen comment')
index = [i for i, l in enumerate(lines) if l.startswith('EditorMode::EditorMode(')][0]
check(any(l.startswith('//!') and 'New' in l and 'dialog' in l for l in lines[max(0, index - 6):index]),
      'D2 the EditorMode constructor comment mentions the New dialog')
public_part = editor_h.split('protected:')[0]
check('protected:' in editor_h and 'void restoreAfterConsole() override;' not in public_part
      and 'void restoreAfterConsole() override;' in editor_h,
      'D3 EditorMode::restoreAfterConsole is protected')
map_handler = read('source/gamemap/MapHandler.cpp')
hidden_option = function_body(map_handler, 'bool isEditOfficialLevelsEnabled()')
check('value.end(), ::tolower' not in hidden_option and 'static_cast<unsigned char>' in hidden_option, 'D4 the tolower in MapHandler takes an unsigned char')

print('%d failure(s)' % len(failures))
sys.exit(1 if failures else 0)
