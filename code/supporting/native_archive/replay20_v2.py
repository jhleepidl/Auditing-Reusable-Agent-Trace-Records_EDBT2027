#!/usr/bin/env python3
"""Replay recorded actions, including only byte-matching recorded tool errors."""
from pathlib import Path
import argparse,sys,json,datetime
R=Path(__file__).resolve().parent;KIT=R/'EDBT_R18_NO_HUMAN_KIT';sys.path.insert(0,str(KIT/'tools'))
import run_native as old
from common import load,write,sha,utc,text_output
S=R/'studies/replay20_v2'
def assert_step(call,error,expected):
 assert old.dump(call)==expected['tool_call'],'recorded action binding mismatch'
 assert error==expected.get('error'),'tool error differs from recorded trace'
def freeze():
 old.check_freeze();old.check_followup();assert not (S/'protocol.json').exists()
 inputs=[p for p in (KIT/'inputs/workspace').rglob('*.json')]
 p={'study':'R18_REPLAY20_V2','frozen_utc':utc(),'parent_failure':'Original execute() stops on any tool error, but source traces for user_task_2 and user_task_17 record the same search errors followed by recovery actions. Parent run is retained unchanged.','change':'Replay all recorded actions only when each call and error exactly matches its source trace. Compare formatted success outputs, all pre/post states and endpoints. Unexpected or missing expected errors remain replay failures. No native tool/evaluator code or input action is modified.','scope':'Correction only to replay20, not sweep/state-repair/query components. All 20 rerun from fresh native states; no pooling with partial parent replay.','files':{'replay20_v2.py':sha(Path(__file__)),'test_replay20_v2.py':sha(R/'test_replay20_v2.py'),**{p.relative_to(R).as_posix():sha(p) for p in inputs}},'parent_source_sha256':sha(KIT/'tools/run_native.py'),'api_calls':0,'human_annotations':0}
 write(S/'protocol.json',p);(S/'protocol.sha256').write_text(sha(S/'protocol.json')+'  protocol.json\n');print('FROZEN',sha(S/'protocol.json'))
def run(out):
 old.check_freeze();old.check_followup();p=load(S/'protocol.json');assert sha(S/'protocol.json')==(S/'protocol.sha256').read_text().split()[0]
 for n,h in p['files'].items():assert sha(R/n)==h,n
 assert sha(KIT/'tools/run_native.py')==p['parent_source_sha256'];out.mkdir(parents=True,exist_ok=False);rows=[]
 with old.no_network():
  api=old.setup();from agentdojo.agent_pipeline.tool_execution import tool_result_to_str
  for i in range(20):
   tid=f'user_task_{i}';d=KIT/'inputs/workspace'/tid;folder=out/tid;trace=[]
   try:
    suite,task,env,pre=old.init(api,'v1','workspace',tid);src=load(d/'evaluator_input.json');messages=load(d/'trace.json');expected=[m for m in messages if m['role']=='tool'];calls=[api.Call(**c) for c in src['actions']];assert len(calls)==len(expected)
    rt=api.Runtime(suite.tools)
    with old.clock():
     for c,m in zip(calls,expected):
      result,error=rt.run_function(env,c.function,c.args)
      entry={'call':old.dump(c),'result':old.dump(result),'error':error,'state':old.dump(env)};trace.append(entry)
      assert_step(c,error,m)
      text='' if error is not None else tool_result_to_str(result)
      expected_text=''.join(x.get('content',x.get('text','')) for x in m['content'] if x['type']=='text')
      entry['formatted_result_matches']=text==expected_text;assert text==expected_text,'formatted tool result mismatch'
    write(folder/'trace.json',trace);write(folder/'pre_state.json',old.dump(pre));write(folder/'post_state.json',old.dump(env))
    initial=old.dump(pre)==load(d/'pre_state.json');final=old.dump(env)==load(d/'post_state.json');output=text_output(src)
    native=old.grade(api,suite,task,pre,env,output,calls);alt=api.get_suite('v1.1.1','workspace');secondary=old.grade(api,alt,alt.get_user_task_by_id(tid),pre,env,output,calls)
    row={'task_id':tid,'initial_json_equal':initial,'final_json_equal':final,'native_v1':native,'recorded_v1':load(d/'result.json')['utility'],'native_v1_1_1_same_trace':secondary,'recorded_errors_reproduced':sum(x['error'] is not None for x in trace),'all_actions_errors_and_formatted_results_match':True,'tool_calls':len(calls),'model_called':False}
    assert initial and final and native==row['recorded_v1'],'state or endpoint mismatch'
   except Exception as e:
    write(folder/'partial_trace.json',trace);row={'task_id':tid,'status':'ERROR','error':type(e).__name__+': '+str(e)}
   rows.append(row);write(folder/'result.json',row)
 write(out/'rows.json',rows);summary={'n':20,'completed':sum('error' not in r for r in rows),'exact_final_states':sum(r.get('final_json_equal',False) for r in rows),'exact_initial_states':sum(r.get('initial_json_equal',False) for r in rows),'native_v1_pass':sum(r.get('native_v1',False) for r in rows),'native_v1_1_1_pass':sum(r.get('native_v1_1_1_same_trace',False) for r in rows),'recorded_tool_errors_reproduced':sum(r.get('recorded_errors_reproduced',0) for r in rows),'tool_calls':sum(r.get('tool_calls',0) for r in rows),'api_calls':0,'human_annotations':0,'scope':'All recorded calls, errors, successful tool response text, native states and primary endpoints replayed. Native endpoints do not certify full semantics.'};write(out/'summary.json',summary);print(json.dumps(summary,indent=2));assert summary['completed']==20
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('command',choices=['freeze','run']);p.add_argument('--out',type=Path);a=p.parse_args()
 if a.command=='freeze':freeze()
 else:run((a.out or S/'results_v1').resolve())
