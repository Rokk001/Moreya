"""Check that the minimap draws earth ground in brown, not in a stony beige. No compile, no game."""
from pathlib import Path
import re

root = Path(__file__).resolve().parents[2]
# The terrain colours are shared by the minimaps and the skirmish map preview: constants in MiniMapColours.h,
# the colour of each tile look in MiniMapColours.cpp; MiniMap.cpp draws with them
minimap = (root / 'source/gamemap/MiniMap.cpp').read_text(encoding='utf-8')
source = ((root / 'source/gamemap/MiniMapColours.h').read_text(encoding='utf-8') +
          (root / 'source/gamemap/MiniMapColours.cpp').read_text(encoding='utf-8'))


def colour(name):
    match = re.search(name + r'\(([\d.]+)f, ([\d.]+)f, ([\d.]+)f\)', source)
    assert match, name
    return tuple(float(v) for v in match.groups())


earth = colour('EARTH_GROUND_COLOUR')
dirt = colour('DIRT_COLOUR')
# Brown: red above green above blue, clearly saturated, and dark.
for c in (earth, dirt):
    assert c[0] > c[1] > c[2] and c[0] - c[2] >= 0.3 and c[0] <= 0.6, c
assert earth != dirt
ground = source[source.index('case TileVisual::dirtGround:'):source.index('case TileVisual::dirtFull:')]
for visual in ('dirtGround', 'goldGround', 'gemGround', 'rockGround'):
    assert 'case TileVisual::' + visual + ':' in ground
assert 'result.colour = EARTH_GROUND_COLOUR;' in ground
assert '0.82f, 0.70f, 0.50f' not in source and '0.82f, 0.70f, 0.50f' not in minimap
# The minimap takes the colour of a seen tile from the shared terrain colours
tile_colour = minimap[minimap.index('MiniMap::TileColour MiniMap::colourFromTile('):]
tile_colour = tile_colour[:tile_colour.index('\n}\n')]
assert 'result = MiniMapColours::terrainColour(visual,' in tile_colour
print('minimap earth colour passes the checks')
