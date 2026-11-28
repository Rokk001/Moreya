"""Check the pages of one creature of the Dungeonbook and the item tooltip (plan INGAME-QS-11 package B1, test T-B1).

Static check, no game and no compiler needed. It computes, with the formulas of Gui.cpp (layout scale, window fit factor,
fonts scaled from 800x600, images of the scaled families) and the window frame of OD/SheetWindow, the on-screen box of
every element of the profile, values and inventory pages, of the head "< Name >", of the navigation bar and of the back
arrow in the title bar, at 640x480, 1920x1200 and 7680x4320 (and 1024x768) with the UI scale 80 % and 120 %, and checks:

1. Every element lies inside the visible area of its page (the page box inside the client of the book) and inside its
   parent; no page has a scrollbar or a scrolled pane; no page holds a button (only the head, the navigation bar and the
   title bar have buttons).
2. No text is cut: every fixed caption fits its box with the shipped font; the texts the code fills in fit with their
   longest values (names, handles, ages, relationships, hometowns, jobs, paths, every rounded value of every magnitude),
   and a window whose text the code shortens to its box (SocialWindow setFittedText, K1) is at least one line high.
3. The profile has the portrait, the name and handle line, the rows Age, Gender, Relationship, Origin, Job and Path in
   this order, Skills, the quote, "Posts" and the six newest post pictures as a grid of 2 columns x 3 rows (K1).
4. The bottom bar has five buttons with icon and label, Skills last (K4); the code disables Skills without a skill tree
   and shows the skill tree with it as the Skills page of the book (INGAME-QS-12 K7: tier 4 skill, four path titles
   and three tiers per path, each skill with its rank inside the page and its rank text and every path name uncut at
   every screen and UI scale above); the profile layout holds no skill tree button.
5. The single-creature view hides the creature list (showPage) and shows the back arrow inside the title bar, left of
   the title and clear of the close button, and the head "< Name >" below the title (K3).
6. The item tooltip (K6): the held KoboldPick shows its display name and no value line, every value line of every
   equipment names its value and none is 0; a Poor, Common, Rare and Epic item get a frame in their quality colour that
   is at least as thick as the inner border of the window frame (ODMenuTemplate/FrameLeft) at every screen.
7. The tooltip position (K11): for cursor positions in the four quadrants of 640x480 and 1920x1200 and on every slot
   of the inventory page the tooltip lies right of and below the cursor where it fits, otherwise moved up or left only as
   far as needed; it is always on the screen and never overlaps the item.

The layout, fonts, imagesets and social tables are content (core-gui and core-config packages, found through
scripts/content_packages.py); without the content every measurement depends on them, so the check names the missing
files as not checked and passes.

Run with --table to print the per-element boxes (fractions of the page and pixels) used in the state file.
"""
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

from PIL import Image, ImageFont

repo = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo / 'scripts'))
import content_packages  # noqa: E402
from lang_texts import english_texts  # noqa: E402

#: The content files the whole check computes on (core-gui and core-config packages): without them nothing of the
#: pages can be measured, so the check names them as not checked and passes
CONTENT_FILES = ('gui/WindowSocial.layout', 'gui/ODMenuTemplate.imageset', 'gui/fonts/MedievalSharp-8.font',
                 'config/social-names.cfg', 'config/social-texts.cfg', 'config/creatureSkills.cfg')
missing_content = [name for name in CONTENT_FILES if content_packages.data_file(repo, name) is None]
if missing_content:
    content_packages.unchecked('check_dungeonbook_pages_b1', missing_content)
    sys.exit(0)
gui_dir = repo / 'gui'
gui_cpp = (repo / 'source/render/Gui.cpp').read_text(encoding='utf-8')
social_cpp = (repo / 'source/render/SocialWindow.cpp').read_text(encoding='utf-8')
item_cpp = (repo / 'source/entities/ItemInstance.cpp').read_text(encoding='utf-8')
weapon_cpp = (repo / 'source/entities/Weapon.cpp').read_text(encoding='utf-8')
lines_h = (repo / 'source/entities/ItemValueLines.h').read_text(encoding='utf-8')
placement_h = (repo / 'source/render/ItemTooltipPlacement.h').read_text(encoding='utf-8')
layout_text = content_packages.read_layout_text(repo, 'gui/WindowSocial.layout')
# The mixed interface files and data tables are read as the game reads them, with their own rows from the content
look_text = content_packages.read_layout_text(repo, 'gui/OD.looknfeel')

DESIGN_W, DESIGN_H = 1024.0, 768.0
FONT_W, FONT_H = 800.0, 600.0
SCREENS = [(640, 480), (1024, 768), (1920, 1200), (7680, 4320)]
USER_SCALES = [0.8, 1.2]
TOLERANCE = 0.75
NUMBER = r'(-?\d+(?:\.\d+)?)'
UDIM = r'\{' + NUMBER + ',' + NUMBER + r'\}'
failures = []


def check(condition, message):
    if not condition:
        failures.append(message)


def udims(value):
    return [(float(a), float(b)) for a, b in re.findall(UDIM, value)]


# ------------------------------------------------------------------------------------------------ fonts and images
# Parses an interface file of the public tree or a package as the game reads it (a mixed file joined with its own
# rows); None for the own rows file of a mixed file, which is no interface file of its own.
def parse_interface_file(path):
    if '.own.' in path.name:
        return None
    return ET.fromstring(content_packages.read_layout_text(repo, content_packages.relative_path(repo, path)))


fonts = {}
for font_file in content_packages.data_glob(repo, 'gui/fonts', '*.font'):
    spec = parse_interface_file(font_file)
    if spec is None:
        continue
    face = ImageFont.truetype(str(content_packages.resolve(repo, 'gui/fonts/' + spec.get('filename'))), 1024)
    fonts[spec.get('name')] = (face, float(spec.get('size')) * (96.0 / 72.0) / 1024.0)
DENSITY = {'OpenDungeonsSkin/': float(re.search(r'SKIN_IMAGE_PIXEL_DENSITY = ([0-9.]+)f', gui_cpp)[1]),
           'OpenDungeonsIcons/': float(re.search(r'ICON_IMAGE_PIXEL_DENSITY = ([0-9.]+)f', gui_cpp)[1]),
           'ODMenuTemplate/': float(re.search(r'MENU_SHEET_IMAGE_PIXEL_DENSITY = ([0-9.]+)f', gui_cpp)[1])}
imagesets = {}
for imageset_file in content_packages.data_glob(repo, 'gui', '*.imageset'):
    root = parse_interface_file(imageset_file)
    if root is None:
        continue
    imagesets[root.get('name')] = {i.get('name'): (float(i.get('width')), float(i.get('height')), float(i.get('xPos')),
                                                   float(i.get('yPos'))) for i in root.findall('Image')}
    imagesets[root.get('name')]['__file__'] = root.get('imagefile')


