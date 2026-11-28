"""Static checks of the campaign map of Moreya (map description, loader, menu code, layout, art and campaign hall).

The map shows only Moreya: 6 wings with 3 level caves and one bonus cave each, the gate with the guild of the
current level in front of it (banner, leader portrait, raid size, origin), the progress of wings and levels, the
current level and the found bonus caves. The province structure of the former world map is gone. The campaign hall
of the main menu shows the same map on its table.

Menu UX plan (M2 to M6): the map is carved into stone and the table top shows its carved map region (TABLE_CROP) on a
map plane that takes up the table top; the clickable map is that table top, with the table edge and the hall floor
around it; the current level glows with an arrow over it; every wing has a greyed out
image drawn over it while it is locked; the hover display is a small carved tablet fitted to its text; the guild
stands on a carved slab with a trail of embers to the current level and its banner there.

The expected values are the structure and guild tables of the campaign, counted once for this branch. The layout is
measured with the shipped font at every supported screen size from 640 x 480 to 7680 x 4320 and at UI scales of
80, 100 and 120 percent. Run from any directory. It does not start a game and compiles nothing.

The map description, its art, the layout, the fonts, the hall material, texture and mesh are files of the content
packages, found through scripts/content_packages.py; the public tree holds no wing. Without content only the code
parts run and the map parts are named as not checked.
"""
from pathlib import Path
import json
import math
import re
import sys
import xml.etree.ElementTree as ET

from PIL import Image, ImageFont

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "scripts"))
import campaign_packages  # noqa: E402
import content_packages  # noqa: E402
import language_package_texts  # noqa: E402

#: The game data files of the content packages the map parts need; without one of them (no content) only the code
#: parts are checked and the others are named as not checked
DATA_FILES = ("gui/MenuCampaign.layout", "gui/campaign/campaign-world.json", "config/mainmenuscene.cfg",
              "materials/scripts/MenuScene.material", "materials/textures/menu/MenuCampaignMap.png",
              "models/MenuMapTableStone.mesh")
MISSING_DATA = [name for name in DATA_FILES if content_packages.data_file(root, name) is None]
HAS_DATA = not MISSING_DATA


def data(relative):
    """A game data file: of the public tree, else of a content package (see scripts/content_packages.py)."""
    return content_packages.resolve(root, relative)


def art_file(relative):
    """A file below gui/campaign/ of the game data (public tree or content package)."""
    return data("gui/campaign/" + relative)


layout = ET.fromstring(data("gui/MenuCampaign.layout").read_text(encoding="utf-8")) if HAS_DATA else None
mode = (root / "source/modes/MenuModeCampaign.cpp").read_text(encoding="utf-8")
mode_h = (root / "source/modes/MenuModeCampaign.h").read_text(encoding="utf-8")
world_cpp = (root / "source/game/CampaignWorld.cpp").read_text(encoding="utf-8")
world_h = (root / "source/game/CampaignWorld.h").read_text(encoding="utf-8")
campaign_cpp = (root / "source/game/Campaign.cpp").read_text(encoding="utf-8")
gui_cpp = (root / "source/render/Gui.cpp").read_text(encoding="utf-8")
# The Package.cfg texts of all wing packages in campaign order
definition = campaign_packages.definition_text(root)
world_text = data("gui/campaign/campaign-world.json").read_text(encoding="utf-8") if HAS_DATA else "{}"
world = json.loads(world_text)
# The public map names no level and no guild: the cave of a wing finds its level by order in the wing package
MAP_NAMES_NO_CONTENT = all("file" not in cave and "guild" not in cave for wing in world.get("wings", [])
                           for cave in wing.get("levels", []) + [wing.get("bonus", {})])
package_entries = campaign_packages.entries(root)
for wing in world.get("wings", []):
    number = str(wing.get("wing"))
    story = [entry for entry in package_entries if entry.get("Wing") == number and entry.get("Bonus") != "1"]
    bonus = [entry for entry in package_entries if entry.get("Wing") == number and entry.get("Bonus") == "1"]
    for order, cave in enumerate(wing.get("levels", [])):
        # A cave of a wing without package keeps a name of its place only
        cave["file"] = story[order]["File"] if order < len(story) else "campaign/wing%s-cave%d" % (number, order + 1)
        guild = campaign_packages.guild_of(story[order]) if order < len(story) else None
        if guild is not None:
            cave["guild"] = guild
            # Banner and portrait of a private package lie in its folder
            cave["_package"] = story[order]["_package"]
    if "bonus" in wing:
        wing["bonus"]["file"] = bonus[0]["File"] if bonus else "campaign/wing%s-bonus" % number
art = root / "gui/campaign"
failures = []


def check(condition, message):
    """Collects a failure message when the condition does not hold."""
    if not condition:
        failures.append(message)


def function(text, name):
    """The body of a function of the menu code, from its definition to the next definition of the class."""
    start = text.index(name)
    following = re.search(r"\n(?:bool|void|size_t|CEGUI::\w+\*) MenuModeCampaign::", text[start + 1:])
    return text[start:start + 1 + following.start()] if following else text[start:]


# ------------------------------------------------------------------------------------------------ expected content
# Names of the 6 wings on the map of Moreya (public: the map shows every wing, a missing one locked)
WING_NAMES = ['The Rotting Cellars', 'The Blood Mines', 'The Weeping Crypts', 'The Chained Depths', 'The Black Catacombs', 'The Abyssal Heart']
# Structure table: wing number, its 3 story maps in order with their guild (name, leader, first raid leader, origin,
# groups, members per group, kind), and its bonus map. The public tree holds no wing: the rows of wings 1 to 6 come
# from the content repository (checks/campaign_map.json), so the table is used with the content only.
EXPECTED_WINGS = []
CONTENT = campaign_packages.content_data(root, "campaign_map")
if CONTENT is not None:
    EXPECTED_WINGS += [(row[0], [tuple(level) for level in row[1]], row[2]) for row in CONTENT["wings"]]
EXPECTED_STORY_CAVES = 18
EXPECTED_BONUS_CAVES = 6
MAP_SIZE = (2560, 1600)
ICON_KEYS = ("locked", "current", "defeated", "bonus_found", "bonus_cleared", "wing_defeated", "hover")
ICON_SIZE = (128, 128)
BANNER_SIZE = (160, 320)
PORTRAIT_SIZE = (256, 256)

