"""Room packages for the check scripts, the tools and the packaging scripts.

Ten rooms take their assets (meshes, material scripts, textures, particle scripts, sounds) from a room package of the
private content repository instead of the public tree; their code stays in the public game. A room package is a folder
with a Package.cfg that names its room in a line "Room=<room name>"; inside the package the assets lie at the same
relative paths as in the public tree (models/, materials/scripts/, materials/textures/, particles/, sounds/). The game
(source/rooms/RoomPackages.cpp) searches them in the same folders as the wing packages of the campaign: the subfolders
of levels/campaign/ and of the content folder (scripts/campaign_packages.py: MOREYA_CONTENT_DIR, else the packages/
folder of a Moreya-Content checkout next to this repository). A packaged room whose package is missing is not
available in the game.

Checks that read a room asset use asset(): it returns the file of the public tree when it is there, else the file of
the room package when the content is present, else None; with None a check checks only the code side. This module
holds no room content.
"""
import re
from pathlib import Path

import campaign_packages

DEFINITION_FILE = campaign_packages.DEFINITION_FILE
ROOM_KEY = 'Room'
#: The packaged rooms: (room name of Package.cfg, package folder of the content repository, room type number), in room
#: type order; fixed for this branch, the same table as PACKAGED_ROOMS in source/rooms/RoomPackages.cpp
ROOMS = (
    ('GuardRoom', 'room-guard-room', 17),
    ('Temple', 'room-temple', 18),
    ('Toilet', 'room-toilet', 19),
    ('Merchant', 'room-merchant', 20),
    ('HerbGarden', 'room-herb-garden', 21),
    ('AlchemyLab', 'room-alchemy-lab', 22),
    ('Tavern', 'room-tavern', 23),
    ('Infirmary', 'room-infirmary', 24),
    ('GhostRoom', 'room-ghost-room', 25),
    ('Spa', 'room-spa', 26),
)
ROOM_NAMES = tuple(room[0] for room in ROOMS)


