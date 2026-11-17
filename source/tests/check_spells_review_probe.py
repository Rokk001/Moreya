"""Compile extracted production rules of the six spells of the spells review against controlled fixtures; never
launch the game.

    python source/tests/check_spells_review_probe.py

Runs one compiled probe with the production bodies of: the wall rule of Break Wall (valid and invalid tiles), the target
rules of Curse, Blessing, Invisibility and Plague, the rule that workers and the champion never get sick, the claimed
tiles Reveal Enemy shows, and the mood effects of curse and blessing (amounts, stacking, clamp at the maximum).
This check deliberately requires the maintained developer compiler environment (cl). It is not a static check.
"""
from pathlib import Path
import json
import subprocess
import tempfile
import time

repo = Path(__file__).resolve().parents[2]


def read(path):
    """Reads a production source file below the repository root."""
    return (repo / path).read_text(encoding="utf-8")


def function(text, signature):
    """Extracts a complete production function, keeping its body unchanged."""
    start = text.index(signature)
    opening = text.index("{", start)
    depth, end = 1, opening + 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


PRELUDE = r"""
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
//! \brief Fails a named production-behaviour assertion.
void check(bool result, const char* name) { if(!result) throw std::runtime_error(name); }
//! \brief Compares fractional values of the production code.
void near(double result, double expected, const char* name) { check(std::abs(result - expected) < 1e-9, name); }
//! \brief A seat with a team: seats of one team are allied.
struct Seat
{
    int mTeam;
    //! \brief Same team, as Seat::isAlliedSeat.
    bool isAlliedSeat(const Seat* seat) const { return mTeam == seat->mTeam; }
};
//! \brief The tile types the wall rule distinguishes.
enum class TileType { nullTileType, dirt, gold, rock, water, lava, gem, manaWell };
//! \brief The tile looks the client knows.
enum class TileVisual { nullTileVisual, claimedFull, dirtFull, goldFull, claimedGround };
//! \brief A tile with the state the rules read.
struct Tile
{
    TileType mType = TileType::dirt;
    TileVisual mVisual = TileVisual::nullTileVisual;
    bool mFull = true;
    bool mClaimed = false;
    bool mServer = true;
    bool mSeen = true;
    Seat* mSeat = nullptr;
    //! \brief The type of the tile.
    TileType getType() const { return mType; }
    //! \brief The look of the tile on a client.
    TileVisual getTileVisual() const { return mVisual; }
    //! \brief True for a wall.
    bool isFullTile() const { return mFull; }
    //! \brief True when the tile is claimed.
    bool isClaimed() const { return mClaimed; }
    //! \brief True on the server map.
    bool getIsOnServerMap() const { return mServer; }
    //! \brief The claiming seat.
    Seat* getSeat() const { return mSeat; }
};
//! \brief A creature kind with its flags.
struct CreatureDefinition
{
    std::vector<int> mMoods;
    bool mWorker = false;
    bool mChampion = false;
    //! \brief The mood lines of the kind; empty for a kind without mood.
    const std::vector<int>& getCreatureMoods() const { return mMoods; }
    //! \brief True for a worker.
    bool isWorker() const { return mWorker; }
    //! \brief True for the champion.
    bool isChampion() const { return mChampion; }
};
//! \brief The mood effect record of the production header.
struct CreatureMoodEffect
{
    std::string mName;
    double mStrength;
    double mTurnsLeft;
    //! \brief Creates a running effect.
    CreatureMoodEffect(const std::string& name, double strength, double turnsLeft) :
        mName(name), mStrength(strength), mTurnsLeft(turnsLeft) {}
};
//! \brief The base mood of the configuration.
struct ConfigManager
{
    //! \brief The one configuration.
    static ConfigManager& getSingleton() { static ConfigManager config; return config; }
    //! \brief CreatureBaseMood, the maximum of the stored mood.
    int getCreatureBaseMood() const { return 1500; }
};
//! \brief A creature with the state the rules read.
struct Creature
{
    const CreatureDefinition* mDefinition = nullptr;
    Seat* mSeat = nullptr;
    Seat* mSeatPrison = nullptr;
    Tile* mTile = nullptr;
    bool mAlive = true;
    bool mKo = false;
    bool mInvisible = false;
    bool mSick = false;
    bool mNeedFireRefresh = false;
    double mStoredMood = 1000.0;
    std::vector<CreatureMoodEffect> mMoodEffects;
    //! \brief True while alive.
    bool isAlive() const { return mAlive; }
    //! \brief The keeper of the creature.
    Seat* getSeat() const { return mSeat; }
    //! \brief The kind of the creature.
    const CreatureDefinition* getDefinition() const { return mDefinition; }
    //! \brief The seat of the prison holding it.
    Seat* getSeatPrison() const { return mSeatPrison; }
    //! \brief True in a prison or torture chamber.
    bool isInContainment() const { return mSeatPrison != nullptr; }
    //! \brief True while knocked out.
    bool isKo() const { return mKo; }
    //! \brief True while the Invisibility spell hides it.
    bool isSpellInvisible() const { return mInvisible; }
    //! \brief True while sick.
    bool isPlagueSick() const { return mSick; }
    //! \brief The tile the creature stands on.
    Tile* getPositionTile() const { return mTile; }
    bool canCatchPlague() const;
    void addMoodEffect(const std::string& name, double totalPoints, double turns);
    void changeStoredMood(double points);
};
//! \brief The seat sees the tile when the fixture says so.
bool seen(Tile& tile, const Seat*) { return tile.mSeen; }
//! \brief Holds the wall rule of Break Wall.
struct SpellBreakWall { static bool isValidWall(Tile& tile, const Seat* caster); };
//! \brief Holds the target rule of Curse.
struct SpellCurse
{
    static bool isValidTarget(const Creature& creature, const Seat* caster);
    //! \brief The vision test of Spell.
    static bool isTileSeenBy(Tile& tile, const Seat* seat) { return seen(tile, seat); }
};
//! \brief Holds the target rule of Blessing.
struct SpellBlessing { static bool isValidTarget(const Creature& creature, const Seat* caster); };
//! \brief Holds the target rule of Invisibility.
struct SpellInvisibility { static bool isValidTarget(const Creature& creature, const Seat* caster); };
//! \brief Holds the target rule of Plague.
struct SpellPlague
{
    static bool isValidTarget(const Creature& creature, const Seat* caster);
    //! \brief The vision test of Spell.
    static bool isTileSeenBy(Tile& tile, const Seat* seat) { return seen(tile, seat); }
};
//! \brief A map of tiles in columns.
struct GameMap
{
    std::vector<std::vector<Tile>> mTiles;
    //! \brief The width of the map.
    int getMapSizeX() const { return static_cast<int>(mTiles.size()); }
    //! \brief The height of the map.
    int getMapSizeY() const { return static_cast<int>(mTiles.front().size()); }
    //! \brief The tile at the coordinates.
    Tile* getTile(int x, int y) { return &mTiles[x][y]; }
};
//! \brief Holds the claimed tile list of Reveal Enemy.
struct SpellRevealEnemy { static std::vector<Tile*> getClaimedTiles(GameMap* gameMap, const Seat* owner); };
"""


