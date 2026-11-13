#include "render/FrameStatistics.h"
#include "render/FrameStallTrace.h"

#include "utils/LogManager.h"

#include <iomanip>
#include <sstream>

//! \brief Separates renderer timing from any work performed by the server thread.
FrameStallTrace& FrameStallTrace::get()
{
    static thread_local FrameStallTrace trace;
    return trace;
}

//! \brief Reads the unsmoothed S3 monotonic clock.
double FrameStallTrace::now()
{
    return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count();
}

//! \brief Uses stable names; broad engine buckets explicitly retain unresolved inner causes.
const char* FrameStallTrace::name(Phase phase)
{
    static const char* const names[Count] = {
        "uninstrumented", "statistics-and-diagnostic-log", "frameStarted", "Ogre-render-targets-unresolved",
        "frameRenderingQueued", "frame-limiter-wait", "CEGUI-time-pulse", "mode-and-input-update",
        "world-animations", "camera-audio-observers", "socket-dispatch", "client-notifications",
        "Ogre-present-unresolved", "frameEnded", "event-pump-unresolved", "CEGUI-render",
        "minimap-update-upload", "creature-create", "game-resource-preparation", "material-preparation",
        "server-message", "log-write-mutex-and-sinks", "terrain-batch-rebuild"
    };
    return names[phase];
}

//! \brief Charges only the current leaf operation, so nested work is never counted twice.
void FrameStallTrace::setPhase(Phase phase)
{
    const double time = now();
    if(mFrame != 0)
        mSeconds[mPhase] += time - mLast;
    mLast = time;
    mPhase = phase;
}

//! \brief Preserves the full preceding interval and records diagnostic I/O in the next interval.
void FrameStallTrace::beginFrame(double time, bool inGame, std::int64_t turn, bool active)
{
    if(mFrame != 0)
        mSeconds[mPhase] += time - mLast;
    const double seconds = mFrame == 0 ? 0.0 : time - mStart;
    std::string report;
    if(seconds > 0.100)
    {
        Phase dominant = Uninstrumented;
        for(int phase = 1; phase < Count; ++phase)
        {
            if(mSeconds[phase] > mSeconds[dominant])
                dominant = static_cast<Phase>(phase);
        }
        std::ostringstream line;
        line << std::fixed << std::setprecision(2) << "Frame stall: frame=" << mFrame
            << " inGame=" << mInGame << " turn=" << mTurn << " windowActive=" << mActive
            << " intervalMs=" << seconds * 1000.0 << " dominantPhase=" << name(dominant)
            << " exclusiveMs=";
        for(int phase = 0; phase < Count; ++phase)
        {
            if(mSeconds[phase] > 0.0)
                line << name(static_cast<Phase>(phase)) << ':' << mSeconds[phase] * 1000.0 << ',';
        }
        for(int phase = 0; phase < Count; ++phase)
        {
            if(mMaxInclusive[phase] > 0.0)
                line << " operation=" << name(static_cast<Phase>(phase))
                    << " context=" << mContexts[phase] << " maxInclusiveMs=" << mMaxInclusive[phase] * 1000.0;
        }
        // This identifies wall time inside an operation, not CPU time or a proven driver/OS root cause.
        // Engine/present/event gaps remain explicitly unresolved until finer evidence exists.
        report = line.str();
    }
    // Keep the original boundary: formatting and writing this report belong to the next S3 frame.
    mSeconds.fill(0.0);
    mPhase = Statistics;
    mLast = time;
    mStart = time;
    ++mFrame;
    mInGame = inGame;
    mTurn = turn;
    mActive = active;
    mMaxInclusive.fill(0.0);
    for(std::string& context : mContexts)
        context.clear();
    if(!report.empty())
        OD_LOG_INF(report);
}

//! \brief Enters a nested operation without allocating a per-frame event list.
FrameStallTrace::Scope::Scope(Phase phase, const char* context) :
    mPrevious(get().mPhase), mPhase(phase), mContext(context), mStart(now()), mFrame(get().mFrame)
{
    get().setPhase(phase);
}

//! \brief Restores parent accounting and retains the slowest completed operation's identity.
FrameStallTrace::Scope::~Scope()
{
    FrameStallTrace& trace = get();
    const double seconds = now() - mStart;
    if(mFrame != 0 && mFrame == trace.mFrame && seconds > trace.mMaxInclusive[mPhase])
    {
        trace.mMaxInclusive[mPhase] = seconds;
        trace.mContexts[mPhase] = mContext;
    }
    trace.setPhase(mPrevious);
}

//! \brief Uses a monotonic clock rather than Ogre's smoothed animation delta.
double FrameStatistics::now()
{
    return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count();
}

