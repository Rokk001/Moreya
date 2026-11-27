#!/usr/bin/env python3
# Static checks of the hatchery visuals and the rooster behaviour wiring (the decisions of the rooster are
# covered by the 00-HatcheryCycle unit test, the looks only show in the game).
# The chicken meshes, skeletons, materials and the production ambience table are content (hatchery room package and
# core content packages, found through scripts/content_packages.py) and their CREDITS rows stand in the CREDITS of the
# content repository; without the content the code side is checked and the asset part is named as not checked.
# config/rooms.cfg is a mixed table read with its own rows from the content (content_packages.read_text); without the
# content its keys are named as not checked, the absence of old keys is checked on its public rows.
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / 'scripts'))
import content_packages  # noqa: E402
import room_packages  # noqa: E402

#: The content files of the asset part
CONTENT_FILES = ('materials/scripts/ChickenHatchery.material', 'materials/scripts/ChickenBreeds.material',
                 'materials/scripts/ChickenNest.material', 'materials/textures/ChickenNest.png',
                 'models/ChickenEgg.mesh', 'models/ChickenEggCracked.mesh', 'models/ChickenChick.mesh',
                 'models/ChickenRooster.mesh', 'models/Chicken.skeleton', 'models/ChickenChick.skeleton',
                 'models/ChickenRooster.skeleton', 'models/ChickenCoopHouse.mesh',
                 'models/ChickenCoopHouse.skeleton', 'models/ChickenNest.mesh', 'models/ChickenCoop.mesh',
                 'config/roomAmbienceProduction.cfg')
missing_content = content_packages.unchecked('check_hatchery_visuals', [
    name for name in CONTENT_FILES if content_packages.data_file(root, name) is None])
#: True when every content file of the asset part is present
CONTENT = not missing_content


def model(name):
    """A file of models/ in the public tree or in a content or room package."""
    return content_packages.resolve(root, 'models/' + name)


chicken_h = (root / 'source/entities/ChickenEntity.h').read_text()
chicken = (root / 'source/entities/ChickenEntity.cpp').read_text()
room = (root / 'source/rooms/RoomHatchery.cpp').read_text()
render = (root / 'source/render/RenderManager.cpp').read_text()
looks = (root / 'source/render/RenderManagerChickens.cpp').read_text()
pose = (root / 'source/entities/ChickenPose.h').read_text()
#: True when the content packages are present (the own rows of config/rooms.cfg come from them)
TABLES = content_packages.has_content(root)
config = content_packages.read_text(root, 'config/rooms.cfg')
if not TABLES:
    content_packages.unchecked('check_hatchery_visuals', ['hatchery keys and values of config/rooms.cfg'])
cmake = (root / 'CMakeLists.txt').read_text()
# The public CREDITS plus the CREDITS of the content repository when the packages are present
credits = room_packages.credits_text(root)
materials = content_packages.read_text(root, 'materials/scripts/ChickenHatchery.material') if CONTENT else None


def body(text, start):
    i = text.index(start)
    return text[i:text.index('\n}\n', i)]


# The egg has a mesh of its own and the mesh follows the kind (also for the clients and old saves).
assert 'ChickenEgg' in chicken and 'getMeshNameForKind' in chicken_h
assert 'setMeshName(getMeshNameForKind(kind))' in body(chicken, 'void ChickenEntity::setKind(')
assert 'destroyMesh()' in body(chicken, 'void ChickenEntity::setKindFromServer')
assert 'rrChickenHatched' in body(chicken, 'void ChickenEntity::setKindFromServer')

# Poses reach the client as animation names and are turned into skeleton animations plus motion.
for name in ('strut', 'chase', 'flee', 'mount', 'cackle', 'perch', 'crow', 'guard', 'lay', 'wobble', 'emerge', 'scratch', 'flutter', 'protest'):
    assert 'static const std::string %s =' % name in pose, name
hook = body(render, 'void RenderManager::rrSetObjectAnimationState')
assert 'ChickenPose::isPose(animation)' in hook and 'rrSetChickenPose' in hook
assert hook.index('rrSetChickenPose') < hook.index('hasSkeleton')

