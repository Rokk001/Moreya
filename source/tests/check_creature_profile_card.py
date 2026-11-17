"""Check the shared creature profile page (gui/WindowCreatureProfilePage.layout) and that the old creature card is gone.

The old creature card (gui/WindowCreatureProfile.layout, Creature::createStatsWindow) opened by a middle click is
removed: a middle click on a creature opens the Dungeonbook on it (check_creature_click_dungeonbook.py). The profile
page the card shared with the Dungeonbook stays: created from its layout (registered for UI scaling), filled by
Creature::fillProfilePage, flowed by Gui::layoutCreatureProfilePage and fully reachable in the book on every screen.
"""
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from PIL import ImageFont

repo = Path(__file__).resolve().parents[2]
gui = (repo / 'source/render/Gui.cpp').read_text()
# The old creature card and its stats page are gone; the page with portrait, texts and bars is shown by the Dungeonbook
assert not (repo / 'gui/WindowCreatureProfile.layout').exists(), 'the old creature card layout is removed'
assert 'WindowCreatureProfile.layout' not in gui and 'createCreatureProfileWindow' not in gui, 'the card is still created'
page = (repo / 'gui/WindowCreatureProfilePage.layout').read_text()
for name in ('ProfilePage', 'Portrait', 'HealthBar', 'ExperienceBar', 'BioText', 'FriendsLabel', 'FriendLink0', 'FriendLink1', 'FoeLabel',
             'FoeLink', 'StatusText', 'LatestText'):
    assert 'name="%s"' % name in page, name
assert 'type="OD/VerticalScrollbar" name="ProfileScrollbar"' in page, 'the shared profile must scroll'
assert 'name="ClippedByParent" value="True"' in page, 'the profile must clip at its viewport'

body = gui[gui.index('CEGUI::Window* Gui::createCreatureProfilePage('):]
body = body[:body.index('\n}\n')]
assert 'WindowCreatureProfilePage.layout' in body and 'registerWindowHierarchy(page)' in body

creature = (repo / 'source/entities/Creature.cpp').read_text()
creature_header = (repo / 'source/entities/Creature.h').read_text()
# No creature window of its own: no stats window, no tabs, no server statistics subscription from the creature
for gone in ('createStatsWindow', 'destroyStatsWindow', 'updateStatsWindow', 'mStatsWindow', 'ProfileTabClicked',
             'StatsTabClicked', 'BookTabClicked', 'showStatsPage', 'refreshProfilePage', 'createCreatureProfileWindow',
             'ClientNotificationType::askCreatureInfos', 'canDisplayStatsWindow'):
    assert gone not in creature and gone not in creature_header, gone + ' of the old creature card is still there'
slot_types = ET.parse(repo / 'gui/SlotTypes.imageset').getroot()
assert {image.attrib['name'] for image in slot_types.findall('Image')} == {'Head', 'Hand', 'Armour', 'Boots', 'Ring', 'Potion', 'Bag'}
assert page.count('name="SlotType"') == 13
assert 'slotType->setVisible(item == nullptr)' in creature
assert '"Hand", "Hand", "Head", "Armour", "Boots", "Ring"' in creature
assert '"Potion", "Potion", "Potion", "Bag", "Bag", "Bag", "Bag"' in creature
assert 'CEGUI::UDim(0, 380)' not in creature, 'the page sets an own size'
assert 'social/SocialProfileCache.h' in creature
# one function fills the page; the Dungeonbook creates the page in its holder and fills it
assert 'float Creature::fillProfilePage(CEGUI::Window* page)' in creature
assert 'WindowCreatureProfilePage.layout' in gui and 'setName("Content")' in gui
social_cpp = (repo / 'source/render/SocialWindow.cpp').read_text()
assert 'fillProfilePage(mProfilePage)' in social_cpp
assert 'createCreatureProfilePage(' in social_cpp, 'the book creates the shared page'

# The initial viewport reserves the portrait, equipment and attributes; social metadata follows.
for name in ('HealthLabel', 'ExperienceLabel', 'RelationText', 'FoeLabel'):
    assert 'name="%s"' % name in page, name
