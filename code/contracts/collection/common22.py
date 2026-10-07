"""Portable artifacts; R21 is immutable upstream authority."""
import datetime, hashlib, json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
R21=ROOT/'baseline_r21' if (ROOT/'baseline_r21').exists() else ROOT.parent/'edbt_r21_followup'
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def canonical_sha(x):return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def rows(p):return [json.loads(s) for s in Path(p).read_text().splitlines() if s.strip()]
def write(p,x):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def write_rows(p,x):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(''.join(json.dumps(v,ensure_ascii=False)+'\n' for v in x))
