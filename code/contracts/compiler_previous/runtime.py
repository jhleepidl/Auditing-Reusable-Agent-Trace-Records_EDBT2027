"""Generic bounded source DAG compiler; no semantic-reference/task imports."""
from __future__ import annotations
import copy
import hashlib
import json
import math
import re
from decimal import Decimal, InvalidOperation, localcontext, ROUND_HALF_EVEN, ROUND_HALF_UP
from functools import cmp_to_key
from pathlib import Path
from jsonschema import Draft202012Validator

HERE=Path(__file__).resolve().parent
SCHEMA=json.loads((HERE/'output_schema.json').read_text())
VALIDATOR=Draft202012Validator(SCHEMA)
LIMITS={'nodes':64,'bindings':128,'depth':16,'row_visits':10000,'items':10000,'source_bytes':1048576,'string_chars':16384,'decimal_precision':40,'magnitude':Decimal('1e12')}
NUMBER=re.compile(r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)')
TARGET=re.compile(r'^/clauses/[0-9]+/(?:state/(?:path|selector/[0-9]+/value|checks/[0-9]+/(?:value|property))|query/(?:entity|value))$')

class InvalidIR(Exception):pass
class UnknownDerivation(Exception):pass


def json_value(value):
    if isinstance(value,Decimal):
        if not value.is_finite():raise UnknownDerivation('nonfinite_numeric_result')
        if value==value.to_integral_value():return int(value)
        result=float(value)
        if not math.isfinite(result) or Decimal(str(result))!=value:raise UnknownDerivation('lossy_json_numeric_result_requires_explicit_quantize')
        return result
    if isinstance(value,list):return [json_value(v) for v in value]
    if isinstance(value,dict):return {k:json_value(v) for k,v in value.items()}
    return value


