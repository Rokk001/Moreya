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

#ifndef HELPERRELAYPROCESS_H
#define HELPERRELAYPROCESS_H

/*! \file HelperRelayProcess.h
 * \brief The relay helper as a child process of the game: start, pipes, handshake, lobby requests and peer queues.
 *
 * Compiled only with OD_NET_HELPER_RELAY (CMake option of the same name, off by default).
 *
 * The game starts the helper executable (command line option --net-helper) with its standard input and output
 * connected to the game: anonymous pipes on Windows, a socket pair on other systems. The game sends hello, the
 * helper answers ready once it is logged in to the platform. A reader thread reads the helper output, splits it
 * into frames with HelperPipe::FrameDecoder and files every frame into thread safe state:
 *
 * - peerConnected / peerDisconnected / peerData go into per peer queues that HelperRelayListener and
 *   HelperRelayConnection (HelperRelayTransport.h) read. Nothing in the server thread or the render loop waits
 *   on the pipe itself.
 * - ready and the lobby answers are queued as lobby events. dispatchLobbyEvents(), called by the frame loop,
 *   delivers them to a HelperLobbyObserver on the calling thread (the later lobby UI).
 *
 * When the helper exits or the stream breaks, every relayed peer reads as disconnected and the observer gets
 * onHelperExited; direct TCP keeps working. See docs/development/NETWORK-TRANSPORT.md.
 */

#ifdef OD_NET_HELPER_RELAY

#include "network/HelperPipeProtocol.h"

#include <condition_variable>
#include <cstddef>
#include <cstdint>
#include <deque>
#include <map>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

/*! \brief Receives the lobby answers of the helper. Every method is called by HelperRelayProcess::dispatchLobbyEvents()
 * on the thread that calls it, never by the reader thread. The default implementations ignore the event.
 */
class HelperLobbyObserver
{
public:
    //! \brief Nothing to release.
    virtual ~HelperLobbyObserver()
    {}

    //! \brief The helper is logged in to the platform as localUserId; lobby requests are possible from now on.
    virtual void onHelperReady(uint64_t localUserId);

    //! \brief The lobby asked for with createLobby() exists and the game is its host.
    virtual void onLobbyCreated(uint64_t lobbyId);

    //! \brief The game joined the lobby; hostUserId is the peer the client connection talks to.
    virtual void onLobbyJoined(uint64_t lobbyId, uint64_t hostUserId);

    //! \brief The player accepted an invite outside the game; joining that lobby is up to the game.
    virtual void onLobbyInviteAccepted(uint64_t lobbyId);

    //! \brief A lobby request (lobbyCreate, lobbyJoin, ...) failed with the reason given by the helper.
    virtual void onLobbyFailed(HelperPipe::MessageType request, const std::string& reason);

    //! \brief The helper reported a fatal error; it exits after this message.
    virtual void onHelperError(const std::string& text);

    //! \brief The helper process ended (or the pipe broke and it was stopped); relayed peers are gone.
    virtual void onHelperExited(int exitCode);
};

/*! \brief Woken by the reader thread after it filed new frames. HelperRelayListener uses it to wake its socket
 * selector. onRelayEvent() runs on the reader thread and must neither block nor call back into the process.
 */
class HelperRelayEventSink
{
public:
    //! \brief Nothing to release.
    virtual ~HelperRelayEventSink()
    {}

    //! \brief New peer or lobby state is there.
    virtual void onRelayEvent() = 0;
};

//! \brief Result of HelperRelayProcess::takePeerData().
enum class HelperPeerRead
{
    //! A message was taken from the queue of the peer.
    data,
    //! No message is queued; the peer is still connected.
    empty,
    //! No message is queued and the peer is gone (peerDisconnected, unknown peer or helper ended).
    disconnected
};

//! \brief One relay helper child process and everything the game knows about its lobby and peers.
class HelperRelayProcess
{
public:
    //! \brief Time the game gives the helper to log in and answer hello with ready.
    static const int DEFAULT_READY_TIMEOUT_MS = 10000;

    //! \brief Time the helper gets to exit after shutdown before it is terminated.
    static const int DEFAULT_STOP_TIMEOUT_MS = 3000;

    //! \brief Creates a process object that has not started a helper yet.
    HelperRelayProcess();

    //! \brief Stops the helper if it runs (see stop()).
    ~HelperRelayProcess();

