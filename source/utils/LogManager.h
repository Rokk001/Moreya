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

#ifndef LOGMANAGER_H
#define LOGMANAGER_H

#include <condition_variable>
#include <deque>
#include <map>
#include <memory>
#include <sstream>
#include <string>
#include <thread>
#include <vector>

#include <mutex>

#include <OgreSingleton.h>

#include "utils/Helper.h"
#include "utils/LogMessageLevel.h"
#include "utils/LogSink.h"

#define OD_LOG_ERR(_message)                      LogManager::getSingleton().logMessage(LogMessageLevel::CRITICAL, __FILE__, __LINE__, (std::string("") + _message))
#define OD_LOG_WRN(_message)                      LogManager::getSingleton().logMessage(LogMessageLevel::WARNING, __FILE__, __LINE__, (std::string("") + _message))
#define OD_LOG_INF(_message)                      LogManager::getSingleton().logMessage(LogMessageLevel::NORMAL, __FILE__, __LINE__, (std::string("") + _message))
#define OD_LOG_DBG(_message)                      LogManager::getSingleton().logMessage(LogMessageLevel::TRIVIAL, __FILE__, __LINE__, (std::string("") + _message))
#define OD_LOG_DIG(_message)                      //LogManager::getSingleton().logMessage(LogMessageLevel::NORMAL, __FILE__, __LINE__, (std::string("DIGGING ") + _message))


#define OD_ASSERT_TRUE(_condition)                if (!(_condition)) LogManager::getSingleton().logMessage(LogMessageLevel::CRITICAL, __FILE__, __LINE__, std::string(#_condition))
#define OD_ASSERT_TRUE_MSG(_condition, _message)  if (!(_condition)) LogManager::getSingleton().logMessage(LogMessageLevel::CRITICAL, __FILE__, __LINE__, (std::string("") + _message))

//! \brief Helper/wrapper class to provide thread-safe logging when ogre is compiled without threads.
//! The sinks are written by an own writer thread, so a slow file or console write never stalls a frame.
class LogManager : public Ogre::Singleton<LogManager>
{
public:
    LogManager();
    ~LogManager();

    //! \brief Add a sink for log messages.
    void addSink(std::unique_ptr<LogSink> sink);

    //! \brief Set the global minimum logging level.
    void setLevel(LogMessageLevel level);

    //! \brief Set the minimum logging level per module.
    void setModuleLevel(const char* module, LogMessageLevel level);

    //! \brief Log a message to the sinks. The message is filtered and timestamped at once and written by the writer
    //! thread; a critical message is written before this returns.
    void logMessage(LogMessageLevel level, const char* filepath, int line, const std::string& message);

    //! \brief Number of critical messages (OD_LOG_ERR, failed OD_ASSERT_TRUE) logged so far, whatever the log level.
    uint32_t getCriticalCount();

    //! \brief The first critical message logged (empty if none).
    std::string getFirstCritical();

    //! \brief Writes every message logged so far to the sinks before it returns. Gives up after one second if
    //! another thread is stuck inside a sink, so a crash handler never hangs here.
    void flush();

    static const std::string GAMELOG_NAME;
private:
    LogManager(const LogManager&) = delete;
    LogManager& operator=(const LogManager&) = delete;

    //! \brief One accepted message waiting for the writer thread, with its timestamp taken when it was logged.
    struct PendingLine
    {
        LogMessageLevel mLevel;
        std::string mModule;
        std::string mTimestamp;
        std::string mFilename;
        int mLine;
        std::string mMessage;
    };

    //! \brief Body of the writer thread: writes queued messages to the sinks until the manager is destroyed and
    //! the queue is empty. The render thread therefore never waits for a file or console write.
    void writerLoop();

    //! \brief Takes all queued messages and writes them to the sinks in logging order. The caller holds mSinkLock.
    void writeQueuedLines();

    //! \brief Flushes the log of the current manager when the program ends through exit().
    static void flushAtExit();

    LogMessageLevel mLevel;
    uint32_t mCriticalCount;
    std::string mFirstCritical;
    std::map<std::string, LogMessageLevel> mModuleLevel;
    //! \brief Guards the counters, the filters, the timestamp stream and mPending.
    std::mutex mLock;
    //! \brief Held while messages are written to the sinks and while a sink is added; keeps the logging order.
    std::timed_mutex mSinkLock;
    std::vector<std::unique_ptr<LogSink>> mSinks;
    std::stringstream mTimestampStream;
    //! \brief Messages accepted by logMessage and not written yet, oldest first.
    std::deque<PendingLine> mPending;
    //! \brief Wakes the writer thread when a message is queued or the manager stops.
    std::condition_variable mPendingChanged;
    //! \brief Set by the destructor; the writer thread ends once the queue is empty.
    bool mStopWriter;
    //! \brief Writes the queued messages to the sinks, off the threads that log them.
    std::thread mWriter;
};

#endif // LOGMANAGER_H
