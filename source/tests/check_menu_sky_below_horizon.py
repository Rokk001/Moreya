#!/usr/bin/env python3
"""Checks that no main menu view shows sky below the horizon (no compile needed).

Every named camera pose of config/mainmenuscene.cfg and samples of every menu flight (outward routes, their
reversed return routes and the arrival, sampled like RenderSceneMenu::samplePath with the slerped view
rotation) are rendered in software: the triangles of every AddEntity mesh at its configured position are
projected with the menu projection of CameraManager::setViewportSize and rasterised into a coverage image.
Sky dome, horizon and cloud materials and blended materials do not cover a pixel; back faces of culled
materials do not either. A pixel whose view ray points below the horizon and that no scenery covers shows
the sky dome (or nothing) where ground belongs, and fails the check.

The frame is rendered at the narrowest supported aspect (5:4). The menu projection keeps the horizontal
16:9 field of view and widens the vertical one for narrower windows, so this frame contains the views of
every supported window from 5:4 to 16:9.

Options: --dump <folder> writes one mask image per view (grey = scenery, blue = sky above the horizon,
red = sky below the horizon); --only <view label prefix> renders only matching views.

The meshes and MenuScene.material live in content packages (found through scripts/content_packages.py); without the
content the check names them as not checked and renders nothing.
"""
import argparse
import math
import os
import re
import struct
import sys
import time

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import content_packages  # noqa: E402

CONFIG = os.path.join(ROOT, "config", "mainmenuscene.cfg")
MODELS = os.path.join(ROOT, "models")
#: The menu scene materials of the public tree or of a content package
MATERIALS = str(content_packages.resolve(ROOT, "materials/scripts/MenuScene.material"))
#: Atmosphere materials: they are the sky, never scenery (MenuCloud draws nothing, see MenuSky.frag).
SKY_MATERIALS = ("MenuSky", "MenuHorizonGlow", "MenuHorizonDark", "MenuCloud")
#: Glowing cracks and eyes are painted onto other surfaces; they never close a gap on their own.
DECAL_MATERIALS = ("MenuEmberCrack", "MenuLavaCrack", "MenuGateEyes")
#: CameraManager: MAIN_MENU_DEFAULT_FOV_Y_DEGREES at MAIN_MENU_REFERENCE_ASPECT_RATIO, near and far clip of the RTS camera.
MENU_FOV_Y_DEGREES = 45.0
MENU_REFERENCE_ASPECT = 16.0 / 9.0
NEAR_CLIP = 0.02
FAR_CLIP = 300.0
#: Narrowest supported window aspect; its frame contains the frames of all wider windows up to 16:9.
CHECK_ASPECT = 5.0 / 4.0
WIDTH = 250
HEIGHT = 200
#: Flight samples per route segment between two waypoints (the waypoints themselves are the poses).
SAMPLES_PER_SEGMENT = 4


def chunks(data, offset, end):
    """Yields (id, payload start, chunk end) of the Ogre chunks between offset and end."""
    while offset + 6 <= end:
        chunk_id, length = struct.unpack_from("<HI", data, offset)
        yield chunk_id, offset + 6, offset + length
        offset += length


def read_positions(data, start, end):
    """Returns the vertex positions of one Ogre geometry chunk as an (n, 3) array."""
    count, = struct.unpack_from("<I", data, start)
    elements = []
    buffers = {}
    for chunk_id, s, e in chunks(data, start + 4, end):
        if chunk_id == 0x5100:
            for _, s3, _ in chunks(data, s, e):
                source, _, semantic, offset, _ = struct.unpack_from("<HHHHH", data, s3)
                elements.append((source, semantic, offset))
        elif chunk_id == 0x5200:
            bind, stride = struct.unpack_from("<HH", data, s)
            for kind, s3, _ in chunks(data, s + 4, e):
                if kind == 0x5210:
                    buffers[bind] = (stride, s3)
    source, _, offset = [x for x in elements if x[1] == 1][0]
    stride, base = buffers[source]
    raw = np.frombuffer(data, dtype=np.uint8, count=count * stride, offset=base).reshape(count, stride)
    return raw[:, offset:offset + 12].copy().view("<f4").reshape(count, 3).astype(np.float64)


