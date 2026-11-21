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

// Compiled only with OD_NET_HELPER_RELAY (see HelperRelayProcess.h and docs/development/NETWORK-TRANSPORT.md).
#ifdef OD_NET_HELPER_RELAY

#include "network/HelperRelayProcess.h"

#include "utils/LogManager.h"

#include <atomic>
#include <chrono>

#ifdef _WIN32
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#else
#include <cerrno>
#include <cstring>
#include <fcntl.h>
#include <signal.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>
#endif

namespace
{
    //! \brief Bytes read from the helper per call of the reader thread.
    const std::size_t READ_BUFFER_SIZE = 64 * 1024;

    //! \brief The process returned by HelperRelayProcess::getActive().
    std::atomic<HelperRelayProcess*> gActiveProcess(nullptr);

    //! \brief The deadline timeoutMs from now.
    std::chrono::steady_clock::time_point deadlineAfter(int timeoutMs)
    {
        return std::chrono::steady_clock::now() + std::chrono::milliseconds(timeoutMs);
    }

#ifdef _WIN32
    //! \brief Exit code given to a helper that had to be terminated (the POSIX value for SIGKILL).
    const int TERMINATED_EXIT_CODE = 137;

    //! \brief Size hint of each anonymous pipe buffer.
    const DWORD PIPE_BUFFER_SIZE = 64 * 1024;

    //! \brief Largest single WriteFile call.
    const std::size_t WRITE_CHUNK_SIZE = 64 * 1024;

    //! \brief Converts UTF-8 to UTF-16 for the wide Windows API; empty if the text is empty or not valid UTF-8.
    std::wstring toWide(const std::string& text)
    {
        if(text.empty())
            return std::wstring();
        int count = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, text.data(), static_cast<int>(text.size()), nullptr, 0);
        if(count <= 0)
            return std::wstring();
        std::wstring wide(static_cast<std::size_t>(count), L'\0');
        MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, text.data(), static_cast<int>(text.size()), &wide[0], count);
        return wide;
    }

    //! \brief Quotes one argument so that the C runtime of the child splits the command line back into it.
    std::wstring quoteWindowsArgument(const std::wstring& argument)
    {
        if(!argument.empty() && (argument.find_first_of(L" \t\n\v\"") == std::wstring::npos))
            return argument;

        std::wstring quoted(1, L'"');
        std::size_t backslashes = 0;
        for(std::wstring::const_iterator it = argument.begin(); it != argument.end(); ++it)
        {
            if(*it == L'\\')
            {
                ++backslashes;
                continue;
            }
            // Backslashes are literal unless they precede a quote; then each one and the quote get escaped
            if(*it == L'"')
                quoted.append(backslashes * 2 + 1, L'\\');
            else
                quoted.append(backslashes, L'\\');
            backslashes = 0;
            quoted.push_back(*it);
        }
        // Backslashes before the closing quote are doubled so that they do not escape it
        quoted.append(backslashes * 2, L'\\');
        quoted.push_back(L'"');
        return quoted;
    }

    //! \brief Closes a handle that is set and marks it as unset.
    void closeHandle(HANDLE& handle)
    {
        if((handle != nullptr) && (handle != INVALID_HANDLE_VALUE))
            CloseHandle(handle);
        handle = nullptr;
    }
#else
    //! \brief Lets the descriptor be closed by exec, so only the dup2 copies reach the helper.
    void setCloseOnExec(int descriptor)
    {
        int flags = fcntl(descriptor, F_GETFD);
        if(flags >= 0)
            fcntl(descriptor, F_SETFD, flags | FD_CLOEXEC);
    }

    //! \brief Copies a string into a writable, NUL terminated buffer for the argv of execv.
    std::vector<char> toArgument(const std::string& text)
    {
        std::vector<char> buffer(text.begin(), text.end());
        buffer.push_back('\0');
        return buffer;
    }

#ifdef MSG_NOSIGNAL
    //! \brief A write to a helper that exited reports an error instead of raising SIGPIPE.
    const int SEND_FLAGS = MSG_NOSIGNAL;
#else
    //! \brief Systems without MSG_NOSIGNAL set SO_NOSIGPIPE on the socket instead (see spawn()).
    const int SEND_FLAGS = 0;
#endif
#endif
}

//! \brief Ignored by default.
void HelperLobbyObserver::onHelperReady(uint64_t)
{
}

//! \brief Ignored by default.
void HelperLobbyObserver::onLobbyCreated(uint64_t)
{
}

//! \brief Ignored by default.
void HelperLobbyObserver::onLobbyJoined(uint64_t, uint64_t)
{
}

//! \brief Ignored by default.
void HelperLobbyObserver::onLobbyInviteAccepted(uint64_t)
{
}

//! \brief Ignored by default.
void HelperLobbyObserver::onLobbyFailed(HelperPipe::MessageType, const std::string&)
{
}

//! \brief Ignored by default.
void HelperLobbyObserver::onHelperError(const std::string&)
{
}

//! \brief Ignored by default.
void HelperLobbyObserver::onHelperExited(int)
{
}

//! \brief An event with every field at its neutral value.
HelperRelayProcess::LobbyEvent::LobbyEvent():
    mKind(LobbyEventKind::ready),
    mLobbyId(0),
    mUserId(0),
    mRequest(HelperPipe::MessageType::hello),
    mExitCode(-1)
{
}

//! \brief A connected peer without messages.
HelperRelayProcess::PeerState::PeerState():
    mDisconnected(false)
{
}

