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

#include "utils/Translation.h"

#include "utils/ContentPackages.h"
#include "utils/LogManager.h"

#include <boost/filesystem.hpp>

#include <algorithm>
#include <cstdlib>
#include <fstream>
#include <set>
#include <sstream>

#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#endif

const std::string Translation::FALLBACK_LANGUAGE = "en";
const std::string Translation::LANGUAGE_KEY = "Language";
const std::string Translation::LANGUAGE_NAME_KEY = "LanguageName";
const std::string Translation::TEXTS_FOLDER = "texts";

namespace
{
//! Name of the definition file of a package (the same as CampaignPackages::DEFINITION_FILE)
const char* const DEFINITION_FILE = "Package.cfg";

//! \brief State of the texts: the languages, their texts and the listeners.
struct State
{
    std::vector<Translation::LanguageInfo> mLanguages;
    //! Texts by language code, then by key
    std::map<std::string, std::map<std::string, std::string>> mTexts;
    std::string mLanguage = Translation::FALLBACK_LANGUAGE;
    std::map<unsigned int, std::function<void()>> mListeners;
    unsigned int mNextListenerId = 1;
};

//! \brief The one state of the program.
State& getState()
{
    static State state;
    return state;
}

//! \brief The text without spaces, tabs and carriage returns at both ends.
std::string trim(const std::string& text)
{
    const std::string::size_type first = text.find_first_not_of(" \t\r");
    if(first == std::string::npos)
        return std::string();
    const std::string::size_type last = text.find_last_not_of(" \t\r");
    return text.substr(first, last - first + 1);
}

//! \brief The whole content of a file, or an empty text when it cannot be read.
std::string readFile(const std::string& path)
{
    std::ifstream file(path.c_str(), std::ios::binary);
    if(!file.is_open())
        return std::string();
    std::ostringstream text;
    text << file.rdbuf();
    return text.str();
}

//! \brief The text with "\n" replaced by a line break and "\\" by a backslash.
std::string unescape(const std::string& text)
{
    std::string result;
    for(std::string::size_type i = 0; i < text.size(); ++i)
    {
        if((text[i] == '\\') && (i + 1 < text.size()))
        {
            if(text[i + 1] == 'n')
            {
                result += '\n';
                ++i;
                continue;
            }
            if(text[i + 1] == '\\')
            {
                result += '\\';
                ++i;
                continue;
            }
        }
        result += text[i];
    }
    return result;
}

//! \brief The text of the key in the given language, or nullptr when the language has none.
const std::string* findText(const State& state, const std::string& language, const std::string& key)
{
    std::map<std::string, std::map<std::string, std::string>>::const_iterator texts = state.mTexts.find(language);
    if(texts == state.mTexts.end())
        return nullptr;
    std::map<std::string, std::string>::const_iterator text = texts->second.find(key);
    if(text == texts->second.end())
        return nullptr;
    return &text->second;
}

//! \brief Orders languages by code.
bool isBefore(const Translation::LanguageInfo& a, const Translation::LanguageInfo& b)
{
    return a.mCode < b.mCode;
}
} // namespace

//! \brief Searches the line "<key>=" and returns its trimmed value.
std::string Translation::parseDefinitionValue(const std::string& definition, const std::string& key)
{
    std::istringstream lines(definition);
    std::string line;
    const std::string prefix = key + "=";
    while(std::getline(lines, line))
    {
        if(line.compare(0, prefix.size(), prefix) != 0)
            continue;
        return trim(line.substr(prefix.size()));
    }
    return std::string();
}

//! \brief Reads "<key>=<text>" lines; see the header for the rules.
unsigned int Translation::parseTexts(const std::string& fileText, const std::string& fileName,
    std::map<std::string, std::string>& texts, std::vector<std::string>& errors)
{
    std::istringstream lines(fileText);
    std::string line;
    unsigned int lineNumber = 0;
    unsigned int added = 0;
    while(std::getline(lines, line))
    {
        ++lineNumber;
        // A byte order mark at the start of the file is not part of the first key
        if((lineNumber == 1) && (line.compare(0, 3, "\xEF\xBB\xBF") == 0))
            line.erase(0, 3);
        if(!line.empty() && (line[line.size() - 1] == '\r'))
            line.erase(line.size() - 1);
        const std::string trimmed = trim(line);
        if(trimmed.empty() || (trimmed[0] == '#'))
            continue;
        const std::string::size_type separator = line.find('=');
        const std::string where = fileName + ":" + std::to_string(lineNumber);
        if(separator == std::string::npos)
        {
            errors.push_back(where + ": no '=' in the line");
            continue;
        }
        const std::string key = trim(line.substr(0, separator));
        if(key.empty())
        {
            errors.push_back(where + ": empty key");
            continue;
        }
        if(texts.count(key) != 0)
        {
            errors.push_back(where + ": key " + key + " is given twice");
            continue;
        }
        texts[key] = unescape(line.substr(separator + 1));
        ++added;
    }
    return added;
}

