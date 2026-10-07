#!/usr/bin/env python3
from common import ROOT,sha,write,utc
p=ROOT/'STUDY_FREEZE.json'
if p.exists():raise SystemExit('Freeze already exists; do not overwrite it.')
files={}
for sub in ['tools','inputs','vendor','protocols']:
 for f in sorted((ROOT/sub).rglob('*')):
  if f.is_file() and '__pycache__' not in f.parts and f.suffix!='.pyc':files[f.relative_to(ROOT).as_posix()]=sha(f)
write(p,{'study_id':'R18_NO_HUMAN_LOCAL_V1','frozen_utc':utc(),'external_preregistration':False,'files':files})
print(sha(p))
