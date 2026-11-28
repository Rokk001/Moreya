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

#ifndef LEVELTEXT_H
#define LEVELTEXT_H

#include "utils/Translation.h"

#include <string>

//! \brief The texts of wing packages (Package.cfg) and level files ([Info] Name and Description, script texts) as shown
//! to the player.
//!
//! A text of these files is either written out (levels made by the editor of an older version, other tools) or a
//! text reference "@<key>" whose text lies in the language files of the language packages (keys of the areas
//! "campaign." and "level."). The reference stays in the file and in a level saved by the editor, so a level keeps
//! working in every language; it is turned into the text of the chosen language only where it is shown.
namespace LevelText
{
    //! \brief True when the text of a wing package or level file is a reference "@<key>" to a language text
    inline bool isReference(const std::string& text)
    {
        return (text.size() > 1) && (text[0] == '@');
    }

    //! \brief The text to show: the text of the chosen language (else English) for a reference "@<key>", any other
    //! text unchanged. A key without a text shows the key itself (Translation::tr).
    inline std::string display(const std::string& text)
    {
        if(!isReference(text))
            return text;

        return Translation::tr(text.substr(1));
    }
}

#endif // LEVELTEXT_H
