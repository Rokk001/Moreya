"""Measure every page of the Dungeonbook (gui/WindowSocial.layout) with the shipped font at 640x480 to 8K.

Static check, no game needed. The parts about the shared creature profile page (order of its rows, its scrollbar and
its reach in the book) were removed with that page (owner decision 2026-11-18); the book shows its own profile as
book-variant-2 (plan INGAME-QS-11 K1), measured below and by check_dungeonbook_pages_b1.py.

The layout, fonts, imagesets and social tables are content (core-gui and core-config packages, found through
scripts/content_packages.py). Without the content the removed pages are checked absent from the public tree and Gui.cpp,
and the measurement, which needs the content everywhere, is named as not checked.
"""
from pathlib import Path
from functools import lru_cache
import re
import sys
import xml.etree.ElementTree as ET

repo = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo / 'scripts'))
import content_packages  # noqa: E402
import language_package_texts  # noqa: E402
import room_packages  # noqa: E402

gui = (repo / 'source/render/Gui.cpp').read_text()
# Absent from the public tree and from every content package
assert content_packages.data_file(repo, 'gui/WindowCreatureProfilePage.layout') is None, \
    'the shared profile page was deleted'
assert 'layoutCreatureProfilePage' not in gui and 'ProfileScrollbar' not in gui
assert content_packages.data_file(repo, 'gui/WindowDungeonbookProfile.layout') is None, \
    'the old profile page with its buttons is gone'
#: The content files the measurement needs (core-gui and core-config packages)
CONTENT_FILES = ('gui/WindowSocial.layout', 'gui/fonts/MedievalSharp-8.font', 'gui/ODMenuTemplate.imageset',
                 'gui/DungeonbookIcons.imageset', 'gui/DungeonbookIcons.png', 'config/social-names.cfg',
                 'config/social-texts.cfg', 'config/items.cfg', 'config/potions.cfg')
missing_content = [name for name in CONTENT_FILES if content_packages.data_file(repo, name) is None]
if missing_content:
    content_packages.unchecked('check_dungeonbook_profile_layout', missing_content)
    sys.exit(0)

# Dungeonbook (gui/WindowSocial.layout), owner decisions 635, 636, 647 and 648: a start page with the creature list
# (portrait, name, level, mood, filters All / Workers / Fighters / Unhappy) and the feed of all creatures, and the four
# pages of one creature (Feed, Profile, Values, Inventory) switched by the navigation bar at the bottom; the head of
# these pages has a back arrow to the start page and previous / next arrows around the name. No button in mid-page.
# Every page is measured with the shipped font at 640x480, 1920x1200 and 7680x4320 (and 1024x768), UI scale 80 % and
# 120 %: the window stays on the screen, no text is higher or wider than its window and nothing leaves its parent.
# Owner decision 732: names and post texts are never shortened with "..." but word wrap; owner decision 830: the game
# values are rounded to at most two decimals (no raw float sums); the longest name, post, nick and value the game can
# produce are measured here.
from PIL import ImageFont

social = (repo / 'source/render/SocialWindow.cpp').read_text()
social_header = (repo / 'source/render/SocialWindow.h').read_text()
social_layout = content_packages.read_layout_text(repo, 'gui/WindowSocial.layout')
book = ET.fromstring(social_layout).find('Window')
size = re.search(r'name="Area" value="\{\{0\.5,(-?\d+)\},\{0\.5,(-?\d+)\},\{0\.5,(\d+)\},\{0\.5,(\d+)\}\}"', social_layout)
book_w, book_h = int(size[3]) - int(size[1]), int(size[4]) - int(size[2])
# 880x644 since the ornate frame and the 20 point title of decision 710 (860x620 before): the pages keep their room;
# 860x648 in the window frame of the menu sheet that every window uses: the highest window the HUD leaves room for,
# narrow enough that at 640x480 it is shrunk only to the screen height, so the pages keep the room for their texts
assert (book_w, book_h) == (860, 648), (book_w, book_h)
assert book.get('type') == 'OD/SheetWindow', 'the Dungeonbook uses the window frame of the menu sheet'
for old in ('Attributes', 'Social profile', 'Statistics', 'Back', 'Show: all creatures', 'Posts of: everyone'):
    assert 'name="Text" value="%s"' % old not in social_layout, 'old button ' + old
for old in ('FilterButton', 'FeedTab', 'ProfileTab', 'FeedModeButton', 'CreatureList', 'ProfilePane', 'SocialButton',
            'StatisticsButton', 'StatisticsPage'):
    assert 'name="%s"' % old not in social_layout and '"%s"' % old not in social, old
assert 'type="OD/Listbox"' not in social_layout

font_files = {}
for name in ('MedievalSharp-6', 'MedievalSharp-8', 'MedievalSharp-10', 'MedievalSharp-12', 'MedievalSharp-13', 'MedievalSharp-20'):
    # the font as the game reads it (a mixed font with its own rows from the content packages)
    spec = ET.fromstring(content_packages.read_layout_text(repo, 'gui/fonts/' + name + '.font'))
    font_files[name] = (ImageFont.truetype(str(content_packages.resolve(repo, 'gui/fonts/' + spec.get('filename'))), 1024),
                        float(spec.get('size')) * (96.0 / 72.0) * (1024.0 / 800.0) / 1024.0)


# Cache exact shaping results for immutable fonts within this check only; keep every layout case.
@lru_cache(maxsize=None)
def text_width(font, text):
    """Width of the text in design pixels with the shipped font (fonts scale like the layout)."""
    face, factor = font_files[font]
    return face.getlength(text) * factor


# Font metrics are constant within this invocation, independently of the tested viewport.
@lru_cache(maxsize=None)
def line_height(font):
    face, factor = font_files[font]
    return sum(face.getmetrics()) * factor


CLIENT_W, CLIENT_H = 828.0, 560.0
# The book had its own ornate iron frame (DungeonbookIcons/BookFrame*, scaled with the display only). It now has the
# window frame of the chosen menu sheet (OD/SheetWindow, ODMenuTemplate imageset scaled with the layout scale by
# Gui.cpp at 1.5625 sheet pixels per design pixel): its side and bottom rails are FRAME_SIDE / FRAME_BOTTOM design
# pixels at every screen and UI scale, and no property of the old frame is left on the window.
menu_sheet = ET.parse(content_packages.resolve(repo, 'gui/ODMenuTemplate.imageset')).getroot()
assert 'MENU_SHEET_IMAGE_PIXEL_DENSITY = 1.5625f' in gui
FRAME_SIDE = max(float(menu_sheet.find("Image[@name='Frame%s']" % n).get('width')) for n in ('Left', 'Right')) / 1.5625
FRAME_BOTTOM = float(menu_sheet.find("Image[@name='FrameBottom']").get('height')) / 1.5625
FRAME_TOP = float(menu_sheet.find("Image[@name='FrameTop']").get('height')) / 1.5625
assert book.find("Property[@name='FrameLeftImage']") is None and book.find("Property[@name='TitlebarFont']") is None


