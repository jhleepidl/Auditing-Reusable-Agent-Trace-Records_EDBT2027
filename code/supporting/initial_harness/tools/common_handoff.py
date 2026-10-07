"""Standard-library helpers. All output directories are append-only run directories."""
from __future__ import annotations
import hashlib, json, pathlib, datetime, zipfile
ROOT = pathlib.Path(__file__).resolve().parents[1]

def sha(path):
    h = hashlib.sha256()
    with pathlib.Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''): h.update(block)
    return h.hexdigest()

def canonical(x):
    return json.dumps(x, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)

def digest(x): return hashlib.sha256(canonical(x).encode()).hexdigest()
def load(p): return json.loads(pathlib.Path(p).read_text(encoding='utf-8'))
def write(p, x):
    p = pathlib.Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(x, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
def utc(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def new_out(p):
    p = pathlib.Path(p); p.mkdir(parents=True, exist_ok=False); return p

def unpack(src, dest):
    dest = pathlib.Path(dest); dest.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(src) as z:
        for i in z.infolist():
            target = (dest / i.filename).resolve()
            if not target.is_relative_to(dest.resolve()): raise ValueError('Unsafe archive path')
            if (i.external_attr >> 16) & 0o170000 == 0o120000: raise ValueError('Archive symlink refused')
        if z.testzip(): raise ValueError('Archive CRC failure')
        z.extractall(dest)

def kit_path(work):
    return pathlib.Path(work) / 'native' / 'EDBT_R18_CPU_RESULTS' / 'EDBT_R18_NO_HUMAN_KIT'

def read_jsonl(p):
    out=[]
    with pathlib.Path(p).open(encoding='utf-8') as f:
        for i,line in enumerate(f,1):
            if line.strip():
                try: out.append(json.loads(line))
                except Exception as e: raise ValueError(f'{p}:{i}: invalid JSON') from e
    return out

def write_jsonl(p, rows):
    p=pathlib.Path(p);p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('x', encoding='utf-8') as f:
        for r in rows: f.write(canonical(r)+'\n')
