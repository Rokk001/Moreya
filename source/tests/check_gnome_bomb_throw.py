"""Check the thrown bomb of the Gnome: the key ThrownBomb, the unchanged hit of the Explosion skill, the look-only bomb
missile with hide and show on the client, the speed rule and, with content present, the Gnome row and its files.

A small cl probe runs the stream round trip of the bomb, its turn limit and the speed rule on the real methods."""
from pathlib import Path
import hashlib
import re
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
import content_packages  # noqa: E402

CHECK = 'check_gnome_bomb_throw'
repo = Path(__file__).resolve().parents[2]

# Fixed expected values, counted once on this branch
# SHA-256 of the body of CreatureSkillExplosion::tryUseFight on origin/main (before the throw was added): with the
# bomb launch taken out, the body must be exactly this, so damage, crit, area, effects and turn stay as they are
TRY_USE_FIGHT_MAIN_SHA256 = '783b9c44573a41eb6689ba76fdbc5fd8ad81f1597ccc471e1ab79444d038e192'
# The lines the branch adds at the end of the successful path of tryUseFight
BOMB_LAUNCH_BLOCK = ('\n'
                     '    // Look only: a creature type with the key ThrownBomb throws its bomb at the target; the hit above'
                     ' is unchanged\n'
                     '    if(creature->getDefinition()->throwsBomb())\n'
                     '        launchThrownBomb(gameMap, *creature, *attackedCreature, attackedTile);\n')
MISSILE_TYPES = ['oneHit', 'boulder', 'blast', 'stone', 'skillBomb']
# Range of Bomb Hail (BaseLine field RangeMax) and its whole BaseLine in the content skill table
BOMB_HAIL_RANGE = 6
BOMB_HAIL_BASELINE = 'Explosion 40 2 6 12 1 30.75 20.5'
GNOME_ROW = 'ThrownBomb\tGnomeBomb.mesh\tGnomeBombFuse\tGnomeBombMeshy'
GNOME_OWN_BLOCK = 510
CONTENT_FILES = ['creatures/models/GnomeBomb.mesh', 'effects/particles/GnomeBombFuse.particle',
                 'effects/materials/scripts/GnomeBombFuse.material']

failures = []


def check(ok, what):
    if not ok:
        failures.append(what)
        print('FAIL: ' + what)


def read(path):
    return (repo / path).read_text(encoding='utf-8').replace('\r\n', '\n')


def function(text, signature, rename=None):
    """The definition that starts with signature, up to the first closing brace in column 0."""
    start = text.index(signature)
    body = text[start:text.index('\n}\n', start) + 3]
    if rename is not None:
        body = body.replace(rename[0], rename[1])
    return body


# --- CreatureDefinition: parse, write, packet, copy -------------------------------------------------------------
definition_h = read('source/entities/CreatureDefinition.h')
definition = read('source/entities/CreatureDefinition.cpp')
for member in ('mThrownBombMesh', 'mThrownBombParticle', 'mThrownBombMaterial'):
    check(definition_h.count('std::string %s;' % member) == 1, 'member %s declared once' % member)
    check(definition.count('%s(def.%s)' % (member, member)) == 1, 'copy constructor copies %s' % member)
    check(definition.count('os << c->%s;' % member) == 1, 'packet writes %s' % member)
    check(definition.count('is >> c->%s;' % member) == 1, 'packet reads %s' % member)
    check(definition.count('%s (""),' % member) == 1, 'constructor starts %s empty' % member)
for getter in ('throwsBomb()', 'getThrownBombMesh()', 'getThrownBombParticle()', 'getThrownBombMaterial()'):
    check(definition_h.count(getter + ' const') == 1, 'getter %s' % getter)
check('inline bool throwsBomb() const { return !mThrownBombMesh.empty(); }' in definition_h,
      'throwsBomb is true exactly when the mesh is set')
packet_out = definition.split('ODPacket& operator<<(ODPacket& os, const CreatureDefinition* c)', 1)[1].split('\n}\n', 1)[0]
packet_in = definition.split('ODPacket& operator>>(ODPacket& is, CreatureDefinition* c)', 1)[1].split('\n}\n', 1)[0]
order_out = [line.strip()[len('os << c->'):-1] for line in packet_out.split('\n') if line.strip().startswith('os << c->')]
order_in = [line.strip()[len('is >> c->'):-1] for line in packet_in.split('\n') if line.strip().startswith('is >> c->')]
PACKET_WINDOW = ['mPreSkill', 'mTierFourSkill', 'mThrownBombMesh', 'mThrownBombParticle', 'mThrownBombMaterial',
                 'mUrgeGrowthPerTurn']


