"""Check the menu button template and the load screen of the chosen menu sheet (INGAME-QS-10 K14, K15, T-M1, G6).

The chosen sheet is variant 2 of the menu concepts ("weathered timber with aged iron bindings"), kept with the asset sources
at <ODP_ASSETS_SRC>/ingame-qs-9/d1/variant-2.png. Static check, no game and no compiler needed. It checks the outcome:

1. Pixels. The four template states in gui/ODMenuTemplate.png are the states painted on the sheet (normal, hovered,
   pressed, disabled), pixel for pixel outside the caption; the painted caption "Campaign" is gone from every state; the
   pointer hand painted over the hovered state is replaced by the template's own mirrored end; the states differ as on
   the sheet (hovered rim brighter, pressed planks redder, disabled without colour). The same holds for the compact
   form the sheet paints inside the load screen, and the load screen panel keeps the sheet's frame while its painted
   buttons, highlighted row and scrollbar are removed.
2. Looks. Every state of the menu button looks (OD.looknfeel) draws exactly the five (compact: three) pieces of its own
   template state, and the caps and knobs keep the proportions of the template pieces at every button size.
3. Screens. Every button of every menu screen (main menu, its sub menus, skirmish, multiplayer, settings, load, configure
   seats, campaign, editor) is a template button; the expected numbers were counted once on this branch.
4. Sizes. At 640x480, 1920x1200 and 7680x4320 (8K), each with the UI scale 80 % and 120 %, every template button lies on
   the screen, is never narrower than its caps and knobs, shows its caption on the planks without cutting it, and
   overlaps no other control; the load screen controls lie on the panel at the places of the sheet.
"""
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image, ImageFont

repo = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo / 'scripts'))
from assets_src import assets_src_dir  # noqa: E402

gui = repo / 'gui'
SHEET = assets_src_dir(repo) / 'ingame-qs-9/d1/variant-2.png'
assert SHEET.is_file(), 'chosen menu sheet missing: %s' % SHEET
sheet = np.asarray(Image.open(SHEET).convert('RGB')).astype(np.int32)
assert sheet.shape == (1200, 1920, 3), sheet.shape
atlas = np.asarray(Image.open(gui / 'ODMenuTemplate.png').convert('RGBA')).astype(np.int32)
imageset = ET.parse(gui / 'ODMenuTemplate.imageset').getroot()
assert imageset.get('name') == 'ODMenuTemplate' and imageset.get('imagefile') == 'ODMenuTemplate.png'
pieces = {i.get('name'): tuple(int(i.get(k)) for k in ('xPos', 'yPos', 'width', 'height')) for i in imageset.findall('Image')}

# ------------------------------------------------------------------------------------------------ 1. pixels
# Places of the template states on the sheet (top left corner of the 400x120 state; measured once on the sheet).
STATE_ON_SHEET = {'Normal': (56, 380), 'Hover': (57, 524), 'Pushed': (58, 670), 'Disabled': (57, 818)}
CAPTION = (108, 34, 296, 88)          # painted caption inside a state
HAND_COLUMNS = 300                    # the pointer hand covers the hovered state from here to the right
STATES = ('Normal', 'Hover', 'Pushed', 'Disabled')
FULL_PIECES = ('LeftCap', 'LeftFill', 'Centre', 'RightFill', 'RightCap')


def assemble(names):
    """The atlas pieces side by side, as the look draws them at the template's own size."""
    parts = []
    for name in names:
        x, y, w, h = pieces[name]
        parts.append(atlas[y:y + h, x:x + w])
    heights = {p.shape[0] for p in parts}
    assert len(heights) == 1, names
    return np.concatenate(parts, 1)


def letters(image, grey):
    """Pixels in the colour of the painted captions: warm bone letters, or light grey letters of the disabled state."""
    red, green, blue = image[..., 0], image[..., 1], image[..., 2]
    if grey:
        return (image[..., :3].mean(axis=2) > 88) & ((red - blue) < 40)
    return (red > 150) & (green > 120) & (blue > 85)


def saturation(image):
    """Mean difference between the strongest and the weakest colour channel (0 for grey)."""
    rgb = image[..., :3].astype(np.float64)
    return float((rgb.max(axis=2) - rgb.min(axis=2)).mean())


full = {}
for state in STATES:
    image = assemble([state + piece for piece in FULL_PIECES])
    assert image.shape == (120, 400, 4), (state, image.shape)
    full[state] = image
    sx, sy = STATE_ON_SHEET[state]
    painted = sheet[sy:sy + 120, sx:sx + 400]
    solid = image[..., 3] == 255
    keep = solid.copy()
    keep[CAPTION[1]:CAPTION[3], CAPTION[0]:CAPTION[2]] = False
    if state == 'Hover':
        keep[:, HAND_COLUMNS - 10:] = False
    difference = np.abs(image[..., :3] - painted)[keep].mean()
    assert keep.sum() > 15000 and difference < 0.5, '%s state is not the painted template (%.2f)' % (state, difference)
    x0, y0, x1, y1 = CAPTION
    before = letters(painted[y0:y1, x0:x1], state == 'Disabled').sum()
    after = letters(image[y0:y1, x0:x1], state == 'Disabled').sum()
    assert before > 1000 and after == 0, '%s state still shows the painted caption (%d of %d pixels)' % (state, after, before)
    # outline: transparent outside the cut corners and the knobs, solid on the planks and the knobs
    assert image[0, 0, 3] == 0 and image[119, 399, 3] == 0 and image[5, 100, 3] == 0, state + ' outline not cut free'
    assert image[60, 200, 3] == 255 and image[4, 201, 3] > 128 and image[116, 201, 3] > 128, state + ' plate or knob missing'
