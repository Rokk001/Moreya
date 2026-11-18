"""Check the fixed size information window (gui/WindowStats.layout) of tiles and the in-game options menu.

The window may not be resized, uses the small body font with top aligned word wrapped text and is
created from the layout (registered for UI scaling) by Tile. A creature has no window of its own any
more: its information is shown in the Dungeonbook (check_creature_click_dungeonbook.py). The options
menu shows an icon at every entry of its list.

In-game options menu (F10, INGAME-QS-11 K7, T-O1). Static check, no game and no compiler needed. It checks the outcome:

1. Entries. The options window holds exactly the game options Save Game, Load Game, Settings, Help, End Game (with
   Quit to Menu, Exit to System, Restart Level and Back on its page) and Continue Game, in the order the code shows
   them, and every entry keeps its action. Objectives, Skill, Production, Player information and Define user cameras
   are gone from the window and from the code of the window.
2. Look. Every entry is a menu template button of the main menu (OD/MenuIconTextButton: the plates, caps, knobs and
   hover of OD/MenuTextButton) with its symbol at the left of the caption; the symbol is drawn in every state (normal,
   hover, pushed, disabled); no OD/IconButton and none of its light wooden hover bar is left in the window. Every
   window the options menu opens (settings navigation, settings, apply popup, user cameras, load screen, exit
   confirmation, help) uses menu template buttons for its own buttons.
3. Sizes. With the formulas of GameMode::setOptionsPage and the frame and font model of check_window_content_fit.py,
   at 640x480, 1024x768, 1920x1200 and 7680x4320 and UI scale 80 %, 100 % and 120 %, for the options page with and
   without saving and the End Game page: the window lies on the screen, its height fits its entries (no empty row),
   every entry lies in the client area of the window frame and is not narrower than its caps, symbol and knobs, the
   plates do not overlap, the symbol lies on the planks left of the caption and no caption is cut.
4. Moved entries. Objectives, Skill and Production stay reachable from the game bar (Goals, Skill and Room Manager
   buttons, the workshop row of the Room Manager); Define user cameras is a button of the settings navigation window;
   the KO setting of the player information window is a check box on the Game page of the settings window that shows
   the seat value and sends a change to the server, which sets the seat (Creature.cpp reads it when a creature is
   defeated).
"""
from pathlib import Path
import re
import time
import xml.etree.ElementTree as ET

STARTED = time.monotonic()
repo = Path(__file__).resolve().parents[2]
layout = (repo / 'gui/WindowStats.layout').read_text()
assert 'name="StatsWindow"' in layout and 'type="OD/SheetWindow"' in layout, 'the window frame of the menu sheet'
assert '<Property name="SizingEnabled" value="False" />' in layout, 'the window must not be resizable'
m = re.search(r'name="Area" value="\{\{0\.5,(-?\d+)\},\{0\.5,(-?\d+)\},\{0\.5,(\d+)\},\{0\.5,(\d+)\}\}"', layout)
assert m, 'a fixed size centred area is expected'
width, height = int(m[3]) - int(m[1]), int(m[4]) - int(m[2])
assert width >= 480 and height >= 440, (width, height)
for prop in ('Font" value="MedievalSharp-8', 'VertFormatting" value="TopAligned', 'HorzFormatting" value="WordWrapLeftAligned',
             'FrameEnabled" value="False'):
    assert prop in layout, prop
assert 'VertScrollbar' not in layout, 'no scrolling wanted'
for name in ('Creature', 'Tile'):
    text = (repo / 'source/entities' / (name + '.cpp')).read_text()
    # Only the tile opens an information window; the creature opens none (its information is in the Dungeonbook)
    assert ('createInfoWindow(' in text) == (name == 'Tile'), name
    assert 'createCreatureProfileWindow(' not in text, name + ' still opens the old creature window'
    assert 'CEGUI::UDim(0, 380)' not in text, name + ' still sets an own size'
    assert "MedievalSharp-12" not in text, name + ' still uses the large title font'

