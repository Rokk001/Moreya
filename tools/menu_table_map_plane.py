#!/usr/bin/env python3
"""Fit the stone campaign table of the main menu (models/MenuMapTableStone.mesh) to the map carved into its top.

The map of Moreya is carved into the top of the stone table (material MenuCampaignMap). It used to be a small plane
of 3.8 x 2.6 inside the pale stone rim (MenuParchment) of the table top, and the texture showed the whole campaign
map with its wide rock border, so the map looked like a small sheet inside a wide frame. The map now takes the whole
table top and the table follows the map, not the other way round: the texture shows only the carved map
(tools/gen_campaign_map_art.py, TABLE_CROP, aspect ratio about 1.79), the table is widened along x to the proportions
of the map, and the map plane covers its whole top.

    python tools/menu_table_map_plane.py [<mesh>] [--scale-x 1.0] [--half-width 3.075] [--half-depth 1.72]

first scales every vertex of the table along x by scale-x (positions; normals are corrected for the stretch and the
bounds of the mesh follow), then moves the corners of the map plane to +-half-width in x and +-half-depth in y (mesh
units, the table centred at the origin); the height and the texture coordinates stay. Only the map plane vertices that
no other submesh uses are moved; the file is rewritten in place. The shipped table was made with --scale-x 1.337
--half-width 3.075 --half-depth 1.72 from the table of 2026-11-22.
"""
import argparse
import math
import struct
import sys

#: Chunk ids of the Ogre mesh format.
MESH_CHUNK = 0x3000
GEOMETRY_CHUNK = 0x5000
VERTEX_DECLARATION = 0x5100
VERTEX_ELEMENT = 0x5110
VERTEX_BUFFER = 0x5200
VERTEX_BUFFER_DATA = 0x5210
SUBMESH_CHUNK = 0x4000
BOUNDS_CHUNK = 0x9000
#: Vertex element semantics of positions and normals.
POSITION = 1
NORMAL = 4
#: Material of the map plane.
MAP_MATERIAL = "MenuCampaignMap"


def chunks(data, offset, end):
    """Yields (id, payload start, chunk end) of the chunks between offset and end."""
    while offset + 6 <= end:
        chunk_id, length = struct.unpack_from("<HI", data, offset)
        yield chunk_id, offset + 6, offset + length
        offset += length


def submesh_indices(data, start):
    """Returns (material, uses shared vertices, vertex indices) of a submesh chunk payload."""
    name_end = data.index(b"\n", start)
    material = data[start:name_end].decode("ascii")
    position = name_end + 1
    shared = data[position] != 0
    count, = struct.unpack_from("<I", data, position + 1)
    wide = data[position + 5] != 0
    indices = struct.unpack_from("<%d%s" % (count, "I" if wide else "H"), data, position + 6)
    return material, shared, indices


def geometry_elements(data, payload, end):
    """Returns (vertex count, {semantic: (source, offset)}, {source: (stride, data start)}) of a geometry chunk."""
    count, = struct.unpack_from("<I", data, payload)
    elements = {}
    buffers = {}
    for chunk_id, chunk_payload, chunk_end in chunks(data, payload + 4, end):
        if chunk_id == VERTEX_DECLARATION:
            for _, element_payload, _ in chunks(data, chunk_payload, chunk_end):
                source, _, semantic, offset, _ = struct.unpack_from("<HHHHH", data, element_payload)
                elements[semantic] = (source, offset)
        elif chunk_id == VERTEX_BUFFER:
            bind, stride = struct.unpack_from("<HH", data, chunk_payload)
            for kind, buffer_payload, _ in chunks(data, chunk_payload + 4, chunk_end):
                if kind == VERTEX_BUFFER_DATA:
                    buffers[bind] = (stride, buffer_payload)
    return count, elements, buffers


def stretch(data, geometry, scale):
    """Scales the positions of a geometry along x and corrects its normals for that stretch."""
    count, elements, buffers = geometry_elements(data, *geometry)
    source, offset = elements[POSITION]
    stride, base = buffers[source]
    for vertex in range(count):
        at = base + vertex * stride + offset
        x, y, z = struct.unpack_from("<3f", data, at)
        struct.pack_into("<3f", data, at, x * scale, y, z)
    if NORMAL in elements:
        source, offset = elements[NORMAL]
        stride, base = buffers[source]
        for vertex in range(count):
            at = base + vertex * stride + offset
            x, y, z = struct.unpack_from("<3f", data, at)
            x /= scale
            length = math.sqrt(x * x + y * y + z * z) or 1.0
            struct.pack_into("<3f", data, at, x / length, y / length, z / length)


def main():
    """Stretches the table and moves the corners of the map plane."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("mesh", nargs="?", default="models/MenuMapTableStone.mesh")
    parser.add_argument("--scale-x", type=float, default=1.0)
    parser.add_argument("--half-width", type=float, default=3.075)
    parser.add_argument("--half-depth", type=float, default=1.72)
    args = parser.parse_args()
    data = bytearray(open(args.mesh, "rb").read())
    start = data.index(b"\n") + 1
    mesh_id, mesh_length = struct.unpack_from("<HI", data, start)
    if mesh_id != MESH_CHUNK:
        print("no mesh chunk")
        return 1
    map_vertices = set()
    other_vertices = set()
    geometry = None
    for chunk_id, payload, end in chunks(data, start + 7, start + mesh_length):
        if chunk_id == GEOMETRY_CHUNK:
            geometry = (payload, end)
        elif chunk_id == SUBMESH_CHUNK:
            material, shared, indices = submesh_indices(data, payload)
            if not shared:
                print("the table has a submesh with its own vertices; only shared vertices are supported")
                return 1
            (map_vertices if material == MAP_MATERIAL else other_vertices).update(indices)
        elif chunk_id == BOUNDS_CHUNK and args.scale_x != 1.0:
            low_x, = struct.unpack_from("<f", data, payload)
            high_x, = struct.unpack_from("<f", data, payload + 12)
            radius, = struct.unpack_from("<f", data, payload + 24)
            struct.pack_into("<f", data, payload, low_x * args.scale_x)
            struct.pack_into("<f", data, payload + 12, high_x * args.scale_x)
            struct.pack_into("<f", data, payload + 24, radius * max(args.scale_x, 1.0))
    if geometry is None or not map_vertices or map_vertices & other_vertices:
        print("the map plane does not have its own shared vertices")
        return 1
    if args.scale_x != 1.0:
        stretch(data, geometry, args.scale_x)
    _, elements, buffers = geometry_elements(data, *geometry)
    source, offset = elements[POSITION]
    stride, base = buffers[source]
    for vertex in sorted(map_vertices):
        at = base + vertex * stride + offset
        x, y, z = struct.unpack_from("<3f", data, at)
        struct.pack_into("<3f", data, at, args.half_width if x > 0 else -args.half_width,
                         args.half_depth if y > 0 else -args.half_depth, z)
    open(args.mesh, "wb").write(bytes(data))
    print("%s: table scaled by %.3f along x, %d map plane corners set to +-%.3f x +-%.3f"
          % (args.mesh, args.scale_x, len(map_vertices), args.half_width, args.half_depth))
    return 0


if __name__ == "__main__":
    sys.exit(main())