def window(order):
    start = order.index('mPreSkill')
    return order[start:start + len(PACKET_WINDOW)]


check(window(order_out) == PACKET_WINDOW and window(order_in) == PACKET_WINDOW,
      'packet writes and reads the key after TierFourSkill in the same order')
check(definition.count('nextParam == "ThrownBomb"') == 1, 'parser reads the key ThrownBomb')
check('defFile >> creatureDef->mThrownBombMesh >> creatureDef->mThrownBombParticle\n'
      '                    >> creatureDef->mThrownBombMaterial;' in definition, 'parser reads mesh, particle, material')
check(definition.count('== "none")\n                    creatureDef->mThrownBomb') == 3, 'parser maps none to empty')
check(definition.count('file << "    ThrownBomb\\t"') == 1, 'writer writes the key ThrownBomb')
check('(def1 == nullptr) ? !def2->mThrownBombMesh.empty() :' in definition,
      'writer writes the key for a new type only when it is set')

# --- Skill: the hit stays as it is, the throw only for types with the key ----------------------------------------
explosion_source = read('source/creatureskill/CreatureSkillExplosion.cpp')
try_use_fight = explosion_source.split('bool CreatureSkillExplosion::tryUseFight(', 1)[1].split(
    '\nCreatureSkillExplosion* CreatureSkillExplosion::clone()', 1)[0]
check(try_use_fight.count(BOMB_LAUNCH_BLOCK) == 1, 'tryUseFight launches the bomb once, only for types with the key')
check(try_use_fight.index(BOMB_LAUNCH_BLOCK) > try_use_fight.index('target->addCreatureEffect(effect);'),
      'the bomb is launched after the explosion was applied')
check(try_use_fight.rstrip().endswith(BOMB_LAUNCH_BLOCK + '\n    return true;\n}'),
      'the launch is the end of the successful path')
unchanged = try_use_fight.replace(BOMB_LAUNCH_BLOCK, '', 1)
check(hashlib.sha256(unchanged.encode('utf-8')).hexdigest() == TRY_USE_FIGHT_MAIN_SHA256,
      'tryUseFight without the launch is byte for byte the body of origin/main')
launcher = function(explosion_source, 'void launchThrownBomb(')
check('new MissileBomb(' in launcher and 'MissileBomb::flightSpeed(distance)' in launcher,
      'the launcher creates the bomb with the speed rule')
for token in ('CreatureEffect', 'Damage', 'hurt(', 'rollCritical', 'addCreatureEffect'):
    check(token not in launcher, 'the launcher has no effect on the fight (%s)' % token)
launch_order = ('bomb->addToGameMap();', 'bomb->createMesh();', 'bomb->setPosition(position);',
                'bomb->notifySeatsWithVision(', 'bomb->doUpkeep();')
positions = [launcher.index(token) for token in launch_order]
check(positions == sorted(positions), 'the bomb is placed and announced before its flight')

# --- Missile: look only --------------------------------------------------------------------------------------------
bomb_h = read('source/entities/MissileBomb.h')
bomb = read('source/entities/MissileBomb.cpp')
check('class MissileBomb: public MissileObject' in bomb_h, 'MissileBomb is a plain MissileObject')
for token in ('Damage', 'hurt(', 'addCreatureEffect', 'takeDamage', 'rollCritical', 'notifyFightPlayer'):
    check(token not in bomb and token not in bomb_h, 'MissileBomb has no damage or effect (%s)' % token)
check('virtual bool hitCreature(Tile* tile, GameEntity* entity) override\n    { return true; }' in bomb_h,
      'the bomb flies over creatures')
check('virtual void hitTargetEntity(Tile* tile, GameEntity* entityTarget) override\n    {}' in bomb_h,
      'the bomb does nothing at the target')
check('MissileObject(gameMap, seat, throwerName, meshName, direction, speed, target, false, false)' in bomb,
      'the bomb hurts no allies and knocks out no one')
