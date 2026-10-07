#!/usr/bin/env python3
"""Complete relocatable scientific verification, without provider/model calls."""
import argparse, datetime, json, os, subprocess, sys, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from package_results import inventory, credential_scan

def execute(rel,*args):
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONHASHSEED='0')
    result=subprocess.run([sys.executable,str(ROOT/rel),*map(str,args)],env=env,capture_output=True,text=True)
    assert result.returncode==0,rel+'\n'+result.stdout+'\n'+result.stderr
    return result.stdout

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path);p.add_argument('--skip-native-program-replay',action='store_true');a=p.parse_args()
    started=datetime.datetime.now(datetime.timezone.utc).isoformat()
    manifest=ROOT/'FILE_MANIFEST_R20.json'
    frozen=json.loads(manifest.read_text())['files'] if manifest.exists() else None
    if frozen is not None:assert inventory()==frozen,'File inventory/hash mismatch before verification'
    scan=credential_scan(); steps=[]
    with tempfile.TemporaryDirectory(prefix='r20-complete-verification-') as td:
        temp=Path(td)
        plan=[('handoff_integrity','EDBT_R20_VALIDATION_HANDOFF/tools/verify_handoff.py',[]),
              ('retained_compatibility','verify_retained.py',['--out',temp/'retained.json']),
              ('e1_retained_recovery','e1/verify.py',[]),
              ('e1_new_native_graph','e1/v5/verify.py',[]),
              ('e2_reference','e2/reference_audit/verify_frozen.py',['--out',temp/'reference.json']),
              ('e2_native_comparator','e2/native_comparator/verify.py',[]),
              ('e2_model_execution_scoring','e2/verify_results.py',['--out',temp/'e2.json']),
              ('manuscript','manuscript_r20/tools/verify_r20_manuscript.py',['--out',temp/'paper.json'])]
        if not a.skip_native_program_replay:plan.insert(4,('e1_full_new_program_reexecution','e1/v5/verify_replay.py',[]))
        for name,rel,args in plan:
            print('Verifying '+name,flush=True)
            output=execute(rel,*args)
            steps.append(dict(check=name,status='PASS',receipt=output.strip()))
        result=dict(status='PASS',started_utc=started,finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    file_manifest_present=frozen is not None,file_manifest_entries=len(frozen) if frozen else None,
                    credential_scan=scan,checks=steps,api_calls_made=0,human_annotations_added=0,
                    retained_replay_boundary=json.loads((temp/'retained.json').read_text()),
                    caveat='Original R18 Python3.11 replay byte checker fails on explicitly reproduced Python3.13 AST rendering metadata; frozen source and every scientific output remain unchanged. Venue readiness and whole-task semantic gold are not certified.')
    if frozen is not None:assert inventory()==frozen,'Verification mutated frozen package bytes'
    if a.out:
        assert not a.out.resolve().is_relative_to(ROOT),'Write verification receipts outside the frozen package'
        a.out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
