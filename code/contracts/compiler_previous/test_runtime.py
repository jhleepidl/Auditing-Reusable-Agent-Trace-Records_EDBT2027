"""Generic CPU tests: synthetic data only, no benchmark references/imports."""
import copy
import json
import unittest
from pathlib import Path
from runtime import compile_annotation, required_binding_targets
HERE=Path(__file__).resolve().parent

def node(nid,op,args=None,**params):return {'id':nid,'op':op,'args':[] if args is None else args,'params':params}
def contract(properties=('amount',),claims=None):
    claims={} if claims is None else claims
    return {'ir_version':'r22.1','scope_id':'synthetic_scope','classification':'state','clauses':[{'obligation_id':'synthetic::effect','kind':'state',
      'state':{'path':'/effects','selector':[],'checks':[{'property':p,'operator':'equals','value':claims.get(p,0)} for p in properties],'identity_profile':'stable_id','identity_field':'id','newness':'pre_id_absence'},'query':None,
      'support':{'request_quote':'synthetic request','initial_state_paths':['/records'],'schema_paths':[],'reason':'synthetic generic example'}}], 'unknown_reason':''}
def scope():return {'scope_id':'synthetic_scope','obligations':[{'obligation_id':'synthetic::effect','target':{'path':'/effects'},'required_properties':[]}]}
def annotation(nodes,output='result',properties=('amount',),claims=None):
    return {'derivation_version':'r22.1','contract':contract(properties,claims),'nodes':nodes,'bindings':[{'target':f'/clauses/0/state/checks/{i}/value','node':output if isinstance(output,str) else output[p]} for i,p in enumerate(properties)]}
def compile_case(a,state,request='synthetic request',**kw):return compile_annotation(a,{'task_request':request,'initial_state':state},scope(),**kw)
def operand(r,index=0):return r['contract']['clauses'][0]['state']['checks'][index]['value']

def arithmetic_example():
    request='Use the Widget payment plus an additional 12.5% and fee 1.75.'
    state={'records':[{'subject':'Wrong item','amount':80,'recipient':'Decoy','sender':'Buyer'}, {'subject':'Widget','amount':80,'recipient':'Vendor','sender':'Buyer'}]}
    nodes=[node('records','source',root='initial_state',pointer='/records'),node('request','source',root='request',pointer=''),
      node('label','text_between',['request'],left='the ',right=' payment',trim=True),node('selected','filter',['records','label'],pointer='/subject',relation='equals',casefold=False),node('one','unique',['selected']),
      node('base','get',['one'],pointer='/amount'),node('recipient','get',['one'],pointer='/recipient'),node('percent','extract_decimal',['request'],anchor='additional '),
      node('hundred','constant',value=100),node('fraction','divide',['percent','hundred']),node('part','multiply',['base','fraction']),node('fee','extract_decimal',['request'],anchor='fee '),node('result','add',['part','fee'])]
    a=annotation(nodes,{'amount':'result','recipient':'recipient'},('amount','recipient'))
    return request,state,a


