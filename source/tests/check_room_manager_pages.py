"""Room Manager pages as their chosen mockups (R6, K10, K11): elements, look, states and 440 screen/scale fit cases.

Per page the check asserts every element R6 and K10 name, where they sit relative to each other (connector lines that
really join the vessel to the products, medallions joined by the line that carries the switch, the infirmary controls on
one row inside the inner panel, ...), and the states the client code sets: the green path and the gold frame follow the
chosen ghost product, the payer medallion gets the gold ring and the coin, the tavern ticks the drink it serves now (beer,
or water while beer is not researched). State rules are taken from the production functions and evaluated for every
input, so a state that does not reach the page fails. Every page is fitted at 640x480 up to 8K (1920x1200 included) and
UI scale 80 % to 120 %. Pictures that are placeholders until they are repainted are named in the output, never passed
as final.

This check does not compile. The companion page-events check executes production callbacks in FINAL; it supports
--source-only while the plan is in progress.

The Room Manager window, its pages, the imagesets and the artwork are game data of the content packages
(scripts/content_packages.py): they are read from the public tree or from the content packages. Without the content
the page contracts are named as not checked and only the code contracts run.
"""
from pathlib import Path
import math
import re
import sys
import xml.etree.ElementTree as ET

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import content_packages  # noqa: E402
import room_packages  # noqa: E402

#: The game data files the page contracts need first; they lie in the public tree or in a content package
DATA_FILES = ('gui/WindowRoomManager.layout', 'gui/ODSkin.scheme', 'gui/RoomManagerGhostPage.layout')
RESOLUTIONS = ((640, 480), (800, 600), (1024, 768), (1280, 720), (1366, 768), (1920, 1080), (1920, 1200),
               (2560, 1440), (3440, 1440), (3840, 2160), (7680, 4320))
SCALES = (.8, .9, 1., 1.1, 1.2)
EXPECTED_SCREEN_CASES = 440
# Room Manager window in design pixels: 880x710 inside the ornate frame before, 898x730 in the window frame of the menu
# sheet so that the client area keeps its size at 1920x1200 (counted once on this branch).
WINDOW_W, WINDOW_H = 898, 730
# Rails of the sheet frame in design pixels: ODMenuTemplate FrameLeft/FrameRight 32, FrameTop/FrameBottom 44 sheet
# pixels at 1.5625 sheet pixels per design pixel.
SHEET_RAIL_SIDE, SHEET_RAIL_TOP, SHEET_RAIL_BOTTOM = 32 / 1.5625, 44 / 1.5625, 44 / 1.5625
PAYER = ('PayerLine', 'KeeperRing', 'Keeper', 'KeeperCoin', 'KeeperLabel',
         'CreatureRing', 'Creature', 'CreatureCoin', 'CreatureLabel')
