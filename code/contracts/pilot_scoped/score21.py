"""Complete task-macro results and paired task bootstrap, no seed pseudo-replication."""
import argparse, collections, csv, json, random, statistics
from pathlib import Path
from common21 import load, rows, write, write_rows, sha
def avg(xs):
 xs=[x for x in xs if x is not None];return statistics.mean(xs) if xs else None
def stats(gold,pred):
 assert set(gold)==set(pred)
 pos=[k for k,v in gold.items() if v['reference_status']=='pass'];neg=[k for k,v in gold.items() if v['reference_status']=='fail'];unknown=[k for k,v in gold.items() if v['reference_status']=='unknown']
 return {'false_pass_rate':sum(pred[k]=='pass' for k in neg)/len(neg) if neg else None,'valid_retention':sum(pred[k]=='pass' for k in pos)/len(pos) if pos else None,'decisive_coverage':sum(v in {'pass','fail'} for v in pred.values())/len(gold), 'false_pass':sum(pred[k]=='pass' for k in neg),'valid_retained':sum(pred[k]=='pass' for k in pos),'false_reject':sum(pred[k]=='fail' for k in pos),'unknown':sum(v=='unknown' for v in pred.values()),'errors':sum(v=='error' for v in pred.values()),'unresolved_promoted':sum(pred[k]=='pass' for k in unknown),'reference_positive':len(pos),'reference_negative':len(neg),'reference_unknown':len(unknown)}
def ci(ds):
 if not ds:return None
 rng=random.Random(20261004);n=len(ds);boots=sorted(sum(ds[rng.randrange(n)] for _ in range(n))/n for _ in range(10000))
 return {'difference':statistics.mean(ds),'paired_task_bootstrap_95_percent_ci':[boots[249],boots[9749]],'tasks':n,'resamples':10000,'seed':20261004}
def main():
 p=argparse.ArgumentParser();p.add_argument('--reference',type=Path,required=True);p.add_argument('--predictions',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
 gold=rows(a.reference);pred=rows(a.predictions);g={x['case_id']:x for x in gold};assert len(g)==len(gold)
 for x in pred:
  assert x['case_id'] in g and all(x[k]==g[x['case_id']][k] for k in ['scope_id','scope_sha256','source_packet_sha256','input_sha256','task_key'])
 assert len({(x['case_id'],x['method'],x['model'],x['seed']) for x in pred})==len(pred),'Duplicate prediction cells'
 receipt=load(a.predictions.parent/'RECEIPT.json');planned={tuple(k) for k in receipt['planned_grid']};actual={tuple(x[k] for k in ['method','model','seed']) for x in pred};assert actual==planned,'Missing or additional entire construction arm/model/seed group'
 assert len(pred)==len(gold)*len(planned),'Incomplete planned prediction grid'
 keys=sorted(planned);taskkeys=sorted({x['task_key'] for x in gold});perseed=[];pertask=[];summary=[];lookup={}
 for method,model,seed in keys:
  pp={x['case_id']:x['status'] for x in pred if (x['method'],x['model'],x['seed'])==(method,model,seed)};assert len(pp)==len(g)
  s=stats(g,pp);perseed.append({'method':method,'model':model,'seed':seed}|s)
  for t in taskkeys:
   gg={k:v for k,v in g.items() if v['task_key']==t};lookup[method,model,seed,t]=stats(gg,{k:pp[k] for k in gg})
 for method,model in sorted({(k[0],k[1]) for k in keys}):
  seeds=sorted(k[2] for k in keys if k[:2]==(method,model));ts=[]
  for t in taskkeys:
   rr={'method':method,'model':model,'task_key':t,'seeds':seeds}
   for metric in ['false_pass_rate','valid_retention','decisive_coverage']:rr[metric]=avg([lookup[method,model,seed,t][metric] for seed in seeds])
   ts.append(rr);pertask.append(rr)
  ss={'method':method,'model':model,'total_tasks':len(taskkeys),'reference_supported_tasks':sum(t['valid_retention'] is not None for t in ts),'seeds':seeds}
  for metric in ['false_pass_rate','valid_retention','decisive_coverage']:ss['task_macro_'+metric]=avg([t[metric] for t in ts])
  for metric in ['false_pass','valid_retained','false_reject','unknown','errors','unresolved_promoted']:ss[metric+'_all_seeds']=sum(v[metric] for v in perseed if v['method']==method and v['model']==model)
  summary.append(ss)
 paired=[]
 for model in sorted({x['model'] for x in summary}):
  for policy in ['scope','scope_source']:
   for arm in ['schema_only','evidence_bound']:
    d={x['task_key']:x for x in pertask if x['model']==model and x['method']=='direct/'+policy};e={x['task_key']:x for x in pertask if x['model']==model and x['method']==arm+'/'+policy}
    if not d or not e:continue
    pair={'model':model,'policy':policy,'contrast':arm+' - direct'}
    for metric in ['false_pass_rate','valid_retention','decisive_coverage']:pair[metric]=ci([e[t][metric]-d[t][metric] for t in sorted(set(d)&set(e)) if e[t][metric] is not None and d[t][metric] is not None])
    pair['joint_direction_gain']=pair['false_pass_rate']['difference']<=0 and pair['valid_retention']['difference']>=0 and (pair['false_pass_rate']['difference']<0 or pair['valid_retention']['difference']>0)
    paired.append(pair)
 result={'designation':'scope-aligned versioned R21 results; selected obligations are not full-task gold','task_macro_summary':summary,'per_seed':perseed,'per_task_metrics':pertask,'paired_contrasts':paired,'primary_contrast':'evidence_bound - direct for each model under scope policy; safety and retention jointly','reference_sha256':sha(a.reference),'predictions_sha256':sha(a.predictions),'seed_repeats_are_not_independent_tasks':True}
 write(a.out/'METRICS.json',result);write_rows(a.out/'TASK_METRICS.jsonl',pertask)
 print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
