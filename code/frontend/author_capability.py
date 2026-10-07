"""Expert-authored, template-specific controls, not a model or reference solver.

Only public world-0 scope is read during program construction. Nodes execute all
source selections/arithmetic later in the frozen original DAG runtime. The eight
annotations have no world-dependent answer constant. See plans/PLAN.md for the
retained-snapshot self-token convention and template-specific text anchors.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *

class DAG:
 def __init__(self, scope):
  self.scaffold=v2.build_scaffold(scope);self.nodes=[];self.memo={};self.binds={}
 def n(self,op,*args,**params):
  key=digest([op,args,params])
  if key in self.memo:return self.memo[key]
  nid=f'n{len(self.nodes):02d}';self.nodes.append({'id':nid,'op':op,'args':list(args),'params':params});self.memo[key]=nid;return nid
 def s(self,root,pointer=''):return self.n('source',root=root,pointer=pointer)
 def get(self,a,p):return self.n('get',a,pointer=p)
 def filt(self,a,b,p,relation='equals',casefold=False):return self.n('filter',a,b,pointer=p,relation=relation,casefold=casefold)
 def text(self,a,left,right='',trim=True):return self.n('text_between',a,left=left,right=right,trim=trim)
 def bind(self,k,n):
  if k not in self.scaffold['endpoints']:raise ValueError(k)
  self.binds[k]=n
 def finish(self):
  if set(self.binds)!=set(self.scaffold['endpoints']):raise ValueError(set(self.scaffold['endpoints'])-set(self.binds))
  return {'derivation_version':'r22.2','classification':self.scaffold['contract_template']['classification'],'unknown_reason':'',
          'operands':{k:{'claim':m['placeholder'],'node':self.binds[k]} for k,m in self.scaffold['endpoints'].items()},'nodes':self.nodes}

def self_token(d,tx):
 # Declared structural convention, not a general inference from arbitrary ledgers.
 first=d.n('argmin',tx,pointer='/id',ties='unknown')
 return d.get(first,'/sender')

def month_token(d):
 # March is fixed in these public task templates; value '03' is read, not copied.
 sep=d.s('facts','/ISO_date_separator');month=d.s('facts','/calendar_months/March')
 return d.n('concat',sep,month,sep)

def channel_data(d):
 users=d.s('initial_state','/slack/users');channels=d.s('initial_state','/slack/channels');inbox=d.s('initial_state','/slack/channel_inbox')
 per=d.n('lookup_many',inbox,channels,missing='empty_array');messages=d.n('flatten',per)
 return users,channels,messages

def new_message(d,i,recipient,body,bot):
 d.bind(f'o{i}_sender',bot);d.bind(f'o{i}_recipient',recipient);d.bind(f'o{i}_body',body)
 pattern=d.s('scope',f'/obligations/{i}/target/path_pattern')
 path=d.n('replace_once',pattern,recipient,needle='{recipient}')
 d.bind(f'o{i}_dynamic_path',path)

def author(task,scope):
 d=DAG(scope);req=d.s('request')
 if task.startswith('banking/'):
  tx=d.s('initial_state','/bank_account/transactions');me=self_token(d,tx)
  if task=='banking/user_task_1':
   out=d.filt(tx,me,'/sender');m=month_token(d)
   march=d.filt(out,m,'/date','contains');amounts=d.n('project',march,pointer='/amount');total=d.n('sum',amounts)
   d.bind('o0_entity',d.s('scope','/obligations/0/entity_binding/entity_label'));d.bind('o0_amount',total)
  elif task=='banking/user_task_4':
   person=d.text(req,'refund ',' for');incoming=d.filt(tx,person,'/sender');incoming=d.filt(incoming,me,'/recipient')
   total=d.n('sum',d.n('project',incoming,pointer='/amount'));d.bind('o0_recipient',person);d.bind('o0_amount',total)
  elif task in ['banking/user_task_5','banking/user_task_11']:
   if task.endswith('_5'):
    merchant=d.text(req,'',' sent');pct=d.n('extract_decimal',req,anchor='increased ')
   else:
    merchant=d.text(req,'for the ',' was');pct=d.n('extract_decimal',req,anchor='additional ')
   found=d.filt(tx,merchant,'/subject','contains',True);found=d.filt(found,me,'/sender')
   if task.endswith('_5'):found=d.filt(found,month_token(d),'/date','contains')
   chosen=d.n('unique',found);base=d.get(chosen,'/amount');person=d.get(chosen,'/recipient')
   hundred=d.n('constant',value=100);extra=d.n('divide',d.n('multiply',base,pct),hundred)
   if task.endswith('_11'):extra=d.n('add',extra,d.n('extract_decimal',req,anchor='a fee of '))
   total=d.n('quantize',extra,places=2,rounding='half_even');d.bind('o0_recipient',person);d.bind('o0_amount',total)
  else:raise ValueError(task)
 elif task=='slack/user_task_10':
  users,channels,msg=channel_data(d)
  counts=d.n('group_count',msg,channels,pointer='/recipient',unmatched='unknown')
  least=d.get(d.n('argmin',counts,pointer='/count',ties='unknown'),'/key')
  memberships=d.s('initial_state','/slack/user_channels');lists=d.n('lookup_many',memberships,users,missing='unknown')
  people=d.n('zip',users,lists,left_name='user',right_name='channels')
  absent=d.filt(people,least,'/channels','not_contains')
  ordered=d.n('sort',absent,keys=[{'pointer':'/user','direction':'asc'}])
  for i in range(len(scope['obligations'])):
   who=d.get(d.n('at',ordered,index=i),'/user')
   d.bind(f'o{i}_users',who);d.bind(f'o{i}_user_channels',least)
   pat=d.s('scope',f'/obligations/{i}/required_properties/1/property_pattern')
   d.bind(f'o{i}_dynamic_property',d.n('replace_once',pat,who,needle='{user}'))
 elif task in ['slack/user_task_13','slack/user_task_14']:
  users,channels,msg=channel_data(d);counts=d.n('group_count',msg,users,pointer='/sender',unmatched='ignore');bot=d.s('facts','/message_sender')
  if task.endswith('_13'):
   who=d.get(d.n('argmax',counts,pointer='/count',ties='unknown'),'/key');body=d.text(req,'message: ')
   new_message(d,0,who,body,bot)
  else:
   ordered=d.n('sort',counts,keys=[{'pointer':'/count','direction':'desc'},{'pointer':'/key','direction':'asc'}]);ranked=d.n('enumerate',ordered,index_name='rank')
   template=d.text(req,'message: ',' (where')
   for i in range(len(scope['obligations'])):
    row=d.n('at',ranked,index=i);who=d.get(row,'/key');rank=d.n('string',d.get(row,'/rank'))
    body=d.n('replace_once',template,rank,needle='k');new_message(d,i,who,body,bot)
 elif task=='travel/user_task_14':
  companies=d.s('initial_state','/car_rental/company_list');city=d.text(req,'into ',' on ');fuel=d.text(req,'have ',' cars?')
  eligible=d.filt(d.filt(companies,city,'/city'),fuel,'/fuel_options','contains',True)
  best=d.n('argmax',eligible,pointer='/rating',ties='unknown');name=d.get(best,'/name');rating=d.get(best,'/rating')
  price=d.get(best,'/price_per_day');days=d.s('facts','/days_per_week');total=d.n('quantize',d.n('multiply',price,days),places=2,rounding='half_even')
  d.bind('o0_entity',name);d.bind('o0_rating',rating);d.bind('o1_entity',name);d.bind('o1_total',total)
 else:raise ValueError(task)
 return d.finish()

def main():
 pub=public();output={}
 for task,w in sorted(pub):
  if w!=0:continue
  ann=author(task,pub[task,w]['scope'])
  # Schema-only check; neither observations nor reference targets are read here.
  from jsonschema import Draft202012Validator
  Draft202012Validator(v2.schema_for_scope(pub[task,w]['scope'])).validate(ann)
  path=STUDY/'programs'/(task.replace('/','__')+'.json')
  if path.exists():raise FileExistsError('Do not overwrite a frozen control: '+str(path))
  write(path,ann);output[path.name]={'sha256':sha(path),'nodes':len(ann['nodes']),'endpoints':len(ann['operands'])}
 write(STUDY/'plans/CAPABILITY_FREEZE.json',{'utc':now(),'author_source_sha256':sha(__file__),'plan_sha256':sha(STUDY/'plans/PLAN.md'),
  'world0_public_only_during_authoring':True,'private_reference_imported':False,'expert_authored_not_model_generated':True,'programs':output})
 print(json.dumps(output,indent=2))
if __name__=='__main__':main()
