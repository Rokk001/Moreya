"""Check the pool attendant mesh and its acts (decisions 1057-1060 and 1070; the figure is the approved Meshy attendant of
2026-11-26, which replaced the hairy mesh that K22 had restored).

Reads the shipped models/PoolAttendant.mesh and .skeleton through OgreXMLConverter and the attendant code; no compiler, no
game. Checks (1) the exact approved mesh (the pinned hash of spa_attendant_meshy_contract.py) with its one Meshy material;
the towel, whistle, hair, body hair and moustache were parts of the former mesh and are not part of the approved model;
(2) the Sit pose: knees bent and apart (no stiff legs), arms beside the belly (no intersection), body not twisted; (3) the
clips: Whistle brings the hand to the mouth, TowelWave raises the hand above the shoulder and waves it, Doze lets him sink
sideways, Climb, Walk and Jump move; (4) the code: the acts, the whistle only with a bather and at the moment of the blow,
the cannonball and its place. Bone names of the shared Meshy rig.
"""
from hashlib import sha256
from pathlib import Path
import math
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(ROOT / 'scripts'))
import content_packages  # noqa: E402
import room_packages  # noqa: E402

#: The assets of the spa come from its room package (scripts/room_packages.py); without the package only the code
#: side is checked
ROOM_ASSETS = room_packages.has_room(ROOT, 'Spa')


def room_file(relative):
    """A file of the game data, or of the room package when it moved there."""
    return room_packages.resolve(ROOT, relative)
helper_source = (ROOT / 'source/tests/check_spa_owner_863.py').read_text(encoding='utf-8')
helpers = {'__file__': str(ROOT / 'source/tests/check_spa_owner_863.py')}
exec(compile(helper_source[:helper_source.index('def check_pose')], 'check_spa_owner_863_helpers', 'exec'), helpers)
CONVERTER = helpers['CONVERTER']
vector, rotation, sample_track, points_for = (helpers[name] for name in
                                            ('vector', 'rotation', 'sample_track', 'points_for'))


def read(name):
    """The CREDITS of both repositories, a mixed table with its own rows of the content, else a file of the game data
    or of the room package."""
    if name == 'CREDITS':
        return room_packages.credits_text(ROOT)
    if name.startswith('config/'):
        return content_packages.read_text(ROOT, name)
    return room_file(name).read_text(encoding='utf-8')


if not ROOM_ASSETS:
    print('check_spa_owner_1057: not checked, the spa room package is not present (the check measures its assets only)')
    sys.exit(0)



# K22 restored the hairy mesh of decisions 1057-1060 and 1070; the owner then approved the Meshy attendant (2026-11-26),
# which replaces it as it is. The delivered mesh is that approved model (its hash is pinned once, in
# spa_attendant_meshy_contract.py, which also checks its fit and look).
meshy_contract = {'__file__': str(ROOT / 'source/tests/spa_attendant_meshy_contract.py')}
exec(compile((ROOT / 'source/tests/spa_attendant_meshy_contract.py').read_text(encoding='utf-8'),
             'spa_attendant_meshy_contract', 'exec'), meshy_contract)
assert sha256(room_file('models/PoolAttendant.mesh').read_bytes()).hexdigest() == \
    meshy_contract['HASHES']['models/PoolAttendant.mesh'], 'the approved Meshy attendant mesh'

with tempfile.TemporaryDirectory(prefix='spa-1057-') as folder:
    converted = {}
    for name in ('PoolAttendant.mesh', 'PoolAttendant.skeleton'):
        path = Path(folder) / (name + '.xml')
        result = subprocess.run([str(CONVERTER), str(room_file('models/' + name)), str(path)], capture_output=True, text=True, cwd=folder)
        assert result.returncode == 0, result.stdout + result.stderr
        converted[name] = ET.parse(path).getroot()
mesh, skeleton = converted['PoolAttendant.mesh'], converted['PoolAttendant.skeleton']

# ---- 1. The look -----------------------------------------------------------------------------------------------------
# The approved model has one material; towel, whistle and hair were parts of the former mesh
sub_by_material = {}
for sub in mesh.findall('submeshes/submesh'):
    sub_by_material.setdefault(sub.get('material'), []).append(sub)
assert set(sub_by_material) == {meshy_contract['MATERIAL']}, 'the approved attendant has its one Meshy material'

