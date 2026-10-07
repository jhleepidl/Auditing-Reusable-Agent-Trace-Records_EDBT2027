"""Declared serialization-shape admission; never rewrites a contract."""
from contract_engine import parts,kind,preflight

def expand(node,root,seen=()):
 if not isinstance(node,dict):return []
 if '$ref' in node:
  ref=node['$ref']
  if not ref.startswith('#/') or ref in seen:return []
  target=root
  for k in parts(ref[1:]):
   if not isinstance(target,dict) or k not in target:return []
   target=target[k]
  return expand(target,root,seen+(ref,))
 if 'anyOf' in node or 'oneOf' in node:
  return [b for n in node.get('anyOf',node.get('oneOf',[])) for b in expand(n,root,seen)]
 if 'allOf' in node:return []
 return [node] if node.get('type') in ['object','array','string','number','integer','boolean','null'] else []

def resolve(schema,tokens):
 nodes=expand(schema,schema)
 for token in tokens:
  following=[]
  for node in nodes:
   t=node.get('type')
   if t=='object':
    props=node.get('properties',{});additional=node.get('additionalProperties')
    if token=='*':children=list(props.values())+([additional] if isinstance(additional,dict) else [])
    elif token in props:children=[props[token]]
    elif isinstance(additional,dict):children=[additional]
    else:children=[]
   elif t=='array' and (token=='*' or token.isdigit()):children=[node.get('items')]
   else:children=[]
   following.extend(b for c in children for b in expand(c,schema))
  nodes=following
 return nodes

def value_fits(value,node,root):
 t=node.get('type');k=kind(value)
 if t=='integer':return k=='number' and float(value).is_integer()
 if k!=t:return False
 if k=='array':
  items=expand(node.get('items'),root)
  return bool(items) and all(any(value_fits(v,n,root) for n in items) for v in value)
 return True

def compatible(node,p,root):
 op=p['operator'];t=node.get('type');v=p['value']
 if op=='exists':return v is True
 if op=='equals':return value_fits(v,node,root)
 if op in ['contains','date','month_day']:return t=='string' and kind(v)=='string'
 if op=='member':return t=='array' and any(value_fits(v,n,root) for n in expand(node.get('items'),root))
 if op in ['gt','ge','lt','le']:return t in ['integer','number'] and kind(v)=='number'
 return False

def schema_admission(annotation,schema):
 if annotation['classification']!='state':return {'admitted':False,'issues':[{'code':'non_state_not_executable'}]}
 issues=[];witness=[]
 if not annotation['state_predicates']:issues.append({'code':'empty_state_contract'})
 for i,p in enumerate(annotation['state_predicates']):
  def issue(code):issues.append({'predicate':i,'path':p['path'],'code':code})
  try:t=parts(p['path'])
  except ValueError:issue('invalid_pointer');continue
  if t.count('*')>1:issue('unsupported_multiple_wildcards');continue
  if p['selector'] and '*' not in t:issue('selector_without_entity_binding')
  nodes=resolve(schema,t)
  witness.append({'predicate':i,'path':p['path'],'declared_types':sorted({n['type'] for n in nodes})})
  if not nodes:issue('no_declared_path_shape')
  elif not any(compatible(n,p,schema) for n in nodes):issue('declared_type_incompatible')
  if '*' in t:
   prefix=t[:t.index('*')+1]
   for selector in p['selector']:
    values=resolve(schema,prefix+[selector['field']])
    if not values:issue('no_declared_selector_shape')
    elif not any(value_fits(selector['value'],n,schema) for n in values):issue('declared_selector_type_incompatible')
 return {'admitted':not issues,'issues':issues,'schema_path_witnesses':witness}

def hybrid_admission(annotation,pre,schema):
 observed=preflight(annotation,pre);declared=schema_admission(annotation,schema)
 # Schema evidence can discharge only lack-of-example issues, never an
 # observed type conflict, unsupported binding or a declared incompatibility.
 remaining=[x for x in observed['issues'] if x['code'] not in ['shape_unverified','selector_field_unverified']]
 return {'admitted':declared['admitted'] and not remaining,'issues':remaining+declared['issues'],'observed_admitted':observed['admitted'],'schema_admitted':declared['admitted'],'discharged_observed_issues':[x for x in observed['issues'] if x['code'] in ['shape_unverified','selector_field_unverified']] if declared['admitted'] else [],'schema_path_witnesses':declared.get('schema_path_witnesses',[])}