//! \brief Creates a process object that has not started a helper yet.
HelperRelayProcess::HelperRelayProcess():
    mStarted(false),
    mReady(false),
    mExited(false),
    mExitCode(-1),
    mLocalUserId(0),
    mLobbyId(0),
    mHostUserId(0),
    mIsLobbyHost(false),
    mJoinFailures(0),
    mObserver(nullptr),
    mWriteClosed(true),
#ifdef _WIN32
    mProcessHandle(nullptr),
    mWriteHandle(nullptr),
    mReadHandle(nullptr)
#else
    mPid(-1),
    mSocket(-1)
#endif
{
}

//! \brief Stops the helper if it runs and drops the global reference to this object.
HelperRelayProcess::~HelperRelayProcess()
{
    stop(DEFAULT_STOP_TIMEOUT_MS);
    HelperRelayProcess* self = this;
    gActiveProcess.compare_exchange_strong(self, nullptr);
}

//! \brief Resets the state, starts the child and the reader thread and sends hello.
bool HelperRelayProcess::start(const std::string& executable, const std::vector<std::string>& arguments)
{
    {
        std::lock_guard<std::mutex> lock(mStateMutex);
        if(mStarted)
        {
            OD_LOG_ERR("The relay helper is already running");
            return false;
        }
        mReady = false;
        mExited = false;
        mExitCode = -1;
        mLocalUserId = 0;
        mLobbyId = 0;
        mHostUserId = 0;
        mIsLobbyHost = false;
        mJoinFailures = 0;
        mPendingPeers.clear();
        mPeers.clear();
        mLobbyEvents.clear();
    }

    if(!spawn(executable, arguments))
        return false;

    {
        std::lock_guard<std::mutex> lock(mWriteMutex);
        mWriteClosed = false;
    }
    {
        std::lock_guard<std::mutex> lock(mStateMutex);
        mStarted = true;
    }
    mReader = std::thread(&HelperRelayProcess::readerLoop, this);
    OD_LOG_INF("Started the relay helper " + executable);

    // A helper that cannot read hello has exited already; the reader thread reports that
    if(!sendFrame(HelperPipe::MessageType::hello, std::vector<uint8_t>()))
        OD_LOG_WRN("Could not send hello to the relay helper");
    return true;
}

//! \brief Waits on the state for ready or exit, at most timeoutMs.
bool HelperRelayProcess::waitForReady(int timeoutMs)
{
    std::chrono::steady_clock::time_point deadline = deadlineAfter(timeoutMs);
    std::unique_lock<std::mutex> lock(mStateMutex);
    while(!mReady && !mExited && mStarted)
    {
        if(mStateChanged.wait_until(lock, deadline) == std::cv_status::timeout)
            break;
    }
    return mReady && !mExited;
}

//! \brief Sends shutdown, closes the input of the helper, waits for its exit (terminating it late) and joins the reader.
void HelperRelayProcess::stop(int timeoutMs)
{
    {
        std::lock_guard<std::mutex> lock(mStateMutex);
        if(!mStarted)
            return;
    }

    sendFrame(HelperPipe::MessageType::shutdown, std::vector<uint8_t>());
    closeWriteEnd();

    bool exited = false;
    {
        std::chrono::steady_clock::time_point deadline = deadlineAfter(timeoutMs);
        std::unique_lock<std::mutex> lock(mStateMutex);
        while(!mExited)
        {
            if(mStateChanged.wait_until(lock, deadline) == std::cv_status::timeout)
                break;
        }
        exited = mExited;
    }
    if(!exited)
    {
        OD_LOG_WRN("The relay helper did not exit after shutdown, terminating it");
        terminateChild();
        unblockReader();
    }

    if(mReader.joinable())
        mReader.join();
    closeHandles();

    std::lock_guard<std::mutex> lock(mStateMutex);
    mStarted = false;
    OD_LOG_INF("The relay helper stopped with exit code " + std::to_string(mExitCode));
}

//! \brief Started and not exited.
bool HelperRelayProcess::isRunning() const
{
    std::lock_guard<std::mutex> lock(mStateMutex);
    return mStarted && !mExited;
}

//! \brief Answered ready and not exited.
bool HelperRelayProcess::isReady() const
{
    std::lock_guard<std::mutex> lock(mStateMutex);
    return mReady && !mExited;
}

//! \brief Whether a started helper has exited.
bool HelperRelayProcess::hasExited() const
{
    std::lock_guard<std::mutex> lock(mStateMutex);
    return mExited;
}

//! \brief Exit code once exited, -1 before.
int HelperRelayProcess::getExitCode() const
{
    std::lock_guard<std::mutex> lock(mStateMutex);
    return mExitCode;
}

//! \brief User id of the ready answer.
uint64_t HelperRelayProcess::getLocalUserId() const
{
    std::lock_guard<std::mutex> lock(mStateMutex);
    return mLocalUserId;
}

//! \brief Sends lobbyCreate once the helper is ready.
bool HelperRelayProcess::createLobby(HelperPipe::LobbyVisibility visibility, uint16_t maxMembers)
{
    if(!isReady())
        return false;
    return sendFrame(HelperPipe::MessageType::lobbyCreate, HelperPipe::encodeLobbyCreate(visibility, maxMembers));
}

//! \brief Sends lobbyJoin once the helper is ready.
bool HelperRelayProcess::joinLobby(uint64_t lobbyId)
{
    if(!isReady())
        return false;
    return sendFrame(HelperPipe::MessageType::lobbyJoin, HelperPipe::encodeId(lobbyId));
}

//! \brief Sends lobbyLeave and forgets the current lobby.
bool HelperRelayProcess::leaveLobby()
{
    if(!isReady())
        return false;
    if(!sendFrame(HelperPipe::MessageType::lobbyLeave, std::vector<uint8_t>()))
        return false;
    std::lock_guard<std::mutex> lock(mStateMutex);
    mLobbyId = 0;
    mHostUserId = 0;
    mIsLobbyHost = false;
    return true;
}

