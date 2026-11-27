"""Creature skill tree (the Skills page of the Dungeonbook): runs source/tests/test_CreatureSkillTreeView.cpp without
Boost.Test and checks the wiring of the page.

The test file is compiled with creatureskill/CreatureSkillTreeView.cpp and CreatureSkillTree.cpp against a tiny
stand-in for the Boost.Test macros it uses and for the configuration and log singletons (like
check_level_script.py and check_creature_skill_trees.py), and run on config/creatureSkills.cfg. The wiring checks
read the layouts and the sources: the Skills page of the book (gui/WindowSocial.layout SkillsPage, INGAME-QS-12 K7;
the separate skill tree window gui/WindowCreatureSkillTree.layout before) holds the tier 4 node and 4 columns of 3
tiers, no separate skill tree window exists or is imported by ModeGame.layout, the fifth button Skills of the
navigation bar shows the page (plan INGAME-QS-11 K4, disabled for a creature without a skill tree; no page holds a
skill tree button), and clicking a skill spends nothing.

Expected: 5 test cases, 0 failures; 13 skill buttons on the Skills page of gui/WindowSocial.layout.

Calls (from the repository root):
  python source/tests/check_creature_skill_tree_view.py

The skill catalog (core-config) and the book layout (core-gui) are found through scripts/content_packages.py;
without the content the test cases (nothing is compiled) and the layout checks are named as not checked and the
source wiring is still checked.
"""
from pathlib import Path
import os
import re
import shutil
import subprocess
import sys
import tempfile

repo = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo / 'scripts'))
import content_packages  # noqa: E402
HAS_CONTENT = content_packages.has_content(repo)

# Test cases of test_CreatureSkillTreeView.cpp and skill buttons of the Skills page (tier 4 and 4 x 3)
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
// The message forms report the given message (used when the config is looked up in the content packages)
#define BOOST_CHECK_MESSAGE(cond, message) SHIM_CHECK((cond), message, false)
#define BOOST_REQUIRE_MESSAGE(cond, message) SHIM_CHECK((cond), message, true)
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
            flags = '/nologo /EHsc /MD /std:c++17 /FI"%s" /Fe"%s" /Fo"%s/" /I"%s" /I"%s"' % (
                tmp / 'config_shim.h', exe, tmp.as_posix(), tmp, repo / 'source')
            # The test file finds the content packages with boost::filesystem: the Boost headers and libraries of the
            # build dependencies (the library is linked automatically by the Boost headers)
            deps = Path(os.environ.get('OD_DEPS_ROOT') or Path.home() / 'build-deps') / 'install'
            boost_include = sorted((deps / 'include').glob('boost-*'))
            assert boost_include, 'no Boost headers in ' + str(deps / 'include')
            flags += ' /I"%s"' % boost_include[-1]
            line = (prefix + 'cl ' + flags + ' ' + ' '.join('"%s"' % s for s in sources)
                    + ' /link /LIBPATH:"%s"' % (deps / 'lib'))
            subprocess.run(line, shell=True, check=True, stdout=subprocess.DEVNULL)
        environment = dict(os.environ)
        environment['OD_TEST_CREATURE_SKILLS_FILE'] = str(content_packages.resolve(repo, 'config/creatureSkills.cfg'))
        # Windows application control may block a freshly built program (WinError 4551); the runner repeats the
        # whole check, including compilation.
        result = subprocess.run([str(exe)], env=environment, capture_output=True, text=True)
        return result.returncode, result.stdout


def read(path):
    """Returns the text of a repository file or of a game data file of the public tree or a content package."""
    return content_packages.read_text(repo, path)


# The test cases run on the skill catalog of the content package core-config; without it nothing is compiled
if not HAS_CONTENT:
    content_packages.unchecked('check_creature_skill_tree_view', ['test cases on config/creatureSkills.cfg'])
else:
    code, output = run_test_cases()
    print(output.strip())
    if code != 0 or ('%d cases, 0 failures' % EXPECTED_CASES) not in output:
        errors.append('test cases: expected %d cases with 0 failures' % EXPECTED_CASES)

# The book layout lies in the content package core-gui
book = read('gui/WindowSocial.layout') if HAS_CONTENT else None
if book is None:
    content_packages.unchecked('check_creature_skill_tree_view', ['gui/WindowSocial.layout Skills page and navigation bar'])