REQUIRED = {
    'Merchant': ('StockList', 'ModeButton/Box', 'ModeButton/Check', 'ModeButton/Label', 'ProfitButton/Box',
                 'ProfitButton/Check', 'ProfitButton/Label', 'MarginSlider', 'MarginLabel', 'EmptyScales', 'EmptyCount',
                 'Confirmation/Item', 'Confirmation/Name', 'Confirmation/Price', 'Confirmation/OK', 'Confirmation/Cancel'),
    'Ghost': ('Vessel', 'Vessel/Empty', 'GhostBarText', 'Stem', 'TrunkUp', 'TrunkDown', 'Path0', 'Path1', 'Path2',
              'GhostProductButton/Selected', 'GhostProductButton/Image', 'GhostProductButton/Lock',
              'Product1/Selected', 'Product1/Image', 'Product1/Lock', 'Product2/Selected', 'Product2/Image',
              'Product2/Lock', 'Ratio0', 'Ratio1', 'Ratio2', 'GhostReviveButton'),
    'Tavern': ('BeerSlot', 'BeerSlot/Beer', 'BeerSlot/BeerLock', 'BeerSlot/BeerServed', 'WaterSlot', 'WaterSlot/Water',
               'WaterSlot/WaterServed', 'PayerButton', 'PayerButton/Arrows') + PAYER,
    'Spa': ('BathRing', 'Bath', 'PriceCoin', 'SpaPriceText', 'KeeperLine', 'CreatureLine', 'SpaPayerButton',
            'SpaPayerButton/Arrows', 'KeeperRing', 'Keeper', 'KeeperCoin', 'KeeperLabel', 'CreatureRing', 'Creature',
            'CreatureCoin', 'CreatureLabel'),
    'Infirmary': ('PatientList', 'InnerPanel', 'PayerButton', 'PayerButton/Arrows', 'HealHeart', 'HealLabel',
                  'HealButton', 'ThresholdLabel', 'Minus', 'ThresholdValue', 'Plus') + PAYER,
    'Alchemy': ('CauldronList', 'HerbPanel', 'Herb0', 'Herb1', 'Herb2', 'Herb3', 'HerbCount0', 'HerbCount1',
                'HerbCount2', 'HerbCount3', 'ModePanel', 'ModeButton', 'ModeButton/Label', 'ModeButton/Potion0',
                'ModeButton/Potion1', 'ModeButton/Potion2'),
    'Casino': ('CasinoPayoutButton/Selected', 'CasinoPayoutButton/Image', 'MoneyButton/Selected', 'MoneyButton/Image',
               'SmilesLabel', 'MoneyLabel'),
    'Workshop': ('Workshops', 'PriorityPanel', 'Orders', 'MoveUp', 'MoveDown'),
}
SAMPLES = {
    'Merchant/MarginLabel': '50 %', 'Merchant/ModeButton/Label': 'Fair', 'Merchant/ProfitButton/Label': 'Profit',
    'Merchant/Confirmation/Name': 'Crown of Iron Resolve', 'Merchant/Confirmation/Price': '1000000',
    'Ghost/GhostBarText': '100 / 100', 'Ghost/Ratio2': '6 : 1', 'Spa/SpaPriceText': '1000',
    'Alchemy/HerbCount0': '4294967295', 'Alchemy/HerbCount1': '4294967295',
    'Alchemy/HerbCount2': '4294967295', 'Alchemy/HerbCount3': '4294967295',
    'Infirmary/ThresholdValue': '100 %', 'Alchemy/ModeButton/Label': 'Combat potions',
}
# New pictures of U1 with their native size; placeholders are repainted later (state file "Codex placeholders").
ARTWORK = {
    'RoomArtworkTavernBeer': ('tavern-beer-mug.png', (128, 128), True),
    'RoomArtworkTavernWater': ('tavern-water-mug.png', (128, 128), True),
    'RoomArtworkInfirmaryHeart': ('infirmary-heart.png', (152, 144), True),
    'RoomArtworkPayerRing': ('payer-ring.png', (256, 256), True),
    'RoomArtworkPayerSwitch': ('payer-switch.png', (128, 64), True),
    'RoomArtworkConnectorLine': ('connector-line.png', (8, 8), False),
}
GREEN, GREY = 'FF62E06A', 'FF6E6A5E'


def props(node):
    """Read direct CEGUI properties."""
    return {p.get('name'): p.get('value') for p in node.findall('Property')}


def windows(root, prefix=''):
    """Resolve actual nested paths instead of assuming controls are direct children."""
    result = {}
    for child in root.findall('Window'):
        name = prefix + child.get('name')
        result[name] = child
        result.update(windows(child, name + '/'))
    return result


def area(value, width, height, scale):
    """Resolve UDim coordinates using the production offset scaling convention."""
    n = [float(x) for x in re.findall(r'-?\d+(?:\.\d+)?', value)]
    assert len(n) == 8, value
    return (n[0] * width + n[1] * scale, n[2] * height + n[3] * scale,
            n[4] * width + n[5] * scale, n[6] * height + n[7] * scale)


def rel(page, path):
    """Rectangle of a direct page child in page fractions."""
    n = [float(x) for x in re.findall(r'-?\d+(?:\.\d+)?', props(page[path])['Area'])]
    assert n[1] == n[3] == n[5] == n[7] == 0, (path, 'page children are placed relative only')
    return n[0], n[2], n[4], n[6]


def near(a, b, what):
    """Two edges touch: a gap or overlap would show as a broken line in the game."""
    assert abs(a - b) <= 0.002, (what, a, b)


def contains(outer, inner, what):
    """inner lies completely inside outer."""
    assert outer[0] - 1e-6 <= inner[0] and inner[2] <= outer[2] + 1e-6, (what, 'horizontal', outer, inner)
    assert outer[1] - 1e-6 <= inner[1] and inner[3] <= outer[3] + 1e-6, (what, 'vertical', outer, inner)


