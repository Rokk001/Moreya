"""The hunter's hoses show their configured colours and the cauldron outlet its brass, iron and ectoplasm. Compiles nothing.

Owner finding: the hoses stayed white and the cauldron outlet was a white untextured shape. Cause: the procedural hose and
outlet called ManualObject::begin without a resource group, so Ogre looked their materials up in its default group
"General", where no material script is loaded, and drew the white fallback material (BaseWhite).

The check resolves every material the way Ogre does at run time: the group named in the production begin() call (Ogre's
default "General" when none is named) must hold a .material script that defines it, read from the resource groups of
cmake/config/resources.cfg.in. A material that is not found becomes BaseWhite. On that resolved material it computes the
colour the player sees:
- hose and wires: the fragment programs of the material on the vertex colours that shadeGhostHose gives the configured
  GhostHoseColour and GhostHoseWireColour1..N (the rubber is the mean of its texture), at the lit top and the dark
  underside; every wire is clearly coloured and the rubber is dark, never white;
- outlet: the production builder buildGhostCauldronOutlet is executed in Python (its loops, vertices, texture
  coordinates and triangles); every section uses a material of the shipped GhostCauldron.mesh, resolves in its group,
  has a texture with surface detail, and every triangle covers texture area, so no face is flat or untextured.
The code before the fix is run too and must fail, so the check tells the fixed outcome from the reported one.
Fixed values counted once on this branch: 2 hose sections, 5 wires, 3 outlet sections with 150, 50 and 8 vertices.
"""
from pathlib import Path
import importlib.util
import math
import re

from PIL import Image, ImageStat

repo = Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(repo / 'scripts'))
import room_packages  # noqa: E402

#: The assets of the ghost room come from its room package (scripts/room_packages.py); without the package only the code
#: side is checked
ROOM_ASSETS = room_packages.has_room(repo, 'GhostRoom')


def room_file(relative):
    """A file of the game data, or of the room package when it moved there."""
    return room_packages.asset(repo, relative) or (repo / relative)
OGRE_DEFAULT_GROUP = 'General'  # ManualObject::begin(material, type, groupName = DEFAULT_RESOURCE_GROUP_NAME)


def read(path):
    """Reads a tracked file relative to the repository root."""
    return (repo / path).read_text(encoding='utf-8')


def body(text, signature):
    """Returns the brace-delimited body that follows the signature."""
    start = text.index(signature)
    opening = text.index('{', start)
    depth, end = 1, opening + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[opening + 1:end - 1]


# --- resource groups and the materials they load ---------------------------------------------------------------------
def groups():
    """Maps each resource group of the shipped resources.cfg template to its directories."""
    result, current = {}, None
    for line in read('cmake/config/resources.cfg.in').splitlines():
        line = line.strip()
        if line.startswith('[') and line.endswith(']'):
            current = line[1:-1]
            result[current] = []
        elif line.startswith('FileSystem=') and '@' not in line:
            result[current].append(repo / line[len('FileSystem='):])
    return result


GROUPS = groups()
# The game adds the asset folders of every found room package to the Graphics group (ResourceManager)
for package in room_packages.package_roots(repo):
    GROUPS.setdefault('Graphics', []).extend(folder for folder in (package / 'models', package / 'materials/scripts',
                                                                     package / 'materials/textures') if folder.is_dir())


def materials_in(group):
    """Returns {material name: script text} for every material script of one group (Ogre archives are flat)."""
    found = {}
    for directory in GROUPS.get(group, []):
        for script in sorted(directory.glob('*.material')):
            text = script.read_text(encoding='utf-8')
            for match in re.finditer(r'^material\s+(\S+)\s*\n\{(.*?)^\}', text, re.M | re.S):
                assert match.group(1) not in found, ('material defined twice in group', group, match.group(1))
                found[match.group(1)] = (match.group(2), text)
    return found


def file_in(group, name):
    """Finds a texture or program file in the directories of one group."""
    hits = [directory / name for directory in GROUPS.get(group, []) if (directory / name).is_file()]
    assert len(hits) == 1, (group, name, hits)
    return hits[0]


def resolve(material, group):
    """The material Ogre renders: the named one when its group holds it, else the white fallback."""
    return materials_in(group).get(material) and material or 'BaseWhite'


