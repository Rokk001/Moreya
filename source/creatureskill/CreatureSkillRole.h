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

#ifndef CREATURESKILLROLE_H
#define CREATURESKILLROLE_H

#include "creatureskill/CreatureSkill.h"

#include <cstdint>
#include <iosfwd>
#include <string>
#include <vector>

class Creature;
class GameEntity;
class GameMap;
class Tile;

//! \brief Common base of the skill kinds of the role groups (taunt, parry, ally defence, shields, instant heal, heals
//! and damage over time, mark, hold, life drain for allies). They share one line layout:
//! "Class cooldown warmup LevelMin Range Radius Duration Value" (CreatureSkillTree builds it from the table row). Each
//! kind is its own class derived from this one; this class only reads and writes the columns and offers the helpers
//! for the rank properties that several kinds share (LONGER, LARGER_RADIUS, AREA, EXTRA_TARGETS).
class CreatureSkillRole : public CreatureSkill
{
public:
    //! \brief Creates a skill with neutral values; the values come from the loaded skill line.
    CreatureSkillRole() :
        mCreatureLevelMin(0),
        mRange(0.0),
        mRadius(0.0),
        mDuration(0.0),
        mValue(0.0)
    {}

    //! \brief Destroys the skill.
    virtual ~CreatureSkillRole()
    {}

    //! \brief Tells whether the creature has the level the skill needs (0 is reached with rank 1).
    virtual bool canBeUsedBy(const Creature* creature) const override;

    //! \brief A role skill that is not used at the start of a turn returns false.
    virtual bool tryUseSupport(GameMap& gameMap, Creature* creature) const override
    { return false; }

    //! \brief A role skill that is not used against a target returns false.
    virtual bool tryUseFight(GameMap& gameMap, Creature* creature, float range,
        GameEntity* attackedObject, Tile* attackedTile, bool ko, bool notifyPlayerIfHit) const override
    { return false; }

    //! \brief Tells whether the other skill is the same class with the same values.
    virtual bool isEqual(const CreatureSkill& creatureSkill) const override;

    //! \brief Appends the names of the columns of the skill line to the format string.
    virtual void getFormatString(std::string& format) const override;
    //! \brief Writes the columns of the skill line.
    virtual void exportToStream(std::ostream& os) const override;
    //! \brief Reads the columns of the skill line; returns false when one is missing or malformed.
    virtual bool importFromStream(std::istream& is) override;

    //! \brief The rank value of the skill (its meaning depends on the kind).
    inline double getValue() const
    { return mValue; }

protected:
    //! \brief The duration column times the LONGER property.
    double getEffectDuration() const;

    //! \brief The radius column (or the first number of AREA when it has one) times the LARGER_RADIUS property.
    double getEffectRadius() const;

    //! \brief The range for a fight skill on an enemy creature; 0 for other targets and for a creature that already
    //! carries as many effects of this skill as the STACK property allows (1 without it).
    //! \param creature The caster.
    //! \param entityAttack The target.
    //! \param effectName The name of the effect the skill puts on the target.
    double getRangeOnCreature(const Creature* creature, GameEntity* entityAttack, const std::string& effectName) const;

    //! \brief The creatures one use of the skill acts on: the target, then with AREA every enemy of the caster within
    //! the AREA radius of the target, else with EXTRA_TARGETS up to that many enemies nearest the target (within its
    //! second number in tiles, else within the range of the skill).
    std::vector<Creature*> getTargets(Creature& caster, Creature& target) const;

    //! \brief Creature level needed to use the skill (0: reached with rank 1)
    uint32_t mCreatureLevelMin;
    //! \brief Range in tiles to the target
    double mRange;
    //! \brief Radius in tiles of an area around the caster
    double mRadius;
    //! \brief Turns the effect lasts
    double mDuration;
    //! \brief The rank value
    double mValue;
};

#endif // CREATURESKILLROLE_H
