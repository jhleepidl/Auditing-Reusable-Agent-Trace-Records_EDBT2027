"""Task-template clustered statistics, retained construction errors and all fixed cases."""
import argparse,collections,json,random,statistics
from pathlib import Path
from common22 import load,rows,write,write_rows,sha
def mean(xs):
    xs=[x for x in xs if x is not None];return statistics.mean(xs) if xs else None
def stats(g,p):
    assert set(g)==set(p)
    pos=[k for k,v in g.items() if v['reference_status']=='pass'];neg=[k for k,v in g.items() if v['reference_status']=='fail'];unk=[k for k,v in g.items() if v['reference_status']=='unknown']
    return {'false_pass_rate':sum(p[k]=='pass' for k in neg)/len(neg) if neg else None,'valid_retention':sum(p[k]=='pass' for k in pos)/len(pos) if pos else None,
      'decisive_coverage':sum(v in {'pass','fail'} for v in p.values())/len(g),'false_pass':sum(p[k]=='pass' for k in neg),'valid_retained':sum(p[k]=='pass' for k in pos),
      'false_reject':sum(p[k]=='fail' for k in pos),'unknown':sum(v=='unknown' for v in p.values()),'errors':sum(v=='error' for v in p.values()),'unresolved_promoted':sum(p[k]=='pass' for k in unk)}
def ci(ds):
    rng=random.Random(20261005);n=len(ds);assert n
    b=sorted(sum(ds[rng.randrange(n)] for _ in range(n))/n for _ in range(10000))
    return {'difference':statistics.mean(ds),'paired_task_bootstrap_95_percent_ci':[b[249],b[9749]],'tasks':n,'resamples':10000,'seed':20261005}
def score(reference,predictions,receipt):
    gold={r['case_id']:r for r in reference};assert len(gold)==len(reference)
    assert len({(p['case_id'],p['method'],p['model'],p['repeat']) for p in predictions})==len(predictions)
    planned={tuple(x) for x in receipt['planned_grid']};actual={(p['method'],p['model'],p['repeat']) for p in predictions};assert actual==planned
    assert len(predictions)==len(gold)*len(planned),'Incomplete planned grid'
    for p in predictions:
        assert p['case_id'] in gold and p['status'] in {'pass','fail','unknown','error'}
        assert all(p[k]==gold[p['case_id']][k] for k in ['task_key','world_id','scope_id','scope_sha256','source_packet_sha256','input_sha256'])
    tasks=sorted({g['task_key'] for g in reference});per_world=[];per_task=[];summary=[]
    for method,model,repeat in sorted(planned):
        p={x['case_id']:x['status'] for x in predictions if (x['method'],x['model'],x['repeat'])==(method,model,repeat)}
        assert set(p)==set(gold)
        for task in tasks:
            for world in sorted({v['world_id'] for v in reference if v['task_key']==task}):
                g={k:v for k,v in gold.items() if v['task_key']==task and v['world_id']==world}
                per_world.append({'method':method,'model':model,'repeat':repeat,'task_key':task,'world_id':world}|stats(g,{k:p[k] for k in g}))
    for method,model in sorted({k[:2] for k in planned}):
        for task in tasks:
            g=[x for x in per_world if (x['method'],x['model'],x['task_key'])==(method,model,task)]
            r={'method':method,'model':model,'task_key':task,'worlds':sorted({x['world_id'] for x in g}),'repeats':sorted({x['repeat'] for x in g})}
            for metric in ['false_pass_rate','valid_retention','decisive_coverage']:
                worldmeans=[mean([x[metric] for x in g if x['world_id']==world]) for world in r['worlds']]
                r[metric]=mean(worldmeans)
            per_task.append(r)
        vals=[r for r in per_task if (r['method'],r['model'])==(method,model)]
        s={'method':method,'model':model,'tasks':len(vals)}
        for metric in ['false_pass_rate','valid_retention','decisive_coverage']:s['task_macro_'+metric]=mean([v[metric] for v in vals])
        for metric in ['false_pass','valid_retained','false_reject','unknown','errors','unresolved_promoted']:s[metric+'_all_cells']=sum(v[metric] for v in per_world if (v['method'],v['model'])==(method,model))
        summary.append(s)
    contrasts=[]
    for model in sorted({s['model'] for s in summary}):
        for other,base in [('derived','literal'),('derived_verified','derived'),('derived','literal_rebound'),('derived','literal_bound')]:
            a={r['task_key']:r for r in per_task if (r['model'],r['method'])==(model,other)};b={r['task_key']:r for r in per_task if (r['model'],r['method'])==(model,base)}
            if not a or not b:continue
            c={'model':model,'contrast':other+' - '+base,'designation':'primary' if base=='literal' else 'secondary'}
            for metric in ['false_pass_rate','valid_retention','decisive_coverage']:c[metric]=ci([a[t][metric]-b[t][metric] for t in tasks if a[t][metric] is not None and b[t][metric] is not None])
            c['nonblanket_retention']=mean([v['valid_retention'] for v in a.values()])>0
            c['observed_joint_direction_gain']=c['nonblanket_retention'] and c['false_pass_rate']['difference']<=0 and c['valid_retention']['difference']>=0 and (c['false_pass_rate']['difference']<0 or c['valid_retention']['difference']>0)
            contrasts.append(c)
    return {'designation':'Eight exposed benchmark-template source-conditioned study; partial selected scope only','task_macro_summary':summary,'per_task_metrics':per_task,'per_world_repeat':per_world,'paired_contrasts':contrasts,
      'statistical_unit':'task template, not worlds/seeds/cases','primary':'Fresh reconstruction derived minus literal separately by model','formal_noninferiority_test':False}
def main():
    p=argparse.ArgumentParser();p.add_argument('--reference',type=Path,required=True);p.add_argument('--predictions',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();assert not a.out.exists();a.out.mkdir(parents=True)
    result=score(rows(a.reference),rows(a.predictions),load(a.predictions.parent/'RECEIPT.json'));result.update(reference_sha256=sha(a.reference),predictions_sha256=sha(a.predictions))
    write(a.out/'METRICS.json',result);write_rows(a.out/'TASK_METRICS.jsonl',result['per_task_metrics']);print(json.dumps(result['task_macro_summary'],indent=2))
if __name__=='__main__':main()
