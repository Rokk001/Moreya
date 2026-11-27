"""Check the main menu crows: wing-beat clips exist in the skeletons and the menu scene uses them. No compile, no game.

Since CS10a the crows are the crow figure of the new figures (Meshy model, own rig with split-off wings, bones named
like the former menu crow: Root, Head, WingL/WingTipL on its -x side, WingR/WingTipR). It rests with folded wings, so
the wingspan is the spread span: the reach of each wing from its root joint plus the distance of the two root joints
(on the former crow, which rested with spread wings, this gives its rest span: 3.436 against 3.43). Fixed value counted
once on content/cs10a-hand-menu: spread span / body length 1.63 (the former crow 2.15).

The crow meshes and skeletons and their CREDITS row are content (core-menu package and the CREDITS of the content
repository, scripts/content_packages.py); without the content they are named as not checked.
"""
from pathlib import Path
import math
import re
import os
import subprocess
import sys
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / 'scripts'))
import content_packages  # noqa: E402
import room_packages  # noqa: E402

WITH_CONTENT = content_packages.has_content(root)
cfg = content_packages.read_text(root, 'config/mainmenuscene.cfg').replace('\r\n', '\n')
# the public CREDITS plus the CREDITS of the content repository when the content is present
credits = room_packages.credits_text(root)
generator = (root / 'tools/blender-assets/menu_scene_models.py').read_text(encoding='utf-8')

CLIPS = ('Watch', 'Flap', 'FlapIn', 'TakeOff', 'Land')
BONES = ('Root', 'Head', 'WingL', 'WingTipL', 'WingR', 'WingTipR')
CROWS = ('CrowA', 'CrowB', 'CrowC', 'CrowD')

output = root / 'out/menu-crow-check'
output.mkdir(parents=True, exist_ok=True)
converter = os.environ.get('OGRE_XML_CONVERTER', 'OgreXMLConverter')

