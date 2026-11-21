#!/usr/bin/env python3
"""Draws the text-free placeholder of the crossed-out hand shown over a creature while the hand cooldown runs.

Everything is drawn from simple shapes by this script, nothing is taken from another work. The output is
deterministic. The picture is a placeholder under its final image name (HandCooldown/NoPickup); a painted picture
replaces gui/HandCooldownIcon.png later without a code or layout change. Run it from the repository root:

    python tools/gen_hand_cooldown_icon.py

Output: gui/HandCooldownIcon.png (64x64 RGBA).

Needs Pillow.
"""

import os

from PIL import Image, ImageDraw

SIZE = 64
SUPER = 4
CANVAS = SIZE * SUPER

# Aged bone hand with a dark outline, a worn dark red ring and slash (dark, worn dungeon palette)
HAND_FILL = (176, 158, 122, 255)
HAND_OUTLINE = (34, 26, 20, 255)
RING_COLOUR = (150, 36, 30, 255)
RING_EDGE = (34, 16, 14, 255)

# Finger rectangles (left, top, right, bottom) on the 64 px picture, the palm and the thumb
FINGERS = ((19, 14, 25, 33), (26, 10, 32, 33), (33, 11, 39, 33), (40, 16, 46, 35))
PALM = (18, 30, 47, 49)
THUMB = ((13, 31), (22, 38), (22, 46), (17, 42))
OUTLINE_WIDTH = 2

OUTPUT = os.path.join("gui", "HandCooldownIcon.png")


def scaled(box):
    """Scales a box or a point list from the 64 px picture to the supersampled canvas."""
    return [value * SUPER for value in box]


def main():
    """Writes the picture."""
    grow = OUTLINE_WIDTH * SUPER
    centre = CANVAS // 2
    outer = 30 * SUPER
    inner = 23 * SUPER
    # Layers: the hand, the ring and the slash over it
    hand_layer = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    hand_draw = ImageDraw.Draw(hand_layer)
    for finger in FINGERS:
        left, top, right, bottom = scaled(finger)
        hand_draw.rounded_rectangle((left - grow, top - grow, right + grow, bottom + grow),
                                    radius=3 * SUPER + grow, fill=HAND_OUTLINE)
    left, top, right, bottom = scaled(PALM)
    hand_draw.rounded_rectangle((left - grow, top - grow, right + grow, bottom + grow), radius=6 * SUPER,
                                fill=HAND_OUTLINE)
    hand_draw.polygon(scaled([c for point in THUMB for c in point]), fill=HAND_OUTLINE)
    for finger in FINGERS:
        left, top, right, bottom = scaled(finger)
        hand_draw.rounded_rectangle((left, top, right, bottom), radius=3 * SUPER, fill=HAND_FILL)
    left, top, right, bottom = scaled(PALM)
    hand_draw.rounded_rectangle((left, top, right, bottom), radius=5 * SUPER, fill=HAND_FILL)
    hand_draw.polygon(scaled([c for point in THUMB for c in point]), fill=HAND_FILL)

    ring_layer = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    ring_draw = ImageDraw.Draw(ring_layer)
    ring_draw.ellipse((centre - outer - SUPER, centre - outer - SUPER, centre + outer + SUPER, centre + outer + SUPER),
                      fill=RING_EDGE)
    ring_draw.ellipse((centre - outer, centre - outer, centre + outer, centre + outer), fill=RING_COLOUR)
    ring_draw.ellipse((centre - inner, centre - inner, centre + inner, centre + inner), fill=(0, 0, 0, 0))
    # Slash from the upper left to the lower right inside the ring
    slash = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    slash_draw = ImageDraw.Draw(slash)
    reach = int(inner * 0.72)
    slash_draw.line((centre - reach, centre - reach, centre + reach, centre + reach), fill=RING_EDGE,
                    width=9 * SUPER)
    slash_draw.line((centre - reach, centre - reach, centre + reach, centre + reach), fill=RING_COLOUR,
                    width=6 * SUPER)

    result = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    result.alpha_composite(hand_layer)
    result.alpha_composite(ring_layer)
    result.alpha_composite(slash)
    result = result.resize((SIZE, SIZE), Image.LANCZOS)
    result.save(OUTPUT)


if __name__ == "__main__":
    main()
