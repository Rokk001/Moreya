"""Tavern assets: models, Blender sources, materials and textures, icon sources, particles, sounds and their ambience
entries, the CREDITS rows, the nine tavern clips in every creature skeleton and the innkeeper clips.

What is checked
  models      TavernCounter, Innkeeper, TavernKeg, TavernTable, TavernMug, Vomit: mesh, one Blender source each, a
              material in a material script, the innkeeper's skeleton with the clips Idle, Pour and Cheer; the counter
              uses TavernCounterWood, TavernRail (self-lit) and TavernSign and never the striped TavernWood; planks,
              robe, hide and apron bright enough for the tavern light, the rail aged brass with a faint glow (710)
  materials   TavernWood, TavernBrass, TavernStone (and the other object materials) with a 128 x 128 texture each, the
              floor and wall materials with their textures and normal maps, the bird effect material
  icons       the painted 256 x 256 sources of TavernButton and BeerButton (the atlas entries are pinned by
              check_forged_icons.py)
  particles   TavernSmoke and DuelBirds, each defined once; the materials they use exist; the bird atlas is 2048 x 2048
  sounds      Pour, Murmur, Clink, Slap and Cheer exist as mono 22050 Hz Vorbis, the two ambience families are loadable,
              the ambience entries name them; scripts/check_sound_sources.py is green
  clips       Drink, Slap, ArmWrestle, Dice, KnockedOut, GetUp, Stagger, Vomit and Hangover in every skeleton a creature
              type uses (the clip names are listed once, the client asks for them in EntityAnimation)
  seat clips  Sit, SitDrink, SitSlap, SitSlapped, SitArmWrestle, SitDice and SitSlumped once in each of the 30 skeletons
              of the types that visit the tavern (their poses are measured by check_tavern_seat_clips.py)
  credits     every file above has a CREDITS row, every changed skeleton has a row for its new clips
  game light  (INGAME-QS-11 K8, "alles nur noch schwarz") every texture the materials of the six tavern models use, sampled
              where the models' surfaces map onto it (OgreXMLConverter converts the meshes), shows in the game at least
              as bright as the tavern floor and not brighter than BRIGHT_SHARE x the floor: the game shows an object texel
              at about OBJECT_LIGHT x its value and a floor texel at about FLOOR_LIGHT x (both measured once on Mario's
              screenshot ODscreenshot_2026-11-18_165308_9 over the build 0.7.3.77 textures); iron, brass, the rail, the
              sign and the foam are accents and need at least ACCENT_SHARE of the floor; the barkeeper keeps the floors of
              owner check 710 (skin 85, hood 45, cloth 130) on the texels his surfaces use; every surface shows detail
              (luminance spread), is not garish (mean saturation, brightest texels) and wood, stone, iron and the
              approved atlases have a normal map. Build 0.7.3.77 fails: counter planks 33 against a floor of 104.

Calls (from the repository root):
  python source/tests/check_tavern_assets.py            file checks, no compiler, no game; the game light section
                                                         needs OGRE_XML_CONVERTER (full path of OgreXMLConverter.exe)
"""
from pathlib import Path
import fnmatch
import re
import struct
import subprocess
import sys
import zlib

root = Path(__file__).resolve().parents[2]
# ODP_ASSETS_SRC (else <repo>/assets-src) holds the asset sources, see scripts/assets_src.py
sys.path.insert(0, str(root / 'scripts'))
from assets_src import assets_src_dir, resolve  # noqa: E402

