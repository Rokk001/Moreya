"""Check that the welcome line shown at the top of the screen has a real glyph for every character.

The welcome line (ODApplication::MOTD) is drawn by the overlay text box "DebugMessages" with the overlay font named
there. The check reads the C++ string literal of the line as the compiler would (escape sequences decoded, the
version added), finds the TrueType file of that font in the font definitions and looks every character up in the
character map of the file. A character without a glyph (glyph 0) is drawn as a box. No compile, no game.
"""
from pathlib import Path
import re
import struct

ROOT = Path(__file__).resolve().parents[2]


def glyph_lookup(path):
    """Returns a function mapping a code point to its glyph id in a TrueType file (format 4 Unicode cmap)."""
    data = path.read_bytes()
    tables = {}
    for index in range(struct.unpack_from('>H', data, 4)[0]):
        tag, _, offset, _ = struct.unpack_from('>4sIII', data, 12 + 16 * index)
        tables[tag] = offset
    base = tables[b'cmap']
    subtable = None
    for index in range(struct.unpack_from('>H', data, base + 2)[0]):
        platform, encoding, offset = struct.unpack_from('>HHI', data, base + 4 + 8 * index)
        if (platform, encoding) in ((3, 1), (0, 3), (0, 4)) and struct.unpack_from('>H', data, base + offset)[0] == 4:
            subtable = base + offset
            break
    assert subtable is not None, 'no Unicode character map in ' + path.name
    segments = struct.unpack_from('>H', data, subtable + 6)[0] // 2
    ends = struct.unpack_from('>%dH' % segments, data, subtable + 14)
    starts = struct.unpack_from('>%dH' % segments, data, subtable + 16 + 2 * segments)
    deltas = struct.unpack_from('>%dh' % segments, data, subtable + 16 + 4 * segments)
    range_position = subtable + 16 + 6 * segments
    range_offsets = struct.unpack_from('>%dH' % segments, data, range_position)

    def glyph(code):
        for i in range(segments):
            if starts[i] <= code <= ends[i]:
                if range_offsets[i] == 0:
                    return (code + deltas[i]) & 0xFFFF
                at = range_position + 2 * i + range_offsets[i] + 2 * (code - starts[i])
                value = struct.unpack_from('>H', data, at)[0]
                return 0 if value == 0 else (value + deltas[i]) & 0xFFFF
        return 0
    return glyph


application = (ROOT / 'source/ODApplication.cpp').read_text(encoding='utf-8')
literal = re.search(r'std::string ODApplication::MOTD = "((?:[^"\\]|\\.)*)" \+ VERSION;', application)
assert literal, 'welcome line definition'
text = literal.group(1).encode('ascii').decode('unicode_escape') + '0.7.4.0'
assert text.startswith('Welcome to Moreya'), text

renderer = (ROOT / 'source/render/TextRenderer.cpp').read_text(encoding='utf-8')
font_name = re.search(r'setParameter\("font_name", "([^"]+)"\)', renderer).group(1)
assert 'addTextBox("DebugMessages", ODApplication::MOTD.c_str()' in application
font_file = None
for definition in (ROOT / 'gui/fonts').glob('*.fontdef'):
    match = re.search(r'font\s+' + re.escape(font_name) + r'\s*\{[^}]*source\s+(\S+)', definition.read_text(encoding='utf-8'))
    if match:
        font_file = ROOT / 'gui/fonts' / match.group(1)
assert font_file is not None and font_file.exists(), font_name

glyph = glyph_lookup(font_file)
missing = sorted({repr(c) for c in text if glyph(ord(c)) == 0})
assert not missing, 'characters drawn as a box in %s: %s' % (font_file.name, ', '.join(missing))
print('welcome line "%s": every character has a glyph in %s' % (text, font_file.name))