# The hand: the hovered right end is the mirrored left end of the hovered state and no longer the painted hand.
hover = full['Hover'][:, :, :3]
mirror = hover[:, ::-1]
right = slice(HAND_COLUMNS + 14, 398)
sx, sy = STATE_ON_SHEET['Hover']
hand_area = (slice(70, 118), slice(312, 372))
assert np.abs(hover[:, right] - mirror[:, right]).mean() < 0.5, 'hovered right end is not the template end'
assert np.abs(sheet[sy:sy + 120, sx:sx + 400][hand_area] - hover[hand_area]).mean() > 20, 'pointer hand still painted'
# The states differ as on the sheet.
rim = np.zeros((120, 400), bool)
rim[8:22, 30:370] = True
rim[99:113, 30:370] = True
planks = (slice(26, 96), slice(70, 330))
assert full['Hover'][..., :3][rim].mean() > full['Normal'][..., :3][rim].mean() + 15, 'hovered rim does not glow'
redness = {s: float((full[s][planks][..., 0] - full[s][planks][..., 2]).mean()) for s in STATES}
assert redness['Pushed'] > redness['Normal'] + 15, 'pressed planks are not ember lit'
assert saturation(full['Disabled']) < 0.6 * saturation(full['Normal']), 'disabled state keeps its colour'

