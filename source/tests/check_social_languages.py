"""Social texts in the language files (localization plan R7.1, R7.2): the texts of config/social-texts.cfg (without the
class names), config/social-names.cfg (epithets, hometowns, age jokes) and config/dungeonbook-quirks.cfg are shown from
the language packages. Checked:
  * the keys of the language files are exactly the keys the game derives from the tables (SocialData::makeTextKey,
    NameGroup::getDisplay*, DungeonbookQuirks::getDisplayText) and the 31 texts of the social code (social.code.*),
    counted per type, in German and in English;
  * the English text of every key is the text of the table (R1.6: no wording changes), the German text exists, is not
    empty, has the same placeholders and no control characters;
  * German has as many different texts as English in every pool of the social texts and names (the generator draws
    another text when two are the same, so a language must not merge two entries); the quirks have a fixed number;
  * the longest German biography fits into the 160 bytes of SocialGenerator::MAX_BIO_LENGTH;
  * both files are valid UTF-8; the tables themselves stay as they are (plain ASCII, checked by check_social_data.py).
Expected values are counted once for this branch (see the constants).

Calls (from the repository root):
  python source/tests/check_social_languages.py

The tables and the language packages are found through scripts/content_packages.py; without the content the check is
named as not checked.
"""
from pathlib import Path
import re
import sys

repo = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo / 'scripts'))
import content_packages  # noqa: E402

# Entries counted once for this branch: the lines of social-texts.cfg per key type (ClassName is not here: it belongs to
# the creature class names), the pool entries of social-names.cfg and the lines of dungeonbook-quirks.cfg
EXPECTED_SOCIAL_TEXTS = {'bio': 28, 'dislike': 50, 'job': 38, 'like': 65, 'mood': 44, 'post': 460, 'quirk': 19,
                         'relation': 14}
EXPECTED_NAME_ENTRIES = {'agejoke': 5, 'hometown': 112, 'title': 136}
EXPECTED_QUIRKS = 4678
# Some tags that differ only in a spelling (gray/grey, blond/blonde) or in a dropped helper word (image)
# give the same German remark. The choice of the remarks uses the texts of the table, so this does not change it.
EXPECTED_DISTINCT_GERMAN_QUIRKS = 4490
# The texts of the social code (CreaturePosts room names and relationship states, fallbacks of SocialGenerator): the
# English text is the text the code showed before the language files
CODE_TEXTS = {
    'social.code.room.temple': 'temple', 'social.code.room.dormitory': 'dormitory',
    'social.code.room.treasury': 'treasury', 'social.code.room.portal': 'portal',
    'social.code.room.workshop': 'workshop', 'social.code.room.traininghall': 'training hall',
    'social.code.room.library': 'library', 'social.code.room.hatchery': 'hatchery', 'social.code.room.crypt': 'crypt',
    'social.code.room.prison': 'prison', 'social.code.room.bridge': 'bridge', 'social.code.room.arena': 'arena',
    'social.code.room.casino': 'casino', 'social.code.room.torture': 'torture chamber',
    'social.code.room.guardroom': 'guard room', 'social.code.room.toilet': 'toilet room',
    'social.code.room.tavern': 'tavern', 'social.code.room.spa': 'lava spa', 'social.code.room.dungeon': 'dungeon',
    'social.code.status.partner': 'In a relationship', 'social.code.status.enemies': 'Sworn enemies',
    'social.code.status.complicated': "It's complicated", 'social.code.status.single': 'Single',
    'social.code.fallback.name': 'Nameless', 'social.code.fallback.relation': 'Single',
    'social.code.fallback.hometown': 'Somewhere', 'social.code.fallback.job': 'Dungeon Resident',
    'social.code.fallback.like': 'quiet days', 'social.code.fallback.dislike': 'loud noises',
    'social.code.fallback.quirk': 'daydreaming', 'social.code.fallback.bio': 'A mysterious minion from {hometown}.',
}
EXPECTED_CODE_TEXTS = 31
EXPECTED_TOTAL = 718 + 253 + 4678 + EXPECTED_CODE_TEXTS
MAX_BIO_LENGTH = 160