# ------------------------------------------------------------------------------------------------ CM4: description
if HAS_DATA:
    check(world.get("version") == 2, "the map description must be version 2")
    check(tuple(world.get("size", ())) == MAP_SIZE, "the map must be 2560 x 1600 pixels")
    check("provinces" not in world and "sites" not in world, "the provinces and bonus sites of the world map must be gone")
    check(not re.search(r'"T\d\d[AB]?"|"B0\d"|mask_rgb|world_idmap', world_text), "no province id, mask or id map may remain")
    wings = world.get("wings", [])
    check(MAP_NAMES_NO_CONTENT, "the caves of the map must name no level file and no guild (they come with the packages)")
    check(len(wings) == len(WING_NAMES), "the map needs exactly 6 wings")
check([row[0] for row in EXPECTED_WINGS] == ([1, 2, 3, 4, 5, 6] if CONTENT is not None else []),
      "the structure table needs, with the content repository, wings 1 to 6")
check(CONTENT is not None or campaign_packages.missing_wings(root) == [1, 2, 3, 4, 5, 6],
      "without content packages wings 1 to 6 must be missing")
wings = world.get("wings", [])
story_caves = [level for wing in wings for level in wing.get("levels", [])]
bonus_caves = [wing["bonus"] for wing in wings if "bonus" in wing]
GUILDS = 3 * len(EXPECTED_WINGS)
if HAS_DATA:
    for index, wing in enumerate(wings, 1):
        check(wing.get("wing") == index, "wing %d is out of order" % index)
        check(wing.get("name") == WING_NAMES[index - 1], "wing %d must be %s" % (index, WING_NAMES[index - 1]))
        check(len(wing.get("levels", [])) == 3, "wing %d needs 3 level caves" % index)
        check("guild" not in wing.get("bonus", {}), "the bonus cave of wing %d has no raid" % index)
    story_caves = [level for wing in wings for level in wing.get("levels", [])]
    bonus_caves = [wing["bonus"] for wing in wings if "bonus" in wing]
    check(len(story_caves) == EXPECTED_STORY_CAVES, "the map needs 18 level caves")
    check(len(bonus_caves) == EXPECTED_BONUS_CAVES, "the map needs 6 bonus caves")
    # Every wing of the structure table: its levels and guilds come with its package
    for index, expected_levels, bonus in EXPECTED_WINGS:
        wing = wings[index - 1] if index <= len(wings) else {}
        check(wing.get("bonus", {}).get("file") == "campaign/%s.level" % bonus,
              "wing %d needs the bonus cave %s" % (index, bonus))
        for level, row in zip(wing.get("levels", []), expected_levels):
            map_name, guild_name, leader, first, origin, groups, size, kind = row
            label = "wing %d %s" % (index, map_name)
            check(level.get("file") == "campaign/%s.level" % map_name, label + ": wrong level file " + str(level.get("file")))
            guild = level.get("guild", {})
            check(guild.get("name") == guild_name, label + ": guild must be " + guild_name)
            check(guild.get("leader") == leader, label + ": leader must be " + leader)
            check(guild.get("first_leader", "") == first, label + ": first raid leader must be '%s'" % first)
            check(guild.get("origin") == origin, label + ": origin must be " + origin)
            check((guild.get("groups"), guild.get("size"), guild.get("kind")) == (groups, size, kind),
                  label + ": raid size must be %d %s(s) of %d" % (groups, kind, size))
            for key, expected_size in (("banner", BANNER_SIZE), ("portrait", PORTRAIT_SIZE)):
                path = campaign_packages.image_path(root, level.get("_package"), guild.get(key, "-"))
                check(path.is_file(), label + ": missing " + key + " " + guild.get(key, "-"))
                if path.is_file():
                    with Image.open(path) as image:
                        check(image.size == expected_size, label + ": %s must be %d x %d" % ((key,) + expected_size))
    GUILDS = 3 * len(EXPECTED_WINGS)
    check(len({level["guild"]["banner"] for level in story_caves if "guild" in level}) == GUILDS,
          "every guild needs its own banner")
    check(len({level["guild"]["portrait"] for level in story_caves if "guild" in level}) == GUILDS,
          "every leader needs its own portrait")
    check(art_file(world.get("base", "-")).is_file(), "missing map image " + world.get("base", "-"))
    if art_file(world.get("base", "-")).is_file():
        with Image.open(art_file(world["base"])) as image:
            check(image.size == MAP_SIZE, "the map image must be 2560 x 1600")
    for key in ICON_KEYS:
        path = art_file(world.get("icons", {}).get(key, "-"))
        check(path.is_file(), "missing cave icon " + key)
        if path.is_file():
            with Image.open(path) as image:
                check(image.size == ICON_SIZE and image.mode == "RGBA", "cave icon %s must be 128 x 128 RGBA" % key)

# The campaign definition and the map name the same 24 levels, in the same wings and the same order
levels = []
for part in re.split(r"(?m)^\[Level\]", definition.replace("\r", ""))[1:]:
    fields = dict(line.split("=", 1) for line in part.splitlines() if "=" in line and not line.startswith("#"))
    if "File" in fields:
        levels.append(fields)
check(len(levels) == 4 * len(EXPECTED_WINGS), "the packages must have %d levels" % (4 * len(EXPECTED_WINGS)))
check(not any("Province" in f for f in levels), "no level may name a province any more")
cfg_story = [(f["File"], f.get("Wing")) for f in levels if f.get("Bonus") != "1"]
map_story = [(level.get("file"), str(wing.get("wing"))) for wing in wings for level in wing.get("levels", [])
             if level.get("file") in [f["File"] for f in levels]]
check(cfg_story == map_story, "the story caves of the map must be the story levels of the packages in their order")
cfg_bonus = sorted((f["File"], f.get("Wing")) for f in levels if f.get("Bonus") == "1")
map_bonus = sorted((wing["bonus"]["file"], str(wing.get("wing"))) for wing in wings if "bonus" in wing
                   and wing["bonus"]["file"] in [f["File"] for f in levels])
check(cfg_bonus == map_bonus, "the bonus caves of the map must be the bonus levels of the packages in their wings")
for f in levels:
    check(f.get("Wing", "") in ("1", "2", "3", "4", "5", "6"), f["File"] + " has no Wing setting from 1 to 6")
    check("Difficulty" not in f, f["File"] + " still has a per-level Difficulty setting (only the campaign difficulty exists)")
check('key == "Province"' not in campaign_cpp and 'key == "Wing"' in campaign_cpp and 'key == "Warden"' in campaign_cpp,
      "the reader must know Wing and Warden and no longer read Province")
