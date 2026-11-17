#!/usr/bin/env python3
"""Draws the placeholder icons of the creature skills until their painted icons exist.

Every skill of config/creatureSkills.cfg (the path skills and the tier-4 skills) gets an image named
by its skill id in gui/CreatureSkillIcons.imageset. Skills of the same kind share one picture: the
iron frame of the game's Lightning icon (gui/ODIcons.png), the game's basalt HUD texture
(gui/ODHudSurface.png) and a simple sign of the kind drawn from shapes by this script. The painted
icons replace the pictures later under the same image names, without a code or layout change.

The output is deterministic. Run it from the repository root to write the pictures again:

    python tools/gen_skill_placeholder_icons.py

Output:
    gui/CreatureSkillIcons.png        atlas of one 256x256 picture per skill kind
    gui/CreatureSkillIcons.imageset   one image per skill id, pointing at the picture of its kind

Needs Pillow.
"""

import math
import re
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "creatureSkills.cfg"
ICONS = ROOT / "gui" / "ODIcons.png"
HUD = ROOT / "gui" / "ODHudSurface.png"
OUT_PNG = ROOT / "gui" / "CreatureSkillIcons.png"
OUT_IMAGESET = ROOT / "gui" / "CreatureSkillIcons.imageset"

CELL = 256
S = 512                      # drawing size of one picture, scaled down to CELL
COLUMNS = 8
FRAME = 28                   # iron frame width at drawing size
LIGHTNING_CELL = (512, 1536)  # position of LightningButton in gui/ODIcons.png

IVORY = ((236, 226, 200, 255), (120, 104, 80, 255))
IRON = ((150, 142, 134, 255), (44, 40, 38, 255))
RED = ((232, 76, 60, 255), (100, 16, 12, 255))
GOLD = ((255, 214, 120, 255), (160, 92, 24, 255))
GREEN = ((150, 220, 90, 255), (34, 90, 20, 255))
BLUE = ((130, 190, 255, 255), (24, 60, 130, 255))
VIOLET = ((200, 140, 255, 255), (70, 30, 120, 255))
ORANGE = ((255, 170, 70, 255), (150, 50, 10, 255))
BROWN = ((176, 124, 76, 255), (70, 42, 22, 255))
TEAL = ((120, 220, 200, 255), (20, 90, 80, 255))
ICE = ((220, 244, 255, 255), (90, 150, 200, 255))


# ------------------------------------------------------------------ drawing helpers

def mask():
    """Returns an empty drawing mask."""
    return Image.new("L", (S, S), 0)


def poly(points):
    """Returns a polygon mask."""
    m = mask()
    ImageDraw.Draw(m).polygon(points, fill=255)
    return m


def ellipse(box):
    """Returns an ellipse mask."""
    m = mask()
    ImageDraw.Draw(m).ellipse(box, fill=255)
    return m


def rect(box):
    """Returns a rectangle mask."""
    m = mask()
    ImageDraw.Draw(m).rectangle(box, fill=255)
    return m


def lines(points, width):
    """Returns a mask of a thick poly line."""
    m = mask()
    ImageDraw.Draw(m).line(points, fill=255, width=width, joint="curve")
    return m


def union(*masks):
    """Returns the union of masks."""
    result = mask()
    for m in masks:
        result = ImageChops.lighter(result, m)
    return result


def cut(a, b):
    """Returns mask a without mask b."""
    return ImageChops.subtract(a, b)


def gradient(colours, box):
    """Returns a vertical colour gradient over the box."""
    top, bottom = colours
    g = Image.new("RGBA", (S, S), bottom)
    d = ImageDraw.Draw(g)
    y0, y1 = box[1], box[3]
    for y in range(S):
        t = min(1.0, max(0.0, (y - y0) / float(max(1, y1 - y0))))
        d.line([(0, y), (S, y)], fill=tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(4)))
    return g


