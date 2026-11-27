#!/usr/bin/env python3
"""Pure check (nothing compiled, nothing started): every material that a shipped mesh names exists in a material script.

The binary meshes of the public tree and of the content packages (models/*.mesh, scripts/content_packages.py) are read
chunk by chunk (Ogre mesh format: the material name opens every submesh chunk); the material scripts below
materials/scripts of the public tree and of the packages are read for their `material <name>` definitions. A mesh whose
material is missing renders with the engine's white fallback and logs an error.

A tile mesh of config/tilesets.cfg whose row names a material is drawn with that material, which must then exist;
a row with '' keeps the mesh's own material.

Fixed expected values of this branch (counted once): 492 meshes in the content packages, 17 tile meshes drawn with
the material of their tile set row, no missing material.
Without the content the packages are named as not checked.
"""
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import content_packages  # noqa: E402

HEADER, MESH, SUBMESH = 0x1000, 0x3000, 0x4000
CHUNK = 6
#: shipped content meshes of this branch (counted once; 478, the trap crate of the workshop, the five clip props, the four
#: coin pouches and the four gold loads; 495 found on main, 503 with the four meshes each of the own items MinotaurAxe and
#: CyclopsClub)
CONTENT_MESHES = 503
TILE_MESHES = 17
#: materials the engine itself defines
ENGINE_MATERIALS = {'BaseWhite', 'BaseWhiteNoLighting'}


def submesh_materials(data):
    """Material names of the submeshes of an Ogre binary mesh."""
    if struct.unpack_from('<H', data)[0] != HEADER:
        raise ValueError('no Ogre mesh header')
    position = data.index(b'\n') + 1
    names = []
    while position + CHUNK <= len(data):
        kind, length = struct.unpack_from('<HI', data, position)
        if kind == MESH:
            # skeletally animated flag, then the sub chunks of the mesh
            inner = position + CHUNK + 1
            end = position + length
            while inner + CHUNK <= end:
                sub_kind, sub_length = struct.unpack_from('<HI', data, inner)
                if sub_kind == SUBMESH:
                    start = inner + CHUNK
                    names.append(data[start:data.index(b'\n', start)].decode('utf-8'))
                if sub_length < CHUNK:
                    raise ValueError('broken chunk length')
                inner += sub_length
            return names
        if length < CHUNK:
            raise ValueError('broken chunk length')
        position += length
    raise ValueError('no mesh chunk')


def defined_materials(paths):
    """Names defined by `material <name>` lines of material scripts."""
    names = set()
    for path in paths:
        for match in re.finditer(r'^\s*material\s+("([^"]+)"|[^\s:{]+)', path.read_text(encoding='utf-8', errors='replace'),
                                 re.M):
            names.add(match.group(2) or match.group(1))
    return names


def main():
    """Checks every shipped mesh against the material scripts."""
    if not content_packages.has_content(ROOT):
        content_packages.unchecked('check_mesh_materials', ['models/*.mesh and materials/scripts of the content packages'])
        return
    meshes = content_packages.data_glob(ROOT, 'models', '*.mesh')
    scripts = content_packages.data_glob(ROOT, 'materials/scripts', '*.material', recursive=True)
    defined = defined_materials(scripts) | ENGINE_MATERIALS
    content = [m for m in meshes if not str(m.resolve()).startswith(str(ROOT.resolve()) + '\\models')
               and not str(m.resolve()).startswith(str(ROOT.resolve()) + '/models')]
    assert len(content) == CONTENT_MESHES, ('content meshes', len(content))
    # A tile mesh of config/tilesets.cfg is drawn with the material its row names (RenderManager sets it on the entity),
    # not with the one stored in the mesh: for those rows the named material must exist.
    tile_rows = re.findall(r'^\s*(?:\d+\s+)?(\S+\.mesh)\s+(\S+)', content_packages.read_text(ROOT, 'config/tilesets.cfg'),
                           re.M)
    # '' keeps the mesh's own material, so such a mesh is checked by its own material as well
    kept = {mesh for mesh, material in tile_rows if material == "''"}
    tile_meshes = {mesh for mesh, _material in tile_rows} - kept
    assert len(tile_meshes) == TILE_MESHES, ('tile meshes', len(tile_meshes))
    missing = {}
    for mesh, material in tile_rows:
        if material != "''" and material not in defined:
            missing.setdefault(material, []).append('config/tilesets.cfg ' + mesh)
    for mesh in meshes:
        if mesh.name in tile_meshes:
            continue
        for name in submesh_materials(mesh.read_bytes()):
            if name not in defined:
                missing.setdefault(name, []).append(content_packages.relative_path(ROOT, mesh))
    assert not missing, sorted(missing.items())
    print('mesh materials ok: %d meshes (%d tile meshes by their tile set material), %d material scripts'
          % (len(meshes), len(tile_meshes), len(scripts)))


if __name__ == '__main__':
    main()
