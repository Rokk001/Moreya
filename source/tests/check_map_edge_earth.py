"""Source check: earth tiles at the map edge must link to the earth border, so the edge shows no step. No compile."""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import content_packages  # noqa: E402

game_map = (ROOT / "source/gamemap/GameMap.cpp").read_text(encoding="utf-8")
render = (ROOT / "source/render/RenderManager.cpp").read_text(encoding="utf-8")
# config/tilesets.cfg is a mixed table: complete only with the own rows of the content, None without the content
tilesets = content_packages.read_text(ROOT, "config/tilesets.cfg") if content_packages.has_content(ROOT) else None

# The border around the map is built from the fully linked (1111) dirtFull meshes.
assert "getTileValues(TileVisual::dirtFull).at(15)" in game_map
assert "createWorldBorder(gameMap);" in render

# Cause: a missing neighbour used to be skipped, so edge earth tiles got the unlinked edge shape.
start = game_map.index("int GameMap::computeTileSetIndex(")
body = game_map[start:game_map.index("\n}\n", start)]
assert "linksToBorder" in body
assert re.search(r"visual\s*==\s*TileVisual::dirtFull", body)
m = re.search(r"if\(t == nullptr\)\s*\{\s*if\(linksToBorder\)\s*index \|= \(1 << i\);\s*continue;\s*\}", body)
assert m, "outside-map neighbour must set the link bit for earth"

# The earth tileset must have a flat 1111 shape that matches what edge tiles now use.
if tilesets is not None:
    assert re.search(r"\[dirtFull\].*?1111\s*\[oneOf\].*?Dirt_fl_1111", tilesets, re.S)
else:
    content_packages.unchecked("check_map_edge_earth", ["1111 earth shape of config/tilesets.cfg"])
print("OK")
