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

//! \brief The suction of a caught ghost out of the trap on the cauldron's shelf into its suction nozzle (decision 936
//! point 4; for the closed cauldron the owner decisions of 2026-11-28): a smooth function of the transfer share, so a
//! share that grows every frame changes the look without jumps or stops. The ghost stays in the trap and is never shown
//! again. The trap's flaps open; then the content of the trap is drawn out of its opening straight up into the nozzle as
//! a glowing green stream, like a waterfall running upwards: its head shoots up into the nozzle, the stream grows
//! denser, thins out again and its tail leaves the trap and rises into the nozzle, so the trap is sucked empty; then the
//! flaps shut. The stream vanishes in the nozzle.
struct GhostTransferPath
{
    //! \brief The stream at a share: head and tail as shares (0 to 1) of the way from the trap's opening up into the
    //! nozzle, and how dense it is (0 to 1).
    struct Stream { double head; double tail; double density; };
    //! Shares over which the trap's lid opens at the start and shuts at the end of the transfer.
    static constexpr double LID_OPEN = 0.04;
    static constexpr double LID_SHUT = 0.93;
    //! Share at which the head of the stream, rising from the open trap from LID_OPEN on, is in the nozzle.
    static constexpr double STREAM_REACH = 0.1;
    //! Share from which the stream is at its densest.
    static constexpr double STREAM_DENSE = 0.35;
    //! Share from which the stream thins out again.
    static constexpr double STREAM_THIN = 0.7;
    //! Share from which the tail of the stream leaves the trap (the trap is empty).
    static constexpr double STREAM_EMPTY = 0.78;
    //! Share at which the tail is in the nozzle and the stream is gone, before the lid shuts.
    static constexpr double STREAM_GONE = 0.9;
    //! \brief The stream at a share (0 to 1): only while the lid is fully open, gone before it shuts.
    static Stream stream(double share);
    //! \brief How far the trap's lid is open (0 to 1) at a share: open before the stream starts, shut after it is gone.
    static double lid(double share);
    //! \brief Smooth step from 0 at a to 1 at b, with zero speed at both ends.
    static double ease(double a, double b, double t);
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
};
#endif
