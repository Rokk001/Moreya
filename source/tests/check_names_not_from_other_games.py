"""Check player-facing item, potion, herb, effect, room and research names against the hook's local term list.

The item and potion tables (config/items.cfg, config/potions.cfg) live in content packages (found through
scripts/content_packages.py); without the content their names are named as not checked and the names of the public
source (effects, rooms, research) are still checked with their fixed counts."""
import importlib.util
import re
from check_items_cfg import ROOT, blocks, read, value
import content_packages
from lang_texts import english_texts


def main():
    """Check whole-word names using the hook's fail-closed local term-list lookup (the table names only when the
    content is present)."""
    spec = importlib.util.spec_from_file_location("protected_content", ROOT / "scripts/check-protected-content.py")
    protected = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(protected)
    terms, error = protected.find_terms(str(ROOT), None)
    if terms is None:
        raise SystemExit("Name check cannot run: " + error)
    displays, counts = [], []
    tables = [name for name in ("config/items.cfg", "config/potions.cfg")
              if content_packages.data_file(ROOT, name) is not None]
    with_content = len(tables) == 2
    if with_content:
        for text, tag in ((read("config/items.cfg"), "Quality"), (read("config/potions.cfg"), "Potion"),
                          (read("config/potions.cfg"), "Herb")):
            names = [value(block, "Display") for block in blocks(text, tag)]
            counts.append(len(names))
            displays.extend(names)
    else:
        content_packages.unchecked("check_names_not_from_other_games",
                                   ["display names of config/items.cfg and config/potions.cfg"])
    effect_table = read("source/entities/ItemEffects.cpp").split("EFFECT_IDS[]", 1)[1].split("};", 1)[0]
    # The names of the effects are the texts of the language entries ui.itemeffect.<lower case id> (an id stands in
    # for its name when the content with the language files is not there)
    english = english_texts(ROOT) or {}
    effect_names = [english.get("ui.itemeffect." + effect.lower(), effect)
                    for effect in re.findall(r'"([^"]+)"', effect_table)]
    counts.append(len(effect_names))
    displays.extend(effect_names)
    room_names = []
    for name in ("RoomMerchant", "RoomHerbGarden", "RoomAlchemyLab"):
        source = read("source/rooms/" + name + ".cpp")
        readable = re.findall(r'getNameReadable\(\)[\s\S]*?\{([\s\S]*?)\}', source)
        assert len(readable) == 1, "missing or ambiguous room display getter: " + name
        body = readable[0]
        returned = re.search(r'return\s+(\w+)\s*;', body)
        assert returned, "missing readable return: " + name
        literal = re.search(r'const std::string\s+' + returned[1] + r'\s*=\s*"([^"]+)"', body)
        if literal is None:
            literal = re.search(r'const std::string\s+' + returned[1] + r'\s*=\s*"([^"]+)"', source)
        assert literal, "unresolved readable room constant: " + name
        room_names.append(literal[1])
    assert set(room_names) == {"Merchant room", "Herb garden", "Alchemy lab"}
    counts.append(len(room_names))
    displays.extend(room_names)
    research = read("source/game/SkillType.cpp").split("std::string skillTypeToPlayerVisibleString(", 1)[1]
    research = research.split("bool isRewardSkill(", 1)[0]
    research_names = []
    for skill in ("roomMerchant", "roomHerbGarden", "roomAlchemyLab", "trapFineTools", "trapMasterTools", "spellSunthornCultivation"):
        found = re.search(r'case SkillType::' + skill + r':\s*return "([^"]+)"', research)
        assert found, "missing research display: " + skill
        research_names.append(found[1])
    assert set(research_names) == {"The Merchant Room", "The Herb Garden", "The Alchemy Lab", "Fine Tools", "Master Tools", "Sunthorn Cultivation"}
    counts.append(len(research_names))
    displays.extend(research_names)
    if with_content:
        assert counts == [551, 29, 4, 49, 3, 6], "incomplete player-name extraction: " + repr(counts)
        assert len(displays) == 642
    else:
        # the public part of the same fixed counts (effects, rooms, research)
        assert counts == [49, 3, 6], "incomplete player-name extraction: " + repr(counts)
        assert len(displays) == 58
    hits = [(display, term) for display in displays for term in terms
            if re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", display, re.I)]
    assert not hits, "forbidden whole-word name matches: " + repr(hits)
    print("player-facing names: local-list word-boundary check passed (%d names)" % len(displays))


if __name__ == "__main__":
    main()