# The nine clips every creature skeleton gets, in the order of the design
TAVERN_CLIPS = ['Drink', 'Slap', 'ArmWrestle', 'Dice', 'KnockedOut', 'GetUp', 'Stagger', 'Vomit', 'Hangover']
# The seven seated clips of every skeleton of a type that visits the tavern, and the number of those skeletons
SEAT_CLIPS = ['Sit', 'SitDrink', 'SitSlap', 'SitSlapped', 'SitArmWrestle', 'SitDice', 'SitSlumped']
VISITING_SKELETONS = 30
# The clips of the innkeeper figure
INNKEEPER_CLIPS = ['Idle', 'Pour', 'Cheer']
# Size of the object textures, of the painted icon sources and of the bird atlas; wood, iron and stone were repainted
# larger for INGAME-QS-11 K8 (the table maps its whole stone top onto one texture)
OBJECT_TEXTURE_SIZE = 128
OBJECT_TEXTURE_SIZES = {'TavernWood': 512, 'TavernIron': 512, 'TavernStone': 1024}
ICON_SOURCE_SIZE = 256
BIRD_ATLAS_SIZE = 2048
# Format of the tavern sounds
SOUND_CHANNELS = 1
SOUND_RATE = 22050


# Returns the text of a repository file.
def read(path):
    return resolve(root, path).read_text(encoding='utf-8', errors='replace')


# Returns (width, height) of a PNG file from its header.
def png_size(path):
    data = resolve(root, path).read_bytes()
    assert data[:8] == b'\x89PNG\r\n\x1a\n', path + ' is not a PNG'
    return struct.unpack('>II', data[16:24])


