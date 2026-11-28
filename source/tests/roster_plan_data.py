"""Fixed data of the creature roster plan for the acceptance checks check_roster_cr*.py (CR1-CR13).

Every value here is written once from the plan (sections 2-10, decisions D1-D40) and from the approved names
(values proposal section 5c); the internal class names, skill group ids, family ids and pre-skill ids are the
contract of the roster work. Nothing here is read from the code or the configuration under test. The values of the
predecessors that a new creature takes over (D23, D30, D38) were counted once from the creatures.cfg, rooms.cfg,
relationships.cfg and creatureReactions.cfg of the base commit 525317fb1 (origin/main before the roster work).

The module also holds the small readers the checks share (a creature block parser and a skill tree parser).
"""
import hashlib
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

KEEPER, HERO, NEUTRAL = "keeper", "hero", "neutral"
WORKER, PRISON, CRYPT, SUMMONED = "worker", "prison", "crypt", "summoned"

# Class -> (side, wage class, skill group, family, display name D15); sections 2-4 and 5, 36 creatures
ROSTER = {
    # Hero side (13)
    "Knight": (HERO, 50, "tank", "human", "Knight"),
    "Dwarf2": (HERO, 200, "tank", "dwarf", "Dwarf Warrior"),
    "Paladin": (HERO, 400, "tank", "human", "Paladin"),
    "Priestess": (HERO, 400, "healer", "human", "Priestess"),
    "Monk": (HERO, 50, "healer", "human", "Monk"),
    "RunelordDwarf": (HERO, 200, "supporter", "dwarf", "Runelord Dwarf"),
    "Defender": (HERO, 400, "warrior", "human", "Defender"),
    "Adventurer": (HERO, 50, "skirmisher", "human", "Adventurer"),
    "Hunter": (HERO, 100, "skirmisher", "human", "Hunter"),
    "DarkElf": (HERO, 100, "skirmisher", "elf", "Dark Elf"),
    "Elf": (HERO, 100, "marksman", "elf", "Elf"),
    "Wizard": (HERO, 200, "mage", "arcane", "Wizard"),
    "DwarfWorker": (HERO, WORKER, "worker", "workfolk", "Dwarf Worker"),
    # Keeper side (15)
    "Troll": (KEEPER, 200, "tank", "greenskin", "Troll"),
    "Orc": (KEEPER, 50, "tank", "greenskin", "Orc"),
    "PitDemon": (KEEPER, 400, "tank", "demon", "Pit Demon"),
    "Vampire": (KEEPER, 400, "healer", "blood", "Vampire"),
    "Cultist": (KEEPER, 50, "healer", "blood", "Cultist"),
    "LizardMan": (KEEPER, 200, "supporter", "dragonkin", "Lizard Man"),
    "Skeleton": (KEEPER, PRISON, "warrior", "undead", "Skeleton"),
    "Goblin": (KEEPER, 100, "skirmisher", "greenskin", "Goblin"),
    "Ghoul": (KEEPER, 50, "skirmisher", "undead", "Ghoul"),
    "Butcher": (KEEPER, 400, "warrior", "greenskin", "Butcher"),
    "CaveHornet": (KEEPER, 100, "skirmisher", "vermin", "Cave Hornet"),
    "Lich": (KEEPER, CRYPT, "mage", "undead", "Lich"),
    "Banshee": (KEEPER, 200, "mage", "undead", "Banshee"),
    "Witch": (KEEPER, 100, "mage", "arcane", "Witch"),
    "Kobold": (KEEPER, WORKER, "worker", "workfolk", "Ziv"),
    # Neutral side (7 rogue creatures and the summoned creature)
    "CrystalGolem": (NEUTRAL, 100, "tank", "stone", "Crystal Golem"),
    "Cyclops": (NEUTRAL, 100, "tank", "stone", "Cyclops"),
    "Minotaur": (NEUTRAL, 200, "warrior", "beast", "Minotaur"),
    "Werewolf": (NEUTRAL, 100, "skirmisher", "beast", "Werewolf"),
    "Gnoll": (NEUTRAL, 100, "marksman", "beast", "Gnoll"),
    "Gnome": (NEUTRAL, 50, "marksman", "arcane", "Gnome"),
    "Dragon": (NEUTRAL, 400, "warrior", "dragonkin", "Dragon"),
    "Champion": (NEUTRAL, SUMMONED, "none", "none", "Shadow Lord"),
}

# The removed classes (CR2) and their successors (D6); keeper-side and rogue DarkElfs become the Banshee (D20, D35)
SUCCESSORS = {
    "Rat": "Banshee", "Spider": "Ghoul", "Roach": "Witch", "LavaSpawn": "Butcher", "Slime": "DarkElf",
    "Dwarf1": "Hunter", "NatureMonster": "Paladin", "Scarab": "Priestess", "TentacleAlbine": "CrystalGolem",
    "TentacleGreen": "Cyclops", "Kreatur": "Minotaur", "Wyvern": "Werewolf",
}
REMOVED = tuple(sorted(SUCCESSORS))
REMOVED_FAMILIES = ("tentacle", "wild")
# The hero worker keeps the model file Dwarf1.mesh; only the class Dwarf1 is removed (contract of the roster work)
KEPT_MESH_OF_REMOVED = {"Dwarf1.mesh": "DwarfWorker"}

