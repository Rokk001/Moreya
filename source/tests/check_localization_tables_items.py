"""Display names of the item tables in German and English (localization plan R7.1, R7.2, R10).

The display texts of config/items.cfg (Display), config/equipments.cfg with its own rows (DisplayName),
config/potions.cfg (Display of the potions and of the herbs) and config/creatureSkills.cfg (Name of the skills, the
tier 4 skills and the templates) are shown from the language packages: the text of the key made from the internal id
of the entry, in lower case:
  item.<id>.<quality>.name      equipment.<name>.name      potion.<id>.name      herb.<id>.name
  skill.<id>.name               skill.t4_<creature>.name   skill.template.<group>.<index>.name
The tables keep the English name as the fallback and the identity of the entry. Checked: every display entry has a
text in lang-en (equal to the English name of the table) and in lang-de (not empty), the language files hold no other
entry of these areas, the number of entries is the fixed number below, and the C++ places show the names through the
language files.

Expected: EXPECTED_ENTRIES entries per language (counted once for this branch from the tables).

Calls (from the repository root):
  python source/tests/check_localization_tables_items.py

The tables and the language packages are found through scripts/content_packages.py; without the content the check
names them as not checked and passes.
"""
from pathlib import Path
import re
import sys

repo = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo / 'scripts'))
import content_packages  # noqa: E402

# Display entries per table, counted once on this branch (items 551, equipment 39, potions 29, herbs 4, skills 111 +
# tier 4 skills 35 + templates 24 + skill paths 37 = 207)
EXPECTED_ENTRIES = {'item': 551, 'equipment': 39, 'potion': 29, 'herb': 4, 'skill': 207}
# The text files of the areas in each language package
FILES = {'item': 'items.txt', 'equipment': 'equipment.txt', 'potion': 'potions.txt', 'herb': 'herbs.txt',
         'skill': 'skills.txt'}
errors = []


def tabs(line):
    """The key and the rest of a table line (key, whitespace, value), or None."""
    parts = line.strip().split(None, 1)
    return (parts[0], parts[1].strip()) if len(parts) == 2 else None


def read_table(name):
    """The lines of a table without comment lines; own rows of a mixed table are joined in."""
    text = content_packages.read_text(repo, name)
    return [line for line in text.splitlines() if line.strip() and not line.lstrip().startswith('#')]


def table_entries():
    """{key: English name} of every display entry of the tables, in the order of the tables."""
    entries = {}

    def add(key, name):
        if key in entries:
            errors.append('two display entries share the key %s' % key)
        entries[key] = name

    # items.cfg: Id of the [Item], Name and Display of each [Quality]
    item = quality = None
    for line in read_table('config/items.cfg'):
        pair = tabs(line)
        if line.strip() == '[Item]':
            item = quality = None
        elif line.strip() == '[Quality]':
            quality = ''
        elif pair and pair[0] == 'Id' and quality is None:
            item = pair[1]
        elif pair and pair[0] == 'Name' and quality is not None:
            quality = pair[1]
        elif pair and pair[0] == 'Display' and quality is not None:
            add('item.%s.%s.name' % (item.lower(), quality.lower()), pair[1])
    # equipments.cfg with its own rows: DisplayName of the [Equipment] named by Name
    equipment = None
    for line in read_table('config/equipments.cfg'):
        pair = tabs(line)
        if pair and pair[0] == 'Name':
            equipment = pair[1]
        elif pair and pair[0] == 'DisplayName':
            add('equipment.%s.name' % equipment.lower(), pair[1])
    # potions.cfg: Display of the [Potion] and [Herb] blocks
    area = identity = None
    for line in read_table('config/potions.cfg'):
        pair = tabs(line)
        if line.strip() == '[Potion]':
            area, identity = 'potion', None
        elif line.strip() == '[Herb]':
            area, identity = 'herb', None
        elif pair and pair[0] == 'Id':
            identity = pair[1]
        elif pair and pair[0] == 'Display' and area:
            add('%s.%s.name' % (area, identity.lower()), pair[1])
    # creatureSkills.cfg: Name of the [Skill] (Id), [TierFour] (Creature) and [Template] (Group, Index) blocks
    block = {}
    section = None
    paths = set()
    for line in read_table('config/creatureSkills.cfg'):
        stripped = line.strip()
        if stripped in ('[Skill]', '[TierFour]', '[Template]'):
            section, block = stripped, {}
        elif stripped.startswith('[/') and section:
            if section == '[Skill]':
                paths.add(block['Path'])
                add('skill.%s.name' % block['Id'].lower(), block['Name'])
            elif section == '[TierFour]':
                add('skill.t4_%s.name' % block['Creature'].lower(), block['Name'])
            else:
                add('skill.template.%s.%s.name' % (block['Group'].lower(), block['Index']), block['Name'])
            section = None
        elif section:
            pair = tabs(line)
            if pair and pair[0] in ('Id', 'Name', 'Creature', 'Group', 'Index', 'Path'):
                block[pair[0]] = pair[1]
    # The path names (column titles of the skills page): English = the Path value
    for path in sorted(paths):
        add('skill.path.%s.name' % path.lower(), path)
    return entries


