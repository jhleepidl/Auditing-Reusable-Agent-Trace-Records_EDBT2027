"""Behavioral regressions/metamorphic controls; no task utilities or reference labels."""
import copy, json, unittest
import contract_executor as ce
SUP={'request_quote':'Add the item','initial_state_paths':['/items'],'schema_paths':[],'reason':'Explicit request condition, structural witness only.'}
def state_clause(name='o',checks=None,selector=None,profile='stable_id',field='id',newness='pre_id_absence',path='/items'):
 return {'obligation_id':name,'kind':'state','state':{'path':path,'selector':selector or [],'checks':checks or [{'property':'amount','operator':'equals','value':12}], 'identity_profile':profile,'identity_field':field,'newness':newness},'query':None,'support':copy.deepcopy(SUP)}
def query_clause(name='q',prop='rating',value=4.5,entity='Speedy Rentals',unit='rating_points',time='unscoped',role='r'):
 return {'obligation_id':name,'kind':'query','state':None,'query':{'entity':entity,'property':prop,'value':value,'unit':unit,'temporal_scope':time,'role':role,'polarity':'positive'},'support':copy.deepcopy(SUP)}
def contract(clauses,scope='s'):
 return {'ir_version':ce.VERSION,'scope_id':scope,'classification':clauses[0]['kind'] if clauses else 'unknown','clauses':clauses,'unknown_reason':''}
def task(clauses):
 obs=[]
 for c in clauses:
  if c['kind']=='state':
   s=c['state'];obs.append({'obligation_id':c['obligation_id'],'kind':'state','target':{'path':s['path'],'identity_profile':s['identity_profile'],'identity_field':s['identity_field']},'required_properties':[{'property':x['property'],'type':ce._type(x['value']),'operator':x['operator']} for x in s['checks']],'newness':s['newness'],'selector_requirements':[],'observation_requirements':['post_state']+(['pre_state'] if s['newness']!='none' else [])})
  else:
   q=c['query'];obs.append({'obligation_id':c['obligation_id'],'kind':'query','property':q['property'],'value_type':ce._type(q['value']),'binding_role':q['role'],'unit':q['unit'],'temporal_scope':q['temporal_scope'],'polarity':'affirmative','observation_requirements':['output']})
 return {'scope_id':'s','task_key':'test/user_task','obligations':obs}
