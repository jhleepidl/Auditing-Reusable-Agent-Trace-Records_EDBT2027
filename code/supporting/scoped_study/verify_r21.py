"""Read-only R21 artifact verification; never makes model/API calls.

Use the pinned Python 3.11.7 environment documented in README_R21.txt.
--replay reexecutes native E1 programs and all frozen model predictions offline.
"""
import argparse, collections, hashlib, json, os, subprocess, sys, tempfile
from pathlib import Path
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parent

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p): return json.loads(Path(p).read_text())
def rows(p): return [json.loads(s) for s in Path(p).read_text().splitlines() if s.strip()]
def manifest(folder,name):
    m=load(folder/name)
    entries=m['files'].items() if isinstance(m['files'],dict) else ((e['path'],e) for e in m['files'])
    for path,entry in entries:
        expected=entry['sha256'] if isinstance(entry,dict) else entry
        assert sha(folder/path)==expected,('hash mismatch',folder,path)
    return len(m['files'])
def run(cmd,env):
    p=subprocess.run([sys.executable,*map(str,cmd)],env=env,capture_output=True,text=True)
    assert p.returncode==0,p.stdout+p.stderr
    return p.stdout
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--replay',action='store_true');parser.add_argument('--out',type=Path)
    a=parser.parse_args();checked={}
    if (R/'FINAL_MANIFEST_R21.json').exists():checked['R21_payloads']=manifest(R,'FINAL_MANIFEST_R21.json')
    checked['frozen_R20_payloads']=manifest(R/'baseline_r20','FILE_MANIFEST_R20.json')
    checked['E1_payloads']=manifest(R/'e1','FINAL_MANIFEST.json')
    checked['independent_provider_audit_payloads']=manifest(R/'validation/provider_method_independent','FINAL_MANIFEST.json')
    f=load(R/'e2/FINAL_METHOD_FREEZE.json')
    assert f['selected_version']=='v2' and f['confirmation_case_inputs_generated']==f['confirmation_model_calls']==0
    assert sha(R/'e2/DEVELOPMENT_SELECTION.json')==f['selection_sha256']
    assert sha(R/'e2/PROTOCOL.json')==f['protocol_sha256']
    assert sha(R/'e2/reference_author/common_scopes.json')==f['public_scope_sha256']
    for path,h in f['files'].items():assert sha(R/'e2'/path)==h,path
    v3=load(R/'e2/MEASUREMENT_V3_FREEZE.json')
    for path,h in v3['files'].items():assert sha(R/path)==h,path
    sourcefreeze=R/'e2/reference_author/source_scope_freeze.json'
    if sha(sourcefreeze)!=f['source_freeze_sha256']:
        assert any(sha(p)==f['source_freeze_sha256'] for p in (R/'e2/reference_author').rglob('source_scope_freeze.json')),'Original source freeze not preserved'
    endfiles=sorted((R/'e2').rglob('PROVIDER_END.json'));spend=0;calls=0;reserve=0;model_errors=0
    for path in endfiles:
        e=load(path);raw=[load(p) for p in (path.parent/'responses').glob('*.json')]
        assert len(raw)==e['requests'] and sum(r['api_attempted'] for r in raw)==e['api_attempts']
        assert len({r['request_id'] for r in raw})==len(raw)
        cost=sum(r['cost_usd'] for r in raw);uncertain=sum(r.get('uncertain_cost_reserve_usd',0) for r in raw)
        assert abs(cost-e['usage_cost_usd'])<1e-9 and abs(uncertain-e['uncertain_cost_reserve_usd'])<1e-9
        assert sum(r['status']!='completed' for r in raw)==e['errors']
        spend+=cost;reserve+=uncertain;calls+=e['api_attempts'];model_errors+=e['errors']
    assert len(list((R/'e2').rglob('PROVIDER_START.json')))==len(endfiles),'Interrupted run must be reserved/reported'
    prior=8.1957672;assert prior+spend+reserve<=30
    ledger=load(R/'COST_LEDGER_R21.json');assert abs(ledger['new_usage_cost_usd']-spend)<1e-9
    assert ledger['new_api_attempts']==calls and abs(ledger['aggregate_prior_plus_new_usd']-(prior+spend+reserve))<1e-9
    env=os.environ.copy();env.update(PYTHONHASHSEED='0',PYTHONDONTWRITEBYTECODE='1',EDBT_R20_ROOT=str(R/'baseline_r20'))
    output={}
    output['E1']=run([R/'e1/verify.py',*(['--replay'] if a.replay else [])],env)
    output['independent_provider_audit']=run([R/'validation/provider_method_independent/verify.py'],env)
    # Historical verify_frozen is a pre-realization stage guard. The complete
    # confirmation verifier checks its only two authorized stage differences,
    # the original freeze/archive, development and new native realizations.
    confirmation_verifier=R/'e2/reference_author/verify_confirmation.py'
    assert confirmation_verifier.exists(),'Missing confirmation native replay verifier'
    output['confirmation']=run([confirmation_verifier],env)
    output['confirmation_corrected_measurement']=run([R/'e2/reference_author/verify_confirmation_v2.py'],env)
    output['final_scientific_review']=run([R/'validation/final_scientific_review/verify.py'],env)
    with tempfile.TemporaryDirectory(prefix='edbt_r21_verify_') as temporary:
        temporary=Path(temporary)
        specs=[('development_v1','development_v1_run','reference_author/development_cases_portable.jsonl','reference_author/private_reference/development_reference_v1.jsonl','development_v1_predictions','development_v1_metrics','score21.py'),
               ('development_v2','development_v2_run','reference_author/development_cases_portable.jsonl','reference_author/private_reference/development_reference_v1.jsonl','development_v2_predictions','development_v2_metrics','score21_v2.py')]
        if a.replay:
            for name,provider,cases,refs,pred,metrics,scorer in specs:
                dest=temporary/name
                run([R/'e2/evaluate21.py','--run',R/'e2'/provider,'--cases',R/'e2'/cases,'--out',dest],env)
                for file in ['predictions.jsonl','diagnostics.jsonl','construction_validation.jsonl']:
                    assert (dest/file).read_bytes()==(R/'e2'/pred/file).read_bytes(),(name,file)
        for name,provider,cases,refs,pred,metrics,scorer in specs:
            dest=temporary/(name+'_metrics')
            run([R/'e2'/scorer,'--reference',R/'e2'/refs,'--predictions',R/'e2'/pred/'predictions.jsonl','--out',dest],env)
            assert load(dest/'METRICS.json')==load(R/'e2'/metrics/'METRICS.json'),name
        if a.replay:
            dest=temporary/'confirmation'
            run([R/'e2/evaluate21.py','--run',R/'e2/confirmation_v2_run','--cases',R/'e2/reference_author/confirmation_cases_portable.jsonl','--out',dest],env)
            for file in ['predictions.jsonl','diagnostics.jsonl','construction_validation.jsonl']:
                assert (dest/file).read_bytes()==(R/'e2/confirmation_v2_predictions'/file).read_bytes(),file
        for phase in ['primary','composite']:
            source=R/'e2/confirmation_v2_split'/phase;dest=temporary/(phase+'_metrics')
            run([R/'e2/score21_v2.py','--reference',source/'reference.jsonl','--predictions',source/'predictions.jsonl','--out',dest],env)
            assert load(dest/'METRICS.json')==load(R/('e2/confirmation_v2_'+phase+'_metrics/METRICS.json')),phase
        if a.replay:
            dest=temporary/'confirmation_corrected_measurement'
            run([R/'e2/evaluate21_v3.py','--run',R/'e2/confirmation_v3_run','--cases',R/'e2/reference_author/confirmation_cases_v2_portable.jsonl','--out',dest],env)
            for file in ['predictions.jsonl','diagnostics.jsonl','construction_validation.jsonl']:
                assert (dest/file).read_bytes()==(R/'e2/confirmation_v3_predictions'/file).read_bytes(),file
        for phase in ['primary','composite']:
            source=R/'e2/confirmation_v3_split'/phase;dest=temporary/(phase+'_measurement_v3_metrics')
            run([R/'e2/score21_v2.py','--reference',source/'reference.jsonl','--predictions',source/'predictions.jsonl','--out',dest],env)
            assert load(dest/'METRICS.json')==load(R/('e2/confirmation_v3_'+phase+'_metrics/METRICS.json')),phase
    output['manuscript']=run([R/'manuscript_r21/tools/verify_r21_manuscript.py'],env)
    result={'status':'PASS','checked_payload_counts':checked,'native_E1_full_replay':a.replay,'frozen_model_prediction_replay':a.replay,
            'metrics_recomputed':True,'new_api_attempts':calls,'new_usage_cost_usd':spend,'uncertain_cost_reserve_usd':reserve,
            'prior_R20_usage_usd':prior,'aggregate_usd':prior+spend+reserve,'model_errors_retained':model_errors,'API_calls_during_verification':0,'subverifier_outputs':output}
    if a.out:a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
