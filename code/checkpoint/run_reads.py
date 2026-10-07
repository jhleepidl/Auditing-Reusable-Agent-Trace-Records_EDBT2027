from pathlib import Path
import argparse,json
from common21 import *
from ablation_reader import restore_arm

def run(out):
    verify_freeze();plan=load(HERE/'READ_PLAN.json');out=new_out(out);rows=[]
    write(out/'START.json',{'utc':utc(),'freeze_sha256':sha(HERE/'FREEZE.json'),'study_id':plan['study_id']})
    with rn.no_network():
        api=rn.setup();suite=api.get_suite('v1','workspace')
        for p in plan['programs']:
            folder=out/'cases'/p['fixture_id'];prefix,post,trace=native_program(api,suite,p);payload=transported(prefix);witness=capture(prefix)
            write(folder/'native_trace.json',trace);write(folder/'prefix_state.json',payload);write(folder/'witness.json',witness)
            for arm in ['v4_control','full_witness']:
                row={'fixture_id':p['fixture_id'],'arm':arm,'status':'error','read_returns_errors_exact':False,'prefix_json_exact':False,'suffix_state_exact':False,'suffix_graph_exact':False}
                try:
                    restored=restore_arm(arm,type(prefix),payload,witness);actual=continue_program(api,suite,restored,p)
                    write(folder/(arm+'_continued_trace.json'),actual);cmp=compare(actual,trace[p['cut']:])
                    native_read=trace[-1];restored_read=actual[-1]
                    row.update(status='completed',prefix_json_exact=digest(rn.dump(restore_arm(arm,type(prefix),payload,witness)))==digest(payload),**cmp,read_returns_errors_exact=restored_read['result']==native_read['result'] and restored_read['error']==native_read['error'],native_read_sha256=digest(native_read['result']),restored_read_sha256=digest(restored_read['result']),native_read_error=native_read['error'],restored_read_error=restored_read['error'])
                except Exception as exc:row['reason']=type(exc).__name__+': '+str(exc)
                write(folder/(arm+'_receipt.json'),row);rows.append(row)
    write(out/'rows.json',rows);summary={'study_id':plan['study_id'],'programs':len(plan['programs']),'by_arm':{a:{'read_returns_errors_exact':sum(r['read_returns_errors_exact'] for r in rows if r['arm']==a),'suffix_state_exact':sum(r['suffix_state_exact'] for r in rows if r['arm']==a),'suffix_graph_exact':sum(r['suffix_graph_exact'] for r in rows if r['arm']==a),'errors':[r for r in rows if r['arm']==a and r['status']!='completed'],'read_mismatches':[r['fixture_id'] for r in rows if r['arm']==a and not r['read_returns_errors_exact']]} for a in ['v4_control','full_witness']},'api_calls':0,'after_exposure_diagnostic':True,'scope':'New actual get_sent_emails read appended to declared exposed programs; no semantic task grading'}
    write(out/'SUMMARY.json',summary);print(json.dumps(summary,indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);run(p.parse_args().out)
