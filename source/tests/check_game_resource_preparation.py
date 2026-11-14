"""Guard loading-screen preparation of late creature and Tavern resources without launching or compiling the game."""
from pathlib import Path
import re

repo = Path(__file__).resolve().parents[2]
render = (repo / 'source/render/RenderManager.cpp').read_text(encoding='utf-8')


def body(signature):
    """Return a top-level function body, including its nested blocks."""
    start = render.index(signature)
    return render[start:render.index('\n}\n', start)]


# Creature classes absent at map load must prepare the same material names used by real entities.
init = body('void RenderManager::initGameRenderer(GameMap* gameMap)')
assert init.index('pinWorldShaderLights();') < init.index('prepareGameCreatureResources(*gameMap);')
assert init.index('prepareGameCreatureResources(*gameMap);') < init.index('prepareGameShaders();')
prepare = body('void RenderManager::prepareGameCreatureResources(GameMap& gameMap)')
assert 'ConfigManager::getSingleton().getCreatureDefinitions()' in prepare
assert 'gameMap.numClassDescriptions()' in prepare and 'gameMap.getClassDescription(i)' in prepare
assert 'std::set<std::string> meshNames;' in prepare and 'meshNames.insert("Chicken.mesh")' in prepare
assert prepare.index('load(meshName, "Graphics")') < prepare.index('suggestTangentVectorBuildParams(src)')
assert prepare.index('buildTangentVectors(src)') < prepare.index('createEntity(mesh)')
assert prepare.index('useSkinnedMetalMaterial(entity)') < prepare.index('entity->getSubEntities()')
assert 'preparedMaterials.insert(materialName).second' in prepare
assert prepare.index('prepareGeneratedShaders(*part->getMaterial())') < prepare.index('prepareOutlinerMaterials(materialName, gameMap)')
# Temporary entities never attach to the scene or enter the game state, including on failure.
assert 'attachObject' not in prepare and 'createChildSceneNode' not in prepare
assert 'catch(...)' in prepare and 'throw;' in prepare
assert prepare.count('mSceneManager->destroyEntity(entity);') == 2
assert render.count('prepareGameCreatureResources(*gameMap);') == 1
seats = body('void RenderManager::prepareOutlinerMaterials(const std::string& materialName, const GameMap& gameMap)')
assert 'gameMap.getSeats()' in seats and 'getBrighterMaterial(outliner->getName())->load();' in seats
brighter = body('Ogre::MaterialPtr RenderManager::getBrighterMaterial(')
# Chicken has RTSS base passes and a custom contour pass. Only passes exposing ambient can be brightened.
assert re.search(r'if\(!pass->hasFragmentProgram\(\)\)\s+continue;\s+'
                 r'Ogre::GpuProgramParametersSharedPtr parameters = pass->getFragmentProgramParameters\(\);\s+'
                 r'if\(parameters->_findNamedConstantDefinition\("ambient", false\) != nullptr\)\s+'
                 r'parameters->setNamedConstant\("ambient",', brighter)

# A generated Chicken pass may lack an ambient uniform. Preloading its hover variant must keep that pass usable.
brighter = body('Ogre::MaterialPtr RenderManager::getBrighterMaterial(const std::string& materialName)')
assert brighter.index('if(!pass->hasFragmentProgram())') < brighter.index('pass->getFragmentProgramParameters()')
assert 'if(parameters->_findNamedConstantDefinition("ambient", false) != nullptr)\n' \
       '                parameters->setNamedConstant("ambient", Ogre::ColourValue(8.0, 8.0, 8.0));' in brighter

# Tavern floors and furnishings load textures and shaders before their first construction during play.
prefixes = render.split('GAME_EFFECT_MATERIAL_PREFIXES[] = {', 1)[1].split('}', 1)[0]
assert '"Tavern"' in prefixes
effects = body('void RenderManager::prepareGameShaders()')
assert 'hasPrefix(name, GAME_EFFECT_MATERIAL_PREFIXES)' in effects
assert 'prepareGeneratedShaders(*material)' in effects
generated = body('void RenderManager::prepareGeneratedShaders(Ogre::Material& material)')
assert generated.index('material.load();') < generated.index('createShaderBasedTechnique') < generated.index('validateMaterial')
print('ok')