check('key == "Map"' not in campaign_cpp and "mMapBlocks" not in campaign_cpp, "the old territory settings must be gone")
check("size_t Campaign::findLevelInWing(uint32_t wing, bool bonus, size_t order) const" in campaign_cpp
      and "campaign.findLevelInWing(worldCave.mWing, worldCave.mBonus, worldCave.mOrder)" in world_cpp,
      "the map finds the level of a cave by its wing and its order")
for key in ('"Guild"', '"GuildLeader"', '"GuildFirstLeader"', '"GuildOrigin"', '"GuildGroups"', '"GuildSize"',
            '"GuildKind"', '"GuildBanner"', '"GuildPortrait"'):
    check("key == " + key in campaign_cpp, "the package reader must read the guild key " + key)

# The loader: 6 wings in order, 3 story caves with a guild each, one bonus cave each; no provinces or id map
check("static const uint32_t NUM_WINGS = 6;" in world_h and "static const uint32_t STORY_CAVES_PER_WING = 3;" in world_h,
      "the loader must require 6 wings of 3 story caves")
importer = world_cpp[world_cpp.index("bool CampaignWorld::importDefinition"):world_cpp.index("size_t CampaignWorld::findLevel")]
for token in ('get_child("wings")', "wing.mNumber != mWings.size() + 1", "levels.size() != STORY_CAVES_PER_WING",
              'node.get_child("bonus")', "mWings.size() != NUM_WINGS"):
    check(token in importer, "the loader must check " + token)
check('"guild"' not in world_cpp and '"file"' not in world_cpp, "the map loader reads no level file and no guild")
for gone in ("Province", "mask", "IdMap", "provinces", "sites"):
    check(gone not in world_cpp and gone not in world_h, "the loader must not know " + gone + " any more")

# ------------------------------------------------------------------------------------------------ CM3: progress
state = world_cpp[world_cpp.index("CampaignCaveState CampaignWorld::getCaveState"):
                  world_cpp.index("uint32_t CampaignWorld::getDefeatedInWing")]
check("campaign.isUnlocked(level)" in state and "CampaignCaveState::hidden" in state,
      "a bonus cave is hidden until its stone was found")
check("CampaignCaveState::bonusCleared : CampaignCaveState::bonusFound" in state, "a bonus cave is found or cleared")
check("campaign.isCompleted(level)" in state and "return CampaignCaveState::defeated;" in state,
      "a won level is shown defeated")
check("level == campaign.getCurrentLevel()" in state and "return CampaignCaveState::current;" in state,
      "the current level is marked")
fill = function(mode, "void MenuModeCampaign::fillMap()")
for state_name, icon in (("locked", "mLocked"), ("current", "mCurrent"), ("defeated", "mDefeated"),
                         ("bonusFound", "mBonusFound"), ("bonusCleared", "mBonusCleared")):
    check("case CampaignCaveState::%s:" % state_name in fill, "fillMap must draw the state " + state_name)
    check(icon in fill, "fillMap must use the icon " + icon)
hidden = fill[fill.index("case CampaignCaveState::hidden:"):]
check(hidden.split("\n", 2)[1].strip() == "continue;", "a hidden bonus cave is not drawn")
check("getDefeatedInWing(campaign, wing.mNumber)" in fill and "mWingDefeated" in fill
      and "CampaignWorld::STORY_CAVES_PER_WING" in fill, "every wing shows its defeated levels and its seal")
progress = function(mode, "void MenuModeCampaign::fillProgressPanel()")
for text in ("Levels defeated: ", "Wings defeated: ", "Heartstone shards: ", "Bonus caves cleared: "):
    check(text in progress, "the progress panel must show " + text.strip(": "))
check("getHeartstonePieces()" in progress and "getHeartstoneTotal()" in progress, "shards found of the shard total")
check("levelsDefeated * PERCENT_FULL / levelTotal" in progress, "the bar shows the defeated story levels in percent")

# ------------------------------------------------------------------------------------------------ CM2: guild panel
guild_panel = function(mode, "void MenuModeCampaign::fillGuildPanel()")
for token in ("findCurrentCave(", "guild.mBanner", "guild.mPortrait", "guild.mName", "getGuildDetailsText(guild)"):
    check(token in guild_panel, "the guild in front of the gate needs " + token)
details = world_cpp[world_cpp.index("std::string CampaignWorld::getGuildDetailsText"):]
# The words are the entries campaign.code.* of the English language package; the code asks for them by their keys
for token in ('"campaign.code.leader"', '"campaign.code.leaders"', '"campaign.code.raid_size"', '"campaign.code.origin"',
              '"\\n"'):
    check(token in details, "the guild details must contain " + token)
if content_packages.has_content(root):
    english = language_package_texts.english(root)
    for key, text in (("campaign.code.leader", "Leader: {name}"), ("campaign.code.leaders", "Leaders: {first} and {second}"),
                      ("campaign.code.raid_size", "Raid size: {text}"), ("campaign.code.origin", "Origin: {text}"),
                      ("campaign.code.size_group_one", "one group of {size}"), ("campaign.code.size_group_two", "two groups of {size}"),
                      ("campaign.code.size_group_many", "{count} groups of {size}"), ("campaign.code.size_raid_one", "one raid of {size}"),
                      ("campaign.code.size_raid_two", "two raids of {size}"), ("campaign.code.size_raid_many", "{count} raids of {size}")):
        check(english.get(key) == text, "the English entry %s must be %r" % (key, text))
else:
    content_packages.unchecked("check_campaign_map", ["the English texts campaign.code.*"])
check("fillGuildPanel();" in fill, "the guild panel is drawn")
if HAS_DATA:
    panel = world["guild_panel"]


def inside(inner, outer):
    """True if the rectangle [x, y, w, h] lies inside the other one."""
    return (outer[0] <= inner[0] and outer[1] <= inner[1] and inner[0] + inner[2] <= outer[0] + outer[2]
            and inner[1] + inner[3] <= outer[1] + outer[3])


def overlap(a, b):
    """True if two rectangles [x, y, w, h] share an area."""
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


if HAS_DATA:
    for key in ("banner", "portrait", "name", "details"):
        check(inside(panel[key], panel["area"]), "the guild " + key + " must lie inside the guild panel")
    for first, second in (("banner", "portrait"), ("portrait", "name"), ("portrait", "details"), ("name", "details")):
        check(not overlap(panel[first], panel[second]), "the guild %s and %s overlap" % (first, second))
    gate_x, gate_y = world["gate"]
    check(panel["area"][1] + panel["area"][3] <= wings[0]["area"][1] and abs(panel["area"][0] - gate_x) < 300,
          "the guild stands in front of the gate, above the wings")
    check(abs(panel["banner"][2] * 2 - panel["banner"][3]) <= 1 and panel["portrait"][2] == panel["portrait"][3],
          "banner (1:2) and portrait (square) keep the proportions of their images")