# ------------------------------------------------------------------------------------------------ in-game options menu
gui = repo / 'gui'
game = (repo / 'source/modes/GameMode.cpp').read_text(encoding='utf-8')
game_header = (repo / 'source/modes/GameMode.h').read_text(encoding='utf-8')
navigation_code = (repo / 'source/modes/GameModeRoomManager.cpp').read_text(encoding='utf-8')
settings_code = (repo / 'source/modes/SettingsWindow.cpp').read_text(encoding='utf-8')


def body(text, signature):
    """A C++ function of a source file, nested braces included."""
    start = text.index(signature)
    opening = text.index('{', start)
    level, end = 1, opening + 1
    while level:
        level += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


def props(window):
    """Properties of a layout window."""
    return {p.get('name'): p.get('value') for p in window.findall('Property')}


scheme = ET.parse(gui / 'ODSkin.scheme').getroot()
targets = {m.get('windowType'): m.get('targetType') for m in scheme.findall('FalagardMapping')}
BUTTON_TARGETS = ('CEGUI/PushButton', 'CEGUI/RadioButton')
# The button looks of the main menu: the template of the chosen menu sheet in its full, compact and filter forms, and
# the full form with a symbol.
MENU_LOOKS = ('OD/MenuTextButton', 'OD/MenuIconTextButton', 'OD/MenuCompactButton', 'OD/MenuFilterButton')
ICON_LOOK = 'OD/MenuIconTextButton'
assert targets[ICON_LOOK] == 'CEGUI/PushButton', 'the symbol button is no push button'

# 1. Entries: exactly the game options of K7 with their captions, in the order the code shows them.
OPTIONS_PAGE = ['SaveGameButton', 'LoadGameButton', 'SettingsButton', 'HelpButton', 'EndGameButton', 'ContinueButton']
END_GAME_PAGE = ['QuitGameButton', 'ExitGameButton', 'RestartLevelButton', 'BackButton', 'ContinueButton']
CAPTIONS = {'SaveGameButton': 'Save Game', 'LoadGameButton': 'Load Game', 'SettingsButton': 'Settings', 'HelpButton': 'Help',
            'EndGameButton': 'End Game', 'ContinueButton': 'Continue Game', 'QuitGameButton': 'Quit to Menu',
            'ExitGameButton': 'Exit to System', 'RestartLevelButton': 'Restart Level', 'BackButton': 'Back'}
ACTIONS = {'SaveGameButton': 'saveGame', 'LoadGameButton': 'loadGame', 'SettingsButton': 'showSettingsFromOptions',
           'HelpButton': 'toggleHelpWindow', 'EndGameButton': 'showEndGameFromOptions', 'ContinueButton': 'hideOptionsWindow',
           'QuitGameButton': 'showQuitMenuFromOptions', 'ExitGameButton': 'showExitApplicationFromOptions',
           'RestartLevelButton': 'showRestartLevelFromOptions', 'BackButton': 'showOptionsWindow'}
REMOVED = ('ObjectivesButton', 'SkillButton', 'ProductionButton', 'PlayerSettingsButton', 'UserCamerasButton')
options_root = ET.parse(gui / 'WindowGameOptions.layout').getroot()
options_window = options_root.find('Window')
assert options_window.get('name') == 'GameOptionsWindow' and options_window.get('type') == 'OD/SheetWindow'
entries = {w.get('name'): w for w in options_window.findall('Window')}
assert sorted(entries) == sorted(CAPTIONS), ('the options window holds other entries than K7', sorted(entries))
for name, window in entries.items():
    assert props(window).get('Text') == CAPTIONS[name], (name, props(window).get('Text'))
