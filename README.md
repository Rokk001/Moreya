## Moreya

Moreya is an open source real-time strategy game set underground. You are the
keeper of a dungeon: your workers dig, claim and mine, you build rooms, traps
and doors, attract creatures and lead them into battle by dropping them where
they are needed, casting spells and luring enemies into traps.

### The campaign

The campaign tells of the guilds that try to plunder the dungeon of Moreya.

- 18 story levels in six wings, each with its own guild, and six hidden bonus
  chambers.
- Every story level starts with the Moreya gate closed. Until the countdown
  ends (up to 60 minutes) you build up your dungeon and reach the goals of the
  level; when you are ready you can open the gate earlier.
- Then the guild's raid comes through the gate: one or two groups under a
  named leader, with fighters, ranged members and healers. Raid members carry
  off gold from your treasuries and pick up the items your fallen creatures
  drop. Break the raid and catch its leader before the leader flees back
  through the gate; a fleeing leader's group follows.
- Hidden shards of the Heartstone can be carried home by your workers. Once all
  are found, later levels offer Summon Champion.
- The first win of a bonus chamber adds three new items to the merchant's
  wares for every later level.
- The difficulty (Easy to Hell) is chosen when a campaign starts and stays for
  the whole campaign.
- In campaign levels the hand holds at most one fighting creature at a time,
  with a 60 second cooldown after dropping it; workers are not limited.
  Skirmish and multiplayer games have no such limit.
- When every guild is defeated the campaign is complete. Defeated levels can be
  played again from the campaign map, or a new campaign can be started.

### Other ways to play

- **Skirmish:** single-player levels against computer keepers.
- **Multiplayer:** host or join a game over the network.
- **Editor:** create and change your own levels.

The in-game help is available through Options. Press Print Screen to save a
screenshot; Load Game in the options (or F8 while hosting a local game) opens
the saved-game browser.

### Build instructions

Moreya is built with CMake 3.13 or newer and a C++17 compiler. It needs
OGRE 14.6.1, CEGUI 0.9999.0, SFML 3.1.0, OIS 1.5.1, Boost, pybind11 and
Python 3. OGRE and CEGUI are built with the patches in
`scripts/win32/patches`.

#### Windows

Requirements: Visual Studio 2026 Build Tools (C++ workload), CMake 4.4.1
under `%BUILD_DEPS_ROOT%	ools`, Python 3.14 and Git. The default paths are
set in `scripts/win32/windows-paths.ps1` and can be overridden with
`BUILD_DEPS_ROOT`, `BUILD_PYTHON_ROOT` and `BUILD_VS_PATH`.

```
powershell -File scripts\win32\install-base-prereqs.ps1
powershell -File scripts\win32\install-boost-prereq.ps1
powershell -File scripts\win32\install-ogre-prereq.ps1
powershell -File scripts\win32\install-cegui-prereq.ps1
powershell -File scripts\win32\configure-windows-prereqs.ps1
cmake --build build\windows --config Release --target opendungeons-plus
```

#### Linux

Requirements: GCC 9 or newer, CMake, Ninja, Git, Python 3 and the X11,
OpenGL, FreeType, Ogg/Vorbis/FLAC and Boost development packages of the
distribution (`INSTALL_SYSTEM_PACKAGES=1` installs them with apt-get).

```
scripts/unix/install-linux-prereqs.sh <prefix>
scripts/unix/build-linux.sh <prefix>
```

#### Repository organisation

**Data files**
```
config/          - Game config files
dist/            - Icons and desktop entry files
gui/             - CEGUI files and GUI images
levels/          - Game levels, including the campaign
licenses/        - License files used for game data and code
materials/       - Materials (model texturing scripts and textures)
models/          - Model files
music/           - Music files
particles/       - Particle effect scripts
scripts/         - Packaging, check and CI scripts
sounds/          - Game sounds
AUTHORS          - List of past and current contributors
CREDITS          - Detailed listing of licenses and credits for the assets
LICENSE.md       - General information about the code and asset licenses
README.md        - The file you are currently reading
RELEASE-NOTES.md - What changed between versions
```

**Code files**
```
cmake/           - Helper files for CMake
source/          - The .cpp and .h files of the game
tools/           - Developer tools and asset generators
CMakeLists.txt   - CMake script for the build
```

### License

The source code is licensed under the GNU General Public License version 3 or
later. The art assets are covered by their respective licenses, listed in the
CREDITS file; see LICENSE.md and the licenses folder.

Moreya is based on the source code of the open source projects OpenDungeons and
OpenDungeonsPlus.
