"""Check that every in-game window and dialog uses the window frame of the chosen menu sheet and fits every screen.

Static check, no game and no compiler needed. The window frame is the frame of the load screen of the chosen menu sheet
(OD/SheetWindow: iron rails, corner brackets, knobs and the wood of the sheet, with the glowing title on the top rail
and the close button beside it). It checks the outcome:

1. Frame. Every window of the game and of the editor (the layouts the game and editor sheets import and the layouts the
   code loads while a game runs) that is a frame window draws the sheet frame: its look draws the frame pieces of the
   sheet (ODMenuTemplate Frame*) and none of the old frames (the forged game window frame, the ornate book frame, the
   skin window edges). Every message panel and the debriefing panel draw the same pieces. The titled windows show their
   title in the sheet title (OD/SheetTitlebar, centred caption). The expected numbers were counted once on this branch.
2. Code. The settings page in a running game is put into the sheet frame by the code, centred like the settings window
   of the main menu; the save browser of a running game shows the framed load panel of the sheet.
3. Buttons. The answer buttons of the confirm and message dialogs are buttons of the menu template.
4. Fit. At 640x480, 1024x768, 1920x1200 and 7680x4320 (8K), each with the UI scale 80 %, 100 % and 120 %, every in-game
   window lies on the screen and every control lies inside the client area of the sheet frame of its window, and no
   fixed caption is cut (geometry and font measurement of check_window_content_fit.py, which models the sheet frame).

Many layouts and the font files live in content packages (found through scripts/content_packages.py). Without the
content the check names every layout it could not read and the fit part as not checked, checks the public layouts
and the code, and leaves out the counts over all layouts (they need every layout); with the content every count runs.
"""
from pathlib import Path
import re
import sys
import time
import xml.etree.ElementTree as ET

STARTED = time.monotonic()
repo = Path(__file__).resolve().parents[2]
gui = repo / 'gui'
sys.path.insert(0, str(repo / 'scripts'))
import content_packages  # noqa: E402

WITH_CONTENT = content_packages.has_content(repo)
# Layouts and parts that need the content and are not checked because it is not present
not_checked = []


def gui_file(name):
    """A file of gui/ from the public tree or a content package, or None when the content is not present."""
    found = content_packages.data_file(repo, 'gui/' + name)
    if found is None and WITH_CONTENT:
        return gui / name   # fails below as before: the content is present but the file is missing
    if found is None and name not in not_checked:
        not_checked.append(name)
    return found

# ------------------------------------------------------------------------------------------------ in-game layouts
# Layouts the code loads by name while a game or the editor runs (each must be loaded so in the source).
CODE_LOADED = {'WindowStats.layout': 'source/render/Gui.cpp', 'WindowConsole.layout': 'source/render/Gui.cpp',
               'WindowDefeatDebriefing.layout': 'source/modes/GameMode.cpp',
               'WindowSettings.layout': 'source/modes/SettingsWindow.cpp',
               'WindowApplyChanges.layout': 'source/modes/SettingsWindow.cpp'}
# The shared creature profile page was deleted (owner decision 2026-11-18); nothing may load it any more
assert content_packages.data_file(repo, 'gui/WindowCreatureProfilePage.layout') is None
assert 'WindowCreatureProfilePage.layout' not in (repo / 'source/render/Gui.cpp').read_text(encoding='utf-8')
for layout, source in CODE_LOADED.items():
    assert 'loadLayoutFromFile("%s")' % layout in (repo / source).read_text(encoding='utf-8'), (layout, source)


def imports(layout, seen):
    """The layout and every layout it imports, recursively (a layout that is not present without the content is named
    as not checked and its own imports are not known)."""
    seen.add(layout)
    found = gui_file(layout)
    if found is None:
        return seen
    for entry in ET.parse(str(found)).getroot().iter('LayoutImport'):
        if entry.get('filename') not in seen:
            imports(entry.get('filename'), seen)
    return seen


