import unittest
from schema_gate import *
def p(path,op,v,selector=None):return dict(path=path,operator=op,value=v,requires_new_entity=False,selector=selector or [])
def a(*ps):return dict(classification='state',state_predicates=list(ps))
class SchemaGateTests(unittest.TestCase):
 def test_dynamic_key(self):
  s={'type':'object','properties':{'web':{'type':'object','additionalProperties':{'type':'string'}}}}
  c=a(p('/web/new','contains','hobby'));g=hybrid_admission(c,{'web':{}},s)
  self.assertTrue(g['admitted']);self.assertFalse(g['observed_admitted'])
 def test_untyped_extra_not_evidence(self):
  s={'type':'object','properties':{},'additionalProperties':True}
  self.assertFalse(schema_admission(a(p('/invented','equals','x')),s)['admitted'])
 def test_empty_typed_collection_selectors(self):
  s={'type':'object','properties':{'sent':{'type':'array','items':{'$ref':'#/$defs/mail'}}},'$defs':{'mail':{'type':'object','properties':{'to':{'type':'string'}}}}}
  c=a(p('/sent/*','exists',True,[dict(field='to',value='A')]))
  self.assertTrue(hybrid_admission(c,{'sent':[]},s)['admitted'])
 def test_observed_conflict_not_repaired(self):
  s={'type':'object','properties':{'a':{'type':'string'}}};c=a(p('/a','equals','x'))
  self.assertTrue(schema_admission(c,s)['admitted']);self.assertFalse(hybrid_admission(c,{'a':{}},s)['admitted'])
 def test_wrong_entity_type_and_binding(self):
  s={'type':'object','properties':{'rows':{'type':'array','items':{'type':'object','properties':{'x':{'type':'number'}}}}}}
  self.assertFalse(schema_admission(a(p('/rows/*','equals','x')),s)['admitted'])
  self.assertFalse(schema_admission(a(p('/rows','exists',True,[dict(field='x',value=1)])),s)['admitted'])
 def test_union_nullable(self):
  s={'type':'object','properties':{'a':{'anyOf':[{'type':'null'},{'type':'string'}]}}}
  self.assertTrue(schema_admission(a(p('/a','equals','x')),s)['admitted']);self.assertFalse(schema_admission(a(p('/a','equals',1)),s)['admitted'])
 def test_member_typed(self):
  s={'type':'object','properties':{'a':{'type':'array','items':{'type':'string'}}}}
  self.assertTrue(schema_admission(a(p('/a','member','x')),s)['admitted']);self.assertFalse(schema_admission(a(p('/a','member',['x'])),s)['admitted'])
 def test_no_alias_and_unsupported_schema(self):
  s={'type':'object','properties':{'sent':{'type':'array','items':{'type':'string'}},'x':{'allOf':[{'type':'string'}]}}}
  self.assertFalse(schema_admission(a(p('/emails/*','exists',True)),s)['admitted']);self.assertFalse(schema_admission(a(p('/x','equals','x')),s)['admitted'])
if __name__=='__main__':unittest.main()
