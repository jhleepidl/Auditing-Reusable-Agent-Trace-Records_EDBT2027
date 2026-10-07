#!/usr/bin/env python3
"""Verify handoff file inventory/SHA256; not evidence of experiment success."""
import json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def main():
    m=json.loads((ROOT/'MANIFEST.json').read_text())['files']
    actual={str(p.relative_to(ROOT)) for p in ROOT.rglob('*') if p.is_file()
            and '__pycache__' not in p.parts and p.name!='MANIFEST.json'}
    if actual!=set(m):raise ValueError(f'Inventory differs: missing={set(m)-actual}, extra={actual-set(m)}')
    for rel,h in m.items():
        if sha(ROOT/rel)!=h:raise ValueError('SHA256 mismatch: '+rel)
    print(f'PASS_HANDOFF_FILE_INTEGRITY: {len(m)} files; not a native experiment result')
if __name__=='__main__':main()
