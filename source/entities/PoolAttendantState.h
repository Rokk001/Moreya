/*
 *  Copyright (C) 2011-2016  OpenDungeons Team
 *
 *  This program is free software: you can redistribute it and/or modify
 *  it under the terms of the GNU General Public License as published by
 *  the Free Software Foundation, either version 3 of the License, or
 *  (at your option) any later version.
 *
 *  This program is distributed in the hope that it will be useful,
 *  but WITHOUT ANY WARRANTY; without even the implied warranty of
 *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *  GNU General Public License for more details.
 *
 *  You should have received a copy of the GNU General Public License
 *  along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

#ifndef POOLATTENDANTSTATE_H
#define POOLATTENDANTSTATE_H

#include <cstdint>
#include <string>

//! \brief What the pool attendant of a lava spa is doing. The attendant sits on his chair and every few seconds plays
//! a short act; now and then he climbs down for one outing, either to the springboard, a jump into the pool and the walk
//! back, or a round on the rim around the pool, and climbs up again (Mario 2026-11-17, answer to Q8).
enum class PoolAttendantState : uint32_t
{
    //! Sitting on the chair (loop); the next act or jump is counted down.
    sitting = 0,
    //! Whistling at the bathers (one clip).
    whistling = 1,
    //! Waving the towel (one clip).
    towelWaving = 2,
    //! Nodding off and nearly falling off the chair (one clip).
    dozing = 3,
    //! Climbing down the ladder of the chair.
    climbingDown = 4,
    //! Walking from the chair to the springboard.
    walkingToBoard = 5,
    //! In the air after the jump from the springboard.
    jumping = 6,
    //! Walking from the pool back to the chair.
    walkingBack = 7,
    //! Climbing up the ladder of the chair.
    climbingUp = 8,
    //! Walking a round on the rim around the pool, from one side of the chair to the other.
    walkingRound = 9
};

//! \brief The outing of the pool attendant when he gets up from his chair: one of them, never both (Mario 2026-11-17,
//! answer to Q8).
enum class PoolAttendantOuting : uint32_t
{
    //! He stays on his chair.
    none = 0,
    //! Down the ladder, to the springboard, a jump into the mud, back to the chair.
    cannonball = 1,
    //! Down the ladder, a round on the rim around the pool, back to the chair.
    round = 2
};

namespace PoolAttendantOutings
{
    //! \brief Share of the outings that are a jump when both are possible; the other ones are a round.
    const double CANNONBALL_SHARE = 0.5;

    //! \brief Chooses the outing of the attendant when his pause on the chair is over: at random one of the outings that
    //! are possible, the only possible one when the other is not, none when neither is.
    //! \param roll A random number from 0 to 1.
    //! \param canJump True when the room has a springboard and a free pool tile for the jump.
    //! \param canWalkRound True when the rim leads around the pool from one side of the chair to the other.
    inline PoolAttendantOuting choose(double roll, bool canJump, bool canWalkRound)
    {
        if(canJump && canWalkRound)
            return (roll < CANNONBALL_SHARE) ? PoolAttendantOuting::cannonball : PoolAttendantOuting::round;
        if(canJump)
            return PoolAttendantOuting::cannonball;
        if(canWalkRound)
            return PoolAttendantOuting::round;
        return PoolAttendantOuting::none;
    }

    //! \brief The name of an outing in the log.
    //! \param outing The outing.
    inline std::string toString(PoolAttendantOuting outing)
    {
        switch(outing)
        {
            case PoolAttendantOuting::cannonball:
                return "cannonball";
            case PoolAttendantOuting::round:
                return "round";
            case PoolAttendantOuting::none:
                break;
        }
        return "none";
    }
}

//! \brief Everything that is saved of a pool attendant in the room stream. The values that follow from the state (the
//! height while climbing, the start and end of a jump) are worked out again when the attendant is restored.
struct PoolAttendantSave
{
    //! \brief Creates a save record of an attendant that sits on his chair.
    PoolAttendantSave() :
        mX(0.0),
        mY(0.0),
        mState(PoolAttendantState::sitting),
        mTurnsLeft(0.0),
        mHasCannonball(false),
        mCannonballTurnsLeft(0.0),
        mHasPlace(false),
        mPlaceX(0),
        mPlaceY(0),
        mHasClipTime(false),
        mClipTime(0.0)
    {}

    //! Position (x) of the attendant in tiles.
    double mX;
    //! Position (y) of the attendant in tiles.
    double mY;
    //! What the attendant was doing.
    PoolAttendantState mState;
    //! Turns until the next act while he sits, turns the act, the climb or the jump still lasts otherwise.
    double mTurnsLeft;
    //! True when the turns until the next jump were saved (an old or hand-written line misses them).
    bool mHasCannonball;
    //! Turns until the next jump of the attendant from the springboard.
    double mCannonballTurnsLeft;
    //! True when the attendant holds a free pool tile for his jump.
    bool mHasPlace;
    //! Pool tile (x) the attendant jumps to.
    int32_t mPlaceX;
    //! Pool tile (y) the attendant jumps to.
    int32_t mPlaceY;
    //! True when the time the clip had really run was saved (an old line misses it and the time is worked out from the turns left).
    bool mHasClipTime;
    //! Turns the clip of an act or of the climb had really run when the attendant was saved.
    double mClipTime;
};

namespace PoolAttendantStateNames
{
    //! \brief The name of a state in the room stream.
    //! \param state The state.
    inline std::string toString(PoolAttendantState state)
    {
        switch(state)
        {
            case PoolAttendantState::sitting:
                return "sit";
            case PoolAttendantState::whistling:
                return "whistle";
            case PoolAttendantState::towelWaving:
                return "towel";
            case PoolAttendantState::dozing:
                return "doze";
            case PoolAttendantState::climbingDown:
                return "climbDown";
            case PoolAttendantState::walkingToBoard:
                return "toBoard";
            case PoolAttendantState::jumping:
                return "jump";
            case PoolAttendantState::walkingBack:
                return "back";
            case PoolAttendantState::climbingUp:
                return "climbUp";
            case PoolAttendantState::walkingRound:
                return "round";
        }
        return "sit";
    }

    //! \brief Reads the name of a state from the room stream.
    //! \param token The name.
    //! \param state Set to the state when the name is known.
    //! \return False for an unknown name.
    inline bool fromString(const std::string& token, PoolAttendantState& state)
    {
        static const PoolAttendantState ALL_STATES[] = {
            PoolAttendantState::sitting, PoolAttendantState::whistling, PoolAttendantState::towelWaving,
            PoolAttendantState::dozing, PoolAttendantState::climbingDown, PoolAttendantState::walkingToBoard,
            PoolAttendantState::jumping, PoolAttendantState::walkingBack, PoolAttendantState::climbingUp,
            PoolAttendantState::walkingRound };
        for(PoolAttendantState candidate : ALL_STATES)
        {
            if(toString(candidate) == token)
            {
                state = candidate;
                return true;
            }
        }
        return false;
    }
}

#endif // POOLATTENDANTSTATE_H