page = body(game, 'void GameMode::setOptionsPage(')
vectors = re.findall(r'std::vector<const char\*>\{([^}]*)\}', page)
assert len(vectors) == 2, vectors
shown = [re.findall(r'"(\w+)"', v) for v in vectors]
assert shown[0] == END_GAME_PAGE and shown[1] == OPTIONS_PAGE, shown
hidden_on_end = re.search(r'for\(const char\* name : \{([^}]*)\}\)\s*options->getChild\(name\)->setVisible\(!endGame\);', page)
shown_on_end = re.search(r'for\(const char\* name : \{([^}]*)\}\)\s*options->getChild\(name\)->setVisible\(endGame\);', page)
assert hidden_on_end and shown_on_end, 'the pages switch their entries'
assert sorted(re.findall(r'"(\w+)"', hidden_on_end[1])) == sorted(n for n in OPTIONS_PAGE if n != 'ContinueButton')
assert sorted(re.findall(r'"(\w+)"', shown_on_end[1])) == sorted(n for n in END_GAME_PAGE if n != 'ContinueButton')
# without saving (multiplayer) Save Game and Load Game leave the page: the first two entries
assert 'entries.erase(entries.begin(), entries.begin() + 2)' in page and OPTIONS_PAGE[:2] == ['SaveGameButton', 'LoadGameButton']
for name, action in ACTIONS.items():
    place = game.index('getChild("GameOptionsWindow/%s")' % name)
    following = game[place:place + 600]
    handler = re.search(r'Subscriber\(&GameMode::(\w+), this\)', following)
    assert handler and handler[1] == action, (name, handler and handler[1], action)
for name in REMOVED:
    assert name not in entries, name + ' is still in the options window'
    assert 'GameOptionsWindow/' + name not in game, name + ' is still connected'
for gone in ('showObjectivesFromOptions', 'showSkillFromOptions', 'showTrapProductionQueue', 'togglePlayerSettingsWindow',
             'showPlayerSettingsWindow', 'buildPlayerSettingsWindow', 'PlayerSettingsWindow'):
    assert gone not in game and gone not in game_header, gone + ' is left from the old options window'
print('1. options window: %d entries of K7 with their actions, %d entries removed' % (len(entries), len(REMOVED)))

# 2. Look: every entry is the menu template button with its symbol, drawn in every state.
assert 'OD/IconButton' not in (gui / 'WindowGameOptions.layout').read_text(encoding='utf-8'), 'the old icon button look is left'
imagesets = {}
for imageset_file in gui.glob('*.imageset'):
    root = ET.parse(imageset_file).getroot()
    imagesets[root.get('name')] = {i.get('name') for i in root.findall('Image')}
for name, window in entries.items():
    assert window.get('type') == ICON_LOOK, (name, window.get('type'))
    icon = props(window).get('IconImage', '')
    imageset, _, image = icon.partition('/')
    assert image in imagesets.get(imageset, set()), (name, 'symbol missing', icon)
looks = {wl.get('name'): wl for wl in ET.parse(gui / 'OD.looknfeel').getroot().findall('WidgetLook')}
assert looks[ICON_LOOK].get('inherits') == 'OD/MenuTextButton', 'the symbol button is not the menu template button'


def find_section(look, name):
    """An imagery section of a look or of the looks it inherits from."""
    while look is not None:
        for section in looks[look].findall('ImagerySection'):
            if section.get('name') == name:
                return section
        look = looks[look].get('inherits')
    raise AssertionError('section %s not found' % name)


def state_drawing(look, state):
    """Images and image properties a state imagery of a look draws."""
    imagery = [s for s in looks[look].findall('StateImagery') if s.get('name') == state]
    assert len(imagery) == 1, (look, state)
    images, image_properties = set(), set()
    for section in imagery[0].iter('Section'):
        drawn = find_section(section.get('look', look), section.get('section'))
        images |= {i.get('name') for i in drawn.iter('Image')}
        image_properties |= {i.get('name') for i in drawn.iter('ImageProperty')}
    return images, image_properties


