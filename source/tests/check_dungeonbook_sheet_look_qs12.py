"""Check the Dungeonbook findings of plan INGAME-QS-12 package B1 (test T-B1, requirements K6, K8 and K9).

Static check, no game and no compiler needed. The Skills page of K7 is measured by check_dungeonbook_pages_b1.py (every
skill with its rank inside the page and no cut text at 640x480, 1024x768, 1920x1200 and 7680x4320 with UI 80 % and
120 %), wired by check_creature_skill_tree_view.py and run by check_dungeonbook_navigation_runtime_n1.py.

1. K6, item tooltips appear at once. A model of the tooltip of CEGUI 0.8 (widgets/Tooltip.cpp and the tooltip parts of
   Window.cpp: the hover time is counted in the time pulse, every move of the pointer restarts it, an active tooltip
   is hidden after the display time) runs the frames of the game (ODFrameListener::frameRenderingQueued: time pulse,
   then the input of the frame, then drawing) with the timing Gui.cpp gives the default tooltip. It asserts the outcome:
   the item card is drawn in the frame the pointer enters the item, it stays for 20 s while the pointer moves on the
   item and the Dungeonbook refreshes its inventory page every 0.25 s, it goes when the pointer leaves; a plain
   tooltip keeps the CEGUI timing (shown only after the pointer rested 0.4 s). The same model with the CEGUI defaults
   (before the fix) shows the card late and loses it while the pointer moves, so the model tells the two apart.
2. K9, every scrollbar of the book is the scrollbar of the chosen sheet variant-2.png: the list, the feed of all
   creatures, the feed of one creature and the list of the filter use OD/SheetScrollbar, whose rail, up and down arrow
   boxes and thumb are the pixels of the sheet's scrollbar (compared with the sheet itself), the arrows on top and at
   the bottom keep the proportions of the sheet, and the rail between them is longer than the smallest thumb at every
   screen and UI scale. No other scrollbar look is left in the book.
3. K8, the filter is a drop-down built from the sheet's parts: OD/SheetCombobox with the sheet's list inset as field
   and as opened list and the sheet's down arrow box as button, beside "Creatures (n)" where it was (D934); the
   entries stay All, Zivs, Fighters and Unhappy with their behaviour, the chosen entry shows the highlighted row of the
   sheet; the closed field lies above the list and inside the start page, every entry fits the field and all four fit
   the opened list at every screen and UI scale.

Needs the chosen sheet at <ODP_ASSETS_SRC>/ingame-qs-9/d1/variant-2.png (like check_menu_button_template.py).
"""
from pathlib import Path
import re
import sys
import time
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image

START = time.monotonic()
repo = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo / 'scripts'))
from assets_src import assets_src_dir  # noqa: E402

gui_dir = repo / 'gui'
gui_cpp = (repo / 'source/render/Gui.cpp').read_text(encoding='utf-8')
social_cpp = (repo / 'source/render/SocialWindow.cpp').read_text(encoding='utf-8')
creature_cpp = (repo / 'source/entities/Creature.cpp').read_text(encoding='utf-8')
frame_cpp = (repo / 'source/render/ODFrameListener.cpp').read_text(encoding='utf-8')
mode_cpp = (repo / 'source/modes/ModeManager.cpp').read_text(encoding='utf-8')
layout = ET.parse(gui_dir / 'WindowSocial.layout').getroot().find('Window')
looks = {look.get('name'): look for look in ET.parse(gui_dir / 'OD.looknfeel').getroot().findall('WidgetLook')}
scheme = (gui_dir / 'ODSkin.scheme').read_text(encoding='utf-8')
failures = []


def check(condition, message):
    if not condition:
        failures.append(message)


def function_of(text, signature):
    body = text[text.index(signature):]
    return body[:body.index('\n}\n')]


