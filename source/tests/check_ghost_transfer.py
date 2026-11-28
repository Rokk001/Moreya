"""Trap delivery point and 20 s transfer check (decision 845 item 5). Compiles nothing.

The ghost cauldron has a delivery point for ghost traps, the trap socket over the middle of its mouth
(RoomGhostRoom::getTrapSocketPosition, 1.574 above the floor = the top of the socket glow of models/GhostCauldron.mesh).
A hunter at its cauldron sets the trap into the socket: the ghost is teleported there and flows visibly into the
cauldron for GhostTransferSeconds (20, config/rooms.cfg with its doc line), the same for every hunter; it replaces the
GhostEmptyTurns emptying and its one-second Empty clip. Hunter efficiency no longer shortens it; the room's CatchTime
research (which shortened the emptying) now shortens the transfer of a researched keeper (16 s, 13.3 s). The phase clock mTurns is
saved, so a loaded game resumes the remaining time. The client shows the open, shining trap on the socket and the ghost
rising out of it, spiralling down and sinking into the ectoplasm for the whole 20 s (a model of GhostEntity::updateLook
runs over the full transfer). No other clip or capture duration changes (fixed config values).
Owner decision 865 moves the delivery point: no longer the socket over the middle of the cauldron's top, but a delivery
device on the cauldron's rim directly beside the hunter, within reach of his hand (RoomGhostRoom::getTrapSocketPosition
for the anchor and the standing tile: GhostDeliveryHandReach 0.55 from the middle of his tile towards the cauldron, its
top at GhostDeliveryHeight 1.1). The hunter takes the shut trap in his hand and puts it in with a visible put-in motion
(once, the one-second Empty clip; the client moves the trap from his hand into the device over GhostPutInSeconds while
the device swings out from the rim), the trap stays shut, then the ghost rises out of the device, glides over the rim
and spirals down into the mouth. The transfer keeps 20/16/13.3 s by the CatchTime research only, the put-in included.
These parts fail on base 6c97ae45c (socket over the middle of the mouth at 1.574, the open trap standing in it, the
Empty clip looping for the whole transfer).
Owner decision 894 replaces the dynamic device beside the hunter by the permanent trap seat of the rebuilt cauldron
(models/GhostCauldron.mesh, bone DeliverySocket): RoomGhostRoom::getTrapSocketPosition(anchor) is the middle of the 2x2
block plus the offset (0.5, 0.82, 1.1); the hunter stands on RoomGhostRoom::getTrapStandingTile, the tile on the +Y side
0.68 from the seat, and faces -Y; reserveCauldron sends him to that one tile. No device, hinge or arm is built any more.
The owner decision of 2026-11-28 (the approved closed cauldron): the seat is the cauldron's stone shelf, offset
(-0.4935, 0.5779, 0.4433), the hunter stands on the +Y tile in front of the block's left tile, 0.922 from it. There the
trap opens with the lid clip of the catch (in place of decision 865's shut trap at the cauldron), its content is drawn
into the suction nozzle over the shelf (RoomGhostRoom::getCauldronMouthPosition, offset (-0.4792, 0.5706, 0.7515)), and
the trap shuts again. A later owner decision of the same day replaces the rising ghost: the ghost stays hidden in the
trap and is never shown again; the content goes up out of the open trap as a glowing green stream, like a waterfall
running upwards (GhostTransferPath::stream drawn by Creature::updateGhostSuctionStream): its head rises into the nozzle,
it grows denser, thins out, its tail leaves the trap and rises into the nozzle (the trap is sucked empty), and only then
the flaps shut. The stream ends inside the nozzle, which hides it.
"""
from pathlib import Path
import math
import re
import struct

repo = Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(repo / 'scripts'))
import room_packages  # noqa: E402
import content_packages  # noqa: E402

#: The assets of the ghost room come from its room package (scripts/room_packages.py); without the package only the code
#: side is checked
ROOM_ASSETS = room_packages.has_room(repo, 'GhostRoom')
#: True when the content packages are present: rooms.cfg and skills.cfg are mixed tables whose own rows come from them;
#: without them the parts that need their values are named as not checked
CONTENT = content_packages.has_content(repo)


def room_file(relative):
    """A file of the game data, or of the room package when it moved there."""
    return room_packages.asset(repo, relative) or (repo / relative)


def read(path):
    return (repo / path).read_text(encoding='utf-8')


def body(text, signature):
    start = text.index(signature)
    opening = text.index('{', start)
    depth, end = 1, opening + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


def has(text, rule, *fragments):
    for fragment in fragments:
        assert fragment in text, (rule, fragment)


