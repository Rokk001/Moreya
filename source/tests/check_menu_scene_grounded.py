#!/usr/bin/env python3
"""Checks that nothing of the main menu scene floats and that no scene surface is a flat untextured one.

No compile needed. Every AddEntity of config/mainmenuscene.cfg is loaded from its binary mesh at its configured
position (bind pose; the crows CrowA-CrowD stand at their perch positions, which are their configured positions).
The sky and horizon elements Backdrop, BloodMoon, HorizonCrows and VolcanicRuins belong in the air and are left out,
and so do the crows SkyCrow1-SkyCrow6 that fly through the moon sky (K17; check_menu_sky_crows checks their flights).

Grounding: the triangles of every mesh are split into connected parts (triangles sharing a vertex position). The
terrain is the largest part of MenuOuterGround (the ground rings and crags); a part whose vertex lies at most
GROUND_CONTACT above it stands on the ground. Every other part is sampled on its surface; two parts touch (rest on,
lean against, hang from or stick into each other) when their samples come closer than CONTACT, two parts of one model
already when they come closer than PIECE_CONTACT (the joints of a skeleton, the links of a chain). A part is carried
when a chain of touching parts leads to the ground; a part that no chain carries floats (a block, quad, window, stone or
banner hanging in the air) and fails the check.

Surfaces: a material without a texture is a flat untextured surface, unless it is a transparent or additive light
effect (scene_blend, such as the green spire beam) or one of the small glowing or coloured details of
DETAIL_MATERIALS (flames, glowing windows, eyes, lava and ember cracks, webs, the banner emblem, the spire glow); each
connected patch of such a detail must stay below DETAIL_MAX_AREA square metres.

Options: --report lists every floating part with its model, bounds, triangle count and materials.
"""
import argparse
import os
import re
import struct
import sys
import time

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CONFIG = os.path.join(ROOT, "config", "mainmenuscene.cfg")
MODELS = os.path.join(ROOT, "models")
MATERIAL_SCRIPTS = [os.path.join(ROOT, "materials", "scripts", name)
                    for name in ("MenuScene.material", "MenuSignpost.material")]
#: Sky and horizon elements that belong in the air (INGAME-QS-12 K1) and the crows flying in the sky (K17).
SKY_ENTITIES = ("Backdrop", "BloodMoon", "HorizonCrows", "VolcanicRuins",
                "SkyCrow1", "SkyCrow2", "SkyCrow3", "SkyCrow4", "SkyCrow5", "SkyCrow6")
#: The entity whose largest part is the terrain everything else must stand on.
TERRAIN_ENTITY = "OuterGround"
#: Parts closer than this many metres touch (mortar joints, eroded faces); parts up to about 2.6 times as far
#: apart may still count as touching.
CONTACT = 0.1
#: Parts of one model closer than this many metres belong to one piece (joints of a skeleton, links of a chain).
PIECE_CONTACT = 0.25
#: Spacing of the surface samples (below the contact cube size of twice CONTACT, so a surface leaves no gap in its cubes).
SAMPLE_STEP = 0.15
#: A part reaches the terrain when a vertex lies at most this far above it (the courtyard bedding ends 0.11 above it).
GROUND_CONTACT = 0.15
#: Untextured materials that are small glowing or coloured details, not surfaces.
DETAIL_MATERIALS = ("MenuWindowGlow", "MenuGateEyes", "MenuEmberCrack", "MenuLavaCrack", "MenuFlame", "MenuFlameCore",
                    "MenuSpireGlow", "MenuWeb", "MenuBannerSymbol", "MenuCrowEye", "MenuCrowPupil")
#: Largest area in square metres of one connected patch of a detail material (the glowing crypt door is the largest).
DETAIL_MAX_AREA = 6.0


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
    """Returns [(material, triangle corner positions (m, 3, 3))] of the submeshes of an Ogre binary mesh."""
    data = open(path, "rb").read()
    offset = data.index(b"\n") + 1
    result = []
    for chunk_id, s, e in chunks(data, offset, len(data)):
        if chunk_id != 0x3000:
            continue
        shared = None
        subs = []
        for kind, s2, e2 in chunks(data, s + 1, e):
            if kind == 0x5000:
                shared = read_positions(data, s2, e2)
            elif kind == 0x4000:
                subs.append((s2, e2))
        for s2, e2 in subs:
            line_end = data.index(b"\n", s2)
            material = data[s2:line_end].decode("ascii")
            p = line_end + 1
            uses_shared = data[p]
            count, = struct.unpack_from("<I", data, p + 1)
            wide = data[p + 5]
            p += 6
            indices = np.frombuffer(data, dtype="<u4" if wide else "<u2", count=count, offset=p).astype(np.int64)
            p += count * (4 if wide else 2)
            vertices = shared
            if not uses_shared:
                for kind, s3, e3 in chunks(data, p, e2):
                    if kind == 0x5000:
                        vertices = read_positions(data, s3, e3)
                        break
            result.append((material, vertices[indices[:count - count % 3].reshape(-1, 3)]))
    return result


