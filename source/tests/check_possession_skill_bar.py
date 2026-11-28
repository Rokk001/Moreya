"""Skill bar of the possession view (possession view A): runs source/tests/test_PossessionBarRules.cpp without
Boost.Test and checks the wiring from the server to the bar.

The test file is compiled with modes/PossessionBarRules.cpp against a tiny stand-in for the Boost.Test macros it uses
(like check_creature_skill_tree_view.py). The wiring checks read the sources: the server builds the key slots the same
way possessedUseSkill counts them and sends them with the appended message possessionSkillBar when the possession
starts, every turn and after a skill key; the client reads the message into GameMode, which creates the bar when the
possession view opens, keeps it visible while the keeper's windows are hidden, places it every frame and removes it
when the view ends.

Expected: 4 test cases, 0 failures.

Calls (from the repository root):
  python source/tests/check_possession_skill_bar.py
"""
from pathlib import Path
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path as _LangPath
sys.path.insert(0, str(_LangPath(__file__).resolve().parent))
from language_texts import english  # noqa: E402
import tempfile
import time

START = time.monotonic()
repo = Path(__file__).resolve().parents[2]

# Test cases of test_PossessionBarRules.cpp
EXPECTED_CASES = 4

boost_shim = r'''
#include <functional>
#include <iostream>
#include <string>
#include <vector>

struct ShimCase {std::string name; std::function<void()> body;};
inline std::vector<ShimCase>& shimCases() {static std::vector<ShimCase> cases; return cases;}
inline int& shimFailures() {static int failures = 0; return failures;}
struct ShimRegister
{
    ShimRegister(const std::string& name, std::function<void()> body)
    { shimCases().push_back(ShimCase{name, body}); }
};

#define BOOST_AUTO_TEST_CASE(name) \
    static void name(); \
    static ShimRegister shimRegister_##name(#name, name); \
    static void name()
#define BOOST_CHECK(cond) \
    do { if(!(cond)) { ++shimFailures(); std::cout << "FAIL " << __LINE__ << ": " << #cond << "\n"; } } while(0)
#define BOOST_CHECK_EQUAL(a, b) BOOST_CHECK((a) == (b))
'''

main = r'''
#include "BoostTestTargetConfig.h"
int main()
{
    for(const ShimCase& c : shimCases())
        c.body();
    std::cout << shimCases().size() << " cases, " << shimFailures() << " failures\n";
    return shimFailures() == 0 ? 0 : 1;
}
'''

errors = []


def find_vcvars():
    """Returns vcvars64.bat of the installed Visual Studio Build Tools (18 or 2022), or None."""
    bases = [os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)'),
             os.environ.get('ProgramFiles', r'C:\Program Files')]
    for base in bases:
        for version in ('18', '2022'):
            for edition in ('BuildTools', 'Community', 'Professional', 'Enterprise'):
                path = Path(base) / 'Microsoft Visual Studio' / version / edition / 'VC/Auxiliary/Build/vcvars64.bat'
                if path.exists():
                    return path
    return None