def function(text, signature):
    """Extract a whole production function body by brace matching."""
    start = text.index(signature)
    opening = text.index('{', start)
    depth, end = 1, opening + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


def evaluate(condition, names):
    """Evaluate a C++ boolean condition of a state rule for one input, without executing anything else."""
    expression = condition.replace('!', ' not ').replace(' not =', '!=').replace('&&', ' and ').replace('||', ' or ')
    assert re.fullmatch(r'[\w\s=!<>()]+', expression), condition
    return bool(eval(expression, {'__builtins__': {}}, names))


def ternary(body, target, names):
    """Value a setProperty/setVisible call on `target` produces for the given inputs."""
    match = re.search(re.escape(target) + r'"\)->(setProperty\("\w+",|setVisible\()\s*([^;]*?)\);', body)
    assert match, (target, 'state never set')
    value = match.group(2).strip()
    parts = re.fullmatch(r'(.+?)\s*\?\s*"(\w+)"\s*:\s*"(\w+)"', value)
    if parts:
        return parts.group(2) if evaluate(parts.group(1), names) else parts.group(3)
    return evaluate(value, names)


def fit_page(name, page, manager):
    """Check all children and visible label samples across the required screen matrix."""
    cases = 0
    for width, height in RESOLUTIONS:
        for user in SCALES:
            raw = min(width / 1024., height / 768.) * user
            scale = raw * min(1., width / (WINDOW_W * raw), height / (WINDOW_H * raw))
            font_scale = min(width / 800., height / 600.) * user
            # Window frame of the chosen menu sheet (OD/SheetWindow): side rails, the title (one 13 point line and 4
            # pixels) on the top rail from three quarters of its height, bottom rail; the rails follow the layout scale
            # (not the fit factor), as the scaled ODMenuTemplate images do.
            title = 0.75 * SHEET_RAIL_TOP * raw + 13 * 4 / 3 * 1.35 * font_scale + 4
            fw = WINDOW_W * scale - 2 * SHEET_RAIL_SIDE * raw
            fh = WINDOW_H * scale - title - SHEET_RAIL_BOTTOM * raw
            bounds = area(props(manager['Pages'])['Area'], fw, fh, scale)
            pw, ph = bounds[2] - bounds[0], bounds[3] - bounds[1]
            assert WINDOW_W * scale <= width + .5 and WINDOW_H * scale <= height + .5
            sizes = {'': (pw, ph)}
            for path, node in page.items():
                parent = path.rpartition('/')[0]
                cw, ch = sizes[parent]
                q = props(node)
                left, top, right, bottom = area(q['Area'], cw, ch, scale)
                assert -.01 <= left < right <= cw + .5, (name, path, width, height, user, 'horizontal bounds')
                assert -.01 <= top < bottom <= ch + .5, (name, path, width, height, user, 'vertical bounds')
                bw, bh = right - left, bottom - top
                sizes[path] = (bw, bh)
                text = SAMPLES.get(name + '/' + path, q.get('Text', ''))
                if not text:
                    continue
                points = float(q.get('Font', 'MedievalSharp-10').rsplit('-', 1)[1])
                px = points * 4 / 3 * font_scale
                if node.get('type') == 'OD/Button':
                    bw -= 12 * scale
                if node.get('type') == 'OD/Checkbox':
                    bw -= 28 * scale
                assert bw > 0, (name, path, 'text inset')
                line_count = max(1, math.ceil(len(text) * .52 * px * 1.15 / bw))
                assert line_count * 1.35 * px <= bh + .5, (name, path, width, height, user, text, 'text height', line_count, bw, bh)
                if 'WordWrap' not in q.get('HorzFormatting', ''):
                    assert line_count == 1, (name, path, width, height, user, text, 'wrap')
            cases += 1
    return cases