//! \brief Emits a permanent statistics line, including empty intervals crossed by a long stall.
void FrameStatistics::log(const char* label, const MenuFlightFrameStats& frames)
{
    std::ostringstream line;
    line << std::fixed << std::setprecision(2) << label << ": frames=" << frames.getFrames()
        << " meanMs=" << frames.getMeanMilliseconds()
        << " p95Ms=" << frames.getP95Milliseconds()
        << " maxMs=" << frames.getMaxMilliseconds()
        << " framesOver33Ms=" << frames.getSlowFrames();
    OD_LOG_INF(line.str());
}

//! \brief Keeps pointer intervals separate while allowing them to overlap a drag or game minute.
void FrameStatistics::pointerMoved(int x, int y, PointerArea area)
{
    if(mHavePosition && x == mX && y == mY)
        return;
    mHavePosition = true;
    mX = x;
    mY = y;
    // Any real movement, also outside a window, extends an active line: it ends
    // only after one second without movement, not when the hand leaves its area.
    const double time = now();
    extendMovement(mMenuMovement, "Menu hand movement", time);
    extendMovement(mWindowMovement, "Game window hand movement", time);
    if(area == Outside)
        return;
    Movement& movement = area == Menu ? mMenuMovement : mWindowMovement;
    movement.mActive = true;
    movement.mLastMovement = time;
}

//! \brief Queues a line ended by a one-second pause, otherwise moves its pause start to this movement.
void FrameStatistics::extendMovement(Movement& movement, const char* label, double time)
{
    if(!movement.mActive)
        return;
    if(time - movement.mLastMovement >= 1.0)
    {
        mCompleted.push_back(Completed{label, movement.mFrames});
        movement.mFrames.reset();
        movement.mActive = false;
        return;
    }
    movement.mLastMovement = time;
}

//! \brief Starts only accepted drags; ordinary button presses do not produce drag lines.
void FrameStatistics::beginDrag()
{
    if(mDragging)
        return;
    mDragFrames.reset();
    mDragging = true;
}

//! \brief Ends the press-to-release interval without counting an extra input-event sample.
void FrameStatistics::endDrag()
{
    if(!mDragging)
        return;
    mCompleted.push_back(Completed{"Window drag", mDragFrames});
    mDragFrames.reset();
    mDragging = false;
}

//! \brief Logs and releases the samples of a pointer interval that has ended.
void FrameStatistics::finishMovement(Movement& movement, const char* label)
{
    if(!movement.mActive)
        return;
    log(label, movement.mFrames);
    movement.mFrames.reset();
    movement.mActive = false;
}

//! \brief Counts every render interval once in each active series, including a frame crossing its end.
float FrameStatistics::sampleFrame(bool inGame, std::int64_t turn, bool active)
{
    const double time = now();
    FrameStallTrace::get().beginFrame(time, inGame, turn, active);
    const float seconds = mPreviousFrame == 0.0 ? 0.0f : static_cast<float>(time - mPreviousFrame);
    mPreviousFrame = time;
    // Input may be delivered before frameStarted (SFML) or after it (OIS). Defer
    // ended intervals so both paths retain their last intersecting render frame.
    for(Completed& completed : mCompleted)
    {
        completed.mFrames.addFrame(seconds);
        log(completed.mLabel, completed.mFrames);
    }
    mCompleted.clear();
    if(mMenuMovement.mActive)
    {
        mMenuMovement.mFrames.addFrame(seconds);
        if(time - mMenuMovement.mLastMovement >= 1.0 || inGame)
            finishMovement(mMenuMovement, "Menu hand movement");
    }
    if(mWindowMovement.mActive)
    {
        mWindowMovement.mFrames.addFrame(seconds);
        if(time - mWindowMovement.mLastMovement >= 1.0 || !inGame)
            finishMovement(mWindowMovement, "Game window hand movement");
    }
    if(mDragging)
        mDragFrames.addFrame(seconds);
    if(inGame && !mInGame)
    {
        mGameFrames.reset();
        mNextMinute = time + 60.0;
    }
    if(mInGame)
    {
        mGameFrames.addFrame(seconds);
        while(time >= mNextMinute)
        {
            log("Game minute", mGameFrames);
            mGameFrames.reset();
            mNextMinute += 60.0;
        }
        if(!inGame)
        {
            log("Game minute interrupted", mGameFrames);
            mGameFrames.reset();
            if(mDragging)
            {
                log("Window drag interrupted", mDragFrames);
                mDragFrames.reset();
                mDragging = false;
            }
        }
    }
    mInGame = inGame;
    return seconds;
}

//! \brief Preserves the last partial intervals on a normal shutdown.
void FrameStatistics::finish()
{
    finishMovement(mMenuMovement, "Menu hand movement interrupted");
    finishMovement(mWindowMovement, "Game window hand movement interrupted");
    endDrag();
    for(const Completed& completed : mCompleted)
        log(completed.mLabel, completed.mFrames);
    mCompleted.clear();
    if(mInGame)
        log("Game minute interrupted", mGameFrames);
    mGameFrames.reset();
    mInGame = false;
}
