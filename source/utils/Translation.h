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

#ifndef TRANSLATION_H
#define TRANSLATION_H

#include <functional>
#include <map>
#include <string>
#include <vector>

//! \brief The texts the game shows to the player, in the language chosen in the settings.
//!
//! Every language is a content package (see ContentPackages) whose Package.cfg names the language in a line
//! "Language=<code>" (for example "de") and its own name in a line "LanguageName=<name>" (for example "Deutsch"). The
//! texts lie in the files of the folder "texts/" of the package, one file per area of the game; every line holds one
//! entry "<key>=<text>" in UTF-8. A text missing in the chosen language is taken from English; a key missing in English
//! too is shown as the key itself. Adding a language needs only a new package.
//!
//! Texts may hold placeholders "{name}", replaced by formatText(); every language places them in its own word order.
//! The functions without a state (parse..., chooseLanguage, formatText) have no dependencies on the GUI, so that the
//! small probes of the checks can test them.
namespace Translation
{
    //! The language used for texts missing in the chosen language and when no language can be chosen
    extern const std::string FALLBACK_LANGUAGE;
    //! Key of the definition line that names the language code of a package
    extern const std::string LANGUAGE_KEY;
    //! Key of the definition line that names the language in its own language
    extern const std::string LANGUAGE_NAME_KEY;
    //! Folder of a language package that holds its text files
    extern const std::string TEXTS_FOLDER;

    //! \brief One available language.
    struct LanguageInfo
    {
        //! Code of the language, for example "de"
        std::string mCode;
        //! Name of the language in its own language, for example "Deutsch"
        std::string mName;
        //! Folder of the language package
        std::string mDirectory;
    };

    //! \brief The value of the first line "<key>=<value>" of a definition text, without spaces and a carriage return
    //! around it, or an empty text when the text has no such line.
    std::string parseDefinitionValue(const std::string& definition, const std::string& key);

    //! \brief Reads the entries of one text file into texts. Empty lines and lines starting with '#' are skipped. In a
    //! text "\n" stands for a line break and "\\" for a backslash. A line without '=', an empty key or a key that is
    //! already in texts is an error; its description (with the line number) is added to errors and the line skipped.
    //! \return The number of entries added.
    unsigned int parseTexts(const std::string& fileText, const std::string& fileName,
        std::map<std::string, std::string>& texts, std::vector<std::string>& errors);

    //! \brief The language to use: the saved language when it is available, else the language of the system when it
    //! is available, else English.
    //! \param saved The language saved in the user configuration, empty on the first start.
    //! \param systemLanguage The code of the system display language, for example "de".
    //! \param available The codes of the available languages.
    std::string chooseLanguage(const std::string& saved, const std::string& systemLanguage,
        const std::vector<std::string>& available);

    //! \brief The text with every placeholder "{name}" of values replaced by its value; unknown placeholders stay.
    std::string formatText(const std::string& text, const std::map<std::string, std::string>& values);

    //! \brief The names of the placeholders "{name}" of a text, sorted, each once.
    std::vector<std::string> getPlaceholders(const std::string& text);

    //! \brief Reads the language packages among the given package folders and their texts. Earlier languages and
    //! texts are replaced. The chosen language becomes English.
    void loadLanguages(const std::vector<std::string>& packageDirectories);

    //! \brief Loads the languages of the content packages found by ContentPackages::discover().
    void discover();

    //! \brief The available languages, sorted by code.
    const std::vector<LanguageInfo>& getLanguages();

    //! \brief The codes of the available languages, sorted.
    std::vector<std::string> getLanguageCodes();

    //! \brief Makes code the chosen language and tells every listener when it changed. An unknown code chooses English.
    void setLanguage(const std::string& code);

    //! \brief The chosen language.
    const std::string& getLanguage();

    //! \brief The code of the display language of the system ("de" for German), or an empty text when unknown.
    std::string getSystemLanguage();

    //! \brief True when the key has a text in the chosen language or in English.
    bool hasText(const std::string& key);

    //! \brief The text of the key in the chosen language, else in English, else the key itself. UTF-8.
    std::string tr(const std::string& key);

    //! \brief The text of the key (as tr(key)) with its placeholders replaced (formatText).
    std::string tr(const std::string& key, const std::map<std::string, std::string>& values);

    //! \brief Registers a function called after the chosen language changed.
    //! \return An id for removeListener().
    unsigned int addListener(const std::function<void()>& listener);

    //! \brief Removes a listener registered with addListener(); an unknown id is ignored.
    void removeListener(unsigned int id);
}

#endif // TRANSLATION_H
