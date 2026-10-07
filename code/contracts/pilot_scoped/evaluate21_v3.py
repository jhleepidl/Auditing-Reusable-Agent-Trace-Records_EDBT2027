"""Evaluate all retained candidates/observations; no source-reference decisions loaded."""
import argparse, collections, hashlib, json, sys
from pathlib import Path
from common21 import ROOT, BASE, load, rows, write, write_rows, sha, now, canonical_sha
sys.path.insert(0,str(ROOT/'e2/method_v2'))
import contract_executor as ex
def main():
 p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--cases',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
 scopefile=ROOT/'e2/reference_author/common_scopes_v2.json';packetfile=ROOT/'e2/reference_author/source_snapshot/task_packets.json'
 ts={t['task_key']:t for t in load(scopefile)['tasks']};ps={t['task_key']:t['packet'] for t in load(packetfile)}
 schemas={};cases=rows(a.cases);data={}
 for c in cases:
  f=(a.cases.parent/c['input_file']).resolve();assert f.is_relative_to(a.cases.parent.resolve()) and sha(f)==c['input_sha256'];data[c['case_id']]=load(f)
 start=load(a.run/'PROVIDER_START.json');inventory=ROOT/start['request_inventory_relative_path'];assert sha(inventory)==start['requests_sha256'] and sha(inventory.parent/'FREEZE.json')==start['request_freeze_sha256']
 planned={r['request_id']:r for r in rows(inventory)}
 responses=[load(f) for f in sorted((a.run/'responses').glob('*.json'))];assert len(responses)==len(planned) and {r['request_id'] for r in responses}==set(planned);pred=[];diagnostics=[];construction=[]
 assert len({c['case_id'] for c in cases})==len(cases)
 for c in cases:
  t=ts[c['task_key']];assert c['scope_sha256']==t['scope_sha256'] and c['source_packet_sha256']==t['source_packet_sha256']
 for r in responses:
  req=planned[r['request_id']];assert all(r[k]==req[k] for k in ['task_key','method','model','seed','phase'])
  actual=load(a.run/'requests'/(r['request_id']+'.json'));assert hashlib.sha256(json.dumps(actual,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()==r['request_sha256']
  assert json.loads(actual['messages'][1]['content'])==req['input'] and actual['messages'][0]['content']==req['system']
  assert actual['model']==req['model'] and actual['seed']==req['seed'] and actual['response_format']['json_schema']['schema']==req['output_schema']
  t=ts[r['task_key']];packet=dict(ps[r['task_key']]);assert canonical_sha(packet)==t['source_packet_sha256']
  assert req['input']['common_scope']==t and req['input']['scope_sha256']==t['scope_sha256'] and req['input']['source_packet']==packet and req['input']['source_packet_sha256']==t['source_packet_sha256']
  if r['status']=='completed':assert r['annotation']==json.loads(r['raw_response']['choices'][0]['message']['content'])
  suite=r['task_key'].split('/')[0]
  if suite not in schemas:schemas[suite]=load(BASE/f'work/native/EDBT_R18_CPU_RESULTS/EDBT_R18_NO_HUMAN_KIT/inputs/r11/schemas/{suite}.json')
  packet['state_schema']=schemas[suite]
  shape=ex.validate(r['annotation']) if r['status']=='completed' else {'valid':False,'issues':[{'code':'provider_or_output_error','message':r.get('error')}]}
  construction.append({k:r[k] for k in ['task_key','method','model','seed','request_id']}|{'status':r['status'],'validation':shape})
  matched=[c for c in cases if c['task_key']==r['task_key']];assert matched,r['task_key']
  for c in matched:
   assert c['scope_id']==t['scope_id']
   d=data[c['case_id']]
   for policy in ['scope','scope_source']:
    base={k:c[k] for k in ['case_id','task_key','scope_id','scope_sha256','source_packet_sha256','input_sha256']};base.update(method=r['method']+'/'+policy,model=r['model'],seed=r['seed'],request_id=r['request_id'])
    if not shape['valid']:result={'verdict':'error','reason':'construction_failed','issues':shape['issues']}
    else:
     try:result=ex.evaluate(r['annotation'],d.get('pre_state'),d.get('post_state'),d.get('output'),public_task=t,packet=packet,policy=policy)
     except Exception as error:result={'verdict':'error','reason':'execution_exception','error':type(error).__name__+': '+str(error)}
    assert result['verdict'] in {'pass','fail','unknown','error'}
    pred.append(base|{'status':result['verdict']});diagnostics.append(base|{'result':result})
 write_rows(a.out/'predictions.jsonl',pred);write_rows(a.out/'diagnostics.jsonl',diagnostics);write_rows(a.out/'construction_validation.jsonl',construction)
 write(a.out/'RECEIPT.json',{'utc':now(),'candidate_count':len(responses),'case_count':len(cases),'prediction_cells':len(pred),'statuses':dict(collections.Counter(v['status'] for v in pred)),'cases_sha256':sha(a.cases),'scope_sha256':sha(scopefile),'source_packets_sha256':sha(packetfile),'request_inventory_sha256':sha(inventory),'planned_grid':[list(k) for k in sorted({(r['method']+'/'+policy,r['model'],r['seed']) for r in planned.values() for policy in ['scope','scope_source']})],'executor_sha256':sha(ROOT/'e2/method_v2/contract_executor.py'),'reference_decisions_loaded':False,'all_errors_retained':True})
 print(json.dumps({'candidates':len(responses),'cases':len(cases),'cells':len(pred),'statuses':dict(collections.Counter(v['status'] for v in pred))}))
if __name__=='__main__':main()
