"""Multiplayer client robustness: lost server, pause in multiplayer, defeat exit, refused start, join port.

The runtime probe compiles source/network/MultiplayerClientRules.h as it is and checks its decisions against fixed
expected values (counted once on this branch: 8 session cases, 6 pause cases, 4 debriefing exits, 5 seat lists,
8 refusal reasons, 14 port inputs). The wiring part checks that the client, the frame listener, the defeat
debriefing, the lobby (with the startGameRefused answer of the server) and the join menu use these decisions. Use --source-only to skip the compiled probe.
"""
from pathlib import Path
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]


def read(relative):
    """Returns a repository text file with LF line ends."""
    return (ROOT / relative).read_text(encoding='utf-8').replace('\r\n', '\n')


def function(text, signature):
    """Returns one complete function of a source text, found by its signature."""
    start = text.index(signature)
    end = text.index('{', start) + 1
    depth = 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


PROBE = r'''
#include <iostream>
#include <string>
#include <vector>
#include "network/MultiplayerClientRules.h"

namespace R = MultiplayerClientRules;
int gChecks = 0;
int gFailures = 0;

//! \brief Counts one expectation and reports it when it fails.
void check(bool ok, const std::string& what)
{
    ++gChecks;
    if(!ok)
    {
        ++gFailures;
        std::cout << "FAIL " << what << std::endl;
    }
}

//! \brief Builds the choices of one lobby seat.
R::LobbySeatChoice seat(bool player, bool team, bool faction)
{
    R::LobbySeatChoice choice;
    choice.mPlayerChosen = player;
    choice.mTeamChosen = team;
    choice.mFactionChosen = faction;
    return choice;
}

//! \brief Reads a port with the default 32222 and returns -1 when it is refused.
long port(const std::string& text, uint32_t defaultPort = 32222)
{
    uint32_t value = 7;
    if(!R::parsePort(text, defaultPort, value))
        return value == 7 ? -1 : -2;
    return static_cast<long>(value);
}

int main()
{
    // Session: network client, local server running, local server is the multiplayer host
    check(!R::isMultiplayerSession(false, false, false), "replay or no client: not multiplayer");
    check(!R::isMultiplayerSession(false, true, false), "no network client beside a single player server");
    check(!R::isMultiplayerSession(false, true, true), "no network client beside a multiplayer server");
    check(!R::isMultiplayerSession(false, false, true), "no network client, no server");
    check(R::isMultiplayerSession(true, false, false), "joined a remote server: multiplayer");
    check(!R::isMultiplayerSession(true, true, false), "local single player, loaded game or editor server: not multiplayer");
    check(R::isMultiplayerSession(true, true, true), "host of a multiplayer game: multiplayer");
    check(R::isMultiplayerSession(true, false, true), "remote server, stale host flag: multiplayer");

    // Pause: game started, paused, exit requested, multiplayer
    check(R::pauseStopsNetwork(true, true, false, false), "a paused single player game stops reading the server");
    check(!R::pauseStopsNetwork(true, true, false, true), "a paused multiplayer game keeps reading the server");
    check(!R::pauseStopsNetwork(false, true, false, false), "before the first turn the server is read");
    check(!R::pauseStopsNetwork(true, true, true, false), "an exit request is handled even while paused");
    check(!R::pauseStopsNetwork(true, false, false, false), "a running single player game reads the server");
    check(!R::pauseStopsNetwork(true, false, false, true), "a running multiplayer game reads the server");

    // Defeat debriefing: campaign active, multiplayer
    check(R::debriefingExit(true, false) == R::DebriefingExit::campaignMenu, "campaign: campaign menu");
    check(R::debriefingExit(true, true) == R::DebriefingExit::campaignMenu, "campaign wins over multiplayer");
    check(R::debriefingExit(false, true) == R::DebriefingExit::multiplayerSubMenu, "multiplayer: multiplayer sub-menu");
    check(R::debriefingExit(false, false) == R::DebriefingExit::skirmishSubMenu, "skirmish: skirmish sub-menu");

    // Lobby seats
    std::vector<R::LobbySeatChoice> seats;
    check(!R::areSeatsFilled(seats), "no seat: not filled");
    seats.push_back(seat(true, true, true));
    seats.push_back(seat(true, true, true));
    check(R::areSeatsFilled(seats), "two complete seats: filled");
    seats[1] = seat(false, true, true);
    check(!R::areSeatsFilled(seats), "a seat without player: not filled");
    seats[1] = seat(true, false, true);
    check(!R::areSeatsFilled(seats), "a seat without team: not filled");
    seats[1] = seat(true, true, false);
    check(!R::areSeatsFilled(seats), "a seat without faction: not filled");

    // The reason codes of startGameRefused are fixed on the wire, and each has its lobby message
    check(static_cast<int32_t>(StartGameRefusal::Reason::seatsIncomplete) == 0, "seats incomplete is sent as 0");
    check(static_cast<int32_t>(StartGameRefusal::Reason::notHost) == 1, "not the host is sent as 1");
    check(static_cast<int32_t>(StartGameRefusal::Reason::wrongState) == 2, "wrong state is sent as 2");
    check(std::string(R::startRefusedMessage(0)) == R::SEATS_NOT_FILLED_MESSAGE, "seats incomplete: the seat message");
    check(std::string(R::startRefusedMessage(1)) == "Only the host can start the game.", "not the host: the host message");
    check(std::string(R::startRefusedMessage(2)) == "The game cannot be started now.", "wrong state: the state message");
    check(std::string(R::startRefusedMessage(3)) == "The server did not start the game.", "an unknown reason: the general message");
    check(std::string(R::startRefusedMessage(-1)) == "The server did not start the game.", "a negative reason: the general message");

    // Join port
    check(port("") == 32222, "empty: the configured port");
    check(port("   ") == 32222, "only spaces: the configured port");
    check(port("", 0) == -1, "empty with an invalid configured port: refused");
    check(port("", 70000) == -1, "empty with a configured port above 65535: refused");
    check(port("32223") == 32223, "a typed port");
    check(port(" 4000 ") == 4000, "spaces around the port are ignored");
    check(port("1") == 1, "the lowest port");
    check(port("65535") == 65535, "the highest port");
    check(port("0") == -1, "port 0: refused");
    check(port("65536") == -1, "above 65535: refused");
    check(port("99999999999") == -1, "a long number: refused without overflow");
    check(port("12a") == -1, "letters: refused");
    check(port("-1") == -1, "a sign: refused");
    check(port("80 81") == -1, "two numbers: refused");

    std::cout << "CHECKS=" << gChecks << " FAILURES=" << gFailures << std::endl;
    return gFailures == 0 && gChecks == 45 ? 0 : 1;
}
'''


