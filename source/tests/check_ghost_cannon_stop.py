"""Decision 1078: the hunter's capture cannon stops beaming once the ghost is inside the trap. Compiles nothing.

The check executes the production predicates in Python instead of matching their text:
- the ghost's height, size and pull into the trap from GhostEntity::updateLook with the shipped rooms.cfg values,
- the top of the ghost's world bounds from the bounds of the shipped Ghost.mesh,
- ghostAboveTrap and the `beaming` condition of Creature::updateGhostHuntVisuals,
- the conditions that put the Beam clip back to Idle and tear down sound, sparks, glow and lightning.
Over the whole beam step (1001 samples of the capture share, three floor heights) the cannon fires while any part of
the ghost is above the trap opening, stops at the first frame the whole body is inside, never resumes, and stops before
the box snaps shut. The old predicate (target only) is executed too and must keep firing after entry, so the check
tells the delivered behaviour from the lost one. Fixed values counted once on this branch: 5 updateLook quantities,
3 ghostAboveTrap exits, entry between capture share 0.96 and 0.98 with the shipped mesh and values (measured 0.971 on
the Ghost.mesh of the content package creatures, top 1.345; 0.94 to 0.96 on the former mesh).

Ghost.mesh is content (core-models package, found through scripts/content_packages.py). Without it the production
predicates are read and their fixed cases without a mesh are run; the beam step over the mesh is named as not checked.
"""
from pathlib import Path
import importlib.util
import re
import sys

repo = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo / 'scripts'))
import content_packages  # noqa: E402

#: True when the shipped ghost mesh is in the public tree or in a content package
GHOST_MESH = content_packages.data_file(repo, 'models/Ghost.mesh') is not None


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


def code_only(text):
    """Removes line comments."""
    return re.sub(r'//[^\n]*', '', text)


def split_ternary(expression):
    """Turns the top-level C++ conditional `a ? b : c` into a Python conditional expression."""
    depth = 0
    question = None
    for index, char in enumerate(expression):
        depth += char in '(' and 1 or 0
        depth -= char in ')' and 1 or 0
        if char == '?' and depth == 0 and question is None:
            question = index
        elif char == ':' and depth == 0 and question is not None and expression[index - 1] != ':' and \
                (index + 1 >= len(expression) or expression[index + 1] != ':'):
            condition, yes, no = expression[:question], expression[question + 1:index], expression[index + 1:]
            return '((%s) if (%s) else (%s))' % (python(yes), python(condition), python(no))
    return None


def python(expression, names=None):
    """Translates one C++ expression of the predicates into Python; unknown names fail at evaluation."""
    for old, new in (names or {}).items():
        expression = expression.replace(old, new)
    ternary = split_ternary(expression.strip())
    if ternary is not None:
        return ternary
    expression = re.sub(r'(\d)f\b', r'\1', expression)
    expression = re.sub(r'static_cast<[^>]+>', '', expression)
    expression = expression.replace('std::max', 'max').replace('std::min', 'min')
    expression = expression.replace('&&', ' and ').replace('||', ' or ')
    expression = re.sub(r'!(?!=)', ' not ', expression)
    expression = expression.replace('nullptr', 'None').replace('true', 'True').replace('false', 'False')
    return ' '.join(expression.split())


def evaluate(expression, values, names=None):
    """Evaluates a translated C++ expression with only the given fixture values."""
    return eval(python(expression, names), {'__builtins__': {'max': max, 'min': min}}, dict(values))


def statements(text):
    """Splits a function body into its top-level statements."""
    result, depth, current = [], 0, ''
    for char in code_only(text):
        depth += (char == '(') - (char == ')')
        if char == ';' and depth == 0:
            result.append(' '.join(current.split()))
            current = ''
        else:
            current += char
    return result


# --- the ghost in the beam: GhostEntity::updateLook ------------------------------------------------------------------
# config/rooms.cfg is a mixed table: read as the game reads it, with its own rows from the content
config = dict(re.findall(r'^(\w+)\s+([-0-9.]+)\s*$', content_packages.read_text(repo, 'config/rooms.cfg'), re.M))
look = body(read('source/entities/GhostEntity.cpp'), 'void GhostEntity::updateLook()')
look = look[:look.index('node->setPosition(')]
height = float(re.search(r'float height = ([0-9.]+)f;', look).group(1))
assert 'if(mState == GhostState::rising)' in look, 'only a rising ghost changes the float height'
quantities = re.findall(r'const double (\w+) = (.*?);', code_only(look), re.S)
assert [name for name, _ in quantities] == ['duration', 'progress', 'capture', 'minScale', 'pullStart', 'shrink', 'scale',
                                           'pull', 'sink'], quantities
