"""R23 explicit-public-view / DAG-order frontend.

Only normalizes node order and publishes exact metadata already supplied in the
R22 request. Delegates all operations/budgets/scalar typing to frozen R22 code.
No task IDs, answers, references, predictions, native observations, or providers
are read. Every new view is bound to the original scope and annotation hashes.
"""
from __future__ import annotations
import sys,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from common import v2,digest,sha
VERSION='r23.cpu.frontend.1'
ALIASES=('common_scope','public_scaffold','endpoints','contract_template')

class TopologyError(ValueError): pass

def order_dag(annotation):
 a=copy.deepcopy(annotation)
 nodes=a.get('nodes',[])
 if not isinstance(nodes,list):raise TopologyError('nodes_array_required')
 ids=[n.get('id') for n in nodes]
 if any(not isinstance(x,str) for x in ids):raise TopologyError('node_id_string_required')
 if len(set(ids))!=len(ids):raise TopologyError('duplicate_node_id')
 if any(not isinstance(n.get('args'),list) or any(not isinstance(x,str) for x in n['args']) for n in nodes):
  raise TopologyError('node_argument_ids_required')
 missing=sorted({x for n in nodes for x in n['args']}-set(ids))
 if missing:raise TopologyError('missing_node_reference:'+','.join(missing))
 done=set();pending=set(ids);seq=[]
 while pending:
  ready=[n for n in nodes if n['id'] in pending and set(n['args']) <= done]
  if not ready:raise TopologyError('cyclic_node_reference')
  for n in ready:seq.append(n);done.add(n['id']);pending.remove(n['id'])
 a['nodes']=seq
 return a,{'changed':[n['id'] for n in seq]!=ids,'original_order':ids,'effective_order':[n['id'] for n in seq]}

def public_scope_view(scope):
 if any(name in scope for name in ALIASES):raise ValueError('public_metadata_alias_collision')
 s=copy.deepcopy(scope);scaffold=v2.build_scaffold(scope)
 s['common_scope']=copy.deepcopy(scope)
 s['public_scaffold']=copy.deepcopy(scaffold)
 s['endpoints']=copy.deepcopy(scaffold['endpoints'])
 s['contract_template']=copy.deepcopy(scaffold['contract_template'])
 return s

def compile_annotation(annotation,packet,public_scope,*,mode='derived',public_facts=None,topology=True,addressing=True):
 before=digest(annotation)
 try:
  effective,order=order_dag(annotation) if topology else (copy.deepcopy(annotation),{'changed':False})
  view=public_scope_view(public_scope) if addressing else public_scope
  result=v2.compile_annotation(effective,packet,view,mode=mode,public_facts=public_facts)
  result.setdefault('provenance',{})['frontend']={
   'version':VERSION,'source_sha256':sha(__file__),
   'original_annotation_sha256':before,'effective_annotation_sha256':digest(effective),
   'original_scope_sha256':digest(public_scope),'effective_scope_view_sha256':digest(view),
   'scaffold_sha256':digest(v2.build_scaffold(public_scope)),
   'topology':topology,'addressing':addressing,'order':order,
   'aliases':list(ALIASES) if addressing else [],
   'scope_view_is_new_derived_artifact':bool(addressing),'ordinary_interpreter_unchanged':True}
  return result
 except (TopologyError,ValueError,KeyError,TypeError) as e:
  return {'status':'error','contract':None,'diagnostics':[{'kind':'frontend_error','reason':str(e)}],
          'provenance':{'frontend':{'version':VERSION,'source_sha256':sha(__file__),'original_annotation_sha256':before,
           'original_scope_sha256':digest(public_scope),'topology':topology,'addressing':addressing}}}
