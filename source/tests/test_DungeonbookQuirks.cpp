/*
 * Copyright (C) 2026 OpenDungeons Team
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
#define BOOST_TEST_MODULE DungeonbookQuirks
#include "BoostTestTargetConfig.h"
#include "game/CreatureAppearance.h"
#include "render/PortraitCatalog.h"
#include "render/DungeonbookQuirks.h"
#include "utils/Translation.h"
#include <boost/filesystem.hpp>
#include <fstream>
#include <sstream>
#include <vector>

namespace
{
//! \brief Writes a file of a test language package, creating the folders on the way.
void writeLanguageFile(const boost::filesystem::path& file, const std::string& text)
{
    boost::filesystem::create_directories(file.parent_path());
    std::ofstream out(file.string().c_str(), std::ios::binary);
    out << text;
}
}

//! \brief Selects stable remarks only from tags painted into the chosen whole image.
BOOST_AUTO_TEST_CASE(actual_feature_tags)
{
    PortraitCatalog catalog;
    std::istringstream images("1\t01.jpg\thair-swept,eyepatch,cigar,scar-diagonal\n2\t02.jpg\thair-braided\n");
    BOOST_REQUIRE(catalog.loadFromStream(images, "", "fixture"));
    std::istringstream lines("eyepatch\tDistrusts the other eye.\ncigar\tCounts smoke as strategy.\nscar-diagonal\tBlames a doorway.\n");
    DungeonbookQuirks quirks;
    quirks.loadFromStream(lines, "fixture");
    CreatureAppearance appearance;
    appearance.setCatalogId("Goblin.mesh");
    appearance.setImageNumber(1);
    BOOST_CHECK_EQUAL(DungeonbookQuirkLogic::collectRemarks(quirks, catalog, appearance).size(), 3u);
    std::vector<std::string> chosen = DungeonbookQuirkLogic::selectRemarks(quirks, catalog, appearance, "Brak");
    BOOST_CHECK_EQUAL(chosen.size(), 2u);
    BOOST_CHECK(chosen == DungeonbookQuirkLogic::selectRemarks(quirks, catalog, appearance, "Brak"));
    appearance.setImageNumber(2);
    BOOST_CHECK(DungeonbookQuirkLogic::selectRemarks(quirks, catalog, appearance, "Brak").empty());
    appearance.setImageNumber(3);
    BOOST_CHECK(DungeonbookQuirkLogic::selectRemarks(quirks, catalog, appearance, "Brak").empty());
}

//! \brief Rejects obsolete rows and preserves first-wins warning behavior.
BOOST_AUTO_TEST_CASE(malformed_and_duplicate_tags)
{
    std::istringstream lines("eyepatch\tFirst.\neyepatch\tSecond.\neye\tpatch\tOld format.\n");
    DungeonbookQuirks quirks;
    quirks.loadFromStream(lines, "fixture");
    BOOST_REQUIRE_EQUAL(quirks.size(), 1u);
    BOOST_CHECK_EQUAL(*quirks.find("eyepatch"), "First.");
    BOOST_CHECK_EQUAL(quirks.getWarnings().size(), 2u);
    BOOST_CHECK(quirks.find("missing") == nullptr);
}

//! \brief The remarks come from the language files and the choice of the two remarks is the same in every
//! language (it depends on the texts of the file, not on the chosen language).
BOOST_AUTO_TEST_CASE(remarks_follow_the_language_with_the_same_choice)
{
    const boost::filesystem::path root = boost::filesystem::temp_directory_path() / "od_test_quirk_language";
    boost::filesystem::remove_all(root);
    writeLanguageFile(root / "lang-en" / "Package.cfg", "Content=lang-en\nLanguage=en\nLanguageName=English\n");
    writeLanguageFile(root / "lang-en" / "texts" / "quirks.txt",
        "quirk.eyepatch=Distrusts the other eye.\nquirk.cigar=Counts smoke as strategy.\nquirk.scar-diagonal=Blames a doorway.\n");
    writeLanguageFile(root / "lang-de" / "Package.cfg", "Content=lang-de\nLanguage=de\nLanguageName=Deutsch\n");
    writeLanguageFile(root / "lang-de" / "texts" / "quirks.txt",
        "quirk.eyepatch=Misstraut dem anderen Auge.\nquirk.cigar=Haelt Rauch fuer Strategie.\nquirk.scar-diagonal=Beschuldigt einen Tuerrahmen.\n");
    std::vector<std::string> folders;
    folders.push_back((root / "lang-de").string());
    folders.push_back((root / "lang-en").string());
    Translation::loadLanguages(folders);

    PortraitCatalog catalog;
    std::istringstream images("1\t01.jpg\thair-swept,eyepatch,cigar,scar-diagonal\n");
    BOOST_REQUIRE(catalog.loadFromStream(images, "", "fixture"));
    // The texts of the file are English, the base of the choice
    std::istringstream lines("eyepatch\tDistrusts the other eye.\ncigar\tCounts smoke as strategy.\nscar-diagonal\tBlames a doorway.\n");
    DungeonbookQuirks quirks;
    quirks.loadFromStream(lines, "fixture");
    CreatureAppearance appearance;
    appearance.setCatalogId("Goblin.mesh");
    appearance.setImageNumber(1);

    const std::string tags[] = {"eyepatch", "cigar", "scar-diagonal"};
    for(const std::string name : {"Brak", "Orc17", "Grub", "Zed"})
    {
        Translation::setLanguage("en");
        std::vector<std::string> english = DungeonbookQuirkLogic::selectRemarks(quirks, catalog, appearance, name);
        Translation::setLanguage("de");
        std::vector<std::string> german = DungeonbookQuirkLogic::selectRemarks(quirks, catalog, appearance, name);
        BOOST_REQUIRE_EQUAL(english.size(), 2u);
        BOOST_REQUIRE_EQUAL(german.size(), 2u);
        for(std::size_t i = 0; i < 2; ++i)
        {
            // The same entry: the German text belongs to the tag whose English text was picked
            std::size_t tagIndex = 0;
            while((tagIndex < 3) && (quirks.getDisplayText(tags[tagIndex]) != german[i]))
                ++tagIndex;
            BOOST_REQUIRE(tagIndex < 3);
            Translation::setLanguage("en");
            BOOST_CHECK_EQUAL(quirks.getDisplayText(tags[tagIndex]), english[i]);
            Translation::setLanguage("de");
        }
    }
    BOOST_CHECK_EQUAL(quirks.getDisplayText("cigar"), "Haelt Rauch fuer Strategie.");
    BOOST_CHECK_EQUAL(quirks.getDisplayText("missing"), "");
    Translation::loadLanguages(std::vector<std::string>());
    // Without language files the text of the file is shown
    BOOST_CHECK_EQUAL(quirks.getDisplayText("cigar"), "Counts smoke as strategy.");
    boost::filesystem::remove_all(root);
}