#: The files of every room package besides its Package.cfg, at their relative paths, fixed for this branch (the inventory
#: of the content repository, docs/ROOM-PACKAGES.md, gives the reasons); 319 files
PACKAGED_ASSETS = {
    'GuardRoom': (),
    'Temple': (
        'sounds/Spatial/Rooms/Temple/Gong/Gong01.ogg',
    ),
    'Toilet': (
        'materials/scripts/ToiletFloor.material', 'materials/scripts/ToiletSeat.material',
        'materials/textures/Toilet0000.png', 'materials/textures/Toilet0000Normal.png',
        'materials/textures/Toilet0001.png', 'materials/textures/Toilet0001Normal.png',
        'materials/textures/Toilet0010.png', 'materials/textures/Toilet0010Normal.png',
        'materials/textures/Toilet0011.png', 'materials/textures/Toilet0011Normal.png',
        'materials/textures/Toilet0100.png', 'materials/textures/Toilet0100Normal.png',
        'materials/textures/Toilet0101.png', 'materials/textures/Toilet0101Normal.png',
        'materials/textures/Toilet0110.png', 'materials/textures/Toilet0110Normal.png',
        'materials/textures/Toilet0111.png', 'materials/textures/Toilet0111Normal.png',
        'materials/textures/Toilet1000.png', 'materials/textures/Toilet1000Normal.png',
        'materials/textures/Toilet1001.png', 'materials/textures/Toilet1001Normal.png',
        'materials/textures/Toilet1010.png', 'materials/textures/Toilet1010Normal.png',
        'materials/textures/Toilet1011.png', 'materials/textures/Toilet1011Normal.png',
        'materials/textures/Toilet1100.png', 'materials/textures/Toilet1100Normal.png',
        'materials/textures/Toilet1101.png', 'materials/textures/Toilet1101Normal.png',
        'materials/textures/Toilet1110.png', 'materials/textures/Toilet1110Normal.png',
        'materials/textures/Toilet1111.png', 'materials/textures/Toilet1111Normal.png',
        'materials/textures/ToiletSeat.png', 'models/ToiletSeat.mesh',
        'sounds/Spatial/Rooms/Toilet/Drip/FxToiletDrip01.ogg', 'sounds/Spatial/Rooms/Toilet/Flush/FxToiletFlush01.ogg',
    ),
    'Merchant': (
        'materials/scripts/MerchantApproved.material', 'materials/textures/MerchantBrassApprovedColor.png',
        'materials/textures/MerchantBrassApprovedNormal.png', 'materials/textures/MerchantCloakApprovedColor.png',
        'materials/textures/MerchantCloakApprovedNormal.png', 'materials/textures/MerchantDetailsApprovedColor.png',
        'materials/textures/MerchantDetailsApprovedNormal.png', 'materials/textures/MerchantFloor.png',
        'materials/textures/MerchantFloorNormal.png', 'materials/textures/MerchantGoldApprovedColor.png',
        'materials/textures/MerchantGoldApprovedNormal.png', 'materials/textures/MerchantHairApprovedColor.png',
        'materials/textures/MerchantHairApprovedNormal.png', 'materials/textures/MerchantHideApprovedColor.png',
        'materials/textures/MerchantHideApprovedNormal.png', 'materials/textures/MerchantHoodApprovedColor.png',
        'materials/textures/MerchantHoodApprovedNormal.png', 'materials/textures/MerchantLantern.png',
        'materials/textures/MerchantLeatherApprovedColor.png', 'materials/textures/MerchantLeatherApprovedNormal.png',
        'materials/textures/MerchantLinenApprovedColor.png', 'materials/textures/MerchantLinenApprovedNormal.png',
        'materials/textures/MerchantRobeApprovedColor.png', 'materials/textures/MerchantRobeApprovedNormal.png',
        'materials/textures/MerchantTableCloth.png', 'materials/textures/MerchantTableWood.png',
        'materials/textures/MerchantWares.png', 'models/Merchant.mesh', 'models/Merchant.skeleton',
        'models/MerchantShelf.mesh', 'models/SalesTable.mesh', 'sounds/Spatial/Rooms/Merchant/Deal/FxDeal01.ogg',
        'sounds/Spatial/Rooms/Merchant/Giggle/FxGiggle01.ogg', 'sounds/Spatial/Rooms/Merchant/Haggle/FxHaggle01.ogg',
    ),
    'HerbGarden': (
        'materials/textures/HerbGardenFloor.png', 'materials/textures/HerbGardenFloorNormal.png',
        'models/BloodrootRipe.mesh', 'models/BloodrootSapling.mesh', 'models/BloodrootSprout.mesh',
        'models/HerbBed.mesh', 'models/HerbBundle.mesh', 'models/IronfernRipe.mesh', 'models/IronfernSapling.mesh',
        'models/IronfernSprout.mesh', 'models/MoonlilyRipe.mesh', 'models/MoonlilySapling.mesh',
        'models/MoonlilySprout.mesh', 'models/MushroomLamp.mesh', 'models/SunthornRipe.mesh',
        'models/SunthornSapling.mesh', 'models/SunthornSprout.mesh', 'models/WaterTrough.mesh',
        'sounds/Spatial/Rooms/HerbGarden/Drip/FxDrip01.ogg', 'sounds/Spatial/Rooms/HerbGarden/Hum/FxHum01.ogg',
        'sounds/Spatial/Rooms/HerbGarden/Rustle/FxRustle01.ogg',
    ),
    'AlchemyLab': (
        'materials/textures/AlchemyLabFloor.png', 'materials/textures/AlchemyLabFloorNormal.png',
        'models/Cauldron.mesh', 'models/Cauldron.skeleton', 'models/StillShelf.mesh',
        'sounds/Spatial/Rooms/AlchemyLab/Bang/FxBang01.ogg', 'sounds/Spatial/Rooms/AlchemyLab/Bubble/FxBubble01.ogg',
        'sounds/Spatial/Rooms/AlchemyLab/Hiss/FxHiss01.ogg',
    ),
    'Tavern': (
        'materials/scripts/TavernEffects.material', 'materials/scripts/TavernFloor.material',
        'materials/scripts/TavernWall.material', 'materials/textures/tavern/DuelBird.png',
        'materials/textures/tavern/Tavern0000.png', 'materials/textures/tavern/Tavern0000Normal.png',
        'materials/textures/tavern/Tavern0001.png', 'materials/textures/tavern/Tavern0001Normal.png',
        'materials/textures/tavern/Tavern0010.png', 'materials/textures/tavern/Tavern0010Normal.png',
        'materials/textures/tavern/Tavern0011.png', 'materials/textures/tavern/Tavern0011Normal.png',
        'materials/textures/tavern/Tavern0100.png', 'materials/textures/tavern/Tavern0100Normal.png',
        'materials/textures/tavern/Tavern0101.png', 'materials/textures/tavern/Tavern0101Normal.png',
        'materials/textures/tavern/Tavern0110.png', 'materials/textures/tavern/Tavern0110Normal.png',
        'materials/textures/tavern/Tavern0111.png', 'materials/textures/tavern/Tavern0111Normal.png',
        'materials/textures/tavern/Tavern1000.png', 'materials/textures/tavern/Tavern1000Normal.png',
        'materials/textures/tavern/Tavern1001.png', 'materials/textures/tavern/Tavern1001Normal.png',
        'materials/textures/tavern/Tavern1010.png', 'materials/textures/tavern/Tavern1010Normal.png',
        'materials/textures/tavern/Tavern1011.png', 'materials/textures/tavern/Tavern1011Normal.png',
        'materials/textures/tavern/Tavern1100.png', 'materials/textures/tavern/Tavern1100Normal.png',
        'materials/textures/tavern/Tavern1101.png', 'materials/textures/tavern/Tavern1101Normal.png',
        'materials/textures/tavern/Tavern1110.png', 'materials/textures/tavern/Tavern1110Normal.png',
        'materials/textures/tavern/Tavern1111.png', 'materials/textures/tavern/Tavern1111Normal.png',
        'materials/textures/tavern/TavernBrass.png', 'materials/textures/tavern/TavernCloth.png',
        'materials/textures/tavern/TavernClothApprovedColor.png',
        'materials/textures/tavern/TavernClothApprovedNormal.png', 'materials/textures/tavern/TavernCounterWood.png',
        'materials/textures/tavern/TavernCounterWoodApprovedColor.png',
        'materials/textures/tavern/TavernCounterWoodApprovedNormal.png', 'materials/textures/tavern/TavernFloor.png',
        'materials/textures/tavern/TavernFloorNormal.png', 'materials/textures/tavern/TavernFoam.png',
        'materials/textures/tavern/TavernHood.png', 'materials/textures/tavern/TavernHoodApprovedColor.png',
        'materials/textures/tavern/TavernHoodApprovedNormal.png', 'materials/textures/tavern/TavernIron.png',
        'materials/textures/tavern/TavernIronNormal.png', 'materials/textures/tavern/TavernKegWood.png',
        'materials/textures/tavern/TavernKegWoodNormal.png', 'materials/textures/tavern/TavernRail.png',
        'materials/textures/tavern/TavernRailApprovedColor.png',
        'materials/textures/tavern/TavernRailApprovedNormal.png', 'materials/textures/tavern/TavernSign.png',
        'materials/textures/tavern/TavernSignApprovedColor.png',
        'materials/textures/tavern/TavernSignApprovedNormal.png', 'materials/textures/tavern/TavernSkin.png',
        'materials/textures/tavern/TavernSkinApprovedColor.png',
        'materials/textures/tavern/TavernSkinApprovedNormal.png', 'materials/textures/tavern/TavernStone.png',
        'materials/textures/tavern/TavernStoneNormal.png', 'materials/textures/tavern/TavernTableWood.png',
        'materials/textures/tavern/TavernTableWoodNormal.png', 'materials/textures/tavern/TavernWall.png',
        'materials/textures/tavern/TavernWallNormal.png', 'materials/textures/tavern/TavernWood.png',
        'materials/textures/tavern/TavernWoodNormal.png', 'models/Innkeeper.mesh', 'models/Innkeeper.skeleton',
        'models/TavernCounter.mesh', 'models/TavernKeg.mesh', 'models/TavernStool.mesh',
        'models/TavernTable.mesh', 'particles/Tavern.particle', 'sounds/Rooms/Tavern/Clink.ogg',
        'sounds/Rooms/Tavern/Murmur.ogg', 'sounds/Rooms/Tavern/Pour.ogg',
        'sounds/Spatial/Rooms/Tavern/Clink/Clink.ogg', 'sounds/Spatial/Rooms/Tavern/Murmur/Murmur.ogg',
        'sounds/Spatial/Rooms/Tavern/Pour/Pour.ogg',
    ),
    'Infirmary': (
        'materials/scripts/InfirmaryFloor.material', 'materials/scripts/InfirmaryObjects.material',
        'materials/textures/InfirmaryFloor.png', 'materials/textures/InfirmaryFloorNormal.png',
        'materials/textures/InfirmaryObjectBone.png', 'materials/textures/InfirmaryObjectBottle.png',
        'materials/textures/InfirmaryObjectCloth.png', 'materials/textures/InfirmaryObjectDark.png',
        'materials/textures/InfirmaryObjectFeather.png', 'materials/textures/InfirmaryObjectHerb.png',
        'materials/textures/InfirmaryObjectIron.png', 'materials/textures/InfirmaryObjectLeather.png',
        'materials/textures/InfirmaryObjectSkin.png', 'materials/textures/InfirmaryObjectStone.png',
        'materials/textures/InfirmaryObjectStraw.png', 'materials/textures/InfirmaryObjectWood.png',
        'models/HerbShelf.mesh', 'models/InfirmaryCotLarge.mesh', 'models/InfirmaryCotMedium.mesh',
        'models/InfirmaryCotSmall.mesh', 'models/InfirmaryShaman.mesh', 'models/InfirmaryShaman.skeleton',
        'models/InstrumentTable.mesh', 'models/MedicineCabinet.mesh', 'models/WashBasin.mesh',
        'particles/Infirmary.particle', 'sounds/Rooms/Infirmary/Admit.ogg', 'sounds/Rooms/Infirmary/Chant.ogg',
        'sounds/Rooms/Infirmary/Discharge.ogg', 'sounds/Rooms/Infirmary/Rattle.ogg',
        'sounds/Spatial/Rooms/Infirmary/Chant/Chant.ogg',
    ),
    'GhostRoom': (
        'materials/scripts/GhostRoomFloor.material', 'materials/textures/GhostApparatusGlow.png',
        'materials/textures/GhostBoxCase.png', 'materials/textures/GhostBoxHazard.png',
        'materials/textures/GhostBrass.png', 'materials/textures/GhostCauldronEctoGlint.png',
        'materials/textures/GhostCauldronEctoplasm.png', 'materials/textures/GhostGaugeFace.png',
        'materials/textures/GhostIron.png', 'materials/textures/GhostLamps_0.png',
        'materials/textures/GhostLamps_1.png', 'materials/textures/GhostLamps_2.png',
        'materials/textures/GhostLamps_3.png', 'materials/textures/GhostLamps_4.png',
        'materials/textures/GhostLamps_5.png', 'materials/textures/GhostLamps_6.png',
        'materials/textures/GhostLamps_7.png', 'materials/textures/GhostLeather.png',
        'materials/textures/GhostPackCanvas.png', 'materials/textures/GhostPackSteel.png',
        'materials/textures/GhostPressChain.png', 'materials/textures/GhostPressGlow_0.png',
        'materials/textures/GhostPressGlow_1.png', 'materials/textures/GhostPressGlow_2.png',
        'materials/textures/GhostPressGlow_3.png', 'materials/textures/GhostPressIron.png',
        'materials/textures/GhostPressPages.png', 'materials/textures/GhostPressRune.png',
        'materials/textures/GhostPressStain.png', 'materials/textures/GhostRoomFloor.png',
        'materials/textures/GhostRoomFloorNormal.png', 'materials/textures/GhostStone.png',
        'materials/textures/ManaStillCoilCopper.png', 'materials/textures/ManaStillCopper.png',
        'materials/textures/ManaStillEmbers_0.png', 'materials/textures/ManaStillEmbers_1.png',
        'materials/textures/ManaStillEmbers_2.png', 'materials/textures/ManaStillEmbers_3.png',
        'materials/textures/ManaStillEmbers_4.png', 'materials/textures/ManaStillEmbers_5.png',
        'materials/textures/ManaStillFlow.png', 'materials/textures/ManaStillGlowRamp.png',
        'materials/textures/ManaStillPuff.png', 'materials/textures/ManaStillWeb.png',
        'materials/textures/SoulForgeFire_0.png', 'materials/textures/SoulForgeFire_1.png',
        'materials/textures/SoulForgeFire_2.png', 'materials/textures/SoulForgeFire_3.png',
        'materials/textures/SoulForgeIron.png', 'materials/textures/SoulForgeSpark.png',
        'materials/textures/SoulForgeSteel.png', 'materials/textures/SoulForgeStone.png', 'models/CrystalBowl.mesh',
        'models/GhostBackpack.mesh', 'models/GhostBell.mesh', 'models/GhostBox.mesh', 'models/GhostBox.skeleton',
        'models/GhostCaptureGun.mesh', 'models/GhostCauldron.mesh', 'models/GhostCauldron.skeleton',
        'models/GhostCauldronFill.mesh', 'models/GhostHook.mesh', 'models/GhostHookEmpty.mesh',
        'models/GhostHoseCoupling.mesh', 'models/GhostPress.mesh', 'models/GhostPress.skeleton',
        'models/GhostRack.mesh', 'models/GhostWallGauges.mesh', 'models/GhostWallGauges.skeleton',
        'models/ManaStill.mesh', 'models/ManaStill.skeleton', 'models/SoulForge.mesh', 'models/SoulForge.skeleton',
        'sounds/Spatial/Rooms/GhostRoom/Beam/Beam.ogg', 'sounds/Spatial/Rooms/GhostRoom/Bell/Bell.ogg',
        'sounds/Spatial/Rooms/GhostRoom/BoxSnap/BoxSnap.ogg',
        'sounds/Spatial/Rooms/GhostRoom/CrystalRing/CrystalRing.ogg', 'sounds/Spatial/Rooms/GhostRoom/Hum/Hum.ogg',
        'sounds/Spatial/Rooms/GhostRoom/PressHiss/PressHiss.ogg',
    ),
    'Spa': (
        'materials/scripts/Spa.material', 'materials/scripts/SpaFloor.material',
        'materials/textures/SpaAttendantFace.png', 'materials/textures/SpaAttendantHair.png',
        'materials/textures/SpaAttendantSkin.png', 'materials/textures/SpaAttendantSuit.png',
        'materials/textures/SpaAttendantTowel.png', 'materials/textures/SpaChairWood.png',
        'materials/textures/SpaFloor.png', 'materials/textures/SpaFloorNormal.png',
        'materials/textures/SpaLifebuoy.png', 'materials/textures/SpaMetalWorn.png', 'materials/textures/SpaMud.png',
        'materials/textures/SpaMudBubble.png', 'models/PoolAttendant.mesh', 'models/PoolAttendant.skeleton',
        'models/SpaChair.mesh', 'models/SpaMudPool.mesh', 'models/SpaPoolRim.mesh', 'models/SpaSpringboard.mesh',
        'particles/Spa.particle', 'sounds/Spatial/Rooms/Spa/Bubble/Bubble.ogg',
        'sounds/Spatial/Rooms/Spa/Splash/Splash.ogg', 'sounds/Spatial/Rooms/Spa/Whistle/Whistle.ogg',
    ),
}
#: The Ogre materials and particle systems that the scripts of a room package define, fixed for this branch: a check
#: that resolves names does not find them without the package
PACKAGED_MATERIALS = {
    'GhostRoom': ('GhostRoomFloor',),
    'Infirmary': ('InfirmaryFloor', 'InfirmaryObjectWood', 'InfirmaryObjectStone', 'InfirmaryObjectCloth',
                  'InfirmaryObjectIron', 'InfirmaryObjectStraw', 'InfirmaryObjectBone', 'InfirmaryObjectHerb',
                  'InfirmaryObjectBottle', 'InfirmaryObjectSkin', 'InfirmaryObjectLeather', 'InfirmaryObjectFeather',
                  'InfirmaryObjectDark'),
    'Merchant': ('MerchantApprovedRobe', 'MerchantApprovedCloak', 'MerchantApprovedLinen', 'MerchantApprovedLeather',
                 'MerchantApprovedBrass', 'MerchantApprovedDetails', 'MerchantApprovedHair', 'MerchantApprovedHood',
                 'MerchantApprovedHide', 'MerchantApprovedGold', 'MerchantApprovedHideHand',
                 'MerchantApprovedDetailsHand', 'MerchantApprovedGoldHand'),
    'Spa': ('SpaMud', 'SpaMudBubble', 'SpaStone', 'SpaWood', 'SpaIron', 'SpaChairWood', 'SpaIronWorn', 'SpaLifebuoyRed',
            'SpaLifebuoyWhite', 'SpaSkin', 'SpaAttendantFace', 'SpaSuit', 'SpaLinen', 'SpaHair', 'SpaBodyHair', 'SpaBlood',
            'SpaWhistle', 'SpaEyes', 'SpaLavaGlow', 'SpaAttendantSclera', 'SpaFloor'),
    'Tavern': ('TavernDuelBirds', 'TavernFloor', 'Tavern0000', 'Tavern0001', 'Tavern0010', 'Tavern0011', 'Tavern0100',
               'Tavern0101', 'Tavern0110', 'Tavern0111', 'Tavern1000', 'Tavern1001', 'Tavern1010', 'Tavern1011',
               'Tavern1100', 'Tavern1101', 'Tavern1110', 'Tavern1111', 'TavernWall'),
    'Toilet': ('Toilet0000', 'Toilet0001', 'Toilet0010', 'Toilet0011', 'Toilet0100', 'Toilet0101', 'Toilet0110',
               'Toilet0111', 'Toilet1000', 'Toilet1001', 'Toilet1010', 'Toilet1011', 'Toilet1100', 'Toilet1101',
               'Toilet1110', 'Toilet1111', 'ToiletSeat'),
}
PACKAGED_PARTICLES = {
    'Infirmary': ('InfirmaryHealGlow',),
    'Spa': ('SpaSteam', 'SpaMudBubbles', 'SpaMudSplash'),
    'Tavern': ('TavernSmoke', 'DuelBirds'),
}
#: The room of every packaged material and particle system
NAME_ROOMS = {name: room for table in (PACKAGED_MATERIALS, PACKAGED_PARTICLES) for room, names in table.items()
              for name in names}
