"""Noncompiling contracts for permanent S3 stall attribution, with fixed timing fixtures.

Source contracts and mutations check boundaries, nested accounting and operation identities.
Arithmetic fixtures evaluate the actual production expressions; no C++ or game is launched.
They do not prove compilation, runtime overhead, or removal of historical stalls.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]


def function(text, signature):
    """Extract one production function without depending on its indentation."""
    start = text.index(signature)
    end = text.index("{", start) + 1
    depth = 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


def contract(source):
    """Freeze clock, complete frame coverage, exclusive accounting and diagnostic I/O order."""
    boundary = function(source, "void FrameStallTrace::beginFrame(")
    transition = function(source, "void FrameStallTrace::setPhase(")
    scope = function(source, "FrameStallTrace::Scope::~Scope(")
    sample = function(source, "float FrameStatistics::sampleFrame(")
    assert "static thread_local FrameStallTrace trace;" in source
    assert "steady_clock::now()" in function(source, "double FrameStallTrace::now(")
    assert "mSeconds[mPhase] += time - mLast;" in transition
    assert "mLast = time;" in transition
    assert transition.index("mSeconds[mPhase] +=") < transition.index("mLast = time;") < transition.index("mPhase = phase;")
    assert "mSeconds[mPhase] += time - mLast;" in boundary
    assert "const double seconds = mFrame == 0 ? 0.0 : time - mStart;" in boundary
    assert "if(seconds > 0.100)" in boundary
    assert "if(inGame)" not in boundary and "std::min" not in boundary
    assert boundary.index('"Frame stall: frame="') < boundary.index("++mFrame;")
    assert boundary.index('" inGame=" << mInGame') < boundary.index("mInGame = inGame;")
    for field in ("turn=", "windowActive=", "intervalMs=", "dominantPhase=", "exclusiveMs=",
                  "operation=", "context=", "maxInclusiveMs="):
        assert field in boundary, field
    assert "mSeconds[phase] > mSeconds[dominant]" in boundary
    for reset in ("mSeconds.fill(0.0);", "mMaxInclusive.fill(0.0);", "mLast = time;", "mStart = time;",
                  "mPhase = Statistics;", "context.clear();"):
        assert boundary.index(reset) < boundary.index("OD_LOG_INF(report);")
    assert source.count("OD_LOG_INF(report);") == 1
    assert "mFrame != 0 && mFrame == trace.mFrame" in scope
    assert "seconds > trace.mMaxInclusive[mPhase]" in scope
    assert "trace.mContexts[mPhase] = mContext;" in scope
    assert "trace.setPhase(mPrevious);" in scope
    assert "mPrevious(get().mPhase)" in source
    assert "beginFrame(time, inGame, turn, active)" in sample
    assert sample.index("const double time = now();") < sample.index("beginFrame(time, inGame, turn, active)")
    assert sample.index("beginFrame(time, inGame, turn, active)") < sample.index("mPreviousFrame = time;")


source = (ROOT / "source/render/FrameStatistics.cpp").read_text()
header = (ROOT / "source/render/FrameStallTrace.h").read_text()
listener = (ROOT / "source/render/ODFrameListener.cpp").read_text()
contract(source)
assert "std::array<double, Count> mSeconds" in header
assert "Scope(const Scope&) = delete;" in header
# Fixed 23 buckets, including three explicitly unresolved engine/OS intervals.
names_body = re.search(r"names\[Count\] = \{(.*?)\};", source, re.S).group(1)
names = re.findall(r'"([^"]+)"', names_body)
assert len(names) == 23 and len(set(names)) == 23
assert [name for name in names if name.endswith("-unresolved")] == [
    "Ogre-render-targets-unresolved", "Ogre-present-unresolved", "event-pump-unresolved"]
start = function(listener, "bool ODFrameListener::frameStarted(")
queued = function(listener, "bool ODFrameListener::frameRenderingQueued(")
ended = function(listener, "bool ODFrameListener::frameEnded(")
assert listener.count("mFrameStatistics.sampleFrame(") == 1
assert "sampleFrame(inGame, mGameMap->getTurnNumber(), mWindow->isActive())" in start
assert start.index("sampleFrame(") < start.index("FrameStallTrace::FrameStarted") < start.index("onFrameStarted(evt)")
assert start.index("FrameStallTrace::RenderTargets") > start.index("mRenderTarget->update();")
for phase, call in (("Limiter", "mFpsLimiter.sleepIfEarly();"), ("GuiPulse", "Gui::keepTooltipInFront();"),
                    ("ModeUpdate", "mModeManager->update(evt);"), ("Animations", "updateAnimations("),
                    ("CameraAudio", "mCameraManager.updateCameraFrameTime("),
                    ("SocketMessages", "processClientSocketMessages(0)"),
                    ("Notifications", "processClientNotifications()")):
    assert queued.index("FrameStallTrace::" + phase) < queued.index(call), phase
assert queued.rindex("FrameStallTrace::Present") < queued.rindex("return mContinue;")
assert ended.index("FrameStallTrace::FrameEnded") < ended.index("onFrameEnded(evt)") < ended.index("FrameStallTrace::EventPump")

# Context lifetimes and instrumentation of both late preparation and actual first-use paths.
client = (ROOT / "source/network/ODClient.cpp").read_text()
message = function(client, "bool ODClient::processMessage(")
assert message.index("const std::string notificationName") < message.index("Scope trace(") < message.index("switch(cmd)")
assert "FrameStallTrace::Message, notificationName.c_str()" in message
render = (ROOT / "source/render/RenderManager.cpp").read_text()
for signature, phase, context in (
    ("void RenderManager::rrCreateCreature(", "CreatureCreate", "curCreature->getName().c_str()"),
    ("void RenderManager::prepareGeneratedShaders(", "MaterialPreparation", "material.getName().c_str()"),
    ("void RenderManager::prepareOutlinerMaterials(", "MaterialPreparation", "materialName.c_str()"),
    ("Ogre::MaterialPtr RenderManager::getOutlinerMaterial(", "MaterialPreparation", "materialName.c_str()"),
    ("Ogre::MaterialPtr RenderManager::getBrighterMaterial(", "MaterialPreparation", "materialName.c_str()")):
    assert "Scope trace(FrameStallTrace::%s, %s);" % (phase, context) in function(render, signature)
for signature in ("void RenderManager::prepareGameCreatureResources(", "void RenderManager::prepareGameShaders("):
    assert "Scope trace(FrameStallTrace::ResourcePreparation);" in function(render, signature)
minimap = (ROOT / "source/gamemap/MiniMapDrawn.cpp").read_text()
assert "Scope trace(FrameStallTrace::MiniMap);" in function(minimap, "void MiniMapDrawn::update(")
assert "Scope trace(FrameStallTrace::GuiRender);" in function(listener, "void ODFrameListener::renderQueueStarted(")

logging = (ROOT / "source/utils/LogManager.cpp").read_text()
log = function(logging, "void LogManager::logMessage(")
assert log.index("Scope trace(FrameStallTrace::LogWrite, filepath);") < log.index("locked(mLock)")
terrain = (ROOT / "source/render/TerrainDrawBatch.cpp").read_text()
assert "Scope trace(FrameStallTrace::TerrainRebuild);" in function(terrain, "void TerrainDrawBatch::preUpdateSceneGraph(")

# Evaluate production arithmetic against a fixed nested 368 ms frame and a 780 ms engine stall.
delta = re.search(r"mSeconds\[mPhase\] \+= ([^;]+);", source).group(1)
threshold = re.search(r"if\((seconds > [\d.]+)\)", source).group(1)
totals = [0.0] * 23
last = 0.0
for time, previous in ((0.005, 1), (0.015, 7), (0.115, 16), (0.135, 7),
                       (0.335, 20), (0.350, 10), (0.368, 12)):
    totals[previous] += eval(delta, {"__builtins__": {}}, {"time": time, "mLast": last})
    last = time
assert abs(sum(totals) - 0.368) < 1e-12
assert abs(totals[7] - 0.030) < 1e-12  # nested minimap's 100 ms is excluded
assert abs(totals[20] - 0.200) < 1e-12
assert max(range(23), key=totals.__getitem__) == 20
engine = [0.0] * 23
last = 0.0
for time, previous in ((0.760, 3), (0.780, 12)):
    engine[previous] += eval(delta, {"__builtins__": {}}, {"time": time, "mLast": last})
    last = time
assert abs(sum(engine) - 0.780) < 1e-12
assert names[max(range(23), key=engine.__getitem__)] == "Ogre-render-targets-unresolved"
# Keeping the original boundary attributes a hypothetical slow diagnostic write to the next interval.
assert eval(delta, {"__builtins__": {}}, {"time": 1.120, "mLast": 1.000}) > 0.100
for seconds, expected in ((0.0, False), (0.100, False), (0.100001, True), (0.368, True), (0.780, True), (4.53715, True)):
    assert eval(threshold, {"__builtins__": {}}, {"seconds": seconds}) is expected

# Reject eight independent losses of evidence or changes to frame accounting.
mutations = (
    ("static thread_local FrameStallTrace trace;", "static FrameStallTrace trace;"),
    ("mSeconds[mPhase] += time - mLast;", "mSeconds[mPhase] += 0;"),
    ("if(seconds > 0.100)", "if(seconds > 1.000)"),
    ("mLast = time;", "mLast = now();"),
    ("trace.setPhase(mPrevious);", "trace.setPhase(Uninstrumented);"),
    ("mFrame != 0 && mFrame == trace.mFrame", "mFrame != 0"),
    ("trace.mContexts[mPhase] = mContext;", "trace.mContexts[mPhase].clear();"),
    ("beginFrame(time, inGame, turn, active)", "beginFrame(now(), inGame, turn, active)"),
)
for old, new in mutations:
    assert old in source
    try:
        contract(source.replace(old, new))
    except AssertionError:
        pass
    else:
        raise AssertionError("accepted mutation: " + old)
print("frame stall trace: 23 phases, fixed timing/threshold fixtures, 8 rejected mutations; no compilation/runtime proof")