def compile_probe():
    """Compiles and runs the rules probe without building the game."""
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix='odp-mp-client-robustness-') as directory:
        work = Path(directory)
        (work / 'check.cpp').write_text(PROBE, encoding='utf-8')
        args = ['cl', '/nologo', '/EHsc', '/MD', '/O2', '/W3',
                '/I' + str(ROOT / 'source'), 'check.cpp', '/Fecheck.exe']
        if shutil.which('cl'):
            subprocess.run(args, cwd=work, check=True, stdout=subprocess.DEVNULL)
        else:
            vcvars = Path(os.environ['ProgramFiles(x86)']) / 'Microsoft Visual Studio/18/BuildTools/VC/Auxiliary/Build/vcvars64.bat'
            batch = work / 'compile.cmd'
            batch.write_text('@echo off\ncall "' + str(vcvars) + '" >nul\n' +
                             subprocess.list2cmdline(args) + '\nexit /b %errorlevel%\n', encoding='utf-8')
            subprocess.run(['cmd', '/d', '/c', str(batch)], cwd=work, check=True, stdout=subprocess.DEVNULL)
        print('ODP_TEST_PHASE {"name":"compile","seconds":%.3f}' % (time.monotonic() - started))
        started = time.monotonic()
        subprocess.run([str(work / 'check.exe')], cwd=work, check=True, timeout=30)
        print('ODP_TEST_PHASE {"name":"probe","seconds":%.3f}' % (time.monotonic() - started))


