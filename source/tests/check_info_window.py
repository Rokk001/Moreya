"""Check the fixed size information window (gui/WindowStats.layout) of tiles.

The window may not be resized, uses the small body font with top aligned word wrapped text and is
created from the layout (registered for UI scaling) by Tile. A creature has no window of its own any
more: its information is shown in the Dungeonbook (check_creature_click_dungeonbook.py). The options
menu shows an icon at every entry of its list.
"""
from pathlib import Path
import re

repo = Path(__file__).resolve().parents[2]
layout = (repo / 'gui/WindowStats.layout').read_text()
assert 'name="StatsWindow"' in layout and 'type="OD/FrameWindow"' in layout
assert '<Property name="SizingEnabled" value="False" />' in layout, 'the window must not be resizable'
m = re.search(r'name="Area" value="\{\{0\.5,(-?\d+)\},\{0\.5,(-?\d+)\},\{0\.5,(\d+)\},\{0\.5,(\d+)\}\}"', layout)
assert m, 'a fixed size centred area is expected'
width, height = int(m[3]) - int(m[1]), int(m[4]) - int(m[2])
assert width >= 480 and height >= 440, (width, height)
for prop in ('Font" value="MedievalSharp-8', 'VertFormatting" value="TopAligned', 'HorzFormatting" value="WordWrapLeftAligned',
             'FrameEnabled" value="False'):
    assert prop in layout, prop
assert 'VertScrollbar' not in layout, 'no scrolling wanted'
for name in ('Creature', 'Tile'):
    text = (repo / 'source/entities' / (name + '.cpp')).read_text()
    # Only the tile opens an information window; the creature opens none (its information is in the Dungeonbook)
    assert ('createInfoWindow(' in text) == (name == 'Tile'), name
    assert 'createCreatureProfileWindow(' not in text, name + ' still opens the old creature window'
    assert 'CEGUI::UDim(0, 380)' not in text, name + ' still sets an own size'
    assert "MedievalSharp-12" not in text, name + ' still uses the large title font'
options = (repo / 'gui/WindowGameOptions.layout').read_text()
for button in re.findall(r'<Window type="(OD/\w*Button)" name="(\w+)"', options):
    if button[1] != 'BackButton':
        assert button[0] == 'OD/IconButton', button[1] + ' has no icon'
print('ok')