# ------------------------------------------------------------------------------------------------ 1. K6 tooltip timing
# The timing the code gives the default tooltip while it points at an item card, read from Gui.cpp
item_hover = float(re.search(r'const float ITEM_TOOLTIP_HOVER_TIME = ([0-9.]+)f;', gui_cpp).group(1))
item_display = float(re.search(r'const float ITEM_TOOLTIP_DISPLAY_TIME = ([0-9.]+)f;', gui_cpp).group(1))
timing = function_of(gui_cpp, 'void applyItemTooltipTiming(CEGUI::Tooltip* tooltip)')
check('isItemTooltipWindow(tooltip->getTargetWindow())' in timing and
      'itemCard ? ITEM_TOOLTIP_HOVER_TIME : sPlainTooltipHoverTime' in timing and
      'itemCard ? ITEM_TOOLTIP_DISPLAY_TIME : sPlainTooltipDisplayTime' in timing,
      'the item card timing applies to item cards only, every other tooltip keeps the plain timing')
switches_at_once = 'if(itemCard)\n        tooltip->update(0.0f);' in timing
on_enter = re.search(r'ges\.subscribeEvent\(\s*CEGUI::Window::EventNamespace \+ "/" \+ CEGUI::Window::EventMouseEntersSurface,'
                     r'\s*CEGUI::Event::Subscriber\(&onWindowEnteredForTooltip\)\);', gui_cpp) is not None
entered = function_of(gui_cpp, 'bool onWindowEnteredForTooltip(const CEGUI::EventArgs& e)')
check('applyTooltipTimingOf(' in entered, 'entering a window applies the timing of its tooltip')
timing_of = function_of(gui_cpp, 'void applyTooltipTimingOf(CEGUI::Window* window)')
check('tooltip->getTargetWindow() == window' in timing_of and 'applyItemTooltipTiming(tooltip);' in timing_of,
      'the timing follows the window the tooltip points at')
on_mark = all('applyTooltipTimingOf(' in function_of(gui_cpp, signature) for signature in (
    'void Gui::markItemTooltip(', 'void Gui::setPlainTooltip(', 'void Gui::copyTooltip('))
check(on_mark, 'marking a window as item card (or plain) under the resting pointer applies the timing at once')
check('sPlainTooltipHoverTime = defaultTooltip->getHoverTime();' in gui_cpp and
      'sPlainTooltipDisplayTime = defaultTooltip->getDisplayTime();' in gui_cpp,
      'the plain timing is the one CEGUI gives the default tooltip')
# The refresh of the inventory page marks every filled slot again (the case of the finding) and changes nothing else
# that would make CEGUI drop the target: no window is hidden, moved or destroyed under the pointer
refresh = function_of(social_cpp, 'void SocialWindow::refreshInventory(')
fill = function_of(creature_cpp, 'void Creature::fillItemSlotWindows(')
check('Creature::fillItemSlotWindows(creature, slots, true);' in refresh and 'Gui::copyTooltip(slot, slot->getParent());'
      in refresh and 'Gui::setItemTooltip(image, *item, creature->getGameMap(), heldWeapon);' in fill,
      'the refresh marks the slots and their boxes as item cards again')
check('markItemTooltip(window, ' in function_of(gui_cpp, 'void Gui::setItemTooltip('),
      'setItemTooltip marks the window as item card')
for text, name in ((refresh, 'refreshInventory'), (fill, 'fillItemSlotWindows')):
    for call in ('->hide()', '->moveToFront()', 'destroyWindow', 'removeChild', '->setArea(', '->setPosition('):
        check(call not in text, '%s calls %s: the pointer could leave the item while it rests' % (name, call))
# Order of a frame: the CEGUI time pulse comes before the input of the frame, which is read in the mode update
pulse = frame_cpp.index('getDefaultGUIContext().injectTimePulse(evt.timeSinceLastFrame);')
check(pulse < frame_cpp.index('mModeManager->update(evt);'), 'the time pulse comes before the mode update')
check('mInputManager.capturePointer();' in function_of(mode_cpp, 'void ModeManager::update('),
      'the input of a frame is read in the mode update, after the time pulse')

CEGUI_HOVER, CEGUI_DISPLAY = 0.4, 7.5   # widgets/Tooltip.cpp constructor: d_hoverTime(0.4f), d_displayTime(7.5f)


