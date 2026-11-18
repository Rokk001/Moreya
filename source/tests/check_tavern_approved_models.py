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
    # 2026-11-18 "Neues Referenzbild, Grenze 4,0"; measured game 2.20, front 3.75)
    'game': ((150, 100, 3), (
        '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'
        'pS1taUtb2l9g/wsYcPvq'
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
