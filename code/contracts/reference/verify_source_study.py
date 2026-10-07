#!/usr/bin/env python3
"""Read-only independent source/data checks; optional pinned native replay.
No model/API calls or competitive executor/derivation imports.
"""
from __future__ import annotations
import argparse,copy,hashlib,json,sys
from collections import Counter
from pathlib import Path
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
from source_worlds import BASE,TASKS,canonical_sha,load_sources
from source_reference_dynamic import derive,evaluate

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rows(p):return [json.loads(s) for s in Path(p).read_text().splitlines() if s.strip()]
def main():
 p=argparse.ArgumentParser();p.add_argument('--development',type=Path,default=HERE/'development_v3');p.add_argument('--confirmation',type=Path);p.add_argument('--native-replay',action='store_true');p.add_argument('--out',type=Path);a=p.parse_args()
 freeze=json.loads((HERE/'SOURCE_IMPLEMENTATION_FREEZE.json').read_text())
 for name,h in freeze['source_files'].items():assert sha(HERE/name)==h,('source freeze drift',name)
 for name,h in freeze['immutable_upstream_files'].items():assert sha(BASE/name)==h,('immutable reference/native drift',name)
 source=json.loads((HERE/'public_packets.json').read_text());assert len(source)==48
 original_packets,original_scopes=load_sources();public={}
 for item in source:
  key,w=item['task_key'],item['world_id'];packet,scope=item['packet'],item['scope'];public[key,w]=item
  assert key in TASKS and w in range(6)
  assert packet['task_request']==original_packets[key]['task_request']
  assert scope['obligations']==original_scopes[key]['obligations']
  assert canonical_sha(packet)==scope['source_packet_sha256']
  assert canonical_sha({k:v for k,v in scope.items() if k!='scope_sha256'})==scope['scope_sha256']
  assert scope['source_packet_id']==packet['packet_id']
  if w==0:assert packet==original_packets[key]
  derive(packet,scope)
 if a.native_replay:
  from realize_cases import native,verify_environment
  verify_environment()
 checked=0;replayed=0;summaries=[]
 paths=[a.development]+([a.confirmation] if a.confirmation else [])
 for data in paths:
  report=json.loads((data/'REPORT.json').read_text());assert report['status']=='PASS'
  cases=rows(data/'cases.jsonl');refs={r['case_id']:r for r in rows(data/'private_reference.jsonl')}
  expected_worlds=report['worlds'];assert len(cases)==len(expected_worlds)*len(TASKS)*8
  assert len({(c['task_key'],c['world_id'],c['mechanism']) for c in cases})==len(cases)
  statuses=Counter()
  for case in cases:
   item=public[case['task_key'],case['world_id']];packet,scope=item['packet'],item['scope']
   receipt=json.loads((data/case['native_trace_path']).read_text());assert receipt['observed']==case['observed']
   assert receipt['planned_status_match'] and receipt['preparation_goal_preserved'] and receipt['native_errors']==0
   assert receipt['source_packet_sha256']==scope['source_packet_sha256'] and receipt['source_scope_sha256']==scope['scope_sha256']
   derived,proof=derive(packet,scope);prepared=copy.deepcopy(packet);prepared['initial_state']=receipt['full_observed']['pre_state']
   prepared_goal,prepared_proof=derive(prepared,scope);assert prepared_goal==derived and prepared_proof==receipt['prepared_source_derivation']
   result=evaluate(packet,scope,case['observed']);assert result==receipt['reference']
   expected={k:v for k,v in refs[case['case_id']].items() if k not in ['case_id','planned_status_match']};assert result==expected
   assert result['reference_status']==case['design_status'];statuses[result['reference_status']]+=1
   if a.native_replay:
    env,rt=native.initialize(case['task_key'].split('/')[0],copy.deepcopy(packet['initial_state']))
    prep=native.execute(env,rt,receipt['preparation_actions']);assert prep==receipt['preparation_receipts']
    assert native.plain(env)==receipt['full_observed']['pre_state']
    actions=native.execute(env,rt,receipt['case_actions']);assert actions==receipt['action_receipts']
    assert native.plain(env)==receipt['full_observed']['post_state'];replayed+=1
   checked+=1
  assert statuses==Counter({'pass':16*len(expected_worlds),'fail':24*len(expected_worlds),'unknown':24*len(expected_worlds)})
  summaries.append({'path':str(data),'worlds':expected_worlds,'cases':len(cases),'statuses':dict(statuses)})
 result={'status':'PASS','public_packets':48,'case_reference_checks':checked,'native_replays':replayed,'datasets':summaries,'API_calls':0,'model_outputs_read':0,'scope':'Source perturbations and narrow independently derived necessary conditions; original R21 labels remain unchanged.'}
 if a.out:a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result,indent=2))
if __name__=='__main__':main()
