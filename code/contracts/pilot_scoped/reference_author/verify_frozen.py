"""Read-only portable R21 source/reference verification; no candidate access.

Prints JSON. --out may create a new receipt outside this frozen author folder.
Never writes/recreates existing frozen probes, native data, or reference labels.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import importlib.metadata
import json
import os
import sys
from collections import Counter
from pathlib import Path
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
BASE=Path(os.environ.get('EDBT_R20_ROOT',ROOT/'baseline_r20' if (ROOT/'baseline_r20').exists() else ROOT.parent/'edbt_r20_followup')).resolve()


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def canonical(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def load(name):return json.loads((HERE/name).read_text())
def rows(name):return [json.loads(line) for line in (HERE/name).read_text().splitlines()]
def pointer(value,path):
    if path=='':return value
    for token in path[1:].split('/'):
        token=token.replace('~1','/').replace('~0','~')
        value=value[int(token)] if isinstance(value,list) else value[token]
    return value


def verify():
    failures=[];checks=Counter()
    def check(condition,description):
        checks['checks']+=1
        if not condition:failures.append(description)
    frozen=load('source_scope_freeze.json')
    for path,expected in frozen['files'].items():
        check((HERE/path).is_file() and sha(HERE/path)==expected,'source freeze hash '+path)
    before={p:sha(HERE/p) for p in frozen['files'] if (HERE/p).is_file()}
    provenance=load('source_provenance_manifest.json')
    inherited_hashes=0
    for entry in provenance['sources']+provenance['transitive_public_runtime_modules']:
        check(sha(HERE/entry['file'])==entry['sha256'],'source provenance '+entry['file'])
        oldpath=entry['inherited_source_path']
        if oldpath.startswith('edbt_r20_followup/'):oldpath=oldpath.split('/',1)[1]
        check(sha(BASE/oldpath)==entry['sha256'],'inherited public source '+oldpath);inherited_hashes+=1
    check(sha(HERE/'common_scopes.json')==provenance['common_scope_sha256'],'aggregate common scope hash')
    check(sha(HERE/provenance['initial_state_schema_file'])==provenance['initial_state_schema_sha256'],'public initial schema hash')
    dependencies={name:importlib.metadata.version(name) for name in provenance['dependencies']}
    check(dependencies==provenance['dependencies'],'pinned public runtime dependencies')
    packets={p['task_key']:p['packet'] for p in load('source_snapshot/task_packets.json')}
    scopes={s['task_key']:s for s in load('common_scopes.json')['tasks']}
    check(len(scopes)==57 and sum(s['supported'] for s in scopes.values())==27,'57 tasks / 27 supported scopes')
    phase_counts=Counter(s['phase'] for s in scopes.values())
    check(phase_counts=={'development':30,'test':23,'composite':4},'retained phase inventory')
    obligations=[o for s in scopes.values() for o in s['obligations']]
    check(len(obligations)==43 and Counter(o['kind'] for o in obligations)=={'state':30,'query':13},'43 atomic obligations')
    check(len({o['obligation_id'] for o in obligations})==43,'unique obligation IDs')
    for key,scope in scopes.items():
        check(scope['source_packet_sha256']==canonical(packets[key]),'canonical packet binding '+key)
        check(scope['scope_sha256']==canonical({k:v for k,v in scope.items() if k!='scope_sha256'}),'canonical scope binding '+key)
        check(scope['required_obligation_ids']==[o['obligation_id'] for o in scope['obligations']],'exact atomic coverage '+key)
        check(scope['task_request']==packets[key]['task_request'],'immutable source request '+key)
        check(scope['full_task_utility_certified'] is False,'narrow scope designation '+key)
    from jsonschema import Draft202012Validator
    validator=Draft202012Validator(load('source_snapshot/output_schema_r21_1.json'))
    schemas=load('initial_state_schemas.json')['suites']
    contracts=rows('compiler_sanity/contracts.jsonl')
    check(len(contracts)==57,'compiler sanity 57 exact contracts')
    compiler_witnesses=0
    for row in contracts:
        key=row['task_key'];scope=scopes[key]
        check(not list(validator.iter_errors(row['contract'])),'typed compiler schema '+key)
        check(row['scope_sha256']==scope['scope_sha256'] and row['source_packet_sha256']==scope['source_packet_sha256'],'compiler authority '+key)
        check([c['obligation_id'] for c in row['contract']['clauses']]==scope['required_obligation_ids'],'compiler exact obligation IDs '+key)
        for clause in row['contract']['clauses']:
            support=clause['support']
            check(bool(support['request_quote']) and support['request_quote'] in scope['task_request'],'compiler literal quote '+clause['obligation_id'])
            try:
                for p in support['initial_state_paths']:pointer(packets[key]['initial_state'],p)
                for p in support['schema_paths']:pointer(schemas[key.split('/')[0]],p)
                check(True,'compiler witnesses')
            except (KeyError,TypeError,IndexError):check(False,'compiler native plain schema/initial pointer '+clause['obligation_id'])
            compiler_witnesses+=1
    from source_reference import evaluate
    from native_runtime import initialize,execute
    from grammar_assurance import probes
    cases=rows('development_cases_portable.jsonl')
    refs={r['case_id']:r for r in rows('private_reference/development_reference_v1.jsonl')}
    check(len(cases)==len(refs)==204,'204 inherited development cases')
    check(len({c['case_id'] for c in cases})==204,'unique development case IDs')
    replays=0
    for case in cases:
        cid,key=case['case_id'],case['task_key'];scope=scopes[key];ref=refs[cid]
        input_path=HERE/case['input_file'];observed=json.loads(input_path.read_text())
        check(sha(input_path)==case['input_sha256']==ref['input_sha256'],'development input binding '+cid)
        rawname=Path(observed['native_realization_receipt']['native_raw_file']).name
        rawpath=HERE/'native_raw'/rawname;raw=json.loads(rawpath.read_text())
        check(sha(rawpath)==observed['native_realization_receipt']['native_raw_sha256'],'development native hash '+cid)
        check(case['scope_sha256']==ref['scope_sha256']==scope['scope_sha256'] and case['source_packet_sha256']==ref['source_packet_sha256']==scope['source_packet_sha256'],'development source/scope authority '+cid)
        result=evaluate(key,observed)
        check(result['reference_status']==ref['reference_status'] and result['obligation_decisions']==ref['obligation_decisions'],'independent source decisions '+cid)
        check(raw['packet_initial_state']==packets[key]['initial_state'],'native immutable source packet '+cid)
        env,runtime=initialize(key.split('/')[0],copy.deepcopy(raw['packet_initial_state']))
        prep=[{'function':r['function'],'args':r['args']} for r in raw['preparation_receipts']]
        check(execute(env,runtime,prep)==raw['preparation_receipts'],'native preparation replay '+cid)
        check(env.model_dump(mode='json')==raw['observed_pre_state'],'native observed pre replay '+cid)
        acts=[{'function':r['function'],'args':r['args']} for r in raw['action_receipts']]
        check(execute(env,runtime,acts)==raw['action_receipts'],'native action replay '+cid)
        check(env.model_dump(mode='json')==raw['observed_post_state'],'native observed post replay '+cid);replays+=1
    computed_probes=probes();stored=load('grammar_probe_results.json')
    check(computed_probes==stored['probes'] and len(computed_probes)==17 and all(p['passed'] for p in computed_probes),'17 source grammar outcomes and explicit justifications')
    from confirmation_generator import plan
    planning=load('confirmation_plan.json')
    check(planning==plan(),'independent dormant confirmation plan unchanged')
    check(len(planning['rows'])==204 and Counter(r['phase'] for r in planning['rows'])=={'test':186,'composite':18},'confirmation plan retains 23+4 tasks / 186+18 realizations')
    check(len({r['task_key'] for r in planning['rows'] if r['phase']=='test'})==23 and len({r['task_key'] for r in planning['rows'] if r['phase']=='composite'})==4,'plan task coverage')
    check(not (HERE/'confirmation_v1').exists(),'no new confirmation materialized before root authorization')
    check({p:sha(HERE/p) for p in before}==before,'verification preserves frozen bytes')
    return {'passed':not failures,'designation':'read-only source/common-scope assurance, not semantic gold or competitive construction',
            'checks':checks['checks'],'source_freeze_files':len(frozen['files']),'inherited_source_hashes':inherited_hashes,
            'tasks':57,'supported_scopes':27,'atomic_obligations':43,'compiler_contracts':len(contracts),'compiler_obligation_witnesses':compiler_witnesses,
            'development_cases':len(cases),'development_native_replays':replays,'development_counts':dict(Counter(r['reference_status'] for r in refs.values())),
            'grammar_probes':17,'planned_primary_realizations':186,'planned_composite_realizations':18,'new_confirmation_materialized':0,
            'dependencies':dependencies,'python_version':sys.version,'source_freeze_sha256':sha(HERE/'source_scope_freeze.json'),
            'failures':failures}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path);args=parser.parse_args()
    if args.out:
        target=args.out.resolve()
        if target.exists() or target.is_relative_to(HERE):raise SystemExit('--out must be new and outside the frozen author folder.')
    result=verify();output=json.dumps(result,indent=2)+'\n'
    if args.out:args.out.write_text(output)
    print(output,end='')
    if not result['passed']:raise SystemExit(1)

if __name__=='__main__':main()
