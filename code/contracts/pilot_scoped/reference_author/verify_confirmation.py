"""Read-only confirmation/source freeze-chain and native replay verifier.

Portable paths; no candidate/model/prediction or evaluator implementation read.
--out creates an external new receipt. Frozen labels/payloads are never rewritten.
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
def load(p):return json.loads(p.read_text())
def rows(p):return [json.loads(s) for s in p.read_text().splitlines()]


def verify():
    failures=[];count=0
    def check(value,description):
        nonlocal count
        count+=1
        if not value:failures.append(description)
    authority=load(HERE/'CONFIRMATION_AUTHORITY_FREEZE.json')
    before={p:sha(HERE/p) for p in authority['files']}
    for p,expected in authority['files'].items():check(sha(HERE/p)==expected,'confirmation authority hash '+p)
    method=load(ROOT/'e2/FINAL_METHOD_FREEZE.json')
    check(sha(ROOT/'e2/FINAL_METHOD_FREEZE.json')==authority['method_freeze_sha256'],'root method freeze hash')
    source=load(HERE/'source_scope_freeze.json')
    amendment=load(HERE/'CONFIRMATION_GENERATOR_AMENDMENT.json')
    check(sha(HERE/'source_scope_freeze.json')==method['source_freeze_sha256']==amendment['original_source_freeze_sha256'],'immutable original source freeze remains bound to final method')
    check(sha(HERE/amendment['archived_original_source_freeze_file'])==sha(HERE/'source_scope_freeze.json'),'byte-preserved original source freeze archive')
    amended=amendment['amended_files']
    check(set(amended)=={'confirmation_generator.py'},'only authorized native generator amended')
    for p,expected in source['files'].items():
        if p in amended:
            item=amended[p]
            check(item['original_sha256']==expected==sha(HERE/item['archived_original']),'archived original bound source '+p)
            check(item['current_sha256']==sha(HERE/p),'authorized amended source '+p)
        else:check(sha(HERE/p)==expected,'immutable bound source '+p)
    # Historical verifier remains byte-preserved. Its two stage-specific failures
    # are expected only after authorized realization and the declared amendment.
    from verify_frozen import verify as verify_source_development
    historical=verify_source_development()
    expected_stage={'source freeze hash confirmation_generator.py','no new confirmation materialized before root authorization'}
    check(set(historical['failures'])==expected_stage,'historical source verification differs only by authorized generator and realization stage')
    check(historical['development_native_replays']==204 and historical['grammar_probes']==17,'historical native/probe assurance unchanged')
    scopes={s['task_key']:s for s in load(HERE/'common_scopes.json')['tasks']}
    packets={p['task_key']:p['packet'] for p in load(HERE/'source_snapshot/task_packets.json')}
    plan=load(HERE/'confirmation_plan.json')
    planned={r['plan_id']:r for r in plan['rows']}
    casepath=HERE/'confirmation_v1/cases.jsonl'
    cases=rows(casepath);refs={r['case_id']:r for r in rows(HERE/'confirmation_v1/private_reference.jsonl')}
    check(sha(HERE/'confirmation_plan.json')==method['confirmation_plan_sha256']==authority['plan_sha256'],'immutable independent plan remains method-bound')
    check((HERE/'confirmation_cases_portable.jsonl').read_bytes()==casepath.read_bytes(),'portable adapter exact rows; no payload or label change')
    casefreeze=load(HERE/'confirmation_v1/FREEZE.json')
    check(casefreeze['root_method_freeze_sha256']==sha(ROOT/'e2/FINAL_METHOD_FREEZE.json'),'native case freeze method binding')
    check(casefreeze['plan_sha256']==sha(HERE/'confirmation_plan.json'),'native case freeze plan binding')
    for p,expected in casefreeze['files'].items():check(sha(HERE/p)==expected,'original native case freeze '+p)
    check(len(cases)==len(refs)==len(planned)==204,'204 realized frozen plan rows')
    check(len({c['case_id'] for c in cases})==204,'distinct confirmation IDs')
    phase=Counter(c['phase'] for c in cases)
    check(phase=={'test':186,'composite':18},'186 primary and 18 composite cases')
    check(len({c['task_key'] for c in cases if c['phase']=='test'})==23 and len({c['task_key'] for c in cases if c['phase']=='composite'})==4,'all retained 23+4 tasks')
    from native_runtime import initialize,execute
    from source_reference import evaluate
    replay_count=0;none_observations=0;grammar_unknown=0;unsupported=0;full_state_masks=0;counts=Counter();phase_status={}
    source_goal_proofs=0
    for c in cases:
        cid,key=c['case_id'],c['task_key'];scope=scopes[key];r=refs[cid];p=planned[cid]
        check(all(c[k]==v for k,v in p.items()),'immutable realization plan allocation '+cid)
        check(c['scope_sha256']==r['scope_sha256']==scope['scope_sha256'] and c['source_packet_sha256']==r['source_packet_sha256']==scope['source_packet_sha256'],'204 source/scope authority bindings '+cid)
        check(scope['source_packet_sha256']==canonical(packets[key]),'canonical source packet '+cid)
        observed=load(HERE/c['input_file'])
        check(sha(HERE/c['input_file'])==c['input_sha256']==r['input_sha256'],'frozen input label hash '+cid)
        rawpath=ROOT/observed['native_realization_receipt']['native_raw_file'];raw=load(rawpath)
        check(sha(rawpath)==observed['native_realization_receipt']['native_raw_sha256'],'raw native hash '+cid)
        check(raw['source_initial_state']==packets[key]['initial_state'],'immutable base packet goal state '+cid)
        check(raw['source_packet_sha256']==scope['source_packet_sha256'],'raw source packet hash '+cid)
        result=evaluate(key,observed)
        check(result['reference_status']==r['reference_status']==p['intended_source_status'] and result['obligation_decisions']==r['obligation_decisions'],'independent strict source decisions '+cid)
        check([o['obligation_id'] for o in r['obligation_decisions']]==scope['required_obligation_ids'],'exact per-obligation label coverage '+cid)
        env,rt=initialize(key.split('/')[0],copy.deepcopy(raw['source_initial_state']))
        prep=execute(env,rt,raw['preparation_actions']);check(prep==raw['preparation_receipts'],'native preparation receipts '+cid)
        check(env.model_dump(mode='json')==raw['pre_state'],'native pre-state '+cid)
        acts=execute(env,rt,raw['actions']);check(acts==raw['native_receipts'],'native action receipts '+cid)
        check(env.model_dump(mode='json')==raw['post_state'],'native post-state '+cid)
        check(not any(step['error'] for step in prep+acts),'registered native successful realization '+cid)
        replay_count+=1
        # Independent conservative source-goal preservation checks on preparation.
        a,b=raw['source_initial_state'],raw['pre_state'];suite=key.split('/')[0]
        if suite=='banking':
            check(a['filesystem']==b['filesystem'] and a['user_account']==b['user_account'],'bank source files/account unchanged by prep '+cid)
            for section in ['transactions','scheduled_transactions']:
                current={t['id']:t for t in b['bank_account'][section]}
                check(all(current.get(t['id'])==t for t in a['bank_account'][section]),'original bank goal transactions unchanged '+cid)
        elif suite=='slack':
            check(a['web']==b['web'] and a['slack']['channel_inbox']==b['slack']['channel_inbox'],'Slack source webpage/channel counts unchanged '+cid)
            check(set(a['slack']['users'])==set(b['slack']['users']) and a['slack']['channels']==b['slack']['channels'] and a['slack']['user_channels']==b['slack']['user_channels'],'Slack source identities/channel memberships unchanged '+cid)
            if key not in ['slack/user_task_13','slack/user_task_14']:
                check(a['slack']['user_inbox']==b['slack']['user_inbox'],'Slack source direct messages unchanged '+cid)
        else:check(a==b,'travel immutable source catalogs '+cid)
        proof=raw['source_goal_preservation_proof']
        check(proof['source_goal_fields_preserved'] and proof['base_state_sha256']==canonical(a) and proof['prepared_state_sha256']==canonical(b) and observed['native_realization_receipt']['source_goal_preservation_proof']==proof,'source-goal proof/hash binding '+cid);source_goal_proofs+=1
        mask=observed['native_realization_receipt']['observation_mask']
        if mask:
            check(mask in ['pre_state','post_state'] and observed[mask] is None,'explicit whole required snapshot mask '+cid)
            check(evaluate(key,{'pre_state':raw['pre_state'],'post_state':raw['post_state'],'output':raw['output']})['reference_status']=='pass','masked full native state realizes valid scoped effect '+cid)
            full_state_masks+=1
        for observation in ['pre_state','post_state','output']:
            if observation!=mask:check(observed[observation]==raw[observation],'unmasked direct observation equals raw '+cid+' '+observation)
        none_observations+=any(observed[k] is None for k in ['pre_state','post_state','output'])
        grammar_unknown+=c['mode']=='out_of_grammar';unsupported+=not scope['supported']
        counts[r['reference_status']]+=1;phase_status.setdefault(c['phase'],Counter())[r['reference_status']]+=1
    check(counts=={'pass':75,'fail':75,'unknown':54},'balanced confirmation source counts')
    check(full_state_masks==22 and none_observations==26 and grammar_unknown==4 and unsupported==24,'explicit unknown mechanisms: 22 state masks +4 unavailable outputs +4 grammar unknowns +24 unsupported')
    check({p:sha(HERE/p) for p in before}==before,'read-only verification preserves all frozen authority bytes')
    return {'passed':not failures,'checks':count,'source_freeze_sha256':sha(HERE/'source_scope_freeze.json'),'confirmation_authority_freeze_sha256':sha(HERE/'CONFIRMATION_AUTHORITY_FREEZE.json'),
      'method_freeze_sha256':sha(ROOT/'e2/FINAL_METHOD_FREEZE.json'),'amendment_sha256':sha(HERE/'CONFIRMATION_GENERATOR_AMENDMENT.json'),
      'adapter_sha256':sha(HERE/'confirmation_cases_portable.jsonl'),'source_frozen_files':len(source['files']),'confirmation_frozen_files':len(authority['files']),
      'development_native_replays':historical['development_native_replays'],'confirmation_native_replays':replay_count,'source_goal_preservation_proofs':source_goal_proofs,
      'primary_cases':phase['test'],'composite_cases':phase['composite'],'counts':dict(counts),'phase_counts':{p:dict(c) for p,c in phase_status.items()},
      'state_masks_with_source_valid_full_native_state':full_state_masks,'unavailable_whole_observations':none_observations,'out_of_grammar_unknowns':grammar_unknown,'unsupported_scope_cases':unsupported,
      'all_reference_obligations_source_only':True,'no_human_annotations':True,'no_candidate_or_prediction_access':True,'failures':failures}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path);args=parser.parse_args()
    if args.out and (args.out.exists() or args.out.resolve().is_relative_to(HERE)):raise SystemExit('--out must be a new path outside frozen reference author folder')
    result=verify();text=json.dumps(result,indent=2)+'\n'
    if args.out:args.out.write_text(text)
    print(text,end='')
    if not result['passed']:raise SystemExit(1)

if __name__=='__main__':main()
