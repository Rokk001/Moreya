#!/usr/bin/env python3
"""Cut the menu button template and the load screen frame out of the chosen menu sheet.

The sheet is the painted variant 2 of the menu concepts ("weathered timber with aged iron bindings"), kept with the asset
sources: <ODP_ASSETS_SRC>/ingame-qs-9/d1/variant-2.png (1920x1200). The tool writes gui/ODMenuTemplate.png and
gui/ODMenuTemplate.imageset:

* the four states of the button template (normal, hovered, pressed, disabled), each 400x120, with the painted caption
  removed from the planks and the outline cut free; each state is split into left cap, left fill, centre knobs, right fill
  and right cap so a button of any width keeps its caps and knobs undistorted (OD/MenuTextButton in OD.looknfeel);
* the load screen panel with its frame, the list inset and empty plank rows, the painted widgets removed (the game draws
  its own filter buttons, list rows and buttons over it);
* the compact form of the template that the sheet paints for the filter and command buttons of the load screen, in the
  same four states, split into left cap, fill and right cap;
* the highlighted list row of the sheet for the selected entry.

Usage: python tools/make_menu_template.py [path of variant-2.png]
"""
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from assets_src import assets_src_dir  # noqa: E402

SHEET_RELATIVE = "ingame-qs-9/d1/variant-2.png"
OUT_PNG = REPO / "gui" / "ODMenuTemplate.png"
OUT_IMAGESET = REPO / "gui" / "ODMenuTemplate.imageset"

# Button template: the normal state of the template column sits at sheet (56, 380); the other states are the same
# template painted lower in the column (offsets measured by aligning the iron caps to the normal state).
BUTTON_ORIGIN = (56, 380)
BUTTON_SIZE = (400, 120)
STATES = (("Normal", 0, 0), ("Hover", 1, 144), ("Pushed", 2, 290), ("Disabled", 1, 438))
# Columns of the five pieces inside the 400x120 state: left cap, left fill, centre knobs, right fill, right cap.
PIECES = (("LeftCap", 0, 62), ("LeftFill", 62, 173), ("Centre", 173, 229), ("RightFill", 229, 338), ("RightCap", 338, 400))
# Outline of the template in state coordinates: the plate with cut corners and the two diamond knobs.
PLATE = [(28.5, 8.5), (371.5, 8.5), (397.5, 34.5), (397.5, 86.5), (371.5, 112.5), (28.5, 112.5), (2.5, 86.5), (2.5, 34.5)]
KNOBS = ([(178.0, 9.5), (201.0, 2.0), (224.0, 9.5)], [(178.0, 111.5), (201.0, 117.5), (224.0, 111.5)])
# Region of the painted caption "Campaign" in state coordinates; only letter pixels and their shadow inside it are replaced.
CAPTION_BOX = (108, 34, 296, 88)
# The pointer hand of the sheet covers the right end of the hovered state; that end is the mirrored left end.
HOVER_MIRROR_FROM = 300

# Load screen panel of the sheet (frame outline and knobs in panel coordinates) and the parts painted inside it.
PANEL_ORIGIN = (1222, 283)
PANEL_SIZE = (662, 775)
PANEL_PLATE = [(15.5, 14.5), (646.5, 14.5), (658.5, 26.5), (658.5, 747.5), (646.5, 759.5), (15.5, 759.5), (3.5, 747.5),
               (3.5, 26.5)]
PANEL_KNOBS = ([(300.0, 15.0), (328.0, 2.0), (356.0, 15.0)], [(300.0, 759.0), (328.0, 772.0), (356.0, 759.0)])
PANEL_TABS = (1250, 352, 1862, 426)          # the four painted filter buttons (sheet coordinates)
PANEL_BUTTONS = (1255, 900, 1858, 1010)      # Delete, Back and Confirm
PANEL_CLEAN_BAND = (1250, 318, 1862, 351)    # empty panel wood above the filter buttons
LIST_PLANKS = (1272, 455, 1793, 869)         # plank rows of the list inset
LIST_SCROLLBAR = (1793, 452, 1842, 872)      # painted scrollbar column inside the inset
SELECTED_ROW = (1272, 484, 1792, 524)        # the highlighted first entry
ROW_PITCH = 40