# The creature whose values a new creature takes over (D23, D30): the successor table, the Gnoll from the Werewolf
# (whose values are the Wyvern's) and the Vampire from the Lich
PREDECESSOR = {
    "Banshee": "Rat", "Ghoul": "Spider", "Witch": "Roach", "Butcher": "LavaSpawn", "Hunter": "Dwarf1",
    "Paladin": "NatureMonster", "Priestess": "Scarab", "CrystalGolem": "TentacleAlbine", "Cyclops": "TentacleGreen",
    "Minotaur": "Kreatur", "Werewolf": "Wyvern", "Gnoll": "Wyvern", "Vampire": "Lich",
}

# Model file of every creature: kept creatures keep theirs, a new creature has <Class>.mesh, the Champion
# ShadowLord.mesh (contract of the roster work)
MESH = {
    "Kobold": "Kobold.mesh", "DwarfWorker": "Dwarf1.mesh", "Orc": "Orc.mesh", "LizardMan": "Lizardman.mesh",
    "Goblin": "Goblin.mesh", "PitDemon": "PitDemon.mesh", "Troll": "Troll.mesh", "Cultist": "Cultist.mesh",
    "CaveHornet": "CaveHornet.mesh", "Skeleton": "skeleton.mesh", "Lich": "lich.mesh",
    "Adventurer": "Adventurer.mesh", "Monk": "Monk.mesh", "Dwarf2": "Dwarf2.mesh", "Knight": "Knight.mesh",
    "Wizard": "Wizard.mesh", "DarkElf": "DarkElf.mesh", "Elf": "Elf.mesh", "RunelordDwarf": "RunelordDwarf.mesh",
    "Defender": "Defender.mesh", "Gnome": "Gnome.mesh", "Dragon": "Dragon.mesh", "Champion": "ShadowLord.mesh",
}
for _name in ("Paladin", "Priestess", "Hunter", "Vampire", "Ghoul", "Butcher", "Banshee", "Witch", "CrystalGolem",
              "Cyclops", "Minotaur", "Werewolf", "Gnoll"):
    MESH[_name] = _name + ".mesh"

# Creatures that attack from a distance (sections 2-4 and the values proposal: ranged magic, bow, spears, bombs);
# the Dragon has both lines (melee and fire), the Champion keeps its lines (explosion and melee)
RANGED = ("Banshee", "LizardMan", "Witch", "Lich", "Vampire", "Priestess", "Wizard", "Elf", "Gnoll", "Gnome")
ATTACK_LINES_DRAGON = ("Melee", "MissileLaunch")
ATTACK_LINES_CHAMPION = ("Explosion", "Melee")

# Life and wage per wage class at level 1 (section 7): MinHP, HP/Level, FeeBase, FeePerLevel (16 % of the wage)
CLASS_VALUES = {50: (35.5, 1.0, 50, 8), 100: (61.5, 1.25, 100, 16), 200: (106.5, 1.63, 200, 32),
                400: (184.5, 2.0, 400, 64)}
# Life about 15 % below the value of the wage class (section 7): Ghoul and Dark Elf
LOW_LIFE = {"Ghoul": 0.85, "DarkElf": 0.85}
# Creatures that keep today's wage and life (section 7): MinHP, HP/Level, FeeBase, FeePerLevel (None = no wage)
KEPT_VALUES = {"Skeleton": (106.5, 1.5, 200, 32), "Lich": (106.5, 1.5, 200, 32),
               "Kobold": (70.0, 1.0, None, None), "DwarfWorker": (70.0, 1.0, None, None),
               "Champion": (600.0, 0.0, 0, 0)}
