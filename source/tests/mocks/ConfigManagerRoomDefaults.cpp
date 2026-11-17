/*
 * Copyright (C) 2026 OpenDungeons Team
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

// Unit tests that link room or seat code reading room settings without the whole configuration. The real
// ConfigManager loads every configuration file; this stub only exists so that ConfigManager::getSingleton()
// returns an object, and it holds no room settings, so every setting falls back to its built-in default.
#include "utils/ConfigManager.h"

template<> ConfigManager* Ogre::Singleton<ConfigManager>::msSingleton = nullptr;

//! \brief Creates the configuration singleton without reading any file.
ConfigManager::ConfigManager(const std::string& configPath, const std::string& userConfigPath,
        const std::string& soundPath)
{
    (void)configPath;
    (void)userConfigPath;
    (void)soundPath;
}

//! \brief Owns nothing, so there is nothing to release.
ConfigManager::~ConfigManager()
{
}

//! \brief No room setting is loaded; an unknown integer setting reads as 0 like in the real configuration.
int32_t ConfigManager::getRoomConfigInt32(const std::string& param) const
{
    (void)param;
    return 0;
}

//! \brief No room setting is loaded, so the caller's built-in default applies.
double ConfigManager::getRoomConfigDoubleOrDefault(const std::string& param, double defaultValue) const
{
    (void)param;
    return defaultValue;
}

namespace
{
//! \brief The one configuration instance of the test; constructing it registers the singleton.
ConfigManager gRoomDefaults("", "", "");
}
