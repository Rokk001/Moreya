"""Static check of the possession controls and the own view of a possession (no build needed).

Checks against the sources of this branch:
- skill keys: 1 to 9 and 0 use the skill slots 0 to 9, Shift with the same keys the slots 10 to 19 (the table is
  computed from the key list of GameMode.cpp and compared with a fixed table)
- Esc is the only way out of the creature; the right mouse button no longer leaves it
- while possessing F5 (quick save) and F10 (options menu with saving) do nothing, and the client and the server refuse
  a save of a possessing player
- the own view: all root windows (the chat included), the keeper hand, the pointer and the indicators over the creatures are
  hidden, the own model of the creature too; a crosshair sits in the middle of the window; the mouse is kept in the
  window; everything comes back when the possession ends
"""
from pathlib import Path
import re
import time

ROOT = Path(__file__).resolve().parents[2]
START = time.monotonic()


def read(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


def function(source, signature):
    """Return the source of the function that starts with the signature (up to its closing brace)."""
    start = source.index(signature)
    end = source.index("{", start) + 1
    depth = 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


problems = []


def check(condition, message):
    if not condition:
        problems.append(message)


game = read("source/modes/GameMode.cpp")
game_header = read("source/modes/GameMode.h")
server = read("source/network/ODServer.cpp")
client = read("source/network/ODClient.cpp")
overlay = read("source/render/CreatureOverlayStatus.cpp")
render = read("source/render/RenderManager.cpp")
input_source = read("source/modes/InputManager.cpp")

# ---- skill keys: the table of the sources against the fixed table of the possession rules
EXPECTED_SLOTS = {("1", False): 0, ("2", False): 1, ("3", False): 2, ("4", False): 3, ("5", False): 4,
                  ("6", False): 5, ("7", False): 6, ("8", False): 7, ("9", False): 8, ("0", False): 9,
                  ("1", True): 10, ("2", True): 11, ("3", True): 12, ("4", True): 13, ("5", True): 14,
                  ("6", True): 15, ("7", True): 16, ("8", True): 17, ("9", True): 18, ("0", True): 19}
per_row = re.search(r"const uint32_t POSSESSION_SKILL_KEYS_PER_ROW = (\d+);", game)
keys = re.search(r"const OIS::KeyCode POSSESSION_SKILL_KEYS\[POSSESSION_SKILL_KEYS_PER_ROW\] = \{([^}]*)\};", game)
check(per_row is not None and keys is not None, "the possession skill key list is missing")
if per_row is not None and keys is not None:
    row = int(per_row.group(1))
    key_names = re.findall(r"OIS::KC_(\w+)", keys.group(1))
    slot_function = function(game, "static int32_t getPossessionSkillSlot(OIS::KeyCode key, bool shift)")
    check("shift ? (index + POSSESSION_SKILL_KEYS_PER_ROW) : index" in slot_function,
          "Shift must give the slot one row further")
    computed = {}
    for index, name in enumerate(key_names):
        computed[(name, False)] = index
        computed[(name, True)] = index + row
    check(computed == EXPECTED_SLOTS, "the skill keys do not give the slots 0 to 19: %s" % sorted(computed.items()))

handle = function(game, "bool GameMode::handlePossessionKey(OIS::KeyCode key, bool pressed)")
check("getPossessionSkillSlot(key, getKeyboard()->isModifierDown(OIS::Keyboard::Shift))" in handle,
      "the skill keys must read Shift")
check("sendPossessionSkill(static_cast<uint32_t>(slot));" in handle, "a skill key must send its slot")
check("POSSESSION_SKILL_SLOT_" not in game, "the old keys 1 to 4 are still there")
for old in ("OIS::KC_1", "OIS::KC_4"):
    check(old not in handle, "the possession keys must not name single number keys any more: " + old)

# ---- Esc only, the right mouse button does not leave the creature
escape = handle[handle.index("case OIS::KC_ESCAPE:"):]
escape = escape[:escape.index("return true;")]
check("sendPossessionExit();" in escape and "closeTopWindow" not in escape, "Esc must leave the creature at once")
check(game.count("sendPossessionExit();") == 1, "only Esc may send the possession exit")
pressed = function(game, "bool GameMode::mousePressed(const OIS::MouseEvent& arg, OIS::MouseButtonID id)")
branch = pressed[pressed.index("if (isLocalPlayerPossessing())"):]
branch = branch[:branch.index("return true;\n    }")]
check("MB_Right" not in branch and "sendPossessionExit" not in branch, "the right mouse button must not leave the creature")
check("sendPossessionAttack();" in branch and "mPossessAttackHeld = true;" in branch,
      "the left mouse button attacks and keeps attacking while held")
check(pressed.index("if (isLocalPlayerPossessing())") < pressed.index("isMouseDownOnCEGUIWindow()"),
      "the possession mouse must not depend on the hidden windows")
released = function(game, "bool GameMode::mouseReleased(const OIS::MouseEvent &arg, OIS::MouseButtonID id)")
check("mPossessAttackHeld = false;" in released, "releasing the left mouse button must stop the attack")
update_input = function(game, "void GameMode::updatePossessionInput(float timeSinceLastFrame)")
check("if (mPossessAttackHeld)" in update_input and "getPossessionAttackRepeat()" in update_input,
      "a held left mouse button must repeat its request once per turn")
check("1.0 / ODApplication::turnsPerSecond" in function(game, "static std::chrono::steady_clock::duration getPossessionAttackRepeat()"),
      "the request is repeated once per turn")
key_pressed = function(game, "bool GameMode::keyPressed(const OIS::KeyEvent& arg)")
check("guiHandledKey && !isLocalPlayerPossessing()" in key_pressed, "the GUI must not take Esc while possessing")

# ---- F5 and F10 do nothing while possessing
normal = function(game, "bool GameMode::keyPressedNormal(const OIS::KeyEvent &arg)")
check(normal.index("handlePossessionKey(arg.key, true)") < normal.index("case OIS::KC_F5:")
      and normal.index("handlePossessionKey(arg.key, true)") < normal.index("case OIS::KC_F10:")
      and normal.index("handlePossessionKey(arg.key, true)") < normal.index("if(arg.key == OIS::KC_M)"),
      "the possession keys must come before F5, F10 and the map")
passed = handle[handle.index("case OIS::KC_F11:"):]
passed = passed[:passed.index("return false;")]
check(set(re.findall(r"OIS::KC_(\w+)", passed)) == {"F11", "F12", "GRAVE"},
      "only console and debug keys may pass while possessing (the chat is hidden)")
check(handle.rstrip().endswith("return true;\n}"), "every other key must do nothing while possessing")
save = function(game, "bool GameMode::saveGame(const CEGUI::EventArgs& /*e*/)")
check("if(isLocalPlayerPossessing())" in save, "the client must not save while possessing")
options = function(game, "bool GameMode::toggleOptionsWindow(const CEGUI::EventArgs& e)")
check("if(isLocalPlayerPossessing())" in options, "the options menu must not open while possessing")
save_map = server[server.index("case ClientNotificationType::askSaveMap:"):]
save_map = save_map[:save_map.index("boost::filesystem::path levelSave;")]
check("if(player->isPossessing())" in save_map, "the server must refuse the save of a possessing player")

# ---- the own view
check("enterPossessionView();" in function(game, "void GameMode::notifyPossessionStarted()"),
      "the possession view must start with the possession")
check("leavePossessionView();" in function(game, "void GameMode::notifyPossessionEnded()"),
      "the possession view must end with the possession")
start = client[client.index("case ServerNotificationType::possessionStart:"):]
check("gm->notifyPossessionStarted();" in start[:start.index("break;")], "the client must start the possession view")
end = client[client.index("case ServerNotificationType::possessionEnd:"):]
check("gm->notifyPossessionEnded();" in end[:end.index("break;")], "the client must end the possession view")
enter = function(game, "void GameMode::enterPossessionView()")
for needle, message in (("getMouseCursor().setVisible(false);", "the pointer"),
                        ("rrToggleHandSelectorVisibility();", "the keeper hand"),
                        ("CreatureOverlayStatus::setAllSuppressed(true);", "the creature indicators"),
                        ("rrSetCreaturesTextOverlay(*mGameMap, false);", "the creature indicators"),
                        ("setPossessionMouseLock(true);", "the mouse lock"),
                        ("addTextBox(POSSESSION_CROSSHAIR_TEXT, POSSESSION_CROSSHAIR_SYMBOL", "the crosshair")):
    check(needle in enter, "the possession view does not handle " + message)
refresh = function(game, "void GameMode::refreshPossessionView()")
check("mRootWindow->getChildAtIdx(index)" in refresh and "child->hide();" in refresh,
      "the root windows (game bar, minimap, keeper windows) must be hidden")
check("POSSESSION_KEPT_WINDOW" not in game and "GameChatWindow" not in refresh,
      "no keeper window stays visible while possessing, the chat included")
check("rrSetCreatureModelVisible(*creature, false);" in refresh, "the own model must be hidden")
check("moveText(POSSESSION_CROSSHAIR_TEXT" in refresh, "the crosshair must stay in the middle of the window")
leave = function(game, "void GameMode::leavePossessionView()")
for needle, message in (("window->show();", "the hidden windows"),
                        ("rrSetCreatureModelVisible(*creature, true);", "the own model"),
                        ("removeTextBox(POSSESSION_CROSSHAIR_TEXT);", "the crosshair"),
                        ("setPossessionMouseLock(false);", "the mouse"),
                        ("CreatureOverlayStatus::setAllSuppressed(false);", "the creature indicators"),
                        ("rrSetCreaturesTextOverlay(*mGameMap, mCreatureIndicatorsVisible);", "the creature indicators"),
                        ("rrToggleHandSelectorVisibility();", "the keeper hand"),
                        ("getMouseCursor().setVisible(true);", "the pointer")):
    check(needle in leave, "the end of the possession view does not give back " + message)
feedback = function(game, "void GameMode::refreshActionFeedback(float elapsed)")
check(feedback.index("if(mPossessionViewActive)") < feedback.index("rrToggleHandSelectorVisibility()"),
      "the frame update must not bring the hand back while possessing")
check("leavePossessionView();" in function(game, "GameMode::~GameMode()"), "leaving the game must end the view")
check("bool mPossessionViewActive = false;" in game_header, "mPossessionViewActive is not declared")
check("!sAllSuppressed &&" in function(overlay, "void CreatureOverlayStatus::update(Ogre::Real timeSincelastFrame)"),
      "the indicators must stay hidden whatever asks for them")
check("entity->setVisible(visible);" in function(render, "void RenderManager::rrSetCreatureModelVisible(Creature& creature, bool visible)"),
      "the own model is not hidden")
refresh_settings = function(input_source, "void InputManager::refreshSettings()")
check("mPossessionMouseLock ||" in refresh_settings, "the mouse lock must capture the mouse")
capture = function(input_source, "void InputManager::capturePointer()")
check("centrePointer();" in capture, "the pointer must go back to the middle while the mouse is locked")

# ---- the crosshair fits every window from 640x480 to 8K: fixed sizes for both ends
share = float(re.search(r"const float POSSESSION_CROSSHAIR_HEIGHT_SHARE = ([0-9.]+)f;", game).group(1))
minimum = float(re.search(r"const float POSSESSION_CROSSHAIR_MIN_HEIGHT = ([0-9.]+)f;", game).group(1))
for height, expected in ((480, 19.2), (4320, 172.8)):
    size = max(minimum, height * share)
    check(abs(size - expected) < 1e-6, "crosshair height %.1f at %d pixels, expected %.1f" % (size, height, expected))
    check(size < height / 10.0, "the crosshair must stay small at %d pixels" % height)

print('ODP_TEST_PHASE {"name":"test","seconds":%.3f}' % (time.monotonic() - START))
if problems:
    for problem in problems:
        print("FAIL: " + problem)
    raise SystemExit(1)
print("Possession skill keys 1-0 and Shift+1-0, Esc only, no saving and own view: PASS (static only)")
