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

#include "render/FrameStallTrace.h"
#include "utils/LogManager.h"

#include <boost/filesystem.hpp>

#include <chrono>
#include <cstdlib>
#include <iomanip>

template<> LogManager* Ogre::Singleton<LogManager>::msSingleton = nullptr;

//! \brief Log filename used when OD Application throws errors without using Ogre default logger.
const std::string LogManager::GAMELOG_NAME = "gameLog";

//! \brief Starts the writer thread and registers the flush at program exit once.
LogManager::LogManager()
    : mLevel(LogMessageLevel::NORMAL),
    mCriticalCount(0),
    mStopWriter(false)
{
    static bool exitFlushRegistered = false;
    if(!exitFlushRegistered)
    {
        exitFlushRegistered = true;
        std::atexit(&LogManager::flushAtExit);
    }
    mWriter = std::thread(&LogManager::writerLoop, this);
}

//! \brief Lets the writer thread write every queued message, then stops it.
LogManager::~LogManager()
{
    {
        std::lock_guard<std::mutex> locked(mLock);
        mStopWriter = true;
    }
    mPendingChanged.notify_one();
    if(mWriter.joinable())
        mWriter.join();
}

//! \brief Adds a sink; waits until no message is being written so the sinks are never changed while in use.
void LogManager::addSink(std::unique_ptr<LogSink> sink)
{
    std::lock_guard<std::timed_mutex> locked(mSinkLock);
    mSinks.push_back(std::move(sink));
}

void LogManager::setLevel(LogMessageLevel level)
{
    mLevel = level;
}

void LogManager::setModuleLevel(const char* module, LogMessageLevel level)
{
    mModuleLevel[module] = level;
}

//! \brief Returns how many critical messages were logged (thread-safe).
uint32_t LogManager::getCriticalCount()
{
    std::lock_guard<std::mutex> locked(mLock);
    return mCriticalCount;
}

//! \brief Returns the first critical message that was logged (thread-safe).
std::string LogManager::getFirstCritical()
{
    std::lock_guard<std::mutex> locked(mLock);
    return mFirstCritical;
}

//! \brief Logs a message to the sinks; guarded by a standard mutex to be thread-safe.
//! \brief Records render-thread stall timing for this operation.
//! The message is filtered and timestamped here and queued for the writer thread, so the calling thread (above all
//! the render thread) only waits for the queue mutex, never for a file or console write. A critical message is
//! written before this returns, so it is in the log even if the program ends right after it.
void LogManager::logMessage(LogMessageLevel level, const char* filepath, int line, const std::string& message)
{
    FrameStallTrace::Scope trace(FrameStallTrace::LogWrite, filepath);
    {
        std::lock_guard<std::mutex> locked(mLock);

        if(level == LogMessageLevel::CRITICAL)
        {
            ++mCriticalCount;
            if(mFirstCritical.empty())
                mFirstCritical = boost::filesystem::path(filepath).filename().string() + ":" + Helper::toString(line) + " " + message;
        }

        // module

        const boost::filesystem::path strippedPath(filepath);
        std::string module = strippedPath.stem().string();

        // Check if the message fails the global threshold.

        if (mLevel > level)
        {
            // Allow per-module overrides of the global logging level.

            if (mModuleLevel.empty())
            {
                return;
            }

            std::map<std::string, LogMessageLevel>::iterator found = mModuleLevel.find(module);
            if (found == mModuleLevel.end() ||
                found->second > level)
            {
                return;
            }
        }

        // filename

        std::string filename = strippedPath.filename().string();

        // timestamp

        time_t current_time = ::time(0);
        struct tm* now = ::localtime(&current_time);

        mTimestampStream.str("");
        mTimestampStream
            << std::setfill('0') << std::setw(2) << now->tm_hour << ':'
            << std::setfill('0') << std::setw(2) << now->tm_min << ':'
            << std::setfill('0') << std::setw(2) << now->tm_sec;

        PendingLine pending;
        pending.mLevel = level;
        pending.mModule = module;
        pending.mTimestamp = mTimestampStream.str();
        pending.mFilename = filename;
        pending.mLine = line;
        pending.mMessage = message;
        mPending.push_back(pending);
    }
    mPendingChanged.notify_one();

    if(level == LogMessageLevel::CRITICAL)
        flush();
}

//! \brief Writes all queued messages on the calling thread. Waits at most one second for a write in progress.
void LogManager::flush()
{
    std::unique_lock<std::timed_mutex> sinks(mSinkLock, std::defer_lock);
    if(!sinks.try_lock_for(std::chrono::seconds(1)))
        return;
    writeQueuedLines();
}

//! \brief Takes the queued messages in one piece and writes them in order; the caller holds mSinkLock.
void LogManager::writeQueuedLines()
{
    std::deque<PendingLine> lines;
    {
        std::lock_guard<std::mutex> locked(mLock);
        lines.swap(mPending);
    }
    for(const PendingLine& pending : lines)
    {
        for (const std::unique_ptr<LogSink>& sink : mSinks)
        {
            sink->write(pending.mLevel, pending.mModule, pending.mTimestamp, pending.mFilename, pending.mLine,
                pending.mMessage);
        }
    }
}

//! \brief Waits for queued messages and writes them until the manager stops and nothing is left.
void LogManager::writerLoop()
{
    while(true)
    {
        {
            std::unique_lock<std::mutex> locked(mLock);
            while(mPending.empty() && !mStopWriter)
                mPendingChanged.wait(locked);
            if(mPending.empty() && mStopWriter)
                return;
        }
        std::lock_guard<std::timed_mutex> sinks(mSinkLock);
        writeQueuedLines();
    }
}

//! \brief Called by exit(): writes what is still queued, so no message logged before an exit() is lost.
void LogManager::flushAtExit()
{
    LogManager* manager = LogManager::getSingletonPtr();
    if(manager != nullptr)
        manager->flush();
}
