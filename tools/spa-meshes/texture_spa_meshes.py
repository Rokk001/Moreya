#!/usr/bin/env python3
"""Gives the pool attendant's chair, life ring and the attendant's hair and metal parts texture coordinates (K22).

Since the Blender re-export of 2026-11-08 every vertex of models/SpaChair.mesh had the texture coordinate (0, 1), so the
wood showed a single texel; the life ring had no texture at all. The attendant's hair, body hair, whistle and cord had
one texture coordinate each. This script reads the OgreXML of a mesh (OgreXMLConverter output), keeps every position,
normal, face and bone weight and writes new texture coordinates for the named submeshes, splitting a vertex where two
faces need different coordinates:

- chair wood (SpaWood -> SpaChairWood): every beam gets its own grain direction along its long axis (principal axis of
  the connected part), the grain runs along v; end faces get a planar projection; each beam its own texture offset;
- chair iron (SpaIron -> SpaIronWorn): planar projection on the axis plane the face looks to; the attendant's hair, body
  hair, whistle and cord (SpaIron -> SpaIronWorn): the same per vertex along its normal, so the thin strands keep their
  vertex count;
- life ring (SpaLifebuoyRed, SpaLifebuoyWhite): u around the ring, v around the tube;
- attendant: the towel part lying on the shoulder top stays there as a folded corner and is cut loose from the hanging
  part (shared vertices doubled), so the hanging part goes into the hand in TowelWave without stretching.

Deterministic, original work of the project, licence GPLv3+. Needs numpy.

Usage: python texture_spa_meshes.py chair|attendant <in.mesh.xml> <out.mesh.xml>
Then: OgreXMLConverter <out> models/<name>.mesh
"""

import math
import sys
import xml.etree.ElementTree as ET

import numpy as np

# material -> (new material name, projection, metres per texture repeat)
CHAIR = {
    'SpaWood': ('SpaChairWood', 'beam', 0.45),
    'SpaIron': ('SpaIronWorn', 'box', 0.12),
    'SpaLifebuoyRed': ('SpaLifebuoyRed', 'ring', 1.0),
    'SpaLifebuoyWhite': ('SpaLifebuoyWhite', 'ring', 1.0),
}
ATTENDANT = {
    'SpaHair': ('SpaHair', 'vbox', 0.09),
    'SpaBodyHair': ('SpaBodyHair', 'vbox', 0.05),
    'SpaWhistle': ('SpaWhistle', 'vbox', 0.05),
    'SpaIron': ('SpaIronWorn', 'vbox', 0.1),
}
RING_GROUP = ('SpaLifebuoyRed', 'SpaLifebuoyWhite')
# index of the Towel bone in models/PoolAttendant.skeleton (TowelTip is the next one)
TOWEL_BONE = 18
# index of the Chest bone in models/PoolAttendant.skeleton
CHEST_BONE = 3


def read_mesh(path):
    """Positions, normals, uvs, bone assignments and submeshes of an OgreXML mesh with shared geometry."""
    root = ET.parse(path).getroot()
    shared = root.find('sharedgeometry')
    positions, normals, uvs = [], [], []
    for buffer in shared.findall('vertexbuffer'):
        for vertex in buffer.findall('vertex'):
            p = vertex.find('position')
            if p is not None:
                positions.append([float(p.get(a)) for a in 'xyz'])
            n = vertex.find('normal')
            if n is not None:
                normals.append([float(n.get(a)) for a in 'xyz'])
            t = vertex.find('texcoord')
            if t is not None:
                uvs.append([float(t.get('u')), float(t.get('v'))])
    assignments = {}
    block = root.find('boneassignments')
    if block is not None:
        for a in block.findall('vertexboneassignment'):
            assignments.setdefault(int(a.get('vertexindex')), []).append((int(a.get('boneindex')), float(a.get('weight'))))
    submeshes = []
    for sub in root.find('submeshes').findall('submesh'):
        faces = [[int(f.get(k)) for k in ('v1', 'v2', 'v3')] for f in sub.find('faces').findall('face')]
        submeshes.append([sub.get('material'), np.array(faces, dtype=np.int64)])
    link = root.find('skeletonlink')
    return {'positions': np.array(positions), 'normals': np.array(normals), 'uvs': np.array(uvs),
            'assignments': assignments, 'submeshes': submeshes,
            'skeleton': link.get('name') if link is not None else None}