create = function(bomb, 'void MissileBomb::createMeshLocal(')
destroy = function(bomb, 'void MissileBomb::destroyMeshLocal(')
check('rrSetCreatureSubMeshVisible(*thrower, mHiddenMaterial, false)' in create, 'createMeshLocal hides the bomb part')
check('getIsOnServerMap()' in create, 'the hide runs on the client only')
check('rrSetCreatureSubMeshVisible(*thrower, mHiddenMaterial, true)' in destroy, 'destroyMeshLocal shows it again')
check('target->showHeldParticleEffect(effectName);' in destroy, 'destroyMeshLocal shows the held explosion')
check(destroy.index('showHeldParticleEffect') < destroy.index('MissileObject::destroyMeshLocal(nt);'),
      'the held explosion shows before the bomb mesh goes')
check("os << \"Bomb\\t\";" in bomb, 'the stream marks the bomb fields')
packet_out = function(bomb, 'void MissileBomb::exportToPacket(')
packet_in = function(bomb, 'void MissileBomb::importFromPacket(')
for field in ('mThrowerName', 'mTargetName', 'mHiddenMaterial'):
    check('os << %s;' % field in packet_out and 'is >> %s' % field in packet_in, 'packet round trip of %s' % field)
check(packet_out.index('mThrowerName') < packet_out.index('mTargetName') < packet_out.index('mHiddenMaterial') and
      packet_in.index('mThrowerName') < packet_in.index('mTargetName') < packet_in.index('mHiddenMaterial'),
      'packet reads the names in the order it writes them')
check("const std::string MissileBomb::IMPACT_PARTICLE_SCRIPT = \"SpellCreatureExplosion\";" in bomb and
      'new CreatureEffectExplosion(mEffectDuration, mEffectValue * targetFactor,\n            "SpellCreatureExplosion");'
      in explosion_source, 'the held particle is the particle of the explosion effect')

missile_h = read('source/entities/MissileObject.h')
enum_text = missile_h.split('enum class MissileObjectType\n{', 1)[1].split('};', 1)[0]
enum_names = [line.strip().rstrip(',') for line in enum_text.split('\n')
              if line.strip() and not line.strip().startswith('//')]
check(enum_names == MISSILE_TYPES, 'missile types %s, the bomb appended last' % MISSILE_TYPES)
missile = read('source/entities/MissileObject.cpp')
check(missile.count('case MissileObjectType::skillBomb:') == 2, 'stream and packet branch for the bomb')
check('obj = MissileBomb::getMissileBombFromStream(gameMap, is);' in missile and
      'obj = MissileBomb::getMissileBombFromPacket(gameMap, is);' in missile, 'branches create the bomb')
check('    ${SRC}/entities/MissileBlast.cpp\n    ${SRC}/entities/MissileBomb.cpp\n' in read('CMakeLists.txt'),
      'MissileBomb.cpp in the source list next to MissileBlast.cpp')

entity = read('source/entities/GameEntity.cpp')
update = function(entity, 'void GameEntity::updateFromPacket(')
check(update.count('MissileBomb::holdImpactParticle(*this, *effect)') == 1, 'client holds the explosion of a bomb')
check(update.index('holdImpactParticle') < update.index('rrEntityAddParticleEffect'),
      'the hold is decided before the particle is shown')
render = read('source/render/RenderManager.cpp')
sub_mesh = function(render, 'void RenderManager::rrSetCreatureSubMeshVisible(')
check('sub->getSubMesh()->getMaterialName() == meshMaterial' in sub_mesh,
      'the hidden part is matched by the material named in the mesh')

# --- Probe: stream round trip, turn limit and speed rule on the real methods -------------------------------------
rename = ('MissileBomb::', 'ProbeBomb::')
methods = ''.join(function(bomb, signature, rename) for signature in (
    'void MissileBomb::addFlightParticle(', 'double MissileBomb::flightSpeed(', 'void MissileBomb::updateDirection(',
    'void MissileBomb::exportToStream(', 'bool MissileBomb::importFromStream('))
methods = methods.replace('MissileObject::exportToStream(os);', 'baseExport(os);')
methods = methods.replace('MissileObject::importFromStream(is)', 'baseImport(is)')
constants = '\n'.join(line.replace('MissileBomb::', 'ProbeBomb::') for line in bomb.split('\n')
                      if line.startswith(('const double MissileBomb::', 'const uint32_t MissileBomb::')))