def parse_config(path=CONFIG):
    """Returns (entities [(name, mesh, position)], poses {name: (position, rotation degrees)})."""
    entities = []
    poses = {}
    for line in open(path, encoding="utf-8"):
        words = line.split()
        if not words or words[0].startswith("#"):
            continue
        if words[0] == "AddEntity":
            entities.append((words[1], words[2], np.array([float(v) for v in words[3:6]])))
        elif words[0] == "Pose":
            values = [float(v) for v in words[2:8]]
            poses[words[1]] = (np.array(values[:3]), values[3:6])
    return entities, poses


def parse_materials(paths=MATERIAL_SCRIPTS):
    """Returns {material: "textured", "blended" (a transparent or additive light effect, no surface) or "flat"}."""
    blocks = {}
    for path in paths:
        text = open(path, encoding="utf-8").read()
        for match in re.finditer(r"^material\s+(\w+)\s*(?::\s*([\w/]+))?\s*\{", text, re.M):
            depth = 1
            end = match.end()
            while depth:
                depth += (text[end] == "{") - (text[end] == "}")
                end += 1
            block = text[match.end():end]
            blocks[match.group(1)] = (match.group(2), re.search(r"\btexture\s+\S+\.png", block) is not None,
                                      re.search(r"\bscene_blend\s+(add|alpha_blend)", block) is not None)
    kinds = {}
    for name in blocks:
        current = name
        kind = "flat"
        while current in blocks and kind == "flat":
            parent, has_texture, blended = blocks[current]
            kind = "textured" if has_texture else "blended" if blended else "flat"
            current = parent
        kinds[name] = kind
    return kinds


def triangle_parts(triangles):
    """Returns one part label per triangle: triangles that share a vertex position belong to the same part."""
    corners = triangles.reshape(-1, 3)
    _, vertex = np.unique(np.round(corners / 1e-4).astype(np.int64), axis=0, return_inverse=True)
    vertex = vertex.reshape(-1, 3)
    edges = np.concatenate([vertex[:, [0, 1]], vertex[:, [1, 2]]])
    return connected_labels(int(vertex.max()) + 1, edges)[vertex[:, 0]]


def connected_labels(count, edges):
    """Returns the smallest node index of the connected component of every node (edges: (k, 2) node pairs)."""
    labels = np.arange(count)
    if len(edges) == 0:
        return labels
    a, b = edges[:, 0], edges[:, 1]
    while True:
        low = np.minimum(labels[a], labels[b])
        before = labels.copy()
        np.minimum.at(labels, a, low)
        np.minimum.at(labels, b, low)
        labels = labels[labels]
        if np.array_equal(labels, before):
            return labels


def surface_samples(triangles, step):
    """Returns sample points on the triangles no farther than step apart, and the triangle index of each.

    Each triangle gets a square grid of spacing step in its own plane (x along its longest edge, y towards the
    opposite corner), clipped to the triangle, plus points along its three edges; so the number of samples follows the
    area and the edge length, also for long thin triangles.
    """
    corners = triangles
    edges = np.stack([corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 1], corners[:, 0] - corners[:, 2]], axis=1)
    lengths = np.linalg.norm(edges, axis=2)
    longest = np.argmax(lengths, axis=1)
    rows = np.arange(len(corners))
    a = corners[rows, longest]
    b = corners[rows, (longest + 1) % 3]
    c = corners[rows, (longest + 2) % 3]
    axis_x = b - a
    length = np.linalg.norm(axis_x, axis=1)
    axis_x = axis_x / np.maximum(length, 1e-12)[:, None]
    offset = c - a
    along = (offset * axis_x).sum(axis=1)
    axis_y = offset - along[:, None] * axis_x
    height = np.linalg.norm(axis_y, axis=1)
    axis_y = axis_y / np.maximum(height, 1e-12)[:, None]
    points = []
    owners = []
    # Edge samples (including the corners).
    for start, end in ((a, b), (b, c), (c, a)):
        count = np.maximum(1, np.ceil(np.linalg.norm(end - start, axis=1) / step)).astype(np.int64)
        for n in np.unique(count):
            chosen = np.where(count == n)[0]
            t = (np.arange(n) / float(n))[None, :, None]
            points.append((start[chosen, None] + (end[chosen] - start[chosen])[:, None] * t).reshape(-1, 3))
            owners.append(np.repeat(chosen, n))
    # Interior grid of the larger triangles.
    nx = np.floor(length / step).astype(np.int64)
    ny = np.floor(height / step).astype(np.int64)
    inner = np.where((nx >= 1) & (ny >= 1))[0]
    for gx, gy in np.unique(np.stack([nx[inner], ny[inner]], axis=1), axis=0):
        chosen = inner[(nx[inner] == gx) & (ny[inner] == gy)]
        x = (np.arange(1, gx + 1) * step)[None, :, None]
        y = (np.arange(1, gy + 1) * step)[None, None, :]
        px = np.broadcast_to(x, (len(chosen), gx, gy))
        py = np.broadcast_to(y, (len(chosen), gx, gy))
        # Inside the triangle (a at x 0, b at x length, c at (along, height)): left of a-c and of c-b.
        cx = along[chosen][:, None, None]
        h = height[chosen][:, None, None]
        l = length[chosen][:, None, None]
        inside = (py * cx <= px * h + 1e-9) & (py * (l - cx) <= (l - px) * h + 1e-9) & (px <= l)
        index, i, j = np.nonzero(inside)
        triangle = chosen[index]
        points.append(a[triangle] + axis_x[triangle] * ((i + 1) * step)[:, None] + axis_y[triangle] * ((j + 1) * step)[:, None])
        owners.append(triangle)
    return np.concatenate(points), np.concatenate(owners)


