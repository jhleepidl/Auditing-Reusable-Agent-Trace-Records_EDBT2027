"""Synthetic normalization tests; benchmark reads are public structure only."""
import copy
import hashlib
import json
import unittest
from pathlib import Path
from runtime import build_scaffold, schema_for_scope, normalize_annotation, compile_annotation, core, CORE_PATH, CORE_SHA256

HERE=Path(__file__).resolve().parent


def node(nid,op,args=None,**params):
    return {'id':nid,'op':op,'args':args or [],'params':params}


def scope():
    return {'scope_id':'synthetic_scope','supported':True,'task_request':'Use Gizmo.',
            'obligations':[{'obligation_id':'synthetic::payment','kind':'state',
                            'target':{'path':'/effects','identity_profile':'stable_id','identity_field':'id'},
                            'newness':'pre_id_absence','selector_requirements':[],
                            'required_properties':[{'property':'recipient','type':'string','operator':'eq'},
                                                   {'property':'amount','type':'number','operator':'eq'}],
                            'binding_role':'payment'}]}


def example():
    s=scope()
    a={'derivation_version':'r22.2','classification':'state','unknown_reason':'',
       'operands':{'o0_recipient':{'claim':'party_A','node':'recipient'},
                   'o0_amount':{'claim':40,'node':'amount'}},
       'nodes':[node('row','source',root='initial_state',pointer='/record'),
                node('recipient','get',['row'],pointer='/recipient'),node('amount','get',['row'],pointer='/amount')]}
    p={'task_request':'Use Gizmo.','initial_state':{'record':{'recipient':'party_A','amount':40}}}
    return s,a,p