def run_test_cases():
    """Compiles and runs the test cases; returns their exit code and output."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / 'BoostTestTargetConfig.h').write_text(boost_shim)
        (tmp / 'main.cpp').write_text(main)
        sources = [repo / 'source/modes/PossessionBarRules.cpp', repo / 'source/tests/test_PossessionBarRules.cpp',
                   tmp / 'main.cpp']
        exe = tmp / 'possession_bar_check.exe'
        compiler = shutil.which('g++') or shutil.which('clang++')
        if compiler:
            command = [compiler, '-std=c++11', '-o', str(exe), '-I' + str(tmp), '-I' + str(repo / 'source')] + \
                [str(s) for s in sources]
            subprocess.run(command, check=True)
        else:
            vcvars = find_vcvars()
            assert shutil.which('cl') is not None or vcvars is not None, 'no C++ compiler found (cl or vcvars64.bat)'
            prefix = '' if shutil.which('cl') else 'call "%s" >nul 2>&1 && ' % vcvars
            flags = '/nologo /EHsc /Fe"%s" /Fo"%s/" /I"%s" /I"%s"' % (exe, tmp.as_posix(), tmp, repo / 'source')
            line = prefix + 'cl ' + flags + ' ' + ' '.join('"%s"' % s for s in sources)
            subprocess.run(line, shell=True, check=True, stdout=subprocess.DEVNULL)
        result = subprocess.run([str(exe)], capture_output=True, text=True)
        return result.returncode, result.stdout


def read(path):
    """Returns the text of a repository file."""
    return (repo / path).read_text(encoding='utf-8')


def function(text, signature):
    """Returns the body of the function that starts with the signature, up to its closing brace."""
    start = text.index(signature)
    return text[start:text.index('\n}\n', start)]


def need(condition, message):
    """Records a wiring problem."""
    if not condition:
        errors.append(message)


setup_start = time.monotonic()
code, output = run_test_cases()
print('ODP_TEST_PHASE {"name":"compile-and-run","seconds":%.3f}' % (time.monotonic() - setup_start))
print(output.strip())
need(code == 0 and ('%d cases, 0 failures' % EXPECTED_CASES) in output,
     'test cases: expected %d cases with 0 failures' % EXPECTED_CASES)

# The message is appended last, so that no existing numeric value changes
notification_h = read('source/network/ServerNotification.h')
enum_body = notification_h[notification_h.index('enum class ServerNotificationType'):]
enum_body = enum_body[:enum_body.index('};')]
names = re.findall(r'^\s*([A-Za-z_]\w*)\s*,?\s*(?://.*)?$', enum_body, re.M)
need(names[-2:] == ['startGameRefused', 'possessionSkillBar'], 'possessionSkillBar must be appended last: %s' % names[-2:])
need('return "possessionSkillBar";' in read('source/network/ServerNotification.cpp'),
     'ServerNotification.cpp: the name of possessionSkillBar is missing')

# Server: one list of key slots, sent at the start, every turn and after a skill key
creature = read('source/entities/Creature.cpp')
slots = function(creature, 'std::vector<CreatureSkillData*> Creature::getPossessedSkillSlots()')
use_skill = function(creature, 'void Creature::possessedUseSkill(uint32_t slot, const Ogre::Vector2& aim)')
for line in ('if(isPossessedBasicAttack(*skillData.mSkill))', 'if(!skillData.mSkill->canBeUsedBy(this))'):
    need(line in slots and line in use_skill, 'the bar slots and the skill keys must use the same filter: %s' % line)
send = function(creature, 'void Creature::sendPossessionSkillBar()')
for needle in ('!mPossessor->getIsHuman()', 'getPossessedSkillSlots()', 'PossessionBarRules::MAX_SLOTS',
               'ServerNotificationType::possessionSkillBar', 'PossessionBarRules::iconImage(skillData.mTreeSkillId',
               'hasManaFor(*skillData.mSkill)', '<< icon << remaining << duration << usable;'):
    need(needle in send, 'Creature::sendPossessionSkillBar: %s missing' % needle)
need('sendPossessionSkillBar();' in function(creature, 'void Creature::startPossession(Player& player)'),
     'Creature::startPossession must send the skill bar')
upkeep = function(creature, 'void Creature::doUpkeep()')
possessed = upkeep[upkeep.index('if(isPossessed())'):upkeep.index('possessedFunc = mActions.back()->action();')]
need('sendPossessionSkillBar();' in possessed, 'Creature::doUpkeep must send the skill bar every possessed turn')
server = read('source/network/ODServer.cpp')
skill_case = server[server.index('case ClientNotificationType::askPossessSkill:'):]
skill_case = skill_case[:skill_case.index('case ClientNotificationType::askPossessExit:')]
need(skill_case.index('creature->possessedUseSkill(slot, aim);') < skill_case.index('creature->sendPossessionSkillBar();'),
     'ODServer: the skill bar must be sent after a skill key')

# Client: the message reaches GameMode, the bar lives with the possession view
client = read('source/network/ODClient.cpp')
bar_case = client[client.index('case ServerNotificationType::possessionSkillBar:'):]
bar_case = bar_case[:bar_case.index('break;\n        }\n')]
for needle in ('count > PossessionBarRules::MAX_SLOTS', 'std::isfinite(slot.mRemaining)', 'gm->setPossessionSkillBar(slots);'):
    need(needle in bar_case, 'ODClient possessionSkillBar: %s missing' % needle)
game = read('source/modes/GameMode.cpp')
need('createPossessionBar();' in function(game, 'void GameMode::enterPossessionView()'),
     'GameMode::enterPossessionView must create the bar')
view = function(game, 'void GameMode::refreshPossessionView()')
need('if (child == mPossessionBar)' in view and 'refreshPossessionBar();' in view,
     'GameMode::refreshPossessionView must keep the bar visible and place it')
need('destroyPossessionBar();' in function(game, 'void GameMode::leavePossessionView()'),
     'GameMode::leavePossessionView must remove the bar')
create = function(game, 'void GameMode::createPossessionBar()')
for needle in ('PossessionBarRules::MAX_SLOTS', 'POSSESSION_BAR_EXIT_PLATE', 'PossessionBarRules::keyLabel(index)',
               'POSSESSION_BAR_RECOVERY'):
    need(needle in create, 'GameMode::createPossessionBar: %s missing' % needle)
need('POSSESSION_BAR_EXIT_TEXT = "mode.game.possession.exit";' in game
     and english('mode.game.possession.exit') == 'Leave   Esc', 'the exit plate must name the Esc key')
refresh = function(game, 'void GameMode::refreshPossessionBar()')
for needle in ('PossessionBarRules::computeLayout(', 'PossessionBarRules::recoveryShare(data)',
               'slot->setEnabled(data.mUsable);'):
    need(needle in refresh, 'GameMode::refreshPossessionBar: %s missing' % needle)

# Build lists
need('${SRC}/modes/PossessionBarRules.cpp' in read('CMakeLists.txt'), 'CMakeLists.txt: PossessionBarRules.cpp missing')
need('add_boost_test(00-PossessionBarRules' in read('source/tests/CMakeLists.txt'),
     'source/tests/CMakeLists.txt: the Boost test 00-PossessionBarRules is missing')

print('ODP_TEST_PHASE {"name":"total","seconds":%.3f}' % (time.monotonic() - START))
if errors:
    for error in errors:
        print('FAIL: ' + error)
    sys.exit(1)
print('possession skill bar: %d test cases, wiring ok' % EXPECTED_CASES)
