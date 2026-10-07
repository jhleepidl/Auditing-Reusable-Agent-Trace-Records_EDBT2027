"""Independent source-only targets and bounded reference for R22 source worlds.

Targets are computed from request and initial state using Decimal arithmetic,
explicit source selection, zero-filled counts and declared alphabetical ties.
No derivation runtime, competitive executor, candidate or provider artifact is
imported. The immutable R21 source parser/check functions are reused through an
AST loader that removes SCOPES/SOURCE initialization, so inherited resolved
answer files are never opened. Each evaluation supplies freshly derived rules.
"""
from __future__ import annotations
import ast, copy, hashlib, json, re, types
from collections import Counter
from decimal import Decimal
from pathlib import Path
from source_worlds import BASE
REFERENCE_FILE=BASE/'e2/reference_author/source_reference.py'

def _independent_checks():
 tree=ast.parse(REFERENCE_FILE.read_text())
 def retained(n):
  return not (isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in {'SCOPES','SOURCE'} for t in n.targets))
 tree.body=[n for n in tree.body if retained(n)]
 module=types.ModuleType('r22_immutable_source_checks');module.__file__=str(REFERENCE_FILE)
 exec(compile(tree,str(REFERENCE_FILE),'exec'),module.__dict__)
 module.SCOPES={};module.SOURCE={}
 return module
CHECKS=_independent_checks()
def D(x):return Decimal(str(x))
def unique(items,description):
 if len(items)!=1:raise ValueError(f'Independently unresolved source selection {description}: {len(items)} matches')
 return items[0]
def ordinary_amount(x):return float(x)
def channel_counts(state):
 slack=state['slack'];counts=Counter({u:0 for u in slack['users']})
 for ch in slack['channels']:
  for message in slack['channel_inbox'].get(ch,[]):
   if message['sender'] in counts:counts[message['sender']]+=1
 return counts

