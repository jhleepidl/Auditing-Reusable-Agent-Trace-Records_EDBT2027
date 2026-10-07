"""Local CPU study helpers. No network, provider, or reference imports."""
from __future__ import annotations
import os,sys,json,hashlib,importlib.util,datetime
from pathlib import Path
sys.dont_write_bytecode=True
STUDY=Path(__file__).resolve().parents[1]
UPSTREAM=Path(os.environ.get('R22_ROOT', str(STUDY/'inputs/R22_subset'))).expanduser().resolve()
if not (UPSTREAM/'derivation_v2/runtime.py').is_file():
 raise FileNotFoundError('Missing R22 inputs: use the bundled inputs/R22_subset or set R22_ROOT to an extracted EDBT_R22_SOURCE directory.')
def load(p): return json.loads(Path(p).read_text())
def rows(p): return [json.loads(s) for s in Path(p).read_text().splitlines() if s.strip()]
def canonical(x): return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def digest(x): return hashlib.sha256(canonical(x)).hexdigest()
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def write_rows(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(''.join(json.dumps(a,ensure_ascii=False,allow_nan=False)+'\n' for a in x))
def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def module(name,path):
 s=importlib.util.spec_from_file_location(name,str(path));m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
v2=module('r23_frozen_v2',UPSTREAM/'derivation_v2/runtime.py')
ex=module('r23_frozen_executor',UPSTREAM/'repair/method_v3/contract_executor.py')

def public():return {(r['task_key'],r['world_id']):r for r in load(UPSTREAM/'source_view/public_packets.json')}
def facts():
 start=load(UPSTREAM/'runs/confirmation_v1/PROVIDER_START.json')
 return rows(UPSTREAM/start['request_inventory_relative_path'])[0]['input']['public_facts']