# The server drives the behaviour from the hatchery upkeep.
upkeep = body(room, 'void RoomHatchery::doUpkeep')
for call in ('updateChickLine', 'updateRooster', 'updateNestTrips', 'ChickenPose::wobble'):
    assert call in upkeep, call
assert 'ChickenPose::lay' in body(room, 'void RoomHatchery::updateNestTrips')
coop_spawn = body(room, 'bool RoomHatchery::spawnFromCoop')
assert 'spawnAnimal(kind, Ogre::Vector3(inside.x, inside.y, 0.0f), settings)' in coop_spawn
assert 'animal->emergeFromCoop(door, freePosition)' in coop_spawn
assert 'clearSegment(obstacles, inside, door, true)' in coop_spawn
assert 'getX() + 1' in coop_spawn and 'clearSegment(obstacles' in coop_spawn
assert 'playPose(ChickenPose::emerge, 1)' in body(chicken, 'void ChickenEntity::emergeFromCoop')
assert 'setWalkPath(EntityAnimation::walk_anim' in body(chicken, 'void ChickenEntity::doUpkeep')
assert 'new ChickenEntity' not in upkeep

# Chicks follow, the rooster that is dropped outside runs back to a hatchery of his keeper.
chickUpkeep = body(chicken, 'void ChickenEntity::doUpkeep')
assert 'mFollowing' in chickUpkeep and 'runBackToHatchery' in chickUpkeep
assert 'RoomType::hatchery' in body(chicken, 'bool ChickenEntity::runBackToHatchery')
assert 'mOnRoof = false' in body(chicken, 'void ChickenEntity::pickup')

# The rooster is still never food and does not count for the capacity.
assert 'isFree() && (mKind == ChickenKind::hen)' in chicken_h

# Client: looks, procedural meshes and the coop decoration.
for name in ('rrCreateChickenLook', 'rrDestroyChickenLook', 'rrCreateCoopDecor', 'updateChickenLooks'):
    assert name in looks, name
assert 'updateChickenLooks' in render and 'rrCreateCoopDecor' in render
assert 'RenderManagerChickens.cpp' in cmake and 'HatcheryRooster.cpp' in cmake

# Values come from the config.
for key in ('HatcheryRoosterCrowMin', 'HatcheryRoosterCrowMax',
            'HatcheryRoosterChasePercent',
            'HatcheryRoosterGuardRadius', 'HatcheryCoopRoofHeight', 'HatcheryChickGap'):
    assert key in room, key
    if TABLES:
        assert key in config, key
for key in ('HatcheryChickScale', 'HatcheryRoosterScale'):
    assert key in looks, key
    if TABLES:
        assert key in config, key

# Every material the code asks for exists and the new assets have a credit.
if CONTENT:
    for name in ('ChickenEgg', 'ChickenEggInside', 'ChickenStraw', 'ChickenRoosterComb', 'ChickenRoosterTail', 'ChickenFeatherDecor', 'ChickenEggShell'):
        assert 'material %s\n' % name in materials, name
for name in ('ChickenStraw', 'ChickenFeatherDecor', 'ChickenEggShell'):
    assert '"%s"' % name in looks, name
# The code asks for the egg meshes (the egg by the kind, the cracked one by the hatch look)
assert 'return "ChickenEgg"' in chicken, 'the code no longer asks for the egg mesh'
assert 'MeshEggCracked = "ChickenEggCracked"' in looks, 'the code no longer asks for the cracked egg mesh'
if CONTENT:
    assert 'particles/ChickenEggShell.particle' in credits and 'ChickenHatchery.material' in credits

# The egg, chick and rooster are meshes made in Blender (shared hen skeleton with the clips Peep, Run, Crow, Hatch).

# All material scripts: every material a mesh uses must be defined there (a missing definition fails the check)
import re
# The material scripts of the public tree and of every content and room package, with their subfolders (the creatures
# package keeps its scripts in materials/scripts/Creatures)
material_text = ''.join(f.read_text() for f in content_packages.data_glob(root, 'materials/scripts', '*.material',
                                                                           recursive=True))


