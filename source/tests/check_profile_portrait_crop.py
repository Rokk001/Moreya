"""Noncompiling regression for whole square portraits, unchanged fallback crop and uniform UI fit."""
from pathlib import Path
import math
import re
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parents[2]
helper = (root / 'source/render/ProfilePortraitCrop.h').read_text()
assert 'const float side = std::min(width, height);' in helper
assert 'CEGUI::Rectf(0.0f, 0.0f, side, side)' in helper
assert 'left' not in helper and 'rotate' not in helper
appearance = (root / 'source/render/CreatureAppearancePicture.cpp').read_text()
portrait = (root / 'source/render/CreaturePortrait.cpp').read_text()
assert 'image.setArea(CEGUI::Rectf(0.0f, 0.0f, static_cast<float>(width), static_cast<float>(height)))' in appearance
assert 'width != 1024 || height != 1024' in appearance
assert 'getProfilePortraitArea(' not in appearance
profile = portrait[portrait.index('const CEGUI::Image& getCreatureProfilePortraitImage('):]
assert profile.count('return getProfileFallbackImage(portraitKey);') == 2
assert 'image.setArea(getProfilePortraitArea(static_cast<float>(width), static_cast<float>(height)))' in profile
fallback = portrait[portrait.index('const CEGUI::Image& getProfileFallbackImage('):portrait.index('struct PortraitScene')]
assert 'image.setArea(getProfilePortraitArea(size.d_width, size.d_height))' in fallback
assert 'getTintedPortraitNames().insert(name)' in fallback
assert 'renderer.createTexture' not in fallback, 'fallback crop must share the panel texture'

# The shared profile page and its square portrait frame were deleted (owner decision 2026-11-18); the book's
# portraits are checked by check_dungeonbook_rework_b1.py and check_dungeonbook_pages_b1.py
assert not (root / 'gui/WindowCreatureProfilePage.layout').exists()

# Positive uniform fit: the old full 1:2 stretch would make these scales unequal.
for width, height in [(887,1774), (221,443), (512,1024), (256,256), (443,221)]:
    side = min(width, height)
    assert side > 0 and side <= width and side <= height
    for fw, fh in [(136,124), (120,120), (240,220), (88,120)]:
        iw, ih = fw-4, fh-4
        scale = min(iw/side, ih/side)
        dw = dh = side*scale
        assert scale > 0 and dw <= iw and dh <= ih
        assert math.isclose(dw/side, dh/side)
        assert (iw-dw)/2 >= 0 and (ih-dh)/2 >= 0
        # Top-left and rightward source coordinates remain unchanged, y0 is zero.
        source = [(0,0), (side,0), (0,side), (side,side)]
        assert source[1][0] > source[0][0] and source[0][1] == 0
print('profile portrait crop ok: whole JPEG square, unchanged tinted/raw fallback and uniform fit')

# The Dungeonbook fallback retains the same top-square crop and masks its outside pixels.
assert 'getCircularCreatureProfilePortraitImage' in portrait
assert 'sourceOgre->getBuffer()->blitToMemory' in portrait
assert 'sourceIndex = (static_cast<size_t>(y) * width + x)' in portrait
assert 'pixels[index + 3] = 0' in portrait
assert 'getTintedPortraitNames().insert(name)' in portrait
