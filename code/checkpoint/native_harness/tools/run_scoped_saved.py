#!/usr/bin/env python3
"""Source-literal necessary-field audit of existing saved states, not native replay."""
from pathlib import Path
import argparse,collections
from guards_followup import check_followup
from common import ROOT,load,write,new_out,check_freeze,sha,utc
from run_native import field_spec,actual_field,satisfies
TARGETS={('banking','user_task_6'),('travel','user_task_3'),('travel','user_task_4')}
def run(out):
 check_freeze();check_followup();out=new_out(out);rows=[]
 for c in load(ROOT/'inputs/r11/cases.json'):
  if (c['suite'],c['task_id']) not in TARGETS:continue
  taskfile=ROOT/f"inputs/r11/tasks/{c['suite']}_{c['task_id']}.json";pkt=load(taskfile);spec=field_spec(c['suite'],c['task_id'],pkt['task_request']);d=ROOT/c['input_dir']
  pre=load(d/'pre_state.json');post=load(d/'post_state.json');w=actual_field(spec,pre,post);sat=satisfies(spec,w)
  rows.append({'suite':c['suite'],'task_id':c['task_id'],'case_id':c['case_id'],'group':c['group'],'spec':spec,'witness':w,'scope_satisfied':sat,'native_recorded':c['native_accepted'],'native_and_necessary_condition':c['native_accepted'] and sat,'full_semantic_reference':'unknown','native_tools_reexecuted':False,'input_pre_sha256':sha(d/'pre_state.json'),'input_post_sha256':sha(d/'post_state.json'),'source_prompt_file_sha256':sha(taskfile)})
 groups={}
 for s,t in sorted(TARGETS):
  sub=[r for r in rows if (r['suite'],r['task_id'])==(s,t)];groups[s+'/'+t]={'cases':len(sub),'required_field_violations':sum(not r['scope_satisfied'] for r in sub),'recorded_native_accepting_violations':sum(r['native_recorded'] and not r['scope_satisfied'] for r in sub),'scoped_overlay_accepting_violations':sum(r['native_and_necessary_condition'] and not r['scope_satisfied'] for r in sub),'recorded_native_scope_satisfied_positives':sum(r['native_recorded'] and r['scope_satisfied'] for r in sub)}
 write(out/'rows.json',rows);write(out/'SUMMARY.json',{'status':'EXECUTED_NECESSARY_FIELD_AUDIT_ON_RECORDED_STATES','by_task':groups,'inputs':len(rows),'human_annotations':0,'api_calls':0,'new_native_executions':0,'selection':'All cases from previously exposed banking6/travel3/travel4 in original 98-case bank. Retrospective source-grounded reanalysis, not fresh independent error prevalence.','authority':'Explicit recipient/date literal from public task request, mapped to native entity field; code-authored interpretation. Violating a necessary field refutes that scoped claim; satisfying it is not full correctness.'})
 print(groups)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',required=True,type=Path);a=p.parse_args();run(a.out)