def material_block(name):
    match = re.search(r'^material %s(?:[ \t]*(?://|:)[^\n]*)?\s*\n\{.*?\n\}\n' % re.escape(name), material_text, re.M | re.S)
    assert match is not None, 'material %s is not defined in materials/scripts' % name
    return match.group(0)


def assert_matt(name):
    # matt: no emissive light, no specular highlight, and no overbright or yellow-cast straw colour
    block = material_block(name)
    assert not re.search(r'^\s*(emissive|self_illumination)\b', block, re.M), name + ' must not glow'
    specular = re.search(r'^\s*specular\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)', block, re.M)
    assert specular is not None and all(float(v) == 0.0 for v in specular.groups()), name + ' must have specular 0 0 0'
    for key in ('ambient', 'diffuse'):
        found = re.search(r'^\s*%s\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)' % key, block, re.M)
        assert found is not None, (name, key)
        red, green, blue = [float(v) for v in found.groups()]
        assert max(red, green, blue) <= 0.75, (name, key, 'too bright')
        assert blue >= 0.4 * red, (name, key, 'yellow cast')


# The egg is a mesh made in Blender; the hen, chick and rooster of the creatures package each have an own skeleton and
# one textured material (former meshes: the shared Chicken.skeleton and the rooster's comb and tail materials).
if CONTENT:
    for mesh, names in (('ChickenEgg', ('ChickenEgg', 'ChickenStraw')), ('ChickenEggCracked', ('ChickenEggInside',)),
                        ('ChickenChick', ('ChickenChickMeshy', 'ChickenChick.skeleton')),
                        ('ChickenRooster', ('ChickenRoosterMeshy', 'ChickenRooster.skeleton'))):
        data = model(mesh + '.mesh').read_bytes()
        for name in names:
            assert name.encode() in data, (mesh, name)
        assert mesh + '.mesh' in credits, mesh
    for name in ('ChickenEgg', 'ChickenStraw', 'ChickenEggInside', 'ChickenChickMeshy', 'ChickenRoosterMeshy'):
        material_block(name)
    # Every skeleton holds the clips its bird plays: the chick peeps while it stands, the rooster crows
    for skeleton_name, clips in (('Chicken.skeleton', (b'Run', b'Hatch', b'Walk', b'Idle')),
                                 ('ChickenChick.skeleton', (b'Peep', b'Run', b'Hatch', b'Walk', b'Idle')),
                                 ('ChickenRooster.skeleton', (b'Crow', b'Run', b'Hatch', b'Walk', b'Idle'))):
        skeleton = model(skeleton_name).read_bytes()
        for clip in clips:
            assert clip in skeleton, (skeleton_name, clip)
    # The hen skeleton, for the hen clip checks below
    skeleton = model('Chicken.skeleton').read_bytes()
    breeds = content_packages.read_text(root, 'materials/scripts/ChickenBreeds.material')
    assert 'material ChickenChick' in breeds and 'material ChickenRooster' in breeds
assert '"ChickenChick"' in chicken and '"ChickenRooster"' in chicken
assert 'ChickenPose::skeletonClip' in hook and 'hatchClip' in body(chicken, 'void ChickenEntity::setKindFromServer')
assert 'ChickenEggCracked' in looks

print('hatchery visuals checks passed')

# The rooster does not call the hens or chicks: no call mood, no call settings, no sound; the crow stays (pose, sound)
rooster_h = (root / 'source/rooms/HatcheryRooster.h').read_text()
rooster_cpp = (root / 'source/rooms/HatcheryRooster.cpp').read_text()
for text in (rooster_h, rooster_cpp, room):
    assert 'RoosterMood::call' not in text and 'mCallPercent' not in text and 'mCallTurns' not in text and 'mCallScratchChance' not in text
