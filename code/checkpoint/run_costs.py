"""Paired warm CPU costs. No external serialized pickle is ever loaded."""
from pathlib import Path
import argparse,json,time,statistics,gzip,pickle,platform,gc
from common21 import *
from ablation_reader import ARMS,restore_arm

def selected_witness(w,arm):
    keys=['format','snapshot_sha256','native_source_revision','root_type']
    if arm=='type_order':keys+=['model_types','dict_orders']
    elif arm=='alias_endpoint_types':keys+=['aliases']
    elif arm=='full_witness':return w
    return {k:w[k] for k in keys}
def encode_live(prefix,arm):
    if arm=='trusted_pickle':return pickle.dumps(prefix,protocol=5)
    state=rn.dump(prefix)
    if arm in ('json_only','v4_control'):return canon(state).encode()
    return canon({'state':state,'witness':selected_witness(capture(prefix),arm)}).encode()
def decode_new_live_bytes(data,arm,cls):
    if arm=='trusted_pickle':return pickle.loads(data) # Newly generated local live-object bytes only, never a file/input.
    d=json.loads(data)
    if arm in ('json_only','v4_control'):return restore_arm(arm,cls,d,None)
    return restore_arm(arm,cls,d['state'],d['witness'])
def run(out):
    verify_freeze();plan=load(HERE/'COST_PLAN.json');out=new_out(out)
    write(out/'START.json',{'utc':utc(),'freeze_sha256':sha(HERE/'FREEZE.json'),'study_id':plan['study_id']});sizes=[];samples=[]
    with rn.no_network():
        api=rn.setup();suite=api.get_suite('v1','workspace')
        for fi,p in enumerate(load(HERE/'CORPUS_PLAN.json')['programs']):
            prefix,post,trace=native_program(api,suite,p);state=rn.dump(prefix);w=capture(prefix)
            raw_state=canon(state).encode();raw_w=canon(w).encode()
            for arm in plan['arms']:
                data=encode_live(prefix,arm);side=0 if arm in ('json_only','v4_control','trusted_pickle') else len(canon(selected_witness(w,arm)).encode())
                sizes.append({'fixture_id':p['fixture_id'],'arm':arm,'canonical_state_bytes':len(raw_state),'canonical_full_witness_bytes':len(raw_w),'selected_sidecar_bytes':side,'serialized_format_bytes':len(data),'gzip_level9_bytes':len(gzip.compress(data,compresslevel=9,mtime=0)),'format':'pickle_protocol_5' if arm=='trusted_pickle' else 'canonical_UTF8_JSON'})
            n=len(plan['arms'])
            for rep in range(-plan['warmups'],plan['paired_repetitions']):
                rotation=(fi+rep)%n;arms=plan['arms'][rotation:]+plan['arms'][:rotation]
                for position,arm in enumerate(arms):
                    start=time.perf_counter_ns();data=encode_live(prefix,arm);captured=time.perf_counter_ns()-start
                    start=time.perf_counter_ns()
                    try:
                        obj=decode_new_live_bytes(data,arm,type(prefix));restored=time.perf_counter_ns()-start
                        # Equal graph/value checks outside the timer, preserving failures.
                        result={'status':'completed','prefix_json_exact':digest(rn.dump(obj))==digest(state),'prefix_graph_exact':capture(obj)==w}
                    except Exception as exc:
                        restored=time.perf_counter_ns()-start;result={'status':'error','reason':type(exc).__name__+': '+str(exc),'prefix_json_exact':False,'prefix_graph_exact':False}
                    if rep>=0:samples.append({'fixture_id':p['fixture_id'],'arm':arm,'paired_rep':rep,'position':position,'capture_ns':captured,'restore_ns':restored,**result})
            print('measured '+p['fixture_id'],flush=True)
    write(out/'sizes.json',sizes);write(out/'paired_samples.json',samples)
    summary={'study_id':plan['study_id'],'programs':36,'warmups':plan['warmups'],'paired_repetitions':plan['paired_repetitions'],'raw_paired_samples':len(samples),'by_arm':{},'environment':{'python':platform.python_version(),'platform':platform.platform(),'machine':platform.machine(),'gc_enabled':gc.isenabled(),'timer':'perf_counter_ns','dependency_pins':75},'api_calls':0}
    for arm in plan['arms']:
        ss=[s for s in sizes if s['arm']==arm];rr=[s for s in samples if s['arm']==arm]
        # Each program contributes one median, avoiding treating repetitions as independent tasks.
        case_medians=[{k:statistics.median(x[k] for x in rr if x['fixture_id']==p['fixture_id']) for k in ['capture_ns','restore_ns']} for p in load(HERE/'CORPUS_PLAN.json')['programs']]
        summary['by_arm'][arm]={'median_serialized_bytes':statistics.median(x['serialized_format_bytes'] for x in ss),'median_gzip_bytes':statistics.median(x['gzip_level9_bytes'] for x in ss),'median_selected_sidecar_bytes':statistics.median(x['selected_sidecar_bytes'] for x in ss),'median_program_capture_ms':statistics.median(x['capture_ns'] for x in case_medians)/1e6,'median_program_restore_ms':statistics.median(x['restore_ns'] for x in case_medians)/1e6,'sample_errors':sum(x['status']!='completed' for x in rr),'prefix_json_exact_samples':sum(x['prefix_json_exact'] for x in rr),'prefix_graph_exact_samples':sum(x['prefix_graph_exact'] for x in rr)}
    summary['median_canonical_full_sidecar_state_ratio']=statistics.median(x['canonical_full_witness_bytes']/x['canonical_state_bytes'] for x in sizes if x['arm']=='full_witness')
    summary['timing_scope']='Capture: dump+canonical encoding and selected graph capture (pickle: dumps protocol5). Restore: JSON parse+reader or pickle.loads; reader intrinsic checks included, equal postchecks outside timer. Warm same process, no file/network/tool replay timing; gc enabled; finite repeated programs, not independent timing trials or end-to-end operating overhead.'
    write(out/'SUMMARY.json',summary);print(json.dumps(summary,indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);run(p.parse_args().out)