def check_ghost(page, game, enum):
    """Connector lines join vessel and products; the green path and the gold frame follow the chosen product."""
    vessel, stem = rel(page, 'Vessel'), rel(page, 'Stem')
    up, down = rel(page, 'TrunkUp'), rel(page, 'TrunkDown')
    buttons = ('GhostProductButton', 'Product1', 'Product2')
    near(stem[0], vessel[2], 'stem starts at the vessel')
    assert vessel[1] < stem[1] < stem[3] < vessel[3], 'stem leaves the vessel side'
    near(stem[2], up[0], 'stem reaches the trunk')
    assert up[0] == down[0] and up[2] == down[2], 'one trunk'
    near(up[3], stem[3], 'upper trunk meets the stem')
    near(down[1], stem[1], 'lower trunk meets the stem')
    for index, button in enumerate(buttons):
        path, slot = rel(page, 'Path%d' % index), rel(page, button)
        near(path[0], up[2], 'path %d leaves the trunk' % index)
        near(path[2], slot[0], 'path %d reaches its product' % index)
        assert slot[1] < (path[1] + path[3]) / 2 < slot[3], ('path %d ends at the middle of its product' % index)
        trunk = up if index == 0 else (down if index == 2 else (up[0], stem[1], up[2], stem[3]))
        assert trunk[1] - 0.002 <= path[1] and path[3] <= trunk[3] + 0.002, ('path %d joins the trunk' % index)
        for line in ('Stem', 'TrunkUp', 'TrunkDown', 'Path%d' % index):
            assert props(page[line])['Image'] == 'RoomArtworkConnectorLine/Image' and page[line].get('type') == 'OD/StaticImage'
        assert props(page[button + '/Selected']).get('Visible') == 'False', 'no product framed before the server answers'
    for path, node in page.items():
        assert props(node).get('Text', '') not in ('---', '&lt;&gt;', '<>'), (path, 'placeholder text')
    glass = rel(page, 'Vessel')
    assert glass[2] - glass[0] > 0 and props(page['Vessel/Empty'])['ImageColours'][:2] in ('C0', 'D0', 'E0', 'FF')
    body = function(game, 'void GameMode::refreshGhostRoomWindow(')
    names = re.search(r'names\[\] = \{([^}]*)\}', body).group(1).replace('"', '').replace(' ', '').split(',')
    kinds = re.search(r'kinds\[\] = \{([^}]*)\}', body).group(1).replace('GhostProduct::', '').replace(' ', '').split(',')
    assert names == list(buttons), names
    for button, kind in zip(names, kinds):
        assert props(page[button])['ID'] == str(enum[kind]), (button, 'click selects the product its picture shows')
    assert '"' + GREEN + '"' in body and '"' + GREY + '"' in body
    assert 'button->getChild("Selected")->setVisible(chosen == kinds[index]);' in body
    assert 'empty->setArea(' in body and '(1.0f - fraction)' in body and 'empty->setVisible(fraction < 1.0f)' in body
    assert '"FrameEnabled", chosen' not in body, 'the old thin frame is no longer the marker'
    colours = {'activePath': GREEN, 'idlePath': GREY}
    for chosen in range(3):
        state = {'chosenIndex': chosen, 'activePath': True, 'idlePath': False}
        green = set()
        for line in ('Stem', 'TrunkUp', 'TrunkDown'):
            value = re.search(r'getChild\("' + line + r'"\)->setProperty\("ImageColours", ([^;]*)\);', body).group(1)
            parts = re.fullmatch(r'(.+?)\s*\?\s*(\w+)\s*:\s*(\w+)', value)
            pick = (parts.group(2) if evaluate(parts.group(1), state) else parts.group(3)) if parts else value.strip()
            if colours[pick] == GREEN:
                green.add(line)
        loop = re.search(r'getChild\("Path" \+ Helper::toString\(index\)\)->setProperty\("ImageColours", '
                         r'index == chosenIndex \? activePath : idlePath\);', body)
        assert loop, 'branch colours follow the chosen product'
        green.add('Path%d' % chosen)
        expected = {'Stem', 'Path%d' % chosen} | ({'TrunkUp'} if chosen == 0 else {'TrunkDown'} if chosen == 2 else set())
        assert green == expected, (chosen, green, 'exactly the way from the vessel to the chosen product is green')