# 1. The config key with its doc line; the other durations stay as they were (fixed values)
if CONTENT:
    rooms = content_packages.read_text(repo, 'config/rooms.cfg')
    match = re.search(r'^(#[^\n]*\n)+GhostTransferSeconds 20\s*$', rooms, re.M)
    assert match and 'delivery point' in match.group(0) and 'decision 845' in match.group(0), 'GhostTransferSeconds 20 with doc line'
    values = dict(re.findall(r'^(Ghost\w+)\s+([-\d.]+)\s*$', rooms, re.M))
    fixed = {'GhostBoxThrowSeconds': '2', 'GhostBeamSeconds': '16', 'GhostBoxSnapSeconds': '2', 'GhostRiseSeconds': '1.5',
             'GhostDissolveSeconds': '1.5', 'GhostTransferSeconds': '20'}
    for key, value in fixed.items():
        assert values.get(key) == value, (key, values.get(key), value)
    transfer_seconds = float(values['GhostTransferSeconds'])
    lid_open = float(values['GhostLidOpenSeconds'])
    # Decision 894: the put-in under a two-line documentation; the hand reach and height of the old device are gone
    rows = rooms.splitlines()
    # Decision 936 point 3: the put-in lasts two seconds so that the hand placement can be seen
    assert values.get('GhostPutInSeconds') == '2'
    assert 'GhostDeliveryHandReach' not in values and 'GhostDeliveryHeight' not in values, 'the old device keys are gone'
    put_in_row = next(i for i, row in enumerate(rows) if row.split()[:1] == ['GhostPutInSeconds'])
    put_in_doc = ' '.join(rows[put_in_row - 2:put_in_row])
    assert all(row.startswith('#') for row in rows[put_in_row - 2:put_in_row]), 'two documentation lines over GhostPutInSeconds'
    assert all(word in put_in_doc for word in ('put-in', 'sets', 'shut', 'trap seat', 'decision 936')), 'the put-in doc lines describe the motion'
    # Decision 936 point 2: the visible pick-up of the trap from the floor, with its doc lines
    assert values.get('GhostPickUpSeconds') == '2' and values.get('GhostPickUpReach') == '0.3', 'pick-up time and reach'
    pick_row = next(i for i, row in enumerate(rows) if row.split()[:1] == ['GhostPickUpSeconds'])
    pick_doc = ' '.join(rows[pick_row - 2:pick_row])
    assert all(row.startswith('#') for row in rows[pick_row - 2:pick_row]) and 'bends down' in pick_doc and 'decision 936' in pick_doc
    assert rows[pick_row + 1].split()[:1] == ['GhostPickUpReach']
    put_in = float(values['GhostPutInSeconds'])
else:
    content_packages.unchecked('check_ghost_transfer', ['durations, put-in and pick-up of config/rooms.cfg'])

# 2. The server: fixed duration, teleport into the socket, saved clock
action = read('source/creatureaction/CreatureActionHuntGhost.cpp')
header = read('source/creatureaction/CreatureActionHuntGhost.h')
has(body(action, 'double CreatureActionHuntGhost::getTransferTurns() const'), '20 s for every hunter, the research shortens it',
    'return researched("GhostTransferSeconds","CatchTime")*ODApplication::turnsPerSecond;')
assert 'getEfficiency' not in body(action, 'double CreatureActionHuntGhost::getTransferTurns() const')
has(read('source/game/SkillManager.cpp'), 'research base: the transfer and the beam (decisions 855, 857)',
    '{SkillType::roomGhostRoom, "CatchTime", ResearchBaseSource::rooms, "GhostTransferSeconds", "GhostBeamSeconds"}')
# The hunter efficiency shortens only the beam (getBeamSeconds), never the transfer
assert 'getBeamSeconds' not in body(action, 'double CreatureActionHuntGhost::getTransferTurns() const')
if CONTENT:
    assert 'GhostEmptyTurns' not in values, 'replaced by GhostTransferSeconds'
state6 = action[action.index('    if(mState==6)\n'):action.index('    if(mState==7)\n')]
has(state6, 'transfer at the delivery point', 'const Ogre::Vector3 socket=RoomGhostRoom::getTrapSocketPosition(*mEmptyAnchor);',
    'if(poured!=nullptr && poured->getPosition()!=socket) poured->teleport(socket);', 'const double duration=getTransferTurns();',
    'while(!mGhosts.empty() && mTurns>=duration)', 'if(ghost!=nullptr) empty->emptyGhost(mCreature,*ghost);',
    'if(mEmptyAnchor==nullptr) { interrupt();return false; }')
