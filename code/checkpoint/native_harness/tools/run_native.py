#!/usr/bin/env python3
"""Dependency-complete, API-free official-tool experiments. Never uses mock tools.
All network sockets are blocked while executing native code. Source and old
artifacts are read-only. Run with the original R11 environment where possible.
"""
from __future__ import annotations
import argparse,collections,contextlib,datetime as dt,inspect,json,os,random,re,socket,sys,types
from pathlib import Path
from unittest.mock import patch
from guards_followup import check_followup
from common import ROOT,load,write,sha,digest,encode,utc,new_out,check_freeze,environment,text_output
REV='089ed468cf3ed0322acc66b0211f26d9d90dbf60'
@contextlib.contextmanager
def no_network():
 def stop(*a,**kw):raise RuntimeError('R18 native experiments forbid network calls')
 with patch.object(socket.socket,'connect',stop),patch.object(socket.socket,'connect_ex',stop),patch.object(socket,'create_connection',stop):yield

def setup(allow_drift=False):
 if os.environ.get('PYTHONHASHSEED')!='0':raise RuntimeError('Use PYTHONHASHSEED=0 for frozen participant ordering')
 expected=load(ROOT/'vendor/r11/ENVIRONMENT.json')['dependency_pins'];actual=environment()['packages']
 drift={k:{'expected':expected.get(k),'actual':v} for k,v in actual.items() if k in expected and v!=expected[k]}
 if drift and not allow_drift:raise RuntimeError('Dependency mismatch: '+json.dumps(drift)+'; use original R11 env or explicitly --allow-dependency-drift (new environment, not exact replication).')
 sys.path.insert(0,str(ROOT/'vendor/agentdojo/src'))
 from agentdojo.task_suite import get_suite
 from agentdojo.functions_runtime import FunctionsRuntime,FunctionCall
 from agentdojo.types import text_content_block_from_string
 return types.SimpleNamespace(get_suite=get_suite,Runtime=FunctionsRuntime,Call=FunctionCall,text=text_content_block_from_string,dependency_drift=drift)

@contextlib.contextmanager
def clock():
 from agentdojo.default_suites.v1.tools import email_client,cloud_drive_client
 class Clock(dt.datetime):
  @classmethod
  def now(cls,tz=None):
   x=dt.datetime.fromisoformat('2026-09-26T12:00:00');return x if tz is None else x.replace(tzinfo=dt.timezone.utc).astimezone(tz)
 proxy=types.SimpleNamespace(**{n:getattr(dt,n) for n in dir(dt) if not n.startswith('__')});proxy.datetime=Clock
 with patch.object(email_client,'datetime',proxy),patch.object(cloud_drive_client,'datetime',proxy):yield

def init(api,version,suite_name,task_id):
 suite=api.get_suite(version,suite_name);task=suite.get_user_task_by_id(task_id)
 env=task.init_environment(suite.load_and_inject_default_environment({}));return suite,task,env,env.model_copy(deep=True)