# 1. Lost server: the client stops itself once in multiplayer, the frame listener returns to the main menu
client = read('source/network/ODClient.cpp')
lost = function(client, 'void ODClient::playerDisconnected()')
assert lost.index('if(isMultiplayerSession())') < lost.index('disconnect();') < lost.index('mServerLost = true;') \
    < lost.index('return;') < lost.index('addEventMessage('), 'multiplayer stops the client before the old event message'
session = function(client, 'bool ODClient::isMultiplayerSession()')
assert 'getSource() == ODSource::network' in session and 'ServerMode::ModeGameMultiPlayer' in session \
    and 'MultiplayerClientRules::isMultiplayerSession(' in session
consume = function(client, 'bool ODClient::consumeServerLost()')
assert 'mServerLost = false;' in consume
assert 'mServerLost(false)' in client
listener = read('source/render/ODFrameListener.cpp')
queued = function(listener, 'bool ODFrameListener::frameRenderingQueued(')
assert '(currentTurn != -1) && (mGameMap->getGamePaused()) && (!mExitRequested)' not in queued
socket = queued.index('processClientSocketMessages(0);')
assert queued.index('MultiplayerClientRules::pauseStopsNetwork(') < socket, 'the pause decision comes before the socket read'
assert 'isMultiplayerSession()' in queued[:socket]
assert socket < queued.index('consumeServerLost()') < queued.index('returnToMenuAfterLostServer();') \
    < queued.index('processClientNotifications();'), 'the lost server is handled right after the socket read'
back = function(listener, 'void ODFrameListener::returnToMenuAfterLostServer()')
assert 'setMainMenuNotice(MultiplayerClientRules::LOST_SERVER_MESSAGE);' in back
assert back.index('setMainMenuNotice(') < back.index('requestMainMenuWithMultiplayerSubMenu();')
print('LOST SERVER OK: one disconnect, one return to the main menu with its message')

# 2. The main menu shows the message once and opens the multiplayer sub-menu after its flight
menu = read('source/modes/MenuModeMain.cpp')
activate = function(menu, 'void MenuModeMain::activate()')
assert activate.index('consumeSkirmishSubMenuRequest()') < activate.index('consumeMultiplayerSubMenuRequest()') \
    < activate.index('consumeMainMenuNotice()') < activate.index('giveFocus();')
assert 'noticeText->setVisible(!notice.empty());' in activate and 'mMultiplayerSubMenuPending = true;' in activate
assert 'mSkirmishSubMenuPending || mMultiplayerSubMenuPending' in activate
assert 'toggleSubMenu(WINDOW_MULTIPLAYER);' in function(menu, 'void MenuModeMain::onFrameStarted(')
assert 'mMultiplayerSubMenuPending = false;' in function(menu, 'bool MenuModeMain::changeModeAfterFlight(')
assert 'const std::string TEXT_NOTICE = "NoticeText";' in menu
main_layout = ET.parse(ROOT / 'gui/MenuMain.layout').getroot()
notice = [w for w in main_layout.iter('Window') if w.get('name') == 'NoticeText']
assert len(notice) == 1 and notice[0].get('type') == 'OD/StaticText'
assert {p.get('name'): p.get('value') for p in notice[0].findall('Property')}.get('Visible') == 'False'
print('MAIN MENU OK: hidden notice text, multiplayer sub-menu after the arrival flight')

# 3. The defeat debriefing of a multiplayer game leads to the multiplayer sub-menu
confirm = function(read('source/modes/GameMode.cpp'), 'bool GameMode::onClickDefeatDebriefingConfirm(')
assert 'MultiplayerClientRules::debriefingExit(' in confirm and 'ODClient::getSingleton().isMultiplayerSession()' in confirm
assert 'requestMainMenuWithMultiplayerSubMenu();' in confirm and 'requestMainMenuWithSkirmishSubMenu();' in confirm \
    and 'MENU_CAMPAIGN' in confirm