#: The room of every packaged asset
ASSET_ROOMS = {relative: room for room, files in PACKAGED_ASSETS.items() for relative in files}


# The packaged room named by a definition text (the first line "Room=<name>" with a packaged room), or None.
def parse_definition(text):
    for line in text.replace('\r', '').split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        match = re.fullmatch(r'Room\s*=\s*(\S+)', line)
        if match and match.group(1) in ROOM_NAMES:
            return match.group(1)
    return None


# Package folders below a folder, in name order, like the game.
def _package_dirs(folder):
    if folder is None or not Path(folder).is_dir():
        return []
    return sorted(path for path in Path(folder).iterdir() if (path / DEFINITION_FILE).is_file())


#: Found packages by (repository, content folder, with_content), so repeated lookups do not scan the folders again
_CACHE = {}


# The found room packages as {room name: folder}, like the game: levels/campaign/ of the repository first, then the
# content folder; the first package of a room wins.
def packages(repo, with_content=True):
    repo = Path(repo)
    content = campaign_packages.content_folder(repo) if with_content else None
    key = (str(repo.resolve()), str(content), with_content)
    if key in _CACHE:
        return dict(_CACHE[key])
    folders = [repo / campaign_packages.PUBLIC_FOLDER, content]
    found = {}
    for folder in folders:
        for path in _package_dirs(folder):
            room = parse_definition((path / DEFINITION_FILE).read_text(encoding='utf-8'))
            if room is not None and room not in found:
                found[room] = path
    _CACHE[key] = dict(found)
    return found


