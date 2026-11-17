"""Decisions 902-904: spa route, keeper drop, full seated time and transition wiring.

Source-only contract checks; the production C++ probes remain in check_spa_rules
and check_spa_streams. No compilation, game process or desktop capture.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(name):
    """Read one production source."""
    return (ROOT / name).read_text(encoding='utf-8')


def body(text, signature):
    """Extract a production function while retaining nested branches."""
    begin = text.index(signature)
    opening = text.index('{', begin)
    depth = 0
    for index in range(opening, len(text)):
        depth += (text[index] == '{') - (text[index] == '}')
        if depth == 0:
            return text[begin:index + 1]
    raise AssertionError('unclosed function: ' + signature)


spa = read('source/rooms/RoomSpa.cpp')
creature = read('source/entities/Creature.cpp')
renderer = read('source/render/RenderManager.cpp')
navigation = read('source/gamemap/RoomObjectNavigation.cpp')
arrival = body(spa, 'Tile* RoomSpa::getArrivalTile(')
assert 'isPoolTile(tile)' in arrival and 'creature.canGoThroughTile(tile)' in arrival
assert 'getGameMap()->path(start, tile, &creature, creature.getSeat())' in arrival
assert 'spa->getArrivalTile(creature)' in read('source/creatureaction/CreatureActionSearchSpa.cpp')
walk = body(spa, 'bool RoomSpa::walkBather(')
# Rewritten on fix/ingame-qs-10-b1 (K28): the walk is split into legs on the rim, in the mud and one step over the rim
# (SpaLayout::nextBathLeg, outcome checked by check_spa_behaviour_b1); the leg that reaches the target ends at the endpoint
for contract in ('creature.canGoThroughTile(tile)', 'SpaLayout::rimWalk(passable, pool,',
                 'SpaLayout::nextBathLeg(pool, std::make_pair(here->getX(), here->getY()), steps, leg)',
                 'if(legSteps == steps.size())', 'SPA_STEP_IN_CLIP', 'SPA_STEP_OUT_CLIP',
                 'path, false, true', 'CreatureActionWalkToTile'):
    assert contract in walk, contract
assert 'setPosition' not in walk and 'startJump' not in walk
assert 'setPosition' not in body(spa, 'bool RoomSpa::walkToPlace('), 'entry never teleports'
# Rewritten on fix/ingame-qs-10-b1 (K29, answer to Q7): a drop on the mud or the rim bathes at the place nearest to the
# drop, without the pleasure buff and the lock of the spa, paid as usual
drop = body(spa, 'void RoomSpa::creatureDropped(')
assert 'canAcceptDrop(creature, *tile, block)' in drop
assert 'CreatureActionUseRoom>(creature, *this, true)' in drop and 'wantsSpaBath' not in drop
accept_drop = body(spa, 'bool RoomSpa::canAcceptDrop(')
assert 'SpaLayout::findDropBlock(' in accept_drop and 'canPay(creature)' in accept_drop
assert 'canUsePleasureRoom' not in accept_drop and 'isWorker()' in accept_drop
assert 'mSpaBathing ||' in body(creature, 'bool Creature::needInterrupt(')
assert 'findBatherOf(&creature) != mBathers.end()' in body(spa, 'bool RoomSpa::keepGuestUntilItLeft(')
assert 'SpaBatherState::reserved) && it->mCreature->isKo()' in body(spa, 'void RoomSpa::abortDisturbedBathers(')
for name in ('bool RoomSpa::walkToPlace(', 'bool RoomSpa::landJump('):
    paying = body(spa, name)
    assert paying.index('payForBath') < paying.index('sitDown(bather)'), 'payment precedes settling'
sit = body(spa, 'void RoomSpa::sitDown(')
assert 'Random::Double(3.0, 5.0) * ODApplication::turnsPerSecond' in sit
assert 'addSpaMood' not in sit and 'startBath' not in sit
upkeep = body(spa, 'void RoomSpa::upkeepBathers(')
assert 'case SpaBatherState::sitting:' in upkeep and 'case SpaBatherState::standing:' in upkeep
assert upkeep.index('startBath(bather)') < upkeep.index('case SpaBatherState::bathing:')
assert 'bather.mState = SpaBatherState::standing;' in upkeep
assert 'Random::Double(3.0, 5.0) * ODApplication::turnsPerSecond' in upkeep
assert 'finishBath(bather)' not in upkeep, 'effects wait until the standing and walking exit finish'
use = body(spa, 'bool RoomSpa::useRoom(')
assert 'case SpaBatherState::leaving:' in use and 'walkBather(creature, rim, destination)' in use
assert use.index('walkBather(creature, rim, destination)') < use.index('finishBath(*it)')
pose = body(renderer, 'void prepareSpaAnimation(')
for contract in ('EntityAnimation::bathe_anim', 'EntityAnimation::idle_anim', 'EntityAnimation::walk_anim',
                 'name == "SpaWade"', 'name == "SpaStand"', 'Ogre::Quaternion::Slerp', 'createAnimationState'):
    assert contract in pose, contract
assert '"SpaSit"' in body(renderer, 'void RenderManager::rrSetObjectAnimationState(')
save = body(spa, 'void RoomSpa::exportToStream(')
assert 'bather.mTransitionTurns' in save and 'it->second.mTransitionTurns' in save
assert 'line >> saved.mTransitionTurns' in body(spa, 'bool RoomSpa::importFromStream(')
ordinary = body(navigation, 'bool RoomObjectNavigation::refine(Creature& creature, std::vector<Ogre::Vector2>& path, RouteCache& cache)')
assert 'path.swap(around);' in ordinary and 'return refined;' in ordinary and 'if(!around.empty())' not in ordinary
assert '(step != posTile) && RoomSpa::isPoolTile(step)' in body(creature, 'bool Creature::setDestination(')
print('spa entry 902-904 source contracts ok; C++ and runtime verification pending')
