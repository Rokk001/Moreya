"""Check direct library research and legacy book conversion wiring."""
from pathlib import Path
import sys

repo = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo / "scripts"))
import content_packages  # noqa: E402
library = (repo / "source/rooms/RoomLibrary.cpp").read_text(encoding="utf-8")
temple = (repo / "source/rooms/RoomDungeonTemple.cpp").read_text(encoding="utf-8")
loader = (repo / "source/gamemap/MapHandler.cpp").read_text(encoding="utf-8")
# config/rooms.cfg is a mixed table: complete only with the own rows of the content, None without the content
config = content_packages.read_text(repo, "config/rooms.cfg") if content_packages.has_content(repo) else None

use = library[library.index("bool RoomLibrary::useRoom("):library.index("void RoomLibrary::exportToStream(")]
assert "new SkillEntity" not in use
assert "getSeat()->addSkillPoints(wholePoints)" in use
assert "mSkillPoints -= wholePoints" in use
assert 'std::setprecision(17) << mSkillPoints' in library and 'is >> mSkillPoints' in library
assert "LibrarySkillPointsBook" not in library
if config is not None:
    assert "LibrarySkillPointsBook" not in config
else:
    content_packages.unchecked("check_library_direct_research", ["LibrarySkillPointsBook in config/rooms.cfg"])
assert "checkIfAvailableSpot" not in library
assert "case GameEntityType::skillEntity:" not in temple
assert 'readGameEntity(gameMap, "SkillEntity", GameEntityType::skillEntity' in loader
assert 'legacyBook->getSeat()->addSkillPoints(legacyBook->getSkillPoints())' in loader
assert 'delete legacyBook' in loader
loaded = library[library.index("bool RoomLibrary::importFromStream("):]
assert "getSeat()->addSkillPoints(wholePoints)" in loaded
assert "mSkillPoints -= wholePoints" in loaded
print("CHECKS OK")
