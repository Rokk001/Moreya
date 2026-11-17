"""Check the look of the four menu crows after the chosen heavy, dark, richly feathered crow. No compile, no game.

It tests the delivered assets, not constants:
- each crow mesh stays within the triangle budget of a small menu figure (about 50 pixels high in the menu camera);
- the plumage is shaggy: the throat hackles reach well below the eye and the lower body feathers hang over the thighs;
- the feather atlas is dark warm black-brown with ragged, cut-out vane margins but a closed vane centre (no see-through wings),
  and the plumage material cuts the margins out with alpha rejection;
- every surface material of the crow (plumage, legs, bill) is textured with visible surface detail.
Fixed values counted once on fix/ingame-qs-10-a8 (16 411 or 16 412 triangles per crow, throat reach 0.225, lowest body
feather 0.110; today's meshes of e64239497: 52 216 triangles, 0.184, 0.157).
"""
from pathlib import Path
import os
import re
import subprocess
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image

root = Path(__file__).resolve().parents[2]
converter = os.environ.get('OGRE_XML_CONVERTER', 'OgreXMLConverter')
output = root / 'out/menu-crow-look'
output.mkdir(parents=True, exist_ok=True)
scene = (root / 'materials/scripts/MenuScene.material').read_text(encoding='utf-8')
textures = root / 'materials/textures/menu'


def material_block(name):
    match = re.search(r'(?ms)^material ' + re.escape(name) + r'\b.*?^}', scene)
    assert match, name
    return match.group(0)


def luminance_detail(path):
    """Mean and standard deviation of the luminance of the opaque texels (sRGB 0..255)."""
    image = np.asarray(Image.open(path).convert('RGBA')).astype(float)
    opaque = image[..., 3] > 128
    lum = image[..., :3] @ np.array([0.299, 0.587, 0.114])
    return image, opaque, float(lum[opaque].mean()), float(lum[opaque].std())


# Materials: plumage with alpha-cut feather atlas, legs and bill textured.
black = material_block('MenuCrowBlack')
assert re.search(r'alpha_rejection greater 1[0-9]{2}', black), 'the feather margins must be cut out with alpha'
assert 'MenuCrowFeather.png' in black and 'MenuCrowFeatherNormal.png' in black
assert 'MenuCrowHorn.png' in material_block('MenuCrowBeak')
assert 'MenuCrowBill.png' in material_block('MenuCrowBill')

# Feather atlas: four cells, dark warm colour, ragged margins, closed centre.
atlas, opaque, mean, detail = luminance_detail(textures / 'MenuCrowFeather.png')
height, width = opaque.shape
assert 18.0 <= mean <= 40.0, ('plumage must stay dark', mean)
assert detail >= 4.0, ('plumage needs visible barb and sheen detail', detail)
rgb = atlas[..., :3][opaque].mean(0)
assert rgb[0] > rgb[1] > rgb[2], ('plumage must be warm black-brown, not neutral grey', rgb)
cell = width // 4
for index in range(4):
    part = opaque[:, index * cell:(index + 1) * cell]
    coverage = part.mean()
    assert 0.6 <= coverage <= 0.9, (index, 'feather coverage', coverage)
    # the vane centre between 10 and 85 percent of the length is closed, so the wings never become see-through
    centre = part[int(0.10 * height):int(0.85 * height), int(0.40 * cell):int(0.60 * cell)]
    assert centre.mean() >= 0.995, (index, 'holes in the vane centre', centre.mean())
    # ragged margin: along the outer quarter the vane opens and closes many times
    margin = part[int(0.10 * height):int(0.85 * height), int(0.12 * cell)]
    changes = int(np.count_nonzero(margin[1:] != margin[:-1]))
    assert changes >= 6, (index, 'margin is not ragged', changes)
for name in ('MenuCrowHorn.png', 'MenuCrowBill.png'):
    _, _, mean, detail = luminance_detail(textures / name)
    assert 20.0 <= mean <= 70.0, (name, 'horn must stay dark', mean)
    assert detail >= 1.5, (name, 'horn needs visible surface detail', detail)

# Meshes: triangle budget, materials, shaggy plumage.
for crow in 'ABCD':
    mesh = root / ('models/MenuCrow' + crow + '.mesh')
    skeleton = root / ('models/MenuCrow' + crow + '.skeleton')
    mesh_xml = output / (crow + '.mesh.xml')
    skeleton_xml = output / (crow + '.skeleton.xml')
    for source, target in ((mesh, mesh_xml), (skeleton, skeleton_xml)):
        subprocess.run([converter, '-q', str(source), str(target)], check=True, stdin=subprocess.DEVNULL,
                       stdout=subprocess.DEVNULL)
    geometry = ET.parse(mesh_xml).getroot()
    bones = [bone.get('name') for bone in ET.parse(skeleton_xml).getroot().findall('./bones/bone')]
    positions = np.array([[float(p.get(axis)) for axis in 'xyz']
                          for p in geometry.findall('./sharedgeometry/vertexbuffer/vertex/position')])
    uvs = np.array([[float(t.get('u')), float(t.get('v'))]
                    for t in geometry.findall('./sharedgeometry/vertexbuffer/vertex/texcoord')])
    faces = {}
    for submesh in geometry.findall('./submeshes/submesh'):
        faces[submesh.get('material')] = np.array([[int(f.get(k)) for k in ('v1', 'v2', 'v3')]
                                                   for f in submesh.findall('./faces/face')])
    assert set(faces) == {'MenuCrowBlack', 'MenuCrowBeak', 'MenuCrowBill', 'MenuCrowEye', 'MenuCrowPupil'}, (crow, set(faces))
    triangles = sum(len(f) for f in faces.values())
    assert 12000 <= triangles <= 17000, (crow, 'triangle budget', triangles)
    strongest = {}
    for assignment in geometry.findall('./boneassignments/vertexboneassignment'):
        vertex, weight = int(assignment.get('vertexindex')), float(assignment.get('weight'))
        if vertex not in strongest or strongest[vertex][1] < weight:
            strongest[vertex] = (bones[int(assignment.get('boneindex'))], weight)
    feathers = np.unique(faces['MenuCrowBlack'])
    assert uvs[feathers].min() >= 0.0 and uvs[feathers].max() <= 1.0, crow
    eye = positions[np.unique(faces['MenuCrowEye'])].mean(0)
    head = [v for v in feathers if strongest[v][0] == 'Head']
    body = [v for v in feathers if strongest[v][0] == 'Root']
    throat = eye[2] - positions[head, 2].min()
    assert throat >= 0.21, (crow, 'throat hackles must hang well below the eye', throat)
    lowest = positions[body, 2].min()
    assert lowest <= 0.13, (crow, 'lower body feathers must hang over the thighs', lowest)
print('menu crow look passes the checks')
