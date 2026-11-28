/*
 * Copyright (C) 2026 OpenDungeons Team
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
#define BOOST_TEST_MODULE Translation
#include "BoostTestTargetConfig.h"
#include "utils/Translation.h"

#include <boost/filesystem.hpp>

#include <fstream>
#include <functional>
#include <map>
#include <string>
#include <vector>

namespace
{
//! \brief Writes a file below folder, creating the folders on the way.
void writeFile(const boost::filesystem::path& file, const std::string& text)
{
    boost::filesystem::create_directories(file.parent_path());
    std::ofstream out(file.string().c_str(), std::ios::binary);
    out << text;
}

//! \brief A fresh temporary folder with an English and a German language package and one content package that is
//! no language; returns the package folders in name order.
std::vector<std::string> makeLanguagePackages(const boost::filesystem::path& root)
{
    boost::filesystem::remove_all(root);
    writeFile(root / "core-x" / "Package.cfg", "Content=core-x\n");
    writeFile(root / "lang-de" / "Package.cfg", "Content=lang-de\r\nLanguage=de\r\nLanguageName=Deutsch\r\n");
    writeFile(root / "lang-de" / "texts" / "menu.txt", "# Hauptmenü\nmenu.quit=Beenden\nmenu.greet=Hallo {name}, {count} Kreaturen\n");
    writeFile(root / "lang-en" / "Package.cfg", "Content=lang-en\nLanguage=en\nLanguageName=English\n");
    writeFile(root / "lang-en" / "texts" / "menu.txt",
        "menu.quit=Quit\nmenu.greet={count} creatures, hello {name}\nmenu.only.english=Only English\n");
    std::vector<std::string> folders;
    folders.push_back((root / "core-x").string());
    folders.push_back((root / "lang-de").string());
    folders.push_back((root / "lang-en").string());
    return folders;
}
} // namespace

//! Checks R2.2: a saved language that is available is used, whatever the system language is.
BOOST_AUTO_TEST_CASE(test_SavedLanguageWins)
{
    std::vector<std::string> available;
    available.push_back("de");
    available.push_back("en");
    BOOST_CHECK_EQUAL(Translation::chooseLanguage("en", "de", available), "en");
    BOOST_CHECK_EQUAL(Translation::chooseLanguage("de", "en", available), "de");
}

//! Checks R2.3: without a saved language a German system chooses German and any other system English.
BOOST_AUTO_TEST_CASE(test_FirstStartUsesSystemLanguage)
{
    std::vector<std::string> available;
    available.push_back("de");
    available.push_back("en");
    BOOST_CHECK_EQUAL(Translation::chooseLanguage("", "de", available), "de");
    BOOST_CHECK_EQUAL(Translation::chooseLanguage("", "fr", available), "en");
    BOOST_CHECK_EQUAL(Translation::chooseLanguage("", "", available), "en");
}

//! Checks R2.5: a saved language whose package is gone falls back to the system language, else English.
BOOST_AUTO_TEST_CASE(test_RemovedLanguageFallsBack)
{
    std::vector<std::string> available;
    available.push_back("en");
    BOOST_CHECK_EQUAL(Translation::chooseLanguage("de", "de", available), "en");
    BOOST_CHECK_EQUAL(Translation::chooseLanguage("fr", "", available), "en");
}

//! Checks the text file rules of R1.4: comments, a byte order mark, line ends, escapes, and errors for bad lines.
BOOST_AUTO_TEST_CASE(test_ParseTexts)
{
    std::map<std::string, std::string> texts;
    std::vector<std::string> errors;
    const std::string file = "\xEF\xBB\xBF" "a=First\\nSecond\r\n# comment\n\n b = x=y \nbad line\n=empty\na=again\nc=back\\\\slash\n";
    BOOST_CHECK_EQUAL(Translation::parseTexts(file, "t.txt", texts, errors), 3u);
    BOOST_CHECK_EQUAL(texts["a"], "First\nSecond");
    BOOST_CHECK_EQUAL(texts["b"], " x=y ");
    BOOST_CHECK_EQUAL(texts["c"], "back\\slash");
    BOOST_REQUIRE_EQUAL(errors.size(), 3u);
    BOOST_CHECK_EQUAL(errors[0], "t.txt:5: no '=' in the line");
    BOOST_CHECK_EQUAL(errors[1], "t.txt:6: empty key");
    BOOST_CHECK_EQUAL(errors[2], "t.txt:7: key a is given twice");
}

//! Checks R1.5: placeholders are replaced in the word order of each language and listed once each.
BOOST_AUTO_TEST_CASE(test_FormatText)
{
    std::map<std::string, std::string> values;
    values["name"] = "Ziv";
    values["count"] = "3";
    BOOST_CHECK_EQUAL(Translation::formatText("Hallo {name}, {count} Kreaturen", values), "Hallo Ziv, 3 Kreaturen");
    BOOST_CHECK_EQUAL(Translation::formatText("{count} creatures, hello {name}", values), "3 creatures, hello Ziv");
    BOOST_CHECK_EQUAL(Translation::formatText("{unknown} {", values), "{unknown} {");
    std::vector<std::string> names = Translation::getPlaceholders("{b} {a} {b}");
    BOOST_REQUIRE_EQUAL(names.size(), 2u);
    BOOST_CHECK_EQUAL(names[0], "a");
    BOOST_CHECK_EQUAL(names[1], "b");
}

//! Checks R1.2, R1.3 and the English fallback: language packages are found among the content packages, a text
//! missing in German comes from English, a key missing everywhere is shown as itself, and an unknown language
//! chooses English. A listener is told once per real change.
BOOST_AUTO_TEST_CASE(test_LoadAndFallback)
{
    const boost::filesystem::path root = boost::filesystem::temp_directory_path() / "od_test_translation";
    Translation::loadLanguages(makeLanguagePackages(root));

    BOOST_REQUIRE_EQUAL(Translation::getLanguages().size(), 2u);
    BOOST_CHECK_EQUAL(Translation::getLanguages()[0].mCode, "de");
    BOOST_CHECK_EQUAL(Translation::getLanguages()[0].mName, "Deutsch");
    BOOST_CHECK_EQUAL(Translation::getLanguages()[1].mName, "English");
    BOOST_CHECK_EQUAL(Translation::getLanguage(), "en");

    unsigned int calls = 0;
    const std::function<void()> countCall = [&calls]() { ++calls; };
    const unsigned int id = Translation::addListener(countCall);
    Translation::setLanguage("de");
    BOOST_CHECK_EQUAL(calls, 1u);
    Translation::setLanguage("de");
    BOOST_CHECK_EQUAL(calls, 1u);

    BOOST_CHECK_EQUAL(Translation::tr("menu.quit"), "Beenden");
    BOOST_CHECK_EQUAL(Translation::tr("menu.only.english"), "Only English");
    BOOST_CHECK_EQUAL(Translation::tr("menu.unknown"), "menu.unknown");
    BOOST_CHECK(Translation::hasText("menu.only.english"));
    BOOST_CHECK(!Translation::hasText("menu.unknown"));
    std::map<std::string, std::string> values;
    values["name"] = "Ziv";
    values["count"] = "2";
    BOOST_CHECK_EQUAL(Translation::tr("menu.greet", values), "Hallo Ziv, 2 Kreaturen");

    Translation::setLanguage("fr");
    BOOST_CHECK_EQUAL(Translation::getLanguage(), "en");
    BOOST_CHECK_EQUAL(calls, 2u);
    BOOST_CHECK_EQUAL(Translation::tr("menu.quit"), "Quit");

    Translation::removeListener(id);
    Translation::setLanguage("de");
    BOOST_CHECK_EQUAL(calls, 2u);
    boost::filesystem::remove_all(root);
}

//! Checks R5: the same text reference of the server is shown in German on one client and in English on another,
//! with values that are references themselves resolved in the language of the client; plain texts (player chat,
//! old saves), unknown keys and a '@' in a plain text stay unchanged; values keep '|', backslashes and line breaks.
BOOST_AUTO_TEST_CASE(test_ResolveReferences)
{
    const boost::filesystem::path root = boost::filesystem::temp_directory_path() / "od_test_translation_refs";
    std::vector<std::string> folders = makeLanguagePackages(root);
    writeFile(root / "lang-de" / "texts" / "msg.txt",
        "msg.claimed=Du hast {room} erobert ({count} Felder)\nmsg.room.arena=Arena\nmsg.pair=[{a}|{b}]\n");
    writeFile(root / "lang-en" / "texts" / "msg.txt",
        "msg.claimed=You have claimed a {room} ({count} tiles)\nmsg.room.arena=arena room\nmsg.pair=[{a}|{b}]\n");
    Translation::loadLanguages(folders);

    std::map<std::string, std::string> values;
    values["room"] = Translation::makeReference("msg.room.arena");
    values["count"] = "12";
    const std::string reference = Translation::makeReference("msg.claimed", values);
    BOOST_CHECK_EQUAL(reference, "@msg.claimed|count=12|room=@msg.room.arena");

    Translation::setLanguage("de");
    BOOST_CHECK_EQUAL(Translation::resolve(reference), "Du hast Arena erobert (12 Felder)");
    Translation::setLanguage("en");
    BOOST_CHECK_EQUAL(Translation::resolve(reference), "You have claimed a arena room (12 tiles)");

    // A nested reference with values travels escaped inside the value and still resolves
    std::map<std::string, std::string> inner;
    inner["room"] = "Arena";
    inner["count"] = "3";
    std::map<std::string, std::string> outer;
    outer["a"] = Translation::makeReference("msg.claimed", inner);
    outer["b"] = "x|y\\z\nw";
    BOOST_CHECK_EQUAL(Translation::resolve(Translation::makeReference("msg.pair", outer)),
        "[You have claimed a Arena (3 tiles)|x|y\\z\nw]");

    // A name reference shows its key when a language has it, else its fallback text
    BOOST_CHECK_EQUAL(Translation::resolve(Translation::makeNameReference("msg.room.arena", "Fallback")), "arena room");
    BOOST_CHECK_EQUAL(Translation::resolve(Translation::makeNameReference("msg.room.none", "Fallback")), "Fallback");

    // Plain texts, unknown keys and texts that only contain a '@' are shown as they are
    BOOST_CHECK_EQUAL(Translation::resolve("You lost the game"), "You lost the game");
    BOOST_CHECK_EQUAL(Translation::resolve("@unknown.key"), "@unknown.key");
    BOOST_CHECK_EQUAL(Translation::resolve("@bob says hi"), "@bob says hi");
    BOOST_CHECK_EQUAL(Translation::resolve(""), "");
    BOOST_CHECK(Translation::isReference("@menu.quit"));
    BOOST_CHECK(!Translation::isReference("@Menu quit"));

    // One reference per line, with the picture tag of the objectives window kept
    BOOST_CHECK_EQUAL(Translation::resolveLines("[image='GoalStatus/Open'] @menu.quit\nplain\n@menu.quit\n"),
        "[image='GoalStatus/Open'] Quit\nplain\nQuit\n");
    boost::filesystem::remove_all(root);
}
