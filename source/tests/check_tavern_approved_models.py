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
    # (owner decision 2026-11-18 "Neues Referenzbild, Grenze 4,0"; measured game 2.14, front 3.37)
    'game': ((150, 100, 3), (
        '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'
    )),
    'front': ((137, 100, 3), (
        'eNrtnVd3XNeV5/3QFkmEQuWcc8455wQUcgZBAARBMUmiqGTLLfW01bZnPN29pqfDy0yvee1PMc/zseZ37iFraNqtlmZJMiDxrr1q'
        '3SoWTt37u3v/9973nCr+7Gdvt7fb2+3t9nZ7u73d3m5vtx/5Vo04Yi7jWw5fs9Vizpzf3Ii7ehl/1GkIO/Res9ptXHlL5o0tbNe1'
        'k95+xleLu5yGFa9F6zKo7Pplm06lW779ls98C1g15bDdZ9FEHXqTehFWPK4s3LJpl7XLdyzaJfXirbeUFI/Sl0L2uNvkM69kfJbu'
        'pB5Lh8qtXK6SjDgNNt3y8p13bPrlt6DYHLplPCrnt3bGtd60UW5mq51CtZ3vjKqVVi6WCRtXFvWqOyb1wk8cVMimRaYELrOmDZxm'
        'rtTIJnORWrfYnTQS2XA47g8nAoaVBVzLb9H+lEFlfZa42+jQq4brbfjUe8VqJ58tJ3qrTYiFE/56t0hI6lULZs0i8YiO/QRBJdzG'
        'kF2X9VuqUWe+mkrkIt1pvb9KDOYyxXipmS3WM0RioZZ2uK0mi96uV3nNGqtu2a5T/aRApb3mXMCa8pgARVXg9NhglS7Gm4PKdLtH'
        '3HVGtUavNN7oWB0mb8Dlj3iIQVFLmDUes+YnxapMZe409LJ+SgUcKVtOpgsxm9NsdZqDUa/OqAnFfb6QOxT3ewLOSCIATG/QRRgS'
        'rQHrT0u18KiM3wIrq3ap3i3BoTetQwalIuhwrVwp6fTaXD6H0aLPlZPegNPltVFouYwrGA72EwGVT4QKAWs+YI049VQF+UqyOSgj'
        '7JABC15EJKJgeJTb50CscDx/2BPLhGDlNqlhZVz5qdQPXpMaVnGXwWdWJzJhyLSGVTwHSa+0861hJZmLQi+aCkaSQV/IRVRa7Car'
        'w+zxU1zcseqWAlad86fRJ0bsOrQdvSIPJrKRUMxnsRsBQiE6WGtSZeUrqVqnuKJRubx2yi3owUqomcNMy6NT3UG4Ajbdjx5U0KYt'
        'he0ekzpo1cAKdWqPq/3VJq3NaKNd7xcrrTzO5vY7Gn2RB4FGEkTnocojrIzqxbBD7/gJSBZZLO424FdRp559mj7iTgm6SjwbbvbL'
        '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'
        'YwLKZzf+7O32597+LyAOYvw='
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