# Mana pool (Mana x ManaPerPoint), Strength and Dexterity at level 1 (values proposal sections 2-4, first estimate;
# the proposal rounds a pool of 43.75 to 44)
ATTRIBUTES = {
    "Troll": (10, 30, 20), "Orc": (10, 30, 20), "PitDemon": (40, 25, 20), "Vampire": (70, 10, 25),
    "Cultist": (70, 10, 25), "LizardMan": (60, 20, 20), "Skeleton": (10, 30, 20), "Goblin": (44, 20, 20),
    "Ghoul": (44, 20, 20), "Butcher": (10, 30, 20), "CaveHornet": (44, 20, 20), "Lich": (70, 10, 25),
    "Banshee": (70, 10, 25), "Witch": (70, 10, 25), "Kobold": (50, 15, 25),
    "Knight": (10, 30, 20), "Dwarf2": (10, 30, 20), "Paladin": (40, 25, 20), "Priestess": (70, 10, 25),
    "Monk": (70, 30, 20), "RunelordDwarf": (60, 20, 20), "Defender": (10, 30, 20), "Adventurer": (44, 20, 20),
    "Hunter": (44, 20, 20), "DarkElf": (44, 20, 20), "Elf": (22.5, 20, 25), "Wizard": (70, 10, 25),
    "DwarfWorker": (50, 15, 25),
    "CrystalGolem": (10, 30, 20), "Cyclops": (10, 30, 20), "Minotaur": (40, 25, 20), "Werewolf": (44, 20, 20),
    "Gnoll": (22.5, 20, 25), "Gnome": (22.5, 20, 25), "Dragon": (40, 25, 20), "Champion": (40, 25, 20),
}
MANA_POOL_TOLERANCE = 0.5
# Walking speed set by the plan: Butcher slow (0.5), Werewolf fast (1.2), Crystal Golem slow (at most 0.5)
SPEED_EXACT = {"Butcher": 0.5, "Werewolf": 1.2}
SPEED_AT_MOST = {"CrystalGolem": 0.5}

# Skill groups (contract ids) with their three paths (section 5, names of section 5c) and the skills of tiers 1-3
GROUPS = ("tank", "healer", "supporter", "warrior", "skirmisher", "marksman", "mage", "worker")
OLD_GROUPS = ("blocker", "blitzer", "flanker", "archer", "caster")
PATHS = {
    "tank": (("Ironclad", ("Taunt", "Fortify", "Hardened Skin")),
             ("Evader", ("Sidestep", "Quick Recovery", "Riposte")),
             ("Regenerator", ("Recover", "Vigor", "Lasting Recovery"))),
    "healer": (("Mender", ("Mend", "Swift Mending", "Lifesaver")),
               ("Renewer", ("Circle of Renewal", "Thrift", "Deep Renewal")),
               ("Warder", ("Ward", "Steadfast Blessing", "Group Ward"))),
    "supporter": (("Empowerer", ("Aura of Might", "Aura of Iron", "Quick Hands")),
                  ("Blighter", ("Enfeeble", "Withering Curse", "Mark of Doom")),
                  ("Binder", ("Hinder", "Hold Fast", "Repel"))),
    "warrior": (("Slayer", ("Keen Edge", "Brutal Force", "Heavy Blow")),
                ("Reaver", ("Rend", "Cruel Cuts", "Deep Wound")),
                ("Ravager", ("Cleaving Spin", "Momentum", "Great Spin"))),
    "skirmisher": (("Assassin", ("Weak Spot", "Sprint", "Assassinate")),
                   ("Venomist", ("Poisoned Blade", "Sickening", "Deadly Venom")),
                   ("Whirlwind", ("Blade Spin", "Flow", "Flurry"))),
    "marksman": (("Sharpshooter", ("Steady Aim", "Keen Eye", "Seeking Shot")),
                 ("Poisoner", ("Poison Arrow", "Pinning Shot", "Piercing Arrows")),
                 ("Barrager", ("Blast Shot", "Rapid Reload", "Volley"))),
    "mage": (("Sparkcaller", ("Lightning", "Kindled Mind", "Frost Grip")),
             ("Witherer", ("Burning Curse", "Soul Siphon", "Thrifty Casting")),
             ("Pyromancer", ("Ember Burst", "Firestorm", "Death Wail"))),
    # Worker paths stay as today (section 10, Q5): path names and skill names of the base commit
    "worker": (("Delving", ("Strong Picks", "Tunnel Legs", "Rock Splitter")),
               ("Claiming", ("Quick Claim", "Deep Pockets", "Hurry")),
               ("Survival", ("Blink", "Toughen", "Patch Up"))),
}
# Template names (D37: three per group, one per path; section 5c: a template carries the name of its path; the
# worker templates keep their names)
TEMPLATE_NAMES = dict((group, tuple(path for path, _ in PATHS[group])) for group in GROUPS)
TEMPLATE_NAMES["worker"] = ("Digger", "Claimer", "Survivor")

# Families (D8, D19): family id -> (path name, tier 1-3 names or None when the names stay as today), members
FAMILIES = {
    "greenskin": ("Greenskin", None, ("Troll", "Orc", "Goblin", "Butcher")),
    "dwarf": ("Dwarf", None, ("Dwarf2", "RunelordDwarf")),
    "undead": ("Undead", None, ("Skeleton", "Lich", "Ghoul", "Banshee")),
    "vermin": ("Vermin", None, ("CaveHornet",)),
    "demon": ("Demon", None, ("PitDemon",)),
    "elf": ("Elf", None, ("Elf", "DarkElf")),
    "human": ("Human", None, ("Knight", "Paladin", "Priestess", "Monk", "Defender", "Adventurer", "Hunter")),
    "arcane": ("Arcane", None, ("Wizard", "Witch", "Gnome")),
    "dragonkin": ("Dragonkin", None, ("LizardMan", "Dragon")),
    "workfolk": ("Workfolk", None, ("Kobold", "DwarfWorker")),
    "blood": ("Bloodbound", ("Blood Thrift", "Blood Mending", "Thick Blood"), ("Vampire", "Cultist")),
    "beast": ("Beastkin", ("Wild Hide", "Fleet Paws", "Feral Strength"), ("Minotaur", "Werewolf", "Gnoll")),
    "stone": ("Stonekin", ("Stone Skin", "Rock Guard", "Granite Body"), ("CrystalGolem", "Cyclops")),
}

