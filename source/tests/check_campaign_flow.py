"""Static check of two campaign flow rules: new campaign confirmation and the way out of a lost level.

The interface files (gui/) are files of the content packages (scripts/content_packages.py); without content their
parts are named as not checked and the code parts are checked alone. The public tree holds no wing, so without content
the campaign has no level.
"""
from pathlib import Path
import sys

repo = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo / 'scripts'))
import campaign_packages  # noqa: E402
import content_packages  # noqa: E402
# The wing packages of the content repository; without them the public tree has no campaign level
has_content = campaign_packages.has_content(repo)


def read(path):
    """A file of the repository as text."""
    return (repo / path).read_text(encoding='utf-8')


def read_data(path):
    """A game data file from the public tree or a content package as text, None without content. A mixed interface
    file (gui/ModeGame.layout, gui/ODSkin.scheme, ...) comes with its own rows from the content packages; without the
    content its own rows are missing, so it counts as not present as well."""
    found = content_packages.data_file(repo, path)
    if not found:
        return None
    if not content_packages.has_content(repo) and '<!--#@own ' in found.read_text(encoding='utf-8'):
        return None
    return content_packages.read_text(repo, path)


layout = read_data('gui/WindowCampaignSubMenu.layout')
menu = read('source/modes/MenuModeMain.cpp')
game = read('source/modes/GameMode.cpp')

# The confirmation widgets exist, start hidden and are the ones the code looks up.
for name in ('NewCampaignConfirmText', 'NewCampaignConfirmButton'):
    if layout is not None:
        start = layout.index('name="%s"' % name)
        assert 'name="Visible" value="False"' in layout[start:layout.index('</Window>', start)], name
    assert '"%s"' % name in menu, name
if layout is None:
    assert not content_packages.has_content(repo), 'gui/WindowCampaignSubMenu.layout is missing although the content is present'
    content_packages.unchecked('campaign flow', ['gui/WindowCampaignSubMenu.layout'])

# Progress is only reset by the confirmation (or at once when there is nothing to lose).
pressed = menu[menu.index('bool MenuModeMain::newCampaignPressed('):menu.index('bool MenuModeMain::newCampaignConfirmed(')]
assert 'hasProgress()' in pressed and 'resetProgress' not in pressed
confirmed = menu[menu.index('bool MenuModeMain::newCampaignConfirmed('):menu.index('void MenuModeMain::showNewCampaignConfirm(')]
assert 'resetProgress()' in confirmed

# A lost campaign level leads back to the campaign menu, anything else to the skirmish sub-menu.
defeat = game[game.index('bool GameMode::onClickDefeatDebriefingConfirm('):game.index('bool GameMode::onClickYesQuitMenu(')]
assert 'Campaign::getSingleton().isActive()' in defeat
assert 'MENU_CAMPAIGN' in defeat and 'requestMainMenuWithSkirmishSubMenu()' in defeat
# A seat whose only goal is to protect its temple must not win at once: the level script wins the hero levels
game_map = read('source/gamemap/GameMap.cpp')
assert 'hasCompletedWinningGoal(seat))' in game_map and '!= "ProtectDungeonTemple"' in game_map
# The Heartstone has three shards, hidden in level 2 of wings 1 to 3 (Coldwell, Greywater, Saltmere);
# the six bonus levels (one per wing) carry none, their reward is the item unlock at the merchant.
# Without content the public tree has no wing, so no bonus level and no shard.
campaign = campaign_packages.definition_text(repo)
blocks = [e for e in campaign.replace(chr(13), '').split('[Level]')[1:] if 'File=' in e]
entries = [e for e in blocks if 'Bonus=1' in e]
assert len(entries) == (6 if has_content else 0)
assert not any('Shard=1' in e for e in entries)
pieces = [e for e in blocks if 'Shard=1' in e]
assert len(pieces) == (3 if has_content else 0)
for piece, file in zip(pieces, ('campaign/Coldwell.level', 'campaign/Greywater.level', 'campaign/Saltmere.level')):
    assert 'File=' + file in piece, file
