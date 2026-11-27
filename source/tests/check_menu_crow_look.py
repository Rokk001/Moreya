"""Check the look of the four menu crows, made from the crow figure of the new figures (CS10a: the approved ragged dark
crow, Meshy model with its own rig and split-off wings). No compile, no game.

It tests the delivered assets, not constants:
- each crow mesh stays within the triangle budget of a small menu figure (about 50 pixels high in the menu camera);
- the plumage is shaggy: the head feathers reach below the head joint and the lower body feathers hang low over the legs;
- the plumage texture is dark warm black-brown with visible feather detail and opaque (no see-through wings);
- every surface of the crow uses the one textured crow material.
Fixed values counted once on content/cs10a-hand-menu (7 383 triangles per crow, head feather reach 0.053 below the head
joint, lowest body feather 0.195, texture luminance mean 44.6 and deviation 17.3, colour 48.8/43.0/42.2); the former
own crow (fix/ingame-qs-10-a8: 16 411 triangles, five materials and an alpha-cut feather atlas) was replaced in CS10a.
The material, the textures and the crow meshes live in content packages (found through scripts/content_packages.py);
without the content the check names them as not checked and starts no converter.
"""
from pathlib import Path
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / 'scripts'))
import content_packages  # noqa: E402

#: The game data files the check reads
CONTENT_FILES = (['materials/scripts/MenuScene.material', 'materials/textures/menu/MenuCrowMeshy.png'] +
                 ['models/MenuCrow' + crow + suffix for crow in 'ABCD' for suffix in ('.mesh', '.skeleton')])
missing = [relative for relative in CONTENT_FILES if content_packages.data_file(root, relative) is None]
if missing and not content_packages.has_content(root):
    content_packages.unchecked('check_menu_crow_look', missing)
    sys.exit(0)
converter = os.environ.get('OGRE_XML_CONVERTER', 'OgreXMLConverter')
output = root / 'out/menu-crow-look'
output.mkdir(parents=True, exist_ok=True)
scene = content_packages.read_text(root, 'materials/scripts/MenuScene.material')


def texture(name):
    """The menu texture of the public tree or of a content package."""
    return content_packages.resolve(root, 'materials/textures/menu/' + name)


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


# Material: the one crow material is textured with the crow's colour texture.
crow_material = material_block('MenuCrowMeshy')
assert 'MenuCrowMeshy.png' in crow_material, 'the crow material must carry the crow texture'

# Plumage texture: dark warm colour with visible feather detail, opaque so the wings never become see-through.
atlas, opaque, mean, detail = luminance_detail(texture('MenuCrowMeshy.png'))
assert opaque.mean() >= 0.999, ('the plumage texture must be opaque', opaque.mean())
assert 30.0 <= mean <= 60.0, ('plumage must stay dark', mean)
assert detail >= 10.0, ('plumage needs visible feather detail', detail)
rgb = atlas[..., :3][opaque].mean(0)
assert rgb[0] > rgb[1] >= rgb[2], ('plumage must be warm black-brown, not neutral grey', rgb)

# Meshes: triangle budget, materials, shaggy plumage.
for crow in 'ABCD':
    mesh = content_packages.resolve(root, 'models/MenuCrow' + crow + '.mesh')
    skeleton = content_packages.resolve(root, 'models/MenuCrow' + crow + '.skeleton')
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
    assert set(faces) == {'MenuCrowMeshy'}, (crow, set(faces))
    triangles = sum(len(f) for f in faces.values())
    assert 7000 <= triangles <= 8000, (crow, 'triangle budget', triangles)
    strongest = {}
    for assignment in geometry.findall('./boneassignments/vertexboneassignment'):
        vertex, weight = int(assignment.get('vertexindex')), float(assignment.get('weight'))
        if vertex not in strongest or strongest[vertex][1] < weight:
            strongest[vertex] = (bones[int(assignment.get('boneindex'))], weight)
    feathers = np.unique(faces['MenuCrowMeshy'])
    assert uvs[feathers].min() >= 0.0 and uvs[feathers].max() <= 1.0, crow
    joints = {}
    root_bones = ET.parse(skeleton_xml).getroot()
    for bone in root_bones.findall('./bones/bone'):
        joints[bone.get('name')] = bone
    parents = {link.get('bone'): link.get('parent') for link in root_bones.findall('./bonehierarchy/boneparent')}

    def joint_height(name):
        """Bind height of a joint, from the full bind transforms of its chain of parents."""
        rotation, position = np.eye(3), np.zeros(3)
        chain = []
        while name:
            chain.append(name)
            name = parents.get(name)
        for link in reversed(chain):
            bone = joints[link]
            local = np.array([float(bone.find('position').get(axis)) for axis in 'xyz'])
            turn = bone.find('rotation')
            axis = np.array([float(turn.find('axis').get(c)) for c in 'xyz'])
            axis = axis / (np.linalg.norm(axis) or 1.0)
            angle = float(turn.get('angle'))
            k = np.array([[0, -axis[2], axis[1]], [axis[2], 0, -axis[0]], [-axis[1], axis[0], 0]])
            turn_matrix = np.eye(3) + np.sin(angle) * k + (1 - np.cos(angle)) * k @ k
            position = position + rotation @ local
            rotation = rotation @ turn_matrix
        return position[2]
    head = [v for v in feathers if strongest[v][0] == 'Head']
    body = [v for v in feathers if strongest[v][0] in ('Root', 'chest')]
    reach = joint_height('Head') - positions[head, 2].min()
    assert reach >= 0.045, (crow, 'head feathers must hang below the head joint', reach)
    lowest = positions[body, 2].min()
    assert lowest <= 0.21, (crow, 'lower body feathers must hang low over the legs', lowest)
print('menu crow look passes the checks')
