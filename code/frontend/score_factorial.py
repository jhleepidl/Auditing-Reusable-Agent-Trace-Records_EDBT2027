"""Reference-separated statistics for retained predictions, all factorial arms."""
from common import *
from collections import Counter
import sys,statistics
sys.path.insert(0,str(UPSTREAM))
import score22
from run_factorial import STAGES,POLICIES


def main():
 full={};contrasts=[];summary=[]
 for stage,run,ds,mode in STAGES:
  reference=rows(UPSTREAM/f'source_study/views/{ds}/private_reference.jsonl');gold={r['case_id']:r for r in reference};base={}
  for policy in POLICIES:
   folder=STUDY/f'results/factorial/{stage}/{policy}';preds=rows(folder/'predictions.jsonl');receipt=load(folder/'RECEIPT.json')
   metrics=score22.score(reference,preds,receipt);metrics.update(reference_sha256=sha(UPSTREAM/f'source_study/views/{ds}/private_reference.jsonl'),predictions_sha256=sha(folder/'predictions.jsonl'),frontend_policy=policy,designation='retrospective CPU-only frontend intervention; not new model confirmation')
   write(folder/'METRICS.json',metrics);base[policy]=metrics
   for row in metrics['task_macro_summary']:
    summary.append({'stage':stage,'policy':policy,**row})
  for policy in ['topology','addressing','combined']:
   old=base['old']['per_task_metrics'];new=base[policy]['per_task_metrics']
   for model,method in sorted({(r['model'],r['method']) for r in new}):
    a={r['task_key']:r for r in old if(r['model'],r['method'])==(model,method)};b={r['task_key']:r for r in new if(r['model'],r['method'])==(model,method)}
    con={'stage':stage,'policy':policy,'model':model,'method':method,'unit':'paired task template; exposed and post-selection','contrast':policy+' - old'}
    for metric in ['valid_retention','false_pass_rate','decisive_coverage']:con[metric]=score22.ci([b[t][metric]-a[t][metric] for t in sorted(a)])
    contrasts.append(con)
  const={}
  for policy in POLICIES:
   cs=rows(STUDY/f'results/factorial/{stage}/{policy}/construction.jsonl')
   oldcs=rows(STUDY/f'results/factorial/{stage}/old/construction.jsonl');oi={(r['request_id'],r['world_id'],r['method']):r for r in oldcs}
   for model in sorted({r['model'] for r in cs}):
    rs=[r for r in cs if r['method']=='derived' and r['model']==model]
    reasons=Counter();trans=Counter();contractdiff=0
    for r in rs:
     oldr=oi[r['request_id'],r['world_id'],r['method']];trans[oldr['compile_status']+' -> '+r['compile_status']]+=1
     if r['compile_status']!='ok':
      ds2=r['compilation'].get('diagnostics') or [{'reason':'unspecified'}];reasons[ds2[0].get('reason','unspecified')]+=1
     if oldr['compile_status']=='ok' and r['compile_status']=='ok' and oldr['compilation']['contract']!=r['compilation']['contract']:contractdiff+=1
    const[policy+'|'+model]={'compilations':len(rs),'statuses':dict(Counter(r['compile_status'] for r in rs)),
       'transitions':dict(trans),'first_reasons':dict(reasons),'previously_ok_contract_changes':contractdiff}
  full[stage]={'construction':const}
 result={'utc':now(),'designation':'all exposed retained candidates; descriptive post-development deltas, no new confirmation',
  'summaries':summary,'paired_contrasts':contrasts,'construction':full,'source_scoring_code_sha256':sha(UPSTREAM/'score22.py')}
 write(STUDY/'results/FACTORIAL_SUMMARY.json',result)
 for stage in ['confirmation_fresh','feedback_round1','review_only_control','feedback_round2','transfer_v2']:
  print('\n'+stage)
  for r in summary:
   if r['stage']==stage and r['method']=='derived':print(r['policy'],r['model'],'VR',round(r['task_macro_valid_retention']*100,4),'FPR',round(r['task_macro_false_pass_rate']*100,4),'errors',r['errors_all_cells'])
 print('completed',len(summary),'summary cells')
if __name__=='__main__':main()
