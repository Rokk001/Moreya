"""Check that closing the game window with the X button ends the game. Text check, no game start, no compiler.

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

print('check_window_close_exit OK')
