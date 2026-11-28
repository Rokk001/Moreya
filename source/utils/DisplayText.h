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

#ifndef DISPLAYTEXT_H
#define DISPLAYTEXT_H

#include <cctype>
#include <string>

//! \brief The display names of the data tables (items, equipment, potions, herbs, creature skills) in the chosen
//! language.
//!
//! The tables keep the English name in their own field (it is the fallback and the source of the English language
//! file); the player reads the text of the language files under a key made from the internal id of the entry, for
//! example "item.poor_head.poor.name" or "potion.healing_small.name" (area, id in lower case, optional part, ".name").
//! The functions are header only and reach the language system through a lookup function that the game installs at
//! start (ODApplication); without it, as in the small probes of the checks, every name stays the English text of the
//! table.
namespace DisplayText
{
    //! \brief Looks a key up in the chosen language (then English); false when no text exists for the key.
    typedef bool (*LookupFunction)(const std::string& key, std::string& text);

    //! \brief The installed lookup function, null while none is installed.
    inline LookupFunction& getLookup()
    {
        static LookupFunction lookup = nullptr;
        return lookup;
    }

    //! \brief Installs the function that reads the texts of the language files.
    inline void setLookup(LookupFunction lookup)
    {
        getLookup() = lookup;
    }

    //! \brief The text in lower case (ASCII letters only), as used in the keys.
    inline std::string lowerKeyPart(const std::string& text)
    {
        std::string result = text;
        for(std::string::size_type index = 0; index < result.size(); ++index)
            result[index] = static_cast<char>(std::tolower(static_cast<unsigned char>(result[index])));
        return result;
    }

    //! \brief The key "<area>.<id>.name" or, with a part, "<area>.<id>.<part>.name"; id and part in lower case.
    inline std::string makeKey(const std::string& area, const std::string& id, const std::string& part = std::string())
    {
        std::string key = area + "." + lowerKeyPart(id);
        if(!part.empty())
            key += "." + lowerKeyPart(part);
        return key + ".name";
    }

    //! \brief The text of the key in the chosen language, or the fallback (the English name of the table) when no
    //! text exists or no lookup function is installed.
    inline std::string translated(const std::string& key, const std::string& fallback)
    {
        LookupFunction lookup = getLookup();
        std::string text;
        if(lookup != nullptr && lookup(key, text))
            return text;
        return fallback;
    }
}

#endif // DISPLAYTEXT_H