def verdict(c,pre=None,post=None,output='',**kw):return ce.evaluate(c,pre,post,output,**kw)['verdict']
class RegressionTests(unittest.TestCase):
 def test_missing_snapshot_is_not_observed_violation(self):
  c=contract([state_clause(newness='none')]);self.assertEqual(verdict(c,{},None),'unknown')
 def test_missing_snapshot_cannot_prove_absence(self):
  c=contract([state_clause(checks=[{'property':'$value','operator':'absent','value':True}],profile='singleton',field=None,newness='none',path='/gone')]);self.assertEqual(verdict(c,{},None),'unknown');self.assertEqual(verdict(c,{},{}),'pass')
 def test_query_control_and_swap(self):
  c=contract([query_clause(),query_clause('t','total',336,unit='money_total',time='seven_day_rental')]);self.assertEqual(verdict(c,output='Speedy Rentals — rating 4.5, total 336'),'pass');self.assertEqual(verdict(c,output='Speedy Rentals — rating 336, total 4.5'),'fail')
 def test_query_conflicting_assertions(self):
  c=contract([query_clause()]);self.assertEqual(verdict(c,output='Speedy Rentals — rating 4.5. Speedy Rentals — rating 1.0'),'fail');self.assertEqual(verdict(c,output='Speedy Rentals — rating 4.5. Speedy Rentals — rating is not 4.5'),'fail')
 def test_stable_identity_first_and_last_reorder(self):
  c=contract([state_clause()]);pre={'items':[{'id':1,'amount':1}]};new={'id':2,'amount':12}
  for after in [[new,*pre['items']],[*pre['items'],new]]:self.assertEqual(verdict(c,pre,{'items':after}),'pass')
  self.assertEqual(verdict(c,{'items':[new,{'id':1,'amount':1}]},{'items':[{'id':1,'amount':1},new]}),'fail')
 def test_same_id_recreate_is_not_id_novelty(self):
  c=contract([state_clause()]);self.assertEqual(verdict(c,{'items':[{'id':1,'amount':1}]},{'items':[{'id':1,'amount':12}]}),'fail')
 def test_entity_conjunction_not_split(self):
  c=contract([state_clause(checks=[{'property':'recipient','operator':'equals','value':'A'},{'property':'amount','operator':'equals','value':12}])]);self.assertEqual(verdict(c,{'items':[]},{'items':[{'id':1,'recipient':'A','amount':1},{'id':2,'recipient':'B','amount':12}]}),'fail')
 def test_duplicate_or_missing_ids_are_unknown(self):
  c=contract([state_clause()]);self.assertEqual(verdict(c,{'items':[]},{'items':[{'amount':12}]}),'unknown');self.assertEqual(verdict(c,{'items':[]},{'items':[{'id':1,'amount':12},{'id':1,'amount':12}]}),'unknown')
 def test_observed_absence_and_missing_obligation_fail_dominance(self):
  a=state_clause('new');b=state_clause('existing',checks=[{'property':'flag','operator':'equals','value':True}],profile='singleton',field=None,newness='none',path='/account');c=contract([a,b]);t=task([a,b]);self.assertEqual(verdict(c,None,{'items':[],'account':{'flag':False}},public_task=t),'fail');self.assertEqual(verdict(c,None,{'items':[],'account':{'flag':True}},public_task=t),'unknown')
 def test_query_missing_empty_complete_omission_and_unsupported(self):
  c=contract([query_clause(),query_clause('t','total',336,unit='money_total',time='seven_day_rental')]);self.assertEqual(verdict(c,output=None),'unknown');self.assertEqual(verdict(c,output=''),'fail');self.assertEqual(verdict(c,output='Speedy Rentals — rating 4.5'),'fail');self.assertEqual(verdict(c,output='Speedy Rentals — rating 4.5, total maybe 336'),'unknown')
 def test_role_binding(self):
  c=contract([query_clause(role='electric')]);self.assertEqual(verdict(c,output='[electric] Speedy Rentals — rating 4.5'),'pass');self.assertEqual(verdict(c,output='[suv] Speedy Rentals — rating 4.5'),'fail')
 def test_unit_and_temporal_binding(self):
  c=contract([query_clause('t','total',336,unit='money_total',time='seven_day_rental')]);self.assertEqual(verdict(c,output='Speedy Rentals — total 336 USD for 7 days'),'pass');self.assertEqual(verdict(c,output='Speedy Rentals — total 336 USD for 3 days'),'fail')
  literal=contract([query_clause('t','total',336,unit='USD',time=None)]);self.assertEqual(verdict(literal,output='Speedy Rentals — total 336 GBP'),'fail')
  self.assertEqual(verdict(contract([query_clause()]),output='Speedy Rentals — rating 4.5 USD'),'fail')
 def test_type_consistency_array_boolean_and_numeric(self):
  a=state_clause(checks=[{'property':'value','operator':'equals','value':[True,False]}],profile='singleton',field=None,newness='none',path='/item');c=contract([a]);self.assertTrue(ce.validate(c)['valid']);self.assertEqual(verdict(c,{}, {'item':{'value':[True,False]}}),'pass');self.assertEqual(verdict(c,{}, {'item':{'value':[1,0]}}),'fail')
  a['state']['checks']=[{'property':'value','operator':'gt','value':True}];self.assertFalse(ce.validate(contract([a]))['valid'])
 def test_malformed_selector_is_construction_error(self):
  a=state_clause();a['state']['selector']=[{'value':1}];c=contract([a]);self.assertFalse(ce.validate(c)['valid']);self.assertEqual(verdict(c,{},{}),'error')
 def test_invalid_pointer_and_nonfinite_values(self):
  a=state_clause(path='/items~x');self.assertFalse(ce.validate(contract([a]))['valid']);a=state_clause();a['state']['checks'][0]['value']=float('nan');self.assertFalse(ce.validate(contract([a]))['valid'])
 def test_scope_operator_duplicate_extra_and_type(self):
  a=state_clause();t=task([a]);c=contract([a]);self.assertTrue(ce.preflight(c,t)['admitted']);c['clauses'][0]['state']['checks'][0]['operator']='exists';c['clauses'][0]['state']['checks'][0]['value']=True;self.assertFalse(ce.preflight(c,t)['admitted'])
  c=contract([a]);c['clauses'][0]['state']['checks']*=2;self.assertFalse(ce.preflight(c,t)['admitted'])
  c=contract([a]);c['clauses'][0]['state']['checks'][0]['value']='12';self.assertFalse(ce.preflight(c,t)['admitted'])
 def test_source_quotes_and_pointers(self):
  a=state_clause();t=task([a]);c=contract([a]);packet={'request':'Add the item now','initial_state':{'items':[]},'state_schema':{'type':'object','properties':{'items':{'type':'array','items':{'type':'object'}}}}};self.assertTrue(ce.preflight(c,t,packet,'scope_source')['admitted']);c['clauses'][0]['support']['request_quote']='Invented';self.assertFalse(ce.preflight(c,t,packet,'scope_source')['admitted'])
  c=contract([a]);c['clauses'][0]['support']['initial_state_paths']=['/not_present'];self.assertFalse(ce.preflight(c,t,packet,'scope_source')['admitted'])
 def test_schema_local_refs_repeated_tokens_and_external_ref(self):
  schema={'type':'object','properties':{'same':{'$ref':'#/$defs/X'}},'$defs':{'X':{'type':'object','properties':{'same':{'type':'string'}}}}};self.assertTrue(ce._schema_resolve(schema,'/same/same'));schema['properties']['same']['$ref']='https://example.invalid/schema';self.assertFalse(ce._schema_resolve(schema,'/same/same'))
  schema={'$ref':'#/$defs/X','$defs':{'X':{'$ref':'#/$defs/X'}}};self.assertFalse(ce._schema_resolve(schema,'/same'))
 def test_membership_binding_and_message_path_binding(self):
  a=state_clause(checks=[{'property':'users','operator':'member','value':'A'},{'property':'user_channels/B','operator':'member','value':'chan'}],profile='singleton',field=None,newness='none',path='/slack');t=task([a]);t['obligations'][0]['required_properties']=[{'property':'users','type':'array[string]','operator':'member'},{'property_pattern':'user_channels/{user}','type':'array[string]','operator':'member','binding':{'capture':'user','value_property':'users'}}];self.assertFalse(ce.preflight(contract([a]),t)['admitted']);a['state']['checks'][1]['property']='user_channels/A';self.assertTrue(ce.preflight(contract([a]),t)['admitted'])
  m=state_clause(checks=[{'property':k,'operator':'equals','value':v} for k,v in [('sender','bot'),('recipient','A'),('body','hello')]],profile='message_multiset',field=['sender','recipient','body'],newness='count_increase',path='/inbox/B');t=task([m]);t['obligations'][0]['target'].update(path_pattern='/inbox/{recipient}',path_bindings=[{'capture':'recipient','value_property':'recipient'}]);t['obligations'][0]['target'].pop('path');self.assertFalse(ce.preflight(contract([m]),t)['admitted']);m['state']['path']='/inbox/A';self.assertTrue(ce.preflight(contract([m]),t)['admitted']);self.assertEqual(verdict(contract([m]),{'inbox':{'A':[]}},{'inbox':{'A':[{'sender':'bot','recipient':'A','body':'hello'}]}}),'pass')
 def test_public_task_subject_alias_only(self):
  a=query_clause(prop='amount',value=12,entity='New Year gift spending',unit='money_amount',time='source_gift_transaction',role='gift');t=task([a]);t['obligations'][0]['entity_binding']={'kind':'task_subject','entity_label':'New Year gift spending','accepted_labels':['New Year gift spending','New Year gift']};self.assertEqual(verdict(contract([a]),output='New Year gift — amount 12',public_task=t),'pass');a['query']['entity']='Other gift';self.assertFalse(ce.preflight(contract([a]),t)['admitted'])
 def test_quoted_wrong_dimension_is_mention_not_contradiction(self):
  c=contract([query_clause()])
  correct='Speedy Rentals — rating 4.5'
  quoted='> Speedy Rentals — rating 0.23 USD'
  self.assertEqual(verdict(c,output=quoted+'\n'+correct),'pass')
  self.assertEqual(verdict(c,output=correct+'\n'+quoted),'pass')
  self.assertEqual(verdict(c,output=quoted),'fail')
  self.assertEqual(verdict(c,output=correct+'\nSpeedy Rentals — rating 0.23 USD'),'fail')
 def test_currency_and_people_qualifier_preserves_role_time_binding(self):
  c=contract([query_clause('t','total',120,entity='Example Airline',unit='money_total',time='two_person_flight',role='flight')])
  for word in ['people','persons','passengers']:
   self.assertEqual(verdict(c,output='[flight] Example Airline — total 120 EUR for 2 '+word),'pass')
  self.assertEqual(verdict(c,output='[flight] Example Airline — total 120 EUR for 3 people'),'fail')
  self.assertEqual(verdict(c,output='[car] Example Airline — total 120 EUR for 2 people'),'fail')
  self.assertEqual(verdict(c,output='[flight] Example Airline — total 120 EUR for 2 dragons'),'unknown')
 def test_diagnostic_receipts_are_json_serializable(self):
  c=contract([query_clause()]);json.dumps(ce.evaluate(c,None,None,'Speedy Rentals — rating 1.0'))
if __name__=='__main__':unittest.main()