def layout_scale(screen, user):
    return min(screen[0] / DESIGN_W, screen[1] / DESIGN_H) * user


def font_scale(screen, user):
    return min(screen[0] / (FONT_W / user), screen[1] / (FONT_H / user))


def text_width(font, text, screen, user):
    face, factor = fonts[font]
    return face.getlength(text) * factor * font_scale(screen, user)


def line_height(font, screen, user):
    face, factor = fonts[font]
    return sum(face.getmetrics()) * factor * font_scale(screen, user)


def menu_image(name, screen, user):
    """Pixel size of an ODMenuTemplate image (scaled with the layout scale at its pixel density)."""
    width, height = imagesets['ODMenuTemplate'][name][:2]
    s = layout_scale(screen, user) / DENSITY['ODMenuTemplate/']
    return width * s, height * s


# ------------------------------------------------------------------------------------------------ layout tree
class Node:
    def __init__(self, element, parent):
        self.parent = parent
        self.type = element.get('type')
        self.name = element.get('name')
        self.props = {p.get('name'): p.get('value') for p in element.findall('Property')}
        # paths below the book: "ProfilePage/AgeValue"
        if parent is None or parent.parent is None:
            self.path = self.name
        else:
            self.path = parent.path + '/' + self.name
        self.children = [Node(c, self) for c in element.findall('Window')]

    def child(self, name):
        found = [c for c in self.children if c.name == name]
        check(len(found) == 1, 'window %s/%s missing' % (self.path, name))
        return found[0] if found else None

    def walk(self):
        yield self
        for c in self.children:
            yield from c.walk()


book = Node(ET.fromstring(layout_text).find('Window'), None)
check(book.type == 'OD/SheetWindow', 'the book uses the window frame of the menu sheet')


def child_rect(node, parent_rect, s):
    value = udims(node.props['Area'])
    px0, py0, px1, py1 = parent_rect
    pw, ph = px1 - px0, py1 - py0
    return (px0 + value[0][0] * pw + value[0][1] * s, py0 + value[1][0] * ph + value[1][1] * s,
            px0 + value[2][0] * pw + value[2][1] * s, py0 + value[3][0] * ph + value[3][1] * s)


def geometry(screen, user):
    """Pixel boxes of every window of the book, its client and its title bar, as Gui.cpp and OD.looknfeel place them."""
    s0 = layout_scale(screen, user)
    area = udims(book.props['Area'])
    off_w, off_h = (area[2][1] - area[0][1]) * s0, (area[3][1] - area[1][1]) * s0
    fit = min(1.0, screen[0] / off_w, screen[1] / off_h)  # Gui::getWindowFitFactor of a centred fixed window
    s = s0 * fit
    outer = child_rect(book, (0.0, 0.0, float(screen[0]), float(screen[1])), s)
    # OD/SheetWindow: frame edges and the title bar (one MedievalSharp-13 line plus 4 pixels from 3/4 of the top rail)
    title_top = outer[1] + 0.75 * menu_image('FrameTop', screen, user)[1]
    title_bottom = title_top + line_height('MedievalSharp-13', screen, user) + 4.0
    left = outer[0] + menu_image('FrameLeft', screen, user)[0]
    right = outer[2] - menu_image('FrameRight', screen, user)[0]
    client = (left, title_bottom, right, outer[3] - menu_image('FrameBottom', screen, user)[1])
    titlebar = (left, title_top, right, title_bottom)
    close = (right - (title_bottom - title_top), title_top, right, title_bottom)
    boxes = {}

    def place(node, parent_client, parent_outer):
        rect = child_rect(node, parent_outer if node.props.get('NonClient') == 'True' else parent_client, s)
        boxes[node.path] = rect
        for c in node.children:
            place(c, rect, rect)
    for c in book.children:
        place(c, client, outer)
    return {'outer': outer, 'client': client, 'titlebar': titlebar, 'close': close, 'boxes': boxes, 'scale': s,
            'fit': fit}


def inside(inner, outer):
    return (inner[0] >= outer[0] - TOLERANCE and inner[1] >= outer[1] - TOLERANCE and
            inner[2] <= outer[2] + TOLERANCE and inner[3] <= outer[3] + TOLERANCE)


