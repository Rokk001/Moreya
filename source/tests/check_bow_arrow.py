"""Arrow of the bow in the pulling hand (client side only, no compiler, no game).

Pure source wiring check: the settings in config/creatureReactions.cfg, the choice of the pulling hand bone (also
against the real skeleton file of the Elf), the release at the moment of the projectile start, a new arrow that is
never taken longer than the time between the shots, clean up, the fallback without a hand bone, and that the crossbow
reload left the game with the crossbow.
config/creatureReactions.cfg lies in the content package core-config; without the content its settings are named as
not checked and the code wiring is still checked."""
from pathlib import Path
import re
import sys

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / 'scripts'))
import content_packages  # noqa: E402


# The text of a repository file or of a game data file of the public tree or a content package.
def read(path):
    return content_packages.read_text(root, path)


def function_body(source, signature):
    start = source.index(signature)
    end = source.index('\n}\n', start)
    return source[start:end]


cpp = read('source/render/CreatureWeaponVisuals.cpp')
config_h = read('source/render/CreatureReactionConfig.h')
config_cpp = read('source/render/CreatureReactionConfig.cpp')
# The reaction settings lie in the content package core-config (None without the content)
cfg = read('config/creatureReactions.cfg') if content_packages.has_content(root) else None
if cfg is None:
    content_packages.unchecked('check_bow_arrow', ['config/creatureReactions.cfg settings and header'])
tool = read('tools/check_creature_reactions.py')

# 1. Settings: cfg value, cfg header text, parser, default, getter, check script
KEYS = {
    'ArrowFollowsHand': ('mArrowFollowsHand(DEFAULT_ARROW_FOLLOWS_HAND)', 'getArrowFollowsHand'),
    'ArrowPullDistance': ('mArrowPullDistance(DEFAULT_ARROW_PULL_DISTANCE)', 'getArrowPullDistance'),
    'ArrowDrawTime': ('mArrowDrawTime(DEFAULT_ARROW_DRAW_TIME)', 'getArrowDrawTime'),
    'ArrowRetakeGap': ('mArrowRetakeGap(DEFAULT_ARROW_RETAKE_GAP)', 'getArrowRetakeGap'),
    'ArrowReloadTime': ('mArrowReloadTime(DEFAULT_ARROW_RELOAD_TIME)', 'getArrowReloadTime'),
    'ArrowHandOffset': ('mArrowHandOffset(Ogre::Vector3::ZERO)', 'getArrowHandOffset'),
}
# The named defaults keep the numbers the defaults had before they got names
for constant, value in (('DEFAULT_ARROW_FOLLOWS_HAND', 'true'), ('DEFAULT_ARROW_PULL_DISTANCE', '0.12'),
                        ('DEFAULT_ARROW_DRAW_TIME', '1.6'), ('DEFAULT_ARROW_RETAKE_GAP', '0.3'),
                        ('DEFAULT_ARROW_RELOAD_TIME', '0.45')):
    assert re.search(constant + r' = ' + re.escape(value) + ';', config_cpp), constant
if cfg is not None:
    settings_start = cfg.rindex('[Settings]')
    settings = cfg[settings_start:cfg.index('[/Settings]', settings_start)]
    header = cfg[:settings_start]
for key, (default, getter) in KEYS.items():
    if cfg is not None:
        assert re.search(r'^\s+%s\s+\S' % key, settings, re.M), 'cfg value missing: ' + key
        assert re.search(r'^#\s+%s\s' % key, header, re.M), 'cfg header does not explain ' + key
    assert 'words[0] == "%s"' % key in config_cpp, 'parser misses ' + key
    assert default in config_cpp, 'default missing: ' + key
    assert getter in config_h, 'getter missing: ' + getter
    assert '"%s"' % key in tool, 'tools/check_creature_reactions.py does not know ' + key
    assert getter + '()' in cpp, 'the visuals do not read ' + key

# the hard coded times of the first version are gone: they come from the settings now
for old in ('RELOAD_GAP', 'RELOAD_TIME', 'DRAW_TIME', 'DRAW_DISTANCE'):
    assert old not in cpp, old

# 2. The pulling hand: the side that does not carry the weapon, read from the bone names
body = function_body(cpp, 'std::string findPullHandBone(')
assert 'Weapon_R' in body and 'RightHand' in body and 'Weapon_L' in body and 'LeftHand' in body
assert 'return std::string();' in body, 'no hand bone must give an empty name'


def find_pull_hand(bones, mount_bone):
    """Python twin of findPullHandBone."""
    lower = mount_bone.lower()
    left = 'left' in lower or lower.endswith('_l') or lower.endswith('.l')
    right = 'right' in lower or lower.endswith('_r') or lower.endswith('.r')
    if left == right:
        return ''
    candidates = (['Weapon_R', 'RightHand', 'Hand_R', 'hand.R', 'Hand.R', 'RightFinger', 'Finger_R'] if left else
                  ['Weapon_L', 'LeftHand', 'Hand_L', 'hand.L', 'Hand.L', 'LeftFinger', 'Finger_L'])
    for name in candidates:
        if name in bones:
            return name
    return ''


