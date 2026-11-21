#!/usr/bin/env python3
"""Prove from the logs of one game start that the loading picture comes first.

Reads the game log (moreya.log) and Ogre.log of the same start and checks three proofs:

1. The startup loading picture is drawn before the resources are registered: in the game log the line
   "startup loading picture drawn" comes before the first "Resource in section" line, and in Ogre.log the
   loading picture and ring textures are loaded before the resource groups GUI and Graphics are created.
2. The picture is drawn before the shader setup: in Ogre.log the loading picture textures are loaded before the
   first shader made by the run time shader system ("RTSS:"), and the game log time of the drawn picture is not
   later than that shader line.
3. The window is shown with the picture at once and keeps it until the menu is ready: "window shown" follows the
   drawn picture and comes at most 1 s after "Creating window:", and "startup menu ready" comes after it.

Both logs must belong to the same start: the Ogre root is created in both within 5 s.

A start that writes both logs without touching the player's own logs:
    moreya.exe --menu-test 5 --appData <empty folder>
(run in the folder of the executable; Ogre.log is written there, moreya.log into the --appData folder).

Usage: python scripts/startup-log-order.py --game-log <moreya.log> --ogre-log <Ogre.log>
Exit code 0 when all three proofs hold, 1 otherwise; every proof is printed with its log lines and times.
"""
import argparse
import re
import sys

GAME_LINE = re.compile(r'^\((\d\d):(\d\d):(\d\d)\) \(([^)]*)\) \[[A-Z]+\] (.*)$')
OGRE_LINE = re.compile(r'^(\d\d):(\d\d):(\d\d): (.*)$')


def read_lines(path, pattern):
    """Returns (line number, seconds of the day, text) for every timestamped line of a log."""
    result = []
    with open(path, encoding='utf-8', errors='replace') as handle:
        for number, line in enumerate(handle, 1):
            match = pattern.match(line.rstrip('\n'))
            if match:
                groups = match.groups()
                seconds = int(groups[0]) * 3600 + int(groups[1]) * 60 + int(groups[2])
                result.append((number, seconds, groups[-1]))
    return result


def first(lines, predicate, after=0):
    """Returns the first log entry after the given line number for which predicate(text) is true, or None."""
    for entry in lines:
        if entry[0] > after and predicate(entry[2]):
            return entry
    return None


def show(name, entry):
    """Formats a log entry for the report."""
    if entry is None:
        return '%s: missing' % name
    hours, rest = divmod(entry[1], 3600)
    return '%s: line %d at %02d:%02d:%02d' % (name, entry[0], hours, rest // 60, rest % 60)


def main():
    """Checks the three proofs and prints them."""
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--game-log', required=True)
    parser.add_argument('--ogre-log', required=True)
    args = parser.parse_args()
    game = read_lines(args.game_log, GAME_LINE)
    ogre = read_lines(args.ogre_log, OGRE_LINE)
    failures = []

    root_game = first(game, lambda t: t.startswith('Creating OGRE::Root instance'))
    root_ogre = ogre[0] if ogre else None
    if root_game is None or root_ogre is None or abs(root_game[1] - root_ogre[1]) > 5:
        print('FAIL: the logs do not belong to the same start (%s; %s)'
              % (show('game log root', root_game), show('Ogre.log first line', root_ogre)))
        return 1

    created = first(game, lambda t: t.startswith('Creating window:'))
    drawn = first(game, lambda t: t == 'startup loading picture drawn')
    shown = first(game, lambda t: t == 'window shown')
    resources = first(game, lambda t: t.startswith('Resource in section'))
    ready = first(game, lambda t: t == 'startup menu ready')
    picture = first(ogre, lambda t: re.match(r"Texture 'loading_\d+\.jpg'", t) is not None)
    ring = first(ogre, lambda t: t.startswith("Texture 'loading_ring.png'"))
    group_gui = first(ogre, lambda t: t == 'Creating resource group GUI')
    group_graphics = first(ogre, lambda t: t == 'Creating resource group Graphics')
    rtss = first(ogre, lambda t: t.startswith('RTSS:'))

    proof1 = (drawn is not None and resources is not None and drawn[0] < resources[0]
              and picture is not None and ring is not None and group_gui is not None and group_graphics is not None
              and max(picture[0], ring[0]) < min(group_gui[0], group_graphics[0]))
    print('Proof 1 (picture before resource registration): %s' % ('PASS' if proof1 else 'FAIL'))
    for item in (show('drawn', drawn), show('first resource location', resources), show('picture texture', picture),
                 show('ring texture', ring), show('group GUI', group_gui), show('group Graphics', group_graphics)):
        print('    ' + item)

    proof2 = (picture is not None and rtss is not None and picture[0] < rtss[0]
              and drawn is not None and drawn[1] <= rtss[1])
    print('Proof 2 (picture before shader setup): %s' % ('PASS' if proof2 else 'FAIL'))
    for item in (show('picture texture', picture), show('first RTSS shader', rtss), show('drawn', drawn)):
        print('    ' + item)

    proof3 = (created is not None and drawn is not None and shown is not None and ready is not None
              and created[0] < drawn[0] < shown[0] < ready[0] and shown[1] - created[1] <= 1)
    print('Proof 3 (window shown with the picture within 1 s, until the menu is ready): %s'
          % ('PASS' if proof3 else 'FAIL'))
    for item in (show('window created', created), show('drawn', drawn), show('window shown', shown),
                 show('menu ready', ready)):
        print('    ' + item)

    for name, passed in (('1', proof1), ('2', proof2), ('3', proof3)):
        if not passed:
            failures.append(name)
    if failures:
        print('FAIL: proof %s' % ', '.join(failures))
        return 1
    print('OK: all three startup proofs hold')
    return 0


if __name__ == '__main__':
    sys.exit(main())