class RuntimeTests(unittest.TestCase):
    def test_exact_percentage_recipient_same_selected_entity(self):
        request,state,a=arithmetic_example();r=compile_case(a,state,request);self.assertEqual(r['status'],'ok');self.assertEqual(operand(r),11.75);self.assertEqual(operand(r,1),'Vendor')
    def test_order_permutation_and_equal_value_decoy(self):
        request,state,a=arithmetic_example();state['records'].reverse();r=compile_case(a,state,request);self.assertEqual(operand(r),11.75);self.assertEqual(operand(r,1),'Vendor')
    def test_frozen_program_reexec_new_source_amount_recipient(self):
        request,state,a=arithmetic_example();old=compile_case(a,state,request);state['records'][1].update(amount=160,recipient='AnotherVendor');new=compile_case(a,state,request);self.assertEqual(operand(new),21.75);self.assertEqual(operand(new,1),'AnotherVendor');self.assertNotEqual(old['provenance']['packet_sha256'],new['provenance']['packet_sha256']);self.assertEqual(old['provenance']['annotation_sha256'],new['provenance']['annotation_sha256'])
    def test_source_grounded_request_number_reexec(self):
        request,state,a=arithmetic_example();r=compile_case(a,state,request.replace('12.5%','25.0%').replace('1.75','2.75'));self.assertEqual(operand(r),22.75)
    def test_wrong_source_field_is_not_semantically_repaired(self):
        request,state,a=arithmetic_example();next(n for n in a['nodes'] if n['id']=='recipient')['params']['pointer']='/sender';r=compile_case(a,state,request);self.assertEqual(r['status'],'ok');self.assertEqual(operand(r,1),'Buyer')
    def test_zero_and_multiple_selection_abstain(self):
        request,state,a=arithmetic_example()
        for records in [[],state['records']+[copy.deepcopy(state['records'][1])]]:
            r=compile_case(a,{'records':records},request);self.assertEqual(r['status'],'unknown');self.assertIn('selection_not_unique',r['diagnostics'][0]['reason'])
    def test_unavailable_source_is_not_empty(self):
        request,_,a=arithmetic_example();r=compile_case(a,None,request);self.assertEqual(r['status'],'unknown')
    def test_verified_claim_mismatch_is_construction_unknown(self):
        request,state,a=arithmetic_example();r=compile_case(a,state,request,mode='verified');self.assertEqual(r['status'],'unknown');self.assertIn('operand_claim_mismatch',r['diagnostics'][0]['reason']);self.assertEqual(len(r['provenance']['binding_results']),2)
    def test_verified_matching_claims(self):
        request,state,a=arithmetic_example();a['contract']['clauses'][0]['state']['checks'][0]['value']=11.75;a['contract']['clauses'][0]['state']['checks'][1]['value']='Vendor';r=compile_case(a,state,request,mode='verified');self.assertEqual(r['status'],'ok')
    def test_derived_null_placeholder(self):
        request,state,a=arithmetic_example();a['contract']['clauses'][0]['state']['checks'][0]['value']=None;r=compile_case(a,state,request);self.assertEqual(r['status'],'ok');self.assertEqual(operand(r),11.75)
    def test_literal_requires_empty_extension(self):
        _,_,a=arithmetic_example();self.assertEqual(compile_case(a,{},mode='literal')['status'],'error');a['nodes']=[];a['bindings']=[];self.assertEqual(compile_case(a,{},mode='literal')['status'],'ok')
    def test_no_missing_binding_silently_filled(self):
        request,state,a=arithmetic_example();a['bindings'].pop();self.assertEqual(compile_case(a,state,request)['status'],'unknown')
    def test_duplicate_binding_rejected(self):
        request,state,a=arithmetic_example();a['bindings'].append(copy.deepcopy(a['bindings'][0]));self.assertEqual(compile_case(a,state,request)['status'],'error')
    def test_answer_constant_rejected(self):
        a=annotation([node('result','constant',value=771)]);self.assertEqual(compile_case(a,{})['status'],'error')
    def test_only_structural_constant_is_not_source_grounding(self):
        a=annotation([node('result','constant',value=100)]);self.assertEqual(compile_case(a,{})['status'],'unknown')
    def test_forward_reference_and_duplicate_ids(self):
        for nodes in [[node('result','get',['future'],pointer='')],[node('result','source',root='initial_state',pointer='/n'),node('result','source',root='initial_state',pointer='/n')]]:
            self.assertEqual(compile_case(annotation(nodes),{'n':3})['status'],'error')
    def test_bool_is_not_numeric(self):
        a=annotation([node('source','source',root='initial_state',pointer='/n'),node('one','constant',value=1),node('result','add',['source','one'])]);self.assertEqual(compile_case(a,{'n':True})['status'],'error')
    def test_group_zero_fills_explicit_channels(self):
        state={'channels':['Busy','MissingEmpty','Quiet'],'inbox':{'Busy':[{'recipient':'Busy'},{'recipient':'Busy'}],'Quiet':[{'recipient':'Quiet'}]}}
        nodes=[node('domain','source',root='initial_state',pointer='/channels'),node('inbox','source',root='initial_state',pointer='/inbox'),node('buckets','lookup_many',['inbox','domain'],missing='empty_array'),node('messages','flatten',['buckets']),node('counts','group_count',['messages','domain'],pointer='/recipient',unmatched='unknown'),node('least','argmin',['counts'],pointer='/count',ties='unknown'),node('result','get',['least'],pointer='/key')]
        r=compile_case(annotation(nodes),state);self.assertEqual(r['status'],'ok');self.assertEqual(operand(r),'MissingEmpty')
        state['inbox']=None;self.assertEqual(compile_case(annotation(nodes),state)['status'],'unknown')
    def test_argmin_ties_abstain(self):
        nodes=[node('rows','source',root='initial_state',pointer='/rows'),node('result','argmin',['rows'],pointer='/count',ties='unknown')]
        r=compile_case(annotation(nodes),{'rows':[{'key':'A','count':0},{'key':'B','count':0}]});self.assertEqual(r['status'],'unknown')
    def test_group_counts_and_alphabetical_rank(self):
        state={'users':['D','B','A','C'],'messages':[{'sender':'C'},{'sender':'A'},{'sender':'B'},{'sender':'C'},{'sender':'D'}]}
        nodes=[node('users','source',root='initial_state',pointer='/users'),node('messages','source',root='initial_state',pointer='/messages'),node('counts','group_count',['messages','users'],pointer='/sender',unmatched='unknown'),node('sorted','sort',['counts'],keys=[{'pointer':'/count','direction':'desc'},{'pointer':'/key','direction':'asc'}]),node('ranked','enumerate',['sorted'],index_name='rank'),node('first','at',['ranked'],index=0),node('result','get',['first'],pointer='/key')]
        r=compile_case(annotation(nodes),state);self.assertEqual(r['status'],'ok');self.assertEqual(operand(r),'C');ranked=next(n['value'] for n in r['provenance']['nodes'] if n['id']=='ranked');self.assertEqual([(v['key'],v['rank']) for v in ranked],[('C',1),('A',2),('B',3),('D',4)])
    def test_duplicate_domain_and_duplicate_total_sort_key_abstain(self):
        a=annotation([node('users','source',root='initial_state',pointer='/users'),node('messages','source',root='initial_state',pointer='/messages'),node('result','group_count',['messages','users'],pointer='/sender',unmatched='unknown')]);self.assertEqual(compile_case(a,{'users':['A','A'],'messages':[]})['status'],'unknown')
        a=annotation([node('rows','source',root='initial_state',pointer='/rows'),node('result','sort',['rows'],keys=[{'pointer':'/count','direction':'desc'}])]);self.assertEqual(compile_case(a,{'rows':[{'count':1},{'count':1}]})['status'],'unknown')
    def test_explicit_quantize_after_repeating_decimal(self):
        a=annotation([node('three','source',root='initial_state',pointer='/n'),node('one','constant',value=1),node('fraction','divide',['one','three']),node('result','quantize',['fraction'],places=2,rounding='half_even')]);r=compile_case(a,{'n':3});self.assertEqual(r['status'],'ok');self.assertEqual(operand(r),0.33)
    def test_decimal_binary_float_noise_absent(self):
        a=annotation([node('a','source',root='initial_state',pointer='/a'),node('b','source',root='initial_state',pointer='/b'),node('result','add',['a','b'])]);r=compile_case(a,{'a':0.1,'b':0.2});self.assertEqual(operand(r),0.3)
    def test_depth_budget(self):
        nodes=[node('n0','source',root='initial_state',pointer='/n')]+[node('n'+str(i),'get',['n'+str(i-1)],pointer='') for i in range(1,17)];r=compile_case(annotation(nodes,'n16'),{'n':3});self.assertEqual(r['status'],'unknown');self.assertIn('depth_budget',r['diagnostics'][0]['reason'])
    def test_intermediate_budget(self):
        a=annotation([node('rows','source',root='initial_state',pointer='/rows'),node('result','count',['rows'])]);r=compile_case(a,{'rows':[0]*10001});self.assertEqual(r['status'],'unknown')
    def test_body_template_and_public_actor_fact_are_source_read(self):
        a=annotation([node('request','source',root='request',pointer=''),node('template','text_between',['request'],left='message: ',right='',trim=True),node('rank','source',root='initial_state',pointer='/rank'),node('ranktext','string',['rank']),node('result','replace_once',['template','ranktext'],needle='k')]);r=compile_case(a,{'rank':2},'Use message: Hello rank k!');self.assertEqual(r['status'],'unknown')
        r=compile_case(a,{'rank':2},'Use message: Hello person k!');self.assertEqual(operand(r),'Hello person 2!')
        a=annotation([node('result','source',root='facts',pointer='/message_sender')]);r=compile_case(a,{},public_facts={'message_sender':'bot'});self.assertEqual(operand(r),'bot')
    def test_scope_mismatch_abstains(self):
        a=annotation([node('result','source',root='initial_state',pointer='/n')]);a['contract']['scope_id']='another';self.assertEqual(compile_case(a,{'n':3})['status'],'unknown')
    def test_dynamic_public_path_and_property_binding_coverage(self):
        c=contract(('users','user_channels/{user}'));c['clauses'][0]['state']['path']='/box/{key}'
        s=scope();s['obligations'][0]['target']={'path_pattern':'/box/{key}'};s['obligations'][0]['required_properties']=[{'property_pattern':'user_channels/{user}'}]
        required=required_binding_targets(c,s);self.assertIn('/clauses/0/state/path',required);self.assertIn('/clauses/0/state/checks/1/property',required)

if __name__=='__main__':unittest.main(verbosity=2)