class Tooltip:
    """CEGUI 0.8 Tooltip: setTargetWindow, resetTimer, doInactiveState, doActiveState, switchTo*State."""

    def __init__(self):
        self.hover, self.display = CEGUI_HOVER, CEGUI_DISPLAY
        self.target, self.active, self.visible, self.elapsed = None, False, False, 0.0

    def set_target(self, window):
        self.target = window
        self.elapsed = 0.0

    def update(self, dt):
        text = self.target is not None and self.target.text
        if self.active:
            if not text:
                self.visible = False
                self.active, self.elapsed, self.target = False, 0.0, None
            else:
                self.elapsed += dt
                if self.display > 0 and self.elapsed >= self.display:
                    self.active, self.elapsed, self.target = False, 0.0, None
                    self.visible = False   # the hide animation of the inactive state
        elif text:
            self.elapsed += dt
            if self.elapsed >= self.hover:
                self.visible, self.active, self.elapsed = True, True, 0.0


class Window:
    def __init__(self, text, item):
        self.text, self.item = text, item


def apply_timing(tooltip, window, fixed):
    """Gui.cpp applyTooltipTimingOf / applyItemTooltipTiming as read above; nothing before the fix."""
    if not fixed or tooltip.target is not window:
        return
    item = window.item
    tooltip.hover = item_hover if item else CEGUI_HOVER
    tooltip.display = item_display if item else CEGUI_DISPLAY
    if item and switches_at_once:
        tooltip.update(0.0)


def run(fixed, script, frames, dt=1.0 / 60.0):
    """Runs the frames; script(frame) returns the input of the frame: ('enter', window), ('move',), ('leave',),
    ('refresh', window) or None. Returns the frames in which the tooltip is drawn."""
    tooltip = Tooltip()
    shown = []
    for frame in range(frames):
        tooltip.update(dt)                      # CEGUI time pulse
        for event in script(frame):             # input and mode update of the frame
            if event[0] == 'enter':
                tooltip.set_target(event[1])    # Window::onMouseEnters
                if fixed and on_enter:
                    apply_timing(tooltip, event[1], fixed)
            elif event[0] == 'move':
                tooltip.elapsed = 0.0           # Window::onMouseMove: resetTimer, in both states
            elif event[0] == 'leave':
                tooltip.set_target(None)
            elif event[0] == 'refresh':         # SocialWindow refresh: setItemTooltip -> markItemTooltip, copyTooltip
                if fixed and on_mark:
                    apply_timing(tooltip, event[1], fixed)
        if tooltip.visible:
            shown.append(frame)
    return shown


slot = Window('Sword\nCommon', True)
label = Window('Feed', False)
ENTER, LEAVE, FRAMES = 30, 30 + 20 * 60, 30 + 22 * 60


def on_item(frame, moving=True):
    """The pointer enters the item, moves on it every frame (or rests on it) for 20 s while the book refreshes every
    0.25 s, and leaves."""
    events = []
    if frame == ENTER:
        events.append(('enter', slot))
    if ENTER <= frame < LEAVE:
        if moving:
            events.append(('move',))
        if frame % 15 == 0:
            events.append(('refresh', slot))
    if frame == LEAVE:
        events.append(('leave',))
    return events


def resting(frame):
    """The pointer enters the item and rests on it for 20 s while the book refreshes, then leaves."""
    return on_item(frame, False)


shown = run(True, on_item, FRAMES)
check(shown and shown[0] == ENTER, 'K6: the item card is drawn in the frame the pointer enters the item (frame %s)'
      % (shown[0] if shown else None))
# CEGUI hides the card at the first time pulse after the pointer left, so it is drawn up to the frame of leaving
for scenario, name in ((shown, 'moves'), (run(True, resting, FRAMES), 'rests')):
    check(scenario == list(range(ENTER, LEAVE + 1)), 'K6: the item card stays while the pointer %s on the item and the '
          'page refreshes, and goes when the pointer leaves' % name)
before = run(False, on_item, FRAMES)
check(not before or before[0] > ENTER, 'the model shows the delay of the CEGUI defaults (otherwise it proves nothing)')


def on_label(frame):
    """The pointer enters a plain window and rests on it."""
    return [('enter', label)] if frame == ENTER else []


plain = run(True, on_label, FRAMES)
check(plain and abs((plain[0] - ENTER) / 60.0 - CEGUI_HOVER) <= 1.0 / 60.0 + 1e-9,
      'a plain tooltip keeps the hover time of CEGUI')

