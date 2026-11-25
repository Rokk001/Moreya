#!/usr/bin/env python3
"""Own rows of the mixed data tables.

A mixed data table (config/global.cfg, config/rooms.cfg, ...) is an upstream table with rows and values that the
project wrote itself. The public table keeps the upstream rows; every run of own rows is replaced there by one marker
line "#@own <n>". The own rows lie in the content package core-config in a file of the same name with ".own" before
the extension (config/global.own.cfg). That file holds one block per marker: a line "#@own <n>" followed by the rows
that belong at the marker, up to the next "#@own" line; lines before the first marker are its header and are not
inserted. Joining the two gives the full table again, line for line; the game does the same when it reads a table
(Helper::readFile with ContentPackages::mergeOwnRows) and the checks read the joined table through
content_packages.read_text.

Without the content package the markers are comments of the public table and the table holds its upstream rows
only.

Commands:
  join <table>                write the joined table to stdout
  split <full file> <table>   split a full table into the public table and the own rows file: lines that appear,
                              in order, in the current public table stay public, every other line is own. Use it
                              when a full table was edited (for example after joining it for a larger change)
  blame-split <table> ...     first split of a table: every non-empty line whose author (git blame -w -M -C) is one
                              of OWN_AUTHORS is own, blank lines between own lines go with them
  verify <table> ...          print whether the joined table equals the given reference file

<table> is a path relative to the repository (config/global.cfg).
"""

import difflib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
import content_packages  # noqa: E402

# The prefix of a marker line in the public table and of a block line in the own rows file
MARKER = '#@own '
# The authors whose lines are own rows (git blame)
OWN_AUTHORS = ('Mario',)
# The content package that holds the own rows files
OWN_ROWS_PACKAGE = 'core-config'
# The content package that holds the own rows files of the interface files of gui/
OWN_GUI_PACKAGE = 'core-gui'
# The extensions of the interface files (XML) whose markers are XML comments "<!--#@own <n>-->"
XML_EXTENSIONS = ('.layout', '.looknfeel', '.scheme', '.imageset', '.font')
# The header of every own rows file
HEADER = ('# Own rows of {table} (content of Moreya, all rights reserved). Each block "#@own <n>" holds the rows\n'
          '# that belong at the marker line "#@own <n>" of the public table (scripts/config_own_rows.py).\n')
XML_HEADER = ('<!-- Own rows of {table} (content of Moreya, all rights reserved). Each block "#@own <n>" in an XML\n'
              '     comment holds the rows that belong at the marker line of the public file\n'
              '     (scripts/config_own_rows.py). -->\n')

_MARKER_LINE = re.compile(r'^#@own (\d+)\s*$')
_XML_MARKER_LINE = re.compile(r'^<!--#@own (\d+)-->\s*$')


def is_xml(table):
    """True when the table is an interface file whose markers are XML comments."""
    return str(table).lower().endswith(XML_EXTENSIONS)


def marker_text(table, number):
    """The marker line of a block of the table, without line end."""
    return ('<!--' + MARKER + str(number) + '-->') if is_xml(table) else (MARKER + str(number))


def own_rows_package(table):
    """The content package of the own rows file of a table."""
    return OWN_GUI_PACKAGE if str(table).replace('\\', '/').startswith('gui/') else OWN_ROWS_PACKAGE


def own_rows_path(table):
    """The relative path of the own rows file of a table: ".own" before the extension."""
    table = str(table).replace('\\', '/')
    stem, dot, ext = table.rpartition('.')
    return stem + '.own.' + ext if dot else table + '.own'


def marker_number(line):
    """The number of a marker line, or None."""
    line = line.rstrip('\r\n')
    match = _MARKER_LINE.match(line) or _XML_MARKER_LINE.match(line)
    return int(match.group(1)) if match else None


def parse_own_rows(text):
    """The blocks of an own rows file: {number: [lines without line ends]}."""
    blocks = {}
    current = None
    for line in text.splitlines():
        number = marker_number(line)
        if number is not None:
            if number in blocks:
                raise ValueError('block #@own %d twice in the own rows file' % number)
            blocks[number] = []
            current = number
        elif current is not None:
            blocks[current].append(line)
    return blocks


def markers(public_text):
    """The marker numbers of a public table, in order."""
    return [n for n in (marker_number(line) for line in public_text.splitlines()) if n is not None]


def join(public_text, own_text):
    """The full table from the public table and the own rows file (lines joined with LF; a final line end of the
    public table is kept). Raises ValueError when a marker has no block or a block has no marker."""
    blocks = parse_own_rows(own_text)
    used = set()
    lines = []
    for line in public_text.splitlines():
        number = marker_number(line)
        if number is None:
            lines.append(line)
            continue
        if number not in blocks:
            raise ValueError('marker #@own %d has no block in the own rows file' % number)
        if number in used:
            raise ValueError('marker #@own %d twice in the public table' % number)
        used.add(number)
        lines.extend(blocks[number])
    unused = sorted(set(blocks) - used)
    if unused:
        raise ValueError('blocks without a marker in the public table: %s' % unused)
    text = '\n'.join(lines)
    if public_text.endswith('\n'):
        text += '\n'
    return text


def own_rows_file(repo, table):
    """The own rows file of a table in the content packages, or None."""
    relative = own_rows_path(table)
    for root in content_packages.package_roots(repo):
        candidate = Path(root) / relative
        if candidate.exists():
            return candidate
    return None


