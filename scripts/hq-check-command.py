"""Journal an opaque compile/deployment command without letting nested commands write its journal."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from hq_check_events import Session, child_environment, build_artifacts
from owned_process import OwnedProcess

# Preserve aggregate exit status while binding complete logs and resources to the HQ run.
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--repo',type=Path,required=True)
    parser.add_argument('--name',required=True)
    parser.add_argument('--timeout',type=int,default=14400)
    parser.add_argument('command',nargs=argparse.REMAINDER)
    args=parser.parse_args()
    command=args.command[1:] if args.command[:1]==['--'] else args.command
    token=os.environ.get('HQ_CHECK_RUN','manual')
    token=''.join(c for c in token if c.isalnum() or c in '-_')
    session=Session(args.repo,args.repo/'out'/('hq-'+args.name+'-'+token+'.txt'),[args.name],build_artifacts(args.repo))
    if session.initial_error:
        session.result(args.name,125,session.initial_error,kind='prerequisite')
        return session.finish()
    try:
        child=OwnedProcess(command,cwd=args.repo,env=child_environment(os.environ),stdin=subprocess.DEVNULL,
                           stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace')
        code,output=child.collect(args.timeout,stream=True)
    except (OSError,RuntimeError,subprocess.SubprocessError) as error:
        code,output=125,str(error)
        print(output,flush=True)
    session.result(args.name,int(code),output)
    status=session.finish()
    return code if code else status

if __name__=='__main__':
    sys.exit(main())
