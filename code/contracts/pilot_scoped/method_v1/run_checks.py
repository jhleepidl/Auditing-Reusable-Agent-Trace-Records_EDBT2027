"""API-free generic method checks; writes an optional external receipt."""
import argparse, copy, hashlib, importlib.metadata, json, sys, unittest
from pathlib import Path
import contract_executor as ce
from test_executor import contract,state_clause,query_clause
R=Path(__file__).resolve().parent

def run(out):
 suite=unittest.defaultTestLoader.discover(str(R),pattern='test_executor.py')
 result=unittest.TextTestRunner(stream=sys.stderr,verbosity=2).run(suite)
 q=contract([query_clause(),query_clause('t','total',336,unit='money_total',time='seven_day_rental'),query_clause('n','name','Speedy Rentals',unit=None,time=None)])
 a=contract([state_clause(newness='none')])
 absent=contract([state_clause(checks=[{'property':'$value','operator':'absent','value':True}],profile='singleton',field=None,newness='none',path='/gone')])
 new=contract([state_clause()]);pre={'items':[{'id':1,'amount':1}]};item={'id':2,'amount':12}
 cases=[('post_not_observed',a,{},None,'','unknown'),('absence_cannot_be_proved_from_missing_snapshot',absent,{},None,'','unknown'),('query_control',q,None,None,'Speedy Rentals — rating 4.5, total 336','pass'),('query_field_value_swap',q,None,None,'Speedy Rentals — rating 336, total 4.5','fail'),('query_conflicting_assertions',q,None,None,'Speedy Rentals — rating 4.5, total 336. Speedy Rentals — rating 1.0, total 336','fail'),('new_entity_first',new,pre,{'items':[item,*pre['items']]},'','pass'),('new_entity_last',new,pre,{'items':[*pre['items'],item]},'','pass')]
 rows=[]
 for name,c,b,p,o,expected in cases:
  actual=ce.evaluate(c,b,p,o);rows.append({'name':name,'actual':actual,'desired':expected,'meets_requirement':actual['verdict']==expected})
 receipt={'status':'PASS' if result.wasSuccessful() and all(x['meets_requirement'] for x in rows) else 'FAIL','tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'targeted_regressions_met':sum(x['meets_requirement'] for x in rows),'targeted_regressions_total':7,'results':rows,'api_calls':0,'jsonschema_version':importlib.metadata.version('jsonschema'),'files':{name:hashlib.sha256((R/name).read_bytes()).hexdigest() for name in ['contract_executor.py','output_schema.json','test_executor.py','IR_SPEC.md']},'designation':'EXPOSED_GENERIC_DEVELOPMENT_REGRESSIONS_NOT_CONFIRMATION_OR_SEMANTIC_GOLD'}
 if out:out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(receipt,indent=2)+'\n')
 print(json.dumps({k:v for k,v in receipt.items() if k!='results'},indent=2))
 return receipt['status']=='PASS'
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path);a=ap.parse_args();raise SystemExit(0 if run(a.out) else 1)
