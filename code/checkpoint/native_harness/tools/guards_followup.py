from common import ROOT,load,sha

def check_followup():
 p=ROOT/'FOLLOWUP_SOURCE_FREEZE.json'
 if not p.exists():raise RuntimeError('Follow-up source freeze missing')
 m=load(p)
 for name,h in m['files'].items():
  if sha(ROOT/name)!=h:raise RuntimeError('Follow-up implementation changed: '+name)
 return m
