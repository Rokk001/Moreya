from hashlib import sha256
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import content_packages  # noqa: E402

CHECK = 'check_room_icons_i1'
MAPPINGS = {
    'AlchemyLabButton': ('alchemy-lab.png', 'RoomCentreIconAlchemyLab/Icon'),
    'ArenaButton': ('arena.png', 'RoomCentreIconArena/Icon'),
    'CasinoButton': ('casino.png', 'RoomCentreIconCasino/Icon'),
    'CryptButton': ('crypt.png', 'RoomCentreIconCrypt/Icon'),
    'DormitoryButton': ('dormitory.png', 'RoomCentreIconDormitory/Icon'),
    'GhostRoomButton': ('ghost-room.png', 'RoomCentreIconGhostRoom/Icon'),
    'GuardRoomButton': ('guard-room.png', 'RoomCentreIconGuardRoom/Icon'),
    'HatcheryButton': ('hatchery.png', 'RoomCentreIconHatchery/Icon'),
    'HerbGardenButton': ('herb-garden.png', 'RoomCentreIconHerbGarden/Icon'),
    'InfirmaryButton': ('infirmary.png', 'RoomCentreIconInfirmary/Icon'),
    'LibraryButton': ('library.png', 'RoomCentreIconLibrary/Icon'),
    'MerchantButton': ('merchant.png', 'RoomCentreIconMerchant/Icon'),
    'PrayerTempleButton': ('prayer-temple.png', 'RoomCentreIconPrayerTemple/Icon'),
    'PrisonButton': ('prison.png', 'RoomCentreIconPrison/Icon'),
    'SpaButton': ('spa.png', 'RoomCentreIconSpa/Icon'),
    'StoneBridgeButton': ('stone-bridge.png', 'RoomCentreIconStoneBridge/Icon'),
    'TavernButton': ('tavern.png', 'RoomCentreIconTavern/Icon'),
    'TempleButton': ('temple.png', 'RoomCentreIconTemple/Icon'),
    'ToiletButton': ('toilet.png', 'RoomCentreIconToilet/Icon'),
    'TortureButton': ('torture-chamber.png', 'RoomCentreIconTortureChamber/Icon'),
    'TrainingHallButton': ('training-hall.png', 'RoomCentreIconTrainingHall/Icon'),
    'TreasuryButton': ('treasury.png', 'RoomCentreIconTreasury/Icon'),
    'WoodenBridgeButton': ('wooden-bridge.png', 'RoomCentreIconWoodenBridge/Icon'),
    'WorkshopButton': ('workshop.png', 'RoomCentreIconWorkshop/Icon'),
}
BUILD_BAR = (
    'DormitoryButton', 'ToiletButton', 'HatcheryButton', 'TavernButton', 'SpaButton', 'LibraryButton',
    'TrainingHallButton', 'TreasuryButton', 'WorkshopButton', 'CasinoButton', 'PrisonButton',
    'WoodenBridgeButton', 'TortureButton', 'StoneBridgeButton', 'CryptButton', 'GhostRoomButton',
    'ArenaButton', 'GuardRoomButton', 'InfirmaryButton', 'PrayerTempleButton', 'MerchantButton',
    'HerbGardenButton', 'AlchemyLabButton',
)
ROOM_CENTRE = (
    'GhostRoomButton', 'MerchantButton', 'TavernButton', 'SpaButton',
    'InfirmaryButton', 'AlchemyLabButton', 'CasinoButton', 'WorkshopButton',
)


def check_mappings():
    """Check the 24 icon files, their imagesets and that each PNG resolves in one GUI folder only. The icons and the
    imagesets are game data: they are read from the public tree or from the content packages (the game registers each
    [GUI] folder of the public tree and of every content package); without the content this part is not checked."""
    icon_folders = content_packages.data_folders(ROOT, 'gui/RoomCentreIcons')
    icon_paths = content_packages.data_glob(ROOT, 'gui/RoomCentreIcons', '*.png')
    if not icon_paths and not content_packages.has_content(ROOT):
        content_packages.unchecked(CHECK, ['gui/RoomCentreIcons', 'the room icon imagesets'])
        return False
    icon_names = {path.name for path in icon_paths}
    assert icon_names == {value[0] for value in MAPPINGS.values()}, 'all 24 chosen A1 files are mapped once'

    # The game registers each [GUI] folder non-recursively, so an imagefile must be a bare name in exactly one of them.
    gui_section = (ROOT / 'cmake/config/resources.cfg.in').read_text(encoding='utf-8').split('[GUI]', 1)[1].split('[', 1)[0]
    gui_names = [line.split('=', 1)[1].strip() for line in gui_section.splitlines() if line.startswith('FileSystem=')]
    assert 'gui/RoomCentreIcons' in gui_names, 'icon folder is a GUI resource location'
    # Every [GUI] location of the public tree and the same folder of every content package
    gui_folders = [folder for name in gui_names for folder in content_packages.data_folders(ROOT, name)]
    scheme = ET.parse(content_packages.resolve(ROOT, 'gui/ODSkin.scheme')).getroot()
    imagesets = {node.get('name'): node.get('filename') for node in scheme.findall('Imageset')}
    distinct_pixels = set()
    for button, (filename, image_ref) in MAPPINGS.items():
        imageset_name, image_name = image_ref.split('/', 1)
        assert imageset_name in imagesets, button + ': imageset registered in ODSkin.scheme'
        imageset_path = content_packages.resolve(ROOT, 'gui/' + imagesets[imageset_name])
        imageset = ET.parse(imageset_path).getroot()
        assert imageset.get('imagefile') == filename, button + ': selected A1 PNG is the source'
        resolving = [folder for folder in gui_folders if (folder / filename).is_file()]
        assert len(resolving) == 1 and resolving[0] in icon_folders, button + ': PNG resolves only in the icon folder'
        image = imageset.find("Image[@name='" + image_name + "']")
        assert image is not None, button + ': mapped CEGUI image exists'
        picture_path = resolving[0] / filename
        with Image.open(picture_path) as picture:
            picture.load()
            digest = sha256(picture.convert('RGBA').tobytes()).hexdigest()
            if button != 'TempleButton':
                assert digest not in distinct_pixels, button + ': distinct in-game icon pixels'
                distinct_pixels.add(digest)
        print('PASS mapping ' + button + ' -> ' + filename + ' -> ' + image_ref)
    assert len(distinct_pixels) == 23, '23 in-game build bar icons are pixel-distinct'
    return True


