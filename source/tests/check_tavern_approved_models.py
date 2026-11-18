#!/usr/bin/env python3
"""Check the approved tavern exports, their skinning and their runtime atlases.

Owner decision of 2026-11-17 on the triangle budget (INGAME-QS-10 A1c): the innkeeper goes from 248891 to 33291
triangles with no visible change from the game camera. His cloth (TavernHood, TavernCloth) was modelled as closed shells
of two layers 1-2 mm apart; the outer layer is kept and decimated and the inner one rebuilt as its reversed copy, so the
inside of hood, sleeves and apron stays drawn with back faces culled. Checked here on the delivered file:
  budget        20000 to 35000 triangles, counts per material fixed from the reviewed export
  inside drawn  at least INNKEEPER_MIN_REVERSED of the cloth triangles have a reversed twin on the same three vertex
                positions (export 0.779; a mesh with only the outer layer has 0)
  look          a small software render of the bind pose from the game camera and from the front (flat atlas colour,
                two-sided Lambert light, back faces culled like the game) differs from the stored render of the
                innkeeper before the reduction by a mean of at most RENDER_MAX_MEAN_DIFFERENCE per channel and covers
                its silhouette by at least RENDER_MIN_SILHOUETTE_OVERLAP (intersection over union)
"""

from array import array
import base64
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
import zlib

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
# Fixed counts and bounds measured from the native serializer round trip.
MESHES = {
    'Innkeeper': (46676, 33291,
                  (-0.23106, -0.130789, 0.00475032),
                  (0.230241, 0.318891, 0.790697),
                  {'TavernSkin', 'TavernHood', 'TavernCloth'}),
    'TavernCounter': (53071, 43424,
                     (-0.52, -0.338, 0.0),
                     (0.520001, 0.0549586, 0.412484),
                     {'TavernCounterWood', 'TavernRail', 'TavernSign'}),
}
ATLASES = {'TavernSkin': 2048, 'TavernHood': 2048, 'TavernCloth': 2048,
           'TavernCounterWood': 2048, 'TavernRail': 1024, 'TavernSign': 512}
CLIPS = {'Idle': 4.0, 'Pour': 2.0, 'Cheer': 2.0}
# Triangle budget of the innkeeper (owner decision 2026-11-17) and the reviewed export of package A1c
INNKEEPER_BUDGET = (20000, 35000)
INNKEEPER_TRIANGLES = {'TavernSkin': 17376, 'TavernHood': 6683, 'TavernCloth': 9232}
INNKEEPER_SHA256 = '9859b7b755971e6c7bd2ce462a8de6ddff83ea0ed65d3562b740ed06e44bd2dc'
INNKEEPER_CLOTH = ('TavernHood', 'TavernCloth')
INNKEEPER_MIN_REVERSED = 0.7      # cloth triangles with a reversed twin (export 0.779; before the reduction 0.0)
# Render comparison against the innkeeper before the reduction (bind pose, flat atlas colour, two-sided light)
RENDER_PIXEL = 0.006
RENDER_HALF_WIDTH = 0.3
RENDER_LIGHT = (-0.4, -0.6, 0.7)
RENDER_AMBIENT = 0.35
VIEWS = {'game': ((0.0, math.sin(math.radians(25)), -math.cos(math.radians(25))),
                  (0.0, math.cos(math.radians(25)), math.sin(math.radians(25))), -0.2, 0.7),
         'front': ((0.0, 1.0, 0.0), (0.0, 0.0, 1.0), 0.0, 0.82)}
RENDER_MAX_MEAN_DIFFERENCE = 4.0  # export: game 1.72, front 3.09
RENDER_MIN_SILHOUETTE_OVERLAP = 0.97  # export: game 0.988, front 0.994
RENDER_REFERENCE = {  # zlib + base64 of the uint8 render of the innkeeper before the reduction (reviewed 2026-11-17),
    # rendered again from the same pre-reduction mesh with the atlases of INGAME-QS-11 K8, parts coloured in Blender
    # (owner decision 2026-11-18 "Neues Referenzbild, Grenze 4,0"; measured game 1.92, front 2.91)
    'game': ((150, 100, 3), (
        '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'
        'LLHEEvsj7P8AJ79x3A=='
    )),
    'front': ((137, 100, 3), (
        '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'
    )),
}

# Keep the navigation footprint synchronized when the approved counter mesh is replaced.
catalog = (ROOT / 'source/gamemap/RoomObjectBounds.h').read_text(encoding='utf-8')
counter_row = re.search(r'\{"TavernCounter",\s*([^}]+)\}', catalog)
assert counter_row, 'TavernCounter navigation bounds missing'
counter_bounds = tuple(float(value.strip().removesuffix('f')) for value in counter_row[1].split(','))
counter_min, counter_max = MESHES['TavernCounter'][2:4]
assert len(counter_bounds) == 4 and all(abs(actual - expected) <= 0.00002 for actual, expected in
                                       zip(counter_bounds, (*counter_min[:2], *counter_max[:2]))), \
    ('TavernCounter navigation bounds differ from the approved mesh', counter_bounds)


