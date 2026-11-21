"""Select deployment probes from immutable commits and a successful deployment receipt."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

# The agreed basis level: Mossgate in the public wing 1 package, or at its former path in older commits
SMOKES = ('levels/campaign/wing1/Mossgate.level', 'levels/campaign/Mossgate.level')
# The former single campaign definition; the campaign now comes from the Package.cfg of each wing package folder
CAMPAIGN = 'levels/campaign/Campaign.cfg'
PACKAGE_DEFINITION = re.compile(r'^levels/campaign/[^/]+/Package\.cfg$')
PACKAGE_TEXT = re.compile(r'^levels/campaign/[^/]+/(LICENSE\.txt|README\.md)$')


# Read immutable Git data without changing any worktree or ref.
def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args], encoding='utf-8', timeout=30).strip()


# Reject symbolic or nonexistent commits in saved evidence.
def commit(repo, value):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{40}', value):
        raise RuntimeError('Deployment comparison requires a full immutable commit SHA')
    if git(repo, 'rev-parse', '--verify', value + '^{commit}') != value:
        raise RuntimeError('Deployment commit cannot be resolved: ' + value)
    return value


# The campaign definitions of a commit: the Package.cfg of every public wing package (its levels lie in its folder),
# or the former levels/campaign/Campaign.cfg of an older commit (levels below levels/). Pairs of (text, folder).
def definitions(repo, revision):
    tracked = git(repo, 'ls-tree', '-r', '--name-only', revision, '--', 'levels/campaign').splitlines()
    packages = sorted(name for name in tracked if PACKAGE_DEFINITION.match(name))
    if packages:
        return [(git(repo, 'show', revision + ':' + name), name.rsplit('/', 1)[0] + '/') for name in packages]
    return [(git(repo, 'show', revision + ':' + CAMPAIGN), None)]


# Parse campaign entries including their order, which determines successor unlocking.
def entries(repo, revision):
    result = {}
    for text, folder in definitions(repo, revision):
        result.update(definition_entries(text, folder, result))
    return result


# Parse the entries of one definition; a package entry names its level file in the package folder.
def definition_entries(text, folder, known):
    result = {}
    block = None
    blocks = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if line == '[Level]':
            block = []
            blocks.append(block)
        elif line == '[/Level]':
            block = None
        elif block is not None:
            block.append(line)
        else:
            raise RuntimeError('Unknown shared Campaign.cfg setting; review scope or request explicit full check')
    for block in blocks:
        files = [line[5:].strip() for line in block if line.startswith('File=')]
        if len(files) != 1 or not files[0].endswith('.level'):
            raise RuntimeError('Invalid Campaign.cfg level entry')
        name = folder + files[0].split('/')[-1] if folder else 'levels/' + files[0]
        if '..' in Path(name).parts or '\\' in name or ':' in name or files[0].startswith('/'):
            raise RuntimeError('Campaign level path escapes levels: ' + name)
        if name in result or name in known:
            raise RuntimeError('Duplicate Campaign.cfg level: ' + name)
        result[name] = tuple(block)
    return result


# Account for changed map files and shared campaign definitions without an implicit full sweep.
def select(repo, base, tip, full=False):
    commit(repo, tip)
    current = entries(repo, tip)
    if full:
        return dict.fromkeys(current, 'explicit full campaign requested')
    commit(repo, base)
    changed = git(repo, 'diff', '--name-only', '-z', '--no-renames', base, tip, '--', 'levels').split('\0')
    tracked = set(git(repo, 'ls-tree', '-r', '--name-only', tip, '--', 'levels').splitlines())
    smoke = next((name for name in SMOKES if name in tracked), SMOKES[0])
    selected = {smoke: 'agreed basis level (owner decision 99)'}
    definition_changed = False
    for name in changed:
        if name.endswith('.level') and name in tracked:
            selected.setdefault(name, 'level changed since successful deploy')
        elif name == CAMPAIGN or PACKAGE_DEFINITION.match(name):
            definition_changed = True
        elif name and not name.endswith('.level') and not PACKAGE_TEXT.match(name):
            raise RuntimeError('Unmapped shared level file changed: ' + name + '; review dependencies or request explicit full check')
    if definition_changed:
        previous = entries(repo, base)
        old_order, new_order = list(previous), list(current)
        for name, value in current.items():
            # Completion checks exercise the next campaign entry too, so changed order affects neighbors.
            index = new_order.index(name)
            neighborhood = new_order[max(0, index - 1):index + 2]
            old_index = old_order.index(name) if name in previous else -1
            old_neighbors = old_order[max(0, old_index - 1):old_index + 2] if old_index >= 0 else []
            if previous.get(name) != value or neighborhood != old_neighbors:
                selected.setdefault(name, 'shared Campaign.cfg entry or sequence changed')
    for name in selected:
        if name not in tracked:
            raise RuntimeError('Selected level missing from outgoing commit: ' + name)
    return selected


# Use only success evidence; planning a new attempt must never advance the baseline.
def prepare(repo, tip, receipt, full=False):
    base = None
    if not full:
        try:
            saved = json.loads(receipt.read_text(encoding='utf-8'))
            if saved.get('schema') != 1 or saved.get('status') != 'success' or not saved.get('evidence'):
                raise ValueError('missing success evidence')
            base = commit(repo, saved.get('data_commit'))
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
            raise RuntimeError('No verified last successful deploy baseline at ' + str(receipt) + ': ' + str(error)) from error
    levels = select(repo, base, tip, full)
    return {'schema': 1, 'base': base, 'tip': tip, 'mode': 'full' if full else 'selected', 'levels': levels}


# Publish JSON by atomic replacement so readers never observe a partial success receipt.
def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.new')
    temporary.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


# Prepare and log scope, or record a wrapper-confirmed successful deployment.
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', required=True, type=Path)
    parser.add_argument('--tip', required=True)
    parser.add_argument('--receipt', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--all-campaign', action='store_true')
    parser.add_argument('--record-success', action='store_true')
    parser.add_argument('--executable', type=Path)
    args = parser.parse_args()
    if args.record_success:
        manifest = json.loads(args.output.read_text(encoding='utf-8'))
        if manifest['tip'] != commit(args.repo, args.tip):
            raise RuntimeError('Success commit does not match selected deployment')
        if args.executable is None:
            parser.error('--record-success requires --executable')
        write_json(args.receipt, {'schema': 1, 'status': 'success', 'data_commit': args.tip,
                                 'exe_sha256': hashlib.sha256(args.executable.read_bytes()).hexdigest(),
                                 'evidence': str(args.output.resolve()),
                                 'completed_utc': datetime.now(timezone.utc).isoformat()})
    else:
        manifest = prepare(args.repo, args.tip, args.receipt, args.all_campaign)
        print('Deploy comparison: ' + str(manifest['base']) + ' -> ' + manifest['tip'], flush=True)
        for name, reason in manifest['levels'].items():
            print('SELECT ' + name + ': ' + reason, flush=True)
        write_json(args.output, manifest)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
