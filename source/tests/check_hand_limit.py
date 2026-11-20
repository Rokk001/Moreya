#!/usr/bin/env python3
"""Non-compiling check of the hand limit in the campaign (raid plan R11, HL1 with V1/C5 config, C3 saving, C4 every
keeper, C8 skirmish and multiplayer unchanged; HL2 message on a refused pickup and cooldown at the hand, C6 screen
sizes and UI scales).

A Python model of HandLimitRules plays fixed scenarios (second fighting creature refused, Zivs not limited, cooldown
after a drop, skirmish and multiplayer unchanged, the cooldown carried through a save and a load with the [HandCooldown]
block, an old save without the block, the refusal messages, the text at the hand and its place on screens from 640x480
to 7680x4320 at UI scale 80-120 %), and the C++ sources, the config and the build lists are checked for the
statements that implement them. Nothing is compiled and the game is not started; the integration build compiles the
code and runs the Boost test 00-HandLimitRules.

Usage: python -I source/tests/check_hand_limit.py
Exit 0 and "hand limit ok" when every item holds.
"""
import math
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
START = time.perf_counter()
FAILURES = []


def read(relative):
    """Returns the text of a file of the repository."""
    with open(os.path.join(ROOT, relative), encoding="utf-8") as handle:
        return handle.read()


def function(source, signature):
    """Returns the body of the function that starts with the signature (up to its closing brace)."""
    start = source.index(signature)
    brace = source.index("{", start)
    depth = 0
    for position in range(brace, len(source)):
        if source[position] == "{":
            depth += 1
        elif source[position] == "}":
            depth -= 1
            if depth == 0:
                return source[start:position + 1]
    raise AssertionError("no end of " + signature)


def check(condition, message):
    """Records a failed item."""
    if not condition:
        FAILURES.append(message)


GLOBAL_CFG = read("config/global.cfg")
CONFIG_MANAGER = read("source/utils/ConfigManager.cpp")
CONFIG_MANAGER_H = read("source/utils/ConfigManager.h")
RULES_H = read("source/game/HandLimitRules.h")
RULES = read("source/game/HandLimitRules.cpp")
PLAYER = read("source/game/Player.cpp")
PLAYER_H = read("source/game/Player.h")
SEAT = read("source/game/Seat.cpp")
SEAT_H = read("source/game/Seat.h")
SERVER = read("source/network/ODServer.cpp")
AI_ACTIONS = read("source/ai/AiActions.cpp")
AI_PRISON = read("source/ai/AiPrison.cpp")
CMAKE = read("CMakeLists.txt")
TESTS_CMAKE = read("source/tests/CMakeLists.txt")
BOOST_TEST = read("source/tests/test_HandLimitRules.cpp")
SAVE_CHECK = read("source/tests/check_save_games_load.py")

# ------------------------------------------------------------------------------------------------ V1 / C5 config
# The keys of the [HandLimit] block counted once for this branch: value and whether the simulation still sets it
EXPECTED_KEYS = {
    "HandLimitFighters": ("1", False),
    "HandLimitCooldownSeconds": ("10", True),
}
block = re.search(r"^\[HandLimit\]\n(.*?)^\[/HandLimit\]", GLOBAL_CFG, re.M | re.S)
check(block is not None, "V1: global.cfg has a [HandLimit] block")
values = dict(re.findall(r"^\s+(\w+)\t(\S+)$", block.group(1), re.M)) if block else {}
check(values == {key: value for key, (value, _) in EXPECTED_KEYS.items()}, "V1: [HandLimit] keys " + repr(values))
for key, (_, simulated) in EXPECTED_KEYS.items():
    doc = re.search(r"^# " + key + r" +(.+)$", GLOBAL_CFG, re.M)
    check(doc is not None, "V1: documentation line of " + key)
    if doc is not None:
        marked = "PLACEHOLDER: set by simulation R3C" in doc.group(1)
        check(marked == simulated, "C5: placeholder mark of " + key + " (the simulation R3C sets the cooldown)")
