"""Four fixed frontends on every retained r22.2 candidate. No reference imports."""
from common import *
import argparse,copy,collections,sys,time
sys.path.insert(0,str(STUDY/'method'))
from frontend import compile_annotation
STAGES=[('development_v2','development_v2','development_v3','fresh'),('confirmation_fresh','confirmation_v1','confirmation_fresh','fresh'),('feedback_round1','feedback_round1','feedback_fresh','fresh'),('feedback_round2','feedback_round2','feedback_fresh','fresh'),('review_only_control','review_only_control','feedback_fresh','fresh'),('transfer_v2','development_v2','confirmation_all','transfer')]
POLICIES={'old':(False,False),'topology':(True,False),'addressing':(False,True),'combined':(True,True)}

def execute(stage,run,dataset,mode,policy):
 folder=STUDY/f'results/factorial/{stage}/{policy}'
 if folder.exists():raise FileExistsError(folder)
 pub=public();schemas=load(UPSTREAM/'source_view/state_schemas.json')
 run=UPSTREAM/'runs'/run;start=load(run/'PROVIDER_START.json');inventory=UPSTREAM/start['request_inventory_relative_path']
 assert sha(inventory)==start['requests_sha256'] and sha(inventory.parent/'FREEZE.json')==start['request_freeze_sha256']
 reqs={r['request_id']:r for r in rows(inventory)};responses=[load(p) for p in sorted((run/'responses').glob('*.json'))]
 assert len(reqs)==len(responses) and set(reqs)=={r['request_id']for r in responses}
 cpath=UPSTREAM/f'source_study/views/{dataset}/cases.jsonl';cases=rows(cpath);observed={};case_groups={}
 for c in cases:
  op=(cpath.parent/c['input_file']).resolve();assert sha(op)==c['input_sha256']
  observed[c['case_id']]=load(op);case_groups.setdefault((c['task_key'],c['world_id']),[]).append(c)
 topo,addr=POLICIES[policy];pred=[];diag=[];construction=[]
 for r in responses:
  req=reqs[r['request_id']];sent=load(run/'requests'/(r['request_id']+'.json'))
  assert hashlib.sha256(json.dumps(sent,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()==r['request_sha256']
  origin=pub[r['task_key'],r['world_id']]
  assert req['input']['source_packet']==origin['packet'] and req['input']['common_scope']==origin['scope']
  assert req['input']['public_scaffold']==v2.build_scaffold(origin['scope'])
  if r['status']=='completed':
   text=''.join(c['text'] for x in r['raw_response'].get('output',[]) if x.get('type')=='message' for c in x.get('content',[]) if c.get('type')=='output_text')
   assert json.loads(text)==r['annotation']
  worlds=[r['world_id']] if mode=='fresh' else sorted(w for t,w in case_groups if t==r['task_key'])
  for world in worlds:
   source=pub[r['task_key'],world];p=copy.deepcopy(source['packet']);p['state_schema']=schemas[r['task_key'].split('/')[0]]
   choices=[('literal','literal')] if r['method']=='literal' else [('derived','derived'),('derived_verified','verified')]
   if mode=='transfer' and r['method']=='literal':choices=[('literal_bound','bound'),('literal_rebound','literal')]
   for method,cmode in choices:
    ts=time.perf_counter()
    if r['status']!='completed':result={'status':'error','contract':None,'provenance':{},'diagnostics':[{'reason':'provider_error'}]}
    elif cmode=='bound':result={'status':'unknown','contract':None,'provenance':{},'diagnostics':[{'reason':'source_binding_changed'}]}
    else:result=compile_annotation(r['annotation'],source['packet'],source['scope'],mode=cmode,public_facts=req['input']['public_facts'],topology=topo,addressing=addr)
    construction.append({'request_id':r['request_id'],'task_key':r['task_key'],'world_id':world,'origin_world_id':r['world_id'],'method':method,'model':r['model'],'repeat':r['repeat'],'compile_status':result['status'],'compile_ms':(time.perf_counter()-ts)*1000,'original_annotation_sha256':digest(r.get('annotation')),'compilation':result})
    for c in case_groups[r['task_key'],world]:
     ob=observed[c['case_id']]
     if result['status']!='ok':d={'verdict':result['status'],'reason':'construction_'+result['status'],'diagnostics':result['diagnostics']}
     else:
      try:d=ex.evaluate(result['contract'],ob.get('pre_state'),ob.get('post_state'),ob.get('output'),public_task=source['scope'],packet=p,policy='scope')
      except Exception as e:d={'verdict':'error','reason':'execution_exception','error':type(e).__name__+':'+str(e)}
     base={k:c[k] for k in ['case_id','task_key','world_id','scope_id','scope_sha256','source_packet_sha256','input_sha256']};base.update(method=method,model=r['model'],repeat=r['repeat'],request_id=r['request_id'])
     pred.append(base|{'status':d['verdict']});diag.append(base|{'result':d})
 groups=sorted({(r['method'],r['model'],r['repeat'])for r in pred});assert len(pred)==len(cases)*len(groups)
 write_rows(folder/'predictions.jsonl',pred);write_rows(folder/'diagnostics.jsonl',diag);write_rows(folder/'construction.jsonl',construction)
 original=rows(UPSTREAM/f'evaluation/{stage}/predictions.jsonl');identity=lambda r:(r['request_id'],r['world_id'],r['method'],r['case_id'])
 oi={identity(r):r for r in original};assert len(oi)==len(original)==len(pred)
 changed=[(r,oi[identity(r)])for r in pred if r['status']!=oi[identity(r)]['status']]
 if policy=='old':assert not changed,'Baseline does not reproduce original prediction statuses'
 write_rows(folder/'prediction_delta.jsonl',[{'original_status':o['status'],**r}for r,o in changed])
 rec={'utc':now(),'stage':stage,'dataset':dataset,'policy':policy,'topology':topo,'addressing':addr,'mode':mode,'cases':len(cases),'candidate_count':len(responses),'compilations':len(construction),'prediction_cells':len(pred),'planned_grid':[list(g) for g in groups],'prediction_statuses':dict(collections.Counter(r['status']for r in pred)),'changed_prediction_cells':len(changed),'reference_decisions_loaded':False,'external_model_calls':0,'new_native_execution':False,'request_inventory_sha256':sha(inventory),'cases_sha256':sha(cpath),'prediction_sha256':sha(folder/'predictions.jsonl'),'frontend_freeze_sha256':sha(STUDY/'plans/FRONTEND_FREEZE.json'),'runner_sha256':sha(__file__),'designation':'retrospective retained-candidate frontend intervention; not new model confirmation'}
 write(folder/'RECEIPT.json',rec);print(stage,policy,'predictions',len(pred),'changed',len(changed),flush=True)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--stage');ap.add_argument('--policy');args=ap.parse_args()
 for rel,h in load(STUDY/'plans/FRONTEND_FREEZE.json')['files'].items():assert sha(STUDY/rel)==h
 for stage,run,data,mode in STAGES:
  if args.stage and args.stage!=stage:continue
  for policy in POLICIES:
   if args.policy and args.policy!=policy:continue
   execute(stage,run,data,mode,policy)
if __name__=='__main__':main()