    /*! \brief Starts the helper executable with the given arguments, starts the reader thread and sends hello.
     * The executable is a path to the program file; it is not searched for. Returns false (and logs why) if the
     * program could not be started or the process already runs a helper. Does not wait for ready; see
     * waitForReady() and HelperLobbyObserver::onHelperReady().
     */
    bool start(const std::string& executable, const std::vector<std::string>& arguments);

    //! \brief Waits up to timeoutMs for ready. False if the helper exited first or the time ran out.
    bool waitForReady(int timeoutMs);

    /*! \brief Sends shutdown, closes the game side of the pipe and waits up to timeoutMs for the helper to exit;
     * terminates it after that. Joins the reader thread. Safe to call when no helper runs.
     */
    void stop(int timeoutMs);

    //! \brief The helper was started and has not exited.
    bool isRunning() const;

    //! \brief The helper answered ready and has not exited.
    bool isReady() const;

    //! \brief A started helper has exited (or was terminated).
    bool hasExited() const;

    //! \brief Exit code of the helper once hasExited(); -1 before.
    int getExitCode() const;

    //! \brief Platform user id reported in ready; 0 before.
    uint64_t getLocalUserId() const;

    //! \brief Asks the helper for a new lobby hosted by this game (lobbyCreate). False if not ready or not sent.
    bool createLobby(HelperPipe::LobbyVisibility visibility, uint16_t maxMembers);

    //! \brief Asks the helper to join the lobby (lobbyJoin). False if not ready or not sent.
    bool joinLobby(uint64_t lobbyId);

    //! \brief Leaves the current lobby (lobbyLeave); the helper closes the relayed sessions.
    bool leaveLobby();

    //! \brief Opens the platform invite dialog for the current lobby (lobbyInvite).
    bool inviteToLobby();

    //! \brief The lobby created or joined last; 0 if none.
    uint64_t getLobbyId() const;

    //! \brief Host of the current lobby: the own user id when hosting, else the id from lobbyJoined.
    uint64_t getHostUserId() const;

    //! \brief Whether the current lobby was created by this game.
    bool isLobbyHost() const;

    //! \brief Sets the observer that dispatchLobbyEvents() calls; nullptr drops the events (they are logged).
    void setLobbyObserver(HelperLobbyObserver* observer);

    //! \brief Waits up to timeoutMs (0: until one comes) for a lobby event that dispatchLobbyEvents() would deliver.
    bool waitForLobbyEvent(int timeoutMs);

    //! \brief Delivers all queued lobby events to the observer on the calling thread; returns how many.
    std::size_t dispatchLobbyEvents();

    /*! \brief Sends one game message to a peer as a peerData frame. False if the helper does not run, the peer
     * is disconnected or the pipe write failed.
     */
    bool sendPeerData(uint64_t peerId, const void* data, std::size_t size);

    //! \brief Sends peerClose for a peer that is still connected.
    void closePeer(uint64_t peerId);

    //! \brief Makes sure the peer has a queue (client side: the host). Messages already queued are kept.
    void openPeer(uint64_t peerId);

    //! \brief Forgets the queue of the peer after its connection was closed.
    void releasePeer(uint64_t peerId);

    //! \brief Takes the oldest peer announced by peerConnected that no listener accepted yet.
    bool takePendingPeer(uint64_t& peerId);

    //! \brief Whether a peerConnected peer waits to be accepted.
    bool hasPendingPeer() const;

    //! \brief Takes the oldest message of the peer; see HelperPeerRead.
    HelperPeerRead takePeerData(uint64_t peerId, std::vector<uint8_t>& payload);

    //! \brief Whether takePeerData() would return data or disconnected (TCP: the socket is readable).
    bool isPeerReady(uint64_t peerId) const;

    //! \brief Like isPeerReady(), but false for a peer without a queue (its connection was closed already).
    bool isKnownPeerReady(uint64_t peerId) const;

    //! \brief Waits up to timeoutMs (0: until it is) for isPeerReady().
    bool waitForPeer(uint64_t peerId, int timeoutMs);

    /*! \brief Joins the lobby unless it is already joined and waits up to timeoutMs (0: no limit) for lobbyJoined.
     * Returns true and the host user id, or false on lobbyFailed for the join, helper exit or timeout.
     */
    bool joinLobbyAndWait(uint64_t lobbyId, int timeoutMs, uint64_t& hostUserId);

    //! \brief Registers a sink woken after the reader thread filed new frames.
    void addEventSink(HelperRelayEventSink* sink);

    //! \brief Removes a sink; once this returns the reader thread does not call it any more.
    void removeEventSink(HelperRelayEventSink* sink);

    //! \brief The process used by NetTransport for new relay connections and listeners; nullptr if none.
    static HelperRelayProcess* getActive();

