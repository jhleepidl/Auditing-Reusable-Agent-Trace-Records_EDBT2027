"""Reproduce paper results from retained inputs into a new output directory.

Default: recorded checkpoint/read/cost analysis and full deterministic CPU replay.
--check-only skips contract execution. Neither mode makes provider calls or runs
new native tools. --native/--timings require the original pinned environment.
"""
from __future__ import annotations
import argparse
import importlib.metadata
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tempfile
import time
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'code/reproduction'))
from release_io import Inputs,load,write

def environment_errors():
    expected=load(ROOT/'configs/environment/native.json');errors=[]
    if platform.python_version()!=expected['python'].split()[0]:errors.append('Python '+expected['python'].split()[0]+' required')
    for name,version in expected['dependency_pins'].items():
        try:got=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:got='not installed'
        if got!=version:errors.append(f'{name}: expected {version}; found {got}')
    return errors

def invoke(command,log,env):
    with log.open('w',encoding='utf-8') as stream:
        p=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT,env=env,text=True)
    if p.returncode:raise RuntimeError(f'Command failed ({p.returncode}); see {log.name}')

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    modes=ap.add_mutually_exclusive_group()
    modes.add_argument('--check-only',action='store_true',help='Standard-library checkpoint/read/cost checks only.')
    modes.add_argument('--native',action='store_true',help='Run native checkpoints and reads with original pins.')
    modes.add_argument('--timings',action='store_true',help='Collect new native timings with original pins.')
    ap.add_argument('--cpu',action='store_true',help='Compatibility alias for the default full CPU mode.')
    ap.add_argument('--output',type=Path,required=True,help='A NEW directory outside the artifact.')
    args=ap.parse_args()
    if not __debug__:ap.error('Do not use python -O; the frozen engines validate with assertions.')
    if args.cpu and (args.check_only or args.native or args.timings):ap.error('--cpu cannot be combined with another mode.')
    output=args.output.expanduser().resolve()
    if output.exists() or output.is_relative_to(ROOT):ap.error('Choose a NEW output directory outside the artifact.')
    output.mkdir(parents=True,exist_ok=False)
    start=time.monotonic();report={'status':'FAIL','provider_calls':0,'fresh_native_execution':False,
        'fresh_timings':False,'python':sys.version,'input_mode':'lean reproduction release'};code=1
    try:
        inputs=Inputs();report['integrity']=inputs.verify();print('Input integrity: PASS',flush=True)
        from checkpoints import run
        from tables import export, csv_file
        from census import run as census_run
        checkpoint=run(inputs,output/'checkpoint');report['checkpoint']=checkpoint
        census=census_run(inputs,output/'checkpoint');report['census_record_groups']=len(census)
        csv_file(output/'tables/table3_census.csv',census)
        fresh=None;env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONHASHSEED='0')
        if args.native or args.timings:
            errors=environment_errors()
            if errors:
                report['status']='BLOCKED';report['native_environment_errors']=errors;code=3
            else:
                with tempfile.TemporaryDirectory(prefix='native-',dir=output) as temp:
                    workspace=Path(temp);inputs.materialize(inputs.groups['native'],workspace)
                    invoke([sys.executable,'-B',str(ROOT/'code/reproduction/native.py'),'--workspace',str(workspace),
                        '--release',str(ROOT),'--output',str(output/'native')]+(['--timings'] if args.timings else []),output/'native.log',env)
                report['native']=load(output/'native/verification.json');report['fresh_native_execution']=True
                report['fresh_timings']=args.timings;report['status']='PASS';code=0
        elif not args.check_only:
            importlib.metadata.version('jsonschema')
            invoke([sys.executable,'-B','-m','unittest','discover','-s',str(ROOT/'tests'),'-p','test_*.py','-v'],output/'release_tests.log',env)
            log=(output/'release_tests.log').read_text();match=re.search(r'Ran (\d+) tests?',log)
            report['release_tests']=int(match[1]) if match else None
            print('Re-executing frozen candidates; outputs are being generated.',flush=True)
            with tempfile.TemporaryDirectory(prefix='cpu-',dir=output) as temp:
                workspace=Path(temp);report['cpu_input_files']=inputs.materialize(inputs.groups['cpu'],workspace)
                invoke([sys.executable,'-B',str(ROOT/'code/reproduction/cpu.py'),'--workspace',str(workspace),
                    '--release',str(ROOT),'--output',str(output/'cpu')],output/'cpu.log',env)
            report['cpu']=load(output/'cpu/verification.json');fresh=output/'cpu/results/FACTORIAL_SUMMARY.json'
            report['status']='PASS';code=0
        else:report['status']='PASS';code=0
        report['tables']=export(inputs,checkpoint,output,fresh)
        report['integrity_after']=inputs.verify()
    except Exception as exc:
        report['status']='FAIL';report['error']=f'{type(exc).__name__}: {exc}';print(report['error'],file=sys.stderr)
        code=1
    report['elapsed_seconds']=round(time.monotonic()-start,3);write(output/'summary.json',report)
    print(report['status']+': '+str(output/'summary.json'),flush=True)
    return code

if __name__=='__main__':raise SystemExit(main())