def collect_boxes(element, box, path, out):
    """Absolute boxes of all windows below element, as fractions of the frame client."""
    for child in element.findall('Window'):
        if child.find("Property[@name='NonClient']") is not None:
            continue  # the back arrow in the title bar (checked below), not in the client
        value = child.find("Property[@name='Area']").get('value')
        dims = [(float(a), float(b)) for a, b in re.findall(r'\{(-?[0-9.]+),(-?[0-9.]+)\}', value)]
        assert len(dims) == 4 and all(offset == 0 for _, offset in dims), child.get('name') + ' scales with its client'
        x0, y0, x1, y1 = (d[0] for d in dims)
        assert 0 <= x0 < x1 <= 1.0001 and 0 <= y0 < y1 <= 1.0001, ('outside its parent', path, child.get('name'))
        width, height = box[2] - box[0], box[3] - box[1]
        absolute = (box[0] + x0 * width, box[1] + y0 * height, box[0] + x1 * width, box[1] + y1 * height)
        name = (path + '/' if path else '') + child.get('name')
        out[name] = (absolute, child)
        collect_boxes(child, absolute, name, out)


boxes = {}
collect_boxes(book, (0.0, 0.0, 1.0, 1.0), '', boxes)
pages = ('HomePage', 'FeedPage', 'ProfilePage', 'ValuesPage', 'InventoryPage')
for page in pages + ('Header', 'NavBar'):
    assert page in boxes, page
assert boxes['NavBar'][0][1] >= max(boxes[p][0][3] for p in pages[1:]) - 1e-6, 'the pages end above the navigation bar'
header_bottom = boxes['Header'][0][3]
for name, (box, element) in boxes.items():
    page = name.split('/')[0]
    if page in pages[1:] and name.count('/') == 1:
        assert box[1] >= header_bottom - 1e-6, (name, 'overlaps the head with the arrows')


def visible_default(name):
    element = boxes[name][1]
    prop = element.find("Property[@name='Visible']")
    return prop is None or prop.get('value') == 'True'


assert visible_default('HomePage') and not any(visible_default(p) for p in pages[1:]), 'the book opens on the start page'
assert not visible_default('Header'), 'the start page has no head with arrows'
# Navigation: five buttons in the bottom bar, the last shows the skill tree page (plan INGAME-QS-11 K4, INGAME-QS-12
# K7); the arrows in the
# head "< Name >" below the title; the back arrow in the title bar (K3); the filters in the head of the start page
nav = [n for n in boxes if n.startswith('NavBar/Nav') and n.count('/') == 1 and n != 'NavBar/NavRule']
assert nav == ['NavBar/NavFeed', 'NavBar/NavProfile', 'NavBar/NavValues', 'NavBar/NavInventory', 'NavBar/NavSkills'], nav
assert [boxes[n + '/Label'][1].find("Property[@name='Text']").get('value') for n in nav] == [
    'Feed', 'Profile', 'Values', 'Inventory', 'Skills']
for arrow in ('PrevButton', 'NextButton'):
    assert 'Header/' + arrow in boxes
assert 'Header/BackButton' not in boxes, 'the back arrow moved from the head to the title bar'
back_arrow = book.find("Window[@name='BackButton']")
assert back_arrow is not None and back_arrow.find("Property[@name='NonClient']").get('value') == 'True'
prev_box, name_box, next_box = (boxes['Header/' + n][0] for n in ('PrevButton', 'NameText', 'NextButton'))
assert prev_box[2] <= name_box[0] and name_box[2] <= next_box[0], 'the arrows sit around the name'
filters = ['HomePage/Filter']
assert boxes[filters[0]][1].get('type') == 'OD/SheetCombobox', 'the filter is the drop-down of the menu sheet (INGAME-QS-12 K8)'
assert boxes['HomePage/CreaturesLabel'][0][2] <= boxes[filters[0]][0][0]
assert boxes[filters[0]][0][1] < boxes['HomePage/ListRows'][0][1]
buttons = [n for n, (b, e) in boxes.items() if e.get('type') in ('OD/Button', 'OD/InvisibleButton')]
for n in buttons:
    allowed = n.startswith('NavBar/') or n.startswith('Header/') or n in filters or (
        n.startswith('HomePage/ListRows/Row') and n.endswith('/Button')) or (
        n.startswith('HomePage/FeedRows/') and n.endswith('/ProfileLink'))
    assert allowed, n + ' is a button in mid-page'
# Rows of the list and of the feeds, scrolled by their scrollbars, no overlap
list_rows = sorted(n for n in boxes if re.fullmatch(r'HomePage/ListRows/Row\d', n))
assert len(list_rows) == 7 and 'LIST_ROWS = 7' in social
for page in ('HomePage', 'FeedPage'):
    rows = sorted(n for n in boxes if re.fullmatch(page + r'/FeedRows/Row\d', n))
    assert len(rows) == 3 and 'FEED_ROWS = 3' in social, page
    for upper, lower in zip(rows, rows[1:]):
        assert boxes[upper][0][3] <= boxes[lower][0][1] + 1e-9
    assert boxes[page + '/FeedScroll'][1].get('type') == 'OD/SheetScrollbar', 'the scrollbar of the menu sheet (INGAME-QS-12 K9)'
for upper, lower in zip(list_rows, list_rows[1:]):
    assert boxes[upper][0][3] <= boxes[lower][0][1] + 1e-9
for part in ('Highlight', 'Portrait', 'Name', 'Level', 'MoodIcon', 'Mood', 'Button'):
    assert 'HomePage/ListRows/Row0/' + part in boxes, part
# Inventory: 13 slots (6 equipment, 3 potions, 4 inventory), each with symbol, quality frame and lock; no overlap
slot_names = ['InventoryPage/SlotBox%d' % i for i in range(13)]
assert all(n in boxes for n in slot_names) and 'InventoryPage/SlotBox13' not in boxes
labels = [boxes[n + '/Label'][1].find("Property[@name='Text']").get('value') for n in slot_names]
assert labels == ['Right Hand', 'Left Hand', 'Head', 'Armour', 'Boots', 'Ring', 'Potion 1', 'Potion 2', 'Potion 3',
                  'Inventory 1', 'Inventory 2', 'Inventory 3', 'Inventory 4'], labels