def check_payer(page, name, helper, switch='PayerButton'):
    """Medallions joined by the line that carries the switch; the payer gets gold ring and coin."""
    keeper, creature = rel(page, 'KeeperRing'), rel(page, 'CreatureRing')
    contains(keeper, rel(page, 'Keeper'), name + ' keeper icon inside its ring')
    contains(creature, rel(page, 'Creature'), name + ' creature icon inside its ring')
    for ring, label in ((keeper, 'KeeperLabel'), (creature, 'CreatureLabel')):
        text = rel(page, label)
        assert text[1] >= ring[3] and text[0] < (ring[0] + ring[2]) / 2 < text[2], (name, label, 'under its medallion')
    for picture in ('KeeperRing', 'CreatureRing'):
        assert props(page[picture])['Image'] == 'RoomArtworkPayerRing/Image'
    assert props(page[switch]).get('Text', '') == '' and props(page[switch + '/Arrows'])['Image'] == 'RoomArtworkPayerSwitch/Image'
    if 'PayerLine' in page:
        line, button = rel(page, 'PayerLine'), rel(page, switch)
        near(line[0], keeper[2], name + ' line starts at the keeper ring')
        near(line[2], creature[0], name + ' line ends at the creature ring')
        assert button[1] < (line[1] + line[3]) / 2 < button[3] and line[0] < button[0] < button[2] < line[2], \
            (name, 'switch sits on the line')
    body = function(helper, 'inline void roomManagerPayer(')
    for keeper_pays in (True, False):
        state = {'keeper': keeper_pays}
        rings = (ternary(body, 'KeeperRing', state), ternary(body, 'CreatureRing', state))
        coins = (ternary(body, 'KeeperCoin', state), ternary(body, 'CreatureCoin', state))
        payer, other = (0, 1) if keeper_pays else (1, 0)
        assert rings[payer] == 'FFFFFFFF' and rings[other] != 'FFFFFFFF', (name, keeper_pays, 'gold ring on the payer')
        assert coins[payer] is True and coins[other] is False, (name, keeper_pays, 'coin on the payer only')


def check_page_data(images, placeholders, pages):
    """Assert the frame, the artwork and the elements, look and fit of every page; fills the images, the placeholder
    pictures and the pages and returns the number of fitted screen cases. The scheme and the imagesets are read with
    their own rows of the content (scripts/content_packages.py)."""
    manager = ET.ElementTree(ET.fromstring(content_packages.read_layout_text(ROOT, 'gui/WindowRoomManager.layout'))).getroot().find('Window')
    assert manager.get('type') == 'OD/SheetWindow', 'the Room Manager uses the window frame of the menu sheet'
    assert props(manager)['Area'] == '{{0.5,-%g},{0.5,-%g},{0.5,%g},{0.5,%g}}' % (
        WINDOW_W / 2, WINDOW_H / 2, WINDOW_W / 2, WINDOW_H / 2), 'fixed frame design dimensions'
    manager_windows = windows(manager)
    scheme = ET.fromstring(content_packages.read_layout_text(ROOT, 'gui/ODSkin.scheme'))
    for entry in scheme.findall('Imageset'):
        root = ET.fromstring(content_packages.read_layout_text(ROOT, 'gui/' + entry.get('filename')))
        for picture in root.findall('Image'):
            images[root.get('name') + '/' + picture.get('name')] = (root, picture)
    for name, (filename, size, placeholder) in ARTWORK.items():
        root, picture = images[name + '/Image']
        assert root.get('imagefile') == filename, name
        with Image.open(data('gui/RoomCentreArtwork/' + filename)) as artwork:
            assert artwork.size == size == (int(picture.get('width')), int(picture.get('height'))), (name, artwork.size)
        # The CREDITS of the public tree and of the content repository (the rows of the moved artwork stand there)
        credit = [row for row in room_packages.credits_text(ROOT).splitlines()
                  if row.startswith('gui/RoomCentreArtwork/' + filename + ' ')]
        assert len(credit) == 1, (filename, 'one CREDITS row')
        assert ('placeholder until repainted' in credit[0]) == placeholder, (filename, 'placeholder marking')
        if placeholder:
            placeholders.append(filename)
    cases = 0
    for name, required in REQUIRED.items():
        root = ET.ElementTree(ET.fromstring(content_packages.read_layout_text(ROOT, 'gui/RoomManager' + name + 'Page.layout'))).getroot().find('Window')
        page = windows(root)
        pages[name] = page
        assert root.get('type') == 'DefaultWindow'
        for path in required:
            assert path in page, (name, path, 'missing R6/K10 element')
        for path, node in page.items():
            q = props(node)
            assert len(re.findall(r'[A-Za-z]+', q.get('Text', ''))) <= 2, (name, path, 'paragraph or long label')
            assert q.get('Text', '') not in ('<>', '---', '^', 'v'), (name, path, 'text stands in for a picture')
            if 'Image' in q:
                assert q['Image'] in images, (name, path, q['Image'], 'missing image')
            assert path not in ('HistoryPanel', 'HistoryText', 'EmptyText', 'GhostExplainText', 'Explanation',
                                'EctoplasmProgress', 'BeerText', 'OrdersLabel')
        page_cases = fit_page(name, page, manager_windows)
        cases += page_cases
        print('PASS %s elements, images and %d screen/scale cases' % (name, page_cases))
    assert cases == EXPECTED_SCREEN_CASES, cases
    return cases


