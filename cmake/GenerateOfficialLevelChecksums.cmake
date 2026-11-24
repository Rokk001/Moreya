# Writes the checksums of the shipped levels into a C++ source that is compiled into the game.
#
#   cmake -DLEVELS_DIR=<repo>/levels [-DCONTENT_DIR=<content packages>] -DOUTPUT=<build>/generated/OfficialLevelChecksums.cpp
#         -P GenerateOfficialLevelChecksums.cmake
#
# Every .level below levels/skirmish, levels/multiplayer and levels/campaign (at any depth) gets an entry with its
# path below levels/ and the SHA-256 of its content without carriage returns (the game hashes the same way, see
# source/gamemap/OfficialLevels.cpp). With CONTENT_DIR the shipped levels of the content packages are added: the
# levels/ folder of every package (keyed by its path below that levels/ folder, as the game keys a level of a content
# package) and the .level files of the wing 1 package (keyed campaign/wing1/<file>, the path of the installed package
# below levels/, as when wing 1 lay in the game data). The output is only rewritten when its content changes, so an unchanged levels
# folder does not recompile the game.

if(NOT LEVELS_DIR OR NOT OUTPUT)
    message(FATAL_ERROR "GenerateOfficialLevelChecksums.cmake needs LEVELS_DIR and OUTPUT")
endif()

set(LEVEL_FILES)
foreach(FOLDER skirmish multiplayer campaign)
    file(GLOB_RECURSE FOLDER_FILES LIST_DIRECTORIES false "${LEVELS_DIR}/${FOLDER}/*.level")
    list(APPEND LEVEL_FILES ${FOLDER_FILES})
endforeach()

# Pairs "<key>|<file>" so that the levels of the game data and of the content packages are sorted by their keys
set(KEYED_FILES)
foreach(LEVEL_FILE ${LEVEL_FILES})
    file(RELATIVE_PATH KEY "${LEVELS_DIR}" "${LEVEL_FILE}")
    list(APPEND KEYED_FILES "${KEY}|${LEVEL_FILE}")
endforeach()
if(CONTENT_DIR AND IS_DIRECTORY "${CONTENT_DIR}")
    file(GLOB PACKAGES LIST_DIRECTORIES true "${CONTENT_DIR}/*")
    foreach(PACKAGE ${PACKAGES})
        if(NOT EXISTS "${PACKAGE}/Package.cfg")
            continue()
        endif()
        foreach(FOLDER skirmish multiplayer campaign)
            file(GLOB_RECURSE FOLDER_FILES LIST_DIRECTORIES false "${PACKAGE}/levels/${FOLDER}/*.level")
            foreach(LEVEL_FILE ${FOLDER_FILES})
                file(RELATIVE_PATH KEY "${PACKAGE}/levels" "${LEVEL_FILE}")
                list(APPEND KEYED_FILES "${KEY}|${LEVEL_FILE}")
            endforeach()
        endforeach()
        # Wing 1 was protected while it lay in the game data; the other wings never were
        get_filename_component(PACKAGE_NAME "${PACKAGE}" NAME)
        set(WING_FILES)
        if(PACKAGE_NAME STREQUAL "wing1")
            file(GLOB WING_FILES LIST_DIRECTORIES false "${PACKAGE}/*.level")
        endif()
        foreach(LEVEL_FILE ${WING_FILES})
            get_filename_component(FILE_NAME "${LEVEL_FILE}" NAME)
            list(APPEND KEYED_FILES "campaign/${PACKAGE_NAME}/${FILE_NAME}|${LEVEL_FILE}")
        endforeach()
    endforeach()
endif()
list(SORT KEYED_FILES)

set(ENTRIES "")
set(COUNT 0)
foreach(KEYED_FILE ${KEYED_FILES})
    string(FIND "${KEYED_FILE}" "|" SEPARATOR)
    string(SUBSTRING "${KEYED_FILE}" 0 ${SEPARATOR} KEY)
    math(EXPR FILE_START "${SEPARATOR} + 1")
    string(SUBSTRING "${KEYED_FILE}" ${FILE_START} -1 LEVEL_FILE)
    file(READ "${LEVEL_FILE}" CONTENT)
    string(REPLACE "\r" "" CONTENT "${CONTENT}")
    string(SHA256 CHECKSUM "${CONTENT}")
    string(APPEND ENTRIES "    {\"${KEY}\", \"${CHECKSUM}\"},\n")
    math(EXPR COUNT "${COUNT} + 1")
endforeach()

set(TEXT "// Generated at build time by cmake/GenerateOfficialLevelChecksums.cmake from the levels folder. Do not edit.\n")
string(APPEND TEXT "#include \"gamemap/OfficialLevelChecksums.h\"\n\n")
string(APPEND TEXT "namespace OfficialLevelChecksums\n{\n")
string(APPEND TEXT "const OfficialLevels::ChecksumEntry ENTRIES[] = {\n${ENTRIES}    {nullptr, nullptr}\n};\n\n")
string(APPEND TEXT "const std::size_t ENTRY_COUNT = ${COUNT};\n}\n")

set(OLD_TEXT "")
if(EXISTS "${OUTPUT}")
    file(READ "${OUTPUT}" OLD_TEXT)
endif()
if(NOT OLD_TEXT STREQUAL TEXT)
    file(WRITE "${OUTPUT}" "${TEXT}")
endif()
