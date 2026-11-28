#ifndef GHOSTENTITY_H
#define GHOSTENTITY_H

#include "entities/RenderedMovableEntity.h"
#include <set>

class Creature;

//! \brief The persisted capture and lifetime phase of a ghost.
enum class GhostState : uint32_t
{
    rising, floating, beamed, boxed, dissolving
};

//! \brief The path of a ghost drawn from the trap on the cauldron's shelf into its suction nozzle (decision 936 point 4,
//! owner decision of 2026-11-28 for the closed cauldron): a smooth function of the transfer share, so a share that grows
//! every frame moves the ghost without jumps or stops. The trap opens, the ghost rises straight up out of it at one even
//! rate in a narrow whirl that closes as it nears the nozzle, is drawn on into the nozzle and vanishes there; then the
//! trap shuts again.
struct GhostTransferPath
{
    //! \brief Position and visibility (0 to 1) of the ghost at a share.
    struct Point { Ogre::Vector3 position; double visible; };
    //! Radius in tiles of the whirl round the line from the trap to the nozzle (inside the nozzle's mouth of 0.12).
    static constexpr double RADIUS = 0.07;
    //! Turns of the whirl over the whole transfer.
    static constexpr double TURNS = 5.0;
    //! Share over which the whirl starts from rest.
    static constexpr double EASE_IN = 0.06;
    //! Share from which the whirl closes to the line, until the ghost is in the nozzle.
    static constexpr double CLOSE = 0.7;
    //! Share at which the ghost reaches the mouth of the nozzle.
    static constexpr double ARRIVE = 0.9;
    //! Tiles the ghost is drawn on up into the nozzle while it vanishes.
    static constexpr double SINK = 0.12;
    //! Shares over which the trap's lid opens at the start and shuts at the end of the transfer.
    static constexpr double LID_OPEN = 0.04;
    static constexpr double LID_SHUT = 0.93;
    //! \brief The point at a share (0 to 1) for the trap position and the middle of the nozzle's mouth.
    static Point at(double share, const Ogre::Vector3& trap, const Ogre::Vector3& mouth);
    //! \brief How far the trap's lid is open (0 to 1) at a share: open before the ghost leaves it, shut after it vanished.
    static double lid(double share);
    //! \brief Smooth step from 0 at a to 1 at b, with zero speed at both ends.
    static double ease(double a, double b, double t);
    //! \brief 0 to 1 from a to b at one constant speed, only the first and last `soft` share eased.
    static double even(double a, double b, double soft, double t);
};

