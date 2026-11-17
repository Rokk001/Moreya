"""Creature skill tree window: runs source/tests/test_CreatureSkillTreeView.cpp without Boost.Test and checks the
wiring of the window.

The test file is compiled with creatureskill/CreatureSkillTreeView.cpp and CreatureSkillTree.cpp against a tiny
stand-in for the Boost.Test macros it uses and for the configuration and log singletons (like
check_level_script.py and check_creature_skill_trees.py), and run on config/creatureSkills.cfg. The wiring checks
read the layouts and the sources: the window layout holds the tier 4 node and 4 columns of 3 tiers, it is imported by
ModeGame.layout, only the Dungeonbook (SocialWindow) shows and connects the profile's skill tree button, and clicking
a skill spends nothing.

Expected: 5 test cases, 0 failures; 13 skill buttons in gui/WindowCreatureSkillTree.layout.

Calls (from the repository root):
  python source/tests/check_creature_skill_tree_view.py
"""
from pathlib import Path
import os
import re
import shutil
import subprocess
import sys
import tempfile

repo = Path(__file__).resolve().parents[2]

# Test cases of test_CreatureSkillTreeView.cpp and skill buttons of the window (tier 4 and 4 x 3)
EXPECTED_CASES = 5
EXPECTED_BUTTONS = 13

boost_shim = r'''
#include <functional>
#include <iostream>
#include <string>
#include <utility>
#include <vector>

struct ShimCase {std::string name; std::function<void()> body;};
inline std::vector<ShimCase>& shimCases() {static std::vector<ShimCase> cases; return cases;}
inline int& shimFailures() {static int failures = 0; return failures;}
struct ShimRegister
{
    ShimRegister(const std::string& name, std::function<void()> body)
    { shimCases().push_back(ShimCase{name, body}); }
};
struct ShimAbort {};

#define BOOST_AUTO_TEST_CASE(name) \
    static void name(); \
    static ShimRegister shimRegister_##name(#name, name); \
    static void name()
#define SHIM_CHECK(cond, text, fatal) \
    do { if(!(cond)) { ++shimFailures(); std::cout << "FAIL " << __LINE__ << ": " << text << "\n"; \
         if(fatal) throw ShimAbort(); } } while(0)
#define BOOST_CHECK(cond) SHIM_CHECK((cond), #cond, false)
#define BOOST_REQUIRE(cond) SHIM_CHECK((cond), #cond, true)
#define BOOST_CHECK_EQUAL(a, b) SHIM_CHECK((a) == (b), #a " == " #b, false)
#define BOOST_REQUIRE_EQUAL(a, b) SHIM_CHECK((a) == (b), #a " == " #b, true)
'''

main = r'''
#include "BoostTestTargetConfig.h"
int main()
{
    for(const ShimCase& c : shimCases())
    {
        try { c.body(); }
        catch(const ShimAbort&) {}
    }
    std::cout << shimCases().size() << " cases, " << shimFailures() << " failures\n";
    return shimFailures() == 0 ? 0 : 1;
}
'''

