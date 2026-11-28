/*
 * Copyright (C) 2026 OpenDungeons Team
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
#ifndef ENGLISHTESTTEXTS_H
#define ENGLISHTESTTEXTS_H

#include "utils/Translation.h"

#include <boost/filesystem.hpp>

#include <algorithm>
#include <cstdlib>
#include <string>
#include <vector>

//! \brief Lets a test read the English texts of the game from the language package of the content (the folders of
//! MOREYA_CONTENT_DIR), so that it can compare the texts the game shows.
namespace EnglishTestTexts
{
//! \brief Loads the language packages of the folder named by MOREYA_CONTENT_DIR and chooses English.
//! \return True when the English texts are there; false without content (the texts are then their keys).
inline bool load()
{
    std::vector<std::string> folders;
    const char* variable = std::getenv("MOREYA_CONTENT_DIR");
    if(variable != nullptr && !std::string(variable).empty())
    {
        boost::system::error_code error;
        if(boost::filesystem::is_directory(variable, error))
        {
            for(boost::filesystem::directory_iterator it(variable, error);
                !error && (it != boost::filesystem::directory_iterator()); it.increment(error))
            {
                if(boost::filesystem::is_regular_file(it->path() / "Package.cfg", error))
                    folders.push_back(it->path().string());
            }
        }
    }
    std::sort(folders.begin(), folders.end());
    Translation::loadLanguages(folders);
    Translation::setLanguage("en");
    const std::vector<std::string> codes = Translation::getLanguageCodes();
    return std::find(codes.begin(), codes.end(), std::string("en")) != codes.end();
}

//! \brief The text a test expects: the English text when the content is there, else the key of the text (what the
//! game shows when no language is loaded).
//! \param loaded The result of load()
//! \param english The English text
//! \param key The key of the text
inline std::string expected(bool loaded, const std::string& english, const std::string& key)
{
    return loaded ? english : key;
}
}

#endif // ENGLISHTESTTEXTS_H
