import sys,copy,unittest
from pathlib import Path
S=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(S/'tools'),str(S/'method')]
from common import *
from frontend import order_dag,public_scope_view,compile_annotation

class FrontendTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.pub=public();cls.facts=facts()
 def setUp(self):
  self.r=self.pub['travel/user_task_14',0];self.scope=self.r['scope'];self.packet=self.r['packet'];self.ann=load(S/'programs/travel__user_task_14.json')
 def run_ann(self,a,**kw):return compile_annotation(a,self.packet,self.scope,public_facts=self.facts,**kw)
 def test_canonical_contract_preserved(self):
  for (task,w),r in self.pub.items():
   a=load(S/'programs'/(task.replace('/','__')+'.json'))
   old=v2.compile_annotation(a,r['packet'],r['scope'],public_facts=self.facts)
   new=compile_annotation(a,r['packet'],r['scope'],public_facts=self.facts)
   self.assertEqual((old['status'],old['contract']),(new['status'],new['contract']))
 def test_reverse_valid_dag(self):
  a=copy.deepcopy(self.ann);a['nodes'].reverse()
  self.assertEqual(self.run_ann(a)['contract'],self.run_ann(self.ann)['contract'])
 def test_order_idempotent(self):
  a=copy.deepcopy(self.ann);a['nodes'].reverse();x,_=order_dag(a);y,info=order_dag(x)
  self.assertEqual(x,y);self.assertFalse(info['changed'])
 def test_no_node_operand_change(self):
  a=copy.deepcopy(self.ann);a['nodes'].reverse();x,_=order_dag(a)
  self.assertEqual({n['id']:n for n in x['nodes']},{n['id']:n for n in a['nodes']});self.assertEqual(x['operands'],a['operands'])
 def test_duplicate_denied(self):
  a=copy.deepcopy(self.ann);a['nodes'].append(a['nodes'][0]);self.assertIn('duplicate_node_id',self.run_ann(a)['diagnostics'][0]['reason'])
 def test_missing_denied(self):
  a=copy.deepcopy(self.ann);a['nodes'][1]['args']=['missing'];self.assertIn('missing_node_reference',self.run_ann(a)['diagnostics'][0]['reason'])
 def test_cycle_denied(self):
  a=copy.deepcopy(self.ann);a['nodes'][0]['args']=[a['nodes'][-1]['id']];self.assertIn('cyclic_node_reference',self.run_ann(a)['diagnostics'][0]['reason'])
 def test_immutable_inputs(self):
  a=copy.deepcopy(self.ann);q=copy.deepcopy(self.scope);p=copy.deepcopy(self.packet);self.run_ann(a)
  self.assertEqual(q,self.scope);self.assertEqual(p,self.packet);self.assertEqual(a,self.ann)
 def test_scope_fields_preserved(self):
  view=public_scope_view(self.scope)
  for k,v in self.scope.items():self.assertEqual(view[k],v)
 def test_exact_public_aliases(self):
  view=public_scope_view(self.scope);s=v2.build_scaffold(self.scope)
  self.assertEqual(view['common_scope'],self.scope);self.assertEqual(view['public_scaffold'],s)
  self.assertEqual(view['endpoints'],s['endpoints']);self.assertEqual(view['contract_template'],s['contract_template'])
 def test_collision_denied(self):
  s=copy.deepcopy(self.scope);s['endpoints']={'injected':'value'}
  self.assertEqual(compile_annotation(self.ann,self.packet,s)['status'],'error')
 def test_original_scope_path_equivalence(self):
  a=copy.deepcopy(self.ann)
  for node in a['nodes']:
   if node['op']=='source' and node['params']['root']=='request':continue
  # Scope-only read aliases are tested on a query entity metadata endpoint.
  r=self.pub['banking/user_task_1',0];a=load(S/'programs/banking__user_task_1.json');b=copy.deepcopy(a)
  for node in b['nodes']:
   if node['op']=='source' and node['params']['root']=='scope':node['params']['pointer']='/common_scope'+node['params']['pointer']
  x=compile_annotation(a,r['packet'],r['scope'],public_facts=self.facts);y=compile_annotation(b,r['packet'],r['scope'],public_facts=self.facts)
  self.assertEqual(x['contract'],y['contract']);self.assertEqual(x['status'],'ok')
 def test_endpoints_aliases_read(self):
  view=public_scope_view(self.scope);sc=v2.build_scaffold(self.scope)
  for k,m in sc['endpoints'].items():
   self.assertEqual(v2.core.get(view,'/endpoints/'+k),m)
   self.assertEqual(v2.core.get(view,'/public_scaffold/endpoints/'+k),m)
 def test_no_fuzzy_path(self):
  a=copy.deepcopy(self.ann);a['nodes'][1]['params']['pointer']='/car_rental/company_lits'
  self.assertEqual(self.run_ann(a)['status'],'unknown')
 def test_private_root_absent(self):
  a=copy.deepcopy(self.ann);a['nodes'][1]['params']={'root':'scope','pointer':'/private_reference'}
  self.assertEqual(self.run_ann(a)['status'],'unknown')
 def test_missing_observation_not_read_by_compiler(self):
  # Compiler has no argument for post_state/output/reference.
  import inspect
  self.assertFalse(set(inspect.signature(compile_annotation).parameters)&{'reference','post_state','output','gold'})
 def test_literal_passthrough(self):
  a=copy.deepcopy(self.ann);a['nodes']=[]
  for v in a['operands'].values():v['node']=None
  old=v2.compile_annotation(a,self.packet,self.scope,mode='literal',public_facts=self.facts)
  new=self.run_ann(a,mode='literal')
  self.assertEqual(old['contract'],new['contract'])
 def test_no_type_coercion(self):
  a=copy.deepcopy(self.ann);a['nodes'][2]['op']='parse_decimal';a['nodes'][2]['params']={}
  self.assertEqual(self.run_ann(a)['status'],'unknown')
 def test_missing_source(self):
  p=copy.deepcopy(self.packet);p['initial_state']=None
  self.assertEqual(compile_annotation(self.ann,p,self.scope,public_facts=self.facts)['status'],'unknown')
 def test_annotations_really_source_derived(self):
  for path in (S/'programs').glob('*.json'):
   for n in load(path)['nodes']:
    if n['op']=='constant':self.assertIn(n['params']['value'],[0,1,100,True,False])
if __name__=='__main__':unittest.main(verbosity=2)
