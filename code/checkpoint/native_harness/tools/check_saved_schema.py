#!/usr/bin/env python3
from pathlib import Path
import argparse
from common import ROOT,load,write,new_out,check_freeze,environment
from guards_followup import check_followup

def main(out):
 check_freeze();check_followup();out=new_out(out)
 from jsonschema import Draft202012Validator
 val={s:Draft202012Validator(load(ROOT/f'inputs/r11/schemas/{s}.json')) for s in ['banking','slack','travel']}
 rows=[]
 for c in load(ROOT/'inputs/r11/cases.json'):
  for side in ['pre','post']:
   errors=[{'path':list(e.absolute_path),'rule':e.validator,'message':e.message} for e in val[c['suite']].iter_errors(load(ROOT/c['input_dir']/(side+'_state.json')))]
   rows.append({'suite':c['suite'],'task_id':c['task_id'],'group':c['group'],'case_id':c['case_id'],'side':side,'valid':not errors,'errors':errors})
 write(out/'rows.json',rows);write(out/'SUMMARY.json',{'checks':len(rows),'valid':sum(r['valid'] for r in rows),'format_annotations_asserted':False,'native_engine_executed':False,'semantic_validation':False,'api_calls':0,'human_annotations':0,'environment':environment()})
 print('Schema-valid snapshots:',sum(r['valid'] for r in rows),'/',len(rows))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();main(a.out)
