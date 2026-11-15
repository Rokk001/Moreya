"""Verify the ODP journal against HQ's real consumer and scheduler using a disposable database."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace

# Drive HQ with ODP events without touching its real database, processes or configuration.
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--hq-root',type=Path,required=True)
    args=parser.parse_args()
    expected=subprocess.check_output(['git','-C',str(args.hq_root),'show','b76c3cb:haivequeen/check_events.py'])
    actual=(args.hq_root/'haivequeen/check_events.py').read_bytes().replace(b'\r\n',b'\n')
    if expected.replace(b'\r\n',b'\n')!=actual:
        raise RuntimeError('HQ protocol differs from the requested b76c3cb contract')
    sys.path.insert(0,str(args.hq_root));sys.path.insert(0,str(Path(__file__).resolve().parent))
    from haivequeen import check_events,db,hives,orchestrator as orch,buildjobs
    from hq_check_events import Session,RESOURCES,digest
    with tempfile.TemporaryDirectory(prefix='odp-hq-protocol-') as temporary:
        root=Path(temporary);primary=root/'primary';worktree=root/'checked'
        subprocess.run(['git','init','-q',str(primary)],check=True)
        (primary/'source.txt').write_text('frozen')
        subprocess.run(['git','-C',str(primary),'add','.'],check=True)
        subprocess.run(['git','-C',str(primary),'-c','user.name=Test','-c','user.email=test@example.invalid','commit','-qm','fixture'],check=True)
        subprocess.run(['git','-C',str(primary),'worktree','add','--detach',str(worktree),'HEAD'],check=True,capture_output=True)
        head=subprocess.check_output(['git','-C',str(worktree),'rev-parse','HEAD'],text=True).strip()
        artifact=worktree/'game.bin';artifact.write_bytes(b'fixture build')
        journal=root/'events.jsonl'
        os.environ.update(check_events.environment(journal,'fixture-run',head))
        conn=db.connect(root/'hq-test.db')
        try:
            db.upsert_project(conn,'fixture',None,'cyan',1)
            for plan in ('first.md','next.md'):
                hives.create(conn,'fixture',plan,'codex','cyan');hives.take_integration(conn,'fixture',plan)
            settings={'integrationStepResources':{'Merge':[],'Check':RESOURCES,'Build':RESOURCES,'Deploy':RESOURCES}}
            env=SimpleNamespace(name='fixture',settings=settings,conn=conn)
            job={'step':'Build','token':'fixture-run','head':head,'cwd':str(worktree),
                 'check_events':str(journal),'buildJobs':4,'buildParallel':1,'pid':os.getpid()}
            state={'phase':'pipeline','step':'Build','placed':True,'steps':{'Build':'running'},'job':job}
            orch.save(conn,'fixture','first.md',state)
            session=Session(worktree,root/'results.txt',['early','retry','later'],{'game.bin':digest(artifact)})
            session.result('early',9,'complete first error')
            assert orch._observe_checks(conn,env,'first.md',state)
            assert state['phase']=='diagnosing' and state['steps']['Build']=='red'
            assert orch._ahead(conn,'fixture','next.md')==['first.md']
            assert 'shared integration' in state['diagnosis_release_reason']
            print('PASS: first final failure immediately enters HQ diagnosing; unproven release remains blocked')
            session.result('retry',1,'WinError 4551 retry',final=False)
            session.result('retry',0,'retry passed')
            session.result('later',5,'second independent error')
            assert session.finish()==1
            orch._observe_checks(conn,env,'first.md',state)
            assert state['diagnosis_released']
            assert orch._ahead(conn,'fixture','next.md')==[]
            assert hives.take_integration(conn,'fixture','next.md')
            assert check_events.resource_wait(conn,[])==''
            assert check_events.resource_wait(conn,['odp:load-ports'])
            assert check_events.resource_wait(conn,['odp:game-instances'])
            assert check_events.resource_wait(conn,['odp:full-build'])
            assert check_events.resource_wait(conn,None)
            assert buildjobs.allocated_cores(buildjobs.running_builds(conn))==4
            print('PASS: proven completion releases ordering, retaining game, port and full-build resources plus four cores')
            state=orch.load(conn,'fixture','first.md')
            result=check_events.finish(state['job'],0,'incorrect aggregate success must not override failures')
            assert set(result['failures'])=={'early','later'}
            assert result['results']['retry']['exit']==0
            assert len(result['results'])==4
            assert len(result['attempts'])==5
            assert all(Path(row['output_path']).is_file() for row in result['attempts'])
            assert check_events.verify(state['job'],worktree,head)==''
            artifact.write_bytes(b'replaced')
            assert 'artifact changed' in check_events.verify(state['job'],worktree,head)
            print('PASS: restart retains all results and retry output; exit zero cannot erase failures; changed artifact is rejected')
            print('HQ b76c3cb protocol SHA-256: '+hashlib.sha256(expected).hexdigest())
        finally:
            conn.close()
    return 0

if __name__=='__main__':
    sys.exit(main())