def joined_text(repo, table, public_text=None):
    """The table as the game reads it: the public table with the own rows of the content packages; the public
    table alone when it has no markers or no own rows file is found."""
    if public_text is None:
        public_text = (Path(repo) / table).read_text(encoding='utf-8')
    if not markers(public_text):
        return public_text
    own = own_rows_file(repo, table)
    if own is None:
        return public_text
    return join(public_text, own.read_text(encoding='utf-8'))


def _blocks_text(table, blocks):
    out = [(XML_HEADER if is_xml(table) else HEADER).format(table=table)]
    for number, block in enumerate(blocks, 1):
        out.append(marker_text(table, number) + '\n')
        out.extend(line + '\n' for line in block)
    return ''.join(out)


def split_lines(lines, own_flags, table=''):
    """Splits lines by their own flags into the public lines (with the markers of the table) and the blocks. Blank
    lines go with the own lines only when they lie between two own lines."""
    flags = list(own_flags)
    count = len(lines)
    index = 0
    while index < count:
        if not flags[index] and lines[index].strip() == '':
            start = index
            while index < count and not flags[index] and lines[index].strip() == '':
                index += 1
            if start > 0 and flags[start - 1] and index < count and flags[index]:
                for blank in range(start, index):
                    flags[blank] = True
        else:
            index += 1
    public = []
    blocks = []
    index = 0
    while index < count:
        if flags[index]:
            block = []
            while index < count and flags[index]:
                block.append(lines[index])
                index += 1
            blocks.append(block)
            public.append(marker_text(table, len(blocks)))
        else:
            public.append(lines[index])
            index += 1
    return public, blocks


def blame_own_flags(repo, table):
    """The own flag of every line of the committed table (HEAD) by git blame -w -M -C."""
    output = subprocess.run(['git', 'blame', '-w', '-M', '-C', '--line-porcelain', 'HEAD', '--', table],
                            cwd=str(repo), check=True, capture_output=True).stdout.decode('utf-8')
    flags = []
    author = None
    for line in output.split('\n'):
        if line.startswith('author '):
            author = line[len('author '):]
        elif line.startswith('\t'):
            flags.append(author in OWN_AUTHORS and line[1:].strip() != '')
    return flags


def committed_text(repo, table):
    """The committed table (HEAD) with LF line ends."""
    return subprocess.run(['git', 'show', 'HEAD:' + table], cwd=str(repo), check=True,
                          capture_output=True).stdout.decode('utf-8').replace('\r\n', '\n')


def _write(path, text, crlf):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = text.replace('\n', '\r\n') if crlf else text
    path.write_bytes(data.encode('utf-8'))


def _uses_crlf(path):
    return path.exists() and b'\r\n' in path.read_bytes()


def own_rows_target(repo, table):
    """Where the own rows file of a table is written: the existing file, else the package of the table."""
    existing = own_rows_file(repo, table)
    if existing is not None:
        return existing
    for root in content_packages.package_roots(repo):
        if Path(root).name == own_rows_package(table):
            return Path(root) / own_rows_path(table)
    raise SystemExit('the content package %s was not found (MOREYA_CONTENT_DIR)' % own_rows_package(table))


def blame_split(repo, table):
    text = committed_text(repo, table)
    lines = text.splitlines()
    flags = blame_own_flags(repo, table)
    if len(flags) != len(lines):
        raise SystemExit('%s: git blame gave %d lines, the file has %d' % (table, len(flags), len(lines)))
    public, blocks = split_lines(lines, flags, table)
    public_path = Path(repo) / table
    crlf = _uses_crlf(public_path)
    _write(public_path, '\n'.join(public) + ('\n' if text.endswith('\n') else ''), crlf)
    target = own_rows_target(repo, table)
    _write(target, _blocks_text(table, blocks), crlf)
    return len(blocks), sum(len(b) for b in blocks)


def split_full(repo, full_path, table):
    full_text = Path(full_path).read_text(encoding='utf-8')
    full = full_text.splitlines()
    public_path = Path(repo) / table
    current = [line for line in public_path.read_text(encoding='utf-8').splitlines() if marker_number(line) is None]
    matcher = difflib.SequenceMatcher(None, current, full, autojunk=False)
    flags = [True] * len(full)
    for block in matcher.get_matching_blocks():
        for offset in range(block.size):
            flags[block.b + offset] = False
    public, blocks = split_lines(full, flags, table)
    crlf = _uses_crlf(public_path)
    _write(public_path, '\n'.join(public) + ('\n' if full_text.endswith('\n') else ''), crlf)
    _write(own_rows_target(repo, table), _blocks_text(table, blocks), crlf)
    return len(blocks), sum(len(b) for b in blocks)


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    command = argv[1]
    if command == 'join' and len(argv) == 3:
        sys.stdout.write(joined_text(ROOT, argv[2]))
        return 0
    if command == 'split' and len(argv) == 4:
        print('%s: %d blocks, %d own lines' % ((argv[3],) + split_full(ROOT, argv[2], argv[3])))
        return 0
    if command == 'blame-split' and len(argv) >= 3:
        for table in argv[2:]:
            print('%s: %d blocks, %d own lines' % ((table,) + blame_split(ROOT, table)))
        return 0
    if command == 'verify' and len(argv) == 4:
        joined = joined_text(ROOT, argv[2]).replace('\r\n', '\n')
        reference = Path(argv[3]).read_text(encoding='utf-8').replace('\r\n', '\n')
        print('equal' if joined == reference else 'DIFFERENT')
        return 0 if joined == reference else 1
    print(__doc__)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv))