def face_normals(pos, faces):
    """Unit normals of triangles."""
    n = np.cross(pos[faces[:, 1]] - pos[faces[:, 0]], pos[faces[:, 2]] - pos[faces[:, 0]])
    length = np.linalg.norm(n, axis=1)
    length[length < 1e-12] = 1.0
    return n / length[:, None]


def box_uv(pos, faces, scale):
    """Per corner: project on the axis plane the face looks to."""
    normals = face_normals(pos, faces)
    axis = np.argmax(np.abs(normals), axis=1)
    planes = {0: (1, 2), 1: (0, 2), 2: (0, 1)}
    uv = np.zeros(faces.shape + (2,))
    for a, (i, j) in planes.items():
        sel = axis == a
        corners = pos[faces[sel]]
        uv[sel, :, 0] = corners[:, :, i] / scale + 0.37 * a
        uv[sel, :, 1] = corners[:, :, j] / scale
    return uv


def vertex_box_uv(pos, nor, faces, scale):
    """Per corner: project each vertex on the axis plane its normal looks to (no vertex split; for thin strands)."""
    axis = np.argmax(np.abs(nor), axis=1)
    planes = np.array([(1, 2), (0, 2), (0, 1)])
    i, j = planes[axis, 0], planes[axis, 1]
    rows = np.arange(len(pos))
    u = pos[rows, i] / scale + 0.37 * axis
    v = pos[rows, j] / scale
    return np.stack([u[faces], v[faces]], axis=-1)


def components(faces):
    """Connected parts of a face list (union-find over shared vertices) -> component id per face."""
    parent = {}

    def find(x):
        while parent.setdefault(x, x) != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for a, b, c in faces:
        ra, rb, rc = find(a), find(b), find(c)
        parent[rb] = ra
        parent[find(rc)] = ra
    return np.array([find(f[0]) for f in faces])


def beam_uv(pos, faces, scale):
    """Per corner: grain (v) along the long axis of the beam the face belongs to; ends planar."""
    uv = np.zeros(faces.shape + (2,))
    normals = face_normals(pos, faces)
    comp = components(faces)
    for index, cid in enumerate(np.unique(comp)):
        sel = np.where(comp == cid)[0]
        verts = np.unique(faces[sel])
        points = pos[verts]
        centre = points.mean(axis=0)
        _, _, vt = np.linalg.svd(points - centre, full_matrices=False)
        long_axis = vt[0]
        offset = np.array([(index * 0.618) % 1.0, (index * 0.382) % 1.0])
        for f in sel:
            n = normals[f]
            corners = pos[faces[f]] - centre
            if abs(np.dot(n, long_axis)) < 0.7:
                across = np.cross(n, long_axis)
                across /= max(np.linalg.norm(across), 1e-9)
                uv[f, :, 0] = corners @ across / scale
                uv[f, :, 1] = corners @ long_axis / scale
            else:
                side = vt[1] if abs(np.dot(n, vt[1])) < 0.7 else vt[2]
                other = np.cross(n, side)
                uv[f, :, 0] = corners @ side / scale
                uv[f, :, 1] = corners @ other / scale
            uv[f] += offset
    return uv