# The package folder of a room, or None when its package is missing.
def package(repo, room):
    return packages(repo).get(room)


# True when the room packages of the content are present (at least one room package was found).
def has_content(repo):
    return bool(packages(repo))


# The file of a room asset: the public file when the public tree has it, else the file of a found room package (of the
# given room, or of any room), else None. Without a given room a file that moved into a content package
# (scripts/content_packages.py, for example a mesh of core-models that a room uses) is found there as well.
def asset(repo, relative, room=None):
    repo = Path(repo)
    relative = str(relative).replace('\\', '/')
    public = repo / relative
    if public.exists():
        return public
    found = packages(repo)
    folders = [found[room]] if room in found else ([] if room is not None else list(found.values()))
    for folder in folders:
        candidate = folder / relative
        if candidate.exists():
            return candidate
    if room is None:
        import content_packages
        for folder in content_packages.packages(repo).values():
            candidate = folder / relative
            if candidate.exists():
                return candidate
    return None


# The file of a relative path: the room asset of a present package when the public tree no longer has it, else the
# path below the repository.
def resolve(repo, relative):
    return asset(repo, relative) or (Path(repo) / relative)


# True when the relative path names a file of a room package (PACKAGED_ASSETS).
def is_packaged(relative):
    return str(relative).replace('\\', '/') in ASSET_ROOMS


