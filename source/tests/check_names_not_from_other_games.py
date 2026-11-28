"""Check player-facing item, potion, herb, effect, room and research names against the hook's local term list.

The item and potion tables (config/items.cfg, config/potions.cfg) and the room and research names (the entries
room.<id>.name and research.<skill>.name of the English language package) live in content packages (found through
scripts/content_packages.py); without the content their names are named as not checked and the effect names of the
public source are still checked with their fixed count."""
import importlib.util
import re
from check_items_cfg import ROOT, blocks, read, value
import content_packages
import language_package_texts


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
    effect_table = read("source/entities/ItemEffects.cpp").split("EFFECT_NAMES[]", 1)[1].split("};", 1)[0]
    effect_names = re.findall(r'\{"[^"]+",\s*"([^"]+)"\}', effect_table)
    counts.append(len(effect_names))
    displays.extend(effect_names)
    # The room and research names are entries of the English language package; the code asks for them by key
    if with_content:
        english = language_package_texts.english(ROOT)
        room_keys = {"RoomMerchant": "room.merchant.name", "RoomHerbGarden": "room.herbgarden.name",
                     "RoomAlchemyLab": "room.alchemylab.name"}
        room_names = []
        for name, key in room_keys.items():
            assert 'Translation::tr("%s")' % key in read("source/rooms/" + name + ".cpp") or \
                'Translation::tr(ROOM_DISPLAY_KEY)' in read("source/rooms/" + name + ".cpp"), "missing readable key: " + name
            assert key in english, "missing room name: " + key
            room_names.append(english[key])
        assert set(room_names) == {"Merchant room", "Herb garden", "Alchemy lab"}
        counts.append(len(room_names))
        displays.extend(room_names)
        research = read("source/game/SkillType.cpp").split("std::string skillTypeToPlayerVisibleString(", 1)[1]
        research = research.split("bool isRewardSkill(", 1)[0]
        research_names = []
        for skill in ("roomMerchant", "roomHerbGarden", "roomAlchemyLab", "trapFineTools", "trapMasterTools", "spellSunthornCultivation"):
            key = "research.%s.name" % skill.lower()
            assert re.search(r'case SkillType::' + skill + r':\s*return Translation::tr\("' + key + r'"\)', research), "missing research key: " + skill
            assert key in english, "missing research display: " + key
            research_names.append(english[key])
        assert set(research_names) == {"The Merchant Room", "The Herb Garden", "The Alchemy Lab", "Fine Tools", "Master Tools", "Sunthorn Cultivation"}
        counts.append(len(research_names))
        displays.extend(research_names)
    else:
        content_packages.unchecked("check_names_not_from_other_games", ["room and research names of the English language package"])
    if with_content:
        assert counts == [551, 29, 4, 49, 3, 6], "incomplete player-name extraction: " + repr(counts)
        assert len(displays) == 642
    else:
        # the public part of the same fixed counts (effects)
        assert counts == [49], "incomplete player-name extraction: " + repr(counts)
        assert len(displays) == 49
    hits = [(display, term) for display in displays for term in terms
            if re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", display, re.I)]
    assert not hits, "forbidden whole-word name matches: " + repr(hits)
    print("player-facing names: local-list word-boundary check passed (%d names)" % len(displays))


if __name__ == "__main__":
    main()
