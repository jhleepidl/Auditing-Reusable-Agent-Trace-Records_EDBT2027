#!/usr/bin/env python3
from pathlib import Path
import json,hashlib,subprocess,sys,importlib.metadata
R=Path(__file__).resolve().parent;KIT=R/'EDBT_R18_NO_HUMAN_KIT';sys.path.insert(0,str(KIT/'tools'))
from common import load,sha

def main():
 subprocess.run([sys.executable,str(KIT/'tools/verify_package.py')],check=True,stdout=subprocess.DEVNULL)
 env=load(R/'validation/full_environment_comparison.json');assert env['expected_pins']==75 and not env['missing'] and not env['different']
 for name,version in load(KIT/'vendor/r11/ENVIRONMENT.json')['dependency_pins'].items():assert importlib.metadata.version(name)==version,name
 n=KIT/'runs/r18_cpu_01/native';q=load(n/'query-crosscheck/rows.json');assert len(q)==3044 and all(x['native']==x['kernel'] and x['matches'] for x in q)
 qs=load(KIT/'runs/r18_cpu_01/local/query_summary.json')
 for task,count,fa in [('2',1488,0),('5',1440,2),('10',100,18)]:
  g=qs['by_task'][task]['finite_canonical_domain'];assert g['n']==count and g['native_kernel']['false_accept']==fa and g['patched_scoped']['false_accept']==0 and g['patched_scoped']['true_positive_retained']==1
 parent=load(n/'replay20/rows.json');assert [x['task_id'] for x in parent if 'error'in x]==['user_task_2','user_task_17'];assert load(n/'RUN_STATUS.json')['components']['replay20']=='ERROR'
 protocol=load(R/'studies/replay20_v2/protocol.json');assert sha(R/'studies/replay20_v2/protocol.json')==(R/'studies/replay20_v2/protocol.sha256').read_text().split()[0]
 for p,h in protocol['files'].items():assert sha(R/p)==h,p
 v=R/'studies/replay20_v2/results_v1';rows=load(v/'rows.json');assert len(rows)==20 and all('error' not in r and r['initial_json_equal'] and r['final_json_equal'] and r['native_v1']==r['recorded_v1'] for r in rows)
 errors=0;calls=0
 for r in rows:
  p=KIT/'inputs/workspace'/r['task_id'];expected=[m for m in load(p/'trace.json') if m['role']=='tool'];trace=load(v/r['task_id']/'trace.json');assert len(trace)==len(expected)
  assert load(v/r['task_id']/'pre_state.json')==load(p/'pre_state.json') and load(v/r['task_id']/'post_state.json')==load(p/'post_state.json')
  for t,m in zip(trace,expected):assert t['call']==m['tool_call'] and t['error']==m.get('error') and t['formatted_result_matches'];errors+=int(t['error'] is not None);calls+=1
 assert (errors,calls)==(2,44)
 assert sum(r['native_v1'] for r in rows)==16 and sum(r['native_v1_1_1_same_trace'] for r in rows)==18
 # Recompute independent source-field / side-effect / hydration audit and compare bytes.
 files=[R/'R18_EXECUTION_RESULTS.json',R/'RUN_AUTHORITY.json',*sorted((R/'analysis').glob('*'))];before={p:p.read_bytes() for p in files}
 subprocess.run([sys.executable,str(R/'analyze_native.py')],check=True,stdout=subprocess.DEVNULL)
 for p,data in before.items():assert p.read_bytes()==data,p
 s=load(R/'R18_EXECUTION_RESULTS.json');assert s['sweep_aggregate']=={'task_version_pairs':291,'unique_suite_task_pairs':97,'official_control_rejections':1,'changed_post_states':72,'changed_pre_states':0,'changed_labels':71,'tool_or_evaluator_errors':0}
 x=s['state_repair'];assert (x['cases'],x['required_field_violations'],x['native_accepting_violations'],x['supplement_accepting_violations'],x['native_positive_controls_retained'],x['negative_isolation_checks'],x['unique_control_post_states'])==(48,36,36,0,12,36,9)
 if (R/'FILE_SHA256SUMS_R18_RESULTS').exists():
  for line in (R/'FILE_SHA256SUMS_R18_RESULTS').read_text().splitlines():h,p=line.split(None,1);assert sha(R/p)==h,p
 print('PASS: original kit, all 75 dependency pins, 3044 query pairs, corrected 20-trace replay, 291 sweep cases, 48 native interventions, 36 isolation checks and all report aggregates')
if __name__=='__main__':main()