# ------------------------------------------------------------------------------------------------ CM1: only Moreya
check('CAMPAIGN_TITLE = "Moreya"' in mode, "the map is titled Moreya")
for gone in ("getProvinceAt", "world_idmap", "WORLD_IDMAP_FILE", "Province", "province", "mLiftWindow", "findSiteAt"):
    check(gone not in mode and gone not in mode_h, "the menu must not know " + gone + " any more")
check("hidden land" not in mode, "no surface land is named any more")
check("bool named = !cave.mBonus && (cave.mLabel.mWidth > 0);" in fill
      and "if(named && (level < campaign.getNumLevels()))" in fill, "only level caves carry a name on the map")

# ------------------------------------------------------------------------------------------------ menu behaviour
if HAS_DATA:
    windows = {w.get("name"): w for w in layout.iter("Window")}
    for path in re.findall(r'const std::string CMP_\w+ = "CampaignWindowFrame/([\w/]+)";', mode):
        check(path.split("/")[-1] in windows, "missing in layout: " + path)
    check("LevelSelect" not in windows, "the level list must be replaced by the map")
    check("DifficultyButton" in windows and "BriefingPanel" in windows, "the difficulty button and the briefing must stay")
check("setAspectMode(CEGUI::AM_SHRINK)" in mode, "the map must keep its aspect ratio")
check("MAP_ASPECT_RATIO = 1.6f" in mode and MAP_SIZE[0] / MAP_SIZE[1] == 1.6, "the map aspect ratio is 1.6")
hover = function(mode, "bool MenuModeCampaign::mapMoved")
check("findCaveAt(" in hover and "updateHover(" in hover and "updateTooltip(" in hover,
      "hover finds the cave under the mouse")
ring = function(mode, "void MenuModeCampaign::updateHover")
check("CampaignCaveState::locked" in ring, "locked caves get a tooltip but no ring")
tip = function(mode, "void MenuModeCampaign::updateTooltip")
check("Guild: " in tip and "Difficulty: " not in tip and "State: " in tip and "Bonus cave of " in tip,
      "tooltip shows wing, guild and state, and no per-level difficulty")
check("getLayoutScale()" in tip and "std::min(TOOLTIP_WIDTH * scale, mapRect.getWidth())" in tip,
      "the tooltip scales with the layout and never gets larger than the map")
click = function(mode, "bool MenuModeCampaign::mapClicked")
check("showBriefing(" in click and "startLevel(" not in click, "a click opens the briefing, it does not start the level")
check("CampaignCaveState::locked" in click, "a locked cave cannot be opened")
check("startLevel(level)" in function(mode, "bool MenuModeCampaign::briefingStartPressed"), "the briefing starts the level")
check("getCaveAt(x, y, mCaveStates)" in function(mode, "size_t MenuModeCampaign::findCaveAt"),
      "only visible caves are hit")

# Leaving the game (or the main menu) for the campaign page again must not meet the windows of an earlier visit:
# the mode is created anew on every request but the gui sheet and its map stay
manager = (root / "source/modes/ModeManager.cpp").read_text(encoding="utf-8")
check("make_unique<MenuModeCampaign>" in manager, "the campaign mode is created again on every request")
clear = function(mode, "void MenuModeCampaign::clearMap()")
check("WORLD_WINDOW_PREFIX" in clear and "getChildAtIdx(" in clear and "removeChild(" in clear,
      "clearMap must remove the map windows of earlier visits by their name prefix")
check("WORLD_WINDOW_PREFIX + name" in mode, "map windows must carry the prefix clearMap looks for")
check("mWorldWindows.clear()" in clear and "mHoverWindow = nullptr" in clear and "mCaveStates.clear()" in clear,
      "clearMap must reset its member state")
quit_game = (root / "source/modes/GameMode.cpp").read_text(encoding="utf-8")
quit_game = quit_game[quit_game.index("bool GameMode::onClickYesQuitMenu"):]
check("MENU_CAMPAIGN" in quit_game[:900], "quitting a campaign game returns to the campaign page")

# ------------------------------------------------------------------------------------------------ layout
# Every map window is a share of the map, so it scales with the map and never leaves it (or the screen).
create = function(mode, "CEGUI::Window* MenuModeCampaign::createMapWindow")
check("setMapArea(window, x, y, width, height)" in create, "map windows are placed in map pixels")
check("CEGUI::UDim(x / mapWidth, 0)" in function(mode, "void MenuModeCampaign::setMapArea"),
      "map windows are relative to the map")
if HAS_DATA:
    fonts = {}
    for font_file in content_packages.data_glob(root, "gui/fonts", "*.font"):
        # The own rows file of a mixed font (gui/fonts/<name>.own.font) is no font; the font is read joined
        if font_file.name.endswith(".own.font"):
            continue
        spec = ET.fromstring(content_packages.read_text(root, content_packages.relative_path(root, font_file)))
        fonts[spec.get("name")] = (data("gui/fonts/" + spec.get("filename")), float(spec.get("size")))


def constant(name):
    """A string or float constant of the menu code, as text."""
    match = re.search(r'const (?:std::string|float) %s = "?([^";]+?)"?f?;' % name, mode)
    return match[1] if match else None


SCREENS = ((640, 480), (800, 600), (1024, 768), (1280, 720), (1280, 1024), (1366, 768), (1920, 1080), (1920, 1200),
           (2560, 1080), (2560, 1440), (3840, 2160), (7680, 4320))
USER_SCALES = (0.8, 1.0, 1.2)
DESIGN_W, DESIGN_H = (float(re.search(r"LAYOUT_DESIGN_%s = ([0-9.]+)f" % k, gui_cpp)[1]) for k in ("WIDTH", "HEIGHT"))
FONT_W, FONT_H = (float(re.search(r"FONT_DESIGN_%s = ([0-9.]+)f" % k, gui_cpp)[1]) for k in ("WIDTH", "HEIGHT"))
# Inner margin of a text window without frame, in screen pixels; the text of the hover display keeps the shares
# TOOLTIP_INSET_X and TOOLTIP_INSET_Y of its carved tablet free on every side (read from the menu code), plus that margin
TEXT_MARGIN = 2
_font_cache = {}