# ------------------------------------------------------------------------------------------------ 2. K9 scrollbars
SHEET = assets_src_dir(repo) / 'ingame-qs-9/d1/variant-2.png'
assert SHEET.is_file(), 'chosen menu sheet missing: %s' % SHEET
sheet = np.asarray(Image.open(SHEET).convert('RGB')).astype(np.int32)
atlas = np.asarray(Image.open(gui_dir / 'ODMenuTemplate.png').convert('RGBA')).astype(np.int32)
pieces = {i.get('name'): tuple(int(i.get(k)) for k in ('xPos', 'yPos', 'width', 'height'))
          for i in ET.parse(gui_dir / 'ODMenuTemplate.imageset').getroot().findall('Image')}
# The scrollbar of the list of the load screen on the sheet (measured once on variant-2.png): the up and down arrow
# boxes, an empty piece of the rail below the thumb and the thumb (top end, middle, bottom end)
ON_SHEET = {'ScrollUp': (1795, 455, 1842, 496), 'ScrollDown': (1795, 829, 1842, 870),
            'ScrollRail': (1795, 625, 1842, 825), 'ScrollThumbTop': (1808, 509, 1829, 521),
            'ScrollThumbMiddle': (1808, 521, 1829, 605), 'ScrollThumbBottom': (1808, 605, 1829, 617)}
for name, (x0, y0, x1, y1) in ON_SHEET.items():
    x, y, w, h = pieces.get(name, (0, 0, 0, 0))
    check((w, h) == (x1 - x0, y1 - y0), '%s has the size of the sheet part' % name)
    if (w, h) == (x1 - x0, y1 - y0):
        part = atlas[y:y + h, x:x + w]
        check(np.array_equal(part[..., :3], sheet[y0:y1, x0:x1]) and (part[..., 3] == 255).all(),
              '%s is the part of the sheet' % name)


def child_of(look, suffix):
    found = [c for c in look.findall('Child') if c.get('nameSuffix') == suffix]
    return found[0] if found else None


def images_of(element):
    return [i.get('name') for i in element.iter('Image')]


def prop(element, name):
    found = [p.get('value') for p in element.findall('Property') if p.get('name') == name]
    return found[0] if found else None


bar = looks['OD/SheetScrollbar']
up, down, thumb = child_of(bar, '__auto_decbtn__'), child_of(bar, '__auto_incbtn__'), child_of(bar, '__auto_thumb__')
check(all(prop(up, state) == 'ODMenuTemplate/ScrollUp' for state in ('NormalImage', 'HoverImage', 'PushedImage')),
      'the up button is the up arrow box of the sheet')
check(all(prop(down, state) == 'ODMenuTemplate/ScrollDown' for state in ('NormalImage', 'HoverImage', 'PushedImage')),
      'the down button is the down arrow box of the sheet')
check(up.find('VertAlignment') is None and down.find('VertAlignment').get('type') == 'BottomAligned',
      'the up arrow on top, the down arrow at the bottom')
check(images_of(bar.find("ImagerySection[@name='rail']")) == ['ODMenuTemplate/ScrollRail'], 'the rail of the sheet')
check(thumb.get('type') == 'OD/SheetScrollbarThumb' and images_of(looks['OD/SheetScrollbarThumb']) ==
      ['ODMenuTemplate/ScrollThumbTop', 'ODMenuTemplate/ScrollThumbMiddle', 'ODMenuTemplate/ScrollThumbBottom'],
      'the thumb of the sheet')
ratio = re.search(r'<Dim type="Height"><UnifiedDim scale="([0-9.]+)" type="Width" /></Dim>',
                  ET.tostring(up, encoding='unicode'))
arrow_ratio = float(ratio.group(1)) if ratio else 0.0
check(abs(arrow_ratio - 41.0 / 47.0) < 0.001, 'the arrow boxes keep the proportions of the sheet')
thumb_area = ET.tostring(thumb, encoding='unicode')
check('<UnifiedDim scale="0.2766" type="LeftEdge" />' in thumb_area and '<UnifiedDim scale="0.4468" type="Width" />'
      in thumb_area, 'the thumb runs in the middle of the rail as on the sheet (13 and 21 of 47 sheet pixels)')
