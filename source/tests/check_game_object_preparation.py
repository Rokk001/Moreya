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
   listed twice, and the list has exactly 227 meshes (189 objects of the code and configs, 38 dirt piles of the
   creature classes, DirtPileEntity::PILE_MESH_PREFIX). A new object mesh in the code without a list entry fails here.
2. Wiring (no compiler): initGameRenderer prepares the objects after the creatures and before the game shaders; the
   preparation does the steps of rrCreateRenderedMovableEntity, never attaches its temporary entity, destroys it, and
   reports a mesh it cannot prepare instead of stopping the map load.
3. Rejected stalls of build 61 (no compiler): BloodStain and GoblinBed, the first objects of the two rejected
   minutes, are listed, and the contour/hover copies made in those minutes are prepared for every creature and seat.
4. Parsing (compiled probe of the production readPreparedObjectMeshes): the game reads exactly the 227 names from the
   real file, in file order, comments ignored.

Fixed values of this branch: 227 listed meshes. Part 4 compiles with cl, so it runs in the compile phase of the
integration only (--no-probe skips it).

config/preparedobjects.cfg and the meshes are content (core-config, core-models and room packages, found through
scripts/content_packages.py). Without the content the wiring and the code part of the rejected stalls are checked;
coverage, the listed stall objects and the probe are named as not checked.
"""
from pathlib import Path
import importlib.util
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import content_packages  # noqa: E402
import room_packages  # noqa: E402

#: The list of the prepared meshes (core-config package)
PREPARED_OBJECTS = 'config/preparedobjects.cfg'


def mesh_exists(name):
    """True when the mesh is in models/ of the game data, of a content package or of a present room package; a mesh of
    a room package that is not present counts as there (only the list and the code are checked then)."""
    relative = 'models/' + name
    return (content_packages.data_file(ROOT, relative) is not None or room_packages.asset(ROOT, relative) is not None
            or room_packages.is_missing_packaged(ROOT, relative))
# 219 since the four classic gold stack meshes left the list (counted on the branch; was 223): floor and carried
# gold are code-built heaps and sacks, the GoldstackLv names are only sizes
# 221 since the training hall has its own wall shields TrainingHallShield1 and 2 next to the WeaponShield meshes
# of the arena (counted on the integration branch; was 219)
# 222 since every finished trap of the workshop shows the TrapCrate mesh (counted on the branch; was 221); 227 with
# the clip props jug, die, flask, rattle and bucket (counted on the integration branch); 229 with the look-only weapons
# LizardManStaff and SkeletonSword of the lizardman and the skeleton (counted on the branch)
LISTED = 229
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
    for line in content_packages.read_text(ROOT, PREPARED_OBJECTS).splitlines():
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
    # config/creatures.cfg is a mixed table: read as the game reads it, with its own rows from the content
    creatures = set(re.findall(r'^\s*MeshName\s+(\S+)', content_packages.read_text(ROOT, 'config/creatures.cfg'),
                               re.M))
    pile_prefix = re.search(r'PILE_MESH_PREFIX = "([^"]+)";', read('source/entities/DirtPileEntity.cpp')).group(1)
    names = set()
    for ref in refs:
        if ref.kind == 'mesh' and (ref.path.startswith(OBJECT_SOURCES) or ref.path.startswith(OBJECT_CONFIGS)):
            names.add(ref.name)
        # The dirt pile of a creature class (DirtPileEntity::PILE_MESH_PREFIX + class name) is an object, too.
        if ref.kind == 'mesh' and ref.name.startswith(pile_prefix):
            names.add(ref.name)
    return {name for name in names
            if mesh_exists(name) and not name.startswith('Menu') and name not in creatures}


def coverage():
    """Part 1: the list holds every object mesh the game can create, and only existing meshes."""
    names = listed()
    assert len(names) == LISTED, len(names)
    assert len(set(names)) == len(names), 'a mesh is listed twice'
    for name in names:
        assert mesh_exists(name), name
    missing = sorted(referenced() - set(names))
    assert not missing, 'object meshes not prepared: %s' % missing
    for figure in ('ChickenEgg.mesh', 'Innkeeper.mesh', 'TavernCounter.mesh', 'SmallSpider.mesh'):
        assert figure in names, figure


def rejected_stalls(render_manager, with_list=True):
    """The first-use work of the two stalls the owner rejected in build 61 (367.97 ms in the minute to 18:44:39,
    780.06 ms in the minute to 18:45:39 of 2026-11-11) is done during the map load: the first BloodStain and the first
    GoblinBed of that session are listed objects, and the contour and hover copies created then (Kobold green, Roach
    red, "couldn't find ... cloning") are made for every configured creature and every seat before play. Without the
    content (with_list False) the listed objects are not checked, only the code."""
    if with_list:
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

// The production reader looks the list up through ContentPackages::resolveFile (header-only lookup part)
#include "utils/ContentPackages.h"

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
    # The config folder that holds the list (public tree or content package)
    config = content_packages.resolve(ROOT, PREPARED_OBJECTS).parent.as_posix() + '/'
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
            f'cl /nologo /EHsc /std:c++14 /I"{ROOT / "source"}" "{cpp}" /Fe:"{directory / "probe.exe"}" '
            f'/Fo:"{directory / "probe.obj"}"\n'
            'if errorlevel 1 exit /b 1\n'
            f'"{directory / "probe.exe"}" "{expected}"\nexit /b %errorlevel%\n',
            encoding='utf-8',
        )
        subprocess.run(['cmd', '/d', '/c', str(batch)], cwd=directory, check=True)


def main():
    """Runs coverage and wiring, then the compiled reader probe unless --no-probe is given; without the content only
    the code parts run and the rest is named as not checked."""
    render_manager = read('source/render/RenderManager.cpp')
    if content_packages.data_file(ROOT, PREPARED_OBJECTS) is None:
        wiring(render_manager)
        rejected_stalls(render_manager, with_list=False)
        content_packages.unchecked('check_game_object_preparation', [PREPARED_OBJECTS + ' (coverage, stall objects, probe)'])
        print('game object preparation: wiring ok')
        return
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
