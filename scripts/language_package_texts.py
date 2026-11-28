"""The texts of the language packages of the content (localization plan R1) for the check scripts.

A language package is a content package whose Package.cfg has a line "Language=<code>"; its texts lie in texts/*.txt as
"<key>=<text>" lines (UTF-8, '#' comments, "\\n" for a line break, "\\\\" for a backslash), the same format
Translation::parseTexts reads. The checks that compared English literals of the code read the text of the key here.

  import language_package_texts
  text = language_package_texts.english(repo)['campaign.code.end']

Without the content packages the dictionaries are empty.
"""
from pathlib import Path

import content_packages


def parse_texts(text):
    """The entries of a text file as a dictionary (an empty line, a '#' line and a line without '=' are skipped)."""
    entries = {}
    if text.startswith('﻿'):
        text = text[1:]
    for line in text.replace('\r', '').split('\n'):
        stripped = line.strip(' \t')
        if not stripped or stripped.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        out = []
        index = 0
        while index < len(value):
            if value[index] == '\\' and index + 1 < len(value) and value[index + 1] in 'n\\':
                out.append('\n' if value[index + 1] == 'n' else '\\')
                index += 2
            else:
                out.append(value[index])
                index += 1
        entries[key.strip(' \t')] = ''.join(out)
    return entries


def definition_value(text, key):
    """The value of the line "<key>=" of a Package.cfg text, or None."""
    for line in text.replace('\r', '').split('\n'):
        if line.startswith(key + '='):
            return line[len(key) + 1:].strip(' \t')
    return None


def language_folders(repo, code):
    """The folders of the content packages that are the language package of the given code."""
    folders = []
    for root in content_packages.package_roots(repo):
        definition = Path(root) / 'Package.cfg'
        if definition.is_file() and definition_value(definition.read_text(encoding='utf-8', errors='replace'), 'Language') == code:
            folders.append(Path(root))
    return folders


def texts(repo, code):
    """Every text of the language with the given code, by key."""
    entries = {}
    for folder in language_folders(repo, code):
        for path in sorted((folder / 'texts').glob('*.txt')):
            entries.update(parse_texts(path.read_text(encoding='utf-8')))
    return entries


def english(repo):
    """Every English text, by key."""
    return texts(repo, 'en')


def german(repo):
    """Every German text, by key."""
    return texts(repo, 'de')