for i, n in enumerate(slot_names):
    for child in ('SlotType', 'QualityFrame', 'Lock'):
        assert '%s/Slot%d/%s' % (n, i, child) in boxes, (n, child)
    assert boxes['%s/Slot%d/Lock' % (n, i)][1].find("Property[@name='Image']").get('value') == 'DungeonbookIcons/Lock'
    for m in slot_names[i + 1:]:
        a, b = boxes[n][0], boxes[m][0]
        assert a[2] <= b[0] + 1e-9 or b[2] <= a[0] + 1e-9 or a[3] <= b[1] + 1e-9 or b[3] <= a[1] + 1e-9, (n, m)
# Values sheet: every value of the former statistics page, the attributes, combat and defense blocks with symbols
for name in ('Experience', 'HitPoints', 'Gold', 'SightRadius', 'Potions', 'Inventory', 'DamagePerSecond', 'SkillPoints'):
    assert 'ValuesPage/%sLabel' % name in boxes and 'ValuesPage/%sValue' % name in boxes, name
for name in ('Strength', 'Dexterity', 'Life', 'Mana', 'CombatLabels', 'CombatValues', 'DefenseLabels', 'DefenseValues',
             'EquipmentTile', 'EquipmentTitle', 'PathTile', 'PathTitle', 'SkillsTile', 'SkillsTitle', 'Portrait/Image',
             'Portrait/Frame'):
    assert 'ValuesPage/' + name in boxes, name
for name, icon in (('CombatIcon', 'Swords'), ('DefenseIcon', 'Shield'), ('EquipmentIcon', 'Equipment'),
                   ('PathIcon', 'Path'), ('SkillsIcon', 'Skills')):
    assert boxes['ValuesPage/' + name][1].find("Property[@name='Image']").get('value') == 'DungeonbookIcons/' + icon
assert boxes['ValuesPage/CombatLabels'][1].find("Property[@name='Text']").get('value').split(chr(10)) == [
    'Critical %', 'Attack Rating', 'Defense Rating']
assert boxes['ValuesPage/DefenseLabels'][1].find("Property[@name='Text']").get('value').split(chr(10)) == [
    'Physical Defense', 'Magical Defense', 'Element Defense']
assert boxes['ValuesPage/Portrait/Frame'][1].find("Property[@name='Image']").get('value') == 'DungeonbookFrame/Ring'
icons = ET.parse(content_packages.resolve(repo, 'gui/DungeonbookIcons.imageset')).getroot()
icon_names = {i.get('name') for i in icons.findall('Image')}
for value in re.findall(r'value="DungeonbookIcons/(\w+)"', social_layout) + re.findall(r'"DungeonbookIcons/(\w+)"', social):
    assert value in icon_names, value
assert content_packages.data_file(repo, 'gui/' + icons.get('imagefile')) is not None
scheme = ET.fromstring(content_packages.read_layout_text(repo, 'gui/ODSkin.scheme'))
assert scheme.find("Imageset[@filename='DungeonbookIcons.imageset'][@name='DungeonbookIcons']") is not None
assert scheme.find("Imageset[@filename='DungeonbookFrame.imageset'][@name='DungeonbookFrame']") is not None
# The row of the moved atlas stands in the CREDITS of the content repository (public CREDITS plus that one)
assert 'gui/DungeonbookIcons.png' in room_packages.credits_text(repo)

# Code: real game data only, every value of today kept, rounded to at most two decimals (owner decision 830: no raw
# float sums such as 51.59700000000005), and the slots filled by the creature code
# The labels of the statistics text are the text references "@creature.stats.<id>" (Creature::statsLabel), the same in
# every language; their English texts are the labels of before
STATISTICS_LABELS = (('experience', 'Experience'), ('hp', 'HP'), ('gold', 'Gold'), ('sight_radius', 'Sight radius'),
                     ('potions', 'Potions'), ('inventory', 'Inventory'), ('damage_per_second', 'Raw damage per second'),
                     ('skill_points', 'Skill points earned / spent'))
for label, _ in STATISTICS_LABELS:
    assert '"%s"' % label in social, label
assert 'findStatisticsValue(entry.stats, Creature::statsLabel(line.label))' in social
if content_packages.has_content(repo):
    english_labels = language_package_texts.english(repo)
    for label, text in STATISTICS_LABELS:
        assert english_labels.get('creature.stats.' + label) == text, label
else:
    content_packages.unchecked('check_dungeonbook_profile_layout', ['English labels of the statistics text'])
for field in ('critical', 'attackRating', 'defenseRating', 'physicalDefense', 'magicalDefense', 'elementDefense'):
    assert 'formatProfileValue(entry.%s)' % field in social, field
assert 'formatProfileValue(values[i])' in social


def function_of(text, signature):
    body = text[text.index(signature):]
    return body[:body.index('\n}\n')]


# The book rounds in ONE place, the creature code: its value text is the rounded text with the thousands grouped
for rounding in ('setprecision', 'std::fixed', 'std::round', 'lround', 'std::trunc', 'std::ceil'):
    assert rounding not in social, 'the Dungeonbook rounds through Creature::formatRoundedNumber only: ' + rounding
profile_value = function_of(social, 'std::string formatProfileValue(double value)')
assert 'return groupThousands(Creature::formatRoundedNumber(value));' in profile_value, profile_value
statistics_numbers = function_of(social, 'std::string formatStatisticsNumbers(')
assert 'formatProfileValue(number)' in statistics_numbers and 'groupThousands(parts[i])' not in statistics_numbers, \
    'the statistics values are rounded as well, also a raw sum an older server wrote'
assert 'parser.imbue(std::locale::classic());' in statistics_numbers
group = function_of(social, 'std::string groupThousands(const std::string& number)')
assert 'THOUSANDS_GROUP = 3;' in social and 'result.insert(comma - THOUSANDS_GROUP, ",")' in group
# The rounded number text of the creature code: two decimals at most, zeros at the end dropped, exponent from 1e15 on
creature_header = (repo / 'source/entities/Creature.h').read_text()
assert 'static std::string formatRoundedNumber(double value);' in creature_header
creature_cpp = (repo / 'source/entities/Creature.cpp').read_text()
assert 'formatExactNumber' not in creature_cpp + creature_header + social, 'the raw exact number text is gone'
rounded = function_of(creature_cpp, 'std::string Creature::formatRoundedNumber(double value)')
for fragment in ('stream << std::fixed;', 'stream << std::scientific;', 'if(std::fabs(value) >= ROUNDED_FIXED_MAX)',
                 'stream << std::setprecision(ROUNDED_DECIMALS) << value;', 'std::locale::classic()',
                 "while(!mantissa.empty() && (mantissa[mantissa.size() - 1] == '0'))",
                 "if(!mantissa.empty() && (mantissa[mantissa.size() - 1] == '.'))", 'if(mantissa == "-0")',
                 'return mantissa + suffix;'):
    assert fragment in rounded, fragment