print('DEBRIEFING OK: campaign, multiplayer and skirmish exits')

# 4. The lobby shows the loading picture only in single player and shows at once why the server refused the start
seats = read('source/modes/MenuModeConfigureSeats.cpp')
launch = function(seats, 'bool MenuModeConfigureSeats::launchSelectedButtonPressed(')
multiplayer = launch.index('if(ODClient::getSingleton().isMultiplayerSession())')
picture = launch.index('LoadingScreen loading;')
assert multiplayer < launch.index('areSeatsFilled(collectSeatChoices())') < launch.index('SEATS_NOT_FILLED_MESSAGE') \
    < launch.index('ClientNotificationType::seatConfigurationSet') < picture, \
    'in multiplayer the start is only asked for with filled seats, without the loading picture'
assert launch.count('LoadingScreen loading;') == 1
# The server answers a refused start, so the lobby has no timeout any more
assert 'void MenuModeConfigureSeats::onFrameStarted(' not in seats and 'mLaunchPending' not in seats
refused = function(seats, 'void MenuModeConfigureSeats::showStartRefused(int32_t reasonValue)')
assert refused.index('LoadingScreen::finish();') < refused.index('showLobbyMessage(MultiplayerClientRules::startRefusedMessage(reasonValue));')
assert 'void showStartRefused(int32_t reasonValue);' in read('source/modes/MenuModeConfigureSeats.h')
answer = client[client.index('case ServerNotificationType::startGameRefused:'):]
answer = answer[:answer.index('\n        case ServerNotificationType::')]
assert answer.index('if(!(packetReceived >> reasonValue))') < answer.index('ModeManager::ModeType::MENU_CONFIGURE_SEATS') \
    < answer.index('mode->showStartRefused(reasonValue);'), 'the client reads the reason and shows it in the lobby'
choices = function(seats, 'MenuModeConfigureSeats::collectSeatChoices()')
for prefix in ('COMBOBOX_PLAYER_PREFIX', 'COMBOBOX_TEAM_ID_PREFIX', 'COMBOBOX_PLAYER_FACTION_PREFIX'):
    assert prefix in choices, prefix
print('LOBBY OK: no loading picture before a multiplayer start, messages for unfilled seats and the refusal reason')

# 5. The join menu has an optional, validated port
client_menu = read('source/modes/MenuModeMultiplayerClient.cpp')
pressed = function(client_menu, 'bool MenuModeMultiplayerClient::clientButtonPressed(')
assert pressed.index('MultiplayerClientRules::parsePort(') < pressed.index('INVALID_PORT_MESSAGE') \
    < pressed.index('ODClient::getSingleton().connect(ip, static_cast<int>(port)'), 'the port is checked before connecting'
assert 'getNetworkPort()' in pressed and 'getNetworkPort()' in function(client_menu, 'void MenuModeMultiplayerClient::activate()')
assert 'const std::string Gui::MPM_EDIT_PORT = "LevelWindowFrame/PortEdit";' in read('source/render/Gui.cpp')
frame_window = [w for w in ET.parse(ROOT / 'gui/MenuMultiplayerClient.layout').getroot().iter('Window')
                if w.get('name') == 'LevelWindowFrame'][0]
children = {w.get('name'): w.get('type') for w in frame_window.findall('Window')}
assert children.get('PortEdit') == 'OD/Editbox' and children.get('PortText') == 'OD/StaticText'
print('JOIN MENU OK: optional port field, validated before connecting')

assert re.search(r'\bauto\b', PROBE) is None and re.search(r'\bauto\b', read('source/network/MultiplayerClientRules.h')) is None

if '--source-only' not in sys.argv:
    compile_probe()
print('check_mp_client_robustness: ok')