# Pre-skill of every creature (D1, D21, D25, D28, D29, D33): (id of the contract, group or "family:<id>", path,
# tier 1 skill name); None = no pre-skill
_TAUNT = ("TNK_A1", "tank", "Ironclad", "Taunt")
_MEND = ("HLR_A1", "healer", "Mender", "Mend")
_CIRCLE = ("HLR_B1", "healer", "Renewer", "Circle of Renewal")
_MIGHT = ("SUP_A1", "supporter", "Empowerer", "Aura of Might")
_WEAK_SPOT = ("SKR_A1", "skirmisher", "Assassin", "Weak Spot")
_BLAST = ("MRK_C1", "marksman", "Barrager", "Blast Shot")
PRE_SKILL = {
    "Knight": _TAUNT, "Dwarf2": _TAUNT, "Paladin": _TAUNT, "Troll": _TAUNT, "Orc": _TAUNT, "PitDemon": _TAUNT,
    "CrystalGolem": _TAUNT, "Cyclops": _TAUNT,
    "Monk": _MEND, "Cultist": _MEND, "Priestess": _CIRCLE, "Vampire": _CIRCLE,
    "RunelordDwarf": _MIGHT, "LizardMan": _MIGHT,
    "DarkElf": _WEAK_SPOT, "Goblin": _WEAK_SPOT,
    # Gnome: the blast shot as the Elf today (D21); the Elf keeps its present pre-skill, the blast shot
    "Gnome": _BLAST, "Elf": _BLAST,
    "Wizard": ("MAG_A1", "mage", "Sparkcaller", "Lightning"),
    # Family pre-skills kept (D33)
    "Lich": ("UND_1", "family:undead", "Undead", "Raise the Fallen"),
    "CaveHornet": ("VRM_1", "family:vermin", "Vermin", "Buzzing Spin"),
    "Dragon": ("DRK_1", "family:dragonkin", "Dragonkin", "Hail of Scales"),
    # Workers keep theirs
    "Kobold": ("WRK_C1", "worker", "Survival", "Blink"), "DwarfWorker": ("WRK_C1", "worker", "Survival", "Blink"),
}
for _name in ROSTER:
    PRE_SKILL.setdefault(_name, None)

# Tier 4 skill of every creature but the Shadow Lord (D16, D34, section 5c): name and the allowed kinds
_TANK_DEFENCE = ("BUFF_SELF_Defense",)
_SELF_STRENGTH = ("BUFF_SELF_StrengthChange",)
_SINGLE_HEAL = ("HEAL_ALLY", "HEAL_INSTANT")
_AREA_HEAL = ("HEAL_AREA", "HOT_AREA")
_AURA = ("AURA_ALLY_Defense", "AURA_ALLY_StrengthChange")
TIER_FOUR = {
    "Knight": ("Oath of Steel", _TANK_DEFENCE), "Dwarf2": ("Anvil Stand", _TANK_DEFENCE),
    "Troll": ("Mossback", _TANK_DEFENCE), "Orc": ("Iron Will", _TANK_DEFENCE),
    "CrystalGolem": ("Crystal Shell", _TANK_DEFENCE), "Cyclops": ("Giant's Bulwark", _TANK_DEFENCE),
    "Paladin": ("Radiant Circle", _AREA_HEAL), "PitDemon": ("Life Leech", ("DRAIN_HEAL_ALLIES",)),
    "Priestess": ("Great Renewal", _AREA_HEAL), "Vampire": ("Blood Theft", ("DRAIN_HEAL_ALLIES",)),
    "Monk": ("Laying on of Hands", _SINGLE_HEAL), "Cultist": ("Blood Rite", _SINGLE_HEAL),
    "RunelordDwarf": ("Rune Circle", _AURA), "LizardMan": ("War Drums", _AURA),
    # Damage dealers that keep their present tier 4 skill (name and kind of the base commit)
    "Adventurer": ("Hero's Moment", ("BUFF_SELF_StrengthChange",)),
    "Goblin": ("Dirty Tricks", ("BUFF_SELF_StrengthChange",)),
    "Skeleton": ("Bone Legion Call", ("SKELARMY",)), "Lich": ("Army of the Dead", ("SKELARMY",)),
    "Elf": ("Arrow Rain", ("HAILSTORM",)), "Wizard": ("Arcane Cataclysm", ("EXPLOSION",)),
    "CaveHornet": ("Hive Storm", ("WHIRLWIND",)), "Dragon": ("Dragonfire", ("EXPLOSION",)),
    "Defender": ("Halberd Sweep", ("FLURRY",)),
    "Ghoul": ("Feeding Frenzy", _SELF_STRENGTH), "Butcher": ("Cleaver", ("STRIKE",)),
    "Hunter": ("Hunting Fever", _SELF_STRENGTH), "DarkElf": ("Assassination", ("STRIKE",)),
    "Banshee": ("Death Scream", ("EXPLOSION",)), "Witch": ("Curse Fire", ("EXPLOSION",)),
    "Minotaur": ("Bull Charge", ("STRIKE",)), "Werewolf": ("Blood Moon", _SELF_STRENGTH),
    "Gnoll": ("Spear Hail", ("HAILSTORM",)), "Gnome": ("Bomb Hail", ("EXPLOSION",)),
    # Workers keep theirs
    "Kobold": ("Gold Rush", ("PASSIVE_dig%",)), "DwarfWorker": ("Mountain Heart", ("PASSIVE_dig%",)),
}

