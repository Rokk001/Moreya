/*
 * Copyright (C) 2026 OpenDungeons Team
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

#ifndef VOICELANGUAGE_H
#define VOICELANGUAGE_H

#include <functional>
#include <map>
#include <string>
#include <vector>

//! \brief Language dependent voice lines (localization plan R9).
//!
//! A voice line is a recording below "sounds/Relative/<voice>/". The recordings of a language lie in the folder
//! "sounds/Relative/<voice>/<language>/<family...>" of the game data, and in the folder
//! "sounds/Relative/<voice>/<family...>" of the language package "lang-<code>" (the language is the package, so the
//! package has no language folder). Recordings that lie directly below the voice folder (no language folder) are
//! English. Adding a language therefore needs only recordings, no code change.
//!
//! The functions have no dependency on the sound library, the GUI or the log, so that the small probes of the checks
//! can test them. The files are collected into a map from sound key to the recordings of that key; the key of a
//! language recording is "<voice>/<language>/<family>", the key of an English recording without language folder is
//! "<voice>/<family>".
namespace VoiceLanguage
{
    //! The language of the recordings that lie directly below the voice folder, and the fallback language
    extern const std::string FALLBACK_LANGUAGE;

    //! \brief The sound key of the recordings of a voice in a language: "<voice>/<language>/<family>".
    std::string makeKey(const std::string& voice, const std::string& language, const std::string& family);

    //! \brief The sound keys to try for a voice line, best first. For the chosen voice and then for the default voice:
    //! the chosen language, English (when it is not the chosen language), and the English recordings that lie
    //! directly below the voice folder. A voice without the family in the language falls back to English before it
    //! falls back to the default voice.
    std::vector<std::string> getLookupKeys(const std::string& voice, const std::string& defaultVoice,
        const std::string& language, const std::string& family);

    //! \brief The first key of the keys for which hasKey is true, or an empty text when none is.
    std::string chooseKey(const std::vector<std::string>& keys, const std::function<bool(const std::string&)>& hasKey);

    //! \brief Collects the ".ogg" files of a folder and of its sub folders. The key of a folder is keyPrefix plus the
    //! names of the folders below the start folder, separated by '/'; a folder without such files gets no entry.
    //! \return False when the folder does not exist.
    bool collectFiles(const std::string& folder, const std::string& keyPrefix,
        std::map<std::string, std::vector<std::string>>& files);

    //! \brief Collects the recordings of a language package: every voice folder in "<package>/sounds/Relative" is read
    //! with the key prefix "<voice>/<language>". A package without such a folder adds nothing.
    //! \return The number of recording files added.
    unsigned int collectPackageFiles(const std::string& packageDirectory, const std::string& language,
        std::map<std::string, std::vector<std::string>>& files);
}

#endif // VOICELANGUAGE_H
