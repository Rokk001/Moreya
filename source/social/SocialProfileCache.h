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

#ifndef SOCIALPROFILECACHE_H
#define SOCIALPROFILECACHE_H

#include "social/CreatureProfile.h"
#include "social/SocialData.h"

#include <map>
#include <set>
#include <stdint.h>
#include <string>
#include <vector>

namespace social
{

//! \brief Client side cache of the creature profiles. The social data files are loaded the
//! first time a profile is needed (the creature card is only opened on the client), any
//! loading problem is logged once. Nothing here is sent over the network or saved.
class SocialProfileCache
{
public:
    static SocialProfileCache& getSingleton();

    //! \brief Gender of a creature ("Female", "Male" or empty), identical to the profile gender. Usable
    //! on the server thread: it uses its own copy of the data, loaded once, and does not touch the cache.
    static std::string getCreatureGender(const std::string& creatureName, const std::string& className);

    //! \brief Returns the profile of the creature, generating it on first use.
    const CreatureProfile& getProfile(const std::string& creatureName, const std::string& className,
        bool isWorker);

    //! \brief The loaded social data (loaded on the first call).
    const SocialData& getData();

    //! \brief Forgets the profiles, called when the game is left. The loaded data stays.
    void clear();

private:
    SocialProfileCache();
    void loadData();

    //! True once loadData() has tried to read the data files
    bool mDataLoaded;
    SocialData mData;
    //! Generated profiles by creature name
    std::map<std::string, CreatureProfile> mProfiles;
    //! Full names handed out so far, kept unique between the cached profiles
    std::set<std::string> mUsedNames;
    //! Classes without a name group that were already logged
    std::set<std::string> mLoggedUnmappedClasses;
};

}

#endif // SOCIALPROFILECACHE_H