# Compact form of the template that the sheet paints for the buttons inside the load screen (filter buttons, Delete, Back,
# Confirm): no knobs and slim caps. Normal is "Back", hovered "Confirm", pressed "Delete" (sheet x range of each, the
# rows are shared); disabled is the normal state with the colour change from normal to disabled of the full template.
COMPACT_ROWS = (910, 986)
COMPACT_STATES = (("Normal", 1465, 1636), ("Hover", 1660, 1849), ("Pushed", 1263, 1441))
COMPACT_MARGIN = 4
COMPACT_CAP = 26
COMPACT_CHAMFER = 7.0
COMPACT_PLANK_ROWS = (18, 58)

ATLAS_SIZE = (1188, 1100)
STATE_PITCH = 122
SELECTED_AT = (0, 490)
PANEL_AT = (524, 0)
COMPACT_AT = (0, 780)
COMPACT_PITCH = 80


def dilate(mask, steps):
    """Grow a boolean mask by the given number of 4-neighbour steps."""
    out = mask.copy()
    for _ in range(steps):
        grown = out.copy()
        grown[1:] |= out[:-1]
        grown[:-1] |= out[1:]
        grown[:, 1:] |= out[:, :-1]
        grown[:, :-1] |= out[:, 1:]
        out = grown
    return out


def box_blur(plane, radius):
    """Separable box blur of one float plane with edge padding."""
    kernel = np.ones(2 * radius + 1) / (2 * radius + 1)
    rows = np.apply_along_axis(lambda v: np.convolve(np.pad(v, radius, mode="edge"), kernel, mode="valid"), 1, plane)
    return np.apply_along_axis(lambda v: np.convolve(np.pad(v, radius, mode="edge"), kernel, mode="valid"), 0, rows)


def lowpass(image, mask, radius=10):
    """Local mean colour of the unmasked pixels (normalised blur), used as the light of the filled pixels."""
    weight = (~mask).astype(np.float32)
    total = box_blur(weight, radius)
    low = np.stack([box_blur(image[..., c] * weight, radius) for c in range(3)], -1) / np.maximum(total, 1e-3)[..., None]
    if (total < 0.05).any():
        wide = box_blur(weight, 3 * radius)
        far = np.stack([box_blur(image[..., c] * weight, 3 * radius) for c in range(3)], -1) / np.maximum(wide, 1e-3)[..., None]
        low = np.where((total < 0.05)[..., None], far, low)
    return np.stack([box_blur(low[..., c], 3) for c in range(3)], -1)


def fill_along_rows(image, mask, period=37, one_sided=False, smooth=0):
    """Replace masked pixels by wood of the same row: the grain detail comes from `period` pixels to the left and to the
    right (blended across each masked run; only from the left when one_sided), the light from the surrounding unmasked
    pixels. With smooth > 0 the filled grain is blurred along the rows by that radius, which hides the seams of the
    repeated copies and keeps the horizontal grain."""
    low = lowpass(image, mask)
    detail = image - low
    height, width = mask.shape
    from_left = detail.copy()
    from_right = detail.copy()
    for x in range(width):
        column = mask[:, x]
        if column.any():
            from_left[column, x] = from_left[column, max(x - period, 0)]
    for x in range(width - 1, -1, -1):
        column = mask[:, x]
        if column.any():
            from_right[column, x] = from_right[column, min(x + period, width - 1)]
    out = detail.copy()
    for y in range(height):
        x = 0
        while x < width:
            if not mask[y, x]:
                x += 1
                continue
            start = x
            while x < width and mask[y, x]:
                x += 1
            t = ((np.arange(start, x) - start + 0.5) / (x - start))[:, None] * (0.0 if one_sided else 1.0)
            out[y, start:x] = (1.0 - t) * from_left[y, start:x] + t * from_right[y, start:x]
    if smooth:
        kernel = np.ones(2 * smooth + 1) / (2 * smooth + 1)
        blurred = np.stack([np.apply_along_axis(
            lambda v: np.convolve(np.pad(v, smooth, mode="edge"), kernel, mode="valid"), 1, out[..., c]) for c in range(3)], -1)
        out = np.where(mask[..., None], blurred, out)
    return low + out


