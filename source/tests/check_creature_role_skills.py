"""Check the role skill kinds and the rank properties of the skill tree (roster plan CR6, CR7).

Source checks: every role kind has its skill class (one file pair, registered under the class name the skill line
uses, built into the game), every rank property token of CreatureSkillTree.cpp is documented in the header of
config/creatureSkills.cfg and the other way round, and the creature hooks of CR7 and of the role effects are wired.
Compiled probe (needs cl in the PATH; with --probe a missing compiler is an error): CreatureSkillTree.cpp reads a
small config with the keys Rank1, Rank3 and Rank5 and Properties, merges the properties per rank, refuses an unknown
token and builds the skill line of every role kind. The expected values are fixed data of this check.
"""
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

root = Path(__file__).resolve().parents[2]

# Role kind -> class name of its skill line (contract of the roster work, CREATURE-ROSTER-WORK)
ROLE_KINDS = {
    'TAUNT': 'Taunt', 'PARRY_COUNTER': 'ParryCounter', 'AURA_ALLY_Defense': 'AuraAllyDefense',
    'BUFF_ALLY_Defense': 'BuffAllyDefense', 'SHIELD_ALLY': 'ShieldAlly', 'SHIELD_AREA': 'ShieldArea',
    'HEAL_INSTANT': 'HealInstant', 'HOT_AREA': 'HotArea', 'HOT_SELF': 'HotSelf', 'CURSE_DOT': 'CurseDot',
    'MARK': 'Mark', 'HOLD': 'Hold', 'BLEED': 'Bleed', 'POISON': 'Poison', 'BURN_DOT': 'BurnDot',
    'DRAIN_HEAL_ALLIES': 'DrainHealAllies', 'CHAIN_LIGHTNING': 'ChainLightning', 'FLURRY': 'Flurry'}
# Number of rank property tokens, counted once on the branch that introduced them
PROPERTY_TOKEN_COUNT = 80
# The new effects of the role skills and the names they are saved under
ROLE_EFFECTS = {'Taunt': 'Taunt', 'Mark': 'Mark', 'Hold': 'Hold', 'Protection': 'Protection', 'Shield': 'Shield',
                'DamageOverTime': 'DamageOverTime', 'HealOverTime': 'HealOverTime'}

FIXTURE = '''
[Skill]
Id        TNK_T1
Name      Taunt
Kind      TAUNT
Group     tank
Path      Ironclad
Tier      1
Values    4 5 6 7 8
Mana      2 2 2 2 2
Cooldown  20
Duration  -
Radius    3
Range     2
BaseLine  -
Rank3     AREA 3
Rank5     LESS_DAMAGE_DEALT 0.8 AREA 4
[/Skill]
[Skill]
Id        TNK_T2
Name      Riposte
Kind      PARRY_COUNTER
Group     tank
Path      Evader
Tier      1
Values    10 12 14 16 18
Mana      -
Cooldown  -
Duration  -
Radius    -
Range     -
BaseLine  -
Rank1     -
Rank3     COUNTER 0.5
Rank5     STUN 2
[/Skill]
[Skill]
Id        WAR_F1
Name      Cleaving Spin
Kind      FLURRY
Group     warrior
Path      Ravager
Tier      1
Values    1/0.6 1/0.7 2/0.6 2/0.7 3/0.7
Mana      5 5 5 5 5
Cooldown  14
Duration  -
Radius    2
Range     1
BaseLine  -
Rank1     CAN_CRIT
[/Skill]
[Skill]
Id        MAG_L1
Name      Lightning
Kind      CHAIN_LIGHTNING
Group     mage
Path      Sparkcaller
Tier      1
Values    1 1.1 1.2 1.3 1.4
Mana      6 6 6 6 6
Cooldown  20
Duration  -
Radius    -
Range     -
BaseLine  ChainLightning 20 1 8 0 0 Bolt none 6 0 0 0 0 10 0 0 0 0 0 10 20
[/Skill]
[TierFour]
Creature  PitDemon
Name      Life Leech
Kind      DRAIN_HEAL_ALLIES
Value     8
Cooldown  40
Duration  -
Mana      10
Radius    4
Range     2
BaseLine  -
Properties MANA_DRAIN 0.5
[/TierFour]
'''