def ring_uv(pos, faces):
    """Per corner: u around the ring (two repeats), v around the tube; seams kept continuous per face."""
    verts = np.unique(faces)
    points = pos[verts]
    centre = points.mean(axis=0)
    _, _, vt = np.linalg.svd(points - centre, full_matrices=False)
    e1, e2, axis = vt[0], vt[1], vt[2]
    rel = pos - centre
    theta = np.arctan2(rel @ e2, rel @ e1)
    radial = np.sqrt((rel @ e1) ** 2 + (rel @ e2) ** 2)
    major = np.median(radial[verts])
    phi = np.arctan2(rel @ axis, radial - major)
    u = theta / (2 * math.pi) * 2.0
    v = phi / (2 * math.pi)
    uv = np.stack([u[faces], v[faces]], axis=-1)
    for k, period in ((0, 2.0), (1, 1.0)):
        values = uv[:, :, k]
        low = values.min(axis=1, keepdims=True)
        wrap = (values.max(axis=1, keepdims=True) - low) > period / 2
        values[:] = np.where(wrap & (values < low + period / 2), values + period, values)
    return uv


def apply(mesh, table):
    """Rewrite texture coordinates of the listed submeshes, splitting vertices as needed."""
    pos, nor, uvs = mesh['positions'], mesh['normals'], mesh['uvs']
    new_pos, new_nor, new_uv = list(pos), list(nor), list(uvs)
    assignments = mesh['assignments']
    ring_faces = [faces for name, faces in mesh['submeshes'] if name in RING_GROUP]
    ring_all = np.vstack(ring_faces) if ring_faces else None
    for sub in mesh['submeshes']:
        name, faces = sub
        if name not in table:
            continue
        new_name, mode, scale = table[name]
        if mode == 'box':
            corner_uv = box_uv(pos, faces, scale)
        elif mode == 'vbox':
            corner_uv = vertex_box_uv(pos, nor, faces, scale)
        elif mode == 'beam':
            corner_uv = beam_uv(pos, faces, scale)
        else:
            all_uv = ring_uv(pos, ring_all)
            start = 0
            for other_name, other in mesh['submeshes']:
                if other_name in RING_GROUP:
                    if other is faces:
                        corner_uv = all_uv[start:start + len(faces)]
                    start += len(other)
        seen = {}
        used = set()
        out = np.zeros_like(faces)
        for f in range(len(faces)):
            for c in range(3):
                vi = int(faces[f, c])
                key = (vi, round(float(corner_uv[f, c, 0]), 5), round(float(corner_uv[f, c, 1]), 5))
                index = seen.get(key)
                if index is None:
                    if vi in used:
                        index = len(new_pos)
                        new_pos.append(pos[vi])
                        new_nor.append(nor[vi])
                        new_uv.append([0.0, 0.0])
                        if vi in assignments:
                            assignments[index] = list(assignments[vi])
                    else:
                        index = vi
                        used.add(vi)
                    seen[key] = index
                    new_uv[index] = [float(corner_uv[f, c, 0]), float(corner_uv[f, c, 1])]
                out[f, c] = index
        sub[0] = new_name
        sub[1] = out
    mesh['positions'], mesh['normals'], mesh['uvs'] = np.array(new_pos), np.array(new_nor), np.array(new_uv)


def split_towel(mesh, towel_bone):
    """Let the towel go into the hand without stretching: the part lying on the shoulder top (bound to the shoulder or
    chest) stays there as a folded corner bound to the chest, every towel face touching it stays with it, and the
    vertices it shares with the hanging part are doubled so the hanging part rides on the towel bones alone."""
    towel_bones = {towel_bone, towel_bone + 1}
    changed = 0
    for sub in mesh['submeshes']:
        if sub[0] != 'SpaLinen':
            continue
        faces = sub[1]

        def on_towel(vi):
            """Whether a vertex hangs on the towel bones alone."""
            return sum(w for b, w in mesh['assignments'].get(int(vi), []) if b in towel_bones) > 0.99
        shoulder_faces = np.array([not all(on_towel(v) for v in face) for face in faces])
        # the corner lies still on the chest, so a raised arm does not pull it apart
        for vi in np.unique(faces[shoulder_faces]):
            if not on_towel(vi):
                mesh['assignments'][int(vi)] = [(CHEST_BONE, 1.0)]
        doubled = {}
        for f in np.where(shoulder_faces)[0]:
            for c in range(3):
                vi = int(faces[f, c])
                if on_towel(vi):
                    if vi not in doubled:
                        doubled[vi] = len(mesh['positions'])
                        mesh['positions'] = np.vstack([mesh['positions'], mesh['positions'][vi]])
                        mesh['normals'] = np.vstack([mesh['normals'], mesh['normals'][vi]])
                        mesh['uvs'] = np.vstack([mesh['uvs'], mesh['uvs'][vi]])
                        mesh['assignments'][doubled[vi]] = [(CHEST_BONE, 1.0)]
                        changed += 1
                    faces[f, c] = doubled[vi]
    return changed


