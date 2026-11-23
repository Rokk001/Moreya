"""Check that closing the game window with the X button ends the game. Text check, no game start, no compiler;
scripts/run-window-close-test.py presses X on the built game in the release run.

Ogre's Win32 render windows use the default window procedure unless the parameter "windowProc" names one. With the
default procedure the X button only destroys the window: ODFrameListener::windowClosed() is never called, the exit is
never requested and the game keeps running without a window. Both render windows the game creates (the primary window
and the replacement window of the video settings) must therefore get Ogre's window event procedure.
"""
from pathlib import Path

repo = Path(__file__).resolve().parents[2]


# Read a source file without starting the game or a compiler.
def read(path):
    return (repo / path).read_text(encoding='utf-8')


# Return the text of one function, from its signature line to the next line that is a closing brace at column 0.
def body(text, signature):
    start = text.index(signature)
    end = text.index('\n}\n', start)
    return text[start:end]


listener = read('source/render/ODFrameListener.cpp')
header = read('source/render/ODFrameListener.h')
application = read('source/ODApplication.cpp')

# The helper names Ogre's window event procedure on Win32.
assert 'static void addWindowEventProcedure(Ogre::NameValuePairList& miscParams);' in header
helper = body(listener, 'void ODFrameListener::addWindowEventProcedure(')
assert 'miscParams["windowProc"]' in helper
assert '&Ogre::WindowEventUtilities::_WndProc' in helper
assert '#if OGRE_PLATFORM == OGRE_PLATFORM_WIN32' in helper

# The primary window gets it before it is created.
create = application.index('ogreRoot.createRenderWindow(windowTitle')
added = application.index('ODFrameListener::addWindowEventProcedure(misc);')
assert added < create, 'the window procedure must be set before the primary window is created'

# The replacement window of the video settings gets it too.
assert 'addWindowEventProcedure(description.miscParams);' in listener
assert listener.index('addWindowEventProcedure(description.miscParams);') < \
    listener.index('replacementWindow = root.createRenderWindow(description);')

# Closing the window still requests the exit, and the main loop ends on it.
assert 'requestExit();' in body(listener, 'void ODFrameListener::windowClosed(')
assert 'if (frameListener.isExitRequested())' in application

# The X button keeps the window: Ogre destroys a window whose listeners all agree to close it, and the shutdown then
# runs without the rendering context it needs and ends with a crash.
assert 'virtual bool windowClosing(Ogre::RenderWindow* rw) override;' in header
closing = body(listener, 'bool ODFrameListener::windowClosing(')
assert 'requestExit();' in closing and 'return false;' in closing

# While the game loads there is no frame listener yet: a listener of its own keeps the window and the main loop
# requests the exit once it runs.
class_start = application.index('class StartupWindowCloseListener')
startup = application[class_start:application.index('\n};\n', class_start)]
assert 'mCloseRequested = true;' in startup and 'return false;' in startup
added_listener = application.index('Ogre::WindowEventUtilities::addWindowEventListener(renderWindow, &startupCloseListener);')
assert application.index('LoadingScreen startupLoading(') > added_listener, \
    'the loading listener must exist before the loading screen pumps the window messages'
assert application.count('if(startupCloseListener.isCloseRequested())\n                frameListener.requestExit();') == 2
assert 'Ogre::WindowEventUtilities::removeWindowEventListener(renderWindow, &startupCloseListener);' in application

# The release run presses X on the built game while it loads and in the main menu and requires exit code 0.
runner = read('scripts/run-checks.py')
assert "'scripts/run-window-close-test.py',['--exe',executable]" in runner
assert "checks += ['deploy-readiness', 'window-close']" in runner
close_test = read('scripts/run-window-close-test.py')
assert 'for case in ("loading", "menu"):' in close_test
assert 'if code != 0:' in close_test

print('check_window_close_exit OK')