# The same config with an unknown token in Rank3: the loader refuses it
BAD_FIXTURE = FIXTURE.replace('Rank3     AREA 3', 'Rank3     NOT_A_TOKEN 3')

PROBE = r'''
#include "creatureskill/CreatureSkillTree.h"
#include <fstream>
#include <iostream>
#include <sstream>
using namespace CreatureSkillTree;

//! \brief Writes the properties as TOKEN:n,n; in their order.
static std::string describe(const std::vector<RankProperty>& properties)
{
    std::ostringstream text;
    for(size_t i = 0; i < properties.size(); ++i)
    {
        text << properties[i].mToken << ":";
        for(size_t j = 0; j < properties[i].mValues.size(); ++j)
            text << (j == 0 ? "" : ",") << properties[i].mValues[j];
        text << ";";
    }
    return text.str();
}

//! \brief Loads the config of argv[1] (and the bad one of argv[2]) and prints lines, properties and the load error.
int main(int argc, char** argv)
{
    std::ifstream file(argv[1]);
    SkillTreeConfig config;
    std::string error;
    if(!config.load(file, error))
    {
        std::cout << "load error " << error << std::endl;
        return 1;
    }
    const std::vector<SkillDef>& skills = config.getSkills();
    for(size_t i = 0; i < skills.size(); ++i)
    {
        const SkillDef& def = skills[i];
        for(uint32_t rank = 1; rank <= 5; ++rank)
        {
            std::cout << "line " << def.mId << " " << rank << " : "
                      << buildSkillLine(def.mKind, def.mValues[rank - 1], def.mCooldown, def.mDuration, def.mRadius,
                                        def.mRange, def.mBaseLine) << std::endl;
            std::cout << "props " << def.mId << " " << rank << " : " << describe(propertiesAtRank(def, rank))
                      << std::endl;
        }
    }
    const TierFourDef* tierFour = config.findTierFour("PitDemon");
    std::cout << "line T4_PitDemon 1 : " << buildSkillLine(tierFour->mKind, tierFour->mValue, tierFour->mCooldown,
        tierFour->mDuration, tierFour->mRadius, tierFour->mRange, tierFour->mBaseLine) << std::endl;
    std::cout << "props T4_PitDemon 1 : " << describe(tierFour->mProperties) << std::endl;

    SkillBuild build;
    build.mRanks["TNK_T2"] = 5;
    build.mRanks["T4_PitDemon"] = 1;
    RankProperty found;
    std::cout << "build STUN " << (findBuildProperty(config, build, "STUN", found) ? found.mValues[0] : -1.0)
              << std::endl;
    std::cout << "build MANA_DRAIN " << (findBuildProperty(config, build, "MANA_DRAIN", found) ? found.mValues[0] : -1.0)
              << std::endl;
    std::cout << "build AREA " << (findBuildProperty(config, build, "AREA", found) ? 1 : 0) << std::endl;

    std::ifstream bad(argv[2]);
    SkillTreeConfig badConfig;
    std::string badError;
    std::cout << "bad " << (badConfig.load(bad, badError) ? "loaded" : badError) << std::endl;
    return 0;
}
'''

# Expected probe output (fixed values of the fixture)
EXPECTED = [
    'line TNK_T1 1 : Taunt 20 0 0 2 3 0 4',
    'props TNK_T1 1 : ',
    'line TNK_T1 3 : Taunt 20 0 0 2 3 0 6',
    'props TNK_T1 3 : AREA:3;',
    'line TNK_T1 5 : Taunt 20 0 0 2 3 0 8',
    'props TNK_T1 5 : AREA:4;LESS_DAMAGE_DEALT:0.8;',
    'line TNK_T2 1 : ParryCounter 0 0 0 0 0 0 10',
    'props TNK_T2 1 : ',
    'props TNK_T2 3 : COUNTER:0.5;',
    'props TNK_T2 5 : COUNTER:0.5;STUN:2;',
    'line WAR_F1 1 : Flurry 14 0 0 1 2 1 0.6',
    'props WAR_F1 1 : CAN_CRIT:;',
    'line WAR_F1 5 : Flurry 14 0 0 1 2 3 0.7',
    'line MAG_L1 2 : ChainLightning 20 1 8 0 0 Bolt none 6 0 0 0 0 11 0 0 0 0 0 11 22',
    'line T4_PitDemon 1 : DrainHealAllies 40 0 0 2 4 0 8',
    'props T4_PitDemon 1 : MANA_DRAIN:0.5;',
    'build STUN 2',
    'build MANA_DRAIN 0.5',
    'build AREA 0',
]
# The loader names the unknown token and the skill
BAD_ERROR = "unknown rank property 'NOT_A_TOKEN' in TNK_T1"


