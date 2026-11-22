"""Small software render of the pool attendant for check_spa_attendant_k22.py (owner triangle budget, 2026-11-17).

A depth-buffered orthographic render of the bind pose: every triangle in the colour of its material texture at the
triangle's texture-coordinate centre times the material's diffuse colour, lit by one two-sided Lambert light. Used to
compare the reduced figure with the reviewed render of the figure before the reduction (mean difference per channel and
silhouette overlap). No compiler, no game.
"""
import math
import re
from pathlib import Path

import numpy as np
from PIL import Image

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
import room_packages  # noqa: E402  (the spa assets come from the spa room package)

RENDER_PIXEL = 0.0125
RENDER_HALF_WIDTH = 0.45
RENDER_LIGHT = (-0.4, -0.6, 0.7)
RENDER_AMBIENT = 0.35
# forward, up, lowest and highest height on the image: the game camera 25 degrees off vertical and the front
VIEWS = {'game': ((0.0, math.sin(math.radians(25)), -math.cos(math.radians(25))),
                  (0.0, math.cos(math.radians(25)), math.sin(math.radians(25))), -0.15, 0.5),
         'front': ((0.0, 1.0, 0.0), (0.0, 0.0, 1.0), 0.0, 1.0)}


def material_colours(root, materials, overrides=None):
    """Texture (or None) and diffuse colour of every material from the material scripts."""
    text = ''.join(p.read_text(encoding='utf-8', errors='replace')
                   for p in room_packages.glob_files(root, 'materials/scripts', '*.material'))
    result = {}
    for name in materials:
        block = re.search(r'^material ' + re.escape(name) + r'\b[^\n]*\n\{.*?^\}', text, re.M | re.S).group(0)
        diffuse = np.array([float(x) for x in re.search(r'diffuse ([\d.]+) ([\d.]+) ([\d.]+)', block).groups()])
        texture = re.search(r'^\s*texture\s+(\S+)', block, re.M)
        path = (overrides or {}).get(name) or (room_packages.resolve(root, 'materials/textures/' + texture.group(1)) if texture else None)
        image = np.asarray(Image.open(path).convert('RGB'), dtype=np.float64) if path else None
        result[name] = (image, diffuse)
    return result


def triangle_colours(root, positions, uvs, faces_by_material, overrides=None):
    """Triangles and their flat colours (0..255)."""
    colours, triangles = [], []
    table = material_colours(root, sorted(faces_by_material), overrides)
    for name in sorted(faces_by_material):
        tri = np.asarray(faces_by_material[name], dtype=np.int64)
        image, diffuse = table[name]
        if image is None:
            colour = np.tile(255.0 * diffuse, (len(tri), 1))
        else:
            uv = uvs[tri].mean(1)
            h, w = image.shape[:2]
            colour = image[np.floor(uv[:, 1] * h).astype(int) % h, np.floor(uv[:, 0] * w).astype(int) % w] * diffuse
        colours.append(colour)
        triangles.append(tri)
    return np.concatenate(triangles), np.concatenate(colours)


def render_view(points, triangles, colours, view):
    """Orthographic depth-buffered render of one view, uint8 RGB."""
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
    for k, (i, j, l) in enumerate(triangles):
        xs = (sx[i], sx[j], sx[l])
        ys = (sy[i], sy[j], sy[l])
        x0, x1 = max(int(math.floor(min(xs))), 0), min(int(math.ceil(max(xs))), width - 1)
        y0, y1 = max(int(math.floor(min(ys))), 0), min(int(math.ceil(max(ys))), height - 1)
        if x0 > x1 or y0 > y1:
            continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        area = (xs[1] - xs[0]) * (ys[2] - ys[0]) - (xs[2] - xs[0]) * (ys[1] - ys[0])
        if abs(area) < 1e-12:
            continue
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


def compare(image, reference):
    """Mean absolute difference per channel (0..255) and silhouette overlap (intersection over union)."""
    difference = float(np.abs(image.astype(np.float64) - reference).mean())
    a, b = image.any(-1), reference.any(-1)
    return difference, float((a & b).sum() / max((a | b).sum(), 1))
