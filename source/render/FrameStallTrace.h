#ifndef FRAMESTALLTRACE_H
#define FRAMESTALLTRACE_H

#include <array>
#include <cstdint>
#include <string>

//! \brief Attributes slow S3 frame intervals to exclusive render-thread operations.
class FrameStallTrace
{
public:
    //! \brief Fixed buckets avoid allocations and logging on ordinary phase transitions.
    enum Phase
    {
        Uninstrumented, Statistics, FrameStarted, RenderTargets, FrameQueued, Limiter,
        GuiPulse, ModeUpdate, Animations, CameraAudio, SocketMessages, Notifications,
        Present, FrameEnded, EventPump, GuiRender, MiniMap, CreatureCreate,
        ResourcePreparation, MaterialPreparation, Message, LogWrite, TerrainRebuild, Count
    };

    //! \brief Times a nested operation and restores its parent even on early return or exception.
    class Scope
    {
    public:
        //! \brief Starts one named operation; context must outlive this scope.
        Scope(Phase phase, const char* context = "");
        //! \brief Records the longest operation and resumes exclusive timing of its parent.
        ~Scope();
    private:
        Scope(const Scope&) = delete;
        Scope& operator=(const Scope&) = delete;
        Phase mPrevious;
        Phase mPhase;
        const char* mContext;
        double mStart;
        std::uint64_t mFrame;
    };

    //! \brief Keeps server threads and their logging outside the render-thread evidence.
    static FrameStallTrace& get();
    //! \brief Closes exactly the preceding S3 interval before starting another, including startup.
    void beginFrame(double time, bool inGame, std::int64_t turn, bool active);
    //! \brief Assigns elapsed time to the previous phase and changes the current phase.
    void setPhase(Phase phase);

private:
    //! \brief Uses the same monotonic clock as the permanent frame statistics.
    static double now();
    //! \brief Maps fixed phases to stable operation names in the permanent log.
    static const char* name(Phase phase);
    std::array<double, Count> mSeconds = {};
    Phase mPhase = Uninstrumented;
    std::array<double, Count> mMaxInclusive = {};
    std::array<std::string, Count> mContexts;
    double mStart = 0.0;
    double mLast = 0.0;
    std::uint64_t mFrame = 0;
    std::int64_t mTurn = -1;
    bool mInGame = false;
    bool mActive = false;
};

#endif // FRAMESTALLTRACE_H
