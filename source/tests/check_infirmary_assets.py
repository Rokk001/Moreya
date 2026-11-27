"""Inspect shipped infirmary assets, their registration and licences without compiling.

The room ambience table config/roomAmbience.cfg lives in a content package (found through scripts/content_packages.py);
without the content the check names the chant loop as not checked and checks everything else."""
from pathlib import Path
import importlib.util
import json
import re
import struct
import xml.etree.ElementTree as ET

repo = Path(__file__).resolve().parents[2]
import sys
# ODP_ASSETS_SRC (else <repo>/assets-src) holds the asset sources, see scripts/assets_src.py
sys.path.insert(0, str(repo / 'scripts'))
import room_packages  # noqa: E402
import content_packages  # noqa: E402

#: The assets of the infirmary come from its room package (scripts/room_packages.py); without the package only the code
#: side is checked
ROOM_ASSETS = room_packages.has_room(repo, 'Infirmary')
#: The shaman figure lies in the creatures content package (no longer in the infirmary room package)
SHAMAN_FILES = ("models/InfirmaryShaman.mesh", "models/InfirmaryShaman.skeleton")


def room_file(relative):
    """A file of the game data, or of the room package when it moved there."""
    return room_packages.asset(repo, relative) or (repo / relative)
from assets_src import assets_src_dir, resolve  # noqa: E402


# Read one registered text asset with consistent Unicode handling (an asset source from ODP_ASSETS_SRC, else the game
# data file of the public tree or of a content or room package; a mixed file joined with its own rows from the content).
def read(path):
    if path.startswith("assets-src/"):
        return resolve(repo, path).read_text(encoding="utf-8")
    return content_packages.read_text(repo, path)


# Verify referenced assets exist and have their own source/licence entry.
def credited(path, credits):
    # Without the infirmary package its assets and their rows (in the content repository) are not there
    if not ROOM_ASSETS and (room_packages.is_packaged(path) or path.startswith("assets-src/rooms/infirmary/")):
        return
    # Without the content the shaman figure of the creatures content package and its rows are not there
    if path in SHAMAN_FILES and not content_packages.has_content(repo):
        content_packages.unchecked("check_infirmary_assets", [path])
        return
    asset = resolve(repo, path)
    assert asset.is_file() and asset.stat().st_size > 0, "missing asset: " + path
    rows = [line for line in credits.splitlines() if path in line]
    assert rows and any(room_packages.licence_ok(repo, line, "GPL") or "CC0" in line for line in rows), \
        "missing licence: " + path


#: The stored clip lengths of the creatures package shaman (all 2.0 s on the former model; the game stretches the six
#: pose clips to InfirmaryShamanAnimationSeconds). Idle from the build report; Chant, RattleShake, HerbSniff and PotionTaste
#: are the clips approved on 2026-11-27 (Chant 4.0 s, PotionTaste 4.4 s, the other two 2.0 s).
CLIP_SECONDS = {"Idle": 4.0, "Walk": 1.0416669845581055, "Chant": 4.0, "PotionTaste": 4.400000095367432,
                "TripOverBucket": 2.5, "Dance": 7.75, "RattleShake": 2.0, "HerbSniff": 2.0}


