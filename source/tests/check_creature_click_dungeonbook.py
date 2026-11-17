"""T-D1: every way that shows a creature's information opens the Dungeonbook on that creature.

Requirement K19: the middle click on a creature, the query action and the patient list of the infirmary open the
Dungeonbook on the page of that creature; the old creature window (Creature::createStatsWindow,
gui/WindowCreatureProfile.layout) is removed; the right button keeps its functions (cancel the current
action, drop what the hand holds, slap the creature under the pointer when the hand is empty).

Two parts:
1. Source contracts (always run, compile nothing): the old window is gone, every entry point reaches the Dungeonbook
   through GameMode::openDungeonbookOnCreature, the Dungeonbook selects that creature and shows its page, and the right
   button branches of GameMode::mousePressed / mouseReleased still do their four jobs and never open the Dungeonbook.
2. Runtime probe (skipped with --source-only): the production bodies of getDungeonbookCreature,
   openDungeonbookOnCreature, openDungeonbookUnderPointer, getQueryTarget, handlePlayerActionQuery,
   selectInfirmaryPatient and showSocialWindow are compiled against a small world and clicked: own and allied creatures
   open the book on their own name, an enemy, a dead creature, a creature of a seat without a keeper and a non-creature
   open nothing; the middle click picks the own creature even when an enemy stands nearer to the pointer ray.
"""
from pathlib import Path
import re
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from item_probe_support import compile_and_run, function, source  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
started = time.perf_counter()


def block_after(text, marker):
    """Return the brace block that follows the first occurrence of marker, braces included."""
    start = text.index(marker)
    opening = text.index('{', start)
    depth, end = 1, opening + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[opening:end]


game = source('source/modes/GameMode.cpp')
game_header = source('source/modes/GameMode.h')
creature_cpp = source('source/entities/Creature.cpp')
creature_h = source('source/entities/Creature.h')
entity_h = source('source/entities/GameEntity.h')
editor = source('source/modes/EditorMode.cpp')
social = source('source/render/SocialWindow.cpp')
gui = source('source/render/Gui.cpp')
client = source('source/network/ODClient.cpp')

# 1a. The old creature window is removed: no layout, no window creation, no creature override that opens it
assert not (ROOT / 'gui/WindowCreatureProfile.layout').exists(), 'the old creature window layout is still there'
for text, name in ((gui, 'Gui.cpp'), (creature_cpp, 'Creature.cpp'), (creature_h, 'Creature.h'), (game, 'GameMode.cpp'),
                   (editor, 'EditorMode.cpp'), (client, 'ODClient.cpp')):
    for gone in ('createCreatureProfileWindow', 'WindowCreatureProfile.layout', 'CreatureStatsWindows_'):
        assert gone not in text, (name, gone)
for gone in ('createStatsWindow', 'updateStatsWindow', 'destroyStatsWindow', 'mStatsWindow', 'canDisplayStatsWindow'):
    assert gone not in creature_h and gone not in creature_cpp, 'Creature still has ' + gone
assert 'canDisplayStatsWindow' not in entity_h, 'no entity offers the old stats window any more'
assert 'creature->updateStatsWindow' not in client, 'the client no longer feeds an old creature window'
# The only stats window left is the tile debug window; nothing calls createStatsWindow on a creature
for text, name in ((game, 'GameMode.cpp'), (editor, 'EditorMode.cpp')):
    calls = re.findall(r'(\w+)->createStatsWindow\(\)', text)
    assert all(call == 'tileClicked' for call in calls), (name, calls)

# 1b. Every entry point opens the Dungeonbook on its creature through one function
open_fn = function(game, 'void GameMode::openDungeonbookOnCreature(')
assert 'showSocialWindow(creature->getName())' in open_fn, 'the book opens on the clicked creature'
show_fn = function(game, 'void GameMode::showSocialWindow(')
assert 'mSocialWindow->showCreature(selectedCreature)' in show_fn
show_creature = function(social, 'void SocialWindow::showCreature(')
assert 'mSelectedCreature = creatureName;' in show_creature and 'mPage = Page::Inventory;' in show_creature
assert show_creature.index('mSelectedCreature = creatureName;') < show_creature.index('show();')
show = function(social, 'void SocialWindow::show()')
assert 'showPage(mSelectedCreature.empty() ? Page::Home : mPage);' in show, 'the book opens on the selected creature'

