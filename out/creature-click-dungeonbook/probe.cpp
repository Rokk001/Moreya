
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

const float MIDDLE_CLICK_MAX_DRAG = 6.0f;
const float MIDDLE_CLICK_PICK_RADIUS = 0.7f;
const float MIDDLE_CLICK_BODY_HEIGHT = 0.4f;
const float MIDDLE_CLICK_REFERENCE_DISPLAY_HEIGHT = 1080.0f;
const int MIDDLE_CLICK_RAY_STEPS = 6;
const float MIDDLE_CLICK_RAY_STEP_HEIGHT = 0.25f;

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

Creature* GameMode::getDungeonbookCreature(GameEntity* entity) const
{
    if((entity == nullptr) || (entity->getObjectType() != GameEntityType::creature))
        return nullptr;

    Player* player = mGameMap->getLocalPlayer();
    if((player == nullptr) || (player->getSeat() == nullptr))
        return nullptr;

    // The same creatures the roster of the book holds: living creatures of the own or an allied keeper
    Creature* creature = static_cast<Creature*>(entity);
    const Seat* owner = creature->getSeat();
    if((owner == nullptr) || (owner->getPlayer() == nullptr) || !player->getSeat()->isAlliedSeat(owner))
        return nullptr;

    if(!creature->isAlive())
        return nullptr;

    return creature;
}
void GameMode::openDungeonbookOnCreature(Creature* creature)
{
    if(creature == nullptr)
        return;

    showSocialWindow(creature->getName());
}
void GameMode::openDungeonbookUnderPointer(const OIS::MouseEvent& arg)
{
    InputManager& inputManager = mModeManager->getInputManager();

    if(mGameMap->getGamePaused())
        return;

    // The pointer ray is checked against the bodies of the entities. Intersecting it with a plane at a fixed
    // height misses a creature that is clicked on its body, because the ray reaches that plane in front of it.
    if(mGameMap->getLocalPlayer() == nullptr)
        return;

    Ogre::Camera* camera = ODFrameListener::getSingleton().getCameraManager()->getActiveCamera();
    if(camera == nullptr)
        return;

    const CEGUI::Vector2f mouse = CEGUI::System::getSingleton().getDefaultGUIContext().getMouseCursor().getPosition();
    const Ogre::Ray ray = camera->getCameraToViewportRay(mouse.d_x / arg.state.width, mouse.d_y / arg.state.height);
    if(ray.getDirection().z >= 0)
        return;

    // The tiles the ray crosses between the floor and above the creatures
    std::vector<Tile*> tiles;
    for(int step = 0; step <= MIDDLE_CLICK_RAY_STEPS; ++step)
    {
        const float height = MIDDLE_CLICK_RAY_STEP_HEIGHT * static_cast<float>(step);
        const Ogre::Vector3 point = ray.getPoint((ray.getOrigin().z - height) / -ray.getDirection().z);
        Tile* tile = mGameMap->getTile(Helper::round(point.x), Helper::round(point.y));
        if((tile != nullptr) && (std::find(tiles.begin(), tiles.end(), tile) == tiles.end()))
            tiles.push_back(tile);
    }

    Creature* closestCreature = nullptr;
    float closestDist = MIDDLE_CLICK_PICK_RADIUS;
    for(Tile* tile : tiles)
    {
        std::vector<GameEntity*> entities;
        tile->fillWithEntities(entities, SelectionEntityWanted::any, mGameMap->getLocalPlayer());
        for(GameEntity* entity : entities)
        {
            Creature* creature = getDungeonbookCreature(entity);
            if(creature == nullptr)
                continue;

            Ogre::Vector3 body = creature->getPosition();
            body.z += MIDDLE_CLICK_BODY_HEIGHT;
            const float dist = ray.getDirection().crossProduct(body - ray.getOrigin()).length();
            if(dist >= closestDist)
                continue;

            closestDist = dist;
            closestCreature = creature;
        }
    }

    if(closestCreature != nullptr)
    {
        openDungeonbookOnCreature(closestCreature);
        return;
    }

    if(showTileDebugWindow)
    {
        Tile* tileClicked = mGameMap->getTile(inputManager.mXPos, inputManager.mYPos);
        if(tileClicked != nullptr)
            tileClicked->createStatsWindow();
    }
}
Creature* GameMode::getQueryTarget(Tile* tile) const
{
    if(tile == nullptr)
        return nullptr;

    const InputManager& inputManager = mModeManager->getInputManager();
    Player* player = mGameMap->getLocalPlayer();
    std::vector<GameEntity*> entities;
    tile->fillWithEntities(entities, SelectionEntityWanted::any, player);
    Creature* closest = nullptr;
    double distance = 0.0;
    for(GameEntity* entity : entities)
    {
        Creature* creature = getDungeonbookCreature(entity);
        if(creature == nullptr)
            continue;
        const Ogre::Vector3& position = creature->getPosition();
        const double candidate = Pathfinding::squaredDistance(position.x, inputManager.mKeeperHandPos.x,
            position.y, inputManager.mKeeperHandPos.y);
        if(closest == nullptr || candidate < distance)
        {
            closest = creature;
            distance = candidate;
        }
    }
    return closest;
}
void GameMode::handlePlayerActionQuery()
{
    const InputManager& inputManager = mModeManager->getInputManager();
    Creature* creature = getQueryTarget(mGameMap->getTile(inputManager.mXPos, inputManager.mYPos));
    if(creature == nullptr)
    {
        displayText(Ogre::ColourValue::Red, "Point at your own or an allied creature to view its information.");
        return;
    }

    displayText(Ogre::ColourValue::White, creature->getName());
    if(inputManager.mCommandState == InputCommandState::validated)
        openDungeonbookOnCreature(creature);
}
bool GameMode::selectInfirmaryPatient(const CEGUI::EventArgs&)
{
    CEGUI::MultiColumnList* list = static_cast<CEGUI::MultiColumnList*>(mRootWindow->getChild("RoomManagerWindow/Pages/InfirmaryPage/PatientList"));
    CEGUI::ListboxItem* item = list->getFirstSelectedItem();
    if(item == nullptr || item->getID() >= mInfirmaryPatientNames.size())
        return true;
    Creature* creature = mGameMap->getCreature(mInfirmaryPatientNames[item->getID()]);
    openDungeonbookOnCreature(getDungeonbookCreature(creature));
    return true;
}
void GameMode::showSocialWindow(const std::string& selectedCreature)
{
    if(mGameMap->getLocalPlayer() == nullptr)
        return;

    mSocialWindow->showCreature(selectedCreature);
}

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