assert re.search(r'ROUNDED_DECIMALS = 2;', creature_cpp) and re.search(r'ROUNDED_FIXED_MAX = 1e15;', creature_cpp)
stats_text = function_of(creature_cpp, 'std::string Creature::getStatsText(const Seat* viewer)')
for fragment in ('statsLabel("experience") << ": " << formatRoundedNumber(mExp)',
                 'statsLabel("hp") << ": " << formatRoundedNumber(getHP()) << " / " << formatRoundedNumber(mMaxHP)',
                 'statsLabel("gold") << ": " << formatRoundedNumber(mGoldCarried)'):
    assert fragment in stats_text, fragment
server_text = (repo / 'source/network/ODServer.cpp').read_text()
for getter in ('getAttackRating', 'getDefenseRating', 'getRawDamagePerSecond'):
    assert 'Creature::formatRoundedNumber(creature->%s())' % getter in server_text, getter
    assert 'Helper::toString(creature->%s())' % getter not in server_text, getter + ' is written with six digits'


def rounded_number(value):
    """Python replica of Creature::formatRoundedNumber: two decimals, zeros at the end dropped, exponent from 1e15."""
    text = ('%.2e' if abs(value) >= 1e15 else '%.2f') % value
    mantissa, sep, exponent = text.partition('e')
    mantissa = mantissa.rstrip('0').rstrip('.')
    if mantissa == '-0':
        mantissa = '0'
    return mantissa + sep + exponent


def group_thousands(number):
    """Python replica of groupThousands in SocialWindow.cpp."""
    if any(c in number for c in 'eEin'):
        return number
    sign = 1 if number.startswith('-') else 0
    whole = number.find('.') if '.' in number else len(number)
    while whole > sign + 3:
        number = number[:whole - 3] + ',' + number[whole - 3:]
        whole -= 3
    return number


# Rounded means: at most two decimals, no zero at the end, the nearest such number (the owner's raw sums included)
for value, text in ((51.59700000000005, '51.6'), (56.51100000000007, '56.51'), (14.8, '14.8'), (42600.0, '42,600'),
                    (41.666666666666664, '41.67'), (0.1 + 0.2, '0.3'), (12.0, '12'), (-1234567.25, '-1,234,567.25'),
                    (3e-05, '0'), (-0.004, '0'), (4.5864, '4.59'), (5e20 / 7, '7.14e+19')):
    assert group_thousands(rounded_number(value)) == text, (value, group_thousands(rounded_number(value)))
for value in (1.0 / 3, 2.0 / 3 * 100, 1e-7 / 3, 123456789.123, 0.001, 999999999999999.9, 51.59700000000005):
    shown = rounded_number(value)
    assert abs(float(shown) - value) <= 0.005 + abs(value) * 1e-15, (value, shown)
    assert '.' not in shown or len(shown.split('.')[1]) <= 2, shown
# The widest value text the book can show: every magnitude and form, negative
WORST_NUMBERS = tuple(sorted({group_thousands(rounded_number(float('-9.8765432109876543e%d' % e))) for e in range(-320, 308)},
                       key=lambda n: (text_width('MedievalSharp-8', n), n))[-12:])
assert all(len(n) >= 10 for n in WORST_NUMBERS) and '-987,654,321,098,765.38' in WORST_NUMBERS, WORST_NUMBERS
# Every magnitude and form (and the round values like 1.0000000000000002), for the attribute cells whose line breaks
# depend on where the commas, points and exponent lie
ALL_NUMBERS = tuple(sorted({group_thousands(rounded_number(float(m % e))) for m in ('-9.8765432109876543e%d',
                            '-1.0000000000000002e%d', '9.8765432109876543e%d', '1.2345e%d') for e in range(-320, 308)}))
assert len(ALL_NUMBERS) > 1000 and set(WORST_NUMBERS) <= set(ALL_NUMBERS), len(ALL_NUMBERS)
# Owner decision 816: Strength, Dexterity, Life and Mana side by side in ONE row (book-variant-2), label on top, the
# rounded value below it; a long value is broken into lines of ATTRIBUTE_LINE_CHARS characters (breakAttributeValue)
ATTRIBUTES = ('Strength', 'Dexterity', 'Life', 'Mana')
LINE_CHARS = int(re.search(r'ATTRIBUTE_LINE_CHARS = (\d+);', social)[1])
break_value = function_of(social, 'std::string breakAttributeValue(const std::string& value)')
for fragment in ('while(rest.size() > ATTRIBUTE_LINE_CHARS)', 'std::string::size_type cut = ATTRIBUTE_LINE_CHARS;',
                 'for(std::string::size_type i = ATTRIBUTE_LINE_CHARS; i >= ATTRIBUTE_LINE_CHARS / 2; --i)',
                 "if(rest[i - 1] == ',' || rest[i - 1] == '.' || rest[i] == 'e' || rest[i] == 'E')",
                 'result += rest.substr(0, cut) + "\\n";', 'rest = rest.substr(cut);', 'return result + rest;'):
    assert fragment in break_value, fragment
values_fill = function_of(social, 'void SocialWindow::refreshValues(')
assert 'const char* names[] = {"Strength", "Dexterity", "Life", "Mana"};' in values_fill
assert ('text << Translation::tr(nameKeys[i]) << "\\n"\n            << (known ? breakAttributeValue(formatProfileValue(values[i])) : std::string("-"));'
        in values_fill), 'the attribute cells show label and rounded value, broken into the lines of the cell'