profile_layout = gui[gui.index('float Gui::layoutCreatureProfilePage'):gui.index('void Gui::applyProfileScroll')]
assert profile_layout.index('CEGUI::Window* equipment') < profile_layout.index('page->getChild("AttributesText")')
assert profile_layout.index('page->getChild("AttributesText")') < profile_layout.index('const char* const personalRows')
assert profile_layout.index('page->getChild("EquipmentRow")') < profile_layout.index('page->getChild("AttributesText")') < profile_layout.index('const char* const barNames') < profile_layout.index('const char* const personalRows')
assert '"EquipmentRow"' in gui[gui.index('const char* const PROFILE_FLOW_ROWS[]'):gui.index('const std::size_t PROFILE_FLOW_ROW_COUNT')]
assert 'page->getPixelSize().d_width / scale - 148.0f - PROFILE_RIGHT_MARGIN' in profile_layout
assert 'page->getPixelSize().d_height / scale * 0.2f' in profile_layout
assert 'std::min(equipmentWidth / 4.0f, headerHeight / 5.0f)' in profile_layout
assert '2.5f, 0.5f, 1.5f, 1.5f, 1.5f, 2.5f,' in profile_layout
assert '1.0f, 1.0f, 0.0f, 1.0f, 2.0f, 2.0f,' in profile_layout
assert 'slot < 13' in profile_layout and '5.0f * edge' in profile_layout
assert 'setScaledArea(equipment, CEGUI::URect(CEGUI::UDim(0, 148), CEGUI::UDim(0, 34),' in profile_layout
assert 'countWrappedLines(equipment' not in profile_layout, 'hidden equipment text must not displace the item slots'
assert '34.0f + equipmentHeight + PROFILE_ROW_GAP' in profile_layout
assert 'getProfileLinesHeight(window, lines, scale)' in gui
assert 'getRenderedString()' in gui, 'measure the actual rendered text rather than a fixed number of rows'
assert 'setDocumentSize(y)' in profile_layout and 'setPageSize(viewport)' in profile_layout
assert 'std::min(scrollbar->getScrollPosition(), y - viewport)' in profile_layout
assert 'applyProfileScroll(page, offset)' in profile_layout
assert 'isFlowRow || (mProfileBaseAreas.find(child) == mProfileBaseAreas.end())' in profile_layout
for name in ('Portrait', 'NameText', 'EquipmentText', 'HandleText', 'AgeText', 'RelationText', 'FromText', 'JobText',
             'HealthLabel', 'HealthBar', 'ExperienceLabel', 'ExperienceBar'):
    cache_rows = gui[gui.index('const char* const PROFILE_FLOW_ROWS[]'):gui.index('const std::size_t PROFILE_FLOW_ROW_COUNT')]
    assert '"' + name + '"' in cache_rows, name + ' must refresh its unscrolled bounds on every layout'

# Use the shipped font and every configured weapon name, not short invented equipment labels.
font_spec = ET.parse(repo / 'gui/fonts/MedievalSharp-8.font').getroot()
font = ImageFont.truetype(str(repo / 'gui/fonts' / font_spec.get('filename')), 1024)
font_factor = float(font_spec.get('size')) * (96.0 / 72.0) * (1024.0 / 800.0) / 1024.0
line_height = sum(font.getmetrics()) * font_factor
weapon_names = re.findall(r'^\s*Name\s+(\S+)', (repo / 'config/equipments.cfg').read_text(), re.M)
assert weapon_names
longest_weapon = max(weapon_names + ['none'], key=font.getlength)
equipment_text = 'Equipment: ' + longest_weapon + ' / ' + longest_weapon
assert '"Equipment: " + getEquipmentText()' in creature
assert 'right + " / " + left' in creature
# Exercise the current attribute formula through MAX_LEVEL, including the two carried-item bonuses.
creature_config = (repo / 'config/creatures.cfg').read_text()
equipment_config = (repo / 'config/equipments.cfg').read_text()
max_level = int(re.search(r'MAX_LEVEL = (\d+)', (repo / 'source/entities/CreatureDefinition.h').read_text())[1])
attribute_values = []
for block in re.findall(r'\[Creature\](.*?)\[/Creature\]', creature_config, re.S):
    stats_values = dict((key, float(value)) for key, value in re.findall(
        r'^\s*(Strength|Dexterity|Life|Mana|StrengthPerLevel|DexterityPerLevel|LifePerLevel|ManaPerLevel)\s+(-?[0-9.]+)', block, re.M))
    for attribute in ('Strength', 'Dexterity', 'Life', 'Mana'):
        bonus = max([0.0] + [float(value) for value in re.findall(
            r'^\s*' + attribute + r'\s+(-?[0-9.]+)', equipment_config, re.M)]) * 2
        for level in (1, max_level):
            attribute_values.append(stats_values.get(attribute, 0.0) +
                                    stats_values.get(attribute + 'PerLevel', 0.0) * (level - 1) + bonus)
