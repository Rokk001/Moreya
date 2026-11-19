#!/usr/bin/env python3
"""Separation check of the creature pictures (pure source scan, no game and no build needed).

Two rules:

1. The Dungeonbook (gui/WindowSocial.layout, SocialWindow) shows the whole portrait of the appearance.
   Only without one SocialWindow::findPortrait falls back to the round tinted profile portrait; the
   preview portraits of the creature bar are never used in the book.
2. The creature bar (CreaturePanel, hand icons) and the preview portrait code never use the folders
   with whole portraits or neutral bases nor any code of the whole portrait.

Usage: python scripts/check_dungeonbook_separation.py
Exit code 0 if both rules hold, 1 otherwise (every violation is printed).
"""

from pathlib import Path
import re
import sys

REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / 'source'

# Functions that give the preview portraits (creature bar and tinted profile portrait)
PREVIEW_CALLS = ('getCreatureProfilePortraitImage', 'getCreaturePanelPortraitImage', 'getCreatureHandIconImage')
# Code and data of the whole Dungeonbook portrait
APPEARANCE_NAMES = ('getCreatureAppearanceImage', 'getCreatureAppearanceRemarks', 'getClientPortraitCatalog',
                    'CreatureAppearancePicture', 'PortraitCatalog', 'PortraitCatalogRegistry', 'DungeonbookQuirks',
                    'DungeonbookAppearanceConfig', 'CreatureAppearance')
FOLDER_NAMES = ('portraits/whole', 'neutral-bases')

errors = []


def read(path):
    return path.read_text(encoding='utf-8', errors='replace')


def body(text, signature):
    """Text of the function whose first line starts with signature (up to the closing brace at column 0)."""
    start = text.find(signature)
    if start < 0:
        return None
    brace = text.index('\n{\n', start)
    end = text.index('\n}\n', brace)
    return text[brace:end]


def fail(message):
    errors.append(message)


# ---------------------------------------------------------------- rule 1: the Dungeonbook
# The book asks for the whole portrait of the appearance first (SocialWindow::findPortrait); only without one it falls
# back to the round tinted profile portrait. The shared profile page that did the same in Creature::fillProfilePage was
# deleted (owner decision 2026-11-18).
creature = read(SOURCE / 'entities/Creature.cpp')
if 'Creature::fillProfilePage' in creature:
    fail('Creature::fillProfilePage is back; the shared profile page was deleted')
social = read(SOURCE / 'render/SocialWindow.cpp')
portrait = body(social, 'const CEGUI::Image* SocialWindow::findPortrait(')
if portrait is None:
    fail('SocialWindow::findPortrait not found')
else:
    whole = portrait.find('getCircularCreatureAppearanceImage(creatureName, appearance)')
    square = portrait.find('getCreatureAppearanceImage(creatureName, appearance)')
    returned = portrait.find('if(image != nullptr)\n        return image;')
    fallback = portrait.find('getCircularCreatureProfilePortraitImage(')
    if whole < 0 or square < 0:
        fail('findPortrait does not ask for the whole portrait')
    elif returned < 0 or not (max(whole, square) < returned < fallback):
        fail('findPortrait uses the tinted profile portrait before the whole portrait')

# The other Dungeonbook code never reaches for the preview portraits
for name in ('render/SocialWindow.cpp', 'render/SocialWindow.h'):
    text = read(SOURCE / name)
    for call in PREVIEW_CALLS:
        if call in text:
            fail('%s uses the preview portrait function %s' % (name, call))
    if 'materials/textures/portrait-' in text or '"portrait-' in text:
        fail('%s names a preview portrait file' % name)

# The whole portrait code decides nothing about the fallback: it never loads a preview portrait itself
# (the header only documents the fallback in its comments, so only the sources are scanned)
for name in ('render/CreatureAppearancePicture.cpp', 'render/PortraitCatalog.cpp', 'render/DungeonbookQuirks.cpp'):
    text = read(SOURCE / name)
    for call in PREVIEW_CALLS:
        if call in text:
            fail('%s uses the preview portrait function %s' % (name, call))
    if re.search(r'"portrait-|portrait-<|CreaturePortrait\.h', text):
        fail('%s uses preview portrait files or the preview portrait code' % name)

# ---------------------------------------------------------------- rule 2: the creature bar
# Files that belong to the creature bar and the preview portraits: no appearance code, no whole-portrait folders
for name in ('render/CreaturePanel.cpp', 'render/CreaturePanel.h', 'render/CreaturePortrait.cpp',
             'render/CreaturePortrait.h'):
    path = SOURCE / name
    if not path.exists():
        continue
    text = read(path)
    for word in APPEARANCE_NAMES + FOLDER_NAMES:
        if word in text:
            fail('%s (creature bar / preview portraits) mentions %s' % (name, word))

# GameMode builds the creature bar hand icons and only clears the whole portraits when a map is unloaded
game = read(SOURCE / 'modes/GameMode.cpp')
for word in ('getCreatureAppearanceImage', 'getCreatureAppearanceRemarks', 'getClientPortraitCatalog',
             'PortraitCatalog', 'PortraitCatalogRegistry', 'DungeonbookQuirks') + FOLDER_NAMES:
    if word in game:
        fail('modes/GameMode.cpp mentions %s' % word)
icon_start = game.find('getCreatureHandIconImage(')
if icon_start < 0:
    fail('hand icon code not found in GameMode.cpp')

# Nowhere in the game code (tests excluded) is a whole-portrait or base folder named, except where the pictures are loaded
allowed_folder_users = {
    'entities/Creature.cpp',  # default asset root of the server registry
    'render/CreatureAppearancePicture.cpp',  # default asset root of the client registry
    'render/DungeonbookAppearanceConfig.h',  # documentation of the default
}
for path in sorted(SOURCE.rglob('*')):
    if path.suffix not in ('.cpp', '.h') or 'tests' in path.relative_to(SOURCE).parts:
        continue
    relative = path.relative_to(SOURCE).as_posix()
    text = read(path)
    if re.search(r'neutral-bases|portraits/whole', text) and relative not in allowed_folder_users:
        fail('%s names the whole-portrait or base folders, only the Dungeonbook picture code may' % relative)

if errors:
    for message in errors:
        print('FAIL: ' + message)
    sys.exit(1)

print('dungeonbook separation ok')
