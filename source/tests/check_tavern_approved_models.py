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
    # rendered again from the same pre-reduction mesh with the retextured atlases of INGAME-QS-11 K8 (owner decision
    # 2026-11-18 "Neues Referenzbild, Grenze 4,0"; measured game 2.31, front 3.89)
    'game': ((150, 100, 3), (
        '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'
        '0pa2tH+D/U+Ab2Yn'
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