INGAME = imports('ModeGame.layout', set()) | imports('ModeEditor.layout', set()) | set(CODE_LOADED)
# The build bar tabs, the room manager pages and the chat line are parts of windows or of the HUD, not windows; they
# are measured with their windows below. Counted once on this branch: 42 layouts (43 before INGAME-QS-12: the creature
# skill tree window of integration/all became the Skills page of the Dungeonbook with K7; 45 before INGAME-QS-11: the
# player information window left the game with K7, its KO setting is on the Game page of the settings window, and the
# shared creature profile page was deleted, owner decision 2026-11-18).
assert len(INGAME) == 42 or not WITH_CONTENT, (len(INGAME), sorted(INGAME))
assert 'WindowCreatureSkillTree.layout' not in INGAME and \
    content_packages.data_file(repo, 'gui/WindowCreatureSkillTree.layout') is None, \
    'the skill tree is a page of the Dungeonbook, no window of its own (INGAME-QS-12 K7)'

# ------------------------------------------------------------------------------------------------ looks
skin = ET.parse(str(gui_file('OD.looknfeel'))).getroot()
looks = {look.get('name'): look for look in skin.findall('WidgetLook')}
scheme = ET.parse(str(gui_file('ODSkin.scheme'))).getroot()
mapping = {m.get('windowType'): (m.get('lookNFeel'), m.get('targetType')) for m in scheme.findall('FalagardMapping')}


def find_section(look, name):
    """An imagery section of a look or of the looks it inherits from."""
    while look is not None:
        for section in looks[look].findall('ImagerySection'):
            if section.get('name') == name:
                return section
        look = looks[look].get('inherits')
    raise AssertionError('section %s not found' % name)


def find_states(look, names):
    """The state imageries of the given names, from the look or the looks it inherits from (nearest first)."""
    found = {}
    while look is not None:
        for state in looks[look].findall('StateImagery'):
            if state.get('name') in names and state.get('name') not in found:
                found[state.get('name')] = (look, state)
        look = looks[look].get('inherits')
    return found


def drawn_images(look, states):
    """Every image the given states of a look draw (sections of other looks followed)."""
    images = set()
    for state_look, state in find_states(look, states).values():
        for section in state.iter('Section'):
            for image in find_section(section.get('look', state_look), section.get('section')).iter('Image'):
                images.add(image.get('name'))
    return images


SHEET_FRAME = {'ODMenuTemplate/Frame' + part for part in ('TopLeft', 'TopRight', 'BottomLeft', 'BottomRight', 'Top',
                                                          'Bottom', 'Left', 'Right', 'Interior', 'TopKnob',
                                                          'BottomKnob')}
OLD_FRAMES = ('OpenDungeonsGameWindow/Frame', 'DungeonbookIcons/BookFrame', 'OpenDungeonsSkin/Window')
FRAME_STATES = {'ActiveWithTitleWithFrame', 'ActiveNoTitleWithFrame', 'InactiveWithTitleWithFrame',
                'ActiveWithTitleNoFrame', 'ActiveNoTitleNoFrame'}
PANEL_STATES = {'Enabled', 'EnabledFrame'}


def check_sheet_frame(look, states, what):
    """The look draws the whole sheet frame and nothing of an old frame in the given states."""
    images = drawn_images(look, states)
    assert SHEET_FRAME <= images, (what, look, 'misses', sorted(SHEET_FRAME - images))
    old = [name for name in images if name.startswith(OLD_FRAMES)]
    assert not old, (what, look, 'draws an old frame', old)


sheet_title = looks['OD/SheetWindow'].find("Child[@nameSuffix='__auto_titlebar__']")
assert sheet_title.get('type') == 'OD/SheetTitlebar'
caption = looks['OD/SheetTitlebar'].find(".//ImagerySection[@name='caption']/TextComponent")
assert caption.find('HorzFormat').get('type') == 'CentreAligned', 'the sheet title is centred'
assert 'OD/MenuTextButton' in {s.get('look') for s in looks['OD/SheetTitlebar'].iter('Section')}, 'the title glows'


def props(window):
    """Properties of a layout window."""
    return {p.get('name'): p.get('value') for p in window.findall('Property')}


