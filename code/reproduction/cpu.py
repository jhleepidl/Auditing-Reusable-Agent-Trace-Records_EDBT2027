"""Generate every retained-candidate prediction from inputs, then validate digests.

Original scientific engines and regression suites execute in a temporary import
layout. The sole runner adaptation redirects its historical baseline lookup to
the original-policy predictions generated earlier in this same run. No prior
prediction, diagnostic, or construction file is supplied to execution.
"""
from __future__ import annotations
import argparse
import contextlib
import importlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import hashlib
sys.dont_write_bytecode=True
from release_io import load, write, sha, canonical, equal

def require(condition,message):
    if not condition:raise ValueError(message)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--workspace',type=Path,required=True)
    ap.add_argument('--release',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args();start=time.monotonic()
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    study=args.workspace/'studies/frontend';upstream=args.workspace/'studies/frozen'
    os.environ['R22_ROOT']=str(upstream)
    sys.path.insert(0,str(study/'tools'))
    frozen=importlib.import_module('common')
    for rel,digest in load(study/'plans/PLAN_FREEZE.json')['bindings'].items():
        require(sha(upstream/rel)==digest,'Plan source binding: '+rel)
    for rel,digest in load(study/'plans/FRONTEND_FREEZE.json')['files'].items():
        require(sha(study/rel)==digest,'Frontend source binding: '+rel)
    tests=[]
    suites=[(upstream/'derivation','test_runtime.py','previous runtime'),
            (upstream/'derivation_v2','test_runtime.py','runtime'),
            (upstream/'repair/method_v3','test_executor.py','interpreter'),
            (study/'tests','test_frontend.py','frontend policies')]
    with (out/'tests.log').open('w',encoding='utf-8') as log:
        for path,pattern,name in suites:
            run=subprocess.run([sys.executable,'-B','-m','unittest','discover','-s',str(path),'-p',pattern,'-v'],
                capture_output=True,text=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
            text=run.stdout+run.stderr;log.write(name+'\n'+text+'\n')
            require(run.returncode==0,name+': regression failure')
            match=re.search(r'Ran (\d+) tests?',text);require(match is not None,'Missing test count')
            tests.append({'suite':name,'passed':int(match[1])})
    print('Scientific regression tests:',sum(t['passed'] for t in tests),flush=True)
    modules={n:importlib.import_module(n) for n in ['run_factorial','score_factorial','run_capability','run_capability_exact','score_capability','score_capability_exact']}
    work=out/'execution';work.mkdir()
    for folder in ['plans','programs','programs_exact','method','tests']:
        shutil.copytree(study/folder,work/folder)
    for m in modules.values():m.STUDY=work
    runner=modules['run_factorial'];original_rows=runner.rows
    baseline_prefix=(upstream/'evaluation').resolve()
    def regenerated_baseline_rows(path):
        path=Path(path).resolve()
        if path.is_relative_to(baseline_prefix):
            relative=path.relative_to(baseline_prefix)
            require(len(relative.parts)==2 and relative.name=='predictions.jsonl','Unexpected baseline dependency')
            generated=work/'results/factorial'/relative.parts[0]/'old/predictions.jsonl'
            require(generated.is_file(),'Original policy must run first')
            return original_rows(generated)
        return original_rows(path)
    runner.rows=regenerated_baseline_rows
    # These dependencies intentionally do not exist in the lean input release.
    require(not (study/'results').exists(),'Unexpected retained frontend outputs')
    require(not (upstream/'evaluation').exists(),'Unexpected retained prediction inputs')
    with (out/'execution.log').open('w',encoding='utf-8') as log:
        with contextlib.redirect_stdout(log):
            modules['run_capability'].main();modules['run_capability_exact'].main()
        for stage,run,dataset,mode in runner.STAGES:
            with contextlib.redirect_stdout(log):
                for policy in runner.POLICIES:runner.execute(stage,run,dataset,mode,policy)
            print('Generated',stage,'/ four frontends',flush=True)
        # Reference judgments are opened for scoring only after all predictions exist.
        with contextlib.redirect_stdout(log):
            modules['score_capability'].main();modules['score_capability_exact'].main();modules['score_factorial'].main()
    expectations=load(args.release/'expected/output_checksums.json');comparisons=[]
    for rel,meta in sorted(expectations.items()):
        path=work/'results'/rel;require(path.is_file(),'Missing generated output '+rel)
        rows=frozen.rows(path);require(len(rows)==meta['rows'],'Row count '+rel)
        if meta['normalization']=='json_array_without_compile_ms':
            for row in rows:row.pop('compile_ms',None)
            observed=hashlib.sha256(canonical(rows)).hexdigest()
        else:observed=sha(path)
        require(observed==meta['sha256'],'Output digest mismatch '+rel)
        comparisons.append({'file':rel,'rows':len(rows),'match':True,'normalization':meta['normalization']})
    summary=load(work/'results/FACTORIAL_SUMMARY.json');summary.pop('utc',None)
    equal(summary,load(args.release/'expected/frontend_summary.json'),'factorial summary')
    for mode in ['capability','capability_exact']:
        summary=load(work/'results'/mode/'SCORED_SUMMARY.json');summary.pop('utc',None)
        equal(summary,load(args.release/'expected'/f'{mode}.json'),mode)
    pred=[r for r in comparisons if r['file'].endswith('predictions.jsonl')]
    report={'status':'PASS','scientific_unit_tests':tests,'output_files_checked':len(comparisons),
        'prediction_diagnostic_pairs':len(pred),'factorial_cells':sum(r['rows'] for r in pred if r['file'].startswith('factorial/')),
        'all_cells':sum(r['rows'] for r in pred),'comparisons':comparisons,'provider_calls':0,'fresh_native_execution':False,
        'regenerated_from_inputs':True,'retained_prediction_files_read':0,'elapsed_seconds':round(time.monotonic()-start,3)}
    shutil.move(str(work/'results'),out/'results');shutil.rmtree(work)
    write(out/'verification.json',report)
    print('PASS: all generated output digests and task statistics match',flush=True)

if __name__=='__main__':main()