header = GLOBAL_CFG[:GLOBAL_CFG.index("[HandLimit]")].rsplit("[/Raid]", 1)[1]
check("campaign level" in header and "Zivs" in header and "Skirmish and" in header and "multiplayer" in header,
      "V1: the block comment names the campaign, the Zivs and skirmish and multiplayer")
check('nextParam == "[HandLimit]"' in function(CONFIG_MANAGER, "bool ConfigManager::loadGlobalConfig("),
      "V1: global.cfg reads the [HandLimit] block")
check('readGlobalNumberBlock(configFile, "[/HandLimit]", mHandLimitConfig)' in CONFIG_MANAGER,
      "V1: the [HandLimit] block is read up to its end tag")
check("double getHandLimitConfigDouble(const std::string& param) const;" in CONFIG_MANAGER_H
      and "std::map<std::string, double> mHandLimitConfig;" in CONFIG_MANAGER_H, "V1: ConfigManager keeps the block")
for key in EXPECTED_KEYS:
    check('getHandLimitConfigDouble("' + key + '")' in PLAYER, "V1: Player reads " + key + " from the config")
check(re.search(r"\b(?:HandLimitFighters|HandLimitCooldownSeconds)\b\s*=\s*\d", PLAYER + RULES) is None,
      "V1: no fixed hand limit value in code")


# ------------------------------------------------------------------------------------------------ rule model
def is_fighting_creature(is_creature, is_worker, is_prisoner):
    """Mirror of HandLimitRules::isFightingCreature."""
    return is_creature and not is_worker and not is_prisoner


def may_pick_up(limit_active, fighting, fighters_in_hand, max_fighters, cooldown_left):
    """Mirror of HandLimitRules::mayPickUp."""
    if not limit_active or not fighting:
        return True
    if fighters_in_hand >= max_fighters:
        return False
    return cooldown_left <= 0.0


def cooldown_after_drop(limit_active, fighting, cooldown_left, cooldown_seconds):
    """Mirror of HandLimitRules::cooldownAfterDrop."""
    if not limit_active or not fighting:
        return cooldown_left
    if cooldown_seconds <= 0.0:
        return 0.0
    return cooldown_seconds


def advance_cooldown(cooldown_left, seconds):
    """Mirror of HandLimitRules::advanceCooldown."""
    if cooldown_left <= seconds:
        return 0.0
    return cooldown_left - seconds


# The C++ rules are the statements the model mirrors
check("return isCreature && !isWorker && !isPrisoner;" in function(RULES, "bool isFightingCreature("),
      "HL1: a fighting creature is a creature that is no Ziv and no prisoner")
pick = function(RULES, "bool mayPickUp(")
check(pick.index("if(!limitActive || !fightingCreature)") < pick.index("if(fightersInHand >= maxFighters)")
      < pick.index("return cooldownLeft <= 0.0;"), "HL1: mayPickUp checks the limit, the count and the cooldown")
drop = function(RULES, "double cooldownAfterDrop(")
check("if(!limitActive || !fightingCreature)\n        return cooldownLeft;" in drop and "return cooldownSeconds;" in drop,
      "HL1: a dropped fighting creature starts the full cooldown, any other drop keeps it")
check("if(cooldownLeft <= seconds)\n        return 0.0;" in function(RULES, "double advanceCooldown("),
      "HL1: the cooldown counts down to 0")
check("#include <cstdint>" in RULES_H and "#include \"" not in RULES_H, "the rules depend on the standard library only")

MAX = int(EXPECTED_KEYS["HandLimitFighters"][0])
COOLDOWN = 10.0


class Keeper(object):
    """A keeper's hand with the rules of Player (pickUpEntity, dropHand, upkeepPlayer) in a model."""

    def __init__(self, campaign):
        self.campaign = campaign
        self.hand = []
        self.cooldown = 0.0

    def pick_up(self, kind):
        """kind: fighter, ziv, prisoner or item. Returns True when the entity went into the hand."""
        fighting = is_fighting_creature(kind != "item", kind == "ziv", kind == "prisoner")
        fighters = len([held for held in self.hand if held == "fighter"])
        if not may_pick_up(self.campaign, fighting, fighters, MAX, self.cooldown):
            return False
        self.hand.append(kind)
        return True

    def drop(self, kind):
        """Drops the held entity of that kind."""
        self.hand.remove(kind)
        fighting = is_fighting_creature(kind != "item", kind == "ziv", kind == "prisoner")
        self.cooldown = cooldown_after_drop(self.campaign, fighting, self.cooldown, COOLDOWN)

    def upkeep(self, seconds):
        """One upkeep of the given game seconds."""
        self.cooldown = advance_cooldown(self.cooldown, seconds)