class ScaffoldTests(unittest.TestCase):
    def test_derived_normalizes_exactly_once_and_preserves_operands(self):
        s,a,p=example();n=normalize_annotation(a,s)
        self.assertEqual(len(n['bindings']),2)
        self.assertEqual(len(set(b['target'] for b in n['bindings'])),2)
        self.assertEqual(n['nodes'],a['nodes'])
        r=compile_annotation(a,p,s);self.assertEqual(r['status'],'ok')
        self.assertEqual([v['value'] for v in r['contract']['clauses'][0]['state']['checks']],['party_A',40])
        self.assertEqual(r['provenance']['normalization']['endpoint_count'],2)

    def test_literal_same_scaffold_no_program(self):
        s,a,p=example();a['nodes']=[]
        for operand in a['operands'].values():operand['node']=None
        n=normalize_annotation(a,s,mode='literal');self.assertEqual(n['bindings'],[])
        self.assertEqual(compile_annotation(a,p,s,mode='literal')['status'],'ok')

    def test_missing_extra_and_missing_node_rejected(self):
        s,a,p=example()
        missing=copy.deepcopy(a);del missing['operands']['o0_amount']
        extra=copy.deepcopy(a);extra['operands']['answer']={'claim':5,'node':'amount'}
        unbound=copy.deepcopy(a);unbound['operands']['o0_amount']['node']=None
        for altered in (missing,extra,unbound):self.assertEqual(compile_annotation(altered,p,s)['status'],'error')

    def test_typed_number_claim_rejects_boolean(self):
        s,a,p=example();a['operands']['o0_amount']['claim']=True
        self.assertEqual(compile_annotation(a,p,s)['status'],'error')

    def test_derived_result_must_match_endpoint_scalar_type(self):
        s,a,p=example();a['operands']['o0_amount']['node']='recipient'
        self.assertEqual(compile_annotation(a,p,s)['status'],'error')

    def test_claim_mismatch_verified_unknown_and_primary_derived_ok(self):
        s,a,p=example();a['operands']['o0_amount']['claim']=0
        self.assertEqual(compile_annotation(a,p,s)['status'],'ok')
        self.assertEqual(compile_annotation(a,p,s,mode='verified')['status'],'unknown')

    def test_no_semantic_repair_of_wrong_field(self):
        s,a,p=example();p['initial_state']['record']['other_party']='party_B'
        a['nodes'][1]['params']['pointer']='/other_party'
        r=compile_annotation(a,p,s);self.assertEqual(r['status'],'ok')
        self.assertEqual(r['contract']['clauses'][0]['state']['checks'][0]['value'],'party_B')

    def test_unchanged_annotation_new_source_reexecution(self):
        s,a,p=example();before=compile_annotation(a,p,s);p['initial_state']['record']['amount']=81
        after=compile_annotation(a,p,s)
        self.assertEqual(before['provenance']['normalization']['input_annotation_sha256'],after['provenance']['normalization']['input_annotation_sha256'])
        self.assertNotEqual(before['provenance']['packet_sha256'],after['provenance']['packet_sha256'])
        self.assertEqual(after['contract']['clauses'][0]['state']['checks'][1]['value'],81)

    def test_abstention_explicit_and_no_partial_program(self):
        s,a,p=example();a.update(classification='unknown',unknown_reason='Ambiguous selection.',nodes=[])
        for operand in a['operands'].values():operand['node']=None
        self.assertEqual(compile_annotation(a,p,s)['status'],'unknown')
        a['unknown_reason']='';self.assertEqual(compile_annotation(a,p,s)['status'],'error')

    def test_wrong_classification_and_literal_program_rejected(self):
        s,a,p=example();self.assertEqual(compile_annotation(a,p,s,mode='literal')['status'],'error')
        a['classification']='query';self.assertEqual(compile_annotation(a,p,s)['status'],'error')

    def test_value_free_scaffold_ignores_task_id_and_source_like_extras(self):
        s=scope();before=build_scaffold(s)
        s.update(task_key='anything/arbitrary',initial_state={'amount':999,'recipient':'SECRET'},expected_target=918)
        self.assertEqual(build_scaffold(s),before)
        values=[core.get(before['contract_template'],v['target']) for v in before['endpoints'].values()]
        self.assertEqual(values,['',0]);self.assertNotIn('SECRET',json.dumps(build_scaffold(s)))

    def test_dynamic_path_and_property_all_explicit_endpoints(self):
        s=scope();o=s['obligations'][0]
        o['target']={'path_pattern':'/messages/{recipient}','identity_profile':'message_multiset','identity_field':['recipient','body']}
        o['required_properties']=[{'property':'recipient','type':'string','operator':'eq'},
                                  {'property_pattern':'channels/{user}','operand_type':'string','type':'array[string]','operator':'member'}]
        sc=build_scaffold(s);targets={v['target'] for v in sc['endpoints'].values()}
        self.assertIn('/clauses/0/state/path',targets);self.assertIn('/clauses/0/state/checks/1/property',targets)
        for e in sc['endpoints'].values():self.assertEqual(core.get(sc['contract_template'],e['target']),e['placeholder'])

    def test_dynamic_property_executes_from_public_pattern_and_same_selected_user(self):
        s=scope();o=s['obligations'][0]
        o['target']={'path':'/workspace','identity_profile':'singleton','identity_field':None}
        o['newness']='none';o['required_properties']=[{'property':'users','type':'array[string]','operand_type':'string','operator':'member'},
            {'property_pattern':'channels/{user}','type':'array[string]','operand_type':'string','operator':'member'}]
        a={'derivation_version':'r22.2','classification':'state','unknown_reason':'',
            'operands':{'o0_users':{'claim':'','node':'user'},'o0_channels':{'claim':'','node':'channel'},
                        'o0_dynamic_property':{'claim':'','node':'property'}},
            'nodes':[node('user','source',root='initial_state',pointer='/selected_user'),
                     node('channel','source',root='initial_state',pointer='/selected_channel'),
                     node('pattern','source',root='scope',pointer='/obligations/0/required_properties/1/property_pattern'),
                     node('property','replace_once',['pattern','user'],needle='{user}')]}
        r=compile_annotation(a,{'task_request':'Use Gizmo.','initial_state':{'selected_user':'U','selected_channel':'C'}},s)
        self.assertEqual(r['status'],'ok');checks=r['contract']['clauses'][0]['state']['checks']
        self.assertEqual(checks[1]['property'],'channels/U');self.assertEqual(checks[0]['value'],'U')
        self.assertEqual(checks[1]['value'],'C');self.assertEqual(len(r['provenance']['binding_results']),3)

    def test_dynamic_path_executes_from_public_pattern_and_recipient(self):
        s=scope();o=s['obligations'][0]
        o['target']={'path_pattern':'/inbox/{recipient}','identity_profile':'message_multiset','identity_field':['recipient']}
        o['required_properties']=[{'property':'recipient','type':'string','operator':'eq'}]
        a={'derivation_version':'r22.2','classification':'state','unknown_reason':'',
           'operands':{'o0_recipient':{'claim':'','node':'recipient'},'o0_dynamic_path':{'claim':'','node':'path'}},
           'nodes':[node('recipient','source',root='initial_state',pointer='/selected_user'),
                    node('pattern','source',root='scope',pointer='/obligations/0/target/path_pattern'),
                    node('path','replace_once',['pattern','recipient'],needle='{recipient}')]}
        r=compile_annotation(a,{'task_request':'Use Gizmo.','initial_state':{'selected_user':'U'}},s)
        self.assertEqual(r['status'],'ok');self.assertEqual(r['contract']['clauses'][0]['state']['path'],'/inbox/U')

    def test_query_fixed_metadata_and_two_source_endpoints(self):
        s=scope();s['obligations']=[{'obligation_id':'synthetic::rating','kind':'query','property':'rating','value_type':'number','unit':'rating_points','temporal_scope':'unscoped','binding_role':'company','polarity':'affirmative'}]
        sc=build_scaffold(s);q=sc['contract_template']['clauses'][0]['query']
        self.assertEqual(q['entity'],'');self.assertEqual(q['value'],0);self.assertEqual(q['polarity'],'positive')
        self.assertEqual(set(sc['endpoints']),{'o0_entity','o0_rating'})

    def test_public_selector_coverage_and_no_resolved_value_copy(self):
        s=scope();s['obligations'][0]['selector_requirements']=[{'field':'id','type':'string','value':'HIDDEN'}]
        sc=build_scaffold(s);self.assertEqual(sc['contract_template']['clauses'][0]['state']['selector'][0]['value'],'')
        self.assertIn('o0_selector_id',sc['endpoints']);self.assertNotIn('HIDDEN',json.dumps(sc))

    def test_core_and_node_schema_unchanged(self):
        self.assertEqual(hashlib.sha256(CORE_PATH.read_bytes()).hexdigest(),CORE_SHA256)
        self.assertEqual(schema_for_scope(scope())['properties']['nodes'],core.SCHEMA['properties']['nodes'])

    def test_exact_eight_public_scope_coverage(self):
        root=HERE.parent
        path=root/'baseline_r21/e2/reference_author/common_scopes_v2.json'
        if not path.exists():path=root.parent/'edbt_r21_followup/e2/reference_author/common_scopes_v2.json'
        chosen={'banking/user_task_1':2,'banking/user_task_4':2,'banking/user_task_5':2,'banking/user_task_11':2,
                'slack/user_task_10':9,'slack/user_task_13':4,'slack/user_task_14':16,'travel/user_task_14':4}
        found={}
        for s in json.loads(path.read_text())['tasks']:
            if s['task_key'] not in chosen:continue
            sc=build_scaffold(s);found[s['task_key']]=len(sc['endpoints'])
            targets=[v['target'] for v in sc['endpoints'].values()]
            self.assertEqual(len(targets),len(set(targets)))
            self.assertEqual(set(schema_for_scope(s)['properties']['operands']['required']),set(sc['endpoints']))
            for e in sc['endpoints'].values():self.assertEqual(core.get(sc['contract_template'],e['target']),e['placeholder'])
        self.assertEqual(found,chosen);self.assertEqual(sum(found.values()),41)


if __name__=='__main__':unittest.main(verbosity=2)
