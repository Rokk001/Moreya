"""Native geometry, animation and texture contract for the accepted merchant replacement."""
from array import array
import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET

# Filled once from the reviewed native serializer output, never derived from assets during a test.
VERTICES = 416263
TRIANGLES = 495863
MINIMUM = (0.247596, -1.01321, 0.00864)
MAXIMUM = (1.03241, -0.516051, 1.30284)
HASHES = {'models/Merchant.mesh': '5109931928e0f297d913ad9cf9f03ce9705d944d31d91bf3b2bcfd0018fba38b', 'models/Merchant.skeleton': 'fedfad77afb1eb86a3925d7ac276a6e41c4a855924e7e57af843b2454da69444', 'materials/textures/MerchantBrassApprovedColor.png': '13e0088f101ba4207e80a63c091ed4bbb236abb751ca4b5dae95a32f30add3bb', 'materials/textures/MerchantBrassApprovedNormal.png': 'f559243be3489daa2d323ee85f3329346dc1f4c416d77087b02c3ea3a6a4309a', 'materials/textures/MerchantCloakApprovedColor.png': '95fbbdb204beaeef31ac5d3e8f227548a5f09739585271c34231b980351d2ebf', 'materials/textures/MerchantCloakApprovedNormal.png': '116205b04f27035ec83ac4d1d0821a367ae532643ed9714304c1c6375c820205', 'materials/textures/MerchantDetailsApprovedColor.png': '05c66a1f06fc1a083f46ea46b4756f245ccc58df61bc262a244d9410dceacdf9', 'materials/textures/MerchantDetailsApprovedNormal.png': 'ca7533d30a23ba2613f963f0976fdcdc5b3a7b0d49772d16062eedb4b2cbeef0', 'materials/textures/MerchantGoldApprovedColor.png': '89f19664b2cf1e7783cbc7a35f7933fa6763ba4aeac073698cf4bd29eaa17e73', 'materials/textures/MerchantGoldApprovedNormal.png': '51b606bd56088b165f734de7d6f6c1fbf174ebf9b091dcafafea9a6eec3d4d6a', 'materials/textures/MerchantHairApprovedColor.png': '8a7f782dc060c358d00484ee76a555dd33213e556a378d75534000da647ee643', 'materials/textures/MerchantHairApprovedNormal.png': '1019976e0f4208990906e5a03f82024fa7424830e41bd6fd43b3e5f9a72291c9', 'materials/textures/MerchantHideApprovedColor.png': '4b42b80dce02d37b9cb0a4b4d39d66c880d78928adfaecf7ab0cf64cfa3165a7', 'materials/textures/MerchantHideApprovedNormal.png': 'cf6f6fe2ae5cd4ac4c2345227dbcd24a319f19e0ff6514cc601f6c38df3c40ee', 'materials/textures/MerchantHoodApprovedColor.png': 'f6d2d351a5b46a1e897af0bf8a88f129a420aab5e371bf08f28c575a6205d878', 'materials/textures/MerchantHoodApprovedNormal.png': '0fa11e685e19c55fc06616a68ce7faf57bdecbc6e81fcea594dc79c155bc9c69', 'materials/textures/MerchantLeatherApprovedColor.png': '06c119d122c8a11ae27c018e7b6ced96d82a99df2289d10c6215c550c0a6c5a7', 'materials/textures/MerchantLeatherApprovedNormal.png': 'db04e79d17f179b1b0bdfbf013ef45b41f18a5dddb2dd821e9e6d9f70cee6221', 'materials/textures/MerchantLinenApprovedColor.png': '044fab840b1b3963d5b24e84f687c1991f8dc4f4d1b4ed68e7c98168a6de7e29', 'materials/textures/MerchantLinenApprovedNormal.png': 'fb4dbccfba52bebc3022ebf60b6ff268562a6036a0ed5ab2dc2c9e7929c5baa5', 'materials/textures/MerchantRobeApprovedColor.png': '3458d9e9b198be35dc7569294cd0b5329081135509f86023309c862895a2edab', 'materials/textures/MerchantRobeApprovedNormal.png': '6b9f50ddf5605e3753704b9ae9e65f1828229b6351c3483899eb7ba7ef7cffe8'}
ATLASES = {'Robe': 2048, 'Cloak': 2048, 'Linen': 2048, 'Leather': 2048,
           'Brass': 1024, 'Details': 1024, 'Hair': 1024, 'Hood': 2048,
           'Hide': 2048, 'Gold': 1024}
