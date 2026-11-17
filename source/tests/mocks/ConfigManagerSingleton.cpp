/*
 * Copyright (C) 2026 OpenDungeons Team
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

// Unit tests that link creatureskill/CreatureSkillTree.cpp without the whole configuration: the skill tree code
// refers to the configuration singleton, which these tests never create, so only its pointer is defined here.
#include "utils/ConfigManager.h"

//! \brief The configuration singleton pointer; it stays empty in these tests.
template<> ConfigManager* Ogre::Singleton<ConfigManager>::msSingleton = nullptr;
