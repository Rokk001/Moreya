#!/usr/bin/env python3
"""Static check of the texts of the campaign and the levels (localization plan R8); compiles nothing, starts no game.

The player texts of the wing packages (Package.cfg: Title, Briefing, Debriefing, Guild, GuildLeader, GuildFirstLeader,
GuildOrigin, Warden) and of every level file ([Info] Name and Description, the script actions message, mainobjectiveid,
objectiveid, optionalobjectiveid, conditionalobjectiveid, objective and hint) are references "@<key>" to the language
files (texts/campaign.txt and texts/levels-*.txt of the language packages). Checked:
  - no such text is written out in a wing package or level file, and the numbers of references are the fixed numbers
    below (R8.1, R8.2);
  - every referenced key has a text in English and in German, no key of the areas "campaign." and "level." is left
    unused (the texts of the campaign code, "campaign.code.", are not wing package or level texts and are skipped), no text is empty and both languages hold the same line breaks and placeholders per key (R1.1, R1.5);
  - the English texts together are the texts the game showed before they moved into the language files, word for word:
    their sha256 is the fixed value ENGLISH_DIGEST (R1.6);
  - the campaign menu, the level lists and the editor show the texts through LevelText::display, a thin wrapper of
    Translation::resolve (the client resolves the references when it shows them).

Calls (from the repository root):
  python source/tests/check_campaign_texts.py

Without the content packages only the level files of the public tree are checked and the rest is named as not checked.
"""
import hashlib
import re
import sys
from pathlib import Path

repo = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo / 'scripts'))
import campaign_packages  # noqa: E402
import content_packages  # noqa: E402

#: Package.cfg keys that hold player texts
PACKAGE_KEYS = ('Title', 'Briefing', 'Debriefing', 'Guild', 'GuildLeader', 'GuildFirstLeader', 'GuildOrigin', 'Warden')
#: Level script actions that hold a player text (the text is the rest of the line after the fixed fields)
ACTIONS = ('message', 'mainobjectiveid', 'objectiveid', 'optionalobjectiveid', 'conditionalobjectiveid', 'objective',
           'hint')
#: References in the Package.cfg files of the six wings (counted once for this branch: 145 texts of the L0 inventory)
EXPECTED_PACKAGE_REFERENCES = 145
#: References in the level files of the public tree (32 files) and in the level files of the content (44 files), per
#: kind of text: [Info] Name, [Info] Description and the actions (counted once for this branch)
EXPECTED_PUBLIC_REFERENCES = {'Name': 32, 'Description': 32, 'message': 23, 'mainobjectiveid': 23, 'objectiveid': 3,
                              'optionalobjectiveid': 9, 'conditionalobjectiveid': 0, 'objective': 4, 'hint': 0}
EXPECTED_CONTENT_REFERENCES = {'Name': 44, 'Description': 44, 'message': 542, 'mainobjectiveid': 111,
                               'objectiveid': 89, 'optionalobjectiveid': 31, 'conditionalobjectiveid': 1,
                               'objective': 3, 'hint': 6}
#: Different keys of the areas "campaign." and "level." in each language (campaign 145, levels 942)
EXPECTED_KEYS = 1087
#: sha256 of the English texts of these keys, as "<key>=<text>" lines sorted by key, each closed by a line feed
ENGLISH_DIGEST = '9ac256c22118a01dda9510fbf0db65d586cfb4ac7d6e50f0f43b73e192d6d8d8'
#: Prefixes of the keys this check covers
PREFIXES = ('campaign.', 'level.')
#: Prefix of the texts the campaign code shows itself (end message, missing wing, guild details; area of the world
#: texts in world.txt): they share the area "campaign." but are no wing package or level texts, so this check skips them
CODE_PREFIX = 'campaign.code.'

errors = []


def read_text(path):
    """The text of a file without carriage returns."""
    return Path(path).read_text(encoding='utf-8').replace('\r', '')


def parse_texts(path):
    """The entries "<key>=<text>" of a language file; comment lines and empty lines are skipped, a key given twice is
    an error."""
    entries = {}
    for number, line in enumerate(read_text(path).split('\n'), 1):
        if not line.strip() or line.startswith('#'):
            continue
        if '=' not in line:
            errors.append('%s:%d: no "=" in the line' % (path.name, number))
            continue
        key, value = line.split('=', 1)
        if key in entries:
            errors.append('%s:%d: key %s is given twice' % (path.name, number, key))
        entries[key] = value
    return entries


def language_texts(folder, code):
    """The entries of the areas of this check of every texts/*.txt file of the language package <code>."""
    entries = {}
    for path in sorted((Path(folder) / ('lang-' + code) / 'texts').glob('*.txt')):
        for key, value in parse_texts(path).items():
            if key.startswith(PREFIXES) and not key.startswith(CODE_PREFIX):
                if key in entries:
                    errors.append('%s: key %s is also in another file of the language' % (path.name, key))
                entries[key] = value
    return entries


def placeholders(text):
    """The placeholders of a text and its line breaks, which both languages must share."""
    return sorted(set(re.findall(r'\{([^{}]*)\}', text))), text.count('\\n')