def load_mesh(path):
    """Returns (vertices, triangles, material per triangle) of an Ogre binary mesh."""
    data = open(path, "rb").read()
    offset = data.index(b"\n") + 1
    vertices = []
    vertex_count = 0
    triangles = []
    materials = []
    for chunk_id, s, e in chunks(data, offset, len(data)):
        if chunk_id != 0x3000:
            continue
        shared = None
        shared_base = None
        subs = []
        for kind, s2, e2 in chunks(data, s + 1, e):
            if kind == 0x5000:
                shared = read_positions(data, s2, e2)
            elif kind == 0x4000:
                subs.append((s2, e2))
        for s2, e2 in subs:
            material = data[s2:data.index(b"\n", s2)].decode("ascii")
            p = data.index(b"\n", s2) + 1
            uses_shared = data[p]
            count, = struct.unpack_from("<I", data, p + 1)
            wide = data[p + 5]
            p += 6
            indices = np.frombuffer(data, dtype="<u4" if wide else "<u2", count=count, offset=p).astype(np.int64)
            p += count * (4 if wide else 2)
            if uses_shared:
                if shared_base is None:
                    shared_base = vertex_count
                    vertices.append(shared)
                    vertex_count += len(shared)
                base = shared_base
            else:
                base = vertex_count
                for kind, s3, e3 in chunks(data, p, e2):
                    if kind == 0x5000:
                        own = read_positions(data, s3, e3)
                        vertices.append(own)
                        vertex_count += len(own)
                        break
            usable = count - count % 3
            triangles.append(indices[:usable].reshape(-1, 3) + base)
            materials.extend([material] * (usable // 3))
    return (np.concatenate(vertices) if vertices else np.zeros((0, 3)),
            np.concatenate(triangles) if triangles else np.zeros((0, 3), dtype=np.int64), materials)


def material_flags(text):
    """Returns {material: (blended, double sided)} with the values inherited from parent materials of the file."""
    blocks = {}
    for match in re.finditer(r"^material\s+([\w/]+)\s*(?::\s*([\w/]+))?\s*\{", text, re.M):
        depth = 1
        end = match.end()
        while depth:
            depth += (text[end] == "{") - (text[end] == "}")
            end += 1
        blocks[match.group(1)] = (match.group(2), text[match.end():end])

    def flags(name):
        parent, body = blocks[name]
        blended, double = flags(parent) if parent in blocks else (False, False)
        blended = blended or re.search(r"\bscene_blend\s+(add|alpha_blend|modulate|colour_blend)\b|\bdepth_write\s+off\b"
                                       r"|\balpha_rejection\b", body) is not None
        double = double or re.search(r"\bcull_hardware\s+none\b", body) is not None
        return blended, double

    return {name: flags(name) for name in blocks}


def parse_config():
    """Returns (entities [(mesh, position)], poses {name: (position, rotation degrees)}, flights {name: waypoints})."""
    entities = []
    poses = {}
    flights = {}
    for line in open(CONFIG, encoding="utf-8"):
        words = line.split()
        if not words or words[0].startswith("#"):
            continue
        if words[0] == "AddEntity":
            entities.append((words[2], np.array([float(v) for v in words[3:6]])))
        elif words[0] == "Pose":
            values = [float(v) for v in words[2:8]]
            poses[words[1]] = (np.array(values[:3]), values[3:6])
        elif words[0] == "Flight":
            flights[words[1]] = words[3:]
        elif words[0] == "FlightFrom":
            # A route that starts at another place: its start place goes first (see views)
            flights[words[1]] = ["@" + words[2]] + words[4:]
    return entities, poses, flights


def outward_chain(name, flights):
    """Returns the pose names from the overview to a place, through the start place of a FlightFrom route."""
    waypoints = flights[name]
    if waypoints and waypoints[0].startswith("@"):
        return outward_chain(waypoints[0][1:], flights) + waypoints[1:]
    return ["overview"] + waypoints


def quaternion(axis, degrees):
    """Returns the (w, x, y, z) quaternion of a rotation about a unit axis."""
    half = math.radians(degrees) * 0.5
    return np.array([math.cos(half)] + [math.sin(half) * a for a in axis])


def multiply(a, b):
    """Returns the Hamilton product a * b of two (w, x, y, z) quaternions."""
    w1, x1, y1, z1 = a
    w2, x2, y2, z2 = b
    return np.array([w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2, w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
                     w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2, w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2])


def pose_orientation(rotation):
    """Returns the orientation RenderSceneMenu builds from a Pose line (local X, then Y, then Z degrees)."""
    return multiply(multiply(quaternion((1, 0, 0), rotation[0]), quaternion((0, 1, 0), rotation[1])),
                    quaternion((0, 0, 1), rotation[2]))


def slerp(t, a, b):
    """Returns Ogre::Quaternion::Slerp(t, a, b, shortestPath = true)."""
    cosine = float(np.dot(a, b))
    if cosine < 0:
        cosine = -cosine
        b = -b
    if abs(cosine) < 1 - 1e-3:
        angle = math.acos(cosine)
        result = (math.sin((1 - t) * angle) * a + math.sin(t * angle) * b) / math.sin(angle)
    else:
        result = (1 - t) * a + t * b
    return result / np.linalg.norm(result)


def matrix(q):
    """Returns the rotation matrix of a (w, x, y, z) quaternion; its columns are the local axes in the world."""
    w, x, y, z = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
                     [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
                     [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)]])