CLIPS = {'Idle': 4.0, 'Walk': 0.6, 'CountGold': 3.2, 'RubHands': 2.0}
BONES = ('Root', 'Pelvis', 'Spine', 'Chest', 'Head', 'UpperArm_R', 'Forearm_R', 'Hand_R',
         'UpperArm_L', 'Forearm_L', 'Hand_L', 'Thigh_R', 'Shin_R', 'Foot_R',
         'Thigh_L', 'Shin_L', 'Foot_L', 'Scales', 'Coins', 'Coin')


# Deserialize a native delivered asset once with bounded execution and retain its real exit status.
def deserialize(root, filename, directory):
    converter = os.environ.get('OGRE_XML_CONVERTER', 'OgreXMLConverter')
    output = directory / (filename + '.xml')
    subprocess.run([converter, '-q', '-log', str(output) + '.log',
                    str(root / 'models' / filename), str(output)],
                   stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                   stderr=subprocess.PIPE, timeout=120, check=True)
    return output


# Keep approved visual content byte-exact while checking the shader and texture contracts independently.
def check_surfaces(root):
    assert len(HASHES) == 22, 'The approved source fixture is incomplete'
    for relative, wanted in HASHES.items():
        with (root / relative).open('rb') as stream:
            actual = hashlib.file_digest(stream, 'sha256').hexdigest()
        assert actual == wanted, ('Approved merchant asset changed', relative)
    script = (root / 'materials/scripts/MerchantApproved.material').read_text(encoding='utf-8')
    credits = (root / 'CREDITS').read_text(encoding='utf-8')
    for family, size in ATLASES.items():
        block = re.search(r'^material MerchantApproved' + family + r'\s*\n\{.*?^}', script, re.M | re.S)
        assert block and 'normal_map tangent_space' in block.group(), family
        for kind in ('Color', 'Normal'):
            name = 'Merchant' + family + 'Approved' + kind + '.png'
            assert 'texture ' + name in block.group(), name
            relative = 'materials/textures/' + name
            with (root / relative).open('rb') as stream:
                header = stream.read(33)
            assert header[:8] == b'\x89PNG\r\n\x1a\n', name
            assert struct.unpack('>II', header[16:24]) == (size, size), name
            assert relative in credits, name
    for source in ('Fabric062', 'Fabric066', 'Leather014'):
        assert 'https://ambientcg.com/view?id=' + source in credits, source


