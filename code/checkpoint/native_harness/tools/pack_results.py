#!/usr/bin/env python3
"""Pack only the specified experiment output directory, not an environment."""
import argparse,hashlib,json,zipfile
from pathlib import Path
from common import ROOT,sha,encode
p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--zip',type=Path,required=True);a=p.parse_args();folder=a.run.resolve()
if not folder.is_dir():raise SystemExit('Missing run directory')
if a.zip.exists():raise SystemExit('Output ZIP exists')
files=[f for f in folder.rglob('*') if f.is_file() and f.suffix in ['.json','.jsonl','.csv','.txt','.log'] and f.name not in ['.env']]
manifest={f.relative_to(folder).as_posix():sha(f) for f in files}
with zipfile.ZipFile(a.zip,'x',zipfile.ZIP_DEFLATED) as z:
 for f in files:z.write(f,'run/'+f.relative_to(folder).as_posix())
 z.writestr('RESULT_FILE_MANIFEST.json',encode(manifest))
 for name in ['STUDY_FREEZE.json','FOLLOWUP_SOURCE_FREEZE.json','INPUT_PROVENANCE.json']:
  z.write(ROOT/name,name)
Path(str(a.zip)+'.sha256').write_text(sha(a.zip)+'  '+a.zip.name+'\n')
print(a.zip)
