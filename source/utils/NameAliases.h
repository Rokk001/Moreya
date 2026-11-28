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

#ifndef NAMEALIASES_H
#define NAMEALIASES_H

#include <cstdint>
#include <string>

//! \brief Maps names that older savegames, levels and config files may still contain to the current names.
//! The old names are stored only as hashes, see NameAliases.cpp and docs/development/NAME-ALIASES.md.
namespace NameAliases
{
//! \brief 64-bit FNV-1a hash of the lowercase name
uint64_t hashName(const std::string& name);

//! \brief Returns the current name if name is an old name, name itself otherwise. Case-insensitive on the old name.
std::string resolve(const std::string& name);

//! \brief Returns the class of the successor if className names a removed creature class, className itself otherwise.
//! Case-insensitive on the removed class. Only creature class names are looked up here.
std::string resolveCreatureClass(const std::string& className);

//! \brief The class a creature of a savegame or level written before the current creature roster is loaded as, by
//! the side of its seat: a keeper-side or rogue creature of the class that moved to the hero side is loaded as that
//! class's successor on the other sides; a hero-side creature and every other class keep their class.
//! \param className The class after resolveCreatureClass.
//! \param heroSide True when the creature belongs to a hero seat.
std::string resolveOldCreatureClassForSide(const std::string& className, bool heroSide);
}

#endif // NAMEALIASES_H