# The belly: the body vertices (mostly on the hips and the spine) between 0.42 and 0.6
# the bone handles: the id attribute when the converter writes one, else the order of the bones (handle order)
bone_names_by_index = {(bone.get('id') or bone.get('handle') or str(index)): bone.get('name')
                       for index, bone in enumerate(skeleton.findall('bones/bone'))}
body_bones = {'Hips', 'Spine', 'Spine01', 'Spine02'}
positions = np.array([[float(p.get(c)) for c in 'xyz'] for p in mesh.findall('sharedgeometry/vertexbuffer/vertex/position')])
on_body = np.zeros(len(positions))
for assignment in mesh.findall('boneassignments/vertexboneassignment'):
    if bone_names_by_index.get(assignment.get('boneindex')) in body_bones:
        on_body[int(assignment.get('vertexindex'))] += float(assignment.get('weight'))
belly = positions[(on_body >= 0.5) & (positions[:, 2] > .42) & (positions[:, 2] < .6)]
assert len(belly) > 50, 'the belly of the approved attendant'

# ---- 2/3. The skeleton and its clips ---------------------------------------------------------------------------------
bones = {bone.get('name'): bone for bone in skeleton.findall('bones/bone')}
parents = {item.get('bone'): item.get('parent') for item in skeleton.findall('bonehierarchy/boneparent')}
clips = {clip.get('name'): clip for clip in skeleton.findall('animations/animation')}
assert set(clips) == {'Sit', 'Whistle', 'TowelWave', 'Doze', 'Walk', 'Climb', 'Jump'}
assert all(abs(float(clip.get('length')) - 2) < 1e-6 for clip in clips.values())
tracks = {name: {track.get('bone'): track.findall('keyframes/keyframe') for track in clip.findall('tracks/track')}
          for name, clip in clips.items()}


def pose(clip, seconds):
    """World matrices of all bones in a clip at a time."""
    result = {}

    def world(name):
        if name in result:
            return result[name]
        bone = bones[name]
        local = np.eye(4)
        local[:3, :3] = rotation(bone.find('rotation'))
        local[:3, 3] = vector(bone.find('position'))
        if name in tracks[clip]:
            translation, orientation = sample_track(tracks[clip][name], seconds)
            local[:3, 3] += translation
            local[:3, :3] = local[:3, :3] @ orientation
        result[name] = world(parents[name]) @ local if name in parents else local
        return result[name]
    for name in bones:
        world(name)
    return {name: matrix[:3, 3] for name, matrix in result.items()}, result


def angle_between(a, b):
    return math.acos(max(-1, min(1, float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))))))


for seconds in (0, .5, 1.0, 1.5):
    sit, matrices = pose('Sit', seconds)
    for side, sign in (('Right', -1), ('Left', 1)):
        thigh, shin, foot = sit[side + 'UpLeg'], sit[side + 'Leg'], sit[side + 'Foot']
        bend = angle_between(shin - thigh, foot - shin)
        assert bend > .45, 'sitting legs are not stiff: the knee bends (%.2f rad)' % bend
        assert sign * shin[0] > .14, 'the knees are apart'
        elbow, wrist = sit[side + 'ForeArm'], sit[side + 'Hand']
        # the arm hangs beside the belly: its inner edge (elbow 0.058 thick) stays outside the belly
        assert sign * elbow[0] - .058 > np.percentile(np.abs(belly[:, 0]), 98) - .002, 'the elbow is beside the belly, not in it'
        assert sign * wrist[0] - .04 > .22, 'the hand rests beside the belly, not in it'
    assert abs(sit['RightUpLeg'][0] + sit['LeftUpLeg'][0]) < .02 and abs(sit['RightUpLeg'][1] - sit['LeftUpLeg'][1]) < .02, \
        'hips not twisted'
    assert abs(sit['RightArm'][2] - sit['LeftArm'][2]) < .03 and abs(sit['RightArm'][1] - sit['LeftArm'][1]) < .03, \
        'shoulders not twisted against the hips'

sit0, sit0_matrices = pose('Sit', 0)

# Whistle: the approved model has no whistle part; the hand brings the whistle to the mouth, so the right hand comes to
# the mouth (as the whistle did) and is far from it at rest
for seconds in (.9, 1.05):
    whistle, whistle_matrices = pose('Whistle', seconds)
    mouth_distance = np.linalg.norm(whistle['RightHand'] - (whistle['Head'] + np.array([0, -.13, .05])))
    assert mouth_distance < .12 + .14, 'Whistle: the hand is at the mouth (%.3f)' % mouth_distance