//! \brief Sends lobbyInvite once the helper is ready.
bool HelperRelayProcess::inviteToLobby()
{
    if(!isReady())
        return false;
    return sendFrame(HelperPipe::MessageType::lobbyInvite, std::vector<uint8_t>());
}

//! \brief Lobby created or joined last.
uint64_t HelperRelayProcess::getLobbyId() const
{
    std::lock_guard<std::mutex> lock(mStateMutex);
    return mLobbyId;
}

//! \brief Host of the current lobby.
uint64_t HelperRelayProcess::getHostUserId() const
{
    std::lock_guard<std::mutex> lock(mStateMutex);
    return mHostUserId;
}

//! \brief Whether the game hosts the current lobby.
bool HelperRelayProcess::isLobbyHost() const
{
    std::lock_guard<std::mutex> lock(mStateMutex);
    return mIsLobbyHost;
}

//! \brief Sets the observer of dispatchLobbyEvents().
void HelperRelayProcess::setLobbyObserver(HelperLobbyObserver* observer)
{
    std::lock_guard<std::mutex> lock(mStateMutex);
    mObserver = observer;
}

//! \brief Waits until a lobby event is queued, at most timeoutMs (0: no limit).
bool HelperRelayProcess::waitForLobbyEvent(int timeoutMs)
{
    std::chrono::steady_clock::time_point deadline = deadlineAfter(timeoutMs);
    std::unique_lock<std::mutex> lock(mStateMutex);
    while(mLobbyEvents.empty())
    {
        if(timeoutMs == 0)
            mStateChanged.wait(lock);
        else if(mStateChanged.wait_until(lock, deadline) == std::cv_status::timeout)
            break;
    }
    return !mLobbyEvents.empty();
}

//! \brief Takes all queued lobby events and calls the observer for each one outside the state lock.
std::size_t HelperRelayProcess::dispatchLobbyEvents()
{
    std::deque<LobbyEvent> events;
    HelperLobbyObserver* observer = nullptr;
    {
        std::lock_guard<std::mutex> lock(mStateMutex);
        events.swap(mLobbyEvents);
        observer = mObserver;
    }

    for(std::deque<LobbyEvent>::const_iterator it = events.begin(); it != events.end(); ++it)
    {
        const LobbyEvent& event = *it;
        if(observer == nullptr)
        {
            OD_LOG_INF("No lobby observer, dropping relay helper event " + std::to_string(static_cast<int>(event.mKind)));
            continue;
        }
        switch(event.mKind)
        {
            case LobbyEventKind::ready:
                observer->onHelperReady(event.mUserId);
                break;
            case LobbyEventKind::created:
                observer->onLobbyCreated(event.mLobbyId);
                break;
            case LobbyEventKind::joined:
                observer->onLobbyJoined(event.mLobbyId, event.mUserId);
                break;
            case LobbyEventKind::inviteAccepted:
                observer->onLobbyInviteAccepted(event.mLobbyId);
                break;
            case LobbyEventKind::failed:
                observer->onLobbyFailed(event.mRequest, event.mText);
                break;
            case LobbyEventKind::error:
                observer->onHelperError(event.mText);
                break;
            case LobbyEventKind::exited:
                observer->onHelperExited(event.mExitCode);
                break;
            default:
                break;
        }
    }
    return events.size();
}

//! \brief Sends a peerData frame to a connected peer.
bool HelperRelayProcess::sendPeerData(uint64_t peerId, const void* data, std::size_t size)
{
    {
        std::lock_guard<std::mutex> lock(mStateMutex);
        if(mExited || !mStarted)
            return false;
        std::map<uint64_t, PeerState>::const_iterator it = mPeers.find(peerId);
        if((it == mPeers.end()) || it->second.mDisconnected)
            return false;
    }
    if(size + 8 > HelperPipe::MAX_BODY_SIZE)
    {
        OD_LOG_ERR("A game message of " + std::to_string(size) + " bytes is too large for the relay helper");
        return false;
    }
    return sendFrame(HelperPipe::MessageType::peerData, HelperPipe::encodePeerData(peerId, data, size));
}

//! \brief Marks a connected peer as gone and sends peerClose for it.
void HelperRelayProcess::closePeer(uint64_t peerId)
{
    {
        std::lock_guard<std::mutex> lock(mStateMutex);
        std::map<uint64_t, PeerState>::iterator it = mPeers.find(peerId);
        if((it == mPeers.end()) || it->second.mDisconnected || mExited)
            return;
        it->second.mDisconnected = true;
    }
    sendFrame(HelperPipe::MessageType::peerClose, HelperPipe::encodeId(peerId));
    notifyStateChanged();
}

//! \brief Creates the queue of the peer if it has none.
void HelperRelayProcess::openPeer(uint64_t peerId)
{
    std::lock_guard<std::mutex> lock(mStateMutex);
    if(mPeers.find(peerId) == mPeers.end())
        mPeers[peerId] = PeerState();
}

//! \brief Drops the queue of the peer and a pending accept of it.
void HelperRelayProcess::releasePeer(uint64_t peerId)
{
    std::lock_guard<std::mutex> lock(mStateMutex);
    mPeers.erase(peerId);
    for(std::deque<uint64_t>::iterator it = mPendingPeers.begin(); it != mPendingPeers.end(); ++it)
    {
        if(*it == peerId)
        {
            mPendingPeers.erase(it);
            break;
        }
    }
}