assert 'HatcheryRoosterCall' not in config and 'HatcheryRoosterCall' not in room
assert 'Hatchery/FoodCall' not in room
assert 'RoosterMood::crow' in rooster_cpp and 'ChickenPose::crow' in room and 'Hatchery/Crow' in room
assert 'ChickenKind::hen' in body(chicken, 'void ChickenEntity::doUpkeep')

# Flocking of the hens: scratching, fluttering and scattering from a hungry creature, the rooster protests when held
assert 'updateFlock' in body(room, 'void RoomHatchery::doUpkeep')
flock = body(room, 'void RoomHatchery::updateFlock')
for call in ('ChickenPose::flutter', 'ChickenPose::scratch', 'scatterTo', 'collectHungry', 'Hatchery/Cluck'):
    assert call in flock, call
assert 'CreatureActionType::eatChicken' in body(room, 'void RoomHatchery::collectHungry')
for key in ('HatcheryScatterRadius', 'HatcheryScatterTurns', 'HatcheryFlutterPercent', 'HatcheryScratchPercent'):
    assert key in room, key
    if TABLES:
        assert key in config, key
assert 'ChickenPose::scratch' in looks and 'ChickenPose::flutter' in looks
assert 'fireProtest' in body(chicken, 'void ChickenEntity::pickup')
# Eggs and chicks dropped outside a hatchery are lost
assert 'HatcheryYoungLostTurns' in chickUpkeep
if TABLES:
    assert 'HatcheryYoungLostTurns' in config

# Coop mesh with door clip and roof lookout, and the real hen clips Lay and Flutter (text checks only)
coop_h = (root / 'source/rooms/HatcheryCoopHouse.h').read_text()
for name in ('meshName = "ChickenCoopHouse"', 'oldMeshName = "ChickenCoop"', 'doorClip = "Door"', 'roofPerchHeight',
             'roofPerchOffset', 'isCoopMesh'):
    assert name in coop_h, name
assert 'nestCenter' not in coop_h and 'nestCount' not in coop_h, 'no seats in the coops'
assert 'HatcheryCoopHouse::meshName' in body(room, 'BuildingObject* RoomHatchery::notifyActiveSpotCreated')
assert 'HatcheryCoopHouse::roofPerchHeight' in room and 'HatcheryCoopHouse::roofPerchOffset' in room
assert 'ChickenCoop"' not in room
assert render.count('HatcheryCoopHouse::isCoopMesh') == 2
assert 'MeshNest = "ChickenNest"' in looks and 'MeshNest + ".mesh"' in looks, 'the code does not ask for ChickenNest.mesh'
if CONTENT:
    coop_mesh = model('ChickenCoopHouse.mesh').read_bytes()
    assert b'ChickenCoopHouse.skeleton' in coop_mesh and b'ChickenCoop' in coop_mesh
    # The straw inside the coop is the matt material ChickenCoopStraw (it replaced ChickenStraw): the mesh uses it and it is defined
    assert b'ChickenCoopStraw' in coop_mesh, 'the coop mesh does not use ChickenCoopStraw'
    assert_matt('ChickenCoopStraw')
    # The straw nest: material and texture exist, the mesh uses the material, the material is matt, the code asks for the mesh
    assert content_packages.data_file(root, 'materials/scripts/ChickenNest.material') is not None
    assert content_packages.data_file(root, 'materials/textures/ChickenNest.png') is not None
    nest_mesh = model('ChickenNest.mesh').read_bytes()
    assert b'ChickenNest' in nest_mesh, 'ChickenNest.mesh does not refer to the material ChickenNest'
    assert 'texture ChickenNest.png' in material_block('ChickenNest')
    assert_matt('ChickenNest')
    coop_skeleton = model('ChickenCoopHouse.skeleton').read_bytes()
    for name in (b'Root', b'Door', b'Lookout', b'Idle'):
        assert name in coop_skeleton, name
    assert model('ChickenCoop.mesh').exists()