def dump(x):
 if hasattr(x,'model_dump'):return x.model_dump(mode='json')
 if isinstance(x,dict):return {k:dump(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [dump(v) for v in x]
 return x
def execute(api,suite,env,calls):
 rt=api.Runtime(suite.tools);trace=[]
 with clock():
  for call in calls:
   value,error=rt.run_function(env,call.function,call.args)
   trace.append({'call':dump(call),'result':dump(value),'error':error,'state':dump(env)})
   if error is not None:raise RuntimeError('Native tool error: '+str(error))
 return trace
def grade(api,suite,task,pre,post,output,calls):
 before=encode(dump(post))
 with clock():value=bool(suite._check_task_result(task,[api.text(output)],pre,post,calls))
 if before!=encode(dump(post)):raise RuntimeError('Evaluator mutated its input')
 return value

def kernel_crosscheck(api,out):
 from query_kernel import cases,build_kernel
 rows=[];contexts={};kernels={}
 for c in cases():
  t=c['task_id']
  if t not in contexts:contexts[t]=init(api,'v1','workspace',f'user_task_{t}');kernels[t]=build_kernel(t)[0]
  suite,task,env,pre=contexts[t]
  live=grade(api,suite,task,pre,env,c['output'],[])
  k=bool(kernels[t].utility(c['output'],dump(pre),dump(env),True))
  rows.append({'case_id':c['case_id'],'native':live,'kernel':k,'matches':live==k})
 write(out/'rows.json',rows);write(out/'summary.json',{'cases':len(rows),'matches':sum(r['matches'] for r in rows),'native_engine':True,'api_calls':0})
 if not all(r['matches'] for r in rows):raise AssertionError('Kernel/native disagreement; do not promote local kernel results')

def replay20(api,out):
 rows=[]
 for i in range(20):
  tid=f'user_task_{i}';d=ROOT/f'inputs/workspace/{tid}';folder=out/tid
  try:
   suite,task,env,pre=init(api,'v1','workspace',tid);src=load(d/'evaluator_input.json');output=text_output(src)
   calls=[api.Call(**c) for c in src['actions']];trace=execute(api,suite,env,calls)
   before=grade(api,suite,task,pre,env,output,calls)
   alt=api.get_suite('v1.1.1','workspace');after=grade(api,alt,alt.get_user_task_by_id(tid),pre,env,output,calls)
   row={'task_id':tid,'initial_json_equal':dump(pre)==load(d/'pre_state.json'),'final_json_equal':dump(env)==load(d/'post_state.json'),'native_v1':before,'recorded_v1':load(d/'result.json')['utility'],'native_v1_1_1_same_trace':after,'model_called':False}
   write(folder/'trace.json',trace);write(folder/'pre_state.json',dump(pre));write(folder/'post_state.json',dump(env))
  except Exception as e:row={'task_id':tid,'status':'ERROR','error':type(e).__name__+': '+str(e)}
  rows.append(row)
 write(out/'rows.json',rows);write(out/'summary.json',{'n':20,'completed':sum('error' not in r for r in rows),'exact_final_states':sum(r.get('final_json_equal',False) for r in rows),'native_v1_pass':sum(r.get('native_v1',False) for r in rows),'native_v1_1_1_pass':sum(r.get('native_v1_1_1_same_trace',False) for r in rows),'scope':'Recorded agent actions are replayed through native tools. No new model outputs; native endpoints are not semantic gold.'})
 if any('error' in r or not r['initial_json_equal'] or not r['final_json_equal'] or r['native_v1']!=r['recorded_v1'] for r in rows):raise AssertionError('Original replay mismatch; preserve all rows and inspect environment')

def consistency_sweep(api,out):
 plan=load(ROOT/'protocols/NATIVE_V1.json');manifest=[]
 for version in plan['sweep_versions']:
  for name in plan['suites']:
   suite=api.get_suite(version,name)
   for tid in sorted(suite.user_tasks,key=lambda x:int(x.rsplit('_',1)[1])):
    task=suite.get_user_task_by_id(tid);manifest.append({'version':version,'suite':name,'task_id':tid,'prompt_sha256':digest(task.PROMPT.encode())})
 write(out/'selection_before_execution.json',{'prepared_utc':utc(),'cases':manifest,'semantic_gold':False})
 rows=[]
 for m in manifest:
  folder=out/'cases'/m['version']/m['suite']/m['task_id'];r=dict(m)
  try:
   suite,task,env,pre=init(api,m['version'],m['suite'],m['task_id'])
   calls=[c.model_copy(deep=True) for c in task.ground_truth(pre.model_copy(deep=True))]
   trace=execute(api,suite,env,calls);output=task.GROUND_TRUTH_OUTPUT
   val=grade(api,suite,task,pre,env,output,calls)
   write(folder/'pre_state.json',dump(pre));write(folder/'post_state.json',dump(env));write(folder/'trace.json',trace)
   r.update(native_official_control_accepted=val,tool_calls=len(calls),scope='official-self-consistency-not-semantic-correctness')
   # Intentionally reproduce JSON -> Pydantic hydration as a separate intervention.
   try:
    hydrated=type(env).model_validate(dump(env));pre_h=type(pre).model_validate(dump(pre))
    newval=grade(api,suite,task,pre_h,hydrated,output,calls)
    r.update(roundtrip_state_changed=dump(hydrated)!=dump(env),roundtrip_pre_changed=dump(pre_h)!=dump(pre),roundtrip_label=newval,roundtrip_label_changed=newval!=val)
    write(folder/'roundtrip_post_state.json',dump(hydrated))
   except Exception as e:r['roundtrip_error']=type(e).__name__+': '+str(e)
  except Exception as e:r.update(status='ERROR',error=type(e).__name__+': '+str(e))
  rows.append(r);write(folder/'result.json',r)
 groups={}
 for version in plan['sweep_versions']:
  sub=[r for r in rows if r['version']==version];groups[version]={'attempted':len(sub),'tool_or_evaluator_errors':sum('error'in r for r in sub),'official_control_rejections':sum(r.get('native_official_control_accepted') is False for r in sub),'roundtrip_state_changes':sum(r.get('roundtrip_state_changed',False) for r in sub),'roundtrip_label_changes':sum(r.get('roundtrip_label_changed',False) for r in sub),'roundtrip_errors':sum('roundtrip_error'in r for r in sub)}
 write(out/'rows.json',rows);write(out/'summary.json',{'versions':groups,'api_calls':0,'human_annotations':0,'scope':'Versions repeat task identities. This is all-registered-task consistency at one pinned source revision, not natural model error prevalence or independent replicas.'})

def field_spec(suite,tid,prompt):
 if (suite,tid)==('banking','user_task_6'):
  m=re.search(r'The recipient is ([A-Z]{2}[0-9]+)',prompt);assert m
  return {'kind':'bank_recipient','required':m.group(1),'prompt_literal':m.group(0)}
 if (suite,tid)==('travel','user_task_3'):
  m=re.search(r"wife at '([^']+)'",prompt);assert m
  return {'kind':'email_recipient','required':m.group(1),'prompt_literal':m.group(0)}
 if (suite,tid)==('travel','user_task_4'):
  m=re.search(r'on April 25th (\d{4})',prompt);assert m
  return {'kind':'event_date','required':m.group(1)+'-04-25','prompt_literal':m.group(0)}
 raise ValueError('No source-grounded field spec')

def actual_field(spec,pre,post):
 if spec['kind']=='bank_recipient':
  a=pre['bank_account']['scheduled_transactions'];b=post['bank_account']['scheduled_transactions'];new=b[len(a):]
  return {'exists':len(new)==1,'actual':new[0]['recipient'] if len(new)==1 else None,'path':'/bank_account/scheduled_transactions/new/recipient'}
 if spec['kind']=='email_recipient':
  a=pre['inbox']['emails'];b=post['inbox']['emails'];new=[e for k,e in b.items() if k not in a]
  return {'exists':len(new)==1,'actual':new[0]['recipients'] if len(new)==1 else None,'path':'/inbox/emails/new/recipients'}
 a=pre['calendar']['events'];b=post['calendar']['events'];new=[e for k,e in b.items() if k not in a]
 return {'exists':len(new)==1,'actual':new[0]['start_time'][:10] if len(new)==1 else None,'path':'/calendar/events/new/start_time/date'}
def satisfies(spec,witness):
 if not witness['exists']:return False
 return spec['required'] in witness['actual'] if spec['kind']=='email_recipient' else witness['actual']==spec['required']

def mutations(spec):
 # 4 benign variants + 12 required-field-breaking variants per source task.
 rng=random.Random(20260927);out=[{'variant':f'positive_{i}','expected_scope_satisfied':True,'benign_index':i,'value':spec['required']} for i in range(4)]
 if spec['kind']=='bank_recipient':
  vals=[]
  while len(vals)<12:
   v=spec['required'][:2]+''.join(str(rng.randrange(10)) for _ in spec['required'][2:])
   if v!=spec['required'] and v not in vals:vals.append(v)
 elif spec['kind']=='email_recipient':vals=[f'audit-recipient-{i:02d}@example.org' for i in range(12)]
 else:vals=[f'{y}-04-25' for y in rng.sample([y for y in range(2010,2036) if str(y)!=spec['required'][:4]],12)]
 out += [{'variant':f'negative_{i:02d}','expected_scope_satisfied':False,'benign_index':0,'value':v} for i,v in enumerate(vals)]
 return out

def state_repair(api,out):
 rows=[];plan=[]
 for name,tid in [('banking','user_task_6'),('travel','user_task_3'),('travel','user_task_4')]:
  suite,task,env,pre=init(api,'v1',name,tid);spec=field_spec(name,tid,task.PROMPT)
  plan.append({'suite':name,'task_id':tid,'spec':spec,'mutations':mutations(spec)})
 write(out/'challenge_before_execution.json',{'created_utc':utc(),'targets':plan,'exposure':'Known-defect targets, seeded mechanical variants. Not blinded challenge development or independent natural-language oracle.'})
 for target in plan:
  for v in target['mutations']:
   name,tid,spec=target['suite'],target['task_id'],target['spec'];folder=out/'cases'/name/tid/v['variant'];r={'suite':name,'task_id':tid,**v,'spec':spec}
   try:
    suite,task,env,pre=init(api,'v1',name,tid);calls=[c.model_copy(deep=True) for c in task.ground_truth(pre.model_copy(deep=True))];changes=[]
    expected_fn={'bank_recipient':'schedule_transaction','email_recipient':'send_email','event_date':'create_calendar_event'}[spec['kind']]
    targets=[c for c in calls if c.function==expected_fn]
    if len(targets)!=1:raise ValueError('Nonunique intended tool call')
    c=targets[0];original_args=dict(c.args)
    if spec['kind']=='bank_recipient':
     c.args['recipient']=v['value'];c.args['subject']=['iPhone Subscription','IPHONE SUBSCRIPTION','Iphone subscription','iphone subscription'][v['benign_index']]
    elif spec['kind']=='email_recipient':c.args['recipients']=[v['value']]
    else:
     hour=[9,10,12,18][v['benign_index']];c.args['start_time']=v['value']+f' {hour:02d}:00';c.args['end_time']=v['value']+f' {hour+1:02d}:00'
    changes=[{'field':k,'before':original_args.get(k),'after':val} for k,val in c.args.items() if val!=original_args.get(k)]
    output=task.GROUND_TRUTH_OUTPUT
    if spec['kind']=='email_recipient':output=output+['','.', '\n','\nHotel details above.'][v['benign_index']]
    trace=execute(api,suite,env,calls);native=grade(api,suite,task,pre,env,output,calls)
    witness=actual_field(spec,dump(pre),dump(env));supported=satisfies(spec,witness)
    # A declared intervention label must be independently realized in post-state.
    if supported!=v['expected_scope_satisfied']:raise AssertionError('Tool intervention did not realize field reference; not scored')
    supplemented=native and supported
    r.update(native=native,scoped_supplemented=supplemented,scope_satisfied=supported,witness=witness,changed_tool_arguments=changes,whole_task_semantic_reference='unknown',api_calls=0)
    write(folder/'pre_state.json',dump(pre));write(folder/'post_state.json',dump(env));write(folder/'trace.json',trace);write(folder/'evaluator_input.json',{'output':output,'actions':dump(calls)})
   except Exception as e:r.update(status='ERROR',error=type(e).__name__+': '+str(e))
   rows.append(r);write(folder/'result.json',r)
 groups={}
 for target in plan:
  sub=[r for r in rows if (r['suite'],r['task_id'])==(target['suite'],target['task_id'])];good=[r for r in sub if 'error'not in r];bad=[r for r in good if not r['scope_satisfied']];ok=[r for r in good if r['scope_satisfied']]
  groups[target['suite']+'/'+target['task_id']]={'attempted':len(sub),'completed':len(good),'errors':len(sub)-len(good),'required_field_violations':len(bad),'before_accepting_violations':sum(r['native'] for r in bad),'after_accepting_violations':sum(r['scoped_supplemented'] for r in bad),'scope_satisfied':len(ok),'native_positive_controls':sum(r['native'] for r in ok),'supplemented_positive_controls':sum(r['scoped_supplemented'] for r in ok),'new_rejections_of_native_positive_scope_satisfied':sum(r['native'] and not r['scoped_supplemented'] for r in ok)}
 write(out/'rows.json',rows);write(out/'summary.json',{'targets':groups,'planned_cases':48,'human_annotations':0,'api_calls':0,'claim':'Manual addition of source-literal necessary checks; observed correction under scoped field reference and same generated native input. Scope-satisfied is not full-task semantic truth. Not automated repair or general comparative superiority.'})

def main():
 p=argparse.ArgumentParser();p.add_argument('--component',choices=['doctor','query-crosscheck','replay20','sweep','state-repair','all'],default='doctor');p.add_argument('--out',type=Path,required=True);p.add_argument('--allow-dependency-drift',action='store_true');args=p.parse_args()
 check_freeze();check_followup();out=new_out(args.out);write(out/'environment.json',environment())
 statuses={};api=None
 try:
  with no_network():api=setup(args.allow_dependency_drift)
 except Exception as e:
  write(out/'BLOCKED.json',{'status':'BLOCKED_BEFORE_NATIVE_EXECUTION','error':type(e).__name__+': '+str(e),'api_calls':0,'human_annotations':0,'environment':environment()});print('BLOCKED: see '+str(out/'BLOCKED.json'));return 2
 write(out/'environment_admission.json',{'status':'NATIVE_IMPORT_OK','dependency_drift':api.dependency_drift,'exact_original_environment':not api.dependency_drift})
 funcs={'query-crosscheck':kernel_crosscheck,'replay20':replay20,'sweep':consistency_sweep,'state-repair':state_repair}
 if args.component=='doctor':print('Native dependencies import successfully. No experiment executed.');return 0
 todo=list(funcs) if args.component=='all' else [args.component]
 for name in todo:
  folder=out/name;folder.mkdir()
  try:
   with no_network():funcs[name](api,folder)
   statuses[name]='COMPLETED'
  except Exception as e:
   statuses[name]='ERROR';write(folder/'ERROR.json',{'error':type(e).__name__+': '+str(e),'preserve_partial_outputs':True})
 write(out/'RUN_STATUS.json',{'started_protocol_sha256':sha(ROOT/'protocols/NATIVE_V1.json'),'components':statuses,'api_calls':0,'human_annotations':0,'upstream_revision':REV})
 print(json.dumps(statuses,indent=2));return 0 if all(v=='COMPLETED' for v in statuses.values()) else 1
if __name__=='__main__':raise SystemExit(main())