probe = r'''
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>
struct EntityParticleEffect {
 EntityParticleEffect(const std::string& name,const std::string& script,int32_t):mName(name),mScript(script){}
 std::string mName,mScript;
};
static int checks=0,failures=0;
static void check(bool ok,const char* what){++checks;if(!ok){++failures;std::cout<<"FAIL: "<<what<<'\n';}}
struct ProbeBomb {
 static const double MIN_FLIGHT_SPEED;static const uint32_t MAX_FLIGHT_TURNS;
 std::string mThrowerName,mTargetName,mHiddenMaterial;int32_t mTargetX=-1,mTargetY=-1;uint32_t mTurnsLeft=MAX_FLIGHT_TURNS;
 std::vector<EntityParticleEffect*> mEntityParticleEffects;int mParticles=0;bool mStopped=false;
 ~ProbeBomb(){for(EntityParticleEffect* e:mEntityParticleEffects)delete e;}
 void stopMissile(){mStopped=true;}
 std::string nextParticleSystemsName(){return "Bomb_Particle"+std::to_string(++mParticles);}
 void baseExport(std::ostream& os)const{os<<"base\t";}
 bool baseImport(std::istream& is){std::string word;return static_cast<bool>(is>>word)&&word=="base";}
 void addFlightParticle(const std::string& particleScript);
 static double flightSpeed(double distance);
 void updateDirection();
 void exportToStream(std::ostream& os)const;
 bool importFromStream(std::istream& is);
};
CONSTANTS
METHODS
int main(){
 const double range=RANGE;
 check(ProbeBomb::flightSpeed(0.0)==0.5,"a target on the own tile gets the minimum speed 0.5");
 check(ProbeBomb::flightSpeed(range)==range,"at the range the speed is the distance per turn");
 const double distances[]={0.0,0.3,1.0,2.5,range,range*std::sqrt(2.0)};
 for(double distance:distances)
  check(ProbeBomb::flightSpeed(distance)>=distance,"the flight reaches the target within the turn of the throw");
 ProbeBomb flight;int upkeeps=0;
 while(!flight.mStopped&&upkeeps<10){flight.updateDirection();++upkeeps;}
 check(upkeeps==3,"a bomb that did not land stops at its third upkeep (two turns of flight)");
 ProbeBomb original;original.mThrowerName="Snapper_3";original.mTargetName="Target_7";
 original.mHiddenMaterial="GnomeBombMeshy";original.mTargetX=4;original.mTargetY=9;original.mTurnsLeft=1;
 original.addFlightParticle("GnomeBombFuse");original.addFlightParticle("");
 std::ostringstream out;original.exportToStream(out);
 ProbeBomb loaded;std::istringstream in(out.str());
 check(loaded.importFromStream(in),"the saved bomb reads back");
 check(loaded.mThrowerName=="Snapper_3"&&loaded.mTargetName=="Target_7"&&loaded.mHiddenMaterial=="GnomeBombMeshy",
  "names survive the round trip");
 check(loaded.mTargetX==4&&loaded.mTargetY==9&&loaded.mTurnsLeft==1,"target tile and turns survive the round trip");
 check(loaded.mEntityParticleEffects.size()==1&&loaded.mEntityParticleEffects[0]->mScript=="GnomeBombFuse",
  "the fuse particle survives the round trip, an empty script adds none");
 ProbeBomb empty;std::ostringstream emptyOut;empty.exportToStream(emptyOut);
 ProbeBomb emptyLoaded;emptyLoaded.mHiddenMaterial="x";std::istringstream emptyIn(emptyOut.str());
 check(emptyLoaded.importFromStream(emptyIn)&&emptyLoaded.mThrowerName.empty()&&emptyLoaded.mHiddenMaterial.empty()&&
  emptyLoaded.mEntityParticleEffects.empty(),"empty names are saved as none and read back empty");
 ProbeBomb broken;std::istringstream brokenIn("base\tSnapper_3\tTarget_7\tnone\t4\t9\t1\t0");
 check(!broken.importFromStream(brokenIn),"a record without the bomb marker is refused");
 std::cout<<"CHECKS="<<checks<<" FAILURES="<<failures<<'\n';return failures?1:0;
}
'''.replace('CONSTANTS', constants).replace('METHODS', methods).replace('RANGE', '%d.0' % BOMB_HAIL_RANGE)


