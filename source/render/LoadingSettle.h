#ifndef LOADINGSETTLE_H
#define LOADINGSETTLE_H

#include <cstdint>

//! \brief Decides when the loading picture of a map load may end after the game or editor mode has opened.
//! The first frames of a new map still create the tile entities, load first-use textures and build shaders (frames of
//! 0.2 to 1.9 s were measured right after the picture used to end). The picture therefore stays until the client has
//! processed the first new game turn (not needed in the editor or while the game is paused) and then QUICK_FRAMES
//! frames in a row took less than QUICK_FRAME_SECONDS each, at the latest after LIMIT_SECONDS of frames.
class LoadingSettle
{
public:
    //! \brief Frames in a row that must be quick before the picture ends.
    static const int QUICK_FRAMES = 3;

    //! \brief Starts waiting; waitForTurn is false for the editor, where no game turns are computed.
    void start(bool waitForTurn)
    {
        mActive = true;
        mWaitForTurn = waitForTurn;
        mHasFirstTurn = false;
        mFirstTurn = 0;
        mTurnDone = false;
        mQuickFrames = 0;
        mElapsed = 0.0;
    }

    //! \brief Stops waiting, for example when the picture ends for another reason.
    void stop()
    {
        mActive = false;
    }

    //! \brief True while the picture waits for the map to settle.
    bool isActive() const
    {
        return mActive;
    }

    //! \brief Takes one sampled frame (its duration, the game turn after it and the pause state) and returns true
    //! exactly once, when the picture should end now. The first frame after start() is the frame of the mode change
    //! itself and only gives the starting turn; its duration is part of the load.
    bool frame(double seconds, int64_t turn, bool paused)
    {
        if(!mActive)
            return false;
        if(!mHasFirstTurn)
        {
            mHasFirstTurn = true;
            mFirstTurn = turn;
            return false;
        }
        mElapsed += seconds;
        if(!mWaitForTurn || paused || turn > mFirstTurn)
            mTurnDone = true;
        if(seconds < QUICK_FRAME_SECONDS)
            ++mQuickFrames;
        else
            mQuickFrames = 0;
        if((mTurnDone && mQuickFrames >= QUICK_FRAMES) || mElapsed >= LIMIT_SECONDS)
        {
            mActive = false;
            return true;
        }
        return false;
    }

private:
    //! \brief A frame shorter than this counts as quick (three normal 60 Hz frames).
    static constexpr double QUICK_FRAME_SECONDS = 0.050;
    //! \brief The picture ends at the latest after this much frame time, whatever the frames took.
    static constexpr double LIMIT_SECONDS = 6.0;

    bool mActive = false;
    bool mWaitForTurn = true;
    bool mHasFirstTurn = false;
    int64_t mFirstTurn = 0;
    bool mTurnDone = false;
    int mQuickFrames = 0;
    double mElapsed = 0.0;
};

#endif // LOADINGSETTLE_H