def begins(code):
    """Lists (material, group) of every ManualObject::begin call, with Ogre's default group when none is named."""
    calls = re.findall(r'\.begin\("(\w+)",Ogre::RenderOperation::OT_TRIANGLE_LIST(?:,"(\w+)")?\)', code)
    assert len(calls) == code.count('.begin('), 'every begin call is understood'
    return [(material, group or OGRE_DEFAULT_GROUP) for material, group in calls]


def texture_detail(group, material):
    """Returns the per-channel standard deviation and mean of the first texture of a material."""
    block = materials_in(group)[material][0]
    texture = re.search(r'^\s*texture\s+(\S+)', block, re.M)
    assert texture, (material, 'has a texture unit')
    image = Image.open(file_in(group, texture.group(1))).convert('RGB')
    stats = ImageStat.Stat(image)
    return stats.stddev, [value / 255.0 for value in stats.mean]


# --- K3: hose and wires ----------------------------------------------------------------------------------------------
config = dict(re.findall(r'^(\w+)\s+(\S+)\s*$', read('config/rooms.cfg'), re.M))


def colour(key):
    """Reads a configured red,green,blue colour like ghostHoseConfigColour."""
    return tuple(float(part) for part in config[key].split(','))


def hose_colours(creature):
    """Colours the player sees on the rubber and every wire, at the lit top and the dark underside."""
    shape = body(creature, 'static void shapeGhostHose(')
    sections = begins(shape)
    assert [material for material, _ in sections] == ['GhostHose', 'GhostHoseWire'], sections
    light = re.search(r'const Ogre::Real light=(.*?);', body(creature, 'static Ogre::ColourValue shadeGhostHose(')).group(1)
    light = re.sub(r'(\d)f\b', r'\1', light).replace('normal.z', 'up')
    glow = float(config['GhostHoseGlow'])
    wires = [colour('GhostHoseWireColour%d' % n) for n in range(1, int(config['GhostHoseWireCount']) + 1)]
    seen = {}
    for (material, group), inputs in zip(sections, ([colour('GhostHoseColour')], wires)):
        rendered = resolve(material, group)
        result = []
        for vertex in inputs:
            for up in (1.0, -1.0):
                shade = eval(light, {'__builtins__': {}}, {'glow': glow, 'up': up})
                shaded = tuple(channel * shade for channel in vertex)
                if rendered == 'BaseWhite':
                    # Ogre's fallback: lit white, the vertex colours are not used
                    result.append((1.0, 1.0, 1.0))
                    continue
                block = materials_in(group)[rendered][0]
                assert 'vertex_program_ref GhostHoseVertex' in block and 'lighting off' in block, rendered
                fragment = re.search(r'fragment_program_ref (\w+)', block).group(1)
                program_file = re.search(r'fragment_program ' + fragment + r' glsl\s*\{\s*source (\S+)',
                                         materials_in(group)[rendered][1]).group(1)
                program = file_in(group, program_file).read_text(encoding='utf-8')
                if 'texture(rubberMap, hoseUV).rgb * hoseColour.rgb' in program:
                    rubber = texture_detail(group, rendered)[1]
                    result.append(tuple(t * c for t, c in zip(rubber, shaded)))
                else:
                    assert 'fragColour = vec4(hoseColour.rgb, 1.0);' in program, program_file
                    result.append(shaded)
        seen[material] = result
    return seen


def check_hose(creature):
    """Every wire shows its own strong colour and the rubber is dark textured hose, never white."""
    seen = hose_colours(creature)
    for pixel in seen['GhostHoseWire']:
        assert max(pixel) - min(pixel) > 0.3, ('wire is clearly coloured, not white or grey', pixel)
    hues = {max(range(3), key=lambda channel: pixel[channel]) for pixel in seen['GhostHoseWire']}
    assert len(hues) == 3, ('wires show red, green and blue leading channels', hues)
    for pixel in seen['GhostHose']:
        assert max(pixel) < 0.5, ('rubber is the dark textured hose, not white', pixel)


# --- K4: the cauldron outlet, executed ---------------------------------------------------------------------------------
class Vector:
    """The parts of Ogre::Vector3 the builder uses."""

    def __init__(self, x, y, z):
        """Stores the three components."""
        self.x, self.y, self.z = x, y, z

    def __neg__(self):
        """Returns the opposite direction."""
        return Vector(-self.x, -self.y, -self.z)


