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

#include "social/SocialData.h"
#include "utils/ContentPackages.h"
#include "utils/Translation.h"

#include <cstdlib>
#include <fstream>
#include <sstream>

namespace social
{

const std::string SocialData::FALLBACK_GROUP = "monster";

namespace
{

std::string trimText(const std::string& text)
{
    const char* whitespace = " \t\r\n";
    std::string::size_type first = text.find_first_not_of(whitespace);
    if(first == std::string::npos)
        return std::string();
    std::string::size_type last = text.find_last_not_of(whitespace);
    return text.substr(first, last - first + 1);
}

void splitAtTabs(const std::string& line, std::vector<std::string>& fields)
{
    fields.clear();
    std::string::size_type start = 0;
    while(true)
    {
        std::string::size_type tab = line.find('\t', start);
        if(tab == std::string::npos)
        {
            fields.push_back(trimText(line.substr(start)));
            break;
        }
        fields.push_back(trimText(line.substr(start, tab - start)));
        start = tab + 1;
    }
    while((!fields.empty()) && fields.back().empty())
        fields.pop_back();
}

bool parseNumber(const std::string& text, int32_t& value)
{
    if(text.empty())
        return false;
    char* end = NULL;
    long number = std::strtol(text.c_str(), &end, 10);
    if((end == NULL) || (*end != '\0'))
        return false;
    value = static_cast<int32_t>(number);
    return true;
}

std::string buildDirectoryPath(const std::string& directory)
{
    if(directory.empty())
        return directory;
    char last = directory[directory.size() - 1];
    if((last == '/') || (last == '\\'))
        return directory;
    return directory + "/";
}

bool isKnownTextKey(const std::string& key)
{
    return (key == "Job") || (key == "Like") || (key == "Dislike") || (key == "Quirk") ||
        (key == "Bio") || (key == "Relation") || (key == "ClassName");
}

//! \brief The text with its ASCII capital letters made lower case.
std::string toLowerAscii(const std::string& text)
{
    std::string result = text;
    for(std::size_t i = 0; i < result.size(); ++i)
    {
        if((result[i] >= 'A') && (result[i] <= 'Z'))
            result[i] = static_cast<char>(result[i] - 'A' + 'a');
    }
    return result;
}

//! \brief The number as three digits ("007"), more digits when it is larger.
std::string formatKeyNumber(uint32_t number)
{
    std::ostringstream stream;
    stream.width(3);
    stream.fill('0');
    stream << number;
    return stream.str();
}

//! \brief The text of the key in the chosen language, or the text of the file when the language files have none.
std::string resolveText(const std::string& key, const std::string& fileText)
{
    if(key.empty() || !Translation::hasText(key))
        return fileText;
    return Translation::tr(key);
}

//! \brief The text of the entry with the given index (counting from 1 in its key) of a pool of a name group.
std::string resolveNameText(const NameGroup& group, const char* kind, const std::vector<std::string>& pool,
    std::size_t index)
{
    if(index >= pool.size())
        return std::string();
    return resolveText("social.name." + group.mName + "." + kind + "." + formatKeyNumber(static_cast<uint32_t>(index + 1)),
        pool[index]);
}

}

//! \brief The title with the given index in the chosen language.
std::string NameGroup::getDisplayTitle(std::size_t index) const
{
    return resolveNameText(*this, "title", mTitles, index);
}

//! \brief The hometown with the given index in the chosen language.
std::string NameGroup::getDisplayHometown(std::size_t index) const
{
    return resolveNameText(*this, "hometown", mHometowns, index);
}

//! \brief The age joke with the given index in the chosen language.
std::string NameGroup::getDisplayAgeJoke(std::size_t index) const
{
    return resolveNameText(*this, "agejoke", mAgeJokes, index);
}

//! \brief The key of a text line of social-texts.cfg in the language files.
std::string SocialData::makeTextKey(const std::string& type, const std::string& state, uint32_t number)
{
    if(type == "ClassName")
        return std::string();

    std::string key = "social." + ((type == "MoodLine") ? std::string("mood") : toLowerAscii(type));
    if(!state.empty())
        key += "." + toLowerAscii(state);
    return key + "." + formatKeyNumber(number);
}

SocialData::SocialData()
{
    ensureFallbackGroup();
}

void SocialData::clearNames()
{
    mGroups.clear();
    mClassToGroup.clear();
    mUnmappedClasses.clear();
}

void SocialData::clearTexts()
{
    mTexts.clear();
}

void SocialData::ensureFallbackGroup()
{
    for(std::size_t i = 0; i < mGroups.size(); ++i)
    {
        if(mGroups[i].mName == FALLBACK_GROUP)
            return;
    }

    // Built-in group used when the file is missing or does not define "monster"
    NameGroup group;
    group.mName = FALLBACK_GROUP;
    group.mAgeMin = 1;
    group.mAgeMax = 30;
    group.mGiven[2].push_back("Nameless");
    group.mHometowns.push_back("Somewhere");
    mGroups.push_back(group);
}

void SocialData::addError(const std::string& source, uint32_t lineNumber, const std::string& message)
{
    std::ostringstream stream;
    stream << source << ":" << lineNumber << ": " << message;
    mErrors.push_back(stream.str());
}

bool SocialData::loadFromDirectory(const std::string& directory)
{
    mErrors.clear();
    std::string path = buildDirectoryPath(directory);
    bool namesOk = loadNamesFile(path + "social-names.cfg");
    bool textsOk = loadTextsFile(path + "social-texts.cfg");
    return namesOk && textsOk;
}

bool SocialData::loadNamesFile(const std::string& path)
{
    // The table may lie in a content package (ContentPackages::resolveFile)
    std::ifstream file(ContentPackages::resolveFile(path).c_str());
    if(!file.is_open())
    {
        clearNames();
        ensureFallbackGroup();
        addError(path, 0, "cannot open the social names file, using built-in names");
        return false;
    }
    return loadNames(file, path);
}

bool SocialData::loadTextsFile(const std::string& path)
{
    // The table may lie in a content package (ContentPackages::resolveFile)
    std::ifstream file(ContentPackages::resolveFile(path).c_str());
    if(!file.is_open())
    {
        clearTexts();
        addError(path, 0, "cannot open the social texts file, using built-in texts");
        return false;
    }
    return loadTexts(file, path);
}

bool SocialData::parseNameGroupLine(const std::vector<std::string>& fields, NameGroup& group, std::string& error)
{
    const std::string& key = fields[0];
    if(key == "Group")
    {
        if(fields.size() < 2)
        {
            error = "Group needs a name";
            return false;
        }
        group.mName = fields[1];
        return true;
    }
    if(key == "Classes")
    {
        for(std::size_t i = 1; i < fields.size(); ++i)
            group.mClasses.push_back(fields[i]);
        return true;
    }
    if(key == "AgeRange")
    {
        int32_t minAge = 0;
        int32_t maxAge = 0;
        if((fields.size() != 3) || !parseNumber(fields[1], minAge) || !parseNumber(fields[2], maxAge) ||
           (minAge < 0) || (maxAge < minAge))
        {
            error = "AgeRange needs two numbers, min <= max";
            return false;
        }
        group.mAgeMin = minAge;
        group.mAgeMax = maxAge;
        return true;
    }
    if(key == "GenderWeights")
    {
        int32_t weights[3] = {0, 0, 0};
        if((fields.size() != 4) || !parseNumber(fields[1], weights[0]) ||
           !parseNumber(fields[2], weights[1]) || !parseNumber(fields[3], weights[2]) ||
           (weights[0] < 0) || (weights[1] < 0) || (weights[2] < 0) ||
           (weights[0] + weights[1] + weights[2] == 0))
        {
            error = "GenderWeights needs three weights (F M X), not all zero";
            return false;
        }
        for(std::size_t i = 0; i < 3; ++i)
            group.mGenderWeights[i] = static_cast<uint32_t>(weights[i]);
        return true;
    }
    if(key == "Given")
    {
        if((fields.size() < 2) || ((fields[1] != "F") && (fields[1] != "M") && (fields[1] != "X")))
        {
            error = "Given needs a gender (F, M or X) and names";
            return false;
        }
        std::size_t index = 2;
        if(fields[1] == "F")
            index = 0;
        else if(fields[1] == "M")
            index = 1;
        for(std::size_t i = 2; i < fields.size(); ++i)
            group.mGiven[index].push_back(fields[i]);
        return true;
    }

    std::vector<std::string>* pool = NULL;
    if(key == "Surname")
        pool = &group.mSurnames;
    else if(key == "Title")
        pool = &group.mTitles;
    else if(key == "Hometown")
        pool = &group.mHometowns;
    else if(key == "AgeJoke")
        pool = &group.mAgeJokes;
    if(pool == NULL)
    {
        error = "unknown key " + key;
        return false;
    }
    for(std::size_t i = 1; i < fields.size(); ++i)
        pool->push_back(fields[i]);
    return true;
}

bool SocialData::loadNames(std::istream& input, const std::string& source)
{
    clearNames();
    std::size_t errorsBefore = mErrors.size();

    bool inGroup = false;
    NameGroup group;
    uint32_t lineNumber = 0;
    std::string line;
    std::vector<std::string> fields;
    while(std::getline(input, line))
    {
        ++lineNumber;
        line = trimText(line);
        if(line.empty() || (line[0] == '#'))
            continue;

        if(line == "[NameGroup]")
        {
            if(inGroup)
                addError(source, lineNumber, "[NameGroup] inside a group, the previous group is dropped");
            group = NameGroup();
            inGroup = true;
            continue;
        }

        if(line == "[/NameGroup]")
        {
            if(!inGroup)
            {
                addError(source, lineNumber, "[/NameGroup] without [NameGroup]");
                continue;
            }
            inGroup = false;
            if(group.mName.empty())
            {
                addError(source, lineNumber, "group without a name is dropped");
                continue;
            }
            bool duplicate = false;
            for(std::size_t i = 0; i < mGroups.size(); ++i)
            {
                if(mGroups[i].mName == group.mName)
                {
                    addError(source, lineNumber, "duplicate group " + group.mName + " is dropped");
                    duplicate = true;
                    break;
                }
            }
            if(duplicate)
                continue;
            std::size_t groupIndex = mGroups.size();
            mGroups.push_back(group);
            for(std::size_t i = 0; i < group.mClasses.size(); ++i)
            {
                if(mClassToGroup.find(group.mClasses[i]) != mClassToGroup.end())
                {
                    addError(source, lineNumber, "class " + group.mClasses[i] + " is already in another group");
                    continue;
                }
                mClassToGroup[group.mClasses[i]] = groupIndex;
            }
            continue;
        }

        if(!inGroup)
        {
            addError(source, lineNumber, "line outside of a [NameGroup] block is ignored");
            continue;
        }

        splitAtTabs(line, fields);
        if(fields.empty())
            continue;
        std::string error;
        if(!parseNameGroupLine(fields, group, error))
            addError(source, lineNumber, error);
    }

    if(inGroup)
        addError(source, lineNumber, "missing [/NameGroup] at the end of the file, the last group is dropped");

    bool hasGroups = !mGroups.empty();
    ensureFallbackGroup();
    if(!hasGroups)
        addError(source, 0, "no name group found, using built-in names");

    return mErrors.size() == errorsBefore;
}

bool SocialData::loadTexts(std::istream& input, const std::string& source)
{
    clearTexts();
    std::size_t errorsBefore = mErrors.size();

    uint32_t lineNumber = 0;
    std::string line;
    std::vector<std::string> fields;
    uint32_t count = 0;
    // Lines read so far per type (and state or category), they number the keys of the language files
    std::map<std::string, uint32_t> lineNumbers;
    while(std::getline(input, line))
    {
        ++lineNumber;
        line = trimText(line);
        if(line.empty() || (line[0] == '#'))
            continue;

        splitAtTabs(line, fields);
        if(fields.empty())
            continue;

        std::string key;
        std::string type = fields[0];
        std::string state;
        ScopedText text;
        if(isKnownTextKey(fields[0]))
        {
            if(fields.size() != 3)
            {
                addError(source, lineNumber, fields[0] + " needs scope and text");
                continue;
            }
            key = fields[0];
            text.mScope = fields[1];
            text.mText = fields[2];
        }
        else if((fields[0] == "MoodLine") || (fields[0] == "Post"))
        {
            if(fields.size() != 4)
            {
                addError(source, lineNumber, fields[0] + " needs state or category, scope and text");
                continue;
            }
            key = fields[0] + ":" + fields[1];
            state = fields[1];
            text.mScope = fields[2];
            text.mText = fields[3];
        }
        else
        {
            addError(source, lineNumber, "unknown key " + fields[0]);
            continue;
        }

        if(text.mScope.empty() || text.mText.empty())
        {
            addError(source, lineNumber, "empty scope or text");
            continue;
        }
        uint32_t& number = lineNumbers[key];
        ++number;
        text.mKey = makeTextKey(type, state, number);
        mTexts[key].push_back(text);
        ++count;
    }

    if(count == 0)
        addError(source, 0, "no text found, using built-in texts");

    return mErrors.size() == errorsBefore;
}

bool SocialData::hasGroupForClass(const std::string& className) const
{
    return mClassToGroup.find(className) != mClassToGroup.end();
}

const NameGroup& SocialData::getGroupForClass(const std::string& className) const
{
    std::map<std::string, std::size_t>::const_iterator it = mClassToGroup.find(className);
    if(it != mClassToGroup.end())
        return mGroups[it->second];

    mUnmappedClasses.insert(className);
    for(std::size_t i = 0; i < mGroups.size(); ++i)
    {
        if(mGroups[i].mName == FALLBACK_GROUP)
            return mGroups[i];
    }
    // ensureFallbackGroup() guarantees the fallback group exists
    return mGroups[0];
}

void SocialData::getTexts(const std::string& key, const std::vector<std::string>& scopes,
    std::vector<std::string>& texts) const
{
    texts.clear();
    std::map<std::string, std::vector<ScopedText> >::const_iterator it = mTexts.find(key);
    if(it == mTexts.end())
        return;

    const std::vector<ScopedText>& entries = it->second;
    for(std::size_t i = 0; i < entries.size(); ++i)
    {
        for(std::size_t j = 0; j < scopes.size(); ++j)
        {
            if(entries[i].mScope == scopes[j])
            {
                texts.push_back(resolveText(entries[i].mKey, entries[i].mText));
                break;
            }
        }
    }
}

uint32_t SocialData::getTextCount(const std::string& key) const
{
    std::map<std::string, std::vector<ScopedText> >::const_iterator it = mTexts.find(key);
    if(it == mTexts.end())
        return 0;
    return static_cast<uint32_t>(it->second.size());
}

}
