"""Portable read-only R21B public-scope/compiler and native case verification.

No executor/candidate/model/prediction imports. Frozen artifacts never rewritten.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def canonical(v):return hashlib.sha256(json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def load(name):return json.loads((HERE/name).read_text())
def rows(name):return [json.loads(s) for s in (HERE/name).read_text().splitlines()]
def pointer(v,p):
    for t in p[1:].split('/'):
        t=t.replace('~1','/').replace('~0','~');v=v[int(t)] if isinstance(v,list) else v[t]
    return v


def verify(pre_realization=False):
    failures=[];checks=0
    def check(value,description):
        nonlocal checks
        checks+=1
        if not value:failures.append(description)
    freeze=load('SOURCE_MEASUREMENT_V2_FREEZE.json')
    before={p:sha(HERE/p) for p in freeze['files']}
    for p,expected in freeze['files'].items():check(sha(HERE/p)==expected,'R21B source/plan freeze '+p)
    check(sha(HERE/'CONFIRMATION_AUTHORITY_FREEZE.json')==freeze['r21a_authority_freeze_sha256'],'R21A authority remains unchanged')
    from verify_confirmation import verify as verify_r21a
    r21a=verify_r21a();check(r21a['passed'],'complete preserved R21A source/native verification')
    v1={s['task_key']:s for s in load('common_scopes.json')['tasks']}
    v2={s['task_key']:s for s in load('common_scopes_v2.json')['tasks']}
    packets={p['task_key']:p['packet'] for p in load('source_snapshot/task_packets.json')}
    check(len(v2)==57 and sum(s['supported'] for s in v2.values())==27,'57 source tasks / 27 supported scopes')
    changed=[]
    for key,s in v2.items():
        old=v1[key]
        check(s['source_packet_sha256']==old['source_packet_sha256']==canonical(packets[key]),'unchanged canonical source packet '+key)
        check(s['required_obligation_ids']==old['required_obligation_ids'],'unchanged atomic IDs '+key)
        check(s['scope_sha256']==canonical({k:v for k,v in s.items() if k!='scope_sha256'}),'canonical v2 scope '+key)
        check(s['scope_id']==key.replace('/','__')+'__common_source_v2','versioned public scope ID '+key)
        for a,b in zip(s['obligations'],old['obligations']):
            a=copy.deepcopy(a)
            if key=='travel/user_task_16' and a['binding_role']=='paris_london_flight':
                check(a.pop('entity_form')=='airline_name','value-free flight entity form')
                binding=a['entity_binding']
                check(binding.pop('source_field')=='airline_name' and binding.pop('native_source_path')=='/flights/flight_list/*/airline' and binding.pop('source_entity_value_disclosed') is False,'explicit source airline convention')
                changed.append(a['obligation_id'])
            check(a==b,'all original obligation semantics preserved '+a['obligation_id'])
    check(len(changed)==2,'exactly two flight metadata additions')
    contracts=rows('compiler_sanity/contracts_v2.jsonl');old_contracts={r['task_key']:r['contract'] for r in rows('compiler_sanity/contracts.jsonl')}
    from jsonschema import Draft202012Validator
    validator=Draft202012Validator(load('source_snapshot/output_schema_r21_2.json'))
    native_schemas=load('initial_state_schemas.json')['suites']
    clauses=0
    for r in contracts:
        key=r['task_key'];s=v2[key];c=r['contract'];old=old_contracts[key]
        check(not list(validator.iter_errors(c)) and c['ir_version']=='r21.2','public r21.2 compiler schema '+key)
        check(c['scope_id']==s['scope_id'] and r['scope_sha256']==s['scope_sha256'] and r['source_packet_sha256']==s['source_packet_sha256'],'compiler authority '+key)
        for a,b in zip(c['clauses'],old['clauses']):
            check(all(a[k]==b[k] for k in ['obligation_id','kind','state','query']),'private source operands unchanged '+a['obligation_id'])
            try:
                for p in a['support']['initial_state_paths']:pointer(packets[key]['initial_state'],p)
                for p in a['support']['schema_paths']:pointer(native_schemas[key.split('/')[0]],p)
                check(a['support']['request_quote'] in s['task_request'],'literal source quote '+a['obligation_id'])
            except (KeyError,TypeError,IndexError):check(False,'source/schema witness '+a['obligation_id'])
            clauses+=1
    check(len(contracts)==57 and clauses==43,'57 compiler sanity contracts /43 clauses')
    from confirmation_generator_v2 import plan
    planned=load('confirmation_plan_v2.json')
    check(planned==plan(),'new independent plan unchanged')
    check(len(planned['rows'])==204 and Counter(r['phase'] for r in planned['rows'])=={'test':186,'composite':18},'same retained 204-case allocation')
    from source_reference import evaluate as eval_old
    from source_reference_v2 import evaluate as evaluate
    for c in rows('development_cases_portable.jsonl'):
        observed=load(c['input_file']);a,b=eval_old(c['task_key'],observed),evaluate(c['task_key'],observed)
        check(a['reference_status']==b['reference_status'] and [(d['obligation_id'],d['status']) for d in a['obligation_decisions']]==[(d['obligation_id'],d['status']) for d in b['obligation_decisions']],'unchanged existing source decisions '+c['case_id'])
    counts=Counter();native_replays=0;proofs=0
    if pre_realization:
        check(not (HERE/'confirmation_v2').exists(),'zero new R21B inputs/native executions before root measurement freeze')
    else:
        cases=rows('confirmation_cases_v2_portable.jsonl');refs={r['case_id']:r for r in rows('confirmation_v2/private_reference.jsonl')}
        cf=load('confirmation_v2/FREEZE.json');mf=ROOT/'e2/MEASUREMENT_V3_FREEZE.json'
        check(sha(mf)==cf['measurement_method_freeze_sha256'],'root V3 method freeze binding')
        check(sha(HERE/'SOURCE_MEASUREMENT_V2_FREEZE.json')==cf['source_plan_freeze_sha256'],'pre-realization source/plan freeze binding')
        check(sha(HERE/'confirmation_generator_v2.py')==cf['generator_sha256'],'native generator bytes frozen before realization')
        check(sha(HERE/'source_reference.py')==cf['source_reference_semantics_sha256'],'independent parser/reference semantics unchanged')
        check((HERE/'confirmation_cases_v2_portable.jsonl').read_bytes()==(HERE/'confirmation_v2/cases.jsonl').read_bytes(),'portable exact adapter')
        check(sha(HERE/'confirmation_cases_v2_portable.jsonl')==cf['portable_adapter_sha256'],'portable adapter hash')
        for p,expected in cf['files'].items():check(sha(HERE/p)==expected,'new native case freeze '+p)
        check(len(cases)==len(refs)==204 and len({c['case_id'] for c in cases})==204,'204 distinct realized R21B IDs')
        check(Counter(c['phase'] for c in cases)=={'test':186,'composite':18},'186 primary /18 composite realizations')
        oldcases={c['case_id']:c for c in rows('confirmation_cases_portable.jsonl')}
        planned={r['plan_id']:r for r in planned['rows']}
        from native_runtime import initialize,execute
        from confirmation_generator import preparation_goal_proof
        for c in cases:
            cid,key=c['case_id'],c['task_key'];s=v2[key];r=refs[cid];p=planned[cid]
            check(all(c[k]==value for k,value in p.items()),'predefined allocation '+cid)
            o=load(c['input_file']);rawpath=ROOT/o['native_realization_receipt']['native_raw_file'];raw=json.loads(rawpath.read_text())
            check(sha(HERE/c['input_file'])==c['input_sha256']==r['input_sha256'],'source decision input hash '+cid)
            check(sha(rawpath)==o['native_realization_receipt']['native_raw_sha256'],'native raw binding '+cid)
            check(raw['source_initial_state']==packets[key]['initial_state'],'immutable source goal packet '+cid)
            result=evaluate(key,o)
            check(result['reference_status']==r['reference_status']==p['intended_source_status'] and result['obligation_decisions']==r['obligation_decisions'],'independent source-only status '+cid)
            check(r['scope_sha256']==s['scope_sha256'] and r['source_packet_sha256']==s['source_packet_sha256'] and r['scope_id']==s['scope_id'],'versioned source authority '+cid)
            env,rt=initialize(key.split('/')[0],copy.deepcopy(raw['source_initial_state']))
            check(execute(env,rt,raw['preparation_actions'])==raw['preparation_receipts'] and env.model_dump(mode='json')==raw['pre_state'],'native preparation/pre replay '+cid)
            check(execute(env,rt,raw['actions'])==raw['native_receipts'] and env.model_dump(mode='json')==raw['post_state'],'native action/post replay '+cid)
            check(not any(step['error'] for step in raw['preparation_receipts']+raw['native_receipts']),'all registered tool calls successful '+cid);native_replays+=1
            check(preparation_goal_proof(key,raw['source_initial_state'],raw['pre_state'])==raw['source_goal_preservation_proof'],'source goal preservation '+cid);proofs+=1
            oldc=oldcases[c['previous_plan_id']];oldo=load(oldc['input_file']);oldraw=json.loads((ROOT/oldo['native_realization_receipt']['native_raw_file']).read_text())
            check(raw['preparation_actions']==oldraw['preparation_actions'] and raw['actions'][1:]==oldraw['actions'] and len(raw['actions'])==len(oldraw['actions'])+1,'distinct extra native read; original effects unchanged '+cid)
            check(o['native_realization_receipt']['observation_mask']==oldo['native_realization_receipt']['observation_mask'],'observation policy/allocation unchanged '+cid)
            counts[r['reference_status']]+=1
        check(counts=={'pass':75,'fail':75,'unknown':54},'balanced source-confirmation counts')
    check({p:sha(HERE/p) for p in before}==before,'read-only verifier preserves all frozen source bytes')
    return {'passed':not failures,'checks':checks,'stage':'pre-realization' if pre_realization else 'post-realization','source_measurement_v2_freeze_sha256':sha(HERE/'SOURCE_MEASUREMENT_V2_FREEZE.json'),
      'r21a_preserved_verified':r21a['passed'],'r21a_native_replays':r21a['confirmation_native_replays'],'scope_tasks':57,'supported_scopes':27,'obligations':43,
      'compiler_contracts':57,'compiler_operands_unchanged':True,'reference_semantics_unchanged':True,'planned_primary':186,'planned_composite':18,
      'new_native_replays':native_replays,'source_goal_proofs':proofs,'new_counts':dict(counts),'no_model_or_prediction_access':True,'failures':failures}


def main(force_confirmation=False):
    parser=argparse.ArgumentParser();parser.add_argument('--pre-realization',action='store_true');parser.add_argument('--out',type=Path);args=parser.parse_args()
    if force_confirmation and args.pre_realization:parser.error('confirmation verifier requires realized frozen cases')
    if args.out and (args.out.exists() or args.out.resolve().is_relative_to(HERE)):raise SystemExit('--out must be new and outside frozen author folder')
    result=verify(args.pre_realization);output=json.dumps(result,indent=2)+'\n'
    if args.out:args.out.write_text(output)
    print(output,end='')
    if not result['passed']:raise SystemExit(1)

if __name__=='__main__':main()