assert 'Heartstone=' not in campaign
assert 'key == "Shard"' in read('source/game/Campaign.cpp') and 'key == "Heartstone"' not in read('source/game/Campaign.cpp')
# The complete Heartstone gives the keepers the Summon champion spell in the levels with Champion=1 (every level
# from wing 4 on) when a campaign level starts
server = read('source/network/ODServer.cpp')
assert 'isLevelChampionAvailable()' in server and 'SkillType::spellSummonChampion, championAvailable, championAvailable' in server
assert [('Champion=1' in e) for e in blocks if 'File=' in e] == ([False] * 12 + [True] * 12 if has_content else [])
campaign_state = read('source/game/Campaign.cpp')
assert 'return mSavedChampionAvailable;' in campaign_state and 'return isChampionAvailableNoLock(mPlayedLevel);' in campaign_state
assert 'return mLevels[index].mChampion;' in campaign_state
# Victory keeps its authoritative goal list and saves progress before notifying the client.
victory = game_map[game_map.index('void GameMap::addWinningSeat('):game_map.index('bool GameMap::seatIsAWinner(')]
assert victory.index('mWinningSeats.push_back(s)') < victory.index('getGoalsStringForPlayer(player)')
assert victory.index('sendLevelStatistics(true)') < victory.index('onLevelWon(campaignUnlockCandidates(*this), &drawCampaignUnlock)') < victory.index('ServerNotificationType::campaignVictory')
assert 'Open the menu and quit' not in victory
goals = game_map[game_map.index('std::string GameMap::getGoalsStringForPlayer('):game_map.index('double GameMap::addGoldToSeat(')]
assert 'else if (seat->numFailedGoals()' not in goals
for state in ('Open', 'Reached', 'Failed'):
    assert "[image='GoalStatus/" + state + "'] " in goals, state
for old_label in ('Open: ', 'Done: ', 'Failed: '):
    assert old_label not in goals, old_label
assert 'Victory!\\n' in goals
assert 'script.getTriggers()' in goals and 'LevelScriptActionType::objective' in goals
assert 'action.mSeatId >= 0 && action.mSeatId != seat->getId()' in goals
assert 'Script objectives:' not in goals and 'scriptObjectives.push_back(action.mText)' in goals
assert 'scriptObjectives.push_back(stateMark + action.mText)' in goals
assert 'stateMark = reachedGoalMark' in goals and 'stateMark = failedGoalMark' in goals
assert 'stateText' not in goals
assert 'getObjectiveState(seat->getId(), action.mObjectiveId)' in goals
script_header = read('source/gamemap/LevelScript.h')
script_source = read('source/gamemap/LevelScript.cpp')
script_runner = read('source/gamemap/LevelScriptRunner.cpp')
assert 'std::string mObjectiveId;' in script_header and 'objectiveState' in script_header
# The legacy ID parser now also accepts the explicitly classified goal variants.
objective_parser = script_source[script_source.index('bool parseAction('):script_source.index('if(type == "objectivestate")')]
for keyword in ('objectiveid', 'mainobjectiveid', 'optionalobjectiveid', 'conditionalobjectiveid'):
    assert 'type == "' + keyword + '"' in objective_parser
assert 'action.mObjectiveId = t[3];' in objective_parser
assert 'if(type == "objectivestate")' in script_source
assert 'if((type == "message") || (type == "objective"))' in script_source
assert 'if(key == "ObjectiveState")' in script_source and 'os << "ObjectiveState\\t"' in script_source
assert 'mObjectiveStates.clear()' in script_source
assert 'script.setObjectiveState(player->getSeat()->getId(), action.mObjectiveId' in script_runner

# Each normal turn sends the objective text regardless of the seat's old goal-dirty flag.
server = read('source/network/ODServer.cpp')
snapshot_start = server.index('// We notify the clients about what they got')
snapshot = server[snapshot_start:server.index('notifyHeartHealth(gameMap, sock, player)', snapshot_start)]
assert 'for (ODSocketClient* sock : mSockClients)' in snapshot
assert 'ServerNotificationType::refreshPlayerSeat' in snapshot
assert 'std::string goals = gameMap->getGoalsStringForPlayer(player);' in snapshot
assert 'serverNotification->mPacket << goals;' in snapshot
assert 'getHasGoalsChanged' not in snapshot
client_source = read('source/network/ODClient.cpp')
refresh = client_source[client_source.index('case ServerNotificationType::refreshPlayerSeat:'):client_source.index('case ServerNotificationType::creaturePanel:')]
assert 'packetReceived >> goalsString' in refresh and 'refreshMainUI(goalsString)' in refresh
refresh_ui = client_source[client_source.index('void ODClient::refreshMainUI('):client_source.index('bool ODClient::connect(')]
assert 'gm->refreshPlayerGoals(goalsString);' in refresh_ui and 'getHasGoalsChanged' not in refresh_ui