# ------------------------------------------------------------------------------------------------ 1. frame
frame_windows = []
panels = []
for layout in sorted(INGAME):
    found = gui_file(layout)
    if found is None:
        continue
    root = ET.parse(str(found)).getroot()
    for window in root.iter('Window'):
        kind = window.get('type')
        look, target = mapping.get(kind, (None, None))
        look = props(window).get('LookNFeel', look)
        if target == 'CEGUI/FrameWindow':
            frame_windows.append((layout, window.get('name')))
            assert look == 'OD/SheetWindow', (layout, window.get('name'), 'is not in the sheet frame', look)
            check_sheet_frame(look, FRAME_STATES, (layout, window.get('name')))
            for key in props(window):
                assert not (key.startswith('Frame') and key.endswith('Image')) and key != 'TitlebarFont', \
                    (layout, window.get('name'), 'keeps a property of an old frame', key)
            assert window.find('AutoWindow') is None, (layout, window.get('name'), 'keeps the old title band')
            if props(window).get('TitlebarEnabled', 'True') == 'True' and props(window).get('Text'):
                hidden = props(window).get('CaptionColour', 'FF').upper()[:2] == '00'
                # only the Workers window hides the sheet title: the plaque of its chosen mockup shows the title
                assert not hidden or layout == 'WindowWorkers.layout', (layout, window.get('name'), 'hides its title')
        elif kind in ('OD/SheetPanel', 'OD/EventPanel'):
            panels.append((layout, window.get('name')))
            check_sheet_frame(look, PANEL_STATES, (layout, window.get('name')))
# Counted once on this branch: 24 frame windows (the quit confirmation is imported by the game and by the editor and
# counted once per layout file; the player information window is gone; 25 before INGAME-QS-12, whose K7 made the
# creature skill tree window a page of the Dungeonbook) and 3 panels (the message panels of game and editor, the
# debriefing panel).
# The counts and names over all layouts need every layout: with the content only.
if WITH_CONTENT:
    assert len(frame_windows) == 24, (len(frame_windows), frame_windows)
    assert sorted(panels) == [('WindowDefeatDebriefing.layout', 'Panel'), ('WindowEvent.layout', 'GameEventText'),
                              ('WindowGameEvent.layout', 'GameEventText')], panels
    # The windows the owner named are among them.
    named = {name for _layout, name in frame_windows}
    for window in ('RoomManagerWindow', 'SocialWindow', 'WorkersWindow', 'ObjectivesWindow', 'SkillTreeWindow',
                   'GameOptionsWindow', 'SettingsNavigationWindow', 'SettingsWindow', 'ConfirmExit', 'ConfirmLoad',
                   'ConfirmRestart', 'EditorOptionsWindow', 'EditorHelpWindow', 'EditorPortalWavesWindow',
                   'LevelWindowFrame'):
        assert window in named, window
else:
    not_checked.append('counts of the frame windows (24), the panels and the named windows')
# The Workers window shows its title on the painted plaque of its chosen mockup; the plaque sits on the top rail.
workers_file = gui_file('WindowWorkers.layout')
if workers_file is not None:
    workers = ET.parse(str(workers_file)).getroot().find('Window')
    assert [w for w in workers.findall('Window') if w.get('name') == 'TitlePlaque'], 'the Workers title plaque'
print('1. %d in-game frame windows and %d panels draw the sheet frame, no old frame left' % (len(frame_windows),
                                                                                             len(panels)))

# ------------------------------------------------------------------------------------------------ 2. code
settings = (repo / 'source/modes/SettingsWindow.cpp').read_text(encoding='utf-8')
menu_branch = settings.split('if(menuPages)', 1)[1].split('else if(gamePage)', 1)[0]
game_branch = settings.split('else if(gamePage)', 1)[1].split('mApplyWindow = ', 1)[0]
for branch, what in ((menu_branch, 'main menu'), (game_branch, 'game')):
    assert 'setLookNFeel("OD/SheetWindow")' in branch, what + ' settings page is not in the sheet frame'
    for part in ('CEGUI::UDim(0.5f, -MENU_WINDOW_HALF_WIDTH)', 'CEGUI::UDim(0.5f, -MENU_WINDOW_HALF_HEIGHT)',
                 'CEGUI::UDim(0.5f, MENU_WINDOW_HALF_WIDTH)', 'CEGUI::UDim(0.5f, MENU_WINDOW_HALF_HEIGHT)'):
        assert part in branch, (what, 'settings page is not centred', part)
