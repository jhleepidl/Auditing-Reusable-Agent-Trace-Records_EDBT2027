"""Compile VALUE-FREE public obligation shapes to a common strict output schema.

No source state, resolved expected operands, reference labels or model outputs read.
Every construction arm on a task receives this identical schema.
"""
import copy
def fixed(value):
    return {'type':'string','enum':[value]} if isinstance(value,str) else {'type':'null'} if value is None else {'type':'array','items':{'type':'string'},'minItems':len(value),'maxItems':len(value)}
def operand(req):
    t=req.get('operand_type',req.get('type',req.get('value_type')))
    return {'type':t} if t in {'string','number','integer','boolean'} else {'type':['string','number','boolean','null']}
def specialize(base,task):
    schema=copy.deepcopy(base);schema.pop('$schema',None)
    obligations=task['obligations'];kinds={o['kind'] for o in obligations}
    if not obligations:
        schema['properties']['classification']=fixed('unknown');schema['properties']['clauses']['maxItems']=0
        return schema
    assert len(kinds)==1
    kind=next(iter(kinds));schema['properties']['classification']['enum']=[kind,'unknown']
    branches=[]
    template=schema['properties']['clauses']['items']
    for o in obligations:
        clause=copy.deepcopy(template);clause['properties']['obligation_id']=fixed(o['obligation_id']);clause['properties']['kind']=fixed(kind)
        clause['properties']['state' if kind=='query' else'query']={'type':'null'}
        if kind=='query':
            q=copy.deepcopy(template['properties']['query']['anyOf'][0])
            for field,key in [('property','property'),('role','binding_role'),('unit','unit'),('temporal_scope','temporal_scope')]:q['properties'][field]=fixed(o[key])
            q['properties']['polarity']=fixed('positive');q['properties']['value']=operand(o)
            if o.get('entity_binding',{}).get('kind')=='task_subject':q['properties']['entity']=fixed(o['entity_binding']['entity_label'])
            clause['properties']['query']=q
        else:
            s=copy.deepcopy(template['properties']['state']['anyOf'][0]);target=o['target']
            if target.get('path'):s['properties']['path']=fixed(target['path'])
            s['properties']['identity_profile']=fixed(target['identity_profile']);s['properties']['newness']=fixed(o['newness'])
            field=target.get('identity_field');s['properties']['identity_field']=fixed(field)
            selectors=o.get('selector_requirements',[])
            if not selectors:s['properties']['selector']['maxItems']=0
            else:
                sel=s['properties']['selector']['items'];alts=[]
                for req in selectors:
                    part=copy.deepcopy(sel);part['properties']['field']=fixed(req['field']);part['properties']['value']=operand(req);alts.append(part)
                s['properties']['selector']['items']={'anyOf':alts}
            checks=s['properties']['checks']['items'];alts=[]
            for req in o['required_properties']:
                part=copy.deepcopy(checks)
                if req.get('property'):part['properties']['property']=fixed(req['property'])
                part['properties']['operator']=fixed({'eq':'equals'}.get(req['operator'],req['operator']));part['properties']['value']=operand(req);alts.append(part)
            s['properties']['checks']['items']={'anyOf':alts};s['properties']['checks']['minItems']=len(alts);s['properties']['checks']['maxItems']=len(alts)
            clause['properties']['state']=s
        branches.append(clause)
    schema['properties']['clauses']['items']={'anyOf':branches};schema['properties']['clauses']['maxItems']=len(branches)
    return schema