# True when the relative path names a file of a room package whose package is not present: a check then checks only
# the code side of that asset.
def is_missing_packaged(repo, relative):
    relative = str(relative).replace('\\', '/')
    return relative in ASSET_ROOMS and ASSET_ROOMS[relative] not in packages(repo)


# True when the name is a material or particle system of a room package whose package is not present.
def is_missing_packaged_name(repo, name):
    return name in NAME_ROOMS and NAME_ROOMS[name] not in packages(repo)


# Every present room package folder (the roots below which its assets lie at their relative paths).
def package_roots(repo):
    return list(packages(repo).values())


# True when the package of the room is present.
def has_room(repo, room):
    return room in packages(repo)


# The text of a room asset, or None when it is not present (see asset()).
def read_text(repo, relative, room=None, encoding='utf-8'):
    path = asset(repo, relative, room)
    return None if path is None else path.read_text(encoding=encoding, errors='replace')


# The bytes of a room asset, or None when it is not present (see asset()).
def read_bytes(repo, relative, room=None):
    path = asset(repo, relative, room)
    return None if path is None else path.read_bytes()


# The public CREDITS, followed by the CREDITS of the content repository when room packages are present: the rows of the
# moved room assets stand there, with the same relative paths.
def credits_text(repo):
    repo = Path(repo)
    text = (repo / 'CREDITS').read_text(encoding='utf-8', errors='replace')
    content = campaign_packages.content_repository(repo)
    if has_content(repo) and content is not None and (content / 'CREDITS').is_file():
        text += '\n' + (content / 'CREDITS').read_text(encoding='utf-8', errors='replace')
    return text


