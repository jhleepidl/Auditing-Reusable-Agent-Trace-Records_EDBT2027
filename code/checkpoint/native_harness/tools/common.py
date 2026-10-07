"""Shared local I/O and immutable-study guards (stdlib only)."""
from __future__ import annotations
import hashlib,json,datetime,sys,platform,importlib.metadata
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def encode(x): return (json.dumps(x,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def digest(b): return hashlib.sha256(b).hexdigest()
def write(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(encode(x))
def utc(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def new_out(p):
 p=Path(p).resolve();p.mkdir(parents=True,exist_ok=False);return p
def check_freeze():
 m=load(ROOT/'STUDY_FREEZE.json')
 for name,h in m['files'].items():
  if sha(ROOT/name)!=h:raise RuntimeError('Frozen source/input changed: '+name)
 return m
def environment():
 deps={}
 for x in ['pydantic','docstring-parser','deepdiff','openai','jsonschema']:
  try:deps[x]=importlib.metadata.version(x)
  except importlib.metadata.PackageNotFoundError:deps[x]=None
 return {'python':sys.version,'platform':platform.platform(),'packages':deps}
def text_output(d):
 v=d['output']
 if isinstance(v,str):return v
 return ''.join(b.get('content',b.get('text','')) for b in v if b.get('type')=='text')
