"""Check that every object the game creates during play is prepared during the map load (frame stall cause: first use).

Measured cause (INGAME-QS-10 P1, deployed build 2026-11-17): an object type that appeared for the first time during
play was loaded in that frame: mesh file, tangents, skinning materials, textures and generated shaders. Frame stall
lines: 116 ms in the render targets when the first chicken egg appeared (P1 run, 18:25:54), 87 ms "addEntity"
(spiders and gold, owner 17:46:53), 203 ms plus 161/107 ms for the first Tavern (owner 16:39:20). Only creatures,
effect and Tavern materials were prepared before.

Now RenderManager::prepareGameObjectResources loads every mesh listed in config/preparedobjects.cfg during the map load.
1. Coverage (no compiler): the mesh references of the object code and object configs, found with the reference
   extractor of check_asset_references.py (source/rooms, entities, traps, spells, render, modes, gamemap, utils and
   config/roomAmbience*.cfg, creatureSkills.cfg, equipments.cfg; menu meshes and the creature meshes of creatures.cfg,
   which prepareGameCreatureResources prepares, excluded) are all listed, every listed mesh exists in models/, no mesh is
   listed twice, and the list has exactly 221 meshes (183 objects of the code and configs, 38 dirt piles of the
   creature classes, DirtPileEntity::PILE_MESH_PREFIX). A new object mesh in the code without a list entry fails here.
2. Wiring (no compiler): initGameRenderer prepares the objects after the creatures and before the game shaders; the
   preparation does the steps of rrCreateRenderedMovableEntity, never attaches its temporary entity, destroys it, and
   reports a mesh it cannot prepare instead of stopping the map load.
3. Rejected stalls of build 61 (no compiler): BloodStain and GoblinBed, the first objects of the two rejected
   minutes, are listed, and the contour/hover copies made in those minutes are prepared for every creature and seat.
4. Parsing (compiled probe of the production readPreparedObjectMeshes): the game reads exactly the 221 names from the
   real file, in file order, comments ignored.

Fixed values of this branch: 221 listed meshes. Part 4 compiles with cl, so it runs in the compile phase of the
integration only (--no-probe skips it).
"""
from pathlib import Path
import importlib.util
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
LISTED = 223
OBJECT_SOURCES = ('source/rooms/', 'source/entities/', 'source/traps/', 'source/spells/', 'source/render/',
                  'source/modes/', 'source/gamemap/', 'source/utils/')
OBJECT_CONFIGS = ('config/roomAmbience', 'config/creatureSkills', 'config/equipments')


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


def listed():
    """Returns the mesh names of config/preparedobjects.cfg in file order, comments removed."""
    names = []
    for line in read('config/preparedobjects.cfg').splitlines():
        words = line.split('#', 1)[0].split()
        if words:
            names.append(words[0])
    return names


def referenced():
    """Returns the object meshes the code and the object configs name, with the extractor of the asset check."""
    spec = importlib.util.spec_from_file_location('asset_references', ROOT / 'source/tests/check_asset_references.py')
    references = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(references)
    assets = references.inventory(ROOT)
    refs = (references.data_references(ROOT) | references.cpp_references(ROOT, assets)
            | references.finite_name_references(ROOT))
    creatures = set(re.findall(r'^\s*MeshName\s+(\S+)', read('config/creatures.cfg'), re.M))
    pile_prefix = re.search(r'PILE_MESH_PREFIX = "([^"]+)";', read('source/entities/DirtPileEntity.cpp')).group(1)
    names = set()
    for ref in refs:
        if ref.kind == 'mesh' and (ref.path.startswith(OBJECT_SOURCES) or ref.path.startswith(OBJECT_CONFIGS)):
            names.add(ref.name)
        # The dirt pile of a creature class (DirtPileEntity::PILE_MESH_PREFIX + class name) is an object, too.
        if ref.kind == 'mesh' and ref.name.startswith(pile_prefix):
            names.add(ref.name)
    return {name for name in names
            if (ROOT / 'models' / name).is_file() and not name.startswith('Menu') and name not in creatures}


def coverage():
    """Part 1: the list holds every object mesh the game can create, and only existing meshes."""
    names = listed()
    assert len(names) == LISTED, len(names)
    assert len(set(names)) == len(names), 'a mesh is listed twice'
    for name in names:
        assert (ROOT / 'models' / name).is_file(), name
    missing = sorted(referenced() - set(names))
    assert not missing, 'object meshes not prepared: %s' % missing
    for figure in ('ChickenEgg.mesh', 'Innkeeper.mesh', 'TavernCounter.mesh', 'SmallSpider.mesh', 'GoldstackLv1.mesh'):
        assert figure in names, figure