# Second fighting creature refused
keeper = Keeper(True)
check(keeper.pick_up("fighter"), "HL1: the first fighting creature is picked up")
check(not keeper.pick_up("fighter"), "HL1: a second fighting creature is refused")
# Zivs are not limited
check(all(keeper.pick_up("ziv") for _ in range(8)), "HL1: Zivs are not limited")
check(keeper.pick_up("item") and keeper.pick_up("prisoner"), "HL1: items and prisoners are not limited")
# Cooldown after a drop
keeper.drop("ziv")
check(keeper.cooldown == 0.0, "HL1: dropping a Ziv starts no cooldown")
keeper.drop("fighter")
check(keeper.cooldown == COOLDOWN, "HL1: dropping the fighting creature starts the cooldown")
check(not keeper.pick_up("fighter"), "HL1: no fighting creature while the cooldown runs")
check(keeper.pick_up("ziv"), "HL1: Zivs during the cooldown")
for _ in range(int(COOLDOWN) - 1):
    keeper.upkeep(1.0)
check(not keeper.pick_up("fighter"), "HL1: the cooldown still runs one second before its end")
keeper.upkeep(1.0)
check(keeper.cooldown == 0.0 and keeper.pick_up("fighter"), "HL1: the next fighting creature after the cooldown")
# Skirmish and multiplayer unchanged
free = Keeper(False)
check(all(free.pick_up("fighter") for _ in range(6)), "C8: skirmish and multiplayer hold any number of fighters")
free.drop("fighter")
check(free.cooldown == 0.0 and free.pick_up("fighter"), "C8: skirmish and multiplayer have no cooldown")

# ------------------------------------------------------------------------------------------------ C4 / C8 wiring
active = function(PLAYER, "bool Player::isHandLimitActive() const")
check("mGameMap->isServerGameMap()" in active and "mGameMap->isInEditorMode()" in active
      and "return Campaign::getSingleton().isActive();" in active,
      "C8: the limit is active only on the server while a campaign level is played (not in the editor)")
check("RaidSimulation" not in active and "getIsHuman" not in active,
      "C4: the limit does not depend on human or computer keeper")
allowed = function(PLAYER, "bool Player::isHandLimitPickupAllowed(const GameEntity* entity) const")
check("HandLimitRules::mayPickUp(limitActive, isHandLimitedEntity(entity), numFightingCreaturesInHand()," in allowed
      and "mHandCooldownSeconds" in allowed, "HL1: the pickup asks the rule with the hand and the cooldown")
limited = function(PLAYER, "static bool isHandLimitedEntity(const GameEntity* entity)")
check("definition->isWorker()" in limited and "getSeatPrison() != nullptr" in limited
      and "GameEntityType::creature" in limited, "HL1: Zivs, prisoners and objects are not fighting creatures")
pickup = function(PLAYER, "void Player::pickUpEntity(GameEntity *entity)")
check("if(mGameMap->isServerGameMap() && !isHandLimitPickupAllowed(entity))" in pickup
      and pickup.index("isHandLimitPickupAllowed(entity)") < pickup.index("entity->pickup();")
      and pickup.index("isHandLimitPickupAllowed(entity)") < pickup.index("addEntityToHand(entity);"),
      "HL1: the server refuses the pickup before the entity leaves the map")
drop_hand = function(PLAYER, "void Player::dropHand(Tile *t, unsigned int index)")
server_part = drop_hand[drop_hand.index("if(mGameMap->isServerGameMap())"):]
check("HandLimitRules::cooldownAfterDrop(isHandLimitActive(), isHandLimitedEntity(entity)," in server_part
      and server_part.index("redemWorkerInHeart(entity, t)") < server_part.index("cooldownAfterDrop(")
      < server_part.index("entity->drop(pos);"), "HL1: a drop on the server starts the cooldown")
