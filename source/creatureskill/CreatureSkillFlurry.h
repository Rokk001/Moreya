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

#ifndef CREATURESKILLFLURRY_H
#define CREATURESKILLFLURRY_H

#include "creatureskill/CreatureSkill.h"

#include <cstdint>
#include <iosfwd>
#include <string>

//! \brief FLURRY: quick melee blows on every enemy creature within the radius of the caster. Line: "Flurry cooldown
//! warmup LevelMin Range Radius Blows Factor"; the rank value is a "blows/factor" pair: every enemy gets Blows blows,
//! each doing Factor times the damage of a melee blow of the caster. A blow cannot be critical unless the skill has
//! CAN_CRIT. PUSH / PULL move every enemy hit the first number of tiles away from / towards the caster, DOUBLE_CAST
//! repeats the whole flurry once, BLEED_ON_HIT puts a bleeding of the first number of damage over the second number
//! of turns on every enemy hit, LARGER_RADIUS multiplies the radius. An enemy with DODGE_AREA may dodge the flurry.
class CreatureSkillFlurry : public CreatureSkill
{
public:
    //! \brief Creates a skill with neutral values; the values come from the loaded skill line.
    CreatureSkillFlurry() :
        mCreatureLevelMin(0),
        mRange(0.0),
        mRadius(0.0),
        mBlows(0.0),
        mFactor(0.0)
    {}

    //! \brief Destroys the skill.
    virtual ~CreatureSkillFlurry()
    {}

    //! \brief Returns the name of the skill class used in skill lines ("Flurry").
    virtual const std::string& getSkillName() const override;

    //! \brief Returns the range on an enemy creature, 0 for any other target.
    virtual double getRangeMax(const Creature* creature, GameEntity* entityAttack) const override;

    //! \brief Tells whether the creature has the level the skill needs (0 is reached with rank 1).
    virtual bool canBeUsedBy(const Creature* creature) const override;

    //! \brief The flurry is never used without a target.
    virtual bool tryUseSupport(GameMap& gameMap, Creature* creature) const override
    { return false; }

    //! \brief Strikes every enemy within the radius.
    virtual bool tryUseFight(GameMap& gameMap, Creature* creature, float range,
        GameEntity* attackedObject, Tile* attackedTile, bool ko, bool notifyPlayerIfHit) const override;

    //! \brief Returns a copy of the skill.
    virtual CreatureSkillFlurry* clone() const override;

    //! \brief Tells whether the other skill is the same class with the same values.
    virtual bool isEqual(const CreatureSkill& creatureSkill) const override;

    //! \brief Appends the names of the columns of the skill line to the format string.
    virtual void getFormatString(std::string& format) const override;
    //! \brief Writes the columns of the skill line.
    virtual void exportToStream(std::ostream& os) const override;
    //! \brief Reads the columns of the skill line; returns false when one is missing or malformed.
    virtual bool importFromStream(std::istream& is) override;

private:
    //! \brief Creature level needed to use the skill (0: reached with rank 1)
    uint32_t mCreatureLevelMin;
    //! \brief Range in tiles to the attacked creature
    double mRange;
    //! \brief Radius in tiles around the caster
    double mRadius;
    //! \brief Blows every enemy gets
    double mBlows;
    //! \brief Factor on the damage of a melee blow
    double mFactor;
};

#endif // CREATURESKILLFLURRY_H
