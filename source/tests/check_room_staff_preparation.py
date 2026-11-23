"""Check that the room staff figures are loaded during the map load, not in the frame their room is first built.

Measured cause (INGAME-QS-10 P1): when the first Tavern was built in the owner session of 2026-11-17 (16:39:20) the
client message "addEntity" took 203 ms and the next two frames 161 ms and 107 ms in the presentation: the frame loaded
the Innkeeper mesh (18 MB, about 249k triangles at that time), built its tangents, made its skinning materials and
compiled their shaders. The merchant, the pool attendant and the infirmary shaman appear the same way with their room.

The staff figures are prepared with all other objects by RenderManager::prepareGameObjectResources from
config/preparedobjects.cfg (whole mechanism: check_game_object_preparation.py). This check requires for the staff:
- the mesh each of the four staff entity classes creates (read from their constructors) is listed in
  config/preparedobjects.cfg and exists in models/;
- RenderManager::initGameRenderer calls prepareGameObjectResources() during the map load, after the creature
  preparation and before the game shaders, so it runs behind the loading screen;
- the preparation does every step rrCreateRenderedMovableEntity does for such a figure on first appearance (mesh load
  in group Graphics, tangents with the same fallback, useShaderSkinning on an entity of the mesh, generated shaders of
  each material) and destroys its temporary entity, so nothing is drawn.

Fixed values of this branch: 4 staff meshes (Innkeeper, Merchant, PoolAttendant, InfirmaryShaman). The check compiles
nothing and starts no game.
"""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import room_packages  # noqa: E402


def mesh_exists(name):
    """True when the mesh is in models/ of the game data or of a present room package; a mesh of a room package that is
    not present counts as there (only the list and the code are checked then)."""
    relative = 'models/' + name
    return room_packages.asset(ROOT, relative) is not None or room_packages.is_missing_packaged(ROOT, relative)


def read(path):
    """Returns the text of a repository file."""
    return (ROOT / path).read_text(encoding='utf-8')


def block(source, signature):
    """Returns the production text from the signature to the end of its braces block, unchanged."""
    start = source.index(signature)
    end = source.index('{', start) + 1
    depth = 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


def staff_meshes():
    """Returns the mesh name each staff entity class gives its figure, from the class sources."""
    names = []
    innkeeper = read('source/entities/InnkeeperEntity.cpp')
    names.append(re.search(r'const std::string InnkeeperEntity::MESH_NAME = "(\w+)";', innkeeper).group(1))
    merchant = read('source/entities/MerchantEntity.cpp')
    names.append(re.search(r'RenderedMovableEntity\(map, "\w+", "(\w+)", 0\.0f, false\)', merchant).group(1))
    attendant = read('source/entities/PoolAttendantEntity.cpp')
    names.append(re.search(r'const std::string PoolAttendantEntity::MESH_NAME = "(\w+)";', attendant).group(1))
    shaman = read('source/entities/InfirmaryShamanEntity.cpp')
    names.append(re.search(r'RenderedMovableEntity\(map, roomName, "(\w+)", 0\.0f, false\)', shaman).group(1))
    return names


def listed(text):
    """Returns the mesh names of a preparedobjects.cfg text, comments removed."""
    names = []
    for line in text.splitlines():
        words = line.split('#', 1)[0].split()
        if words:
            names.append(words[0])
    return names


def check(render_manager, objects):
    """Asserts the staff part of the preparation on the given RenderManager.cpp and preparedobjects.cfg texts."""
    expected = staff_meshes()
    assert len(expected) == 4, expected
    names = listed(objects)
    for name in expected:
        assert name + '.mesh' in names, name
        assert mesh_exists(name + '.mesh'), name

    init = block(render_manager, 'void RenderManager::initGameRenderer(')
    assert init.count('prepareGameObjectResources();') == 1
    assert (init.index('prepareGameCreatureResources(*gameMap);') < init.index('prepareGameObjectResources();')
            < init.index('prepareGameShaders();'))

    prepare = block(render_manager, 'void RenderManager::prepareGameObjectResources(')
    create = block(render_manager, 'void RenderManager::rrCreateRenderedMovableEntity(')
    assert 'Ogre::MeshManager::getSingleton().load(meshName + ".mesh","Graphics")' in create
    assert 'Ogre::MeshManager::getSingleton().load(objectFile, "Graphics");' in prepare
    for step in ('suggestTangentVectorBuildParams(src)', 'buildTangentVectors(src);',
                 'catch(const Ogre::ItemIdentityException&)'):
        assert step in create and step in prepare, step
    assert 'useShaderSkinning(ent);' in create
    order = [prepare.index(step) for step in ('MeshManager::getSingleton().load(', 'buildTangentVectors(src);',
                                               'mSceneManager->createEntity(mesh);', 'useShaderSkinning(entity);',
                                               'prepareGeneratedShaders(*part->getMaterial());',
                                               'mSceneManager->destroyEntity(entity);')]
    assert order == sorted(order), order
    assert 'attachObject' not in prepare


def mutations(render_manager, objects):
    """Each wrong preparation must be rejected by the contract."""
    wrong = [
        (render_manager.replace('    prepareGameObjectResources();\n', '', 1), objects),
        (render_manager, objects.replace('Innkeeper.mesh\n', '', 1)),
        (render_manager.replace('            useShaderSkinning(entity);\n', '', 1), objects),
        (render_manager.replace('        if(entity != nullptr)\n            mSceneManager->destroyEntity(entity);\n', '', 1),
         objects),
    ]
    for index, (source, config) in enumerate(wrong):
        assert (source, config) != (render_manager, objects), index
        try:
            check(source, config)
        except (AssertionError, AttributeError, ValueError):
            continue
        raise AssertionError('mutation %d was not rejected' % index)


def main():
    """Runs the contract on the production source and the rejected mutations."""
    render_manager = read('source/render/RenderManager.cpp')
    objects = read('config/preparedobjects.cfg')
    check(render_manager, objects)
    mutations(render_manager, objects)
    print('room staff preparation passes the checks (4 meshes)')


if __name__ == '__main__':
    main()