class ManualObject:
    """Records sections, vertices with texture coordinates and triangles like Ogre::ManualObject."""

    def __init__(self):
        """Starts without sections."""
        self.sections = []

    def begin(self, material, operation, group=OGRE_DEFAULT_GROUP):
        """Starts a section with its material and the resource group it is looked up in."""
        self.sections.append({'material': material, 'group': group, 'vertices': [], 'triangles': []})

    def position(self, x, y, z):
        """Adds a vertex."""
        self.sections[-1]['vertices'].append({'p': (x, y, z), 'uv': None})

    def normal(self, *values):
        """Normals do not change the texture coverage."""
        pass

    def textureCoord(self, u, v):
        """Sets the texture coordinates of the last vertex."""
        self.sections[-1]['vertices'][-1]['uv'] = (u, v)

    def triangle(self, a, b, c):
        """Adds a triangle of the current section."""
        self.sections[-1]['triangles'].append((a, b, c))

    def end(self):
        """Ends the current section."""
        pass


def expression(text):
    """Translates one C++ expression of the outlet builder into Python."""
    text = re.sub(r'(\d)f\b', r'\1', text)
    text = text.replace('static_cast<float>', 'float').replace('static_cast<Ogre::uint32>', 'int')
    text = text.replace('Ogre::Math::TWO_PI', 'TWO_PI').replace('std::cos', 'math.cos').replace('std::sin', 'math.sin')
    text = text.replace('Ogre::Vector3::UNIT_Y', 'Vector(0,1,0)').replace('Ogre::Vector3::UNIT_Z', 'Vector(0,0,1)')
    text = text.replace('Ogre::RenderOperation::OT_TRIANGLE_LIST', '"OT_TRIANGLE_LIST"')
    text = re.sub(r'(\w+==\w+)\?([^:,()]+):([^,()]+)', r'(\2 if \1 else \3)', text)
    return text.replace('{', '[').replace('}', ']')


def top_level(text, separator):
    """Splits at separators outside brackets."""
    parts, depth, current = [], 0, ''
    for char in text:
        depth += (char in '([{') - (char in ')]}')
        if char == separator and depth == 0:
            parts.append(current)
            current = ''
        else:
            current += char
    return parts + [current]


def statement(text):
    """Translates one simple statement of the outlet builder."""
    text = text.strip()
    match = re.fullmatch(r'const Ogre::Vector3 (\w+)\((.*)\)', text, re.S)
    if match:
        return ['%s=Vector(%s)' % (match.group(1), expression(match.group(2)))]
    match = re.fullmatch(r'const (?:size_t|float|Ogre::uint32) (.*)', text, re.S)
    if match:
        lines = []
        for part in top_level(match.group(1), ','):
            name, value = part.split('=', 1)
            lines.append('%s=%s' % (name.replace('[]', '').strip(), expression(value)))
        return lines
    assert re.fullmatch(r'outlet\.\w+\(.*\)', text, re.S), text
    return [expression(text)]


def matching(code, index, opening, closing):
    """Returns the position of the bracket that closes the one at index."""
    depth = 0
    while True:
        depth += (code[index] == opening) - (code[index] == closing)
        if depth == 0:
            return index
        index += 1


def parse(code, index, indent):
    """Translates the statement at index (a for loop with or without braces, or a simple statement)."""
    if code.startswith('for(', index):
        end = matching(code, index + 3, '(', ')')
        header = re.fullmatch(r'size_t (\w+)=(\w+);\1(<=?)(.+?);\+\+\1', code[index + 4:end])
        assert header, code[index:end + 1]
        limit = expression(header.group(4)) + ('+1' if header.group(3) == '<=' else '')
        lines = ['%sfor %s in range(%s,%s):' % (indent, header.group(1), header.group(2), limit)]
        index = end + 1
        while code[index].isspace():
            index += 1
        if code[index] == '{':
            close = matching(code, index, '{', '}')
            return lines + translate(code[index + 1:close], indent + '    '), close + 1
        inner, index = parse(code, index, indent + '    ')
        return lines + inner, index
    depth, end = 0, index
    while code[end] != ';' or depth:
        depth += (code[end] in '({') - (code[end] in ')}')
        end += 1
    return [indent + line for line in statement(code[index:end])], end + 1