def overlaps(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


# ------------------------------------------------------------------------------------------------ texts
def wrap_lines(font, text, width, screen, user):
    lines = []
    for paragraph in text.split('\n'):
        current = ''
        for word in paragraph.split(' '):
            trial = word if not current else current + ' ' + word
            if current and text_width(font, trial, screen, user) > width + 1e-6:
                lines.append(current)
                current = word
            else:
                current = trial
        lines.append(current)
    return lines


def text_fits(node, text, box, screen, user):
    """True when the text fits the box of the static text window (unframed: the box is the text area)."""
    font = node.props.get('Font', 'MedievalSharp-8')
    width, height = box[2] - box[0], box[3] - box[1]
    if node.props.get('HorzFormatting', '').startswith('WordWrap'):
        lines = wrap_lines(font, text, width, screen, user)
        widest = max(text_width(font, w, screen, user) for w in text.replace('\n', ' ').split(' ') if w)
        return widest <= width + TOLERANCE and len(lines) * line_height(font, screen, user) <= height + TOLERANCE
    lines = text.split('\n')
    return (max(text_width(font, part, screen, user) for part in lines) <= width + TOLERANCE and
            len(lines) * line_height(font, screen, user) <= height + TOLERANCE)


# The longest values the code fills in. Names: every given name with every surname or title (config/social-names.cfg)
names, hometowns, age_jokes = [], [], []
for line in content_packages.read_layout_text(repo, 'config/social-names.cfg').split('\n'):
    cells = line.rstrip('\r').split('\t')
    if cells[0] == '[NameGroup]':
        names.append(([], []))
    elif cells[0] == 'Given':
        names[-1][0].extend(c for c in cells[2:] if c)
    elif cells[0] in ('Surname', 'Title'):
        names[-1][1].extend(c for c in cells[1:] if c)
    elif cells[0] == 'Hometown':
        hometowns.extend(c for c in cells[1:] if c)
    elif cells[0] == 'AgeJoke':
        age_jokes.extend(c for c in cells[1:] if c)
full_names = [g + ((' ' + t) if t else '') for given, last in names for g in given for t in [''] + last]
check(len(full_names) > 5000 and hometowns and age_jokes, 'names, hometowns and age jokes are read')
texts = {'Relation': [], 'Job': [], 'Bio': []}
for line in content_packages.read_layout_text(repo, 'config/social-texts.cfg').split('\n'):
    cells = line.rstrip('\r').split('\t')
    if cells[0] in texts:
        texts[cells[0]].append(cells[-1])
check(all(texts.values()), 'relations, jobs and bios are read')
statuses = re.findall(r'return "([A-Za-z\' ]+)";', (repo / 'source/social/CreaturePosts.cpp').read_text(encoding='utf-8')[
    (repo / 'source/social/CreaturePosts.cpp').read_text(encoding='utf-8').index('CreaturePosts::getRelationshipStatus'):][:600])
check('Single' in statuses and 'In a relationship' in statuses, 'relationship statuses are read')
paths = sorted(set(re.findall(r'^Path\s+(.+?)\s*$', content_packages.read_layout_text(repo, 'config/creatureSkills.cfg'), re.M)))
check(len(paths) >= 3, 'skill paths are read')
handle_max = '@' + 'w' * 14 + '99'  # the handle: letters of the first name, at most 2 digits (Creature.cpp)
check('PROFILE_HANDLE_NUMBER_COUNT' in (repo / 'source/entities/Creature.cpp').read_text(encoding='utf-8'), 'handle')
longest_given = max((g for given, _ in names for g in given), key=len)
handle_max = '@' + longest_given.lower() + '99'


def widest(pool, font, screen=(1024, 768), user=1.0, count=3):
    return sorted(set(pool), key=lambda t: -text_width(font, t, screen, user))[:count]


def rounded(value):
    """Creature::formatRoundedNumber: at most two decimals without zeros at the end, exponent from 1e15 on."""
    if abs(value) >= 1e15:
        text = '%.2e' % value
        mantissa, exponent = text.split('e')
        mantissa = mantissa.rstrip('0').rstrip('.')
        return mantissa + 'e' + exponent
    text = ('%.2f' % value).rstrip('0').rstrip('.')
    return '0' if text in ('-0', '') else text


def group(number):
    if any(c in number for c in 'ein'):
        return number
    sign = 1 if number.startswith('-') else 0
    whole = number.find('.') if '.' in number else len(number)
    result = number
    comma = whole
    while comma > sign + 3:
        result = result[:comma - 3] + ',' + result[comma - 3:]
        comma -= 3
    return result


NUMBERS = sorted({group(rounded(float('-9.8765432109876543e%d' % e))) for e in range(-12, 15)},
                 key=lambda n: (fonts['MedievalSharp-8'][0].getlength(n), n))[-4:]
PAIRS = [a + ' / ' + b for a in NUMBERS[-2:] for b in NUMBERS[-2:]]
# The worst texts per dynamic window (window path: texts); the profile values are shortened to their box by the code
DYNAMIC = {
    'Header/NameText': widest(full_names, 'MedievalSharp-12'),
    'ProfilePage/AgeValue': [str(n) for n in range(1, 31)] + age_jokes,
    'ProfilePage/GenderValue': ['Female', 'Male', '-'],
    'ProfilePage/RelationshipValue': texts['Relation'] + statuses,
    'ProfilePage/OriginValue': hometowns,
    'ProfilePage/JobValue': texts['Job'],
    'ProfilePage/PathValue': paths + ['none'],
    'ProfilePage/QuoteText': ['"' + bio + '"' for bio in texts['Bio']],
    'ProfilePage/PostsTitle': ['Posts (200)'],
    'ProfilePage/PostsEmpty': ['Nothing posted yet.'],
    'ValuesPage/CombatValues': ['\n'.join([n + '%', n, n]) for n in NUMBERS],
    'ValuesPage/DefenseValues': ['\n'.join([n, n, n]) for n in NUMBERS],
    'InventoryPage/HintText': ['This creature is out of sight; its items are not known here.',
                               'Only the hands of a creature of another keeper can be seen.'],
}
for key in ('Experience', 'HitPoints', 'Gold', 'SightRadius', 'Potions', 'Inventory', 'DamagePerSecond', 'SkillPoints'):
    DYNAMIC['ValuesPage/%sValue' % key] = NUMBERS + PAIRS + ['-', '4 / 4']
# The Skills page (INGAME-QS-12 K7): every path name of config/creatureSkills.cfg as a column title, every rank text of
# a skill ("rank/most ranks" of CreatureSkillTreeView barText; SkillRanksPerSkill of config/global.cfg, 1 for tier 4)
max_rank = int(re.search(r'^\s*SkillRanksPerSkill\s+(\d+)', content_packages.read_layout_text(repo, 'config/global.cfg'),
                         re.M).group(1))
SKILL_NODES = ['TierFour'] + ['Column%dTier%d' % (c, t) for c in range(4) for t in (3, 2, 1)]
for column in range(4):
    DYNAMIC['SkillsPage/Column%dTitle' % column] = paths
for node_name in SKILL_NODES:
    DYNAMIC['SkillsPage/%sRank' % node_name] = (['%d/1' % r for r in (0, 1)] if node_name == 'TierFour' else
                                                ['%d/%d' % (r, max_rank) for r in range(max_rank + 1)])
# Windows whose text SocialWindow shortens to the box (setFittedText); they need room for at least one line
SOCIAL_LINES = ('LikesText', 'DislikesText', 'FriendsText', 'FoeText', 'StatusText', 'EffectLine0', 'EffectLine1',
                'EffectLine2', 'RemarksText')
FITTED = ('AgeValue', 'GenderValue', 'RelationshipValue', 'OriginValue', 'JobValue', 'PathValue', 'SkillsValue',
          'QuoteText') + SOCIAL_LINES
for name in FITTED:
    check(('"%s"' % name in social_cpp) or name.startswith('EffectLine'), 'SocialWindow fills ProfilePage/%s' % name)
check(social_cpp.count('setFittedText(page->getChild(rowWindows[i])') == 1 and
      'setFittedText(page->getChild("SkillsValue")' in social_cpp and
      'setFittedText(page->getChild("QuoteText")' in social_cpp, 'the profile texts are shortened to their boxes')
fitted_body = social_cpp[social_cpp.index('void setFittedText('):]
fitted_body = fitted_body[:fitted_body.index('\n}\n')]
check('shortened = start + "...";' in fitted_body and
      'window->setTooltipText(Gui::toCeguiText(escapeMarkup(tooltip.empty() ? text : text + "\\n" + tooltip)));'
      in fitted_body,
      'a shortened text ends in "..." and its tooltip shows it whole with its explanation')

# The social lines of the profile (owner decision 2026-11-18): the data of the former shared page, each with a hover
# text that says what the line is, a buff or debuff with what it does and the time left
social_lines = social_cpp[social_cpp.index('void SocialWindow::refreshProfileSocialLines('):]
social_lines = social_lines[:social_lines.index('\n}\n')]
for fragment in ('info = creature->getProfileSocialInfo();', 'info.mEffectTooltips[i]'):
    check(fragment in social_lines, 'refreshProfileSocialLines: ' + fragment)
# The explaining texts are language entries: the code names the key, the English file says what the line said before
EXPLANATIONS = (('ui.dungeonbook.likes.tooltip', '. What this creature enjoys, from its social profile.'),
                ('ui.dungeonbook.dislikes.tooltip', '. What this creature cannot stand, from its social profile.'),
                ('ui.dungeonbook.friends.tooltip', '. The creatures of your side this one gets along with best.'),
                ('ui.dungeonbook.foe.tooltip', '. The creature of your side this one gets along with worst.'),
                ('ui.dungeonbook.status.tooltip', '\\nWhat the creature says about its mood right now.'),
                ('ui.dungeonbook.remarks.tooltip', 'Remarks that match the picture of this creature.'))
english = english_texts(repo)
for key, text in EXPLANATIONS:
    check('"%s"' % key in social_lines, 'refreshProfileSocialLines: ' + key)
    if english is not None:
        check(text in english.get(key, ''), 'the language file explains %s as before' % key)
creature_cpp = (repo / 'source/entities/Creature.cpp').read_text(encoding='utf-8')
effects_fn = creature_cpp[creature_cpp.index('static std::string getProfileEffectsText('):]
effects_fn = effects_fn[:effects_fn.index('\n}\n')]
check(effects_fn.count('.push_back(getProfileEffectTooltip(') == 3, 'every buff and debuff line gets its own explanation')
tooltip_fn = creature_cpp[creature_cpp.index('static std::string getProfileEffectTooltip('):]
tooltip_fn = tooltip_fn[:tooltip_fn.index('\n}\n')]
check('"ui.profile.effect.tooltip"' in tooltip_fn and 'getProfileEffectTime(turns)' in tooltip_fn and
      (english is None or ' Time left: {time}.' in english.get('ui.profile.effect.tooltip', '')),
      'the explanation names the time left')
info_fn = creature_cpp[creature_cpp.index('Creature::ProfileSocialInfo Creature::getProfileSocialInfo('):]
info_fn = info_fn[:info_fn.index('\n}\n')]
for fragment in ('info.mLikes.push_back(profile.mLikes[i]);', 'DungeonbookQuirkLogic::formatRemarks(',
                 'collectProfileRelations(', 'cache.findFriendsAndFoe(getName(), rosterVersion)',
                 'social::SocialGenerator::moodLine(', 'getProfileEffectsText(mRelaxTurns, mHangoverTurns, mMoodEffects,'):
    check(fragment in info_fn, 'getProfileSocialInfo: ' + fragment)

# No picture or icon of the book without interaction (owner decision 2026-11-18): every picture window, or the first
# window above it that takes the mouse, has a hover text in the layout or one the code sets
CREATURE_PAGES = ('FeedPage', 'ProfilePage', 'ValuesPage', 'InventoryPage')
# a picture without a hover text of its own shows the one of its parent (CEGUI InheritsTooltipText)
CODE_TIPS = {'ProfilePage/Portrait': 'page->getChild("Portrait")->setTooltipText(',
             'ValuesPage/Portrait': 'page->getChild("Portrait")->setTooltipText(',
             'ValuesPage/Portrait/Image': 'page->getChild("Portrait")->setTooltipText(',
             'InventoryPage/Portrait': 'page->getChild("Portrait")->setTooltipText(',
             'FeedPage/FeedRows/Row0/Portrait': 'row->getChild("Portrait")->setTooltipText(',
             'FeedPage/FeedRows/Row0/Picture': 'picture->setTooltipText(Gui::toCeguiText(text));',
             'ProfilePage/PostThumb0': 'thumb->setTooltipText(Gui::toCeguiText(Translation::tr("ui.dungeonbook.withage", thumbValues)));'}
for page_name in CREATURE_PAGES + ('NavBar', 'Header'):
    for node in book.child(page_name).walk():
        if node.type != 'OD/StaticImage' or 'Rule' in node.name:
            continue
        owner = node
        while owner.props.get('MousePassThroughEnabled') == 'True' or owner.type == 'DefaultWindow' and owner.name == 'Clip':
            owner = owner.parent
        key = owner.path.replace('Row1', 'Row0').replace('Row2', 'Row0')
        key = 'ProfilePage/PostThumb0' if key.startswith('ProfilePage/PostThumb') else key
        coded = key in CODE_TIPS and CODE_TIPS[key] in social_cpp
        slot = key.startswith('InventoryPage/SlotBox')  # item card, lock text or "<slot>: empty" (refreshInventory)
        tiles = key.endswith('Icon') and key.split('/')[-1][:-4] in ('Equipment', 'Path', 'Skills') and \
            'page->getChild(std::string(tiles[i]) + "Icon")->setTooltipText(tooltip);' in social_cpp
        check(owner.props.get('TooltipText') or coded or slot or tiles,
              '%s has no hover text (%s takes the mouse)' % (node.path, owner.path))
check('Gui::setPlainTooltip(slot, trWith("ui.dungeonbook.inventory.empty", "slot",' in social_cpp and
      (english is None or english.get('ui.dungeonbook.inventory.empty') == '{slot}: empty'), 'an empty slot names itself')

# ------------------------------------------------------------------------------------------------ 1. to 3. pages
CREATURE_PAGES = ('FeedPage', 'ProfilePage', 'ValuesPage', 'InventoryPage', 'SkillsPage')
BUTTON_TYPES = ('OD/Button', 'OD/InvisibleButton', 'OD/ImageButton', 'OD/IconButton', 'OD/MenuTextButton',
                'OD/Checkbox', 'OD/RadioButton', 'OD/Combobox', 'OD/SheetCombobox', 'OD/TabButton')
SCROLL_TYPES = ('OD/VerticalScrollbar', 'OD/HorizontalScrollbar', 'OD/ScrollablePane', 'OD/MenuScrollablePane',
                'OD/SheetScrollbar')
# The Skills page (INGAME-QS-12 K7) is a plain page as well; its skills are the icons of the former skill tree window
# (OD/ResearchButton, nothing happens on a click, check_creature_skill_tree_view.py)
for page_name in ('ProfilePage', 'ValuesPage', 'InventoryPage', 'SkillsPage'):
    page = book.child(page_name)
    check(page.type == 'DefaultWindow', page_name + ' is a plain page, no scrolled pane')
    for node in page.walk():
        check(node.type not in SCROLL_TYPES, node.path + ': no scrollbar on the page')
        check(node.props.get('VertScrollbar') != 'True' and node.props.get('HorzScrollbar') != 'True',
              node.path + ': no scrollbar on the page')
        check(node.type not in BUTTON_TYPES, node.path + ': no button on the page (K4)')
feed = book.child('FeedPage')
for node in feed.walk():
    check(node.type not in BUTTON_TYPES, node.path + ': no button on the feed of one creature (K4)')
check(not any('SkillTreeButton' in path.read_text(encoding='utf-8') for path in content_packages.data_glob(repo, 'gui', '*.layout')),
      'the skill tree button of the profile page is removed (K4)')

tightest = {}
table = {}
for screen in SCREENS:
    for user in USER_SCALES:
        g = geometry(screen, user)
        boxes, client = g['boxes'], g['client']
        case = '%dx%d %d%%' % (screen[0], screen[1], round(user * 100))
        check(inside(g['outer'], (0, 0, screen[0], screen[1])), case + ': the book is on the screen')
        for page_name in CREATURE_PAGES + ('Header', 'NavBar'):
            page = book.child(page_name)
            visible = boxes[page.path]
            check(inside(visible, client), '%s: %s inside the client of the book' % (case, page_name))
            for node in page.walk():
                box = boxes[node.path]
                if node.parent is not page.parent:
                    check(inside(box, boxes[node.parent.path]), '%s: %s inside its parent' % (case, node.path))
                check(inside(box, visible), '%s: %s inside the visible area of %s' % (case, node.path, page_name))
                table.setdefault(node.path, {})[case] = (box, visible)
                caption = node.props.get('Text')
                if caption and node.type == 'OD/StaticText':
                    caption = caption.replace('&#10;', '\n')
                    check(text_fits(node, caption, box, screen, user), '%s: caption of %s is cut' % (case, node.path))
                if node.path in DYNAMIC:
                    for value in DYNAMIC[node.path]:
                        fits = text_fits(node, value, box, screen, user)
                        if node.name in FITTED:
                            # shortened by the code; recorded, the box must hold at least one line
                            tightest.setdefault(node.path, set())
                            if not fits:
                                tightest[node.path].add(value)
                        else:
                            check(fits, '%s: %s cuts "%s"' % (case, node.path, value))
                if node.name in FITTED:
                    font = node.props.get('Font', 'MedievalSharp-8')
                    check(box[3] - box[1] >= line_height(font, screen, user) - TOLERANCE,
                          '%s: %s is lower than one line' % (case, node.path))
        # the profile line: the widest name in the large font and the longest handle in the small one on one line
        name_box = boxes['ProfilePage/NameText']
        widest_name = max(text_width('MedievalSharp-12', n, screen, user) for n in widest(full_names, 'MedievalSharp-12'))
        check(widest_name + text_width('MedievalSharp-8', '   ' + handle_max, screen, user) <= name_box[2] - name_box[0],
              case + ': the widest name and the longest handle share the profile line')
        check(line_height('MedievalSharp-12', screen, user) <= name_box[3] - name_box[1] + TOLERANCE,
              case + ': the profile line holds the large font')
        # the attribute cells: label and two lines of a value broken into 14 characters (decision 816)
        for name in ('Strength', 'Dexterity', 'Life', 'Mana'):
            cell = boxes['ValuesPage/' + name]
            check(3 * line_height('MedievalSharp-8', screen, user) <= cell[3] - cell[1] + TOLERANCE and
                  text_width('MedievalSharp-8', '-987,654,321,', screen, user) <= cell[2] - cell[0],
                  case + ': attribute cell ' + name)
        # The round portrait of the values page as CEGUI draws it: the ring (Frame) and the picture (Image) are shrunk
        # to squares (AspectMode Shrink, ratio 1) and centred in their parents (alignment Centre: the area position is
        # an offset from the middle). The ring is centred above the four attribute cells.
        outer = boxes['ValuesPage/Portrait']
        drawn = {}
        for part in ('Frame', 'Image'):
            node = book.child('ValuesPage').child('Portrait').child(part)
            area = udims(node.props['Area'])
            ow, oh = outer[2] - outer[0], outer[3] - outer[1]
            w, h = (area[2][0] - area[0][0]) * ow, (area[3][0] - area[1][0]) * oh
            check(node.props.get('AspectMode') == 'Shrink' and node.props.get('AspectRatio', '1') == '1',
                  'the %s of the values portrait keeps a square' % part)
            check(node.props.get('HorizontalAlignment') == 'Centre' and node.props.get('VerticalAlignment') == 'Centre',
                  'the %s of the values portrait is centred' % part)
            side = min(w, h)
            x0 = outer[0] + (ow - side) / 2.0 + area[0][0] * ow
            y0 = outer[1] + (oh - side) / 2.0 + area[1][0] * oh
            drawn[part] = (x0, y0, x0 + side, y0 + side)
        ring, picture = drawn['Frame'], drawn['Image']
        cells = [boxes['ValuesPage/' + n] for n in ('Strength', 'Dexterity', 'Life', 'Mana')]
        row_centre = (cells[0][0] + cells[-1][2]) / 2.0
        check(abs((ring[0] + ring[2]) / 2.0 - row_centre) <= 1.0, case + ': the ring is centred above the attributes')
        check(abs((picture[0] + picture[2]) / 2.0 - (ring[0] + ring[2]) / 2.0) <= 1.0 and
              abs((picture[1] + picture[3]) / 2.0 - (ring[1] + ring[3]) / 2.0) <= 1.0 and inside(picture, ring),
              case + ': the picture sits in the middle of the ring')
        check(inside(ring, outer) and ring[3] <= cells[0][1] + TOLERANCE, case + ': the ring is above the attributes')
        table.setdefault('ValuesPage/Portrait (ring drawn)', {})[case] = (ring, boxes['ValuesPage'])
        table.setdefault('ValuesPage/Portrait (picture drawn)', {})[case] = (picture, boxes['ValuesPage'])
        # The keeper mark of every list entry (INGAME-QS-7 U-2): beside level and mood, a usual nick on one line
        for row in range(7):
            base = 'HomePage/ListRows/Row%d/' % row
            keeper, mood, entry_box = boxes[base + 'Keeper'], boxes[base + 'Mood'], boxes[base.rstrip('/')]
            check(inside(keeper, entry_box) and keeper[0] >= mood[2] - TOLERANCE, case + ': keeper mark of ' + base)
            for nick in ('Player 1', 'Player 4', 'Keeper'):
                check(text_width('MedievalSharp-8', nick, screen, user) <= keeper[2] - keeper[0] and
                      line_height('MedievalSharp-8', screen, user) <= keeper[3] - keeper[1] + TOLERANCE,
                      '%s: the keeper "%s" fits the list entry' % (case, nick))
        # 5. the back arrow in the title bar, left of the title, clear of the close button
        back = boxes.get('BackButton', (0.0, 0.0, 0.0, 0.0))
        check('BackButton' in boxes, case + ': the back arrow is a window of the book')
        title_w = text_width('MedievalSharp-13', book.props.get('Text', ''), screen, user)
        title_left = (g['titlebar'][0] + g['titlebar'][2] - title_w) / 2.0
        check(inside(back, g['titlebar']), '%s: the back arrow lies in the title bar %s %s' % (case, back, g['titlebar']))
        check(back[2] <= title_left and not overlaps(back, g['close']), case + ': the back arrow is left of the title')
        prev, name_text, nxt = (boxes['Header/' + n] for n in ('PrevButton', 'NameText', 'NextButton'))
        check(prev[2] <= name_text[0] and name_text[2] <= nxt[0], case + ': "< Name >" in the head')
        check(boxes['Header'][1] >= client[1] - TOLERANCE and all(boxes[p][1] >= boxes['Header'][3] - TOLERANCE
                                                                 for p in CREATURE_PAGES), case + ': pages below the head')

# 3. the profile structure
profile = book.child('ProfilePage')
order = [c.name for c in profile.children if c.name.endswith('Label')]
check(order == ['AgeLabel', 'GenderLabel', 'RelationshipLabel', 'OriginLabel', 'JobLabel', 'PathLabel', 'SkillsLabel'],
      'profile rows in the order of book-variant-2: %s' % order)
labels = [profile.child(n).props.get('Text') for n in order]
check(labels == ['Age:', 'Gender:', 'Relationship:', 'Origin:', 'Job:', 'Path:', 'Skills:'], labels)
g = geometry((1920, 1200), 1.0)
b = g['boxes']
rows = [b['ProfilePage/' + n] for n in order[:6]]
check(all(r1[3] <= r2[1] + TOLERANCE for r1, r2 in zip(rows, rows[1:])), 'the rows of the table follow each other')
check(b['ProfilePage/Portrait'][2] < b['ProfilePage/NameText'][0], 'the portrait is left of the name')
check(b['ProfilePage/NameText'][3] <= rows[0][1], 'name and handle above the table')
check(b['ProfilePage/SkillsLabel'][1] >= rows[-1][3] and b['ProfilePage/QuoteText'][1] >= b['ProfilePage/SkillsValue'][3],
      'skills below the table, the quote below the skills')
thumbs = [b['ProfilePage/PostThumb%d' % i] for i in range(6)]
columns = sorted({round(t[0], 3) for t in thumbs})
grid_rows = sorted({round(t[1], 3) for t in thumbs})
check(len(columns) == 2 and len(grid_rows) == 3, 'the post pictures form 2 columns x 3 rows')
check(all(t[0] > b['ProfilePage/QuoteText'][2] and t[0] >= b['ProfilePage/PostsTitle'][0] - TOLERANCE for t in thumbs),
      'the post pictures are the right column under "Posts"')
check(all(not overlaps(a, c) for i, a in enumerate(thumbs) for c in thumbs[i + 1:]), 'the post pictures do not overlap')
check([round(t[1], 3) for t in thumbs] == [grid_rows[0], grid_rows[0], grid_rows[1], grid_rows[1], grid_rows[2],
                                            grid_rows[2]], 'the newest posts fill the grid row by row')
check('MAX_OWN_POSTS = 6' in social_cpp and 'page->getChild("PostThumb" + std::to_string(rows))' in social_cpp,
      'the six newest posts are shown')
for gone in ('SocialHolder', 'SocialText', 'InfoText', 'KeeperText', 'HealthBar'):
    check(gone not in [n.name for n in profile.walk()], 'the profile of book-variant-2 has no ' + gone)

# Painted surfaces (owner 2026-11-18, the book must look like book-variant-2): every rule of the pages is the painted
# iron rule of the book, no flat bar; the values panels and tiles have the rust frame of the slot boxes
for page_name in CREATURE_PAGES + ('NavBar',):
    for node in book.child(page_name).walk():
        if node.name.endswith('Rule') or node.name in ('Rule1', 'Rule2'):
            check(node.type == 'OD/StaticImage' and node.props.get('Image') in (
                'DungeonbookIcons/BookTitleRule', 'DungeonbookIcons/BookFrameLeft', 'OpenDungeonsGameWindow/TitleRule'),
                node.path + ' is a painted rule')
for name in ('StatsPanel', 'CombatPanel', 'DefensePanel', 'EquipmentTile', 'PathTile', 'SkillsTile'):
    props = book.child('ValuesPage').child(name).props
    check(props.get('FrameEnabled') == 'True' and props.get('FrameColours') == 'tl:FF6E4A2C tr:FF6E4A2C bl:FF6E4A2C br:FF6E4A2C',
          'ValuesPage/%s has the rust frame' % name)

# 4. the navigation bar
nav = book.child('NavBar')
buttons = [c for c in nav.children if c.type == 'OD/Button']
check([c.name for c in buttons] == ['NavFeed', 'NavProfile', 'NavValues', 'NavInventory', 'NavSkills'],
      'five buttons, Skills last: %s' % [c.name for c in buttons])
check([c.child('Label').props.get('Text') for c in buttons] == ['Feed', 'Profile', 'Values', 'Inventory', 'Skills'],
      'the labels of the navigation bar')
check(all(c.child('Icon').props.get('Image', '').startswith('DungeonbookIcons/') for c in buttons), 'icon and label')
widths = [udims(c.props['Area'])[2][0] - udims(c.props['Area'])[0][0] for c in buttons]
check(max(widths) - min(widths) < 1e-3, 'the five buttons are equally wide')
for needle in ('NAV_SKILLS_BUTTON = "NavSkills"', 'skills->setEnabled(hasSkillTree);',
               'NAV_SKILLS_BUTTON), CEGUI::PushButton::EventClicked,\n        CEGUI::Event::Subscriber(&SocialWindow::onSkillTreeClicked',
               'if(mSelectedCreature.empty() || !selectedCreatureHasSkillTree())'):
    check(needle in social_cpp, 'SocialWindow: ' + needle.split('\n')[0])

# The keeper mark of the list (INGAME-QS-7 U-2) is filled from the roster entry, the row tooltip names it whole
rows_fill = social_cpp[social_cpp.index('void SocialWindow::refreshListRows()'):]
rows_fill = rows_fill[:rows_fill.index('\n}\n')]
check('setFittedText(row->getChild("Keeper"), entry->keeper, false, "");' in rows_fill and
      'rowValues["keeper"] = entry->keeper;' in rows_fill and '"ui.dungeonbook.row.tooltip"' in rows_fill and
      (english is None or english.get('ui.dungeonbook.row.tooltip') == '{name} ({class}), keeper {keeper}'),
      'every list entry marks the keeper of its creature')

# 5. the single-creature view
show =social_cpp[social_cpp.index('void SocialWindow::showPage(Page page)'):]
show = show[:show.index('\n}\n')]
for needle in ('mWindow->getChild("HomePage")->setVisible(page == Page::Home);',
               'mWindow->getChild("BackButton")->setVisible(page != Page::Home);',
               'mWindow->getChild("Header")->setVisible(page != Page::Home);'):
    check(needle in show, 'showPage: ' + needle)
back_node = book.child('BackButton')
check(back_node.props.get('NonClient') == 'True' and back_node.props.get('Visible') == 'False',
      'the back arrow is a hidden NonClient child of the book')

# ------------------------------------------------------------------------------------------------ 6. the item tooltip
equipment_text = content_packages.read_layout_text(repo, 'config/equipments.cfg')
equipment_text = equipment_text[equipment_text.rindex('[EquipmentDefinitions]'):]
blocks = re.findall(r'\[Equipment\](.*?)\[/Equipment\]', equipment_text, re.S)
check(len(blocks) >= 30, 'equipment blocks are read')
pick = None
for block in blocks:
    name = re.search(r'^\s*Name\s+(\S+)', block, re.M)[1]
    display = re.search(r'^\s*DisplayName\s+(.+?)\s*$', block, re.M)
    # every equipment has a display name, which is never a joined internal name like "KoboldPick"
    check(display is not None and not re.search(r'[a-z0-9][A-Z]', display[1]), '%s has a display name' % name)
    values = {k: float(v) for k, v in re.findall(r'^\s*(\w+)\s+(-?[0-9.]+)\s*$', block, re.M)}
    if name == 'KoboldPick':
        pick = (display[1] if display else '', values)
check(pick is not None and pick[0] == 'Kobold Pick', 'the KoboldPick reads "Kobold Pick"')
check('if (nextParam == "DisplayName")' in weapon_cpp and 'std::string Weapon::getDisplayName() const' in weapon_cpp,
      'Weapon reads the DisplayName')
for function in ('std::string ItemInstance::describe(', 'std::string ItemInstance::describeTooltip('):
    body = item_cpp[item_cpp.index(function):]
    body = body[:body.index('\n}\n')]
    check('heldWeapon->getDisplayName()' in body and 'heldWeapon->getName()' not in body, function + ': display name')
    check('describeWeaponValueLines(*heldWeapon)' in body and '" / "' not in body, function + ': named value lines')

# Python replica of ItemValueLines::describeWeapon; the header holds the same labels and the same zero rule
LINE_LABELS = [('Physical damage', 'PhysicalDamageMin', 'PhysicalDamage'), ('Magical damage', 'MagicalDamageMin', 'MagicalDamage'),
               ('Elemental damage', 'ElementDamageMin', 'ElementDamage'), ('Physical defence', None, 'PhysicalDefense'),
               ('Magical defence', None, 'MagicalDefense'), ('Elemental defence', None, 'ElementDefense'),
               ('Attack rating', None, 'AttackRating'), ('Defence rating', None, 'DefenseRating')]
# The header holds the language keys of the labels; the language file holds the labels the tooltip showed before
LABEL_KEYS = ['ui.item.value.physicaldamage', 'ui.item.value.magicaldamage', 'ui.item.value.elementaldamage',
              'ui.item.value.physicaldefence', 'ui.item.value.magicaldefence', 'ui.item.value.elementaldefence',
              'ui.item.value.attackrating', 'ui.item.value.defencerating']
english = english_texts(repo)
for (label, _, _), key in zip(LINE_LABELS, LABEL_KEYS):
    check('"%s"' % key in lines_h, 'ItemValueLines.h names the key "%s"' % key)
    if english is not None:
        check(english.get(key) == label, 'the language file says "%s" for %s' % (label, key))
check('if(value != 0.0)' in lines_h and 'if(minimum != 0.0 || maximum != 0.0)' in lines_h, 'a value of 0 has no line')


def number(value):
    return '%d' % value if value == int(value) else '%g' % value


def weapon_lines(values):
    result = []
    for label, low, high in LINE_LABELS:
        top = values.get(high, 0.0)
        bottom = values.get(low, top) if low else top
        if (low and (bottom != 0.0 or top != 0.0)) or (not low and top != 0.0):
            result.append('%s: %s' % (label, number(top) if (not low or bottom == top) else number(bottom) + '-' + number(top)))
    return result


check(weapon_lines(pick[1] if pick else {}) == [], 'the KoboldPick tooltip has no value line (all its values are 0)')
for block in blocks:
    values = {k: float(v) for k, v in re.findall(r'^\s*(\w+)\s+(-?[0-9.]+)\s*$', block, re.M)}
    for line in weapon_lines(values):
        label, _, value = line.partition(': ')
        check(label in [l for l, _, _ in LINE_LABELS] and value and not re.fullmatch(r'0(-0)?', value),
              'value line "%s" names its value and is not 0' % line)

# the quality colours and the thick frame
QUALITY = {'Poor': 'FF8A8A8A', 'Common': 'FFFFFFFF', 'Rare': 'FF3E7BFF', 'Epic': 'FFA64DFF'}
colours = re.search(r'QUALITY_COLOURS = \{\{"(\w+)", "(\w+)", "(\w+)", "(\w+)"\}\}', item_cpp)
check(colours is not None and list(colours.groups()) == list(QUALITY.values()), 'the four quality colours')
look = ET.fromstring(look_text).find("WidgetLook[@name='OD/ItemTooltip']")
border = look.find("ImagerySection[@name='border']/FrameComponent")
frame_image = re.search(r'ITEM_TOOLTIP_FRAME_IMAGE = "([^"]+)"', gui_cpp)[1]
check([i.get('name') for i in border.findall('Image')] == [frame_image] * 8, 'the frame is drawn on all eight parts')
check(border.find("ColourRectProperty[@name='QualityFrameColour']") is not None and border.find('Colours') is None,
      'the frame takes the colour of the quality')
check('tooltip->setProperty("QualityFrameColour", frame);' in gui_cpp and
      'markItemTooltip(window, ItemInstance::getQualityColour(item.mQuality), std::string());' in gui_cpp,
      'Gui gives the tooltip the colour of the item')
check(gui_cpp.index('createItemTooltipFrameImage();') < gui_cpp.index('createFromFile("ODSkin.scheme")'),
      'the frame image exists before the look is loaded')
frame_pixels = int(re.search(r'ITEM_TOOLTIP_FRAME_PIXELS = (\d+);', gui_cpp)[1])
frame_design = frame_pixels / DENSITY['OpenDungeonsIcons/']
# The inner border of the window frame: the opaque columns of ODMenuTemplate/FrameLeft inside its darkest gap
fl = imagesets['ODMenuTemplate']['FrameLeft']
sheet = Image.open(content_packages.resolve(repo, 'gui/' + imagesets['ODMenuTemplate']['__file__'])).convert('RGBA')
column_light = []
for col in range(int(fl[0])):
    pixels = [sheet.getpixel((int(fl[2]) + col, int(fl[3]) + row)) for row in range(40, int(fl[1]) - 40, 4)]
    column_light.append(sum(0.299 * p[0] + 0.587 * p[1] + 0.114 * p[2] for p in pixels) / len(pixels))
brightest = column_light.index(max(column_light))
gap = min(range(brightest, len(column_light)), key=lambda c: column_light[c])
inner_border = (len(column_light) - gap - 1) / DENSITY['ODMenuTemplate/']
check(frame_design >= inner_border, 'frame %.2f design px thinner than the inner window border %.2f' % (frame_design,
                                                                                                     inner_border))
for quality, colour in QUALITY.items():
    for screen in SCREENS:
        for user in USER_SCALES:
            s = layout_scale(screen, user)
            check(frame_design * s >= inner_border * s, '%s frame at %s' % (quality, screen))
    check(QUALITY[quality] in item_cpp, quality + ' colour in ItemInstance')

# ------------------------------------------------------------------------------------------------ 7. the position
for needle in ('float x = std::max(std::max(hand.mRight, item.mRight), cursorX) + gap;', 'float y = cursorY + gap;',
               'if(y + height > screenHeight)\n        y = screenHeight - height;',
               'if(x + width > screenWidth)\n    {\n        x = screenWidth - width;',
               'const float below = std::max(item.mBottom, cursorY) + gap;',
               'const float above = item.mTop - gap - height;'):
    check(needle in placement_h, 'ItemTooltipPlacement: ' + needle.split('\n')[0])
check('placeItemTooltip(tooltip, target, hand, cursor, screen, gap);' in gui_cpp, 'Gui places the item card')


def place(cursor, hand, item, size, screen, gap):
    """Python replica of ItemTooltipPlacement::place."""
    x = max(hand[2], item[2], cursor[0]) + gap
    y = cursor[1] + gap
    if y + size[1] > screen[1]:
        y = screen[1] - size[1]
    if x + size[0] > screen[0]:
        x = screen[0] - size[0]
        if overlaps((x, y, x + size[0], y + size[1]), item):
            below = max(item[3], cursor[1]) + gap
            above = item[1] - gap - size[1]
            if below + size[1] <= screen[1]:
                y = below
            elif above >= 0:
                y = above
    x = max(0.0, min(x, screen[0] - size[0]))
    y = max(0.0, min(y, screen[1] - size[1]))
    return (x, y, x + size[0], y + size[1])


def card_size(screen, user):
    """Pixel size of the item card of the KoboldPick: name, quality and price, type, hands, level, inside the frame."""
    lines = [('MedievalSharp-13', 'Kobold Pick'), ('MedievalSharp-10', 'Poor     00 20'),
             ('MedievalSharp-10', 'Type: tool'), ('MedievalSharp-10', 'Hands: 1'), ('MedievalSharp-10', 'Level 1')]
    inset = 2 * (frame_design * layout_scale(screen, user) + 8.0)
    return (max(text_width(f, t, screen, user) for f, t in lines) + inset,
            sum(line_height(f, screen, user) for f, _ in lines) + inset)


placements = 0
for screen in ((640, 480), (1920, 1200)):
    for user in USER_SCALES:
        size = card_size(screen, user)
        gap = 0.25 * line_height('MedievalSharp-10', screen, user)
        # the hand picture as in the screenshot ODscreenshot_2026-11-18_164734_0 (about 80 x 64 pixels at 1200 high)
        hand_w, hand_h = 80.0 * screen[1] / 1200.0, 64.0 * screen[1] / 1200.0
        g = geometry(screen, user)
        cursors = [(screen[0] * fx, screen[1] * fy, None) for fx in (0.1, 0.2, 0.8, 0.95) for fy in (0.1, 0.2, 0.8, 0.95)]
        cursors += [((b[0] + b[2]) / 2, (b[1] + b[3]) / 2, b) for k, b in g['boxes'].items()
                    if re.fullmatch(r'InventoryPage/SlotBox\d+', k)]
        for cx, cy, slot in cursors:
            item = slot if slot else (cx - 20.0 * g['scale'], cy - 20.0 * g['scale'], cx + 20.0 * g['scale'],
                                      cy + 20.0 * g['scale'])
            hand = (cx, cy, cx + hand_w, cy + hand_h)
            box = place((cx, cy), hand, item, size, screen, gap)
            placements += 1
            where = '%dx%d %d%% cursor (%.0f, %.0f)' % (screen[0], screen[1], round(user * 100), cx, cy)
            check(inside(box, (0, 0, screen[0], screen[1])), where + ': tooltip on the screen')
            check(not overlaps(box, item), where + ': tooltip over the item')
            fits_right = max(hand[2], item[2], cx) + gap + size[0] <= screen[0]
            fits_below = cy + gap + size[1] <= screen[1]
            if fits_right:
                check(box[0] >= cx and box[0] >= item[2], where + ': right of the cursor and of the item')
                check(box[1] >= cy if fits_below else box[3] == screen[1], where + ': below, or up just enough')
            else:
                check(box[2] == screen[0], where + ': left only as far as needed')

if '--table' in sys.argv:
    for path, cases in table.items():
        if not re.match(r'(ProfilePage|ValuesPage|InventoryPage|Header|NavBar)(/|$)', path):
            continue
        if path.count('/') > 1 and not re.search(r'SlotBox\d+$|PostThumb\d$|Nav\w+$', path):
            continue
        row = []
        for case in ('640x480 80%', '640x480 120%', '1920x1200 80%', '1920x1200 120%', '7680x4320 80%', '7680x4320 120%'):
            box, page = cases[case]
            row.append('[%.0f,%.0f-%.0f,%.0f]' % box)
        box, page = cases['1920x1200 80%']
        frac = ((box[0] - page[0]) / (page[2] - page[0]), (box[1] - page[1]) / (page[3] - page[1]),
                (box[2] - page[0]) / (page[2] - page[0]), (box[3] - page[1]) / (page[3] - page[1]))
        print('| %s | %.3f-%.3f x %.3f-%.3f | %s |' % (path, frac[0], frac[2], frac[1], frac[3], ' '.join(row)))

for failure in failures:
    print('FAIL ' + failure)
shortened = {k: len(v) for k, v in tightest.items() if v}
print('Dungeonbook pages B1: %d screens x %d UI scales, %d windows, %d tooltip placements, frame %.1f >= inner border '
      '%.2f design px; texts the code shortens at the smallest size: %s; %d failures' % (
          len(SCREENS), len(USER_SCALES), len(table), placements, frame_design, inner_border,
          ', '.join('%s %d' % (k.split('/')[-1], n) for k, n in sorted(shortened.items())) or 'none', len(failures)))
if failures:
    sys.exit(1)