# Middle click: a released middle click that did not move picks along the pointer ray and opens the book
released = function(game, 'bool GameMode::mouseReleased(')
middle = block_after(released, 'if(id == OIS::MB_Middle)')
assert 'openDungeonbookUnderPointer(arg)' in middle and 'isClick' in middle, 'the middle click opens the Dungeonbook'
pick = function(game, 'void GameMode::openDungeonbookUnderPointer(')
assert 'getDungeonbookCreature(entity)' in pick and 'openDungeonbookOnCreature(closestCreature)' in pick
assert 'getCameraToViewportRay' in pick and 'findWorldPositionFromMouse' not in pick
# Query action: the validated click opens the book on the queried creature
query = function(game, 'void GameMode::handlePlayerActionQuery(')
assert 'getQueryTarget(' in query and 'openDungeonbookOnCreature(creature)' in query
assert 'InputCommandState::validated' in query
target = function(game, 'Creature* GameMode::getQueryTarget(')
assert 'getDungeonbookCreature(entity)' in target
# Infirmary patient list: a selected patient opens the book on that patient
patient = function(game, 'bool GameMode::selectInfirmaryPatient(')
assert 'openDungeonbookOnCreature(getDungeonbookCreature(creature))' in patient
assert re.search(r'CEGUI::MultiColumnList\* patients = [^;]*InfirmaryPage/PatientList"\)\);(?:[^;]*;){0,6}?\s*'
                 r'addEventConnection\(patients->subscribeEvent\(CEGUI::Window::EventMouseClick,\s*'
                 r'CEGUI::Event::Subscriber\(&GameMode::selectInfirmaryPatient, this\)\)\);', game), \
    'a click on the patient list opens the selected patient'
# The book shows the creatures of its roster: the own and allied keepers' living creatures (ODServer roster)
roster = source('source/network/ODServer.cpp')
roster = roster[roster.index('void notifyDungeonbookRoster('):]
roster = roster[:roster.index('ServerNotificationType::dungeonbookRoster')]
assert 'owner->getPlayer() != nullptr && seat->isAlliedSeat(owner) && creature->isAlive()' in roster
book_creature = function(game, 'Creature* GameMode::getDungeonbookCreature(')
for fragment in ('GameEntityType::creature', 'owner->getPlayer() == nullptr', 'isAlliedSeat(owner)', 'isAlive()'):
    assert fragment in book_creature, fragment
# The editor has no Dungeonbook; its middle button opens nothing
editor_pressed = function(editor, 'bool EditorMode::mousePressed(')
editor_middle = block_after(editor_pressed, 'if (id == OIS::MB_Middle)')
assert 'createStatsWindow' not in editor_middle and 'return true;' in editor_middle
# The query outlines exactly the creatures it can open
selection = source('source/game/PlayerSelection.cpp')
set_action = function(selection, 'void PlayerSelection::setCurrentAction(')
assert 'creatureAliveOrDead' not in set_action and 'SelectionEntityWanted::creatureAliveAllied' in set_action

# 1c. The right button keeps its functions and never opens the Dungeonbook
pressed = function(game, 'bool GameMode::mousePressed(')
possession = block_after(pressed, 'if (isLocalPlayerPossessing())')
# Possession (owner decision of the possession rework): only Esc leaves the creature, the right button does nothing
assert 'sendPossessionExit' not in possession, 'the right button does not leave possession'
key_pressed = function(game, 'bool GameMode::keyPressedNormal(')
assert 'isLocalPlayerPossessing() && handlePossessionKey(arg.key, true)' in key_pressed, 'possession keys come first'
possession_key = function(game, 'bool GameMode::handlePossessionKey(')
assert re.search(r'case OIS::KC_ESCAPE:\s*if \(pressed\)\s*sendPossessionExit\(\);\s*return true;', possession_key), \
    'Esc leaves possession'
