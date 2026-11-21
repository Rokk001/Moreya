include(BoostTestTargets)

# SFML 3 is found through its CMake package, which only provides imported targets;
# the tests name the network and system libraries through SFML_LIBRARIES.
if(NOT SFML_LIBRARIES)
    set(SFML_LIBRARIES SFML::System SFML::Network)
endif()

# The aa-*/ab-* tests are integration tests: each test binary is a game client
# that expects a headless game server listening on localhost:32222 and hosting
# the multiplayer level named after the two-letter test prefix
# (levels/multiplayer/aa.level, ab.level, ...). The 00-* tests are plain unit
# tests and need no server.
# On Unix we wrap the integration tests in a launcher script that starts and
# stops that server, so they can be run through a plain `ctest` (or by running
# scripts/unix/run_unit_tests.sh from the build directory). On Windows, use
# scripts/win32/OpenDungeonsTests.bat instead.
if(UNIX)
    set(SERVER_LAUNCHER_AA LAUNCHER
        ${CMAKE_SOURCE_DIR}/scripts/unix/run_boost_test_with_server.sh
        $<TARGET_FILE:${PROJECT_BINARY_NAME}> aa.level)
    set(SERVER_LAUNCHER_AB LAUNCHER
        ${CMAKE_SOURCE_DIR}/scripts/unix/run_boost_test_with_server.sh
        $<TARGET_FILE:${PROJECT_BINARY_NAME}> ab.level)
else()
    set(SERVER_LAUNCHER_AA)
    set(SERVER_LAUNCHER_AB)
endif()

add_boost_test(00-Random
        SOURCES
        test_Random.cpp
        ${SRC}/utils/Random.h
        ${SRC}/utils/Random.cpp)

add_boost_test(00-AiLevels
        SOURCES
        test_AiLevels.cpp
        ${SRC}/ai/AiMath.h
        ${SRC}/ai/AiMath.cpp
        ${SRC}/ai/AiSaveFormat.h
        ${SRC}/ai/AiSaveFormat.cpp)

add_boost_test(00-SocialGenerator
        SOURCES
        test_SocialGenerator.cpp
        ${SRC}/social/CreatureProfile.h
        ${SRC}/social/SocialRng.h
        ${SRC}/social/SocialData.h
        ${SRC}/social/SocialData.cpp
        ${SRC}/social/SocialGenerator.h
        ${SRC}/social/SocialGenerator.cpp)

add_boost_test(00-SelectionSize
        SOURCES
        test_SelectionSize.cpp
        ${SRC}/utils/SelectionSize.h)

add_boost_test(00-PointerMapping
        SOURCES
        test_PointerMapping.cpp
        ${SRC}/modes/PointerMapping.h)

add_boost_test(00-WheelAccumulator
        SOURCES
        test_WheelAccumulator.cpp
        ${SRC}/modes/WheelAccumulator.h)

add_boost_test(00-ItemTooltipPlacement
        SOURCES
        test_ItemTooltipPlacement.cpp
        ${SRC}/render/ItemTooltipPlacement.h)

add_boost_test(00-ItemValueLines
        SOURCES
        test_ItemValueLines.cpp
        ${SRC}/entities/ItemValueLines.h)

add_boost_test(00-PostLog
        SOURCES
        test_PostLog.cpp
        ${SRC}/social/SocialRng.h
        ${SRC}/social/PostLog.h
        ${SRC}/social/PostLog.cpp)

add_boost_test(00-ODPacket
        SOURCES
        test_ODPacket.cpp
        ${SRC}/network/ODPacket.h
        ${SRC}/network/ODPacket.cpp
        LIBRARIES
        ${SFML_LIBRARIES})

add_boost_test(00-ConsoleInterface
        SOURCES
        test_ConsoleInterface.cpp
        ${SRC}/modes/AbstractModeManager.h
        ${SRC}/modes/ConsoleInterface.h
        ${SRC}/modes/ConsoleInterface.cpp
        ${SRC}/modes/Command.h
        ${SRC}/modes/Command.cpp)

add_boost_test(00-Goal
        SOURCES
        test_Goal.cpp
        ${SRC}/goals/Goal.cpp
        ${SRC}/utils/Helper.cpp
        ${SRC}/render/FrameStatistics.cpp
        ${SRC}/utils/LogManager.cpp
        ${SRC}/utils/LogSinkConsole.cpp
        LIBRARIES
        ${OGRE_LIBRARIES}
        ${SFML_LIBRARIES}
        ${Boost_FILESYSTEM_LIBRARY_RELEASE}
        ${Boost_SYSTEM_LIBRARY_RELEASE})