def text(relative):
    return (root / relative).read_text(encoding='utf-8')


def function(source, signature):
    """Returns the source of the function that starts with the signature (up to its closing brace)."""
    start = source.index(signature)
    end = source.index('{', start) + 1
    depth = 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


def property_tokens():
    """The tokens of PROPERTY_TOKENS in CreatureSkillTree.cpp."""
    source = text('source/creatureskill/CreatureSkillTree.cpp')
    block = source[source.index('PROPERTY_TOKENS[] ='):]
    block = block[:block.index('};')]
    return re.findall(r'"([A-Z_]+)"', block)


def cfg_header():
    """The comment lines at the start of creatureSkills.cfg."""
    lines = []
    for line in text('config/creatureSkills.cfg').splitlines():
        if not line.startswith('#') and line.strip():
            break
        lines.append(line)
    return '\n'.join(lines)


def check_sources():
    cmake = text('CMakeLists.txt')
    tree = text('source/creatureskill/CreatureSkillTree.cpp')
    # Every role kind is laid out by the tree and has its own registered class
    for kind, name in ROLE_KINDS.items():
        assert f'"{kind}"' in tree, kind
        header = text(f'source/creatureskill/CreatureSkill{name}.h')
        source = text(f'source/creatureskill/CreatureSkill{name}.cpp')
        assert f'class CreatureSkill{name} : public' in header, name
        assert f'static CreatureSkillRegister reg(new CreatureSkill{name}Factory);' in source, name
        assert f'const std::string CreatureSkill{name}Name = "{name}";' in source, name
        assert f'creatureskill/CreatureSkill{name}.cpp' in cmake, name
    for base in ('Role', 'DamageOverTime'):
        assert f'creatureskill/CreatureSkill{base}.cpp' in cmake, base
    for name, saved in ROLE_EFFECTS.items():
        source = text(f'source/creatureeffect/CreatureEffect{name}.cpp')
        assert f'static const std::string CreatureEffect{name}Name = "{saved}";' in source, name
        assert 'static CreatureEffectRegister reg(' in source, name
        assert f'creatureeffect/CreatureEffect{name}.cpp' in cmake, name

    # Every property token is documented in the header of the config and every documented token exists
    tokens = property_tokens()
    assert len(tokens) == len(set(tokens)) == PROPERTY_TOKEN_COUNT, len(tokens)
    header = cfg_header()
    documented = set(re.findall(r'^#\s{3}([A-Z][A-Z_]+[A-Z])\b', header, re.M))
    documented |= set(re.findall(r'([A-Z][A-Z_]+[A-Z]) n1,', header))
    roles = header[header.index('# Rank properties'):]
    for token in tokens:
        assert re.search(r'\b' + token + r'\b', roles), token
    role_doc = documented & set(re.findall(r'^#\s{3}([A-Z][A-Z_]+[A-Z])\b', roles, re.M))
    assert role_doc <= set(tokens), sorted(role_doc - set(tokens))
    for kind in ROLE_KINDS:
        assert re.search(r'\b' + kind + r'\b', header), kind
    for key in ('Rank1', 'Rank3', 'Rank5', 'Properties'):
        assert re.search(r'^#\s+' + key + r'\s', header, re.M), key

    # CR7: a heal or strengthening cast in a fight gives the experience of one attack of the creature
    creature = text('source/entities/Creature.cpp')
    upkeep = function(creature, 'void Creature::doUpkeep(')
    hook = upkeep[upkeep.index('if(!skillData.mSkill->tryUseSupport('):]
    hook = hook[:hook.index('mNeedFireRefresh = true;')]
    assert 'isHealOrStrengthenSkill(*skillData.mSkill) && isActionInList(CreatureActionType::fight)' in hook
    assert 'receiveExp(getSkillCastExperience());' in hook
    cast = function(creature, 'double Creature::getSkillCastExperience(')
    attack = function(creature, 'void Creature::useAttack(')
    assert 'getRoomConfigDouble("ArenaXpPerFightTurn")' in cast and 'ResearchEffect::XpPerHit' in cast
    assert 'getRoomConfigDouble("ArenaXpPerFightTurn") * mAttackRecoveryTurns' in attack
    assert 'getAppliedCooldownNbTurns(*skillData.mSkill)' in cast and 'isLevelScaledAttack' in cast

    # The creature asks the running role effects and the passive properties
    take = function(creature, 'double Creature::takeDamage(')
    assert 'applySkillDamageRules(attacker, totalDamage)' in take and 'spreadDamageOverTimeOnDeath();' in take
    assert 'getSkillHealReceivedFactor()' in function(creature, 'void Creature::heal(')
    search = function(creature, 'bool Creature::searchBestTargetInList(')
    assert 'getTaunter()' in search and 'getFocusSeatId()' in search and 'isRooted()' in search
    assert 'setTreeProperties(properties)' in function(creature, 'CreatureSkill* Creature::createTreeSkill(')
    assert 'rebuildSkillProperties();' in function(creature, 'void Creature::rebuildTreeSkills(')
    melee = function(text('source/creatureskill/CreatureSkillMeleeFight.cpp'), 'bool CreatureSkillMeleeFight::tryUseFight(')
    assert 'rollSkillParry(parrySkill)' in melee and 'onSkillMeleeResult(' in melee