# Deserialize the actual game file with a bounded native converter invocation.
def deserialize(name, directory):
    converter = os.environ.get('OGRE_XML_CONVERTER', 'OgreXMLConverter')
    target = directory / (name + '.xml')
    subprocess.run([converter, '-q', '-log', str(target) + '.log',
                    str(ROOT / 'models' / name), str(target)],
                   stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                   stderr=subprocess.PIPE, timeout=120, check=True)
    return target


# Stream large meshes and reject invalid geometry, UVs, tangents or skin weights.
def check_mesh(name, path):
    vertices, triangles, wanted_min, wanted_max, wanted_materials = MESHES[name]
    totals = array('f', [0.0]) * vertices
    counts = {tag: 0 for tag in ('position', 'normal', 'tangent', 'texcoord', 'face')}
    minimum = [math.inf] * 3
    maximum = [-math.inf] * 3
    materials = set()
    skeleton = None
    material = None
    points, uvs, faces = [], [], {}
    for event, element in ET.iterparse(path, events=('start', 'end')):
        tag = element.tag
        if event == 'start':
            if tag == 'sharedgeometry':
                assert int(element.get('vertexcount')) == vertices, name
            elif tag == 'submesh':
                material = element.get('material')
                materials.add(material)
                faces.setdefault(material, [])
            continue
        if tag in ('position', 'normal', 'tangent'):
            value = [float(element.get(axis)) for axis in 'xyz']
            assert all(math.isfinite(v) for v in value), (name, tag)
            if tag == 'position':
                minimum = [min(a, b) for a, b in zip(minimum, value)]
                maximum = [max(a, b) for a, b in zip(maximum, value)]
                points.append(value)
            elif tag == 'normal':
                assert abs(math.sqrt(sum(v * v for v in value)) - 1.0) < 0.005, name
            else:
                parity = float(element.get('w', '0'))
                assert abs(abs(parity) - 1.0) < 0.001, (name, 'tangent parity')
        elif tag == 'texcoord':
            assert all(-0.0001 <= float(element.get(axis)) <= 1.0001
                       for axis in ('u', 'v')), (name, 'atlas UV')
            uvs.append((float(element.get('u')), float(element.get('v'))))
        elif tag == 'face':
            triangle = tuple(int(element.get(axis)) for axis in ('v1', 'v2', 'v3'))
            assert all(0 <= index < vertices for index in triangle), (name, 'index')
            faces[material].append(triangle)
        elif tag == 'vertexboneassignment':
            index = int(element.get('vertexindex'))
            bone = int(element.get('boneindex'))
            weight = float(element.get('weight'))
            assert 0 <= index < vertices and 0 <= bone < 15, name
            assert math.isfinite(weight) and 0.0 < weight <= 1.0, name
            totals[index] += weight
        elif tag == 'skeletonlink':
            skeleton = element.get('name')
        if tag in counts:
            counts[tag] += 1
        element.clear()
    assert counts == dict(position=vertices, normal=vertices, tangent=vertices,
                          texcoord=vertices, face=triangles), (name, counts)
    assert materials == wanted_materials, (name, materials)
    assert all(abs(a - b) < 0.00002 for a, b in zip(minimum, wanted_min)), name
    assert all(abs(a - b) < 0.00002 for a, b in zip(maximum, wanted_max)), name
    if name == 'Innkeeper':
        assert skeleton == 'Innkeeper.skeleton'
        assert all(abs(value - 1.0) < 0.001 for value in totals), 'Unweighted skin vertex'
    else:
        assert skeleton is None and not any(totals), 'The counter must remain static'
    return {'points': np.array(points, dtype=np.float64), 'uvs': np.array(uvs, dtype=np.float64), 'faces': faces}


# Triangle budget of the owner decision of 2026-11-17: total in range, fixed counts per material, delivered file unchanged.
def check_innkeeper_budget(mesh):
    counts = {material: len(triangles) for material, triangles in mesh['faces'].items()}
    assert counts == INNKEEPER_TRIANGLES, ('innkeeper triangles per material', counts)
    total = sum(counts.values())
    assert INNKEEPER_BUDGET[0] <= total <= INNKEEPER_BUDGET[1], ('innkeeper outside the triangle budget', total)
    with (ROOT / 'models' / 'Innkeeper.mesh').open('rb') as stream:
        digest = hashlib.sha256(stream.read()).hexdigest()
    assert digest == INNKEEPER_SHA256, 'models/Innkeeper.mesh differs from the reviewed export'