def terrain_heights(triangles, cell):
    """Returns (origin, cell, heights) of the highest terrain surface per grid cell (-inf where there is none)."""
    points, _ = surface_samples(triangles, cell * 0.5)
    origin = points[:, :2].min(axis=0)
    index = np.floor((points[:, :2] - origin) / cell).astype(np.int64)
    shape = index.max(axis=0) + 1
    heights = np.full(shape, -np.inf)
    np.maximum.at(heights, (index[:, 0], index[:, 1]), points[:, 2])
    return origin, cell, heights


def load_scene():
    """Returns the scene as (entity names, triangles (n, 3, 3), materials (n), entity index (n), part index (n))."""
    entities, _ = parse_config()
    names = []
    triangles = []
    materials = []
    entity = []
    part = []
    cache = {}
    first_part = 0
    for name, mesh, position in entities:
        if name in SKY_ENTITIES:
            continue
        if mesh not in cache:
            cache[mesh] = load_mesh(os.path.join(MODELS, mesh))
        submeshes = cache[mesh]
        if not submeshes:
            continue
        placed = np.concatenate([t for _, t in submeshes]) + position
        labels = np.unique(triangle_parts(placed), return_inverse=True)[1].ravel()
        names.append(name)
        triangles.append(placed)
        materials.append(np.concatenate([[m] * len(t) for m, t in submeshes]))
        entity.append(np.full(len(placed), len(names) - 1))
        part.append(labels + first_part)
        first_part += int(labels.max()) + 1
    return (names, np.concatenate(triangles), np.concatenate(materials), np.concatenate(entity),
            np.concatenate(part))


def contact_edges(cells, owner, group, size):
    """Returns part pairs (k, 2) whose sample cells lie closer than about size / 2, within the same group.

    The samples (cells, positions in metres) are sorted into cubes of size metres in eight grids shifted by half a
    cube along each axis; parts with samples in one cube of a grid (and the same group) touch.
    The keys are made unique by an in-place sort and a neighbour comparison: the same result as np.unique, which
    takes its slower hash path for the 18 million keys of the menu scene.
    """
    edges = []
    scaled = cells / size
    for shift in [(dx, dy, dz) for dx in (0, 1) for dy in (0, 1) for dz in (0, 1)]:
        cube = np.floor(scaled + np.array(shift) * 0.5).astype(np.int64) + 2048
        key = (((cube[:, 0] * 4096 + cube[:, 1]) * 4096 + cube[:, 2]) * 128 + group) * 65536 + owner
        key.sort()
        if len(key):
            key = key[np.concatenate(([True], key[1:] != key[:-1]))]
        same = (key[1:] >> 16) == (key[:-1] >> 16)
        edges.append(np.stack([key[:-1][same] & 65535, key[1:][same] & 65535], axis=1))
    return np.concatenate(edges)


