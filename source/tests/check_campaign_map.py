"""Static checks of the campaign map of Moreya (map description, loader, menu code, layout, art and campaign hall).

The map shows only Moreya: 6 wings with 3 level caves and one bonus cave each, the gate with the guild of the
current level in front of it (banner, leader portrait, raid size, origin), the progress of wings and levels, the
current level and the found bonus caves. The province structure of the former world map is gone. The campaign hall
of the main menu shows the same map on its table.

The expected values are the structure and guild tables of the campaign, counted once for this branch. The layout is
measured with the shipped font at every supported screen size from 640 x 480 to 7680 x 4320 and at UI scales of
80, 100 and 120 percent. Run from any directory. It does not start a game and compiles nothing.
"""
from pathlib import Path
import json
import math
import re
import sys
import xml.etree.ElementTree as ET

from PIL import Image, ImageFont

root = Path(__file__).resolve().parents[2]
layout = ET.fromstring((root / "gui/MenuCampaign.layout").read_text(encoding="utf-8"))
mode = (root / "source/modes/MenuModeCampaign.cpp").read_text(encoding="utf-8")
mode_h = (root / "source/modes/MenuModeCampaign.h").read_text(encoding="utf-8")
world_cpp = (root / "source/game/CampaignWorld.cpp").read_text(encoding="utf-8")
world_h = (root / "source/game/CampaignWorld.h").read_text(encoding="utf-8")
campaign_cpp = (root / "source/game/Campaign.cpp").read_text(encoding="utf-8")
gui_cpp = (root / "source/render/Gui.cpp").read_text(encoding="utf-8")
definition = (root / "levels/campaign/Campaign.cfg").read_text(encoding="utf-8")
world_text = (root / "gui/campaign/campaign-world.json").read_text(encoding="utf-8")
world = json.loads(world_text)
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
# Structure table: wing name, its 3 story maps in order with their guild (name, leader, first raid leader, origin,
# groups, members per group, kind), and its bonus map.
EXPECTED_WINGS = [
    ("The Rotting Cellars", [
        ("Brackenford", "The Mud Fists", "Elsa Brack", "", "Brackenford", 1, 5, "group"),
        ("Coldwell", "The Iron Latch", "Hugo Cole", "", "Coldwell", 1, 5, "group"),
        ("Ravensledge", "The Grey Fang", "Rolf Scarrow", "", "Wolfscar", 1, 10, "raid")], "Mossgate"),
    ("The Blood Mines", [
        ("Tinmoor", "The Deep Picks", "Merrin Tay", "", "Tinmoor", 2, 5, "group"),
        ("Greywater", "The Drowned Oath", "Corwin Gray", "", "Greywater", 2, 5, "group"),
        ("Highcairn", "The Stone Crown", "Hilde Cairn", "", "Highcairn", 2, 10, "raid")], "CrowshotGallery"),
    ("The Weeping Crypts", [
        ("Lanternhill", "The Pale Flame", "Ines Vale", "", "Lanternhill", 1, 10, "group"),
        ("Saltmere", "The Salt Wolves", "Bram Seward", "", "Saltmere", 1, 10, "group"),
        ("HollinFen", "The Order of the White Thorn", "Agathe Hollin", "", "Hollin Fen", 1, 25, "raid")],
     "SkittleCavern"),
    ("The Chained Depths", [
        ("Cinderhollow", "The Ember Ram", "Pell Ashgrove", "", "Cinderhollow", 2, 10, "group"),
        ("Ashcombe", "The Burnt Wheel", "Liesl Ashby", "", "Ashcombe", 2, 10, "group"),
        ("Ironbridge", "The Anvil Host", "Gareth Fenn", "", "Ironbridge", 2, 25, "raid")], "SwarmNight"),
    ("The Black Catacombs", [
        ("Bellwick", "The Silent Bell", "Lorens Bell", "", "Bellwick", 1, 25, "group"),
        ("Goldspire", "The Gilded Hand", "Alaric Penn", "", "Goldspire", 1, 25, "group"),
        ("Kingsfall", "The Sun Court", "Prince Aurel", "", "Kingsfall", 1, 40, "raid")], "BoulderCourse"),
    ("The Abyssal Heart", [
        ("VarnsCrossing", "The Black Legion", "Marshal Varn", "", "Varn's Crossing", 2, 25, "group"),
        ("Wraithwood", "The Ash Coven", "Elowen Ash", "", "Wraithwood", 2, 25, "group"),
        ("HollowmarkCitadel", "The Crown Eternal", "High King Castellan", "Sabine Rook", "Hollowmark Citadel", 2, 40,
         "raid")], "TwistingHalls"),
]
EXPECTED_STORY_CAVES = 18
EXPECTED_BONUS_CAVES = 6
MAP_SIZE = (2560, 1600)
ICON_KEYS = ("locked", "current", "defeated", "bonus_found", "bonus_cleared", "wing_defeated", "hover")
ICON_SIZE = (128, 128)
BANNER_SIZE = (160, 320)
PORTRAIT_SIZE = (256, 256)

