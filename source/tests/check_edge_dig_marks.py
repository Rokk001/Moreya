"""Check dig marking beyond the map edge (INGAME-QS-12 K2, T-D1). Text check, no game start, no compiler.

A place beyond the map edge has no Tile. It behaves like an undiscovered tile: it can be marked and unmarked by click
and drag, the drag rectangle, its size label and the marking extend over it, no refusal text or prohibition sign
appears, the marks are saved and loaded, they give no worker any dig work and they are never discovered.
"""
from pathlib import Path
import re
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from language_texts import english  # noqa: E402

repo = Path(__file__).resolve().parents[2]


# Read a source file without starting the game or a compiler.
def read(path):
    return (repo / path).read_text(encoding='utf-8')


# Return the text of one function or method, from its signature line to the next line that is a closing brace at column 0.
def body(text, signature):
    start = text.index(signature)
    end = text.index('\n}\n', start)
    return text[start:end]


places = read('source/utils/EdgePlaces.h')
game_mode = read('source/modes/GameMode.cpp')
game_mode_h = read('source/modes/GameMode.h')
seat = read('source/game/Seat.cpp')
seat_h = read('source/game/Seat.h')
player = read('source/game/Player.cpp')
server = read('source/network/ODServer.cpp')
client = read('source/network/ODClient.cpp')
render = read('source/render/RenderManager.cpp')
game_map = read('source/gamemap/GameMap.cpp')

# The reach and the rectangle logic are in one header, covered by the 00-EdgePlaces unit test.
assert 'static const int EDGE_PLACE_REACH = 96;' in places
# The reach lies beyond all ground the game camera can show (farthest about 88 places on a 32:9 screen), so a drag never
# shows where marking stops. These are the camera limits that bound the visible ground; if one changes, the reach must be
# checked again.
assert 'const Ogre::Real MAX_CAMERA_Z = 16.0;' in read('source/camera/CameraManager.h')
camera = read('source/camera/CameraManager.cpp')
assert 'const Ogre::Real MAX_CAMERA_PITCH = 50.0f;' in camera
assert camera.count('setFOVy(') == 2, 'only the main menu changes the field of view, and restores it'
assert 'add_boost_test(00-EdgePlaces' in read('source/tests/CMakeLists.txt')
assert (repo / 'source/tests/test_EdgePlaces.cpp').exists()

# Pointer: a place beyond the edge is found while digging marks apply (no action selected, empty hand), also during a
# drag; all four places that compute the pointer tile use it, so click, drag, release and hover agree.
assert 'bool GameMode::findDigEdgePlaceFromMouse(' in game_mode
finder = body(game_mode, 'bool GameMode::findDigEdgePlaceFromMouse(')
assert 'SelectedAction::none' in finder and 'SelectedAction::selectTile' in finder and 'numObjectsInHand() > 0' in finder
assert 'EdgePlaces::clampToReach' in finder
# No ground point beyond the edge is refused: the reach does not reject, it only moves a far place to the outer ring, and a
# drag above the horizon still resolves (the visible ground is not bounded by the camera limits: the view direction may
# be as flat as MAX_VIEW_DIRECTION_Z = -0.1, so a fixed reach cannot be proved to cover it).
assert 'isMarkable' not in finder, 'the finder must not refuse places beyond the reach'
assert 'EdgePlaces::clampToReach(x, y, sizeX, sizeY);' in finder
assert 'EDGE_PLACE_FAR_DISTANCE' in finder and 'if(!dragging)' in finder
assert game_mode.count('findDigEdgePlaceFromMouse(') == 5, 'moved, pressed, released, frame update and the definition'

# Press: a left press beyond the edge starts a dig selection and decides between marking and unmarking by the mark there.
pressed = body(game_mode, 'bool GameMode::mousePressed(')
assert 'isDigEdgePlace(inputManager.mXPos, inputManager.mYPos)' in pressed
assert 'mDigSetBool = !mGameMap->getLocalPlayer()->getSeat()->isEdgePlaceMarked(' in pressed
# Other actions beyond the edge stay as before: the refusal remains for them (hand drops, building, spells).
assert 'mode.input.outside_map' in pressed and english('mode.input.outside_map') == 'Point at a tile inside the map.'
check_input = body(game_mode, 'void GameMode::checkInputCommand()')
assert '!isDigEdgePlace(inputManager.mXPos, inputManager.mYPos)' in check_input
assert 'mode.input.outside_map' in check_input

