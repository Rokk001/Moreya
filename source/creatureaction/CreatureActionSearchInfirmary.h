/*
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

#ifndef CREATUREACTIONSEARCHINFIRMARY_H
#define CREATUREACTIONSEARCHINFIRMARY_H

#include "creatureaction/CreatureAction.h"

class Tile;

//! \brief A creature sick with the plague walks by itself to the nearest infirmary of its seat with a free cot it can
//! be admitted to, whatever its HP, and is admitted there (the admission cures it, the fee is paid as for a carried
//! patient). Without such an infirmary, or once the creature is not sick any more, the action ends.
class CreatureActionSearchInfirmary : public CreatureAction
{
public:
    //! \brief Creates the walk of the given sick creature.
    CreatureActionSearchInfirmary(Creature& creature) :
        CreatureAction(creature)
    {}

    virtual ~CreatureActionSearchInfirmary()
    {}

    //! \brief Returns the type of the action.
    CreatureActionType getType() const override
    { return CreatureActionType::searchInfirmary; }

    //! \brief Gets the function that runs this action.
    std::function<bool()> action() override; // allowed-lambda: signature required by CreatureAction

    //! \brief One turn of the walk: admission when the creature stands in an infirmary that takes it, otherwise a path
    //! to the cot of the nearest one.
    //! \param creature The sick creature.
    //! \return True when the action ended or a walk was started and the creature may go on in the same turn.
    static bool handleSearchInfirmary(Creature& creature);

    //! \brief The cot tile of the nearest infirmary of the creature's seat that would admit the sick creature now and
    //! that it can reach, or nullptr.
    //! \param creature The sick creature.
    static Tile* findInfirmaryTile(Creature& creature);
};

#endif // CREATUREACTIONSEARCHINFIRMARY_H
