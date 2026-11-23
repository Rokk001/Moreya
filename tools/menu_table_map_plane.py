#!/usr/bin/env python3
"""Size the map plane on top of the stone campaign table of the main menu (models/MenuMapTableStone.mesh).

The map of Moreya is carved into the top of the stone table (material MenuCampaignMap). It used to be a small plane
of 3.8 x 2.6 inside the pale stone rim (MenuParchment) of the table top, and the texture showed the whole campaign
map with its wide rock border, so the map looked like a small sheet inside a wide frame. The plane now covers the rim
as well and the texture shows only the carved map with a narrow border of the stone around it
(tools/gen_campaign_map_art.py), so the map takes up the table top.

    python tools/menu_table_map_plane.py [<mesh>] [--half-width 2.035] [--half-depth 1.435]

moves the corners of the map plane to +-half-width in x and +-half-depth in y (mesh units, the table centred at the
origin); the height, the normals and the texture coordinates stay. Only the vertices that no other submesh uses are
moved; the file is rewritten in place.
"""
import argparse
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
#: Vertex element semantic of positions.
POSITION = 1
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


def main():
    """Moves the corners of the map plane."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("mesh", nargs="?", default="models/MenuMapTableStone.mesh")
    parser.add_argument("--half-width", type=float, default=2.035)
    parser.add_argument("--half-depth", type=float, default=1.435)
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
            if shared:
                (map_vertices if material == MAP_MATERIAL else other_vertices).update(indices)
    if geometry is None or not map_vertices or map_vertices & other_vertices:
        print("the map plane does not have its own shared vertices")
        return 1
    count, = struct.unpack_from("<I", data, geometry[0])
    element = None
    buffers = {}
    for chunk_id, payload, end in chunks(data, geometry[0] + 4, geometry[1]):
        if chunk_id == VERTEX_DECLARATION:
            for _, element_payload, _ in chunks(data, payload, end):
                source, _, semantic, offset, _ = struct.unpack_from("<HHHHH", data, element_payload)
                if semantic == POSITION:
                    element = (source, offset)
        elif chunk_id == VERTEX_BUFFER:
            bind, stride = struct.unpack_from("<HH", data, payload)
            for kind, buffer_payload, _ in chunks(data, payload + 4, end):
                if kind == VERTEX_BUFFER_DATA:
                    buffers[bind] = (stride, buffer_payload)
    stride, base = buffers[element[0]]
    for vertex in sorted(map_vertices):
        at = base + vertex * stride + element[1]
        x, y, z = struct.unpack_from("<3f", data, at)
        struct.pack_into("<3f", data, at, args.half_width if x > 0 else -args.half_width,
                         args.half_depth if y > 0 else -args.half_depth, z)
    open(args.mesh, "wb").write(bytes(data))
    print("%s: %d map plane corners set to +-%.3f x +-%.3f" % (args.mesh, len(map_vertices), args.half_width,
                                                               args.half_depth))
    return 0


if __name__ == "__main__":
    sys.exit(main())
