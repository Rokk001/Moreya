"""Validate all potion recipes, growth inputs and their required atlas entries.

The recipes config/potions.cfg and the atlas gui/Items.imageset live in content packages (found through
scripts/content_packages.py); without the content the check names them as not checked and passes."""
import xml.etree.ElementTree as ET
from check_items_cfg import ROOT, blocks, read, value
import content_packages


def main():
    """Check exact potion counts and resource references without accepting a partial atlas (named as not checked when
    the content is not present)."""
    missing = [name for name in ("config/potions.cfg", "gui/Items.imageset")
               if content_packages.data_file(ROOT, name) is None]
    if missing:
        content_packages.unchecked("check_potions_cfg", missing)
        return
    text = read("config/potions.cfg")
    potions, herb_blocks = blocks(text, "Potion"), blocks(text, "Herb")
    assert len(potions) == 29 and len(herb_blocks) == 4
    herbs = {value(block, "Id"): block for block in herb_blocks}
    assert {name: float(value(block, "GrowSeconds")) for name, block in herbs.items()} == {
        "Bloodroot": 90, "Moonlily": 90, "Ironfern": 90, "Sunthorn": 240}
    for name, block in herbs.items():
        assert int(value(block, "Stages")) == 3
        assert value(block, "Research") == ("spellSunthornCultivation" if name == "Sunthorn" else "none")
    kinds = {"healing": "HealPercent", "mana": "ManaPercent", "strength": "StrengthChange",
             "dexterity": "DexterityChange", "guard": "DefenseChange", "vitality": "MaxHPChange",
             "focus": "MaxManaChange", "mending": "HealPerTenSeconds", "flow": "ManaRegenChange"}
    ids, images = set(), []
    for potion in potions:
        name, size, kind = value(potion, "Id"), value(potion, "Size"), value(potion, "Kind")
        assert name not in ids, name
        ids.add(name)
        if size == "Single":
            assert (name, kind, int(value(potion, "LevelMin"))) in {
                ("lifespring", "FullRestore", 20), ("thaw", "EndFreeze", 1)}
            assert float(value(potion, "Duration")) == 0
        else:
            index = {"Small": 0, "Medium": 1, "Large": 2}[size]
            prefix = name.rsplit("_", 1)[0]
            assert kind == kinds[prefix]
            assert int(value(potion, "LevelMin")) == (1, 10, 20)[index]
            assert float(value(potion, "Duration")) == (0 if prefix in {"healing", "mana"} else (30, 60, 90)[index])
        recipe = value(potion, "Herbs").split()
        assert len(recipe) % 2 == 0 and recipe
        assert all(recipe[index] in herbs and int(recipe[index + 1]) > 0 for index in range(0, len(recipe), 2)), name
        assert float(value(potion, "BrewSeconds")) > 0 and float(value(potion, "Price")) > 0
        image = value(potion, "Image")
        images.append(image)
    assert ids == {kind + "_" + size for kind in kinds for size in ("small", "medium", "large")} | {"lifespring", "thaw"}
    atlas = ET.parse(str(content_packages.resolve(ROOT, "gui/Items.imageset"))).getroot()
    assert atlas.get("name") == "ItemImages"
    atlas_names = {image.get("name") for image in atlas.iter("Image")}
    for image in images:
        assert image in atlas_names, "missing potion atlas entry: " + image
    print("potions: 29 recipes, four herbs, durations, level gates and complete image references passed")


if __name__ == "__main__":
    main()
