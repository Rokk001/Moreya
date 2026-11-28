/*
 * Copyright (C) 2026 OpenDungeons Team
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

#include "sound/VoiceLanguage.h"

#include <boost/filesystem.hpp>

#include <algorithm>

const std::string VoiceLanguage::FALLBACK_LANGUAGE = "en";

//! \brief The sound key "<voice>/<language>/<family>".
std::string VoiceLanguage::makeKey(const std::string& voice, const std::string& language, const std::string& family)
{
    return voice + "/" + language + "/" + family;
}

//! \brief The keys of the chosen voice, then of the default voice: chosen language, English, English without folder.
std::vector<std::string> VoiceLanguage::getLookupKeys(const std::string& voice, const std::string& defaultVoice,
    const std::string& language, const std::string& family)
{
    std::vector<std::string> voices;
    voices.push_back(voice);
    if(defaultVoice != voice)
        voices.push_back(defaultVoice);

    std::vector<std::string> keys;
    for(const std::string& name : voices)
    {
        if(!language.empty() && (language != FALLBACK_LANGUAGE))
            keys.push_back(makeKey(name, language, family));
        keys.push_back(makeKey(name, FALLBACK_LANGUAGE, family));
        keys.push_back(name + "/" + family);
    }
    return keys;
}

//! \brief The first key that exists.
std::string VoiceLanguage::chooseKey(const std::vector<std::string>& keys,
    const std::function<bool(const std::string&)>& hasKey)
{
    for(const std::string& key : keys)
    {
        if(hasKey(key))
            return key;
    }
    return std::string();
}

//! \brief Reads the ".ogg" files of the folder and of its sub folders into the map, one key per folder.
bool VoiceLanguage::collectFiles(const std::string& folder, const std::string& keyPrefix,
    std::map<std::string, std::vector<std::string>>& files)
{
    boost::system::error_code error;
    if(!boost::filesystem::is_directory(folder, error))
        return false;

    std::vector<std::string> directories;
    std::vector<std::string> recordings;
    boost::filesystem::directory_iterator end;
    for(boost::filesystem::directory_iterator it(folder, error); !error && (it != end); it.increment(error))
    {
        if(boost::filesystem::is_directory(it->status()))
            directories.push_back(it->path().filename().string());
        else if(it->path().extension().string() == ".ogg")
            recordings.push_back(boost::filesystem::canonical(it->path()).string());
    }
    std::sort(directories.begin(), directories.end());
    std::sort(recordings.begin(), recordings.end());

    for(const std::string& directory : directories)
    {
        const std::string family = keyPrefix.empty() ? directory : keyPrefix + "/" + directory;
        collectFiles(folder + "/" + directory, family, files);
    }
    // The files of a folder belong to its key; a folder without files gets no entry (as the voice folders themselves)
    if(!recordings.empty() && !keyPrefix.empty())
    {
        std::vector<std::string>& entry = files[keyPrefix];
        entry.insert(entry.end(), recordings.begin(), recordings.end());
    }
    return true;
}

//! \brief Reads the voice folders of a language package with the key prefix "<voice>/<language>".
unsigned int VoiceLanguage::collectPackageFiles(const std::string& packageDirectory, const std::string& language,
    std::map<std::string, std::vector<std::string>>& files)
{
    unsigned int before = 0;
    for(std::map<std::string, std::vector<std::string>>::const_iterator it = files.begin(); it != files.end(); ++it)
        before += static_cast<unsigned int>(it->second.size());

    const std::string relativeFolder = packageDirectory + "/sounds/Relative";
    boost::system::error_code error;
    if(boost::filesystem::is_directory(relativeFolder, error))
    {
        std::vector<std::string> voices;
        boost::filesystem::directory_iterator end;
        for(boost::filesystem::directory_iterator it(relativeFolder, error); !error && (it != end); it.increment(error))
        {
            if(boost::filesystem::is_directory(it->status()))
                voices.push_back(it->path().filename().string());
        }
        std::sort(voices.begin(), voices.end());
        for(const std::string& voice : voices)
            collectFiles(relativeFolder + "/" + voice, voice + "/" + language, files);
    }

    unsigned int after = 0;
    for(std::map<std::string, std::vector<std::string>>::const_iterator it = files.begin(); it != files.end(); ++it)
        after += static_cast<unsigned int>(it->second.size());
    return after - before;
}
