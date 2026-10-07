import unittest
from replay20_v2 import assert_step
class ErrorTraceBinding(unittest.TestCase):
 def setUp(self):self.call={'function':'search','args':{'query':'q'},'id':'1'}
 def test_expected_error_continues(self):assert_step(self.call,'not found',{'tool_call':self.call,'error':'not found'})
 def test_unexpected_error_stops(self):
  with self.assertRaises(AssertionError):assert_step(self.call,'not found',{'tool_call':self.call,'error':None})
 def test_missing_expected_error_stops(self):
  with self.assertRaises(AssertionError):assert_step(self.call,None,{'tool_call':self.call,'error':'not found'})
 def test_wrong_action_binding_stops(self):
  with self.assertRaises(AssertionError):assert_step(self.call,None,{'tool_call':dict(self.call,id='2'),'error':None})
if __name__=='__main__':unittest.main()
