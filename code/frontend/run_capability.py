"""Compile/predict first, score in a separate tool. No reference imports."""
from common import *
from collections import Counter
import copy,time

def main():
 freeze=load(STUDY/'plans/CAPABILITY_FREEZE.json')
 for p,m in freeze['programs'].items():assert sha(STUDY/'programs'/p)==m['sha256']
 for p,h in load(STUDY/'plans/PLAN_FREEZE.json')['bindings'].items():assert sha(UPSTREAM/p)==h
 pub=public();f=facts();schemas=load(UPSTREAM/'source_view/state_schemas.json')
 cases=[];observations={}
 for ds in ['development_v3','confirmation_all']:
  path=UPSTREAM/f'source_study/views/{ds}/cases.jsonl'
  for c in rows(path):
   p=(path.parent/c['input_file']).resolve();assert sha(p)==c['input_sha256']
   cases.append(c);observations[c['case_id']]=load(p)
 assert len(cases)==len(set(c['case_id'] for c in cases))==384
 construction=[];preds=[];diag=[]
 for (task,world),public_row in sorted(pub.items()):
  ann=load(STUDY/'programs'/(task.replace('/','__')+'.json'))
  before=time.perf_counter();compiled=v2.compile_annotation(ann,public_row['packet'],public_row['scope'],mode='derived',public_facts=f)
  receipt={'task_key':task,'world_id':world,'annotation_sha256':digest(ann),'source_sha256':digest(public_row['packet']),
           'compile_status':compiled['status'],'compile_ms':(time.perf_counter()-before)*1000,'compilation':compiled,
           'max_depth':max([t.get('depth',0) for t in compiled.get('provenance',{}).get('nodes',[])]+[0]),
           'node_count':len(ann['nodes'])}
  construction.append(receipt)
  packet=copy.deepcopy(public_row['packet']);packet['state_schema']=schemas[task.split('/')[0]]
  for c in cases:
   if (c['task_key'],c['world_id'])!=(task,world):continue
   ob=observations[c['case_id']]
   if compiled['status']!='ok':result={'verdict':compiled['status'],'reason':'construction_'+compiled['status'],'diagnostics':compiled['diagnostics']}
   else:
    try:result=ex.evaluate(compiled['contract'],ob.get('pre_state'),ob.get('post_state'),ob.get('output'),public_task=public_row['scope'],packet=packet,policy='scope')
    except Exception as e:result={'verdict':'error','reason':type(e).__name__+':'+str(e)}
   base={k:c[k] for k in ['case_id','task_key','world_id','scope_id','scope_sha256','source_packet_sha256','input_sha256']}
   preds.append(base|{'method':'expert_capability','model':'none','repeat':1,'status':result['verdict']});diag.append(base|{'result':result})
 path=STUDY/'results/capability'
 if path.exists():raise FileExistsError(path)
 write_rows(path/'construction.jsonl',construction);write_rows(path/'predictions.jsonl',preds);write_rows(path/'diagnostics.jsonl',diag)
 write(path/'RECEIPT.json',{'utc':now(),'designation':'expert-authored capability, retrospective exposed-world test; not a model result',
  'template_count':8,'source_world_count':48,'case_count':384,'predictions_sha256':sha(path/'predictions.jsonl'),
  'compile_statuses':dict(Counter(c['compile_status'] for c in construction)),'prediction_statuses':dict(Counter(c['status'] for c in preds)),
  'reference_decisions_loaded':False,'new_native_execution':False,'external_model_calls':0,
  'capability_freeze_sha256':sha(STUDY/'plans/CAPABILITY_FREEZE.json'),'runner_sha256':sha(__file__)})
 print(json.dumps(load(path/'RECEIPT.json'),indent=2))
 for r in construction:
  if r['compile_status']!='ok':print(r['task_key'],r['world_id'],r['compilation']['diagnostics'])
if __name__=='__main__':main()
