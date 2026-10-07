#!/usr/bin/env python3
"""Unpack byte-preserved inputs and produce an explicit exposure/split inventory."""
from pathlib import Path
import argparse
from common_handoff import ROOT,sha,load,write,unpack,kit_path,new_out

def main():
    p=argparse.ArgumentParser();p.add_argument('--work',required=True,type=Path);a=p.parse_args()
    expected=load(ROOT/'inputs/INPUT_HASHES.json')
    for name,h in expected.items():
        if sha(ROOT/'inputs'/name)!=h: raise ValueError(f'Input hash mismatch: {name}')
    work=new_out(a.work)
    unpack(ROOT/'inputs/EDBT_R18_CPU_RESULTS.zip',work/'native')
    unpack(ROOT/'inputs/EDBT_R19_COHERENCE_SOURCE.zip',work/'manuscript')
    kit=kit_path(work)
    rows=load(kit/'runs/r18_cpu_01/native/sweep/selection_before_execution.json')['cases']
    tasks=[]
    for r in rows:
        if r['version']!='v1': continue
        n=int(r['task_id'].split('_')[-1]); suite=r['suite']
        split=('development' if n<10 else 'prospective_contract_test') if suite!='workspace' else 'replay_regression_only'
        if suite=='slack' and n>=17:split='compositional_transfer_secondary'
        tasks.append({**r,'split':split,'prior_exposure':'ALL_TASKS_SEEN_IN_R18_NATIVE_CENSUS',
                      'not_an_unseen_benchmark':True})
    assert sum(x['split']=='development' for x in tasks)==30
    assert sum(x['split']=='prospective_contract_test' for x in tasks)==23
    assert sum(x['split']=='compositional_transfer_secondary' for x in tasks)==4
    write(work/'TASK_EXPOSURE_AND_SPLIT.json',tasks)
    write(work/'INPUT_RECEIPT.json',{'hashes':expected,'kit':str(kit.resolve()),
        'status':'INPUTS_PREPARED_NO_NEW_EXPERIMENT','note':'Contract-test tasks are new to R11 contract construction, not unexposed benchmark tasks.'})
    print('Prepared:',work);print('Native kit:',kit)
if __name__=='__main__':main()