# ------------------------------------------------------------------------------------------------ CM4: description
check(world.get("version") == 2, "the map description must be version 2")
check(tuple(world.get("size", ())) == MAP_SIZE, "the map must be 2560 x 1600 pixels")
check("provinces" not in world and "sites" not in world, "the provinces and bonus sites of the world map must be gone")
check(not re.search(r'"T\d\d[AB]?"|"B0\d"|mask_rgb|world_idmap', world_text), "no province id, mask or id map may remain")
wings = world.get("wings", [])
check(len(wings) == len(EXPECTED_WINGS), "the map needs exactly 6 wings")
story_caves = [level for wing in wings for level in wing.get("levels", [])]
bonus_caves = [wing["bonus"] for wing in wings if "bonus" in wing]
check(len(story_caves) == EXPECTED_STORY_CAVES, "the map needs 18 level caves")
check(len(bonus_caves) == EXPECTED_BONUS_CAVES, "the map needs 6 bonus caves")
for index, (wing, expected) in enumerate(zip(wings, EXPECTED_WINGS), 1):
    name, expected_levels, bonus = expected
    check(wing.get("wing") == index, "wing %d is out of order" % index)
    check(wing.get("name") == name, "wing %d must be %s" % (index, name))
    check(len(wing.get("levels", [])) == 3, "wing %d needs 3 level caves" % index)
    check(wing.get("bonus", {}).get("file") == "campaign/%s.level" % bonus,
          "wing %d needs the bonus cave %s" % (index, bonus))
    check("guild" not in wing.get("bonus", {}), "the bonus cave of wing %d has no raid" % index)
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
            path = art / guild.get(key, "-")
            check(path.is_file(), label + ": missing " + key + " " + guild.get(key, "-"))
            if path.is_file():
                with Image.open(path) as image:
                    check(image.size == expected_size, label + ": %s must be %d x %d" % ((key,) + expected_size))
check(len({level["guild"]["banner"] for level in story_caves if "guild" in level}) == EXPECTED_STORY_CAVES,
      "every guild needs its own banner")
check(len({level["guild"]["portrait"] for level in story_caves if "guild" in level}) == EXPECTED_STORY_CAVES,
      "every leader needs its own portrait")
check((art / world.get("base", "-")).is_file(), "missing map image " + world.get("base", "-"))
if (art / world.get("base", "-")).is_file():
    with Image.open(art / world["base"]) as image:
        check(image.size == MAP_SIZE, "the map image must be 2560 x 1600")
