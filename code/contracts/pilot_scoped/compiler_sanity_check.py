"""Oracle-assisted representation diagnostic, excluded from builder effectiveness."""
import argparse, collections, copy, json, sys
from pathlib import Path
from common21 import ROOT, BASE, load, rows, write, write_rows, sha, now, canonical_sha
sys.path.insert(0,str(ROOT/'e2/method_v1'));import contract_executor as ex
def main():
 p=argparse.ArgumentParser();p.add_argument('--cases',type=Path,required=True);p.add_argument('--reference',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.cases=a.cases.resolve();a.reference=a.reference.resolve();a.out.mkdir(parents=True,exist_ok=False)
 source=ROOT/'e2/reference_author';scope=source/'common_scopes.json';compiler=source/'compiler_sanity/contracts.jsonl';ts={x['task_key']:x for x in load(scope)['tasks']};ps={x['task_key']:x['packet'] for x in load(source/'source_snapshot/task_packets.json')};cs={x['task_key']:x for x in rows(compiler)};gs={x['case_id']:x for x in rows(a.reference)};admissions=[];pred=[];comparisons=collections.Counter();mismatches=[]
 for key,t in ts.items():
  row=cs[key];assert row['scope_sha256']==t['scope_sha256'] and row['source_packet_sha256']==t['source_packet_sha256']
  p=copy.deepcopy(ps[key]);assert canonical_sha(p)==t['source_packet_sha256'];suite=key.split('/')[0]
  p['state_schema']=load(BASE/f'work/native/EDBT_R18_CPU_RESULTS/EDBT_R18_NO_HUMAN_KIT/inputs/r11/schemas/{suite}.json')
  val=ex.validate(row['contract']);assert val['valid'],(key,val)
  for policy in ['scope','scope_source']:
   gate=ex.preflight(row['contract'],t,p,policy);assert gate['admitted']==t['supported'],(key,gate)
   admissions.append({'task_key':key,'supported':t['supported'],'policy':policy,'admission':gate})
 for c in rows(a.cases):
  f=a.cases.parent/c['input_file'];assert sha(f)==c['input_sha256'];d=load(f);key=c['task_key'];t=ts[key];p=copy.deepcopy(ps[key]);suite=key.split('/')[0];p['state_schema']=load(BASE/f'work/native/EDBT_R18_CPU_RESULTS/EDBT_R18_NO_HUMAN_KIT/inputs/r11/schemas/{suite}.json');gold=gs[c['case_id']]
  assert all(gold[k]==c[k] for k in ['scope_id','input_sha256','task_key'])
  for policy in ['scope','scope_source']:
   result=ex.evaluate(cs[key]['contract'],d.get('pre_state'),d.get('post_state'),d.get('output'),public_task=t,packet=p,policy=policy)
   row={'case_id':c['case_id'],'task_key':key,'policy':policy,'reference_status':gold['reference_status'],'status':result['verdict'],'result':result};pred.append(row);comparisons[policy,gold['reference_status'],result['verdict']]+=1
   if result['verdict']!=gold['reference_status']:mismatches.append(row)
 write_rows(a.out/'admissions.jsonl',admissions);write_rows(a.out/'observations.jsonl',pred);write_rows(a.out/'mismatches.jsonl',mismatches)
 write(a.out/'REPORT.json',{'utc':now(),'designation':'oracle-assisted compiler representation diagnostic; not a competitive builder or full-task semantic gold','contracts':len(cs),'supported_admission':sum(r['supported'] for r in admissions)//2,'cases':len(gs),'comparison_cells':len(pred),'confusion':[{ 'policy':k[0],'reference':k[1],'prediction':k[2],'count':n} for k,n in sorted(comparisons.items())],'mismatches':len(mismatches),'input_sha256':{str(p.relative_to(ROOT)):sha(p) for p in [scope,compiler,a.cases,a.reference,ROOT/'e2/method_v1/contract_executor.py']},'unsafe_reference_fail_to_pass':sum(r['reference_status']=='fail' and r['status']=='pass' for r in mismatches)})
 print(json.dumps({'contracts':len(cs),'mismatches':len(mismatches),'confusion':str(dict(comparisons))}))
if __name__=='__main__':main()