def screen_font(name, screen, user_scale):
    """The font as CEGUI draws it at that screen size and UI scale (autoscaled from 800 x 600)."""
    path, size = fonts[name]
    pixels = math.ceil(size * 96 / 72 * min(screen[0] / FONT_W, screen[1] / FONT_H) * user_scale)
    key = (path, pixels)
    if key not in _font_cache:
        _font_cache[key] = ImageFont.truetype(str(path), pixels)
    return _font_cache[key]


def wrapped_height(face, text, width, wrap):
    """Height of the text when it is wrapped at width (or not wrapped); None if a word or line is wider."""
    line_height = sum(face.getmetrics())
    rows = 0
    for line in text.split("\n"):
        if not wrap:
            if face.getlength(line) > width:
                return None
            rows += 1
            continue
        current = ""
        rows += 1
        for word in line.split():
            if face.getlength(word) > width:
                return None
            candidate = (current + " " + word).strip()
            if face.getlength(candidate) > width and current:
                rows += 1
                current = word
            else:
                current = candidate
    return rows * line_height


def scaled_rectangle(values, parent, scale):
    """A layout area {{sx,ox},{sy,oy},{ex,ox},{ey,oy}} on the screen after the offset scaling of Gui."""
    return (values[0] * parent[0] + values[1] * scale, values[2] * parent[1] + values[3] * scale,
            values[4] * parent[0] + values[5] * scale, values[6] * parent[1] + values[7] * scale)


# The texts drawn on the map: (what, rectangle in map pixels, font constant, texts, wrapped)
titles = {f["File"]: f.get("Title", "") for f in levels}
# A cave of a wing without package says that the wing is coming in Early Access
for wing in wings:
    for cave in wing["levels"]:
        titles.setdefault(cave["file"], campaign_packages.MISSING_WING_TEXT)
check('Translation::tr("campaign.code.missing_wing")'
      in (root / "source/game/CampaignPackages.cpp").read_text(encoding="utf-8"),
      "the game asks for the text of a missing wing by its key")
if content_packages.has_content(root):
    check(language_package_texts.english(root).get("campaign.code.missing_wing") == campaign_packages.MISSING_WING_TEXT,
          "the English text of a missing wing is the one the checks use")
else:
    content_packages.unchecked("check_campaign_map", ["the English text campaign.code.missing_wing"])
if HAS_DATA:
    map_texts = [("title", world["title_cartouche"], "FONT_TITLE", [constant("CAMPAIGN_TITLE")], False)]
    for wing in wings:
        # A wing whose name is painted on the map gets only its progress written
        wing_texts = ["3 / 3"] if wing.get("name_painted") else [wing["name"] + "   3 / 3", wing["name"]]
        map_texts.append(("wing %s label" % wing["wing"], wing["label"], "FONT_WING", wing_texts, True))
        for cave in wing["levels"]:
            # A level without label is named in its tooltip only
            if "label" in cave:
                map_texts.append((cave["file"] + " label", cave["label"], "FONT_CAVE", [titles.get(cave["file"], "")],
                                  True))
        for level in wing["levels"]:
            if "guild" not in level:
                continue
            guild = level["guild"]
            leader = ("Leaders: %s and %s" % (guild["first_leader"], guild["leader"]) if guild.get("first_leader")
                      else "Leader: " + guild["leader"])
            raid = "%s %s%s of %d" % ({1: "one", 2: "two"}[guild["groups"]], guild["kind"],
                                      "" if guild["groups"] == 1 else "s", guild["size"])
            map_texts.append((guild["name"] + " name", panel["name"], "FONT_GUILD_NAME", [guild["name"]], True))
            map_texts.append((guild["name"] + " details", panel["details"], "FONT_GUILD_DETAILS",
                              [leader + "\nRaid size: " + raid + "\nOrigin: " + guild["origin"]], True))
    bar = world["progress_panel"]
    progress_text = [bar[0] + bar[2] * 0.04, bar[1], bar[2] * 0.92, bar[3] * 0.70]
    map_texts.append(("progress", progress_text, "FONT_PROGRESS", [
        "Levels defeated: 18 / 18\nWings defeated: 6 / 6\nHeartstone shards: 3 / 3\nBonus caves cleared: 6 / 6"], False))
    map_texts.append(("percent", [bar[0] + bar[2] * 0.80, bar[1] + bar[3] * 0.68, bar[2] * 0.16, bar[3] * 0.32],
                      "FONT_PROGRESS", ["100%"], False))
for constant_name, value in (("PROGRESS_LEFT", "0.04"), ("PROGRESS_TEXT_WIDTH", "0.92"),
                             ("PROGRESS_TEXT_HEIGHT", "0.70"), ("PROGRESS_PERCENT_LEFT", "0.80"),
                             ("PROGRESS_PERCENT_TOP", "0.68"), ("PROGRESS_PERCENT_WIDTH", "0.16"),
                             ("PROGRESS_PERCENT_HEIGHT", "0.32")):
    check(constant(constant_name) == value, "the progress layout constant %s changed, measure it again" % constant_name)

