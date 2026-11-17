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
RENDER_REFERENCE = {  # zlib + base64 of the uint8 render of the innkeeper before the reduction (reviewed 2026-11-17)
    'game': ((150, 100, 3), (
        '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'
    )),
    'front': ((137, 100, 3), (
        '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'
        'AcWf3nrz+KEf/x+pRnka'
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
