#!/usr/bin/env python3
"""Score explicit-scope contract decisions against separately frozen references.
All declared method/model/seed/case cells are required; missing outputs cannot
be dropped. Use status='error' for execution failures. Risk and valid retention
are both reported. No semantic labels are inferred from native evaluator output.
"""
from __future__ import annotations
import argparse,collections,statistics,random,math
from pathlib import Path
from common_handoff import read_jsonl,load,write,new_out,sha
VALID={'pass','fail','unknown','error'}

def unit_stats(gold,pred):
    n=len(gold);pos=[k for k,v in gold.items() if v['reference_status']=='pass'];neg=[k for k,v in gold.items() if v['reference_status']=='fail']
    unk=[k for k,v in gold.items() if v['reference_status']=='unknown']
    def rate(n,d):return n/d if d else None
    false_pass=sum(pred[k]=='pass' for k in neg);retained=sum(pred[k]=='pass' for k in pos)
    return {'n':n,'reference_positive':len(pos),'reference_negative':len(neg),'reference_unresolved':len(unk),
      'false_pass':false_pass,'false_pass_rate':rate(false_pass,len(neg)),
      'valid_retained':retained,'valid_retention':rate(retained,len(pos)),
      'false_reject':sum(pred[k]=='fail' for k in pos),'unknown':sum(v=='unknown' for v in pred.values()),
      'errors':sum(v=='error' for v in pred.values()),
      'unresolved_reference_promoted_to_pass':sum(pred[k]=='pass' for k in unk),
      'unresolved_reference_decided':sum(pred[k] in ('pass','fail') for k in unk),
      'decisive_coverage':rate(sum(v in ('pass','fail') for v in pred.values()),n)}

def compare(gold_rows,pred_rows,methods,models,seeds,bootstrap=2000):
    if not gold_rows:raise ValueError('Empty reference inventory')
    for name,values in [('methods',methods),('models',models),('seeds',seeds)]:
        if not values or len(values)!=len(set(values)):raise ValueError('Empty or duplicate '+name)
    if bootstrap<100:raise ValueError('Use at least 100 bootstrap resamples')
    gold={r['case_id']:r for r in gold_rows}
    if len(gold)!=len(gold_rows):raise ValueError('Duplicate reference case ID')
    for r in gold_rows:
        for field in ['case_id','task_key','scope_id','reference_status','input_sha256','reference_evidence']:
            if field not in r:raise ValueError('Reference missing '+field)
        if r['reference_status'] not in {'pass','fail','unknown'}:raise ValueError('Bad reference status')
        if not r['reference_evidence']:raise ValueError('Source/evidence cannot be empty')
    groups=collections.defaultdict(dict)
    for r in pred_rows:
        key=(r['method'],r['model'],r['seed']);cid=r['case_id']
        if key not in {(x,y,z) for x in methods for y in models for z in seeds}:raise ValueError('Undeclared method/model/seed')
        if cid not in gold:raise ValueError('Unknown prediction case')
        if cid in groups[key]:raise ValueError('Duplicate prediction cell')
        if r['status'] not in VALID:raise ValueError('Invalid decision')
        if r['input_sha256']!=gold[cid]['input_sha256'] or r['scope_id']!=gold[cid]['scope_id']:
            raise ValueError('Input or claim scope mismatch')
        groups[key][cid]=r['status']
    per=[];task_metrics={}
    tasks=sorted({r['task_key'] for r in gold.values()})
    for method in methods:
        for model in models:
            by_task=collections.defaultdict(list)
            for seed in seeds:
                key=(method,model,seed);pred=groups[key]
                if set(pred)!=set(gold):raise ValueError(f'Incomplete cell inventory for {key}; explicitly record errors')
                per.append({'method':method,'model':model,'seed':seed,**unit_stats(gold,pred)})
                for task in tasks:
                    sub={k:v for k,v in gold.items() if v['task_key']==task}
                    by_task[task].append(unit_stats(sub,{k:pred[k] for k in sub}))
            task_metrics[(method,model)]={}
            for task,stats in by_task.items():
                task_metrics[(method,model)][task]={m:statistics.mean([s[m] for s in stats if s[m] is not None])
                   if any(s[m] is not None for s in stats) else None
                   for m in ('false_pass_rate','valid_retention','decisive_coverage')}
    comparisons=[];baseline=methods[0]
    for model in models:
        for method in methods[1:]:
            for metric in ('false_pass_rate','valid_retention','decisive_coverage'):
                ds=[task_metrics[(method,model)][t][metric]-task_metrics[(baseline,model)][t][metric]
                    for t in tasks if task_metrics[(method,model)][t][metric] is not None and task_metrics[(baseline,model)][t][metric] is not None]
                rng=random.Random(20261004);boots=sorted(statistics.mean(rng.choices(ds,k=len(ds))) for _ in range(bootstrap)) if ds else []
                comparisons.append({'model':model,'method':method,'baseline':baseline,'metric':metric,
                     'task_macro_difference':statistics.mean(ds) if ds else None,'tasks':len(ds),
                     'task_cluster_bootstrap_95':[boots[int(.025*(len(boots)-1))],boots[int(.975*(len(boots)-1))]] if boots else None})
    return {'per_seed':per,'paired_task_macro_differences':comparisons,
            'tasks':len(tasks),'cases':len(gold),'scope':'Declared reference scope only; neither exact-atom agreement nor native pass is semantic gold.',
            'statistical_note':'Bootstrap clusters are tasks. Model/seed repetitions are averaged within task, never counted as new independent tasks.'}

def main():
    p=argparse.ArgumentParser();p.add_argument('--reference',type=Path,required=True);p.add_argument('--predictions',type=Path,required=True)
    p.add_argument('--inventory',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    inv=load(a.inventory);out=new_out(a.out)
    report=compare(read_jsonl(a.reference),read_jsonl(a.predictions),inv['methods'],inv['models'],inv['seeds'])
    report['input_files_sha256']={str(f):sha(f) for f in (a.reference,a.predictions,a.inventory)}
    write(out/'METRICS.json',report)
if __name__=='__main__':main()
