"""Languages of the game (localization plan R1, R2): runs source/tests/test_Translation.cpp without Boost.Test and
checks the language packages of the content.

The test file is compiled with utils/Translation.cpp against a tiny stand-in for the Boost.Test macros it uses and for
the log singleton (like check_creature_skill_tree_view.py). The language packages are the content packages whose
Package.cfg has a line "Language=<code>"; their texts lie in texts/*.txt as "<key>=<text>" lines (UTF-8). Checked:
German and English are there, every key has a text in both, both texts of a key have the same placeholders, every
file is valid UTF-8 and every line follows the rules of Translation::parseTexts.

Expected: 6 test cases, 0 failures; EXPECTED_ENTRIES entries in each language (counted once for this branch).

Calls (from the repository root):
  python source/tests/check_localization.py

The language packages are found through scripts/content_packages.py; without the content the package checks are
named as not checked and the test cases still run.
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

# Test cases of test_Translation.cpp
EXPECTED_CASES = 6
# Languages of the game at the start (plan D1) and entries of each language, counted once for this branch
EXPECTED_LANGUAGES = {'de': 'Deutsch', 'en': 'English'}
EXPECTED_ENTRIES = 2

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

# Translation.cpp logs through the log singleton; the include guard is taken first and the macros write to stderr.
log_shim = r'''#define LOGMANAGER_H
#include <iostream>
#include <string>
#define OD_LOG_ERR(_message) (std::cerr << (std::string("") + _message) << std::endl)
#define OD_LOG_INF(_message) ((void)0)
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
        (tmp / 'log_shim.h').write_text(log_shim)
        (tmp / 'main.cpp').write_text(main)
        sources = [repo / 'source/utils/Translation.cpp', repo / 'source/tests/test_Translation.cpp', tmp / 'main.cpp']
        exe = tmp / 'translation_check.exe'
        compiler = shutil.which('g++') or shutil.which('clang++')
        if compiler:
            command = [compiler, '-std=c++11', '-include', str(tmp / 'log_shim.h'), '-o', str(exe),
                       '-I' + str(tmp), '-I' + str(repo / 'source')] + [str(s) for s in sources] + [
                       '-lboost_filesystem', '-lboost_system']
            subprocess.run(command, check=True)
        else:
            vcvars = find_vcvars()
            assert shutil.which('cl') is not None or vcvars is not None, 'no C++ compiler found (cl or vcvars64.bat)'
            prefix = '' if shutil.which('cl') else 'call "%s" >nul 2>&1 && ' % vcvars
            flags = '/nologo /EHsc /MD /std:c++17 /FI"%s" /Fe"%s" /Fo"%s/" /I"%s" /I"%s"' % (
                tmp / 'log_shim.h', exe, tmp.as_posix(), tmp, repo / 'source')
            # boost::filesystem of the build dependencies (the library is linked automatically by the Boost headers)
            deps = Path(os.environ.get('OD_DEPS_ROOT') or Path.home() / 'build-deps') / 'install'
            boost_include = sorted((deps / 'include').glob('boost-*'))
            assert boost_include, 'no Boost headers in ' + str(deps / 'include')
            flags += ' /I"%s"' % boost_include[-1]
            line = (prefix + 'cl ' + flags + ' ' + ' '.join('"%s"' % s for s in sources)
                    + ' /link /LIBPATH:"%s"' % (deps / 'lib'))
            subprocess.run(line, shell=True, check=True, stdout=subprocess.DEVNULL)
        # Windows application control may block a freshly built program (WinError 4551); the runner repeats the
        # whole check, including compilation.
        result = subprocess.run([str(exe)], capture_output=True, text=True)
        return result.returncode, result.stdout


def parse_texts(text, name):
    """The entries of a text file by the rules of Translation::parseTexts; bad lines are added to errors."""
    entries = {}
    if text.startswith('\ufeff'):
        text = text[1:]
    for number, line in enumerate(text.split('\n'), 1):
        line = line.rstrip('\r')
        if not line.strip(' \t') or line.strip(' \t').startswith('#'):
            continue
        if '=' not in line:
            errors.append('%s:%d: no "=" in the line' % (name, number))
            continue
        key, value = line.split('=', 1)
        key = key.strip(' \t')
        if not key:
            errors.append('%s:%d: empty key' % (name, number))
        elif key in entries:
            errors.append('%s:%d: key %s is given twice' % (name, number, key))
        else:
            entries[key] = value
    return entries


def placeholders(text):
    """The placeholder names of a text, as Translation::getPlaceholders."""
    return sorted(set(re.findall(r'\{([^{}]*)\}', text)))


def definition_value(text, key):
    """The value of the line "<key>=" of a Package.cfg, or None."""
    for line in text.replace('\r', '').split('\n'):
        if line.startswith(key + '='):
            return line[len(key) + 1:].strip(' \t')
    return None


def language_packages():
    """{code: (name, folder)} of the found language packages."""
    languages = {}
    for root in content_packages.package_roots(repo):
        definition = (Path(root) / 'Package.cfg').read_text(encoding='utf-8', errors='replace')
        code = definition_value(definition, 'Language')
        if code:
            languages[code] = (definition_value(definition, 'LanguageName') or code, Path(root))
    return languages


code, output = run_test_cases()
print(output.strip())
if code != 0 or ('%d cases, 0 failures' % EXPECTED_CASES) not in output:
    errors.append('test cases: expected %d cases with 0 failures' % EXPECTED_CASES)

if not HAS_CONTENT:
    content_packages.unchecked('check_localization', ['language packages of the content'])
else:
    languages = language_packages()
    texts = {}
    for code_, name in EXPECTED_LANGUAGES.items():
        if code_ not in languages:
            errors.append('language package %s is missing' % code_)
            continue
        if languages[code_][0] != name:
            errors.append('language %s: name %r, expected %r' % (code_, languages[code_][0], name))
        entries = {}
        for path in sorted((languages[code_][1] / 'texts').glob('*.txt')):
            try:
                text = path.read_bytes().decode('utf-8')
            except UnicodeDecodeError as error:
                errors.append('%s: not UTF-8 (%s)' % (path.name, error))
                continue
            for key, value in parse_texts(text, '%s/%s' % (code_, path.name)).items():
                if key in entries:
                    errors.append('%s/%s: key %s is also in another file' % (code_, path.name, key))
                entries[key] = value
        texts[code_] = entries
        if len(entries) != EXPECTED_ENTRIES:
            errors.append('language %s: %d entries, expected %d' % (code_, len(entries), EXPECTED_ENTRIES))
    if 'en' in texts and 'de' in texts:
        for key in sorted(set(texts['en']) ^ set(texts['de'])):
            errors.append('key %s is not in both German and English' % key)
        for key in sorted(set(texts['en']) & set(texts['de'])):
            if placeholders(texts['en'][key]) != placeholders(texts['de'][key]):
                errors.append('key %s: German and English have different placeholders' % key)


def read(path):
    """The text of a repository file."""
    return (repo / path).read_text(encoding='utf-8', errors='replace')


# R3.1: the font of the texts above the creatures holds the German letters and the typographic quotes
fontdef = read('gui/fonts/ogrefonts.fontdef')
ranges = [tuple(int(v) for v in r.split('-')) for line in fontdef.splitlines() if line.strip().startswith('code_points')
          for r in line.split()[1:]]
for char in 'äöüÄÖÜß„“':
    if not any(low <= ord(char) <= high for low, high in ranges):
        errors.append('gui/fonts/ogrefonts.fontdef: code point of %r missing' % char)

# R2: the language is loaded and chosen at the start, applies at once and is chosen in the settings
application = read('source/ODApplication.cpp')
for needle in ('Translation::discover();', 'Translation::setLanguage(Translation::chooseLanguage(configManager.getGameValue('
               'Config::LANGUAGE', 'Translation::getSystemLanguage(), Translation::getLanguageCodes()));'):
    if needle not in application:
        errors.append('source/ODApplication.cpp: %s missing' % needle)
gui = read('source/render/Gui.cpp')
register = gui[gui.index('void Gui::registerWindow(CEGUI::Window* window)'):]
if 'translateWindow(window);' not in register[:register.index('\n}\n')]:
    errors.append('source/render/Gui.cpp: registerWindow does not show the texts of the window in the chosen language')
for needle in ('Translation::addListener(languageChanged);', 'Translation::removeListener(mLanguageListener);',
               'const std::string Gui::TEXT_KEY_PREFIX = "@";'):
    if needle not in gui:
        errors.append('source/render/Gui.cpp: %s missing' % needle)
settings = read('source/modes/SettingsWindow.cpp')
for needle in ('GameSP/LanguageCombo"', 'config.setGameValue(Config::LANGUAGE, code);', 'Translation::setLanguage(code);'):
    if needle not in settings:
        errors.append('source/modes/SettingsWindow.cpp: %s missing' % needle)
layout = read('gui/WindowSettings.layout')
for needle in ('name="LanguageCombo"', 'value="@settings.language"', 'value="@settings.language.tooltip"'):
    if needle not in layout:
        errors.append('gui/WindowSettings.layout: %s missing' % needle)

# Every text key of a layout (public tree and content) has an English text
if HAS_CONTENT and 'en' in texts:
    layouts = sorted(set((repo / 'gui').glob('*.layout')) | set(content_packages.data_glob(repo, 'gui', '*.layout')))
    for path in layouts:
        for key in re.findall(r'<Property name="(?:Text|TooltipText)" value="@([^"]+)"',
                              path.read_text(encoding='utf-8', errors='replace')):
            if key not in texts['en']:
                errors.append('%s: text key %s has no English text' % (path.name, key))

for error in errors:
    print('FAIL: ' + error)
if errors:
    sys.exit(1)
print('OK: %d test cases, languages %s with %d entries each' % (
    EXPECTED_CASES, ', '.join(sorted(EXPECTED_LANGUAGES)), EXPECTED_ENTRIES))