assert attribute_values
number_texts = [format(value, '.1f').removesuffix('.0') for value in attribute_values]
longest_number = max(number_texts, key=font.getlength)
critical_text = max([format(value, '.1f') for value in attribute_values], key=font.getlength)
attribute_lines = ['Strength {0} - Dexterity {0} - Life {0}'.format(longest_number),
                   'Mana {0} - Critical {1} %'.format(longest_number, critical_text)]
for label in ('Strength ', ' - Dexterity ', ' - Life ', '\\nMana ', ' - Critical '):
    assert '"' + label + '"' in creature


def wrapped_lines(text, available):
    """Measure word wrapping with the shipped font, including a word wider than the available row."""
    lines, current = 1, ''
    for word in text.split():
        candidate = (current + ' ' + word).strip()
        if current and font.getlength(candidate) * font_factor > available:
            lines += 1
            current = word
        else:
            current = candidate
        assert font.getlength(word) * font_factor <= available, ('word overflows the profile', word, available)
    return lines


skin = ET.parse(repo / 'gui/ODSkin.imageset').getroot()
side = float(skin.find("Image[@name='WindowLeftEdge']").get('width')) / 4.0
# Below the title bar the frame has no top edge; only the bottom edge reduces the client height.
border = float(skin.find("Image[@name='WindowBottomEdge']").get('height')) / 4.0
title = 18.0 * 10.0 / 8.0 + 12.0
social_layout = (repo / 'gui/WindowSocial.layout').read_text()
social_size = re.search(r'Area" value="\{\{0.5,(-?\d+)\},\{0.5,(-?\d+)\},\{0.5,(\d+)\},\{0.5,(\d+)\}\}"', social_layout)
social_width = int(social_size[3]) - int(social_size[1])
social_height = int(social_size[4]) - int(social_size[2])
social = (repo / 'source/render/SocialWindow.cpp').read_text()
assert 'OwnPostsText' in page and 'OwnPostsText' not in social_layout
# The book shows the shared page without portrait, name, attributes and item slots (they have their own places in the
# book) and lists the recent posts in its own column; the rows of the compact page start at the top.
hidden = social[social.index('const char* const hidden[]'):]
hidden = hidden[:hidden.index('};')]
for name in ('Portrait', 'NameText', 'AttributesText', 'EquipmentText', 'EquipmentRow', 'OwnPostsText'):
    assert '"%s"' % name in hidden, name
assert 'page->getChild("PostThumb" + std::to_string(rows))' in social and '(rows < MAX_OWN_POSTS)' in social
assert social.index('const char* const hidden[]') < social.index('creature->fillProfilePage(mProfilePage)')
assert 'const bool compact = !page->getChild("Portrait")->isVisible();' in profile_layout
assert 'float y = compact ? PROFILE_ROW_GAP : std::max(PROFILE_FLOW_TOP, 34.0f + equipmentHeight + PROFILE_ROW_GAP);' in profile_layout
import xml.etree.ElementTree as ElementTree
social_root = ElementTree.fromstring(social_layout).find('Window')
profile_page = social_root.find("Window[@name='ProfilePage']")
holder_area = [float(v) for v in re.findall(r'\{(-?[0-9.]+),0\}', profile_page.find(
    "Window[@name='SocialHolder']/Property[@name='Area']").get('value'))]
