#!/usr/bin/env python3
"""Verify package bytes and (optionally) rerun executed CPU-only components."""
from pathlib import Path
import argparse,json,subprocess,sys,tempfile
from common import ROOT,load,sha,write,check_freeze
from guards_followup import check_followup

def verify(replay=False):
 manifest=load(ROOT/'FILE_MANIFEST.json')
 for name,h in manifest['files'].items():
  if sha(ROOT/name)!=h:raise AssertionError('Package file mismatch: '+name)
 check_freeze();check_followup();source=load(ROOT/'INPUT_PROVENANCE.json')
 for c in source['copies']:
  if sha(ROOT/c['path'])!=c['sha256']:raise AssertionError('Source-copy mismatch: '+c['path'])
 pairs=load(ROOT/'inputs/r11/contracts.json');rawmap=load(ROOT/'inputs/r11/primary_contract_map.json');m={r['packet_id']:r for r in rawmap}
 for r in pairs:
  if r['a']!=m[r['packet_id']]['primary'] or r['b']!=load(ROOT/f"inputs/r11/builder_b/{r['packet_id']}.json"):raise AssertionError('Derived candidate mismatch')
  if r['initial_state']!=load(ROOT/f"inputs/r11/tasks/{r['suite']}_{r['task_id']}.json")['initial_state']:raise AssertionError('Derived pre-state mismatch')
 result={'payload_files':len(manifest['files']),'byte_copies':len(source['copies']),'derived_candidate_pairs':len(pairs),'local_frozen_source':'PASS','native_followup_frozen_source':'PASS','human_annotations':0,'new_api_calls':0,'full_native_runtime_this_validation':False}
 if replay:
  with tempfile.TemporaryDirectory(prefix='r18_verify_') as temp:
   root=Path(temp)
   subprocess.run([sys.executable,str(ROOT/'tools/run_offline.py'),'--out',str(root/'offline')],check=True,stdout=subprocess.DEVNULL)
   same=['interpreter_replay.json','interpreter_rows.json','query_rows.json','query_summary.json','workspace20_inventory.json']
   for fn in same:
    if (root/'offline'/fn).read_bytes()!=(ROOT/'results/local_v1'/fn).read_bytes():raise AssertionError('Recomputed output differs: '+fn)
   subprocess.run([sys.executable,str(ROOT/'tools/run_scoped_saved.py'),'--out',str(root/'scope')],check=True,stdout=subprocess.DEVNULL)
   for fn in ['rows.json','SUMMARY.json']:
    if (root/'scope'/fn).read_bytes()!=(ROOT/'results/scoped_saved_v1'/fn).read_bytes():raise AssertionError('Scoped replay mismatch')
   result['deterministic_recomputed_outputs']=7
 result['status']='PASS';print(json.dumps(result,indent=2));return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--replay',action='store_true');a=p.parse_args();verify(a.replay)
