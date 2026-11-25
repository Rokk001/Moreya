"""Check the hairy pool attendant mesh (1057-1060 and 1070, restored by K22) and its acts.

Reads the shipped models/PoolAttendant.mesh and .skeleton through OgreXMLConverter and the attendant code; no compiler, no
game. Checks (1) the exact hairy mesh that K22 restored with its fitting skeleton (it replaces the mesh decision 1186 had
put back) and its visible props, including towel, whistle, hair, body hair and moustache;
(2) the Sit pose: knees bent and apart (no stiff legs), arms beside the
belly (no intersection), body not twisted; (3) the clips: Whistle brings the whistle to the mouth, TowelWave holds the
towel in the hand above the shoulder and waves it, Doze lets him sink sideways, Climb, Walk and Jump move; (4) the code:
the acts, the whistle only with a bather and at the moment of the blow, the cannonball and its place.
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



# K22 restored the hairy mesh of decisions 1057-1060 and 1070 that fits the skeleton (decision 1186 had put back the older
# mesh, whose joints sat beside the joints of this skeleton) and, after the owner findings of 2026-11-17, carries the head of
# the attendant in the game today, volume body hair and a small whistle; check_spa_attendant_k22.py checks fit and look.
assert sha256(room_file('models/PoolAttendant.mesh').read_bytes()).hexdigest() == (
    '6b22bbb1da5fdb1292d38e37141b543a94f175dc04cecfaffb5e14de672c4403'
), 'K22 restores the hairy attendant mesh that fits its skeleton'

with tempfile.TemporaryDirectory(prefix='spa-1057-') as folder:
    converted = {}
    for name in ('PoolAttendant.mesh', 'PoolAttendant.skeleton'):
        path = Path(folder) / (name + '.xml')
        result = subprocess.run([str(CONVERTER), str(room_file('models/' + name)), str(path)], capture_output=True, text=True, cwd=folder)
        assert result.returncode == 0, result.stdout + result.stderr
        converted[name] = ET.parse(path).getroot()
mesh, skeleton = converted['PoolAttendant.mesh'], converted['PoolAttendant.skeleton']

# ---- 1. The look -----------------------------------------------------------------------------------------------------
sub_by_material = {}
for sub in mesh.findall('submeshes/submesh'):
    sub_by_material.setdefault(sub.get('material'), []).append(sub)
for material in ('SpaSkin', 'SpaSuit', 'SpaHair', 'SpaBodyHair', 'SpaLinen', 'SpaWhistle', 'SpaEyes', 'SpaIronWorn'):
    assert material in sub_by_material, 'the attendant needs the material ' + material
faces = {m: sum(len(s.findall('faces/face')) for s in subs) for m, subs in sub_by_material.items()}
assert faces['SpaLinen'] >= 300 and faces['SpaHair'] >= 1000, 'towel, hair and moustache stay'
assert faces['SpaBodyHair'] >= 10000, 'full body hair'

suit = points_for(mesh, 'SpaSuit')
belly = suit[(suit[:, 2] > .42) & (suit[:, 2] < .6)]
whistle = points_for(mesh, 'SpaWhistle')
assert np.ptp(whistle[:, 0]) > .05 and np.ptp(whistle[:, 2]) > .095, 'whistle must read from the camera'

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
    for suffix, sign in (('_R', -1), ('_L', 1)):
        thigh, shin, foot = sit['Thigh' + suffix], sit['Shin' + suffix], sit['Foot' + suffix]
        bend = angle_between(shin - thigh, foot - shin)
        assert bend > .45, 'sitting legs are not stiff: the knee bends (%.2f rad)' % bend
        assert sign * shin[0] > .14, 'the knees are apart'
        elbow, wrist = sit['Forearm' + suffix], sit['Hand' + suffix]
        # the arm hangs beside the belly: its inner edge (elbow 0.058 thick) stays outside the belly of the suit
        assert sign * elbow[0] - .058 > np.percentile(np.abs(belly[:, 0]), 98) - .002, 'the elbow is beside the belly, not in it'
        assert sign * wrist[0] - .04 > .22, 'the hand rests beside the belly, not in it'
    assert abs(sit['Thigh_R'][0] + sit['Thigh_L'][0]) < .02 and abs(sit['Thigh_R'][1] - sit['Thigh_L'][1]) < .02, 'hips not twisted'
    assert abs(sit['UpperArm_R'][2] - sit['UpperArm_L'][2]) < .03 and abs(sit['UpperArm_R'][1] - sit['UpperArm_L'][1]) < .03, \
        'shoulders not twisted against the hips'

sit0, sit0_matrices = pose('Sit', 0)


def bind_matrix(name):
    """World matrix of a bone in the bind pose."""
    local = np.eye(4)
    local[:3, :3] = rotation(bones[name].find('rotation'))
    local[:3, 3] = vector(bones[name].find('position'))
    return bind_matrix(parents[name]) @ local if name in parents else local


# owner finding 3 (2026-11-17): the WhistleHang joint is the ring at the end of the cord; the whistle itself (the centre of
# its vertices) is carried by that bone
whistle_centre = np.append(points_for(mesh, 'SpaWhistle').mean(axis=0), 1)
whistle_bind_inverse = np.linalg.inv(bind_matrix('WhistleHang'))


def whistle_at(matrices):
    """Centre of the whistle in a pose."""
    return (matrices['WhistleHang'] @ whistle_bind_inverse @ whistle_centre)[:3]


for seconds in (.9, 1.05):
    whistle, whistle_matrices = pose('Whistle', seconds)
    head = whistle['Head']
    mouth_distance = np.linalg.norm(whistle_at(whistle_matrices) - (head + np.array([0, -.13, .05])))
    assert mouth_distance < .12, 'Whistle: the whistle is at the mouth (%.3f)' % mouth_distance
    assert np.linalg.norm(whistle['Hand_R'] - whistle_at(whistle_matrices)) < .14, 'Whistle: the whistle is in the hand'
assert np.linalg.norm(whistle_at(sit0_matrices) - (sit0['Head'] + np.array([0, -.13, .05]))) > .2, \
    'the whistle hangs on his chest at rest'

towel0, _ = pose('TowelWave', .75)
towel1, _ = pose('TowelWave', .95)
towel2, _ = pose('TowelWave', 1.15)
for towel in (towel0, towel1, towel2):
    assert np.linalg.norm(towel['Towel'] - towel['Hand_R']) < .2, 'TowelWave: the towel is in his hand'
    assert towel['Towel'][2] > towel['UpperArm_R'][2] + .1, 'TowelWave: the towel is above his shoulder'
assert np.linalg.norm(towel0['Towel'] - towel1['Towel']) > .08 and np.linalg.norm(towel1['Towel'] - towel2['Towel']) > .08, \
    'TowelWave: the towel is visibly waved'
assert np.linalg.norm(towel0['TowelTip'] - towel1['TowelTip']) > .1, 'TowelWave: the end of the towel flaps'
assert np.linalg.norm(sit0['Towel'] - sit0['Hand_R']) > .25, 'the towel lies on the shoulder at rest, not in the hand'

doze, _ = pose('Doze', 1.3)
assert sit0['Head'][2] - doze['Head'][2] > .02 and abs(doze['Head'][0] - sit0['Head'][0]) > .04, 'Doze: he sinks and slides sideways'
assert doze['Head'][1] < sit0['Head'][1] - .04, 'Doze: he slumps forward'

climb0, _ = pose('Climb', 0)
climb1, _ = pose('Climb', .5)
assert abs(climb0['Hand_R'][2] - climb1['Hand_R'][2]) > .05 or abs(climb0['Hand_L'][2] - climb1['Hand_L'][2]) > .05, 'Climb moves the hands'
walk0, _ = pose('Walk', 0)
walk1, _ = pose('Walk', .08)
assert abs(walk0['Foot_R'][1] - walk1['Foot_R'][1]) > .02 or abs(walk0['Foot_R'][2] - walk1['Foot_R'][2]) > .02, 'Walk moves the feet'
jump0, _ = pose('Jump', 0)
jump1, _ = pose('Jump', 1.0)
assert np.linalg.norm(jump0['Foot_R'] - jump1['Foot_R']) > .15, 'Jump tucks the legs (cannonball)'
assert jump1['Foot_R'][1] < jump1['Pelvis'][1] - .02 or jump1['Foot_R'][2] > jump1['Pelvis'][2] - .35, 'Jump: knees pulled up'

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
materials = read('materials/scripts/Spa.material')
for material in sub_by_material:
    assert re.search(r'^material ' + material + r' ', materials, re.M), material
credits = read('CREDITS')
assert re.search(r'^models/PoolAttendant\.mesh .*decision 863', credits, re.M)
assert re.search(r'^models/PoolAttendant\.skeleton .*1057-1060, 1070', credits, re.M)

print('check_spa_owner_1057 ok: hairy attendant mesh, bent legs, arms beside the belly, readable acts')