min_thumb = float(re.search(r'\{\{0,0\},\{0,([0-9.]+)\}\}', prop(thumb, 'MinSize')).group(1))
for look_name, window_type in (('OD/SheetScrollbar', 'CEGUI/Scrollbar'), ('OD/SheetScrollbarThumb', 'CEGUI/Thumb'),
                               ('OD/SheetCombobox', 'CEGUI/Combobox'), ('OD/SheetComboDropList', 'CEGUI/ComboDropList'),
                               ('OD/SheetComboEditbox', 'CEGUI/Editbox')):
    check('lookNFeel="%s"' % look_name in scheme and 'targetType="%s" windowType="%s"' % (window_type, look_name)
          in scheme, look_name + ' is registered in the scheme')

scrollbars = [w for w in layout.iter('Window') if 'Scroll' in (w.get('type') or '')]
check(sorted(w.get('name') for w in scrollbars) == ['FeedScroll', 'FeedScroll', 'ListScroll'] and
      all(w.get('type') == 'OD/SheetScrollbar' for w in scrollbars), 'the three scrollbars of the book are the sheet\'s')
check(not any(prop(w, 'VertScrollbar') == 'True' or prop(w, 'HorzScrollbar') == 'True' for w in layout.iter('Window')),
      'no text of the book brings its own scrollbar')
drop_bar = child_of(looks['OD/SheetComboDropList'], '__auto_vscrollbar__')
check(drop_bar is not None and drop_bar.get('type') == 'OD/SheetScrollbar', 'the list of the filter uses it too')
check(looks['OD/SheetComboDropList'].get('inherits') == 'OD/ComboDropList' and
      child_of(looks['OD/SheetComboDropList'], '__auto_hscrollbar__') is None, 'only the vertical bar is replaced')

# Geometry of the book (the formulas of Gui.cpp as check_dungeonbook_pages_b1.py computes them)
pages_check = (repo / 'source/tests/check_dungeonbook_pages_b1.py').read_text(encoding='utf-8')
geometry_code = pages_check[:pages_check.index('# ------------------------------------------------------------------------------------------------ texts')]
book_geometry = {'__file__': str(repo / 'source/tests/check_dungeonbook_pages_b1.py')}
exec(compile(geometry_code, 'check_dungeonbook_pages_b1.py', 'exec'), book_geometry)
check(not book_geometry['failures'], 'the geometry of the book is read')
SCREENS, USER_SCALES = book_geometry['SCREENS'], book_geometry['USER_SCALES']
geometry, line_height, text_width, menu_image = (book_geometry[n] for n in ('geometry', 'line_height', 'text_width',
                                                                             'menu_image'))
inside = book_geometry['inside']
FILTER_FONT = prop(layout.find("Window[@name='HomePage']/Window[@name='Filter']"), 'Font')
cases = 0
for screen in SCREENS:
    for user in USER_SCALES:
        g = geometry(screen, user)
        boxes = g['boxes']
        case = '%dx%d %d%%' % (screen[0], screen[1], round(user * 100))
        for path, page in (('HomePage/ListScroll', 'HomePage'), ('HomePage/FeedScroll', 'HomePage'),
                           ('FeedPage/FeedScroll', 'FeedPage')):
            box = boxes[path]
            width, height = box[2] - box[0], box[3] - box[1]
            arrows = 2 * arrow_ratio * width
            check(inside(box, boxes[page]), '%s: %s inside its page' % (case, path))
            check(height - arrows >= min_thumb * g['scale'], '%s: %s keeps rail room for its thumb' % (case, path))
            cases += 1
        # 3. K8: the closed field above the list, its entries fit the field and the four entries fit the opened list
        combo = boxes['HomePage/Filter']
        frame = 0.5 * (menu_image('InsetTop', screen, user)[1] + menu_image('InsetBottom', screen, user)[1])
        side = 0.5 * (menu_image('InsetLeft', screen, user)[0] + menu_image('InsetRight', screen, user)[0])
        edit_height = line_height(FILTER_FONT, screen, user) + frame
        button_width = edit_height * 47.0 / 41.0
        field = (combo[0], combo[1], combo[2] - button_width, combo[1] + edit_height)
        check(field[3] <= boxes['HomePage/ListPanel'][1] + 0.75, '%s: the closed filter lies above the list' % case)
        check(inside((combo[0], combo[1], combo[2], field[3]), boxes['HomePage']), '%s: the filter inside the page' % case)
        for entry in ('All', 'Zivs', 'Fighters', 'Unhappy'):
            check(text_width(FILTER_FONT, entry, screen, user) <= field[2] - field[0] - side,
                  '%s: the entry %s fits the field' % (case, entry))
        list_height = combo[3] - field[3]
        check(4 * line_height(FILTER_FONT, screen, user) + frame <= list_height + 0.75,
              '%s: the four entries fit the opened list' % case)
        label = boxes['HomePage/CreaturesLabel']
        check(abs(label[2] - combo[0]) <= 0.75 and combo[1] < label[3], '%s: the filter beside "Creatures (n)"' % case)
        cases += 1