def language_texts(code):
    """{key: text} of all text files of a language package, and the folder of the package."""
    for root in content_packages.package_roots(repo):
        definition = (Path(root) / 'Package.cfg').read_text(encoding='utf-8', errors='replace')
        if re.search(r'^Language=%s\s*$' % code, definition, re.M):
            texts = {}
            for area_file in FILES.values():
                path = Path(root) / 'texts' / area_file
                if not path.is_file():
                    errors.append('lang-%s: %s is missing' % (code, area_file))
                    continue
                for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
                    if not line.strip() or line.startswith('#'):
                        continue
                    key, _, text = line.partition('=')
                    if key in texts:
                        errors.append('lang-%s %s:%d: key %s twice' % (code, area_file, number, key))
                    texts[key] = text
            return texts
    errors.append('language package %s is missing' % code)
    return {}


def area_of(key):
    return key.split('.', 1)[0]


if not content_packages.has_content(repo):
    content_packages.unchecked('check_localization_tables_items', ['item tables', 'language packages'])
else:
    entries = table_entries()
    counts = {}
    for key in entries:
        counts[area_of(key)] = counts.get(area_of(key), 0) + 1
    if counts != EXPECTED_ENTRIES:
        errors.append('display entries per table %s, expected %s' % (counts, EXPECTED_ENTRIES))
    for code in ('en', 'de'):
        texts = language_texts(code)
        own = {key: text for key, text in texts.items() if area_of(key) in EXPECTED_ENTRIES}
        for key, english in entries.items():
            if key not in own:
                errors.append('lang-%s: no text for %s' % (code, key))
            elif not own[key].strip():
                errors.append('lang-%s: empty text for %s' % (code, key))
            elif code == 'en' and own[key] != english:
                errors.append('lang-en: %s is %r, the table says %r' % (key, own[key], english))
        for key in own:
            if key not in entries:
                errors.append('lang-%s: %s belongs to no entry of the tables' % (code, key))
        for key, text in own.items():
            if '{' in text or '}' in text:
                errors.append('lang-%s: %s holds a placeholder' % (code, key))

# The C++ places that show the names read them from the language files
checks = {
    'source/utils/DisplayText.h': ['std::string key = area + "." + lowerKeyPart(id);', 'return key + ".name";'],
    'source/ODApplication.cpp': ['DisplayText::setLookup(lookupDisplayText);'],
    'source/entities/ItemDefinition.cpp': ['DisplayText::makeKey("item", mId, QUALITY_NAMES.at(',
                                           'DisplayText::translated(getNameKey(quality), getQuality(quality).mDisplay)'],
    'source/entities/ItemInstance.cpp': ['definition->getDisplayText(mQuality)', 'potion->getDisplayText()'],
    'source/entities/PotionDefinition.cpp': ['DisplayText::makeKey("potion", mId)', 'DisplayText::makeKey("herb", mId)'],
    'source/entities/Weapon.cpp': ['DisplayText::makeKey("equipment", mName)',
                                   'DisplayText::translated(getNameKey(), fallback)'],
    'source/creatureskill/CreatureSkillTree.h': ['DisplayText::makeKey("skill", mId)',
                                                 'DisplayText::makeKey("skill", "T4_" + mCreature)',
                                                 'DisplayText::makeKey("skill.template", mGroup, std::to_string(mIndex))'],
    'source/creatureskill/CreatureSkillTreeView.cpp': ['lines.push_back(skill.getDisplayText());',
                                                      'DisplayText::makeKey("skill.path", *it)'],
    'source/entities/Creature.cpp': ['skillName = skill->getDisplayText();', 'skillName = tierFour->getDisplayText();',
                                     'return templ->getDisplayText();'],
    'source/modes/EditorMode.cpp': ['definition->getDisplayText(quality) + " ("'],
    'source/modes/GameModeAlchemy.cpp': ['recipe->getDisplayText()', 'void GameMode::refreshItemNameTexts()',
                                         'setLabWindowData(mLabWindowData);'],
    'source/creatureskill/CreatureSkillTreeView.h': ['std::string mTitle;'],
    'source/render/SocialWindow.cpp': ['escapeMarkup(view.mColumns[column].mTitle)'],
    'source/modes/GameMode.cpp': ['refreshItemNameTexts();'],
    'source/modes/GameModeMerchant.cpp': ['Gui::toCeguiText(entry.second.getDisplayName(mGameMap))'],
}
for name, needles in checks.items():
    text = (repo / name).read_text(encoding='utf-8')
    for needle in needles:
        if needle not in text:
            errors.append('%s: %s missing' % (name, needle))

if errors:
    print('FAIL: localization of the item tables')
    for error in errors:
        print('  ' + error)
    sys.exit(1)
print('OK: item tables localized, %d display entries (%s) in German and English' % (
    sum(EXPECTED_ENTRIES.values()), ', '.join('%s %d' % pair for pair in sorted(EXPECTED_ENTRIES.items()))))