def package_references(path):
    """The values of the player text lines of a Package.cfg: [(key, value)]"""
    found = []
    for line in read_text(path).split('\n'):
        match = re.match(r'^(\w+)=(.*)$', line)
        if match and match.group(1) in PACKAGE_KEYS:
            found.append((match.group(1), match.group(2)))
    return found


def level_references(path):
    """The player texts of a level file: [(kind, text)] with the kinds Name, Description and the action types."""
    found = []
    in_info = False
    for line in read_text(path).split('\n'):
        if line == '[Info]':
            in_info = True
        elif line == '[/Info]':
            in_info = False
        elif in_info:
            match = re.match(r'^(Name|Description)\t(.*)$', line)
            if match:
                found.append((match.group(1), match.group(2)))
        else:
            fields = line.split('\t')
            if fields[0] == 'Action' and len(fields) >= 4 and fields[1] in ACTIONS:
                found.append((fields[1], fields[-1]))
    return found


def count_references(files, expected, where, keys):
    """Checks that every player text of the level files is a reference and that the numbers match the fixed numbers."""
    counts = dict.fromkeys(expected, 0)
    for path in files:
        for kind, text in level_references(path):
            counts[kind] += 1
            if text.startswith('@') and len(text) > 1:
                keys.add(text[1:])
            else:
                errors.append('%s: %s text is written out: %s' % (path.name, kind, text[:60]))
    if counts != expected:
        errors.append('%s: expected %s references, found %s' % (where, expected, counts))


def check_code():
    """The menus and lists show the references in the language of the player."""
    menu = (repo / 'source/modes/MenuModeCampaign.cpp').read_text(encoding='utf-8')
    for fragment in ('LevelText::display(level.mTitle)', 'LevelText::display(level.mDebriefing)',
                     'LevelText::display(campaignLevel.mBriefing)', 'LevelText::display(guild.mName)',
                     'LevelText::display(guild.mLeader)', 'LevelText::display(guild.mFirstLeader)',
                     'LevelText::display(guild.mOrigin)', 'LevelText::display(action.mText)'):
        if fragment not in menu:
            errors.append('MenuModeCampaign.cpp must show texts through ' + fragment)
    handler = (repo / 'source/gamemap/MapHandler.cpp').read_text(encoding='utf-8')
    if handler.count('LevelText::display(') != 2:
        errors.append('MapHandler.cpp getMapInfo must show the name and the description through LevelText::display')
    header = (repo / 'source/utils/LevelText.h').read_text(encoding='utf-8')
    if 'return Translation::resolve(text);' not in header:
        errors.append('LevelText::display must show a reference through Translation::resolve')


check_code()
keys = set()
game_levels = sorted((repo / 'levels').glob('*/*.level'))
if len(game_levels) != 32:
    errors.append('expected 32 level files in levels/, found %d' % len(game_levels))
count_references(game_levels, EXPECTED_PUBLIC_REFERENCES, 'levels/', keys)

if not content_packages.has_content(repo):
    content_packages.unchecked('check_campaign_texts', ['wing packages, level files and language files of the content'])
else:
    folder = campaign_packages.content_folder(repo)
    package_files = sorted(Path(folder).glob('wing*/Package.cfg'))
    if len(package_files) != 6:
        errors.append('expected 6 wing packages, found %d' % len(package_files))
    references = 0
    for path in package_files:
        for key, value in package_references(path):
            references += 1
            if value.startswith('@') and len(value) > 1:
                keys.add(value[1:])
            else:
                errors.append('%s: %s is written out: %s' % (path.parent.name, key, value[:60]))
    if references != EXPECTED_PACKAGE_REFERENCES:
        errors.append('expected %d references in the Package.cfg files, found %d'
                      % (EXPECTED_PACKAGE_REFERENCES, references))

    content_levels = sorted(Path(folder).glob('wing*/*.level')) + sorted(Path(folder).glob('core-levels/levels/*/*.level'))
    if len(content_levels) != 44:
        errors.append('expected 44 level files in the content, found %d' % len(content_levels))
    count_references(content_levels, EXPECTED_CONTENT_REFERENCES, 'content', keys)

    english = language_texts(folder, 'en')
    german = language_texts(folder, 'de')
    if len(keys) != EXPECTED_KEYS:
        errors.append('expected %d different references, found %d' % (EXPECTED_KEYS, len(keys)))
    for name, texts in (('English', english), ('German', german)):
        for key in sorted(keys - set(texts)):
            errors.append('%s text missing: %s' % (name, key))
        for key in sorted(set(texts) - keys):
            errors.append('%s text of no wing package or level file: %s' % (name, key))
        for key, text in texts.items():
            if not text.strip():
                errors.append('%s text is empty: %s' % (name, key))
    for key in sorted(set(english) & set(german)):
        if placeholders(english[key]) != placeholders(german[key]):
            errors.append('placeholders or line breaks differ: ' + key)
    digest = hashlib.sha256(''.join('%s=%s\n' % (key, english[key]) for key in sorted(english)).encode('utf-8'))
    if digest.hexdigest() != ENGLISH_DIGEST:
        errors.append('the English texts differ from the texts the game showed before (sha256 %s)' % digest.hexdigest())

for error in errors:
    print('FAIL ' + error)
if errors:
    sys.exit(1)
print('ok: %d references checked' % len(keys))
