"""Check that a frame reads the server messages without waiting for one. It does not start a game.

The frame used to call processClientSocketMessages() with its default timeout of 5 ms. When no server message was
waiting, every frame waited out the selector timeout (about 11 ms with the coarse system timer). The frame now
passes timeout 0, and a timeout of 0 receives on the socket without blocking instead of waiting on the selector
(a selector wait of zero would block until data comes). Other callers keep their timeout.
The socket is reached through the transport connection (mConnection); the TCP backend passes the blocking mode and
the receive status of the SFML socket through unchanged.
"""
from pathlib import Path
import re
import sys

repo = Path(__file__).resolve().parents[2]
listener = (repo / 'source/render/ODFrameListener.cpp').read_text(encoding='utf-8')
client = (repo / 'source/network/ODSocketClient.cpp').read_text(encoding='utf-8')
tcp = (repo / 'source/network/TcpNetTransport.cpp').read_text(encoding='utf-8')
editor = (repo / 'source/modes/EditorMode.cpp').read_text(encoding='utf-8')


def function(text, signature):
    start = text.index(signature)
    end = text.index('{', start) + 1
    depth = 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


queued = function(listener, 'bool ODFrameListener::frameRenderingQueued(')
calls = re.findall(r'processClientSocketMessages\(([^)]*)\)', queued)
assert calls == ['0'], 'the frame must read the server messages with timeout 0, found %s' % calls

one = function(client, 'bool ODSocketClient::processOneClientSocketMessage(')
poll = one.index('(miliseconds <= 0) && (mSource == ODSource::network)')
wait = one.index('isDataAvailable(miliseconds)')
assert poll < wait, 'timeout 0 must be handled before the selector wait'
branch = one[poll:wait]
assert 'mConnection->setBlocking(false);' in branch, 'timeout 0 must receive without blocking'
assert branch.index('mConnection->setBlocking(false);') < branch.index('recv(packetReceived)') \
    < branch.index('mConnection->setBlocking(true);'), 'the socket must be blocking again after the poll'
assert 'comStatus == ODComStatus::NotReady' in branch and 'return false;' in branch, \
    'no waiting message must end the loop without a disconnect'
assert 'playerDisconnected();' in one[wait:], 'a receive error must still disconnect'

# recv reports NotReady only for a non blocking socket, which the poll relies on
receive = function(client, 'ODSocketClient::ODComStatus ODSocketClient::recv(')
assert '(!mConnection->isBlocking()) &&' in receive and 'return ODComStatus::NotReady;' in receive

# The TCP backend hands the blocking mode and the receive status of the socket through
assert 'mSocket.setBlocking(blocking);' in function(tcp, 'void TcpNetConnection::setBlocking(')
assert 'return mSocket.isBlocking();' in function(tcp, 'bool TcpNetConnection::isBlocking(')
assert 'return toNetStatus(mSocket.receive(packet.mPacket));' in function(tcp, 'NetStatus TcpNetConnection::receive(')
assert 'case sf::Socket::Status::NotReady:\n            return NetStatus::NotReady;' in tcp

# The editor keeps its own timeout of 75 ms
assert editor.count('processClientSocketMessages(75);') == 2, 'the editor timeout changed'

print('frame socket poll ok: frame timeout 0, non blocking receive, editor timeout 75 ms kept')
sys.exit(0)