# Portal (D5, D7): faction spawn pools by wage class (sections 2-3), workers by spell, prison and crypt
SPAWN_POOLS = {
    "Keeper": (("Orc", "Cultist", "Ghoul"), ("Goblin", "CaveHornet", "Witch"), ("Troll", "LizardMan", "Banshee"),
               ("PitDemon", "Vampire", "Butcher")),
    "Hero": (("Knight", "Monk", "Adventurer"), ("Hunter", "DarkElf", "Elf"), ("Dwarf2", "RunelordDwarf", "Wizard"),
             ("Paladin", "Priestess", "Defender")),
}
WORKER_CLASS = {"Keeper": "Kobold", "Hero": "DwarfWorker"}
PRISON_CLASS, CRYPT_CLASS = "Skeleton", "Lich"
# Required room of every portal creature and favourite room of every neutral creature (D32; room type ids of
# rooms.cfg: Torture is the torture chamber)
REQUIRED_ROOM = {
    "Orc": "Tavern", "Cultist": "Library", "Ghoul": "Hatchery", "Adventurer": "Tavern", "Monk": "Library",
    "Knight": "TrainingHall",
    "Goblin": "Workshop", "Witch": "HerbGarden", "CaveHornet": "GuardRoom", "Hunter": "GuardRoom", "Elf": "HerbGarden",
    "DarkElf": "Casino",
    "Troll": "Prison", "LizardMan": "AlchemyLab", "Banshee": "GhostRoom", "Dwarf2": "Workshop",
    "RunelordDwarf": "GhostRoom", "Wizard": "AlchemyLab",
    "PitDemon": "Torture", "Vampire": "Crypt", "Butcher": "Temple", "Paladin": "Temple", "Priestess": "Infirmary",
    "Defender": "Prison",
}
NEUTRAL_FAVOURITE = {"Gnome": "Workshop", "CrystalGolem": "Workshop", "Cyclops": "GuardRoom", "Werewolf": "HerbGarden",
                     "Gnoll": "Hatchery", "Minotaur": "Arena"}
# Drache as today: the rooms of the Dragon of the base commit
DRAGON_ROOMS = (("Library", "150", "3.0"), ("TrainingHall", "100", "1.0"), ("Casino", "90", "1.0"),
                ("Tavern", "90", "1.0"), ("Temple", "90", "0.5"), ("Arena", "96", "1"), ("GuardRoom", "0", "1.0"))

# Values a new creature takes over from its predecessor (D23, D30, D38), counted once from the base commit:
# need values of [Stats], SHA-256 (first 16 hex digits) of the [MoodModifiers] and [CreatureBehaviours] rows
# (tokens joined by one space, rows by a newline), the room lines of the predecessor and its temple prayer mana.
NEED_KEYS = ("WakefulnessLost/Turn", "HungerGrowth/Turn", "UrgeGrowth/Turn", "ThirstGrowth/Turn", "Cleanliness",
             "DirtFactor", "AfraidOfGhosts", "TileSightRadius")
