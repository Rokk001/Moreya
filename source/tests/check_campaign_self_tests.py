#!/usr/bin/env python3
"""Runs the self-tests of the two campaign level checks in every check run.

scripts/check-campaign-opening.py and source/tests/check_campaign_playability.py check the campaign levels when they
run without arguments; their --self-test mode feeds them broken copies of the levels and requires each copy to fail
(for the opening check: an enemy source that can walk to the heart at level start stays red, a Moreya gate in gate
mode does not count). The check runner starts every script without arguments, so without this script the self-tests
would never run and could fall behind the levels unnoticed.

Usage: python -I source/tests/check_campaign_self_tests.py
Exit 0 and "campaign self-tests ok" when both self-tests pass.
"""
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# The two self-tests and the line each prints when it passes
SELF_TESTS = (
    ("scripts/check-campaign-opening.py", "self-test passed"),
    ("source/tests/check_campaign_playability.py", "campaign playability self-test passed"),
)
# Upper bound in seconds for one self-test (the playability self-test takes about 20 s)
TIMEOUT_SECONDS = 300


def run_self_test(script, passed_line):
    """Runs one self-test; returns an error text or None when it passed."""
    start = time.monotonic()
    result = subprocess.run([sys.executable, "-I", "-B", os.path.join(ROOT, script), "--self-test"], cwd=ROOT,
                            stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8",
                            errors="replace", timeout=TIMEOUT_SECONDS)
    name = os.path.basename(script)
    print('ODP_TEST_PHASE ' + json.dumps({"name": name, "seconds": round(time.monotonic() - start, 3)}))
    if result.returncode != 0 or passed_line not in result.stdout:
        tail = "\n".join((result.stdout + result.stderr).splitlines()[-15:])
        return "%s --self-test failed (exit %d):\n%s" % (script, result.returncode, tail)
    return None


def main():
    """Runs both self-tests and reports every failure."""
    failures = [error for error in (run_self_test(script, line) for script, line in SELF_TESTS) if error]
    for failure in failures:
        print("FAIL: " + failure)
    if failures:
        return 1
    print("campaign self-tests ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