add_boost_test(00-CreatureRelationships
        SOURCES
        test_CreatureRelationships.cpp
        ${SRC}/game/CreatureRelationships.h
        ${SRC}/game/CreatureRelationships.cpp
        ${SRC}/utils/Helper.cpp
        ${SRC}/render/FrameStatistics.cpp
        ${SRC}/utils/LogManager.cpp
        ${SRC}/utils/LogSinkConsole.cpp
        LIBRARIES
        ${OGRE_LIBRARIES}
        ${SFML_LIBRARIES}
        ${Boost_FILESYSTEM_LIBRARY_RELEASE}
        ${Boost_SYSTEM_LIBRARY_RELEASE})

add_boost_test(00-PortraitCatalog
        SOURCES
        test_PortraitCatalog.cpp
        ${SRC}/render/PortraitCatalog.cpp
        ${SRC}/render/DungeonbookAppearanceConfig.cpp)

add_boost_test(00-CreatureAppearance
        SOURCES
        test_CreatureAppearance.cpp
        ${SRC}/game/CreatureAppearance.cpp
        ${SRC}/render/PortraitCatalog.cpp
        ${SRC}/render/PortraitCatalogRegistry.cpp)

add_boost_test(00-DungeonbookQuirks
        SOURCES
        test_DungeonbookQuirks.cpp
        ${SRC}/render/DungeonbookQuirks.cpp
        ${SRC}/render/PortraitCatalog.cpp
        ${SRC}/game/CreatureAppearance.cpp)

add_boost_test(00-DungeonbookMultiplayer
        SOURCES
        test_DungeonbookMultiplayer.cpp
        ${SRC}/network/ODPacket.cpp
        ${SRC}/render/PortraitCatalog.cpp
        ${SRC}/render/DungeonbookQuirks.cpp
        ${SRC}/game/CreatureAppearance.cpp
        LIBRARIES
        ${SFML_LIBRARIES})

add_boost_test(00-WholePortraitJpeg
        SOURCES
        test_WholePortraitJpeg.cpp
        LIBRARIES
        ${OGRE_LIBRARIES})
if(DEFINED 00-WholePortraitJpeg_TARGET_NAME)
    target_compile_definitions(${00-WholePortraitJpeg_TARGET_NAME} PRIVATE
        OD_WHOLE_PORTRAIT_SAMPLE="${CMAKE_SOURCE_DIR}/materials/portraits/whole/Elf.mesh/01.jpg")
endif()

add_boost_test(00-RelationshipHooks
        SOURCES
        test_RelationshipHooks.cpp
        ${SRC}/game/CreatureRelationships.h
        ${SRC}/game/CreatureRelationships.cpp
        ${SRC}/network/ODPacket.h
        ${SRC}/network/ODPacket.cpp
        ${SRC}/network/RelationshipPacket.h
        ${SRC}/utils/Helper.cpp
        ${SRC}/render/FrameStatistics.cpp
        ${SRC}/utils/LogManager.cpp
        ${SRC}/utils/LogSinkConsole.cpp
        LIBRARIES
        ${OGRE_LIBRARIES}
        ${SFML_LIBRARIES}
        ${Boost_FILESYSTEM_LIBRARY_RELEASE}
        ${Boost_SYSTEM_LIBRARY_RELEASE})

add_boost_test(00-LevelScript
        SOURCES
        test_LevelScript.cpp
        ${SRC}/gamemap/LevelScript.h
        ${SRC}/gamemap/LevelScript.cpp)

add_boost_test(00-CreatureSkillTreeView
        SOURCES
        test_CreatureSkillTreeView.cpp
        ${SRC}/creatureskill/CreatureSkillTreeView.h
        ${SRC}/creatureskill/CreatureSkillTreeView.cpp
        ${SRC}/creatureskill/CreatureSkillTree.cpp
        ${SRC}/tests/mocks/ConfigManagerSingleton.cpp
        ${SRC}/utils/Helper.cpp
        ${SRC}/render/FrameStatistics.cpp
        ${SRC}/utils/LogManager.cpp
        ${SRC}/utils/LogSinkConsole.cpp
        LIBRARIES
        ${SFML_LIBRARIES}
        ${Boost_FILESYSTEM_LIBRARY_RELEASE}
        ${Boost_SYSTEM_LIBRARY_RELEASE}
        ${OGRE_LIBRARIES})

add_boost_test(00-Campaign
        SOURCES
        test_Campaign.cpp
        ${SRC}/game/Campaign.h
        ${SRC}/game/Campaign.cpp
        ${SRC}/game/CampaignWorld.cpp)

add_boost_test(00-CampaignLevels
        SOURCES
        test_CampaignLevels.cpp
        ${SRC}/game/Campaign.h
        ${SRC}/game/Campaign.cpp
        ${SRC}/game/CampaignWorld.cpp)

