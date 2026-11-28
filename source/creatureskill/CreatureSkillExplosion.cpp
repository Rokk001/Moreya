/*
 *  Copyright (C) 2011-2016  OpenDungeons Team
 *
 *  This program is free software: you can redistribute it and/or modify
 *  it under the terms of the GNU General Public License as published by
 *  the Free Software Foundation, either version 3 of the License, or
 *  (at your option) any later version.
 *
 *  This program is distributed in the hope that it will be useful,
 *  but WITHOUT ANY WARRANTY; without even the implied warranty of
 *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *  GNU General Public License for more details.
 *
 *  You should have received a copy of the GNU General Public License
 *  along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

#include "creatureskill/CreatureSkillExplosion.h"

#include "creatureeffect/CreatureEffectExplosion.h"
#include "creatureeffect/CreatureEffectStrengthChange.h"
#include "creatureskill/CreatureSkillManager.h"
#include "entities/Creature.h"
#include "entities/CreatureDefinition.h"
#include "entities/GameEntityType.h"
#include "entities/MissileBomb.h"
#include "entities/Tile.h"
#include "gamemap/GameMap.h"
#include "sound/SoundEffectsManager.h"
#include "utils/ConfigManager.h"
#include "utils/LogManager.h"

#include <istream>
#include <vector>

const std::string CreatureSkillExplosionName = "Explosion";

namespace
{
class CreatureSkillExplosionFactory : public CreatureSkillFactory
{
    CreatureSkill* createCreatureSkill() const override
    { return new CreatureSkillExplosion; }

    const std::string& getCreatureSkillName() const override
    { return CreatureSkillExplosionName; }
};

// Register the factory
static CreatureSkillRegister reg(new CreatureSkillExplosionFactory);

//! \brief Height above the ground the thrown bomb flies at (the height of the other creature missiles)
const Ogre::Real THROWN_BOMB_HEIGHT = 0.3;
//! \brief Below this squared distance the target counts as on the thrower's tile: the bomb gets a fixed direction
const Ogre::Real THROWN_BOMB_MIN_SQUARED_DISTANCE = 0.0001f;

//! \brief Throws the bomb of a creature type with the key ThrownBomb at the attacked creature (the first of targets,
//! the creatures the blast hit). Look only: the bomb lands on the target tile in the turn of the throw and has no
//! effect; the explosion was applied by the skill. The clients show the explosions of all targets when it lands.
void launchThrownBomb(GameMap& gameMap, Creature& thrower, const std::vector<Creature*>& targets, Tile* targetTile)
{
    Tile* throwerTile = thrower.getPositionTile();
    if((throwerTile == nullptr) || (targetTile == nullptr) || targets.empty())
        return;

    std::vector<std::string> targetNames;
    for(Creature* target : targets)
        targetNames.push_back(target->getName());

    const CreatureDefinition* definition = thrower.getDefinition();
    Ogre::Vector3 position = thrower.getPosition();
    position.z = THROWN_BOMB_HEIGHT;
    Ogre::Vector3 direction(static_cast<Ogre::Real>(targetTile->getX()), static_cast<Ogre::Real>(targetTile->getY()),
        THROWN_BOMB_HEIGHT);
    direction = direction - position;
    const double distance = static_cast<double>(direction.length());
    if(direction.squaredLength() < THROWN_BOMB_MIN_SQUARED_DISTANCE)
        direction = Ogre::Vector3::UNIT_X;
    else
        direction.normalise();

    MissileBomb* bomb = new MissileBomb(&gameMap, thrower.getSeat(), thrower.getName(),
        definition->getThrownBombMesh(), definition->getThrownBombParticle(), definition->getThrownBombMaterial(),
        direction, MissileBomb::flightSpeed(distance), targets.front(), targetTile, targetNames);
    bomb->addToGameMap();
    bomb->createMesh();
    bomb->setPosition(position);
    // Announce the bomb before its flight, like the other creature missiles
    bomb->notifySeatsWithVision(throwerTile->getSeatsWithVision());
    bomb->doUpkeep();
}
}

const std::string& CreatureSkillExplosion::getSkillName() const
{
    return CreatureSkillExplosionName;
}

double CreatureSkillExplosion::getRangeMax(const Creature* creature, GameEntity* entityAttack) const
{
    // Explosion can be cast on creatures only
    if(entityAttack->getObjectType() != GameEntityType::creature)
        return 0.0;

    return mMaxRange;
}

bool CreatureSkillExplosion::canBeUsedBy(const Creature* creature) const
{
    if(creature->getLevel() < mCreatureLevelMin)
        return false;

    return true;
}

//! \brief Puts the blast on the attacked creature; the rank properties AREA, LARGER_RADIUS, WEAKEN, FEAR and
//! BURNING_GROUND widen it and the target bonuses of the caster scale it per creature hit.
bool CreatureSkillExplosion::tryUseFight(GameMap& gameMap, Creature* creature, float range,
        GameEntity* attackedObject, Tile* attackedTile, bool ko, bool notifyPlayerIfHit) const
{
    if(attackedObject->getObjectType() != GameEntityType::creature)
    {
        OD_LOG_ERR("creature=" + creature->getName() + ", attackedObject=" + attackedObject->getName() + ", attackedTile=" + Tile::displayAsString(attackedTile));
        return false;
    }

    Creature* attackedCreature = static_cast<Creature*>(attackedObject);
    // The damage follows the SkillDamageFactor of the creature type
    double damageFactor = creature->getDefinition()->getSkillDamageFactor();
    // A skill of the skill tree also scales with the level, the health tier and the spell passives of the creature
    if(isTreeSkill())
        damageFactor *= creature->getTreeSpellDamageFactor();
    // The blast has no hit roll: it is critical when the roll succeeds, which multiplies its damage values (the
    // magical defense of the target is subtracted from the multiplied values by the effect)
    const bool critical = creature->rollCritical();
    if(critical)
        damageFactor *= ConfigManager::getSingleton().getCritDamageMultiplier();

    // Rank property AREA: every enemy within its radius (times LARGER_RADIUS) of the target is hit too
    std::vector<Creature*> targets;
    targets.push_back(attackedCreature);
    if(hasProperty("AREA"))
    {
        const std::vector<Creature*> nearby = creature->getEnemyCreaturesNear(attackedCreature->getPosition(),
            getPropertyValue("AREA", 0, 0.0) * getPropertyValue("LARGER_RADIUS", 0, 1.0));
        for(Creature* enemy : nearby)
        {
            if(enemy != attackedCreature && !enemy->rollAreaDodge())
                targets.push_back(enemy);
        }
    }

    for(Creature* target : targets)
    {
        const double targetFactor = damageFactor * creature->getSkillTargetDamageFactor(*target, this);
        CreatureEffectExplosion* effect = new CreatureEffectExplosion(mEffectDuration, mEffectValue * targetFactor,
            "SpellCreatureExplosion");
        effect->setDamageMin(mEffectValueMin * targetFactor);
        target->addCreatureEffect(effect);
        // Rank properties WEAKEN (factor, turns) and FEAR (turns) on every creature hit
        if(hasProperty("WEAKEN"))
        {
            CreatureEffectStrengthChange* weaken = new CreatureEffectStrengthChange(
                getPropertyValue("WEAKEN", 1, mEffectDuration), getPropertyValue("WEAKEN", 0, 1.0), "SpellCreatureWeak");
            tagEffect(weaken);
            target->addCreatureEffect(weaken);
        }
        if(hasProperty("FEAR"))
            target->fleeFromSkill(*creature, getPropertyValue("FEAR", 0, 0.0));
    }
    if(critical)
        attackedCreature->fireCriticalSpell(creature->getName());

    // Rank property BURNING_GROUND: the ground around the target burns (damage per turn, turns, radius)
    if(hasProperty("BURNING_GROUND"))
        creature->addSkillBurningGround(*this, attackedTile);

    // Look only: a creature type with the key ThrownBomb throws its bomb at the target; the hit above is unchanged
    if(creature->getDefinition()->throwsBomb())
        launchThrownBomb(gameMap, *creature, targets, attackedTile);

    return true;
}

CreatureSkillExplosion* CreatureSkillExplosion::clone() const
{
    return new CreatureSkillExplosion(*this);
}

void CreatureSkillExplosion::getFormatString(std::string& format) const
{
    CreatureSkill::getFormatString(format);
    if(!format.empty())
        format += "\t";

    format += "RangeMax\tLevelMin\tEffectDuration\tEffectValue\tEffectValueMin";

}

void CreatureSkillExplosion::exportToStream(std::ostream& os) const
{
    CreatureSkill::exportToStream(os);
    os << "\t" << mMaxRange;
    os << "\t" << mCreatureLevelMin;
    os << "\t" << mEffectDuration;
    os << "\t" << mEffectValue;
    os << "\t" << mEffectValueMin;
}

bool CreatureSkillExplosion::importFromStream(std::istream& is)
{
    if(!CreatureSkill::importFromStream(is))
        return false;

    if(!(is >> mMaxRange))
        return false;
    if(!(is >> mCreatureLevelMin))
        return false;
    if(!(is >> mEffectDuration))
        return false;
    if(!(is >> mEffectValue))
        return false;
    mEffectValueMin = mEffectValue;
    is >> std::ws;
    if(is.eof())
        is.clear();
    else if(!(is >> mEffectValueMin))
        return false;

    return true;
}

bool CreatureSkillExplosion::isEqual(const CreatureSkill& creatureSkill) const
{
    if(!CreatureSkill::isEqual(creatureSkill))
        return false;

    const CreatureSkillExplosion* skill = dynamic_cast<const CreatureSkillExplosion*>(&creatureSkill);
    if(skill == nullptr)
        return false;

    if(mMaxRange != skill->mMaxRange)
        return false;
    if(mCreatureLevelMin != skill->mCreatureLevelMin)
        return false;
    if(mEffectDuration != skill->mEffectDuration)
        return false;
    if(mEffectValue != skill->mEffectValue)
        return false;
    if(mEffectValueMin != skill->mEffectValueMin)
        return false;

    return true;
}