def skeleton_bones(name):
    data = content_packages.resolve(root, 'models/' + name + '.skeleton').read_bytes()
    return set(m.decode() for m in re.findall(rb'Weapon_[LR]|LeftHand|RightHand', data))


# The skeleton lies in the content package creatures; without the content it is named as not checked
if content_packages.has_content(root):
    elf = skeleton_bones('Elf')
    assert find_pull_hand(elf, 'Weapon_L') == 'Weapon_R', 'Elf: bow in the left hand, the right hand pulls'
else:
    content_packages.unchecked('check_bow_arrow', ['models/Elf.skeleton hands'])
assert find_pull_hand({'Weapon_R'}, 'Weapon_R') == '', 'the weapon bone is never its own pulling hand'
assert find_pull_hand({'Body'}, 'Weapon_L') == '', 'no hand bone: fallback'
assert find_pull_hand({'Weapon_L', 'LeftHand'}, 'Spine') == '', 'unknown side: fallback'

# 3. The arrow is taken from the hand and follows it (position from the bone world positions, every frame)
place = function_body(cpp, 'void placeArrow(')
assert '_getDerivedPosition()' in function_body(cpp, 'bool getHandPosition(') and 'handPosition' in place
assert 'config.getArrowPullDistance()' in place and 'toHand' in place, 'drawn from the string toward the hand'
assert 'std::min(distance, config.getArrowPullDistance())' in place, 'the pull is limited'
assert 'followsHand' in place

# 4. Release: the held arrow is gone with the projectile (same event, no waiting for the next look)
shot = function_body(cpp, 'void noteShot(')
assert 'mReleasedAt = now;' in shot
assert 'setVisible(false)' in shot, 'the held arrow is hidden at once at the launch'
assert 'event.mText.empty()' in shot, 'magic missiles have no arrow'
assert 'sinceShot < config.getArrowRetakeGap()' in place and 'arrow->setVisible(false)' in place

# 5. A new arrow is never taken longer than the time between the shots
duration = function_body(cpp, 'double getReloadDuration(')
assert 'getArrowReloadTime()' in duration and 'shooter.mShotInterval - config.getArrowRetakeGap()' in duration
assert 'std::min(duration,' in duration
assert 'held.mShotInterval = (held.mReleasedAt > -999.0) ? (now - held.mReleasedAt) : 0.0;' in shot


def reload_duration(setting, interval, gap, minimum=0.05):
    return min(setting, max(minimum, interval - gap)) if interval > 0 else setting


for interval in (0.0, 0.5, 0.9, 1.4, 2.0, 5.0, 12.0):
    d = reload_duration(0.45, interval, 0.3)
    assert d <= 0.45
    if interval > 0.35:
        assert d + 0.3 <= interval + 1e-9, 'reload longer than the shot interval'
assert reload_duration(0.45, 3.0, 0.3) == 0.45

# 6. The crossbow left the game (drop items plan): no crossbow reload, setting, mount or weapon kind is left
render = read('source/render/RenderManager.cpp')
for text in (cpp, config_h, config_cpp, tool, render, read('source/render/CreatureCombatReactions.cpp')):
    assert 'rossbow' not in text and 'BOLT_' not in text and 'straightenWeapon' not in text, 'crossbow code left'
if cfg is not None:
    assert 'Crossbow' not in cfg, 'crossbow setting left in config/creatureReactions.cfg'

# 7. Clean up: removeArrow (arrow gone) on every way out
remove = function_body(cpp, 'void removeArrow(')
assert 'destroyArrow(shooter.mArrowName)' in remove
tick = function_body(cpp, 'void tick(')
assert tick.count('removeArrow(') >= 3, 'not armed, dead or gone, creature removed'
assert 'removeArrow(it->second)' in function_body(cpp, 'void removeAllArrows(')
assert 'removeAllArrows();' in function_body(cpp, 'void CreatureWeaponVisuals::stopAll(')
assert 'stopAll(reactions)' in function_body(cpp, 'void CreatureWeaponVisuals::update(')
assert 'isActive' in function_body(cpp, 'void CreatureWeaponVisuals::update('), 'only the full mode'
assert 'isCreatureNearCamera' in tick, 'only creatures near the camera'
destroy = function_body(cpp, 'void destroyArrow(')
assert 'detachFromParent()' in destroy and 'destroyEntity' in destroy

# 8. Fallback without a hand bone: old behavior (arrow on the bow), logged once per mesh
assert 'sNoHandLogged' in cpp and 'OD_LOG_INF(' in cpp
assert 'if(followsHand)' in place and place.count('No hand known') == 1
assert 'getArrowFollowsHand()' in function_body(cpp, 'bool createArrow(')

# 9. Nothing on the server or the network was touched by this feature
for forbidden in ('ODServer', 'ServerNotification', 'ClientNotification', 'sendCosmeticEvent', 'fireCreatureRefreshIfNeeded'):
    assert forbidden not in cpp, forbidden
assert 'mActivity' not in cpp

print('check_bow_arrow: ok')
sys.exit(0)