GHOST_NAMES = {'config.getRoomConfigDouble(': 'room(', 'mCaptureProgress': 'capture_progress'}


def ghost_top(capture_progress, floor, mesh_top):
    """Top of the ghost's world bounds for one capture share, from the production updateLook quantities."""
    values = {'room': lambda key: float(config[key]), 'capture_progress': capture_progress, 'height': height}
    for name, expression in quantities:
        if name in ('duration', 'progress'):
            continue
        values[name] = evaluate(expression, values, GHOST_NAMES)
    assert values['scale'] > 0.0
    # The node sits at mPosition plus the sink and carries the uniform scale; the entity is the mesh on that node.
    return floor + values['sink'] + values['scale'] * mesh_top


if GHOST_MESH:
    spec = importlib.util.spec_from_file_location('ghost_meshes', repo / 'source/tests/check_ghost_apparatus_visible.py')
    meshes = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(meshes)
    mesh_bottom, mesh_top = meshes.read_mesh('Ghost')['bounds'][2], meshes.read_mesh('Ghost')['bounds'][5]
    assert mesh_top > 0.0 > mesh_bottom - 1.0, (mesh_bottom, mesh_top)
ghost = read('source/entities/GhostEntity.cpp')
assert 'setMeshName("Ghost");' in ghost and 'mPosition.z = 0.0f;' in ghost, 'every ghost is the Ghost mesh on the floor'

# --- the cannon: ghostAboveTrap and updateGhostHuntVisuals -----------------------------------------------------------
creature = read('source/entities/Creature.cpp')
above_body = statements(body(creature, 'static bool ghostAboveTrap('))
assert len([s for s in above_body if s.startswith('if(') or s.startswith('return')]) == 3, above_body
ABOVE_NAMES = {'static_cast<const GhostEntity&>(ghost).getState()': 'state', 'GhostState::beamed': '"beamed"',
               'scene->hasEntity(name)': 'has_entity', 'bounds.isFinite()': 'finite',
               'bounds.getMaximum().z': 'top', 'ghost.getPosition().z': 'floor'}


def ghost_above_trap(values):
    """Runs the production ghostAboveTrap statements on one fixture."""
    for statement in above_body:
        if statement.startswith('if('):
            depth, index = 0, 2
            for index in range(2, len(statement)):
                depth += (statement[index] == '(') - (statement[index] == ')')
                if depth == 0:
                    break
            condition, rest = statement[3:index], statement[index + 1:].strip()
            assert rest.startswith('return '), statement
            if evaluate(condition, values, ABOVE_NAMES):
                return evaluate(rest[len('return '):], values, ABOVE_NAMES)
        elif statement.startswith('return '):
            return evaluate(statement[len('return '):], values, ABOVE_NAMES)
        else:
            assert re.match(r'const (std::string name|Ogre::AxisAlignedBox bounds)=', statement), statement
    raise AssertionError('ghostAboveTrap has no final return')


visuals = body(creature, 'void Creature::updateGhostHuntVisuals(')
beaming_expression = re.search(r'const bool beaming=(.*?);', visuals).group(1)
clip_stop = re.search(r'if\((!beaming[^\n]*?)\)\s*\n\s*setAnimationState\(EntityAnimation::idle_anim,', visuals).group(1)
cleanup = re.search(r'\n    if\(([^\n]*)\)\n    \{\n((?:        [^\n]*\n)+?)        return;\n    \}', visuals[visuals.index(
    'mGhostPose!=nullptr'):])
assert cleanup, 'teardown of the beam effects'
for teardown in ('stopSpatialLoop(mGhostBeamSound)', 'destroyParticleSystem(mGhostBeamSparks)',
                 'destroyBillboardSet(mGhostBeamImpact)', 'destroyBillboardChain(mGhostBeamChain)'):
    assert teardown in cleanup.group(2), teardown
