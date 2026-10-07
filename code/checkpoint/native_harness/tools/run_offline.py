#!/usr/bin/env python3
"""CPU-only real execution of frozen interpreter/schema code and narrow kernels."""
from __future__ import annotations
import argparse,collections,csv,json,sys,time,statistics
from pathlib import Path
from common import ROOT,load,write,sha,utc,new_out,check_freeze,environment,text_output
from query_kernel import ALLOWED_IDS,build_kernel,context,reference_spec,patched,cases
sys.path.insert(0,str(ROOT/'vendor/r11'))
from contract_engine import evaluate,preflight
from schema_gate import schema_admission,hybrid_admission

def tally(rows,key):return dict(collections.Counter(r[key] for r in rows))
def main(out):
 freeze=check_freeze();out=new_out(out);start=utc()
 original=load(ROOT/'inputs/r11/cases.json');annotations={(r['suite'],r['task_id']):r for r in load(ROOT/'inputs/r11/contracts.json')}
 schemas={s:load(ROOT/f'inputs/r11/schemas/{s}.json') for s in ('banking','slack','travel')}
 loaded=[];results=[];disagreements=[]
 for r in original:
  d=ROOT/r['input_dir'];pre=load(d/'pre_state.json');post=load(d/'post_state.json')
  if sha(d/'pre_state.json')!=r['pre_sha256'] or sha(d/'post_state.json')!=r['post_sha256']:raise ValueError('Source state integrity failure')
  ann=annotations[(r['suite'],r['task_id'])];loaded.append((r,ann,pre,post))
 def compute(item):
  r,ann,pre,post=item;row={k:r[k] for k in ['group','suite','task_id','case_id','a_class','b_class']};row['arms']={}
  for arm in ['initial','schema','hybrid']:
   row['arms'][arm]={}
   for b in ['a','b']:
    a=ann[b];gate=preflight(a,pre) if arm=='initial' else schema_admission(a,schemas[r['suite']]) if arm=='schema' else hybrid_admission(a,pre,schemas[r['suite']])
    v=evaluate(a,pre,post)['verdict'] if gate['admitted'] else 'unknown';row['arms'][arm][b]=v
   a,b=row['arms'][arm]['a'],row['arms'][arm]['b'];row['arms'][arm]['route']='partial_checks_pass' if a==b=='pass' else 'shared_partial_violation' if a==b=='fail' else 'review_contract_or_execution'
  return row
 for item in loaded:
  row=compute(item);results.append(row)
  if row['arms']!=item[0]['arms']:disagreements.append({'case':row,'expected':item[0]['arms']})
 if disagreements:raise AssertionError('Replay differs from R11: '+str(disagreements[:1]))
 # Microbenchmark: loaded JSON only, no native engine or model time.
 for _ in range(2):
  for item in loaded:compute(item)
 timing=[]
 for rep in range(7):
  st=time.perf_counter_ns()
  for item in loaded:compute(item)
  timing.append((time.perf_counter_ns()-st)/1e6)
 primary=[r for r in results if r['group']=='primary'];common=[r for r in primary if r['a_class']==r['b_class']=='state']
 replay_summary={'status':'EXECUTED_FROZEN_INTERPRETER_AND_GATES_ON_RECORDED_JSON','cases':len(results),'arms':3,'builder_checks':len(results)*3*2,'exact_original_arm_matches':len(results),'native_tools_reexecuted':False,'human_annotations':0,'api_calls':0,'common_state_n':len(common),'common_state_joint_decisive':{arm:sum(r['arms'][arm]['a']==r['arms'][arm]['b'] and r['arms'][arm]['a']!='unknown' for r in common) for arm in ['initial','schema','hybrid']}}
 write(out/'interpreter_replay.json',replay_summary);write(out/'interpreter_rows.json',results)
 write(out/'timing.json',{'scope':'already-loaded JSON; both contracts and all 3 gates; 98 cases per repetition; excludes I/O, native tools, provider calls','warmups':2,'repetitions':7,'batch_ms':timing,'median_batch_ms':statistics.median(timing),'max_batch_ms':max(timing),'median_per_case_ms':statistics.median(timing)/len(loaded),'environment':environment()})
 specs={t:reference_spec(t) for t in ALLOWED_IDS};kernels={t:build_kernel(t) for t in ALLOWED_IDS};qrows=[]
 for c in cases():
  t=c['task_id'];_,pre=context(t);utility=kernels[t][0];native=bool(utility.utility(c['output'],pre,pre,True));after=patched(specs[t],c['output'])
  qrows.append(dict(c,native_kernel='pass' if native else 'fail',patched_scoped=after))
 summary={}
 for t in ALLOWED_IDS:
  rows=[r for r in qrows if r['task_id']==t];rr={}
  for group in ['finite_canonical_domain','strict_whole_output_profile']:
   sub=[r for r in rows if r['group']==group]
   if not sub:continue
   npos=sum(r['reference']=='pass' for r in sub);nneg=sum(r['reference']=='fail' for r in sub)
   rr[group]={'n':len(sub),'reference_positive':npos,'reference_negative':nneg}
   for arm in ['native_kernel','patched_scoped']:
    rr[group][arm]={'false_accept':sum(r['reference']=='fail' and r[arm]=='pass' for r in sub),'false_reject':sum(r['reference']=='pass' and r[arm]=='fail' for r in sub),'unknown':sum(r[arm]=='unknown' for r in sub),'true_positive_retained':sum(r['reference']=='pass' and r[arm]=='pass' for r in sub)}
  summary[str(t)]=rr
 write(out/'query_rows.json',qrows);write(out/'query_summary.json',{'status':'EXECUTED_EXTRACTED_OFFICIAL_UTILITY_BODIES_NOT_FULL_NATIVE_RUNTIME','task_count':len(ALLOWED_IDS),'generated_cases':len(qrows),'selection':'Known exposed fixed tasks; finite parameter enumeration and strict-format profile, not held-out discovery','specs':specs,'kernel_provenance':{t:k[1] for t,k in kernels.items()},'by_task':summary,'claim_limit':'Restricted answer-language repair, not unrestricted natural-language semantic judging; task5 uses explicitly documented calendar-gap interpretation.'})
 # All-20 inventory; do not silently impose whole-output profile on location+time task17.
 inventory=[]
 for t in range(20):
  d=ROOT/f'inputs/workspace/user_task_{t}';prompt=load(d/'task.json')['prompt'];text=text_output(load(d/'evaluator_input.json'));native=load(d/'result.json')['utility']
  row={'task_id':t,'prompt':prompt,'native_endpoint_recorded':native,'original_output':text,'full_semantic_status':'unknown'}
  if t in [2,5,11,14]:
   import re
   pattern=r'[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}' if t in [2,14] else r'[0-9]{2}:[0-9]{2}'
   row.update(format_scope='strict_whole_answer_profile',profile_matches=bool(re.fullmatch(pattern,text)),contains_formatted_value=bool(re.search(pattern,text)))
  elif t==17:row.update(format_scope='component_time_not_whole_answer',profile_matches=None)
  else:row.update(format_scope='not_screened',profile_matches=None)
  if t in ALLOWED_IDS:
   pre=load(d/'pre_state.json');post=load(d/'post_state.json');actual=bool(kernels[t][0].utility(text,pre,post,True));row['extracted_native_kernel_matches_recorded']=actual==native
   if actual!=native:raise AssertionError('Kernel and recorded original differ')
   row['scoped_patch_on_realized_output']=patched(specs[t],text)
  inventory.append(row)
 write(out/'workspace20_inventory.json',inventory)
 write(out/'SUMMARY.json',{'study_id':'R18_NO_HUMAN_LOCAL_V1','started_utc':start,'finished_utc':utc(),'freeze_sha256':sha(ROOT/'STUDY_FREEZE.json'),'api_calls':0,'human_annotations':0,'new_agent_runs':0,'native_engine_replay':False,'interpreter_replay':replay_summary,'query_cases':len(qrows),'query_tasks':list(ALLOWED_IDS),'kernel_realized_output_checks':3,'outputs':['interpreter_replay.json','interpreter_rows.json','query_summary.json','query_rows.json','workspace20_inventory.json','timing.json'],'not_completed':['full native dependency-complete cross-check','all-suite official consistency sweep','reachable state-repair experiment','optional model comparison']})
 print(json.dumps({'interpreter':replay_summary,'query':summary},indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();main(a.out)