for state in ('Normal', 'Hover', 'Pushed', 'PushedOff', 'Disabled'):
    template_images, _ = state_drawing('OD/MenuTextButton', state)
    images, image_properties = state_drawing(ICON_LOOK, state)
    assert images == template_images, (state, 'plates differ from the main menu button', sorted(images ^ template_images))
    assert all(i.startswith('ODMenuTemplate/') for i in images), (state, images)
    assert 'IconImage' in image_properties, state + ': the symbol is not drawn'
    assert not image_properties & {'HoverImage', 'PushedImage', 'DisabledImage'}, state + ': the old hover bar is drawn'
symbol = find_section(ICON_LOOK, 'symbol').find('ImageryComponent/Area')
caption = find_section(ICON_LOOK, 'caption').find('TextComponent/Area')


def height_scale(area, dim_type):
    """The height factor of a plain UnifiedDim of a component area dimension."""
    dim = [d for d in area.findall('Dim') if d.get('type') == dim_type][0].find('UnifiedDim')
    assert dim is not None and dim.get('type') == 'Height', dim_type
    return float(dim.get('scale'))


SYMBOL_LEFT, SYMBOL_TOP = height_scale(symbol, 'LeftEdge'), height_scale(symbol, 'TopEdge')
SYMBOL_SIZE = height_scale(symbol, 'Width')
assert abs(height_scale(symbol, 'Height') - SYMBOL_SIZE) < 1e-6, 'the symbol is not square'
CAPTION_LEFT = height_scale(caption, 'LeftEdge')
# Every window the options menu opens: settings navigation (pages and user cameras), settings, its apply popup, the
# user cameras, the load screen, the exit confirmation of the End Game entries and the help window.
OPENED = {'WindowSettingsNavigation.layout': 'SettingsNavigationWindow', 'WindowSettings.layout': 'SettingsWindow',
          'WindowApplyChanges.layout': 'ConfirmRestart', 'WindowUserCameras.layout': 'UserCamerasWindow',
          'MenuLoad.layout': 'LoadPanel', 'WindowQuit.layout': 'ConfirmExit', 'WindowHelp.layout': 'GameHelpWindow'}
assert 'getChild("SettingsNavigationWindow")' in body(game, 'bool GameMode::showSettingsFromOptions(')
assert 'mSettings.showPage(page)' in body(game, 'bool GameMode::openSettingsNavigationPage(')
assert 'showUserCameras(e)' in body(game, 'bool GameMode::openSettingsNavigationCameras(')
assert 'getChild("UserCamerasWindow")' in body(game, 'bool GameMode::showUserCameras(')
assert 'loadLayoutFromFile("WindowSettings.layout")' in settings_code and 'loadLayoutFromFile("WindowApplyChanges.layout")' in settings_code
assert 'new MenuModeLoad(mModeManager, true)' in body(game, 'bool GameMode::loadGame(')
assert 'mSheets[loadSavedGameMenu] =  wmgr->loadLayoutFromFile("MenuLoad.layout")' in (repo / 'source/render/Gui.cpp').read_text(encoding='utf-8')
assert 'getChild(Gui::EXIT_CONFIRMATION_POPUP)' in body(game, 'void GameMode::popupExit(')
assert 'getChild("GameHelpWindow")' in body(game, 'bool GameMode::showHelpWindow(')
opened_buttons = 0
for opened_layout, window_name in OPENED.items():
    windows = list(ET.parse(gui / opened_layout).getroot().iter('Window'))
    assert window_name in {w.get('name') for w in windows}, (opened_layout, window_name)
    assert 'OD/IconButton' not in (gui / opened_layout).read_text(encoding='utf-8'), opened_layout + ' keeps the old look'
    for window in windows:
        if targets.get(window.get('type')) in BUTTON_TARGETS:
            opened_buttons += 1
            assert window.get('type') in MENU_LOOKS and 'LookNFeel' not in props(window), \
                (opened_layout, window.get('name'), window.get('type'), 'is not a main menu button')
# counted once on this branch: navigation 7, settings 2, apply popup 2, user cameras 4, load screen 7, exit 2, help 0
assert opened_buttons == 24, opened_buttons
print('2. %d option entries and %d buttons of %d opened windows are main menu buttons, symbol in every state' % (
    len(entries), opened_buttons, len(OPENED)))