# Ogre binary serialisation writes strings null-free and newline terminated.
for crow in CROWS:
    mesh = content_packages.resolve(root, 'models/Menu' + crow + '.mesh')
    skeleton = content_packages.resolve(root, 'models/Menu' + crow + '.skeleton')
    if not WITH_CONTENT and not (mesh.is_file() and skeleton.is_file()):
        content_packages.unchecked('check_menu_crow_animation', ['models/Menu' + crow + '.mesh and .skeleton'])
        continue
    assert mesh.is_file() and skeleton.is_file(), crow
    data = skeleton.read_bytes()
    for name in CLIPS + BONES:
        assert (name + '\n').encode() in data, (crow, name)
    assert b'Menu' + crow.encode() + b'.skeleton' in mesh.read_bytes(), crow
    mesh_xml = output / (crow + '.mesh.xml')
    skeleton_xml = output / (crow + '.skeleton.xml')
    for source, target in ((mesh, mesh_xml), (skeleton, skeleton_xml)):
        subprocess.run([converter, '-q', str(source), str(target)], check=True, stdin=subprocess.DEVNULL)
    geometry = ET.parse(mesh_xml).getroot()
    rig = ET.parse(skeleton_xml).getroot()
    bones = {index: bone.get('name') for index, bone in enumerate(rig.findall('./bones/bone'))}
    joints = {bone.get('name'): bone for bone in rig.findall('./bones/bone')}
    parents = {link.get('bone'): link.get('parent') for link in rig.findall('./bonehierarchy/boneparent')}

    def joint(name):
        """Bind position of a joint, from the full bind transforms of its chain of parents."""
        chain = []
        while name:
            chain.append(name)
            name = parents.get(name)
        turn_total = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
        place = [0.0, 0.0, 0.0]
        for link in reversed(chain):
            bone = joints[link]
            local = [float(bone.find('position').get(axis)) for axis in 'xyz']
            place = [place[i] + sum(turn_total[i][j] * local[j] for j in range(3)) for i in range(3)]
            turn = bone.find('rotation')
            axis = [float(turn.find('axis').get(c)) for c in 'xyz']
            norm = math.sqrt(sum(c * c for c in axis)) or 1.0
            x, y, z = (c / norm for c in axis)
            angle = float(turn.get('angle'))
            c, s_, t = math.cos(angle), math.sin(angle), 1 - math.cos(angle)
            matrix = [[t * x * x + c, t * x * y - s_ * z, t * x * z + s_ * y],
                      [t * x * y + s_ * z, t * y * y + c, t * y * z - s_ * x],
                      [t * x * z - s_ * y, t * y * z + s_ * x, t * z * z + c]]
            turn_total = [[sum(turn_total[i][k] * matrix[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
        return place
    positions = geometry.findall('./sharedgeometry/vertexbuffer/vertex/position')
    assigned = {}
    for assignment in geometry.findall('./boneassignments/vertexboneassignment'):
        name = bones[int(assignment.get('boneindex'))]
        assigned.setdefault(name, []).append(positions[int(assignment.get('vertexindex'))])
    body = assigned['Root'] + assigned['Head']
    # The authoring mesh uses Y for nose-to-tail and X for wingspan.
    length = max(float(p.get('y')) for p in body) - min(float(p.get('y')) for p in body)

    def reach(root_bone, tip_bone):
        """Farthest distance of a wing's vertices from its root joint."""
        centre = joint(root_bone)
        return max(math.dist(centre, [float(p.get(axis)) for axis in 'xyz'])
                   for p in assigned.get(root_bone, []) + assigned.get(tip_bone, []))
    span = reach('WingL', 'WingTipL') + reach('WingR', 'WingTipR') + math.dist(joint('WingL'), joint('WingR'))
    assert 1.55 <= span / length <= 1.75, (crow, 'spread wingspan/body length', span / length)
    for clip in ('Flap', 'TakeOff'):
        for wing in ('WingL', 'WingR'):
            track = rig.find("./animations/animation[@name='%s']/tracks/track[@bone='%s']" % (clip, wing))
            angles = [float(r.get('angle')) * float(r.find('axis').get('z')) for r in track.findall('./keyframes/keyframe/rotate')]
            assert max(angles) - min(angles) >= math.radians(80), (crow, clip, wing, angles)
    
if WITH_CONTENT or 'the menu crows are the crow figure of Moreya' in credits:
    assert 'the menu crows are the crow figure of Moreya' in credits
else:
    content_packages.unchecked('check_menu_crow_animation', ['CREDITS row of the crows'])
for clip in CLIPS:
    assert '"' + clip + '"' in generator, clip

# The scene file must place every crow and drive it through the whole take-off, flight and landing sequence.
# config/mainmenuscene.cfg is a mixed table: the crows are only complete with its own rows from the content.
if WITH_CONTENT:
    groups = re.findall(r'\[RenderSceneGroup\]\n(.*?)\n\[/RenderSceneGroup\]', cfg, re.S)
    for crow in CROWS:
        assert re.search(r'^AddEntity ' + crow + r' Menu' + crow + r'\.mesh ', cfg, re.M), crow
        own = [g for g in groups if re.search(r'^AnimationTime ' + crow + ' Watch', g, re.M)]
        assert len(own) == 1, crow
        lines = [line for line in own[0].split('\n') if line and not line.startswith('#')]
        assert lines[0] == '*Repeat', crow
        names = [line.split()[0] for line in lines[1:]]
        assert names == ['AnimationTime', 'AnimationOnce', 'TurnEntity', 'MoveEntity', 'PosEntity', 'Wait', 'PosEntity',
                         'MoveEntity', 'AnimationOnce', 'PosEntity', 'TurnEntity'], (crow, names)
        assert lines[11].split()[2] == 'Watch'
        watch = float(lines[1].split()[3])
        assert watch > 0 and watch % 8 == 0, (crow, 'Watch time must be a whole number of 8 s loops')
        assert lines[2].split()[2] == 'TakeOff' and lines[9].split()[2] == 'Land'
        out = lines[4].split()
        inbound = lines[8].split()
        assert out[2] == 'Flap' and inbound[2] == 'FlapIn'
        speed = float(out[3])
        assert speed == float(inbound[3])
        # Four beats of 0.5 s per eighteen tiles: the inbound flight must end on the Flap start pose, where Land begins.
        start = [float(v) for v in lines[7].split()[2:5]]
        perch = [float(v) for v in inbound[4:7]]
        distance = math.dist(start, perch)
        beats = distance / speed / 0.5
        assert abs(beats - round(beats)) < 0.02, (crow, distance, beats)
        # The landing returns to the exact perch the entity was placed at.
        place = re.search(r'^AddEntity ' + crow + r' \S+ (\S+) (\S+) (\S+)', cfg, re.M)
        assert all(abs(float(a) - b) < 1e-6 for a, b in zip(place.groups(), perch)), crow
        # The hidden waiting position is below the ground and the flight keeps the same heading while it rises.
        assert float(lines[5].split()[4]) < -100
else:
    content_packages.unchecked('check_menu_crow_animation', ['crow flights of config/mainmenuscene.cfg'])
print('menu crow animation passes the checks')
