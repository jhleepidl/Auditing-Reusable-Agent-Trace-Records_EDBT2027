"""Synthetic infrastructure unit tests. These are NOT empirical paper results."""
import sys,unittest,tempfile,json,zipfile,datetime
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from pydantic import BaseModel,Field,model_validator
from typed_restore import checked_restore,UnsupportedSnapshot
from score_contracts import compare
from make_contract_requests import literal_prompt
from common_handoff import unpack,sha,write_jsonl,read_jsonl,new_out

class Item(BaseModel):
    date:datetime.datetime
    value:int
class Snapshot(BaseModel):
    initial_items:list[Item]
    items:dict[str,Item]=Field(default_factory=dict)
    optional:str|None=None
    @model_validator(mode='after')
    def reset_to_initial(self):
        self.items={str(i):x for i,x in enumerate(self.initial_items)}
        return self

class ReaderTests(unittest.TestCase):
    def payload(self):
        return {'initial_items':[{'date':'2024-01-01T10:00:00','value':1}],
                'items':{'0':{'date':'2024-01-01T10:00:00','value':9}},'optional':None}
    def test_native_constructor_drifts_but_reader_preserves(self):
        p=self.payload();self.assertNotEqual(Snapshot.model_validate(p).model_dump(mode='json'),p)
        restored=checked_restore(Snapshot,p);self.assertEqual(restored.model_dump(mode='json'),p)
    def test_nested_types_restored(self):
        self.assertIsInstance(checked_restore(Snapshot,self.payload()).items['0'].date,datetime.datetime)
    def test_reader_does_not_mutate_input(self):
        p=self.payload();r=checked_restore(Snapshot,p);r.items['0'].value=100
        self.assertEqual(p['items']['0']['value'],9)
    def test_unknown_fields_blocked(self):
        p=self.payload();p['new_field']=1
        with self.assertRaises(UnsupportedSnapshot):checked_restore(Snapshot,p)
    def test_missing_required_blocked(self):
        p=self.payload();del p['initial_items']
        with self.assertRaises(UnsupportedSnapshot):checked_restore(Snapshot,p)
    def test_invalid_scalar_blocked(self):
        p=self.payload();p['items']['0']['date']='not-a-date'
        with self.assertRaises(UnsupportedSnapshot):checked_restore(Snapshot,p)
    def test_scalar_coercion_not_claimed_lossless(self):
        p=self.payload();p['items']['0']['value']='9'
        with self.assertRaises(UnsupportedSnapshot):checked_restore(Snapshot,p)

class MetricTests(unittest.TestCase):
    def gold(self):
        return [{'case_id':str(i),'task_key':'synthetic/task','scope_id':'demo-field',
                 'reference_status':s,'input_sha256':'unit-test-only','reference_evidence':['synthetic-obligation']}
                for i,s in enumerate(['pass','fail','unknown'])]
    def preds(self):
        return [{'method':m,'model':'synthetic-model','seed':1,'case_id':str(i),'scope_id':'demo-field',
                 'input_sha256':'unit-test-only','status':s}
                for m,vals in [('baseline',['pass','pass','pass']),('abstain',['unknown']*3)] for i,s in enumerate(vals)]
    def runmetric(self,p=None,g=None):return compare(self.gold() if g is None else g,self.preds() if p is None else p,['baseline','abstain'],['synthetic-model'],[1],bootstrap=100)
    def test_all_unknown_is_not_useful_retention(self):
        r=self.runmetric();a=r['per_seed'][1]
        self.assertEqual(a['false_pass_rate'],0);self.assertEqual(a['valid_retention'],0);self.assertEqual(a['decisive_coverage'],0)
    def test_missing_cells_fail(self):
        with self.assertRaises(ValueError):self.runmetric(self.preds()[:-1])
    def test_duplicate_cells_fail(self):
        p=self.preds();p.append(p[0])
        with self.assertRaises(ValueError):self.runmetric(p)
    def test_input_hash_mismatch_fails(self):
        p=self.preds();p[0]['input_sha256']='bad'
        with self.assertRaises(ValueError):self.runmetric(p)
    def test_scope_mismatch_fails(self):
        p=self.preds();p[0]['scope_id']='full-task'
        with self.assertRaises(ValueError):self.runmetric(p)
    def test_empty_reference_fails(self):
        with self.assertRaises(ValueError):self.runmetric([],[])
    def test_unresolved_not_promoted_to_truth(self):self.assertEqual(self.runmetric()['per_seed'][0]['unresolved_reference_promoted_to_pass'],1)

class InputTests(unittest.TestCase):
    def test_zip_slip_blocked(self):
        with tempfile.TemporaryDirectory() as t:
            z=Path(t)/'bad.zip'
            with zipfile.ZipFile(z,'w') as f:f.writestr('../escape.txt','x')
            with self.assertRaises(ValueError):unpack(z,Path(t)/'out')
    def test_output_dirs_no_overwrite(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(FileExistsError):new_out(Path(t))
    def test_prompt_only_static_extraction(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'task.py';p.write_text('raise RuntimeError("MUST NOT EXECUTE")\nclass UserTask0:\n    URL="example.org"\n    PROMPT=f"Read {URL}."\n    def utility(self):return False\n')
            self.assertEqual(literal_prompt(p,'UserTask0'),'Read example.org.')
    def test_prompt_calls_not_executed(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'task.py';p.write_text('class UserTask0:\n    PROMPT=eval("1+1")\n')
            with self.assertRaises(ValueError):literal_prompt(p,'UserTask0')
    def test_combined_prompt_static_extraction(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'task.py';p.write_text('class UserTask0:\n    PROMPT="A"\nclass UserTask1:\n    PROMPT="B"\nx.create_combined_task("UserTask2", s.user_tasks["user_task_0"], s.user_tasks["user_task_1"])\n')
            self.assertEqual(literal_prompt(p,'UserTask2'),'Perform the following tasks in the order they are given: 1. A 2. B')
    def test_jsonl_roundtrip(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'rows.jsonl';rows=[{'text':'한글','status':'unknown'}]
            write_jsonl(p,rows);self.assertEqual(read_jsonl(p),rows)
if __name__=='__main__':unittest.main()