# ------------------------------------------------------------------------------------------------ 3. K8 drop-down
filter_window = layout.find("Window[@name='HomePage']/Window[@name='Filter']")
check(filter_window.get('type') == 'OD/SheetCombobox' and prop(filter_window, 'ReadOnly') == 'True',
      'the filter is the read-only drop-down of the sheet')
combo_look = looks['OD/SheetCombobox']
check(child_of(combo_look, '__auto_editbox__').get('type') == 'OD/SheetComboEditbox' and
      child_of(combo_look, '__auto_droplist__').get('type') == 'OD/SheetComboDropList', 'field and list of the sheet')
button = child_of(combo_look, '__auto_button__')
check(all(prop(button, state) == 'ODMenuTemplate/ScrollDown' for state in ('NormalImage', 'HoverImage', 'PushedImage')),
      'the button is the down arrow box of the sheet')
check('<AbsoluteDim value="1.1463" />' in ET.tostring(button, encoding='unicode'),
      'the arrow box keeps the proportions of the sheet (47 x 41)')
INSET = ['ODMenuTemplate/InsetPlanks', 'ODMenuTemplate/InsetTop', 'ODMenuTemplate/InsetBottom', 'ODMenuTemplate/InsetLeft',
         'ODMenuTemplate/InsetRight', 'ODMenuTemplate/InsetTopLeft', 'ODMenuTemplate/InsetTopRight',
         'ODMenuTemplate/InsetBottomLeft', 'ODMenuTemplate/InsetBottomRight']
for look_name in ('OD/SheetComboEditbox', 'OD/SheetComboDropList'):
    section = looks[look_name].find("ImagerySection[@name='field']")
    check(section is not None and images_of(section) == INSET, look_name + ' draws the list inset of the sheet')
    states = [s for s in looks[look_name].findall('StateImagery') if s.get('name') in ('Enabled', 'ReadOnly')]
    check(states and all([sec.get('section') for sec in s.iter('Section')] == ['field'] for s in states),
          look_name + ' shows the inset in its states')
check('"All", "Zivs", "Fighters", "Unhappy"' in social_cpp, 'the entries of the filter stay')
check('const char* const FILTER_SELECTION_BRUSH = "ODMenuTemplate/LoadRowSelected";' in social_cpp and
      'item->setSelectionBrushImage(FILTER_SELECTION_BRUSH);' in social_cpp, 'the chosen entry is the sheet\'s row')
filtered = function_of(social_cpp, 'bool SocialWindow::onFilterClicked(')
check('mFilter = filters[item->getID()];' in filtered and 'showPage(Page::Home);' in filtered,
      'choosing an entry filters the list as before')

for failure in failures:
    print('FAIL ' + failure)
print('ODP_TEST_PHASE {"name":"check","seconds":%.2f}' % (time.monotonic() - START))
print('Dungeonbook QS-12 B1: item card drawn in frame %s of entering (before the fix: %s), shown %d of %d frames on the '
      'item; %d scrollbar and drop-down cases at %d screens x %d UI scales; %d failures' % (
          shown[0] - ENTER if shown else None, before[0] - ENTER if before else None, len(shown), LEAVE - ENTER + 1,
          cases, len(SCREENS), len(USER_SCALES), len(failures)))
if failures:
    sys.exit(1)