for removed in ('GhostEmptyTurns', 'getEfficiency'):
    assert removed not in state6, ('the old emptying is replaced', removed)
# Decisions 865 and 936: the put-in motion starts once on arrival, facing the seat; the hunter keeps his Idle clip and
# the client lays the generated reach pose over it (no more one-second Empty clip)
has(state6, 'the put-in motion once', 'if(!mPutIn) { mCreature.setAnimationState(EntityAnimation::idle_anim,true,facing(mCreature,socket),false);mPutIn=true; }')
assert state6.index('getTrapSocketPosition') < state6.index('if(!mPutIn)') < state6.index('const double duration=getTransferTurns();')
assert 'empty_anim,true' not in action, 'the Empty clip no longer loops for the whole transfer'
assert action.count('EntityAnimation::empty_anim') == 0, 'decision 936: the put-in is the generated reach pose, no Empty clip'
has(header, 'the put-in flag', 'bool mPutIn = false;')
restore = body(action, 'void CreatureActionHuntGhost::restore()')
has(restore, 'a loaded delivery past its put-in does not repeat it', 'if(mState==6 && isTransferring() &&',
    'mTurns>=ConfigManager::getSingleton().getRoomConfigDouble("GhostPutInSeconds")*ODApplication::turnsPerSecond)',
    'mPutIn=true;', 'mCreature.setAnimationState(EntityAnimation::idle_anim,true,Ogre::Vector3::ZERO,false);')
export = body(action, 'void CreatureActionHuntGhost::exportToStream(')
assert "<< mState << ' ' << (mTarget.empty()?\"none\":mTarget) << ' '" in export and "<< mTurns <<" in export, 'clock saved'
has(body(action, 'bool CreatureActionHuntGhost::isTransferring() const'), 'at the cauldron',
    'mState==6 && !mGhosts.empty() && mDestination!=nullptr', '!mCreature.isMoving() && mCreature.getPositionTile()==mDestination')
has(body(action, 'uint32_t CreatureActionHuntGhost::getBoxVisualState() const'), 'visual state 5', 'if(isTransferring()) return 5u;')
has(body(action, 'std::string CreatureActionHuntGhost::getThrowGhostName() const'), 'transferred ghost',
    'if(isTransferring()) return mGhosts.front();')
has(header, 'declarations', 'uint32_t getBoxVisualState() const;', 'double getTransferTurns() const;', 'bool isTransferring() const;')

# 3. Decision 894: the delivery point is the permanent trap seat of the cauldron, offset (0.5, 0.82, 1.1) from its middle
room = read('source/rooms/RoomGhostRoom.cpp')
socket_body = body(room, 'Ogre::Vector3 RoomGhostRoom::getTrapSocketPosition(const Tile& anchor)')
has(socket_body, 'the exact offset of the seat',
    'return Ogre::Vector3(static_cast<float>(anchor.getX())+0.5f+TRAP_SOCKET_OFFSET_X,',
    'static_cast<float>(anchor.getY())+0.5f+TRAP_SOCKET_OFFSET_Y,TRAP_SOCKET_OFFSET_Z);')
# Since 2026-11-28 the seat is the stone shelf of the approved closed cauldron, under its suction nozzle
has(room, 'the measured offset', 'static const float TRAP_SOCKET_OFFSET_X=-0.4935f;',
    'static const float TRAP_SOCKET_OFFSET_Y=0.5779f;', 'static const float TRAP_SOCKET_OFFSET_Z=0.4433f;')
for old in ('TRAP_SOCKET_HEIGHT', '1.574', 'GhostDeliveryHandReach', 'GhostDeliveryHeight', 'standing.getX()'):
    assert old not in room, ('no socket over the middle of the mouth, no device beside the hunter', old)
standing_body = body(room, 'Tile* RoomGhostRoom::getTrapStandingTile(GameMap& map, const Tile& anchor)')
has(standing_body, 'the +Y side of the block', 'return map.getTile(anchor.getX(),anchor.getY()+2);')
reserve = body(room, 'Tile* RoomGhostRoom::reserveCauldron(Creature& hunter)')
has(reserve, 'the hunter walks to the one place beside the seat', 'Tile* best=getTrapStandingTile(*getGameMap(),*cauldron.anchor);')
assert 'for(int y=-1;y<=2;++y)' not in reserve, 'no choice of any ring tile any more'
has(read('source/rooms/RoomGhostRoom.h'), 'declarations', 'static Ogre::Vector3 getTrapSocketPosition(const Tile& anchor);',
    'static Tile* getTrapStandingTile(GameMap& map, const Tile& anchor);',
    'static Ogre::Vector3 getCauldronMouthPosition(const Ogre::Vector3& cauldron);', 'static float getCauldronRimRadius();')
