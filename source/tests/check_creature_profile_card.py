"""Check that the old creature card and the shared creature profile page are gone and that what they showed lives on.

The old creature card (gui/WindowCreatureProfile.layout, Creature::createStatsWindow) opened by a middle click is
removed: a middle click on a creature opens the Dungeonbook on it (check_creature_click_dungeonbook.py). The shared
profile page (gui/WindowCreatureProfilePage.layout, Creature::fillProfilePage, Gui::layoutCreatureProfilePage) was
deleted by the owner on 2026-11-18 once the Dungeonbook showed its own profile as book-variant-2 (plan INGAME-QS-11
K1, measured by check_dungeonbook_pages_b1.py). Checked here: both are gone, the item slots keep their slot symbols
(Creature::fillItemSlotWindows, used by the inventory page of the book), the handle is never the internal name and the
middle click picks along the pointer ray.
"""
from pathlib import Path
import xml.etree.ElementTree as ET

repo = Path(__file__).resolve().parents[2]
gui = (repo / 'source/render/Gui.cpp').read_text()
gui_header = (repo / 'source/render/Gui.h').read_text()
creature = (repo / 'source/entities/Creature.cpp').read_text()
creature_header = (repo / 'source/entities/Creature.h').read_text()
social_cpp = (repo / 'source/render/SocialWindow.cpp').read_text()

# The old creature card and the shared profile page are gone
assert not (repo / 'gui/WindowCreatureProfile.layout').exists(), 'the old creature card layout is removed'
assert not (repo / 'gui/WindowCreatureProfilePage.layout').exists(), 'the shared profile page is removed'
assert 'WindowCreatureProfile.layout' not in gui and 'createCreatureProfileWindow' not in gui, 'the card is still created'
for gone in ('createCreatureProfilePage', 'layoutCreatureProfilePage', 'layoutProfileTextRow', 'applyProfileScroll',
             'onProfileWheel', 'onProfileScrolled', 'mProfileBaseAreas', 'ProfileScrollbar'):
    assert gone not in gui and gone not in gui_header, gone + ' of the shared profile page is still there'
# No creature window of its own: no stats window, no tabs, no server statistics subscription from the creature
for gone in ('createStatsWindow', 'destroyStatsWindow', 'updateStatsWindow', 'mStatsWindow', 'ProfileTabClicked',
             'StatsTabClicked', 'BookTabClicked', 'showStatsPage', 'refreshProfilePage', 'createCreatureProfileWindow',
             'ClientNotificationType::askCreatureInfos', 'canDisplayStatsWindow', 'fillProfilePage'):
    assert gone not in creature and gone not in creature_header, gone + ' of the old creature pages is still there'
assert 'fillProfilePage(' not in social_cpp and 'createCreatureProfilePage(' not in social_cpp

# The item slots keep their painted slot symbols (the inventory page of the book has 13 of them)
slot_types = ET.parse(repo / 'gui/SlotTypes.imageset').getroot()
assert {image.attrib['name'] for image in slot_types.findall('Image')} == {'Head', 'Hand', 'Armour', 'Boots', 'Ring', 'Potion', 'Bag'}
book = ET.parse(repo / 'gui/WindowSocial.layout').getroot().find('Window')
inventory = book.find("Window[@name='InventoryPage']")
assert len([w for w in inventory.iter('Window') if w.get('name') == 'SlotType']) == 13
assert 'slotType->setVisible(item == nullptr)' in creature
assert '"Hand", "Hand", "Head", "Armour", "Boots", "Ring"' in creature
assert '"Potion", "Potion", "Potion", "Bag", "Bag", "Bag", "Bag"' in creature
assert 'Creature::fillItemSlotWindows(creature, slots, true)' in social_cpp
assert 'social/SocialProfileCache.h' in creature

# The profile texts: no unspecified values, the handle is never the internal name
assert 'Unspecified' not in (repo / 'source/social/SocialGenerator.cpp').read_text()
assert '"@" + getName()' not in creature, 'the handle must not be the internal name'
assert 'setText(getName() + " (" + getDefinition()->getClassName() + ")")' not in creature
assert 'std::string Creature::getProfileHandle(const social::CreatureProfile& profile)' in creature
assert 'Creature::getProfileHandle(profile)' in social_cpp

# The middle click opens the Dungeonbook on the creature under the pointer
game = (repo / 'source/modes/GameMode.cpp').read_text()
pick = game[game.index('void GameMode::openDungeonbookUnderPointer'):game.index('bool GameMode::mousePressed')]
assert 'findWorldPositionFromMouse' not in pick, 'the middle click must pick along the pointer ray'
assert 'openDungeonbookOnCreature(closestCreature)' in pick, 'the middle click opens the Dungeonbook on the creature'
assert 'getCameraToViewportRay' in pick
print('ok')
