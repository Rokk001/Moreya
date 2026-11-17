"""Check that the loading ring textures are cut out of the painted ring and that its thorns keep the painted shape.

1. tools/make_loading_ring.py run on the painted source crop (gui/loading/loading-ring-painted.png below
   ODP_ASSETS_SRC) gives exactly the committed loading_ring.png and loading_ring_empty.png (at most 1/255 apart), so
   the textures come from the painting and are reproducible.
2. The thorns match the painting: outside the widened band, inside the painted quarter each texture is cut from
   (fill: 6 to 84 degrees, empty track: 252 to 332 degrees, clear of the seams), every opaque texture pixel is
   compared with the painted crop sampled here independently at the same place (bilinear, centre and scale read
   from the tool). The mean colour difference must stay below 4/255 over at least 150 thorn pixels each.
3. The widened band is closed: at every heading (0.5 degree steps) at least 22 of the 24 band pixels are opaque.

Fixed values of this branch: 256x256 textures, band 78 to 102 px. No compile, no game.
"""
from pathlib import Path
import math
import re
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from assets_src import assets_src_dir  # noqa: E402

tool = (ROOT / 'tools/make_loading_ring.py').read_text(encoding='utf-8')


def constant(name):
    """Reads a numeric constant of the tool."""
    match = re.search(r'^' + name + r' = \(?([0-9.]+)(?:, ([0-9.]+))?\)?$', tool, re.M)
    assert match, name
    return tuple(float(v) for v in match.groups() if v is not None)


centre = constant('SOURCE_CENTRE')
scale = constant('SOURCE_THORN_TIP')[0] / constant('TEXTURE_THORN_TIP')[0]
band = (constant('BAND_INNER')[0], constant('BAND_OUTER')[0])
assert band == (78.0, 102.0), band
source_path = assets_src_dir(ROOT) / 'gui/loading/loading-ring-painted.png'
assert source_path.exists(), 'painted source missing: %s' % source_path
painting = np.asarray(Image.open(source_path).convert('RGB'), dtype=float)
folder = ROOT / 'materials/textures/loading'
committed = {name: np.asarray(Image.open(folder / name).convert('RGBA'), dtype=int)
             for name in ('loading_ring.png', 'loading_ring_empty.png')}

# 1. Reproducible from the painting
with tempfile.TemporaryDirectory() as directory:
    subprocess.run([sys.executable, '-I', str(ROOT / 'tools/make_loading_ring.py'), directory], check=True)
    for name, pixels in committed.items():
        built = np.asarray(Image.open(Path(directory) / name).convert('RGBA'), dtype=int)
        assert built.shape == pixels.shape == (256, 256, 4), name
        difference = np.abs(built - pixels).max()
        assert difference <= 1, '%s differs from the painted cut-out by %d' % (name, difference)

# 2. Thorns as painted
ys, xs = np.mgrid[0:256, 0:256].astype(float)
dx, dy = xs + 0.5 - 128.0, ys + 0.5 - 128.0
radius = np.hypot(dx, dy)
heading = np.degrees(np.arctan2(dx, -dy)) % 360.0
source_x = centre[0] + radius * scale * np.sin(np.radians(heading))
source_y = centre[1] - radius * scale * np.cos(np.radians(heading))
x0 = np.floor(source_x).astype(int)
y0 = np.floor(source_y).astype(int)
fx = (source_x - x0)[..., None]
fy = (source_y - y0)[..., None]


def texel(x, y):
    """Painted pixel at index coordinates, clamped to the crop."""
    return painting[np.clip(y, 0, painting.shape[0] - 1), np.clip(x, 0, painting.shape[1] - 1)]


# Bilinear sample at index coordinates, the way the tool reads the painting.
painted = (texel(x0, y0) * (1 - fx) * (1 - fy) + texel(x0 + 1, y0) * fx * (1 - fy)
           + texel(x0, y0 + 1) * (1 - fx) * fy + texel(x0 + 1, y0 + 1) * fx * fy)
for name, (low, high) in (('loading_ring.png', (6.0, 84.0)), ('loading_ring_empty.png', (252.0, 332.0))):
    pixels = committed[name]
    thorn = ((radius < band[0] - 1.0) | (radius > band[1] + 1.0)) & (heading >= low) & (heading <= high) \
        & (pixels[..., 3] > 200)
    count = int(thorn.sum())
    assert count >= 150, '%s: only %d thorn pixels' % (name, count)
    mean = float(np.abs(pixels[..., :3][thorn] - painted[thorn]).mean())
    assert mean < 4.0, '%s: thorns differ from the painting by %.1f/255 on average' % (name, mean)
    print('%s: %d thorn pixels, mean difference to the painting %.1f/255' % (name, count, mean))

# 3. Closed widened band
for name, pixels in committed.items():
    for step in range(720):
        angle = math.radians(step / 2.0)
        opaque = 0
        for r in range(int(band[0]), int(band[1])):
            x = int(128 + (r + 0.5) * math.sin(angle))
            y = int(128 - (r + 0.5) * math.cos(angle))
            opaque += pixels[y, x, 3] > 200
        assert opaque >= 22, '%s: band open or thin at %.1f degrees (%d of 24 px)' % (name, step / 2.0, opaque)
print('loading ring is cut out of the painting, thorns as painted, band closed')