def canonical(value):return json.dumps(json_value(value),sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
def digest(value):return hashlib.sha256(canonical(value)).hexdigest()
def number(value):
    if isinstance(value,bool) or not isinstance(value,(int,float,Decimal)):raise InvalidIR('numeric_type_required_boolean_is_not_number')
    result=Decimal(str(value))
    if not result.is_finite():raise UnknownDerivation('nonfinite_numeric_source')
    if abs(result)>LIMITS['magnitude']:raise UnknownDerivation('numeric_magnitude_budget')
    return result


def tokens(pointer):
    if not isinstance(pointer,str) or pointer and not pointer.startswith('/'):raise InvalidIR('invalid_json_pointer')
    if re.search(r'~(?![01])',pointer):raise InvalidIR('invalid_json_pointer_escape')
    return [] if pointer=='' else [v.replace('~1','/').replace('~0','~') for v in pointer[1:].split('/')]


def get(value,pointer,*,allow_none=False):
    for key in tokens(pointer):
        if value is None:raise UnknownDerivation('source_value_unavailable')
        if isinstance(value,dict):
            if key not in value:raise UnknownDerivation('source_pointer_absent')
            value=value[key]
        elif isinstance(value,list):
            if not re.fullmatch(r'0|[1-9][0-9]*',key):raise InvalidIR('array_pointer_index_required')
            index=int(key)
            if index>=len(value):raise UnknownDerivation('source_pointer_index_absent')
            value=value[index]
        else:raise InvalidIR('source_pointer_traverses_scalar')
    if value is None and not allow_none:raise UnknownDerivation('source_value_unavailable')
    return value


def put(value,pointer,replacement):
    parts=tokens(pointer)
    if not parts:raise InvalidIR('cannot_replace_contract_root')
    parent=get(value,'/'+ '/'.join(v.replace('~','~0').replace('/','~1') for v in parts[:-1])) if len(parts)>1 else value
    final=parts[-1]
    if isinstance(parent,dict) and final in parent:parent[final]=replacement
    elif isinstance(parent,list) and re.fullmatch(r'0|[1-9][0-9]*',final) and int(final)<len(parent):parent[int(final)]=replacement
    else:raise InvalidIR('binding_target_absent')


def equal(a,b):
    if isinstance(a,bool) or isinstance(b,bool):return type(a) is type(b) and a==b
    if isinstance(a,(int,float,Decimal)) and isinstance(b,(int,float,Decimal)):return number(a)==number(b)
    if isinstance(a,list) and isinstance(b,list):return len(a)==len(b) and all(equal(x,y) for x,y in zip(a,b))
    if isinstance(a,dict) and isinstance(b,dict):return a.keys()==b.keys() and all(equal(a[k],b[k]) for k in a)
    return type(a) is type(b) and a==b


def trace_value(value):
    if isinstance(value,Decimal):return {'decimal':format(value,'f')}
    if isinstance(value,list):return [trace_value(v) for v in value]
    if isinstance(value,dict):return {k:trace_value(v) for k,v in value.items()}
    return value


def compare(a,b):
    if isinstance(a,str) and isinstance(b,str):return (a>b)-(a<b)
    a,b=number(a),number(b);return (a>b)-(a<b)


class Budget:
    def __init__(self):self.visits=0;self.items=0
    def visit(self,n):
        self.visits+=n
        if self.visits>LIMITS['row_visits']:raise UnknownDerivation('row_visit_budget')
    def inspect(self,value,depth=0):
        if depth>32:raise UnknownDerivation('intermediate_data_depth_budget')
        self.items+=1
        if self.items>LIMITS['items']:raise UnknownDerivation('intermediate_item_budget')
        if isinstance(value,str) and len(value)>LIMITS['string_chars']:raise UnknownDerivation('string_budget')
        if isinstance(value,(int,float,Decimal)) and not isinstance(value,bool):number(value)
        elif isinstance(value,list):
            for item in value:self.inspect(item,depth+1)
        elif isinstance(value,dict):
            for k,v in value.items():
                if not isinstance(k,str):raise InvalidIR('JSON_object_key_must_be_string')
                self.inspect(v,depth+1)
        elif value is not None and not isinstance(value,(str,bool)):raise InvalidIR('unsupported_source_type')


def array(value):
    if value is None:raise UnknownDerivation('source_value_unavailable')
    if not isinstance(value,list):raise InvalidIR('array_type_required')
    return value


def string(value):
    if value is None:raise UnknownDerivation('source_value_unavailable')
    if not isinstance(value,str):raise InvalidIR('string_type_required')
    return value


def contains(haystack,needle,casefold):
    if isinstance(haystack,str):return string(needle).casefold() in haystack.casefold() if casefold else string(needle) in haystack
    if isinstance(haystack,list):return any(string(v).casefold()==string(needle).casefold() for v in haystack) if casefold else any(equal(v,needle) for v in haystack)
    raise InvalidIR('contains_requires_string_or_array')


def execute_node(node,args,roots,budget):
    op,p=node['op'],node['params']
    if op=='source':return copy.deepcopy(get(roots.get(p['root']),p['pointer']))
    if op=='request_span':
        text=string(roots['request'])
        if p['end']<=p['start']:raise InvalidIR('request_span_end_must_exceed_start')
        if p['end']>len(text):raise UnknownDerivation('request_span_unavailable')
        return text[p['start']:p['end']]
    if op=='text_between':
        text=string(args[0]);left,right=p['left'],p['right']
        if left and text.count(left)!=1:raise UnknownDerivation('text_left_anchor_not_unique')
        start=text.index(left)+len(left) if left else 0
        tail=text[start:]
        if right and tail.count(right)!=1:raise UnknownDerivation('text_right_anchor_not_unique')
        answer=tail[:tail.index(right)] if right else tail
        return answer.strip() if p['trim'] else answer
    if op=='extract_decimal':
        text=string(args[0]);anchor=p['anchor']
        if not anchor or text.count(anchor)!=1:raise UnknownDerivation('numeric_anchor_not_unique')
        tail=text[text.index(anchor)+len(anchor):].lstrip();match=NUMBER.match(tail)
        if not match:raise UnknownDerivation('no_decimal_after_anchor')
        return number(Decimal(match.group()))
    if op=='constant':return p['value']
    if op=='get':return copy.deepcopy(get(args[0],p['pointer']))
    if op=='at':
        values=array(args[0]);i=p['index']
        if i>=len(values):raise UnknownDerivation('at_index_unavailable')
        return copy.deepcopy(values[i])
    if op=='unique':
        values=array(args[0])
        if len(values)!=1:raise UnknownDerivation('selection_not_unique')
        return copy.deepcopy(values[0])
    if op=='filter':
        values=array(args[0]);budget.visit(len(values));needle=args[1];result=[]
        for row in values:
            v=get(row,p['pointer']);relation=p['relation'];cf=p['casefold']
            if relation in ['equals','not_equals']:
                matched=string(v).casefold()==string(needle).casefold() if cf else equal(v,needle)
                if relation=='not_equals':matched=not matched
            elif relation in ['contains','not_contains']:
                matched=contains(v,needle,cf)
                if relation=='not_contains':matched=not matched
            elif relation=='prefix':matched=string(v).casefold().startswith(string(needle).casefold()) if cf else string(v).startswith(string(needle))
            else:
                if cf:raise InvalidIR('casefold_not_defined_for_numeric_comparison')
                result_cmp=compare(v,needle);matched={'gt':result_cmp>0,'ge':result_cmp>=0,'lt':result_cmp<0,'le':result_cmp<=0}[relation]
            if matched:result.append(copy.deepcopy(row))
        return result
    if op=='project':
        values=array(args[0]);budget.visit(len(values));return [copy.deepcopy(get(row,p['pointer'])) for row in values]
    if op=='lookup_many':
        mapping,keys=args
        if not isinstance(mapping,dict):raise InvalidIR('lookup_many_requires_object')
        keys=array(keys);budget.visit(len(keys));result=[]
        for key in keys:
            key=string(key)
            if key in mapping:
                if mapping[key] is None:raise UnknownDerivation('lookup_value_unavailable')
                result.append(copy.deepcopy(mapping[key]))
            elif p['missing']=='empty_array':result.append([])
            else:raise UnknownDerivation('lookup_key_absent')
        return result
    if op=='flatten':
        values=array(args[0]);budget.visit(len(values));result=[]
        for child in values:result.extend(copy.deepcopy(array(child)))
        budget.visit(len(result));return result
    if op=='zip':
        left,right=map(array,args)
        if len(left)!=len(right):raise UnknownDerivation('zip_domain_length_mismatch')
        if not p['left_name'] or not p['right_name'] or p['left_name']==p['right_name']:raise InvalidIR('zip_distinct_nonempty_field_names_required')
        budget.visit(len(left));return [{p['left_name']:copy.deepcopy(a),p['right_name']:copy.deepcopy(b)} for a,b in zip(left,right)]
    if op=='group_count':
        records,domain=map(array,args);budget.visit(len(records)+len(domain));counts={}
        for key in domain:
            string(key)
            if key in counts:raise UnknownDerivation('group_domain_duplicate_identity')
            counts[key]=0
        for row in records:
            key=string(get(row,p['pointer']))
            if key not in counts:
                if p['unmatched']=='unknown':raise UnknownDerivation('group_key_outside_domain')
                continue
            counts[key]+=1
        return [{'key':key,'count':counts[key]} for key in domain]
    if op=='count':return len(array(args[0]))
    if op=='sum':
        values=array(args[0]);budget.visit(len(values));return sum((number(v) for v in values),Decimal(0))
    if op in ['argmin','argmax']:
        values=array(args[0]);budget.visit(len(values))
        if not values:raise UnknownDerivation('extremum_empty_domain')
        pairs=[(row,get(row,p['pointer'])) for row in values]
        best=pairs[0][1]
        for _,value in pairs[1:]:
            c=compare(value,best)
            if c<0 if op=='argmin' else c>0:best=value
        winners=[row for row,value in pairs if compare(value,best)==0]
        if len(winners)!=1:raise UnknownDerivation('extremum_ambiguous_tie')
        return copy.deepcopy(winners[0])
    if op=='sort':
        values=array(args[0]);budget.visit(max(1,len(values))*max(1,len(values).bit_length()))
        def cmp(a,b):
            for key in p['keys']:
                c=compare(get(a,key['pointer']),get(b,key['pointer']))
                if c:return c if key['direction']=='asc' else -c
            return 0
        result=sorted(copy.deepcopy(values),key=cmp_to_key(cmp))
        if any(cmp(a,b)==0 for a,b in zip(result,result[1:])):raise UnknownDerivation('sort_total_key_not_unique')
        return result
    if op=='enumerate':
        values=array(args[0]);budget.visit(len(values));result=[]
        if not p['index_name']:raise InvalidIR('enumerate_index_field_required')
        for index,row in enumerate(values,1):
            if not isinstance(row,dict) or p['index_name'] in row:raise InvalidIR('enumerate_requires_records_without_index_field')
            result.append({**copy.deepcopy(row),p['index_name']:index})
        return result
    if op=='parse_decimal':
        text=string(args[0]).strip()
        if not NUMBER.fullmatch(text):raise UnknownDerivation('decimal_token_not_complete')
        return number(Decimal(text))
    if op in ['add','subtract','multiply','divide']:
        a,b=map(number,args)
        if op=='divide' and b==0:raise UnknownDerivation('division_by_zero')
        return {'add':lambda:a+b,'subtract':lambda:a-b,'multiply':lambda:a*b,'divide':lambda:a/b}[op]()
    if op=='quantize':return number(args[0]).quantize(Decimal(1).scaleb(-p['places']),rounding=ROUND_HALF_EVEN if p['rounding']=='half_even' else ROUND_HALF_UP)
    if op=='string':
        v=args[0]
        if isinstance(v,str):return v
        if isinstance(v,bool) or not isinstance(v,(int,float,Decimal)):raise InvalidIR('string_cast_requires_number_or_string')
        v=number(v);return format(v,'f')
    if op=='concat':return ''.join(string(v) for v in args)
    if op=='replace_once':
        template,replacement=map(string,args);needle=p['needle']
        if not needle or template.count(needle)!=1:raise UnknownDerivation('replace_needle_not_unique')
        return template.replace(needle,replacement,1)
    raise InvalidIR('unrecognized_operation')


def required_binding_targets(contract,public_task):
    scopes={o['obligation_id']:o for o in public_task.get('obligations',[])};targets=[]
    for i,clause in enumerate(contract.get('clauses',[])):
        prefix=f'/clauses/{i}';scope=scopes.get(clause.get('obligation_id'),{})
        if clause.get('kind')=='query':targets.extend([prefix+'/query/entity',prefix+'/query/value'])
        elif clause.get('kind')=='state' and clause.get('state'):
            state=clause['state']
            targets.extend(prefix+f'/state/checks/{j}/value' for j in range(len(state['checks'])))
            targets.extend(prefix+f'/state/selector/{j}/value' for j in range(len(state['selector'])))
            if scope.get('target',{}).get('path_pattern'):targets.append(prefix+'/state/path')
            patterns=[p['property_pattern'] for p in scope.get('required_properties',[]) if 'property_pattern' in p]
            for j,c in enumerate(state['checks']):
                for pattern in patterns:
                    leading=pattern.split('{',1)[0]
                    if c['property'].startswith(leading):targets.append(prefix+f'/state/checks/{j}/property')
    return sorted(set(targets))


def compile_annotation(annotation,packet,public_task,*,mode='derived',public_facts=None,required_targets=None):
    """Compile only. Semantic task observation evaluation is a separate API."""
    result={'status':'error','contract':None,'provenance':{},'diagnostics':[]}
    traces=[];budget=Budget()
    try:
        if mode not in ['literal','derived','verified']:raise InvalidIR('invalid_compilation_mode')
        errors=sorted(VALIDATOR.iter_errors(annotation),key=lambda e:str(list(e.path)))
        if errors:raise InvalidIR('schema:'+str(list(errors[0].path))+':'+errors[0].message)
        if annotation['contract']['scope_id']!=public_task.get('scope_id'):raise UnknownDerivation('public_scope_id_mismatch')
        facts={} if public_facts is None else public_facts
        roots={'request':packet.get('task_request',packet.get('request')),'initial_state':packet.get('initial_state'),'scope':public_task,'facts':facts}
        source_bytes=len(canonical({'packet':packet,'scope':public_task,'facts':facts}))
        if source_bytes>LIMITS['source_bytes']:raise UnknownDerivation('aggregate_source_byte_budget')
        result['provenance']={'packet_sha256':digest(packet),'scope_input_sha256':digest(public_task),'public_facts_sha256':digest(facts),
                              'annotation_sha256':digest(annotation),'mode':mode,'nodes':traces,'binding_results':[]}
        contract=copy.deepcopy(annotation['contract'])
        if mode=='literal':
            if annotation['nodes'] or annotation['bindings']:raise InvalidIR('literal_mode_requires_empty_program_and_bindings')
            result.update(status='ok',contract=contract);return result
        if contract['classification']=='unknown':raise UnknownDerivation('model_declared_abstention')
        values={};depths={};dependencies={}
        with localcontext() as ctx:
            ctx.prec=LIMITS['decimal_precision']
            for node in annotation['nodes']:
                nid=node['id']
                if nid in values:raise InvalidIR('duplicate_node_id')
                if any(a not in values for a in node['args']):raise InvalidIR('forward_missing_or_cyclic_node_reference')
                depth=1+max((depths[a] for a in node['args']),default=0)
                if depth>LIMITS['depth']:raise UnknownDerivation('DAG_depth_budget')
                value=execute_node(node,[values[a] for a in node['args']],roots,budget)
                budget.inspect(value);values[nid]=value;depths[nid]=depth
                deps=set().union(*(dependencies[a] for a in node['args'])) if node['args'] else set()
                if node['op']=='source':deps.add(node['params']['root']+':'+node['params']['pointer'])
                if node['op']=='request_span':deps.add('request:span:'+str(node['params']['start'])+':'+str(node['params']['end']))
                dependencies[nid]=deps
                traces.append({'id':nid,'op':node['op'],'args':node['args'],'params':copy.deepcopy(node['params']),
                    'depth':depth,'source_dependencies':sorted(deps),'value':trace_value(value),'value_sha256':digest(trace_value(value))})
        targets=[b['target'] for b in annotation['bindings']]
        if len(set(targets))!=len(targets):raise InvalidIR('duplicate_binding_target')
        required=required_binding_targets(contract,public_task) if required_targets is None else list(required_targets)
        if set(required)!=set(targets):raise UnknownDerivation('operand_binding_coverage_mismatch:missing='+str(sorted(set(required)-set(targets)))+':extra='+str(sorted(set(targets)-set(required))))
        mismatches=[]
        for binding in annotation['bindings']:
            target,nid=binding['target'],binding['node']
            if not TARGET.fullmatch(target) or nid not in values:raise InvalidIR('invalid_binding_target_or_node')
            if not dependencies[nid]:raise UnknownDerivation('operand_has_no_source_dependency')
            claim=get(contract,target,allow_none=True);derived=json_value(values[nid])
            if not isinstance(derived,(str,int,float,bool,list)) or isinstance(derived,list) and any(isinstance(v,(dict,list)) for v in derived):raise InvalidIR('binding_requires_supported_literal_operand')
            matching=equal(claim,derived)
            result['provenance']['binding_results'].append({'target':target,'node':nid,'claimed':claim,'derived':derived,'claim_matches':matching,'source_dependencies':sorted(dependencies[nid])})
            if not matching:mismatches.append(target)
            put(contract,target,derived)
        if mode=='verified' and mismatches:raise UnknownDerivation('operand_claim_mismatch:'+str(mismatches))
        result.update(status='ok',contract=contract)
    except UnknownDerivation as e:result.update(status='unknown',contract=None);result['diagnostics'].append({'kind':'construction_unknown','reason':str(e)})
    except (InvalidIR,KeyError,TypeError,ValueError,InvalidOperation,OverflowError) as e:result.update(status='error',contract=None);result['diagnostics'].append({'kind':'construction_error','reason':str(e)})
    result['provenance']['budget']={'row_visits':budget.visits,'intermediate_items':budget.items}
    return result