failures = []
checks = 0


def check(condition, message):
    global checks
    checks += 1
    if not condition:
        failures.append(message)


def split_fields(line):
    """The tab separated fields of a table line, without the empty ones at the end (SocialData splitAtTabs)."""
    fields = [field.strip() for field in line.split('\t')]
    while fields and not fields[-1]:
        fields.pop()
    return fields


def social_text_entries(text):
    """[(key, text)] of social-texts.cfg by the key rule of SocialData::makeTextKey (ClassName lines have no key)."""
    simple = ('Job', 'Like', 'Dislike', 'Quirk', 'Bio', 'Relation', 'ClassName')
    counters = {}
    entries = []
    for raw in text.split('\n'):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        fields = split_fields(line)
        if fields[0] in simple:
            kind, state, value = fields[0], '', fields[2]
        elif fields[0] in ('MoodLine', 'Post'):
            kind, state, value = fields[0], fields[1], fields[3]
        else:
            check(False, 'social-texts.cfg: unknown line ' + line)
            continue
        counter_key = kind + ':' + state
        counters[counter_key] = counters.get(counter_key, 0) + 1
        if kind == 'ClassName':
            continue
        name = 'mood' if kind == 'MoodLine' else kind.lower()
        key = 'social.' + name + ('.' + state.lower() if state else '') + '.%03d' % counters[counter_key]
        entries.append((key, value))
    return entries


def name_entries(text):
    """[(key, text)] of the epithets, hometowns and age jokes of social-names.cfg by NameGroup::getDisplay*."""
    entries = []
    group = None
    counters = {}
    for raw in text.split('\n'):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if line == '[NameGroup]':
            group = None
            counters = {}
            continue
        if line == '[/NameGroup]':
            continue
        fields = split_fields(line)
        if fields[0] == 'Group':
            group = fields[1]
        elif fields[0] in ('Title', 'Hometown', 'AgeJoke'):
            for value in fields[1:]:
                counters[fields[0]] = counters.get(fields[0], 0) + 1
                entries.append(('social.name.%s.%s.%03d' % (group, fields[0].lower(), counters[fields[0]]), value))
    return entries


def quirk_entries(text):
    """[(key, text)] of dungeonbook-quirks.cfg: the key is "quirk." and the feature tag."""
    entries = []
    for raw in text.split('\n'):
        line = raw.rstrip('\r')
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        fields = [field.strip() for field in line.split('\t')]
        entries.append(('quirk.' + fields[0], fields[1]))
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


def language_texts(code):
    """{key: text} of all text files of the language package, or None when the package is missing."""
    for root in content_packages.package_roots(repo):
        definition = (Path(root) / 'Package.cfg').read_text(encoding='utf-8', errors='replace')
        if definition_value(definition, 'Language') != code:
            continue
        entries = {}
        for path in sorted((Path(root) / 'texts').glob('*.txt')):
            try:
                text = path.read_bytes().decode('utf-8')
            except UnicodeDecodeError as error:
                check(False, '%s/%s: not UTF-8 (%s)' % (code, path.name, error))
                continue
            check(not re.search('[\x00-\x08\x0b\x0c\x0e-\x1f]', text), '%s/%s has control characters' % (code, path.name))
            for line in text.split('\n'):
                line = line.rstrip('\r')
                if not line.strip() or line.strip().startswith('#') or '=' not in line:
                    continue
                key, value = line.split('=', 1)
                entries[key.strip()] = value
        return entries
    return None


if not content_packages.has_content(repo):
    content_packages.unchecked('check_social_languages', ['social, name and quirk texts of the language packages'])
