#!/usr/bin/env python3
"""Post-execution evidence audit; does not rewrite frozen native study results."""
from pathlib import Path
import collections,csv,json,sys
R=Path(__file__).resolve().parent;KIT=R/'EDBT_R18_NO_HUMAN_KIT';sys.path.insert(0,str(KIT/'tools'))
from common import load,write,sha,digest,encode
N=KIT/'runs/r18_cpu_01/native';D=R/'analysis'
def diff(a,b,path=()):
 if type(a)!=type(b):return [path]
 if isinstance(a,dict):
  out=[]
  for k in sorted(a.keys()|b.keys()):out+=diff(a[k],b[k],path+(k,)) if k in a and k in b else [path+(k,)]
  return out
 if isinstance(a,list):
  if len(a)!=len(b):return [path+('LENGTH',)]
  return [p for i,(x,y) in enumerate(zip(a,b)) for p in diff(x,y,path+(str(i),))]
 return [] if a==b else [path]
def pointer(p):return '/'+('/'.join(x.replace('~','~0').replace('/','~1') for x in p))
def main():
 D.mkdir(exist_ok=True);rows=load(N/'state-repair/rows.json');plans=load(N/'state-repair/challenge_before_execution.json')['targets'];isolation=[]
 for plan in plans:
  name,tid=plan['suite'],plan['task_id'];spec=plan['spec'];base=N/'state-repair/cases'/name/tid/'positive_0';base_post=load(base/'post_state.json');base_input=load(base/'evaluator_input.json');base_pre=load(base/'pre_state.json')
  sub=[r for r in rows if r['suite']==name and r['task_id']==tid];assert len(sub)==16
  for r in sub:
   folder=base.parent/r['variant'];post=load(folder/'post_state.json');pre=load(folder/'pre_state.json');inp=load(folder/'evaluator_input.json');trace=load(folder/'trace.json');assert pre==base_pre and trace[-1]['state']==post
   assert all(t['error'] is None for t in trace);assert [t['call'] for t in trace]==inp['actions']
   # Derive required actual field from the realized native state independently.
   if name=='banking':
    new=post['bank_account']['scheduled_transactions'][len(pre['bank_account']['scheduled_transactions']):];assert len(new)==1;actual=new[0]['recipient'];satisfied=actual==spec['required']
   elif tid=='user_task_3':
    old=pre['inbox']['emails'];new=[e for k,e in post['inbox']['emails'].items() if k not in old];assert len(new)==1;actual=new[0]['recipients'];satisfied=spec['required'] in actual
   else:
    old=pre['calendar']['events'];new=[e for k,e in post['calendar']['events'].items() if k not in old];assert len(new)==1;actual=new[0]['start_time'][:10];satisfied=actual==spec['required']
   assert satisfied==r['scope_satisfied']==r['expected_scope_satisfied']
   assert r['scoped_supplemented']==(r['native'] and satisfied)
   paths=diff(base_post,post);action_paths=diff(base_input['actions'],inp['actions'])
   if not satisfied:
    if name=='banking':allowed=lambda p:p[:2]==('bank_account','scheduled_transactions') and p[-1]=='recipient';allowed_action=lambda p:p[-1]=='recipient'
    elif tid=='user_task_3':allowed=lambda p:p[:2] in [('inbox','emails'),('inbox','sent')] and p[-2:]==('recipients','0');allowed_action=lambda p:p[-2:]==('recipients','0')
    else:
     event=new[0]
     # Native calendar creation embeds that same event in the invitation email;
     # require full equality before recognizing these as linked date views.
     email_new=[e for k,e in post['inbox']['emails'].items() if k not in pre['inbox']['emails']]
     assert len(email_new)==1 and email_new[0]['attachments']==[event]
     assert post['inbox']['sent'][-1]['attachments']==[event]
     allowed=lambda p:(p[:2]==('calendar','events') or (p[:2] in [('inbox','emails'),('inbox','sent')] and p[-3:-1]==('attachments','0'))) and p[-1] in ['start_time','end_time']
     allowed_action=lambda p:p[-1] in ['start_time','end_time']
    assert paths and all(allowed(p) for p in paths),(name,tid,paths)
    assert action_paths and all(allowed_action(p) for p in action_paths)
    assert inp['output']==base_input['output']
   isolation.append({'suite':name,'task_id':tid,'variant':r['variant'],'satisfied':satisfied,'actual':actual,'native':r['native'],'supplemented':r['scoped_supplemented'],'post_diff_paths_vs_positive_0':[pointer(p) for p in paths],'action_diff_paths_vs_positive_0':[pointer(p) for p in action_paths],'negative_only_expected_fields_changed':True if not satisfied else None,'post_sha256':sha(folder/'post_state.json'),'trace_sha256':sha(folder/'trace.json')})
 write(D/'state_intervention_isolation.json',isolation)
 sweep=load(N/'sweep/rows.json');manifest=load(N/'sweep/selection_before_execution.json')['cases'];assert len(sweep)==len(manifest)==291
 assert [(r['version'],r['suite'],r['task_id']) for r in sweep]==[(r['version'],r['suite'],r['task_id']) for r in manifest]
 hydration=[];table=[]
 for r in sweep:
  assert 'error' not in r and 'roundtrip_error' not in r
  folder=N/'sweep/cases'/r['version']/r['suite']/r['task_id'];post=load(folder/'post_state.json');h=load(folder/'roundtrip_post_state.json');paths=diff(post,h)
  assert bool(paths)==r['roundtrip_state_changed'];assert r['roundtrip_label_changed']==(r['roundtrip_label']!=r['native_official_control_accepted'])
  if paths:hydration.append({'version':r['version'],'suite':r['suite'],'task_id':r['task_id'],'native':r['native_official_control_accepted'],'after_hydration':r['roundtrip_label'],'changed_paths':[pointer(p) for p in paths]})
 for v in ['v1','v1.1.1','v1.2.2']:
  for name in ['workspace','banking','slack','travel']:
   s=[r for r in sweep if r['version']==v and r['suite']==name];table.append({'version':v,'suite':name,'tasks':len(s),'official_accept':sum(r['native_official_control_accepted'] for r in s),'official_reject':sum(not r['native_official_control_accepted'] for r in s),'post_changed':sum(r['roundtrip_state_changed'] for r in s),'pre_changed':sum(r['roundtrip_pre_changed'] for r in s),'label_changed':sum(r['roundtrip_label_changed'] for r in s)})
 write(D/'hydration_changed_paths.json',hydration);write(D/'sweep_by_suite.json',table)
 with (D/'SWEEP_BY_SUITE.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(table[0]));w.writeheader();w.writerows(table)
 with (D/'STATE_REPAIR_CASES.csv').open('w',newline='') as f:
  keys=['suite','task_id','variant','satisfied','native','supplemented'];w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows({k:r[k] for k in keys} for r in isolation)
 replay=load(R/'studies/replay20_v2/results_v1/summary.json');query=load(N/'query-crosscheck/summary.json')
 summary={'status':'ALL_FOUR_NATIVE_COMPONENTS_COMPLETED_WITH_VERSIONED_REPLAY20_CORRECTION','query_crosscheck':query,'replay20_corrected':replay,'sweep_by_suite':table,'sweep_aggregate':{'task_version_pairs':len(sweep),'unique_suite_task_pairs':len({(r['suite'],r['task_id']) for r in sweep}),'official_control_rejections':sum(not r['native_official_control_accepted'] for r in sweep),'changed_post_states':len(hydration),'changed_pre_states':sum(r['roundtrip_pre_changed'] for r in sweep),'changed_labels':sum(r['roundtrip_label_changed'] for r in sweep),'tool_or_evaluator_errors':0},'state_repair':{'cases':len(rows),'targets':3,'scope_satisfied_controls':sum(r['scope_satisfied'] for r in rows),'required_field_violations':sum(not r['scope_satisfied'] for r in rows),'native_accepting_violations':sum(r['native'] and not r['scope_satisfied'] for r in rows),'supplement_accepting_violations':sum(r['scoped_supplemented'] and not r['scope_satisfied'] for r in rows),'native_positive_controls_retained':sum(r['native'] and r['scope_satisfied'] and r['scoped_supplemented'] for r in rows),'negative_isolation_checks':sum(not r['satisfied'] and r['negative_only_expected_fields_changed'] for r in isolation),'unique_control_post_states':len({r['post_sha256'] for r in isolation if r['satisfied']}),'unique_all_post_states':len({r['post_sha256'] for r in isolation}),'whole_task_semantic_truth':'unknown'},'human_annotations':0,'new_api_calls':0,'inference_cost_usd':0,'api_baseline':'NOT_EXECUTED; optional and unnecessary for requested CPU experiment','scope':'Finite canonical query language, all-registered official self-consistency at pinned source, and outcome-informed manual source-field supplement; not natural failure prevalence, full semantic accuracy, automated repair, or independent version replicas.'}
 write(R/'R18_EXECUTION_RESULTS.json',summary)
 write(R/'RUN_AUTHORITY.json',{'original_kit_payload':'EDBT_R18_NO_HUMAN_KIT/FILE_MANIFEST.json','native_primary_run':'EDBT_R18_NO_HUMAN_KIT/runs/r18_cpu_01/native','query_crosscheck':'native_primary_run/query-crosscheck','sweep':'native_primary_run/sweep','state_repair':'native_primary_run/state-repair','replay20_authority':'studies/replay20_v2/results_v1','replay20_parent_partial_preserved':'native_primary_run/replay20','note':'Original kit source and original run status remain unchanged. The parent run reports replay20 ERROR; the separate corrected study is the completed replay authority. Summaries do not pool the two replay versions.'})
 print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
