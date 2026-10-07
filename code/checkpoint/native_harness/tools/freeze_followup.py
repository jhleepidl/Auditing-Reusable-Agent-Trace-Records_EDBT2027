from common import ROOT,write,sha,utc
p=ROOT/'FOLLOWUP_SOURCE_FREEZE.json'
if p.exists():raise SystemExit('Do not overwrite a frozen study version')
files={f.relative_to(ROOT).as_posix():sha(f) for sub in ['tools','protocols'] for f in sorted((ROOT/sub).rglob('*')) if f.is_file() and '__pycache__' not in f.parts and f.suffix!='.pyc'}
write(p,{'frozen_utc':utc(),'status':'Native full-engine and API experiments NOT EXECUTED. Prior saved-state audit is retrospective reanalysis. No external preregistration.','parent_freeze_sha256':sha(ROOT/'STUDY_FREEZE.json'),'files':files})
print(sha(p))