check("advanceHandCooldown(timeSinceLastUpkeep);"
      in function(PLAYER, "void Player::upkeepPlayer(double timeSinceLastUpkeep)")
      and "mHandCooldownSeconds = HandLimitRules::advanceCooldown(mHandCooldownSeconds, seconds);"
      in function(PLAYER, "void Player::advanceHandCooldown(double seconds)"),
      "HL1: the cooldown runs down in the upkeep of every keeper")
check("mHandCooldownSeconds(0.0)" in function(PLAYER, "Player::Player(GameMap* gameMap, int32_t id)"),
      "HL1: a new keeper starts without cooldown")
# Every pickup of a keeper, human or computer, goes through Player::pickUpEntity on the server
human = function(SERVER, "case ClientNotificationType::askEntityPickUp:")
check("player->pickUpEntity(entity);" in human, "C4: a human keeper's pickup goes through pickUpEntity")
fighter = SERVER[SERVER.index("case ClientNotificationType::askPickupFighter:"):]
fighter = fighter[:fighter.index("break;", fighter.index("pickUpEntity"))]
check("player->pickUpEntity(creature);" in fighter, "C4: the pick up fighter shortcut goes through pickUpEntity")
check("if(creature->tryPickup(seat)) player.pickUpEntity(creature);" in AI_ACTIONS,
      "C4: a computer keeper's pickup goes through pickUpEntity")
check("player.pickUpEntity(creature);" in AI_PRISON, "C4: a computer keeper's prisoner pickup goes through pickUpEntity")


# ------------------------------------------------------------------------------------------------ C3 save and load
def write_seat_block(cooldown):
    """Mirror of the [HandCooldown] part of Seat::exportSeatToStream (repr is the round-trip precision)."""
    if cooldown > 0.0:
        return "[HandCooldown]\t" + repr(cooldown) + "\t[/HandCooldown]\n[SkillNotAllowed]"
    return "[SkillNotAllowed]"


def read_seat_block(text):
    """Mirror of the [HandCooldown] part of Seat::importSeatFromStream; None when the loader refuses."""
    tokens = text.split()
    loaded = 0.0
    while tokens and tokens[0] == "[HandCooldown]":
        if len(tokens) < 4:
            return None
        try:
            seconds = float(tokens[1])
        except ValueError:
            return None
        if seconds != seconds or seconds in (float("inf"), float("-inf")) or seconds < 0.0 or \
                tokens[2] != "[/HandCooldown]":
            return None
        loaded = seconds
        tokens = tokens[3:]
    if not tokens or tokens[0] != "[SkillNotAllowed]":
        return None
    return loaded


saved = Keeper(True)
saved.pick_up("fighter")
saved.drop("fighter")
saved.upkeep(2.0 / 3.0)
restored = read_seat_block(write_seat_block(saved.cooldown))
check(restored == saved.cooldown, "C3: the running cooldown goes through a save and a load exactly")
check(read_seat_block(write_seat_block(0.0)) == 0.0, "C3: without a cooldown nothing is written and 0 is loaded")
check(read_seat_block("[SkillNotAllowed]") == 0.0, "C3: an old save without the block loads without cooldown")
check(read_seat_block("[HandCooldown]\t-1\t[/HandCooldown]\n[SkillNotAllowed]") is None,
      "C3: a negative cooldown is refused")
export = function(SEAT, "bool Seat::exportSeatToStream(std::ostream& os) const")
saved_part = export[export.index("if(!mGameMap->isInEditorMode() && getPlayer() != nullptr)"):export.index(
    'os << "[SkillNotAllowed]"')]
check("if(getPlayer()->getHandCooldownSeconds() > 0.0)" in saved_part
      and 'os << "[HandCooldown]\\t" << std::setprecision(std::numeric_limits<double>::max_digits10)' in saved_part
      and '<< getPlayer()->getHandCooldownSeconds() << "\\t[/HandCooldown]\\n";' in saved_part
      and "os.precision(handPrecision);" in saved_part,
      "C3: a saved game writes the running cooldown at round-trip precision, levels written by the editor do not")