_NEEDS_DIRTY = ("0.05", "0.1", "0.1", "0.1", "0.25", "1.75")
_NEEDS_ROUGH = ("0.05", "0.1", "0.1", "0.1", "0.5", "1.5")
PREDECESSOR_NEEDS = {
    "Rat": _NEEDS_DIRTY + ("1", "15"), "Spider": _NEEDS_DIRTY + ("1", "15"), "Roach": _NEEDS_DIRTY + ("1", "15"),
    "LavaSpawn": ("0.025", "0.1", "0.1", "0.1", "0.5", "1.5", "0", "15"),
    "Dwarf1": ("0.05", "0.1", "0.1", "0.1", "1", "1", "1", "15"),
    "NatureMonster": ("0.035", "0.1", "0.1", "0.1", "1", "1", "0", "15"),
    "Scarab": _NEEDS_DIRTY + ("0", "15"), "TentacleAlbine": _NEEDS_ROUGH + ("0", "15"),
    "TentacleGreen": _NEEDS_ROUGH + ("0", "15"), "Kreatur": _NEEDS_ROUGH + ("0", "15"),
    "Wyvern": _NEEDS_ROUGH + ("0", "15"), "Lich": ("0", "0", "0", "0", "0.5", "0.25", "0", "15"),
}
PREDECESSOR_MOODS = {
    "Rat": "c3e15b5a06aa1a15", "Spider": "de5a24494d2606bb", "Roach": "8373ea2aafb8d09e",
    "LavaSpawn": "8373ea2aafb8d09e", "Dwarf1": "c3e15b5a06aa1a15", "NatureMonster": "8373ea2aafb8d09e",
    "Scarab": "8373ea2aafb8d09e", "TentacleAlbine": "8373ea2aafb8d09e", "TentacleGreen": "8373ea2aafb8d09e",
    "Kreatur": "8373ea2aafb8d09e", "Wyvern": "8373ea2aafb8d09e", "Lich": "8373ea2aafb8d09e",
}
PREDECESSOR_BEHAVIOURS = {
    "Rat": "067bf7012b6e18e8", "Spider": "d4647e8122d81894", "Roach": "d4647e8122d81894",
    "LavaSpawn": "067bf7012b6e18e8", "Dwarf1": "067bf7012b6e18e8", "NatureMonster": "067bf7012b6e18e8",
    "Scarab": "067bf7012b6e18e8", "TentacleAlbine": "067bf7012b6e18e8", "TentacleGreen": "067bf7012b6e18e8",
    "Kreatur": "067bf7012b6e18e8", "Wyvern": "067bf7012b6e18e8", "Lich": "067bf7012b6e18e8",
}
_COMMON = (("TrainingHall", "100", "1.0"), ("Casino", "90", "1.0"), ("Tavern", "90", "1.0"))
PREDECESSOR_ROOMS = {
    "Rat": _COMMON + (("Workshop", "80", "0.4"), ("Library", "50", "0.5"), ("Temple", "90", "0.5"),
                      ("Arena", "96", "1"), ("GuardRoom", "0", "1.0")),
    "Spider": _COMMON + (("Temple", "90", "0.5"), ("Arena", "96", "1"), ("GuardRoom", "0", "1.0"),
                         ("HerbGarden", "80", "0.5")),
    "Roach": _COMMON + (("Temple", "90", "0.5"), ("Arena", "96", "1"), ("GuardRoom", "0", "1.0"),
                        ("HerbGarden", "90", "1.0")),
    "LavaSpawn": _COMMON + (("Workshop", "80", "1.2"), ("Temple", "90", "0.5"), ("Library", "0", "0.5"),
                            ("Arena", "96", "1"), ("GuardRoom", "0", "1.0"), ("AlchemyLab", "80", "0.5")),
    "Dwarf1": (("Workshop", "200", "2.0"), ("Casino", "90", "1.0"), ("Tavern", "90", "1.0"),
               ("TrainingHall", "100", "1.0"), ("Temple", "90", "0.5"), ("Library", "0", "0.5"), ("Arena", "96", "1"),
               ("GuardRoom", "0", "1.0")),
    "NatureMonster": (("HerbGarden", "100", "1.5"),) + _COMMON + (("Temple", "90", "0.5"), ("Library", "0", "1.0"),
                                                                 ("Arena", "96", "1"), ("GuardRoom", "0", "1.0"),
                                                                 ("AlchemyLab", "90", "1.0")),
    "Scarab": _COMMON + (("Workshop", "80", "0.6"), ("Temple", "90", "0.5"), ("Library", "0", "0.5"),
                         ("Arena", "96", "1"), ("GuardRoom", "0", "1.0")),
    "TentacleAlbine": _COMMON + (("Temple", "90", "0.5"), ("Arena", "96", "1"), ("GuardRoom", "0", "1.0")),
    "TentacleGreen": _COMMON + (("Temple", "90", "0.5"), ("Arena", "96", "1"), ("GuardRoom", "0", "1.0")),
    "Kreatur": _COMMON + (("AlchemyLab", "80", "1.0"), ("Workshop", "80", "0.8"), ("Temple", "90", "0.5"),
                          ("Arena", "96", "1"), ("GuardRoom", "0", "1.0")),
    "Wyvern": (("Library", "150", "1.5"),) + _COMMON + (("Workshop", "80", "1.0"), ("Temple", "90", "0.5"),
                                                       ("Arena", "96", "1"), ("GuardRoom", "0", "1.0")),
    "Lich": (("Library", "150", "3.0"), ("Casino", "90", "1.0"), ("Tavern", "90", "1.0"),
             ("TrainingHall", "100", "1.0"), ("Temple", "90", "1"), ("Arena", "96", "1"), ("GuardRoom", "0", "1.0")),
}
# Rooms that every fighter type lists; the favourite room of a predecessor is one of its other rooms
ROOMS_OF_EVERY_TYPE = ("TrainingHall", "Casino", "Tavern", "Temple", "Arena", "GuardRoom")
PREDECESSOR_PRAYER_MANA = {
    "Rat": "0.9597012332812229", "Spider": "0.9597012332812229", "Roach": "1.9194024665624458",
    "LavaSpawn": "3.8388049331248917", "Dwarf1": "0.9597012332812229", "NatureMonster": "7.677609866249783",
    "Scarab": "7.677609866249783", "TentacleAlbine": "1.9194024665624458", "TentacleGreen": "1.9194024665624458",
    "Kreatur": "3.8388049331248917", "Wyvern": "1.9194024665624458", "Lich": "7.677609866249783",
}
# Racial relationship pairs of the base commit with the predecessor replaced by the new creature (D38)
RELATIONSHIP_PAIRS = {("LizardMan", "Ghoul"): "-10", ("Skeleton", "Vampire"): "10"}
# "Creatures" lines of creatureReactions.cfg that name the predecessor on the base commit (D38: the reaction lists
# of other creatures); the new creature is named on as many lines
PREDECESSOR_REACTION_LINES = {
    "Rat": 1, "Spider": 1, "Roach": 4, "LavaSpawn": 6, "Dwarf1": 1, "NatureMonster": 2, "Scarab": 1,
    "TentacleAlbine": 2, "TentacleGreen": 2, "Kreatur": 1, "Wyvern": 1, "Lich": 5,
}