add_boost_test(00-HandLimitRules
        SOURCES
        test_HandLimitRules.cpp
        ${SRC}/game/HandLimitRules.h
        ${SRC}/game/HandLimitRules.cpp)

add_boost_test(00-ServerGuards
        SOURCES
        test_ServerGuards.cpp
        ${SRC}/network/ServerGuards.h
        ${SRC}/network/ODPacket.cpp
        LIBRARIES
        ${SFML_LIBRARIES})

add_boost_test(00-Pathfinding
        SOURCES
        test_Pathfinding.cpp)

add_boost_test(00-DungeonHeartTier
        SOURCES
        test_DungeonHeartTier.cpp
        ${SRC}/rooms/HeartHealthTier.h
        ${SRC}/rooms/HeartHealthTier.cpp)

add_boost_test(00-HatcheryCycle
        SOURCES
        test_HatcheryCycle.cpp
        ${SRC}/rooms/HatcheryCycle.h
        ${SRC}/rooms/HatcheryCycle.cpp
        ${SRC}/rooms/HatcheryNestField.h
        ${SRC}/rooms/HatcheryRooster.h
        ${SRC}/rooms/HatcheryRooster.cpp
        ${SRC}/tests/mocks/ConfigManagerRoomDefaults.cpp
        LIBRARIES
        ${OGRE_LIBRARIES})

add_boost_test(00-WallTorches
        SOURCES
        test_WallTorches.cpp
        ${SRC}/rooms/WallTorches.h
        ${SRC}/rooms/WallTorches.cpp)

add_boost_test(00-WallCorners
        SOURCES
        test_WallCorners.cpp
        ${SRC}/gamemap/WallCorners.h
        ${SRC}/gamemap/WallCorners.cpp)

add_boost_test(00-LevelPreview
        SOURCES
        test_LevelPreview.cpp
        ${SRC}/gamemap/LevelPreview.h
        ${SRC}/gamemap/LevelPreview.cpp
        ${SRC}/gamemap/MiniMapColours.h
        ${SRC}/gamemap/MiniMapColours.cpp
        LIBRARIES
        ${OGRE_LIBRARIES}
        ${Boost_FILESYSTEM_LIBRARY_RELEASE}
        ${Boost_SYSTEM_LIBRARY_RELEASE})
if(DEFINED 00-LevelPreview_TARGET_NAME)
    target_compile_definitions(${00-LevelPreview_TARGET_NAME} PRIVATE
        OD_LEVELS_DIR="${CMAKE_SOURCE_DIR}/levels")
endif()

add_boost_test(aa-LaunchGame
        ${SERVER_LAUNCHER_AA}
        SOURCES
        ${SRC}/tests/mocks/ODClientTest.cpp
        ${SRC}/tests/mocks/ConfigManagerRoomDefaults.cpp
        ${SRC}/game/SeatData.cpp
        ${SRC}/game/SkillType.cpp
        ${SRC}/network/ClientNotification.cpp
        ${SRC}/network/ODPacket.cpp
        ${SRC}/network/ODSocketClient.cpp
        ${SRC}/network/ODSocketServer.cpp
        ${SRC}/network/ServerMode.cpp
        ${SRC}/network/ServerNotification.cpp
        ${SRC}/utils/Helper.cpp
        ${SRC}/utils/NameAliases.cpp
        ${SRC}/render/FrameStatistics.cpp
        ${SRC}/utils/LogManager.cpp
        ${SRC}/utils/LogSinkConsole.cpp
        test_LaunchGame.cpp
        LIBRARIES
        ${SFML_LIBRARIES}
        ${Boost_FILESYSTEM_LIBRARY_RELEASE}
        ${Boost_SYSTEM_LIBRARY_RELEASE}
        ${OGRE_LIBRARIES})

add_boost_test(aa-TestCreatures
        ${SERVER_LAUNCHER_AA}
        SOURCES
        ${SRC}/tests/mocks/ODClientTest.cpp
        ${SRC}/tests/mocks/ConfigManagerRoomDefaults.cpp
        ${SRC}/game/SeatData.cpp
        ${SRC}/game/SkillType.cpp
        ${SRC}/network/ClientNotification.cpp
        ${SRC}/network/ODPacket.cpp
        ${SRC}/network/ODSocketClient.cpp
        ${SRC}/network/ODSocketServer.cpp
        ${SRC}/network/ServerMode.cpp
        ${SRC}/network/ServerNotification.cpp
        ${SRC}/utils/Helper.cpp
        ${SRC}/utils/NameAliases.cpp
        ${SRC}/render/FrameStatistics.cpp
        ${SRC}/utils/LogManager.cpp
        ${SRC}/utils/LogSinkConsole.cpp
        test_Creatures.cpp
        LIBRARIES
        ${SFML_LIBRARIES}
        ${Boost_FILESYSTEM_LIBRARY_RELEASE}
        ${Boost_SYSTEM_LIBRARY_RELEASE}
        ${OGRE_LIBRARIES})

