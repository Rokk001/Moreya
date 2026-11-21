#!/usr/bin/env python3
"""Return from a running game to the main menu never draws a destroyed camera (K5).

Cause of the crash on the return to the main menu: RenderManager::initGameRenderer adds a viewport of the camera
"RenderToTexture" to the depth pre-pass target mRenderTarget ("smokeTexture"), and ODFrameListener::frameStarted
updates mRenderTarget every frame while it is set, also in the menu. The game teardown destroyed that camera but kept
the target and its viewport, so the next menu frame rendered a freed camera (access violation in
SceneManager::findLightsAffectingFrustum, the camera's virtual isVisible call).

Runtime part (with --exe, the outcome): the game is started once per game kind with
`--run-level <level> --seconds <N> --scenario return-to-menu` (skirmish, campaign, sandbox) or
`--scenario editor-return-to-menu` (editor). The game runs N seconds of real time in the game or editor mode, leaves
it through the Yes handler of the quit dialog (campaign: to the campaign map, then to the main menu), checks before
every following frame that no render target the frame loop updates shows a camera that the scene manager no longer
owns, and passes after the main menu has started 120 frames. A run passes only with exit code 0 and a PASS line that
says the main menu was reached. A crash, a destroyed camera on a target, a timeout or a missing line is a failure.
It refuses to run while another moreya.exe is running, so a game the owner plays is never touched.

The runtime part is not started by the check runner: CLAUDE.md allows exactly one load test per integration, and this
part starts the game four times. Run it once on a build that contains the change:
  python -I source/tests/check_return_to_main_menu.py --exe build/windows/moreya.exe

Static part (no arguments; run by the check runner, compiles nothing): the release order that removes the cause, with
mutations that must be rejected:
  - RenderManager::destroySmokeRenderTarget removes the viewports and clears mRenderTarget before the camera
    "RenderToTexture" is destroyed;
  - stopGameRenderer, initGameRenderer and EditorMode::loadLevelFromFile use it, and no other code destroys that camera;
  - frameStarted steps the return-to-menu run before it updates mRenderTarget, and updates it only while it is set;
  - the minimap removes its viewport before destroying its camera.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time

REPO = Path(__file__).resolve().parents[2]
SOURCE = REPO / 'source'

# Game kinds of K5 with their fixed level and scenario. TestInfirmary is the level of the crash session.
KINDS = (
    ('skirmish', 'levels/skirmish/TestInfirmary.level', 'return-to-menu'),
    ('campaign', 'levels/campaign/Mossgate.level', 'return-to-menu'),
    ('sandbox', 'levels/skirmish/Sandbox.level', 'return-to-menu'),
    ('editor', 'levels/skirmish/TestInfirmary.level', 'editor-return-to-menu'),
)
PASS_TEXT = 'left to the main menu'
# Real time limit per run: start and level load, the played seconds, the menu frames and shutdown.
RUN_LIMIT_BASE_SECONDS = 300


def read(relative):
    return (SOURCE / relative).read_text(encoding='utf-8')


def strip_comments(text):
    return re.sub(r'//[^\n]*|/\*.*?\*/', '', text, flags=re.S)


def function_body(text, signature):
    """Body of the function whose definition starts with signature (braces matched, comments and strings skipped)."""
    start = text.find(signature)
    assert start >= 0, 'definition not found: ' + signature
    opening = text.index('{', start)
    depth = 0
    for match in re.finditer(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"|[{}]', text[opening:], re.S):
        if match.group() == '{':
            depth += 1
        elif match.group() == '}':
            depth -= 1
            if depth == 0:
                return strip_comments(text[opening:opening + match.end()])
    raise AssertionError('body not closed: ' + signature)


def check_release_order(renderer):
    """The target leaves the frame loop (viewports removed, pointer cleared) before its camera is destroyed."""
    body = function_body(renderer, 'void RenderManager::destroySmokeRenderTarget()')
    viewports = body.find('mRenderTarget->removeAllViewports();')
    cleared = body.find('mRenderTarget = nullptr;')
    camera = body.find('destroyCamera("RenderToTexture")')
    assert viewports >= 0, 'the viewports of the target are not removed'
    assert cleared >= 0, 'mRenderTarget is not cleared'
    assert camera >= 0, 'the camera RenderToTexture is not destroyed'
    assert viewports < camera and cleared < camera, 'the camera is destroyed while the target still shows it'
    assert 'm_texture.reset();' in body, 'the texture reference is kept'


def check_users(renderer, editor):
    """Every teardown path uses the ordered release; nothing else destroys the camera RenderToTexture."""
    stop = function_body(renderer, 'void RenderManager::stopGameRenderer(GameMap* gameMap)')
    init = function_body(renderer, 'void RenderManager::initGameRenderer(GameMap* gameMap)')
    load = function_body(editor, 'bool EditorMode::loadLevelFromFile(const std::string& fileName)')
    assert 'destroySmokeRenderTarget();' in stop, 'stopGameRenderer does not release the target'
    assert 'RenderManager::getSingleton().destroySmokeRenderTarget();' in load, 'the editor reload does not release it'
    release = init.find('destroySmokeRenderTarget();')
    create = init.find('mRenderTarget = m_texture->getBuffer()->getRenderTarget();')
    assert 0 <= release < create, 'initGameRenderer does not release a left-over target before making a new one'
    release_body = function_body(renderer, 'void RenderManager::destroySmokeRenderTarget()')
    for path in sorted(SOURCE.rglob('*.cpp')):
        if 'tests' in path.relative_to(SOURCE).parts:
            continue
        text = strip_comments(path.read_text(encoding='utf-8', errors='replace'))
        if path.name == 'RenderManager.cpp':
            text = text.replace(release_body, '', 1)
        assert 'destroyCamera("RenderToTexture")' not in text, (
            str(path.relative_to(REPO)) + ' destroys the camera RenderToTexture outside destroySmokeRenderTarget')


def check_frame_loop(listener):
    """frameStarted steps the test run first and updates the target only while it is set."""
    body = function_body(listener, 'bool ODFrameListener::frameStarted(const Ogre::FrameEvent& evt)')
    step = body.find('stepReturnToMenuTest(evt.timeSinceLastFrame);')
    guard = body.find('mRenderManager->mRenderTarget != nullptr')
    update = body.find('mRenderManager->mRenderTarget->update();')
    assert step >= 0, 'the return-to-menu run is not stepped'
    assert 0 <= guard < update, 'the target is updated without the null check'
    assert step < update, 'the run is stepped after the target update'
    stepper = function_body(listener, 'void ODFrameListener::stepReturnToMenuTest(Ogre::Real seconds)')
    assert '!mRenderManager->hasRenderTargetWithDestroyedCamera()' in stepper, 'the run does not see the target state'
    assert 'gameMode->quitToMenu();' in stepper and 'editorMode->onClickYesQuitMenu();' in stepper


def check_minimap(minimap):
    """The minimap target loses its viewport before its camera is destroyed."""
    body = function_body(minimap, 'MiniMapCamera::~MiniMapCamera()')
    viewports = body.find('rt->removeAllViewports();')
    camera = body.find('sceneManager->destroyCamera(mMiniMapCam);')
    assert 0 <= viewports < camera, 'the minimap camera is destroyed while its target still shows it'


def check_all(renderer, editor, listener, minimap):
    check_release_order(renderer)
    check_users(renderer, editor)
    check_frame_loop(listener)
    check_minimap(minimap)


def rejected(renderer, editor, listener, minimap):
    try:
        check_all(renderer, editor, listener, minimap)
    except AssertionError:
        return True
    return False


def static_check():
    """Checks the sources and that every mutation that brings the cause back is rejected."""
    renderer = read('render/RenderManager.cpp')
    editor = read('modes/EditorMode.cpp')
    listener = read('render/ODFrameListener.cpp')
    minimap = read('gamemap/MiniMapCamera.cpp')
    check_all(renderer, editor, listener, minimap)

    old_teardown = ('    if(cameraManager->hasCamera("RenderToTexture"))\n'
                    '        cameraManager->destroyCamera("RenderToTexture");\n')
    mutations = [
        ('target kept', renderer.replace('        mRenderTarget = nullptr;\n', '', 1), editor, listener, minimap),
        ('viewports kept', renderer.replace('        mRenderTarget->removeAllViewports();\n', '', 1),
         editor, listener, minimap),
        ('camera first', renderer.replace('    if(mRenderTarget != nullptr)\n    {\n        mRenderTarget->removeListener',
                                          old_teardown + '    if(mRenderTarget != nullptr)\n    {\n'
                                          '        mRenderTarget->removeListener', 1), editor, listener, minimap),
        ('stop without release', renderer.replace('    destroySmokeRenderTarget();\n    removeIfExists<Ogre::TextureManager>("PerlinNoiseTexture"',
                                                  '    removeIfExists<Ogre::TextureManager>("PerlinNoiseTexture"', 1),
         editor, listener, minimap),
        ('editor destroys the camera', renderer,
         editor.replace('    RenderManager::getSingleton().destroySmokeRenderTarget();\n',
                        '    ODFrameListener::getSingleton().getCameraManager()->destroyCamera("RenderToTexture");\n', 1),
         listener, minimap),
        ('no null check', renderer, editor,
         listener.replace('mRenderManager  && mRenderManager->mRenderTarget != nullptr', 'mRenderManager', 1), minimap),
        ('minimap camera first', renderer, editor, listener,
         minimap.replace('    rt->removeAllViewports();\n', '', 1)),
    ]
    for name, *texts in mutations:
        assert texts != [renderer, editor, listener, minimap], 'mutation did not apply: ' + name
        assert rejected(*texts), 'mutation not rejected: ' + name
    print('static part: release order, users, frame loop and minimap ok; %d mutations rejected' % len(mutations))


def game_running():
    """True when an moreya.exe process exists (tasklist, no kill)."""
    result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq moreya.exe', '/NH'], capture_output=True)
    return 'moreya.exe' in result.stdout.decode('utf-8', errors='replace').lower()


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(('127.0.0.1', 0))
        return probe.getsockname()[1]


def run_kind(exe, kind, level, scenario, seconds):
    """Runs one game kind; returns (passed, text)."""
    appdata = tempfile.mkdtemp(prefix='od-return-menu-')
    limit = RUN_LIMIT_BASE_SECONDS + 2 * seconds
    command = [str(exe), '--run-level', str(REPO / level), '--seconds', str(seconds), '--scenario', scenario,
               '--appData', appdata, '--port', str(free_port())]
    started = time.monotonic()
    try:
        completed = subprocess.run(command, cwd=str(exe.parent), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   universal_newlines=True, errors='replace', timeout=limit)
        code = completed.returncode
        output = completed.stdout or ''
    except subprocess.TimeoutExpired as expired:
        code = None
        output = expired.output or ''
        if isinstance(output, bytes):
            output = output.decode('utf-8', errors='replace')
    finally:
        print('ODP_TEST_PHASE ' + json.dumps({'name': kind, 'seconds': time.monotonic() - started}), flush=True)
        shutil.rmtree(appdata, ignore_errors=True)
    lines = [line.strip() for line in output.splitlines() if line.startswith('PASS ') or line.startswith('FAIL ')]
    result = lines[-1] if lines else 'no result line'
    if code is None:
        return False, '%s: killed after %d s (%s)' % (kind, limit, result)
    if code != 0:
        return False, '%s: exit code %d (%s)' % (kind, code, result)
    if not result.startswith('PASS ') or PASS_TEXT not in result:
        return False, '%s: exit code 0 without the main menu PASS line (%s)' % (kind, result)
    return True, '%s: %s' % (kind, result)


def runtime_check(exe, seconds):
    if game_running():
        print('FAIL: another moreya.exe is running; the runtime part is not started')
        return 1
    failed = 0
    for kind, level, scenario in KINDS:
        passed, text = run_kind(exe, kind, level, scenario, seconds)
        print(('PASS ' if passed else 'FAIL ') + text, flush=True)
        failed += 0 if passed else 1
    print('%d of %d game kinds returned to the main menu' % (len(KINDS) - failed, len(KINDS)))
    return 1 if failed else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--exe', default=None, help='built game executable; without it only the static part runs')
    parser.add_argument('--seconds', type=int, default=5, help='real seconds in the game or editor (default 5)')
    args = parser.parse_args()
    static_check()
    if args.exe is None:
        return 0
    exe = Path(args.exe).resolve()
    if not exe.is_file():
        print('FAIL: executable not found: ' + str(exe))
        return 2
    return runtime_check(exe, args.seconds)


if __name__ == '__main__':
    sys.exit(main())