# Measured once on the export of models/GhostCauldron.mesh (rim and top of the pot, ectoplasm top of the state file)
has(body(room, 'Ogre::Vector3 RoomGhostRoom::getCauldronMouthPosition('), 'suction nozzle on the mesh',
    'static const float NOZZLE_OFFSET_X=-0.4792f,NOZZLE_OFFSET_Y=0.5706f,NOZZLE_HEIGHT=0.7515f;',
    'return Ogre::Vector3(cauldron.x+NOZZLE_OFFSET_X,cauldron.y+NOZZLE_OFFSET_Y,NOZZLE_HEIGHT);')
has(body(room, 'float RoomGhostRoom::getCauldronRimRadius()'), 'rim on the mesh', 'static const float RIM_RADIUS=0.68f;')
seat_offset = (-0.4935, 0.5779, 0.4433)
nozzle_offset = (-0.4792, 0.5706, 0.7515)


# Model of getTrapSocketPosition and getTrapStandingTile for the block with its anchor in (0, 0); the middle of the block is (0.5, 0.5)
def device_for(anchor_x, anchor_y):
    return anchor_x + 0.5 + seat_offset[0], anchor_y + 0.5 + seat_offset[1], seat_offset[2]


stand = (0, 2)
hand_reach = math.hypot(device_for(0, 0)[0] - stand[0], device_for(0, 0)[1] - stand[1])
# The shelf lies 0.42 inside the block's front edge: measured once, 0.922 from the middle of the nearest outside tile
assert abs(hand_reach - 0.9221) < 1e-4, hand_reach
assert abs(device_for(0, 0)[0] - stand[0]) < 0.01 and device_for(0, 0)[1] < stand[1], 'the hunter faces -Y towards the seat'
dx, dy, dz = device_for(0, 0)
assert abs(dz - 0.4433) < 1e-9, 'the seat is the top of the stone shelf'
nx, ny, nz = nozzle_offset
assert math.hypot(nx - seat_offset[0], ny - seat_offset[1]) < 0.02 and nz - dz > 0.25, 'the nozzle hangs over the seat'
assert stand not in [(x, y) for x in range(2) for y in range(2)], 'the standing tile lies outside the block'
has(body(room, 'void RoomGhostRoom::createCauldronObjects()'), 'cauldron centred on its block', 'tile->getX()+0.5f,tile->getY()+0.5f,0.0f,0.0f,false);')
assets = read('source/tests/check_ghost_assets.py')
has(assets, 'the seat marker of the export is checked there', 'zip(offset,(-.4935,.5779,.4433))')
if ROOM_ASSETS:
    mesh = room_file('models/GhostCauldron.mesh').read_bytes()
    assert b'GhostEctoplasm\n' in mesh

# 4. The client: the share is sent, the trap stands open and shines on the socket, the ghost gets the share
creature = read('source/entities/Creature.cpp')
refresh = body(creature, 'void Creature::refreshGhostHuntVisuals()')
has(refresh, 'transferred share sent', 'else if(boxMode==5)', 'const double transfer=hunt->getTransferTurns();',
    'turns=transfer>0.0?std::min(1.0,turns/transfer):1.0;', 'const double transfer=hunt->getTransferTurns();', '(boxMode==1 || boxMode==3 || boxMode==4 || boxMode==5 || boxMode==7) && turns!=mGhostThrowTurns')
visuals = body(creature, 'void Creature::updateGhostHuntVisuals(double seconds)')
has(visuals, 'the shut trap put into the device beside the hunter',
    'const bool lyingBox=mGhostBoxMode==1 || mGhostBoxMode==3 || mGhostBoxMode==4 || mGhostBoxMode==5 || mGhostBoxMode==6 || mGhostBoxMode==7;',
    'updateGhostSuctionStream(*scene,suction,position+Ogre::Vector3(0.0f,0.0f,GHOST_STREAM_INSET*trapTop),',
    'mGhostDeliveryMouth,seconds);', 'mGhostHeldBox->setVisible(mGhostBoxMode==2);')
