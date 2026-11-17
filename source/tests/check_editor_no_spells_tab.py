"""The level editor shows no spells tab; the game keeps its spells tab.

Casting a spell in the editor never did anything (the editor's castSpell case was an empty placeholder), so the tab
leaves the editor. The checks read the layouts and the code that is shared by the game and the editor:
- gui/ModeEditor.layout imports the room, trap and creature tabs but not WindowTabSpells.layout; gui/ModeGame.layout
  still imports it;
- the editor arranges only its rooms and traps pages;
- the code that the editor runs for every skill (SkillManager connecting the spells' cast buttons and
  EditorMode::refreshGuiSkill showing the cast buttons) skips a cast button the sheet does not have, so the editor
  starts without the tab.

Plain source check, no compiler, no game. Expected: 0 spells tab imports in the editor layout, 1 in the game layout.

Calls (from the repository root):
  python source/tests/check_editor_no_spells_tab.py
"""
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[2]

SPELLS_IMPORT = 'filename="WindowTabSpells.layout"'
# Spells tab imports: none in the editor, one in the game
EXPECTED_EDITOR_IMPORTS = 0
EXPECTED_GAME_IMPORTS = 1

errors = []


def read(path):
    """Returns the text of a repository file."""
    return (root / path).read_text(encoding='utf-8')


editor_layout = read('gui/ModeEditor.layout')
game_layout = read('gui/ModeGame.layout')
if editor_layout.count(SPELLS_IMPORT) != EXPECTED_EDITOR_IMPORTS:
    errors.append('gui/ModeEditor.layout: expected %d spells tab imports, found %d'
                  % (EXPECTED_EDITOR_IMPORTS, editor_layout.count(SPELLS_IMPORT)))
for tab in ('WindowTabRooms.layout', 'WindowTabTraps.layout', 'WindowTabCreatures.layout'):
    if 'filename="%s"' % tab not in editor_layout:
        errors.append('gui/ModeEditor.layout: %s is missing' % tab)
if game_layout.count(SPELLS_IMPORT) != EXPECTED_GAME_IMPORTS:
    errors.append('gui/ModeGame.layout: expected %d spells tab import, found %d'
                  % (EXPECTED_GAME_IMPORTS, game_layout.count(SPELLS_IMPORT)))

gui = read('source/render/Gui.cpp')
editor_pages = gui[gui.index('void Gui::arrangeEditorActionButtons('):]
editor_pages = editor_pages[:editor_pages.index('\n}\n')]
if 'const char* pages[] = {"MainTabControl/Rooms", "MainTabControl/Traps"};' not in editor_pages:
    errors.append('Gui::arrangeEditorActionButtons must arrange only the rooms and traps pages')

skills = read('source/game/SkillManager.cpp')
spell_connect = skills[skills.index('static const std::string guiPath = "MainTabControl/Spells/";') - 1200:
                       skills.index('static const std::string guiPath = "MainTabControl/Spells/";')]
if 'if(!rootWindow->isChild(getGuiPath() + mButtonName))\n            return;' not in spell_connect:
    errors.append('SkillManager: the spells must skip a cast button the sheet does not have')

editor = read('source/modes/EditorMode.cpp')
refresh = editor[editor.index('void EditorMode::refreshGuiSkill()'):]
refresh = refresh[:refresh.index('\n}\n')]
if 'if(!castButtonName.empty() && guiSheet->isChild(castButtonName))' not in refresh:
    errors.append('EditorMode::refreshGuiSkill must skip a cast button the editor sheet does not have')

for error in errors:
    print('FAIL: ' + error)
if errors:
    sys.exit(1)
print('OK: the editor has no spells tab, the game keeps it')
