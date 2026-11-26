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

#include "utils/NameAliases.h"

#include <cctype>
#include <cstddef>

namespace NameAliases
{
namespace
{
struct AliasEntry
{
    uint64_t mOldNameHash;
    const char* mNewName;
};

// Hash (see hashName) of an old name and the name that replaced it.
const AliasEntry ALIASES[] =
{
    { 0xc2e36dae4fa92ba9ULL, "Defector" },
    { 0xebb6ba9f1bb36afcULL, "HexenHen" },
    { 0x3ebfce12ba6591ceULL, "DefectorPrice" },
    { 0x07189ed04edc38a9ULL, "HexenHenPrice" },
    { 0x1eb5d3c128e01e4bULL, "DefectorNbTurns" },
    { 0x83fd4821972c1610ULL, "HexenHenNbTurns" },
    { 0x0d966eb99b481be4ULL, "DefectorCooldown" },
    { 0x751fda58ff8e9335ULL, "HexenHenCooldown" },
    { 0xea6e2641e5aa5320ULL, "WatchBannerCostPerTile" },
    { 0xf11f805888770df5ULL, "WatchBannerWorkshopPointsPerTile" },
    { 0x1b8ed332f5999e5cULL, "WatchBannerAuraTiles" },
    { 0xea5ce66d289c14b4ULL, "IronboundDoorCostPerTile" },
    { 0x0659273bfd7b79b6ULL, "IronboundDoorPointsPerTile" },
    { 0x4d1e3e15545063c4ULL, "IronboundDoorHP" },
    { 0x6f9980a82006cc8cULL, "RunedDoorCostPerTile" },
    { 0xcae444515713542eULL, "RunedDoorPointsPerTile" },
    { 0x486cf42cdb24c44cULL, "RunedDoorHP" },
    { 0x5dbabe71752a61c2ULL, "RunedDoorManaToFire" },
    { 0x9a76263f0432455bULL, "RunedDoorRegenPerTurn" },
    { 0xac46967da4c30effULL, "RunedDoorReloadTurns" },
    { 0xc64a120ca900f225ULL, "RunedDoorDamage" },
    { 0xfea599dbea82e978ULL, "spellHexenHen" },
    { 0xaf1772cc154463d5ULL, "spellDefector" },
    { 0xd93144790c52abbfULL, "trapDoorIronbound" },
    { 0xa6a9ead8659e219dULL, "trapDoorRuned" },
    { 0x979dc0f5d17eadfdULL, "trapWatchBanner" },
    { 0x6bfc6edafe8335dcULL, "ManaWellBonusPerTile" },
    { 0x72e77dd3320fce48ULL, "RoomConvertClaimRate" },
    { 0xcabd9ef942198d29ULL, "manaWellGround" },
};

// Hash (see hashName) of a removed creature class and the class of its successor. Kept apart from ALIASES so that
// only creature class names are mapped to a creature class.
const AliasEntry CREATURE_CLASS_ALIASES[] =
{
    { 0x89f6be1960ff4c78ULL, "Banshee" },
    { 0x2d9f61f3374744a8ULL, "Ghoul" },
    { 0xc8f622466403f436ULL, "Witch" },
    { 0x06c60ee0cc2939feULL, "Butcher" },
    { 0xd492fe6ba7915f3bULL, "DarkElf" },
    { 0x3c55031b39a7eb3eULL, "Hunter" },
    { 0xe75ffbe9a99a68ccULL, "Paladin" },
    { 0x9e417bb7b4c3bccfULL, "Priestess" },
    { 0x0e0008a6a918a58aULL, "CrystalGolem" },
    { 0x7153171d9afb2c02ULL, "Cyclops" },
    { 0xa494741dbc7edaa5ULL, "Minotaur" },
    { 0xcb5b3bd5f628d1ccULL, "Werewolf" },
};

// The class that left its side: a keeper-side or rogue creature of this class in a file written before the current
// creature roster is loaded as SIDE_SUCCESSOR_CLASS; on the hero side it stays.
const char* const SIDE_MOVED_CLASS = "DarkElf";
const char* const SIDE_SUCCESSOR_CLASS = "Banshee";

//! \brief Returns the new name of the entry whose hash is the hash of the name, the name itself when there is none.
std::string lookUp(const AliasEntry* entries, std::size_t count, const std::string& name)
{
    if(name.empty())
        return name;

    uint64_t hash = hashName(name);
    for(std::size_t i = 0; i < count; ++i)
    {
        if(entries[i].mOldNameHash == hash)
            return entries[i].mNewName;
    }

    return name;
}
}

uint64_t hashName(const std::string& name)
{
    uint64_t hash = 14695981039346656037ULL;
    for(std::size_t i = 0; i < name.size(); ++i)
    {
        hash ^= static_cast<uint64_t>(std::tolower(static_cast<unsigned char>(name[i])));
        hash *= 1099511628211ULL;
    }
    return hash;
}

std::string resolve(const std::string& name)
{
    if(name.empty())
        return name;

    uint64_t hash = hashName(name);
    for(std::size_t i = 0; i < sizeof(ALIASES) / sizeof(ALIASES[0]); ++i)
    {
        if(ALIASES[i].mOldNameHash == hash)
            return ALIASES[i].mNewName;
    }

    return name;
}

//! \brief Looks the class name up in the table of the removed creature classes.
std::string resolveCreatureClass(const std::string& className)
{
    return lookUp(CREATURE_CLASS_ALIASES, sizeof(CREATURE_CLASS_ALIASES) / sizeof(CREATURE_CLASS_ALIASES[0]),
        className);
}

//! \brief The class that left its side becomes its successor on every side but the hero side.
std::string resolveOldCreatureClassForSide(const std::string& className, bool heroSide)
{
    if(!heroSide && (className == SIDE_MOVED_CLASS))
        return SIDE_SUCCESSOR_CLASS;

    return className;
}
}