//! \brief Saved language, else system language, else English; only available languages are chosen.
std::string Translation::chooseLanguage(const std::string& saved, const std::string& systemLanguage,
    const std::vector<std::string>& available)
{
    if(!saved.empty() && (std::find(available.begin(), available.end(), saved) != available.end()))
        return saved;
    if(!systemLanguage.empty() && (std::find(available.begin(), available.end(), systemLanguage) != available.end()))
        return systemLanguage;
    return FALLBACK_LANGUAGE;
}

//! \brief Replaces every "{name}" whose name is in values.
std::string Translation::formatText(const std::string& text, const std::map<std::string, std::string>& values)
{
    std::string result;
    std::string::size_type position = 0;
    while(position < text.size())
    {
        const std::string::size_type open = text.find('{', position);
        if(open == std::string::npos)
            break;
        const std::string::size_type close = text.find('}', open + 1);
        if(close == std::string::npos)
            break;
        result += text.substr(position, open - position);
        const std::string name = text.substr(open + 1, close - open - 1);
        std::map<std::string, std::string>::const_iterator value = values.find(name);
        if(value != values.end())
            result += value->second;
        else
            result += text.substr(open, close - open + 1);
        position = close + 1;
    }
    result += text.substr(position);
    return result;
}

//! \brief Collects the names between '{' and '}'.
std::vector<std::string> Translation::getPlaceholders(const std::string& text)
{
    std::set<std::string> names;
    std::string::size_type position = 0;
    while(position < text.size())
    {
        const std::string::size_type open = text.find('{', position);
        if(open == std::string::npos)
            break;
        const std::string::size_type close = text.find('}', open + 1);
        if(close == std::string::npos)
            break;
        names.insert(text.substr(open + 1, close - open - 1));
        position = close + 1;
    }
    return std::vector<std::string>(names.begin(), names.end());
}

//! \brief Reads every package with a language line and the text files of its texts folder, in name order.
void Translation::loadLanguages(const std::vector<std::string>& packageDirectories)
{
    State& state = getState();
    state.mLanguages.clear();
    state.mTexts.clear();
    state.mLanguage = FALLBACK_LANGUAGE;
    for(const std::string& directory : packageDirectories)
    {
        const std::string definition = readFile(directory + "/" + DEFINITION_FILE);
        const std::string code = parseDefinitionValue(definition, LANGUAGE_KEY);
        if(code.empty())
            continue;
        if(state.mTexts.count(code) != 0)
        {
            OD_LOG_ERR("Language " + code + " is given by two packages, " + directory + " is skipped");
            continue;
        }
        LanguageInfo language;
        language.mCode = code;
        language.mName = parseDefinitionValue(definition, LANGUAGE_NAME_KEY);
        if(language.mName.empty())
            language.mName = code;
        language.mDirectory = directory;
        state.mLanguages.push_back(language);

        std::map<std::string, std::string>& texts = state.mTexts[code];
        std::vector<boost::filesystem::path> files;
        boost::system::error_code error;
        const boost::filesystem::path textsFolder = boost::filesystem::path(directory) / TEXTS_FOLDER;
        if(boost::filesystem::is_directory(textsFolder, error))
        {
            for(boost::filesystem::directory_iterator it(textsFolder, error);
                !error && (it != boost::filesystem::directory_iterator()); it.increment(error))
            {
                if(boost::filesystem::is_regular_file(it->path(), error) && (it->path().extension() == ".txt"))
                    files.push_back(it->path());
            }
        }
        std::sort(files.begin(), files.end());
        std::vector<std::string> errors;
        for(const boost::filesystem::path& file : files)
            parseTexts(readFile(file.string()), file.filename().string(), texts, errors);
        for(const std::string& message : errors)
            OD_LOG_ERR("Language " + code + ": " + message);
        OD_LOG_INF("Language " + code + " (" + language.mName + "): " + std::to_string(texts.size()) + " texts");
    }
    std::sort(state.mLanguages.begin(), state.mLanguages.end(), isBefore);
}