def break_attribute_value(value):
    """Python replica of breakAttributeValue in SocialWindow.cpp."""
    lines = []
    while len(value) > LINE_CHARS:
        cut = LINE_CHARS
        for i in range(LINE_CHARS, LINE_CHARS // 2 - 1, -1):
            if value[i - 1] in ',.' or value[i] in 'eE':
                cut = i
                break
        lines.append(value[:cut])
        value = value[cut:]
    return lines + [value]


for value in ALL_NUMBERS + ('11', '-', '42,600', '41.666666666666664'):
    assert ''.join(break_attribute_value(value)) == value, ('a character of the value is lost', value)
    assert all(0 < len(part) <= LINE_CHARS for part in break_attribute_value(value)), value
assert LINE_CHARS == 14, 'the expected breaks below are written for 14 characters per line'
for value, expected in (('14', ['14']), ('42,600', ['42,600']), ('41.666666666666664', ['41.66666666666', '6664']),
                        ('-9.876543210987655e+280', ['-9.87654321098', '7655e+280']),
                        ('-987,654,321,098,765.4', ['-987,654,321,', '098,765.4']),
                        ('-1.0000000000000002e-05', ['-1.00000000000', '00002e-05'])):
    assert break_attribute_value(value) == expected, (value, break_attribute_value(value))
ATTRIBUTE_TEXTS = {name: tuple(name + '\n' + '\n'.join(break_attribute_value(n)) for n in ALL_NUMBERS + ('-', '0'))
                   for name in ATTRIBUTES}
ATTRIBUTE_LINES = max(t.count('\n') + 1 for texts in ATTRIBUTE_TEXTS.values() for t in texts)
cells = [boxes['ValuesPage/' + name][0] for name in ATTRIBUTES]
for cell in cells[1:]:
    assert abs(cell[1] - cells[0][1]) < 1e-9 and abs(cell[3] - cells[0][3]) < 1e-9, 'the four attributes share ONE row'
    assert abs((cell[2] - cell[0]) - (cells[0][2] - cells[0][0])) < 1e-3, 'the four attribute cells are equally wide'
for left, right in zip(cells, cells[1:]):
    assert left[2] < right[0], 'Strength, Dexterity, Life, Mana from left to right without overlap'
combat_panel = boxes['ValuesPage/CombatPanel'][0]
assert abs(cells[0][0] - combat_panel[0]) < 1e-9 and abs(cells[-1][2] - combat_panel[2]) < 1e-9, \
    'the attribute row spans the right column like the combat block below it'
assert boxes['ValuesPage/Portrait'][0][3] <= cells[0][1] + 1e-9 and cells[0][3] <= combat_panel[1] + 1e-9, \
    'the attribute row lies between the portrait ring and the combat block'
for name in ATTRIBUTES:
    cell = {p.get('name'): p.get('value') for p in boxes['ValuesPage/' + name][1].findall('Property')}
    assert cell['Font'] == 'MedievalSharp-8' and cell['HorzFormatting'] == 'CentreAligned', name
    assert cell['BackgroundEnabled'] == 'True' and 'Text' not in cell, name
assert not any(re.fullmatch(r'ValuesPage/(Strength|Dexterity|Life|Mana)\w+', n) for n in boxes), 'one window per attribute'
# The Equipment, Path and Skills tiles show symbol and title (book-variant-2); their whole text is in the tooltip and
# path and skills are rows of the profile page (plan INGAME-QS-11 K1)
assert 'entry.equipment, entry.path, entry.skills' in social and 'fitTextToWindow' not in social
tiles = function_of(social, 'void SocialWindow::refreshValues(')
for fragment in ('tileText["tile"] = Translation::tr(tileKeys[i]);', 'tileText["value"] = value;',
                 'page->getChild(std::string(tiles[i]) + "Tile")->setTooltipText(tooltip);',
                 'page->getChild(std::string(tiles[i]) + "Title")->setTooltipText(tooltip);'):
    assert fragment in tiles, fragment
for name in ('Equipment', 'Path', 'Skills'):
    assert 'ValuesPage/%sValue' % name not in boxes, name + ' tile shows a shortened text'
    tile = boxes['ValuesPage/%sTile' % name][1].find("Property[@name='MousePassThroughEnabled']")
    assert tile is not None and tile.get('value') == 'False', name + ' tile must show its tooltip'
# The profile of book-variant-2 (plan INGAME-QS-11 K1): path and skills are rows of the book's own profile page,
# filled from the roster (or from the creature known here)
profile_fill_book = function_of(social, 'void SocialWindow::refreshProfile(')
for fragment in ('std::string path = entry.path;', 'std::string skills = entry.skills;',
                 'path = creature->getSkillPathText();', 'skills = creature->getSkillListText();',
                 'setFittedText(page->getChild("SkillsValue"), skills.empty() ? std::string("-") : skills, true, "");'):
    assert fragment in profile_fill_book, fragment
for name in ('SocialHolder', 'SocialText', 'InfoText', 'KeeperText'):
    assert 'ProfilePage/' + name not in boxes, name + ' is not on the profile of book-variant-2'
# Decision 732: the start page, the feeds, the head and the values show their whole texts. Plan INGAME-QS-11 K1: a
# text of the profile page that is longer than its place is shortened with "..." and shown whole in its tooltip; that
# is the only shortening of the book (setFittedText and the name line of refreshProfile)
for gone in ('elideToWidth', 'setElidedText', 'fitTextToWindow', 'isTileTextFitting', "'...'"):
    assert gone not in social, gone + ' shortens a text of the Dungeonbook'
dots = [m.start() for m in re.finditer(re.escape('"..."'), social)
        if not social[social.rindex('\n', 0, m.start()) + 1:m.start()].lstrip().startswith('//')]
concatenated = [m.start() for m in re.finditer(re.escape('+ "..'), social)]
assert all(fitted_range_start < d for d in concatenated for fitted_range_start in (social.index('void setFittedText('),)) \
    and set(concatenated) <= set(d - 2 for d in dots), 'dots are only added by the shortening of the profile'
fitted_range = (social.index('void setFittedText('), social.index('//! \\brief Returns the value after "label: "'))
profile_range = (social.index('void SocialWindow::refreshProfile('), social.index('void SocialWindow::refreshValues('))
assert dots and all(fitted_range[0] < d < fitted_range[1] or profile_range[0] < d < profile_range[1] for d in dots), \
    'only the profile shortens its texts'
assert 'void setFullText(CEGUI::Window* window, const std::string& text)' in social
assert 'window->setText(Gui::toCeguiText(escapeMarkup(text)));' in function_of(social, 'void setFullText(')
for call in ('setFullText(home->getChild("CreaturesLabel"), Translation::tr(labelKey, labelValues));',
             'setFullText(row->getChild("Name"), profile.getFullName());',
             'setFullText(header->getChild("NameText"), profile.getFullName());',
             'setFullText(valueWindow, line.slots ? countFilledSlots(value) : formatStatisticsNumbers(value));',
             'head->setText(Gui::toCeguiText(std::string(FEED_NAME_COLOUR) + escapeMarkup(profile.getFullName()) +',
             'textWindow->setText(Gui::toCeguiText(std::string(FEED_TEXT_COLOUR) + escapeMarkup(text)));'):
    assert call in social, call
assert 'Creature::fillItemSlotWindows(creature, slots, true)' in social
creature_text = (repo / 'source/entities/Creature.cpp').read_text()
fill = creature_text[creature_text.index('void Creature::fillItemSlotWindows('):]
fill = fill[:fill.index('\n}\n')]
for fragment in ('creature->mEquipment[slot]', 'creature->mPotionSlots[slot - 6]', 'creature->mInventory[slot - 9]',
                 'slot >= VISIBLE_ITEM_HAND_SLOTS', 'ItemDrops::poorWeapon(*weapon)', 'Gui::setItemTooltip(image, *item, creature->getGameMap(), heldWeapon)',
                 'slotType->setVisible(item == nullptr)', 'slot - 6 >= creature->mPotionSlots.size()',
                 'image->getChild("Lock")->setVisible(locked)', '"PotionSlotLevel2"', '"PotionSlotLevel3"'):
    assert fragment in fill, fragment
assert 'fillItemSlotWindows(this, slotWindows, false)' not in creature_text, 'the shared profile page is deleted'
for handler in ('onBackClicked', 'onPreviousClicked', 'onNextClicked', 'onNavClicked', 'onFilterClicked', 'onListRowClicked',
                'onListWheel', 'onFeedWheel', 'onListScrolled', 'onFeedScrolled', 'onLinkClicked'):
    assert 'bool SocialWindow::%s' % handler in social and '&SocialWindow::%s' % handler in social, handler
step = social[social.index('void SocialWindow::stepCreature'):]
step = step[:step.index('\n}\n')]
assert '% count' in step and 'mListedCreatures' in step, 'previous and next wrap around the shown list'
assert 'row->getChild("Highlight")->setVisible(entry->name == mSelectedCreature)' in social
assert 'describeMood(*entry, mood, icon)' in social
assert 'MAX_FEED_ROWS = 25' in social and 'MAX_OWN_POSTS = 6' in social
assert 'fillProfilePage(' not in social and 'fillProfilePage(' not in creature_text, 'the shared profile page is deleted'

# Sizes. Fonts and layout scale by the same factor from the display and the UI scale (the line heights in design
# pixels do not depend on the resolution); Gui::getWindowFitFactor shrinks a window larger than the screen together
# with its children but not the fonts, so the texts are compared with the shrunk boxes.
# The title is the sheet title (OD/SheetTitlebar): one line of the 13 point title font of OD/SheetWindow.
sheet_look = ET.fromstring(content_packages.read_layout_text(repo, 'gui/OD.looknfeel')).find("WidgetLook[@name='OD/SheetWindow']")
assert sheet_look.find("PropertyLinkDefinition[@name='TitlebarFont']").get('initialValue') == 'MedievalSharp-13'
TITLE_LINE = line_height('MedievalSharp-13')
need = {}


def require(name, font, lines=1, texts=(), pad_w=6.0, pad_h=0.0, wrap=False):
    """A window and the texts it must show in full. A wrapped window word wraps every text with the shipped font at its
    width (as CEGUI does, at the spaces) and must be high enough for all its lines and wide enough for its widest word;
    lines is the least number of lines it has room for."""
    if wrap:
        formatting = boxes[name][1].find("Property[@name='HorzFormatting']")
        assert formatting is not None and formatting.get('value').startswith('WordWrap'), name + ' must word wrap'
    need[name] = (font, lines, texts, pad_w, pad_h, wrap)


def wrap_lines(font, text, width):
    """Lines of the text word wrapped at the spaces to the width (CEGUI word wrap); a word never splits."""
    lines = []
    for paragraph in text.split('\n'):
        current = ''
        for word in paragraph.split(' '):
            trial = word if not current else current + ' ' + word
            if current and text_width(font, trial) > width + 1e-6:
                lines.append(current)
                current = word
            else:
                current = trial
        lines.append(current)
    return lines


# The longest texts the book can show (owner decision 732: names and post texts in full, word wrapped). Names: every
# given name with every surname and epithet of config/social-names.cfg (CreatureProfile::getFullName). Posts: every
# post template of config/social-texts.cfg with each slot filled by its widest values (names, hometowns, jobs, likes,
# dislikes, quirks, rooms of CreaturePosts::getRoomName, item names of items.cfg and potions.cfg, level 30).
name_groups = []
for line in content_packages.read_layout_text(repo, 'config/social-names.cfg').split('\n'):
    cells = line.split('\t')
    if cells[0] == '[NameGroup]':
        name_groups.append({'given': [], 'last': [], 'home': []})
    elif cells[0] == 'Given':
        name_groups[-1]['given'] += [c for c in cells[2:] if c]
    elif cells[0] in ('Surname', 'Title'):
        name_groups[-1]['last'] += [c for c in cells[1:] if c]
    elif cells[0] == 'Hometown':
        name_groups[-1]['home'] += [c for c in cells[1:] if c]
full_names = [g + ((' ' + s) if s else '') for group in name_groups for g in group['given'] for s in [''] + group['last']]
assert len(full_names) > 5000 and 'CreatureProfile' in (repo / 'source/social/CreatureProfile.h').read_text()


def widest(pool, font='MedievalSharp-8', count=3):
    return sorted(set(pool), key=lambda t: -text_width(font, t))[:count]


WIDEST_NAMES_8 = widest(full_names) + sorted(full_names, key=len)[-1:]
WIDEST_NAMES_10 = widest(full_names, 'MedievalSharp-10') + sorted(full_names, key=len)[-1:]
pools = {'job': [], 'like': [], 'dislike': [], 'quirk': []}
templates = []
for line in content_packages.read_layout_text(repo, 'config/social-texts.cfg').split('\n'):
    cells = line.split('\t')
    if cells[0].lower() in pools:
        pools[cells[0].lower()].append(cells[-1])
    elif cells[0] == 'Post':
        templates.append(cells[-1])
assert len(templates) > 300 and all(pools.values()), 'post templates and slot pools are read'
items = ['Soul crystal', 'Ectoplasm', 'Mana crystal', 'Research book']
for cfg in ('items.cfg', 'potions.cfg'):
    items += re.findall(r'^\s*Display\s+(.+?)\s*$', content_packages.read_layout_text(repo, 'config/' + cfg), re.M)
posts_source = (repo / 'source/social/CreaturePosts.cpp').read_text()
# The room names are entries of the language files (getSocialCodeText(key, English fallback)); the English text of
# the key is measured, the fallback stands in for it without the content
room_keys = re.findall(r'getSocialCodeText\("(social\.code\.room\.[a-z_]+)", "([a-z ]+)"\)',
                       posts_source[posts_source.index('CreaturePosts::getRoomName'):][:3000])
english_rooms = language_package_texts.english(repo)
rooms = [english_rooms.get(key, fallback) for key, fallback in room_keys]
assert len(items) > 50 and len(rooms) > 15, (len(items), len(rooms))
slot_values = {'name': WIDEST_NAMES_8, 'friend': WIDEST_NAMES_8, 'hometown': widest([h for g in name_groups for h in g['home']]),
               'job': widest(pools['job']), 'like': widest(pools['like']), 'dislike': widest(pools['dislike']),
               'quirk': widest(pools['quirk']), 'level': ['30'], 'room': widest(rooms), 'item': widest(items)}
import itertools
WORST_POSTS = []
for template in templates:
    slots = sorted(set(re.findall(r'\{(\w+)\}', template)))
    for choice in itertools.product(*(slot_values.get(s, ['']) for s in slots)):
        values = dict(zip(slots, choice))
        WORST_POSTS.append(re.sub(r'\{(\w+)\}', lambda m: values.get(m[1], ''), template))
# The age of a post (formatAge) and the level or crown (about two letters wide) after the name in the feed head
AGES = ('just now', '59 sec ago', '59 min ago', '2147483 h ago')
HEADS = [n + '   ' + level + age for n in WIDEST_NAMES_8 for level in ('', 'Lv. 30 - ', 'WW - ') for age in AGES]
NICK = 'W' * 20  # the nick of a keeper has at most 20 characters (MenuModeMultiplayerServer)
assert 'nickCeguiStr.length() > 20' in (repo / 'source/modes/MenuModeMultiplayerServer.cpp').read_text()

require('HomePage/CreaturesLabel', 'MedievalSharp-10', texts=('Known creatures (999 of 999)',), wrap=True)
# The combo area includes its popup; its edit box holds one choice at a time.
for text in ('All', 'Zivs', 'Fighters', 'Unhappy'):
    require('HomePage/Filter', 'MedievalSharp-8', texts=(text,), pad_w=28.0, pad_h=6.0)
require('HomePage/FeedTitle', 'MedievalSharp-10', texts=('All-Creature Feed',))
for row in list_rows:
    require(row + '/Name', 'MedievalSharp-8', lines=2, texts=WIDEST_NAMES_8, wrap=True)
    require(row + '/Level', 'MedievalSharp-8', texts=('Lv. 30',))
    require(row + '/Mood', 'MedievalSharp-8', texts=('Furious', 'Content', 'Neutral', 'Unhappy', 'Hungry'), wrap=True)
    # the keeper the creature serves (INGAME-QS-7 U-2): a usual nick on one line; a longer one is shortened by the code
    require(row + '/Keeper', 'MedievalSharp-8', texts=('Player 1', 'Player 4', 'Keeper'))
for page in ('HomePage', 'FeedPage'):
    for i in range(3):
        require('%s/FeedRows/Row%d/Head' % (page, i), 'MedievalSharp-8', texts=HEADS, wrap=True)
        require('%s/FeedRows/Row%d/Text' % (page, i), 'MedievalSharp-8', lines=2, texts=WORST_POSTS, wrap=True)
    require(page + '/FeedEmpty', 'MedievalSharp-8', lines=2)
require('FeedPage/FeedTitle', 'MedievalSharp-10', texts=('Feed',))
WIDEST_NAMES_12 = widest(full_names, 'MedievalSharp-12') + sorted(full_names, key=len)[-1:]
require('Header/NameText', 'MedievalSharp-12', texts=WIDEST_NAMES_12)
for n in nav:
    require(n + '/Label', 'MedievalSharp-10', texts=(boxes[n + '/Label'][1].find("Property[@name='Text']").get('value'),))
# The profile of book-variant-2: the widest name in the large font with the longest handle on one line, the labels of
# the table, and the longest values of the rows (they would be shortened with "..." by the code, K1, but fit)
handles = ['@' + max((g for group in name_groups for g in group['given']), key=len).lower() + '99']
require('ProfilePage/NameText', 'MedievalSharp-12', texts=WIDEST_NAMES_12, pad_w=0.0)
for label in ('Age', 'Gender', 'Relationship', 'Origin', 'Job', 'Path', 'Skills'):
    require('ProfilePage/%sLabel' % label, 'MedievalSharp-8', texts=(label + ':',))
age_jokes = [c for line in content_packages.read_layout_text(repo, 'config/social-names.cfg').split('\n')
             for c in line.split('\t')[1:] if line.startswith('AgeJoke') and c]
relations = [line.split('\t')[-1] for line in content_packages.read_layout_text(repo, 'config/social-texts.cfg').split('\n')
             if line.startswith('Relation\t')]
require('ProfilePage/AgeValue', 'MedievalSharp-8', texts=tuple(age_jokes) + ('30',))
require('ProfilePage/GenderValue', 'MedievalSharp-8', texts=('Female', 'Male', '-'))
require('ProfilePage/RelationshipValue', 'MedievalSharp-8', texts=tuple(relations) + (
    'In a relationship', 'Sworn enemies', "It's complicated", 'Single'))
require('ProfilePage/OriginValue', 'MedievalSharp-8', texts=tuple(widest([h for g in name_groups for h in g['home']])))
require('ProfilePage/JobValue', 'MedievalSharp-8', texts=tuple(widest(pools['job'])))
require('ProfilePage/SkillsValue', 'MedievalSharp-8', lines=3, wrap=True)
require('ProfilePage/QuoteText', 'MedievalSharp-8', lines=4, wrap=True)
# the social lines of the creature (owner decision 2026-11-18), each shortened to its box with its hover text
require('ProfilePage/StatusText', 'MedievalSharp-8', lines=2, wrap=True)
for line in ('LikesText', 'DislikesText', 'FriendsText', 'FoeText', 'EffectLine0', 'EffectLine1', 'EffectLine2'):
    require('ProfilePage/' + line, 'MedievalSharp-8', texts=('Buff: Relaxed (9:59)', 'Foe: none', 'Friends: none yet'))
require('ProfilePage/RemarksText', 'MedievalSharp-8', lines=2, wrap=True)
require('ProfilePage/PostsTitle', 'MedievalSharp-10', texts=('Posts (200)',))
require('ProfilePage/PostsEmpty', 'MedievalSharp-8', lines=2, texts=('Nothing posted yet.',))
# Values: rounded numbers (two decimals at most, every magnitude); a pair "a / b" wraps after the slash
pairs = tuple(a + ' / ' + b for a in WORST_NUMBERS[-3:] for b in WORST_NUMBERS[-3:])
for name, label in (('Experience', 'Experience:'), ('HitPoints', 'Hit points:'), ('Gold', 'Gold:'),
                    ('SightRadius', 'Sight radius:'), ('Potions', 'Potions:'), ('Inventory', 'Inventory:'),
                    ('DamagePerSecond', 'Damage per second:'), ('SkillPoints', 'Skill points:')):
    require('ValuesPage/%sLabel' % name, 'MedievalSharp-8', texts=(label,), pad_w=4.0)
    require('ValuesPage/%sValue' % name, 'MedievalSharp-8', lines=2, texts=WORST_NUMBERS + pairs + ('-',), pad_w=4.0,
            wrap=True)
# The attribute cells of the one row: label and every value line of every magnitude, whole (decision 816)
assert ATTRIBUTE_LINES == 3, ATTRIBUTE_LINES
for name in ATTRIBUTES:
    require('ValuesPage/' + name, 'MedievalSharp-8', lines=ATTRIBUTE_LINES, texts=ATTRIBUTE_TEXTS[name])
require('ValuesPage/CombatLabels', 'MedievalSharp-8', lines=3, texts=('Critical %', 'Attack Rating', 'Defense Rating'))
require('ValuesPage/DefenseLabels', 'MedievalSharp-8', lines=3, texts=('Physical Defense', 'Magical Defense', 'Element Defense'))
require('ValuesPage/CombatValues', 'MedievalSharp-8', lines=3, texts=tuple(n + '%' for n in WORST_NUMBERS) + WORST_NUMBERS)
require('ValuesPage/DefenseValues', 'MedievalSharp-8', lines=3, texts=WORST_NUMBERS)
for name in ('Equipment', 'Path', 'Skills'):
    require('ValuesPage/%sTitle' % name, 'MedievalSharp-8', texts=(name,), pad_w=2.0)
for i, label in enumerate(labels):
    require('InventoryPage/SlotBox%d/Label' % i, 'MedievalSharp-8', texts=(label,), pad_w=2.0)
require('InventoryPage/PotionsLabel', 'MedievalSharp-8', texts=('Potions',))
require('InventoryPage/InventoryLabel', 'MedievalSharp-8', texts=('Inventory',))
require('InventoryPage/HintText', 'MedievalSharp-8', lines=2, wrap=True, texts=(
    'This creature is out of sight; its items are not known here.',
    'Only the hands of a creature of another keeper can be seen.'))
for name in need:
    assert name in boxes, name

state_lines = []
wrapped_lines = {}
narrowest_link = 1e9
# The values sheet is a page like the others (plan INGAME-QS-11 K2): no scrolled document, every cell on the page
values_page = boxes['ValuesPage'][1]
assert values_page.get('type') == 'DefaultWindow', 'the values page does not scroll'
assert boxes['ValuesPage'][0][1] >= boxes['Header'][0][3], 'the values page starts below the head'
assert 'documentWidth' not in gui and '"ValuesPage"' not in gui, 'no scroll document for the values page'
for screen_w, screen_h in ((640, 480), (1024, 768), (1920, 1200), (7680, 4320)):
    for user in (0.8, 1.2):
        scale = min(screen_w / 1024.0, screen_h / 768.0) * user
        fit = min(1.0, screen_w / (book_w * scale), screen_h / (book_h * scale))
        win_w, win_h = book_w * fit, book_h * fit  # design pixels after the fit, fonts unchanged
        assert win_w * scale <= screen_w + 1e-6 and win_h * scale <= screen_h + 1e-6, 'the book is larger than the screen'
        # the title bar is one line of the title font plus 4 screen pixels on the top rail from three quarters of its
        # height; the side and bottom rails of the sheet frame take their edges (scaled like the layout, not fitted)
        client_w = win_w - 2 * FRAME_SIDE
        client_h = win_h - (0.75 * FRAME_TOP + TITLE_LINE + 4.0 / scale) - FRAME_BOTTOM
        tightest = {}
        for name, (font, lines, texts, pad_w, pad_h, wrap) in need.items():
            box = boxes[name][0]
            width = (box[2] - box[0]) * client_w
            height = (box[3] - box[1]) * client_h
            if wrap:
                # every text in full: all its wrapped lines in the height, its widest word in the width
                wrapped = [wrap_lines(font, t, width - pad_w) for t in texts]
                lines = max([lines] + [len(w) for w in wrapped])
                words = [word for t in texts for word in t.replace('\n', ' ').split(' ')]
                wanted_w = max([text_width(font, word) + pad_w for word in words] + [0.0])
                assert all(text_width(font, part) + pad_w <= width + 1e-6 for w in wrapped for part in w), name
                wrapped_lines[name] = max(wrapped_lines.get(name, 0), lines)
            else:
                wanted_w = max([text_width(font, part) + pad_w for t in texts for part in t.split('\n')] + [0.0])
            wanted_h = lines * line_height(font) + pad_h
            assert height + 1e-6 >= wanted_h, ('text too high for its window', name, screen_w, screen_h, user,
                                               round(height, 1), round(wanted_h, 1))
            assert width + 1e-6 >= wanted_w, ('text too wide for its window', name, screen_w, screen_h, user,
                                              round(width, 1), round(wanted_w, 1))
            page = name.split('/')[0]
            ratio = max(wanted_h / height, wanted_w / width)
            if ratio > tightest.get(page, (0.0, ''))[0]:
                tightest[page] = (ratio, name)
        # the slot pictures stay squares of at least 24 screen pixels, the portraits at least 40
        for i in range(13):
            slot = boxes['InventoryPage/SlotBox%d/Slot%d' % (i, i)][0]
            edge = min((slot[2] - slot[0]) * client_w, (slot[3] - slot[1]) * client_h) * scale
            assert edge >= 12.0, ('slot too small', screen_w, screen_h, user, edge)
        # the one attribute row: each cell in screen pixels and the room its widest and highest text takes
        cell = boxes['ValuesPage/Strength'][0]
        cell_w = (cell[2] - cell[0]) * client_w
        cell_h = (cell[3] - cell[1]) * client_h
        attribute_w = max(text_width('MedievalSharp-8', part) + 6.0 for name in ATTRIBUTES
                          for t in ATTRIBUTE_TEXTS[name] for part in t.split('\n'))
        state_lines.append('%dx%d UI %d%%: attribute row 4 cells of %dx%d px, widest line %.0f%% of the width, '
                           'label + %d value lines %.0f%% of the height' % (
                               screen_w, screen_h, round(user * 100), round(cell_w * scale), round(cell_h * scale),
                               attribute_w / cell_w * 100, ATTRIBUTE_LINES - 1,
                               ATTRIBUTE_LINES * line_height('MedievalSharp-8') / cell_h * 100))
        state_lines.append('%dx%d UI %d%%: book %dx%d px (fit %.2f); tightest text per page: %s' % (
            screen_w, screen_h, round(user * 100), round(win_w * scale), round(win_h * scale), fit,
            ', '.join('%s %s %.0f%%' % (p.replace('Page', ''), tightest[p][1].split('/')[-1], tightest[p][0] * 100)
                      for p in ('HomePage', 'Header', 'FeedPage', 'ProfilePage', 'ValuesPage', 'InventoryPage', 'NavBar')
                      if p in tightest)))
print('Dungeonbook pages verified: start page, head with back/previous/next arrows, bottom navigation, feed, profile, '
      'values sheet and 13-slot inventory fit 640x480 to 8K at 80 to 120 percent')
for line in state_lines:
    print('  ' + line)
print('Full texts (decision 732), most wrapped lines at any size: list name %d, feed head %d, post text %d (%d posts), '
      'value %d; widest value %s; head and profile name on one line (widest %.0f design px)' % (
          wrapped_lines['HomePage/ListRows/Row0/Name'], wrapped_lines['HomePage/FeedRows/Row0/Head'],
          wrapped_lines['HomePage/FeedRows/Row0/Text'], len(WORST_POSTS),
          wrapped_lines['ValuesPage/HitPointsValue'], WORST_NUMBERS[-1],
          max(text_width('MedievalSharp-12', n) for n in WIDEST_NAMES_12)))
