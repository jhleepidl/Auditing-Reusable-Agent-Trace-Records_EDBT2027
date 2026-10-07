import unittest,copy
from typing import Any
from pydantic import BaseModel
from common21 import capture,digest,transported,identity
from ablation_reader import *

class Leaf(BaseModel):value:int
class Root(BaseModel):
    arbitrary:Any
    typed:Leaf
    ordered:dict[str,Leaf]
class Readers(unittest.TestCase):
    def fixture(self,shared=True):
        a=Leaf(value=3);b=a if shared else Leaf(value=3)
        return Root.model_construct(arbitrary=a,typed=b,ordered={'z':a,'a':Leaf(value=8)})
    def test_full_recovers_alias_types_and_order(self):
        x=self.fixture();w=capture(x);y=restore_arm('full_witness',Root,transported(x),w)
        self.assertIs(y.arbitrary,y.typed);self.assertIs(y.typed,y.ordered['z']);self.assertEqual(list(y.ordered),['z','a']);self.assertEqual(capture(y),w)
    def test_type_order_does_not_guess_aliases(self):
        x=self.fixture();y=restore_arm('type_order',Root,transported(x),capture(x))
        self.assertIsInstance(y.arbitrary,Leaf);self.assertIsNot(y.arbitrary,y.typed);self.assertEqual(list(y.ordered),['z','a'])
    def test_alias_endpoint_type_without_order(self):
        x=self.fixture();w=capture(x);w.pop('model_types');w.pop('dict_orders')
        y=restore_arm('alias_endpoint_types',Root,transported(x),w)
        self.assertIsInstance(y.arbitrary,Leaf);self.assertIs(y.arbitrary,y.typed);self.assertEqual(list(y.ordered),['a','z'])
    def test_equal_independent_values_remain_independent(self):
        x=self.fixture(False);y=restore_arm('full_witness',Root,transported(x),capture(x));self.assertIsNot(y.arbitrary,y.typed)
    def test_reject_mismatched_source_and_values(self):
        x=self.fixture();p=transported(x);w=capture(x)
        for key,value in [('snapshot_sha256','bad'),('native_source_revision','bad')]:
            wrong=copy.deepcopy(w);wrong[key]=value
            with self.assertRaises(UnsupportedAblation):restore_arm('alias_endpoint_types',Root,p,wrong)
    def test_reject_unequal_alias_and_self_link(self):
        x=self.fixture();p=transported(x);w=capture(x)
        wrong=copy.deepcopy(w);wrong['aliases'][0]['path']=copy.deepcopy(wrong['aliases'][0]['target'])
        with self.assertRaises(UnsupportedAblation):restore_arm('alias_endpoint_types',Root,p,wrong)
        p['typed']['value']=4;w['snapshot_sha256']=digest(p)
        with self.assertRaises(UnsupportedAblation):restore_arm('alias_endpoint_types',Root,p,w)
    def test_input_and_witness_immutable(self):
        x=self.fixture();p=transported(x);w=capture(x);before=copy.deepcopy((p,w));restore_arm('full_witness',Root,p,w);self.assertEqual((p,w),before)
    def test_pickle_preserves_graph_and_independence(self):
        for shared in (True,False):
            x=self.fixture(shared);c=capture_live(x)
            try:y=restore_live(c);self.assertEqual(capture(y),capture(x));self.assertEqual(y.arbitrary is y.typed,shared)
            finally:release(c)
    def test_external_bytes_and_mutated_capability_refused(self):
        with self.assertRaises(UnsupportedAblation):restore_live(b'external pickle')
        c=capture_live(self.fixture())
        try:
            c.payload+=b'changed'
            with self.assertRaises(UnsupportedAblation):restore_live(c)
        finally:release(c)
if __name__=='__main__':unittest.main()