def data(path):
    """Path of a game data file from the public tree or a content package."""
    return content_packages.resolve(ROOT, path)


def data_present():
    """True when the page contracts can be checked: the data files are found or the content is present (then a
    missing one fails as before); else names them as not checked."""
    missing = [path for path in DATA_FILES if content_packages.data_file(ROOT, path) is None]
    if not missing or content_packages.has_content(ROOT):
        return True
    content_packages.unchecked('check_room_manager_pages', ['the Room Manager pages, imagesets and artwork'] + missing)
    return False


def main():
    """Assert the fixed per-page contract, the state rules and production event/request routing; without the content
    only the code contracts run."""
    DATA = data_present()
    images = {}
    placeholders = []
    pages = {}
    cases = 0
    if DATA:
        cases = check_page_data(images, placeholders, pages)
    game = (ROOT / 'source/modes/GameMode.cpp').read_text()
    merchant = (ROOT / 'source/modes/GameModeMerchant.cpp').read_text()
    lab = (ROOT / 'source/modes/GameModeAlchemy.cpp').read_text()
    helper = (ROOT / 'source/modes/RoomManagerListItem.h').read_text()
    enum = {k: int(v) for k, v in re.findall(r'(\w+) = (\d+)', re.search(
        r'enum class GhostProduct : uint32_t \{([^}]*)\};', (ROOT / 'source/game/SeatData.h').read_text()).group(1))}

    if DATA:
        check_ghost(pages['Ghost'], game, enum)
        assert pages['Ghost']['GhostReviveButton'].get('type') == 'OD/Checkbox'
        print('PASS ghost connector lines, green active path, gold frame on the chosen product, vessel fill')

    if DATA:
        tavern = pages['Tavern']
        assert props(tavern['BeerSlot/Beer'])['Image'] == 'RoomArtworkTavernBeer/Image', 'beer mug, not the barrel'
        assert props(tavern['WaterSlot/Water'])['Image'] == 'RoomArtworkTavernWater/Image'
        assert all('BeerButton' not in props(node).get('Image', '') for node in tavern.values()), 'no barrel'
        check_payer(tavern, 'Tavern', helper)
    body = function(game, 'void GameMode::setTavernWindowShown(')
    for researched in (True, False):
        state = {'beerResearched': researched}
        beer = ternary(body, 'BeerSlot/BeerServed', state)
        water = ternary(body, 'WaterSlot/WaterServed', state)
        assert (beer, water) == (researched, not researched), (researched, 'K11 the served drink has the tick')
        assert ternary(body, 'BeerSlot/BeerLock', state) is (not researched), 'locked beer shows the lock'
    print('PASS tavern mug, water, served drink (K11), medallions and switch on the line')

    if DATA:
        check_payer(pages['Spa'], 'Spa', helper, 'SpaPayerButton')
        spa = pages['Spa']
        ring = rel(spa, 'BathRing')
        for inside in ('Bath', 'PriceCoin', 'SpaPriceText'):
            contains(ring, rel(spa, inside), 'spa ' + inside + ' inside the bath ring')
        near(rel(spa, 'KeeperLine')[0], rel(spa, 'KeeperRing')[2], 'spa keeper line')
        near(rel(spa, 'KeeperLine')[2], ring[0], 'spa keeper line to the bath ring')
        near(rel(spa, 'CreatureLine')[0], ring[2], 'spa creature line from the bath ring')
        near(rel(spa, 'CreatureLine')[2], rel(spa, 'CreatureRing')[0], 'spa creature line')
        assert rel(spa, 'SpaPayerButton')[1] >= ring[3], 'switch under the bath ring'
        print('PASS spa bath ring with price and coin, lines, medallions, switch')

    if DATA:
        infirmary = pages['Infirmary']
        check_payer(infirmary, 'Infirmary', helper)
        panel = rel(infirmary, 'InnerPanel')
        for inside in PAYER + ('PayerButton', 'HealHeart', 'HealLabel', 'HealButton', 'ThresholdLabel', 'Minus',
                               'ThresholdValue', 'Plus'):
            contains(panel, rel(infirmary, inside), 'infirmary ' + inside + ' inside the inner panel')
        row = [rel(infirmary, item) for item in ('ThresholdLabel', 'Minus', 'ThresholdValue', 'Plus')]
        assert all(a[2] <= b[0] + 1e-6 for a, b in zip(row, row[1:])), 'discharge controls left to right'
        assert max(r[1] for r in row) < min(r[3] for r in row), 'discharge controls on one line'
        assert props(infirmary['HealHeart'])['Image'] == 'RoomArtworkInfirmaryHeart/Image'
        assert infirmary['HealButton'].get('type') == 'OD/Checkbox' and props(infirmary['HealButton'])['Text'] == ''
    assert 'item->setSuffix(roomManagerImage("OpenDungeonsIcons/HourglassIcon"), seconds);' in game
    assert 'getCreatureProfilePortraitImage' in game and 'maxHp <= 0.0' in game and 'std::ceil(remaining)' in game
    assert 'row, images, fraction, false, 0xFFB33030' in game
    print('PASS infirmary patients with portrait, bar and time, medallions, heart and tick box, one-line discharge')

    if DATA:
        merchant_page = pages['Merchant']
        for button in ('ModeButton', 'ProfitButton'):
            assert props(merchant_page[button + '/Box']).get('Visible', 'True') == 'True', 'empty tick box always shown'
            assert props(merchant_page[button + '/Check']).get('Visible') == 'False'
            contains((0, 0, 1, 1), rel(windows(merchant_page[button]), 'Box'), button)
        for item in ('EmptyScales', 'EmptyCount'):
            assert props(merchant_page[item]).get('Visible') == 'False'
            contains(rel(merchant_page, 'StockList'), rel(merchant_page, item), item + ' over the empty slots')
        assert props(merchant_page['EmptyCount'])['Text'] == '0'
    for item in ('EmptyScales', 'EmptyCount'):
        assert 'MerchantPage/' + item + '")->setVisible(items.empty());' in merchant, item + ' follows the stock'
    print('PASS merchant tick boxes, margin, empty state, confirmation')

    if DATA:
        alchemy = pages['Alchemy']
        for index in range(4):
            contains(rel(alchemy, 'HerbPanel'), rel(alchemy, 'Herb%d' % index), 'herb in its panel')
        contains(rel(alchemy, 'ModePanel'), rel(alchemy, 'ModeButton'), 'mode in its panel')
        assert props(alchemy['ModeButton']).get('Text', '') == ''
    body = function(lab, 'void GameMode::setLabModeShown(')
    assert '{"Auto", "Healing/mana", "Combat potions"}' in body and 'button->getChild("Label")->setText(labels[mode]);' in body
    assert '{{true, true, true}, {true, true, false}, {false, false, true}}' in body
    print('PASS alchemy framed rows, herb panel, Auto mode with potion pictures')

    if DATA:
        casino = pages['Casino']
    body = function(game, 'void GameMode::setCasinoPayoutShown(')
    for level, chosen in ((1, 'CasinoPayoutButton'), (0, 'MoneyButton')):
        state = {'level': level, 'smiles': 1, 'money': 0}
        flat = body.replace('static_cast<uint32_t>(CasinoPayout::smiles)', 'smiles').replace(
            'static_cast<uint32_t>(CasinoPayout::money)', 'money')
        marks = {button: ternary(flat, button + '/Selected', state) for button in ('CasinoPayoutButton', 'MoneyButton')}
        assert marks == {'CasinoPayoutButton': chosen == 'CasinoPayoutButton', 'MoneyButton': chosen == 'MoneyButton'}
    if DATA:
        assert props(casino['CasinoPayoutButton'])['ID'] == '1' and props(casino['MoneyButton'])['ID'] == '0'
    print('PASS casino gold frame on the chosen picture only')

    if DATA:
        workshop = pages['Workshop']
        for button, direction in (('MoveUp', 'Up'), ('MoveDown', 'Down')):
            q = props(workshop[button])
            assert workshop[button].get('type') == 'OD/InvisibleButton' and q['NormalImage'].endswith('WorkerArrow' + direction + 'Normal')
            assert q['DisabledImage'].endswith('WorkerArrow' + direction + 'Disabled')
            contains(rel(workshop, 'PriorityPanel'), rel(workshop, button), button)
    assert 'new RoomManagerListItem(Helper::toString(index + 1),' in game, 'tile shows only its number'
    assert 'new RoomManagerListItem("", 0, pictures, progress);' in game, 'workshop rows: pictures and bar only'
    assert 'const float numberHeight = height * 0.26f;' in helper and 'drawFrame(' in helper
    print('PASS workshop framed rows, numbered priority tiles, arrow pictures')

    if DATA:
        for text in (game, merchant, lab):
            for name, path in re.findall(r'RoomManagerWindow/Pages/(\w+)Page/([^"\n]+)"\)', text):
                if path.endswith('/'):
                    continue
                assert path in pages[name], (name, path, 'client refers to removed control')
        for path in re.findall(r'page->getChild\("([^"]+)"\)', function(game, 'void GameMode::setTavernWindowShown(')):
            assert path in pages['Tavern'], (path, 'tavern client control')
        for path in re.findall(r'page->getChild\("([^"]+)"\)', function(game, 'void GameMode::refreshGhostRoomWindow(')):
            assert path in pages['Ghost'], (path, 'ghost client control')
    for callback in ('confirmMerchantItem', 'cancelMerchantItem', 'buyMerchantItem', 'hoverMerchantItem',
                     'cycleMerchantMode', 'changeMerchantMargin'):
        assert '&GameMode::' + callback in merchant, callback + ' event disconnected'
    assert 'mMerchantPendingId' in merchant and 'getGold() >= price' in merchant
    assert 'mode == "profit"' in merchant and 'setVisible(mode == "profit")' in merchant
    # The full item card of every item tooltip (plan INGAME-QS-11 K6) with the box of the hovered cell (K11)
    assert 'setTooltipText(Gui::describeItemTooltip(items[index].second, mGameMap, nullptr))' in merchant
    assert 'positionSelf()' in merchant and 'merchantItemAtPointer(list, event.position, &cell)' in merchant
    assert 'historyText(' not in merchant and '/HistoryText' not in merchant
    assert 'setSelected(seat->getGhostRevive())' in game and 'mUpdatingGhost = true' in game
    assert 'isApparatusUnlocked(*seat, nextKind)' in game and 'setEnabled(unlocked)' in game
    assert 'getLevelsPerEctoplasm(*seat)' in game
    for callback in ('cycleGhostProduct', 'toggleGhostRevive', 'cycleTavernPayer', 'cycleSpaPayer',
                     'cycleInfirmaryPayer', 'toggleInfirmaryHealing', 'changeInfirmaryThreshold', 'cycleCasinoPayout',
                     'moveTrapProductionOrderEarlier', 'moveTrapProductionOrderLater', 'cycleLabMode'):
        assert '&GameMode::' + callback in game, callback + ' event disconnected'
    assert 'recipe->getImage()' in lab and 'getCreatureProfilePortraitImage' in lab and 'cauldron.mRemaining' in lab
    assert 'data.mHerbs.find(herb.mId)' in lab and 'setLabModeShown(data.mMode)' in lab
    assert 'mTrapProductionData.orders[selected->getID()].name << earlier' in game
    assert 'order.name == selectedName' in game and 'roomManagerTrapImage(order.type)' in game
    assert 'static_cast<float>(workshop.points) / workshop.required' in game
    if DATA:
        for image in re.findall(r'"([A-Za-z]+(?:TrapButton|CannonButton))"', helper):
            assert 'OpenDungeonsIcons/' + image in images, image + ' production icon'
    assert 'brush.render' in helper and 'std::min(1.0f, mProgress)' in helper
    server = (ROOT / 'source/rooms/RoomMerchant.cpp').read_text()
    assert 'RoomMerchant::sellToKeeper' in server and 'player.pickUpEntity(bag)' in server
    print('PASS production routes, stable item identity, locks, payer/payout, patients, brewing and priority')
    for filename in placeholders:
        print('PLACEHOLDER gui/RoomCentreArtwork/' + filename + ' (not final, repaint listed in the state file)')
    if DATA:
        print('DONE pages=8 screen_cases=%d red=0 placeholders=%d' % (cases, len(placeholders)))
    else:
        print('DONE code contracts; pages not checked (content not present)')


if __name__ == '__main__':
    main()