cancel = block_after(pressed, 'if(id == OIS::MB_Right && mPlayerSelection.getCurrentAction() != SelectedAction::none)')
assert 'mPlayerSelection.setCurrentAction(SelectedAction::none);' in cancel, 'right button cancels the current action'
right = block_after(pressed, '    if (id == OIS::MB_Right)\n    {')
assert 'numObjectsInHand() > 0' in right and 'mPendingHandDrop = true;' in right, 'right button drops what the hand holds'
assert 'canSlap(' in right and 'ClientNotificationType::askSlapEntity' in right, 'right button slaps when the hand is empty'
right_up = block_after(released, 'if (id == OIS::MB_Right)')
assert 'sendPendingHandDropRequest(false);' in right_up, 'the held drop is sent on release'
for name, block in (('possession', possession), ('cancel', cancel), ('right press', right), ('right release', right_up)):
    for opener in ('openDungeonbook', 'showSocialWindow', 'createStatsWindow'):
        assert opener not in block, (name, opener)
# The middle press returns before the right-button branch, so the two never mix
assert pressed.index('if (id == OIS::MB_Middle)\n        return true;') < pressed.index('    if (id == OIS::MB_Right)\n    {')
print('source contracts ok: old window removed; middle click, query and patient list open the Dungeonbook; '
      'Esc leaves possession; right button keeps cancel, drop and slap')

if '--source-only' in sys.argv:
    print('runtime probe skipped (--source-only)')
    print('ODP_TEST_PHASE {"name":"source","seconds":%.3f}' % (time.perf_counter() - started))
    sys.exit(0)

constants = '\n'.join(re.findall(r'^const (?:float|int) MIDDLE_CLICK_\w+ = [^;]+;', game, re.M))
assert 'MIDDLE_CLICK_PICK_RADIUS' in constants and 'MIDDLE_CLICK_RAY_STEPS' in constants
production = '\n'.join(function(game, signature) for signature in (
    'Creature* GameMode::getDungeonbookCreature(', 'void GameMode::openDungeonbookOnCreature(',
    'void GameMode::openDungeonbookUnderPointer(', 'Creature* GameMode::getQueryTarget(',
    'void GameMode::handlePlayerActionQuery(', 'bool GameMode::selectInfirmaryPatient(', 'void GameMode::showSocialWindow('))

