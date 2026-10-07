#!/usr/bin/env python3
"""Execute the unchanged R11 state DSL on separately frozen challenge inputs.

Candidate JSONL: task_key, method, model, seed, annotation (or null on failure).
Case JSONL: case_id, task_key, scope_id, input_file, input_sha256.
Each input_file (relative to the case manifest) contains pre_state and post_state.
No reference decisions are loaded. Query/excluded candidates remain UNKNOWN,
not fabricated state or semantic passes. Scope is supplied by the challenge, not
inferred from agreement with candidate predicates.
"""
from pathlib import Path
import sys,argparse,collections
from common_handoff import load,read_jsonl,write_jsonl,write,new_out,kit_path,sha

def main():
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True)
    p.add_argument('--candidates',type=Path,required=True);p.add_argument('--cases',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--gates',nargs='+',choices=['literal','initial','hybrid'],default=['literal','initial','hybrid'])
    a=p.parse_args();out=new_out(a.out);kit=kit_path(a.work)
    sys.path.insert(0,str(kit/'vendor/r11'))
    import contract_engine as ce
    import schema_gate as sg
    candidates=read_jsonl(a.candidates);cases=read_jsonl(a.cases)
    if not candidates or not cases:raise ValueError('Empty input inventory')
    if len({r['case_id'] for r in cases})!=len(cases):raise ValueError('Duplicate case ID')
    seen=set();inputs={}
    for c in cases:
        path=(a.cases.parent/c['input_file']).resolve()
        if not path.is_relative_to(a.cases.parent.resolve()):raise ValueError('Case input must stay inside challenge directory')
        if sha(path)!=c['input_sha256']:raise ValueError('Case input hash mismatch: '+c['case_id'])
        inputs[c['case_id']]=load(path)
    rows=[];diagnostics=[]
    for cand in candidates:
        key=tuple(cand[k] for k in ['task_key','method','model','seed'])
        if key in seen:raise ValueError('Duplicate candidate cell')
        seen.add(key);matched=[c for c in cases if c['task_key']==cand['task_key']]
        if not matched:raise ValueError('Candidate without challenge cases: '+str(key))
        suite=cand['task_key'].split('/')[0]
        schema=load(kit/f'inputs/r11/schemas/{suite}.json')
        for c in matched:
            data=inputs[c['case_id']]
            for gate in a.gates:
                row={'case_id':c['case_id'],'scope_id':c['scope_id'],'input_sha256':c['input_sha256'],
                     'method':cand['method']+'/'+gate,'model':cand['model'],'seed':cand['seed']}
                detail={'case_id':c['case_id'],'candidate_key':key,'gate_policy':gate}
                try:
                    ann=cand['annotation']
                    if ann is None:raise ValueError('Candidate construction failed; retained as error')
                    if gate=='literal':g={'admitted':True,'issues':[]}
                    elif gate=='initial':g=ce.preflight(ann,data['pre_state'])
                    else:g=sg.hybrid_admission(ann,data['pre_state'],schema)
                    result=ce.evaluate(ann,data['pre_state'],data['post_state']) if g['admitted'] else {'verdict':'unknown','reason':'not_admitted'}
                    row['status']=result['verdict'];detail.update(admission=g,result=result)
                except Exception as e:
                    row['status']='error';detail['error']=type(e).__name__+': '+str(e)
                rows.append(row);diagnostics.append(detail)
    write_jsonl(out/'predictions.jsonl',rows);write_jsonl(out/'diagnostics.jsonl',diagnostics)
    write(out/'EXECUTION_RECEIPT.json',{'candidates_sha256':sha(a.candidates),'cases_sha256':sha(a.cases),
      'interpreter_sha256':sha(kit/'vendor/r11/contract_engine.py'),'gate_sha256':sha(kit/'vendor/r11/schema_gate.py'),
      'prediction_cells':len(rows),'uses_reference_labels':False,'query_engine':'NOT_IMPLEMENTED_IN_R11_STATE_DSL',
      'note':'Score all declared cells with score_contracts.py. These statuses do not automatically set the paper semantic dimension a_M.'})
if __name__=='__main__':main()