delivery = visuals[visuals.index('else if(mGhostBoxMode==5)'):visuals.index('else if(mGhostBoxMode==6)')]
ordered_parts = ('const Ogre::Vector3 seat=ghost->getPosition();',
    'const double putIn=config.getRoomConfigDouble("GhostPutInSeconds");',
    'const double transferSeconds=SkillManager::getResearchValue(getSeat(),SkillType::roomGhostRoom,',
    'config.getRoomConfigDouble("GhostTransferSeconds"),"CatchTime");',
    'mGhostDeliveryClock=mGhostThrowTurns*transferSeconds>=putIn?putIn:0.0;',
    'mGhostDeliveryMouth=ghostCauldronMouthNear(*getGameMap(),seat);',
    'else mGhostDeliveryClock+=frame;',
    'const double placed=putIn>0.0?std::max(0.0,std::min(1.0,mGhostDeliveryClock/putIn)):1.0;',
    # Decision 936 point 3: the trap leaves the hand on one eased curve over a point above the seat down onto it
    'const float release=static_cast<float>(ghostEase(0.3,0.62,placed));',
    'const Ogre::Vector3 above=seat+Ogre::Vector3(0.0f,0.0f,0.08f);',
    'position=heldOrigin*((1.0f-release)*(1.0f-release))+above*(2.0f*(1.0f-release)*release)+seat*(release*release);',
    'boxTurn=Ogre::Quaternion::Slerp(release,heldTurn,Ogre::Quaternion::IDENTITY,true);',
    'poseMode=5;poseWeight=ghostPoseWeight(placed,0.35,0.6);',
    # Decision 936 point 4: the flow clock runs every frame, the server share only corrects it gently
    'mGhostFlowClock+=frame;', 'const double error=serverSeconds-mGhostFlowClock;',
    'if(std::fabs(error)>1.5) { mGhostFlowClock=serverSeconds;mGhostFlowCorrection=0.0; }',
    'const double step=std::max(-0.5*frame,std::min(0.5*frame,mGhostFlowCorrection*std::min(1.0,seconds)));',
    'share=(mGhostFlowClock-putIn)/(transferSeconds-putIn);',
    'if(inserted<1.0f) share=0.0;',
    'mGhostTransferShown=std::max(mGhostTransferShown,std::max(0.0,std::min(1.0,share)));',
    # the trap opens on the shelf for each ghost and shuts after it (owner decision of 2026-11-28)
    'mGhostLidShown=inserted>=1.0f?GhostTransferPath::lid(mGhostTransferShown):0.0;', 'lidTarget=mGhostLidShown;',
    'trapLight=inserted>=1.0f?1.0:0.0;', 'if(inserted>=1.0f) suction=mGhostTransferShown;')
position = -1
for part in ordered_parts:
    found = delivery.find(part, position + 1)
    assert found > position, ('put-in, then the flow, the trap stays shut', part)
    position = found
assert 'mGhostTransferShown+=(share-mGhostTransferShown)' not in delivery, 'decision 936: no chase of the 1.4 Hz server share'
for removed in ('Hinge', 'buildGhostDeliveryDevice', 'swing', 'GHOST_DEVICE', 'yaw'):
    assert removed not in delivery, ('no device is built or swung any more', removed)
for removed in ('poured', 'GhostLidOpenSeconds'):
    assert removed not in delivery, ('the trap opens only on the transfer path, not on the catch timing', removed)
for removed in ('destroyGhostDelivery', 'buildGhostDeliveryDevice', 'addGhostDeviceBox', 'mGhostDeliveryHinge', 'mGhostDeliveryNode', 'mGhostDeliveryDevice'):
    assert removed not in creature and removed not in read('source/entities/Creature.h'), ('the dynamic device is removed', removed)
mouth_body = body(creature, 'static Ogre::Vector3 ghostCauldronMouthNear(')
has(mouth_body, 'the ghost flows into the nearest cauldron', 'entity->getMeshName()!="GhostCauldron"',
    'RoomGhostRoom::getCauldronMouthPosition(best->getPosition())')
has(body(creature, 'void Creature::clearGhostHuntVisuals()'), 'reset', 'mGhostStreamClock=0.0;', 'mGhostTransferShown=0.0;',
    'if(mGhostStreamChain!=nullptr) { scene->destroyBillboardChain(mGhostStreamChain);mGhostStreamChain=nullptr; }',
    'if(mGhostStreamMotes!=nullptr) { scene->destroyBillboardSet(mGhostStreamMotes);mGhostStreamMotes=nullptr; }',
    'mGhostDeliveryGhost.clear();mGhostDeliveryClock=0.0;')
ghost = read('source/entities/GhostEntity.cpp')
look = body(ghost, 'void GhostEntity::updateLook()')
ghost_header = read('source/entities/GhostEntity.h')
# The ghost stays hidden in the trap at the cauldron: nothing of the transfer shows the ghost itself any more
has(look, 'the boxed ghost stays hidden', 'node->setVisible(mState != GhostState::boxed);', 'alpha = 0.0f;')
for removed in ('mTransferProgress', 'mTransferTarget', 'GhostTransferPath::at', 'node->setVisible(true);'):
    assert removed not in look and removed not in ghost_header, ('no ghost rises out of the trap any more', removed)