//! \brief Loads the languages of the found content packages.
void Translation::discover()
{
    loadLanguages(ContentPackages::getPackageDirectories());
    if(getState().mTexts.count(FALLBACK_LANGUAGE) == 0)
        OD_LOG_ERR("The English language package is missing; texts are shown as their keys");
}

//! \brief The kept languages.
const std::vector<Translation::LanguageInfo>& Translation::getLanguages()
{
    return getState().mLanguages;
}

//! \brief The codes of the kept languages.
std::vector<std::string> Translation::getLanguageCodes()
{
    std::vector<std::string> codes;
    for(const LanguageInfo& language : getState().mLanguages)
        codes.push_back(language.mCode);
    return codes;
}

//! \brief Changes the language and calls the listeners when it changed.
void Translation::setLanguage(const std::string& code)
{
    State& state = getState();
    const std::string chosen = (state.mTexts.count(code) != 0) ? code : FALLBACK_LANGUAGE;
    if(chosen == state.mLanguage)
        return;
    state.mLanguage = chosen;
    OD_LOG_INF("Language: " + chosen);
    // A listener may add or remove listeners, so the calls run on a copy
    const std::map<unsigned int, std::function<void()>> listeners = state.mListeners;
    for(const std::pair<const unsigned int, std::function<void()>>& listener : listeners)
        listener.second();
}

//! \brief The chosen language.
const std::string& Translation::getLanguage()
{
    return getState().mLanguage;
}

//! \brief The two-letter code of the user's display language.
std::string Translation::getSystemLanguage()
{
#ifdef _WIN32
    wchar_t localeName[LOCALE_NAME_MAX_LENGTH] = {0};
    if(LCIDToLocaleName(MAKELCID(GetUserDefaultUILanguage(), SORT_DEFAULT), localeName, LOCALE_NAME_MAX_LENGTH, 0) == 0)
        return std::string();
    std::string code;
    for(const wchar_t* c = localeName; (*c != 0) && (*c != L'-'); ++c)
        code += static_cast<char>(*c);
    return code;
#else
    const char* lang = std::getenv("LANG");
    if(lang == nullptr)
        return std::string();
    std::string code(lang);
    const std::string::size_type end = code.find_first_of("_.@");
    return code.substr(0, end);
#endif
}

//! \brief True when the chosen language or English has the key.
bool Translation::hasText(const std::string& key)
{
    const State& state = getState();
    return (findText(state, state.mLanguage, key) != nullptr) || (findText(state, FALLBACK_LANGUAGE, key) != nullptr);
}

//! \brief The text in the chosen language, English or the key.
std::string Translation::tr(const std::string& key)
{
    const State& state = getState();
    const std::string* text = findText(state, state.mLanguage, key);
    if(text == nullptr)
        text = findText(state, FALLBACK_LANGUAGE, key);
    return text != nullptr ? *text : key;
}

//! \brief The text with its placeholders replaced.
std::string Translation::tr(const std::string& key, const std::map<std::string, std::string>& values)
{
    return formatText(tr(key), values);
}

