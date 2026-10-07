"""Release transport and validation tests; no scientific results are fabricated."""
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'code/reproduction'))
from release_io import Inputs,safe,equal,canonical

class Paths(unittest.TestCase):
    def test_parent_escape(self):
        with self.assertRaises(ValueError):safe(ROOT,'../escape')
    def test_absolute(self):
        with self.assertRaises(ValueError):safe(ROOT,'/tmp/escape')
    def test_inside(self):self.assertEqual(safe(ROOT,'code'),ROOT/'code')
    def test_symlink_escape(self):
        with tempfile.TemporaryDirectory() as a,tempfile.TemporaryDirectory() as b:
            p=Path(a);(p/'out').symlink_to(b)
            with self.assertRaises(ValueError):safe(p,'out/file')

class Equality(unittest.TestCase):
    def test_roundoff(self):equal(1/3,0.33333333333333337)
    def test_changed_metric(self):
        with self.assertRaises(ValueError):equal(.2,.21)
    def test_changed_count(self):
        with self.assertRaises(ValueError):equal(4,3)
    def test_missing_key(self):
        with self.assertRaises(ValueError):equal({}, {'x':1})
    def test_missing_row(self):
        with self.assertRaises(ValueError):equal([1], [1,2])
    def test_nan(self):
        with self.assertRaises(ValueError):equal(float('nan'),1.)
    def test_canonical_order(self):self.assertEqual(canonical({'b':2,'a':1}),canonical({'a':1,'b':2}))

class Transport(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.p=Path(self.tmp.name);(self.p/'configs').mkdir()
        self.b=b'{"x":1}\n';(self.p/'payload.json.gz').write_bytes(gzip.compress(self.b,mtime=0))
        self.meta={'path':'payload.json.gz','bytes':len(self.b),'sha256':hashlib.sha256(self.b).hexdigest(),'encoding':'gzip'}
        (self.p/'configs/input_layout.json').write_text(json.dumps({'files':{'original':self.meta},'groups':{}}))
    def tearDown(self):self.tmp.cleanup()
    def test_exact_gzip(self):self.assertEqual(Inputs(self.p).bytes('original'),self.b)
    def test_tampered_gzip(self):
        (self.p/'payload.json.gz').write_bytes(gzip.compress(b'{"x":2}\n'))
        with self.assertRaises(ValueError):Inputs(self.p).bytes('original')
    def test_bounded_expansion(self):
        (self.p/'payload.json.gz').write_bytes(gzip.compress(self.b*100))
        with self.assertRaises(ValueError):Inputs(self.p).bytes('original')
    def test_alias_copy(self):
        out=self.p/'tmp';Inputs(self.p).materialize(['original'],out)
        self.assertEqual((out/'original').read_bytes(),self.b)

class Package(unittest.TestCase):
    def test_no_supplied_output_directory(self):self.assertFalse((ROOT/'results').exists())
    def test_no_retained_predictions_in_cpu(self):
        i=Inputs()
        self.assertFalse(any('/evaluation/' in n or n.startswith('studies/frontend/results/') for n in i.groups['cpu']))
    def test_expected_finite_files(self):
        d=json.loads((ROOT/'expected/output_checksums.json').read_text())
        self.assertEqual(len(d),78)
        self.assertEqual(sum(m['rows'] for n,m in d.items() if n.endswith('/predictions.jsonl')),54016)
    def test_large_files_transport(self):
        self.assertLess(max(p.stat().st_size for p in ROOT.rglob('*') if p.is_file()),7_000_000)
    def test_output_inside_refused(self):
        p=subprocess.run([sys.executable,str(ROOT/'reproduce.py'),'--check-only','--output',str(ROOT/'not-an-output')],capture_output=True)
        self.assertEqual(p.returncode,2);self.assertFalse((ROOT/'not-an-output').exists())
    def test_existing_output_refused(self):
        with tempfile.TemporaryDirectory() as td:
            p=subprocess.run([sys.executable,str(ROOT/'reproduce.py'),'--check-only','--output',td],capture_output=True)
            self.assertEqual(p.returncode,2)
    def test_optimized_interpreter_refused(self):
        p=subprocess.run([sys.executable,'-O',str(ROOT/'reproduce.py'),'--check-only','--output',str(ROOT/'no-output')],capture_output=True)
        self.assertEqual(p.returncode,2);self.assertFalse((ROOT/'no-output').exists())

if __name__=='__main__':unittest.main()
