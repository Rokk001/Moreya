"""The ghost room page of the Room Manager works on every screen from 640x480 to 8K at UI scale 80 % to 120 %.

Restores the ghost UI range check for the page that replaced the standalone ghost room window. Runs no compiler and
takes no screenshot: the page geometry is resolved like Gui::applyScale and CEGUI do it, and every caption is measured
with the shipped font file (Pillow), not estimated from its length.

Model, read from the shipped files: layout scale s = min(w/1024, h/768) * user scale, shrunk by the fit factor of the
Room Manager frame (Gui::getWindowFitFactor, the frame never gets larger than the screen); fonts scale with
min(w/800, h/600) * user scale and are not fitted (Gui::updateResourceScaling); the frame is the window frame of the
chosen menu sheet (OD/SheetWindow): its rails are the ODMenuTemplate images scaled with the layout scale at the sheet
pixel density of Gui.cpp (before: the DungeonbookIcons images at their native 3840x2160 automatic scaling), and the
title bar starts at three quarters of the top rail and is the line spacing of the title font plus its padding
(OD/SheetWindow; before: the title font line plus 12 pixels of OD/FrameWindow). For 12 screens (including the extreme
aspect ratios 640x4320 and 7680x480) and 5 user scales
(60 cases) it asserts the outcome on the screen:
- the frame lies inside the screen and every control inside its parent;
- no two clickable controls cover one another;
- every caption the production code can show (static texts, every vessel plaque text "x / z" the refresh writes for
  all research levels, the crystal ratio from rooms.cfg) fits on one line inside its control, and no caption's drawn
  text box covers a clickable control or another caption.
Fixed values counted once on this branch (after the U1 rebuild of the page after its chosen mockup: connector lines,
vessel cover, chosen-product frames): 27 windows on the page, 4 clickable controls, 6 captions, 60 cases.

The layouts, the menu sheet imageset and the fonts are content (core-gui package, found through
scripts/content_packages.py); the mixed files (ODSkin.imageset, OD.looknfeel, the fonts, rooms.cfg, skills.cfg) are read
joined with their own rows (content_packages.read_text). Without the content the code of the captions the production
refresh writes is checked and the caption values and the 60 cases are named as not checked.
"""
from itertools import combinations, product
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

from PIL import ImageFont

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'scripts'))
import content_packages  # noqa: E402

#: The content files the screen cases measure (core-gui package)
CONTENT_FILES = ('gui/WindowRoomManager.layout', 'gui/RoomManagerGhostPage.layout', 'gui/ODMenuTemplate.imageset',
                 'gui/fonts/MedievalSharp-8.font')
SCREENS = ((640, 480), (640, 4320), (800, 600), (1024, 768), (1280, 720), (1366, 768), (1920, 1080), (2560, 1440),
           (3440, 1440), (3840, 2160), (7680, 480), (7680, 4320))
SCALES = (.8, .9, 1., 1.1, 1.2)
PAGE_WINDOWS = 27
CLICKABLE = ('OD/Button', 'OD/Checkbox')
CLICKABLE_COUNT = 4
CAPTION_COUNT = 6


def read(path):
    """Reads tracked production input without depending on the current directory (public tree, else content package)."""
    return content_packages.read_layout_text(REPO, path)


def props(node):
    """Returns the explicit CEGUI properties of a window."""
    return {p.get('name'): p.get('value') for p in node.findall('Property')}


def udims(value):
    """Parses the four (relative, offset) pairs of a CEGUI area."""
    pairs = re.findall(r'\{(-?[\d.]+),(-?[\d.]+)\}', value)
    assert len(pairs) == 4, value
    return [(float(a), float(b)) for a, b in pairs]


def rectangle(area, left, top, width, height, scale):
    """Resolves an area against its parent rectangle; offsets are scaled by the layout scale (Gui::scaleRect)."""
    (x0, ox0), (y0, oy0), (x1, ox1), (y1, oy1) = udims(area)
    return (left + x0 * width + ox0 * scale, top + y0 * height + oy0 * scale,
            left + x1 * width + ox1 * scale, top + y1 * height + oy1 * scale)