    //! \brief Sets the process returned by getActive(); the owner resets it to nullptr before destroying it.
    static void setActive(HelperRelayProcess* process);

private:
    //! \brief What a lobby event reports.
    enum class LobbyEventKind
    {
        ready,
        created,
        joined,
        inviteAccepted,
        failed,
        error,
        exited
    };

    //! \brief One queued lobby event; the fields not used by the kind stay at their defaults.
    struct LobbyEvent
    {
        LobbyEvent();
        LobbyEventKind mKind;
        uint64_t mLobbyId;
        uint64_t mUserId;
        HelperPipe::MessageType mRequest;
        std::string mText;
        int mExitCode;
    };

    //! \brief Messages of one peer not taken yet and whether the peer is gone.
    struct PeerState
    {
        PeerState();
        std::deque<std::vector<uint8_t> > mMessages;
        bool mDisconnected;
    };

    //! \brief Not copyable: it owns a child process, pipe handles and a thread.
    HelperRelayProcess(const HelperRelayProcess&);
    HelperRelayProcess& operator=(const HelperRelayProcess&);

    //! \brief Creates the pipes and the child process; fills the handles. Platform specific.
    bool spawn(const std::string& executable, const std::vector<std::string>& arguments);

    //! \brief Reader thread: reads until end of stream, files the frames, then waits for the child to exit.
    void readerLoop();

    //! \brief Reads bytes from the helper; 0 at end of stream or on a read error. Platform specific.
    std::size_t readFromHelper(uint8_t* buffer, std::size_t size);

    //! \brief Writes all bytes to the helper; false if the pipe is closed or broken. Platform specific.
    bool writeToHelper(const uint8_t* data, std::size_t size);

    //! \brief Encodes and writes one frame under the write lock.
    bool sendFrame(HelperPipe::MessageType type, const std::vector<uint8_t>& body);

    //! \brief Files one frame into the state; the caller holds mStateMutex.
    void handleFrameLocked(const HelperPipe::Frame& frame);

    //! \brief Wakes waiting threads and the event sinks after the state changed.
    void notifyStateChanged();

    //! \brief Whether takePeerData() would return data or disconnected; the caller holds mStateMutex.
    bool isPeerReadyLocked(uint64_t peerId) const;

    //! \brief Closes the game side of the pipe that the helper reads, so it sees the end of its input.
    void closeWriteEnd();

    //! \brief Terminates the child unless it has exited. Platform specific.
    void terminateChild();

    //! \brief Ends a blocking read of the reader thread on a pipe that another process keeps open. Platform specific.
    void unblockReader();

    //! \brief Waits for the child to end and returns its exit code. Platform specific, reader thread only.
    int waitForChildExit();

    //! \brief Releases the ended child after mExited is set (POSIX: waitpid). Platform specific, reader thread only.
    void reapChild();

    //! \brief Closes all remaining handles after the reader thread ended. Platform specific.
    void closeHandles();

    //! \brief Guards everything below up to mObserver; mStateChanged is notified on every change.
    mutable std::mutex mStateMutex;
    std::condition_variable mStateChanged;
    bool mStarted;
    bool mReady;
    bool mExited;
    int mExitCode;
    uint64_t mLocalUserId;
    uint64_t mLobbyId;
    uint64_t mHostUserId;
    bool mIsLobbyHost;
    //! \brief Counts lobbyFailed answers to lobbyJoin, so joinLobbyAndWait() sees a failure after its request.
    uint64_t mJoinFailures;
    std::deque<uint64_t> mPendingPeers;
    std::map<uint64_t, PeerState> mPeers;
    std::deque<LobbyEvent> mLobbyEvents;
    HelperLobbyObserver* mObserver;

    //! \brief Guards the sink list; held while the reader thread calls the sinks.
    std::mutex mSinkMutex;
    std::vector<HelperRelayEventSink*> mSinks;

    //! \brief Serializes frame writes from the server thread, the client and the lobby calls.
    std::mutex mWriteMutex;
    bool mWriteClosed;

    std::thread mReader;

#ifdef _WIN32
    //! \brief HANDLE values of the child process, the pipe the game writes and the pipe the game reads.
    void* mProcessHandle;
    void* mWriteHandle;
    void* mReadHandle;
#else
    //! \brief Process id of the child and the game end of the socket pair (both directions).
    int mPid;
    int mSocket;
#endif
};

#endif // OD_NET_HELPER_RELAY

#endif // HELPERRELAYPROCESS_H