//! \brief Takes the oldest pending peer while the helper runs.
bool HelperRelayProcess::takePendingPeer(uint64_t& peerId)
{
    std::lock_guard<std::mutex> lock(mStateMutex);
    if(mPendingPeers.empty() || mExited)
        return false;
    peerId = mPendingPeers.front();
    mPendingPeers.pop_front();
    return true;
}

//! \brief Whether a pending peer is there while the helper runs.
bool HelperRelayProcess::hasPendingPeer() const
{
    std::lock_guard<std::mutex> lock(mStateMutex);
    return !mPendingPeers.empty() && !mExited;
}

//! \brief Takes the oldest message of the peer; queued messages are delivered before the disconnect.
HelperPeerRead HelperRelayProcess::takePeerData(uint64_t peerId, std::vector<uint8_t>& payload)
{
    std::lock_guard<std::mutex> lock(mStateMutex);
    std::map<uint64_t, PeerState>::iterator it = mPeers.find(peerId);
    if(it == mPeers.end())
        return HelperPeerRead::disconnected;
    PeerState& peer = it->second;
    if(!peer.mMessages.empty())
    {
        payload.swap(peer.mMessages.front());
        peer.mMessages.pop_front();
        return HelperPeerRead::data;
    }
    if(peer.mDisconnected || mExited)
        return HelperPeerRead::disconnected;
    return HelperPeerRead::empty;
}

//! \brief Whether a message or the disconnect of the peer is there.
bool HelperRelayProcess::isPeerReady(uint64_t peerId) const
{
    std::lock_guard<std::mutex> lock(mStateMutex);
    return isPeerReadyLocked(peerId);
}

//! \brief Ready as isPeerReady(), but a peer without a queue never is (the listener must not wake for it).
bool HelperRelayProcess::isKnownPeerReady(uint64_t peerId) const
{
    std::lock_guard<std::mutex> lock(mStateMutex);
    if(mPeers.find(peerId) == mPeers.end())
        return false;
    return isPeerReadyLocked(peerId);
}

//! \brief Waits until the peer is ready, at most timeoutMs (0: no limit).
bool HelperRelayProcess::waitForPeer(uint64_t peerId, int timeoutMs)
{
    std::chrono::steady_clock::time_point deadline = deadlineAfter(timeoutMs);
    std::unique_lock<std::mutex> lock(mStateMutex);
    while(!isPeerReadyLocked(peerId))
    {
        if(timeoutMs == 0)
            mStateChanged.wait(lock);
        else if(mStateChanged.wait_until(lock, deadline) == std::cv_status::timeout)
            break;
    }
    return isPeerReadyLocked(peerId);
}

//! \brief Sends lobbyJoin unless the lobby is joined with a connected host and waits for the answer.
bool HelperRelayProcess::joinLobbyAndWait(uint64_t lobbyId, int timeoutMs, uint64_t& hostUserId)
{
    uint64_t failuresBefore = 0;
    {
        std::lock_guard<std::mutex> lock(mStateMutex);
        if(!mReady || mExited)
            return false;
        if(!mIsLobbyHost && (mLobbyId == lobbyId) && (mHostUserId != 0))
        {
            std::map<uint64_t, PeerState>::const_iterator it = mPeers.find(mHostUserId);
            if((it != mPeers.end()) && !it->second.mDisconnected)
            {
                hostUserId = mHostUserId;
                return true;
            }
        }
        failuresBefore = mJoinFailures;
        // A new lobbyJoined has to arrive; the answer to an earlier join must not count
        mLobbyId = 0;
        mHostUserId = 0;
        mIsLobbyHost = false;
    }

    if(!sendFrame(HelperPipe::MessageType::lobbyJoin, HelperPipe::encodeId(lobbyId)))
        return false;

    std::chrono::steady_clock::time_point deadline = deadlineAfter(timeoutMs);
    std::unique_lock<std::mutex> lock(mStateMutex);
    while(true)
    {
        if(!mIsLobbyHost && (mLobbyId == lobbyId) && (mHostUserId != 0))
        {
            hostUserId = mHostUserId;
            return true;
        }
        if((mJoinFailures != failuresBefore) || mExited)
            return false;
        if(timeoutMs == 0)
            mStateChanged.wait(lock);
        else if(mStateChanged.wait_until(lock, deadline) == std::cv_status::timeout)
        {
            if(!mIsLobbyHost && (mLobbyId == lobbyId) && (mHostUserId != 0))
            {
                hostUserId = mHostUserId;
                return true;
            }
            OD_LOG_WRN("No answer of the relay helper to joining lobby " + std::to_string(lobbyId));
            return false;
        }
    }
}

//! \brief Adds a sink for the reader thread.
void HelperRelayProcess::addEventSink(HelperRelayEventSink* sink)
{
    std::lock_guard<std::mutex> lock(mSinkMutex);
    for(std::vector<HelperRelayEventSink*>::const_iterator it = mSinks.begin(); it != mSinks.end(); ++it)
    {
        if(*it == sink)
            return;
    }
    mSinks.push_back(sink);
}

//! \brief Removes a sink; takes the sink lock, so a call in progress on the reader thread has ended.
void HelperRelayProcess::removeEventSink(HelperRelayEventSink* sink)
{
    std::lock_guard<std::mutex> lock(mSinkMutex);
    for(std::vector<HelperRelayEventSink*>::iterator it = mSinks.begin(); it != mSinks.end(); ++it)
    {
        if(*it == sink)
        {
            mSinks.erase(it);
            return;
        }
    }
}

//! \brief The process used for new relay connections and listeners.
HelperRelayProcess* HelperRelayProcess::getActive()
{
    return gActiveProcess.load();
}