def sample_path(points, progress):
    """Returns the (position, orientation) of RenderSceneMenu::samplePath at a progress in [0, 1]."""
    if progress >= 1.0:
        return points[-1]
    coordinate = max(0.0, progress) * (len(points) - 1)
    index = min(int(coordinate), len(points) - 2)
    t = coordinate - index
    first, second = points[index][0], points[index + 1][0]
    before = points[max(index - 1, 0)][0]
    after = points[min(index + 2, len(points) - 1)][0]
    position = 0.5 * ((2 * first) + (-before + second) * t + (2 * before - 5 * first + 4 * second - after) * t * t
                      + (-before + 3 * first - 3 * second + after) * t * t * t)
    return position, slerp(t, points[index][1], points[index + 1][1])


def views(poses, flights):
    """Yields (label, position, orientation) for every named pose and the inner samples of every flight."""
    oriented = {name: (position, pose_orientation(rotation)) for name, (position, rotation) in poses.items()}
    for name, view in oriented.items():
        yield "pose " + name, view[0], view[1]
    routes = []
    for name, waypoints in flights.items():
        if name == "overview":
            continue
        if name == "arrival":
            routes.append(("flight arrival", ["arrival"] + waypoints))
            continue
        chain = outward_chain(name, flights)
        # A FlightFrom route flies from its start place and returns through it to the overview
        outward = [waypoints[0][1:]] + waypoints[1:] if waypoints and waypoints[0].startswith("@") else chain
        routes.append(("flight " + name + " out", outward))
        routes.append(("flight " + name + " back", list(reversed(chain))))
    # A return route runs the same curve backwards, so its samples repeat the outward ones and are rendered once.
    seen = set()
    for label, names in routes:
        points = [oriented[name] for name in names]
        steps = (len(points) - 1) * SAMPLES_PER_SEGMENT
        for step in range(1, steps):
            if step % SAMPLES_PER_SEGMENT == 0:
                continue
            position, orientation = sample_path(points, step / float(steps))
            key = tuple(np.round(position, 3)) + tuple(np.round(orientation * np.sign(orientation[0] or 1), 4))
            if key in seen:
                continue
            seen.add(key)
            yield "%s %.2f" % (label, step / float(steps)), position, orientation


def model_path(mesh):
    """Returns the mesh file of models/ of the public tree or of a content package (else the path below models/)."""
    return str(content_packages.resolve(ROOT, "models/" + mesh))


def missing_content():
    """Returns the scene files (MenuScene.material and the meshes of the AddEntity lines) that are not present because
    the content is not present; empty with the content."""
    if content_packages.has_content(ROOT):
        return []
    entities, _, _ = parse_config()
    needed = ["materials/scripts/MenuScene.material"] + ["models/" + mesh for mesh in sorted(set(m for m, _ in entities))]
    return [relative for relative in needed if content_packages.data_file(ROOT, relative) is None]