# Temple recipes of the base commit with the successors put in (D6, D20: recipes 8 and 18-23 name the Banshee)
TEMPLE_RECIPES = (
    "Elf+Elf=Orc", "Gnome+Gnome+Gnome=ManaBoost", "Lich+Lich=PitDemon", "Troll+Troll=Cultist",
    "Butcher+Butcher=LizardMan", "Cultist+Cultist=Goblin", "Banshee+Banshee=Butcher", "Skeleton+Skeleton=Banshee",
    "Orc+Orc=Lich", "PitDemon+PitDemon=Banshee", "LizardMan+LizardMan=Skeleton",
    "Orc+Cultist+CaveHornet=Workers", "Orc+CaveHornet+Cultist=Workers", "Cultist+Orc+CaveHornet=Workers",
    "Cultist+CaveHornet+Orc=Workers", "CaveHornet+Orc+Cultist=Workers", "CaveHornet+Cultist+Orc=Workers",
    "PitDemon+Banshee+Cultist=Workers", "PitDemon+Cultist+Banshee=Workers", "Banshee+PitDemon+Cultist=Workers",
    "Banshee+Cultist+PitDemon=Workers", "Cultist+PitDemon+Banshee=Workers", "Cultist+Banshee+PitDemon=Workers",
)
# Number of temple recipes that name each successor (counted once from the list above)
RECIPES_PER_SUCCESSOR = {"Banshee": 9, "Butcher": 2, "Ghoul": 0, "Witch": 0, "DarkElf": 0, "Hunter": 0,
                         "Paladin": 0, "Priestess": 0, "CrystalGolem": 0, "Cyclops": 0, "Minotaur": 0,
                         "Werewolf": 0}

# Skill kinds by role (CR4, D3): the kinds that act for allies like a healer, the kinds of a supporter, the taunt,
# the damage kinds and the invisibility (D28)
ALLY_HEAL_KINDS = ("HEAL_ALLY", "HEAL_AREA", "HEAL_INSTANT", "HOT_AREA", "SHIELD_ALLY", "SHIELD_AREA",
                   "BUFF_ALLY_Defense", "DRAIN_HEAL_ALLIES")
SUPPORT_KINDS = ("AURA_ALLY_StrengthChange", "AURA_ALLY_Defense")
TAUNT_KINDS = ("TAUNT",)
DAMAGE_KINDS = ("EXPLOSION", "HAILSTORM", "GASCLOUD", "GRENADE", "GUIDEDBOLT", "WHIRLWIND", "STRIKE", "BLEED",
                "POISON", "CURSE_DOT", "BURN_DOT", "CHAIN_LIGHTNING", "FLURRY", "DRAIN", "MARK", "PASSIVE_dmg%",
                "PASSIVE_spell%", "PASSIVE_alldmg%", "PASSIVE_crit")
INVISIBLE_KINDS = ("INVISIBLE",)
# Tier 4 skills that may heal allies although the creature is a tank (the hybrids, D2, D16)
HYBRID_TIER_FOUR = ("Paladin", "PitDemon")