add_boost_test(aa-TestRooms
        ${SERVER_LAUNCHER_AA}
        SOURCES
        ${SRC}/tests/mocks/ODClientTest.cpp
        ${SRC}/tests/mocks/ConfigManagerRoomDefaults.cpp
        ${SRC}/game/SeatData.cpp
        ${SRC}/game/SkillType.cpp
        ${SRC}/network/ClientNotification.cpp
        ${SRC}/network/ODPacket.cpp
        ${SRC}/network/ODSocketClient.cpp
        ${SRC}/network/ODSocketServer.cpp
        ${SRC}/network/ServerMode.cpp
        ${SRC}/network/ServerNotification.cpp
        ${SRC}/rooms/RoomType.cpp
        ${SRC}/utils/Helper.cpp
        ${SRC}/utils/NameAliases.cpp
        ${SRC}/render/FrameStatistics.cpp
        ${SRC}/utils/LogManager.cpp
        ${SRC}/utils/LogSinkConsole.cpp
        test_Rooms.cpp
        LIBRARIES
        ${SFML_LIBRARIES}
        ${Boost_FILESYSTEM_LIBRARY_RELEASE}
        ${Boost_SYSTEM_LIBRARY_RELEASE}
        ${OGRE_LIBRARIES})

add_boost_test(aa-TestRoomSplit
        ${SERVER_LAUNCHER_AA}
        SOURCES
        ${SRC}/tests/mocks/ODClientTest.cpp
        ${SRC}/tests/mocks/ConfigManagerRoomDefaults.cpp
        ${SRC}/game/SeatData.cpp
        ${SRC}/game/SkillType.cpp
        ${SRC}/network/ClientNotification.cpp
        ${SRC}/network/ODPacket.cpp
        ${SRC}/network/ODSocketClient.cpp
        ${SRC}/network/ODSocketServer.cpp
        ${SRC}/network/ServerMode.cpp
        ${SRC}/network/ServerNotification.cpp
        ${SRC}/rooms/RoomType.cpp
        ${SRC}/utils/Helper.cpp
        ${SRC}/utils/NameAliases.cpp
        ${SRC}/render/FrameStatistics.cpp
        ${SRC}/utils/LogManager.cpp
        ${SRC}/utils/LogSinkConsole.cpp
        test_RoomSplit.cpp
        LIBRARIES
        ${SFML_LIBRARIES}
        ${Boost_FILESYSTEM_LIBRARY_RELEASE}
        ${Boost_SYSTEM_LIBRARY_RELEASE}
        ${OGRE_LIBRARIES})

add_boost_test(ab-TestTraps
        ${SERVER_LAUNCHER_AB}
        SOURCES
        ${SRC}/tests/mocks/ODClientTest.cpp
        ${SRC}/tests/mocks/ConfigManagerRoomDefaults.cpp
        ${SRC}/game/SeatData.cpp
        ${SRC}/game/SkillType.cpp
        ${SRC}/network/ClientNotification.cpp
        ${SRC}/network/ODPacket.cpp
        ${SRC}/network/ODSocketClient.cpp
        ${SRC}/network/ODSocketServer.cpp
        ${SRC}/network/ServerMode.cpp
        ${SRC}/network/ServerNotification.cpp
        ${SRC}/rooms/RoomType.cpp
        ${SRC}/utils/Helper.cpp
        ${SRC}/utils/NameAliases.cpp
        ${SRC}/render/FrameStatistics.cpp
        ${SRC}/utils/LogManager.cpp
        ${SRC}/utils/LogSinkConsole.cpp
        test_Traps.cpp
        LIBRARIES
        ${SFML_LIBRARIES}
        ${Boost_FILESYSTEM_LIBRARY_RELEASE}
        ${Boost_SYSTEM_LIBRARY_RELEASE}
        ${OGRE_LIBRARIES})


if(UNIX)
    # The integration tests all use the same server port: prevent ctest from
    # running two of them concurrently (e.g. with ctest -j).
    set_tests_properties(
        aa-LaunchGame-boost_test
        aa-TestCreatures-boost_test
        aa-TestRooms-boost_test
        aa-TestRoomSplit-boost_test
        ab-TestTraps-boost_test
        PROPERTIES RESOURCE_LOCK od-test-server)
endif()