# The map items the player points at or reads, which the controls at the bottom must not cover
if HAS_DATA:
    map_items = [("guild panel", panel["area"]), ("title", world["title_cartouche"]), ("progress", world["progress_panel"])]
    for wing in wings:
        map_items.append(("wing %s label" % wing["wing"], wing["label"]))
        size = wing["seal_size"]
        map_items.append(("wing %s seal" % wing["wing"],
                          [wing["seal"][0] - size / 2, wing["seal"][1] - size / 2, size, size]))
        for cave in wing["levels"] + [wing["bonus"]]:
            size = cave["size"] * float(constant("HOVER_SCALE"))
            map_items.append((cave["file"], [cave["pos"][0] - size / 2, cave["pos"][1] - size / 2, size, size]))
            if "label" in cave:
                map_items.append((cave["file"] + " label", cave["label"]))
    for name, rect in map_items:
        check(inside(rect, [0, 0, MAP_SIZE[0], MAP_SIZE[1]]), name + " lies outside the map")
    for wing in wings:
        for name, rect in map_items:
            if name == "wing %s label" % wing["wing"] or name == "wing %s seal" % wing["wing"]:
                check(inside(rect, wing["area"]), name + " lies outside its wing")
        for cave in wing["levels"]:
            if "label" in cave:
                check(inside(cave["label"], wing["area"]), cave["file"] + " label lies outside its wing")
        check("label" not in wing["bonus"], "the bonus cave of wing %s is named in its tooltip only" % wing["wing"])
    caves_and_labels = [item for item in map_items if item[0].startswith("campaign/") or "label" in item[0]
                        or "seal" in item[0]]
    for i, (first_name, first) in enumerate(caves_and_labels):
        for second_name, second in caves_and_labels[i + 1:]:
            check(not overlap(first, second), "%s and %s overlap on the map" % (first_name, second_name))

    controls = ("ControlBackdrop", "DifficultyButton", "RelationshipsCheckbox", "BackButton", "LoadingText")
    control_areas = {}
    for name in controls:
        area = next(p.get("value") for p in windows[name].findall("Property") if p.get("name") == "Area")
        control_areas[name] = [float(v) for v in re.findall(r"-?\d+(?:\.\d+)?", area)]
    tooltip_size = (float(constant("TOOLTIP_WIDTH")), float(constant("TOOLTIP_HEIGHT")))
    tooltip_texts = ["%s\n%s\nGuild: %s\nState: Defeated, can be played again"
                     % (titles.get(level["file"], ""), wing["name"], level["guild"]["name"])
                     for wing in wings for level in wing["levels"] if "guild" in level]
    tooltip_texts += ["%s\n%s\nState: Locked" % (campaign_packages.MISSING_WING_TEXT, wing["name"]) for wing in wings]
    tooltip_texts += ["%s\nBonus cave of %s\nState: Cleared, can be played again"
                      % (titles.get(wing["bonus"]["file"], ""), wing["name"]) for wing in wings]
    measured = 0
    for screen in SCREENS:
        map_width = min(screen[0], screen[1] * MAP_SIZE[0] / MAP_SIZE[1])
        map_height = map_width * MAP_SIZE[1] / MAP_SIZE[0]
        map_left = (screen[0] - map_width) / 2
        map_top = (screen[1] - map_height) / 2
        map_scale = map_width / MAP_SIZE[0]
        check(map_width <= screen[0] and map_height <= screen[1], "the map is larger than the screen %dx%d" % screen)
        for user_scale in USER_SCALES:
            where = "%dx%d at %d%%" % (screen + (round(user_scale * 100),))
            layout_scale = min(screen[0] / DESIGN_W, screen[1] / DESIGN_H) * user_scale
            for what, rect, font_constant, texts, wrap in map_texts:
                face = screen_font(constant(font_constant), screen, user_scale)
                width = rect[2] * map_scale - 2 * TEXT_MARGIN
                height = rect[3] * map_scale - 2 * TEXT_MARGIN
                for text in texts:
                    used = wrapped_height(face, text, width, wrap)
                    measured += 1
                    check(used is not None and used <= height, "%s does not fit at %s" % (what, where))
            # The bottom controls never cover a cave, a label or a panel of the map
            for control in controls:
                box = scaled_rectangle(control_areas[control], screen, layout_scale)
                check(0 <= box[0] < box[2] <= screen[0] and 0 <= box[1] < box[3] <= screen[1],
                      "%s leaves the screen at %s" % (control, where))
                for name, rect in map_items:
                    item = (map_left + rect[0] * map_scale, map_top + rect[1] * map_scale,
                            map_left + (rect[0] + rect[2]) * map_scale, map_top + (rect[1] + rect[3]) * map_scale)
                    check(not (item[0] < box[2] and box[0] < item[2] and item[1] < box[3] and box[1] < item[3]),
                          "%s covers %s at %s" % (control, name, where))
            # The tooltip: never larger than the map, its longest texts fit
            tooltip = (min(tooltip_size[0] * layout_scale, map_width), min(tooltip_size[1] * layout_scale, map_height))
            inner = (tooltip[0] * (1.0 - 2.0 * float(constant("TOOLTIP_INSET_X"))) - 2 * TEXT_MARGIN,
                     tooltip[1] * (1.0 - 2.0 * float(constant("TOOLTIP_INSET_Y"))) - 2 * TEXT_MARGIN)
            face = screen_font(constant("FONT_TOOLTIP"), screen, user_scale)
            for text in tooltip_texts:
                used = wrapped_height(face, text, inner[0], True)
                measured += 1
                check(used is not None and used <= inner[1], "the tooltip text does not fit at " + where)
    check(measured > 0, "no text was measured")

# ------------------------------------------------------------------------------------------------ CM5: campaign hall
if HAS_DATA:
    # The scene as the game reads it: config/mainmenuscene.cfg with its own rows from the content packages
    scene = content_packages.read_text(root, "config/mainmenuscene.cfg")
    # The hall with the stone table is the open hall of the whole scene (menu UX plan M1)
    check(re.search(r"(?m)^AddEntity CampaignHallOpen MenuCampaignHallOpen\.mesh ", scene) is not None,
          "the campaign hall stays")
    check(re.search(r"(?m)^AddEntity CampaignStoneTable MenuMapTableStone\.mesh ", scene) is not None,
          "the stone map table stays in the hall")
    material = data("materials/scripts/MenuScene.material").read_text(encoding="utf-8")
    block = material[material.index("material MenuCampaignMap"):]
    check("texture MenuCampaignMap.png" in block[:block.index("\n}")], "the table shows the texture MenuCampaignMap.png")