# Every consumer of the cannon follows the same flag: holster, hand, aim, hose end and own weapons.
for consumer in ('mGhostCaptureGun->setVisible(beaming);', 'mGhostPackGun->setVisible(!beaming);', 'if(beaming) aimGhostCannon(',
                 'Ogre::Entity* hoseGun=beaming?mGhostCaptureGun:mGhostPackGun;'):
    assert consumer in visuals, consumer
BEAM_NAMES = {'target!=nullptr': 'has_target', 'mGhostBoxMode': 'box_mode', 'ghostAboveTrap(scene,*target)': 'above()'}
CLIP_NAMES = {'getAnimationStateName()==EntityAnimation::beam_anim': 'animation=="beam_anim"'}


def frame(capture, floor, expression=beaming_expression, box_mode=3, state='beamed', has_target=True):
    """Runs one client frame of the cannon: whether it beams, whether the clip is reset, whether effects are torn down."""
    top = ghost_top(capture, floor, mesh_top)
    above = lambda: ghost_above_trap({'state': state, 'has_entity': True, 'finite': True, 'top': top, 'floor': floor})
    beaming = evaluate(expression, {'has_target': has_target, 'box_mode': box_mode, 'above': above}, BEAM_NAMES)
    reset = evaluate(clip_stop, {'beaming': beaming, 'animation': 'beam_anim'}, CLIP_NAMES)
    torn_down = evaluate(cleanup.group(1), {'beaming': beaming, 'target': object() if has_target else None,
                                           'mGhostBeamTarget': type('Name', (), {'empty': lambda self: not has_target})()})
    return beaming, reset, torn_down, top


# --- the outcome over the whole beam step ----------------------------------------------------------------------------
if GHOST_MESH:
    SAMPLES = 1000
    for floor in (0.0, 1.0, 5.0):
        previous = True
        stopped_at = None
        for step in range(SAMPLES + 1):
            capture = step / SAMPLES
            beaming, reset, torn_down, top = frame(capture, floor)
            assert beaming == (top > floor), (floor, capture, top, 'the cannon fires exactly while the ghost shows above the trap')
            assert reset == (not beaming), 'the Beam clip goes back to Idle the frame the cannon stops'
            assert torn_down == (not beaming), 'sound, sparks, glow and lightning end with the beam'
            assert previous or not beaming, (floor, capture, 'the cannon never resumes during the rest of the pull')
            if not beaming and stopped_at is None:
                stopped_at = capture
            previous = beaming
        assert frame(0.0, floor)[0], 'the cannon fires at the start of the beam step'
        assert stopped_at is not None and 0.96 < stopped_at < 0.98, (floor, stopped_at, 'stops at entry, before the snap')
        # The trap is still open at that moment: the server ends the beam step only at a capture share of 1
        assert stopped_at < 1.0
        # The old predicate kept the cannon on the ghost for the whole step, also after the ghost was inside the trap.
        assert frame(stopped_at, floor, expression='target!=nullptr')[0], 'the lost behaviour is told apart'

    # No other moment of the hunt shows the cannon firing: no target, another box state, a ghost that is no longer beamed.
    for capture in (0.0, 0.5, 0.9):
        assert not frame(capture, 0.0, has_target=False)[0]
        for box_mode in (0, 1, 2, 4, 5, 6, 7):
            assert not frame(capture, 0.0, box_mode=box_mode)[0], box_mode
        for state in ('rising', 'floating', 'boxed', 'dissolving'):
            assert not frame(capture, 0.0, state=state)[0], state
# A ghost without a drawn body yet keeps the cannon on it (the trap lies below it); invalid bounds do too.
assert ghost_above_trap({'state': 'beamed', 'has_entity': False, 'finite': True, 'top': 0.0, 'floor': 0.0})
assert ghost_above_trap({'state': 'beamed', 'has_entity': True, 'finite': False, 'top': -1.0, 'floor': 0.0})
if not GHOST_MESH:
    content_packages.unchecked('check_ghost_cannon_stop', ['models/Ghost.mesh (beam step over the mesh)'])
    print('ghost cannon predicates read, fixed cases without a mesh: ok')
else:
    print('ghost cannon stops at trap entry: 3 floors x 1001 frames, clip and effects follow, old predicate told apart: ok')
