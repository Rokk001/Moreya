"""Wiring check: the creature highlight is a thin contour only and the creature keeps its normal colours."""
from pathlib import Path

repo = Path(__file__).resolve().parents[2]


def read(path):
    return (repo / path).read_text(encoding='utf-8')


render = read('source/render/RenderManager.cpp')
vert = read('shaders/Enlarge.vert')

# The contour copy is made in getOutlinerMaterial(); rrAddOutliner() puts it on every sub entity
body = render.split('Ogre::MaterialPtr RenderManager::getOutlinerMaterial')[1].split('void RenderManager::rrRemoveOutliner')[0]
# The extra pass draws only the back faces of a shell behind the model, so the model hides all of it but the rim.
assert 'setCullingMode(Ogre::CULL_ANTICLOCKWISE)' in body
# X1 rework (E9): the bias must push the shell away from the camera (negative), a positive bias filled the creature red
assert 'setDepthBias(-4.0f, -32.0f)' in body and 'setDepthBias(1.0f, 1.0f)' not in body
# X1 rework 3 (E9, decision 710): the contour is a constant number of SCREEN pixels, not a world-space offset. A world
# offset (0.012 of the mesh size) was as thick as thin parts (skeleton bones, wing membranes, spider legs) and huge in
# close-ups, which drew the creature filled red.
assert 'setNamedConstant("pixelWidth"' in body and 'OutlinerContourPixels' in body
assert 'ACT_VIEWPORT_SIZE' in body and 'ACT_VIEW_MATRIX' in body and 'ACT_VIEWPROJ_MATRIX' in body
assert 'OutlinerContourWidthFactor' not in render and 'getBounds().getSize()' not in body
px = float(render.split('OutlinerContourPixels = ')[1].split('f;')[0])
assert 0.5 <= px <= 2.5, px
assert 'uniform    float pixelWidth;' in vert and 'uniform    vec4 viewportSize;' in vert
assert 'clip.xy += dir * pixelWidth * 2.0 * viewportSize.zw * clip.w' in vert
assert 'normalize(normal.xyz) * width' not in vert and 'position.xyz +' not in vert and 'blendIndices' in vert
# Every sub-entity of every creature gets the pass (no creature type is skipped) and it is added to a clone only.
assert 'getNumSubEntities()' in body and '->clone(outlinerName,"Graphics")' in body
# INGAME-QS-12 K12: no creature carries the seat-colour outline while it is not under the cursor.
creature = read('source/entities/Creature.cpp')


def function_body(text, signature):
    """Returns the text of the function that starts with signature, up to the next function at column 0."""
    start = text.index(signature)
    end = text.index(chr(10) + '}', start)
    return text[start:end]


# A created creature (every seat takes this path) and a re-meshed creature get no outliner material.
created = function_body(render, 'void RenderManager::rrCreateCreature(')
remeshed = function_body(render, 'void RenderManager::rrChangeCreatureMesh(')
for body_text in (created, remeshed):
    assert 'showOutliner' not in body_text and 'rrAddOutliner' not in body_text and 'getOutlinerMaterial' not in body_text
assert 'showOutliner()' not in render
# Nothing else outside the hover path puts the contour on a creature.
assert creature.count('showOutliner();') == 1
# The creature under the cursor gets the K7 contour (outliner copy, then its brightened hover copy) ...
hover_on = function_body(creature, 'void Creature::maxAmbient()')
assert hover_on.index('showOutliner();') < hover_on.index('rrIncreaseAmbient(this)')
# ... and loses it again when the pointer leaves: hover copy first, then the contour copy.
hover_off = function_body(creature, 'void Creature::normalizeAmbient()')
assert hover_off.index('rrNormalizeAmbient(this)') < hover_off.index('removeOutliner();')
# Taking the marker off a creature that has none (new entity while hovered) is silent and leaves its material alone.
remove = function_body(render, 'void RenderManager::rrRemoveOutliner(')
assert 'continue;' in remove and 'Called rrRemoveOutliner' not in remove
normalize = function_body(render, 'void RenderManager::rrNormalizeAmbient(')
assert 'continue;' in normalize and 'Called rrRemoveBrighter' not in normalize
print('ok')