//! \brief Sets the process used for new relay connections and listeners.
void HelperRelayProcess::setActive(HelperRelayProcess* process)
{
    gActiveProcess.store(process);
}

//! \brief Reads and files frames until the stream ends or breaks, then records the exit of the child.
void HelperRelayProcess::readerLoop()
{
    HelperPipe::FrameDecoder decoder;
    std::vector<uint8_t> buffer(READ_BUFFER_SIZE);
    bool broken = false;
    while(!broken)
    {
        std::size_t count = readFromHelper(buffer.data(), buffer.size());
        if(count == 0)
            break;

        decoder.feed(buffer.data(), count);
        {
            std::lock_guard<std::mutex> lock(mStateMutex);
            HelperPipe::Frame frame;
            HelperPipe::DecodeResult result = decoder.next(frame);
            while(result == HelperPipe::DecodeResult::frame)
            {
                handleFrameLocked(frame);
                result = decoder.next(frame);
            }
            broken = (result == HelperPipe::DecodeResult::error);
        }
        notifyStateChanged();
    }

    if(broken)
    {
        // The protocol closes a broken stream; the helper cannot be talked to any more
        OD_LOG_ERR("The relay helper sent a broken frame stream, terminating it");
        terminateChild();
    }

    int exitCode = waitForChildExit();
    {
        std::lock_guard<std::mutex> lock(mStateMutex);
        mExited = true;
        mExitCode = exitCode;
        LobbyEvent event;
        event.mKind = LobbyEventKind::exited;
        event.mExitCode = exitCode;
        mLobbyEvents.push_back(event);
    }
    reapChild();
    if(exitCode == 0)
        OD_LOG_INF("The relay helper exited");
    else
        OD_LOG_WRN("The relay helper exited with code " + std::to_string(exitCode));
    notifyStateChanged();
}

//! \brief Encodes the frame and writes it unless the game side of the pipe is closed.
bool HelperRelayProcess::sendFrame(HelperPipe::MessageType type, const std::vector<uint8_t>& body)
{
    std::vector<uint8_t> frame;
    if(!HelperPipe::encodeFrame(type, body, frame))
        return false;
    std::lock_guard<std::mutex> lock(mWriteMutex);
    if(mWriteClosed)
        return false;
    return writeToHelper(frame.data(), frame.size());
}

//! \brief Updates the lobby state, the peer queues and the lobby events from one frame.
void HelperRelayProcess::handleFrameLocked(const HelperPipe::Frame& frame)
{
    bool valid = true;
    switch(frame.mType)
    {
        case HelperPipe::MessageType::ready:
        {
            uint64_t userId = 0;
            valid = HelperPipe::decodeId(frame.mBody, userId);
            if(!valid)
                break;
            mReady = true;
            mLocalUserId = userId;
            LobbyEvent event;
            event.mKind = LobbyEventKind::ready;
            event.mUserId = userId;
            mLobbyEvents.push_back(event);
            break;
        }
        case HelperPipe::MessageType::lobbyCreated:
        {
            uint64_t lobbyId = 0;
            valid = HelperPipe::decodeId(frame.mBody, lobbyId);
            if(!valid)
                break;
            mLobbyId = lobbyId;
            mHostUserId = mLocalUserId;
            mIsLobbyHost = true;
            LobbyEvent event;
            event.mKind = LobbyEventKind::created;
            event.mLobbyId = lobbyId;
            mLobbyEvents.push_back(event);
            break;
        }
        case HelperPipe::MessageType::lobbyJoined:
        {
            uint64_t lobbyId = 0;
            uint64_t hostUserId = 0;
            valid = HelperPipe::decodeLobbyJoined(frame.mBody, lobbyId, hostUserId);
            if(!valid)
                break;
            mLobbyId = lobbyId;
            mHostUserId = hostUserId;
            mIsLobbyHost = false;
            // The host may send right after the join, before the client connection exists
            mPeers[hostUserId] = PeerState();
            LobbyEvent event;
            event.mKind = LobbyEventKind::joined;
            event.mLobbyId = lobbyId;
            event.mUserId = hostUserId;
            mLobbyEvents.push_back(event);
            break;
        }
        case HelperPipe::MessageType::lobbyInviteAccepted:
        {
            uint64_t lobbyId = 0;
            valid = HelperPipe::decodeId(frame.mBody, lobbyId);
            if(!valid)
                break;
            LobbyEvent event;
            event.mKind = LobbyEventKind::inviteAccepted;
            event.mLobbyId = lobbyId;
            mLobbyEvents.push_back(event);
            break;
        }
        case HelperPipe::MessageType::lobbyFailed:
        {
            HelperPipe::MessageType request = HelperPipe::MessageType::hello;
            std::string reason;
            valid = HelperPipe::decodeLobbyFailed(frame.mBody, request, reason);
            if(!valid)
                break;
            if(request == HelperPipe::MessageType::lobbyJoin)
                ++mJoinFailures;
            OD_LOG_WRN("Lobby request " + std::to_string(static_cast<int>(request)) + " failed: " + reason);
            LobbyEvent event;
            event.mKind = LobbyEventKind::failed;
            event.mRequest = request;
            event.mText = reason;
            mLobbyEvents.push_back(event);
            break;
        }
        case HelperPipe::MessageType::peerConnected:
        {
            uint64_t peerId = 0;
            valid = HelperPipe::decodeId(frame.mBody, peerId);
            if(!valid)
                break;
            // A peer that connects again starts with an empty queue and is accepted once
            mPeers[peerId] = PeerState();
            for(std::deque<uint64_t>::iterator it = mPendingPeers.begin(); it != mPendingPeers.end(); ++it)
            {
                if(*it == peerId)
                {
                    mPendingPeers.erase(it);
                    break;
                }
            }
            mPendingPeers.push_back(peerId);
            break;
        }
        case HelperPipe::MessageType::peerDisconnected:
        {
            uint64_t peerId = 0;
            valid = HelperPipe::decodeId(frame.mBody, peerId);
            if(!valid)
                break;
            std::map<uint64_t, PeerState>::iterator it = mPeers.find(peerId);
            if(it != mPeers.end())
                it->second.mDisconnected = true;
            for(std::deque<uint64_t>::iterator itPending = mPendingPeers.begin(); itPending != mPendingPeers.end(); ++itPending)
            {
                if(*itPending == peerId)
                {
                    mPendingPeers.erase(itPending);
                    break;
                }
            }
            break;
        }
        case HelperPipe::MessageType::peerData:
        {
            uint64_t peerId = 0;
            std::vector<uint8_t> payload;
            valid = HelperPipe::decodePeerData(frame.mBody, peerId, payload);
            if(!valid)
                break;
            std::map<uint64_t, PeerState>::iterator it = mPeers.find(peerId);
            if((it == mPeers.end()) || it->second.mDisconnected)
            {
                OD_LOG_DBG("Dropping relayed data of unknown or closed peer " + std::to_string(peerId));
                break;
            }
            it->second.mMessages.push_back(payload);
            break;
        }
        case HelperPipe::MessageType::error:
        {
            std::string text;
            valid = HelperPipe::decodeText(frame.mBody, text);
            if(!valid)
                break;
            OD_LOG_ERR("Relay helper error: " + text);
            LobbyEvent event;
            event.mKind = LobbyEventKind::error;
            event.mText = text;
            mLobbyEvents.push_back(event);
            break;
        }
        default:
            // Frames of a newer helper or of the other direction are ignored, as the protocol says
            OD_LOG_DBG("Ignoring relay helper frame of type " + std::to_string(static_cast<int>(frame.mType)));
            break;
    }
    if(!valid)
        OD_LOG_WRN("Ignoring a malformed relay helper frame of type " + std::to_string(static_cast<int>(frame.mType)));
}