load = function(SEAT, "bool Seat::importSeatFromStream(std::istream& is)")
loop_head = load[load.index("// Optional seat blocks"):load.index('    if(str == "[HandCooldown]")')]
check('str == "[HandCooldown]"' in loop_head, "C3: [HandCooldown] is an optional seat block")
hand_block = load[load.index('    if(str == "[HandCooldown]")'):load.index('    if(str == "[RevealedTiles]")')]
check('if(!(is >> seconds >> str) || !std::isfinite(seconds) || (seconds < 0.0) || (str != "[/HandCooldown]") ||'
      in hand_block and "mHandCooldownLoaded = seconds;" in hand_block and "continue;" in hand_block,
      "C3: the loader reads and checks the block")
init = function(SEAT, "void Seat::initSeat()")
check("getPlayer()->setHandCooldownSeconds(mHandCooldownLoaded);" in init, "C3: the loaded cooldown goes on")
check("double mHandCooldownLoaded = 0.0;" in SEAT_H, "C3: a seat without the block has no cooldown")
setter = function(PLAYER, "void Player::setHandCooldownSeconds(double seconds)")
check("if(!std::isfinite(seconds) || (seconds < 0.0))" in setter, "C3: an invalid restored cooldown is 0")
check('"[HandCooldown]"' in SAVE_CHECK and '"[/HandCooldown]"' in SAVE_CHECK,
      "C3: the saved game reader check knows the block")


# ------------------------------------------------------------------------------------------------ HL2 message and text
def refusal(limit_active, fighting, fighters_in_hand, max_fighters, cooldown_left):
    """Mirror of HandLimitRules::refusal."""
    if not limit_active or not fighting:
        return "none"
    if fighters_in_hand >= max_fighters:
        return "handFull"
    if cooldown_left > 0.0:
        return "cooldown"
    return "none"


def display_seconds(cooldown_left):
    """Mirror of HandLimitRules::displaySeconds."""
    if not cooldown_left > 0.0:
        return 0
    return int(max(1.0, math.ceil(cooldown_left)))


def refusal_message(reason, cooldown_left):
    """Mirror of HandLimitRules::refusalMessage."""
    if reason == "handFull":
        return "Your hand cannot hold another fighting creature."
    if reason == "cooldown":
        return "You can pick up the next fighting creature in %d s." % display_seconds(cooldown_left)
    return ""


def cooldown_text(cooldown_left):
    """Mirror of HandLimitRules::cooldownText."""
    seconds = display_seconds(cooldown_left)
    return "Next fighter: %d s" % seconds if seconds else ""


def text_place(px, py, ox, oy, width, height, screen_w, screen_h):
    """Mirror of HandLimitRules::cooldownTextPlace."""
    return max(0.0, min(px + ox, screen_w - width)), max(0.0, min(py + oy, screen_h - height))


# The C++ texts are the ones of the model (short plain English)
for text in ("Your hand cannot hold another fighting creature.",
             "You can pick up the next fighting creature in ", "Next fighter: "):
    check('"' + text + '"' in RULES, "HL2: text " + repr(text))
check(refusal(True, True, 1, MAX, 0.0) == "handFull" and refusal(True, True, 1, MAX, COOLDOWN) == "handFull",
      "HL2: a full hand is named first")
check(refusal(True, True, 0, MAX, 2.1) == "cooldown"
      and refusal_message("cooldown", 2.1) == "You can pick up the next fighting creature in 3 s.",
      "HL2: the cooldown message names the whole seconds left")
check(refusal(True, False, 1, MAX, COOLDOWN) == "none" and refusal(False, True, 1, MAX, COOLDOWN) == "none",
      "HL2: no message for Zivs, skirmish and multiplayer")
check(cooldown_text(COOLDOWN) == "Next fighter: 10 s" and cooldown_text(0.01) == "Next fighter: 1 s"
      and cooldown_text(0.0) == "", "HL2: the text at the hand")