for removed in ('setTransferProgress', 'setTransferTarget'):
    assert removed not in ghost_header and removed not in creature, ('the ghost gets no transfer share any more', removed)
# The stream: one smooth function of the share (the model below mirrors it with the constants of the header)
stream_code = body(ghost, 'GhostTransferPath::Stream GhostTransferPath::stream(')
has(stream_code, 'the stream of the share',
    'const double head = std::max(0.0, std::min(1.0, (t - LID_OPEN) / (STREAM_REACH - LID_OPEN)));',
    'const double tail = std::max(0.0, std::min(1.0, (t - STREAM_EMPTY) / (STREAM_GONE - STREAM_EMPTY)));',
    'stream.head = head * head;', 'stream.tail = tail * tail;',
    'stream.density = ease(LID_OPEN, STREAM_DENSE, t) * (1.0 - ease(STREAM_THIN, STREAM_GONE, t));')
has(body(ghost, 'double GhostTransferPath::lid('), 'the lid of the trap', 'return ease(0.0, LID_OPEN, t) * (1.0 - ease(LID_SHUT, 1.0, t));')
has(body(ghost, 'double GhostTransferPath::ease('), 'smooth step', 'return x * x * (3.0 - 2.0 * x);')
path_constants = {name: float(value) for name, value in
                  re.findall(r'static constexpr double (\w+) = ([\d.]+);', ghost_header)}
# Fixed for the suction stream: the head is in the nozzle after 0.06 of the transfer, densest from 0.35 to 0.7, the trap
# empty from 0.78, the stream gone at 0.9, before the lid shuts from 0.93
assert path_constants == {'LID_OPEN': 0.04, 'LID_SHUT': 0.93, 'STREAM_REACH': 0.1, 'STREAM_DENSE': 0.35,
                          'STREAM_THIN': 0.7, 'STREAM_EMPTY': 0.78, 'STREAM_GONE': 0.9}, path_constants
# The hunter draws the stream: glowing bands and rising motes in the beam's green, from the trap's opening up to
# GHOST_STREAM_DEPTH inside the nozzle, hidden without a suction
stream_draw = body(creature, 'void Creature::updateGhostSuctionStream(')
has(stream_draw, 'the drawn stream',
    'const GhostTransferPath::Stream stream=GhostTransferPath::stream(std::max(0.0,share));',
    'if(share<0.0 || stream.head<=stream.tail || stream.density<=0.0)',
    'if(mGhostStreamNode!=nullptr) mGhostStreamNode->setVisible(false);',
    'mGhostStreamChain->setMaterialName("GhostBeam");', 'mGhostStreamMotes->setMaterialName("GhostBeam");',
    'const Ogre::Vector3 end=mouth+Ogre::Vector3(0.0f,0.0f,GHOST_STREAM_DEPTH);',
    'const double way=stream.tail+(stream.head-stream.tail)*static_cast<double>(i)/static_cast<double>(GHOST_STREAM_SEGMENTS);',
    'if(way<stream.tail || way>stream.head)')
assert 'Random::' not in stream_draw, 'the stream is the same every frame for the same clock'
has(creature, 'the stream constants', 'static const Ogre::Real GHOST_STREAM_INSET=0.8f;',
    'static const Ogre::Real GHOST_STREAM_DEPTH=0.1f;', 'static const Ogre::Real GHOST_STREAM_BASE_WIDTH=0.32f;',
    'static const Ogre::Real GHOST_STREAM_TOP_WIDTH=0.1f;')
has(visuals, 'no stream outside the suction', 'if(suction<0.0 && mGhostStreamNode!=nullptr) mGhostStreamNode->setVisible(false);')


# 5. Model of the timeline: 20 s at 1.4 turns per second; the put-in first, then the trap opens, the ghost is drawn
# straight up out of it into the nozzle, visible until it is in the nozzle, and the trap shuts. The model is the
# smooth path of decision 936 (GhostTransferPath::at and ::lid with the constants of the header).
def ease(a, b, t):
    x = max(0.0, min(1.0, (t - a) / (b - a)))
    return x * x * (3.0 - 2.0 * x)


