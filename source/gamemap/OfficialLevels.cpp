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

#include "gamemap/OfficialLevels.h"

#include <boost/filesystem.hpp>

#include <cctype>
#include <cstdint>
#include <fstream>
#include <sstream>
#include <vector>

namespace OfficialLevels
{

namespace
{
//! \brief The shipped level folders below levels/.
const char* const OFFICIAL_FOLDERS[] = {"skirmish", "multiplayer", "campaign"};

//! \brief Round constants of SHA-256 (FIPS 180-4).
const uint32_t SHA256_K[64] = {
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
};

//! \brief Rotates a 32 bit value to the right.
uint32_t rotateRight(uint32_t value, unsigned int bits)
{
    return (value >> bits) | (value << (32 - bits));
}

//! \brief Processes one 64 byte block of SHA-256 into the state.
void sha256Block(uint32_t state[8], const unsigned char* block)
{
    uint32_t w[64];
    for(unsigned int i = 0; i < 16; ++i)
    {
        w[i] = (static_cast<uint32_t>(block[i * 4]) << 24) | (static_cast<uint32_t>(block[i * 4 + 1]) << 16)
            | (static_cast<uint32_t>(block[i * 4 + 2]) << 8) | static_cast<uint32_t>(block[i * 4 + 3]);
    }
    for(unsigned int i = 16; i < 64; ++i)
    {
        uint32_t s0 = rotateRight(w[i - 15], 7) ^ rotateRight(w[i - 15], 18) ^ (w[i - 15] >> 3);
        uint32_t s1 = rotateRight(w[i - 2], 17) ^ rotateRight(w[i - 2], 19) ^ (w[i - 2] >> 10);
        w[i] = w[i - 16] + s0 + w[i - 7] + s1;
    }

    uint32_t a = state[0];
    uint32_t b = state[1];
    uint32_t c = state[2];
    uint32_t d = state[3];
    uint32_t e = state[4];
    uint32_t f = state[5];
    uint32_t g = state[6];
    uint32_t h = state[7];
    for(unsigned int i = 0; i < 64; ++i)
    {
        uint32_t s1 = rotateRight(e, 6) ^ rotateRight(e, 11) ^ rotateRight(e, 25);
        uint32_t ch = (e & f) ^ ((~e) & g);
        uint32_t temp1 = h + s1 + ch + SHA256_K[i] + w[i];
        uint32_t s0 = rotateRight(a, 2) ^ rotateRight(a, 13) ^ rotateRight(a, 22);
        uint32_t maj = (a & b) ^ (a & c) ^ (b & c);
        uint32_t temp2 = s0 + maj;
        h = g;
        g = f;
        f = e;
        e = d + temp1;
        d = c;
        c = b;
        b = a;
        a = temp1 + temp2;
    }
    state[0] += a;
    state[1] += b;
    state[2] += c;
    state[3] += d;
    state[4] += e;
    state[5] += f;
    state[6] += g;
    state[7] += h;
}

//! \brief Compares two keys, without regard to case on Windows.
bool sameKey(const std::string& first, const char* second)
{
    const std::string other(second);
    if(first.size() != other.size())
        return false;
#ifdef _WIN32
    for(std::size_t i = 0; i < first.size(); ++i)
    {
        if(std::tolower(static_cast<unsigned char>(first[i])) != std::tolower(static_cast<unsigned char>(other[i])))
            return false;
    }
    return true;
#else
    return first == other;
#endif
}

//! \brief Tells whether two paths name the same existing folder.
bool sameFolder(const boost::filesystem::path& first, const boost::filesystem::path& second)
{
    boost::system::error_code error;
    bool same = boost::filesystem::equivalent(first, second, error);
    return !error && same;
}
} // namespace

//! \brief Computes SHA-256 with a self-contained implementation (no extra library is needed).
std::string computeSha256(const std::string& data)
{
    uint32_t state[8] = {0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
                         0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19};
    const unsigned char* bytes = reinterpret_cast<const unsigned char*>(data.data());
    const std::size_t size = data.size();
    std::size_t offset = 0;
    for(; offset + 64 <= size; offset += 64)
        sha256Block(state, bytes + offset);

    // The last block gets the 0x80 marker, zero padding and the length in bits (big endian)
    unsigned char tail[128] = {0};
    const std::size_t rest = size - offset;
    for(std::size_t i = 0; i < rest; ++i)
        tail[i] = bytes[offset + i];
    tail[rest] = 0x80;
    const std::size_t tailSize = (rest < 56) ? 64 : 128;
    const uint64_t bits = static_cast<uint64_t>(size) * 8;
    for(unsigned int i = 0; i < 8; ++i)
        tail[tailSize - 1 - i] = static_cast<unsigned char>(bits >> (8 * i));
    sha256Block(state, tail);
    if(tailSize == 128)
        sha256Block(state, tail + 64);

    static const char* const HEX = "0123456789abcdef";
    std::string result;
    result.reserve(64);
    for(unsigned int i = 0; i < 8; ++i)
    {
        for(int shift = 28; shift >= 0; shift -= 4)
            result.push_back(HEX[(state[i] >> shift) & 0xf]);
    }
    return result;
}

//! \brief Hashes a level content without its carriage returns, as the build step does.
std::string computeLevelChecksum(const std::string& content)
{
    std::string normalized;
    normalized.reserve(content.size());
    for(std::string::const_iterator it = content.begin(); it != content.end(); ++it)
    {
        if(*it != '\r')
            normalized.push_back(*it);
    }
    return computeSha256(normalized);
}

//! \brief Walks up from the file and compares every parent folder with the three shipped folders.
bool getOfficialKey(const std::string& filePath, const std::string& levelsRoot, std::string& key)
{
    key.clear();
    if(filePath.empty() || levelsRoot.empty())
        return false;

    boost::system::error_code error;
    boost::filesystem::path file = boost::filesystem::absolute(boost::filesystem::path(filePath), error);
    if(error)
        return false;
    boost::filesystem::path root = boost::filesystem::absolute(boost::filesystem::path(levelsRoot), error);
    if(error)
        return false;

    std::vector<boost::filesystem::path> roots;
    for(const char* folder : OFFICIAL_FOLDERS)
    {
        boost::filesystem::path official = root / folder;
        if(boost::filesystem::is_directory(official, error) && !error)
            roots.push_back(official);
    }
    if(roots.empty())
        return false;

    // The names below the matching folder, from the file upwards
    std::vector<std::string> names;
    names.push_back(file.filename().string());
    boost::filesystem::path folder = file.parent_path();
    while(!folder.empty())
    {
        for(std::size_t i = 0; i < roots.size(); ++i)
        {
            if(!sameFolder(folder, roots[i]))
                continue;

            key = roots[i].filename().string();
            for(std::vector<std::string>::reverse_iterator it = names.rbegin(); it != names.rend(); ++it)
                key += "/" + *it;
            return true;
        }
        boost::filesystem::path parent = folder.parent_path();
        if(parent == folder)
            break;
        names.push_back(folder.filename().string());
        folder = parent;
    }
    return false;
}

//! \brief Searches the table entry of a key.
const char* findChecksum(const std::string& key, const ChecksumEntry* entries, std::size_t count)
{
    if(entries == nullptr)
        return nullptr;
    for(std::size_t i = 0; i < count; ++i)
    {
        if(entries[i].mKey != nullptr && sameKey(key, entries[i].mKey))
            return entries[i].mSha256;
    }
    return nullptr;
}

//! \brief Reads the file and compares its checksum with the table entry of its key.
Verdict verifyLevelFile(const std::string& filePath, const std::string& levelsRoot, const ChecksumEntry* entries,
    std::size_t count)
{
    std::string key;
    if(!getOfficialKey(filePath, levelsRoot, key))
        return Verdict::NotOfficial;

    const char* expected = findChecksum(key, entries, count);
    if(expected == nullptr)
        return Verdict::NotShipped;

    std::ifstream file(filePath.c_str(), std::ios::in | std::ios::binary);
    if(!file.is_open())
        return Verdict::Unreadable;
    std::ostringstream content;
    content << file.rdbuf();
    if(file.bad())
        return Verdict::Unreadable;

    if(computeLevelChecksum(content.str()) == expected)
        return Verdict::Unchanged;
    return Verdict::Modified;
}

//! \brief True only in a build made with the developer option.
bool isDeveloperModeBuild()
{
#ifdef OD_DEVELOPER_MODE
    return true;
#else
    return false;
#endif
}

//! \brief Rejects a changed shipped level; only a developer build lets it through outside of multiplayer.
bool mayLoad(Verdict verdict, bool multiplayer)
{
    if(verdict != Verdict::Modified)
        return true;
#ifdef OD_DEVELOPER_MODE
    if(!multiplayer)
        return true;
#else
    (void)multiplayer;
#endif
    return false;
}

//! \brief A shipped level opens in the editor only with the hidden option.
bool mayEditorOpen(bool officialLevel, bool editOfficialLevels)
{
    return !officialLevel || editOfficialLevels;
}

//! \brief Applies the extension of the player maps to a file name.
std::string toUserMapName(const std::string& fileName)
{
    if(fileName.empty() || (fileName == ".") || (fileName == ".."))
        return fileName;

    const std::string levelExtension(LEVEL_FILE_EXTENSION);
    const std::string mapExtension(USER_MAP_EXTENSION);
    if((fileName.size() > levelExtension.size())
        && (fileName.compare(fileName.size() - levelExtension.size(), levelExtension.size(), levelExtension) == 0))
    {
        return fileName.substr(0, fileName.size() - levelExtension.size()) + mapExtension;
    }
    if((fileName.size() > mapExtension.size())
        && (fileName.compare(fileName.size() - mapExtension.size(), mapExtension.size(), mapExtension) == 0))
    {
        return fileName;
    }
    return fileName + mapExtension;
}

//! \brief Picks the file an editor save writes; never a shipped level without the hidden option.
EditorSaveTarget resolveEditorSaveTarget(const std::string& target, bool saveAs, const std::string& levelsRoot,
    bool editOfficialLevels, const std::string& userSkirmishFolder, const std::string& userMultiplayerFolder)
{
    EditorSaveTarget result;
    result.mPath = target;

    const boost::filesystem::path requested(target);
    const std::string name = requested.filename().string();
    // A missing file name is refused by the caller, it is no file of a shipped folder
    if(name.empty() || (name == ".") || (name == ".."))
        return result;

    std::string key;
    const bool official = getOfficialKey(target, levelsRoot, key);
    if(official && editOfficialLevels)
        return result;

    if(!official)
    {
        if(saveAs)
            result.mPath = (requested.parent_path() / toUserMapName(name)).string();
        return result;
    }

    // A shipped level without the hidden option: an own copy in the user level folder
    const bool multiplayer = (key.compare(0, std::string("multiplayer/").size(), "multiplayer/") == 0);
    const boost::filesystem::path folder(multiplayer ? userMultiplayerFolder : userSkirmishFolder);
    const std::string stem = requested.stem().string();
    boost::filesystem::path copy = folder / (stem + USER_MAP_EXTENSION);
    boost::system::error_code error;
    for(int number = 2; boost::filesystem::exists(copy, error) && (number < 10000); ++number)
    {
        std::ostringstream copyName;
        copyName << stem << "-" << number << USER_MAP_EXTENSION;
        copy = folder / copyName.str();
    }
    result.mPath = copy.string();
    result.mRedirected = true;
    return result;
}

} // namespace OfficialLevels