# Compact form (load screen): normal = "Back", hovered = "Confirm", pressed = "Delete" of the sheet, 4 pixel margin.
COMPACT_ON_SHEET = {'Normal': (1461, 910), 'Hover': (1656, 910), 'Pushed': (1259, 910)}
compact = {}
for state in STATES:
    image = assemble(['Compact' + state + piece for piece in ('LeftCap', 'Fill', 'RightCap')])
    compact[state] = image
    height, width = image.shape[:2]
    assert height == 76 and image[0, 0, 3] == 0 and image[38, width // 2, 3] == 255, state + ' compact outline'
    cap = pieces['Compact' + state + 'LeftCap'][2]
    if state in COMPACT_ON_SHEET:
        sx, sy = COMPACT_ON_SHEET[state]
        painted = sheet[sy:sy + height, sx:sx + width]
        caps = np.zeros((height, width), bool)
        caps[:, :cap] = caps[:, width - cap:] = True
        caps &= image[..., 3] == 255
        assert np.abs(image[..., :3] - painted)[caps].mean() < 0.5, state + ' compact caps are not the painted ones'
        inner = (slice(18, 58), slice(cap, width - cap))
        assert letters(painted[inner], False).sum() > 200 and letters(image[inner], False).sum() == 0, \
            state + ' compact state still shows its painted caption'
assert compact['Hover'][..., :3][compact['Hover'][..., 3] == 255].mean() > \
    compact['Normal'][..., :3][compact['Normal'][..., 3] == 255].mean() + 10, 'compact hovered state does not glow'
assert saturation(compact['Disabled']) < 0.6 * saturation(compact['Normal']), 'compact disabled state keeps its colour'

# Load screen panel: frame as on the sheet, painted controls removed.
PANEL_ON_SHEET = (1222, 283)
x, y, w, h = pieces['LoadPanel']
panel = atlas[y:y + h, x:x + w]
px, py = PANEL_ON_SHEET
painted_panel = sheet[py:py + h, px:px + w]
frame = np.zeros((h, w), bool)
frame[:40, :] = frame[-40:, :] = frame[:, :30] = frame[:, -30:] = True
frame &= panel[..., 3] == 255
assert frame.sum() > 50000 and np.abs(panel[..., :3] - painted_panel)[frame].mean() < 0.5, 'load screen frame is not the sheet'
for name, (x0, y0, x1, y1) in {'filter buttons': (1250, 352, 1862, 426), 'buttons': (1255, 900, 1858, 1010)}.items():
    region = (slice(y0 - py, y1 - py), slice(x0 - px, x1 - px))
    assert letters(painted_panel[region], False).sum() > 1000 and letters(panel[region], False).sum() == 0, \
        'load screen panel still shows the painted ' + name
row = (slice(484 - py, 524 - py), slice(1272 - px, 1792 - px))
assert panel[row][..., 0].mean() < painted_panel[row][..., 0].mean() - 30, 'highlighted list row still painted'
x, y, w, h = pieces['LoadRowSelected']
assert np.abs(atlas[y:y + h, x:x + w, :3] - sheet[484:524, 1272:1792]).mean() < 0.5, 'selected row is not the sheet row'

# ------------------------------------------------------------------------------------------------ 2. looks
look_text = (gui / 'OD.looknfeel').read_text(encoding='utf-8')
looks = {wl.get('name'): wl for wl in ET.fromstring(look_text).findall('WidgetLook')}


def find_section(look, name):
    """An imagery section of a look or of the looks it inherits from."""
    while look is not None:
        for section in looks[look].findall('ImagerySection'):
            if section.get('name') == name:
                return section
        look = looks[look].get('inherits')
    raise AssertionError('section %s not found' % name)


def state_images(look, state):
    """Images drawn by one state imagery of a look."""
    imagery = [s for s in looks[look].findall('StateImagery') if s.get('name') == state]
    assert len(imagery) == 1, (look, state)
    images = []
    for section in imagery[0].iter('Section'):
        for image in find_section(section.get('look', look), section.get('section')).iter('Image'):
            images.append(image.get('name'))
    return images


def unified(component, dim_type):
    """The scale of the plain UnifiedDim of a component area dimension (a width that follows the height)."""
    dim = [d for d in component.find('Area').findall('Dim') if d.get('type') == dim_type][0]
    unified_dim = dim.find('UnifiedDim')
    return float(unified_dim.get('scale')), unified_dim.get('type')


EXPECTED_STATES = {'Normal': 'Normal', 'Hover': 'Hover', 'Pushed': 'Pushed', 'PushedOff': 'Normal', 'Disabled': 'Disabled'}
for look, prefix, names in (('OD/MenuTextButton', '', FULL_PIECES), ('OD/MenuCompactButton', 'Compact', ('LeftCap', 'Fill', 'RightCap'))):
    for state, template_state in EXPECTED_STATES.items():
        expected = sorted('ODMenuTemplate/' + prefix + template_state + n for n in names)
        assert sorted(state_images(look, state)) == expected, (look, state, state_images(look, state))
    # Caps and knobs keep the template proportions: their width follows the height by the ratio of the atlas pieces.
    for section in ('plate_normal', 'plate_hover', 'plate_pushed', 'plate_disabled'):
        for component in find_section(look, section).findall('ImageryComponent'):
            image = component.find('Image').get('name').split('/', 1)[1]
            x, y, w, h = pieces[image]
            if image.endswith('Cap') or image.endswith('Centre'):
                scale, base = unified(component, 'Width')
                assert base == 'Height' and abs(scale - w / float(h)) < 1e-4, (look, image, scale, w / float(h))
for state, template_state in EXPECTED_STATES.items():
    for prefix, chosen in (('', template_state), ('Selected', 'Disabled' if state == 'Disabled' else
                                                  'Pushed' if state == 'Pushed' else 'Hover')):
        expected = sorted('ODMenuTemplate/Compact' + chosen + n for n in ('LeftCap', 'Fill', 'RightCap'))
        assert sorted(state_images('OD/MenuFilterButton', prefix + state)) == expected, ('filter', prefix + state)
scheme = (gui / 'ODSkin.scheme').read_text(encoding='utf-8')
for window_type, target in (('OD/MenuTextButton', 'CEGUI/PushButton'), ('OD/MenuCompactButton', 'CEGUI/PushButton'),
                            ('OD/MenuFilterButton', 'CEGUI/RadioButton'), ('OD/LoadListbox', 'CEGUI/Listbox')):
    assert re.search(r'lookNFeel="%s" renderer="[^"]+" targetType="%s" windowType="%s"' % (window_type, target, window_type),
                     scheme), window_type
assert '<Imageset filename="ODMenuTemplate.imageset" name="ODMenuTemplate" />' in scheme
load_code = (repo / 'source/modes/MenuModeLoad.cpp').read_text(encoding='utf-8')
assert load_code.count('setSelectionBrushImage("ODMenuTemplate/LoadRowSelected")') == 1, 'chosen save not shown as the sheet row'

# ------------------------------------------------------------------------------------------------ 3. screens
TEMPLATE_TYPES = ('OD/MenuTextButton', 'OD/MenuCompactButton', 'OD/MenuFilterButton')
MENU_LAYOUTS = ('MenuMain.layout', 'WindowCampaignSubMenu.layout', 'WindowSkirmishSubMenu.layout',
                'WindowMultiplayerSubMenu.layout', 'WindowEditorSubMenu.layout', 'WindowSettingsSubMenu.layout',
                'MenuCampaign.layout', 'MenuSkirmish.layout', 'MenuMultiplayerServer.layout', 'MenuMultiplayerClient.layout',
                'MenuMasterServerJoin.layout', 'MenuLoad.layout', 'MenuReplay.layout', 'MenuConfigureSeats.layout',
                'MenuEditorLoad.layout', 'MenuEditorNew.layout', 'WindowSettings.layout', 'WindowApplyChanges.layout')
# Template buttons per screen, counted once on this branch.
EXPECTED_BUTTONS = {'MenuMain.layout': 7, 'WindowCampaignSubMenu.layout': 4, 'WindowSkirmishSubMenu.layout': 3,
                    'WindowMultiplayerSubMenu.layout': 5, 'WindowEditorSubMenu.layout': 3, 'WindowSettingsSubMenu.layout': 5,
                    'MenuCampaign.layout': 4, 'MenuSkirmish.layout': 2, 'MenuMultiplayerServer.layout': 2,
                    'MenuMultiplayerClient.layout': 2, 'MenuMasterServerJoin.layout': 2, 'MenuLoad.layout': 7,
                    'MenuReplay.layout': 3, 'MenuConfigureSeats.layout': 4, 'MenuEditorLoad.layout': 2,
                    'MenuEditorNew.layout': 2, 'WindowSettings.layout': 2, 'WindowApplyChanges.layout': 2}
button_targets = set(re.findall(r'targetType="CEGUI/(?:PushButton|RadioButton)" windowType="([^"]+)"', scheme)) | {'OD/IconButton'}
for layout in MENU_LAYOUTS:
    windows = list(ET.parse(gui / layout).getroot().iter('Window'))
    buttons = [w for w in windows if w.get('type') in button_targets]
    other = [w.get('name') for w in buttons if w.get('type') not in TEMPLATE_TYPES]
    assert not other, '%s: buttons without the menu template: %s' % (layout, other)
    assert len(buttons) == EXPECTED_BUTTONS[layout], (layout, len(buttons))

# ------------------------------------------------------------------------------------------------ 4. sizes
DESIGN_W, DESIGN_H = 1024.0, 768.0
FONT_W, FONT_H = 800.0, 600.0
SCREENS = ((640, 480), (1920, 1200), (7680, 4320))
USER_SCALES = (0.8, 1.2)
TOLERANCE = 0.75
CAPTION_AREA = {'OD/MenuTextButton': (0.516667, 0.183333, 0.816667), 'OD/MenuCompactButton': (0.25, 0.21, 0.79),
                'OD/MenuFilterButton': (0.25, 0.21, 0.79)}
# Narrowest button that still shows both caps and (full template) the knobs undistorted, in button heights.
MIN_WIDTH = {'OD/MenuTextButton': (pieces['NormalLeftCap'][2] + pieces['NormalCentre'][2] + pieces['NormalRightCap'][2]) / 120.0,
             'OD/MenuCompactButton': 2 * 26 / 76.0, 'OD/MenuFilterButton': 2 * 26 / 76.0}
CONTROLS = TEMPLATE_TYPES + ('OD/Editbox', 'OD/Combobox', 'OD/Checkbox', 'OD/MenuListbox', 'OD/LoadListbox',
                             'OD/MenuMultiColumnList', 'OD/MultiLineEditbox', 'OD/Spinner', 'OD/TabControl')
fonts = {}
for font_file in (gui / 'fonts').glob('*.font'):
    spec = ET.parse(font_file).getroot()
    fonts[spec.get('name')] = (ImageFont.truetype(str(gui / 'fonts' / spec.get('filename')), 1024),
                               float(spec.get('size')) * (96.0 / 72.0) / 1024.0)
skin_set = ET.parse(gui / 'ODSkin.imageset').getroot()
skin = {i.get('name'): (float(i.get('width')), float(i.get('height'))) for i in skin_set.findall('Image')}
game_set = ET.parse(gui / 'ODGameWindow.imageset').getroot()
game_window = {i.get('name'): (float(i.get('width')), float(i.get('height'))) for i in game_set.findall('Image')}


def udims(value):
    """The (scale, offset) pairs of a CEGUI area value like {{0.5,-120},{0.5,10},...}."""
    return [(float(a), float(b)) for a, b in re.findall(r'\{(-?[\d.]+),(-?[\d.]+)\}', value)]


class Node:
    """One window of a layout with its properties and children (imported layouts included)."""

    def __init__(self, element, parent, layout):
        self.parent, self.layout = parent, layout
        self.type, self.name = element.get('type'), element.get('name')
        self.props = {p.get('name'): p.get('value') for p in element.findall('Property')}
        self.children = []
        for child in element:
            if child.tag == 'Window':
                self.children.append(Node(child, self, layout))
            elif child.tag == 'LayoutImport':
                for imported in ET.parse(gui / child.get('filename')).getroot().findall('Window'):
                    self.children.append(Node(imported, self, child.get('filename')))

    def font(self):
        """Font of the window, inherited from the parents as CEGUI does."""
        node = self
        while node is not None:
            if 'Font' in node.props:
                return node.props['Font']
            node = node.parent
        return 'LiberationSans-10'

    def visible(self):
        """Whether the layout shows the window from the start."""
        return self.props.get('Visible') != 'False'


def is_fill(node):
    """Whether the window fills its parent."""
    return udims(node.props.get('Area', '')) == [(0, 0), (0, 0), (1, 0), (1, 0)]


def screen_sized(node):
    """Gui::isScreenSizedContainer: no parent, or a window that fills a screen sized parent."""
    return node is None or (is_fill(node) and screen_sized(node.parent))


def fit_factor(node, screen, scale):
    """Gui::getWindowFitFactor: shrink factor that keeps a top window on the screen."""
    value = udims(node.props.get('Area', ''))
    factor = 1.0
    off_w, off_h = (value[2][1] - value[0][1]) * scale, (value[3][1] - value[1][1]) * scale
    rel_w, rel_h = value[2][0] - value[0][0], value[3][0] - value[1][0]
    if off_w > 0 and rel_w < 1.0:
        factor = min(factor, (1.0 - rel_w) * screen[0] / off_w)
    if off_h > 0 and rel_h < 1.0:
        factor = min(factor, (1.0 - rel_h) * screen[1] / off_h)
    return factor


def line_height(font, screen, user):
    """Line height of a font in screen pixels (fonts scale with 800x600 design and the UI scale)."""
    face, factor = fonts[font]
    return sum(face.getmetrics()) * factor * min(screen[0] / (FONT_W / user), screen[1] / (FONT_H / user))


def client(node, rect, screen, user, s):
    """Children area: the window without its frame and title (frame windows of OD.looknfeel), else the window."""
    x0, y0, x1, y1 = rect
    layout_scale = min(screen[0] / DESIGN_W, screen[1] / DESIGN_H) * user
    if node.type == 'OD/MenuFrameWindow':
        edge = layout_scale / 4.0
        return (x0 + skin['WindowLeftEdge'][0] * edge, y0 + line_height('MedievalSharp-10', screen, user) + 12.0,
                x1 - skin['WindowRightEdge'][0] * edge, y1 - skin['WindowBottomEdge'][1] * edge)
    if node.type == 'OD/SheetWindow':
        top = sheet_image('FrameTop', screen, user)[1]
        if node.props.get('TitlebarEnabled', 'True') == 'True':
            top = 0.75 * top + line_height(node.props.get('TitlebarFont', 'MedievalSharp-13'), screen, user) + 4.0
        return (x0 + sheet_image('FrameLeft', screen, user)[0], y0 + top,
                x1 - sheet_image('FrameRight', screen, user)[0], y1 - sheet_image('FrameBottom', screen, user)[1])
    if node.type == 'OD/FrameWindow':
        return (x0 + game_window['FrameLeft'][0], y0 + line_height('MedievalSharp-10', screen, user) + 12.0,
                x1 - game_window['FrameRight'][0], y1 - game_window['FrameBottom'][1])
    return rect


def sheet_image(name, screen, user):
    """Screen size of an ODMenuTemplate image: the game scales the sheet pictures by the layout scale at the sheet's
    density (Gui.cpp MENU_SHEET_IMAGE_PIXEL_DENSITY)."""
    layout_scale = min(screen[0] / DESIGN_W, screen[1] / DESIGN_H) * user
    return pieces[name][2] / SHEET_DENSITY * layout_scale, pieces[name][3] / SHEET_DENSITY * layout_scale


def plate(node, rect):
    """The visible plate of a template button: the knobs of the full template stand above and below the plate and may
    reach over the neighbouring button, as on the sheet."""
    if node.type != 'OD/MenuTextButton':
        return rect
    height = rect[3] - rect[1]
    return rect[0], rect[1] + 8.5 / 120.0 * height, rect[2], rect[3] - 7.5 / 120.0 * height


def inside(inner, outer):
    """Whether a rectangle lies inside another one (renderer rounding allowed)."""
    return inner[0] >= outer[0] - TOLERANCE and inner[1] >= outer[1] - TOLERANCE and inner[2] <= outer[2] + TOLERANCE \
        and inner[3] <= outer[3] + TOLERANCE


def collect(node, parent_client, screen, user, fit, out):
    """Pixel rectangles of a window and its children (formulas of Gui::applyScale) appended to out."""
    if 'Area' not in node.props:
        return
    layout_scale = min(screen[0] / DESIGN_W, screen[1] / DESIGN_H) * user
    if not screen_sized(node) and screen_sized(node.parent):
        fit = fit_factor(node, screen, layout_scale)
    s = layout_scale * fit
    value = udims(node.props['Area'])
    px0, py0, px1, py1 = parent_client
    rect = (px0 + value[0][0] * (px1 - px0) + value[0][1] * s, py0 + value[1][0] * (py1 - py0) + value[1][1] * s,
            px0 + value[2][0] * (px1 - px0) + value[2][1] * s, py0 + value[3][0] * (py1 - py0) + value[3][1] * s)
    out.append((node, rect))
    if node.type in ('OD/TabControl',):
        return
    # Hidden windows (sub menus, dialogs, the briefing) are shown by the code later and are measured as well.
    for child in node.children:
        collect(child, client(node, rect, screen, user, s), screen, user, fit, out)


def overlaps(a, b):
    """Whether two rectangles share more than the renderer rounding."""
    return min(a[2], b[2]) - max(a[0], b[0]) > TOLERANCE and min(a[3], b[3]) - max(a[1], b[1]) > TOLERANCE


SHEET_DENSITY = float(re.search(r'MENU_SHEET_IMAGE_PIXEL_DENSITY = ([0-9.]+)f',
                                 (repo / 'source/render/Gui.cpp').read_text(encoding='utf-8'))[1])
assert SHEET_DENSITY == 1.5625, 'the sheet is painted for 1920x1200: 1.5625 sheet pixels per design pixel'
FRAME_TYPES = ('OD/SheetWindow', 'OD/SheetPanel', 'OD/SheetStaticText')
MAIN_BUTTONS = ('StartCampaignButton', 'StartSkirmishButton', 'MultiplayerModeButton', 'LoadGameButton', 'MapEditorButton',
                'SettingsButton', 'QuitButton')
# Main menu column of the chosen sheet in sheet pixels (1920x1200), measured once on the sheet: plates 708 to 1075 wide,
# 77 high, tops 383, 471, 557, 643, 730, 815, 906; the button area adds the knobs of the template (8.5 and 7.5 of 120).
SHEET_COLUMN_WIDTH = 371.0
SHEET_COLUMN_HEIGHT = 88.8
SHEET_COLUMN_TOPS = (376.7, 464.7, 550.7, 636.7, 723.7, 808.7, 899.7)
# The whole column stands 13.75 sheet pixels (8.8 design pixels) higher than on the sheet, so that its last entry stays
# inside the window 480 design pixels high that check_menu_resources.py requires of the main menu.
SHEET_COLUMN_SHIFT = -13.75
# The windows of the menu screens (K34), counted once on this branch: 17 framed windows; the settings window gets its
# frame and centred place from SettingsWindow.cpp (checked below).
MENU_WINDOWS = {'MenuMain.layout': (), 'WindowCampaignSubMenu.layout': ('WindowPanel',),
                'WindowSkirmishSubMenu.layout': ('WindowPanel',), 'WindowMultiplayerSubMenu.layout': ('WindowPanel',),
                'WindowEditorSubMenu.layout': ('WindowPanel',), 'WindowSettingsSubMenu.layout': ('WindowPanel',),
                'MenuCampaign.layout': ('BriefingPanel',), 'MenuSkirmish.layout': ('WindowPanel',),
                'MenuMultiplayerServer.layout': ('WindowPanel',), 'MenuMultiplayerClient.layout': ('WindowPanel',),
                'MenuMasterServerJoin.layout': ('WindowPanel',), 'MenuLoad.layout': ('LoadPanel',),
                'MenuReplay.layout': ('WindowPanel',), 'MenuConfigureSeats.layout': ('ListPlayers', 'GameSettingsWindow'),
                'MenuEditorLoad.layout': ('WindowPanel',), 'MenuEditorNew.layout': ('LevelWindowFrame',),
                'WindowSettings.layout': (), 'WindowApplyChanges.layout': ('ConfirmRestart',)}
assert sum(len(v) for v in MENU_WINDOWS.values()) == 17
# Controls that belong to a window drawn by a frame panel beside them; the description of a save is shown below the
# load screen panel because the sheet's panel has no place for it.
WINDOW_CONTENT = CONTROLS + ('OD/MenuTitle', 'OD/StaticText', 'OD/StaticImage', 'DefaultWindow')
BELOW_THE_WINDOW = {('MenuLoad.layout', 'MapDescriptionText')}
# Gate entrance of the 3D menu scene: centre of the front opening of MenuGate.mesh in mesh coordinates, measured once
# from the mesh vertices (OgreXMLConverter): the opening runs from x -4.434 to 4.359 at the front face (y -3.0) between
# 0.5 and 3 above the ground; its centre x is -0.0375. The column centre may be at most 2 screen pixels beside it.
ENTRANCE_LOCAL = (-0.0375, -3.0, 1.75)
ENTRANCE_TOLERANCE = 2.0
scene_cfg = (repo / 'config/mainmenuscene.cfg').read_text(encoding='utf-8')
camera_code = (repo / 'source/camera/CameraManager.cpp').read_text(encoding='utf-8')
OVERVIEW_POSE = [float(v) for v in re.search(r'(?m)^Pose overview ([-\d. ]+)$', scene_cfg)[1].split()]
GATE_POSITION = [float(v) for v in re.search(r'(?m)^AddEntity Gate MenuGate\.mesh ([-\d. ]+)$', scene_cfg)[1].split()]
MENU_FOV_Y = float(re.search(r'MAIN_MENU_DEFAULT_FOV_Y_DEGREES = ([\d.]+)f', camera_code)[1])
reference = re.search(r'MAIN_MENU_REFERENCE_ASPECT_RATIO = ([\d.]+)f / ([\d.]+)f', camera_code)
MENU_REFERENCE_ASPECT = float(reference[1]) / float(reference[2])


def entrance_screen_x(screen):
    """Screen x of the gate entrance seen from the overview pose (CameraManager::setViewportSize projection, pose
    rotation X then Y then Z as RenderSceneMenu applies it; an Ogre camera looks down -Z)."""
    import math
    position = np.array(OVERVIEW_POSE[:3])
    rx, ry, rz = [math.radians(v) for v in OVERVIEW_POSE[3:6]]
    x_rot = np.array([[1, 0, 0], [0, math.cos(rx), -math.sin(rx)], [0, math.sin(rx), math.cos(rx)]])
    y_rot = np.array([[math.cos(ry), 0, math.sin(ry)], [0, 1, 0], [-math.sin(ry), 0, math.cos(ry)]])
    z_rot = np.array([[math.cos(rz), -math.sin(rz), 0], [math.sin(rz), math.cos(rz), 0], [0, 0, 1]])
    rotation = x_rot @ y_rot @ z_rot
    point = np.array(GATE_POSITION) + np.array(ENTRANCE_LOCAL)
    local = rotation.T @ (point - position)
    assert local[2] < 0, 'the gate is behind the overview camera'
    aspect = screen[0] / float(screen[1])
    half_fov_y = math.atan(math.tan(math.radians(MENU_FOV_Y) / 2.0) * max(1.0, MENU_REFERENCE_ASPECT / aspect))
    ndc = (local[0] / -local[2]) / (math.tan(half_fov_y) * aspect)
    return screen[0] / 2.0 * (1.0 + ndc)


checked = 0
for layout in MENU_LAYOUTS:
    roots = [Node(w, None, layout) for w in ET.parse(gui / layout).getroot().findall('Window')]
    for screen in SCREENS:
        for user in USER_SCALES:
            placed = []
            for root in roots:
                collect(root, (0.0, 0.0, float(screen[0]), float(screen[1])), screen, user, 1.0, placed)
            for node, rect in placed:
                if node.type not in TEMPLATE_TYPES:
                    continue
                checked += 1
                where = '%s %s at %dx%d %d%%' % (layout, node.name, screen[0], screen[1], round(user * 100))
                x0, y0, x1, y1 = rect
                width, height = x1 - x0, y1 - y0
                assert x0 >= -TOLERANCE and y0 >= -TOLERANCE and x1 <= screen[0] + TOLERANCE and y1 <= screen[1] + TOLERANCE, \
                    where + ' leaves the screen'
                assert width >= MIN_WIDTH[node.type] * height - TOLERANCE, where + ' is narrower than its caps and knobs'
                cap, top, bottom = CAPTION_AREA[node.type]
                caption = node.props.get('Text', '')
                if caption:
                    face, factor = fonts[node.font()]
                    font_scale = factor * min(screen[0] / (FONT_W / user), screen[1] / (FONT_H / user))
                    left, ink_top, right, ink_bottom = face.getbbox(caption, anchor='lm')
                    assert face.getlength(caption) * font_scale <= width - 2 * cap * height + TOLERANCE, \
                        where + ' caption wider than the planks'
                    assert (ink_bottom - ink_top) * font_scale <= (bottom - top) * height + TOLERANCE, \
                        where + ' caption higher than the planks'
                for other, other_rect in placed:
                    if other is node or other.type not in CONTROLS or other.parent is not node.parent:
                        continue
                    if other.visible() != node.visible():
                        continue  # the code shows one of the two instead of the other
                    if other.type in ('OD/Combobox',):
                        other_rect = (other_rect[0], other_rect[1], other_rect[2],
                                      min(other_rect[3], other_rect[1] + 1.5 * line_height(other.font(), screen, user)))
                    if other.type in TEMPLATE_TYPES:
                        other_rect = plate(other, other_rect)
                    assert not overlaps(plate(node, rect), other_rect), '%s overlaps %s' % (where, other.name)
            rects = {}
            for node, rect in placed:
                rects.setdefault(node.name, (node, rect))
            # K34: every menu window is drawn in the window frame of the sheet and centred on the screen; the controls
            # placed beside its frame panel lie inside the frame.
            for name in MENU_WINDOWS[layout]:
                node, rect = rects[name]
                where = '%s %s at %dx%d %d%%' % (layout, name, screen[0], screen[1], round(user * 100))
                assert node.type in FRAME_TYPES or node.props.get('Image') == 'ODMenuTemplate/LoadPanel', \
                    where + ' is not in the window frame of the chosen sheet'
                assert abs((rect[0] + rect[2]) / 2.0 - screen[0] / 2.0) <= 1.0 and \
                    abs((rect[1] + rect[3]) / 2.0 - screen[1] / 2.0) <= 1.0 + 0.06 * screen[1], where + ' is not centred'
                assert inside(rect, (0, 0, screen[0], screen[1])), where + ' leaves the screen'
                if node.type in ('OD/SheetWindow', 'OD/SheetStaticText'):
                    continue  # its controls are its children, laid out in its client area
                interior = (rect[0] + sheet_image('FrameLeft', screen, user)[0] * 0.5,
                            rect[1] + sheet_image('FrameTop', screen, user)[1] * 0.5,
                            rect[2] - sheet_image('FrameRight', screen, user)[0] * 0.5,
                            rect[3] - sheet_image('FrameBottom', screen, user)[1] * 0.5)
                for other, other_rect in placed:
                    if other.parent is not node.parent or other is node or other.type not in WINDOW_CONTENT \
                            or (layout, other.name) in BELOW_THE_WINDOW:
                        continue
                    if other.type == 'OD/Combobox':
                        other_rect = other_rect[:3] + (min(other_rect[3], other_rect[1] + 1.5 * line_height(other.font(), screen, user)),)
                    assert inside(plate(other, other_rect), interior), '%s: %s leaves the window frame' % (where, other.name)
            if layout == 'MenuLoad.layout':
                panel = rects['LoadPanel'][1]
                # the load screen panel sits in the middle of the screen at every size and UI scale
                assert abs((panel[0] + panel[2]) / 2.0 - screen[0] / 2.0) <= 1.0 and \
                    abs((panel[1] + panel[3]) / 2.0 - screen[1] / 2.0) <= 1.0, \
                    'load screen not centred at %dx%d %d%%' % (screen[0], screen[1], round(user * 100))
                for name in ('KindFilter', 'SaveGameSelect', 'DeleteButton', 'BackButton', 'LaunchButton'):
                    assert inside(rects[name][1], panel), name + ' leaves the load screen panel'
                w, h = pieces['LoadPanel'][2:]
                assert abs((panel[2] - panel[0]) / (panel[3] - panel[1]) - w / float(h)) < 0.01, 'load panel distorted'
                assert not overlaps(rects['MapDescriptionText'][1], panel), 'description covers the load screen panel'
            if layout == 'MenuMain.layout':
                # The column stands exactly over the gate entrance of the 3D menu scene at the overview camera pose.
                entrance = entrance_screen_x(screen)
                for name in MAIN_BUTTONS:
                    x0, y0, x1, y1 = rects[name][1]
                    assert abs((x0 + x1) / 2.0 - entrance) <= ENTRANCE_TOLERANCE, \
                        '%s is %.1f pixels beside the gate entrance at %dx%d %d%%' % (
                            name, (x0 + x1) / 2.0 - entrance, screen[0], screen[1], round(user * 100))
            if layout == 'MenuMain.layout' and screen == (1920, 1200):
                # The column of the chosen sheet: at 1920x1200 the buttons have the sheet's size and rows (the horizontal place is
                # the gate entrance, checked above), scaled
                # around the screen centre by the UI scale.
                for index, name in enumerate(MAIN_BUTTONS):
                    x0, y0, x1, y1 = rects[name][1]
                    assert abs((x1 - x0) / user - SHEET_COLUMN_WIDTH) <= 2.0, name + ' width differs from the sheet'
                    assert abs((y1 - y0) / user - SHEET_COLUMN_HEIGHT) <= 2.0, name + ' height differs from the sheet'
                    assert abs(600.0 + (y0 - 600.0) / user - SHEET_COLUMN_TOPS[index] - SHEET_COLUMN_SHIFT) <= 3.0, name + ' row differs from the sheet'

# K34: no main menu button is visible while a menu window is open, and Back shows the main menu again.
gui_code = (repo / 'source/render/Gui.cpp').read_text(encoding='utf-8')
for layout in MENU_LAYOUTS:
    if layout == 'MenuMain.layout' or layout.endswith('SubMenu.layout') or layout in ('WindowSettings.layout',
                                                                                     'WindowApplyChanges.layout'):
        continue
    names = {w.get('name') for w in ET.parse(gui / layout).getroot().iter('Window')}
    # a window of its own sheet: the main menu sheet with its buttons is replaced while it is shown
    assert not names & set(MAIN_BUTTONS), layout + ' shows main menu buttons'
    assert re.search(r'mSheets\[\w+\] = +wmgr->loadLayoutFromFile\("%s"\)' % re.escape(layout), gui_code), layout + ' is no sheet'
main_code = (repo / 'source/modes/MenuModeMain.cpp').read_text(encoding='utf-8').replace('\r\n', '\n')


def body(code, signature):
    """Body of a function of a source file."""
    return code.split(signature, 1)[1].split('\n}', 1)[0]


show_sub = body(main_code, 'void MenuModeMain::showSubMenu')
assert 'setVisible(other == name)' in show_sub and 'showMainMenuButtons(false);' in show_sub, 'a sub menu window must hide the main menu'
assert 'showMainMenuButtons(true)' not in body(main_code, 'bool MenuModeMain::openSettingsPage'), 'settings keep the main menu hidden'
back = body(main_code, 'bool MenuModeMain::goBack')
assert 'window->hide();' in back and 'showMainMenuButtons(true);' in back and 'mOverviewPending' in back, 'Back must restore the main menu'
assert 'mOverviewPending = false;\n        showMainMenuButtons(true);' in body(main_code, 'void MenuModeMain::onFrameStarted'), \
    'the main menu returns after the flight back'
load_mode = (repo / 'source/modes/MenuModeLoad.cpp').read_text(encoding='utf-8')
assert 'loadGuiSheet(Gui::guiSheet::loadSavedGameMenu)' in load_mode and 'return goBack();' in load_mode, \
    'the load screen must replace the main menu sheet and go back to it'
settings_code = (repo / 'source/modes/SettingsWindow.cpp').read_text(encoding='utf-8')
menu_branch = settings_code.split('if(menuPages)', 1)[1].split('else if(gamePage)', 1)[0]
assert 'setLookNFeel("OD/SheetWindow")' in menu_branch and 'CEGUI::UDim(0.5f, -MENU_WINDOW_HALF_HEIGHT)' in menu_branch \
    and 'CEGUI::UDim(0.5f, MENU_WINDOW_HALF_HEIGHT)' in menu_branch, 'the settings window of the main menu must be a centred sheet window'

# The window frame pieces are the load screen frame of the sheet, the border pieces the sheet's screen border.
px, py = PANEL_ON_SHEET
lx, ly = pieces['LoadPanel'][:2]
for name in ('FrameTopLeft', 'FrameTopRight', 'FrameBottomLeft', 'FrameBottomRight', 'FrameTop', 'FrameBottom', 'FrameLeft',
             'FrameRight', 'FrameTopKnob', 'FrameBottomKnob'):
    x, y, w, h = pieces[name]
    part = atlas[y:y + h, x:x + w]
    painted = sheet[py + y - ly:py + y - ly + h, px + x - lx:px + x - lx + w]
    solid = part[..., 3] == 255
    # leave out the wood the tool wove in where the sheet paints the filter buttons and the three buttons
    for x0, y0, x1, y1 in ((1250, 352, 1862, 426), (1255, 900, 1858, 1010)):
        rows = slice(max(0, y0 - (py + y - ly)), max(0, y1 - (py + y - ly)))
        columns = slice(max(0, x0 - (px + x - lx)), max(0, x1 - (px + x - lx)))
        solid[rows, columns] = False
    assert solid.sum() > 0.4 * w * h and np.abs(part[..., :3] - painted)[solid].mean() < 0.5, name + ' is not the sheet frame'
for name, (sx, sy) in {'BorderTopLeft': (0, 0), 'BorderTopRight': (1810, 0), 'BorderBottomLeft': (0, 1090),
                       'BorderBottomRight': (1810, 1090), 'BorderTopPendant': (925, 0), 'BorderBottomPendant': (925, 1142)}.items():
    x, y, w, h = pieces[name]
    part = atlas[y:y + h, x:x + w]
    solid = part[..., 3] == 255
    assert solid.sum() > 0.15 * w * h and np.abs(part[..., :3] - sheet[sy:sy + h, sx:sx + w])[solid].mean() < 0.5, \
        name + ' is not the sheet border'
x, y, w, h = pieces['FrameInterior']
tile = atlas[y:y + h, x:x + w, :3]
assert np.abs(tile[0] - tile[-1]).mean() < 25 and np.abs(tile[:, 0] - tile[:, -1]).mean() < 25, 'interior tile shows seams'
assert tile.std() > 8, 'interior wood has no painted detail'
for look in ('OD/SheetPanel', 'OD/SheetStaticText'):
    for state in looks[look].findall('StateImagery'):
        if state.get('name') in ('Enabled', 'EnabledFrame'):
            drawn = {i.get('name') for sec in state.iter('Section') for i in find_section(sec.get('look', look), sec.get('section')).iter('Image')}
            assert {'ODMenuTemplate/FrameTopLeft', 'ODMenuTemplate/FrameInterior', 'ODMenuTemplate/FrameTopKnob'} <= drawn, look
for state in looks['OD/SheetWindow'].findall('StateImagery'):
    drawn = {i.get('name') for sec in state.iter('Section') for i in find_section('OD/SheetWindow', sec.get('section')).iter('Image')}
    assert {'ODMenuTemplate/FrameTopLeft', 'ODMenuTemplate/FrameBottomRight', 'ODMenuTemplate/FrameInterior'} <= drawn, state.get('name')
for layout in MENU_LAYOUTS:
    if layout.startswith('Menu'):
        assert any(w.get('type') == 'OD/ScreenBorder' for w in ET.parse(gui / layout).getroot().iter('Window')), \
            layout + ' lacks the screen border of the sheet'
print('MENU BUTTON TEMPLATE OK: 4 states and the compact form match the chosen sheet; %d menu screens; '
      '%d button placements at 3 screens x 2 UI scales; %d menu windows framed and centred; main menu column as on the sheet'
      % (len(MENU_LAYOUTS), checked, sum(len(v) for v in MENU_WINDOWS.values())))