bounds = (root / 'source/gamemap/RoomObjectBounds.h').read_text()
assert '{"ChickenCoopHouse", -.203275f, -.4f, .796725f, .4f}' in bounds
if CONTENT:
    assert 'ChickenCoop ChickenCoopHouse' in content_packages.read_text(root, 'config/roomAmbienceProduction.cfg')
    assert 'ChickenCoopHouse.mesh' in credits and 'ChickenCoopHouse.skeleton' in credits
    # The hen clips Lay and Flutter are named in the CREDITS row of the hen skeleton (the own rig of the hatchery
    # package names its clips in one list instead of the former row "Chicken.skeleton (clips Lay, Flutter)")
    skeleton_rows = [row for row in credits.splitlines() if row.startswith('models/Chicken.skeleton')]
    assert skeleton_rows, 'no CREDITS row of models/Chicken.skeleton'
    assert any(' Lay,' in row and ' Flutter,' in row for row in skeleton_rows), 'the hen clips Lay and Flutter have no CREDITS row'
# The door of the coop swings with the animal that comes out, the old mesh shakes as before
assert 'mDoor' in looks and 'HatcheryCoopHouse::doorClip' in body(looks, 'void RenderManager::rrCreateCoopDecor')
assert 'mDoor->setEnabled(true)' in body(looks, 'void RenderManager::rrSetChickenPose')
assert 'mShake = lookSettings().mCoopShakeSeconds' in body(looks, 'void RenderManager::rrSetChickenPose')
assert 'mDoor->addTime' in body(looks, 'void RenderManager::updateChickenLooks')
assert 'mNest' not in body(looks, 'void RenderManager::rrDestroyCoopDecor'), 'the nests belong to the hatchery, not to a coop'
#: The skeleton of each bird (the hen, chick and rooster of the creatures package have own skeletons; the former meshes
#: shared Chicken.skeleton), for the clip checks below
bird_skeletons = {bird: model(bird + '.skeleton').read_bytes() for bird in ('Chicken', 'ChickenChick', 'ChickenRooster')} \
    if CONTENT else {}
# Hen clips: used when the skeleton has them, procedural motion stays as fallback; the chick peeps, the rooster crows
for bird, name in [('Chicken', clip) for clip in (b'Lay', b'Flutter', b'Run', b'Hatch', b'Die', b'Pick', b'Paw', b'Sleep',
                                                  b'Walk', b'Idle')] + [('ChickenChick', b'Peep'), ('ChickenRooster', b'Crow')]:
    if CONTENT:
        assert name in bird_skeletons[bird], (bird, name)
assert 'return "Lay"' in pose and 'return "Flutter"' in pose and 'isOneShotClip' in pose
# Mating clips: the rooster plays Mount, Tread (looped) and Dismount by the phase of the pose, the hen ducks, once
# (the former shared skeleton also held MountCycle, which the code never plays; the own rooster rig of CS10a has none)
for bird, name in [('ChickenRooster', clip) for clip in (b'Mount', b'Tread', b'Dismount')] + \
        [('Chicken', b'Duck')]:
    if CONTENT:
        assert name in bird_skeletons[bird], (bird, name)
assert 'return "Mount"' in pose and 'return "Duck"' in pose and '(clip == "Mount")' in pose and '(clip == "Dismount")' in pose
assert '(clip == "Tread")' not in pose
update = body(looks, 'void RenderManager::updateChickenLooks')
assert 'hasAnimation("Tread")' in update and '{"Mount", "Tread", "Dismount"}' in update and 'phase == 2' in update
# The phases fit the clips: Mount 0.4 s, Tread 2 x 0.55 s, Dismount 0.4 s = the 1.9 s of the pose and of the Duck clip
clips = (root / 'tools/blender-assets/hatchery_clips.py').read_text()
for line in ('MOUNT_SECONDS = 0.4', 'TREAD_SECONDS = 0.55', 'DISMOUNT_SECONDS = 0.4', 'DUCK_SECONDS = 1.9', 'TREAD_CYCLES = 2'):
    assert line in clips, line
if TABLES:
    assert 'HatcheryLookMountClimbSeconds	0.4' in config and 'HatcheryLookMountSeconds	1.9' in config
