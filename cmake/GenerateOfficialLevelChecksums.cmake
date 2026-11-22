# Writes the checksums of the shipped levels into a C++ source that is compiled into the game.
#
#   cmake -DLEVELS_DIR=<repo>/levels -DOUTPUT=<build>/generated/OfficialLevelChecksums.cpp -P GenerateOfficialLevelChecksums.cmake
#
# Every .level below levels/skirmish, levels/multiplayer and levels/campaign (at any depth) gets an entry with its
# path below levels/ and the SHA-256 of its content without carriage returns (the game hashes the same way, see
# source/gamemap/OfficialLevels.cpp). The output is only rewritten when its content changes, so an unchanged levels
# folder does not recompile the game.

if(NOT LEVELS_DIR OR NOT OUTPUT)
    message(FATAL_ERROR "GenerateOfficialLevelChecksums.cmake needs LEVELS_DIR and OUTPUT")
endif()

set(LEVEL_FILES)
foreach(FOLDER skirmish multiplayer campaign)
    file(GLOB_RECURSE FOLDER_FILES LIST_DIRECTORIES false "${LEVELS_DIR}/${FOLDER}/*.level")
    list(APPEND LEVEL_FILES ${FOLDER_FILES})
endforeach()
list(SORT LEVEL_FILES)

set(ENTRIES "")
set(COUNT 0)
foreach(LEVEL_FILE ${LEVEL_FILES})
    file(RELATIVE_PATH KEY "${LEVELS_DIR}" "${LEVEL_FILE}")
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
