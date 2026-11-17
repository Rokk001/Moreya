"""Check that the turning swirl of the portal looks round at every moment: no edge or corner of its square shows.

Every particle system that draws the material RoomAmbSwirl turns a square billboard. The check reads the blend mode
of the material and the texture, then draws the sprite turned by every angle from 0 to 89 degrees in 1 degree steps
(bilinear, as the material samples it) the way the material blends it: with scene_blend add the light a pixel adds is
its colour, alpha is ignored. Outcomes asserted for every angle:
- no pixel outside the circle inscribed in the square adds light (more than 1/255), so no corner ever shows;
- the band along the edges of the turned square adds no light, so no straight edge ever shows;
- the swirl itself is still there: at least 300 of the 64x64 texels add light above 40/255.
The material must clamp the texture, so filtering never pulls colour from the opposite edge.
No compile, no game.
"""
from pathlib import Path
import math
import re

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]

material_text = (ROOT / 'materials/scripts/RoomAmbienceCoreObjects.material').read_text(encoding='utf-8')
start = material_text.index('material RoomAmbSwirl')
material = material_text[start:material_text.index('\nmaterial ', start + 1) if '\nmaterial ' in material_text[start + 1:]
                         else len(material_text)]
blend = re.search(r'scene_blend\s+(\w+)', material).group(1)
assert blend in ('add', 'alpha_blend'), blend
assert re.search(r'tex_address_mode\s+clamp', material), 'the swirl texture must be clamped'
texture_name = re.search(r'texture\s+(\S+\.png)', material).group(1)

# Every particle system using the material turns a square billboard.
systems = 0
for path in (ROOT / 'particles').glob('*.particle'):
    text = path.read_text(encoding='utf-8')
    systems += len(re.findall(r'material\s+RoomAmbSwirl\b', text))
assert systems >= 1, 'no particle system draws the swirl'

image = Image.open(ROOT / 'materials/textures' / texture_name).convert('RGBA')
size = image.width
assert image.width == image.height == 64, image.size
pixels = image.load()


def added_light(x, y):
    """Light (0 to 255) the material adds for one texel, by its blend mode."""
    r, g, b, a = pixels[x, y]
    light = max(r, g, b)
    return light if blend == 'add' else light * a / 255.0


light = [[added_light(x, y) for x in range(size)] for y in range(size)]
lit = sum(1 for row in light for v in row if v > 40)
assert lit >= 300, lit


def sample(u, v):
    """Bilinear sample of the added light with clamped addressing at texel coordinates (centre at i + 0.5)."""
    u = min(max(u - 0.5, 0.0), size - 1.0)
    v = min(max(v - 0.5, 0.0), size - 1.0)
    x0, y0 = int(math.floor(u)), int(math.floor(v))
    x1, y1 = min(x0 + 1, size - 1), min(y0 + 1, size - 1)
    fx, fy = u - x0, v - y0
    return (light[y0][x0] * (1 - fx) * (1 - fy) + light[y0][x1] * fx * (1 - fy)
            + light[y1][x0] * (1 - fx) * fy + light[y1][x1] * fx * fy)


half = size / 2.0
worst_corner = 0.0
worst_edge = 0.0
for degrees in range(90):
    angle = math.radians(degrees)
    cos, sin = math.cos(angle), math.sin(angle)
    # Screen pixels of the turned sprite on a canvas holding its corners (radius half * sqrt(2)).
    extent = int(math.ceil(half * math.sqrt(2.0))) + 1
    for sy in range(-extent, extent):
        for sx in range(-extent, extent):
            px, py = sx + 0.5, sy + 0.5
            # Back into texture space.
            u = cos * px + sin * py + half
            v = -sin * px + cos * py + half
            if u < 0.0 or v < 0.0 or u >= size or v >= size:
                continue
            value = sample(u, v)
            if math.hypot(px, py) > half:
                worst_corner = max(worst_corner, value)
            if min(u, v, size - u, size - v) < 1.5:
                worst_edge = max(worst_edge, value)
assert worst_corner <= 1.0, 'a corner of the turning square adds light %.1f/255' % worst_corner
assert worst_edge <= 1.0, 'an edge of the turning square adds light %.1f/255' % worst_edge
print('portal swirl is round at every angle: %d systems, %d lit texels, corners %.1f, edges %.1f'
      % (systems, lit, worst_corner, worst_edge))
