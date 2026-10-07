"""Native source-world cases; confirmation dormant until root freeze token.

No competitive runtime/executor/candidate/provider artifact imports. Effects are
created through registered native tools, never manual post-state mutation.
"""
from __future__ import annotations
import argparse,copy,datetime,hashlib,importlib.metadata,importlib.util,json,os,sys
from collections import Counter
from pathlib import Path
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
from source_worlds import BASE,canonical_sha
from source_reference_dynamic import derive,evaluate,REFERENCE_FILE
R20=BASE/'baseline_r20' if (BASE/'baseline_r20').exists() else BASE.parent/'edbt_r20_followup'
os.environ.setdefault('EDBT_R20_ROOT',str(R20))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def module(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
native=module('r22_independent_native',BASE/'e2/reference_author/native_runtime.py')
def action(name,**args):return {'function':name,'args':args}
def goal_actions(packet,rules):
 rule=rules[0]
 if rule['kind']=='new_payment':return [action('send_money',recipient=rule['recipient'],amount=rule['amount'],subject='R22 source-scoped native fixture',date='2022-03-25')]
 if rule['kind']=='memberships':return [action('add_user_to_channel',user=x['user'],channel=x['channel']) for x in rule['members']]
 if rule['kind']=='new_messages':return [action('send_direct_message',recipient=x['recipient'],body=x['body']) for x in rule['messages']]
 return []
def read_actions(packet,rules):
 state=packet['initial_state']
 if 'bank_account' in state:return [action('get_most_recent_transactions',n=100)]
 if 'slack' in state:return [action('get_channels')]
 names=[x['name'] for x in state['car_rental']['company_list'] if x['city']=='Los Angeles']
 return [action('get_all_car_rental_companies_in_city',city='Los Angeles'),action('get_car_price_per_day',company_name=names)]
def query_output(rules,mode):
 rec=rules[0]['records'][0];entity=rec['entity'];facts=rec['facts']
 pairs=list(facts.items())
 if mode=='valid_order':pairs.reverse()
 def render(role=None,wrong_value=False,wrong_entity=False,unsupported=False):
  en='Unselected source entity' if wrong_entity else entity
  fields=[]
  for i,(prop,value) in enumerate(pairs):
   if wrong_value and i==0:value=float(value)+1
   alias={'amount':'paid','rating':'score','total':'cost'}[prop]
   qualifier=' widgets' if unsupported else ' points' if prop=='rating' else ' EUR over 7 days' if prop=='total' else ''
   fields.append(f'{alias} equals {value}{qualifier}')
  return (f'[{role}] ' if role else '')+en+' — '+', '.join(fields)
 if mode=='wrong_value':return render(wrong_value=True)
 if mode=='wrong_entity':return render(wrong_entity=True)
 if mode=='wrong_role':return render()+'\n'+render(role='london_car_company' if 'rating' in facts else 'new_year_gift_spending')
 if mode=='unavailable_output':return None
 if mode=='unsupported_output':return render(unsupported=True)
 return render()
def program(packet,scope,rules,mode):
 goals=goal_actions(packet,rules);reads=read_actions(packet,rules);prep=[];acts=copy.deepcopy(goals);mask=None
 if rules[0]['kind']=='query_fact':
  return [],reads if mode!='valid_order' else list(reversed(reads)),query_output(rules,mode),('output_omitted' if mode=='missing_output_key' else None)
 if mode=='valid_order':acts=list(reversed(goals))+reads
 elif mode=='wrong_value':
  acts=copy.deepcopy(goals)
  if 'amount' in acts[0]['args']:acts[0]['args']['amount']+=1
  elif 'body' in acts[0]['args']:acts[0]['args']['body']+=' (wrong requested body)'
  else:acts=acts[1:]
 elif mode=='wrong_entity':
  acts=copy.deepcopy(goals)
  if 'recipient' in acts[0]['args']:
   if 'slack' in packet['initial_state']:
    acts[0]['args']['recipient']=next(u for u in sorted(packet['initial_state']['slack']['users']) if u!=acts[0]['args']['recipient'])
   else:
    acts[0]['args']['recipient']=next(t['recipient'] for t in packet['initial_state']['bank_account']['transactions'] if t['recipient']!=acts[0]['args']['recipient'])
  else:
   target=acts[0]['args']['channel'];wrong=next(ch for ch in packet['initial_state']['slack']['channels'] if ch!=target)
   for a in acts:a['args']['channel']=wrong
 elif mode=='wrong_identity':
  if rules[0]['kind']=='memberships':acts=goals+[action('remove_user_from_slack',user=rules[0]['members'][0]['user'])]
  else:prep=goals;acts=reads
 elif mode in ['unavailable_pre','unavailable_post','unavailable_both','missing_post_key']:mask=mode
 return prep,acts,None,mask

def verify_environment():
 envfile=R20/'work/native/EDBT_R18_CPU_RESULTS/EDBT_R18_NO_HUMAN_KIT/vendor/r11/ENVIRONMENT.json'
 pins=json.loads(envfile.read_text())['dependency_pins'];assert len(pins)==75 and sys.version.split()[0]=='3.11.7'
 for package,expected in pins.items():assert importlib.metadata.version(package)==expected,('native dependency pin',package)
 return {'python':sys.version.split()[0],'pins_verified':len(pins),'dependency_authority_sha256':sha(envfile)}

def realize(worlds,out):
 if out.exists():raise RuntimeError('Refuse overwrite: '+str(out))
 out.mkdir(parents=True);(out/'cases').mkdir();environment=verify_environment()
 packets=json.loads((HERE/'public_packets.json').read_text());cases=[];refs=[];goals=[];errors=[]
 for item in packets:
  if item['world_id'] not in worlds:continue
  packet,scope=item['packet'],item['scope'];rule,proof=derive(packet,scope);rules=rule['rules'];kind=rules[0]['kind']
  goals.append({'task_key':item['task_key'],'world_id':item['world_id'],'source_packet_sha256':scope['source_packet_sha256'],'scope_sha256':scope['scope_sha256'],'source_rules':rules,'source_derivation':proof})
  if kind=='query_fact':modes=['valid','valid_order','wrong_value','wrong_entity','wrong_role','unavailable_output','missing_output_key','unsupported_output']
  elif kind=='memberships':modes=['valid','valid_order','wrong_value','wrong_entity','wrong_identity','unavailable_post','missing_post_key','unavailable_both']
  else:modes=['valid','valid_order','wrong_value','wrong_entity','wrong_identity','unavailable_pre','unavailable_post','unavailable_both']
  for index,mode in enumerate(modes):
   identifier=item['task_key'].replace('/','__')+f'__w{item["world_id"]}__c{index+1:02d}_{mode}'
   prep,acts,output,mask=program(packet,scope,rules,mode);suite=item['task_key'].split('/')[0]
   env,rt=native.initialize(suite,copy.deepcopy(packet['initial_state']));prep_receipts=native.execute(env,rt,prep)
   pre=native.plain(env)
   prepared_packet=copy.deepcopy(packet);prepared_packet['initial_state']=pre
   prepared_rule,prepared_proof=derive(prepared_packet,scope)
   goal_preserved=prepared_rule['rules']==rules
   if not goal_preserved:raise RuntimeError('Preparation changed independent source goal: '+identifier)
   action_receipts=native.execute(env,rt,acts);post=native.plain(env)
   full={'pre_state':pre,'post_state':post,'output':output};observed=copy.deepcopy(full)
   if mask=='output_omitted':observed.pop('output')
   elif mask=='unavailable_pre':observed['pre_state']=None
   elif mask=='unavailable_post':observed['post_state']=None
   elif mask=='missing_post_key':observed.pop('post_state')
   elif mask=='unavailable_both':observed['pre_state']=None;observed['post_state']=None
   ref=evaluate(packet,scope,observed);expected='pass' if index<2 else 'fail' if index<5 else 'unknown'
   expected_match=ref['reference_status']==expected
   native_errors=[r for r in prep_receipts+action_receipts if r['error'] is not None]
   errors.extend({'case_id':identifier,'receipt':r} for r in native_errors)
   case={'case_id':identifier,'task_key':item['task_key'],'world_id':item['world_id'],'scope_id':scope['scope_id'],'source_packet_sha256':scope['source_packet_sha256'],'scope_sha256':scope['scope_sha256'],'mechanism':mode,'observed':observed,'native_trace_path':f'cases/{identifier}.json','design_status':expected}
   receipt={'case_id':identifier,'source_packet_sha256':scope['source_packet_sha256'],'source_scope_sha256':scope['scope_sha256'],'preparation_actions':prep,'case_actions':acts,'preparation_receipts':prep_receipts,'action_receipts':action_receipts,'full_observed':full,'observed':observed,'reference':ref,'planned_reference_status':expected,'planned_status_match':expected_match,'native_errors':len(native_errors),'preparation_goal_preserved':goal_preserved,'prepared_source_derivation':prepared_proof}
   (out/'cases'/f'{identifier}.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
   cases.append(case);refs.append({'case_id':identifier,**ref,'planned_status_match':expected_match})
 for filename,rows in [('cases.jsonl',cases),('private_reference.jsonl',refs),('private_source_rules.jsonl',goals)]:
  (out/filename).write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
 mismatches=[r for r in refs if not r['planned_status_match']]
 report={'status':'PASS' if not mismatches and not errors else 'FAILED_DEVELOPMENT_OR_CONFIRMATION_REALIZATION','utc':now(),'worlds':worlds,'task_worlds':len(goals),'cases':len(cases),'source_reference_counts':dict(Counter(r['reference_status'] for r in refs)),'planned_status_mismatches':mismatches,'native_errors':len(errors),'environment':environment,'API_calls':0,'candidate_or_model_outputs_read':0,'independence':'Source targets/formulas are independent of the competitive DAG/executor; only immutable independent R21 observation checks are reused. Inherited resolved rule files are not read by the AST loader.','implementation_hashes':{p.name:sha(p) for p in [HERE/'PLAN.json',HERE/'source_worlds.py',HERE/'source_reference_dynamic.py',HERE/'realize_cases.py',HERE/'public_packets.json',REFERENCE_FILE,BASE/'e2/reference_author/native_runtime.py']}}
 (out/'REPORT.json').write_text(json.dumps(report,indent=2)+'\n')
 if mismatches or errors:raise RuntimeError('Retained realization failure; inspect REPORT.json')
 print(json.dumps(report,indent=2))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--stage',choices=['development','confirmation'],required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--freeze-token');a=p.parse_args()
 if a.stage=='confirmation':
  if not a.freeze_token:raise RuntimeError('Confirmation requires explicit root method/protocol freeze token')
  gate=ROOT/'SOURCE_CONFIRMATION_AUTHORIZATION.json'
  if not gate.exists():raise RuntimeError('Root confirmation authorization absent')
  authority=json.loads(gate.read_text());assert a.freeze_token==authority['freeze_token'] and authority['source_plan_sha256']==sha(HERE/'PLAN.json') and authority['public_packets_sha256']==sha(HERE/'public_packets.json')
  worlds=list(range(1,6))
 else:worlds=[0]
 realize(worlds,a.out)