# New mechanics of CR6 (section 10 Q5, marked "new") and the reused abilities: (group, path, tier) -> kinds
NEW_MECHANICS = {
    ("tank", "Ironclad", 1): ("TAUNT",),
    ("tank", "Evader", 3): ("PARRY_COUNTER",),
    ("tank", "Regenerator", 3): ("HOT_SELF",),
    ("healer", "Mender", 3): ("HEAL_INSTANT",),
    ("healer", "Renewer", 1): ("HOT_AREA",),
    ("healer", "Warder", 1): ("SHIELD_ALLY",),
    ("healer", "Warder", 2): ("BUFF_ALLY_Defense",),
    ("healer", "Warder", 3): ("SHIELD_AREA",),
    ("supporter", "Empowerer", 2): ("AURA_ALLY_Defense",),
    ("supporter", "Blighter", 2): ("CURSE_DOT",),
    ("supporter", "Blighter", 3): ("MARK",),
    ("supporter", "Binder", 2): ("HOLD",),
    ("warrior", "Reaver", 1): ("BLEED",),
    ("skirmisher", "Venomist", 1): ("POISON",),
    ("skirmisher", "Whirlwind", 3): ("FLURRY",),
    ("marksman", "Poisoner", 1): ("POISON",),
    ("mage", "Witherer", 1): ("BURN_DOT",),
}
REUSED_MECHANICS = {
    ("healer", "Mender", 1): ("HEAL_ALLY",),
    ("supporter", "Empowerer", 1): ("AURA_ALLY_StrengthChange",),
    ("supporter", "Blighter", 1): ("DEBUFF_Weak",),
    ("supporter", "Binder", 1): ("DEBUFF_Slow",),
    ("warrior", "Slayer", 3): ("STRIKE",),
    ("warrior", "Ravager", 1): ("FLURRY",),
    ("marksman", "Barrager", 1): ("GRENADE",),
    ("mage", "Sparkcaller", 1): ("CHAIN_LIGHTNING", "GUIDEDBOLT"),
    ("mage", "Sparkcaller", 3): ("FREEZE",),
    ("mage", "Witherer", 2): ("DRAIN",),
}
# Taunt of one enemy at rank 1 and of all enemies near at rank 3 (D25, the approved Panzer example)
TAUNT_RANK3_PROPERTY = "AREA"
TAUNT_RANK5_PROPERTY = "LESS_DAMAGE_DEALT"
PARRY_COUNTER_PROPERTY = "COUNTER"
# New kinds that run for a time (a Duration cell) and kinds that are never cast (no mana)
TIMED_KINDS = ("AURA_ALLY_Defense", "BUFF_ALLY_Defense", "SHIELD_ALLY", "SHIELD_AREA", "HOT_AREA", "HOT_SELF",
               "CURSE_DOT", "MARK", "BLEED", "POISON", "BURN_DOT")
NEVER_CAST_KINDS = ("PARRY_COUNTER",)


def read(relative):
    """Returns the text of a file of the repository."""
    with open(os.path.join(ROOT, relative), encoding="utf-8") as handle:
        return handle.read()


def rows_hash(rows):
    """Returns the first 16 hex digits of the SHA-256 of rows of tokens (tokens joined by a space, rows by a newline)."""
    return hashlib.sha256("\n".join(" ".join(row) for row in rows).encode("utf-8")).hexdigest()[:16]


def parse_creatures(text):
    """Returns {class: {stat key: [tokens], "[Block]": [rows of tokens] or None}} of a creatures.cfg text."""
    creatures = {}
    for block in re.findall(r"^\[Creature\]\n(.*?)^\[/Creature\]", text, re.M | re.S):
        name = re.search(r"^\s*Name\s+(\S+)", block, re.M).group(1)
        entry = {}
        stats = re.search(r"\[Stats\](.*?)\[/Stats\]", block, re.S).group(1)
        for line in stats.splitlines():
            words = line.split("#")[0].split()
            if words:
                entry[words[0]] = words[1:]
        for key in ("RoomAffinity", "MoodModifiers", "CreatureBehaviours", "CreatureSkills", "XP"):
            match = re.search(r"\[%s\](.*?)\[/%s\]" % (key, key), block, re.S)
            rows = None
            if match:
                rows = [line.split("#")[0].split() for line in match.group(1).splitlines()
                        if line.split("#")[0].split()]
            entry["[" + key + "]"] = rows
        if name in creatures:
            raise AssertionError("creature defined twice: " + name)
        creatures[name] = entry
    return creatures


def parse_skill_config(text):
    """Returns (skills, tier fours, templates) of a creatureSkills.cfg text, each a list of {key: rest of line}."""
    result = {"Skill": [], "TierFour": [], "Template": []}
    for kind in result:
        for block in re.findall(r"^\[%s\]\n(.*?)^\[/%s\]" % (kind, kind), text, re.M | re.S):
            entry = {}
            for line in block.splitlines():
                line = line.split("#")[0].strip()
                if not line:
                    continue
                parts = line.split(None, 1)
                entry[parts[0]] = parts[1].strip() if len(parts) > 1 else ""
            result[kind].append(entry)
    return result["Skill"], result["TierFour"], result["Template"]


class Checker(object):
    """Collects the failed items of a check, each under the requirement it belongs to."""

    def __init__(self):
        """Starts with no failure and no item."""
        self.failures = []
        self.items = 0

    def check(self, condition, message):
        """Counts an item and records it as failed when the condition does not hold."""
        self.items += 1
        if not condition:
            self.failures.append(message)
        return condition
