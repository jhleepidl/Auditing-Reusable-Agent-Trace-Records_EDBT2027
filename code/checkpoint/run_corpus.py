from pathlib import Path
import argparse,json
from common21 import *
from ablation_reader import *

def run(out):
    f=verify_freeze();plan=load(HERE/'CORPUS_PLAN.json');out=new_out(out)
    write(out/'START.json',{'utc':utc(),'freeze_sha256':sha(HERE/'FREEZE.json'),'study_id':plan['study_id']});rows=[]
    with rn.no_network():
        api=rn.setup();suite=api.get_suite('v1','workspace')
        for p in plan['programs']:
            folder=out/'cases'/p['fixture_id']
            prefix,post,trace=native_program(api,suite,p);payload=transported(prefix);witness=capture(prefix)
            write(folder/'native_trace.json',trace);write(folder/'prefix_state.json',payload);write(folder/'witness.json',witness)
            checkpoint=capture_live(prefix)
            for arm in plan['arms']:
                row={'fixture_id':p['fixture_id'],'original_group':p['original_group'],'arm':arm,'status':'error','prefix_json_exact':False,'prefix_graph_exact':False,'returns_errors_exact':False,'suffix_state_exact':False,'suffix_graph_exact':False}
                try:
                    restored=restore_arm(arm,type(prefix),payload,witness,checkpoint)
                    row.update(prefix_json_exact=digest(rn.dump(restored))==digest(payload),prefix_graph_exact=capture(restored)==witness)
                    write(folder/(arm+'_prefix_state.json'),rn.dump(restored));write(folder/(arm+'_prefix_graph.json'),capture(restored))
                    actual=continue_program(api,suite,restored,p);write(folder/(arm+'_continued_trace.json'),actual)
                    row.update(status='completed',**compare(actual,trace[p['cut']:]))
                except Exception as exc:row['reason']=type(exc).__name__+': '+str(exc)
                write(folder/(arm+'_receipt.json'),row);rows.append(row)
            release(checkpoint)
    write(out/'rows.json',rows)
    metrics=['prefix_json_exact','prefix_graph_exact','returns_errors_exact','suffix_state_exact','suffix_graph_exact']
    summary={'study_id':plan['study_id'],'programs':36,'rows':len(rows),'fixed_denominator_per_arm':36,'by_arm':{arm:{'completed':sum(r['status']=='completed' for r in rows if r['arm']==arm),**{k:sum(r[k] for r in rows if r['arm']==arm) for k in metrics},'failures':[r for r in rows if r['arm']==arm and (r['status']!='completed' or not r['suffix_state_exact'])]} for arm in plan['arms']},'api_calls':0,'after_exposure_diagnostic':True}
    write(out/'SUMMARY.json',summary);print(json.dumps({k:{m:v for m,v in val.items() if m!='failures'} for k,val in summary['by_arm'].items()},indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);run(p.parse_args().out)
