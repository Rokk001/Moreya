"""Check the bone names the render code asks a skeleton for by name without being able to do without them.

The mount pose of a rooster asks the hen and the rooster for their head bone; a name no rig has ended the game with
Ogre::ItemIdentityException. Checked with fixed values: the chicken render code asks for the bone 'head' only, through
CHICKEN_HEAD_BONE and behind hasBone; the Chicken, ChickenRooster and ChickenChick skeletons have it; the keeper hand
skeleton has the bones Hand1, Hand2, Index3 and Thumb3 that the hand code asks for.
The skeletons lie in the content packages (needs OgreXMLConverter, environment variable OGRE_XML_CONVERTER); without
the content only the code is checked."""
from pathlib import Path
import os
import re
import subprocess
import sys
import tempfile

repo = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo / 'scripts'))
import content_packages  # noqa: E402

CHICKEN_BONES = ('head',)
CHICKEN_RIGS = ('Chicken', 'ChickenRooster', 'ChickenChick')
HAND_BONES = ('Hand1', 'Hand2', 'Index3', 'Thumb3')


def read(path):
    """The text of a file below the repository root."""
    return (repo / path).read_text(encoding='utf-8')


def bones_of(rig, work):
    """Bone names of models/<rig>.skeleton, None when the content is not present."""
    found = content_packages.data_file(repo, 'models/%s.skeleton' % rig)
    if found is None:
        assert not content_packages.has_content(repo), 'missing skeleton ' + rig
        return None
    target = work / (rig + '.xml')
    subprocess.run([os.environ.get('OGRE_XML_CONVERTER', 'OgreXMLConverter'), '-q', str(found), str(target)], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return set(re.findall(r'<bone [^>]*name="([^"]+)"', target.read_text()))


chickens = read('source/render/RenderManagerChickens.cpp')
assert 'const std::string CHICKEN_HEAD_BONE = "head";' in chickens
asked = re.findall(r'(?:getBone|hasBone|attachObjectToBone)\(\s*([^,()]+?)\s*[,)]', chickens)
assert asked and set(asked) == {'CHICKEN_HEAD_BONE'}, asked
assert 'henRig->hasBone(CHICKEN_HEAD_BONE) && roosterRig->hasBone(CHICKEN_HEAD_BONE)' in chickens

render = read('source/render/RenderManager.cpp')
named = set(re.findall(r'(?:getBone|attachObjectToBone)\("([^"]+)"', render))
# Names asked for without a hasBone test: only the bones of the keeper hand
unguarded = {name for name in named if 'hasBone("%s")' % name not in render}
assert unguarded <= set(HAND_BONES) | {'LeftHand', 'RightHand', 'Weapon_L', 'Weapon_R', 'Pick'}, unguarded

with tempfile.TemporaryDirectory(prefix='chickenbones_') as directory:
    work = Path(directory)
    for rig, wanted in [(rig, CHICKEN_BONES) for rig in CHICKEN_RIGS] + [('Keeperhand', HAND_BONES)]:
        bones = bones_of(rig, work)
        if bones is None:
            content_packages.unchecked('check_chicken_bones', ['models/%s.skeleton' % rig])
            continue
        assert set(wanted) <= bones, (rig, sorted(set(wanted) - bones))

print('check_chicken_bones ok')