else:
    texts_cfg = content_packages.read_text(repo, 'config/social-texts.cfg')
    names_cfg = content_packages.read_text(repo, 'config/social-names.cfg')
    quirks_cfg = content_packages.read_text(repo, 'config/dungeonbook-quirks.cfg')
    social = social_text_entries(texts_cfg)
    names = name_entries(names_cfg)
    quirks = quirk_entries(quirks_cfg)

    # The counts of the tables
    for kind, expected in EXPECTED_SOCIAL_TEXTS.items():
        count = len([1 for key, _ in social if key.startswith('social.%s.' % kind)])
        check(count == expected, 'social-texts.cfg: %d %s lines, expected %d' % (count, kind, expected))
    for kind, expected in EXPECTED_NAME_ENTRIES.items():
        count = len([1 for key, _ in names if key.split('.')[3] == kind])
        check(count == expected, 'social-names.cfg: %d %s entries, expected %d' % (count, kind, expected))
    check(len(quirks) == EXPECTED_QUIRKS, 'dungeonbook-quirks.cfg: %d lines, expected %d' % (len(quirks), EXPECTED_QUIRKS))
    check(len(CODE_TEXTS) == EXPECTED_CODE_TEXTS, '%d code texts, expected %d' % (len(CODE_TEXTS), EXPECTED_CODE_TEXTS))
    check(len(social) + len(names) + len(quirks) + len(CODE_TEXTS) == EXPECTED_TOTAL, 'the tables hold %d entries, expected %d' %
          (len(social) + len(names) + len(quirks) + len(CODE_TEXTS), EXPECTED_TOTAL))
    table = dict(social + names + quirks + list(CODE_TEXTS.items()))
    check(len(table) == EXPECTED_TOTAL, 'two entries of the tables have the same key')

    languages = {}
    for code in ('en', 'de'):
        entries = language_texts(code)
        check(entries is not None, 'language package %s is missing' % code)
        if entries is None:
            continue
        languages[code] = entries
        mine = dict((key, value) for key, value in entries.items() if key.startswith(('social.', 'quirk.')))
        check(set(mine) == set(table), 'language %s: %d of %d keys differ from the keys of the tables (e.g. %s)' % (
            code, len(set(mine) ^ set(table)), len(table), sorted(set(mine) ^ set(table))[:3]))

    if 'en' in languages and 'de' in languages:
        for key, fixed in sorted(table.items()):
            english = languages['en'].get(key)
            german = languages['de'].get(key)
            if english is None or german is None:
                continue
            check(english == fixed, 'language en: %s is not the text of the table' % key)
            check(german.strip() != '', 'language de: %s is empty' % key)
            check(placeholders(german) == placeholders(english), 'key %s: German and English have different placeholders' % key)
        # A pool keeps as many different texts in German as in English
        pools = {}
        for key in table:
            pool = key.rsplit('.', 1)[0] if key.startswith('social.') else 'quirk'
            pools.setdefault(pool, []).append(key)
        for pool, keys in sorted(pools.items()):
            english_count = len(set(languages['en'].get(key) for key in keys))
            german_count = len(set(languages['de'].get(key) for key in keys))
            if pool == 'quirk':
                check(german_count == EXPECTED_DISTINCT_GERMAN_QUIRKS, 'pool quirk: %d different German texts, expected %d' %
                      (german_count, EXPECTED_DISTINCT_GERMAN_QUIRKS))
                continue
            check(german_count == english_count, 'pool %s: %d different German texts for %d English texts' %
                  (pool, german_count, english_count))
        # The longest German bio, with the longest German text in every slot, fits the limit
        bio_keys = [key for key in table if key.startswith('social.bio.')]

        def longest(prefix):
            values = [languages['de'][key] for key in table if key.startswith(prefix) and key in languages['de']]
            return max(values, key=lambda value: len(value.encode('utf-8'))) if values else ''
        slots = {'quirk': longest('social.quirk.')}
        for key in bio_keys:
            text = languages['de'].get(key, '')
            for slot in placeholders(text):
                slots.setdefault(slot, 'x' * 24)
            filled = re.sub(r'\{([^{}]*)\}', lambda match: slots[match.group(1)], text)
            check(len(filled.encode('utf-8')) <= MAX_BIO_LENGTH, 'German bio %s is longer than %d bytes with the longest quirk' %
                  (key, MAX_BIO_LENGTH))
        print('social texts: %d entries per language checked' % len(table))

for failure in failures:
    print('FAIL: ' + failure)
print('check_social_languages: %d checks, %d failures' % (checks, len(failures)))
sys.exit(1 if failures else 0)