def fill_from_band(image, box, band, strength=0.6):
    """Fill a rectangle with the texture of a clean band, repeated downwards with every copy shifted sideways by a third
    of its width, at reduced strength and matched to the light around the rectangle (the game draws its buttons over
    most of it)."""
    x0, y0, x1, y1 = box
    bx0, by0, bx1, by1 = band
    source = image[by0:by1, x0:x1].copy()
    rows = []
    shift = 0
    while sum(len(r) for r in rows) < y1 - y0:
        rows.append(np.roll(source, shift, axis=1))
        shift += (x1 - x0) // 3
    tile = np.concatenate(rows, 0)[:y1 - y0]
    # Light of the wood: blend from the smoothed rows just above to the smoothed rows just below the rectangle.
    above = np.stack([box_blur(image[y0 - 6:y0, x0:x1, c], 12) for c in range(3)], -1).mean(axis=0)
    below = np.stack([box_blur(image[y1:y1 + 6, x0:x1, c], 12) for c in range(3)], -1).mean(axis=0)
    t = ((np.arange(y1 - y0) + 0.5) / (y1 - y0))[:, None, None]
    light = (1.0 - t) * above[None] + t * below[None]
    tile_light = np.stack([box_blur(tile[..., c], 14) for c in range(3)], -1)
    image[y0:y1, x0:x1] = light + strength * (tile - tile_light)


def outline_alpha(size, polygons, supersample=4):
    """Anti-aliased alpha of the given polygons."""
    canvas = Image.new("L", (size[0] * supersample, size[1] * supersample), 0)
    draw = ImageDraw.Draw(canvas)
    for polygon in polygons:
        draw.polygon([(x * supersample, y * supersample) for x, y in polygon], fill=255)
    return np.asarray(canvas.resize(size, Image.LANCZOS)).astype(np.float32)


def caption_mask(state_image, disabled):
    """Letters of the painted caption and their dark shadow inside the caption box."""
    red, green, blue = state_image[..., 0], state_image[..., 1], state_image[..., 2]
    luminance = state_image.mean(axis=2)
    if disabled:
        letters = (luminance > 88) & ((red - blue) < 40)
    else:
        letters = (red > 150) & (green > 120) & (blue > 85)
    box = np.zeros_like(letters)
    x0, y0, x1, y1 = CAPTION_BOX
    box[y0:y1, x0:x1] = True
    letters &= box
    near = dilate(letters, 6)
    kernel = np.ones(15) / 15.0
    wood = np.apply_along_axis(lambda v: np.convolve(v, kernel, mode="same"), 1, luminance)
    shadow = near & (luminance < wood - 6)
    return dilate(dilate(letters, 2) | shadow, 2)


def button_states(sheet):
    """The four template states as 400x120 RGBA float arrays."""
    width, height = BUTTON_SIZE
    alpha = outline_alpha(BUTTON_SIZE, [PLATE] + list(KNOBS))
    states = []
    for name, dx, dy in STATES:
        x0, y0 = BUTTON_ORIGIN[0] + dx, BUTTON_ORIGIN[1] + dy
        image = sheet[y0:y0 + height, x0:x0 + width].copy()
        if name == "Hover":
            mirrored = image[:, ::-1]
            blend = np.clip((np.arange(width) - HOVER_MIRROR_FROM) / 12.0, 0.0, 1.0)[None, :, None]
            image = image * (1.0 - blend) + mirrored * blend
        image = fill_along_rows(image, caption_mask(image, name == "Disabled"))
        states.append((name, np.dstack([image, alpha])))
    return states


