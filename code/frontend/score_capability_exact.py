"""Scoring reads the reference only AFTER frozen capability predictions exist."""
from common import *
from collections import Counter

def main():
 path=STUDY/'results/capability_exact';pred=rows(path/'predictions.jsonl');refs={}
 for ds in ['development_v3','confirmation_all']:
  refs.update({r['case_id']:r for r in rows(UPSTREAM/f'source_study/views/{ds}/private_reference.jsonl')})
 bad=[];per={}
 for task in sorted({r['task_key'] for r in pred}):
  rs=[r for r in pred if r['task_key']==task];pos=[r for r in rs if refs[r['case_id']]['reference_status']=='pass'];neg=[r for r in rs if refs[r['case_id']]['reference_status']=='fail'];unk=[r for r in rs if refs[r['case_id']]['reference_status']=='unknown']
  per[task]={'cases':len(rs),'agreement':sum(r['status']==refs[r['case_id']]['reference_status'] for r in rs),
   'valid_retention':sum(r['status']=='pass' for r in pos)/len(pos),'false_pass':sum(r['status']=='pass' for r in neg)/len(neg),
   'unknown_promotions':sum(r['status']!='unknown' for r in unk)}
 for r in pred:
  if r['status']!=refs[r['case_id']]['reference_status']:bad.append(r|{'reference':refs[r['case_id']]['reference_status']})
 report={'utc':now(),'prediction_sha256':sha(path/'predictions.jsonl'),'designation':'expert-authored capability not model performance',
         'cases':len(pred),'agreement':len(pred)-len(bad),'per_task':per,'mismatches':bad}
 write(path/'SCORED_SUMMARY.json',report);print(json.dumps(report,indent=2))
if __name__=='__main__':main()