reason_body = function(RULES, "Refusal refusal(")
check(reason_body.index("if(fightersInHand >= maxFighters)") < reason_body.index("if(cooldownLeft > 0.0)"),
      "HL2: the rule names a full hand before the cooldown")
check("std::max(0.0f, std::min(pointerX + offsetX, screenWidth - textWidth));" in RULES
      and "std::max(0.0f, std::min(pointerY + offsetY, screenHeight - textHeight));" in RULES,
      "C6: the text is moved back inside the screen")

# C6: the longest text at the hand stays inside every screen from 640x480 to 8K at UI scale 80-120 %
GAME_MODE = read("source/modes/GameMode.cpp")
GAME_MODE_H = read("source/modes/GameMode.h")
constants = dict((name, float(value)) for name, value in re.findall(
    r"^const float (POINTER_TEXT_BASE_HEIGHT|HAND_COOLDOWN_TEXT_OFFSET_Y|HAND_COOLDOWN_CHAR_WIDTH_SHARE|"
    r"POINTER_TEXT_OFFSET_X) = ([\d.]+)f;", GAME_MODE, re.M))
check(len(constants) == 4, "C6: the place and size constants of the text at the hand " + repr(constants))
longest = len(cooldown_text(999.5))
for screen_w, screen_h in ((640, 480), (800, 600), (1920, 1080), (3840, 2160), (7680, 4320)):
    for ui_scale in (0.8, 1.0, 1.2):
        feedback = ui_scale * screen_h / 1080.0
        height = constants.get("POINTER_TEXT_BASE_HEIGHT", 16.0) * feedback
        width = longest * height * constants.get("HAND_COOLDOWN_CHAR_WIDTH_SHARE", 0.6)
        for px, py in ((0, 0), (screen_w / 2, screen_h / 2), (screen_w - 1, screen_h - 1), (screen_w - 1, 0)):
            left, top = text_place(px, py, constants.get("POINTER_TEXT_OFFSET_X", 145.0) * feedback,
                                   constants.get("HAND_COOLDOWN_TEXT_OFFSET_Y", 4.0) * feedback, width, height,
                                   screen_w, screen_h)
            check(0 <= left and left + width <= screen_w and 0 <= top and top + height <= screen_h,
                  "C6: text at the hand inside %dx%d at scale %.1f, pointer %s" % (screen_w, screen_h, ui_scale,
                                                                                  (px, py)))

# Server: a refused pickup tells a human keeper why and resends the cooldown; computer keepers get nothing
pickup = function(PLAYER, "void Player::pickUpEntity(GameEntity *entity)")
check("notifyHandLimitRefusal(entity);" in pickup[pickup.index("isHandLimitPickupAllowed(entity)"):
                                                  pickup.index("entity->pickup();")],
      "HL2: a refused pickup sends the message")
refused = function(PLAYER, "void Player::notifyHandLimitRefusal(const GameEntity* entity)")
check("!getIsHuman()" in refused and "HandLimitRules::refusalMessage(reason, mHandCooldownSeconds)" in refused
      and "ServerNotificationType::chatServer" in refused and "notifyHandCooldown();" in refused,
      "HL2: the message goes to a human keeper only, with the cooldown")
notify = function(PLAYER, "void Player::notifyHandCooldown()")
check("!mGameMap->isServerGameMap() || !getIsHuman()" in notify
      and "ServerNotificationType::setHandCooldown" in notify and "<< mHandCooldownSeconds;" in notify,
      "HL2: the cooldown goes to the client of a human keeper")
check("notifyHandCooldown();" in setter, "HL2: every new cooldown (drop, load) is sent")
drop_hand = function(PLAYER, "void Player::dropHand(Tile *t, unsigned int index)")
check("setHandCooldownSeconds(handCooldown);" in drop_hand, "HL2: the cooldown of a drop is sent")
check(re.search(r"dungeonbookRoster,\n(?:\s*//!.*\n)+\s*setHandCooldown\n\};", read(
    "source/network/ServerNotification.h")) is not None, "HL2: the new notification is appended at the end")