assert 'OD/GameSettingsWindow' not in game_branch, 'the old full width game page'
load = ET.parse(str(gui_file('MenuLoad.layout'))).getroot()
panel = [w for w in load.iter('Window') if w.get('name') == 'LoadPanel']
assert panel and props(panel[0])['Image'] == 'ODMenuTemplate/LoadPanel', 'the save browser shows the sheet panel'
load_mode = (repo / 'source/modes/MenuModeLoad.cpp').read_text(encoding='utf-8')
assert 'LoadPanel' not in load_mode or 'LoadPanel")->hide' not in load_mode, 'the panel is hidden in the game'
print('2. settings page of the game centred in the sheet frame, save browser shows the sheet panel')

# ------------------------------------------------------------------------------------------------ 3. buttons
ANSWER_BUTTONS = {'WindowQuit.layout': ('YesOption', 'NoOption'), 'LoadConfirm.layout': ('YesOption', 'NoOption'),
                  'WindowSandboxRealm.layout': ('NextRealmButton', 'StayButton'),
                  'WindowApplyChanges.layout': ('CancelButton', 'ApplyButton'),
                  'WindowSettings.layout': ('CancelButton', 'ApplyButton'),
                  'EditorLoad.layout': ('BackButton', 'LoadButton'), 'EditorSave.layout': ('BackButton', 'SaveButton'),
                  'EditorNew.layout': ('BackButton', 'LaunchNewLevel')}
for layout, names in ANSWER_BUTTONS.items():
    found = gui_file(layout)
    if found is None:
        continue
    types = {w.get('name'): w.get('type') for w in ET.parse(str(found)).getroot().iter('Window')}
    for name in names:
        assert types[name] == 'OD/MenuTextButton', (layout, name, types[name])
print('3. %d answer buttons of %d dialogs are menu template buttons' % (
    sum(len(v) for v in ANSWER_BUTTONS.values()), len(ANSWER_BUTTONS)))

# ------------------------------------------------------------------------------------------------ 4. fit
# The geometry, the frame model of OD/SheetWindow and the caption measurement of check_window_content_fit.py, run on
# the in-game layouts at three UI scales.
# The font model measures with the font files of gui/fonts and walks every layout; without the content they are not all
# there.
FONT_FILES_MISSING = [font.name for font in sorted((gui / 'fonts').glob('*.font'))
                      if not (gui / 'fonts' / ET.parse(str(font)).getroot().get('filename')).is_file()]
if FONT_FILES_MISSING and not WITH_CONTENT:
    not_checked.append('4. fit of the in-game windows (font files of ' + ', '.join(FONT_FILES_MISSING) + ')')
else:
    fit_source = (repo / 'source/tests/check_window_content_fit.py').read_text(encoding='utf-8')
    marker = '\nall_problems = {}\n'
    assert marker in fit_source and "if node.type == 'OD/SheetWindow':" in fit_source
    namespace = {'__file__': str(repo / 'source/tests/check_window_content_fit.py'), '__name__': 'content_fit'}
    exec(compile(fit_source[:fit_source.index(marker)], 'check_window_content_fit.py', 'exec'), namespace)
    SCREENS = [(640, 480), (1024, 768), (1920, 1200), (7680, 4320)]
    USER_SCALES = [0.8, 1.0, 1.2]
    faults = []
    cases = 0
    stats = {'windows': 0}
    for sheet in namespace['sheets']:
        if sheet.layout not in INGAME:
            continue
        for screen in SCREENS:
            for user in USER_SCALES:
                problems = []
                namespace['walk'](sheet, (0.0, 0.0, float(screen[0]), float(screen[1])),
                                  (0.0, 0.0, float(screen[0]), float(screen[1])), screen, user, 1.0, problems, stats)
                cases += 1
                for node, kind, got, limit in problems:
                    faults.append('%s %s at %dx%d %d%%: %s (%s vs %s)' % (node.layout, node.path, screen[0], screen[1],
                                                                         round(user * 100), kind, got, limit))
    for fault in faults[:40]:
        print('FAULT', fault)
    assert not faults, '%d in-game windows or controls do not fit' % len(faults)
    print('4. %d in-game sheets x %d screens x %d UI scales: %d window evaluations, everything inside its sheet frame' % (
        cases // (len(SCREENS) * len(USER_SCALES)), len(SCREENS), len(USER_SCALES), stats['windows']))
content_packages.unchecked('check_ingame_window_frame', not_checked)
print('ODP_TEST_PHASE {"name":"check","seconds":%.2f}' % (time.monotonic() - STARTED))
print('INGAME WINDOW FRAME OK')
