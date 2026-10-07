"""Recompute Table 3 fractions from retained per-record native execution receipts."""
from release_io import load,write,equal

def run(inputs,out):
    config=load(inputs.root/'configs/census_inputs.json');result=[]
    for label,names in config.items():
        rows=[inputs.json(k) for k in names]
        keys=[(r['dataset'],r['suite'],r['task_id'],r['version']) for r in rows]
        if len(set(keys))!=len(rows) or len(rows)!=311:raise ValueError('Incomplete or duplicate census grid')
        for r in rows:
            if r.get('status')=='completed':
                if r['same_label']!=(r['label']==r['native_label']):raise ValueError('Label comparison mismatch')
                if r['exact_state']!=(r['restored_pre_sha256']==r['pre_sha256'] and r['restored_post_sha256']==r['post_sha256']):
                    raise ValueError('State hash comparison mismatch')
        for ds in ['sweep','replay20']:
            rr=[r for r in rows if r['dataset']==ds]
            result.append({'reader':label,'dataset':ds,'records':len(rr),
                'eligible_suffixes':sum(r['continuation_eligible'] for r in rr),
                'fidelity':sum(bool(r.get('exact_state') and r.get('same_label')) for r in rr),
                'exact_suffix':sum(r.get('continuation_exact') is True for r in rr)})
    equal(result,load(inputs.root/'expected/census_metrics.json'),'census metrics')
    write(out/'census_metrics.json',result)
    return result
