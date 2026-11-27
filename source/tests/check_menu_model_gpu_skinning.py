"""Check that the animated menu models are skinned on the GPU. It does not start a game.

Cause 1 of the slow frames, menu part: banners, crows, cages, chained dead, the title plaque and the wall hooks use
RTSS materials that are shared with static meshes, so Lena's creature shaders do not apply to them and Ogre skinned them
on the CPU (74.5 percent of the menu frame). RenderManager::useShaderSkinning gives each sub entity its own copy of the
material with the RTSS hardware skinning stage, then lets HardwareSkinningFactory::prepareEntityForSkinning read the
bone and weight counts. This check follows that chain without a build.

The material scripts and the menu meshes live in content packages (found through scripts/content_packages.py); the
meshes are read from the public models/ and the package folders. Without the content the check names the material and
mesh part as not checked and checks the code.
"""
from pathlib import Path
import re
import sys

repo = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo / 'scripts'))
import content_packages  # noqa: E402

WITH_CONTENT = content_packages.has_content(repo)
# Parts that need the content and are not checked because it is not present
not_checked = []
render = (repo / 'source/render/RenderManager.cpp').read_text(encoding='utf-8')
header = (repo / 'source/render/RenderManager.h').read_text(encoding='utf-8')

assert 'bool useShaderSkinning(Ogre::Entity* entity);' in header
assert '#include <RTShaderSystem/OgreShaderExHardwareSkinning.h>' in render

start = render.index('bool RenderManager::useShaderSkinning(Ogre::Entity* entity)')
body = render[start:render.index('Adds a menu point light with its own scene node', start)]

# The stage is stored per material, so it must never be added to the shared original
assert 'material->clone(copyName)' in body
assert 'SRS_HARDWARE_SKINNING' in body and 'addTemplateSubRenderState' in body
assert 'createShaderBasedTechnique(*copy' in body and 'cloneShaderBasedTechniques(*material, *copy)' in body
assert 'prepareEntityForSkinning(entity)' in body
assert body.index('setMaterial(skinned[index])') < body.index('prepareEntityForSkinning(entity)'), \
    'the bone counts must be read from the copies'
# Ogre skins an entity on the GPU only if all sub entities are; materials with their own programs are refused up front
assert 'hasVertexProgram()' in body
assert body.index('hasVertexProgram()') < body.index('material->clone(copyName)')
# The menu display stage (MenuDisplayShading.cpp) selects materials by the prefix "Menu" of their name
shading = (repo / 'source/render/MenuDisplayShading.cpp').read_text(encoding='utf-8')
assert 'MENU_MATERIAL_PREFIX = "Menu"' in shading
assert 'material->getName() + SHADER_SKINNING_INFIX' in body, 'the copy must keep the name of the original as prefix'
# "@@", "##" and "_alpha_" are parsed out of material names by the colour and outline code
infix = re.search(r'SHADER_SKINNING_INFIX = "([^"]+)"', render).group(1)
assert not any(mark in infix for mark in ('@@', '##', '_alpha_', '_item_'))
# A skinned entity needs a skinning shadow caster
assert 'setCustomShadowCasterMaterials(Ogre::RTShader::ST_LINEAR' in body
if content_packages.data_file(repo, 'materials/scripts/CreatureSkinning.material') is None and not WITH_CONTENT:
    not_checked.append('materials/scripts/CreatureSkinning.material')
else:
    assert 'material CreatureShadowCaster' in content_packages.read_text(repo, 'materials/scripts/CreatureSkinning.material')

# The menu entities call it
menu = render[render.index('Ogre::Entity* RenderManager::addEntityMenu('):]
menu = menu[:menu.index('void RenderManager::removeEntityMenu')]
assert 'useShaderSkinning(ent);' in menu
assert menu.index('createEntity(entityName, meshPtr)') < menu.index('useShaderSkinning(ent);') < menu.index('attachObject(ent)')

# The skinned menu models and their materials: none of them may use a vertex program (only the sky does)
if content_packages.data_file(repo, 'materials/scripts/MenuScene.material') is None and not WITH_CONTENT:
    not_checked.append('materials/scripts/MenuScene.material and the skinned menu meshes')
else:
    scene = content_packages.read_text(repo, 'materials/scripts/MenuScene.material')
    sky_materials = set()
    for block in re.split(r'(?m)^(?=material\s)', scene):
        name = re.match(r'material\s+(\S+)', block)
        if name and 'vertex_program_ref' in block:
            sky_materials.add(name.group(1))
    # the menu meshes of the public models/ and of the content packages
    skinned = [path for path in content_packages.data_glob(repo, 'models', 'Menu*.mesh') if b'.skeleton' in path.read_bytes()]
    assert len(skinned) >= 14, 'expected the banners, crows, cages, chained dead, plaque and hooks'
    for path in skinned:
        used = set(re.findall(rb'Menu[A-Za-z0-9_]*', path.read_bytes()))
        clash = sky_materials & {name.decode() for name in used}
        assert not clash, '%s uses a material with its own vertex program: %s' % (path.name, clash)
content_packages.unchecked('check_menu_model_gpu_skinning', not_checked)
print('ok')
