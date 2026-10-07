"""Exposed repair validation against unchanged source references, never new confirmation."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
import copy,hashlib,json,collections
import contract_executor as ex
R=Path(__file__).resolve().parent;ROOT=R.parents[1];A=ROOT/'e2/reference_author';BASE=ROOT/'baseline_r20'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text())
def rows(p):return [json.loads(s) for s in p.read_text().splitlines() if s.strip()]
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
def main():
 plan=load(R/'REPAIR_DIAGNOSTIC_PLAN.json')
 for name,h in plan['files'].items():assert sha(ROOT/name)==h,name
 assert sha(Path(__file__))==plan['runner_sha256']
 scopes={t['task_key']:t for t in load(A/'common_scopes.json')['tasks']};packets={t['task_key']:t['packet'] for t in load(A/'source_snapshot/task_packets.json')}
 contracts={t['task_key']:copy.deepcopy(t['contract']) for t in rows(A/'compiler_sanity/contracts.jsonl')}
 for c in contracts.values():c['ir_version']=ex.VERSION
 schemas={suite:load(BASE/f'work/native/EDBT_R18_CPU_RESULTS/EDBT_R18_NO_HUMAN_KIT/inputs/r11/schemas/{suite}.json') for suite in ['banking','slack','travel']}
 out=R/'repair_diagnostic_v1';assert not out.exists();out.mkdir();allrows=[];summaries={}
 for phase,casefile,reffile in [('old_development','development_cases_portable.jsonl','private_reference/development_reference_v1.jsonl'),('exposed_R21A','confirmation_cases_portable.jsonl','confirmation_v1/private_reference.jsonl')]:
  cases=rows(A/casefile);refs={x['case_id']:x for x in rows(A/reffile)}
  assert len(cases)==len(refs)==204
  for case in cases:
   p=(A/case['input_file']).resolve();assert p.is_relative_to(A) and sha(p)==case['input_sha256'];d=load(p)
   task=scopes[case['task_key']];ref=refs[case['case_id']];c=contracts[case['task_key']];packet=dict(packets[case['task_key']]);packet['state_schema']=schemas[case['task_key'].split('/')[0]]
   assert case['source_packet_sha256']==digest(packets[case['task_key']])
   for policy in ['scope','scope_source']:
    result=ex.evaluate(c,d.get('pre_state'),d.get('post_state'),d.get('output'),public_task=task,packet=packet,policy=policy)
    allrows.append({'phase':phase,'case_id':case['case_id'],'policy':policy,'reference_status':ref['reference_status'],'prediction':result['verdict'],'matched':result['verdict']==ref['reference_status'],'input_sha256':case['input_sha256'],'contract_sha256_ir_version_only':digest(c),'result':result})
  summaries[phase]={}
  for policy in ['scope','scope_source']:
   rs=[x for x in allrows if x['phase']==phase and x['policy']==policy]
   summaries[phase][policy]={'cases':len(rs),'matched':sum(x['matched'] for x in rs),'unsafe_fail_to_pass':sum(x['reference_status']=='fail' and x['prediction']=='pass' for x in rs),'unknown_promoted_to_pass':sum(x['reference_status']=='unknown' and x['prediction']=='pass' for x in rs),'errors':sum(x['prediction']=='error' for x in rs),'statuses':dict(collections.Counter(x['prediction'] for x in rs))}
 (out/'rows.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in allrows))
 receipt={'status':'PASS' if all(x['matched'] for x in allrows) else 'FAIL','designation':'EXPOSED_MEASUREMENT_REPAIR_DIAGNOSTIC_NOT_NEW_CONSTRUCTION_CONFIRMATION','ir_version':ex.VERSION,'source_operands_or_reference_labels_changed':False,'only_contract_ir_version_adapted':True,'models_or_provider_responses_read':False,'API_calls':0,'by_dataset_and_policy':summaries,'mismatches':[x for x in allrows if not x['matched']],'plan_sha256':sha(R/'REPAIR_DIAGNOSTIC_PLAN.json'),'rows_sha256':sha(out/'rows.jsonl')}
 (out/'REPORT.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({k:v for k,v in receipt.items() if k!='mismatches'},indent=2))
 assert receipt['status']=='PASS'
if __name__=='__main__':main()
