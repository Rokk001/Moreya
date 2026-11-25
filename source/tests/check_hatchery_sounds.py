#!/usr/bin/env python3
# Checks the hatchery animal sounds: the files exist, have a CREDITS entry, and the server plays every family.
# The sounds are content (hatchery room package, found through scripts/content_packages.py) and their CREDITS rows stand
# in the CREDITS of the content repository; without the content the sound files are named as not checked.
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / 'scripts'))
import content_packages  # noqa: E402
import room_packages  # noqa: E402

# The public CREDITS plus the CREDITS of the content repository when the packages are present
credits = room_packages.credits_text(root)
room = (root / 'source/rooms/RoomHatchery.cpp').read_text() if (root / 'source/rooms/RoomHatchery.cpp').exists() else ''

families = ('Crow', 'Protest', 'Cluck', 'Peep', 'EggCrack')
#: True when the hatchery sounds are in the public tree or in a content or room package
SOUNDS_PRESENT = bool(content_packages.data_folders(root, 'sounds/Spatial/Rooms/Hatchery'))
if not SOUNDS_PRESENT:
    content_packages.unchecked('check_hatchery_sounds', ['sounds/Spatial/Rooms/Hatchery'])
for family in families if SOUNDS_PRESENT else ():
    # The sounds of the family in the public tree and in every package
    files = content_packages.data_glob(root, 'sounds/Spatial/Rooms/Hatchery/' + family, '*.ogg')
    if not files and not content_packages.has_content(root):
        # Without the content only the families that stayed in the public tree are checked
        content_packages.unchecked('check_hatchery_sounds', ['sounds/Spatial/Rooms/Hatchery/' + family])
        continue
    assert len(files) >= 2, family
    for ogg in files:
        assert ogg.stat().st_size > 1000, ogg
        assert ogg.stat().st_size < 60000, ogg
        assert 'sounds/Spatial/Rooms/Hatchery/%s/%s' % (family, ogg.name) in credits, ogg.name
assert 'tools/hatchery/gen_hatchery_sounds.py' in credits
assert (root / 'tools/hatchery/gen_hatchery_sounds.py').exists()

# The server plays them through the room sound message (family "Rooms/Hatchery/<Family>")
for family in families:
    assert '"Hatchery/%s"' % family in room, family
# the rooster in the keeper's hand protests with a family of his own, not with the hen cackle
assert 'fireRoomSound(tile, "Hatchery/Protest")' in room
# the crow on the roof keeps its sound: it is fired when the rooster starts the crow mood, and only then
begin = room[room.index('void RoomHatchery::beginRoosterMood('):]
begin = begin[:begin.index('\n}\n')]
assert 'if(plan.mMood == RoosterMood::crow)' in begin and 'fireAnimalSound(*rooster, "Hatchery/Crow")' in begin
assert room.count('fireAnimalSound(*rooster, "Hatchery/Crow")') == 1, 'the roof crow is the only mood that crows'
assert 'fireAnimalSound(*winner, "Hatchery/Crow")' in room, 'the winner of a fight crows'
# the rooster no longer calls the hens: the food call sound is gone for good (files, credits, generator, code)
gen = (root / 'tools/hatchery/gen_hatchery_sounds.py').read_text()
# Absent from the public tree and from every package
assert content_packages.data_file(root, 'sounds/Spatial/Rooms/Hatchery/FoodCall') is None, 'FoodCall files are removed'
assert 'FoodCall' not in credits, 'no credits entry for the food call'
assert 'FoodCall' not in gen and 'make_food_call' not in gen, 'the generator no longer makes the food call'
assert 'FoodCall' not in room and 'Hatchery/FoodCall' not in room, 'the rooster does not call the hens'
for source_file in (root / 'source').rglob('*'):
    if source_file.suffix in ('.cpp', '.h') and 'FoodCall' in source_file.read_text(errors='ignore'):
        raise AssertionError('FoodCall still used in ' + str(source_file))
assert 'FoodCall' not in (root / 'config/rooms.cfg').read_text()
print('hatchery sounds ok')