# The rows of the CREDITS of the content repository (empty without room packages): the rows of the moved room assets,
# under the licence of the content repository ("All rights reserved") for the own assets.
def content_credit_rows(repo):
    repo = Path(repo)
    content = campaign_packages.content_repository(repo)
    if not has_content(repo) or content is None or not (content / 'CREDITS').is_file():
        return set()
    return set((content / 'CREDITS').read_text(encoding='utf-8', errors='replace').splitlines())


# True when a CREDITS row states the licence: the given licence of the public repository, or "All rights reserved" for a
# row of the content repository (the licence of the room packages for the own assets).
def licence_ok(repo, row, public_licence):
    if public_licence in row:
        return True
    return 'All rights reserved' in row and row in content_credit_rows(repo)


# The files of a glob pattern below a relative folder of the public tree, of every present room package and of every
# present content package (scripts/content_packages.py; the game loads the scripts and textures of all alike).
def glob_files(repo, folder, pattern):
    import content_packages
    repo = Path(repo)
    roots = []
    for root in [repo] + package_roots(repo) + list(content_packages.packages(repo).values()):
        if root not in roots:
            roots.append(root)   # a room package that is also a content package is read once
    return [path for root in roots for path in sorted((root / folder).glob(pattern))]


# Every file below a relative folder of the public tree and of the found room packages, as {relative path: file}.
def files_below(repo, relative):
    repo = Path(repo)
    result = {}
    roots = [repo] + list(packages(repo).values())
    for root in roots:
        base = root / relative
        if not base.is_dir():
            continue
        for path in base.rglob('*'):
            if path.is_file():
                result.setdefault(path.relative_to(root).as_posix(), path)
    return result