def rejected_stalls(render_manager):
    """The first-use work of the two stalls the owner rejected in build 61 (367.97 ms in the minute to 18:44:39,
    780.06 ms in the minute to 18:45:39 of 2026-11-11) is done during the map load: the first BloodStain and the first
    GoblinBed of that session are listed objects, and the contour and hover copies created then (Kobold green, Roach
    red, "couldn't find ... cloning") are made for every configured creature and every seat before play."""
    names = listed()
    for figure in ('BloodStain.mesh', 'GoblinBed.mesh'):
        assert figure in names, figure
    creatures = block(render_manager, 'void RenderManager::prepareGameCreatureResources(')
    assert 'ConfigManager::getSingleton().getCreatureDefinitions()' in creatures
    assert 'prepareOutlinerMaterials(materialName, gameMap);' in creatures
    outliner = block(render_manager, 'void RenderManager::prepareOutlinerMaterials(')
    assert 'for(const Seat* seat : gameMap.getSeats())' in outliner
    assert 'getOutlinerMaterial(materialName, seat->getColorValue());' in outliner
    assert 'getBrighterMaterial(outliner->getName())->load();' in outliner
    init = block(render_manager, 'void RenderManager::initGameRenderer(')
    assert init.index('prepareGameCreatureResources(*gameMap);') < init.index('prepareGameObjectResources();')


def wiring(render_manager):
    """Part 2: the preparation runs during the map load and never stops it or draws anything."""
    init = block(render_manager, 'void RenderManager::initGameRenderer(')
    assert init.count('prepareGameObjectResources();') == 1
    assert (init.index('prepareGameCreatureResources(*gameMap);') < init.index('prepareGameObjectResources();')
            < init.index('prepareGameShaders();'))
    assert 'static const std::string PREPARED_OBJECTS_FILE = "preparedobjects.cfg";' in render_manager
    prepare = block(render_manager, 'void RenderManager::prepareGameObjectResources(')
    assert 'readPreparedObjectMeshes()' in prepare
    for step in ('Ogre::MeshManager::getSingleton().load(objectFile, "Graphics");', 'buildTangentVectors(src);',
                 'catch(const Ogre::ItemIdentityException&)', 'mSceneManager->createEntity(mesh);',
                 'useShaderSkinning(entity);', 'prepareGeneratedShaders(*part->getMaterial());',
                 'catch(const Ogre::Exception& exception)', 'mSceneManager->destroyEntity(entity);'):
        assert step in prepare, step
    assert 'attachObject' not in prepare and 'throw;' not in prepare


PROBE_PREAMBLE = r'''
#include <cassert>
#include <cstdio>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

#define OD_LOG_WRN(_message) std::printf("%s\n", (std::string("") + _message).c_str())
struct ResourceManager
{
    static ResourceManager& getSingleton() { static ResourceManager manager; return manager; }
    std::string getConfigPath() const { return CONFIG_PATH; }
    static const char* CONFIG_PATH;
};
'''

PROBE_MAIN = r'''
int main(int argc, char** argv)
{
    std::vector<std::string> expected;
    std::ifstream names(argv[1]);
    std::string name;
    while(std::getline(names, name))
        expected.push_back(name);
    const std::vector<std::string> read = readPreparedObjectMeshes();
    assert(read == expected);
    assert(read.size() == LISTED);
    std::printf("the game reads %u object meshes\n", static_cast<unsigned int>(read.size()));
    (void)argc;
    return 0;
}
'''


def probe(render_manager):
    """Part 3: compiles the production list reader against the real config file and compares the names."""
    reader = block(render_manager, 'static std::vector<std::string> readPreparedObjectMeshes()')
    constant = 'static const std::string PREPARED_OBJECTS_FILE = "preparedobjects.cfg";'
    config = (ROOT / 'config').as_posix() + '/'
    vcvars = Path('C:/Program Files (x86)/Microsoft Visual Studio/18/BuildTools/VC/Auxiliary/Build/vcvars64.bat')
    with tempfile.TemporaryDirectory() as directory:
        directory = Path(directory)
        expected = directory / 'expected.txt'
        expected.write_text('\n'.join(listed()) + '\n', encoding='utf-8')
        source = (PROBE_PREAMBLE + 'const char* ResourceManager::CONFIG_PATH = "%s";\n' % config
                  + 'static const size_t LISTED = %d;\n' % LISTED + constant + '\n' + reader + '\n' + PROBE_MAIN)
        cpp = directory / 'probe.cpp'
        cpp.write_text(source, encoding='utf-8')
        batch = directory / 'run.cmd'
        batch.write_text(
            f'@echo off\ncall "{vcvars}" >nul\n'
            f'cl /nologo /EHsc /std:c++14 "{cpp}" /Fe:"{directory / "probe.exe"}" '
            f'/Fo:"{directory / "probe.obj"}"\n'
            'if errorlevel 1 exit /b 1\n'
            f'"{directory / "probe.exe"}" "{expected}"\nexit /b %errorlevel%\n',
            encoding='utf-8',
        )
        subprocess.run(['cmd', '/d', '/c', str(batch)], cwd=directory, check=True)


def main():
    """Runs coverage and wiring, then the compiled reader probe unless --no-probe is given."""
    render_manager = read('source/render/RenderManager.cpp')
    coverage()
    wiring(render_manager)
    rejected_stalls(render_manager)
    print('game object preparation: %d meshes listed, all object meshes covered, wiring ok' % LISTED)
    if '--no-probe' in sys.argv:
        return
    probe(render_manager)
    print('game object preparation passes the checks')


if __name__ == '__main__':
    main()
