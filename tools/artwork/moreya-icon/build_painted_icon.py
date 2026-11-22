#!/usr/bin/env python3
"""Builds the Moreya application icon files from the two painted sources.

The sources are AI-generated paintings (Codex image generation, 2026-11-22) in the asset source folder, read from the
environment variable ODP_ASSETS_SRC, else from <repo>/assets-src:
- moreya-icon/GateB.png: the Moreya gate with a half-raised portcullis and green light, for 48 pixels and larger,
- moreya-icon/SmallB1.png: the same gate simplified to a few bold shapes, for 16, 24 and 32 pixels, where the detailed
  painting is no longer recognisable (for example in the Windows taskbar).

Outputs:
- dist/moreya.ico (16, 24, 32, 48, 64, 128 and 256 pixels) for the Windows executable and window,
- dist/hicolor/<n>x<n>/apps/moreya.png for 16, 32, 48, 64, 128 and 256 pixels,
- dist/hicolor/scalable/apps/moreya.svg and its copy meta/gui/moreya.svg: an SVG that shows the 256 pixel painting
  from a moreya.png written beside each of them.

Usage: python tools/artwork/moreya-icon/build_painted_icon.py [--repo <worktree>]
"""
import argparse
import os
from pathlib import Path

from PIL import Image

PNG_SIZES = (16, 32, 48, 64, 128, 256)
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)
# Sizes up to this one use the simplified painting.
SMALL_MAX = 32


def source_root(repo):
    """Return the asset source folder: ODP_ASSETS_SRC if set, else <repo>/assets-src."""
    configured = os.environ.get('ODP_ASSETS_SRC')
    return Path(configured) if configured else repo / 'assets-src'


def icon_image(large, small, size):
    """Return the icon at one pixel size, reduced from the painting meant for that size."""
    painting = small if size <= SMALL_MAX else large
    return painting.resize((size, size), Image.LANCZOS)


def svg_text():
    """Return an SVG of 256 x 256 units that shows the 256 pixel painting moreya.png lying next to it."""
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<!-- Moreya application icon: the painted Moreya gate, shown from moreya.png beside this file. Written by '
            'tools/artwork/moreya-icon/build_painted_icon.py. -->\n'
            '<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256">\n'
            '<image width="256" height="256" href="moreya.png"/>\n'
            '</svg>\n')


def main():
    """Read both paintings and write the ICO, PNG and SVG icon files into the repository."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[3])
    args = parser.parse_args()
    repo = args.repo.resolve()
    folder = source_root(repo) / 'moreya-icon'
    large = Image.open(folder / 'GateB.png').convert('RGBA')
    small = Image.open(folder / 'SmallB1.png').convert('RGBA')
    for size in PNG_SIZES:
        target = repo / 'dist' / 'hicolor' / ('%dx%d' % (size, size)) / 'apps' / 'moreya.png'
        target.parent.mkdir(parents=True, exist_ok=True)
        icon_image(large, small, size).save(target, optimize=True)
    images = [icon_image(large, small, size) for size in ICO_SIZES]
    # Each ICO entry is written from its own image, so the small entries keep the simplified painting.
    images[-1].save(repo / 'dist' / 'moreya.ico', format='ICO', sizes=[(s, s) for s in ICO_SIZES],
                    append_images=images[:-1])
    # Each SVG refers to a 256 pixel moreya.png in its own folder, so both copies are identical and self-contained.
    text = svg_text()
    for target in (repo / 'dist/hicolor/scalable/apps/moreya.svg', repo / 'meta/gui/moreya.svg'):
        target.write_text(text, encoding='utf-8', newline='\n')
        icon_image(large, small, 256).save(target.with_suffix('.png'), optimize=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