//! \brief An untouchable spirit that floats over open terrain and frightens timid creatures.
class GhostEntity : public RenderedMovableEntity
{
public:
    //! \brief Creates an unpublished ghost with all corpse identity, seat and position fields set.
    GhostEntity(GameMap* map, const Creature& corpse);
    //! \brief Creates an unpublished ghost for stream or packet loading.
    explicit GhostEntity(GameMap* map);
    //! \brief Releases any remaining server-side presentation effect records.
    ~GhostEntity() override;
    //! \brief Registers through the existing movable path and restores saved movement endpoints.
    void addToGameMap(GameMap* map = nullptr) override;
    //! \brief Returns the synchronized ghost entity type.
    GameEntityType getObjectType() const override;
    //! \brief Advances lifetime, presentation phases, wandering and fear on the server.
    void doUpkeep() override;
    //! \brief Advances movement and the client fade without removing entities in a frame callback.
    void update(Ogre::Real elapsed) override;
    //! \brief Converts configured tiles per second to the movement system's tiles per turn.
    double getMoveSpeed() const override;
    //! \brief Plays the dead class's Walk at half its authored rate.
    double getAnimationSpeedFactor() const override;
    //! \brief Moves a released boxed ghost and synchronizes the authoritative position.
    void teleport(const Ogre::Vector3& position);
    //! \brief Returns the dead creature's class.
    const std::string& getClassName() const { return mClassName; }
    //! \brief Returns the corpse identity used for revival.
    const std::string& getCreatureName() const { return mCreatureName; }
    //! \brief Returns the whole level contributed to ectoplasm or revival.
    uint32_t getLevel() const { return mLevel; }
    //! \brief Returns the lifetime left in fractional turns.
    double getLifeLeft() const { return mLifeLeft; }
    //! \brief Returns the current lifetime and capture phase.
    GhostState getState() const { return mState; }
    //! \brief Sets capture state, stopping autonomous movement and hiding boxed ghosts.
    void setState(GhostState state);
    //! \brief Applies the hunter's client-only capture share (0 to 1 over the beam): the shrink to half size, then the
    //! pull down into the open thrown capture box.
    void setCaptureProgress(double progress) { mCaptureProgress = progress; }
    //! \brief Applies the hunter's client-only transfer share (0 to 1 over GhostTransferSeconds, decisions 845 and 865):
    //! the boxed ghost rises out of the delivery device beside the hunter (its position), glides over the rim to the
    //! middle of the cauldron's mouth (setTransferTarget), spirals down there and sinks into the ectoplasm; 0 keeps a
    //! boxed ghost hidden.
    void setTransferProgress(double progress) { mTransferProgress = progress; }
    //! \brief Sets the client-only middle of the ectoplasm in the cauldron's mouth the transferred ghost flows into
    //! (decision 865); without it the ghost spirals down at its own position.
    void setTransferTarget(const Ogre::Vector3& mouth) { mTransferTarget = mouth; mHasTransferTarget = true; }
    //! \brief Returns the name of the hunter that reserved this ghost.
    const std::string& getAssignedHunter() const { return mAssignedHunter; }
    //! \brief Stores or releases the hunter reservation.
    void setAssignedHunter(const std::string& name);
    //! \brief Writes the exact ghost record followed by persisted presentation and movement counters.
    void exportToStream(std::ostream& stream) const override;
    //! \brief Restores the exact ghost phase, lifetime and optional runtime continuation.
    bool importFromStream(std::istream& stream) override;
    //! \brief Sends all identity and presentation fields to newly observing clients.
    void exportToPacket(ODPacket& packet, const Seat* seat) const override;
    //! \brief Restores the complete creation packet.
    void importFromPacket(ODPacket& packet) override;
    //! \brief Sends current phase, lifetime and hunter reservation through entity refresh.
    void exportToPacketForUpdate(ODPacket& packet, Seat* seat) override;
    //! \brief Applies a phase refresh to the existing client entity.
    void updateFromPacket(ODPacket& packet) override;
    //! \brief Creates a validated ghost from one saved record.
    static GhostEntity* loadFromStream(GameMap* map, std::istream& stream);
    //! \brief Creates a ghost from an entity creation packet.
    static GhostEntity* loadFromPacket(GameMap* map, ODPacket& packet);
protected:
    //! \brief Creates the shrouded ghost mesh and restores its current ghost presentation.
    void createMeshLocal(NodeType type = NodeType::MTILES_NODE) override;
private:
    //! \brief Chooses a reachable non-full tile inside the configured Chebyshev square.
    void wander();
    //! \brief Scares eligible visible creatures once per flight.
    void scareCreatures();
    //! \brief Sends changed lifetime and state to current observers.
    void refresh();
    //! \brief Applies fade, rise, capture shrinking and boxed visibility to the client node.
    void updateLook();
    std::string mClassName;
    std::string mCreatureName;
    uint32_t mLevel;
    double mLifeLeft;
    GhostState mState;
    std::string mAssignedHunter;
    std::set<std::string> mScaredCreatures;
    double mStateTurns;
    double mHowlTurns;
    double mCaptureProgress = 0.0;
    double mTransferProgress = 0.0;
    Ogre::Vector3 mTransferTarget = Ogre::Vector3::ZERO;
    bool mHasTransferTarget = false;
};
#endif