page_area = [float(v) for v in re.findall(r'\{(-?[0-9.]+),0\}', profile_page.find("Property[@name='Area']").get('value'))]
holder_width_fraction = holder_area[2] - holder_area[0]
holder_height_fraction = (holder_area[3] - holder_area[1]) * (page_area[3] - page_area[1])
assert 'y = layoutProfileTextRow(page->getChild("OwnPostsText"), y, scale)' in profile_layout
assert profile_layout.index('page->getChild("OwnPostsText")') > profile_layout.index('textRowsAfter[i]')
assert 'mProfilePage->setUserString("ProfileCreature", mSelectedCreature)' in social
assert 'setScrollPosition(0)' in social, 'a newly selected creature must open on the essential information'
scale_body = gui[gui.index('void Gui::applyScale('):gui.index('bool Gui::isScreenSizedContainer')]
assert 'layoutCreatureProfilePage(page)' in scale_body, 'profiles must reflow after UI or resolution changes'
assert scale_body.index('updateResourceScaling(displaySize)') < scale_body.index('layoutCreatureProfilePage(page)')
# The health and experience row is one label line high (at least PROFILE_BAR_ROW_MIN_HEIGHT) and followed by
# PROFILE_BAR_ROW_GAP, so the bars stay clear of the handle line (owner decision 830, check_dungeonbook_profile_overlap.py)
bar_row_min = float(re.search(r'PROFILE_BAR_ROW_MIN_HEIGHT = ([0-9.]+)f;', gui)[1])
bar_row_gap = float(re.search(r'PROFILE_BAR_ROW_GAP = ([0-9.]+)f;', gui)[1])
assert 'y += barRowHeight + PROFILE_BAR_ROW_GAP;' in profile_layout and 'y += 24.0f;' not in profile_layout
bar_row = max(bar_row_min, line_height + 4) + bar_row_gap

for screen_width, screen_height in ((640, 480), (1024, 768), (1920, 1200), (7680, 4320)):
    for percent in range(80, 121):
        scale = min(screen_width / 1024.0, screen_height / 768.0) * percent / 100.0
        # The book is the only window that shows the page: compact, health and experience bars first, then the social
        # rows, all reachable by scrolling
        fit = min(1.0, screen_width / (social_width * scale), screen_height / (social_height * scale))
        viewport = (social_height * fit - title - border) * holder_height_fraction
        page_width = (social_width * fit - 2 * side) * holder_width_fraction
        assert page_width - 48 >= 200, ('the social rows of the book are too narrow', page_width)
        core_bottom = 4 + bar_row
        assert core_bottom <= viewport
        rows_bottom = core_bottom
        for lines in (1, 1, 1, 1, 1, 2, 8, 4, 3, 3, 2, 2, 4, 4, 6):
            top = rows_bottom + 4
            rows_bottom = top + lines * line_height + 4
            assert lines * line_height + 8 <= viewport, 'a single row is higher than the book viewport'
            maximum = max(0.0, rows_bottom - viewport)
            offset = min(top, maximum)
            assert top - offset >= 0 and rows_bottom - offset <= viewport + 1e-6
assert 'Unspecified' not in (repo / 'source/social/SocialGenerator.cpp').read_text()
assert '"@" + getName()' not in creature, 'the handle must not be the internal name'
assert 'setText(getName() + " (" + getDefinition()->getClassName() + ")")' not in creature
game = (repo / 'source/modes/GameMode.cpp').read_text()
pick = game[game.index('void GameMode::openDungeonbookUnderPointer'):game.index('bool GameMode::mousePressed')]
assert 'findWorldPositionFromMouse' not in pick, 'the middle click must pick along the pointer ray'
assert 'openDungeonbookOnCreature(closestCreature)' in pick, 'the middle click opens the Dungeonbook on the creature'
assert 'getCameraToViewportRay' in pick
print('ok')