# 3. Sizes, with the formulas of GameMode::setOptionsPage and the frame and font model of check_window_content_fit.py.
fit_source = (repo / 'source/tests/check_window_content_fit.py').read_text(encoding='utf-8')
marker = '\nall_problems = {}\n'
assert marker in fit_source
namespace = {'__file__': str(repo / 'source/tests/check_window_content_fit.py'), '__name__': 'content_fit'}
exec(compile(fit_source[:fit_source.index(marker)], 'check_window_content_fit.py', 'exec'), namespace)
assert namespace['text_area'] is not None and ICON_LOOK in namespace['MENU_SYMBOL_CAPTION'], 'the font model lacks the symbol button'
assert abs(namespace['MENU_SYMBOL_CAPTION'][ICON_LOOK][0] - CAPTION_LEFT) < 1e-6, 'font model and look place the caption differently'


def find_node(nodes, name):
    """The layout node of the given window name below the given nodes."""
    for node in nodes:
        if node.name == name:
            return node
        found = find_node(node.children, name)
        if found is not None:
            return found
    return None


window_node = find_node(namespace['sheets'], 'GameOptionsWindow')
assert window_node is not None
entry_nodes = {child.name: child for child in window_node.children}
number = r'([0-9.]+)f'
height_rule = re.search(r'std::min\(' + number + r', \(' + number + r' \+ ' + number +
                        r' \* entries\.size\(\)\) \* gui\.getLayoutScale\(\) / display\.d_height\)', page)