# The approved status marks are graphical, registered, scalable, and separate from text labels.
import xml.etree.ElementTree as ET
from PIL import Image
scheme_text = read_data('gui/ODSkin.scheme')
atlas_text = read_data('gui/GoalStatus.imageset')
if scheme_text is not None and atlas_text is not None:
    scheme = ET.fromstring(scheme_text)
    assert scheme.find("Imageset[@filename='GoalStatus.imageset']") is not None
    atlas = ET.fromstring(atlas_text)
    assert atlas.get('autoScaled') == 'true'
    assert atlas.get('nativeHorzRes') == '1024' and atlas.get('nativeVertRes') == '768'
    marks = {item.get('name'): item for item in atlas.findall('Image')}
    assert set(marks) == {'Open', 'Reached', 'Failed'}
    with Image.open(content_packages.resolve(repo, 'gui/' + atlas.get('imagefile'))) as artwork:
        assert artwork.mode == 'RGBA' and artwork.size == (60, 20)
        assert artwork.getpixel((0, 0))[3] == 0
        for index, state in enumerate(('Open', 'Reached', 'Failed')):
            mark = marks[state]
            assert [int(mark.get(key)) for key in ('xPos', 'yPos', 'width', 'height')] == [index * 20, 0, 20, 20]
            pixels = [artwork.getpixel((x, y)) for y in range(20) for x in range(index * 20, (index + 1) * 20)]
            if state == 'Reached':
                assert any(g > 140 and g > r * 1.5 and g > b * 1.5 and a > 200 for r, g, b, a in pixels)
            if state == 'Failed':
                assert any(r > 160 and r > g * 1.5 and r > b * 1.5 and a > 200 for r, g, b, a in pixels)
else:
    assert not content_packages.has_content(repo), 'the goal status art is missing although the content is present'
    content_packages.unchecked('campaign flow', ['gui/ODSkin.scheme', 'gui/GoalStatus.imageset'])
assert 'startsWith(name, "GoalStatus/")' in read('source/render/Gui.cpp')
# The goal marks are credited where they lie: CREDITS of the repository, or of the content repository for the files
# of a content package
goal_art = content_packages.data_file(repo, 'gui/GoalStatus.png')
assert goal_art is not None or not content_packages.has_content(repo), 'gui/GoalStatus.png is missing'
if goal_art is not None:
    public_art = goal_art.resolve().is_relative_to(repo.resolve())
    credits_text = read('CREDITS') if public_art else         (campaign_packages.content_repository(repo) / 'CREDITS').read_text(encoding='utf-8')
    assert 'gui/GoalStatus.svg, gui/GoalStatus.png' in credits_text
briefing = read('source/modes/MenuModeCampaign.cpp')
assert "[image='GoalStatus/Open'] " in briefing
assert 'Open: ' not in briefing

# A new minimap entry uses existing artwork and the same objectives toggle.
import xml.etree.ElementTree as ET
hud_text = read_data('gui/ModeGame.layout')
if hud_text is not None:
    hud = ET.fromstring(hud_text)
    button = hud.find(".//Window[@name='GoalsButton']")
    assert button is not None
    properties = {item.get('name'): item.get('value') for item in button.findall('Property')}
    assert properties['TooltipText'] == 'Goals'
    assert properties['NormalImage'] == 'OpenDungeonsIcons/ObjectivesIcon'
    assert properties['Area'] == '{{0,4},{1,-224},{0,44},{1,-184}}'
else:
    assert not content_packages.has_content(repo), 'gui/ModeGame.layout is missing although the content is present'
    content_packages.unchecked('campaign flow', ['gui/ModeGame.layout'])
connection = game[game.index('guiSheet->getChild("GoalsButton")'):]
connection = connection[:connection.index('//Casino payout window')]
assert '&GameMode::toggleObjectivesWindow' in connection

# Only the saved campaign victory opens the existing result and its explicit map confirmation.
notification = read('source/network/ServerNotification.h')
enum = notification[notification.index('enum class ServerNotificationType'):notification.index('ODPacket& operator<<')]
assert enum.index('timeLimit,') < enum.index('campaignVictory')
client = read('source/network/ODClient.cpp')
packet = client[client.index('case ServerNotificationType::campaignVictory:'):client.index('case ServerNotificationType::timeLimit:')]
assert 'std::string goalsDisplay;' in packet and 'packetReceived >> goalsDisplay' in packet
assert 'showCampaignVictory(goalsDisplay)' in packet
result = game[game.index('void GameMode::showCampaignVictory('):game.index('bool GameMode::onClickDefeatDebriefingConfirm(')]
assert '!Campaign::getSingleton().isActive()' in result and 'mDefeatDebriefing != nullptr' in result
assert result.index('refreshPlayerGoals(goalsDisplay)') < result.index('showDefeatDebriefing()')
assert 'requestMode(AbstractModeManager::MENU_CAMPAIGN)' in result
print('campaign flow: ok')