namespace
{
//! Deepest nesting of references inside values that resolve() follows
const unsigned int MAX_REFERENCE_DEPTH = 8;

//! Name of the value that holds the fallback text of a name reference
const char* const FALLBACK_VALUE = "_";

//! \brief True for the characters a key may have.
bool isKeyCharacter(char c)
{
    return ((c >= 'a') && (c <= 'z')) || ((c >= '0') && (c <= '9')) || (c == '.') || (c == '_') || (c == '-');
}

//! \brief The value with a backslash, a '|' and line breaks escaped.
std::string escapeValue(const std::string& value)
{
    std::string result;
    for(std::string::size_type i = 0; i < value.size(); ++i)
    {
        const char c = value[i];
        if((c == '\\') || (c == '|'))
        {
            result += '\\';
            result += c;
        }
        else if(c == '\n')
            result += "\\n";
        else if(c == '\r')
            result += "\\r";
        else
            result += c;
    }
    return result;
}

//! \brief Splits a text at every '|' that is not escaped; the segments stay escaped.
std::vector<std::string> splitSegments(const std::string& text)
{
    std::vector<std::string> segments;
    std::string current;
    for(std::string::size_type i = 0; i < text.size(); ++i)
    {
        if((text[i] == '\\') && (i + 1 < text.size()))
        {
            current += text[i];
            current += text[i + 1];
            ++i;
        }
        else if(text[i] == '|')
        {
            segments.push_back(current);
            current.clear();
        }
        else
            current += text[i];
    }
    segments.push_back(current);
    return segments;
}

//! \brief The value with the escapes of escapeValue() removed.
std::string unescapeValue(const std::string& value)
{
    std::string result;
    for(std::string::size_type i = 0; i < value.size(); ++i)
    {
        if((value[i] == '\\') && (i + 1 < value.size()))
        {
            ++i;
            if(value[i] == 'n')
                result += '\n';
            else if(value[i] == 'r')
                result += '\r';
            else
                result += value[i];
        }
        else
            result += value[i];
    }
    return result;
}

//! \brief resolve() with the depth of the references that are already open.
std::string resolveDepth(const std::string& text, unsigned int depth)
{
    if(!Translation::isReference(text))
        return text;
    const std::vector<std::string> segments = splitSegments(text);
    const std::string key = segments[0].substr(1);
    std::map<std::string, std::string> values;
    for(std::vector<std::string>::size_type i = 1; i < segments.size(); ++i)
    {
        const std::string::size_type separator = segments[i].find('=');
        if(separator == std::string::npos)
            continue;
        std::string value = unescapeValue(segments[i].substr(separator + 1));
        if((depth < MAX_REFERENCE_DEPTH) && !value.empty() && (value[0] == '@'))
            value = resolveDepth(value, depth + 1);
        values[segments[i].substr(0, separator)] = value;
    }
    if(!Translation::hasText(key))
    {
        // The fallback text of a name reference, else the reference as it is
        std::map<std::string, std::string>::const_iterator fallback = values.find(FALLBACK_VALUE);
        return (fallback != values.end()) ? fallback->second : text;
    }
    return Translation::tr(key, values);
}
} // namespace

//! \brief "@key" plus an escaped "|name=value" for every value.
std::string Translation::makeReference(const std::string& key, const std::map<std::string, std::string>& values)
{
    std::string reference = "@" + key;
    for(const std::pair<const std::string, std::string>& value : values)
        reference += "|" + value.first + "=" + escapeValue(value.second);
    return reference;
}

//! \brief "@key".
std::string Translation::makeReference(const std::string& key)
{
    return "@" + key;
}

//! \brief "@key" with the fallback text in the value "_".
std::string Translation::makeNameReference(const std::string& key, const std::string& fallback)
{
    std::map<std::string, std::string> values;
    values[FALLBACK_VALUE] = fallback;
    return makeReference(key, values);
}

//! \brief Lowercase letters; characters that are no key character become '_'.
std::string Translation::toKeyPart(const std::string& id)
{
    std::string result;
    for(std::string::size_type i = 0; i < id.size(); ++i)
    {
        char c = id[i];
        if((c >= 'A') && (c <= 'Z'))
            c = static_cast<char>(c - 'A' + 'a');
        result += isKeyCharacter(c) ? c : '_';
    }
    return result;
}

//! \brief A leading '@', one or more key characters, then the end or a '|'.
bool Translation::isReference(const std::string& text)
{
    if(text.empty() || (text[0] != '@'))
        return false;
    std::string::size_type end = 1;
    while((end < text.size()) && isKeyCharacter(text[end]))
        ++end;
    if(end == 1)
        return false;
    return (end == text.size()) || (text[end] == '|');
}

//! \brief Looks up the key of a reference and fills in its values.
std::string Translation::resolve(const std::string& text)
{
    return resolveDepth(text, 0);
}

//! \brief Resolves every line, keeping a picture tag at the start of the line.
std::string Translation::resolveLines(const std::string& text)
{
    std::string result;
    std::string::size_type position = 0;
    while(position <= text.size())
    {
        std::string::size_type end = text.find('\n', position);
        const bool last = (end == std::string::npos);
        if(last)
            end = text.size();
        std::string line = text.substr(position, end - position);
        std::string tag;
        if(line.compare(0, 7, "[image=") == 0)
        {
            const std::string::size_type close = line.find("] ");
            if(close != std::string::npos)
            {
                tag = line.substr(0, close + 2);
                line.erase(0, close + 2);
            }
        }
        result += tag + resolve(line);
        if(last)
            break;
        result += '\n';
        position = end + 1;
    }
    return result;
}

//! \brief Keeps the listener under a new id.
unsigned int Translation::addListener(const std::function<void()>& listener)
{
    State& state = getState();
    const unsigned int id = state.mNextListenerId++;
    state.mListeners[id] = listener;
    return id;
}

//! \brief Forgets the listener of the id.
void Translation::removeListener(unsigned int id)
{
    getState().mListeners.erase(id);
}
