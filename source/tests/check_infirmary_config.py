"""Check the infirmary config contract without compiling or launching the game."""
from collections import Counter
from pathlib import Path
import re
import sys

repo = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo / "scripts"))
import content_packages  # noqa: E402

# Read one configured scalar and reject missing or duplicate declarations.
def value(text, key):
    found = re.findall(r"^\s*" + re.escape(key) + r"\s+([^#\s]+)", text, re.M)
    assert len(found) == 1, (key, found)
    return float(found[0])

# Validate every fixed parameter and the roster-derived cot shares. The tables are mixed (config/rooms.cfg,
# creatures.cfg, skills.cfg): they are read with their own rows from the content; without it only the code is checked.
def main():
    manager = (repo / "source/game/SkillManager.cpp").read_text(encoding="utf-8")
    assert re.search(r'\{SkillType::roomInfirmary,\s*"HealTime",\s*ResearchBaseSource::rooms,\s*"InfirmaryFullHealSeconds",\s*""\}', manager)
    assert re.search(r'createSkill\(mSkills,\s*SkillType::roomInfirmary,\s*(?:std::vector<SkillType>)?\{SkillType::roomGuardRoom\}\)', manager)
    if not content_packages.has_content(repo):
        content_packages.unchecked("check_infirmary_config", ["config/rooms.cfg", "config/creatures.cfg",
                                                              "config/skills.cfg"])
        print("infirmary config: ok (code only)")
        return
    rooms = content_packages.read_text(repo, "config/rooms.cfg")
    expected = {"InfirmaryCostPerTile": 240, "InfirmaryHP": 50,
        "InfirmaryFullHealSeconds": 60, "DormitoryFullHealSeconds": 150,
        "InfirmaryCotShareSmall": 12, "InfirmaryCotShareMedium": 17,
        "InfirmaryCotShareLarge": 6, "InfirmaryMinRoomSide": 4,
        "InfirmaryAdmissionWageShare": .3, "InfirmaryMoodWageShare": .075,
        "InfirmaryManaPerWage": 2, "InfirmaryDischargeMinPercent": 40,
        "InfirmaryDischargeMaxPercent": 100, "InfirmaryDischargeStepPercent": 10,
        "InfirmaryDischargeDefaultPercent": 100,        "InfirmaryHealGlowTurns": 7, "InfirmaryShamanWalkMinSeconds": 8,
        "InfirmaryShamanWalkMaxSeconds": 15, "InfirmaryShamanPoseMinSeconds": 10,
        "InfirmaryShamanPoseMaxSeconds": 20, "InfirmaryShamanAnimationSeconds": 2}
    if "void Tile::addDirt(" in (repo / "source/entities/Tile.cpp").read_text(encoding="utf-8"):
        expected["InfirmaryDirtPerTreatment"] = 17.4
    for key, number in expected.items():
        assert value(rooms, key) == number, key
    # The mood is a one-time value (share of the wage) added to the stored mood: no mood duration key any more.
    assert not re.search(r"^\s*InfirmaryMoodDefaultTurns\b", rooms, re.M)
    assert value(rooms, "InfirmaryCostPerTile") == value(rooms, "PrisonCostPerTile")
    creatures = content_packages.read_text(repo, "config/creatures.cfg")
    dimensions = Counter(tuple(sorted(map(int, row))) for row in
        re.findall(r"^\s*BedDim\s+(\d+)\s+(\d+)\s*$", creatures, re.M))
    assert dimensions == {(1, 1): 12, (1, 2): 17, (2, 2): 6}, dimensions
    skills = re.sub(r'#[^\n]*', '', content_packages.read_text(repo, "config/skills.cfg"))
    assert value(skills.split("[Skills]", 1)[1].split("[/Skills]", 1)[0], "roomInfirmary") == 600
    assert re.search(r"^\s*roomInfirmary\s+HealTime\s+mul\s+1\.0\s+0\.8\s+0\.667\s*$", skills, re.M)
    print("infirmary config: ok")

if __name__ == "__main__":
    main()
