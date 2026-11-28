#!/usr/bin/env python3
"""Checks that the Champion fights at level 30, hits as configured and shows a crown instead of a level.

The crown pictures, its material and its imageset lie in the content packages (scripts/content_packages.py); without
the content the config, the script, the scheme and the code are checked and the crown files and their CREDITS rows
(in the CREDITS of the content repository, by their paths) are named as not checked.
"""

import re
import struct
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import content_packages  # noqa: E402
import room_packages  # noqa: E402
#: The crown files of the content packages
CROWN_FILES = ("materials/textures/ChampionCrown.png", "gui/ChampionCrownIcon.png",
               "materials/scripts/ChampionCrown.material", "gui/ChampionCrown.imageset")
#: True when the crown files are present (they are checked only then)
CROWN = all(content_packages.data_file(ROOT, path) is not None for path in CROWN_FILES)
#: The mixed files of config/ and gui/ come with their own rows only with the content (scripts/content_packages.py)
WITH_CONTENT = content_packages.has_content(ROOT)


def read(path):
    """Returns the text of a repository file (a game data file also from the content packages); a mixed file of config/
    or gui/ comes joined with its own rows of the content."""
    return content_packages.read_layout_text(ROOT, path)


def png_size(path):
    """Returns (width, height, colour type) of a png file."""
    data = content_packages.resolve(ROOT, path).read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", path + " is no png"
    width, height = struct.unpack(">II", data[16:24])
    return width, height, data[25]


def function_body(source, signature):
    """Returns the text of the function that starts with the signature."""
    start = source.index(signature)
    brace = source.index("{", start)
    depth = 0
    for index in range(brace, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start:index + 1]
    raise AssertionError("unterminated function " + signature)


# Spell: the cooldown of the rebalance (840 s), price and drain unchanged
if WITH_CONTENT:
    spells = read("config/spells.cfg")
    section = spells[spells.rindex("[Spells]"):spells.rindex("[/Spells]")]
    values = dict(re.findall(r"^\s+(\w+)\s+([\d.]+)\s*$", section, re.M))
    assert values["SummonChampionCooldown"] == "840", "SummonChampionCooldown is 840"
    assert (values["SummonChampionPrice"], values["SummonChampionDrainPerSecond"]) == ("108000", "2250")

# Champion definition: melee damage 146.8 to 220.2 physical, other columns 0, MinHP 600
if WITH_CONTENT:
    creatures = read("config/creatures.cfg")
    blocks = re.findall(r"^\[Creature\]\n(.*?)^\[/Creature\]", creatures, re.M | re.S)
    champions = [b for b in blocks if re.search(r"^\s+Champion\s+1\s*$", b, re.M)]
    assert len(champions) == 1
    champion = champions[0]
    assert re.search(r"^\s+MinHP\s+600\s*$", champion, re.M), "MinHP stays 600"
    melee = re.search(r"^\s+Melee\t(.*)$", champion, re.M)
    assert melee is not None, "the champion has a Melee line"
    columns = melee.group(1).split("\t")
    # Columns after the name: cooldown, warmup, level min, then the damage fields; the six damage columns are the last six
    assert [float(c) for c in columns[0:2]] == [6.0, 1.0], "melee cooldown and warmup unchanged"
    assert [float(c) for c in columns[-6:]] == [146.8, 220.2, 0, 0, 0, 0], "melee damage 146.8 to 220.2 physical"

# Spawn order: level 30 and full hit points before the champion enters the map
cast = function_body(read("source/spells/SpellSummonChampion.cpp"), "bool SpellSummonChampion::castSpell")
level = cast.index("champion->setLevel(MAX_LEVEL);")
heal = cast.index("champion->setHP(champion->getMaxHp());")
add = cast.index("champion->addToGameMap();")
assert level < heal < add, "setLevel, setHP, addToGameMap in this order"
assert re.search(r"static const uint32_t MAX_LEVEL = 30;", read("source/entities/CreatureDefinition.h"))

# Crown picture: one script, the same 64x64 RGBA picture under two names
script = read("tools/gen_champion_crown.py")
for text in ("(8, 52), (8, 22), (20, 36), (32, 14), (44, 36), (56, 22), (56, 52)",
             "(246, 186, 38, 255)", "(120, 80, 10, 255)", "(180, 30, 30, 255)",
             "((20, 44), (32, 44), (44, 44))", "JEWEL_RADIUS = 4", "CROWN_OUTLINE_WIDTH = 3",
             "materials", "ChampionCrown.png", "ChampionCrownIcon.png"):
    assert text in script, text
if not CROWN:
    content_packages.unchecked("check_world_balance_champion", [path for path in CROWN_FILES
                                                                if content_packages.data_file(ROOT, path) is None])
else:
    for path in ("materials/textures/ChampionCrown.png", "gui/ChampionCrownIcon.png"):
        assert png_size(path) == (64, 64, 6), path + " is a 64x64 RGBA picture"
    assert content_packages.resolve(ROOT, "materials/textures/ChampionCrown.png").read_bytes() == \
        content_packages.resolve(ROOT, "gui/ChampionCrownIcon.png").read_bytes(), "both names hold the same picture"