def load_scene():
    """Returns the world triangles (n, 3, 3) of the scene that can cover the sky and their double-sided flags."""
    flags = material_flags(open(MATERIALS, encoding="utf-8").read())
    entities, poses, flights = parse_config()
    cache = {}
    triangles = []
    double = []
    for mesh, position in entities:
        if mesh not in cache:
            vertices, faces, materials = load_mesh(model_path(mesh))
            keep = np.array([m not in SKY_MATERIALS and m not in DECAL_MATERIALS and not flags.get(m, (False, False))[0]
                             for m in materials], dtype=bool)
            sided = np.array([flags.get(m, (False, False))[1] for m in materials], dtype=bool)
            cache[mesh] = (vertices[faces[keep]] if len(faces) else np.zeros((0, 3, 3)), sided[keep] if len(faces) else sided)
        tri, sided = cache[mesh]
        triangles.append((tri + position).astype(np.float32))
        double.append(sided)
    return np.concatenate(triangles), np.concatenate(double), poses, flights


def group_chunks(triangles, double, cell=6.0):
    """Sorts the triangles into spatial cells; returns (triangles, double, cell starts, cell centres, cell radii)."""
    centroid = triangles.mean(axis=1)
    keys = np.floor(centroid / cell).astype(np.int64)
    key = (keys[:, 0] + 4096) * 67108864 + (keys[:, 1] + 4096) * 8192 + (keys[:, 2] + 4096)
    order = np.argsort(key, kind="stable")
    triangles, double, key = triangles[order], double[order], key[order]
    starts = np.concatenate([[0], np.nonzero(np.diff(key))[0] + 1, [len(key)]])
    centres = np.array([triangles[a:b].reshape(-1, 3).mean(axis=0) for a, b in zip(starts[:-1], starts[1:])])
    radii = np.array([np.linalg.norm(triangles[a:b].reshape(-1, 3) - centre, axis=1).max()
                      for a, b, centre in zip(starts[:-1], starts[1:], centres)])
    return triangles, double, starts, centres, radii


def clip_near(camera_triangles):
    """Clips camera-space triangles (depth along +z) at the near plane.

    Returns (triangles, index of the source triangle of each result triangle).
    """
    result = []
    source = []
    for number, triangle in enumerate(camera_triangles):
        polygon = []
        for index in range(3):
            a = triangle[index]
            b = triangle[(index + 1) % 3]
            if a[2] >= NEAR_CLIP:
                polygon.append(a)
            if (a[2] >= NEAR_CLIP) != (b[2] >= NEAR_CLIP):
                t = (NEAR_CLIP - a[2]) / (b[2] - a[2])
                polygon.append(a + (b - a) * t)
        for index in range(1, len(polygon) - 1):
            result.append((polygon[0], polygon[index], polygon[index + 1]))
            source.append(number)
    return np.array(result, dtype=camera_triangles.dtype).reshape(-1, 3, 3), np.array(source, dtype=np.int64)


def _open_pixels(cover, left, right, top, bottom):
    """Returns the number of still uncovered pixels inside each bounding box (summed-area table)."""
    table = np.zeros((cover.shape[0] + 1, cover.shape[1] + 1), dtype=np.int64)
    table[1:, 1:] = np.cumsum(np.cumsum(~cover, axis=0), axis=1)
    return table[bottom + 1, right + 1] - table[top, right + 1] - table[bottom + 1, left] + table[top, left]


def _fill(x, y, area, left, top, right, bottom, part, size, cover):
    """Marks the pixel centres inside the triangles part, whose bounding boxes are at most size pixels wide."""
    offset_y, offset_x = np.mgrid[0:size, 0:size]
    px = left[part, None] + offset_x.ravel()[None, :]
    py = top[part, None] + offset_y.ravel()[None, :]
    inside = (px <= right[part, None]) & (py <= bottom[part, None])
    sign = np.sign(area[part])[:, None]
    for a, b in ((0, 1), (1, 2), (2, 0)):
        ax, ay = x[part, a, None], y[part, a, None]
        bx, by = x[part, b, None], y[part, b, None]
        edge = ((bx - ax) * (py - ay) - (by - ay) * (px - ax)) * sign
        inside &= edge >= -1e-9 * np.abs(area[part, None])
    cover[py[inside], px[inside]] = True