# Stream the detailed mesh to keep validation memory bounded while checking every vertex and triangle.
def check_mesh(path):
    totals = array('f', [0.0]) * VERTICES
    influences = array('B', [0]) * VERTICES
    counts = dict(position=0, normal=0, tangent=0, texcoord=0, face=0)
    minimum = [math.inf] * 3
    maximum = [-math.inf] * 3
    materials = set()
    skeleton = None
    stack = []
    for event, element in ET.iterparse(path, events=('start', 'end')):
        tag = element.tag
        if event == 'start':
            stack.append(element)
            if tag == 'sharedgeometry':
                assert int(element.get('vertexcount')) == VERTICES
            elif tag == 'submesh':
                materials.add(element.get('material'))
            continue
        if tag in ('position', 'normal', 'tangent'):
            value = [float(element.get(axis)) for axis in 'xyz']
            assert all(math.isfinite(v) for v in value), tag
            if tag == 'position':
                minimum = [min(a, b) for a, b in zip(minimum, value)]
                maximum = [max(a, b) for a, b in zip(maximum, value)]
            else:
                assert abs(math.sqrt(sum(v*v for v in value)) - 1.0) < .005, tag
                if tag == 'tangent':
                    assert abs(abs(float(element.get('w'))) - 1.0) < .001
        elif tag == 'texcoord':
            assert all(-.0001 <= float(element.get(axis)) <= 1.0001 for axis in ('u', 'v'))
        elif tag == 'face':
            assert all(0 <= int(element.get(axis)) < VERTICES for axis in ('v1', 'v2', 'v3'))
        elif tag == 'vertexboneassignment':
            index = int(element.get('vertexindex')); bone = int(element.get('boneindex'))
            weight = float(element.get('weight'))
            assert 0 <= index < VERTICES and 0 <= bone < 20
            assert math.isfinite(weight) and 0 < weight <= 1
            totals[index] += weight; influences[index] += 1
        elif tag == 'skeletonlink':
            skeleton = element.get('name')
        if tag in counts:
            counts[tag] += 1
        element.clear()
        stack.pop()
        if stack:
            stack[-1].remove(element)
    assert counts == dict(position=VERTICES, normal=VERTICES, tangent=VERTICES,
                          texcoord=VERTICES, face=TRIANGLES), counts
    assert materials == {'MerchantApproved' + name for name in ATLASES}, materials
    assert all(abs(a-b) < .00002 for a, b in zip(minimum, MINIMUM)), minimum
    assert all(abs(a-b) < .00002 for a, b in zip(maximum, MAXIMUM)), maximum
    assert skeleton == 'Merchant.skeleton'
    assert all(abs(v-1) < .001 for v in totals), 'Every vertex must remain bound'
    assert all(1 <= v <= 4 for v in influences), 'Unsupported skin influence count'


# Preserve all game-driven clips, fitted joint hierarchy, finite poses and closed animation loops.
def check_skeleton(path):
    tree = ET.parse(path).getroot()
    bones = tree.findall('./bones/bone')
    assert tuple(b.get('name') for b in bones) == BONES
    parents = {p.get('bone'): p.get('parent') for p in tree.findall('./bonehierarchy/boneparent')}
    assert parents['Scales'] == 'Pelvis', 'Balance scales must remain at the belt'
    root = bones[0].find('position')
    assert abs(float(root.get('x'))-.64) < .00001
    assert abs(float(root.get('y'))+.76) < .00001
    clips = tree.findall('./animations/animation')
    assert {c.get('name'): float(c.get('length')) for c in clips} == CLIPS
    for clip in clips:
        tracks = clip.findall('./tracks/track')
        assert {t.get('bone') for t in tracks} == set(BONES)
        for track in tracks:
            keys = track.findall('./keyframes/keyframe')
            assert len(keys) >= 25, (clip.get('name'), track.get('bone'))
            times = [float(k.get('time')) for k in keys]
            assert times[0] == 0 and abs(times[-1]-float(clip.get('length'))) < .00001
            assert all(a < b for a, b in zip(times, times[1:]))
            for key in keys:
                for element in key.iter():
                    assert all(math.isfinite(float(v)) for v in element.attrib.values())
            for tag, attributes in (('translate', 'xyz'), ('scale', 'xyz')):
                first = keys[0].find(tag); last = keys[-1].find(tag)
                assert all(abs(float(first.get(axis))-float(last.get(axis))) < .0001 for axis in attributes)
            assert abs(float(keys[0].find('rotate').get('angle')) - float(keys[-1].find('rotate').get('angle'))) < .0001


# Verify the current accepted replacement without loading its large XML into a second in-memory tree.
def verify_approved_merchant(root):
    root = Path(root)
    started = time.perf_counter()
    check_surfaces(root)
    with tempfile.TemporaryDirectory(prefix='approved-merchant-') as temporary:
        directory = Path(temporary)
        mesh = deserialize(root, 'Merchant.mesh', directory)
        skeleton = deserialize(root, 'Merchant.skeleton', directory)
        prepared = time.perf_counter()
        print('ODP_TEST_PHASE ' + json.dumps({'name': 'setup', 'seconds': prepared-started}))
        check_mesh(mesh)
        check_skeleton(skeleton)
        print('ODP_TEST_PHASE ' + json.dumps({'name': 'native asset validation', 'seconds': time.perf_counter()-prepared}))