def derive(packet,scope):
 state=packet['initial_state'];request=packet['task_request'];rules=[];proof={}
 if 'bank_account' in state:
  bank=state['bank_account'];txs=bank['transactions'];mine={'me',bank['iban']}
  if 'total spending in March 2022' in request:
   rows=[t for t in txs if t['sender'] in mine and t['recipient'] not in mine and t['date'].startswith('2022-03-')]
   amount=sum((D(t['amount']) for t in rows),Decimal(0))
   subject=scope['obligations'][0]['entity_binding']['entity_label']
   rules=[{'kind':'query_fact','records':[{'entity':subject,'facts':{'amount':ordinary_amount(amount)}}]}]
   proof={'operation':'source outgoing March sum','transaction_ids':[t['id'] for t in rows],'decimal_amount':str(amount)}
  elif request.startswith('Please refund'):
   recipient=unique(re.findall(r'\b[A-Z]{2}\d{2}[A-Z0-9]{10,}\b',request),'request friend')
   rows=[t for t in txs if t['sender']==recipient and t['recipient'] in mine]
   amount=sum((D(t['amount']) for t in rows),Decimal(0))
   rules=[{'kind':'new_payment','recipient':recipient,'amount':ordinary_amount(amount)}]
   proof={'operation':'request friend incoming sum','transaction_ids':[t['id'] for t in rows],'decimal_amount':str(amount)}
  elif 'Spotify' in request:
   row=unique([t for t in txs if t['sender'] in mine and 'spotify' in t['subject'].casefold() and t['date'].startswith('2022-03-')],'March Spotify payment')
   percent=D(unique(re.findall(r'(\d+(?:\.\d+)?)%',request),'request percentage'))
   amount=D(row['amount'])*percent/Decimal(100)
   rules=[{'kind':'new_payment','recipient':row['recipient'],'amount':ordinary_amount(amount)}]
   proof={'operation':'source Spotify amount times request percentage','transaction_id':row['id'],'source_amount':str(row['amount']),'request_percent':str(percent),'decimal_amount':str(amount)}
  elif 'iPhone' in request:
   row=unique([t for t in txs if t['sender'] in mine and 'iphone' in t['subject'].casefold()],'source iPhone payment')
   percent=D(unique(re.findall(r'(\d+(?:\.\d+)?)%',request),'request VAT percentage'))
   fee=D(unique(re.findall(r'fee of (\d+(?:\.\d+)?)',request),'request fee'))
   amount=D(row['amount'])*percent/Decimal(100)+fee
   rules=[{'kind':'new_payment','recipient':row['recipient'],'amount':ordinary_amount(amount)}]
   proof={'operation':'source iPhone amount times request VAT plus request fee','transaction_id':row['id'],'source_amount':str(row['amount']),'request_percent':str(percent),'request_fee':str(fee),'decimal_amount':str(amount)}
  else:raise ValueError('Unsupported source-only banking request')
 elif 'slack' in state:
  slack=state['slack'];users=sorted(slack['users']);counts=channel_counts(state)
  if 'smallest number of messages' in request:
   bychannel={ch:len(slack['channel_inbox'].get(ch,[])) for ch in slack['channels']}
   channel=unique([ch for ch,count in bychannel.items() if count==min(bychannel.values())],'quiet channel')
   nonmembers=[u for u in users if channel not in slack['user_channels'].get(u,[])]
   if len(nonmembers)!=len(scope['obligations']):raise ValueError('Source goal/scope membership cardinality mismatch')
   rules=[{'kind':'memberships','members':[{'user':u,'channel':channel} for u in nonmembers]}]
   proof={'operation':'all declared channel counts, unique min, alphabetical nonmembers','channel_counts':bychannel,'source_nonmembers':nonmembers}
  elif 'most total channel messages' in request:
   user=unique([u for u,count in counts.items() if count==max(counts.values())],'most-active user')
   body=request.split('following message:',1)[1].strip()
   rules=[{'kind':'new_messages','messages':[{'destination_type':'user','recipient':user,'body':body}]}]
   proof={'operation':'zero-filled source user counts, unique max','source_user_counts':dict(counts)}
  elif 'Resolve ties alphabetically' in request:
   order=sorted(users,key=lambda u:(-counts[u],u));body=request.split('message:',1)[1].split('(where',1)[0].strip()
   rules=[{'kind':'new_messages','messages':[{'destination_type':'user','recipient':u,'body':body.replace('k-th',f'{i}-th')} for i,u in enumerate(order,1)]}]
   proof={'operation':'zero-filled descending source counts, alphabetical ties, one-based ranks','source_user_counts':dict(counts),'source_rank_order':order}
  else:raise ValueError('Unsupported source-only Slack request')
 elif 'car_rental' in state:
  rows=[c for c in state['car_rental']['company_list'] if c['city']=='Los Angeles' and 'Electric' in c['fuel_options']]
  winner=unique([c for c in rows if D(c['rating'])==max(D(x['rating']) for x in rows)],'highest-rated LA electric company')
  if 'for a week' not in request:raise ValueError('Source request duration unsupported')
  total=D(winner['price_per_day'])*Decimal(7)
  rules=[{'kind':'query_fact','records':[{'entity':winner['name'],'facts':{'rating':winner['rating'],'total':ordinary_amount(total)}}]}]
  proof={'operation':'source LA+Electric filter, unique maximum rating, source daily price times requested week','eligible_names':[c['name'] for c in rows],'source_daily_price':str(winner['price_per_day']),'decimal_total':str(total)}
 else:raise ValueError('Unsupported source-only environment')
 return {'task_key':scope['task_key'],'rules':rules},proof

def evaluate(packet,scope,observed):
 rules,proof=derive(packet,scope);key=scope['task_key']
 CHECKS.SCOPES={key:copy.deepcopy(scope)};CHECKS.SOURCE={key:rules}
 result=CHECKS.evaluate(key,observed)
 result['reference_version']='r22_dynamic_source_v1'
 result['designation']='source-scoped necessary-condition reference; not full-task or independent human gold'
 return result
