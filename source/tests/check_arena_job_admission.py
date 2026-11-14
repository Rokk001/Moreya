"""Keep arena job search consistent with fenced-room admission without compiling."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def body(source, signature):
    """Read a production function through its unindented closing brace."""
    return source.split(signature, 1)[1].split('\n}', 1)[0]


def verify(source):
    """Both search paths must test capacity and the creature's actual interior tile."""
    admission = body(source, 'static bool canStartRoomWork(')
    assert 'if(!room.hasOpenCreatureSpot(&creature))\n        return false;' in admission
    assert 'if(room.getType() != RoomType::arena)\n        return true;' in admission
    assert 'static_cast<FencedRoom&>(room).getActualRoomTiles()' in admission
    assert ('return std::find(interior.begin(), interior.end(), creature.getPositionTile()) '
            '!= interior.end();') in admission
    search = body(source, 'bool CreatureActionSearchJob::handleSearchJob(')
    assert search.count('canStartRoomWork(creature, *room)') == 2
    assert 'if(canStartRoomWork(creature, *room))' in search
    assert '|| !canStartRoomWork(creature, *room))\n                continue;' in search
    assert 'room->hasOpenCreatureSpot(&creature)' not in search


source = (ROOT / 'source/creatureaction/CreatureActionSearchJob.cpp').read_text(encoding='utf-8')
verify(source)
for old, new in (
    ('if(room.getType() != RoomType::arena)', 'if(room.getType() == RoomType::arena)'),
    ('!= interior.end();', '== interior.end();'),
    ('if(!room.hasOpenCreatureSpot(&creature))', 'if(false)'),
    ('if(canStartRoomWork(creature, *room))', 'if(room->hasOpenCreatureSpot(&creature))'),
    ('|| !canStartRoomWork(creature, *room))', '|| !room->hasOpenCreatureSpot(&creature))'),
):
    try:
        verify(source.replace(old, new, 1))
    except AssertionError:
        continue
    raise AssertionError('Unsafe arena admission mutation accepted: ' + new)

# Capacity remains usable before a drop: dropping checks the destination interior separately.
arena = (ROOT / 'source/rooms/RoomArena.cpp').read_text(encoding='utf-8')
capacity = body(arena, 'bool RoomArena::hasOpenCreatureSpot(')
assert 'getPositionTile()' not in capacity
fenced = (ROOT / 'source/rooms/FencedRoom.cpp').read_text(encoding='utf-8')
drop = body(fenced, 'void FencedRoom::creatureDropped(')
assert drop.index('std::find(mActualTiles.begin()') < drop.index('make_unique<CreatureActionUseRoom>')
print('Arena job admission: both search paths guarded; five unsafe mutations rejected; drops preserved')