def rasterise(screen, cover):
    """Marks every pixel centre covered by one of the screen triangles (n, 3, 2) in pixel coordinates.

    The largest triangles are drawn first; a smaller triangle whose bounding box is already fully covered
    cannot change the coverage and is skipped.
    """
    height, width = cover.shape
    x = screen[:, :, 0]
    y = screen[:, :, 1]
    area = (x[:, 1] - x[:, 0]) * (y[:, 2] - y[:, 0]) - (x[:, 2] - x[:, 0]) * (y[:, 1] - y[:, 0])
    left = np.maximum(np.ceil(x.min(axis=1) - 1e-6), 0).astype(np.int64)
    right = np.minimum(np.floor(x.max(axis=1) + 1e-6), width - 1).astype(np.int64)
    top = np.maximum(np.ceil(y.min(axis=1) - 1e-6), 0).astype(np.int64)
    bottom = np.minimum(np.floor(y.max(axis=1) + 1e-6), height - 1).astype(np.int64)
    usable = (left <= right) & (top <= bottom) & (np.abs(area) > 1e-12)
    span = np.maximum(right - left, bottom - top) + 1
    sizes = (1, 2, 4, 8, 16, 32, 64)
    for index in np.nonzero(usable & (span > sizes[-1]))[0]:
        _fill(x, y, area, left, top, right, bottom, np.array([index]), int(span[index]), cover)
    for number in range(len(sizes) - 1, -1, -1):
        size = sizes[number]
        smaller = sizes[number - 1] if number else 0
        group = np.nonzero(usable & (span > smaller) & (span <= size))[0]
        if len(group) == 0:
            continue
        group = group[_open_pixels(cover, left[group], right[group], top[group], bottom[group]) > 0]
        step = max(1, 400000 // (size * size))
        for start in range(0, len(group), step):
            _fill(x, y, area, left, top, right, bottom, group[start:start + step], size, cover)


def render(triangles, double, position, orientation, chunks=None):
    """Returns (coverage, below horizon) boolean images of one camera view.

    chunks (cell starts, centres, radii of group_chunks) lets whole cells outside the view frustum be skipped.
    """
    axes = matrix(orientation)
    half_y = math.atan(math.tan(math.radians(MENU_FOV_Y_DEGREES) * 0.5) * max(1.0, MENU_REFERENCE_ASPECT / CHECK_ASPECT))
    tan_y = math.tan(half_y)
    tan_x = tan_y * CHECK_ASPECT
    if chunks is not None:
        starts, centres, radii = chunks
        offset = centres - position
        cx, cy, cz = offset @ axes[:, 0], offset @ axes[:, 1], -(offset @ axes[:, 2])
        # Distance of each cell centre to the four side planes of the frustum (positive inside).
        inside = cz + radii >= NEAR_CLIP
        for slope, value in ((tan_x, cx), (tan_x, -cx), (tan_y, cy), (tan_y, -cy)):
            inside &= (slope * cz - value) / math.sqrt(1 + slope * slope) >= -radii
        cells = np.nonzero(inside)[0]
        lengths = starts[cells + 1] - starts[cells]
        index = np.repeat(starts[cells] - np.concatenate([[0], np.cumsum(lengths)[:-1]]), lengths) + np.arange(lengths.sum())
        triangles = triangles[index]
        double = double[index]
    relative = triangles - position.astype(np.float32)
    axes32 = axes.astype(np.float32)
    # Camera space: x right, y up, z depth along the view direction (the camera looks down its local -Z).
    camera = np.stack([relative @ axes32[:, 0], relative @ axes32[:, 1], -(relative @ axes32[:, 2])], axis=-1)
    depth = camera[:, :, 2]
    ahead = (depth >= NEAR_CLIP).sum(axis=1)
    whole = camera[ahead == 3]
    whole_double = double[ahead == 3]
    clipped_source = ahead % 3 != 0
    clipped, origin = clip_near(camera[clipped_source])
    camera = np.concatenate([whole, clipped])
    sided = np.concatenate([whole_double, double[clipped_source][origin]])
    ndc_x = camera[:, :, 0] / (camera[:, :, 2] * tan_x)
    ndc_y = camera[:, :, 1] / (camera[:, :, 2] * tan_y)
    visible = ~((ndc_x > 1).all(axis=1) | (ndc_x < -1).all(axis=1) | (ndc_y > 1).all(axis=1) | (ndc_y < -1).all(axis=1)
                | (camera[:, :, 2] > FAR_CLIP).all(axis=1))
    # Ogre culls clockwise triangles on screen (y up) unless the material sets cull_hardware none.
    facing = (ndc_x[:, 1] - ndc_x[:, 0]) * (ndc_y[:, 2] - ndc_y[:, 0]) - (ndc_x[:, 2] - ndc_x[:, 0]) * (ndc_y[:, 1] - ndc_y[:, 0])
    visible &= sided | (facing > 0)
    screen = np.stack([(ndc_x[visible] + 1) * 0.5 * WIDTH - 0.5, (1 - ndc_y[visible]) * 0.5 * HEIGHT - 0.5], axis=-1).astype(np.float64)
    cover = np.zeros((HEIGHT, WIDTH), dtype=bool)
    rasterise(screen, cover)
    columns = ((np.arange(WIDTH) + 0.5) / WIDTH * 2 - 1) * tan_x
    rows = (1 - (np.arange(HEIGHT) + 0.5) / HEIGHT * 2) * tan_y
    # World height component of every pixel ray: right * x + up * y - back.
    rise = axes[2, 0] * columns[None, :] + axes[2, 1] * rows[:, None] - axes[2, 2]
    return cover, rise < 0


def write_mask(path, cover, below):
    """Writes the mask image of one view (grey scenery, blue sky above, red sky below the horizon)."""
    from PIL import Image
    image = np.zeros(cover.shape + (3,), dtype=np.uint8)
    image[cover] = (90, 90, 90)
    image[~cover & ~below] = (40, 70, 160)
    image[~cover & below] = (230, 20, 20)
    Image.fromarray(image).save(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dump", help="folder for one mask image per view")
    parser.add_argument("--only", default="", help="render only views whose label starts with this text")
    args = parser.parse_args()
    missing = missing_content()
    if missing:
        content_packages.unchecked("check_menu_sky_below_horizon", missing)
        return 0
    started = time.monotonic()
    triangles, double, poses, flights = load_scene()
    triangles, double, starts, centres, radii = group_chunks(triangles, double)
    print('ODP_TEST_PHASE {"name":"setup","seconds":%.2f}' % (time.monotonic() - started))
    started = time.monotonic()
    failures = []
    count = 0
    for label, position, orientation in views(poses, flights):
        if not label.startswith(args.only):
            continue
        cover, below = render(triangles, double, position, orientation, (starts, centres, radii))
        count += 1
        sky_below = ~cover & below
        if args.dump:
            os.makedirs(args.dump, exist_ok=True)
            write_mask(os.path.join(args.dump, label.replace(" ", "_") + ".png"), cover, below)
        if sky_below.any():
            rows, columns = np.nonzero(sky_below)
            failures.append("%s at (%.1f, %.1f, %.1f): %d of %d pixels show sky below the horizon (columns %d-%d, rows %d-%d)"
                            % (label, position[0], position[1], position[2], sky_below.sum(), sky_below.size,
                               columns.min(), columns.max(), rows.min(), rows.max()))
    print('ODP_TEST_PHASE {"name":"render","seconds":%.2f}' % (time.monotonic() - started))
    for line in failures:
        print("FAIL " + line)
    if failures:
        return 1
    if count == 0:
        print("FAIL no view rendered")
        return 1
    print("OK: %d menu views (%d poses and flight samples) show sky only above the horizon" % (count, count))
    return 0


if __name__ == "__main__":
    sys.exit(main())