def shade(img, m, colours):
    """Paints a mask with a drop shadow, a gradient body, a dark lower edge and a light upper rim."""
    box = m.getbbox()
    if box is None:
        return
    shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    shadow.putalpha(ImageChops.offset(m, 8, 11).filter(ImageFilter.GaussianBlur(8)).point(lambda v: v * 3 // 4))
    img.alpha_composite(shadow)
    body = gradient(colours, box)
    body.putalpha(m)
    img.alpha_composite(body)
    lower = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    lower.putalpha(ImageChops.subtract(m, ImageChops.offset(m, -5, -6)).filter(ImageFilter.GaussianBlur(2))
                   .point(lambda v: v * 2 // 3))
    img.alpha_composite(lower)
    upper = Image.new("RGBA", (S, S), (255, 245, 225, 0))
    upper.putalpha(ImageChops.subtract(m, ImageChops.offset(m, 4, 5)).filter(ImageFilter.GaussianBlur(1))
                   .point(lambda v: v * 2 // 3))
    img.alpha_composite(upper)


def glow(img, centre, radius, colour):
    """Paints a soft coloured light."""
    g = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    x, y = centre
    ImageDraw.Draw(g).ellipse((x - radius, y - radius, x + radius, y + radius), fill=colour)
    img.alpha_composite(g.filter(ImageFilter.GaussianBlur(max(2, radius // 2))))


def star_points(cx, cy, outer, inner, count, turn=-math.pi / 2):
    """Returns the corner points of a star."""
    points = []
    for k in range(count * 2):
        r = outer if k % 2 == 0 else inner
        a = turn + k * math.pi / count
        points.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return points


# ------------------------------------------------------------------ signs

def sword(cx, cy, length, angle):
    """Returns the mask of a sword with its tip pointing along angle (radians)."""
    dx, dy = math.cos(angle), math.sin(angle)
    px, py = -dy, dx
    tip = (cx + dx * length * 0.55, cy + dy * length * 0.55)
    base = (cx - dx * length * 0.2, cy - dy * length * 0.2)
    w = length * 0.09
    blade = poly([(base[0] + px * w, base[1] + py * w), (tip[0] + px * w * 0.4, tip[1] + py * w * 0.4),
                  (tip[0] + dx * w * 2, tip[1] + dy * w * 2),
                  (tip[0] - px * w * 0.4, tip[1] - py * w * 0.4), (base[0] - px * w, base[1] - py * w)])
    g = length * 0.2
    guard = lines([(base[0] + px * g, base[1] + py * g), (base[0] - px * g, base[1] - py * g)], int(length * 0.05))
    hilt_end = (base[0] - dx * length * 0.25, base[1] - dy * length * 0.25)
    hilt = lines([base, hilt_end], int(length * 0.06))
    pommel = ellipse((hilt_end[0] - w * 1.3, hilt_end[1] - w * 1.3, hilt_end[0] + w * 1.3, hilt_end[1] + w * 1.3))
    return union(blade, guard, hilt, pommel)


def heart(cx, cy, r):
    """Returns a heart mask."""
    return union(ellipse((cx - r, cy - r * 0.7, cx, cy + r * 0.3)), ellipse((cx, cy - r * 0.7, cx + r, cy + r * 0.3)),
                 poly([(cx - r * 0.97, cy - r * 0.05), (cx + r * 0.97, cy - r * 0.05), (cx, cy + r * 1.05)]))


def cross(cx, cy, r):
    """Returns a plus sign mask."""
    t = r * 0.36
    return union(rect((cx - t, cy - r, cx + t, cy + r)), rect((cx - r, cy - t, cx + r, cy + t)))


def shield(cx, cy, r):
    """Returns a shield mask."""
    return poly([(cx - r, cy - r), (cx + r, cy - r), (cx + r, cy), (cx + r * 0.6, cy + r * 0.7), (cx, cy + r * 1.15),
                 (cx - r * 0.6, cy + r * 0.7), (cx - r, cy)])


def chevrons(cx, cy, r, count=2, up=False, down=False):
    """Returns the mask of pointing chevrons (right, up or down)."""
    result = mask()
    for k in range(count):
        o = (k - (count - 1) / 2.0) * r * 0.75
        if up:
            pts = [(cx - r, cy + r * 0.5 + o), (cx, cy - r * 0.5 + o), (cx + r, cy + r * 0.5 + o)]
        elif down:
            pts = [(cx - r, cy - r * 0.5 + o), (cx, cy + r * 0.5 + o), (cx + r, cy - r * 0.5 + o)]
        else:
            pts = [(cx - r * 0.5 + o, cy - r), (cx + r * 0.5 + o, cy), (cx - r * 0.5 + o, cy + r)]
        result = union(result, lines(pts, int(r * 0.3)))
    return result


def hourglass(cx, cy, r):
    """Returns an hourglass mask."""
    return union(poly([(cx - r * 0.7, cy - r), (cx + r * 0.7, cy - r), (cx + r * 0.08, cy), (cx + r * 0.7, cy + r),
                       (cx - r * 0.7, cy + r), (cx - r * 0.08, cy)]),
                 rect((cx - r * 0.85, cy - r * 1.12, cx + r * 0.85, cy - r * 0.95)),
                 rect((cx - r * 0.85, cy + r * 0.95, cx + r * 0.85, cy + r * 1.12)))


def drop(cx, cy, r):
    """Returns a drop mask."""
    return union(ellipse((cx - r, cy - r * 0.2, cx + r, cy + r * 1.8)),
                 poly([(cx - r * 0.86, cy + r * 0.3), (cx + r * 0.86, cy + r * 0.3), (cx, cy - r * 1.3)]))


def ring(cx, cy, r, width):
    """Returns a ring mask."""
    return cut(ellipse((cx - r, cy - r, cx + r, cy + r)),
               ellipse((cx - r + width, cy - r + width, cx + r - width, cy + r - width)))


def fist(cx, cy, r):
    """Returns a raised fist mask."""
    knuckles = union(*[ellipse((cx - r + k * r * 0.5, cy - r * 0.9, cx - r * 0.42 + k * r * 0.5, cy - r * 0.2))
                       for k in range(4)])
    palm = poly([(cx - r, cy - r * 0.55), (cx + r, cy - r * 0.55), (cx + r * 0.9, cy + r * 0.35),
                 (cx - r * 0.9, cy + r * 0.35)])
    wrist = rect((cx - r * 0.6, cy + r * 0.3, cx + r * 0.6, cy + r * 1.2))
    thumb = poly([(cx - r, cy - r * 0.2), (cx - r * 0.2, cy - r * 0.05), (cx - r * 0.25, cy + r * 0.2),
                  (cx - r * 1.05, cy + r * 0.1)])
    return union(knuckles, palm, wrist, thumb)


def skull(cx, cy, r):
    """Returns a skull mask with eye holes."""
    head = union(ellipse((cx - r, cy - r, cx + r, cy + r * 0.8)), rect((cx - r * 0.55, cy + r * 0.4, cx + r * 0.55,
                                                                         cy + r * 1.05)))
    eyes = union(ellipse((cx - r * 0.62, cy - r * 0.2, cx - r * 0.12, cy + r * 0.32)),
                 ellipse((cx + r * 0.12, cy - r * 0.2, cx + r * 0.62, cy + r * 0.32)))
    teeth = union(*[rect((cx - r * 0.42 + k * r * 0.3, cy + r * 0.72, cx - r * 0.3 + k * r * 0.3, cy + r * 1.05))
                    for k in range(3)])
    return cut(cut(head, eyes), teeth)


def cloud(cx, cy, r):
    """Returns a cloud mask."""
    return union(ellipse((cx - r, cy - r * 0.3, cx - r * 0.1, cy + r * 0.5)),
                 ellipse((cx - r * 0.55, cy - r * 0.75, cx + r * 0.4, cy + r * 0.3)),
                 ellipse((cx + r * 0.05, cy - r * 0.45, cx + r, cy + r * 0.5)),
                 rect((cx - r * 0.6, cy + r * 0.05, cx + r * 0.6, cy + r * 0.5)))


def burst(cx, cy, r, count=10):
    """Returns a jagged burst mask."""
    return poly(star_points(cx, cy, r, r * 0.45, count))


def spiral(cx, cy, r, width):
    """Returns a spiral mask."""
    pts = []
    for k in range(120):
        a = k * 0.17
        rr = r * k / 120.0
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    return lines(pts, width)


def snowflake(cx, cy, r):
    """Returns a snowflake mask."""
    result = mask()
    for k in range(6):
        a = k * math.pi / 3
        ex, ey = cx + r * math.cos(a), cy + r * math.sin(a)
        result = union(result, lines([(cx, cy), (ex, ey)], int(r * 0.13)))
        for f in (0.55, 0.8):
            bx, by = cx + r * f * math.cos(a), cy + r * f * math.sin(a)
            for side in (-1, 1):
                b = a + side * 0.7
                result = union(result, lines([(bx, by), (bx + r * 0.22 * math.cos(b), by + r * 0.22 * math.sin(b))],
                                             int(r * 0.09)))
    return result


def pickaxe(cx, cy, r):
    """Returns a pickaxe mask."""
    handle = lines([(cx - r * 0.7, cy + r), (cx + r * 0.4, cy - r * 0.5)], int(r * 0.16))
    head = poly([(cx - r * 0.5, cy - r * 0.95), (cx + r * 0.2, cy - r * 0.75), (cx + r, cy - r * 0.1),
                 (cx + r * 0.35, cy - r * 0.45), (cx - r * 0.25, cy - r * 0.55)])
    return union(handle, head)


def flag(cx, cy, r):
    """Returns a banner on a pole."""
    pole = rect((cx - r * 0.8, cy - r, cx - r * 0.62, cy + r * 1.1))
    cloth = poly([(cx - r * 0.62, cy - r), (cx + r, cy - r * 0.85), (cx + r * 0.6, cy - r * 0.35), (cx + r * 0.95, cy + r * 0.15),
                  (cx - r * 0.62, cy + r * 0.05)])
    return union(pole, cloth)


def coins(cx, cy, r):
    """Returns a stack of coins."""
    result = mask()
    for k in range(4):
        y = cy + r * 0.7 - k * r * 0.42
        result = union(result, ellipse((cx - r, y - r * 0.32, cx + r, y + r * 0.32)))
    return result


def eye(cx, cy, r):
    """Returns an open eye mask with a pupil hole."""
    lens = poly([(cx - r, cy)] + [(cx + r * math.cos(a), cy - r * 0.6 * math.sin(a)) for a in
                                  [k * math.pi / 12 for k in range(1, 12)]] + [(cx + r, cy)] +
                [(cx + r * math.cos(a), cy + r * 0.6 * math.sin(a)) for a in [k * math.pi / 12 for k in range(11, 0, -1)]])
    return cut(lens, ellipse((cx - r * 0.25, cy - r * 0.25, cx + r * 0.25, cy + r * 0.25)))


def arrow(cx, cy, r, angle):
    """Returns an arrow mask pointing along angle."""
    dx, dy = math.cos(angle), math.sin(angle)
    px, py = -dy, dx
    tail = (cx - dx * r, cy - dy * r)
    head = (cx + dx * r * 0.45, cy + dy * r * 0.45)
    tip = (cx + dx * r, cy + dy * r)
    shaft = lines([tail, head], int(r * 0.22))
    point = poly([tip, (head[0] + px * r * 0.42, head[1] + py * r * 0.42), (head[0] - px * r * 0.42, head[1] - py * r * 0.42)])
    return union(shaft, point)


def bomb(cx, cy, r):
    """Returns a round bomb with a fuse."""
    return union(ellipse((cx - r, cy - r * 0.7, cx + r, cy + r * 1.3)), rect((cx - r * 0.25, cy - r, cx + r * 0.25, cy - r * 0.6)),
                 lines([(cx, cy - r), (cx + r * 0.3, cy - r * 1.35), (cx + r * 0.7, cy - r * 1.3)], int(r * 0.1)))


def dashed_ring(cx, cy, r, width):
    """Returns a ring broken into dashes."""
    result = mask()
    for k in range(12):
        a0 = k * math.pi / 6
        pts = [(cx + r * math.cos(a0 + t * 0.03), cy + r * math.sin(a0 + t * 0.03)) for t in range(10)]
        result = union(result, lines(pts, width))
    return result


def broken_sword(cx, cy, r):
    """Returns a sword broken in two."""
    whole = sword(cx, cy, r * 2.2, -math.pi / 4)
    gap = poly([(cx - r * 0.3, cy - r * 0.05), (cx + r * 0.05, cy - r * 0.45), (cx + r * 0.2, cy - r * 0.3),
                (cx - r * 0.15, cy + r * 0.1)])
    return cut(whole, gap)


# ------------------------------------------------------------------ one picture per kind

C = S // 2


def k_passive_dmg(img):
    shade(img, sword(C, C + 20, 380, -math.pi / 4), IRON)


def k_passive_spell(img):
    glow(img, (C, C), 120, (200, 140, 255, 140))
    shade(img, poly(star_points(C, C, 150, 60, 5)), VIOLET)


def k_passive_alldmg(img):
    shade(img, sword(C, C + 20, 380, -math.pi / 4), IRON)
    shade(img, sword(C, C + 20, 380, -3 * math.pi / 4), IRON)


def k_passive_hp(img):
    shade(img, heart(C, C - 10, 140), RED)


def k_passive_crit(img):
    shade(img, union(ring(C, C, 140, 26), ring(C, C, 70, 22), cross(C, C, 175)), GOLD)


def k_passive_cd(img):
    shade(img, hourglass(C, C, 140), BLUE)


def k_passive_avoid(img):
    shade(img, arrow(C, C, 150, -math.pi / 2 + 0.6), TEAL)
    shade(img, lines([(C - 120, C + 140), (C - 40, C + 40), (C - 130, C - 40)], 30), TEAL)


def k_passive_ar(img):
    shade(img, sword(C - 30, C + 30, 330, -math.pi / 4), IRON)
    shade(img, chevrons(C + 120, C + 90, 60, 2, up=True), GOLD)


def k_passive_dr(img):
    shade(img, shield(C, C - 20, 140), IRON)


def k_passive_dig(img):
    shade(img, pickaxe(C, C, 150), BROWN)


def k_passive_claim(img):
    shade(img, flag(C, C, 150), RED)


def k_passive_carry(img):
    shade(img, coins(C, C, 130), GOLD)


def k_passive_move(img):
    shade(img, chevrons(C, C, 120, 3), GREEN)


def k_passive_wake(img):
    shade(img, eye(C, C, 160), IVORY)


def k_passive_manacost(img):
    shade(img, drop(C, C - 40, 100), BLUE)
    shade(img, chevrons(C + 130, C + 110, 50, 2, down=True), BLUE)


def k_buff_strength(img):
    glow(img, (C, C), 150, (255, 190, 80, 110))
    shade(img, fist(C, C, 120), GOLD)


def k_buff_speed(img):
    glow(img, (C, C), 150, (255, 190, 80, 110))
    shade(img, chevrons(C, C, 120, 3), GOLD)


def k_buff_defense(img):
    glow(img, (C, C), 150, (255, 190, 80, 110))
    shade(img, shield(C, C - 20, 140), GOLD)


def k_aura_strength(img):
    shade(img, ring(C, C, 180, 22), GOLD)
    shade(img, fist(C, C, 95), GOLD)


def k_debuff_weak(img):
    glow(img, (C, C), 150, (150, 70, 200, 110))
    shade(img, broken_sword(C, C, 170), VIOLET)


def k_debuff_slow(img):
    glow(img, (C, C), 150, (150, 70, 200, 110))
    shade(img, hourglass(C, C, 140), VIOLET)


def k_explosion(img):
    glow(img, (C, C), 170, (255, 130, 40, 150))
    shade(img, burst(C, C, 175, 11), ORANGE)


def k_hailstorm(img):
    shade(img, cloud(C, C - 60, 160), ICE)
    for k in range(5):
        x = C - 120 + k * 60
        shade(img, ellipse((x - 16, C + 90 + (k % 2) * 40, x + 16, C + 122 + (k % 2) * 40)), ICE)


def k_gascloud(img):
    glow(img, (C, C), 150, (120, 200, 60, 120))
    shade(img, cloud(C, C + 10, 170), GREEN)


def k_grenade(img):
    shade(img, bomb(C, C + 20, 120), IRON)
    glow(img, (C + 85, C - 135), 26, (255, 180, 80, 255))


def k_guidedbolt(img):
    glow(img, (C, C), 140, (130, 190, 255, 110))
    shade(img, lines([(C - 160, C + 120), (C - 40, C - 30), (C + 60, C + 40), (C + 150, C - 120)], 34), BLUE)
    shade(img, poly([(C + 185, C - 175), (C + 95, C - 135), (C + 175, C - 75)]), BLUE)


def k_whirlwind(img):
    shade(img, spiral(C, C, 170, 30), TEAL)


def k_freeze(img):
    glow(img, (C, C), 150, (180, 230, 255, 120))
    shade(img, snowflake(C, C, 170), ICE)


def k_invisible(img):
    shade(img, dashed_ring(C, C, 150, 26), IVORY)
    shade(img, eye(C, C, 90), IVORY)


def k_teleport(img):
    shade(img, ring(C - 80, C + 60, 90, 22), VIOLET)
    shade(img, ring(C + 80, C - 60, 90, 22), VIOLET)
    shade(img, arrow(C, C, 110, -math.pi / 4), VIOLET)


def k_drain(img):
    shade(img, drop(C, C - 60, 100), RED)
    shade(img, chevrons(C, C + 150, 70, 2, up=True), RED)


def k_raisedead(img):
    glow(img, (C, C), 150, (140, 220, 140, 90))
    shade(img, skull(C, C - 20, 120), IVORY)
    shade(img, chevrons(C, C + 170, 60, 1, up=True), GREEN)


def k_skelarmy(img):
    shade(img, skull(C - 110, C + 40, 70), IVORY)
    shade(img, skull(C + 110, C + 40, 70), IVORY)
    shade(img, skull(C, C - 60, 85), IVORY)


def k_strike(img):
    shade(img, fist(C, C, 120), IRON)
    shade(img, burst(C + 110, C - 120, 60, 7), ORANGE)


def k_heal_self(img):
    glow(img, (C, C), 150, (120, 220, 100, 110))
    shade(img, heart(C, C - 10, 140), RED)
    shade(img, cross(C + 90, C + 80, 55), GREEN)


def k_heal_ally(img):
    glow(img, (C, C), 150, (120, 220, 100, 110))
    shade(img, heart(C - 50, C - 30, 100), RED)
    shade(img, heart(C + 70, C + 30, 90), RED)
    shade(img, cross(C + 120, C + 130, 45), GREEN)


def k_heal_area(img):
    shade(img, ring(C, C, 180, 22), GREEN)
    shade(img, cross(C, C, 100), GREEN)


KINDS = {
    "PASSIVE_dmg%": k_passive_dmg, "PASSIVE_spell%": k_passive_spell, "PASSIVE_alldmg%": k_passive_alldmg,
    "PASSIVE_hp%": k_passive_hp, "PASSIVE_crit": k_passive_crit, "PASSIVE_cd%": k_passive_cd,
    "PASSIVE_avoid": k_passive_avoid, "PASSIVE_ar%": k_passive_ar, "PASSIVE_dr%": k_passive_dr,
    "PASSIVE_dig%": k_passive_dig, "PASSIVE_claim%": k_passive_claim, "PASSIVE_carry%": k_passive_carry,
    "PASSIVE_move%": k_passive_move, "PASSIVE_wake%": k_passive_wake, "PASSIVE_manacost%": k_passive_manacost,
    "BUFF_SELF_StrengthChange": k_buff_strength, "BUFF_SELF_SpeedChange": k_buff_speed,
    "BUFF_SELF_Defense": k_buff_defense, "AURA_ALLY_StrengthChange": k_aura_strength, "DEBUFF_Weak": k_debuff_weak,
    "DEBUFF_Slow": k_debuff_slow, "EXPLOSION": k_explosion, "HAILSTORM": k_hailstorm, "GASCLOUD": k_gascloud,
    "GRENADE": k_grenade, "GUIDEDBOLT": k_guidedbolt, "WHIRLWIND": k_whirlwind, "FREEZE": k_freeze,
    "INVISIBLE": k_invisible, "TELEPORT": k_teleport, "DRAIN": k_drain, "RAISEDEAD": k_raisedead,
    "SKELARMY": k_skelarmy, "STRIKE": k_strike, "HEAL_SELF": k_heal_self, "HEAL_ALLY": k_heal_ally,
    "HEAL_AREA": k_heal_area,
}


# ------------------------------------------------------------------ tile, config, output

def tile(variant):
    """Returns the basalt tile with the game's iron frame; variant shifts the basalt crop."""
    hud = Image.open(HUD).convert("RGBA")
    side = min(hud.width, hud.height)
    x0 = (variant * 211) % max(1, hud.width - side)
    base = hud.crop((x0, 0, x0 + side, side)).resize((S, S), Image.LANCZOS)
    base = Image.blend(base, Image.new("RGBA", (S, S), (0, 0, 0, 255)), 0.3)
    frame = Image.open(ICONS).convert("RGBA").crop(LIGHTNING_CELL + (LIGHTNING_CELL[0] + 256, LIGHTNING_CELL[1] + 256))
    frame = frame.resize((S, S), Image.LANCZOS)
    inner = Image.new("L", (S, S), 255)
    ImageDraw.Draw(inner).rectangle((FRAME, FRAME, S - FRAME, S - FRAME), fill=0)
    base.paste(frame, (0, 0), inner)
    return base


def read_skills():
    """Returns [(skill id, kind)] of every [Skill] and [TierFour] block in config order."""
    skills = []
    block = None
    fields = {}
    for raw in CONFIG.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if line in ("[Skill]", "[TierFour]"):
            block = line
            fields = {}
        elif line in ("[/Skill]", "[/TierFour]"):
            if block == "[Skill]":
                skills.append((fields["Id"], fields["Kind"]))
            else:
                skills.append(("T4_" + fields["Creature"], fields["Kind"]))
            block = None
        elif block is not None and line:
            parts = re.split(r"\s+", line, maxsplit=1)
            fields[parts[0]] = parts[1] if len(parts) > 1 else ""
    return skills


def main():
    """Writes the atlas and the imageset."""
    skills = read_skills()
    kinds = []
    for _, kind in skills:
        if kind not in KINDS:
            print("No placeholder sign for kind " + kind)
            return 1
        if kind not in kinds:
            kinds.append(kind)
    rows = (len(kinds) + COLUMNS - 1) // COLUMNS
    atlas = Image.new("RGBA", (COLUMNS * CELL, rows * CELL), (0, 0, 0, 0))
    cell_of = {}
    for index, kind in enumerate(kinds):
        img = tile(index)
        KINDS[kind](img)
        x, y = (index % COLUMNS) * CELL, (index // COLUMNS) * CELL
        atlas.alpha_composite(img.resize((CELL, CELL), Image.LANCZOS), (x, y))
        cell_of[kind] = (x, y)
    atlas.save(OUT_PNG, optimize=True)
    out = ['<?xml version="1.0" encoding="utf-8"?>',
           '<Imageset autoScaled="true" imagefile="CreatureSkillIcons.png" name="CreatureSkillIcons" '
           'nativeHorzRes="2048" nativeVertRes="1536" version="2">']
    for skill_id, kind in skills:
        x, y = cell_of[kind]
        out.append('    <Image height="%d" name="%s" width="%d" xPos="%d" yPos="%d" />' % (CELL, skill_id, CELL, x, y))
    out.append("</Imageset>")
    OUT_IMAGESET.write_text("\n".join(out) + "\n", encoding="utf-8")
    print("%d skills, %d placeholder pictures" % (len(skills), len(kinds)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
