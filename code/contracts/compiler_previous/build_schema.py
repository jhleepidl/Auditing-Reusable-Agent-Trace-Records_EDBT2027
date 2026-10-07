"""Generic JSON DAG extension of the shared strict literal contract schema."""
from pathlib import Path
import copy,json
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
BASE=ROOT/'baseline_r21' if (ROOT/'baseline_r21').exists() else ROOT.parent/'edbt_r21_followup'

def obj(properties):return {'type':'object','properties':properties,'required':list(properties),'additionalProperties':False}
def enum(values):return {'type':'string','enum':values}
I={'type':'integer','minimum':0,'maximum':1000000}
S={'type':'string','maxLength':4096}
P={'type':'string','maxLength':256,'pattern':'^(?:|/.*)$'}
OPS={
 'source':(0,0,obj({'root':enum(['initial_state','request','scope','facts']),'pointer':P})),
 'request_span':(0,0,obj({'start':I,'end':I})),
 'text_between':(1,1,obj({'left':S,'right':S,'trim':{'type':'boolean'}})),
 'extract_decimal':(1,1,obj({'anchor':S})),
 'constant':(0,0,obj({'value':{'anyOf':[{'type':'integer','enum':[0,1,100]},{'type':'boolean'}]}})),
 'get':(1,1,obj({'pointer':P})),
 'at':(1,1,obj({'index':{'type':'integer','minimum':0,'maximum':31}})),
 'unique':(1,1,obj({})),
 'filter':(2,2,obj({'pointer':P,'relation':enum(['equals','not_equals','contains','not_contains','prefix','gt','ge','lt','le']),'casefold':{'type':'boolean'}})),
 'project':(1,1,obj({'pointer':P})),
 'lookup_many':(2,2,obj({'missing':enum(['unknown','empty_array'])})),
 'flatten':(1,1,obj({})),
 'zip':(2,2,obj({'left_name':S,'right_name':S})),
 'group_count':(2,2,obj({'pointer':P,'unmatched':enum(['ignore','unknown'])})),
 'count':(1,1,obj({})),
 'sum':(1,1,obj({})),
 'argmin':(1,1,obj({'pointer':P,'ties':enum(['unknown'])})),
 'argmax':(1,1,obj({'pointer':P,'ties':enum(['unknown'])})),
 'sort':(1,1,obj({'keys':{'type':'array','minItems':1,'maxItems':3,'items':obj({'pointer':P,'direction':enum(['asc','desc'])})}})),
 'enumerate':(1,1,obj({'index_name':S})),
 'parse_decimal':(1,1,obj({})),
 'add':(2,2,obj({})), 'subtract':(2,2,obj({})), 'multiply':(2,2,obj({})), 'divide':(2,2,obj({})),
 'quantize':(1,1,obj({'places':{'type':'integer','minimum':0,'maximum':6},'rounding':enum(['half_even','half_up'])})),
 'string':(1,1,obj({})),
 'concat':(2,8,obj({})),
 'replace_once':(2,2,obj({'needle':S})),
}

def schema():
    contract=copy.deepcopy(json.loads((BASE/'e2/reference_author/source_snapshot/output_schema_r21_2.json').read_text()))
    contract.pop('$schema',None)
    contract['properties']['ir_version']['enum']=['r22.1']
    nodes=[]
    for op,(minimum,maximum,params) in OPS.items():
        nodes.append(obj({'id':{'type':'string','pattern':'^[a-z][a-z0-9_]{0,31}$'},'op':enum([op]),
            'args':{'type':'array','minItems':minimum,'maxItems':maximum,'items':{'type':'string','pattern':'^[a-z][a-z0-9_]{0,31}$'}},'params':params}))
    binding=obj({'target':{'type':'string','maxLength':256,'pattern':r'^/clauses/[0-9]+/(state/(path|selector/[0-9]+/value|checks/[0-9]+/(value|property))|query/(entity|value))$'},
                 'node':{'type':'string','pattern':'^[a-z][a-z0-9_]{0,31}$'}})
    return {'$schema':'https://json-schema.org/draft/2020-12/schema',**obj({'derivation_version':enum(['r22.1']),'contract':contract,
       'nodes':{'type':'array','maxItems':64,'items':{'anyOf':nodes}},
       'bindings':{'type':'array','maxItems':128,'items':binding}})}

if __name__=='__main__':(HERE/'output_schema.json').write_text(json.dumps(schema(),indent=2)+'\n')
