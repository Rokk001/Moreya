"""Shared helper of the compiled check probes: a stand-in for the ConfigManager that CreatureProgression.h includes."""
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
import content_packages  # noqa: E402


def global_cfg_text(root):
    """Return config/global.cfg as the game reads it: joined with its own rows of the content packages (without the
    content the keys of the own rows are missing; a caller names its probe as not checked then)."""
    return content_packages.read_text(Path(root), 'config/global.cfg')


def global_cfg_number(root, key):
    """Return the numeric value of a key of config/global.cfg (the probes use the shipped values)."""
    match = re.search(r'^\s*' + re.escape(key) + r'\s+([-\d.eE]+)', global_cfg_text(root), re.M)
    assert match, key
    return float(match[1])


def global_cfg_numbers(root, key):
    """Return all numeric values of one tab-separated global config key."""
    match = re.search(r'^\s*' + re.escape(key) + r'\s+([^\r\n]+)', global_cfg_text(root), re.M)
    assert match, key
    return [float(value) for value in match[1].split('\t') if value.strip()]


def config_manager_stub(root):
    """Return C++ source that defines a minimal ConfigManager (and its include guard) with the growth keys of global.cfg.

    The real header needs Ogre and Boost; the probes only need the four getters used by CreatureProgression.h.
    """
    return '''
#define CONFIGMANAGER_H
#include <algorithm>
#include <vector>
class ConfigManager {
public:
 static ConfigManager& getSingleton(){static ConfigManager instance;return instance;}
 double getCreatureDamageGrowth() const {return %r;}
 double getCreatureDamageExponent() const {return %r;}
 double getCreatureHpGrowthPerLevel() const {return %r;}
 double getCooldownReductionPerLevel() const {return std::max(0.0,std::min(1.0,%r));}
 double getSkillSpellReferenceMinHP() const {return %r;}
 std::vector<double> getBuildingDamageCurve() const {return {%s};}
};
''' % (global_cfg_number(root, 'CreatureDamageGrowth'), global_cfg_number(root, 'CreatureDamageExponent'),
       global_cfg_number(root, 'CreatureHpGrowthPerLevel'), global_cfg_number(root, 'CooldownReductionPerLevel'),
       global_cfg_number(root, 'SkillSpellReferenceMinHP'),
       ', '.join(repr(value) for value in global_cfg_numbers(root, 'BuildingDamageCurve')))