def stream_at(share):
    """(head, tail, density) of the suction stream at a share."""
    c = path_constants
    t = max(0.0, min(1.0, share))
    head = max(0.0, min(1.0, (t - c['LID_OPEN']) / (c['STREAM_REACH'] - c['LID_OPEN'])))
    tail = max(0.0, min(1.0, (t - c['STREAM_EMPTY']) / (c['STREAM_GONE'] - c['STREAM_EMPTY'])))
    return head * head, tail * tail, ease(c['LID_OPEN'], c['STREAM_DENSE'], t) * (1.0 - ease(c['STREAM_THIN'], c['STREAM_GONE'], t))


def lid_at(share):
    t = max(0.0, min(1.0, share))
    return ease(0.0, path_constants['LID_OPEN'], t) * (1.0 - ease(path_constants['LID_SHUT'], 1.0, t))


turns_per_second = float(re.search(r'double ODApplication::turnsPerSecond = ([\d.]+);', read('source/ODApplication.cpp')).group(1))
if CONTENT:
    duration = transfer_seconds * turns_per_second
    assert abs(duration - 28.0) < 1e-9, duration
for x, y in [(0, 0)]:
    device = device_for(x, y)
    mouth = (x + 0.5 + nozzle_offset[0], y + 0.5 + nozzle_offset[1], nozzle_offset[2])
    # The stream goes straight up from the trap on the shelf into the nozzle over it
    assert math.hypot(mouth[0] - device[0], mouth[1] - device[1]) < 0.02 and mouth[2] > device[2] + 0.25, (device, mouth)
    previous = (0.0, 0.0)
    for step in range(0, 1001):
        share = step / 1000.0
        head, tail, density = stream_at(share)
        if head > tail or density > 0.0:
            assert lid_at(share) > 0.999, ('the stream flows only while the lid is fully open', step)
        assert 0.0 <= tail <= head <= 1.0, ('the tail follows the head', step)
        assert head >= previous[0] and tail >= previous[1], ('the stream only rises', step)
        previous = (head, tail)
        if share <= path_constants['LID_OPEN'] or share >= path_constants['STREAM_GONE']:
            assert head == tail or density == 0.0, ('no stream before the lid is open or after the trap is empty', step)
        if path_constants['STREAM_DENSE'] <= share <= path_constants['STREAM_THIN']:
            assert head == 1.0 and tail == 0.0 and density == 1.0, ('the full stream from the trap into the nozzle', step)
    assert lid_at(0.0) == 0.0 and lid_at(1.0) == 0.0 and lid_at(0.5) == 1.0, 'shut, open for the stream, shut again'
    assert stream_at(0.0) == (0.0, 0.0, 0.0), 'nothing flows before the trap is open'
    assert stream_at(path_constants['STREAM_GONE'])[1] == 1.0, 'the trap is empty, the tail is in the nozzle'
    assert path_constants['STREAM_GONE'] < path_constants['LID_SHUT'], 'the flaps shut only after the trap is empty'
    if CONTENT:
        # Decision 936 point 4, smooth: the flow of 18 s drawn at 60 frames a second has no jump of the head, the tail or
        # the density
        frames = int((transfer_seconds - put_in) * 60)
        points = [stream_at(i / frames) for i in range(frames + 1)]
        for k, limit in ((0, 0.05), (1, 0.05), (2, 0.01)):
            jump = max(abs(points[i + 1][k] - points[i][k]) for i in range(frames))
            assert jump < limit, ('no jump', k, jump)
