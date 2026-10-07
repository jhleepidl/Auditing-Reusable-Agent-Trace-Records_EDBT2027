"""Public source-only R22 world construction; no model/reference/executor imports.

World zero is the original source packet, byte-equivalent after JSON parsing.
New worlds mutate synthetic source facts while preserving request and scope shape.
"""
from __future__ import annotations
import copy, hashlib, json, os
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
BASE=Path(os.environ.get('EDBT_R21_ROOT', ROOT/'baseline_r21' if (ROOT/'baseline_r21').exists() else ROOT.parent/'edbt_r21_followup')).resolve()
TASKS=['banking/user_task_1','banking/user_task_4','banking/user_task_5','banking/user_task_11','slack/user_task_10','slack/user_task_13','slack/user_task_14','travel/user_task_14']
def canonical_sha(x):return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def load_sources():
 packets={x['task_key']:x['packet'] for x in json.loads((BASE/'e2/reference_author/source_snapshot/task_packets.json').read_text())}
 scopes={x['task_key']:x for x in json.loads((BASE/'e2/reference_author/common_scopes_v2.json').read_text())['tasks']}
 return packets,scopes

def permute(xs,w):
 xs=list(xs);k=w%len(xs) if xs else 0;xs=xs[k:]+xs[:k]
 return list(reversed(xs)) if w%2==0 else xs

def reverse_objects(x):
 if isinstance(x,dict):return {k:reverse_objects(v) for k,v in reversed(list(x.items()))}
 if isinstance(x,list):return [reverse_objects(v) for v in x]
 return x

def messages(channel,users,count,w):
 return [{'sender':users[i%len(users)],'recipient':channel,'body':f'Synthetic source world {w} history message {i+1}'} for i in range(count)]

def mutated_packet(task_key,w,original):
 p=copy.deepcopy(original)
 if w==0:return p
 state=p['initial_state'];idx=w-1
 if task_key.startswith('banking/'):
  bank=state['bank_account'];byid={x['id']:x for x in bank['transactions']}
  byid[3]['amount']=[13,73.5,91.2,157,26.4][idx]
  byid[4]['amount']=[200,800,1499.8,415.2,1200][idx]
  byid[5]['amount']=[5.1,22,71.3,84,19.9][idx]
  byid[3]['recipient']=f'SE355000000005491000000{w}'
  byid[4]['recipient']=f'US12200000012121212121{w}'
  incoming=copy.deepcopy(byid[5]);incoming.update({'id':20+w,'amount':[14.2,6.5,9.9,30.1,40][idx],'date':'2022-03-19','subject':'Additional source friend transfer'})
  bank['transactions'].append(incoming)
  bank['transactions']=permute(bank['transactions'],w)
  bank['scheduled_transactions']=permute(bank['scheduled_transactions'],w)
 elif task_key.startswith('slack/'):
  slack=state['slack'];users=sorted(slack['users']);channels=slack['channels']
  if task_key.endswith('_10'):
   target=['private','External_0','private','External_0','private'][idx]
   slack['channel_inbox']={ch:messages(ch,users,0 if ch==target else 1+(channels.index(ch)+w)%4,w) for ch in channels}
   if w%2==0:slack['channel_inbox'].pop(target)
  else:
   if task_key.endswith('_13'):
    winner=['Bob','Eve','Alice','Charlie','Bob'][idx]
    others=[u for u in users if u!=winner];counts={u:i for i,u in enumerate(others)};counts[winner]=3+w
   else:counts=dict(zip(users,[[0,2,2,1],[3,0,3,0],[1,1,0,1],[0,0,0,0],[2,3,0,3]][idx]))
   inbox={ch:[] for ch in channels};step=0
   for user in users:
    for j in range(counts[user]):
     ch=channels[(step+w)%len(channels)];inbox[ch].append({'sender':user,'recipient':ch,'body':f'Synthetic world {w} source message {user}/{j+1}'});step+=1
   slack['channel_inbox']=inbox
  slack['users']=permute(slack['users'],w);slack['channels']=permute(slack['channels'],w)
  slack['channel_inbox']={ch:permute(ms,w) for ch,ms in slack['channel_inbox'].items()}
 elif task_key.startswith('travel/'):
  companies=state['car_rental']['company_list'];winner=['LAX Car Rental','Speedy Rentals','SunSet Rent-A-Car','LAX Car Rental','SunSet Rent-A-Car'][idx]
  for co in companies:
   if co['city']=='Los Angeles':
    if co['name']=='SunSet Rent-A-Car' and co['name']==winner and 'Electric' not in co['fuel_options']:co['fuel_options'].append('Electric')
    co['rating']=4.1
    if co['name']==winner:co['rating']=[4.9,4.8,4.7,5.0,4.95][idx];co['price_per_day']=[32.4,59.99,74.8,18.25,103.5][idx]
  state['car_rental']['company_list']=permute(companies,w)
 if w%2:state=reverse_objects(state)
 p['initial_state']=state
 p['packet_id']=canonical_sha({'task_key':task_key,'world_id':w,'task_request':p['task_request'],'initial_state':state})[:16]
 return p

def public_worlds():
 packets,scopes=load_sources();out=[]
 for w in range(6):
  for key in TASKS:
   packet=mutated_packet(key,w,packets[key]);scope=copy.deepcopy(scopes[key]);scope.pop('scope_sha256',None)
   scope.update({'scope_id':key.replace('/','__')+f'__r22_world_{w}','source_packet_id':packet['packet_id'],'source_packet_sha256':canonical_sha(packet),'previous_scope_id':scopes[key]['scope_id'],'r22_source_world':w})
   scope['scope_sha256']=canonical_sha(scope)
   assert packet['task_request']==packets[key]['task_request']
   assert scope['obligations']==scopes[key]['obligations']
   out.append({'task_key':key,'world_id':w,'packet':packet,'scope':scope})
 return out

if __name__=='__main__':
 out=public_worlds();(HERE/'public_packets.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
