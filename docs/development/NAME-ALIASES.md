# Own names

Names of features that are specific to this project. Use these names in code, config, GUI,
levels, docs and texts.

| Feature | Name | Identifier forms |
| --- | --- | --- |
| Spell that converts an enemy creature for a while | Defector | `Defector`, `defector`, `SpellDefector` |
| Spell that turns a creature into a harmless hen | Hexen Hen | `HexenHen`, `hexenHen`, `hexen_hen`, `SpellHexenHen` |
| Trap that calls the guards of a guard room | Watch Banner | `WatchBanner`, `watchBanner`, `TrapWatchBanner` |
| Sturdy door | Ironbound Door | `IronboundDoor`, `doorIronbound` |
| Door that fires and repairs itself | Runed Door | `RunedDoor`, `doorRuned` |
| Tile that gives extra mana to its owner | Mana Well | `ManaWell`, `manaWell`, `manaWellGround` |
| Permanent hero spawn of a map | Hero Portal | `HeroPortal` |
| Room where creatures fight | Arena | `RoomArena` |

Words that stay generic: Alarm, Gas, Lightning, Freeze, Fear, Steel Door, Barricade, Inferno,
Possess, Temple, Guard Room, Tremor, Create Gold, Champion.

# Loading data with older names

Savegames, levels and config files written before a rename may still contain the previous
spelling of a name. The old spellings are not written out anywhere in the repository. They are
stored only as 64-bit FNV-1a hashes of the lowercase name in `source/utils/NameAliases.cpp`,
each one with the current name. `NameAliases::resolve(name)` returns the current name for a
hashed old name and the argument unchanged for every other name.

It is called at the points where such names are parsed:

- `CreatureEffectManager::load` (effect names stored with creatures),
- `Skills::fromString` (skill names in levels, savegames and level scripts),
- `ConfigManager` (keys of the game, room, spell, trap and skill config),
- `Seat::readTilesVisualInitialStates` (tile visual tags in the seat block of savegames).

Shipped levels and configs use the current names directly, so the alias path is only taken for
older data. Tileset files are not covered: their material names are shipped with the game.

Removed creature classes have a table of their own (`CREATURE_CLASS_ALIASES`, same hash), so that
only creature class names are mapped to a creature class. `NameAliases::resolveCreatureClass(name)`
returns the class of the successor. It is used by:

- `GameMap::getClassDescription` and `GameMap::resolveClassName` (every lookup of a class by its
  name: creatures, ghosts, prisoners, portal waves, level scripts, raids), asked only when the map
  has no class of that name,
- `GameMap::getClassDescriptionForTuning` (the `[CreatureDefinitions]` tuning of an older level
  tunes the successor),
- `Creature::importFromStream` (the creature takes the class and the mesh of its successor).

Levels and saved games carry the line `CreatureRoster` in their `[Info]` block. While the
creatures of a file without it (written before the current roster) are read,
`NameAliases::resolveOldCreatureClassForSide` also maps the class that moved to the hero side: a
keeper-side or rogue creature of it loads as its successor, a hero-side one keeps its class.

When a name is renamed in the future, add the hash of the old name (lowercase, FNV-1a, offset
`14695981039346656037`, prime `1099511628211`) to the table, never the old name itself, and add the
case to `source/tests/check_name_aliases.py`, which builds the old names from fragments.