# Hover reads like an undiscovered tile; the selection reaches over the edge and reports no refusal for edge places.
none_action = body(game_mode, 'void GameMode::handlePlayerActionNone()')
edge_hover = none_action[none_action.index('tile == nullptr && isDigEdgePlace'):none_action.index('if(tile != nullptr && (!tile->getEverVisible()')]
assert 'mode.game.cursor.unexplored' in edge_hover
assert english('mode.game.cursor.unexplored') == 'Unexplored. Click or drag to mark for digging.'
assert 'ColourValue::Red' not in edge_hover
select = body(game_mode, 'void GameMode::handlePlayerActionSelectTile()')
assert 'EdgePlaces::inRectangle(' in select
assert 'diggableTiles.empty() && edgePlaces.empty()' in select
assert 'mPreviewEdgePlaces = edgePlaces;' in select
assert 'isEdgePlaceMarked(place.first, place.second)' in select, 'unmarking concerns only marked places'
# The request still goes through the unchanged message; the server derives the edge places from the same rectangle.
assert select.index('unselectAllTiles();') < select.index('ClientNotificationType::askMarkTiles')
ask = server[server.index('case ClientNotificationType::askMarkTiles:'):]
ask = ask[:ask.index('case ClientNotificationType::askSlapEntity:')]
assert 'player->markEdgePlacesForDigging(isDigSet, EdgePlaces::inRectangle(x1, y1, x2, y2,' in ask
# The edge places come from the rectangle as sent: clipping it to the map first would drop every one of them.
assert ask.index('player->markEdgePlacesForDigging(') < ask.index('ServerGuards::clipRectangleToMap('), \
    'edge places must be marked before the rectangle is clipped to the map'

# The drag rectangle outline and the size label extend over edge places.
update = body(game_mode, 'void GameMode::updateSelectedTiles()')
assert 'EdgePlaces::inRectangle(' in update and 'outlineEdgePlaces' in update
label = body(game_mode, 'void GameMode::refreshSelectionSizeLabel()')
assert 'mPreviewEdgePlaces' in label and 'isDigEdgePlace(' in label
assert 'const std::vector<std::pair<int, int> >& edgePlaces' in read('source/render/RenderManager.h')
preview = render[render.index('void RenderManager::rrDrawTilePreview('):render.index('float RenderManager::rrGetEdgeMarkHeight')]
assert preview.count('edgePlaces') >= 8 and 'edgeHeight' in preview

# Marks beyond the edge are kept per seat, never touch a Tile (so no worker target, no discovery), are saved with the
# marked tiles and restored on load, and the client is told about them.
assert 'std::set<std::pair<int, int> > mEdgeDigMarks;' in seat_h
set_edge = body(seat, 'bool Seat::setEdgePlaceMarked(')
assert 'EdgePlaces::isMarkable(' in set_edge and 'getTile' not in set_edge
assert 'for(const std::pair<int, int>& place : mEdgeDigMarks)' in seat
export_marks = seat[seat.index('os << "[markedTiles]"'):seat.index('os << "[/markedTiles]"')]
assert 'mEdgeDigMarks' in export_marks
import_marks = seat[seat.index('if(str == "[/markedTiles]")'):seat.index('if(str == "[EverVisitedTiles]")')]
assert 'EdgePlaces::isBeyondEdge(' in import_marks and 'setEdgePlaceMarked(tilecoords.first, tilecoords.second, true)' in import_marks
assert import_marks.index('setEdgePlaceMarked') < import_marks.index('mTilesStateLoaded[tilecoords]')
init = seat[seat.index('void Seat::initSeat()'):]
assert 'notifyEdgePlacesMarked(true, edgeMarks, false)' in init[:init.index('\n}\n')]
player_edge = body(player, 'void Player::markEdgePlacesForDigging(')
assert 'getIsHuman()' in player_edge and 'setEdgePlaceMarked(' in player_edge and 'Tile' not in player_edge
assert 'ServerNotificationType::markEdgePlaces' in player and 'markEdgePlaces,' in read('source/network/ServerNotification.h')
client_case = client[client.index('case ServerNotificationType::markEdgePlaces:'):client.index('case ServerNotificationType::carryEntity:')]
assert 'setEdgePlaceMarked(x, y, digSet)' in client_case and 'rrRefreshEdgeMarks(' in client_case

# Worker targets and the vision rule work on tiles only: nothing in them reads edge marks.
for path in ('source/game/WorkerTargets.cpp', 'source/creatureaction/CreatureActionSearchTileToDig.cpp',
             'source/creatureaction/CreatureActionDigTile.cpp'):
    assert 'EdgeDig' not in read(path) and 'EdgePlace' not in read(path), path
# An undiscovered tile inside the map keeps its rules: marked whatever its type, mark removed on discovery when not
# diggable, marks behind it stay.
assert 'mTilesStates[tile].mMarkedForDigging && !tile->isDiggable(this))' in seat
assert 'unexplored || getSeat()->isTileDiggableForClient(tile)' in player

# Look: one earth block with the dig marking per place, built from the tile set like a marked undiscovered tile.
refresh = body(render, 'void RenderManager::rrRefreshEdgeMarks(')
assert 'colourizeEntity(entity, nullptr, true, false)' in refresh
mesh = body(game_map, 'const TileSetValue& GameMap::getMeshForEdgeMark()')
assert 'TileVisual::dirtFull' in mesh and 'allNeighboursLinked = 15' in mesh
assert 'rrRefreshEdgeMarks(std::set<std::pair<int, int> >(), *this)' in game_map, 'blocks are removed when the map is cleared'

# The refusal text only appears for other actions; none of the new code paths shows it or the prohibition sign.
for name, text in (('finder', finder), ('edge hover', edge_hover), ('select edge', select)):
    assert 'Prohibition' not in text, name
print('check_edge_dig_marks ok')