step_rule = re.search(r'const float step = ' + number + r' / entries\.size\(\);', page)
top_rule = re.search(r'const float top = ' + number + r' \+ step \* i;', page)
button_rule = re.search(r'CEGUI::UDim\(top \+ step \* ' + number + r' / ' + number + r', 0\)', page)
side_rule = re.search(r'CEGUI::UDim\(0\.5f, -(\d+)\), CEGUI::UDim\(0\.5f - height / 2\.0f, 0\)', page)
inset_rule = re.search(r'CEGUI::URect\(CEGUI::UDim\(0, (\d+)\), CEGUI::UDim\(top, 0\),\s*CEGUI::UDim\(1, -(\d+)\)', page)
assert height_rule and step_rule and top_rule and button_rule and side_rule and inset_rule, 'setOptionsPage changed its form'
LIMIT, FRAME, ROW = (float(v) for v in height_rule.groups())
STEP, TOP = float(step_rule[1]), float(top_rule[1])
BUTTON = float(button_rule[1]) / float(button_rule[2])
HALF_WIDTH, INSET = float(side_rule[1]), float(inset_rule[1])
assert float(inset_rule[2]) == INSET
SCREENS = ((640, 480), (1024, 768), (1920, 1200), (7680, 4320))
USER_SCALES = (0.8, 1.0, 1.2)
TOLERANCE = namespace['TOLERANCE']
KNOB_TOP, KNOB_BOTTOM = 8.5 / 120.0, 7.5 / 120.0  # the knobs of the template stand above and below the plate
# narrowest symbol button: both caps, the centre knob piece and the symbol with its gap before the caption
MIN_WIDTH = 2 * 0.516667 + 0.466667 + (CAPTION_LEFT - SYMBOL_LEFT)
cases = 0
for screen in SCREENS:
    for user in USER_SCALES:
        s = min(screen[0] / namespace['DESIGN_W'], screen[1] / namespace['DESIGN_H']) * user
        for page_name, names in (('options', OPTIONS_PAGE), ('options without saving', OPTIONS_PAGE[2:]),
                                 ('End Game', END_GAME_PAGE)):
            where = '%s page at %dx%d %d%%' % (page_name, screen[0], screen[1], round(user * 100))
            fraction = min(LIMIT, (FRAME + ROW * len(names)) * s / screen[1])
            rect = (screen[0] / 2.0 - HALF_WIDTH * s, screen[1] * (0.5 - fraction / 2.0),
                    screen[0] / 2.0 + HALF_WIDTH * s, screen[1] * (0.5 + fraction / 2.0))
            assert rect[0] >= -TOLERANCE and rect[1] >= -TOLERANCE and rect[2] <= screen[0] + TOLERANCE \
                and rect[3] <= screen[1] + TOLERANCE, where + ': the window leaves the screen'
            client = namespace['client_rect'](window_node, rect, screen, user, s)
            step = STEP / len(names)
            plates = []
            for index, name in enumerate(names):
                node = entry_nodes[name]
                top = TOP + step * index
                box = (client[0] + INSET * s, client[1] + top * (client[3] - client[1]),
                       client[2] - INSET * s, client[1] + (top + step * BUTTON) * (client[3] - client[1]))
                here = '%s: %s' % (where, name)
                h = box[3] - box[1]
                assert box[0] >= client[0] - TOLERANCE and box[1] >= client[1] - TOLERANCE and \
                    box[2] <= client[2] + TOLERANCE and box[3] <= client[3] + TOLERANCE, here + ' leaves the window frame'
                assert box[2] - box[0] >= MIN_WIDTH * h - TOLERANCE, here + ' is narrower than its caps and symbol'
                symbol_box = (box[0] + SYMBOL_LEFT * h, box[1] + SYMBOL_TOP * h,
                              box[0] + (SYMBOL_LEFT + SYMBOL_SIZE) * h, box[1] + (SYMBOL_TOP + SYMBOL_SIZE) * h)
                text_box = namespace['text_area'](node, box, screen, user, s)
                assert symbol_box[2] <= text_box[0] + TOLERANCE and symbol_box[0] >= box[0] and \
                    symbol_box[3] <= box[3], here + ': the symbol is not on the planks left of the caption'
                assert symbol_box[2] - symbol_box[0] >= 8.0, here + ': the symbol is too small to be seen'
                problems = []
                namespace['check_text'](node, box, screen, user, s, problems)
                assert not problems, (here, problems)
                plates.append((box[1] + KNOB_TOP * h, box[3] - KNOB_BOTTOM * h))
                cases += 1
            for upper, lower in zip(plates, plates[1:]):
                assert upper[1] <= lower[0] + TOLERANCE, where + ': two entries overlap'
            # the window height fits its entries: below the last entry no room for another one
            last_bottom = client[1] + (TOP + step * (len(names) - 1) + step * BUTTON) * (client[3] - client[1])
            assert client[3] - last_bottom < step * (client[3] - client[1]), where + ': the window is higher than its entries'
print('3. %d entry placements at %d screens x %d UI scales on the three pages: on the screen, inside the frame, '
      'symbol left of an uncut caption' % (cases, len(SCREENS), len(USER_SCALES)))

# 4. Moved entries stay reachable.
hud = {w.get('name'): w for w in ET.parse(gui / 'ModeGame.layout').getroot().iter('Window')}
for button, handler, window in (('GoalsButton', 'toggleObjectivesWindow', 'ObjectivesWindow'),
                                ('ResearchButton', 'toggleSkillWindow', 'SkillTreeWindow')):
    assert button in hud and props(hud[button]).get('Visible') != 'False', button + ' is not on the game bar'
    place = game.index('getChild("%s")->subscribeEvent(' % button)
    assert 'Subscriber(&GameMode::%s, this)' % handler in game[place:place + 300], (button, handler)
    assert 'getChild("%s")' % window in body(game, 'bool GameMode::' + handler + '('), (handler, window)
