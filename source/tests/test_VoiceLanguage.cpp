/*
 * Copyright (C) 2026 OpenDungeons Team
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
#define BOOST_TEST_MODULE VoiceLanguage
#include "BoostTestTargetConfig.h"
#include "sound/VoiceLanguage.h"

#include <boost/filesystem.hpp>

#include <fstream>
#include <functional>
#include <map>
#include <string>
#include <vector>

namespace
{
typedef std::map<std::string, std::vector<std::string>> FileMap;

//! \brief Writes a recording file (the given path plus the extension ".ogg") below the folder, creating the folders on
//! the way. The content is no sound, the folder scan only looks at the file names.
void writeRecording(const boost::filesystem::path& file)
{
    boost::filesystem::create_directories(file.parent_path());
    std::ofstream out((file.string() + ".ogg").c_str(), std::ios::binary);
    out << "x";
}

//! \brief A fresh temporary game data folder with the test voice "Test": the family "Keeper/Lost" in German and in
//! English, the family "Keeper/Victory" only in English, and the voice "Plain" with English recordings that lie
//! directly below the voice folder (as the recordings of today). The voice "Default" has "Keeper/Defeat" in German.
void makeGameData(const boost::filesystem::path& root)
{
    boost::filesystem::remove_all(root);
    writeRecording(root / "Relative" / "Test" / "de" / "Keeper" / "Lost" / "lost");
    writeRecording(root / "Relative" / "Test" / "en" / "Keeper" / "Lost" / "lost");
    writeRecording(root / "Relative" / "Test" / "en" / "Keeper" / "Victory" / "victory");
    writeRecording(root / "Relative" / "Plain" / "Keeper" / "Lost" / "lost");
    writeRecording(root / "Relative" / "Default" / "de" / "Keeper" / "Defeat" / "defeat");
    writeRecording(root / "Relative" / "Default" / "Keeper" / "Defeat" / "defeat");
}

//! \brief Reads the voice folders "Test", "Plain" and "Default" of a game data folder.
FileMap readGameData(const boost::filesystem::path& root)
{
    FileMap files;
    const char* voices[] = {"Default", "Plain", "Test"};
    for(const char* voice : voices)
        VoiceLanguage::collectFiles((root / "Relative" / voice).string(), voice, files);
    return files;
}

//! \brief The key under which a voice line of the voice is found, or an empty text, as the game looks it up.
std::string lookup(const FileMap& files, const std::string& voice, const std::string& language,
    const std::string& family)
{
    std::function<bool(const std::string&)> hasKey = [&files](const std::string& key) -> bool
        {
            return files.find(key) != files.end();
        };
    return VoiceLanguage::chooseKey(VoiceLanguage::getLookupKeys(voice, "Default", language, family), hasKey);
}
} // namespace

//! Checks R9.1: German chosen plays the German file of the family, English chosen the English file.
BOOST_AUTO_TEST_CASE(test_LanguageFolderIsChosen)
{
    boost::filesystem::path root = boost::filesystem::temp_directory_path() / "od_voice_language_a";
    makeGameData(root);
    FileMap files = readGameData(root);
    BOOST_CHECK_EQUAL(lookup(files, "Test", "de", "Keeper/Lost"), "Test/de/Keeper/Lost");
    BOOST_CHECK_EQUAL(lookup(files, "Test", "en", "Keeper/Lost"), "Test/en/Keeper/Lost");
    BOOST_REQUIRE(files.find("Test/de/Keeper/Lost") != files.end());
    BOOST_CHECK_EQUAL(files["Test/de/Keeper/Lost"].size(), 1u);
    boost::filesystem::remove_all(root);
}

//! Checks R9.3: a family missing in German plays the English file.
BOOST_AUTO_TEST_CASE(test_MissingFamilyFallsBackToEnglish)
{
    boost::filesystem::path root = boost::filesystem::temp_directory_path() / "od_voice_language_b";
    makeGameData(root);
    FileMap files = readGameData(root);
    BOOST_CHECK_EQUAL(lookup(files, "Test", "de", "Keeper/Victory"), "Test/en/Keeper/Victory");
    // A language without any recording plays English everywhere
    BOOST_CHECK_EQUAL(lookup(files, "Test", "fr", "Keeper/Lost"), "Test/en/Keeper/Lost");
    boost::filesystem::remove_all(root);
}

//! Checks R9.3 and R9.4: the fallback to the voice Default stays, and recordings directly below the voice folder keep
//! working as English.
BOOST_AUTO_TEST_CASE(test_DefaultVoiceAndTodaysEnglishRecordings)
{
    boost::filesystem::path root = boost::filesystem::temp_directory_path() / "od_voice_language_c";
    makeGameData(root);
    FileMap files = readGameData(root);
    // The voice Plain has only the recordings of today: they are English, also when German is chosen
    BOOST_CHECK_EQUAL(lookup(files, "Plain", "en", "Keeper/Lost"), "Plain/Keeper/Lost");
    BOOST_CHECK_EQUAL(lookup(files, "Plain", "de", "Keeper/Lost"), "Plain/Keeper/Lost");
    // The voice Test has no "Keeper/Defeat": the Default voice answers, in German when German is chosen
    BOOST_CHECK_EQUAL(lookup(files, "Test", "de", "Keeper/Defeat"), "Default/de/Keeper/Defeat");
    BOOST_CHECK_EQUAL(lookup(files, "Test", "en", "Keeper/Defeat"), "Default/Keeper/Defeat");
    // No voice has the family
    BOOST_CHECK_EQUAL(lookup(files, "Test", "de", "Keeper/Nothing"), "");
    boost::filesystem::remove_all(root);
}

//! Checks R9.2: a language package brings its recordings below sounds/Relative/<voice>/ without a language folder and
//! without a code change; they are found under the language of the package.
BOOST_AUTO_TEST_CASE(test_LanguagePackageBringsRecordings)
{
    boost::filesystem::path root = boost::filesystem::temp_directory_path() / "od_voice_language_d";
    makeGameData(root);
    boost::filesystem::path package = root / "packages" / "lang-fr";
    writeRecording(package / "sounds" / "Relative" / "Test" / "Keeper" / "Lost" / "perdu");
    writeRecording(package / "sounds" / "Relative" / "Test" / "Keeper" / "Lost" / "perdu2");
    FileMap files = readGameData(root);
    BOOST_CHECK_EQUAL(VoiceLanguage::collectPackageFiles(package.string(), "fr", files), 2u);
    BOOST_CHECK_EQUAL(lookup(files, "Test", "fr", "Keeper/Lost"), "Test/fr/Keeper/Lost");
    BOOST_CHECK_EQUAL(files["Test/fr/Keeper/Lost"].size(), 2u);
    // The family that the package does not bring is English
    BOOST_CHECK_EQUAL(lookup(files, "Test", "fr", "Keeper/Victory"), "Test/en/Keeper/Victory");
    // A package without a sounds folder adds nothing
    BOOST_CHECK_EQUAL(VoiceLanguage::collectPackageFiles((root / "packages" / "lang-xx").string(), "xx", files), 0u);
    boost::filesystem::remove_all(root);
}

//! Checks R9.5: the keys depend only on the language given at the call, so the next line follows a language change.
BOOST_AUTO_TEST_CASE(test_LanguageChangeAppliesToNextLine)
{
    boost::filesystem::path root = boost::filesystem::temp_directory_path() / "od_voice_language_e";
    makeGameData(root);
    FileMap files = readGameData(root);
    BOOST_CHECK_EQUAL(lookup(files, "Test", "de", "Keeper/Lost"), "Test/de/Keeper/Lost");
    BOOST_CHECK_EQUAL(lookup(files, "Test", "en", "Keeper/Lost"), "Test/en/Keeper/Lost");
    BOOST_CHECK_EQUAL(lookup(files, "Test", "de", "Keeper/Lost"), "Test/de/Keeper/Lost");
    std::vector<std::string> keys = VoiceLanguage::getLookupKeys("Test", "Default", "de", "Keeper/Lost");
    BOOST_REQUIRE_EQUAL(keys.size(), 6u);
    BOOST_CHECK_EQUAL(keys[0], "Test/de/Keeper/Lost");
    BOOST_CHECK_EQUAL(keys[1], "Test/en/Keeper/Lost");
    BOOST_CHECK_EQUAL(keys[2], "Test/Keeper/Lost");
    BOOST_CHECK_EQUAL(keys[3], "Default/de/Keeper/Lost");
    BOOST_CHECK_EQUAL(keys[4], "Default/en/Keeper/Lost");
    BOOST_CHECK_EQUAL(keys[5], "Default/Keeper/Lost");
    boost::filesystem::remove_all(root);
}
