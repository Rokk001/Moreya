"""Validate the equipment catalogue, its group and family paths, prices and actual creature weapon compatibility.

The catalogue config/items.cfg lives in a content package (found through scripts/content_packages.py); without the
content the check names the catalogue as not checked and passes."""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import content_packages  # noqa: E402
KINDS = {"Damage%", "MaxHP%", "CritChance", "Defense%", "AttackRating%", "DefenseRating%",
         "MoveSpeed%", "Avoid", "Cooldown%", "DamageAttribute", "Life", "Mana", "ManaCost%",
         "Wakefulness%", "Dig%", "Claim%", "Carry%"}
# Path lines per (Group, Path) of the effect-based assignment to the new roster, counted once on the branch
# feature/drop-items-roster after the moves and the 46 new lines of the drop items plan: one line per path, slot
# and weapon class that a creature of the path carries.
PATH_COUNTS = {
    ("tank", "Ironclad"): 10, ("tank", "Evader"): 10, ("tank", "Regenerator"): 10,
    ("healer", "Renewer"): 6, ("healer", "Mender"): 6, ("healer", "Warder"): 6,
    ("supporter", "Empowerer"): 6, ("supporter", "Binder"): 6, ("supporter", "Blighter"): 6,
    ("warrior", "Slayer"): 6, ("warrior", "Ravager"): 6, ("warrior", "Reaver"): 6,
    ("skirmisher", "Assassin"): 6, ("skirmisher", "Venomist"): 6, ("skirmisher", "Whirlwind"): 6,
    ("marksman", "Sharpshooter"): 5, ("marksman", "Poisoner"): 5, ("marksman", "Barrager"): 5,
    ("mage", "Pyromancer"): 5, ("mage", "Sparkcaller"): 5, ("mage", "Witherer"): 5,
    ("worker", "Delving"): 5, ("worker", "Claiming"): 5, ("worker", "Survival"): 5,
    ("family", "Arcane"): 5, ("family", "Demon"): 5, ("family", "Greenskin"): 8, ("family", "Dwarf"): 6,
    ("family", "Elf"): 6, ("family", "Human"): 7, ("family", "Undead"): 6, ("family", "Dragonkin"): 5,
    ("family", "Workfolk"): 5, ("family", "Beastkin"): 5, ("family", "Stonekin"): 5, ("family", "Vermin"): 4,
    ("family", "Bloodbound"): 5,
}
# Weapon and shield lines whose WeaponClass no creature of their group or family spawns with (counted once on the
# branch feature/drop-items-roster): none, the lines that named a class their path does not carry moved to paths that
# carry it and the wand and crossbow lines left the game.
UNWEARABLE = set()


def read(name):
    """Read a repository input (the public file, else the file of a content package) without discarding its Unicode
    display names."""
    return content_packages.read_text(ROOT, name)


def blocks(text, tag):
    """Return complete tagged blocks after removing configuration comments."""
    text = re.sub(r"#[^\n]*", "", text)
    return re.findall(r"\[" + tag + r"\]([\s\S]*?)\[/" + tag + r"\]", text)


def values(block, key):
    """Return each complete value line for a possibly repeated configuration key."""
    return re.findall(r"^\s*" + re.escape(key) + r"[ \t]+([^\r\n]+)", block, re.M)


def value(block, key):
    """Require one occurrence of a scalar configuration field."""
    found = values(block, key)
    assert len(found) == 1, (key, found)
    return found[0].strip()