for key in ICON_KEYS:
    path = art / world.get("icons", {}).get(key, "-")
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
check(len(levels) == EXPECTED_STORY_CAVES + EXPECTED_BONUS_CAVES, "the campaign must have 24 levels")
check(not any("Province" in f for f in levels), "no level may name a province any more")
cfg_story = [(f["File"], f.get("Wing")) for f in levels if f.get("Bonus") != "1"]
map_story = [(level.get("file"), str(wing.get("wing"))) for wing in wings for level in wing.get("levels", [])]
check(cfg_story == map_story, "the story caves of the map must be the story levels of Campaign.cfg in their order")
cfg_bonus = sorted((f["File"], f.get("Wing")) for f in levels if f.get("Bonus") == "1")
map_bonus = sorted((wing["bonus"]["file"], str(wing.get("wing"))) for wing in wings if "bonus" in wing)
check(cfg_bonus == map_bonus, "the bonus caves of the map must be the bonus levels of Campaign.cfg in their wings")
for f in levels:
    check(f.get("Wing", "") in ("1", "2", "3", "4", "5", "6"), f["File"] + " has no Wing setting from 1 to 6")
    check(1 <= int(f.get("Difficulty", "1")) <= 5, f["File"] + " has a difficulty outside of 1 to 5")
check('key == "Province"' not in campaign_cpp and 'key == "Wing"' in campaign_cpp and 'key == "Warden"' in campaign_cpp,
      "the reader must know Wing and Warden and no longer read Province")
check('key == "Map"' not in campaign_cpp and "mMapBlocks" not in campaign_cpp, "the old territory settings must be gone")
check("size_t Campaign::findLevelByFile(const std::string& file) const" in campaign_cpp,
      "the map finds the level of a cave by its file")

# The loader: 6 wings in order, 3 story caves with a guild each, one bonus cave each; no provinces or id map
check("static const uint32_t NUM_WINGS = 6;" in world_h and "static const uint32_t STORY_CAVES_PER_WING = 3;" in world_h,
      "the loader must require 6 wings of 3 story caves")
importer = world_cpp[world_cpp.index("bool CampaignWorld::importDefinition"):world_cpp.index("size_t CampaignWorld::findCave")]
for token in ('get_child("wings")', "wing.mNumber != mWings.size() + 1", "levels.size() != STORY_CAVES_PER_WING",
              'readGuild(level->second.get_child("guild")', 'node.get_child("bonus")', "mWings.size() != NUM_WINGS"):
    check(token in importer, "the loader must check " + token)
for gone in ("Province", "mask", "IdMap", "provinces", "sites"):
    check(gone not in world_cpp and gone not in world_h, "the loader must not know " + gone + " any more")
guild_reader = world_cpp[world_cpp.index("bool readGuild"):world_cpp.index("std::string countText")]
for key in ('"name"', '"leader"', '"first_leader"', '"origin"', '"groups"', '"size"', '"kind"', '"banner"', '"portrait"'):
    check(key in guild_reader, "the guild reader must read " + key)

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
for token in ('"Leader: "', '"Leaders: "', '"\\nRaid size: "', '"\\nOrigin: "'):
    check(token in details, "the guild details must contain " + token)
check("fillGuildPanel();" in fill, "the guild panel is drawn")
panel = world["guild_panel"]


def inside(inner, outer):
    """True if the rectangle [x, y, w, h] lies inside the other one."""
    return (outer[0] <= inner[0] and outer[1] <= inner[1] and inner[0] + inner[2] <= outer[0] + outer[2]
            and inner[1] + inner[3] <= outer[1] + outer[3])


def overlap(a, b):
    """True if two rectangles [x, y, w, h] share an area."""
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


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
check("if(!cave.mBonus && (level < campaign.getNumLevels()))" in fill, "only level caves carry a name on the map")

# ------------------------------------------------------------------------------------------------ menu behaviour
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
check("Guild: " in tip and "Difficulty: " in tip and "State: " in tip and "Bonus cave of " in tip,
      "tooltip shows wing, guild, state and difficulty")
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
fonts = {}
for font_file in (root / "gui/fonts").glob("*.font"):
    spec = ET.parse(font_file).getroot()
    fonts[spec.get("name")] = (root / "gui/fonts" / spec.get("filename"), float(spec.get("size")))


def constant(name):
    """A string or float constant of the menu code, as text."""
    match = re.search(r'const (?:std::string|float) %s = "?([^";]+?)"?f?;' % name, mode)
    return match[1] if match else None


SCREENS = ((640, 480), (800, 600), (1024, 768), (1280, 720), (1280, 1024), (1366, 768), (1920, 1080), (1920, 1200),
           (2560, 1080), (2560, 1440), (3840, 2160), (7680, 4320))