# Canonical key of a triangle given by three corner positions (the same for every rotation of the corner order).
def triangle_key(corners):
    first = corners.index(min(corners))
    return tuple(corners[first:] + corners[:first])


# The inside of hood, sleeves and apron stays drawn with back faces culled: most cloth triangles have a twin on the same
# three vertex positions with the opposite winding. Returns the measured fraction.
def check_innkeeper_inside(mesh):
    points = [tuple(point) for point in np.round(mesh['points'], 6).tolist()]
    cloth = [t for material in INNKEEPER_CLOTH for t in mesh['faces'][material]]
    keys = set(triangle_key([points[a], points[b], points[c]]) for a, b, c in cloth)
    twins = sum(triangle_key([points[a], points[c], points[b]]) in keys for a, b, c in cloth)
    fraction = twins / max(len(cloth), 1)
    assert fraction >= INNKEEPER_MIN_REVERSED, ('the inside of the innkeeper cloth is not drawn', fraction)
    return fraction


# Colour of every triangle: its material's colour atlas at the triangle's UV centre (Ogre v runs downwards).
def triangle_colours(mesh):
    script = (ROOT / 'materials/scripts/TavernObjects.material').read_text(encoding='utf-8')
    colours, triangles = [], []
    for material in sorted(mesh['faces']):
        block = re.search(r'^material ' + material + r'\s*\n\{.*?^}', script, re.M | re.S).group()
        texture = re.search(r'texture\s+(\S+Color\.png)', block).group(1)
        image = np.asarray(Image.open(ROOT / 'materials/textures/tavern' / texture).convert('RGB'), dtype=np.float64)
        tri = np.array(mesh['faces'][material], dtype=np.int64)
        uv = mesh['uvs'][tri].mean(1)
        h, w = image.shape[:2]
        colours.append(image[np.clip((uv[:, 1] * h).astype(int), 0, h - 1), np.clip((uv[:, 0] * w).astype(int), 0, w - 1)])
        triangles.append(tri)
    return np.concatenate(triangles), np.concatenate(colours)


# Small depth-buffered orthographic render of the bind pose: flat atlas colour times a two-sided Lambert light, back
# faces culled (counter-clockwise front faces, as the game draws them).
def render_view(points, triangles, colours, view):
    forward, up, low, high = VIEWS[view]
    forward = np.array(forward) / np.linalg.norm(forward)
    up = np.array(up) / np.linalg.norm(up)
    right = np.cross(forward, up)
    width = int(round(2 * RENDER_HALF_WIDTH / RENDER_PIXEL))
    height = int(round((high - low) / RENDER_PIXEL))
    sx = (points @ right + RENDER_HALF_WIDTH) / RENDER_PIXEL
    sy = (high - points @ up) / RENDER_PIXEL
    depth_of = points @ forward
    light = np.array(RENDER_LIGHT) / np.linalg.norm(RENDER_LIGHT)
    image = np.zeros((height, width, 3))
    depth = np.full((height, width), np.inf)
    a, b, c = points[triangles[:, 0]], points[triangles[:, 1]], points[triangles[:, 2]]
    normal = np.cross(b - a, c - a)
    normal /= np.maximum(np.linalg.norm(normal, axis=1), 1e-12)[:, None]
    shade = RENDER_AMBIENT + (1 - RENDER_AMBIENT) * np.abs(normal @ light)
    facing = normal @ forward < 0
    for k, (i, j, l) in enumerate(triangles):
        if not facing[k]:
            continue
        xs = (sx[i], sx[j], sx[l])
        ys = (sy[i], sy[j], sy[l])
        x0, x1 = max(int(math.floor(min(xs))), 0), min(int(math.ceil(max(xs))), width - 1)
        y0, y1 = max(int(math.floor(min(ys))), 0), min(int(math.ceil(max(ys))), height - 1)
        if x0 > x1 or y0 > y1:
            continue
        area = (xs[1] - xs[0]) * (ys[2] - ys[0]) - (xs[2] - xs[0]) * (ys[1] - ys[0])
        if abs(area) < 1e-12:
            continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        w1 = ((gx - xs[0]) * (ys[2] - ys[0]) - (xs[2] - xs[0]) * (gy - ys[0])) / area
        w2 = ((xs[1] - xs[0]) * (gy - ys[0]) - (gx - xs[0]) * (ys[1] - ys[0])) / area
        w0 = 1 - w1 - w2
        inside = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
        if not inside.any():
            continue
        z = w0 * depth_of[i] + w1 * depth_of[j] + w2 * depth_of[l]
        block = depth[y0:y1 + 1, x0:x1 + 1]
        nearer = inside & (z < block)
        block[nearer] = z[nearer]
        image[y0:y1 + 1, x0:x1 + 1][nearer] = colours[k] * shade[k]
    return np.clip(image, 0, 255).astype(np.uint8)