def floating_parts(scene):
    """Returns the part indices that no chain of touching parts connects to the terrain.

    A part reaches the terrain when one of its vertices lies at most GROUND_CONTACT above it. Every other part is
    sampled on its surface (SAMPLE_STEP apart). Two parts touch when their samples
    come closer than CONTACT (contact_edges); within one model PIECE_CONTACT applies.
    """
    names, triangles, materials, entity, part = scene
    count = int(part.max()) + 1
    assert count < 65536 and len(names) < 128, "part and model indices must fit into the cube keys"
    terrain_entity = names.index(TERRAIN_ENTITY)
    sizes = np.bincount(part[entity == terrain_entity], minlength=count)
    terrain_part = int(np.argmax(sizes))
    origin, cell, heights = terrain_heights(triangles[part == terrain_part], 0.5)
    corners = triangles.reshape(-1, 3)
    cells = np.floor((corners[:, :2] - origin) / cell).astype(np.int64)
    inside = np.all((cells >= 0) & (cells < heights.shape), axis=1)
    ground = np.full(len(corners), -np.inf)
    ground[inside] = heights[cells[inside, 0], cells[inside, 1]]
    grounded = np.zeros(count, dtype=bool)
    grounded[np.repeat(part, 3)[corners[:, 2] <= ground + GROUND_CONTACT]] = True
    grounded[terrain_part] = True
    others = np.where(part != terrain_part)[0]
    sample, sample_part = surface_samples(triangles[others], SAMPLE_STEP)
    sample_part = part[others][sample_part]
    model = np.zeros(count, dtype=np.int64)
    model[part] = entity
    edges = [contact_edges(sample, sample_part, 0, 2.0 * CONTACT)]
    labels = connected_labels(count, np.unique(np.concatenate(edges), axis=0))
    carried = np.zeros(count, dtype=bool)
    carried[labels[grounded]] = True
    # Within one model, parts closer than PIECE_CONTACT form one piece (the joints of a skeleton, a chain, a carving).
    loose_models = np.unique(model[~carried[labels]])
    chosen = np.isin(model[sample_part], loose_models)
    if chosen.any():
        edges.append(contact_edges(sample[chosen], sample_part[chosen], model[sample_part[chosen]], 2.0 * PIECE_CONTACT))
        labels = connected_labels(count, np.unique(np.concatenate(edges), axis=0))
        carried = np.zeros(count, dtype=bool)
        carried[labels[grounded]] = True
    return np.where(~carried[labels])[0]


def untextured_surfaces(scene):
    """Returns messages for every flat untextured surface and every oversized detail patch."""
    names, triangles, materials, entity, part = scene
    kinds = parse_materials()
    problems = []
    for material in np.unique(materials):
        if kinds.get(material, "flat") != "flat":
            continue
        chosen = materials == material
        for index in np.unique(entity[chosen]):
            selected = triangles[chosen & (entity == index)]
            if material not in DETAIL_MATERIALS:
                problems.append("%s: untextured surface %s (%.2f m2)" % (names[index], material, area(selected)))
                continue
            labels = np.unique(triangle_parts(selected), return_inverse=True)[1].ravel()
            sizes = np.bincount(labels, weights=0.5 * np.linalg.norm(np.cross(selected[:, 1] - selected[:, 0],
                                                                              selected[:, 2] - selected[:, 0]), axis=1))
            for patch in sizes[sizes > DETAIL_MAX_AREA]:
                problems.append("%s: %s patch of %.2f m2 is a surface, not a detail" % (names[index], material, patch))
    return problems


def area(triangles):
    """Returns the total area of the triangles."""
    return 0.5 * np.linalg.norm(np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]), axis=1).sum()


def main():
    """Runs the grounding and surface checks and prints the result."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--report", action="store_true", help="list every floating part")
    options = parser.parse_args()
    start = time.monotonic()
    scene = load_scene()
    names, triangles, materials, entity, part = scene
    setup_end = time.monotonic()
    print('ODP_TEST_PHASE {"name":"setup","seconds":%.2f}' % (setup_end - start))
    failures = []
    floating = floating_parts(scene)
    order = np.argsort(part, kind="stable")
    bounds = np.searchsorted(part[order], np.arange(int(part.max()) + 2))
    per_entity = {}
    for index in floating:
        members = order[bounds[index]:bounds[index + 1]]
        per_entity.setdefault(names[entity[members[0]]], []).append(members)
    for name, groups in sorted(per_entity.items()):
        corners = triangles[np.concatenate(groups)].reshape(-1, 3)
        failures.append("%s: %d floating parts between (%.2f %.2f %.2f) and (%.2f %.2f %.2f)"
                        % ((name, len(groups)) + tuple(corners.min(axis=0)) + tuple(corners.max(axis=0))))
        if options.report:
            for members in groups:
                corners = triangles[members].reshape(-1, 3)
                print("  part %s tris=%d (%.2f %.2f %.2f)-(%.2f %.2f %.2f) %s"
                      % ((name, len(members)) + tuple(corners.min(axis=0)) + tuple(corners.max(axis=0))
                         + (",".join(np.unique(materials[members])),)))
    failures += untextured_surfaces(scene)
    print('ODP_TEST_PHASE {"name":"test","seconds":%.2f}' % (time.monotonic() - setup_end))
    for line in failures:
        print("FAIL " + line)
    if failures:
        return 1
    print("OK: %d parts of %d menu entities rest on the ground or on each other; no flat untextured surface"
          % (int(part.max()) + 1, len(names)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