assert np.linalg.norm(sit0['RightHand'] - (sit0['Head'] + np.array([0, -.13, .05]))) > .2, \
    'the hand does not rest at the mouth'

# TowelWave: the approved model has no towel part; the right hand is above the shoulder and visibly waved
towel0, _ = pose('TowelWave', .75)
towel1, _ = pose('TowelWave', .95)
towel2, _ = pose('TowelWave', 1.15)
for towel in (towel0, towel1, towel2):
    assert towel['RightHand'][2] > towel['RightArm'][2] + .1, 'TowelWave: the hand is above his shoulder'
assert np.linalg.norm(towel0['RightHand'] - towel1['RightHand']) > .08 and \
    np.linalg.norm(towel1['RightHand'] - towel2['RightHand']) > .08, 'TowelWave: the hand is visibly waved'

doze, _ = pose('Doze', 1.3)
assert sit0['Head'][2] - doze['Head'][2] > .02 and abs(doze['Head'][0] - sit0['Head'][0]) > .04, 'Doze: he sinks and slides sideways'
assert doze['Head'][1] < sit0['Head'][1] - .04, 'Doze: he slumps forward'

climb0, _ = pose('Climb', 0)
climb1, _ = pose('Climb', .5)
assert abs(climb0['RightHand'][2] - climb1['RightHand'][2]) > .05 or abs(climb0['LeftHand'][2] - climb1['LeftHand'][2]) > .05, \
    'Climb moves the hands'
walk0, _ = pose('Walk', 0)
walk1, _ = pose('Walk', .08)
assert abs(walk0['RightFoot'][1] - walk1['RightFoot'][1]) > .02 or abs(walk0['RightFoot'][2] - walk1['RightFoot'][2]) > .02, \
    'Walk moves the feet'
jump0, _ = pose('Jump', 0)
jump1, _ = pose('Jump', 1.0)
assert np.linalg.norm(jump0['RightFoot'] - jump1['RightFoot']) > .15, 'Jump tucks the legs (cannonball)'
assert jump1['RightFoot'][1] < jump1['Hips'][1] - .02 or jump1['RightFoot'][2] > jump1['Hips'][2] - .35, 'Jump: knees pulled up'

# ---- 4. The code ------------------------------------------------------------------------------------------------------
cpp = read('source/entities/PoolAttendantEntity.cpp')
assert 'const bool canWhistle = mRoom->hasBatherInPool();' in cpp and 'NB_ACTS_WITH_BATHER' in cpp, 'whistle only with a bather'
assert 'WHISTLE_BLOW_SECONDS' in cpp and cpp.count('SOUND_WHISTLE') == 2, 'the whistle sounds when the hand blows, once per act'
assert cpp.index('mWhistleSounded = true;') < cpp.index('RoomSpa::playSoundAt(mChairTile, SOUND_WHISTLE);'), 'sound after the flag'
assert 'getConfigTurns("SpaAttendantActMinSeconds")' in cpp and 'getConfigTurns("SpaAttendantActMaxSeconds")' in cpp
assert 'getConfigTurns("SpaAttendantCannonballMinSeconds")' in cpp and 'findAttendantPlace' in cpp and 'startJump' in cpp
for clip in ('towelWave', 'doze', 'whistle', 'sit', 'climb'):
    assert 'PoolAttendantPose::' + clip in cpp, clip
rooms = read('config/rooms.cfg')
for key, value in (('SpaAttendantActMinSeconds', '10'), ('SpaAttendantActMaxSeconds', '20'),
                   ('SpaAttendantCannonballMinSeconds', '120'), ('SpaAttendantCannonballMaxSeconds', '180')):
    assert re.search(r'^\s+' + key + r'\s+' + value + r'\s*$', rooms, re.M), key
# the approved model's material has its own script in the creatures package (former: Spa.material)
for material in sub_by_material:
    materials = content_packages.read_text(ROOT, 'materials/scripts/Creatures/' + material + '.material')
    assert re.search(r'^material ' + material + r'\b', materials, re.M), material
credits = read('CREDITS')
# the rows of the approved Meshy model (the rows of the former mesh, decisions 863 and 1057-1060, 1070, stay as history)
assert re.search(r'^models/PoolAttendant\.mesh .*Meshy', credits, re.M)
assert re.search(r'^models/PoolAttendant\.skeleton .*Meshy', credits, re.M)

print('check_spa_owner_1057 ok: approved attendant mesh, bent legs, arms beside the belly, readable acts')