def inside(inner, outer, tolerance=0.5):
    """True when the inner rectangle has a positive size and lies within the outer one."""
    return (outer[0] - tolerance <= inner[0] < inner[2] <= outer[2] + tolerance and
            outer[1] - tolerance <= inner[1] < inner[3] <= outer[3] + tolerance)


def apart(first, second):
    """True when two rectangles do not overlap (touching edges are allowed)."""
    return (first[2] <= second[0] + 1e-6 or second[2] <= first[0] + 1e-6 or
            first[3] <= second[1] + 1e-6 or second[3] <= first[1] + 1e-6)


class Font:
    """A shipped CEGUI font measured with its TrueType file at a reference size."""

    def __init__(self, name):
        """Opens the TrueType file of a CEGUI font definition."""
        spec = ET.fromstring(read('gui/fonts/' + name + '.font'))
        self.points = float(spec.get('size'))
        assert (spec.get('nativeHorzRes'), spec.get('nativeVertRes')) == ('800', '600'), name
        self.face = ImageFont.truetype(str(content_packages.resolve(REPO, 'gui/fonts/' + spec.get('filename'))), 1024)
        self.line = self.face.font.height / 1024.0

    def pixels(self, font_scale):
        """The pixel size at the given font scale: points at 96 dpi, scaled like CEGUI's ASM_Min automatic scaling."""
        return self.points * 4.0 / 3.0 * font_scale

    def width(self, text, font_scale):
        """Width of one line of text in screen pixels."""
        return self.face.getlength(text) / 1024.0 * self.pixels(font_scale)

    def height(self, font_scale):
        """Line spacing in screen pixels (FreeType size metrics height, CEGUI LineSpacing)."""
        return self.line * self.pixels(font_scale)


FONTS = {}


def font(name):
    """Caches the measured fonts."""
    if name not in FONTS:
        FONTS[name] = Font(name)
    return FONTS[name]


def walk(node, path=''):
    """Lists (path, node, parent path) of every window below a node."""
    result = []
    for child in node.findall('Window'):
        name = path + child.get('name')
        result.append((name, child, path.rstrip('/')))
        result += walk(child, name + '/')
    return result


def frame_contract():
    """Reads the frame, border and title data the model uses from the shipped files."""
    manager = ET.ElementTree(ET.fromstring(content_packages.read_layout_text(REPO, 'gui/WindowRoomManager.layout'))).getroot().find('Window')
    frame = props(manager)
    (fx0, fox0), (fy0, foy0), (fx1, fox1), (fy1, foy1) = udims(frame['Area'])
    assert (fx0, fy0, fx1, fy1) == (.5, .5, .5, .5), 'a centred frame of fixed design size'
    assert manager.get('type') == 'OD/SheetWindow', 'the Room Manager uses the window frame of the menu sheet'
    images = ET.parse(content_packages.resolve(REPO, 'gui/ODMenuTemplate.imageset')).getroot()
    sizes = {i.get('name'): (float(i.get('width')), float(i.get('height'))) for i in images.findall('Image')}
    looks = read('gui/OD.looknfeel')
    look = looks[looks.index('<WidgetLook name="OD/SheetWindow">'):]
    look = look[:look.index('</WidgetLook>')]
    for key in ('FrameLeft', 'FrameRight', 'FrameBottom', 'FrameTop'):
        assert 'ImageDim name="ODMenuTemplate/%s"' % key in look, key + ' is not a rail of the sheet frame'
    border = {key: sizes[key] for key in ('FrameLeft', 'FrameRight', 'FrameBottom', 'FrameTop')}
    title_match = re.search(r'<FontDim font="([\w-]+)" padding="(\d+)" type="LineSpacing" />', look)
    title_font, title_padding = title_match.group(1), float(title_match.group(2))
    assert re.search(r'name="TitlebarFont" targetProperty="Font"', look)
    assert 'initialValue="%s" name="TitlebarFont"' % title_font in look, 'the title font is the font of the title height'
    assert 'TitlebarFont' not in frame, 'the title font of the sheet title is fixed'
    pages = {n.get('name'): n for n in manager.iter('Window')}['Pages']
    checkbox = ET.fromstring(read('gui/ODSkin.imageset')).find("Image[@name='CheckboxNormal']")
    gui = read('source/render/Gui.cpp')
    skin_density = float(re.search(r'SKIN_IMAGE_PIXEL_DENSITY = ([\d.]+)f;', gui).group(1))
    sheet_density = float(re.search(r'MENU_SHEET_IMAGE_PIXEL_DENSITY = ([\d.]+)f;', gui).group(1))
    assert 'startsWith(name, "ODMenuTemplate/")' in gui, 'the sheet frame scales with the layout'
    for fragment in ('const float scale = layoutScale * getWindowFitFactor(window);', 'FONT_DESIGN_WIDTH / mUserScale',
                     'setAutoScaled(CEGUI::ASM_Min);', 'return startsWith(name, "OpenDungeonsSkin/")'):
        assert fragment in gui, fragment
    return {'width': fox1 - fox0, 'height': foy1 - foy0, 'border': border, 'title_font': title_font,
            'title_padding': title_padding, 'sheet_density': sheet_density, 'pages': props(pages)['Area'],
            'checkbox_inset': float(checkbox.get('width')) / skin_density}