//! \brief Notifies the waiting threads, then calls the sinks outside the state lock.
void HelperRelayProcess::notifyStateChanged()
{
    mStateChanged.notify_all();
    std::lock_guard<std::mutex> lock(mSinkMutex);
    for(std::vector<HelperRelayEventSink*>::const_iterator it = mSinks.begin(); it != mSinks.end(); ++it)
        (*it)->onRelayEvent();
}

//! \brief Data or disconnect of the peer is there; an unknown peer or an ended helper reads as disconnected.
bool HelperRelayProcess::isPeerReadyLocked(uint64_t peerId) const
{
    std::map<uint64_t, PeerState>::const_iterator it = mPeers.find(peerId);
    if(it == mPeers.end())
        return true;
    return !it->second.mMessages.empty() || it->second.mDisconnected || mExited;
}

#ifdef _WIN32

//! \brief Creates two anonymous pipes and starts the helper with them as its standard input and output.
bool HelperRelayProcess::spawn(const std::string& executable, const std::vector<std::string>& arguments)
{
    std::wstring application = toWide(executable);
    if(application.empty())
    {
        OD_LOG_ERR("The relay helper path is empty or not valid UTF-8");
        return false;
    }
    std::wstring commandLine = quoteWindowsArgument(application);
    for(std::vector<std::string>::const_iterator it = arguments.begin(); it != arguments.end(); ++it)
    {
        commandLine += L' ';
        commandLine += quoteWindowsArgument(toWide(*it));
    }
    std::vector<wchar_t> commandBuffer(commandLine.begin(), commandLine.end());
    commandBuffer.push_back(L'\0');

    SECURITY_ATTRIBUTES inheritable;
    ZeroMemory(&inheritable, sizeof(inheritable));
    inheritable.nLength = sizeof(inheritable);
    inheritable.bInheritHandle = TRUE;

    HANDLE childInput = nullptr;
    HANDLE gameOutput = nullptr;
    HANDLE gameInput = nullptr;
    HANDLE childOutput = nullptr;
    HANDLE childError = nullptr;
    bool ok = (CreatePipe(&childInput, &gameOutput, &inheritable, PIPE_BUFFER_SIZE) != FALSE)
        && (CreatePipe(&gameInput, &childOutput, &inheritable, PIPE_BUFFER_SIZE) != FALSE);
    // The game ends of the pipes stay in the game
    if(ok)
    {
        ok = (SetHandleInformation(gameOutput, HANDLE_FLAG_INHERIT, 0) != FALSE)
            && (SetHandleInformation(gameInput, HANDLE_FLAG_INHERIT, 0) != FALSE);
    }
    // The standard error of the helper goes nowhere: the game may have no console, and the frame stream is stdout
    if(ok)
    {
        childError = CreateFileW(L"NUL", GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE, &inheritable,
            OPEN_EXISTING, 0, nullptr);
        ok = (childError != INVALID_HANDLE_VALUE);
    }
    DWORD error = ok ? 0 : GetLastError();

    PROCESS_INFORMATION processInfo;
    ZeroMemory(&processInfo, sizeof(processInfo));
    if(ok)
    {
        // Only the three standard handles are inherited, not every inheritable handle of the game
        SIZE_T attributeSize = 0;
        InitializeProcThreadAttributeList(nullptr, 1, 0, &attributeSize);
        std::vector<unsigned char> attributeBuffer(attributeSize);
        LPPROC_THREAD_ATTRIBUTE_LIST attributes = reinterpret_cast<LPPROC_THREAD_ATTRIBUTE_LIST>(attributeBuffer.data());
        HANDLE inherited[3] = { childInput, childOutput, childError };
        ok = (attributeSize > 0) && (InitializeProcThreadAttributeList(attributes, 1, 0, &attributeSize) != FALSE);
        if(ok)
        {
            ok = (UpdateProcThreadAttribute(attributes, 0, PROC_THREAD_ATTRIBUTE_HANDLE_LIST, inherited,
                sizeof(inherited), nullptr, nullptr) != FALSE);
            if(ok)
            {
                STARTUPINFOEXW startup;
                ZeroMemory(&startup, sizeof(startup));
                startup.StartupInfo.cb = sizeof(startup);
                startup.StartupInfo.dwFlags = STARTF_USESTDHANDLES;
                startup.StartupInfo.hStdInput = childInput;
                startup.StartupInfo.hStdOutput = childOutput;
                startup.StartupInfo.hStdError = childError;
                startup.lpAttributeList = attributes;
                ok = (CreateProcessW(application.c_str(), commandBuffer.data(), nullptr, nullptr, TRUE,
                    EXTENDED_STARTUPINFO_PRESENT | CREATE_NO_WINDOW, nullptr, nullptr, &startup.StartupInfo,
                    &processInfo) != FALSE);
            }
            if(!ok)
                error = GetLastError();
            DeleteProcThreadAttributeList(attributes);
        }
        else
        {
            error = GetLastError();
        }
    }

    // The child holds its own copies of its ends now
    closeHandle(childInput);
    closeHandle(childOutput);
    closeHandle(childError);
    if(!ok)
    {
        closeHandle(gameOutput);
        closeHandle(gameInput);
        OD_LOG_ERR("Could not start the relay helper " + executable + " (error " + std::to_string(error) + ")");
        return false;
    }

    CloseHandle(processInfo.hThread);
    mProcessHandle = processInfo.hProcess;
    mWriteHandle = gameOutput;
    mReadHandle = gameInput;
    return true;
}