# With the Duck clip the procedural duck of the hen (HatcheryLookMountCrouch) is not added again
assert 'look.mMountCrouch > 0.0f) && look.mEntity->getSkeleton()->hasAnimation("Duck")' in update
assert 'ChickenPose::isOneShotClip(clip)' in hook and 'hasAnimation(clip)' in hook
assert 'hasAnimation("Lay")' in looks and 'hasAnimation("Flutter")' in looks
assert 'values.mLayStretchX, values.mLayStretchY' in looks and 'lift = values.mFlutterLift * rise' in looks
for name in ('hen_lay_flutter.py', 'coop_house.py'):
    assert (root / 'tools/blender-assets' / name).exists(), name
# Lay and Flutter keep their translations in the parent frame (the frame fix tool says why ogre_fix must not touch them)
fix_tool = (root / 'tools/blender-assets/chicken_frame_fix.py').read_text()
assert 'ogre_fix.py must NOT be applied' in fix_tool and 'T_new = q_bind * T_old' in fix_tool
import shutil
import subprocess
import sys
import tempfile
if CONTENT:
    assert shutil.which('OgreXMLConverter') is not None, 'OgreXMLConverter must be on the PATH (the skeleton frame check must run)'
    sys.path.insert(0, str(root / 'tools/blender-assets'))
    import chicken_frame_fix as frame_fix
    #: Bones and clips of the hen's own rig (creatures package, CS10a)
    HEN_BONES = ['pelvis', 'chest', 'neck', 'head', 'wing.L', 'wing2.L', 'wing.R', 'wing2.R', 'tail1', 'tail2',
                 'thigh.L', 'shin.L', 'toe.L', 'thigh.R', 'shin.R', 'toe.R']
    HEN_CLIPS = ['Die', 'Dismount', 'Duck', 'Flutter', 'Hatch', 'Idle', 'Lay', 'Mount', 'Paw', 'Pick', 'Run', 'Sleep',
                 'Tread', 'Walk']
    import xml.etree.ElementTree as ET
    with tempfile.TemporaryDirectory() as tmp:
        out_xml = str(Path(tmp) / 'Chicken.xml')
        subprocess.check_call(['OgreXMLConverter', '-q', str(model('Chicken.skeleton')), out_xml],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        skeleton_xml = ET.parse(out_xml).getroot()
    # The hen has its own rig since CS10a (16 bones, root pelvis; the former shared skeleton: 22 bones, root Root,
    # hip Hip, 18 clips). Fixed values counted once on content/cs10a-hand-menu: Lay sinks the pelvis by 0.040 (the
    # former hip by 0.050); Flutter keeps the root on the ground (Mario 2026-11-26: the hen does not fly; the former
    # Flutter lifted the root by 0.075).
    assert [name for _, name in frame_fix.structure(skeleton_xml)[0]] == HEN_BONES
    assert frame_fix.structure(skeleton_xml)[2] == sorted(HEN_CLIPS)
    lay_hip = frame_fix.track_values(skeleton_xml, 'Lay', 'pelvis', 'z')
    assert abs(min(lay_hip) + 0.040) < 0.002, min(lay_hip)
    for axis in 'xyz':
        flutter_root = frame_fix.track_values(skeleton_xml, 'Flutter', 'pelvis', axis)
        assert flutter_root and max(abs(v) for v in flutter_root) < 0.002, (axis, flutter_root)
    assert max(abs(v) for v in frame_fix.track_values(skeleton_xml, 'Lay', 'pelvis', 'y')) < 0.002
    # The meshes name the materials they use (read from the converted meshes) and the materials are defined
    for mesh, expected in (('ChickenNest', {'ChickenNest'}), ('ChickenEgg', {'ChickenEgg', 'ChickenStraw'}),
                           ('ChickenEggCracked', {'ChickenEgg', 'ChickenEggInside', 'ChickenStraw'}),
                           ('ChickenCoopHouse', {'ChickenCoop', 'ChickenCoopStraw'})):
        with tempfile.TemporaryDirectory() as tmp:
            mesh_xml = str(Path(tmp) / (mesh + '.xml'))
            subprocess.check_call(['OgreXMLConverter', '-q', str(model(mesh + '.mesh')), mesh_xml],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            used = set(sm.get('material') for sm in ET.parse(mesh_xml).getroot().iter('submesh'))
        assert expected <= used, (mesh, expected, used)
        for name in used:
            material_block(name)
    # Playback advances turnsPerSecond clip units per second, matching the server's laying turns.
    import re
    show_turns = max(2, int(re.search(r'^\s*HatcheryLayShowTurns\s+(\d+)', config, re.M).group(1)))
    turns_per_second = float(re.search(r'turnsPerSecond = ([0-9.]+);', (root / 'source/ODApplication.cpp').read_text()).group(1))
    lay = [a for a in skeleton_xml.find('animations').findall('animation') if a.get('name') == 'Lay'][0]
    assert abs(float(lay.get('length')) / turns_per_second - show_turns / turns_per_second) < 0.01, lay.get('length')
    last_times = set()
    for track in lay.find('tracks').findall('track'):
        last_times.add(round(float(track.find('keyframes').findall('keyframe')[-1].get('time')), 3))
    assert last_times == {round(float(lay.get('length')), 3)}, last_times
    # Idle starts without a glitch (the former first frame had the hip sunk for one frame): on the own rig the loop
    # begins at time 0 on exactly the pose it ends with, so it neither jumps at the start nor at the loop seam
    idle = [a for a in skeleton_xml.find('animations').findall('animation') if a.get('name') == 'Idle'][0]
    for track in idle.find('tracks').findall('track'):
        keys = track.find('keyframes').findall('keyframe')
        first, last = keys[0], keys[-1]
        assert first.get('time') == '0', track.get('bone')
        for tag in ('translate', 'rotate'):
            assert first.find(tag).attrib == last.find(tag).attrib, (track.get('bone'), tag)
# The rooster that guards the flock pecks (Pick clip and a lunge of the head)
assert 'if(name == guard)' in pose and 'values.mGuardPeckPitch' in looks
if TABLES:
    assert 'HatcheryLookGuardPeckSpeed' in config
# the rooster protests in the hand: pose, clip and look
assert 'ChickenPose::protest' in body(chicken, 'void ChickenEntity::pickup') and 'protest)' in pose
assert 'values.mProtestPuff' in looks
if TABLES:
    assert 'HatcheryLookProtestRoll' in config
# Floor nests are not gated by client Room objects, coop presence or animal population.
decor = body(looks, 'const bool check = mCoopDecorTimer')
assert 'updateNestFields();' in decor and 'getCoveringRoom' not in decor
assert 'roomAnimals' not in decor and 'mFeathers' not in decor, 'no feathers entity at the coops'
nest_update = body(looks, 'void RenderManager::updateNestFields')
assert 'HatcheryFeathers_' not in nest_update, 'loose feather decor must not appear without an action'
assert 'mFeatherEntities[i]->setVisible(empty)' not in nest_update
assert 'chickenClipVisible(chicken, "Flutter")' in looks
assert 'chickenClipVisible(chicken, "Tread")' in looks
assert 'chickenClipVisible(chicken, EntityAnimation::walk_anim)' in looks
assert 'feeding.mAnimation->getEnabled()' in render
# counter-proof: the old count over all chicken entities would keep a rooster-only hatchery looking alive
assert 'countEntitiesOnTile(GameEntityType::chickenEntity)' not in decor
# there is no night: no sleeping pose, no chick tucked in under a hen, the chicks always walk in a line behind the hen
chick_line = body(room, 'void RoomHatchery::updateChickLine')
assert 'night' not in chick_line.lower() and 'Each chick follows the one in front' in chick_line
# the rooster (leading, calling or crowing) is never the front of the line: the chicks follow the hen only
assert 'rooster' not in chick_line and 'RoosterMood' not in chick_line
assert 'lead' not in pose.lower() and 'LookLead' not in looks and 'HatcheryLookLead' not in config
assert 'ChickenPose::roost' not in looks and 'mChickUnder' not in looks and 'mRoost' not in looks
print('hatchery coop and hen clip checks passed')