def captions(with_values=True):
    """Every text the page can show, per control: layout texts and the values the production refresh writes. Without
    the values (no content: rooms.cfg and skills.cfg lack their own rows) only the code of the refresh is checked."""
    game = read('source/modes/GameMode.cpp')
    refresh = game[game.index('void GameMode::refreshGhostRoomWindow()'):]
    refresh = refresh[:refresh.index('\n}\n')]
    # Whole levels on the plaque; a fractional target keeps one decimal.
    assert 'text << static_cast<int64_t>(std::floor(progress + 1e-9)) << " / ";' in refresh
    assert 'if(std::fabs(perEctoplasm - std::floor(perEctoplasm + 0.5)) < 1e-9)' in refresh
    assert 'text << static_cast<int64_t>(std::floor(perEctoplasm + 0.5));' in refresh
    assert 'text << std::fixed << std::setprecision(1) << perEctoplasm;' in refresh
    assert 'page->getChild("GhostBarText")->setText(text.str());' in refresh
    assert 'const double progress = perEctoplasm > 0.0 ? std::fmod(seat->getEctoplasmLevels(), perEctoplasm) : 0.0;' in refresh
    assert 'Helper::toString(config.getRoomConfigDouble("GhostEctoplasmPerCrystal")) + " : 1"' in refresh
    if not with_values:
        return None
    base = float(re.search(r'^GhostLevelsPerEctoplasm\s+([\d.]+)', read('config/rooms.cfg'), re.M).group(1))
    research = re.search(r'^\s*roomGhostRoom\s+EctoplasmLevels\s+mul\s+([\d.\s]+)$', read('config/skills.cfg'), re.M)
    texts = {'GhostBarText': []}
    for factor in research.group(1).split():
        per = base * float(factor)
        whole = abs(per - int(per + 0.5)) < 1e-9
        target = '%d' % int(per + 0.5) if whole else '%.1f' % per
        texts['GhostBarText'] += ['%d / %s' % (k, target) for k in range(int(per + 1e-9) + 1)]
    crystal = float(re.search(r'^GhostEctoplasmPerCrystal\s+([\d.]+)', read('config/rooms.cfg'), re.M).group(1))
    texts['Ratio2'] = ['%.6g : 1' % crystal]
    return texts