probe = r'''
#include <algorithm>
#include <cmath>
#include <iostream>
#include <map>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace Ogre
{
//! \brief A world position or direction.
struct Vector3
{
    float x, y, z;
    //! \brief Difference of two positions.
    Vector3 operator-(const Vector3& other) const { Vector3 result = {x - other.x, y - other.y, z - other.z}; return result; }
    //! \brief Cross product, used for the distance of a body to the pointer ray.
    Vector3 crossProduct(const Vector3& o) const { Vector3 result = {y * o.z - z * o.y, z * o.x - x * o.z, x * o.y - y * o.x}; return result; }
    //! \brief Euclidean length.
    float length() const { return std::sqrt(x * x + y * y + z * z); }
};
//! \brief A pointer ray with a unit direction.
struct Ray
{
    Vector3 mOrigin, mDirection;
    //! \brief Start of the ray at the camera.
    const Vector3& getOrigin() const { return mOrigin; }
    //! \brief Unit direction of the ray.
    const Vector3& getDirection() const { return mDirection; }
    //! \brief The point at the given distance along the ray.
    Vector3 getPoint(float t) const { Vector3 result = {mOrigin.x + mDirection.x * t, mOrigin.y + mDirection.y * t, mOrigin.z + mDirection.z * t}; return result; }
};
//! \brief The game camera; it returns the ray the test aims.
struct Camera
{
    Ray mRay;
    //! \brief The ray through the pointer.
    Ray getCameraToViewportRay(float, float) const { return mRay; }
};
//! \brief A text colour, told apart by its code.
struct ColourValue
{
    int mCode;
    static const ColourValue Red;
    static const ColourValue White;
};
const ColourValue ColourValue::Red = {1};
const ColourValue ColourValue::White = {2};
}

namespace OIS
{
//! \brief Size of the render window.
struct MouseState { int width, height; };
//! \brief A mouse event with the window size.
struct MouseEvent { MouseState state; };
}

namespace CEGUI
{
//! \brief A pointer position in pixels.
struct Vector2f { float d_x, d_y; };
//! \brief The mouse cursor of the GUI.
struct MouseCursor
{
    Vector2f mPosition;
    //! \brief Pointer position.
    Vector2f getPosition() const { return mPosition; }
};
//! \brief The GUI context that owns the cursor.
struct GUIContext
{
    MouseCursor mCursor;
    //! \brief The cursor of this context.
    MouseCursor& getMouseCursor() { return mCursor; }
};
//! \brief The GUI system singleton.
struct System
{
    GUIContext mContext;
    //! \brief The one GUI system of the probe.
    static System& getSingleton() { static System system; return system; }
    //! \brief The default GUI context.
    GUIContext& getDefaultGUIContext() { return mContext; }
};
//! \brief Arguments of a GUI event.
struct EventArgs {};
//! \brief A row of a list.
struct ListboxItem
{
    unsigned int mId;
    //! \brief Row number.
    unsigned int getID() const { return mId; }
};
//! \brief A GUI window with named children.
struct Window
{
    std::map<std::string, Window*> mChildren;
    //! \brief Allows lists to derive from windows.
    virtual ~Window() {}
    //! \brief The child at the path; the probe registers every path it uses.
    Window* getChild(const std::string& path) { return mChildren.at(path); }
};
//! \brief The patient list of the infirmary page.
struct MultiColumnList : public Window
{
    ListboxItem* mSelected = nullptr;
    //! \brief The selected row or null.
    ListboxItem* getFirstSelectedItem() { return mSelected; }
};
}

namespace Helper
{
//! \brief Rounds a coordinate to the tile index.
int round(double value) { return static_cast<int>(std::floor(value + 0.5)); }
}

namespace Pathfinding
{
//! \brief Squared distance of two points given as x1, x2, y1, y2.
double squaredDistance(double x1, double x2, double y1, double y2) { return (x1 - x2) * (x1 - x2) + (y1 - y2) * (y1 - y2); }
}

enum class GameEntityType { creature, chicken };
enum class SelectionEntityWanted { any };
enum class InputCommandState { infoOnly, validated };

struct Player;
//! \brief A seat with its team and keeper.
struct Seat
{
    int mTeam;
    Player* mPlayer;
    //! \brief Same team means allied (production Seat::isAlliedSeat).
    bool isAlliedSeat(const Seat* seat) const { return mTeam == seat->mTeam; }
    //! \brief The keeper of the seat, null for a seat without one.
    Player* getPlayer() const { return mPlayer; }
};
//! \brief A keeper on a seat.
struct Player
{
    Seat* mSeat;
    //! \brief The seat of the keeper.
    Seat* getSeat() const { return mSeat; }
};
//! \brief Something standing on a tile.
struct GameEntity
{
    GameEntityType mType;
    std::string mName;
    Seat* mSeat;
    Ogre::Vector3 mPosition;
    //! \brief Allows creatures to derive from entities.
    virtual ~GameEntity() {}
    //! \brief Kind of the entity.
    GameEntityType getObjectType() const { return mType; }
    //! \brief Internal name.
    const std::string& getName() const { return mName; }
    //! \brief Owning seat.
    Seat* getSeat() const { return mSeat; }
    //! \brief World position (feet).
    const Ogre::Vector3& getPosition() const { return mPosition; }
};
//! \brief A creature, alive or dead.
struct Creature : public GameEntity
{
    bool mAlive;
    //! \brief True while the creature lives.
    bool isAlive() const { return mAlive; }
};
//! \brief A map tile with the entities on it and its debug window.
struct Tile
{
    std::vector<GameEntity*> mEntities;
    int mDebugWindows = 0;
    //! \brief Lists the entities on the tile.
    void fillWithEntities(std::vector<GameEntity*>& entities, SelectionEntityWanted, Player*) { entities = mEntities; }
    //! \brief Opens the tile debug window.
    void createStatsWindow() { ++mDebugWindows; }
};
//! \brief The client map of the probe.
struct GameMap
{
    bool mPaused = false;
    Player* mLocalPlayer = nullptr;
    std::map<std::pair<int, int>, Tile*> mTiles;
    std::map<std::string, Creature*> mCreatures;
    //! \brief True while the game is paused.
    bool getGamePaused() const { return mPaused; }
    //! \brief The keeper of this client.
    Player* getLocalPlayer() const { return mLocalPlayer; }
    //! \brief The tile at x, y or null outside the map.
    Tile* getTile(int x, int y) const { std::map<std::pair<int, int>, Tile*>::const_iterator it = mTiles.find(std::make_pair(x, y)); return it == mTiles.end() ? nullptr : it->second; }
    //! \brief The creature with that name or null.
    Creature* getCreature(const std::string& name) const { std::map<std::string, Creature*>::const_iterator it = mCreatures.find(name); return it == mCreatures.end() ? nullptr : it->second; }
};
//! \brief Pointer tile, keeper hand and command state.
struct InputManager
{
    int mXPos = -1, mYPos = -1;
    Ogre::Vector3 mKeeperHandPos = {0.0f, 0.0f, 0.0f};
    InputCommandState mCommandState = InputCommandState::infoOnly;
};
//! \brief Owner of the input manager.
struct ModeManager
{
    InputManager mInput;
    //! \brief The input manager.
    InputManager& getInputManager() { return mInput; }
};
//! \brief The camera manager with the active camera.
struct CameraManager
{
    Ogre::Camera* mCamera = nullptr;
    //! \brief The camera the player looks through.
    Ogre::Camera* getActiveCamera() { return mCamera; }
};
//! \brief The frame listener singleton that owns the camera manager.
struct ODFrameListener
{
    CameraManager mCameras;
    //! \brief The one frame listener of the probe.
    static ODFrameListener& getSingleton() { static ODFrameListener listener; return listener; }
    //! \brief The camera manager.
    CameraManager* getCameraManager() { return &mCameras; }
};
//! \brief The Dungeonbook; records on which creature it was opened.
struct SocialWindow
{
    std::vector<std::string> mOpened;
    //! \brief Opens the book on the creature's page.
    void showCreature(const std::string& creatureName) { mOpened.push_back(creatureName); }
};

@CONSTANTS@

//! \brief The game mode members the production entry points use.
class GameMode
{
public:
    GameMap* mGameMap = nullptr;
    ModeManager* mModeManager = nullptr;
    SocialWindow* mSocialWindow = nullptr;
    CEGUI::Window* mRootWindow = nullptr;
    std::vector<std::string> mInfirmaryPatientNames;
    bool showTileDebugWindow = false;
    std::vector<std::pair<int, std::string> > mTexts;
    //! \brief Records a pointer text with its colour.
    void displayText(const Ogre::ColourValue& colour, const std::string& text) { mTexts.push_back(std::make_pair(colour.mCode, text)); }
    Creature* getDungeonbookCreature(GameEntity* entity) const;
    void openDungeonbookOnCreature(Creature* creature);
    void openDungeonbookUnderPointer(const OIS::MouseEvent& arg);
    Creature* getQueryTarget(Tile* tile) const;
    void handlePlayerActionQuery();
    bool selectInfirmaryPatient(const CEGUI::EventArgs&);
    void showSocialWindow(const std::string& selectedCreature);
};

@PRODUCTION@

//! \brief Fails the probe with the name of the broken case.
void check(bool valid, const std::string& label)
{
    if(!valid)
        throw std::runtime_error(label);
}

//! \brief Builds a creature standing at x, y.
Creature makeCreature(const std::string& name, Seat* seat, float x, float y, bool alive)
{
    Creature creature;
    creature.mType = GameEntityType::creature;
    creature.mName = name;
    creature.mSeat = seat;
    creature.mPosition.x = x;
    creature.mPosition.y = y;
    creature.mPosition.z = 0.0f;
    creature.mAlive = alive;
    return creature;
}

//! \brief Clicks every entry point and checks on which creature the Dungeonbook opens.
int main()
{
    try
    {
        Seat own = {1, nullptr}, ally = {1, nullptr}, foe = {2, nullptr}, keeperless = {1, nullptr};
        Player me = {&own}, friendKeeper = {&ally}, enemy = {&foe};
        own.mPlayer = &me;
        ally.mPlayer = &friendKeeper;
        foe.mPlayer = &enemy;
        const float beside = MIDDLE_CLICK_PICK_RADIUS * 0.5f;
        Creature ownCreature = makeCreature("Own", &own, 2.0f + beside, 3.0f, true);
        Creature allyCreature = makeCreature("Ally", &ally, 5.0f, 5.0f, true);
        Creature foeCreature = makeCreature("Foe", &foe, 2.0f, 3.0f, true);
        Creature deadCreature = makeCreature("Dead", &own, 7.0f, 7.0f, false);
        Creature roamingCreature = makeCreature("Roaming", &keeperless, 8.0f, 8.0f, true);
        GameEntity chicken;
        chicken.mType = GameEntityType::chicken;
        chicken.mName = "Chicken";
        chicken.mSeat = &own;
        chicken.mPosition = foeCreature.mPosition;

        Tile mixed, allyTile, foeTile, deadTile, roamingTile;
        mixed.mEntities.push_back(&chicken);
        mixed.mEntities.push_back(&foeCreature);
        mixed.mEntities.push_back(&ownCreature);
        allyTile.mEntities.push_back(&allyCreature);
        foeTile.mEntities.push_back(&foeCreature);
        deadTile.mEntities.push_back(&deadCreature);
        roamingTile.mEntities.push_back(&roamingCreature);

        GameMap map;
        map.mLocalPlayer = &me;
        map.mTiles[std::make_pair(2, 3)] = &mixed;
        map.mTiles[std::make_pair(5, 5)] = &allyTile;
        map.mTiles[std::make_pair(6, 6)] = &foeTile;
        map.mTiles[std::make_pair(7, 7)] = &deadTile;
        map.mTiles[std::make_pair(8, 8)] = &roamingTile;
        map.mCreatures["Own"] = &ownCreature;
        map.mCreatures["Foe"] = &foeCreature;

        ModeManager modes;
        SocialWindow book;
        CEGUI::Window root;
        CEGUI::MultiColumnList patients;
        root.mChildren["RoomManagerWindow/Pages/InfirmaryPage/PatientList"] = &patients;
        GameMode mode;
        mode.mGameMap = &map;
        mode.mModeManager = &modes;
        mode.mSocialWindow = &book;
        mode.mRootWindow = &root;

        // Which entities the book can show
        check(mode.getDungeonbookCreature(&ownCreature) == &ownCreature, "own creature is in the book");
        check(mode.getDungeonbookCreature(&allyCreature) == &allyCreature, "allied creature is in the book");
        check(mode.getDungeonbookCreature(&foeCreature) == nullptr, "enemy creature is not in the book");
        check(mode.getDungeonbookCreature(&deadCreature) == nullptr, "dead creature is not in the book");
        check(mode.getDungeonbookCreature(&roamingCreature) == nullptr, "creature of a seat without keeper is not in the book");
        check(mode.getDungeonbookCreature(&chicken) == nullptr, "a chicken is not in the book");
        check(mode.getDungeonbookCreature(nullptr) == nullptr, "nothing is not in the book");

        // Middle click straight down on the mixed tile: the enemy and the chicken lie on the ray, the own creature
        // half the pick radius beside it; the book opens on the own creature
        Ogre::Camera camera;
        camera.mRay.mOrigin.x = 2.0f; camera.mRay.mOrigin.y = 3.0f; camera.mRay.mOrigin.z = 10.0f;
        camera.mRay.mDirection.x = 0.0f; camera.mRay.mDirection.y = 0.0f; camera.mRay.mDirection.z = -1.0f;
        ODFrameListener::getSingleton().mCameras.mCamera = &camera;
        CEGUI::System::getSingleton().mContext.mCursor.mPosition.d_x = 400.0f;
        CEGUI::System::getSingleton().mContext.mCursor.mPosition.d_y = 300.0f;
        OIS::MouseEvent click = {{800, 600}};
        mode.openDungeonbookUnderPointer(click);
        check(book.mOpened == std::vector<std::string>(1, "Own"), "middle click opens the book on the own creature");

        // Middle click on an allied creature opens the book on it
        book.mOpened.clear();
        camera.mRay.mOrigin.x = 5.0f; camera.mRay.mOrigin.y = 5.0f;
        mode.openDungeonbookUnderPointer(click);
        check(book.mOpened == std::vector<std::string>(1, "Ally"), "middle click opens the book on the allied creature");

        // Middle click on an enemy, a dead creature or a keeperless creature opens nothing (no window at all)
        const float targets[][2] = {{6.0f, 6.0f}, {7.0f, 7.0f}, {8.0f, 8.0f}};
        for(const float* aim : targets)
        {
            book.mOpened.clear();
            camera.mRay.mOrigin.x = aim[0]; camera.mRay.mOrigin.y = aim[1];
            modes.mInput.mXPos = static_cast<int>(aim[0]);
            modes.mInput.mYPos = static_cast<int>(aim[1]);
            mode.openDungeonbookUnderPointer(click);
            check(book.mOpened.empty(), "middle click on a creature outside the book opens nothing");
        }
        check(foeTile.mDebugWindows == 0 && deadTile.mDebugWindows == 0, "no tile window without the debug switch");

        // A paused game opens nothing
        book.mOpened.clear();
        camera.mRay.mOrigin.x = 2.0f; camera.mRay.mOrigin.y = 3.0f;
        map.mPaused = true;
        mode.openDungeonbookUnderPointer(click);
        map.mPaused = false;
        check(book.mOpened.empty(), "middle click while paused opens nothing");

        // Query action: while pointing it names the creature, the validated click opens the book on it
        book.mOpened.clear();
        modes.mInput.mXPos = 2;
        modes.mInput.mYPos = 3;
        modes.mInput.mKeeperHandPos = foeCreature.mPosition;
        modes.mInput.mCommandState = InputCommandState::infoOnly;
        mode.handlePlayerActionQuery();
        check(book.mOpened.empty() && !mode.mTexts.empty() && mode.mTexts.back().first == Ogre::ColourValue::White.mCode &&
              mode.mTexts.back().second == "Own", "query names the own creature before the click");
        modes.mInput.mCommandState = InputCommandState::validated;
        mode.handlePlayerActionQuery();
        check(book.mOpened == std::vector<std::string>(1, "Own"), "query click opens the book on the own creature");
        book.mOpened.clear();
        modes.mInput.mXPos = 6;
        modes.mInput.mYPos = 6;
        mode.handlePlayerActionQuery();
        check(book.mOpened.empty() && mode.mTexts.back().first == Ogre::ColourValue::Red.mCode,
              "query on an enemy opens nothing and says why");

        // Infirmary patient list: the selected patient opens the book on it, no selection opens nothing
        book.mOpened.clear();
        mode.mInfirmaryPatientNames.push_back("Own");
        CEGUI::EventArgs args;
        mode.selectInfirmaryPatient(args);
        check(book.mOpened.empty(), "no selected patient opens nothing");
        CEGUI::ListboxItem row = {0};
        patients.mSelected = &row;
        mode.selectInfirmaryPatient(args);
        check(book.mOpened == std::vector<std::string>(1, "Own"), "patient list opens the book on the patient");

        // Without a local keeper the book stays closed
        book.mOpened.clear();
        mode.showSocialWindow("Own");
        map.mLocalPlayer = nullptr;
        mode.showSocialWindow("Own");
        check(book.mOpened == std::vector<std::string>(1, "Own"), "the book needs a local keeper");
    }
    catch(const std::exception& error)
    {
        std::cerr << "FAIL: " << error.what() << std::endl;
        return 1;
    }
    std::cout << "creature click probe ok: middle click, query and patient list open the Dungeonbook on own and allied "
              << "creatures only" << std::endl;
    return 0;
}
'''.replace('@CONSTANTS@', constants).replace('@PRODUCTION@', production)

print('ODP_TEST_PHASE {"name":"source","seconds":%.3f}' % (time.perf_counter() - started))
compile_and_run('creature-click-dungeonbook', probe)
print('creature click Dungeonbook check ok')
