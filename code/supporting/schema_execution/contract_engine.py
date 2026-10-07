"""Version 1 literal partial-contract interpreter. No aliases or contract repair."""
import json,re,datetime
MISSING=object()
def kind(v):
 if v is None:return 'null'
 if isinstance(v,bool):return 'boolean'
 if isinstance(v,(int,float)):return 'number'
 if isinstance(v,str):return 'string'
 if isinstance(v,list):return 'array'
 return 'object'
def equal(a,b):
 if a is MISSING or b is MISSING:return False
 if kind(a)!=kind(b):return False
 if isinstance(a,list):return len(a)==len(b) and all(equal(x,y) for x,y in zip(a,b))
 if isinstance(a,dict):return a.keys()==b.keys() and all(equal(a[k],b[k]) for k in a)
 return a==b

def parts(path):
 if not isinstance(path,str) or not path.startswith('/') or re.search(r'~(?![01])',path):raise ValueError('invalid pointer')
 return [x.replace('~1','/').replace('~0','~') for x in path[1:].split('/')]
def at(node,tokens):
 for key in tokens:
  if isinstance(node,dict):node=node.get(key,MISSING)
  elif isinstance(node,list) and key.isdigit() and int(key)<len(node):node=node[int(key)]
  else:return MISSING
 return node

def expanded(root,tokens):
 nodes=[root]
 for key in tokens:
  nxt=[]
  for node in nodes:
   if key=='*' and isinstance(node,(dict,list)):nxt.extend(node.values() if isinstance(node,dict) else node)
   else:
    v=at(node,[key])
    if v is not MISSING:nxt.append(v)
  nodes=nxt
 return nodes

def compatible(v,p):
 op=p['operator'];a=kind(v);b=kind(p['value'])
 if op=='exists':return p['value'] is True
 if op=='equals':return a==b
 if op in ('contains','date','month_day'):return a==b=='string'
 if op=='member':return a=='array'
 if op in ('gt','ge','lt','le'):return a==b=='number'
 return False

def atom(v,p):
 op=p['operator'];b=p['value']
 if v is MISSING:return False
 if op=='exists':return b is True
 if not compatible(v,p):return False
 if op=='equals':return equal(v,b)
 if op=='contains':return b.casefold() in v.casefold()
 if op=='member':return any(equal(x,b) for x in v)
 if op in ('date','month_day'):
  try:d=datetime.datetime.fromisoformat(v.replace('Z','+00:00')).date().isoformat()
  except (ValueError,TypeError):return False
  return (d if op=='date' else d[5:])==b
 if op=='gt':return v>b
 if op=='ge':return v>=b
 if op=='lt':return v<b
 if op=='le':return v<=b
 raise ValueError(op)

def preflight(annotation,pre):
 if annotation['classification']!='state':return {'admitted':False,'issues':[{'code':'non_state_not_executable'}]}
 issues=[]
 if not annotation['state_predicates']:issues.append({'code':'empty_state_contract'})
 for i,p in enumerate(annotation['state_predicates']):
  def issue(code):issues.append({'predicate':i,'code':code,'path':p['path']})
  try:t=parts(p['path'])
  except ValueError:issue('invalid_pointer');continue
  if t.count('*')>1:issue('unsupported_multiple_wildcards');continue
  if p['selector'] and '*' not in t:issue('selector_without_entity_binding')
  vals=expanded(pre,t)
  if vals and not any(compatible(v,p) for v in vals):issue('observed_type_incompatible')
  if not vals:
   # An empty collection supports existence of future entities; it does not
   # establish the shape of their fields or selectors.
   prefix=t[:t.index('*')] if '*' in t else t
   collection=at(pre,prefix)
   if not ('*' in t and t[-1]=='*' and p['operator']=='exists' and isinstance(collection,(dict,list)) and not p['selector']):issue('shape_unverified')
  if '*' in t and p['selector']:
   entities=expanded(pre,t[:t.index('*')+1])
   for s in p['selector']:
    seen=[at(e,[s['field']]) for e in entities];seen=[v for v in seen if v is not MISSING]
    if not seen:issue('selector_field_unverified')
    elif not any(kind(v)==kind(s['value']) for v in seen):issue('selector_type_incompatible')
 return {'admitted':not issues,'issues':issues}

def evaluate(annotation,pre,post):
 if annotation['classification']!='state':return {'verdict':'unknown','reason':'query_or_excluded_has_no_state_interpretation','groups':[]}
 predicates=annotation['state_predicates'];groups={};unknown=[]
 if not predicates:return {'verdict':'unknown','reason':'empty_state_contract','groups':[]}
 for i,p in enumerate(predicates):
  try:t=parts(p['path'])
  except ValueError:unknown.append(i);continue
  if t.count('*')>1 or (p['selector'] and '*' not in t):unknown.append(i);continue
  if '*' in t:
   n=t.index('*');key=('entity',tuple(t[:n]),json.dumps(sorted(p['selector'],key=lambda s:s['field']),sort_keys=True))
  else:key=('direct',tuple(t),'')
  groups.setdefault(key,[]).append((i,p,t))
 results=[]
 for (mode,prefix,selector_key),ps in groups.items():
  if mode=='direct':
   ok=all(atom(at(post,t),p) and (not p['requires_new_entity'] or at(pre,t) is MISSING) for _,p,t in ps)
   candidates=1;matched=int(ok)
  else:
   before=at(pre,list(prefix));after=at(post,list(prefix));new=any(p['requires_new_entity'] for _,p,_ in ps)
   if isinstance(after,dict):items=[v for k,v in after.items() if not new or not isinstance(before,dict) or k not in before]
   elif isinstance(after,list):items=after[len(before):] if new and isinstance(before,list) else after
   else:items=[]
   selectors=ps[0][1]['selector'];items=[v for v in items if all(equal(at(v,[s['field']]),s['value']) for s in selectors)]
   matched=sum(all(atom(at(v,t[len(prefix)+1:]),p) for _,p,t in ps) for v in items);candidates=len(items);ok=matched>0
  results.append({'predicate_indices':[i for i,_,_ in ps],'pass':ok,'candidate_count':candidates,'matching_count':matched})
 # Unsupported semantics take precedence: never silently drop an atom.
 verdict='unknown' if unknown else ('pass' if all(x['pass'] for x in results) else 'fail')
 return {'verdict':verdict,'unsupported_predicate_indices':unknown,'groups':results}

def gated(annotation,pre,post):
 gate=preflight(annotation,pre)
 result=evaluate(annotation,pre,post) if gate['admitted'] else {'verdict':'unknown','reason':'contract_not_admitted'}
 return {'gate':gate,'result':result}
