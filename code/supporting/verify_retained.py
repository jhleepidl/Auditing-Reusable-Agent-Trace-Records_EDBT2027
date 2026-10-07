#!/usr/bin/env python3
"""Verify immutable R18 evidence and explicit Python AST metadata compatibility.

The original --replay checker fails byte equality on three ast.dump hashes:
R18 used Python3.13.5; the pinned native environment uses Python3.11.7.
No frozen bytes are patched. This verifier requires all decision rows unchanged
and reproduces all historical AST hashes with the documented 3.13 empty-field
elision, alongside checking the unchanged full source-file SHA256.
See https://docs.python.org/3.13/library/ast.html#ast.dump
"""
import argparse, ast, copy, hashlib, json, subprocess, sys, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent
KIT=ROOT/'work/native/EDBT_R18_CPU_RESULTS/EDBT_R18_NO_HUMAN_KIT'

def load(p):return json.loads(p.read_text())
def run(script,out):
    r=subprocess.run([sys.executable,str(KIT/'tools'/script),'--out',str(out)],capture_output=True,text=True)
    assert r.returncode==0,r.stdout+r.stderr

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path);a=ap.parse_args()
    r=subprocess.run([sys.executable,str(KIT/'tools/verify_package.py')],capture_output=True,text=True)
    assert r.returncode==0,r.stdout+r.stderr
    static=json.loads(r.stdout)
    source=KIT/'vendor/agentdojo/src/agentdojo/default_suites/v1/workspace/user_tasks.py'
    tree=ast.parse(source.read_text()); normalized={}
    for task in [2,5,10]:
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==f'UserTask{task}')
        f=copy.deepcopy(next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='utility'))
        for node in ast.walk(f):
            for k,v in list(ast.iter_fields(node)):
                if v is None or v==[]:delattr(node,k)
        normalized[str(task)]=hashlib.sha256(ast.dump(f,include_attributes=False).encode()).hexdigest()
    with tempfile.TemporaryDirectory(prefix='r20-retained-verify-') as td:
        temp=Path(td);run('run_offline.py',temp/'offline')
        exact=[]
        for name in ['interpreter_replay.json','interpreter_rows.json','query_rows.json','workspace20_inventory.json']:
            assert (temp/'offline'/name).read_bytes()==(KIT/'results/local_v1'/name).read_bytes(),name
            exact.append(name)
        old=load(KIT/'results/local_v1/query_summary.json'); new=load(temp/'offline/query_summary.json')
        differences=[]
        for task in ['2','5','10']:
            oo=old['kernel_provenance'][task];nn=new['kernel_provenance'][task]
            assert oo['source_file_sha256']==nn['source_file_sha256']==hashlib.sha256(source.read_bytes()).hexdigest()
            assert oo['utility_ast_sha256']==normalized[task]
            if oo['utility_ast_sha256']!=nn['utility_ast_sha256']:
                differences.append(dict(task=task,historical_ast_sha256=oo['utility_ast_sha256'],current_ast_sha256=nn['utility_ast_sha256']))
            nn['utility_ast_sha256']=normalized[task]
        assert old==new,'Difference beyond the explicitly reproduced AST rendering metadata'
        run('run_scoped_saved.py',temp/'scope')
        for name in ['rows.json','SUMMARY.json']:
            assert (temp/'scope'/name).read_bytes()==(KIT/'results/scoped_saved_v1'/name).read_bytes(),name
            exact.append('scoped_saved/'+name)
    result=dict(status='PASS_WITH_EXPLICIT_AST_METADATA_COMPATIBILITY',static=static,
                byte_exact_recomputed_outputs=exact,query_decision_rows=3044,interpreter_cases=98,
                historical_python=load(KIT/'results/local_v1/timing.json')['environment']['python'],current_python=sys.version,
                original_verifier_replay_status='FAILED: query_summary.json utility_ast_sha256 byte comparison under Python3.11; retained unmodified',
                metadata_differences=differences,all_historical_ast_hashes_reproduced=True,
                source_bytes_unchanged=True,all_scientific_decisions_unchanged=True,
                documentation='https://docs.python.org/3.13/library/ast.html#ast.dump',api_calls=0)
    if a.out:a.out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))

if __name__=='__main__':main()