def main():
    """Assert every prescribed catalogue count, path, quality, range, price and weapon class (the catalogue is named as
    not checked when the content is not present)."""
    if content_packages.data_file(ROOT, "config/items.cfg") is None:
        content_packages.unchecked("check_items_cfg", ["config/items.cfg"])
        return
    items = blocks(read("config/items.cfg"), "Item")
    assert len(items) == 224, "expected five Poor and 219 path lines"
    equipment = {value(block, "Name"): block for block in blocks(read("config/equipments.cfg"), "Equipment")}
    creatures = blocks(read("config/creatures.cfg"), "Creature")
    effects_source = read("source/entities/ItemEffects.cpp")
    effect_table = effects_source.split("EFFECT_NAMES[]", 1)[1].split("};", 1)[0]
    effects = set(re.findall(r'\{"([^"]+)",\s*"[^"]+"\}', effect_table))
    group_paths, family_paths = set(), {}
    for skill in blocks(read("config/creatureSkills.cfg"), "Skill"):
        if values(skill, "Group"):
            group_paths.add((value(skill, "Group"), value(skill, "Path")))
        else:
            family_paths[value(skill, "Family")] = value(skill, "Path")
    path_counts, unwearable = {}, set()
    identifiers, displays, poor, paths = set(), set(), [], []
    for item in items:
        item_id = value(item, "Id")
        assert item_id not in identifiers, item_id
        identifiers.add(item_id)
        qualities = {value(block, "Name"): block for block in blocks(item, "Quality")}
        if value(item, "Path") == "none":
            poor.append(item_id)
            assert set(qualities) == {"Poor"}, item_id
        else:
            paths.append(item_id)
            assert set(qualities) == {"Common", "Rare", "Epic"}, item_id
            owner = (value(item, "Group"), value(item, "Path"))
            assert owner in group_paths or (owner[0] == "family" and owner[1] in family_paths.values()), (item_id, owner)
            path_counts[owner] = path_counts.get(owner, 0) + 1
        representative = value(item, "PoorEquipment")
        if representative != "none":
            assert representative in equipment, (item_id, representative)
        slot, weapon_class = value(item, "Slot"), value(item, "WeaponClass")
        if slot in {"weapon", "shield"} and value(item, "Path") != "none":
            eligible = []
            for creature in creatures:
                group = value(creature, "SkillGroup")
                family = value(creature, "SkillFamily")
                if not (family_paths.get(family) == value(item, "Path") if value(item, "Group") == "family"
                        else group == value(item, "Group")):
                    continue
                for hand in ("WeaponSpawnR", "WeaponSpawnL"):
                    for spawned in values(creature, hand):
                        if spawned in equipment:
                            eligible.append(value(equipment[spawned], "WeaponType"))
            if weapon_class not in eligible:
                unwearable.add(item_id)
            assert value(equipment[representative], "WeaponType") == weapon_class, item_id
        for quality, block in qualities.items():
            display = value(block, "Display")
            if quality != "Poor":
                assert display.casefold() not in displays, display
                displays.add(display.casefold())
            minimum = {"Poor": 1, "Common": 1, "Rare": 10, "Epic": 20}[quality]
            assert int(value(block, "LevelMin")) == minimum, (item_id, quality)
            counts = tuple(map(int, value(block, "BonusCount").split()))
            assert counts == {"Poor": (0, 0), "Common": (1, 1), "Rare": (2, 3), "Epic": (4, 5)}[quality], item_id
            bonuses = values(block, "Bonus")
            assert len(bonuses) >= counts[1], (item_id, quality)
            for bonus in bonuses:
                kind, low, high = bonus.split()
                assert kind in KINDS and float(low) <= float(high), (item_id, bonus)
            actual_effects = values(block, "Effect")
            assert len(actual_effects) == {"Poor": 0, "Common": 0, "Rare": 1, "Epic": 2}[quality], item_id
            assert all(effect.split()[0] in effects for effect in actual_effects), item_id
            price = tuple(map(float, value(block, "Price").split()))
            assert price == {"Poor": (20,), "Common": (100,), "Rare": (300, 100), "Epic": (1500, 250)}[quality], item_id
    assert len(poor) == 5 and len(paths) == 219 and len(displays) == 657
    assert set(poor) == {"POOR_Head", "POOR_Armour", "POOR_Boots", "POOR_Ring", "POOR_Shield"}
    assert path_counts == PATH_COUNTS, sorted(set(path_counts.items()) ^ set(PATH_COUNTS.items()))
    assert unwearable == UNWEARABLE, sorted(unwearable ^ UNWEARABLE)
    print("equipment catalogue: 224 lines, 657 distinct path displays, %d group/family paths, %d unwearable weapon lines,"
          " ranges/effects/prices/weapons passed" % (len(PATH_COUNTS), len(UNWEARABLE)))


if __name__ == "__main__":
    main()