assert 'RoomManagerButton' in hud, 'the Room Manager button is not on the game bar'
initialize = body(navigation_code, 'void GameMode::initializeRoomManager(')
assert 'getChild("RoomManagerButton")->subscribeEvent(' in initialize and '&GameMode::toggleRoomManager' in initialize
assert 'case RoomType::workshop: requestTrapProductionQueue(); break;' in body(navigation_code, 'void GameMode::refreshRoomManager(')
assert '"WorkshopPage"' in navigation_code, 'the workshop page is not a page of the Room Manager'
navigation = {w.get('name'): w for w in ET.parse(gui / 'WindowSettingsNavigation.layout').getroot().iter('Window')}
assert props(navigation['Cameras']).get('Text') == 'Define User Cameras'
assert re.search(r'getChild\("Cameras"\)->subscribeEvent\(CEGUI::PushButton::EventClicked,\s*'
                 r'CEGUI::Event::Subscriber\(&GameMode::openSettingsNavigationCameras, this\)\)',
                 body(game, 'void GameMode::initializeSettingsNavigation(')), 'Define User Cameras is not connected'
for name in ('Video', 'Audio', 'Input', 'Game'):
    assert name in navigation, name
assert not (gui / 'WindowPlayerSettings.layout').exists(), 'the player information window is left'
assert 'WindowPlayerSettings.layout' not in (gui / 'ModeGame.layout').read_text(encoding='utf-8')
settings_layout = ET.parse(gui / 'WindowSettings.layout').getroot()
game_page = [w for w in settings_layout.iter('Window') if w.get('name') == 'GameSP'][0]
ko = [w for w in game_page.findall('Window') if w.get('name') == 'KOCreatureCheckbox']
assert ko and ko[0].get('type') == 'OD/Checkbox' and props(ko[0])['Text'] == 'KO enemy creatures instead of killing', \
    'the KO setting is not on the Game page of the settings window'
assert props(ko[0]).get('Visible') == 'False', 'the KO setting is shown outside a running game (menu, editor)'
ko_path = 'MainTabControl/Game/GameSP/KOCreatureCheckbox'
show = body(settings_code, 'void SettingsWindow::setKoCreaturesSetting(')
assert ko_path + '")->setVisible(' in show and 'mKoCreaturesCurrent && mKoCreaturesApply' in show
sync = body(settings_code, 'void SettingsWindow::syncKoCreaturesSetting(')
assert ko_path in sync and 'setSelected(mKoCreaturesCurrent())' in sync, 'the check box does not show the seat value'
assert 'syncKoCreaturesSetting();' in body(settings_code, 'void SettingsWindow::initConfig('), 'the window does not reread the seat'
save = body(settings_code, 'bool SettingsWindow::saveConfig(')
assert ko_path in save and 'mKoCreaturesApply(koCreaturesCheckbox->isSelected())' in save, 'Apply does not send the KO setting'
# the KO setting is sent before anything in saveConfig can stop the saving
assert save.index('mKoCreaturesApply(') < save.index('return false;'), 'a refused renderer change drops the KO setting'
assert re.search(r'mSettings\.setKoCreaturesSetting\(std::bind\(&GameMode::isLocalKoCreaturesEnabled, this\),\s*'
                 r'std::bind\(&GameMode::requestKoCreaturesSetting, this, std::placeholders::_1\)\);', game)
assert 'getSeat()->getKoCreatures()' in body(game, 'bool GameMode::isLocalKoCreaturesEnabled(')
request = body(game, 'void GameMode::requestKoCreaturesSetting(')
assert 'ClientNotificationType::askSetPlayerSettings' in request and 'mPacket << enabled' in request
assert 'mSettings.syncKoCreaturesSetting()' in body(game, 'void GameMode::syncPlayerSettings(')
server = (repo / 'source/network/ODServer.cpp').read_text(encoding='utf-8')
handled = server[server.index('case ClientNotificationType::askSetPlayerSettings:'):][:600]
assert 'packetReceived >> koCreatures' in handled and 'setPlayerSettings(koCreatures)' in handled, 'the server ignores it'
assert 'getSeat()->getKoCreatures()' in (repo / 'source/entities/Creature.cpp').read_text(encoding='utf-8'), 'KO has no effect'
print('4. Objectives, Skill and Production on the game bar; user cameras and the KO setting in the settings')
print('ODP_TEST_PHASE {"name":"check","seconds":%.2f}' % (time.monotonic() - STARTED))
print('ok')