def phase(name, seconds):
    print('ODP_TEST_PHASE {"name":"%s","seconds":%.3f}' % (name, seconds))


with tempfile.TemporaryDirectory(prefix='odp-gnome-bomb-') as directory:
    work = Path(directory)
    (work / 'probe.cpp').write_text(probe, encoding='utf-8')
    started = time.monotonic()
    compiled = subprocess.run(['cl', '/nologo', '/EHsc', '/MD', '/std:c++17', 'probe.cpp', '/Feprobe.exe'], cwd=work,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    phase('compile', time.monotonic() - started)
    if compiled.returncode != 0:
        print(compiled.stdout)
        check(False, 'the probe compiles')
    else:
        started = time.monotonic()
        ran = subprocess.run([str(work / 'probe.exe')], cwd=work, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True)
        phase('probe', time.monotonic() - started)
        print(ran.stdout.strip())
        check(ran.returncode == 0, 'the probe passes')

# --- Content: the Gnome row, Bomb Hail and the files ---------------------------------------------------------------
if not content_packages.has_content(repo):
    content_packages.unchecked(CHECK, ['Gnome row ThrownBomb', 'Bomb Hail range', 'bomb mesh, fuse particle and material'])
else:
    own = content_packages.data_file(repo, 'config/creatures.own.cfg')
    own_text = Path(own).read_text(encoding='utf-8').replace('\r\n', '\n')
    block = own_text.split('#@own %d\n' % GNOME_OWN_BLOCK, 1)[1].split('\n#@own ', 1)[0]
    rows = [line.strip() for line in own_text.split('\n') if line.strip().startswith('ThrownBomb')]
    check(rows == [GNOME_ROW], 'exactly one creature row ThrownBomb in the content, %r' % GNOME_ROW)
    check(('    ' + GNOME_ROW) in block.split('\n'), 'the row is in own block %d' % GNOME_OWN_BLOCK)
    public_rows = read('config/creatures.cfg').split('#@own %d\n' % GNOME_OWN_BLOCK, 1)[0]
    names = re.findall(r'^\s*Name\s+(\S+)', public_rows, re.M)
    check(bool(names) and names[-1] == 'Gnome', 'own block %d belongs to the Gnome' % GNOME_OWN_BLOCK)
    skills = Path(content_packages.data_file(repo, 'config/creatureSkills.cfg')).read_text(encoding='utf-8')
    hail = skills.replace('\r\n', '\n').split('Name      Bomb Hail\n', 1)
    check(len(hail) == 2, 'Bomb Hail is in the skill table')
    if len(hail) == 2:
        baseline = hail[1].split('[/TierFour]', 1)[0]
        line = re.search(r'^BaseLine\s+(.+)$', baseline, re.M)
        check(line is not None and ' '.join(line.group(1).split()) == BOMB_HAIL_BASELINE,
              'Bomb Hail BaseLine %r' % BOMB_HAIL_BASELINE)
        if line is not None:
            check(float(line.group(1).split()[3]) == BOMB_HAIL_RANGE, 'Bomb Hail range %d' % BOMB_HAIL_RANGE)
    roots = content_packages.packages(repo)
    for relative in CONTENT_FILES:
        package, rest = relative.split('/', 1)
        check(package in roots and (Path(roots[package]) / rest).is_file(), 'content file %s' % relative)
    if 'creatures' in roots:
        gnome = Path(roots['creatures']) / 'models/Gnome.mesh'
        check(gnome.is_file() and b'GnomeBombMeshy' in gnome.read_bytes(), 'Gnome.mesh has the part GnomeBombMeshy')
    if 'effects' in roots:
        particle = (Path(roots['effects']) / 'particles/GnomeBombFuse.particle')
        check(particle.is_file() and 'particle_system GnomeBombFuse\n' in particle.read_text(encoding='utf-8')
              .replace('\r\n', '\n'), 'the fuse particle script is GnomeBombFuse')

if failures:
    print('%s: %d failure(s)' % (CHECK, len(failures)))
    raise SystemExit(1)
print('%s: ok' % CHECK)
