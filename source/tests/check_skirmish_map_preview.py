"""Check of the map preview of the skirmish level selection (INGAME-QS-10 S1, T-S1). No compile, no game.

The colours and the picture of every official level are checked by the Boost test 00-LevelPreview
(test_LevelPreview.cpp). This check covers what that test cannot reach without the GUI:
  - every change of the selected level shows the picture of exactly the selected level file, and no selection or an
    unreadable level hides it;
  - the in-game minimaps and the preview take the tile colours from the same function;
  - the preview window lies in the free area above the level list at every screen size from 640x480 to 8K, overlaps
    no other window of the page and keeps the shape of the map.
Run from any directory.
"""
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parents[2]
failures = []


def check(condition, message):
    """Records a failure when the condition does not hold."""
    if not condition:
        failures.append(message)


def read(path):
    """Returns the text of a repository file."""
    return (root / path).read_text(encoding="utf-8")


def strip_comments(text):
    """Removes C++ comments so that a comment cannot satisfy a check."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"//[^\n]*", "", text)


def body(source, signature):
    """Returns the braces body of the first function that starts with the signature."""
    start = source.index(signature)
    open_brace = source.index("{", start)
    depth = 0
    for index in range(open_brace, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[open_brace:index + 1]
    raise AssertionError("no end of " + signature)


def ordered(text, tokens):
    """True if every token occurs in the text, in the given order."""
    position = 0
    for token in tokens:
        position = text.find(token, position)
        if position < 0:
            return False
        position += len(token)
    return True


# --- Selection: every change of the selected level shows that level -------------------------------------------
mode = strip_comments(read("source/modes/MenuModeSkirmish.cpp"))
constructor = body(mode, "MenuModeSkirmish::MenuModeSkirmish(")
check(ordered(constructor, ["getChild(Gui::SKM_LIST_LEVELS)->subscribeEvent(", "CEGUI::Listbox::EventSelectionChanged",
                            "&MenuModeSkirmish::updateMapPreview"]),
      "the level list must call updateMapPreview on every selection change")

files_list = body(mode, "bool MenuModeSkirmish::updateFilesList(")
check("updateMapPreview();" in files_list, "a new level list must update (hide) the preview of the previous list")

preview = body(mode, "bool MenuModeSkirmish::updateMapPreview(")
# The file is the one of the selected item, the same file the launch button starts
check(ordered(preview, ["levelSelectList->getFirstSelectedItem()", "fileName = mFilesList[selItem->getID()]"]),
      "the preview must read the level file of the selected item")
launch = body(mode, "bool MenuModeSkirmish::launchSelectedButtonPressed(")
check("mFilesList[id]" in launch, "the launch button must start mFilesList of the selected item as the preview shows it")
check(ordered(preview, ["preview.loadFromFile(fileName)", "preview.getPictureSize(width, height)",
                        "preview.drawPicture(width, height, seatColour, pixels)",
                        "texture.loadFromMemory(pixels.data()", "CEGUI::Texture::PF_RGBA",
                        "image.setTexture(&texture)", "image.setArea(", "previewWindow->setAspectRatio(",
                        "previewWindow->setProperty(\"Image\", MAP_PREVIEW_IMAGE)", "previewWindow->show()",
                        "mPreviewFile = fileName"]),
      "the preview must load the selected file, draw it, upload the pixels and show them in the preview window")
check(ordered(preview, ["if(fileName.empty() || !preview.loadFromFile(fileName))", "previewWindow->hide()",
                        "return true;"]),
      "no selection or an unreadable level must hide the preview")
# A picture of the previous level is never left standing: the cache only skips the same file in the same state
check("if((fileName == mPreviewFile) && (previewWindow->isVisible() == !fileName.empty()))" in preview,
      "the preview may only skip the work for the level it already shows")
check(ordered(preview, ["mPreviewFile.clear();", "LevelPreview preview;"]),
      "the shown file must be forgotten before a new one is loaded")
seat_colour = body(mode, "static Ogre::ColourValue seatColourFromConfig(")
check("ConfigManager::getSingleton().getColorFromId(colourId)" in seat_colour,
      "the preview must draw the seats in the seat colours of the game")

gui = read("source/render/Gui.cpp")
check('const std::string Gui::SKM_MAP_PREVIEW = "LevelWindowFrame/MapPreview";' in gui,
      "Gui::SKM_MAP_PREVIEW must name the preview window of the layout")

# --- The minimap colours: one function for the minimaps and the preview ---------------------------------------
minimap = strip_comments(read("source/gamemap/MiniMap.cpp"))
tile_colour = body(minimap, "MiniMap::TileColour MiniMap::colourFromTile(")
check("MiniMapColours::terrainColour(visual," in tile_colour, "the minimap must colour tiles with MiniMapColours")
level_preview = strip_comments(read("source/gamemap/LevelPreview.cpp"))
check("MiniMapColours::terrainColour(mVisuals[index]," in body(level_preview, "void LevelPreview::drawPicture("),
      "the preview must colour tiles with MiniMapColours")
check("typedef MiniMapTileColour TileColour;" in strip_comments(read("source/gamemap/MiniMap.h")),
      "the minimap must use the shared colour structure")

# --- The Boost test of the pictures is built and finds the level files ----------------------------------------
tests = read("source/tests/CMakeLists.txt")
check(ordered(tests, ["add_boost_test(00-LevelPreview", "test_LevelPreview.cpp", "${SRC}/gamemap/LevelPreview.cpp",
                      "${SRC}/gamemap/MiniMapColours.cpp", 'OD_LEVELS_DIR="${CMAKE_SOURCE_DIR}/levels"']),
      "the Boost test 00-LevelPreview must be registered with the level folder")
build = read("CMakeLists.txt")
check("${SRC}/gamemap/LevelPreview.cpp" in build and "${SRC}/gamemap/MiniMapColours.cpp" in build,
      "the game must build the preview and the shared minimap colours")
boost_test = read("source/tests/test_LevelPreview.cpp")
check(ordered(boost_test, ['levelFiles("skirmish")', 'levelFiles("multiplayer")', "readTemples(path)",
                           "first->second == second->second"]),
      "the Boost test must check every official level, its temples and that the pictures differ")

# --- Layout: the free area above the level list, at every screen size ------------------------------------------
layout = ET.fromstring(read("gui/MenuSkirmish.layout"))
frame = None
for window in layout.iter("Window"):
    if window.get("name") == "LevelWindowFrame":
        frame = window
check(frame is not None, "LevelWindowFrame is missing")


def properties(window):
    """Returns the properties of a layout window as a dictionary."""
    return {p.get("name"): p.get("value") for p in window.findall("Property")}


def area(window):
    """Returns the Area of a layout window as ((sx, ox), (sy, oy), (sx, ox), (sy, oy))."""
    numbers = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", properties(window)["Area"])]
    return [(numbers[i], numbers[i + 1]) for i in range(0, 8, 2)]


def rectangle(window, width, height):
    """Returns the pixel rectangle (left, top, right, bottom) of a window of the full screen page."""
    a = area(window)
    return (a[0][0] * width + a[0][1], a[1][0] * height + a[1][1],
            a[2][0] * width + a[2][1], a[3][0] * height + a[3][1])


children = {w.get("name"): w for w in frame.findall("Window")} if frame is not None else {}
page = {w.get("name"): w for w in layout.find("Window").findall("Window")}
preview_window = children.get("MapPreview")
check(preview_window is not None, "the layout has no MapPreview window in LevelWindowFrame")
if preview_window is not None:
    props = properties(preview_window)
    check(preview_window.get("type") == "OD/StaticImage", "the preview must be a static image")
    check(props.get("Visible") == "False", "the preview must be hidden until a level is selected")
    check(props.get("AspectMode") == "Shrink", "the preview must keep the shape of the map inside its area")
    check(props.get("HorizontalAlignment") == "Centre", "the preview must be centred in the free area")
    check(props.get("MousePassThroughEnabled") == "True", "the preview must not take the clicks of the page")
    others = [children[n] for n in children if n not in ("MapPreview",)]
    others += [page[n] for n in ("VersionText", "LoadingText") if n in page]
    for width, height in ((640, 480), (800, 600), (1024, 768), (1920, 1080), (3840, 2160), (7680, 4320)):
        left, top, right, bottom = rectangle(preview_window, width, height)
        check(0 <= left and right <= width and 0 <= top and bottom <= height,
              "the preview area leaves the %dx%d screen" % (width, height))
        check(bottom - top >= 120, "the preview is lower than 120 pixels at %dx%d" % (width, height))
        for other in others:
            if properties(other).get("Visible") == "False":
                continue
            o_left, o_top, o_right, o_bottom = rectangle(other, width, height)
            overlaps = left < o_right and o_left < right and top < o_bottom and o_top < bottom
            check(not overlaps, "the preview overlaps %s at %dx%d" % (other.get("name"), width, height))

if failures:
    for failure in failures:
        print("FAIL: " + failure)
    sys.exit(1)
print("skirmish map preview passes the checks")