def fmt(value):
    """Short float text."""
    return ('%.6g' % value) if abs(value) >= 1e-9 else '0'


def write_mesh(mesh, path):
    """Write an OgreXML mesh with shared geometry in the layout OgreXMLConverter reads."""
    lines = ['<?xml version="1.0"?>\n<mesh>\n']
    count = len(mesh['positions'])
    lines.append('\t<sharedgeometry vertexcount="%d">\n\t\t<vertexbuffer positions="true" normals="true">\n' % count)
    for p, n in zip(mesh['positions'], mesh['normals']):
        lines.append('\t\t\t<vertex>\n\t\t\t\t<position x="%s" y="%s" z="%s" />\n\t\t\t\t<normal x="%s" y="%s" z="%s" />\n'
                     '\t\t\t</vertex>\n' % tuple(fmt(x) for x in list(p) + list(n)))
    lines.append('\t\t</vertexbuffer>\n\t\t<vertexbuffer texture_coord_dimensions_0="float2" texture_coords="1">\n')
    for u, v in mesh['uvs']:
        lines.append('\t\t\t<vertex>\n\t\t\t\t<texcoord u="%s" v="%s" />\n\t\t\t</vertex>\n' % (fmt(u), fmt(v)))
    lines.append('\t\t</vertexbuffer>\n\t</sharedgeometry>\n\t<submeshes>\n')
    for name, faces in mesh['submeshes']:
        wide = 'true' if count > 65535 else 'false'
        lines.append('\t\t<submesh material="%s" usesharedvertices="true" use32bitindexes="%s" '
                     'operationtype="triangle_list">\n\t\t\t<faces count="%d">\n' % (name, wide, len(faces)))
        for a, b, c in faces:
            lines.append('\t\t\t\t<face v1="%d" v2="%d" v3="%d" />\n' % (a, b, c))
        lines.append('\t\t\t</faces>\n\t\t</submesh>\n')
    lines.append('\t</submeshes>\n')
    if mesh['skeleton']:
        lines.append('\t<skeletonlink name="%s" />\n\t<boneassignments>\n' % mesh['skeleton'])
        for vi in range(count):
            for bone, weight in mesh['assignments'].get(vi, []):
                lines.append('\t\t<vertexboneassignment vertexindex="%d" boneindex="%d" weight="%s" />\n'
                             % (vi, bone, fmt(weight)))
        lines.append('\t</boneassignments>\n')
    lines.append('</mesh>\n')
    with open(path, 'w', newline='\n') as handle:
        handle.write(''.join(lines))


def main():
    kind, source, target = sys.argv[1:4]
    mesh = read_mesh(source)
    if kind == 'attendant':
        print('towel vertices doubled for the shoulder corner:', split_towel(mesh, TOWEL_BONE))
        apply(mesh, ATTENDANT)
    else:
        apply(mesh, CHAIR)
    write_mesh(mesh, target)
    print('vertices', len(mesh['positions']), 'faces', sum(len(f) for _, f in mesh['submeshes']))


if __name__ == '__main__':
    main()