//! \brief Blocking ReadFile on the output pipe of the helper; 0 when it is closed or the read was cancelled.
std::size_t HelperRelayProcess::readFromHelper(uint8_t* buffer, std::size_t size)
{
    DWORD received = 0;
    if(ReadFile(mReadHandle, buffer, static_cast<DWORD>(size), &received, nullptr) == FALSE)
        return 0;
    return static_cast<std::size_t>(received);
}

//! \brief WriteFile in chunks until everything is written; the caller holds mWriteMutex.
bool HelperRelayProcess::writeToHelper(const uint8_t* data, std::size_t size)
{
    if(mWriteHandle == nullptr)
        return false;
    while(size > 0)
    {
        DWORD chunk = static_cast<DWORD>((size > WRITE_CHUNK_SIZE) ? WRITE_CHUNK_SIZE : size);
        DWORD written = 0;
        if((WriteFile(mWriteHandle, data, chunk, &written, nullptr) == FALSE) || (written == 0))
            return false;
        data += written;
        size -= written;
    }
    return true;
}

//! \brief Closes the input pipe of the helper.
void HelperRelayProcess::closeWriteEnd()
{
    std::lock_guard<std::mutex> lock(mWriteMutex);
    mWriteClosed = true;
    HANDLE handle = mWriteHandle;
    closeHandle(handle);
    mWriteHandle = nullptr;
}

//! \brief Terminates the child unless it has exited already.
void HelperRelayProcess::terminateChild()
{
    std::lock_guard<std::mutex> lock(mStateMutex);
    if(!mExited && (mProcessHandle != nullptr))
        TerminateProcess(mProcessHandle, static_cast<UINT>(TERMINATED_EXIT_CODE));
}

//! \brief Cancels a ReadFile of the reader thread that would wait for a pipe kept open by another process.
void HelperRelayProcess::unblockReader()
{
    if(mReader.joinable())
        CancelSynchronousIo(mReader.native_handle());
}

//! \brief Waits for the child process and returns its exit code.
int HelperRelayProcess::waitForChildExit()
{
    if(mProcessHandle == nullptr)
        return -1;
    WaitForSingleObject(mProcessHandle, INFINITE);
    DWORD code = 0;
    if(GetExitCodeProcess(mProcessHandle, &code) == FALSE)
        return -1;
    return static_cast<int>(code);
}

//! \brief Nothing to reap on Windows; the process handle is closed by closeHandles().
void HelperRelayProcess::reapChild()
{
}

//! \brief Closes the process handle and both pipe ends.
void HelperRelayProcess::closeHandles()
{
    closeWriteEnd();
    HANDLE readHandle = mReadHandle;
    closeHandle(readHandle);
    mReadHandle = nullptr;
    std::lock_guard<std::mutex> lock(mStateMutex);
    HANDLE processHandle = mProcessHandle;
    closeHandle(processHandle);
    mProcessHandle = nullptr;
}

#else // _WIN32

