#!/usr/bin/env python3
"""Runtime test: closing the game window with the X button ends the game cleanly.

Starts the built executable twice with its own --appData and sends the window the message of the X button (WM_CLOSE):

    loading  as soon as the loading picture is drawn, while the game is still loading
    menu     as soon as the main menu is ready

Each start passes only if the process then ends by itself with exit code 0 within its limit and its log reports no
unhandled exception. A game that is still running after the limit is killed by this script and counts as a failure.

Usage:
    python scripts/run-window-close-test.py --exe build/windows/moreya.exe
"""

import argparse
import ctypes
import ctypes.wintypes
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

WM_CLOSE = 0x0010
LOADING_MARKER = "startup loading picture drawn"
MENU_MARKER = "startup menu ready"
# Log lines that mean the shutdown did not end cleanly
FAILURE_MARKERS = ("Unhandled exception", "[CRITICAL]")
# Upper bounds, not waits: each phase ends as soon as its condition is met
START_LIMIT_SECONDS = 180.0
# After an X during loading the game first finishes loading and then exits
EXIT_LIMIT_SECONDS = {"loading": 180.0, "menu": 60.0}
POLL_SECONDS = 0.1


def read_log(appdata):
    """Returns the game log of the given appData folder, or an empty text while it does not exist yet."""
    path = os.path.join(appdata, "moreya.log")
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError:
        return ""


def visible_windows(pid):
    """Returns the visible top-level windows of the given process."""
    user32 = ctypes.windll.user32
    found = []
    callback_type = ctypes.WINFUNCTYPE(ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)

    def collect(hwnd, _):
        """Keeps a window that belongs to the process and is visible."""
        owner = ctypes.wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid and user32.IsWindowVisible(hwnd):
            found.append(hwnd)
        return True

    user32.EnumWindows(callback_type(collect), 0)
    return found


def phase(name, seconds):
    """Prints a phase measurement for the timing report."""
    print("ODP_TEST_PHASE " + json.dumps({"name": name, "seconds": round(seconds, 3)}), flush=True)


def run_case(exe, case):
    """Starts the game, presses X at the point of the case and returns (passed, message)."""
    marker = LOADING_MARKER if case == "loading" else MENU_MARKER
    appdata = tempfile.mkdtemp(prefix="od-window-close-")
    process = subprocess.Popen([exe, "--appData", appdata], cwd=os.path.dirname(os.path.abspath(exe)),
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    started = time.monotonic()
    try:
        windows = []
        while time.monotonic() - started < START_LIMIT_SECONDS:
            if process.poll() is not None:
                return False, "%s: the game ended with code %s before X was pressed" % (case, process.returncode)
            if marker in read_log(appdata):
                windows = visible_windows(process.pid)
                if windows:
                    break
            time.sleep(POLL_SECONDS)
        if not windows:
            return False, "%s: no visible window with '%s' after %d s" % (case, marker, START_LIMIT_SECONDS)
        phase(case + ":start", time.monotonic() - started)

        for hwnd in windows:
            ctypes.windll.user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
        closed = time.monotonic()
        try:
            code = process.wait(timeout=EXIT_LIMIT_SECONDS[case])
        except subprocess.TimeoutExpired:
            return False, "%s: the game still ran %d s after X; killed by the script" % (case, EXIT_LIMIT_SECONDS[case])
        phase(case + ":exit", time.monotonic() - closed)

        log = read_log(appdata)
        for failure in FAILURE_MARKERS:
            if failure in log:
                line = next(text for text in log.splitlines() if failure in text)
                return False, "%s: exit code %d, the log reports: %s" % (case, code, line.strip())
        if code != 0:
            return False, "%s: the game ended with exit code %d (0x%08X) after X" % (case, code, code & 0xFFFFFFFF)
        return True, "%s: the game ended cleanly %.1f s after X" % (case, time.monotonic() - closed)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        shutil.rmtree(appdata, ignore_errors=True)


def main():
    """Runs both cases and returns 0 only if both ended cleanly."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--exe", required=True, help="the built game executable")
    args = parser.parse_args()
    if sys.platform != "win32":
        print("FAIL: the window close test needs Windows")
        return 1
    if not os.path.isfile(args.exe):
        print("FAIL: executable missing: " + args.exe)
        return 1

    failed = 0
    for case in ("loading", "menu"):
        passed, message = run_case(args.exe, case)
        print(("PASS " if passed else "FAIL ") + message, flush=True)
        failed += int(not passed)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