# Parse animation chunks with the maintained Ogre chunk reader and check actual clip lengths.
def clips():
    path = repo / "tools/blender-assets/splice_animation_chunks.py"
    spec = importlib.util.spec_from_file_location("infirmary_skeleton_chunks", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _, chunks = module.chunks(room_file("models/InfirmaryShaman.skeleton").read_bytes())
    animations = {name: data for kind, name, data in chunks if kind == module.ANIMATION}
    expected = {"Idle", "Walk", "Chant", "RattleShake", "HerbSniff", "PotionTaste", "TripOverBucket", "Dance"}
    assert set(animations) == expected, sorted(animations)
    for name, data in animations.items():
        duration = struct.unpack_from("<f", data, data.index(b"\n", 6) + 1)[0]
        assert name in CLIP_SECONDS and abs(duration - CLIP_SECONDS[name]) < 1e-6, (name, duration)


# Run the floor generator's actual seam calculation in memory without rewriting any asset.
def floor_seam():
    path = repo / "tools/room-floors/generate_room_floors.py"
    spec = importlib.util.spec_from_file_location("infirmary_floor_check", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result, strength = module.build("infirmary")
    ratio = module.wrap_check(result)
    assert ratio < 2.0, ("infirmary wrap seam ratio", ratio)
    print("infirmary wrap seam ratio: %.2f" % ratio)


# Validate every asset family and reject an uninstalled logical GUI image.
def main():
    credits = room_packages.credits_text(repo)
    furniture = ("InfirmaryCotSmall", "InfirmaryCotMedium", "InfirmaryCotLarge",
        "MedicineCabinet", "InstrumentTable", "WashBasin", "HerbShelf")
    for name in furniture + ("InfirmaryShaman",):
        credited("models/" + name + ".mesh", credits)
        credited("assets-src/rooms/infirmary/" + name + ".blend", credits)
    credited("models/InfirmaryShaman.skeleton", credits)
    credited("materials/scripts/InfirmaryObjects.material", credits)
    if ROOM_ASSETS:
        objects = read("materials/scripts/InfirmaryObjects.material")
        textures = set(re.findall(r"^\s*texture\s+(\S+)", objects, re.M))
        assert textures, "object materials have no textures"
        for texture in textures:
            credited("materials/textures/" + texture, credits)
    for path in ("materials/textures/InfirmaryFloor.png", "materials/textures/InfirmaryFloorNormal.png",
            "materials/scripts/InfirmaryFloor.material", "assets-src/gui/icons/tiles/InfirmaryButton.png"):
        credited(path, credits)
    if ROOM_ASSETS:
        floor = read("materials/scripts/InfirmaryFloor.material")
        assert "InfirmaryFloor.png" in floor and "InfirmaryFloorNormal.png" in floor
    # config/tilesets.cfg is a mixed file: complete only with its own rows from the content
    content = content_packages.has_content(repo)
    if content:
        tiles = read("config/tilesets.cfg")
        assert re.search(r"^\s*infirmaryRoom\s+infirmaryRoom\s*$", tiles, re.M)
        block = tiles.split("[infirmaryRoom]", 1)[1].split("[/infirmaryRoom]", 1)[0]
        assert "InfirmaryFloor" in block and "TortureFloor" not in block
    else:
        content_packages.unchecked("check_infirmary_assets", ["infirmaryRoom of config/tilesets.cfg"])
    # The heal glow stands in the particle script of the infirmary package
    if ROOM_ASSETS:
        particle = read("particles/Infirmary.particle")
        block = particle.split("particle_system InfirmaryHealGlow", 1)[1].split("particle_system", 1)[0]
        for pattern in (r"colour\s+0\.45\s+1\.0\s+0\.55\s+0\.8", r"emission_rate\s+4\b", r"quota\s+6\b"):
            assert re.search(pattern, block), pattern
        assert not re.search(r"^\s*duration\s", block, re.M), "heal glow must stay continuous"
        assert "InfirmaryHealGlow" in credits
    for name in ("Admit", "Discharge", "Chant", "Rattle") if ROOM_ASSETS else ():
        path = "sounds/Rooms/Infirmary/" + name + ".ogg"
        credited(path, credits)
        assert resolve(repo, path).read_bytes().startswith(b"OggS"), path
        row = next(line for line in credits.splitlines() if path in line)
        assert "CC0" in row and "https://freesound.org/" in row, path
    # The chant loop stands in the room ambience table of a content package
    if content_packages.data_file(repo, "config/roomAmbience.cfg") is None and not content_packages.has_content(repo):
        content_packages.unchecked("check_infirmary_assets", ["InfirmaryChant loop of config/roomAmbience.cfg"])
    else:
        ambience = read("config/roomAmbience.cfg")
        entries = re.findall(r"\[Effect\](.*?)\[/Effect\]", ambience, re.S)
        chants = [entry for entry in entries if re.search(r"^\s*Name\s+InfirmaryChant\s*$", entry, re.M)]
        assert len(chants) == 1, "missing or duplicate registered chant loop"
        block = chants[0]
        for pattern in (r"Match\s+InfirmaryShaman", r"Kind\s+Sound", r"Family\s+Rooms/Infirmary/Chant", r"Loop\s+yes"):
            assert re.search(pattern, block), pattern
    if ROOM_ASSETS:
        clips()
    bounds = read("source/gamemap/RoomObjectBounds.h")
    for name in furniture:
        assert re.search(r'\{"' + name + r'"\s*,', bounds), "missing measured mesh bounds: " + name
    assert re.search(r'if\(name\.compare\(0, 12, "InfirmaryCot"\) == 0\)\s*return \{1\.0f, 1\.0f\};', bounds)
    shaman = read("source/entities/InfirmaryShamanEntity.cpp")
    assert 'setWalkPath("Walk", "Idle", true, true, path, false, true)' in shaman
    assert 'setAnimationState("Idle", true)' in shaman
    generator = read("tools/room-floors/generate_room_floors.py")
    assert "'infirmary': {'field': infirmary_field" in generator
    assert "'infirmary': (48.0, 0.7)" in generator
    seam_block = generator.split("SEAM_CHECK_ROOMS =", 1)[1].split(")", 1)[0]
    assert "'infirmary'" in seam_block
    floor_seam()
    # The icon atlas lies whole in a content package
    if content_packages.data_file(repo, "gui/ODIcons.imageset") is None or content_packages.data_file(repo, "gui/ODIcons.png") is None:
        content_packages.unchecked("check_infirmary_assets", ["gui/ODIcons.imageset", "gui/ODIcons.png"])
    else:
        imageset = ET.fromstring(read("gui/ODIcons.imageset"))
        image = imageset.find("Image[@name='InfirmaryButton']")
        assert image is not None, "missing logical atlas image: OpenDungeonsIcons/InfirmaryButton"
        # The existing painted atlas builder doubles the logical slot coordinates and dimensions.
        slot = next(entry for entry in json.loads(read("assets-src/gui/icons/slots.json"))
                    if entry["name"] == "InfirmaryButton")
        assert (int(slot["width"]), int(slot["height"])) == (128, 128)
        icon_width, icon_height = int(image.get("width")), int(image.get("height"))
        assert (icon_width, icon_height) == (int(slot["width"]) * 2, int(slot["height"]) * 2)
        assert (int(image.get("xPos")), int(image.get("yPos"))) == (int(slot["xPos"]) * 2, int(slot["yPos"]) * 2)
        source = (assets_src_dir(repo) / "gui/icons" / slot["source"]).read_bytes()
        assert source[:8] == bytes([137, 80, 78, 71, 13, 10, 26, 10])
        assert struct.unpack_from(">II", source, 16) == (icon_width, icon_height)
        atlas = content_packages.resolve(repo, "gui/" + imageset.get("imagefile")).read_bytes()
        assert atlas[:8] == b"\x89PNG\r\n\x1a\n", "icon atlas must be a PNG"
        width, height = struct.unpack_from(">II", atlas, 16)
        assert int(image.get("xPos")) + icon_width <= width and int(image.get("yPos")) + icon_height <= height
    print("infirmary assets: ok" + ("" if ROOM_ASSETS else " (infirmary package not present: its assets not checked)"))


if __name__ == "__main__":
    main()