# Render comparison (owner decision on the triangle budget): the reduced innkeeper seen from the game camera and from
# the front differs from the reviewed render before the reduction by at most RENDER_MAX_MEAN_DIFFERENCE (mean absolute
# difference per channel, 0..255) and covers the same silhouette (intersection over union). Returns the measured values.
def check_innkeeper_render(mesh):
    triangles, colours = triangle_colours(mesh)
    measured = {}
    assert set(RENDER_REFERENCE) == set(VIEWS), 'a reference render is missing'
    for view, (shape, encoded) in RENDER_REFERENCE.items():
        reference = np.frombuffer(zlib.decompress(base64.b64decode(''.join(encoded))), dtype=np.uint8).reshape(shape)
        image = render_view(mesh['points'], triangles, colours, view)
        assert image.shape == reference.shape, (view, image.shape)
        difference = np.abs(image.astype(np.float64) - reference).mean()
        assert difference <= RENDER_MAX_MEAN_DIFFERENCE, ('the reduced innkeeper looks different', view, difference)
        a, b = image.any(-1), reference.any(-1)
        overlap = (a & b).sum() / max((a | b).sum(), 1)
        assert overlap >= RENDER_MIN_SILHOUETTE_OVERLAP, ('the reduced innkeeper has another silhouette', view, overlap)
        measured[view] = (round(float(difference), 2), round(float(overlap), 3))
    return measured


# Verify material references, atlas dimensions and the licensing of every new texture.
def check_atlases():
    script = (ROOT / 'materials/scripts/TavernObjects.material').read_text(encoding='utf-8')
    credits = (ROOT / 'CREDITS').read_text(encoding='utf-8')
    for material, size in ATLASES.items():
        block = re.search(r'^material ' + material + r'\s*\n\{.*?^}', script, re.M | re.S)
        assert block and 'normal_map tangent_space' in block.group(), material
        for kind in ('Color', 'Normal'):
            filename = material + 'Approved' + kind + '.png'
            relative = 'materials/textures/tavern/' + filename
            assert 'texture ' + filename in block.group(), filename
            with (ROOT / relative).open('rb') as stream:
                header = stream.read(33)
            assert header[:8] == b'\x89PNG\r\n\x1a\n', filename
            assert struct.unpack('>II', header[16:24]) == (size, size), filename
            assert relative in credits, filename


# Keep navigation at the approved counter's measured footprint after model replacements.
def check_counter_navigation_bounds():
    catalog = (ROOT / 'source/gamemap/RoomObjectBounds.h').read_text()
    row = re.search(r'\{"TavernCounter",\s*([^}]+)\}', catalog)
    assert row, 'TavernCounter missing from navigation catalog'
    actual = tuple(float(value.strip().removesuffix('f')) for value in row[1].split(','))
    minimum, maximum = MESHES['TavernCounter'][2:4]
    assert actual == (minimum[0], minimum[1], maximum[0], maximum[1]), \
        ('TavernCounter navigation must match the approved mesh', actual)


# Exercise the native assets, navigation footprint and existing innkeeper animation contracts.
def main():
    check_atlases()
    check_counter_navigation_bounds()
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix='tavern-assets-') as temporary:
        directory = Path(temporary)
        converted = {name: deserialize(name + '.mesh', directory) for name in MESHES}
        prepared = time.perf_counter()
        print('ODP_TEST_PHASE ' + json.dumps({'name': 'setup', 'seconds': prepared - started}))
        meshes = {name: check_mesh(name, path) for name, path in converted.items()}
        check_innkeeper_budget(meshes['Innkeeper'])
        inside = check_innkeeper_inside(meshes['Innkeeper'])
        look = check_innkeeper_render(meshes['Innkeeper'])
        skeleton = ET.parse(deserialize('Innkeeper.skeleton', directory)).getroot()
        assert len(skeleton.findall('./bones/bone')) == 15
        clips = {a.get('name'): float(a.get('length'))
                 for a in skeleton.findall('./animations/animation')}
        assert clips == CLIPS, clips
        for animation in skeleton.findall('./animations/animation'):
            assert animation.findall('./tracks/track/keyframes/keyframe'), animation.get('name')
        print('ODP_TEST_PHASE ' + json.dumps({'name': 'validation', 'seconds': time.perf_counter() - prepared}))
    print('check_tavern_approved_models: ok (2 native meshes, 15 bones, 3 clips, 12 atlases; innkeeper %d triangles, '
          'cloth inside %.3f, render difference/overlap %s)' % (sum(INNKEEPER_TRIANGLES.values()), inside, look))


if __name__ == '__main__':
    main()