# The skill tree code reads tuning values from the configuration and logs errors; the view never calls them, so the
# singletons are replaced (their include guards are taken first) by empty stand-ins.
config_shim = r'''#define CONFIGMANAGER_H
#define LOGMANAGER_H
#include <iostream>
#include <string>
class ConfigManager
{
public:
    static ConfigManager& getSingleton() { static ConfigManager config; return config; }
    double getSkillDeviationPoints() const { return 20; }
    double getSkillResetMinFollowers() const { return 3; }
    double getSkillTier2UnlockRanks() const { return 1; }
    double getSkillTier3UnlockRanks() const { return 2; }
    double getSkillTier4MinSpent() const { return 20; }
    double getSkillUnfollowedWeight() const { return 3; }
    double getAuraAllyMinAllies() const { return 2; }
    double getSkeletonArmyRadius() const { return 3; }
};
#define OD_LOG_ERR(_message) (std::cerr << (std::string("") + _message) << std::endl)
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
    """Compiles and runs the test cases; returns their output."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / 'BoostTestTargetConfig.h').write_text(boost_shim)
        (tmp / 'config_shim.h').write_text(config_shim)
        (tmp / 'main.cpp').write_text(main)
        sources = [repo / 'source/creatureskill/CreatureSkillTree.cpp',
                   repo / 'source/creatureskill/CreatureSkillTreeView.cpp',
                   repo / 'source/tests/test_CreatureSkillTreeView.cpp', tmp / 'main.cpp']
        exe = tmp / 'skill_tree_view_check.exe'
        compiler = shutil.which('g++') or shutil.which('clang++')
        if compiler:
            command = [compiler, '-std=c++11', '-include', str(tmp / 'config_shim.h'), '-o', str(exe),
                       '-I' + str(tmp), '-I' + str(repo / 'source')] + [str(s) for s in sources]
            subprocess.run(command, check=True)
        else:
            vcvars = find_vcvars()
            assert shutil.which('cl') is not None or vcvars is not None, 'no C++ compiler found (cl or vcvars64.bat)'
            prefix = '' if shutil.which('cl') else 'call "%s" >nul 2>&1 && ' % vcvars
            flags = '/nologo /EHsc /std:c++17 /FI"%s" /Fe"%s" /Fo"%s/" /I"%s" /I"%s"' % (
                tmp / 'config_shim.h', exe, tmp.as_posix(), tmp, repo / 'source')
            line = prefix + 'cl ' + flags + ' ' + ' '.join('"%s"' % s for s in sources)
            subprocess.run(line, shell=True, check=True, stdout=subprocess.DEVNULL)
        environment = dict(os.environ)
        environment['OD_TEST_CREATURE_SKILLS_FILE'] = str(repo / 'config/creatureSkills.cfg')
        # Windows application control may block a freshly built program (WinError 4551); the runner repeats the
        # whole check, including compilation.
        result = subprocess.run([str(exe)], env=environment, capture_output=True, text=True)
        return result.returncode, result.stdout


def read(path):
    """Returns the text of a repository file."""
    return (repo / path).read_text(encoding='utf-8')


code, output = run_test_cases()
print(output.strip())
if code != 0 or ('%d cases, 0 failures' % EXPECTED_CASES) not in output:
    errors.append('test cases: expected %d cases with 0 failures' % EXPECTED_CASES)

layout = read('gui/WindowCreatureSkillTree.layout')
buttons = re.findall(r'type="OD/ResearchButton" name="([^"]+)"', layout)
expected = ['TierFour'] + ['Column%dTier%d' % (c, t) for c in range(4) for t in (3, 2, 1)]
if len(buttons) != EXPECTED_BUTTONS or sorted(buttons) != sorted(expected):
    errors.append('gui/WindowCreatureSkillTree.layout: expected the %d skill buttons %s' % (EXPECTED_BUTTONS, expected))
for name in expected:
    for suffix in ('Bar', 'Rank'):
        if 'name="%s%s"' % (name, suffix) not in layout:
            errors.append('gui/WindowCreatureSkillTree.layout: %s%s missing' % (name, suffix))
for column in range(4):
    if 'name="Column%dTitle"' % column not in layout:
        errors.append('gui/WindowCreatureSkillTree.layout: Column%dTitle missing' % column)
if 'filename="WindowCreatureSkillTree.layout"' not in read('gui/ModeGame.layout'):
    errors.append('gui/ModeGame.layout does not import WindowCreatureSkillTree.layout')

profile = read('gui/WindowCreatureProfilePage.layout')
button = re.search(r'name="SkillTreeButton" >(.*?)</Window>', profile, re.S)
if button is None or '<Property name="Visible" value="False" />' not in button.group(1):
    errors.append('gui/WindowCreatureProfilePage.layout: SkillTreeButton missing or not hidden by default')

social = read('source/render/SocialWindow.cpp')
for needle in ('getChild("SkillTreeButton")->setVisible(', '&SocialWindow::onSkillTreeClicked',
               '&SocialWindow::onSkillTreeCloseClicked', 'buildTreeView('):
    if needle not in social:
        errors.append('source/render/SocialWindow.cpp: %s missing' % needle)
# Only the Dungeonbook shows the button: no other source mentions it
for path in (repo / 'source').rglob('*.cpp'):
    rel = path.relative_to(repo).as_posix()
    if rel != 'source/render/SocialWindow.cpp' and rel != 'source/render/Gui.cpp' and \
            'SkillTreeButton' in path.read_text(encoding='utf-8', errors='replace'):
        errors.append('%s uses SkillTreeButton; only the Dungeonbook profile shows it' % rel)
# View only: the skill buttons of the window have no click handler
if re.search(r'Column\d?.*Tier.*EventClicked|TierFour.*EventClicked', social):
    errors.append('source/render/SocialWindow.cpp: a skill of the tree reacts to a click')

for error in errors:
    print('FAIL: ' + error)
if errors:
    sys.exit(1)
print('OK: %d test cases, %d skill buttons, window wired to the Dungeonbook profile' % (EXPECTED_CASES, EXPECTED_BUTTONS))
