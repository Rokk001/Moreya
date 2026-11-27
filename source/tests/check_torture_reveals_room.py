"""Check that a tortured enemy creature that dies gives away one not yet seen room
of its owner instead of a timed disc around the dungeon heart."""
from pathlib import Path
import sys

repo = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo / "scripts"))
import content_packages  # noqa: E402


def read(path):
    """The text of a repository file; a mixed table of config/ comes joined with its own rows of the content."""
    return content_packages.read_text(repo, path)


rooms = read("config/rooms.cfg")
assert "TortureRevealRadius" not in rooms and "TortureRevealTurns" not in rooms
torture = read("source/rooms/RoomTorture.cpp")
assert "TortureRevealRadius" not in torture and "TortureRevealTurns" not in torture
body = torture[torture.index("void RoomTorture::revealEnemyInformation"):]
body = body[:body.index("bool RoomTorture::useRoom")]
assert "room->getSeat() != creature.getSeat()" in body
assert "hasSeenTile(firstTile)" in body
assert "getCoveredTiles()" in body
assert "revealTiles(roomToReveal->getCoveredTiles(), 1)" in body
assert "dungeonTemple" not in body
assert "if(creature->getHP() <= damage)" in torture
if not content_packages.has_content(repo):
    content_packages.unchecked("check_torture_reveals_room", ["own rows of config/rooms.cfg"])
print("CHECKS OK")