check('return "setHandCooldown";' in read("source/network/ServerNotification.cpp"), "HL2: notification name")
client = read("source/network/ODClient.cpp")
client_case = client[client.index("case ServerNotificationType::setHandCooldown:"):]
client_case = client_case[:client_case.index("break;")]
check("packetReceived >> seconds" in client_case and "getPlayer()->setHandCooldownSeconds(seconds);" in client_case,
      "HL2: the client keeps the cooldown")
check("mLocalPlayer->advanceHandCooldown(1.0 / ODApplication::turnsPerSecond);"
      in function(read("source/gamemap/GameMap.cpp"), "void GameMap::clientUpKeep(int64_t turnNumber)"),
      "HL2: the client counts the cooldown down every turn")
# Client: the text at the hand
check("addTextBox(ODApplication::HAND_COOLDOWN_STRING" in read("source/ODApplication.cpp")
      and 'ODApplication::HAND_COOLDOWN_STRING = "handCooldown"' in read("source/ODApplication.cpp"),
      "HL2: the text box at the hand exists")
shown = function(GAME_MODE, "void GameMode::refreshHandCooldownText(float pointerX, float pointerY, float scale)")
check("HandLimitRules::cooldownText(player->getHandCooldownSeconds())" in shown
      and "HandLimitRules::cooldownTextPlace(" in shown and "POINTER_TEXT_BASE_HEIGHT * scale" in shown
      and "getSurfaceSize()" in shown and "mDefeatSequence.isStarted()" in shown,
      "HL2/C6: the text at the hand shows the cooldown, scaled and inside the screen")
check("refreshHandCooldownText(pointer.d_x, pointer.d_y, pointerScale);"
      in function(GAME_MODE, "void GameMode::refreshActionFeedback(float elapsed)"),
      "HL2: the text follows the hand every frame")
check("void refreshHandCooldownText(float pointerX, float pointerY, float scale);" in GAME_MODE_H,
      "HL2: GameMode declares the text at the hand")
for signature in ("void GameMode::startDefeatSequence(", "void GameMode::notifyPossessionStarted()",
                  "void GameMode::refreshPossessionView()"):
    check('setText(ODApplication::HAND_COOLDOWN_STRING, "")' in function(GAME_MODE, signature),
          "HL2: the text at the hand disappears in " + signature)
check('setText(ODApplication::HAND_COOLDOWN_STRING, "")' in function(read("source/modes/MenuModeMain.cpp"),
                                                                       "void MenuModeMain::activate()"),
      "HL2: the text at the hand disappears in the main menu")

# ------------------------------------------------------------------------------------------------ build and tests
check("${SRC}/game/HandLimitRules.cpp" in CMAKE, "C2: HandLimitRules.cpp is in the source list of the game")
check(re.search(r"add_boost_test\(00-HandLimitRules\s+SOURCES\s+test_HandLimitRules\.cpp\s+\$\{SRC\}/game/"
                r"HandLimitRules\.h\s+\$\{SRC\}/game/HandLimitRules\.cpp\)", TESTS_CMAKE) is not None,
      "the Boost test 00-HandLimitRules is built")
cases = re.findall(r"(.*)\n(BOOST_AUTO_TEST_CASE\((\w+)\))", BOOST_TEST)
check(sorted(name for _, _, name in cases) == sorted(["test_fightingCreature", "test_secondFighterRefused",
                                                       "test_zivsNotLimited", "test_cooldownAfterDrop",
                                                       "test_skirmishAndMultiplayerUnchanged",
                                                       "test_savedCooldownGoesOn", "test_refusalMessage",
                                                       "test_cooldownText", "test_cooldownTextInsideScreen"]),
      "the Boost test has the six cases of R11 step 3 and the three cases of HL2")
check(all(line.startswith("//!") for line, _, _ in cases), "every Boost test case has a comment")
check("auto " not in PLAYER and "auto " not in RULES and "auto " not in BOOST_TEST, "explicit types, no auto")

elapsed = time.perf_counter() - START
print('ODP_TEST_PHASE {"name":"hand-limit","seconds":%.3f}' % elapsed)
if FAILURES:
    for failure in FAILURES:
        print("FAIL: " + failure)
    sys.exit(1)
print("hand limit ok")
