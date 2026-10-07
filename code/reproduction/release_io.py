"""Read immutable inputs and create isolated working directories.

Aliases relocate identical original inputs; gzip is lossless transport, not a
semantic conversion. Expected results are used only after regeneration.
"""
from __future__ import annotations
import gzip
import hashlib
import json
import math
import shutil
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

def load(path: Path) -> Any:
    with path.open(encoding='utf-8') as stream:
        return json.load(stream)

def write(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')

def sha(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def canonical(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')

def safe(root: Path, relative: str) -> Path:
    p = Path(relative)
    if p.is_absolute() or '..' in p.parts:
        raise ValueError('Unsafe relative path: '+relative)
    dest = (root / p).resolve()
    if not dest.is_relative_to(root.resolve()):
        raise ValueError('Path leaves root: '+relative)
    return dest

def equal(actual: Any, expected: Any, where: str = '') -> None:
    """Exact structures/counts; tolerate only floating-point rounding, not changed metrics."""
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or set(actual)!=set(expected):
            raise ValueError('Different keys: '+where)
        for k in expected: equal(actual[k],expected[k],where+'/'+str(k))
    elif isinstance(expected, list):
        if not isinstance(actual,list) or len(actual)!=len(expected):
            raise ValueError('Different list length: '+where)
        for i,(a,b) in enumerate(zip(actual,expected)):equal(a,b,where+'/'+str(i))
    elif isinstance(expected,float):
        if not isinstance(actual,(int,float)) or not math.isclose(actual,expected,rel_tol=1e-12,abs_tol=1e-14):
            raise ValueError(f'Numerical mismatch at {where}: {actual!r} != {expected!r}')
    elif actual != expected:
        raise ValueError(f'Mismatch at {where}: {actual!r} != {expected!r}')

class Inputs:
    def __init__(self,root:Path=ROOT):
        self.root=root.resolve()
        index=load(self.root/'configs/input_layout.json')
        self.files=index['files'];self.groups=index['groups']

    def bytes(self,name:str)->bytes:
        m=self.files[name];p=safe(self.root,m['path'])
        if m.get('encoding')=='gzip':
            # A recorded byte limit also bounds decompression of damaged input.
            with gzip.open(p,'rb') as f:
                b=f.read(m['bytes']+1)
        else:b=p.read_bytes()
        if len(b)!=m['bytes'] or hashlib.sha256(b).hexdigest()!=m['sha256']:
            raise ValueError('Input checksum mismatch: '+name)
        return b

    def json(self,name:str)->Any:return json.loads(self.bytes(name))

    def materialize(self,names:list[str],destination:Path)->int:
        for name in sorted(set(names)):
            target=safe(destination,name)
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(self.bytes(name))
        return len(set(names))

    def verify(self)->dict:
        inventory=load(self.root/'configs/release_manifest.json')['files']
        for rel,meta in inventory.items():
            p=safe(self.root,rel)
            if not p.is_file() or p.stat().st_size!=meta['bytes'] or sha(p)!=meta['sha256']:
                raise ValueError('Release integrity mismatch: '+rel)
        # Check every logical original binding, including compressed files and aliases.
        checked=set()
        for name,m in self.files.items():
            token=(m['path'],m['sha256'])
            if token not in checked:self.bytes(name);checked.add(token)
        return {'status':'PASS','payload_files':len(inventory),'logical_inputs':len(self.files),
                'distinct_input_bindings':len(checked)}
