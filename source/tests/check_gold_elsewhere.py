"""Check the gold shown outside the treasury: a coin heap for gold on the floor, a sack for gold carried
by a worker, brighter veins in the walls, and the wiring of these into the renderer. Also runs the render
budget count (no game start needed).

The sack material and texture are content (core-models package, found through scripts/content_packages.py) and their
CREDITS row stands in the CREDITS of the content repository; without the content they are named as not checked."""
from pathlib import Path
import subprocess
import sys

repo = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo / 'scripts'))
import content_packages  # noqa: E402
import room_packages  # noqa: E402

#: The content files of the sack (core-models package)
SACK_FILES = ('materials/scripts/GoldSack.material', 'materials/textures/GoldSackMeshy.png') + tuple(
    'models/GoldSack_%d.mesh' % size for size in range(1, 5))


def read(path):
    return (repo / path).read_text(encoding='utf-8')


render = read('source/render/RenderManager.cpp')
loose = read('source/render/LooseGoldMesh.cpp')
header = read('source/render/LooseGoldMesh.h')

# Floor gold becomes a heap at every treasury detail (the classic stack meshes no longer exist), carried gold a
# sack only while the treasury detail is not off: one detail test left, in prepareSack (fixed value 1, was 2).
assert 'LooseGoldMesh::prepareHeap(mSceneManager, meshName)' in render
assert 'GameEntityType::treasuryObject' in render
assert 'LooseGoldMesh::prepareSack(mSceneManager, carried->getMeshName())' in render
assert loose.count('TreasuryGoldMesh::Detail::off') == 1
# The gold a worker carries on its back is the sack (or the heap while the sack is off), never a stack mesh.
workers = read('source/render/WorkerReactions.cpp')
assert 'LooseGoldMesh::prepareSack(sceneManager, stackName)' in workers
assert 'LooseGoldMesh::prepareHeap(sceneManager, stackName)' in workers
assert '"GoldstackLv" + Helper::toString(level) + ".mesh"' not in workers
# The sack and its visibility swap are undone when the gold is put down and when the object goes away.
assert '_sack' in render and render.count('"_sack"') >= 3
assert 'carriedEnt->setVisible(true)' in render
# Four sizes follow the four classic stack names the server already sends; nothing else is replicated.
assert 'sizeCount = 4' in header
assert 'GoldstackLv' in loose
assert 'GoldstackLv1' in read('source/entities/TreasuryObject.cpp')
# Assets: material, texture, the four pouch meshes, credits, build.
missing_content = [name for name in SACK_FILES if content_packages.data_file(repo, name) is None]
if not missing_content:
    assert 'material GoldSack' in content_packages.read_text(repo, 'materials/scripts/GoldSack.material')
    assert 'texture GoldSackMeshy.png' in content_packages.read_text(repo, 'materials/scripts/GoldSack.material')
    # The row of a moved asset stands in the CREDITS of the content repository (public CREDITS plus that one)
    assert 'GoldSackMeshy.png' in room_packages.credits_text(repo)
    assert all('GoldSack_%d.mesh' % size in room_packages.credits_text(repo) for size in range(1, 5))
else:
    content_packages.unchecked('check_gold_elsewhere', missing_content)
assert 'LooseGoldMesh.cpp' in read('CMakeLists.txt')
# Veins: brighter gold wall shader with a glint, brighter gem material.
frag = read('shaders/GoldDistortion.frag')
assert 'veinGain' in frag and 'veinTime' in frag
gold_material = read('materials/scripts/Gold.material')
assert 'veinGain' in gold_material and 'veinTime time_0_x' in gold_material
assert 'emissive 0.22' in read('materials/scripts/GemFull.material')

result = subprocess.run([sys.executable, str(repo / 'tools/treasury-gold/check_gold_budget.py')])
assert result.returncode == 0, 'render budget exceeded'

print('check_gold_elsewhere ok')