def check():
    """Runs the 60 screen and scale cases on the ghost page."""
    contract = frame_contract()
    root = ET.ElementTree(ET.fromstring(content_packages.read_layout_text(REPO, 'gui/RoomManagerGhostPage.layout'))).getroot().find('Window')
    assert root.get('name') == 'GhostPage' and props(root)['Area'] == '{{0,0},{0,0},{1,0},{1,0}}'
    windows = walk(root)
    assert len(windows) + 1 == PAGE_WINDOWS, len(windows) + 1
    clickable = [path for path, node, _ in windows if node.get('type') in CLICKABLE]
    assert len(clickable) == CLICKABLE_COUNT, clickable
    dynamic = captions()
    texts = {}
    for path, node, _ in windows:
        values = dynamic.get(path, []) + ([props(node)['Text']] if props(node).get('Text') else [])
        if values:
            texts[path] = values
    assert len(texts) == CAPTION_COUNT, sorted(texts)
    title = font(contract['title_font'])
    for (width, height), user in product(SCREENS, SCALES):
        raw = min(width / 1024.0, height / 768.0) * user
        fit = min(1.0, width / (contract['width'] * raw), height / (contract['height'] * raw))
        scale = raw * fit
        font_scale = min(width / 800.0, height / 600.0) * user
        image_scale = raw / contract['sheet_density']
        frame = ((width - contract['width'] * scale) / 2, (height - contract['height'] * scale) / 2,
                 (width + contract['width'] * scale) / 2, (height + contract['height'] * scale) / 2)
        case = (width, height, user)
        assert inside(frame, (0, 0, width, height)), (case, 'frame inside the screen')
        left = frame[0] + contract['border']['FrameLeft'][0] * image_scale
        right = frame[2] - contract['border']['FrameRight'][0] * image_scale
        top = (frame[1] + 0.75 * contract['border']['FrameTop'][1] * image_scale + title.height(font_scale)
               + contract['title_padding'])
        bottom = frame[3] - contract['border']['FrameBottom'][1] * image_scale
        assert left < right and top < bottom, (case, 'client area')
        page = rectangle(contract['pages'], left, top, right - left, bottom - top, scale)
        assert inside(page, (left, top, right, bottom)), (case, 'page inside the frame')
        rects = {'': page}
        for path, node, parent in windows:
            outer = rects[parent]
            rects[path] = rectangle(props(node)['Area'], outer[0], outer[1], outer[2] - outer[0], outer[3] - outer[1], scale)
            assert inside(rects[path], outer), (case, path, 'inside its parent')
        for first, second in combinations(clickable, 2):
            assert apart(rects[first], rects[second]), (case, first, second, 'clickable controls apart')
        boxes = {}
        for path, values in texts.items():
            node = dict((p, n) for p, n, _ in windows)[path]
            q = props(node)
            face = font(q.get('Font', 'MedievalSharp-10'))
            box = rects[path]
            inset = contract['checkbox_inset'] * scale + 3.0 if node.get('type') == 'OD/Checkbox' else 0.0
            available = box[2] - box[0] - inset
            assert 'WordWrap' not in q.get('HorzFormatting', ''), (path, 'one-line captions')
            line = face.height(font_scale)
            assert line <= box[3] - box[1] + 0.5, (case, path, 'caption height', line, box[3] - box[1])
            widest = max(face.width(text, font_scale) for text in values)
            assert widest <= available + 0.5, (case, path, 'caption width', widest, available)
            centred = q.get('HorzFormatting') == 'CentreAligned'
            text_left = box[0] + inset + ((available - widest) / 2 if centred else 0.0)
            middle = (box[1] + box[3]) / 2
            boxes[path] = (text_left, middle - line / 2, text_left + widest, middle + line / 2)
        for path, box in boxes.items():
            for control in clickable:
                if path != control and not path.startswith(control + '/'):
                    assert apart(box, rects[control]), (case, path, control, 'caption covers a control')
        for first, second in combinations(boxes, 2):
            assert apart(boxes[first], boxes[second]), (case, first, second, 'captions overlap')
    return len(SCREENS) * len(SCALES)


def main():
    """Runs the fixed-scope range check of the ghost room page; without the content only the captions of the code."""
    missing = [name for name in CONTENT_FILES if content_packages.data_file(REPO, name) is None]
    if not content_packages.has_content(REPO):
        missing += ['caption values of config/rooms.cfg and config/skills.cfg']
    if missing:
        captions(with_values=False)
        content_packages.unchecked('check_ghost_ui_range', missing)
        print('ghost UI range: captions of the production refresh: ok')
        return
    cases = check()
    print('ghost UI range: Room Manager ghost page, %d windows, %d clickable, %d captions, %d screen/scale cases: ok'
          % (PAGE_WINDOWS, CLICKABLE_COUNT, CAPTION_COUNT, cases))


if __name__ == '__main__':
    main()