models = (root / "tools/blender-assets/menu_scene_models.py").read_text(encoding="utf-8")
check('b.face_materials.append("MenuCampaignMap")' in models, "the table model has the map plane")
if HAS_DATA:
    hall = data("materials/textures/menu/MenuCampaignMap.png")
    # The table top shows the carved map frame of the map of Moreya (TABLE_CROP of tools/gen_campaign_map_art.py),
    # stretched to the map size; the map covers the whole table top and the table follows the map (Mario 2026-11-23): the
    # map plane is at least MIN_TABLE_MAP_WIDTH wide (the old plane was 3.8), has the aspect ratio of the map frame and
    # covers at least MIN_TOP_COVER of the width and the depth of the table top (its faces above TOP_HEIGHT). The clickable
    # map is the rendered table (M2, Mario 2026-11-23), so it shows the hall texture on the table top seen in perspective:
    # the hall texture projected through the corners of the table top of the map description ("table_top": texture pixel,
    # place on the full screen map) correlates in luminance (640 x 400, inside the table top) by at least
    # MIN_TABLE_TOP_CORRELATION with the full screen map (0.94 measured on this branch; the same projection 20 pixels to
    # the side 0.36, 20 pixels down -0.02); it replaces the mean colour difference of at most 1.0 against the carved map
    # frame, which held only while the full screen map was the unlit flat image the texture was cut from
    TABLE_CROP = (400, 418, 1752, 980)
    MIN_TABLE_TOP_CORRELATION = 0.85
    MIN_TABLE_MAP_WIDTH = 6.0
    MIN_TOP_COVER = 0.98
    TOP_HEIGHT = 1.6
    with Image.open(hall) as hall_image, Image.open(art_file(world["base"])) as map_image:
        check(hall_image.size == map_image.size, "the hall texture must have the size of the map of Moreya")
        import numpy  # noqa: E402
        from PIL import ImageDraw  # noqa: E402
        table_top = world.get("table_top", [])
        check(len(table_top) >= 4, "the map description names no corners of the table top (table_top)")
        if len(table_top) >= 4:
            # Homography from the full screen map to the hall texture through the corners of the table top
            rows = []
            values = []
            for u, v, x, y in table_top:
                rows.append([x, y, 1.0, 0.0, 0.0, 0.0, -u * x, -u * y])
                rows.append([0.0, 0.0, 0.0, x, y, 1.0, -v * x, -v * y])
                values.extend([u, v])
            coefficients = numpy.linalg.lstsq(numpy.array(rows), numpy.array(values), rcond=None)[0]
            projected = hall_image.convert("L").transform(map_image.size, Image.PERSPECTIVE, tuple(coefficients),
                                                          Image.BICUBIC)
            top_mask = Image.new("L", map_image.size, 0)
            ImageDraw.Draw(top_mask).polygon([(x, y) for _, _, x, y in table_top], fill=255)
            hall_grey = numpy.asarray(projected.resize((640, 400)), dtype=numpy.float64)
            map_grey = numpy.asarray(map_image.convert("L").resize((640, 400)), dtype=numpy.float64)
            inside_top = numpy.asarray(top_mask.resize((640, 400))) > 250
            correlation = numpy.corrcoef(hall_grey[inside_top], map_grey[inside_top])[0, 1]
            check(correlation >= MIN_TABLE_TOP_CORRELATION, "the clickable map must show the carved map of the campaign "
                  "hall on the table top (run tools/gen_campaign_map_art.py), correlation %.3f (at least %.2f)"
                  % (correlation, MIN_TABLE_TOP_CORRELATION))
    sys.path.insert(0, str(root / "source/tests"))
    import check_menu_moreya_entrance as entrance  # noqa: E402
    plane = entrance.submeshes(str(data("models/MenuMapTableStone.mesh"))).get("MenuCampaignMap")
    check(plane is not None, "the stone table has no map plane")
    if plane is not None:
        corners = plane[0][plane[1]].reshape(-1, 3)
        plane_width, plane_depth = corners[:, 0].max() - corners[:, 0].min(), corners[:, 1].max() - corners[:, 1].min()
        check(plane_width >= MIN_TABLE_MAP_WIDTH, "the map plane is only %.2f wide (at least %.2f)"
              % (plane_width, MIN_TABLE_MAP_WIDTH))
        check(abs(plane_width / plane_depth - TABLE_CROP[2] / TABLE_CROP[3]) < 0.01,
              "the map plane (%.3f) and the carved map region (%.3f) need the same aspect ratio"
              % (plane_width / plane_depth, TABLE_CROP[2] / TABLE_CROP[3]))
        top_faces = [vertices[triangles] for material, (vertices, triangles) in
                     entrance.submeshes(str(data("models/MenuMapTableStone.mesh"))).items()
                     if material != "MenuCampaignMap" and len(triangles)]
        top = [faces[faces[:, :, 2].min(axis=1) > TOP_HEIGHT].reshape(-1, 3) for faces in top_faces]
        top = [points for points in top if len(points)]
        if top:
            import numpy  # noqa: E402
            points = numpy.concatenate(top)
            top_width = points[:, 0].max() - points[:, 0].min()
            top_depth = points[:, 1].max() - points[:, 1].min()
            check(plane_width >= MIN_TOP_COVER * top_width and plane_depth >= MIN_TOP_COVER * top_depth,
                  "the map does not cover the table top: %.2f x %.2f of %.2f x %.2f"
                  % (plane_width, plane_depth, top_width, top_depth))

# ------------------------------------------------------------------------------------------------ menu UX M2 to M6
# M2: the map is carved stone, no painted colours: the mean saturation of the map region (MAP_REGION) stays at most
# MAX_MAP_SATURATION (the painted map had 0.68, the carved one 0.45)
if HAS_DATA:
    MAP_REGION = (395, 410, 1765, 1000)
    MAX_MAP_SATURATION = 0.5
    with Image.open(art_file(world["base"])) as map_image:
        region = map_image.convert("HSV").crop((MAP_REGION[0], MAP_REGION[1], MAP_REGION[0] + MAP_REGION[2],
                                                MAP_REGION[1] + MAP_REGION[3])).resize((440, 250))
        saturation = sum(region.getchannel("S").tobytes()) / (440 * 250 * 255.0)
    check(saturation <= MAX_MAP_SATURATION, "the map is not carved stone: mean saturation %.2f (at most %.2f)"
          % (saturation, MAX_MAP_SATURATION))
# M2 (Mario on build 93 and on the previews): the clickable map is the solid stone table in the hall, the table is the
# map: the full screen map is the render of the stone table with its own carved map texture on its (cut-off) top, its
# slab, trestles and the hall floor round it, seen in perspective; no map image is laid over it
art_tool = (root / "tools/gen_campaign_map_art.py").read_text(encoding="utf-8")
render_tool = (root / "tools/render_campaign_map_table.py").read_text(encoding="utf-8")
check("TABLE_RENDER" in art_tool and "screen = table_view(root, outline, placement)" in art_tool
      and "screen[top:top + height, left:left + width]" not in art_tool,
      "the full screen map must be the rendered stone table in the hall, nothing laid over it "
      "(tools/gen_campaign_map_art.py)")
check("MenuCampaignMap.png" in render_tool,
      "the table render must show the table with its carved map texture on the map plane")
check(all(name in render_tool for name in ("MenuMapTableStone.mesh", "MenuCampaignHallOpen.mesh", "MenuHallFloor")),
      "the table render must show the stone table and the hall floor of the menu scene")
check(re.search(r"(?m)^TABLE_CROP = \(400, 418, 1752, 980\)$", art_tool) is not None,
      "the carved map frame of the full screen map is TABLE_CROP (400, 418, 1752, 980)")
