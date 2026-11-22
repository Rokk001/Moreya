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

// Header-only Boost.Test, see test_DungeonHeartTier.cpp.
// OVERRIDE_BOOST_TEST_INCLUDED_WARNING
#define BOOST_TEST_MODULE OfficialLevels
#include <boost/test/included/unit_test.hpp>

#include "gamemap/OfficialLevelChecksums.h"
#include "gamemap/OfficialLevels.h"

#include "boost/filesystem.hpp"

#include <fstream>
#include <string>
#include <vector>

namespace
{
//! \brief The content of the test level.
const std::string LEVEL_CONTENT = "OpenDungeons_Version:0.7.4\n[Info]\nName\tKeep\n[/Info]\n";

//! \brief A temporary game data folder with a shipped level folder tree, an own level and user level folders.
struct LevelFolders
{
    //! \brief Creates the folders and the level files.
    LevelFolders() :
        mRoot(boost::filesystem::temp_directory_path() / boost::filesystem::unique_path("od-official-%%%%-%%%%"))
    {
        boost::filesystem::create_directories(mRoot / "levels" / "skirmish");
        boost::filesystem::create_directories(mRoot / "levels" / "multiplayer");
        boost::filesystem::create_directories(mRoot / "other");
        boost::filesystem::create_directories(mRoot / "user" / "skirmish");
        boost::filesystem::create_directories(mRoot / "user" / "multiplayer");
        write("levels/skirmish/Keep.level", LEVEL_CONTENT);
        write("levels/skirmish/Changed.level", LEVEL_CONTENT + "# changed\n");
        write("levels/multiplayer/Duel.level", LEVEL_CONTENT);
        write("other/Own.level", LEVEL_CONTENT);
        mChecksum = OfficialLevels::computeLevelChecksum(LEVEL_CONTENT);
        mTable.push_back({"skirmish/Keep.level", mChecksum.c_str()});
        mTable.push_back({"skirmish/Changed.level", mChecksum.c_str()});
        mTable.push_back({"multiplayer/Duel.level", mChecksum.c_str()});
    }

    //! \brief Removes the folders.
    ~LevelFolders()
    {
        boost::system::error_code error;
        boost::filesystem::remove_all(mRoot, error);
    }

    //! \brief Writes a file below the root.
    void write(const std::string& relative, const std::string& content)
    {
        std::ofstream file((mRoot / relative).string().c_str(), std::ios::binary);
        file << content;
    }

    //! \brief The path of a file below the root.
    std::string path(const std::string& relative) const
    {
        return (mRoot / relative).string();
    }

    //! \brief The verdict of a file against the test table.
    OfficialLevels::Verdict verify(const std::string& relative) const
    {
        return OfficialLevels::verifyLevelFile(path(relative), path("levels"), mTable.data(), mTable.size());
    }

    boost::filesystem::path mRoot;
    std::string mChecksum;
    std::vector<OfficialLevels::ChecksumEntry> mTable;
};
}

//! Checks the SHA-256 implementation against the published test vectors and that carriage returns do not count.
BOOST_AUTO_TEST_CASE(test_Sha256Vectors)
{
    BOOST_CHECK_EQUAL(OfficialLevels::computeSha256(""),
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855");
    BOOST_CHECK_EQUAL(OfficialLevels::computeSha256("abc"),
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
    BOOST_CHECK_EQUAL(OfficialLevels::computeSha256("abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq"),
        "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1");
    BOOST_CHECK_EQUAL(OfficialLevels::computeLevelChecksum("a\r\nb\r\n"), OfficialLevels::computeSha256("a\nb\n"));
}

//! Checks that a changed copy of a shipped level is rejected and that the unchanged level and own levels load.
BOOST_AUTO_TEST_CASE(test_ChangedShippedLevelRejected)
{
    LevelFolders folders;
    BOOST_CHECK(folders.verify("levels/skirmish/Keep.level") == OfficialLevels::Verdict::Unchanged);
    BOOST_CHECK(folders.verify("levels/skirmish/Changed.level") == OfficialLevels::Verdict::Modified);
    BOOST_CHECK(folders.verify("other/Own.level") == OfficialLevels::Verdict::NotOfficial);
    BOOST_CHECK(OfficialLevels::mayLoad(OfficialLevels::Verdict::Unchanged, true));
    BOOST_CHECK(OfficialLevels::mayLoad(OfficialLevels::Verdict::NotOfficial, true));
    // A changed shipped level never loads in multiplayer, in single player only in a developer build
    BOOST_CHECK(!OfficialLevels::mayLoad(OfficialLevels::Verdict::Modified, true));
#ifdef OD_DEVELOPER_MODE
    BOOST_CHECK(OfficialLevels::isDeveloperModeBuild());
    BOOST_CHECK(OfficialLevels::mayLoad(OfficialLevels::Verdict::Modified, false));
#else
    BOOST_CHECK(!OfficialLevels::isDeveloperModeBuild());
    BOOST_CHECK(!OfficialLevels::mayLoad(OfficialLevels::Verdict::Modified, false));
#endif
}

//! Checks the save target of the editor without and with the hidden option.
BOOST_AUTO_TEST_CASE(test_EditorSaveTarget)
{
    LevelFolders folders;
    const std::string userSkirmish = folders.path("user/skirmish");
    const std::string userMultiplayer = folders.path("user/multiplayer");
    const std::string levels = folders.path("levels");

    OfficialLevels::EditorSaveTarget target = OfficialLevels::resolveEditorSaveTarget(
        folders.path("levels/skirmish/Keep.level"), false, levels, false, userSkirmish, userMultiplayer);
    BOOST_CHECK(target.mRedirected);
    BOOST_CHECK(boost::filesystem::path(target.mPath) == boost::filesystem::path(userSkirmish) / "Keep.mmap");

    target = OfficialLevels::resolveEditorSaveTarget(folders.path("levels/multiplayer/Duel.level"), false, levels,
        false, userSkirmish, userMultiplayer);
    BOOST_CHECK(target.mRedirected);
    BOOST_CHECK(boost::filesystem::path(target.mPath) == boost::filesystem::path(userMultiplayer) / "Duel.mmap");

    target = OfficialLevels::resolveEditorSaveTarget(folders.path("levels/skirmish/Keep.level"), false, levels, true,
        userSkirmish, userMultiplayer);
    BOOST_CHECK(!target.mRedirected);
    BOOST_CHECK_EQUAL(target.mPath, folders.path("levels/skirmish/Keep.level"));

    BOOST_CHECK(!OfficialLevels::mayEditorOpen(true, false));
    BOOST_CHECK(OfficialLevels::mayEditorOpen(true, true));
    BOOST_CHECK(OfficialLevels::mayEditorOpen(false, false));
}

//! Checks that the checksums compiled into the build match every shipped level of the repository.
BOOST_AUTO_TEST_CASE(test_BuildChecksumsMatchRepositoryLevels)
{
    const boost::filesystem::path levels(OD_LEVELS_DIR);
    BOOST_REQUIRE(OfficialLevelChecksums::ENTRY_COUNT > 0);
    for(std::size_t i = 0; i < OfficialLevelChecksums::ENTRY_COUNT; ++i)
    {
        const boost::filesystem::path file = levels / OfficialLevelChecksums::ENTRIES[i].mKey;
        BOOST_CHECK_MESSAGE(OfficialLevels::verifyLevelFile(file.string(), levels.string(),
            OfficialLevelChecksums::ENTRIES, OfficialLevelChecksums::ENTRY_COUNT) == OfficialLevels::Verdict::Unchanged,
            file.string());
    }
}
