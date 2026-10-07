#!/usr/bin/env python3
"""Lossless adapter-output normalization: retain failed calls as null candidates.
Requires private packet mapping on the evaluation side, not on the model side.
Model aliases are not silently relabelled; resolved IDs remain in the audit log.
"""
import argparse
from pathlib import Path
from common_handoff import load,read_jsonl,write_jsonl,write,new_out,sha

def main():
    p=argparse.ArgumentParser();p.add_argument('--requests',type=Path,required=True)
    p.add_argument('--mapping',type=Path,required=True);p.add_argument('--run',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=new_out(a.out)
    mapping={r['packet_id']:r['task_key'] for r in load(a.mapping)};rows=[];resolved={}
    for r in read_jsonl(a.requests):
        pth=a.run/'responses'/(r['request_id']+'.json')
        row={k:r[k] for k in ['method','model','seed']};row['task_key']=mapping[r['packet_id']]
        row['request_id']=r['request_id']
        if pth.exists():
            rec=load(pth)
            if any(rec.get(k)!=r[k] for k in ['request_id','packet_id','method','model','seed']):raise ValueError('Attempt binding mismatch')
            response=rec.get('response',{});ann=response.get('annotation')
            row.update(annotation=ann if rec.get('status')=='completed' else None,
                       construction_status=rec.get('status'),resolved_model_id=response.get('resolved_model_id'))
            if row['resolved_model_id']:resolved.setdefault(r['model'],set()).add(row['resolved_model_id'])
        else:row.update(annotation=None,construction_status='missing_attempt',resolved_model_id=None)
        rows.append(row)
    write_jsonl(out/'candidates.jsonl',rows)
    write(out/'NORMALIZATION_RECEIPT.json',{'requests_sha256':sha(a.requests),'mapping_sha256':sha(a.mapping),
        'candidate_cells':len(rows),'missing_or_failed_calls':sum(x['annotation'] is None for x in rows),
        'resolved_model_ids':{k:sorted(v) for k,v in resolved.items()},
        'warning':'An alias resolving to multiple snapshots invalidates a fixed-model comparison; split or rerun all planned cells.'})
if __name__=='__main__':main()
