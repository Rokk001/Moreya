"""Owner decision 901 (1): the merchant walked to a wall, vanished there and showed up elsewhere. No compiler, no game.

Causes found by reading
  rig offset      Merchant.mesh was modelled at the front corner of a sales table, (+0.64, -0.76) from its origin (STAND in
                  the asset notes). The node turns with the figure and the server walks the origin over the tile centres of
                  tables and shelves, so the figure appeared up to 0.76 tiles inside the wall below the shelf. RenderManager
                  then hung the entity on a child node that cancelled the offset. Owner finding of 2026-11-17: the merchant mesh now
                  stands on its own origin (check_merchant_assets.py checks the mesh), so the entity hangs directly on its
                  node and no offset or child node may remain that would push the figure off the node again.
  furniture route the route led over the tile centres of the tables and the wall shelves (solid furniture), his tile was
                  taken as the stop; now he walks over free floor tiles only and stands beside the stop
  teleport        the fallback setPosition went to the central (table) tile; now to a free tile beside the first table

One check per fault; call (from the repository root): python source/tests/check_merchant_stand_901.py
"""
import re, sys, pathlib

root = pathlib.Path(__file__).resolve().parents[2]
fails = []

def text(rel):
    return (root / rel).read_text(encoding="utf-8", errors="replace")

render = text("source/render/RenderManager.cpp")
ent = text("source/entities/MerchantEntity.cpp")
room = text("source/rooms/RoomMerchant.cpp")
room_h = text("source/rooms/RoomMerchant.h")

# rig offset (owner finding of 2026-11-17): the mesh stands on its own origin, so the entity hangs directly on its node, without any offset
create = render.split("void RenderManager::rrCreateRenderedMovableEntity")[1].split("renderedMovableEntity->setParentSceneNode")[0]
if "MERCHANT_RIG_OFFSET" in render or re.search(r'meshName == "Merchant"', create):
    fails.append("rig offset: RenderManager still treats the Merchant figure apart (offset or child node)")
if not re.search(r"ent = mSceneManager->createEntity\(tempString, meshPtr\);\s*(//[^\n]*\n\s*)*node->attachObject\(ent\);", create):
    fails.append("rig offset: the figure entity is not attached directly to its node")
destroy = render.split("void RenderManager::rrDestroyRenderedMovableEntity")[1].split("destroySceneNode(node)")[0]
if "detachFromParent()" not in destroy:
    fails.append("rig offset: the figure entity is not detached when it is destroyed")

# free tiles only
if "isFurnitureTile(next)" not in ent or "isFullTile()" not in ent:
    fails.append("route: the walk may lead over furniture or full tiles")
if "getStandTileBeside" not in room or "isFurnitureTile" not in room_h:
    fails.append("stand tile: RoomMerchant has no free stand tile beside a stop")
stand = room.split("Tile* RoomMerchant::getStandTileBeside")[1].split("\n}\n")[0]
if "isFullTile()" not in stand or "getCoveringRoom() == this" not in stand or "!isFurnitureTile(next)" not in stand:
    fails.append("stand tile: it must be a free floor tile of the room")
if "setPosition(mCentralActiveSpotTiles" in room or "getStandTileBeside(mCentralActiveSpotTiles.front())" not in room:
    fails.append("spawn: the merchant must start beside the first table")

# never vanish: the teleport goes to a stand tile; the walk is checked to be reachable before it starts
if "getStandTileBeside(home->getSalesTables().front())" not in ent:
    fails.append("teleport: the fallback must use a free stand tile")
if "previous.find(next) != previous.end() && next != start" not in ent:
    fails.append("route: the stand tile must be reachable on free tiles")
if "removeFromGameMap" in ent.split("void MerchantEntity::doUpkeep")[1].split("mDealTurns > 0.0")[0] and \
        "RoomMerchant::getForSeat(*getGameMap(), getSeat()) == nullptr" not in ent:
    fails.append("vanish: the figure is removed without the room being gone")

if fails:
    print("FAIL"); [print(" -", f) for f in fails]; sys.exit(1)
print("OK check_merchant_stand_901")