USER_SCALES = (0.8, 1.0, 1.2)
DESIGN_W, DESIGN_H = (float(re.search(r"LAYOUT_DESIGN_%s = ([0-9.]+)f" % k, gui_cpp)[1]) for k in ("WIDTH", "HEIGHT"))
FONT_W, FONT_H = (float(re.search(r"FONT_DESIGN_%s = ([0-9.]+)f" % k, gui_cpp)[1]) for k in ("WIDTH", "HEIGHT"))
# Inner margin of a text window without frame, in screen pixels, and of the framed tooltip, in design pixels
TEXT_MARGIN = 2
TOOLTIP_MARGIN = 12
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
map_texts = [("title", world["title_cartouche"], "FONT_TITLE", [constant("CAMPAIGN_TITLE")], False)]
for wing in wings:
    map_texts.append(("wing %s label" % wing["wing"], wing["label"], "FONT_WING", [wing["name"] + "   3 / 3"], True))
    for cave in wing["levels"]:
        map_texts.append((cave["file"] + " label", cave["label"], "FONT_CAVE", [titles.get(cave["file"], "")], True))
    for level in wing["levels"]:
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
tooltip_texts = ["%s\n%s\nGuild: %s\nState: Defeated, can be played again\nDifficulty: 5 / 5"
                 % (titles.get(level["file"], ""), wing["name"], level["guild"]["name"])
                 for wing in wings for level in wing["levels"]]
tooltip_texts += ["%s\nBonus cave of %s\nState: Cleared, can be played again\nDifficulty: 5 / 5"
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
        face = screen_font(constant("FONT_TOOLTIP"), screen, user_scale)
        for text in tooltip_texts:
            used = wrapped_height(face, text, tooltip[0] - 2 * TOOLTIP_MARGIN * layout_scale, True)
            measured += 1
            check(used is not None and used <= tooltip[1] - 2 * TOOLTIP_MARGIN * layout_scale,
                  "the tooltip text does not fit at " + where)
check(measured > 0, "no text was measured")

# ------------------------------------------------------------------------------------------------ CM5: campaign hall
scene = (root / "config/mainmenuscene.cfg").read_text(encoding="utf-8")
check(re.search(r"(?m)^AddEntity CampaignHall MenuCampaignHall\.mesh ", scene) is not None, "the campaign hall stays")
check(re.search(r"(?m)^AddEntity CampaignTable MenuMapTable\.mesh ", scene) is not None,
      "the map table stays in the hall")
material = (root / "materials/scripts/MenuScene.material").read_text(encoding="utf-8")
block = material[material.index("material MenuCampaignMap"):]
check("texture MenuCampaignMap.png" in block[:block.index("\n}")], "the table shows the texture MenuCampaignMap.png")
models = (root / "tools/blender-assets/menu_scene_models.py").read_text(encoding="utf-8")
check('b.face_materials.append("MenuCampaignMap")' in models, "the table model has the map plane")
hall = root / "materials/textures/menu/MenuCampaignMap.png"
with Image.open(hall) as hall_image, Image.open(art / world["base"]) as map_image:
    check(hall_image.size == map_image.size, "the hall texture must have the size of the map of Moreya")
    check(hall_image.convert("RGBA").tobytes() == map_image.convert("RGBA").tobytes(),
          "the campaign hall must show the map of Moreya (run tools/artwork/moreya-map/make_placeholders.py --hall-only)")
old_world = art / "world_base.png"
if old_world.is_file():
    check(hall.read_bytes() != old_world.read_bytes(), "the campaign hall must not show the old world map")

if failures:
    print("\n".join(failures))
    sys.exit(1)
print("campaign map checks passed: 6 wings, %d level caves, %d bonus caves, %d guilds; %d text fits at %d screens x %d "
      "UI scales; the campaign hall shows the map of Moreya" % (len(story_caves), len(bonus_caves), len(story_caves),
                                                                measured, len(SCREENS), len(USER_SCALES)))
