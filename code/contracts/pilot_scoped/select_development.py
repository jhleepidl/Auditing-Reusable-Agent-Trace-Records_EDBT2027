"""Apply the fixed utility rule to exposed development; never confirmation metrics."""
import argparse, statistics
from pathlib import Path
from common21 import ROOT,load,write,sha,now
def main():
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();assert not a.out.exists();versions=[]
 for i in [1,2,3]:
  f=ROOT/f'e2/development_v{i}_metrics/METRICS.json'
  if not f.exists():continue
  x=load(f);ss=[t for t in x['task_macro_summary'] if t['method']=='evidence_bound/scope'];assert len(ss)==2
  contrasts=[t for t in x['paired_contrasts'] if t['contrast']=='evidence_bound - direct' and t['policy']=='scope'];assert len(contrasts)==2
  safety=all(t['false_pass_rate']['difference']<=0 for t in contrasts);retention=all(t['valid_retention']['difference']>=0 for t in contrasts);strict=any(t['false_pass_rate']['difference']<0 or t['valid_retention']['difference']>0 for t in contrasts);nonblanket=all(t['task_macro_valid_retention']>0 for t in ss)
  versions.append({'version':'v'+str(i),'order':i,'utility':statistics.mean(t['task_macro_valid_retention']-t['task_macro_false_pass_rate'] for t in ss),'valid_retention':statistics.mean(t['task_macro_valid_retention'] for t in ss),'joint_direction_target_met':safety and retention and strict and nonblanket,'per_model_contrasts':contrasts,'metrics_sha256':sha(f)})
 assert versions;best=max(versions,key=lambda t:(t['utility'],t['valid_retention'],-t['order']))
 write(a.out,{'utc':now(),'designation':'development selection; no confirmation outcomes available','protocol_sha256':sha(ROOT/'e2/PROTOCOL.json'),'selection_rule':'equal-model mean task-macro retention minus false-pass rate; higher retention then earlier version break ties','versions':versions,'selected_version':best['version'],'selected_joint_direction_target_met':best['joint_direction_target_met'],'no_claim_of_confirmed_improvement':True,'third_version_not_needed_if_target_met':True})
 print(best['version'],best['utility'],best['joint_direction_target_met'])
if __name__=='__main__':main()