def main():
    """Check all 24 room icon mappings and the in-game/editor presentation points; without the content the icon files
    and their imagesets are named as not checked."""
    assert len(MAPPINGS) == 24, 'fixed inventory contains 24 room icons'
    mapped = check_mappings()

    gui_source = (ROOT / 'source' / 'render' / 'Gui.cpp').read_text(encoding='utf-8')
    arrange = re.search(r'void Gui::arrangeRoomButtons\(CEGUI::Window\* rooms\)(.*?)\n\}', gui_source, re.S)
    assert arrange is not None, 'in-game room build bar arrangement exists'
    arranged_buttons = [button for button in re.findall(r'"([A-Za-z]+Button)"', arrange.group(1))
        if button != 'DestroyRoomButton']
    assert arranged_buttons == list(BUILD_BAR), 'build bar contains exactly the 23 mapped room buttons'

    rooms = ET.parse(ROOT / 'gui' / 'WindowTabRooms.layout').getroot()
    room_buttons = {node.get('name'): node for node in rooms.iter('Window') if node.get('name') in MAPPINGS}
    assert len(room_buttons) == 24, 'all 23 build buttons and editor TempleButton exist'
    for button in BUILD_BAR:
        assert room_buttons[button].find("Property[@name='NormalImage']").get('value') == MAPPINGS[button][1], \
            button + ': in-game build bar uses the selected icon'
    assert room_buttons['TempleButton'].find("Property[@name='NormalImage']").get('value') == MAPPINGS['TempleButton'][1], \
        'editor TempleButton uses the selected temple icon'
    editor = (ROOT / 'source' / 'modes' / 'EditorMode.cpp').read_text(encoding='utf-8')
    assert 'getChild(Gui::BUTTON_TEMPLE)->show()' in editor, 'TempleButton is shown in the editor'

    research = ET.parse(ROOT / 'gui' / 'WindowSkillTree.layout').getroot()
    research_buttons = {node.get('name'): node for node in research.iter('Window') if node.get('name') in MAPPINGS}
    assert len(research_buttons) == 23, 'research tree contains all 23 in-game room buttons'
    for button in BUILD_BAR:
        assert research_buttons[button].find("Property[@name='ButtonImage']").get('value') == MAPPINGS[button][1], \
            button + ': research tree uses the selected icon'

    manager = (ROOT / 'source' / 'modes' / 'GameModeRoomManager.cpp').read_text(encoding='utf-8')
    icon_array = re.search(r'ROOM_ICONS\[\]\s*=\s*\{(.*?)\};', manager, re.S)
    assert icon_array is not None, 'room centre list icon mapping exists'
    centre_refs = re.findall(r'"([^"]+)"', icon_array.group(1))
    expected_refs = [MAPPINGS[button][1] for button in ROOM_CENTRE]
    assert centre_refs == expected_refs, 'room centre list uses the matching selected icon for all eight rows'
    refresh = re.search(r'void GameMode::refreshRoomManager\(\)(.*?)\n\}', manager, re.S)
    assert refresh is not None, 'room centre runtime refresh exists'
    runtime = refresh.group(1)
    assert 'row->setVisible(counts[index] > 0)' in runtime, 'runtime shows a row only when its room type is owned'
    assert 'if(counts[index] == 0)\n            continue;' in runtime, 'runtime skips unowned room types without shifting their icon index'
    assert 'row->getChild("Icon")->setProperty("Image", ROOM_ICONS[index])' in runtime, \
        'runtime assigns each visible row the icon at its fixed room type index'
    traps = (ROOT / 'gui' / 'WindowTabTraps.layout').read_text(encoding='utf-8')
    assert "image='" + MAPPINGS['WorkshopButton'][1] + "'" in traps, 'workshop room icon use in traps tab is replaced'

    if mapped:
        print('DONE mappings=24 build-bar=23 distinct=23 editor-temple=PASS room-centre=8')
    else:
        print('DONE mappings=not checked build-bar=23 editor-temple=PASS room-centre=8')
    return 0


if __name__ == '__main__':
    sys.exit(main())