# M4: every wing has a greyed out image over its own caves: RGBA, inside the map, grey (mean saturation of its opaque
# pixels at most MAX_LOCKED_SATURATION) and darker than the map below it (at most MAX_LOCKED_SHARE of its luminance)
MAX_LOCKED_SATURATION = 0.1
MAX_LOCKED_SHARE = 0.7
if HAS_DATA:
    with Image.open(art_file(world["base"])) as map_image:
        map_grey = map_image.convert("L")
        for wing in wings:
            locked = wing.get("locked", {})
            area = locked.get("area", [0, 0, 0, 0])
            path = art_file(locked.get("image", "-"))
            check(path.is_file(), "wing %d has no greyed out image" % wing["wing"])
            check(inside(area, [0, 0, MAP_SIZE[0], MAP_SIZE[1]]), "the greyed out image of wing %d leaves the map"
                  % wing["wing"])
            for cave in wing["levels"] + [wing["bonus"]]:
                check(inside([cave["pos"][0], cave["pos"][1], 1, 1], area),
                      "the greyed out image of wing %d does not cover its cave at %s" % (wing["wing"], cave["pos"]))
            if not path.is_file():
                continue
            with Image.open(path) as image:
                check(image.mode == "RGBA" and list(image.size) == area[2:], "the greyed out image of wing %d must be "
                      "RGBA in the size of its area" % wing["wing"])
                hsv = image.convert("RGB").convert("HSV")
                alpha = image.getchannel("A").tobytes()
                opaque = [index for index, value in enumerate(alpha) if value > 128]
                sat = hsv.getchannel("S").tobytes()
                lum = image.convert("L").tobytes()
                below = map_grey.crop((area[0], area[1], area[0] + area[2], area[1] + area[3])).tobytes()
                mean_sat = sum(sat[index] for index in opaque) / (255.0 * max(len(opaque), 1))
                share = sum(lum[index] for index in opaque) / max(sum(below[index] for index in opaque), 1)
                check(mean_sat <= MAX_LOCKED_SATURATION and share <= MAX_LOCKED_SHARE,
                      "the greyed out image of wing %d is not grey and dark (saturation %.2f, luminance share %.2f)"
                      % (wing["wing"], mean_sat, share))
locking = function(mode, "bool MenuModeCampaign::isWingLocked")
check("CampaignCaveState::locked" in locking and "CampaignCaveState::hidden" in locking
      and "isWingAvailable(wing)" in locking, "a wing is locked while none of its caves can be played")
check("wing.mLockedImage" in fill and "isWingLocked(wing.mNumber)" in fill and "LOCKED_CAVE_ALPHA" in fill,
      "fillMap must grey out the locked wings and their caves")
check('get_child_optional("locked")' in world_cpp and "mLockedImage" in world_h,
      "the map loader must read the greyed out image of a wing")
# M3: the current level glows under its larger marker and a golden arrow bobs over it, without hovering
if HAS_DATA:
    ART_SIZES = {"tooltip_plaque.png": (512, 200), "current_glow.png": (256, 256), "current_pointer.png": (128, 160),
                 "raid_ember.png": (64, 64), "guild_plaque.png": tuple(panel["area"][2:])}
    for name, size in ART_SIZES.items():
        path = art_file("moreya/" + name)
        check(path.is_file(), "missing map art " + name)
        if path.is_file():
            with Image.open(path) as image:
                check(image.mode == "RGBA" and image.size == size, "map art %s must be RGBA %d x %d" % ((name,) + size))
check("fillCurrentMarker();" in fill and "CURRENT_CAVE_SCALE" in fill and "ART_CURRENT_POINTER" in fill,
      "fillMap must draw the glow, the larger marker and the arrow of the current level")
animation = function(mode, "void MenuModeCampaign::updateMapAnimation")
check("mCurrentGlow->setAlpha(" in animation and "setMapArea(mCurrentPointer" in animation
      and "mRaidEmbers[i]->setAlpha(" in animation, "the glow pulses, the arrow bobs and the raid trail runs")
check("updateMapAnimation(evt.timeSinceLastFrame);" in function(mode, "void MenuModeCampaign::onFrameStarted"),
      "the map is animated every frame")
# M5: the hover display is a carved tablet just large enough for its text
check("ART_TOOLTIP_PLAQUE" in fill and "mTooltipPlaque->addChild(mTooltip)" in fill,
      "the hover display is a carved tablet with its text inside")
check("getTextExtent(" in tip and '"VertExtent"' in tip and "TOOLTIP_INSET_X" in tip,
      "the hover display is fitted to its text")
# M6: the guild stands on a carved slab, and its trail of embers leads to the level it attacks with its banner there
check("ART_GUILD_PLAQUE" in guild_panel and "fillRaidTrail(cave, guild.mBanner, packageDirectory);" in guild_panel,
      "the guild panel needs its slab and the raid trail to the current level")
trail = function(mode, "void MenuModeCampaign::fillRaidTrail")
check("ART_RAID_EMBER" in trail and '"RaidBanner", banner' in trail, "the raid trail needs its embers and the banner")
# The old world map and its previews are gone (raid plan FINAL step 1b): the hall can no longer show them
# (searched in the public tree, the content packages and the wing packages)
for gone in ("world_base.png", "world_idmap.png", "preview_states.png", "provinces", "sites"):
    check(content_packages.data_file(root, "gui/campaign/" + gone) is None,
          "the old world map file %s must be gone" % gone)
preview_files = content_packages.data_glob(root, "gui/campaign/previews", "*.png")
preview_files += [path for folder, _, _, _ in campaign_packages.packages(root)
                  for path in (folder / "previews").glob("*.png")]
old_previews = sorted(path.name for path in preview_files if re.fullmatch(r"(T\d\d[AB]?|B0\d)\.png", path.name))
check(not old_previews, "the old previews must be gone: %s" % old_previews)

if not HAS_DATA:
    measured = 0
    check(not content_packages.has_content(root),
          "content files missing although the content is present: " + ", ".join(MISSING_DATA))
    content_packages.unchecked("campaign map", MISSING_DATA)
if failures:
    print("\n".join(failures))
    sys.exit(1)
print("campaign map checks passed: 6 wings, %d level caves, %d bonus caves, %d guilds; %d text fits at %d screens x %d "
      "UI scales; the campaign hall shows the map of Moreya" % (len(story_caves), len(bonus_caves), GUILDS,
                                                                measured, len(SCREENS), len(USER_SCALES)))
