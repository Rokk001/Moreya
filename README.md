## Moreya

Moreya is an open source real-time strategy game set underground. You are the
keeper of a dungeon: your workers dig, claim and mine, you build rooms, traps
and doors, attract creatures and lead them into battle by dropping them where
they are needed, casting spells and luring enemies into traps.

### Download

Ready-to-play builds for Windows and Linux are attached to the
[releases](https://github.com/Rokk001/Moreya/releases) of this repository.

- **Windows:** unpack the zip archive and start `opendungeons-plus.exe`.
- **Linux (x86_64):** unpack the tar.gz archive and start `./moreya` in its
  top folder. The build needs glibc 2.38 or newer (for example Ubuntu 24.04,
  Fedora 39, Debian 13 or newer).

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

You need the following libraries:

- OGRE SDK (14.6.1)
- Boost (the version OGRE was linked against)
- CEGUI SDK (0.9999.0)
- SFML (3.1.0)
- OIS (1.5.1)

You also need CMake 3.13 or newer and a C++17 compiler:

- Windows: Visual Studio 2019 or newer
- Linux: GCC 9 or newer

On Linux:
```
mkdir build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
make -jX    # X is the number of CPU cores to use
```
The workflow `.github/workflows/linux-release.yml` shows a complete Linux
build including its dependencies.

On Windows, generate a Visual Studio solution with CMake and build the
`opendungeons-plus` target in the Release configuration.

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
