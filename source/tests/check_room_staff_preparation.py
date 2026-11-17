"""Check that the room staff figures are loaded during the map load, not in the frame their room is first built.

Measured cause (INGAME-QS-10 P1): when the first Tavern was built in the owner session of 2026-11-17 (16:39:20) the
client message "addEntity" took 203 ms and the next two frames 161 ms and 107 ms in the presentation: the frame loaded
the Innkeeper mesh (18 MB, about 249k triangles at that time), built its tangents, made its skinning materials and
compiled their shaders. The merchant, the pool attendant and the infirmary shaman appear the same way with their room.

The check reads the production sources and the models and requires:
- RenderManager::initGameRenderer calls prepareRoomStaffResources() during the map load, after the creature
  preparation and before the game shaders, so it runs behind the loading screen;
- the prepared mesh list is exactly the meshes the four staff entity classes create (read from their constructors),
  and every one of them exists in models/;
- prepareRoomStaffResources does every step rrCreateRenderedMovableEntity does for such a figure on first appearance
  (mesh load in group Graphics, tangents with the same fallback, useShaderSkinning on an entity of the mesh, generated
  shaders of each material) and destroys its temporary entity on success and on an exception, so nothing is drawn.

Fixed values of this branch: 4 staff meshes (Innkeeper, Merchant, PoolAttendant, InfirmaryShaman). The check compiles
nothing and starts no game.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]


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


def check(render_manager):
    """Asserts the preparation contract on the given RenderManager.cpp text."""
    init = block(render_manager, 'void RenderManager::initGameRenderer(')
    assert init.count('prepareRoomStaffResources();') == 1
    assert (init.index('prepareGameCreatureResources(*gameMap);') < init.index('prepareRoomStaffResources();')
            < init.index('prepareGameShaders();'))

    listed = re.search(r'ROOM_STAFF_MESHES\[\] = \{([^}]*)\};', render_manager).group(1)
    listed = re.findall(r'"(\w+)"', listed)
    expected = staff_meshes()
    assert len(expected) == 4, expected
    assert sorted(listed) == sorted(expected), (listed, expected)
    for name in listed:
        assert (ROOT / 'models' / (name + '.mesh')).is_file(), name

    prepare = block(render_manager, 'void RenderManager::prepareRoomStaffResources(')
    create = block(render_manager, 'void RenderManager::rrCreateRenderedMovableEntity(')
    assert 'Ogre::MeshManager::getSingleton().load(meshName + ".mesh","Graphics")' in create
    assert 'Ogre::MeshManager::getSingleton().load(meshName, "Graphics");' in prepare
    assert 'std::string(staffFigure) + ".mesh"' in prepare
    for step in ('suggestTangentVectorBuildParams(src)', 'buildTangentVectors(src);',
                 'catch(const Ogre::ItemIdentityException&)'):
        assert step in create and step in prepare, step
    assert 'useShaderSkinning(ent);' in create
    order = [prepare.index(step) for step in ('MeshManager::getSingleton().load(', 'buildTangentVectors(src);',
                                               'mSceneManager->createEntity(mesh);', 'useShaderSkinning(entity);',
                                               'prepareGeneratedShaders(*part->getMaterial());')]
    assert order == sorted(order), order
    # The temporary entity is destroyed on success and when a step throws; it is never attached to a node.
    assert prepare.count('mSceneManager->destroyEntity(entity);') == 2
    assert 'catch(...)' in prepare and 'throw;' in prepare
    assert 'attachObject' not in prepare
    assert 'FrameStallTrace::Scope trace(FrameStallTrace::ResourcePreparation);' in prepare


def mutations(render_manager):
    """Each wrong preparation must be rejected by the contract."""
    wrong = [
        render_manager.replace('    prepareRoomStaffResources();\n', '', 1),
        render_manager.replace('"Innkeeper", ', '', 1),
        render_manager.replace('            useShaderSkinning(entity);\n', '', 1),
        render_manager.replace('        mSceneManager->destroyEntity(entity);\n        ++prepared;',
                               '        ++prepared;', 1),
    ]
    for index, text in enumerate(wrong):
        assert text != render_manager, index
        try:
            check(text)
        except (AssertionError, AttributeError, ValueError):
            continue
        raise AssertionError('mutation %d was not rejected' % index)


def main():
    """Runs the contract on the production source and the rejected mutations."""
    render_manager = read('source/render/RenderManager.cpp')
    check(render_manager)
    mutations(render_manager)
    print('room staff preparation passes the checks (4 meshes)')


if __name__ == '__main__':
    main()
