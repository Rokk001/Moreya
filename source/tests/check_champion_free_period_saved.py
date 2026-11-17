"""The champion's free period goes on after loading a save instead of starting again.

The turns since the champion was summoned (Creature::mChampionTurns, read by Creature::handleChampionUpkeep to decide
whether the free seconds are used up) are written as the optional block "[Champion] <turns> [/Champion]" of the creature
line and read back by Creature::importFromStream. Old saves have no block and load as before.

Plain source check, no compiler, no game. Expected: exactly 1 writer and 1 reader of the block, the writer only for a
counter above 0, the reader assigning mChampionTurns and refusing a block without its closing token.

Calls (from the repository root):
  python source/tests/check_champion_free_period_saved.py
"""
from pathlib import Path
import re
import sys

root = Path(__file__).resolve().parents[2]

# One writer and one reader of the block
EXPECTED_WRITERS = 1
EXPECTED_READERS = 1

errors = []


def function(text, signature):
    """Returns the body of the function whose definition starts with signature (up to the next closing brace at
    column 0)."""
    start = text.index(signature)
    end = text.index('\n}\n', start)
    return text[start:end]


creature = (root / 'source/entities/Creature.cpp').read_text(encoding='utf-8')
export = function(creature, 'void Creature::exportToStream(std::ostream& os) const')
importer = function(creature, 'bool Creature::importFromStream(std::istream& is)')

writers = re.findall(r'os << "\\t\[Champion\] " << mChampionTurns << " \[/Champion\]";', export)
if len(writers) != EXPECTED_WRITERS:
    errors.append('exportToStream: expected %d writer of the [Champion] block, found %d' % (EXPECTED_WRITERS, len(writers)))
if 'if(mChampionTurns > 0)\n        os << "\\t[Champion] "' not in export:
    errors.append('exportToStream: the [Champion] block must only be written for a counter above 0')

readers = re.findall(r'if\(appearanceToken == "\[Champion\]"\)', importer)
if len(readers) != EXPECTED_READERS:
    errors.append('importFromStream: expected %d reader of the [Champion] block, found %d' % (EXPECTED_READERS, len(readers)))
if 'if(!(is >> mChampionTurns >> championClose) || (championClose != "[/Champion]"))\n                return false;' \
        not in importer:
    errors.append('importFromStream: the [Champion] block must set mChampionTurns and refuse a missing closing token')

# The upkeep still decides the free period from the counter, so a loaded counter continues it
upkeep = function(creature, 'bool Creature::handleChampionUpkeep()')
if '++mChampionTurns;' not in upkeep or 'static_cast<double>(mChampionTurns) <= (freeSeconds * ODApplication::turnsPerSecond)' \
        not in upkeep:
    errors.append('handleChampionUpkeep: the free period no longer follows mChampionTurns')

for error in errors:
    print('FAIL: ' + error)
if errors:
    sys.exit(1)
print('OK: the champion free period counter is saved and loaded with the creature')