def run_probe(require):
    if shutil.which('cl') is None:
        assert not require, '--probe needs the compiler (cl) in the PATH'
        print('compiled probe not run (no cl in the PATH)')
        return None
    shim = text('source/tests/check_creature_skill_trees.py')
    shim = shim[shim.index('SHIM = r"""') + len('SHIM = r"""'):]
    shim = shim[:shim.index('"""')]
    getters = []
    global_cfg = text('config/global.cfg')
    for key in ('SkillDeviationPoints', 'SkillResetMinFollowers', 'SkillTier2UnlockRanks', 'SkillTier3UnlockRanks',
                'SkillTier4MinSpent', 'SkillUnfollowedWeight', 'AuraAllyMinAllies', 'SkeletonArmyRadius'):
        found = re.findall(r'^\s*' + key + r'\s+(\S+)', global_cfg, re.M)
        assert len(found) == 1, key
        getters.append('    double get%s() const { return %s; }' % (key, found[0]))
    shim = shim.replace('@GETTERS@', '\n'.join(getters))
    with tempfile.TemporaryDirectory() as work_name:
        work = Path(work_name)
        (work / 'probe.cpp').write_text(PROBE, encoding='utf-8')
        (work / 'probe_shim.h').write_text(shim, encoding='utf-8')
        (work / 'good.cfg').write_text(FIXTURE, encoding='utf-8')
        (work / 'bad.cfg').write_text(BAD_FIXTURE, encoding='utf-8')
        start = time.monotonic()
        subprocess.run(['cl', '/nologo', '/EHsc', '/std:c++17', f'/I{root / "source"}', f'/FI{work / "probe_shim.h"}',
                        'probe.cpp', str(root / 'source/creatureskill/CreatureSkillTree.cpp'), '/Fe:probe.exe'],
                       cwd=work, check=True, stdout=subprocess.DEVNULL)
        print('ODP_TEST_PHASE {"name":"setup","seconds":%.2f}' % (time.monotonic() - start))
        result = subprocess.run([str(work / 'probe.exe'), str(work / 'good.cfg'), str(work / 'bad.cfg')], cwd=work,
                                check=True, capture_output=True, text=True)
    return result.stdout.splitlines()


def check_probe(output):
    """The lines, merged properties and build lookups of the fixture, and the refused unknown token."""
    for line in EXPECTED:
        assert line in output, (line, output)
    bad = [line for line in output if line.startswith('bad ')]
    assert len(bad) == 1 and bad[0].startswith('bad line ') and bad[0].endswith(BAD_ERROR), bad


def main():
    check_sources()
    output = run_probe('--probe' in sys.argv)
    if output is not None:
        check_probe(output)
    print('check_creature_role_skills: ok')


main()