def translate(code, indent=''):
    """Translates the builder body into Python lines, statement by statement."""
    lines, index = [], 0
    while index < len(code):
        if code[index].isspace():
            index += 1
            continue
        inner, index = parse(code, index, indent)
        lines += inner
    return lines


def run_outlet(building):
    """Executes the production outlet builder and returns the recorded object."""
    code = re.sub(r'//[^\n]*', '', body(building, 'static void buildGhostCauldronOutlet('))
    outlet = ManualObject()
    exec('\n'.join(translate(code)), {'__builtins__': {'range': range, 'float': float, 'int': int},
                                      'math': math, 'TWO_PI': 2.0 * math.pi, 'Vector': Vector, 'outlet': outlet})
    return outlet


spec = importlib.util.spec_from_file_location('ghost_meshes', repo / 'source/tests/check_ghost_apparatus_visible.py')
meshes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(meshes)
CAULDRON_MATERIALS = ({material for material, _ in meshes.read_mesh('GhostCauldron')['submeshes']} if ROOM_ASSETS
                      else set())


def check_outlet(building):
    """Every outlet section is a resolved, textured cauldron material and every triangle covers texture area."""
    outlet = run_outlet(building)
    assert [section['material'] for section in outlet.sections] == ['GhostBrass', 'GhostIron', 'GhostCauldronEctoplasm']
    assert [len(section['vertices']) for section in outlet.sections] == [150, 50, 8]
    for section in outlet.sections:
        material, group = section['material'], section['group']
        assert material in CAULDRON_MATERIALS, (material, 'the cauldron itself uses this material')
        assert resolve(material, group) == material, (material, group, 'not found: drawn white')
        deviation, _ = texture_detail(group, material)
        assert max(deviation) > 1.0, (material, 'its texture has surface detail')
        for a, b, c in section['triangles']:
            corners = [section['vertices'][i]['uv'] for i in (a, b, c)]
            assert None not in corners, (material, 'every vertex has texture coordinates')
            area = (corners[1][0] - corners[0][0]) * (corners[2][1] - corners[0][1]) - \
                   (corners[2][0] - corners[0][0]) * (corners[1][1] - corners[0][1])
            assert abs(area) > 1e-6, (material, (a, b, c), 'face covers texture area, not one flat texel')


def main():
    """Checks the shipped code, then confirms that the reported state fails the same outcome checks."""
    creature = read('source/entities/Creature.cpp')
    building = read('source/entities/BuildingObject.cpp')
    for name in ('GhostHose', 'GhostHoseWire', 'GhostBrass', 'GhostIron', 'GhostCauldronEctoplasm'):
        assert resolve(name, OGRE_DEFAULT_GROUP) == 'BaseWhite', (name, 'Ogre default group loads no material scripts')
    check_hose(creature)
    if not ROOM_ASSETS:
        # The outlet uses the cauldron mesh and textures of the ghost room package
        try:
            check_hose(creature.replace(',"Graphics");', ');'))
        except AssertionError:
            print('ghost hose materials: ok (ghost room package not present: outlet not checked)')
            return
        raise AssertionError(('check_hose', 'the reported white state must fail'))
    check_outlet(building)
    # The reported state: no group in begin(), and the outlet bore and lip on one texel.
    reported_creature = creature.replace(',"Graphics");', ');')
    reported_building = building.replace(',"Graphics");', ');').replace(
        'outlet.textureCoord(static_cast<float>(side)/sides,0.94f+0.08f);', 'outlet.textureCoord(0.0f,0.0f);')
    for check, text in ((check_hose, reported_creature), (check_outlet, reported_building)):
        try:
            check(text)
        except AssertionError:
            continue
        raise AssertionError((check.__name__, 'the reported white state must fail'))
    flat = building.replace(
        'outlet.textureCoord(static_cast<float>(side)/sides,ring==0?0.60f:0.94f);', 'outlet.textureCoord(0.0f,0.0f);')
    try:
        check_outlet(flat)
    except AssertionError:
        pass
    else:
        raise AssertionError('a bore on one texel must fail')
    print('ghost hose and outlet materials: 2 hose sections, 5 wires coloured, 3 outlet sections textured: ok')


if __name__ == '__main__':
    main()