def load_panel(sheet):
    """The load screen panel without its painted widgets, as RGBA float array."""
    image = sheet.copy()
    # Empty list: the highlighted entry becomes the plank row below it, the painted scrollbar becomes planks.
    x0, y0, x1, y1 = SELECTED_ROW
    image[y0:y1, x0:x1] = sheet[y0 + ROW_PITCH:y1 + ROW_PITCH, x0:x1]
    x0, y0, x1, y1 = LIST_SCROLLBAR
    mask = np.zeros(image.shape[:2], bool)
    mask[y0:y1, x0:x1] = True
    region = (LIST_PLANKS[0], y0, x1, y1)
    part = image[region[1]:region[3], region[0]:region[2]]
    image[region[1]:region[3], region[0]:region[2]] = fill_along_rows(part, mask[region[1]:region[3], region[0]:region[2]], 50,
                                                                                   one_sided=True)
    # Filter buttons and the three buttons are drawn by the game; the panel wood continues under them.
    fill_from_band(image, PANEL_TABS, PANEL_CLEAN_BAND)
    fill_from_band(image, PANEL_BUTTONS, PANEL_CLEAN_BAND)
    px, py = PANEL_ORIGIN
    crop = image[py:py + PANEL_SIZE[1], px:px + PANEL_SIZE[0]]
    alpha = outline_alpha(PANEL_SIZE, [PANEL_PLATE] + list(PANEL_KNOBS))
    return np.dstack([crop, alpha])


def compact_states(sheet, big_states):
    """The four states of the compact template as RGBA float arrays of their own widths."""
    y0, y1 = COMPACT_ROWS
    height = y1 - y0
    states = []
    for name, left, right in COMPACT_STATES:
        x0, x1 = left - COMPACT_MARGIN, right + COMPACT_MARGIN
        image = sheet[y0:y1, x0:x1].copy()
        width = x1 - x0
        letters = caption_mask_box(image, (COMPACT_CAP, COMPACT_PLANK_ROWS[0], width - COMPACT_CAP, COMPACT_PLANK_ROWS[1]))
        image = fill_along_rows(image, letters, 23, smooth=6)
        m, c = COMPACT_MARGIN + 0.5, COMPACT_CHAMFER
        outline = [(m + c, m), (width - m - c, m), (width - m, m + c), (width - m, height - m - c), (width - m - c, height - m),
                   (m + c, height - m), (m, height - m - c), (m, m + c)]
        states.append((name, np.dstack([image, outline_alpha((width, height), [outline])])))
    # Disabled: the colour change that turns the normal full template into its disabled state, fitted on the caps and
    # rails (the caption area left out), applied to the compact normal state.
    normal = big_states[0][1]
    disabled = big_states[3][1]
    keep = normal[..., 3] > 250
    keep[CAPTION_BOX[1]:CAPTION_BOX[3], CAPTION_BOX[0]:CAPTION_BOX[2]] = False
    source = np.hstack([normal[keep][:, :3], np.ones((int(keep.sum()), 1), np.float32)])
    target = disabled[keep][:, :3]
    matrix = np.linalg.lstsq(source, target, rcond=None)[0]
    compact_normal = states[0][1]
    flat = np.hstack([compact_normal[..., :3].reshape(-1, 3), np.ones((compact_normal.shape[0] * compact_normal.shape[1], 1))])
    converted = (flat @ matrix).reshape(compact_normal.shape[0], compact_normal.shape[1], 3)
    states.append(("Disabled", np.dstack([converted, compact_normal[..., 3]])))
    return states