//! \brief Creates a socket pair and forks; the child gets one end as standard input and output and runs execv.
bool HelperRelayProcess::spawn(const std::string& executable, const std::vector<std::string>& arguments)
{
    // The argv is built before fork: the child of a threaded process may only call async-signal-safe functions
    std::vector<std::vector<char> > storage;
    storage.push_back(toArgument(executable));
    for(std::vector<std::string>::const_iterator it = arguments.begin(); it != arguments.end(); ++it)
        storage.push_back(toArgument(*it));
    std::vector<char*> argv;
    for(std::vector<std::vector<char> >::iterator it = storage.begin(); it != storage.end(); ++it)
        argv.push_back(it->data());
    argv.push_back(nullptr);

    int sockets[2] = { -1, -1 };
    if(socketpair(AF_UNIX, SOCK_STREAM, 0, sockets) != 0)
    {
        OD_LOG_ERR("Could not create the relay helper socket pair: " + std::string(std::strerror(errno)));
        return false;
    }
    // Reports a failed execv to the game: the pipe closes without data when execv succeeds
    int status[2] = { -1, -1 };
    if(pipe(status) != 0)
    {
        OD_LOG_ERR("Could not create the relay helper status pipe: " + std::string(std::strerror(errno)));
        close(sockets[0]);
        close(sockets[1]);
        return false;
    }
    setCloseOnExec(sockets[0]);
    setCloseOnExec(sockets[1]);
    setCloseOnExec(status[0]);
    setCloseOnExec(status[1]);

    pid_t pid = fork();
    if(pid < 0)
    {
        OD_LOG_ERR("Could not fork for the relay helper: " + std::string(std::strerror(errno)));
        close(sockets[0]);
        close(sockets[1]);
        close(status[0]);
        close(status[1]);
        return false;
    }
    if(pid == 0)
    {
        // Child: dup2 clears close-on-exec on the copies, so only they reach the helper
        dup2(sockets[1], STDIN_FILENO);
        dup2(sockets[1], STDOUT_FILENO);
        execv(argv[0], argv.data());
        int execError = errno;
        ssize_t written = write(status[1], &execError, sizeof(execError));
        _exit((written >= 0) ? 127 : 126);
    }

    close(sockets[1]);
    close(status[1]);
    int execError = 0;
    ssize_t received = 0;
    do
    {
        received = read(status[0], &execError, sizeof(execError));
    } while((received < 0) && (errno == EINTR));
    close(status[0]);
    if(received > 0)
    {
        int childStatus = 0;
        waitpid(pid, &childStatus, 0);
        close(sockets[0]);
        OD_LOG_ERR("Could not start the relay helper " + executable + ": " + std::string(std::strerror(execError)));
        return false;
    }

#if !defined(MSG_NOSIGNAL) && defined(SO_NOSIGPIPE)
    int noSigPipe = 1;
    setsockopt(sockets[0], SOL_SOCKET, SO_NOSIGPIPE, &noSigPipe, sizeof(noSigPipe));
#endif
    mPid = static_cast<int>(pid);
    mSocket = sockets[0];
    return true;
}

//! \brief Blocking recv on the socket pair; 0 at end of stream or on an error.
std::size_t HelperRelayProcess::readFromHelper(uint8_t* buffer, std::size_t size)
{
    ssize_t received = 0;
    do
    {
        received = recv(mSocket, buffer, size, 0);
    } while((received < 0) && (errno == EINTR));
    if(received <= 0)
        return 0;
    return static_cast<std::size_t>(received);
}

//! \brief send until everything is written; the caller holds mWriteMutex.
bool HelperRelayProcess::writeToHelper(const uint8_t* data, std::size_t size)
{
    if(mSocket < 0)
        return false;
    while(size > 0)
    {
        ssize_t written = send(mSocket, data, size, SEND_FLAGS);
        if((written < 0) && (errno == EINTR))
            continue;
        if(written <= 0)
            return false;
        data += written;
        size -= static_cast<std::size_t>(written);
    }
    return true;
}

//! \brief Shuts down the sending direction of the socket pair; the helper reads the end of its input.
void HelperRelayProcess::closeWriteEnd()
{
    std::lock_guard<std::mutex> lock(mWriteMutex);
    if(!mWriteClosed && (mSocket >= 0))
        shutdown(mSocket, SHUT_WR);
    mWriteClosed = true;
}

//! \brief Kills the child unless the reader thread has seen it exit (its pid may be reused after that).
void HelperRelayProcess::terminateChild()
{
    std::lock_guard<std::mutex> lock(mStateMutex);
    if(!mExited && (mPid > 0))
        kill(static_cast<pid_t>(mPid), SIGKILL);
}

//! \brief Shuts down both directions of the socket pair, which ends a recv of the reader thread.
void HelperRelayProcess::unblockReader()
{
    if(mSocket >= 0)
        shutdown(mSocket, SHUT_RDWR);
}

//! \brief Waits for the child to end without reaping it (reapChild() does), so terminateChild() cannot hit another process.
int HelperRelayProcess::waitForChildExit()
{
    if(mPid <= 0)
        return -1;
    siginfo_t info;
    std::memset(&info, 0, sizeof(info));
    int result = 0;
    do
    {
        result = waitid(P_PID, static_cast<id_t>(mPid), &info, WEXITED | WNOWAIT);
    } while((result != 0) && (errno == EINTR));
    if(result != 0)
        return -1;
    if(info.si_code == CLD_EXITED)
        return info.si_status;
    return 128 + info.si_status;
}

//! \brief Reaps the child after mExited is set.
void HelperRelayProcess::reapChild()
{
    if(mPid <= 0)
        return;
    int childStatus = 0;
    pid_t result = 0;
    do
    {
        result = waitpid(static_cast<pid_t>(mPid), &childStatus, 0);
    } while((result < 0) && (errno == EINTR));
}

//! \brief Closes the socket pair end of the game.
void HelperRelayProcess::closeHandles()
{
    closeWriteEnd();
    if(mSocket >= 0)
        close(mSocket);
    mSocket = -1;
    std::lock_guard<std::mutex> lock(mStateMutex);
    mPid = -1;
}

#endif // _WIN32

#endif // OD_NET_HELPER_RELAY
