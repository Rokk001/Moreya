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

#ifndef SOCIALDATA_H
#define SOCIALDATA_H

#include <istream>
#include <map>
#include <set>
#include <stdint.h>
#include <string>
#include <vector>

namespace social
{

//! \brief Name pools of one group of creature classes (see config/social-names.cfg).
struct NameGroup
{
    NameGroup() :
        mAgeMin(1),
        mAgeMax(30)
    {
        mGenderWeights[0] = 1;
        mGenderWeights[1] = 1;
        mGenderWeights[2] = 1;
    }

    //! Name of the group ("monster" is the fallback group)
    std::string mName;
    //! Creature classes served by the group
    std::vector<std::string> mClasses;
    //! Lowest age a creature of the group can get
    int32_t mAgeMin;
    //! Highest age a creature of the group can get
    int32_t mAgeMax;
    //! Weights of female, male and unspecified
    uint32_t mGenderWeights[3];
    //! Given names for female, male and unspecified
    std::vector<std::string> mGiven[3];
    //! Surnames, used for some creatures instead of a title
    std::vector<std::string> mSurnames;
    //! Titles, used for some creatures instead of a surname
    std::vector<std::string> mTitles;
    std::vector<std::string> mHometowns;
    //! Replacements of the age number for some creatures
    std::vector<std::string> mAgeJokes;

    //! \brief The title with the given index of mTitles in the chosen language (key
    //! "social.name.<group>.title.<number>", the number counts from 1 in the order of the pool). Without a text in
    //! the language files the title of the file is returned.
    std::string getDisplayTitle(std::size_t index) const;

    //! \brief The hometown with the given index of mHometowns in the chosen language (key
    //! "social.name.<group>.hometown.<number>"), else the hometown of the file.
    std::string getDisplayHometown(std::size_t index) const;

    //! \brief The age joke with the given index of mAgeJokes in the chosen language (key
    //! "social.name.<group>.agejoke.<number>"), else the joke of the file.
    std::string getDisplayAgeJoke(std::size_t index) const;
};

//! \brief A text of the social code (room names of the posts, relationship states, fallbacks of the generator) in the
//! chosen language: the text of the key in the language files, else the given English text.
std::string getSocialCodeText(const std::string& key, const std::string& english);

//! \brief A text of config/social-texts.cfg together with the scope it applies to
//! ("*", a group name, a creature class name, "worker" or "fighter").
struct ScopedText
{
    //! Scope the text applies to
    std::string mScope;
    //! The text of the file, shown only when the language files have no text for mKey
    std::string mText;
    //! Key of the text in the language files ("social.post.eat.003"), empty for the texts that are not translated here
    std::string mKey;
};

//! \brief Loads config/social-names.cfg and config/social-texts.cfg.
//! The player sees the texts of the language files: every title, hometown, age joke and text line (except the class
//! names) has a key (see NameGroup::getDisplayTitle and makeTextKey); the text of the file is only the English
//! text for a missing language file (and for the tests that read their own texts from a stream).
//! The files are read line based (columns separated by tabs, values may contain spaces).
//! Nothing here needs Ogre, CEGUI or the game: errors are collected and can be read with
//! getErrors() so that the caller can log them once. A missing or broken file never
//! throws; the generator then falls back to built-in texts.
class SocialData
{
public:
    static const std::string FALLBACK_GROUP;

    SocialData();

    //! \brief Loads both files from the given directory (with a trailing slash or not).
    //! Returns true if both could be read without errors.
    bool loadFromDirectory(const std::string& directory);
    bool loadNamesFile(const std::string& path);
    bool loadTextsFile(const std::string& path);
    bool loadNames(std::istream& input, const std::string& source);
    bool loadTexts(std::istream& input, const std::string& source);

    //! \brief Group serving the class. Classes without a group use the group "monster"
    //! (and are remembered in getUnmappedClasses()).
    const NameGroup& getGroupForClass(const std::string& className) const;

    //! \brief True if a name group explicitly lists the class.
    bool hasGroupForClass(const std::string& className) const;

    const std::vector<NameGroup>& getGroups() const
    { return mGroups; }

    //! \brief Texts of the given key ("Job", "Like", "MoodLine:Hungry", "Post:eat", ...)
    //! whose scope is one of the given scopes, in file order. Every text is the one of the chosen language
    //! (Translation::tr of its key, see ScopedText::mKey), so the order and the choice by index are the same in
    //! every language; a text without an entry in the language files is the text of the file.
    void getTexts(const std::string& key, const std::vector<std::string>& scopes,
        std::vector<std::string>& texts) const;

    //! \brief Number of texts stored for a key, whatever the scope.
    uint32_t getTextCount(const std::string& key) const;

    const std::vector<std::string>& getErrors() const
    { return mErrors; }

    const std::set<std::string>& getUnmappedClasses() const
    { return mUnmappedClasses; }

private:
    void clearNames();
    void clearTexts();
    void ensureFallbackGroup();
    bool parseNameGroupLine(const std::vector<std::string>& fields, NameGroup& group, std::string& error);
    void addError(const std::string& source, uint32_t lineNumber, const std::string& message);

    //! \brief The key of a text line in the language files: "social.<type>.<number>" or, for the lines with a state
    //! or category, "social.<type>.<state>.<number>"; the number counts the lines of that type (and state) in the file.
    //! Empty for the lines that are not translated here (ClassName).
    static std::string makeTextKey(const std::string& type, const std::string& state, uint32_t number);

    //! All name groups in file order
    std::vector<NameGroup> mGroups;
    //! Index into mGroups for every listed creature class
    std::map<std::string, std::size_t> mClassToGroup;
    //! Texts by key, in file order
    std::map<std::string, std::vector<ScopedText> > mTexts;
    //! Messages of everything that could not be read
    std::vector<std::string> mErrors;
    //! Classes asked for that no group lists (filled by const lookups)
    mutable std::set<std::string> mUnmappedClasses;
};

}

#endif // SOCIALDATA_H