def caption_mask_box(state_image, box):
    """Light letters and their dark shadow inside the given box (x0, y0, x1, y1)."""
    red, green, blue = state_image[..., 0], state_image[..., 1], state_image[..., 2]
    letters = (red > 150) & (green > 120) & (blue > 85)
    inside = np.zeros_like(letters)
    inside[box[1]:box[3], box[0]:box[2]] = True
    letters &= inside
    # The short captions are replaced as a whole: the bounding box of the letters with their shadow.
    rows = np.where(letters.any(axis=1))[0]
    columns = np.where(letters.any(axis=0))[0]
    mask = np.zeros_like(letters)
    mask[max(rows.min() - 4, box[1]):min(rows.max() + 6, box[3]), max(columns.min() - 5, box[0]):min(columns.max() + 7, box[2])] = True
    return mask


def to_bytes(array):
    """Float RGBA to 8 bit."""
    return np.clip(np.round(array), 0, 255).astype(np.uint8)


def main():
    sheet_path = Path(sys.argv[1]) if len(sys.argv) > 1 else assets_src_dir(REPO) / SHEET_RELATIVE
    sheet_image = Image.open(sheet_path).convert("RGB")
    assert sheet_image.size == (1920, 1200), "unexpected sheet size %s" % (sheet_image.size,)
    sheet = np.asarray(sheet_image).astype(np.float32)
    atlas = np.zeros((ATLAS_SIZE[1], ATLAS_SIZE[0], 4), np.float32)
    images = []
    big_states = button_states(sheet)
    for index, (name, state) in enumerate(big_states):
        top = index * STATE_PITCH
        atlas[top:top + BUTTON_SIZE[1], 0:BUTTON_SIZE[0]] = state
        for piece, left, right in PIECES:
            images.append((name + piece, left, top, right - left, BUTTON_SIZE[1]))
    x0, y0, x1, y1 = SELECTED_ROW
    row = np.dstack([sheet[y0:y1, x0:x1], np.full((y1 - y0, x1 - x0), 255.0, np.float32)])
    atlas[SELECTED_AT[1]:SELECTED_AT[1] + (y1 - y0), SELECTED_AT[0]:SELECTED_AT[0] + (x1 - x0)] = row
    images.append(("LoadRowSelected", SELECTED_AT[0], SELECTED_AT[1], x1 - x0, y1 - y0))
    for index, (name, state) in enumerate(compact_states(sheet, big_states)):
        top = COMPACT_AT[1] + index * COMPACT_PITCH
        height, width = state.shape[:2]
        atlas[top:top + height, COMPACT_AT[0]:COMPACT_AT[0] + width] = state
        images.append(("Compact" + name + "LeftCap", COMPACT_AT[0], top, COMPACT_CAP, height))
        images.append(("Compact" + name + "Fill", COMPACT_AT[0] + COMPACT_CAP, top, width - 2 * COMPACT_CAP, height))
        images.append(("Compact" + name + "RightCap", COMPACT_AT[0] + width - COMPACT_CAP, top, COMPACT_CAP, height))
    panel = load_panel(sheet)
    atlas[PANEL_AT[1]:PANEL_AT[1] + PANEL_SIZE[1], PANEL_AT[0]:PANEL_AT[0] + PANEL_SIZE[0]] = panel
    images.append(("LoadPanel", PANEL_AT[0], PANEL_AT[1], PANEL_SIZE[0], PANEL_SIZE[1]))
    Image.fromarray(to_bytes(atlas), "RGBA").save(OUT_PNG, optimize=True)

    root = ET.Element("Imageset", {"name": "ODMenuTemplate", "imagefile": OUT_PNG.name, "nativeHorzRes": "1920",
                                   "nativeVertRes": "1200", "autoScaled": "false", "version": "2"})
    for name, x, y, w, h in images:
        ET.SubElement(root, "Image", {"name": name, "xPos": str(x), "yPos": str(y), "width": str(w), "height": str(h)})
    ET.indent(root, "    ")
    OUT_IMAGESET.write_text('<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode") + "\n",
                            encoding="utf-8")
    print("wrote %s (%d images) from %s" % (OUT_PNG.name, len(images), sheet_path.name))


if __name__ == "__main__":
    main()
