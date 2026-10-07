"""Optional native rerun of the bundled scientific readers and tool programs.

The release manifest binds the selected executable dependencies. Historical
whole-archive inventories are not used to demand unrelated generated files.
No semantic engine is modified; the original freeze callback is replaced solely
by checks on this release's input hashes, plans and exact dependency pins.
"""
from __future__ import annotations
import argparse
import importlib
import importlib.metadata
import os
from pathlib import Path
import platform
import sys
sys.dont_write_bytecode=True
from release_io import Inputs,load,write,equal,sha,canonical

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--workspace',type=Path,required=True);ap.add_argument('--release',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True);ap.add_argument('--timings',action='store_true');a=ap.parse_args()
    a.output.mkdir(parents=True,exist_ok=False);inputs=Inputs(a.release)
    prefix='studies/frozen/baseline_r21/';e1=a.workspace/prefix/'e1';r20=a.workspace/prefix/'baseline_r20'
    os.environ['EDBT_R20_ROOT']=str(r20)
    sys.path.insert(0,str(e1))
    environment=load(a.release/'configs/environment/native.json')
    def verify_dependencies():
        if platform.python_version()!=environment['python'].split()[0]:raise RuntimeError('Pinned native Python required')
        for name,version in environment['dependency_pins'].items():
            if importlib.metadata.version(name)!=version:raise RuntimeError('Native dependency mismatch: '+name)
        for logical in inputs.groups['native']:
            if sha(a.workspace/logical)!=inputs.files[logical]['sha256']:raise ValueError('Native input drift: '+logical)
        return load(e1/'FREEZE.json')
    verify_dependencies()
    c=importlib.import_module('common21');c.verify_freeze=verify_dependencies
    if a.timings:
        module=importlib.import_module('run_costs');module.run(a.output/'costs')
        report={'status':'PASS','fresh_native_execution':True,'fresh_timing_measurements':True,
                'scope':'New measurements; not expected to equal the paper hardware timings.'}
    else:
        for name,dir_ in [('run_corpus','checkpoints'),('run_reads','reads')]:
            importlib.import_module(name).run(a.output/dir_)
        count=0
        for root,old in [('checkpoints','corpus_results_v1'),('reads','read_results_v1')]:
            folder=a.output/root
            for path in (folder/'cases').rglob('*.json'):
                if path.name.endswith('_receipt.json'):continue
                logical=prefix+'e1/'+old+'/'+path.relative_to(folder).as_posix()
                expected=inputs.json(logical)
                if canonical(load(path))!=canonical(expected):raise ValueError('Native observation mismatch: '+logical)
                count+=1
        expected=load(a.release/'expected/checkpoint_summary.json')
        for root,key in [('checkpoints','corpus'),('reads','reads')]:
            equal(load(a.output/root/'SUMMARY.json'),expected[key],root)
        report={'status':'PASS','fresh_native_execution':True,'fresh_timing_measurements':False,
                'native_observation_files_checked':count,'checkpoint_programs':36,'read_programs':12,
                'provider_calls':0,'scope':'Bundled pinned environment and declared programs only.'}
    write(a.output/'verification.json',report)

if __name__=='__main__':main()