else:
    page = re.search(r'<Window type="DefaultWindow" name="SkillsPage">(.*?)\n        </Window>', book, re.S)
    layout = page.group(1) if page else ''
    if not page:
        errors.append('gui/WindowSocial.layout: the Skills page is missing')
    buttons = re.findall(r'type="OD/ResearchButton" name="([^"]+)"', layout)
    expected = ['TierFour'] + ['Column%dTier%d' % (c, t) for c in range(4) for t in (3, 2, 1)]
    if len(buttons) != EXPECTED_BUTTONS or sorted(buttons) != sorted(expected):
        errors.append('gui/WindowSocial.layout SkillsPage: expected the %d skill buttons %s' % (EXPECTED_BUTTONS, expected))
    for name in expected:
        for suffix in ('Bar', 'Rank'):
            if 'name="%s%s"' % (name, suffix) not in layout:
                errors.append('gui/WindowSocial.layout SkillsPage: %s%s missing' % (name, suffix))
    for column in range(4):
        if 'name="Column%dTitle"' % column not in layout:
            errors.append('gui/WindowSocial.layout SkillsPage: Column%dTitle missing' % column)
# INGAME-QS-12 K7: no separate window opens for the skill tree
if content_packages.data_file(repo, 'gui/WindowCreatureSkillTree.layout') is not None or 'WindowCreatureSkillTree' in read('gui/ModeGame.layout'):
    errors.append('the separate skill tree window still exists; the skill tree is a page of the Dungeonbook')

# Plan INGAME-QS-11 K4: the skill tree opens from the fifth button "Skills" of the navigation bar of the book, no page
# holds a skill tree button any more
for layout_path in content_packages.data_glob(repo, 'gui', '*.layout'):
    if 'SkillTreeButton' in layout_path.read_text(encoding='utf-8', errors='replace'):
        errors.append('gui/%s: a page holds a SkillTreeButton' % layout_path.name)
if book is not None:
    nav = re.search(r'<Window type="DefaultWindow" name="NavBar">(.*?)\n        </Window>', book, re.S)
    nav_buttons = re.findall(r'<Window type="OD/Button" name="(Nav[A-Za-z]+)">', nav.group(1)) if nav else []
    if nav_buttons != ['NavFeed', 'NavProfile', 'NavValues', 'NavInventory', 'NavSkills']:
        errors.append('gui/WindowSocial.layout: the navigation bar must hold Feed, Profile, Values, Inventory, Skills: %s'
                      % nav_buttons)

social = read('source/render/SocialWindow.cpp')
for needle in ('NAV_SKILLS_BUTTON = "NavSkills"', 'NAV_SKILLS_BUTTON), CEGUI::PushButton::EventClicked,',
               '&SocialWindow::onSkillTreeClicked', 'skills->setEnabled(hasSkillTree);', 'buildTreeView(',
               'CEGUI::Window* tree = mWindow->getChild("SkillsPage");', '"InventoryPage", "SkillsPage"};'):
    if needle not in social:
        errors.append('source/render/SocialWindow.cpp: %s missing' % needle)
clicked = social[social.index('bool SocialWindow::onSkillTreeClicked('):]
clicked = clicked[:clicked.index('\n}\n')]
if 'showPage(Page::Skills);' not in clicked or 'show()' in clicked or 'activate()' in clicked:
    errors.append('source/render/SocialWindow.cpp: the Skills button must show the Skills page and open no window')
for gone in ('CreatureSkillTreeWindow', 'onSkillTreeCloseClicked', 'mSkillTreeWindow'):
    if gone in social or gone in read('source/render/SocialWindow.h'):
        errors.append('source/render/SocialWindow: the skill tree window (%s) is gone' % gone)
# The button needs a creature with a skill tree; without one it is shown disabled
has_tree = social[social.index('bool SocialWindow::selectedCreatureHasSkillTree() const'):]
if '!creature->getSkillTypeInfo().mGroup.empty()' not in has_tree[:has_tree.index('\n}\n')]:
    errors.append('source/render/SocialWindow.cpp: the Skills button does not ask for the skill tree of the creature')
# No source uses a skill tree button of a page any more
for path in (repo / 'source').rglob('*.cpp'):
    rel = path.relative_to(repo).as_posix()
    if 'SkillTreeButton' in path.read_text(encoding='utf-8', errors='replace'):
        errors.append('%s uses SkillTreeButton; the skill tree opens from the navigation bar only' % rel)
# View only: the skill buttons of the window have no click handler
if re.search(r'Column\d?.*Tier.*EventClicked|TierFour.*EventClicked', social):
    errors.append('source/render/SocialWindow.cpp: a skill of the tree reacts to a click')

for error in errors:
    print('FAIL: ' + error)
if errors:
    sys.exit(1)
print('OK: %d test cases, %d skill buttons, Skills page wired to the Skills button of the Dungeonbook' % (EXPECTED_CASES, EXPECTED_BUTTONS))