def production():
    """The production bodies the probe runs, unchanged."""
    wall = read("source/spells/SpellBreakWall.cpp")
    creature = read("source/entities/Creature.cpp")
    return "\n".join((
        function(wall, "bool SpellBreakWall::isValidWall("),
        function(read("source/spells/SpellCurse.cpp"), "bool SpellCurse::isValidTarget("),
        function(read("source/spells/SpellBlessing.cpp"), "bool SpellBlessing::isValidTarget("),
        function(read("source/spells/SpellInvisibility.cpp"), "bool SpellInvisibility::isValidTarget("),
        function(read("source/spells/SpellPlague.cpp"), "bool SpellPlague::isValidTarget("),
        function(read("source/spells/SpellRevealEnemy.cpp"), "std::vector<Tile*> SpellRevealEnemy::getClaimedTiles("),
        function(creature, "bool Creature::canCatchPlague("),
        function(creature, "void Creature::addMoodEffect("),
        function(creature, "void Creature::changeStoredMood("),
    ))


CASES = r"""
//! \brief Runs every case and prints OK.
int main()
{
    Seat own = {1};
    Seat ally = {1};
    Seat enemy = {2};

    // Break Wall: an enemy claimed earth wall, nothing else
    Tile wall;
    wall.mClaimed = true;
    wall.mSeat = &enemy;
    check(SpellBreakWall::isValidWall(wall, &own), "enemy claimed earth wall");
    wall.mSeat = &ally;
    check(!SpellBreakWall::isValidWall(wall, &own), "allied wall refused");
    wall.mSeat = &own;
    check(!SpellBreakWall::isValidWall(wall, &own), "own wall refused");
    wall.mSeat = &enemy;
    wall.mClaimed = false;
    check(!SpellBreakWall::isValidWall(wall, &own), "unclaimed wall refused");
    wall.mClaimed = true;
    const TileType refused[] = {TileType::gold, TileType::gem, TileType::rock, TileType::lava, TileType::water};
    for(TileType type : refused)
    {
        wall.mType = type;
        check(!SpellBreakWall::isValidWall(wall, &own), "gold, gem, rock, lava and water refused");
    }
    wall.mType = TileType::dirt;
    wall.mFull = false;
    check(!SpellBreakWall::isValidWall(wall, &own), "claimed ground refused");
    Tile seenWall;
    seenWall.mServer = false;
    seenWall.mVisual = TileVisual::claimedFull;
    seenWall.mSeat = &enemy;
    check(SpellBreakWall::isValidWall(seenWall, &own), "client: an enemy claimed wall");
    seenWall.mVisual = TileVisual::dirtFull;
    check(!SpellBreakWall::isValidWall(seenWall, &own), "client: an earth wall refused");

    // Creature kinds
    CreatureDefinition fighter;
    fighter.mMoods.push_back(1);
    CreatureDefinition moodless;
    CreatureDefinition worker;
    worker.mMoods.push_back(1);
    worker.mWorker = true;
    CreatureDefinition champion;
    champion.mChampion = true;
    Tile ground;
    ground.mFull = false;

    // Curse: a visible living enemy with a mood anywhere, not in the caster's prison, not hidden
    Creature target;
    target.mDefinition = &fighter;
    target.mSeat = &enemy;
    target.mTile = &ground;
    check(SpellCurse::isValidTarget(target, &own), "curse: visible enemy");
    target.mSeat = &ally;
    check(!SpellCurse::isValidTarget(target, &own), "curse: allied creature refused");
    target.mSeat = &enemy;
    target.mDefinition = &moodless;
    check(!SpellCurse::isValidTarget(target, &own), "curse: a kind without mood refused");
    target.mDefinition = &fighter;
    target.mSeatPrison = &own;
    check(!SpellCurse::isValidTarget(target, &own), "curse: the caster's prisoner refused");
    target.mSeatPrison = &ally;
    check(SpellCurse::isValidTarget(target, &own), "curse: a prisoner of another keeper");
    target.mSeatPrison = nullptr;
    ground.mSeen = false;
    check(!SpellCurse::isValidTarget(target, &own), "curse: an unseen creature refused");
    ground.mSeen = true;
    target.mInvisible = true;
    check(!SpellCurse::isValidTarget(target, &own), "curse: a hidden creature refused");
    target.mInvisible = false;
    target.mAlive = false;
    check(!SpellCurse::isValidTarget(target, &own), "curse: a dead creature refused");
    target.mAlive = true;

    // Plague: a visible living enemy that can be sick and is not sick yet
    check(SpellPlague::isValidTarget(target, &own), "plague: visible enemy");
    target.mSick = true;
    check(!SpellPlague::isValidTarget(target, &own), "plague: already sick refused");
    target.mSick = false;
    target.mDefinition = &worker;
    check(!SpellPlague::isValidTarget(target, &own), "plague: a worker never gets sick");
    target.mDefinition = &champion;
    check(!SpellPlague::isValidTarget(target, &own), "plague: the champion never gets sick");
    target.mDefinition = &fighter;
    target.mSeat = &ally;
    check(!SpellPlague::isValidTarget(target, &own), "plague: allied creature refused");

    // Blessing: an own living creature with a mood anywhere, not in a prison
    Creature mine;
    mine.mDefinition = &fighter;
    mine.mSeat = &own;
    check(SpellBlessing::isValidTarget(mine, &own), "blessing: own creature");
    mine.mSeatPrison = &enemy;
    check(!SpellBlessing::isValidTarget(mine, &own), "blessing: a prisoner refused");
    mine.mSeatPrison = nullptr;
    mine.mDefinition = &moodless;
    check(!SpellBlessing::isValidTarget(mine, &own), "blessing: a kind without mood refused");
    mine.mDefinition = &fighter;
    Creature allied;
    allied.mDefinition = &fighter;
    allied.mSeat = &ally;
    check(!SpellBlessing::isValidTarget(allied, &own), "blessing: an allied creature refused");

    // Invisibility: an own living creature, not knocked out, not in a prison
    check(SpellInvisibility::isValidTarget(mine, &own), "invisibility: own creature");
    mine.mKo = true;
    check(!SpellInvisibility::isValidTarget(mine, &own), "invisibility: knocked out refused");
    mine.mKo = false;
    mine.mSeatPrison = &enemy;
    check(!SpellInvisibility::isValidTarget(mine, &own), "invisibility: a prisoner refused");
    mine.mSeatPrison = nullptr;
    check(!SpellInvisibility::isValidTarget(target, &own), "invisibility: an enemy refused");

    // Workers and the champion never get sick
    Creature sick;
    sick.mDefinition = &fighter;
    check(sick.canCatchPlague(), "a fighter can get sick");
    sick.mDefinition = &worker;
    check(!sick.canCatchPlague(), "a worker never gets sick");
    sick.mDefinition = &champion;
    check(!sick.canCatchPlague(), "the champion never gets sick");

    // Reveal Enemy: every tile claimed by the keeper, claimed ground, rooms and walls alike
    GameMap map;
    map.mTiles.assign(3, std::vector<Tile>(2));
    map.mTiles[0][0].mClaimed = true;
    map.mTiles[0][0].mSeat = &enemy;
    map.mTiles[2][1].mClaimed = true;
    map.mTiles[2][1].mSeat = &enemy;
    map.mTiles[1][1].mClaimed = true;
    map.mTiles[1][1].mSeat = &own;
    map.mTiles[1][0].mSeat = &enemy;
    std::vector<Tile*> shown = SpellRevealEnemy::getClaimedTiles(&map, &enemy);
    check(shown.size() == 2 && shown[0] == map.getTile(0, 0) && shown[1] == map.getTile(2, 1),
        "reveal: exactly the claimed tiles of the keeper");

    // Curse and blessing: the spread amount is the total over the turns, two casts stack, the mood stays in range
    Creature moody;
    moody.mDefinition = &fighter;
    moody.addMoodEffect("Curse", -300.0, 252.0);
    moody.addMoodEffect("Curse", -300.0, 252.0);
    check(moody.mMoodEffects.size() == 2, "two curses stack");
    near(moody.mMoodEffects[0].mStrength * moody.mMoodEffects[0].mTurnsLeft, -300.0, "the curse fall over its turns");
    moody.addMoodEffect("Blessing", 375.0, 252.0);
    near(moody.mMoodEffects[2].mStrength, 375.0 / 252.0, "the blessing rise per turn at research level 2");
    moody.mStoredMood = 1400.0;
    moody.changeStoredMood(250.0);
    near(moody.mStoredMood, 1500.0, "the mood never rises above the maximum");
    moody.changeStoredMood(-2000.0);
    near(moody.mStoredMood, 0.0, "the mood never falls below zero");
    Creature plain;
    plain.mDefinition = &moodless;
    plain.addMoodEffect("Curse", -300.0, 252.0);
    check(plain.mMoodEffects.empty(), "a kind without mood gets no mood effect");

    std::cout << "OK" << std::endl;
    return 0;
}
"""


def run_probe(name, code):
    """Builds and runs one self-contained probe with bounded child lifetimes; returns the build and run seconds."""
    with tempfile.TemporaryDirectory(prefix=name + "-") as directory:
        work = Path(directory)
        source, binary = work / "check.cpp", work / "check.exe"
        source.write_text(code, encoding="utf-8")
        start = time.monotonic()
        subprocess.run(["cl", "/nologo", "/EHsc", "/MD", "/std:c++17", str(source), "/Fe:" + str(binary)],
                       cwd=work, check=True, stdin=subprocess.DEVNULL, timeout=180)
        built = time.monotonic()
        subprocess.run([str(binary)], cwd=work, check=True, stdin=subprocess.DEVNULL, timeout=60)
        return built - start, time.monotonic() - built


build_seconds, run_seconds = run_probe("spells-review", PRELUDE + production() + CASES)
print("ODP_TEST_PHASE " + json.dumps({"name": "setup", "seconds": round(build_seconds, 3)}))
print("ODP_TEST_PHASE " + json.dumps({"name": "test", "seconds": round(run_seconds, 3)}))
print("spells review probe passed")
