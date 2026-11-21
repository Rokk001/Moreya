"""Check exact ground and room-ownership source contracts; does not execute C++ or gameplay."""
from pathlib import Path
import re
import sys

root = Path(__file__).resolve().parents[2]
runner = (root / 'source/gamemap/LevelScriptRunner.cpp').read_text(encoding='utf-8')
door = (root / 'source/traps/TrapDoor.h').read_text(encoding='utf-8')
tiles = (root / 'source/gamemap/TileContainer.cpp').read_text(encoding='utf-8')
parser = (root / 'source/gamemap/LevelScript.cpp').read_text(encoding='utf-8')

# Ground proofs reject walls, open water/lava, physical door locks and arena fences without needing an actor.
dry = runner[runner.index('bool isDryGroundPassable('):runner.index('bool areGroundPointsConnected(')]
assert 'tile->getFullness() != 0.0' in dry
assert 'TileType::water' in dry and 'TileType::lava' in dry and '!tile->getHasBridge()' in dry
assert 'trap->isDoor()' in dry and '!static_cast<TrapDoor*>(trap)->isGroundPassageOpen(tile)' in dry
assert 'trap->appearsAsWallForSeat(tile, seat)' in dry
assert 'RoomType::arena' in dry and 'getActualRoomTiles()' in dry
for surface in ('dirt', 'gold', 'rock', 'manaWell'):
    assert 'tile->getType() == TileType::' + surface in dry
assert '!isActivated(tile) || (!mIsLocked && !mIsLockedState)' in door

# The BFS uses only the current map and existing cardinal neighbors, even with no surviving workers.
bfs = runner[runner.index('bool areGroundPointsConnected('):runner.index('bool isConditionMet(')]
assert 'gameMap.getCreatures()' not in bfs and 'isAlive()' not in bfs and 'Creature*' not in bfs
assert 'gameMap.getSeatById(cond.mSeatId)' in bfs
assert 'isDryGroundPassable(seat, start, start)' in bfs and 'isDryGroundPassable(seat, start, end)' in bfs
assert 'tile->getAllNeighbors()' in bfs and 'visited.count(neighbor)' in bfs
assert 'isDryGroundPassable(seat, start, neighbor)' in bfs
assert 'isDiggable' not in bfs and 'throughDiggableTiles' not in bfs
neighbors = tiles[tiles.index('void TileContainer::setTileNeighbors('):]
neighbors = neighbors[:neighbors.index('\n}\n')]
assert 'i < 2' in neighbors and '--tempX;' in neighbors and '--tempY;' in neighbors

# A room footprint needs every original coordinate to be open, completely claimed and consistently room-owned.
mask = runner[runner.index('case LevelScriptConditionType::roomFootprintClaimed:'):runner.index('case LevelScriptConditionType::trapGone:')]
for required in ('tile->getFullness() != 0.0', 'tile->getSeat() != seat',
                 'tile->getClaimedPercentage() < 1.0', '!tile->isClaimedForSeat(seat)',
                 'tile->getCoveringRoom()', '(room != nullptr && room->getSeat() != seat)',
                 '(cond.mType == LevelScriptConditionType::roomFootprintClaimed && room == nullptr)'):
    assert required in mask, required
assert 'std::min(cond.mX1, cond.mX2)' in mask and 'std::min(cond.mY1, cond.mY2)' in mask
assert 'if(type == "groundconnected" || type == "roomclaimed" || type == "groundclaimed")' in parser
assert 'os << "groundconnected\\t"' in parser
assert '? "roomclaimed\\t" : "groundclaimed\\t"' in parser

# Victory packets snapshot goals immediately: every new pure observer and its display dependencies must run first.
# Every campaign level of the wing packages and the dropped maps of levels/campaign/ (scripts/campaign_packages.py)
sys.path.insert(0, str(root / 'scripts'))
import campaign_packages  # noqa: E402
for level in campaign_packages.all_level_files(root):
    blocks = re.findall(r'\[Trigger\].*?\[/Trigger\]', level.read_text(encoding='utf-8'), re.S)
    observers = []
    wins = []
    writers = {}
    for index, block in enumerate(blocks):
        lines = [line.split() for line in block.splitlines() if line.strip()]
        name = next((line[1] for line in lines if line[0] == 'Name'), '')
        actions = [line for line in lines if line[0] == 'Action']
        if any(line[1] == 'win' for line in actions):
            wins.append(index)
        if name.startswith('goal') and actions and all(line[1] in ('objectivestate', 'setflag') for line in actions):
            observers.append((index, name, lines))
            for line in actions:
                if line[1] == 'setflag':
                    writers.setdefault((line[2], line[3]), []).append(index)
    if not wins:
        continue
    for index, name, lines in observers:
        assert index < min(wins), str(level) + ': presentation observer after victory: ' + name
        for line in lines:
            if line[:2] == ['Cond', 'flag'] and len(line) == 4:
                for dependency in writers.get((line[2], line[3]), []):
                    assert dependency < index, str(level) + ': late presentation dependency for ' + name
# The army observer runs before Kingsfall's only victory; the court victories courtTaken and collectWin were removed
# with Prince Aurel's court goal (he leads the raid now) and must stay removed.
# Kingsfall belongs to the wing 5 content package and is checked when it is present.
if campaign_packages.has_content(root):
    kingsfall = campaign_packages.read_level(root, 'Kingsfall')
    army_observer = kingsfall.index('Name\tgoalArmyAtHeart\n')
    assert army_observer < kingsfall.index('Name\tmainVictory\n')
    assert 'Name\tcourtTaken\n' not in kingsfall and 'Name\tcollectWin\n' not in kingsfall
    assert kingsfall.count('Action\twin\t1\n') == 1
print('campaign exact ground/room source contracts: ok; C++ and gameplay not executed')