if CONTENT:
    # The put-in comes first and the whole delivery keeps the transfer time: 20, 16 and 13.3 s by the research
    for seconds in (20.0, 16.0, 20.0 * 0.667):
        for t_step in range(0, int(seconds * 100) + 1):
            t_now = t_step / 100.0
            inserted = max(0.0, min(1.0, t_now / put_in))
            share = 0.0 if inserted < 1.0 else max(0.0, (t_now - put_in) / (seconds - put_in))
            if t_now < put_in:
                assert share == 0.0, ('the ghost waits in the shut trap until it is put in', t_now)
            if t_now < put_in:
                assert inserted < 1.0, ('the trap goes into the seat over the put-in', t_now)
        # At the end of the transfer time (the server's clock) the ghost has fully flowed in, not before the put-in is over
        assert share == 1.0 and t_now == seconds or abs(t_now - seconds) < 0.01 and abs(share - 1.0) < 0.01 / (seconds - put_in), \
            ('the ghost has fully flowed in at the end of the transfer time', seconds, t_now, share)
        assert all(max(0.0, (k / 100.0 - put_in) / (seconds - put_in)) < 1.0 for k in range(0, int(seconds * 100) - 1)), \
            'not fully in before the transfer time is over'

    # 5b. Decision 936 point 4, the root cause of the stutter: the server sends the transfer share only once a turn (1.4
    # times a second). The old client chased it (6/s): the ghost jumped after every turn and nearly stopped before the
    # next. The client flow clock runs every frame, the server share only corrects it within half the speed of time.
    flow = transfer_seconds - put_in
    old_shown, new_clock, correction, seen, frame_seconds = 0.0, 0.0, 0.0, 0.0, 1.0 / 60.0
    old_steps, new_steps = [], []
    for frame_index in range(1, int(flow * 60)):
        now = frame_index * frame_seconds
        server = math.floor(now * turns_per_second) / turns_per_second
        previous_old, previous_new = old_shown, new_clock
        old_shown += (server / flow - old_shown) * min(1.0, frame_seconds * 6.0)
        new_clock += frame_seconds
        if server != seen:
            seen = server
            error = server - new_clock
            correction = 0.0 if abs(error) > 1.5 else error
            new_clock = server if abs(error) > 1.5 else new_clock
        step = max(-0.5 * frame_seconds, min(0.5 * frame_seconds, correction * min(1.0, frame_seconds)))
        new_clock += step
        correction -= step
        if now > 2.0:
            old_steps.append(old_shown - previous_old)
            new_steps.append(new_clock - previous_new)
    assert max(old_steps) > 8 * min(old_steps), 'the old chase jerked (premise of the fix)'
    assert min(new_steps) >= 0.5 * frame_seconds - 1e-12 and max(new_steps) <= 1.5 * frame_seconds + 1e-12, 'never stops, never jumps'
    assert max(abs(new_steps[i + 1] - new_steps[i]) for i in range(len(new_steps) - 1)) < 0.02 * frame_seconds, 'no sudden change'
    assert abs(new_clock - (int(flow * 60) - 1) * frame_seconds) < 1.0, 'stays with the server clock'

    # 6. A loaded game resumes the remaining time: the saved clock k leaves duration - k turns
    for saved in (0.0, 7.0, 27.0):
        turns, left = saved, 0
        while turns < duration:
            turns += 1.0
            left += 1
        assert left == math.ceil(duration - saved), (saved, left)
else:
    content_packages.unchecked('check_ghost_transfer', ['smooth flow, put-in timing, client flow clock and resumed time (values of config/rooms.cfg)'])

# 7. Decisions 855 and 857: only the CatchTime research shortens the transfer (20 s, 16 s, 13.3 s); hunter efficiency
# does not. The transfer clock runs one turn per game turn for every hunter, nothing in its time reads an efficiency.
def code_only(text):
    return re.sub(r'//[^\n]*', '', text)


transfer_body = code_only(body(action, 'double CreatureActionHuntGhost::getTransferTurns() const'))
state6 = code_only(state6)
refresh = code_only(refresh)
for word in ('fficiency', 'getAffinity', 'getLevel', 'Speed'):
    assert word not in transfer_body, ('the transfer time does not depend on the hunter', word)
assert state6.count('mTurns+=') == 1 and 'if(mLastTimedTurn!=map.getTurnNumber()) { mTurns+=1.0;mLastTimedTurn=map.getTurnNumber(); }' in state6, \
    'the transfer clock gains exactly one turn per game turn'
for word in ('fficiency', 'getAffinity', 'Speed', 'getBeamSeconds'):
    assert word not in state6, ('the transfer phase does not read the hunter efficiency', word)
transfer_share = refresh[refresh.index('else if(boxMode==5)'):]
transfer_share = transfer_share[:transfer_share.index('break;')]
assert 'fficiency' not in transfer_share and 'getCaptureTurns' not in transfer_share, \
    'the client share of the transfer does not read the hunter efficiency or the beam time'
# The CatchTime research line is an own row of config/skills.cfg
if CONTENT:
    catch_time = re.search(r'^\s*roomGhostRoom\s+CatchTime\s+mul\s+(\S+)\s+(\S+)\s+(\S+)\s*$', content_packages.read_text(repo, 'config/skills.cfg'), re.M)
    assert catch_time, 'CatchTime research line'
    seconds_by_level = [transfer_seconds * float(f) for f in catch_time.groups()]
    assert [round(s, 1) for s in seconds_by_level] == [20.0, 16.0, 13.3], seconds_by_level
else:
    content_packages.unchecked('check_ghost_transfer', ['CatchTime research line of config/skills.cfg'])
print('ghost transfer: trap seat of the cauldron, hunter walks to its side, put-in, trap opens, green stream into the nozzle until the trap is empty, trap shuts, 20 s, resumed, CatchTime only: ok')