# Returns the mean luminance (0..255) of an 8-bit grey, RGB or RGBA PNG without interlacing.
def png_mean_luminance(path):
    data = resolve(root, path).read_bytes()
    assert data[:8] == b'\x89PNG\r\n\x1a\n', path + ' is not a PNG'
    at, idat, head = 8, b'', None
    while at < len(data):
        size, kind = struct.unpack('>I4s', data[at:at + 8])
        body = data[at + 8:at + 8 + size]
        if kind == b'IHDR':
            head = struct.unpack('>IIBBBBB', body)
        elif kind == b'IDAT':
            idat += body
        at += 12 + size
    width, height, depth, colour, _, _, interlace = head
    channels = {0: 1, 2: 3, 4: 2, 6: 4}[colour]
    assert depth == 8 and interlace == 0, path + ' must be an 8-bit PNG without interlacing'
    raw = zlib.decompress(idat)
    stride = width * channels
    prev = bytearray(stride)
    total = 0.0
    for y in range(height):
        kind = raw[y * (stride + 1)]
        line = bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        for i in range(stride):
            a = line[i - channels] if i >= channels else 0
            b = prev[i]
            c = prev[i - channels] if i >= channels else 0
            if kind == 1:
                line[i] = (line[i] + a) & 255
            elif kind == 2:
                line[i] = (line[i] + b) & 255
            elif kind == 3:
                line[i] = (line[i] + (a + b) // 2) & 255
            elif kind == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        for x in range(width):
            px = line[x * channels:x * channels + channels]
            total += px[0] if channels < 3 else 0.299 * px[0] + 0.587 * px[1] + 0.114 * px[2]
        prev = line
    return total / (width * height)


# Returns (channels, rate) of an Ogg Vorbis file from its identification header.
def vorbis_format(path):
    data = resolve(root, path).read_bytes()
    assert data[:4] == b'OggS', path + ' is not an Ogg file'
    at = data.index(b'\x01vorbis')
    channels = data[at + 11]
    rate = struct.unpack('<I', data[at + 12:at + 16])[0]
    return channels, rate


# Returns the creature types of creatures.cfg: name -> mesh name
def creature_types():
    types = {}
    for block in re.findall(r'\[Creature\](.*?)\[/Creature\]', read('config/creatures.cfg'), re.S):
        fields = {}
        for line in block.splitlines():
            words = line.split()
            if len(words) >= 2 and not words[0].startswith('#'):
                fields.setdefault(words[0], words[1])
        if 'Name' in fields:
            types[fields['Name']] = fields['MeshName']
    return types


materials = ''.join(p.read_text(encoding='utf-8', errors='replace') for p in (root / 'materials' / 'scripts').glob('*.material'))
credits = read('CREDITS')

# 1. Models: mesh, Blender source, material, the innkeeper's skeleton
MODELS = {'TavernCounter': 'assets-src/rooms/tavern/TavernCounter.blend', 'Innkeeper': 'assets-src/rooms/tavern/Innkeeper.blend',
          'TavernKeg': 'assets-src/rooms/tavern/TavernKeg.blend', 'TavernTable': 'assets-src/rooms/tavern/TavernTable.blend',
          'TavernMug': 'assets-src/rooms/tavern/TavernMug.blend', 'Vomit': 'assets-src/dirt/Vomit.blend'}
for name, source in MODELS.items():
    mesh = root / 'models' / (name + '.mesh')
    assert mesh.is_file() and mesh.stat().st_size > 0, 'models/' + name + '.mesh missing'
    assert resolve(root, source).is_file(), source + ' missing'
mesh_material_names = {'TavernCounter': ('TavernCounterWood', 'TavernRail', 'TavernSign'), 'TavernKeg': ('TavernKegWood', 'TavernIron', 'TavernBrass'),
                       'TavernTable': ('TavernStone', 'TavernTableWood'), 'TavernMug': ('TavernWood', 'TavernFoam'),
                       'Innkeeper': ('TavernCloth', 'TavernHood', 'TavernSkin'), 'Vomit': ('TavernVomit',)}
for name, used in mesh_material_names.items():
    data = (root / 'models' / (name + '.mesh')).read_bytes()
    assert any(m.encode('ascii') in data for m in used), 'models/' + name + '.mesh uses none of ' + ', '.join(used)
# Owner check 664 (build 0.7.3.37): the counter is built from its own plank atlas (not the wave-striped shared
# TavernWood); its foot rail, sign rim and bell use the polished, slightly self-lit TavernRail; the plate uses TavernSign
counter = (root / 'models' / 'TavernCounter.mesh').read_bytes()
for used in ('TavernCounterWood', 'TavernRail', 'TavernSign'):
    assert re.search(rb'(?<![A-Za-z])' + used.encode('ascii') + rb'(?![A-Za-z])', counter), 'models/TavernCounter.mesh needs the material ' + used
assert not re.search(rb'(?<![A-Za-z])TavernWood(?![A-Za-z])', counter), 'models/TavernCounter.mesh must not use the striped TavernWood'
rail = re.search(r'^material TavernRail\b.*?^}', materials, re.M | re.S)
assert rail and re.search(r'^\s*emissive\s+0*\.0*[1-9]', rail.group(0), re.M), 'TavernRail needs its self-light so the rail reads from the room camera'
innkeeper = (root / 'models' / 'Innkeeper.mesh').read_bytes()
for used in ('TavernHood', 'TavernSkin', 'TavernCloth'):
    assert used.encode('ascii') in innkeeper, 'models/Innkeeper.mesh needs the material ' + used
assert b'Innkeeper.skeleton' in (root / 'models' / 'Innkeeper.mesh').read_bytes(), 'the innkeeper mesh needs its skeleton'
innkeeper_skeleton = (root / 'models' / 'Innkeeper.skeleton').read_bytes()
for clip in INNKEEPER_CLIPS:
    assert (clip + '\n').encode('ascii') in innkeeper_skeleton, 'Innkeeper.skeleton has no clip ' + clip
# Owner check 710 (build 0.7.3.41): the counter read as a black box with a yellow edge and the innkeeper as a dark
# faceless figure. A vertical face shows at about 0.7 x its texture value in the tavern light, so the planks, the robe,
# the hide and the apron need a minimum brightness (build 41: 37, 28, 62, 107), and the rail must not glare yellow
# (build 41: texture 169, emissive 0.22 0.16 0.06).
for name, low in (('TavernCounterWood', 55), ('TavernHood', 45), ('TavernSkin', 85), ('TavernCloth', 130)):
    value = png_mean_luminance('materials/textures/tavern/' + name + '.png')
    assert value >= low, '%s.png is too dark for the tavern light (mean %.0f, needs %d)' % (name, value, low)
value = png_mean_luminance('materials/textures/tavern/TavernRail.png')
assert value <= 145, 'TavernRail.png glares yellow (mean %.0f, at most 145): aged brass, not a bright yellow edge' % value
emissive = re.search(r'^\s*emissive\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)', rail.group(0), re.M)
assert emissive and max(float(x) for x in emissive.groups()) <= 0.12, 'TavernRail self-light at most 0.12 (a stronger glow reads as a yellow edge)'

# 2. Materials and textures
# The table and the keg have their own wood baked onto their UV layouts (INGAME-QS-11 K8)
for name in ('TavernTableWood', 'TavernKegWood'):
    assert re.search(r'^material ' + name + r'\b', materials, re.M), 'material ' + name + ' missing'
    for suffix in ('', 'Normal'):
        assert png_size('materials/textures/tavern/' + name + suffix + '.png') == (1024, 1024), name + suffix + ' texture size'
for name in ('TavernWood', 'TavernBrass', 'TavernStone', 'TavernIron', 'TavernCloth', 'TavernHood', 'TavernSkin', 'TavernFoam',
             'TavernSign', 'TavernVomit', 'TavernCounterWood', 'TavernRail'):
    assert re.search(r'^material ' + name + r'\b', materials, re.M), 'material ' + name + ' missing'
    size = OBJECT_TEXTURE_SIZES.get(name, OBJECT_TEXTURE_SIZE)
    assert png_size('materials/textures/tavern/' + name + '.png') == (size, size), name + ' texture size'
for name in ('TavernFloor', 'TavernWall'):
    assert re.search(r'^material ' + name + r'\b', materials, re.M), 'material ' + name + ' missing'
    for suffix in ('', 'Normal'):
        assert png_size('materials/textures/tavern/' + name + suffix + '.png')[0] > 0, name + suffix + '.png missing'
assert re.search(r'^material TavernDuelBirds\b', materials, re.M), 'material TavernDuelBirds missing'
assert png_size('materials/textures/tavern/DuelBird.png') == (BIRD_ATLAS_SIZE, BIRD_ATLAS_SIZE), 'bird atlas size'
assert (assets_src_dir(root) / 'rooms' / 'tavern' / 'DuelBird.png').is_file(), 'bird source missing'

# 3. Icons: the painted sources of the two buttons
for icon in ('TavernButton', 'BeerButton'):
    assert png_size('assets-src/gui/icons/tiles/' + icon + '.png') == (ICON_SOURCE_SIZE, ICON_SOURCE_SIZE), icon + ' source size'

# 4. Particles: each defined once in all particle files, the materials exist
all_particles = ''.join(p.read_text(encoding='utf-8', errors='replace') for p in (root / 'particles').glob('*.particle'))
for system in ('TavernSmoke', 'DuelBirds'):
    assert len(re.findall(r'^particle_system ' + system + r'\s*$', all_particles, re.M)) == 1, 'particle ' + system + ' must be defined exactly once'
tavern_particles = read('particles/Tavern.particle')
for used in re.findall(r'^\s*material\s+(\S+)', tavern_particles, re.M):
    assert re.search(r'^material ' + used + r'\b', materials, re.M), 'particle material ' + used + ' missing'
ambience = read('config/roomAmbience.cfg')
assert 'System      TavernSmoke' in ambience and 'Match       TavernCounter' in ambience, 'the counter smoke is wired in roomAmbience.cfg'
assert 'DuelBirds' in read('source/render/RenderManager.cpp'), 'the bird particle is attached by the render code'

# 5. Sounds: the five files as mono 22050 Hz Vorbis, the two ambience families, the ambience entries
for sound in ('sounds/Rooms/Tavern/Pour.ogg', 'sounds/Rooms/Tavern/Murmur.ogg', 'sounds/Rooms/Tavern/Clink.ogg',
              'sounds/Creatures/Default/Slap.ogg', 'sounds/Creatures/Default/Cheer.ogg',
              'sounds/Spatial/Rooms/Tavern/Murmur/Murmur.ogg', 'sounds/Spatial/Rooms/Tavern/Clink/Clink.ogg'):
    assert (root / sound).is_file(), sound + ' missing'
    assert vorbis_format(sound) == (SOUND_CHANNELS, SOUND_RATE), sound + ' must be mono 22050 Hz Vorbis, found ' + str(vorbis_format(sound))
for family in ('Rooms/Tavern/Murmur', 'Rooms/Tavern/Clink'):
    assert 'Family      ' + family in ambience, 'roomAmbience.cfg needs the family ' + family
assert 'Loop        yes' in ambience[ambience.index('Name        TavernMurmur'):], 'the murmur is a loop'
sound_check = subprocess.run([sys.executable, str(root / 'scripts' / 'check_sound_sources.py')], capture_output=True, text=True, cwd=str(root))
assert sound_check.returncode == 0, 'check_sound_sources.py failed:\n' + sound_check.stdout + sound_check.stderr

# 6. The nine clips in every skeleton a creature type uses (binary skeleton: the clip names end with a line feed)
animation_h = read('source/entities/MovableGameEntity.h')
for token in ('drink_anim = "Drink"', 'armwrestle_anim = "ArmWrestle"', 'slap_anim = "Slap"', 'dice_anim = "Dice"', 'knockedout_anim = "KnockedOut"',
              'getup_anim = "GetUp"', 'stagger_anim = "Stagger"', 'vomit_anim = "Vomit"', 'hangover_anim = "Hangover"'):
    assert token in animation_h, 'EntityAnimation lacks ' + token
types = creature_types()
assert len(types) == 35, len(types)
skeletons = {}
for name, mesh in types.items():
    data = (root / 'models' / mesh).read_bytes()
    found = re.findall(rb'([A-Za-z0-9_]+)\.skeleton', data)
    assert found, mesh + ' has no skeleton'
    skeletons[name] = found[0].decode('ascii') + '.skeleton'
unique_skeletons = sorted(set(skeletons.values()))
assert len(unique_skeletons) == 32, 'the 35 types use 32 skeletons, found ' + str(len(unique_skeletons))
for skeleton in unique_skeletons:
    data = (root / 'models' / skeleton).read_bytes()
    for clip in TAVERN_CLIPS:
        assert len(re.findall(rb'(?<![A-Za-z0-9_])' + clip.encode('ascii') + rb'\n', data)) == 1, skeleton + ' must hold the clip ' + clip + ' exactly once'

# The seated clips in every skeleton of a type that visits the tavern (its Tavern line is not 0 0)
for token in ('sit_anim = "Sit"', 'sit_drink_anim = "SitDrink"', 'sit_slap_anim = "SitSlap"', 'sit_slapped_anim = "SitSlapped"',
              'sit_armwrestle_anim = "SitArmWrestle"', 'sit_dice_anim = "SitDice"', 'sit_slumped_anim = "SitSlumped"'):
    assert token in animation_h, 'EntityAnimation lacks ' + token
visiting = set()
for block in re.findall(r'\[Creature\](.*?)\[/Creature\]', read('config/creatures.cfg'), re.S):
    name_field = re.search(r'^\s*Name\s+(\S+)', block, re.M)
    tavern_line = re.search(r'^\s*Tavern\s+(\S+)\s+(\S+)', block, re.M)
    if name_field and tavern_line and (float(tavern_line.group(1)) > 0.0 or float(tavern_line.group(2)) > 0.0):
        visiting.add(skeletons[name_field.group(1)])
assert len(visiting) == VISITING_SKELETONS, 'the types that visit the tavern use 30 skeletons, found ' + str(len(visiting))
for skeleton in sorted(visiting):
    data = (root / 'models' / skeleton).read_bytes()
    for clip in SEAT_CLIPS:
        assert len(re.findall(rb'(?<![A-Za-z0-9_])' + clip.encode('ascii') + rb'\n', data)) == 1, skeleton + ' must hold the clip ' + clip + ' exactly once'

# 7. CREDITS: a row for every file of the tavern assets and for every skeleton with new clips
patterns = []
for line in credits.splitlines():
    first = re.split(r'\s{2,}', line.strip())[0]
    for part in first.split(','):
        part = re.sub(r'\s*\(.*$', '', part.strip().lstrip('->').strip())
        if part:
            patterns.append(part)


# Whether a CREDITS row names the file (a path or a wildcard pattern).
def credited(path):
    return any(fnmatch.fnmatchcase(path.lower(), p.lower()) for p in patterns)


files = ['models/' + name + '.mesh' for name in MODELS] + list(MODELS.values()) + ['models/Innkeeper.skeleton']
files += ['materials/scripts/TavernObjects.material', 'materials/scripts/TavernFloor.material', 'materials/scripts/TavernWall.material',
          'materials/scripts/TavernEffects.material', 'particles/Tavern.particle', 'materials/textures/tavern/DuelBird.png',
          'assets-src/rooms/tavern/DuelBird.png', 'assets-src/gui/icons/tiles/TavernButton.png', 'assets-src/gui/icons/tiles/BeerButton.png',
          'materials/textures/tavern/TavernFloor.png', 'materials/textures/tavern/TavernFloorNormal.png',
          'materials/textures/tavern/TavernWall.png', 'materials/textures/tavern/TavernWallNormal.png']
files += ['materials/textures/tavern/' + name + '.png' for name in ('TavernWood', 'TavernBrass', 'TavernStone', 'TavernIron', 'TavernCloth',
                                                                      'TavernHood', 'TavernSkin', 'TavernFoam', 'TavernSign', 'TavernVomit',
                                                                      'TavernCounterWood', 'TavernRail', 'TavernTableWood', 'TavernKegWood',
                                                                      'TavernWoodNormal', 'TavernIronNormal', 'TavernStoneNormal',
                                                                      'TavernTableWoodNormal', 'TavernKegWoodNormal')]
files += ['models/TavernStool.mesh']
files += ['sounds/Rooms/Tavern/Pour.ogg', 'sounds/Rooms/Tavern/Murmur.ogg', 'sounds/Rooms/Tavern/Clink.ogg',
          'sounds/Creatures/Default/Slap.ogg', 'sounds/Creatures/Default/Cheer.ogg',
          'sounds/Spatial/Rooms/Tavern/Murmur/Murmur.ogg', 'sounds/Spatial/Rooms/Tavern/Clink/Clink.ogg']
for path in files:
    assert credited(path), 'CREDITS has no row for ' + path
for skeleton in unique_skeletons:
    assert re.search(r'^models/' + re.escape(skeleton) + r' \(new Drink, Slap, ArmWrestle, Dice, KnockedOut, GetUp, Stagger, Vomit, Hangover tracks\)',
                     credits, re.M | re.I), 'CREDITS has no row for the new clips in ' + skeleton
for skeleton in sorted(visiting):
    assert re.search(r'^models/' + re.escape(skeleton) + r' \(new Sit, SitDrink, SitSlap, SitSlapped, SitArmWrestle, SitDice, SitSlumped tracks\)',
                     credits, re.M), 'CREDITS has no row for the seated clips in ' + skeleton
# Every sound row names a source address and the licence CC0 (the recordings are real, never generated)
for sound in ('Pour', 'Murmur', 'Clink', 'Slap', 'Cheer'):
    row = [l for l in credits.splitlines() if re.search(r'/' + sound + r'\.ogg\s', l)]
    assert row, 'CREDITS has no row for ' + sound + '.ogg'
    for line in row:
        assert 'https://freesound.org/' in line and 'CC0' in line, sound + ' row needs a source address and CC0: ' + line[:80]


# 8. Game light (INGAME-QS-11 K8): every texture of the tavern models' materials, sampled where the surfaces map onto it
import numpy as np  # noqa: E402
import os  # noqa: E402
import tempfile  # noqa: E402
import time  # noqa: E402
import xml.etree.ElementTree as ET  # noqa: E402
from PIL import Image  # noqa: E402

# How the game shows a texel, measured once on ODscreenshot_2026-11-18_165308_9 over the build 0.7.3.77 textures:
# objects (table top 53 -> 59, counter planks 30 -> 33, apron, hood, stool and bench) about 1.10 x, the tavern floor
# (Room.frag with room light, gain and the cursor light; texel 54 -> 104) about 1.93 x
OBJECT_LIGHT = 1.10
FLOOR_LIGHT = 1.93
FLOOR_TEXTURE = 'Tavern1111.png'   # the floor of a tavern tile inside the room
BRIGHT_SHARE = 1.45                # not brighter than this share of the floor (the apron is the lightest surface)
ACCENT_SHARE = 0.60                # iron, brass, rail, sign and foam are accents, never plain black
ACCENTS = {'TavernIron', 'TavernBrass', 'TavernRail', 'TavernSign', 'TavernFoam'}
# The barkeeper's atlases keep the floors of owner check 710 on the texels his surfaces use
BARKEEPER_FLOORS = {'TavernSkin': 85, 'TavernHood': 45, 'TavernCloth': 130}
MIN_SPREAD = 0.08                  # luminance standard deviation / mean of a surface: visible grain, folds, wear
ACCENT_SPREAD = 0.05               # the same for the small accents (the smooth patina of the sign: 0.07)
MAX_SATURATION = {'TavernStone': 0.25, 'TavernIron': 0.25}
DEFAULT_MAX_SATURATION = 0.58      # wood, cloth, hide: worn and muted (build 77 counter planks: 0.75)
MAX_CHANNEL = 235                  # p99.5 of the brightest channel: no white or glaring texels
NORMAL_MAPPED = ('TavernWood', 'TavernIron', 'TavernStone', 'TavernTableWood', 'TavernKegWood', 'TavernCounterWood',
                 'TavernHood', 'TavernSkin', 'TavernCloth')
LIGHT_MODELS = ('TavernCounter', 'Innkeeper', 'TavernKeg', 'TavernTable', 'TavernStool', 'TavernMug')
SAMPLES = 40000
LUMA = np.array([0.299, 0.587, 0.114])


# Returns the texture names of a material (colour first, then the normal map) from the material scripts.
def material_textures(name):
    block = re.search(r'^material ' + name + r'\b.*?^}', materials, re.M | re.S)
    assert block, 'material ' + name + ' missing'
    return re.findall(r'^\s*texture\s+(\S+)', block.group(0), re.M)


# Returns positions, uvs and {material: faces} of a binary mesh, converted to XML by OgreXMLConverter.
def mesh_geometry(name, work):
    converter = os.environ.get('OGRE_XML_CONVERTER', 'OgreXMLConverter')
    source = Path(work) / (name + '.mesh')
    source.write_bytes((root / 'models' / (name + '.mesh')).read_bytes())
    target = Path(work) / (name + '.mesh.xml')
    subprocess.run([converter, '-q', str(source), str(target)], check=True, capture_output=True)
    tree = ET.parse(str(target)).getroot()
    positions, uvs = [], []
    for buffer in tree.find('sharedgeometry').findall('vertexbuffer'):
        for vertex in buffer.findall('vertex'):
            position = vertex.find('position')
            if position is not None:
                positions.append([float(position.get(k)) for k in 'xyz'])
            uv = vertex.find('texcoord')
            if uv is not None:
                uvs.append([float(uv.get('u')), float(uv.get('v'))])
    faces = {}
    for sub in tree.find('submeshes').findall('submesh'):
        rows = [[int(f.get(k)) for k in ('v1', 'v2', 'v3')] for f in sub.find('faces').findall('face')]
        faces.setdefault(sub.get('material'), []).extend(rows)
    return np.array(positions), np.array(uvs), {m: np.array(f) for m, f in faces.items()}


# Returns the texels a surface shows: SAMPLES points spread evenly over the area of its faces (seeded, nearest texel).
def surface_texels(positions, uvs, faces, texture):
    a, b, c = positions[faces[:, 0]], positions[faces[:, 1]], positions[faces[:, 2]]
    area = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
    rng = np.random.default_rng(1)
    pick = rng.choice(len(faces), SAMPLES, p=area / area.sum())
    r1, r2 = np.sqrt(rng.random(SAMPLES)), rng.random(SAMPLES)
    w = np.stack([1 - r1, r1 * (1 - r2), r1 * r2], 1)
    uv = uvs[faces[pick, 0]] * w[:, :1] + uvs[faces[pick, 1]] * w[:, 1:2] + uvs[faces[pick, 2]] * w[:, 2:]
    image = np.asarray(Image.open(str(root / 'materials' / 'textures' / 'tavern' / texture)).convert('RGB')).astype(float)
    height, width = image.shape[:2]
    return image[(np.mod(uv[:, 1], 1.0) * height).astype(int) % height, (np.mod(uv[:, 0], 1.0) * width).astype(int) % width]


light_start = time.monotonic()
floor_texels = np.asarray(Image.open(str(root / 'materials' / 'textures' / 'tavern' / FLOOR_TEXTURE)).convert('RGB')).astype(float)
floor_shown = (floor_texels @ LUMA).mean() * FLOOR_LIGHT
seen = {}
with tempfile.TemporaryDirectory(prefix='tavern_light_') as work:
    for model in LIGHT_MODELS:
        positions, uvs, faces = mesh_geometry(model, work)
        for material, rows in faces.items():
            textures = material_textures(material)
            texels = surface_texels(positions, uvs, rows, textures[0])
            luma = texels @ LUMA
            top = texels.max(1)
            saturation = np.where(top > 0, (top - texels.min(1)) / np.maximum(top, 1e-6), 0.0).mean()
            shown = luma.mean() * OBJECT_LIGHT
            where = '%s %s (%s)' % (model, material, textures[0])
            low = ACCENT_SHARE if material in ACCENTS else 1.0
            assert shown >= low * floor_shown, '%s shows %.0f in the game light, darker than %.2f x the tavern floor (%.0f)' % (
                where, shown, low, floor_shown)
            # the foam of the mug is light by nature; every other surface stays below BRIGHT_SHARE of the floor
            assert material == 'TavernFoam' or shown <= BRIGHT_SHARE * floor_shown,'%s shows %.0f, brighter than %.2f x the tavern floor (%.0f): too bright' % (
                where, shown, BRIGHT_SHARE, floor_shown)
            spread = ACCENT_SPREAD if material in ACCENTS else MIN_SPREAD
            assert luma.std() >= spread * luma.mean(), '%s shows no surface detail (spread %.2f, needs %.2f)' % (
                where, luma.std() / luma.mean(), spread)
            if material not in ACCENTS:
                limit = MAX_SATURATION.get(material, DEFAULT_MAX_SATURATION)
                assert saturation <= limit, '%s is garish (mean saturation %.2f, at most %.2f)' % (where, saturation, limit)
                assert np.percentile(top, 99.5) <= MAX_CHANNEL, '%s has glaring texels (p99.5 %.0f, at most %d)' % (
                    where, np.percentile(top, 99.5), MAX_CHANNEL)
            if material in BARKEEPER_FLOORS:
                assert luma.mean() >= BARKEEPER_FLOORS[material], '%s used texels are too dark (mean %.0f, needs %d)' % (
                    where, luma.mean(), BARKEEPER_FLOORS[material])
            if material in NORMAL_MAPPED:
                assert len(textures) >= 2 and (root / 'materials' / 'textures' / 'tavern' / textures[1]).is_file(), where + ' needs its normal map'
            seen[material] = shown
for material in ('TavernCounterWood', 'TavernRail', 'TavernSign', 'TavernSkin', 'TavernHood', 'TavernCloth', 'TavernTableWood',
                 'TavernKegWood', 'TavernWood', 'TavernStone', 'TavernIron', 'TavernBrass', 'TavernFoam'):
    assert material in seen, 'no tavern model uses ' + material
print('ODP_TEST_PHASE {"name":"game-light","seconds":%.2f}' % (time.monotonic() - light_start))
print('tavern game light: floor %.0f, ' % floor_shown + ', '.join('%s %.0f' % kv for kv in sorted(seen.items())))

print('tavern assets ok')