# Material, imageset, scheme and credits
if CROWN:
    material = read("materials/scripts/ChampionCrown.material")
    assert "material ChampionCrown" in material and "texture ChampionCrown.png" in material
    assert "scene_blend alpha_blend" in material
if content_packages.data_file(ROOT, "materials/scripts/CreatureOverlayStatus.material") is not None:
    assert "ChampionCrown" not in read("materials/scripts/CreatureOverlayStatus.material")
if CROWN:
    imageset = read("gui/ChampionCrown.imageset")
    assert 'imagefile="ChampionCrownIcon.png" name="ChampionCrown"' in imageset
    assert '<Image height="64" name="Crown" width="64" xPos="0" yPos="0" />' in imageset
if WITH_CONTENT:
    scheme = ET.fromstring(read("gui/ODSkin.scheme"))
    image_sets = scheme.findall('Imageset')
    icons = [i for i, node in enumerate(image_sets) if node.get('name') == 'OpenDungeonsIcons']
    crown = [i for i, node in enumerate(image_sets) if node.get('name') == 'ChampionCrown']
    assert len(icons) == len(crown) == 1 and icons[0] < crown[0], "crown registered once after the icon set"
    assert image_sets[crown[0]].get('filename') == 'ChampionCrown.imageset', "crown imageset binding"
# The rows of the crown files moved with them into the CREDITS of the content repository, where a row names the file by
# its path (the texture row was "-> ChampionCrown.png" below its folder heading in the public CREDITS)
credits = room_packages.credits_text(ROOT)
if CROWN:
    for text in ("materials/textures/ChampionCrown.png", "gui/ChampionCrownIcon.png", "gui/ChampionCrown.imageset"):
        assert text in credits, text
    assert credits.count("tools/gen_champion_crown.py") == 2

# Overhead overlay: the crown child sits between recovery and status and is created before the first health update
overlay = read("source/render/CreatureOverlayStatus.cpp")
enum = overlay[overlay.index("enum class CreatureOverlays"):overlay.index("nbCreatureOverlays")]
assert re.search(r"recovery,.*crown,.*status,", enum, re.S), "crown after recovery and before status"
constructor = function_body(overlay, "CreatureOverlayStatus::CreatureOverlayStatus(")
crown_block = constructor.index("CreatureOverlays::crown")
assert constructor.index("CreatureOverlays::recovery") < crown_block < constructor.index("updateHealth();")
for text in ('createChildOverlay("MedievalSharp", CROWN_CHAR_HEIGHT', "forceTextArea(crownId, CROWN_SIZE, CROWN_SIZE)",
             "setMaterialName(crownId, CROWN_MATERIAL_NAME)", "displayOverlay(crownId, 0)",
             'CROWN_MATERIAL_NAME = "ChampionCrown"'):
    assert text in overlay, text
assert "CROWN_SIZE = 64" in overlay
shown = function_body(overlay, "static void showLevelDisplay")
assert 'setCaption(levelId, "")' in shown and "displayOverlay(crownId, -1)" in shown
health = function_body(overlay, "void CreatureOverlayStatus::updateHealth()")
assert "showLevelDisplay(" in health and "isChampion()" in health
status = function_body(overlay, "void CreatureOverlayStatus::updateStatus(")
assert status.count("showLevelDisplay(") == 2, "caption restored at both places"
assert status.rstrip().endswith('displayOverlay(crownId, 0);\n}'), "the crown is hidden while a mood symbol is shown"

# Text places show the crown tag
definition = read("source/entities/CreatureDefinition.h")
assert "CHAMPION_CROWN_MARKUP = \"[image-size='w:16 h:16'][image='ChampionCrown/Crown']\"" in definition
creature = read("source/entities/Creature.cpp")
# The handle line with the crown belonged to the shared profile page, deleted by the owner on 2026-11-18
assert 'handle += " - " + CHAMPION_CROWN_MARKUP;' not in creature
assert 'tempSS << "Level: " << CHAMPION_CROWN_MARKUP' in creature
social = read("source/render/SocialWindow.cpp")
# The Dungeonbook list and feed: the crown stands in the level place, the whole name is escaped on its own and word
# wraps (decision 732: never shortened)
assert 'row->getChild("Level")->setText(Gui::toCeguiText(levelText(entry->champion, entry->level)))' in social
assert 'setFullText(row->getChild("Name"), profile.getFullName())' in social
assert "window->setText(Gui::toCeguiText(escapeMarkup(text)));" in social and "elideToWidth" not in social
assert "if(champion)\n        return CHAMPION_CROWN_MARKUP;" in social
# The profile of book-variant-2 has no level row (plan INGAME-QS-11 K1); the crown stays in the list and the feeds
# (the one function levelText gives the crown, and the list and the feed both call it)
assert social.count('CHAMPION_CROWN_MARKUP') >= 1 and social.count('levelText(entry->champion, entry->level)') >= 2

if not WITH_CONTENT:
    content_packages.unchecked("check_world_balance_champion", ["champion spell values (own rows of config/spells.cfg)",
                                                                "champion definition (own rows of config/creatures.cfg)",
                                                                "crown imageset of gui/ODSkin.scheme"])
print("world balance champion checks passed")
