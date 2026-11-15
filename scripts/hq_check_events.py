"""ODP adapter for the run-bound HQ diagnostic-drain JSONL contract."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

RESOURCES = ['odp:full-build', 'odp:shared-build-output', 'odp:game-instances',
             'odp:load-ports', 'odp:check-cache']
KEYS = ('HQ_CHECK_EVENTS', 'HQ_CHECK_RUN', 'HQ_CHECK_COMMIT')

# Resolve Git state strictly, without interpreting console text as an outcome.
def git(repo, *args):
    return subprocess.check_output(['git','-C',str(repo),*args],text=True,encoding='utf-8',timeout=30).strip()

# Hash declared build inputs without retaining a large executable in memory.
def digest(path):
    value=hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024*1024), b''):
            value.update(block)
    return value.hexdigest()

# Append one durable protocol record; child checks never inherit writer ownership.
def report(event, **fields):
    configured=[bool(os.environ.get(key)) for key in KEYS]
    if not any(configured):
        return
    if not all(configured):
        raise RuntimeError('Incomplete HQ_CHECK_EVENTS/HQ_CHECK_RUN/HQ_CHECK_COMMIT environment')
    record=dict(fields,event=event,run=os.environ['HQ_CHECK_RUN'],commit=os.environ['HQ_CHECK_COMMIT'])
    data=(json.dumps(record,ensure_ascii=True)+'\n').encode('utf-8')
    if len(data)>65536:
        raise RuntimeError('HQ record exceeds 64 KiB; use durable output paths')
    with open(os.environ['HQ_CHECK_EVENTS'],'ab') as stream:
        stream.write(data); stream.flush(); os.fsync(stream.fileno())

# Remove journal capabilities from checks and their descendants, retaining ordinary settings.
def child_environment(env):
    return {key:value for key,value in env.items() if key not in (*KEYS, 'HQ_CHECK_DEFER_RELEASE')}

# Freeze only files consumed by checks, never mutable logs or generated probe outputs.
def build_artifacts(repo):
    directory=Path(repo)/'build/windows'
    return {p.relative_to(repo).as_posix():digest(p) for p in sorted(directory.glob('*'))
            if p.is_file() and p.suffix.lower() in ('.exe','.dll','.cfg','.pdb')}

# Own the complete required suite and its immutable final results.
class Session:
    # Capture commit, artifacts and the complete required list before any result.
    def __init__(self, repo, output, checks, artifacts, resources=None):
        self.repo=Path(repo).resolve(); self.output=Path(output).resolve()
        self.logs=self.output.with_suffix('.checks'); self.logs.mkdir(parents=True,exist_ok=True)
        self.head=git(self.repo,'rev-parse','HEAD'); self.artifacts=dict(artifacts)
        self.checks=list(checks)+['snapshot-integrity']; self.results={}; self.attempt=0
        if len(set(self.checks))!=len(self.checks):
            raise RuntimeError('Duplicate required check ID')
        self.initial_error=self.verify()
        isolated=(self.repo/'.git').is_file()
        report('suite',checks=self.checks,isolated_worktree=isolated,artifacts=self.artifacts,
               resources=RESOURCES if resources is None else resources)

    # Detect commit, tracked-source or artifact mutation without repairing or hiding it.
    def verify(self):
        if os.environ.get('HQ_CHECK_COMMIT',self.head)!=self.head or git(self.repo,'rev-parse','HEAD')!=self.head:
            return 'Checked commit differs from HQ_CHECK_COMMIT or changed during checks'
        if git(self.repo,'status','--porcelain','--untracked-files=no'):
            return 'Tracked files differ from the checked commit'
        for name, expected in self.artifacts.items():
            path=(self.repo/name).resolve()
            if not path.is_relative_to(self.repo) or not path.is_file() or digest(path)!=expected:
                return 'Declared build artifact changed or disappeared: '+name
        return ''

    # Persist the entire output, then report its real exit code and retry finality.
    def result(self, check, code, output, final=True, **details):
        if check not in self.checks or check in self.results or type(code) is not int:
            raise RuntimeError('Invalid or replaced final check result: '+check)
        self.attempt+=1
        log=self.logs/('%04d.log'%self.attempt)
        with log.open('w',encoding='utf-8',newline='') as stream:
            stream.write(output); stream.flush(); os.fsync(stream.fileno())
        report('result',check=check,exit=code,final=final,output_path=str(log),
               output_sha256=digest(log),**details)
        if final:
            self.results[check]=code

    # Finish every missing prerequisite explicitly and release writes only after all work ends.
    def finish(self):
        for check in self.checks:
            if check not in self.results and check!='snapshot-integrity':
                self.result(check,125,'Required check did not complete; prerequisite or runner failure',kind='missing-result')
        problem=self.initial_error or self.verify()
        self.result('snapshot-integrity',1 if problem else 0,problem or 'Commit, tracked files and declared artifacts unchanged')
        # Profiling writes shared history after this function; that outer writer owns the final release marker.
        if not problem and not os.environ.get('HQ_CHECK_DEFER_RELEASE'):
            report('shared_writes_finished')
        return int(any(self.results.values()))
