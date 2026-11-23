#!/usr/bin/env python3
"""Give submeshes of an Ogre binary mesh other materials, leaving every vertex, index and other chunk unchanged.

The forecourt behind the campaign hall, its portal and the frame of the hall opening (models/MenuMoreyaForecourt.mesh,
MenuMoreyaPortal.mesh, MenuHallForecourtArch.mesh) share their stone materials with the whole main menu scene. To age
only them into a dark ruin (materials MenuRuin* in materials/scripts/MenuScene.material) without changing the start
screen, their submeshes get own materials:

    python tools/menu_rename_mesh_materials.py <mesh> <old material>=<new material> [...]

Only the material name at the start of each submesh chunk (0x4000) is replaced; the lengths of that chunk and of the
mesh chunk (0x3000) grow or shrink by the difference. Names not listed stay. The file is rewritten in place.
"""
import struct
import sys

#: Chunk ids of the Ogre mesh format: the mesh and its submeshes.
MESH_CHUNK = 0x3000
SUBMESH_CHUNK = 0x4000
#: Size of a chunk header (id and length).
HEADER_SIZE = 6


def rename(data, names):
    """Returns the mesh bytes with the materials of its submeshes renamed and the count of renamed submeshes."""
    start = data.index(b"\n") + 1
    mesh_id, mesh_length = struct.unpack_from("<HI", data, start)
    if mesh_id != MESH_CHUNK:
        raise ValueError("no mesh chunk after the file header")
    # The mesh chunk: header, the skeletally animated flag, then its sub chunks up to its end.
    body_start = start + HEADER_SIZE + 1
    mesh_end = start + mesh_length
    if mesh_end != len(data):
        raise ValueError("the mesh chunk does not end at the end of the file")
    parts = [data[:body_start]]
    renamed = 0
    position = body_start
    while position < mesh_end:
        chunk_id, length = struct.unpack_from("<HI", data, position)
        chunk = data[position:position + length]
        if chunk_id == SUBMESH_CHUNK:
            name_end = chunk.index(b"\n", HEADER_SIZE)
            material = chunk[HEADER_SIZE:name_end].decode("ascii")
            if material in names:
                new_name = names[material].encode("ascii")
                chunk = (struct.pack("<HI", chunk_id, length - (name_end - HEADER_SIZE) + len(new_name))
                         + new_name + chunk[name_end:])
                renamed += 1
        parts.append(chunk)
        position += length
    result = b"".join(parts)
    result = result[:start] + struct.pack("<HI", MESH_CHUNK, len(result) - start) + result[start + HEADER_SIZE:]
    return result, renamed


def main():
    """Renames the materials of one mesh as given on the command line."""
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    names = dict(argument.split("=", 1) for argument in sys.argv[2:])
    with open(sys.argv[1], "rb") as source:
        data = source.read()
    result, renamed = rename(data, names)
    with open(sys.argv[1], "wb") as target:
        target.write(result)
    print("%s: %d submeshes renamed" % (sys.argv[1], renamed))
    return 0


if __name__ == "__main__":
    sys.exit(main())
