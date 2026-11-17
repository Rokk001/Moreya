"""Compile the actual network test wait methods against deterministic clocks and sockets."""
from pathlib import Path
import os
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
source = (ROOT / 'source/tests/mocks/ODClientTest.cpp').read_text()


# Extract an actual C++ method for the deterministic dependency fixture.
def function(signature):
    start = source.index(signature)
    opening = source.index('{', start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


probe = r'''
#include <string>
#include <cstdint>
#include <stdexcept>
static int ticks=0, attempts=0, readyAt=0, sleeps=0, binds=0, freeAt=0, errors=0, closes=0, disconnects=0, sends=0;
namespace sf {
//! \brief Exposes deterministic elapsed milliseconds.
struct Time { int value; int asMilliseconds() const { return value; } };
//! \brief Constructs the fixture time value.
Time milliseconds(int value) { return Time{value}; }
//! \brief Advances simulated time without wall-clock waiting.
void sleep(Time value) { ticks+=value.value; ++sleeps; }
//! \brief Measures elapsed simulated time.
struct Clock { int start=ticks; Time getElapsedTime() const { return Time{ticks-start}; } };
//! \brief Supplies the socket status values used by production.
struct Socket { enum class Status {Done, Error}; };
//! \brief Simulates release of the local test listener.
struct TcpListener {
    //! \brief Counts bind attempts and releases at the configured attempt.
    Socket::Status listen(unsigned short port) { ++binds; if(port!=32222) throw std::runtime_error("wrong port"); return binds>=freeAt ? Socket::Status::Done : Socket::Status::Error; }
    //! \brief Records closing the temporary listener.
    void close() { ++closes; }
};
}
#define BOOST_ERROR(message) (++errors)
#define OD_LOG_INF(message) ((void)0)
//! \brief Accepts handshake fields without networking.
struct ODPacket { template<class T> ODPacket& operator<<(const T&) { return *this; } };
enum class ClientNotificationType {hello};
static const std::string OD_VERSION_STR="test";
//! \brief Supplies the network record schema suffix that the hello names.
namespace NetworkProtocol { static const std::string WIRE_SCHEMA_SUFFIX=" / wire-test"; }
//! \brief Simulates server connection readiness.
struct ODSocketClient {
    //! \brief Rejects unbounded attempts and returns configured readiness.
    bool connect(const std::string&, int, uint32_t timeout, const std::string&) {
        if(timeout==0 || timeout>5000) throw std::runtime_error("unbounded attempt");
        return ++attempts>=readyAt;
    }
    //! \brief Records the base disconnect call.
    void disconnect(bool) { ++disconnects; }
};
//! \brief Hosts the actual production wait methods in the fixture.
struct ODClientTest: ODSocketClient {
    int mLocalServerPort=0;
    bool connect(const std::string&, int, uint32_t, const std::string&);
    void disconnect(bool);
    //! \brief Records exactly one hello after connection succeeds.
    void send(ODPacket&) { ++sends; }
};
FUNCTIONS
//! \brief Fails the fixture on any incorrect wait result.
void check(bool value) { if(!value) throw std::runtime_error("network wait regression"); }
//! \brief Resets all deterministic dependency state.
void reset() { ticks=attempts=sleeps=binds=errors=closes=disconnects=sends=0; readyAt=freeAt=1; }
//! \brief Exercises readiness and failure cases with bounded execution.
int main() {
    ODClientTest client;
    reset(); check(client.connect("localhost",32222,10,"")); check(attempts==1 && sleeps==0 && sends==1);
    client.disconnect(false); check(binds==1 && sleeps==0 && disconnects==1 && closes==1 && errors==0);
    reset(); readyAt=3; check(client.connect("localhost",32222,10,"")); check(attempts==3 && sleeps==2 && ticks==100);
    freeAt=3; client.disconnect(false); check(binds==3 && ticks==200 && errors==0);
    reset(); readyAt=1000; check(!client.connect("localhost",32222,10,"")); check(ticks==5000 && attempts==100 && sends==0);
    reset(); client.mLocalServerPort=32222; freeAt=1000; client.disconnect(false); check(errors==1 && ticks==5000 && binds==101);
    reset(); client.mLocalServerPort=0; client.disconnect(false); check(disconnects==1 && sleeps==0 && binds==0);
    reset(); check(client.connect("localhost",32222,0,"")); check(attempts==1);
    return 0;
}
'''.replace('FUNCTIONS', function('bool ODClientTest::connect(') + '\n' + function('void ODClientTest::disconnect('))
with tempfile.TemporaryDirectory(prefix='odp-network-waits-') as temporary:
    work = Path(temporary)
    (work / 'probe.cpp').write_text(probe)
    subprocess.run(['cl', '/nologo', '/EHsc', '/std:c++17', 'probe.cpp', '/Feprobe.exe'], cwd=work, check=True, timeout=60)
    subprocess.run([str(work / 'probe.exe')], cwd=work, check=True, timeout=10)
    # Verify that the real socket library rejects an occupied listener and accepts its release.
    (work / 'port.cpp').write_text(r'''
#include <SFML/Network.hpp>
//! \brief Exercises readiness and failure cases with bounded execution.
int main() {
    sf::TcpListener owner;
    sf::TcpListener candidate;
    if(owner.listen(0) != sf::Socket::Status::Done) return 1;
    const unsigned short port = owner.getLocalPort();
    if(candidate.listen(port) == sf::Socket::Status::Done) return 2;
    owner.close();
    if(candidate.listen(port) != sf::Socket::Status::Done) return 3;
    return 0;
}
''')
    deps = Path(os.environ.get('BUILD_DEPS_ROOT') or Path.home() / 'build-deps') / 'install'
    subprocess.run(['cl', '/nologo', '/EHsc', '/std:c++17', '/MD', '/I' + str(deps / 'include'),
                    'port.cpp', '/Feport.exe', '/link', '/LIBPATH:' + str(deps / 'lib'),
                    'sfml-network.lib', 'sfml-system.lib'], cwd=work, check=True, timeout=60)
    environment = dict(os.environ)
    environment['PATH'] = str(deps / 'bin') + os.pathsep + environment.get('PATH', '')
    subprocess.run([str(work / 'port.exe')], cwd=work, env=environment, check=True, timeout=10)
print('PASS: immediate/delayed connection and port release, both deadlines, disconnected client and bounded zero-timeout connection')
