"""Derive checkpoint/read rows from observations, never from retained result rows."""
from __future__ import annotations
import hashlib
import statistics
from pathlib import Path
from release_io import Inputs, canonical, equal, load, write

E='studies/frozen/baseline_r21/e1/'
FIELDS=('prefix_json_exact','prefix_graph_exact','returns_errors_exact','suffix_state_exact','suffix_graph_exact')

def digest(obj):return hashlib.sha256(canonical(obj)).hexdigest()
def require(ok,msg):
    if not ok:raise ValueError(msg)
def compare(actual,expected):
    require(len(actual)==len(expected),'Suffix length differs')
    return {'returns_errors_exact':all(a['result']==b['result'] and a['error']==b['error'] for a,b in zip(actual,expected)),
            'suffix_state_exact':all(digest(a['state'])==digest(b['state']) for a,b in zip(actual,expected)),
            'suffix_graph_exact':all(a['graph_sha256']==b['graph_sha256'] for a,b in zip(actual,expected))}

def run(inputs:Inputs,out:Path)->dict:
    read=lambda x: inputs.json(E+x)
    plan=read('CORPUS_PLAN.json');programs=plan['programs'];arms=plan['arms'];rows=[]
    for p in programs:
        base='corpus_results_v1/cases/'+p['fixture_id']+'/'
        native=read(base+'native_trace.json');prefix=read(base+'prefix_state.json');w=read(base+'witness.json');cut=p['cut']
        require(len(native)==len(p['steps']),'Native step inventory')
        require(w['snapshot_sha256']==digest(prefix)==digest(native[cut-1]['state']),'Snapshot binding')
        require(digest(w)==native[cut-1]['graph_sha256'],'Graph binding')
        require([i for i,r in enumerate(native) if r['error'] is not None]==p['expected_error_indices'],'Expected-error inventory')
        for arm in arms:
            state=read(base+arm+'_prefix_state.json');graph=read(base+arm+'_prefix_graph.json');trace=read(base+arm+'_continued_trace.json')
            rows.append({'fixture_id':p['fixture_id'],'arm':arm,'prefix_json_exact':digest(state)==digest(prefix),
                         'prefix_graph_exact':graph==w,**compare(trace,native[cut:])})
    summary={a:{k:sum(r[k] for r in rows if r['arm']==a) for k in FIELDS} for a in arms}
    rplan=read('READ_PLAN.json');readrows=[]
    for p in rplan['programs']:
        base='read_results_v1/cases/'+p['fixture_id']+'/';native=read(base+'native_trace.json')
        require(native[-1]['call']['function']=='get_sent_emails','Expected actual native read')
        for arm in ['v4_control','full_witness']:
            trace=read(base+arm+'_continued_trace.json')
            require(trace[-1]['call']['function']=='get_sent_emails','Expected restored read')
            readrows.append({'fixture_id':p['fixture_id'],'arm':arm,**compare(trace,native[p['cut']:]),
                'read_returns_errors_exact':trace[-1]['result']==native[-1]['result'] and trace[-1]['error']==native[-1]['error']})
    samples=read('cost_results_v1/paired_samples.json');sizes=read('cost_results_v1/sizes.json');costplan=read('COST_PLAN.json')
    require(len(samples)==len(programs)*len(arms)*costplan['paired_repetitions']==1512,'Timing grid')
    require(len(sizes)==len(programs)*len(arms),'Size grid')
    costs={}
    for arm in arms:
        ss=[s for s in sizes if s['arm']==arm];rr=[s for s in samples if s['arm']==arm]
        med=lambda f: statistics.median(statistics.median(s[f+'_ns'] for s in rr if s['fixture_id']==p['fixture_id']) for p in programs)/1e6
        costs[arm]={'median_program_capture_ms':med('capture'),'median_program_restore_ms':med('restore'),
                    'median_serialized_bytes':statistics.median(s['serialized_format_bytes'] for s in ss),
                    'median_gzip_bytes':statistics.median(s['gzip_level9_bytes'] for s in ss)}
    f9=read('corpus_results_v1/cases/F09/prefix_state.json');f10=read('corpus_results_v1/cases/F10/prefix_state.json')
    p9=next(p for p in programs if p['fixture_id']=='F09');p10=next(p for p in programs if p['fixture_id']=='F10')
    require(f9==f10 and p9['steps'][p9['cut']:]==p10['steps'][p10['cut']:],'Value-identical example')
    n9=read('corpus_results_v1/cases/F09/native_trace.json');n10=read('corpus_results_v1/cases/F10/native_trace.json')
    require(digest(n9[-1]['state'])!=digest(n10[-1]['state']),'F09/F10 post-state contrast')
    # Only after deriving observations do we consult compact publication expectations.
    expected=load(inputs.root/'expected/checkpoint_summary.json')
    for a in arms:
        for k in FIELDS:equal(summary[a][k],expected['corpus']['by_arm'][a][k],a+'/'+k)
        for k,v in costs[a].items():equal(v,expected['costs']['by_arm'][a][k],a+'/'+k)
    agreement={a:sum(r['read_returns_errors_exact'] for r in readrows if r['arm']==a) for a in ['v4_control','full_witness']}
    for a,v in agreement.items():equal(v,expected['reads']['by_arm'][a]['read_returns_errors_exact'],a+'/reads')
    report={'status':'PASS','checkpoint_programs':len(programs),'checkpoint_rows':len(rows),'read_rows':len(readrows),
        'read_denominator':len(rplan['programs']),'paired_timing_samples':len(samples),'checkpoint_summary':summary,
        'read_agreement':agreement,'cost_summary':costs,
        'identical_checkpoint_example':{'programs':['F09','F10'],'prefix_json_equal':True,'suffix_calls_equal':True,
            'complete_post_states_differ':True,'original_tool_return_and_error_equal':n9[-1]['result']==n10[-1]['result'] and n9[-1]['error']==n10[-1]['error']},
        'scope':'Recomputed from retained native and restored observations; not new native execution or new timing.'}
    write(out/'checkpoint_rows.json',rows);write(out/'read_rows.json',readrows);write(out/'checkpoint_summary.json',report)
    return report
