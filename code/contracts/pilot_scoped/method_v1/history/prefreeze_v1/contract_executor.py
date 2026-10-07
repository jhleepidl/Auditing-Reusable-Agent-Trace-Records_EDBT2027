"""R21 common typed executor and structural admission policy.

No reference/oracle/native-utility imports or task-specific expected-value lookup.
Public obligations constrain scope/shape; candidate operands remain candidate data.
"""
from __future__ import annotations
import collections, copy, datetime, decimal, json, math, re, unicodedata
from pathlib import Path
from typing import Any
import jsonschema

VERSION = 'r21.1'
MISSING = object()
OPERATORS = {'exists','absent','equals','contains','member','not_member','gt','ge','lt','le','date','month_day','changed'}
PROFILES = {'stable_id','dict_key','message_multiset','scalar_set','singleton','position'}
NEWNESS = {'none','pre_id_absence','pre_key_absence','count_increase','index_absence'}

SCALAR = {'type':['string','number','boolean','null']}
VALUE = {'anyOf':[SCALAR,{'type':'array','items':SCALAR}]}
def obj(properties):
    return {'type':'object','properties':properties,'required':list(properties),'additionalProperties':False}
SUPPORT = obj({'request_quote':{'type':'string'},'initial_state_paths':{'type':'array','items':{'type':'string'}},'schema_paths':{'type':'array','items':{'type':'string'}},'reason':{'type':'string'}})
STATE = obj({'path':{'type':'string'},'selector':{'type':'array','items':obj({'field':{'type':'string'},'value':VALUE})},'checks':{'type':'array','items':obj({'property':{'type':'string'},'operator':{'type':'string','enum':sorted(OPERATORS)},'value':VALUE})},'identity_profile':{'type':'string','enum':sorted(PROFILES)},'identity_field':{'anyOf':[{'type':'string'},{'type':'array','items':{'type':'string'}},{'type':'null'}]},'newness':{'type':'string','enum':sorted(NEWNESS)}})
QUERY = obj({'entity':{'type':'string'},'property':{'type':'string'},'value':SCALAR,'unit':{'type':['string','null']},'temporal_scope':{'type':['string','null']},'role':{'type':'string'},'polarity':{'type':'string','enum':['positive','negative']}})
SCHEMA = obj({'ir_version':{'type':'string','enum':[VERSION]},'scope_id':{'type':'string'},'classification':{'type':'string','enum':['state','query','unknown']},'clauses':{'type':'array','items':obj({'obligation_id':{'type':'string'},'kind':{'type':'string','enum':['state','query']},'state':{'anyOf':[STATE,{'type':'null'}]},'query':{'anyOf':[QUERY,{'type':'null'}]},'support':SUPPORT})},'unknown_reason':{'type':'string'}})
SCHEMA['$schema']='https://json-schema.org/draft/2020-12/schema'

class InvalidIR(ValueError): pass

def normalized(s): return unicodedata.normalize('NFKC',str(s)).casefold().strip()
def equal(a,b):
    """JSON equality, with booleans distinct from numbers and no coerced strings."""
    if a is MISSING or b is MISSING: return a is b
    if isinstance(a,bool) or isinstance(b,bool): return type(a) is type(b) and a==b
    if a is None or b is None: return a is b
    if isinstance(a,(int,float)) and isinstance(b,(int,float)): return a==b
    if type(a) is not type(b): return False
    if isinstance(a,list): return len(a)==len(b) and all(equal(x,y) for x,y in zip(a,b))
    if isinstance(a,dict): return a.keys()==b.keys() and all(equal(a[k],b[k]) for k in a)
    return a==b

def parts(pointer,relative=False):
    if not isinstance(pointer,str): raise InvalidIR('pointer_not_string')
    if pointer=='$value' and relative: return []
    if pointer=='': return []
    if relative and not pointer.startswith('/'): pointer='/'+pointer
    if not pointer.startswith('/'): raise InvalidIR('not_json_pointer')
    if re.search(r'~(?![01])',pointer): raise InvalidIR('invalid_pointer_escape')
    tokens=[x.replace('~1','/').replace('~0','~') for x in pointer[1:].split('/')]
    if any(x in {'*','..'} for x in tokens): raise InvalidIR('wildcard_or_parent_in_concrete_pointer')
    return tokens

def at(value,pointer,relative=False):
    if value is MISSING:return MISSING
    tokens=parts(pointer,relative)
    for t in tokens:
        if isinstance(value,dict):
            if t not in value:return MISSING
            value=value[t]
        elif isinstance(value,list):
            if not re.fullmatch(r'0|[1-9][0-9]*',t) or int(t)>=len(value):return MISSING
            value=value[int(t)]
        else:return MISSING
    return value

def _finite(v):
    if isinstance(v,float) and not math.isfinite(v):return False
    if isinstance(v,dict):return all(_finite(x) for x in v.values())
    if isinstance(v,list):return all(_finite(x) for x in v)
    return True

def _operand_issue(check):
    op,v=check['operator'],check['value']
    if op in {'gt','ge','lt','le'} and (isinstance(v,bool) or not isinstance(v,(int,float))):return 'numeric_operand_required'
    if op in {'contains','date','month_day'} and not isinstance(v,str):return 'string_operand_required'
    if op in {'exists','absent','changed'} and not (v is None or v is True):return 'operator_requires_null_or_true'
    if op=='date':
        try:datetime.date.fromisoformat(v)
        except (ValueError,TypeError):return 'invalid_iso_date'
    if op=='month_day' and not re.fullmatch(r'(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])',v):return 'invalid_month_day'
    return None

def validate(contract):
    issues=[]
    for e in sorted(jsonschema.Draft202012Validator(SCHEMA).iter_errors(contract),key=lambda e:str(list(e.path))):
        issues.append({'code':'invalid_output_shape','path':list(e.path),'message':e.message})
    if not _finite(contract):issues.append({'code':'non_finite_number'})
    if issues:return {'valid':False,'issues':issues,'version':VERSION}
    ids=[c['obligation_id'] for c in contract['clauses']]
    if len(ids)!=len(set(ids)):issues.append({'code':'duplicate_obligation_id'})
    kinds={c['kind'] for c in contract['clauses']}
    if contract['classification']=='unknown' and contract['clauses']:issues.append({'code':'unknown_with_executable_clauses'})
    if contract['classification']!='unknown' and (kinds-{contract['classification']}):issues.append({'code':'classification_clause_kind_mismatch'})
    for i,c in enumerate(contract['clauses']):
        if c[c['kind']] is None or c['query' if c['kind']=='state' else 'state'] is not None:
            issues.append({'code':'kind_payload_mismatch','clause':i});continue
        if c['kind']=='state':
            s=c['state']
            if not s['checks']:issues.append({'code':'empty_state_checks','clause':i})
            for label,pointer in [('path',s['path'])]+[('selector',x['field']) for x in s['selector']]+[('property',x['property']) for x in s['checks']]:
                try:parts(pointer,relative=label!='path')
                except InvalidIR as e:issues.append({'code':str(e),'clause':i,'field':label})
            for x in s['checks']:
                issue=_operand_issue(x)
                if issue:issues.append({'code':issue,'clause':i,'property':x['property']})
            if s['identity_profile']=='stable_id' and not isinstance(s['identity_field'],str):issues.append({'code':'stable_id_field_required','clause':i})
            if s['identity_profile']=='message_multiset' and not isinstance(s['identity_field'],list):issues.append({'code':'multiset_fields_required','clause':i})
            if s['newness']=='pre_id_absence' and s['identity_profile']!='stable_id':issues.append({'code':'newness_profile_mismatch','clause':i})
            if s['newness']=='pre_key_absence' and s['identity_profile']!='dict_key':issues.append({'code':'newness_profile_mismatch','clause':i})
            if s['newness']=='count_increase' and s['identity_profile']!='message_multiset':issues.append({'code':'newness_profile_mismatch','clause':i})
            if s['newness']=='index_absence' and s['identity_profile']!='position':issues.append({'code':'newness_profile_mismatch','clause':i})
        elif not c['query']['entity'].strip() or not c['query']['property'].strip():issues.append({'code':'empty_query_binding','clause':i})
    return {'valid':not issues,'issues':issues,'version':VERSION}

def _pattern_match(actual,pattern):
    """One segment per public * or {binding}; never arbitrary regex execution."""
    if not isinstance(pattern,str):return False
    tokens=pattern.strip('/').split('/');a=actual.strip('/').split('/')
    return len(tokens)==len(a) and all(x==y or x=='*' or re.fullmatch(r'\{[A-Za-z_][A-Za-z_0-9]*\}',x) for x,y in zip(tokens,a))

def _property_match(prop,requirement):
    name=requirement.get('property')
    pattern=requirement.get('property_pattern')
    return prop==name or bool(pattern and _pattern_match(prop,pattern))

def _type(v):
    if v is None:return 'null'
    if isinstance(v,bool):return 'boolean'
    if isinstance(v,(int,float)):return 'number'
    if isinstance(v,str):return 'string'
    if isinstance(v,list):return 'array'
    if isinstance(v,dict):return 'object'
    return 'unsupported'

def _compatible_operand(check,req):
    t=req.get('type');op=check['operator'];v=check['value']
    if op in {'exists','absent','changed'}:return True
    if t is None:return False
    if isinstance(t,list):return any(_compatible_operand(check,dict(req,type=x)) for x in t)
    if t in {'integer','float','int'}:t='number'
    if t in {'bool'}:t='boolean'
    if t in {'string_array','array[string]','list[string]'}:t='array';item='string'
    else:item=req.get('item_type')
    if op in {'member','not_member'}:return t=='array' and (item is None or _type(v)==item)
    if op=='contains':return t=='string' and isinstance(v,str)
    if op in {'gt','ge','lt','le'}:return t=='number' and _type(v)=='number'
    if op in {'date','month_day'}:return t=='string' and isinstance(v,str)
    return _type(v)==t

def _schema_resolve(schema,pointer):
    """Resolve a concrete data pointer with bounded LOCAL JSON-schema refs only."""
    tokens=parts(pointer)
    def walk(node,remaining,depth,seen):
        if depth>64 or not isinstance(node,dict):return False
        if '$ref' in node:
            ref=node['$ref']
            if not isinstance(ref,str) or not ref.startswith('#/'):return False
            marker=(ref,tuple(remaining))
            if marker in seen:return False
            try:target=at(schema,ref[1:])
            except InvalidIR:return False
            return target is not MISSING and walk(target,remaining,depth+1,seen|{marker})
        choices=node.get('anyOf') or node.get('oneOf')
        if choices:return any(walk(ch,remaining,depth+1,seen) for ch in choices)
        if not remaining:return bool(node)
        token=remaining[0]
        if node.get('type')=='array' or 'items' in node:
            if not re.fullmatch(r'0|[1-9][0-9]*',token):return False
            child=node.get('items',{})
        elif token in node.get('properties',{}):child=node['properties'][token]
        elif isinstance(node.get('additionalProperties'),dict):child=node['additionalProperties']
        else:return False
        return walk(child,remaining[1:],depth+1,seen)
    return walk(schema,tokens,0,set())

def _support_issues(support,packet,public_task=None):
    issues=[];request=packet.get('request',packet.get('task_request',packet.get('prompt','')))
    if not isinstance(request,str) or not support['request_quote'] or support['request_quote'] not in request:issues.append('invalid_request_quote')
    pre=packet.get('initial_state',packet.get('pre_state',packet.get('pre')))
    schema=packet.get('state_schema',packet.get('schema'))
    suite=(public_task or {}).get('task_key','/').split('/')[0]
    projected=schema.get('suites',{}).get(suite,schema) if isinstance(schema,dict) else schema
    for pointer in support['initial_state_paths']:
        try:ok=pre is not None and at(pre,pointer) is not MISSING
        except InvalidIR:ok=False
        if not ok:issues.append('unresolved_initial_pointer:'+pointer)
    for pointer in support['schema_paths']:
        try:
            # Schema pointers can address the schema object directly or resolve data paths.
            leaf=at(schema,pointer) if isinstance(schema,dict) else MISSING
            direct=leaf is not MISSING and not (isinstance(leaf,dict) and isinstance(leaf.get('$ref'),str) and not leaf['$ref'].startswith('#/'))
            ok=isinstance(schema,dict) and (direct or _schema_resolve(projected,pointer))
        except InvalidIR:ok=False
        if not ok:issues.append('unresolved_schema_pointer:'+pointer)
    if not support['initial_state_paths'] and not support['schema_paths']:issues.append('no_structural_source_witness')
    if not support['reason'].strip():issues.append('empty_support_reason')
    return issues

def preflight(contract,public_task,packet=None,policy='scope'):
    if policy not in {'scope','scope_source'}:raise ValueError('Unknown common admission policy')
    shape=validate(contract)
    if not shape['valid']:return {'admitted':False,'construction_valid':False,'issues':shape['issues'],'clauses':{},'coverage':{},'policy':policy}
    if contract['scope_id']!=public_task.get('scope_id'):
        return {'admitted':False,'construction_valid':True,'issues':[{'code':'scope_id_mismatch'}],'clauses':{},'coverage':{},'policy':policy}
    obligations={o['obligation_id']:o for o in public_task.get('obligations',[])}
    by_clause={c['obligation_id']:c for c in contract['clauses']};results={};allissues=[]
    extras=sorted(set(by_clause)-set(obligations));missing=sorted(set(obligations)-set(by_clause))
    for name in extras:allissues.append({'code':'additional_obligation','obligation_id':name})
    for name in missing:allissues.append({'code':'missing_obligation','obligation_id':name})
    for name,c in by_clause.items():
        if name not in obligations:continue
        o=obligations[name];issues=[]
        if c['kind']!=o['kind']:issues.append('kind_scope_mismatch')
        elif c['kind']=='state':
            s=c['state'];target=o.get('target',{});path=target.get('path');pattern=target.get('path_pattern')
            if not (s['path']==path or pattern and _pattern_match(s['path'],pattern)):issues.append('path_scope_mismatch')
            for key in ['identity_profile','identity_field']:
                if not equal(s[key],target.get(key)):issues.append(key+'_scope_mismatch')
            raw_new=o.get('newness','none')
            expected_new=raw_new.get('mode','none') if isinstance(raw_new,dict) else raw_new
            if s['newness']!=expected_new:issues.append('newness_scope_mismatch')
            reqs=o.get('required_properties',[])
            matched=[]
            for check in s['checks']:
                applicable=[i for i,req in enumerate(reqs) if _property_match(check['property'],req)]
                if len(applicable)!=1:issues.append('additional_or_ambiguous_property:'+check['property']);continue
                k=applicable[0];matched.append(k)
                if not _compatible_operand(check,reqs[k]):issues.append('operand_property_type_conflict:'+check['property'])
                required_op={'eq':'equals'}.get(reqs[k].get('operator'),reqs[k].get('operator'))
                if required_op and check['operator']!=required_op:issues.append('operator_scope_mismatch:'+check['property'])
            for i,req in enumerate(reqs):
                if matched.count(i)>1:issues.append('duplicate_required_property:'+str(req.get('property',req.get('property_pattern'))))
                if i not in matched:issues.append('missing_required_property:'+str(req.get('property',req.get('property_pattern'))))
            # Optional PUBLIC binding rule: a captured dynamic path segment must equal another check operand.
            for req in reqs:
                binding=req.get('binding')
                if not isinstance(binding,dict):continue
                checks=[x for x in s['checks'] if _property_match(x['property'],req)]
                other=[x for x in s['checks'] if x['property']==binding.get('value_property')]
                pattern=req.get('property_pattern','');tokens=pattern.strip('/').split('/')
                capture='{'+str(binding.get('capture'))+'}'
                if len(checks)!=1 or len(other)!=1 or capture not in tokens:issues.append('unsupported_public_binding_rule');continue
                value=checks[0]['property'].strip('/').split('/')[tokens.index(capture)]
                if not equal(value,other[0]['value']):issues.append('cross_entity_binding_mismatch')
            if s.get('selector') is not None:
                required_selectors=o.get('selector_requirements',[])
                for req in required_selectors:
                    candidates=[x for x in s['selector'] if x['field']==req['field']]
                    expected_type={'integer':'number'}.get(req.get('type'),req.get('type'))
                    if len(candidates)!=1:issues.append('missing_required_selector:'+req['field'])
                    elif _type(candidates[0]['value'])!=expected_type:issues.append('selector_type_conflict:'+req['field'])
                    elif req.get('type')=='integer' and not isinstance(candidates[0]['value'],int):issues.append('selector_integer_required:'+req['field'])
                for selector in s['selector']:
                    if selector['field'] not in {x['field'] for x in required_selectors}:issues.append('additional_selector:'+selector['field'])
            for rule in target.get('path_bindings',[]):
                tokens=(target.get('path_pattern') or '').strip('/').split('/');capture='{'+rule['capture']+'}'
                operands=[x['value'] for x in s['checks'] if x['property']==rule['value_property']]
                if capture not in tokens or len(operands)!=1:issues.append('unsupported_path_binding_rule');continue
                concrete=s['path'].strip('/').split('/')
                if tokens.index(capture)>=len(concrete):issues.append('path_binding_shape_mismatch');continue
                actual=concrete[tokens.index(capture)]
                if not equal(actual,operands[0]):issues.append('path_entity_binding_mismatch')
        else:
            q=c['query'];reqs=o.get('required_properties',[{'property':o.get('property'),'type':o.get('value_type')}])
            applicable=[r for r in reqs if _property_match(q['property'],r)]
            if len(reqs)!=1 or len(applicable)!=1:issues.append('query_property_scope_mismatch')
            elif not _compatible_operand({'operator':'equals','value':q['value']},applicable[0]):issues.append('query_value_type_conflict')
            for key,public_key in [('role','binding_role'),('unit','unit_scope'),('temporal_scope','temporal_scope')]:
                expected=o.get(public_key,o.get('unit') if key=='unit' else None)
                if not equal(q[key],expected):issues.append(key+'_scope_mismatch')
            entity_binding=o.get('entity_binding',{})
            if entity_binding.get('kind')=='task_subject' and q['entity']!=entity_binding.get('entity_label'):issues.append('task_subject_entity_scope_mismatch')
            if q['polarity']!={'affirmative':'positive'}.get(o.get('polarity'),o.get('polarity','positive')):issues.append('polarity_scope_mismatch')
        if policy=='scope_source':issues.extend(_support_issues(c['support'],packet or {},public_task))
        results[name]={'admitted':not issues,'issues':issues}
        allissues.extend({'code':x,'obligation_id':name} for x in issues)
    return {'admitted':not allissues and bool(obligations),'construction_valid':True,'issues':allissues,'clauses':results,'coverage':{'required':len(obligations),'present':len(set(by_clause)&set(obligations)),'missing':missing,'additional':extras},'policy':policy}

def aggregate(verdicts):
    if 'fail' in verdicts:return 'fail'
    if verdicts and all(x=='pass' for x in verdicts):return 'pass'
    return 'unknown'

def _atom(before,after,check,pre_observed=True):
    op,v=check['operator'],check['value']
    if op=='exists':return ('pass' if after is not MISSING else 'fail','observed_presence')
    if op=='absent':return ('pass' if after is MISSING else 'fail','observed_absence')
    if op=='changed':
        if not pre_observed:return 'unknown','missing_pre_observation'
        return ('pass' if before is not MISSING and after is not MISSING and not equal(before,after) else 'fail','observed_change')
    if after is MISSING:return 'fail','observed_property_absence'
    if op=='equals':return ('pass' if equal(after,v) else 'fail','typed_equality')
    if op in {'member','not_member'}:
        if not isinstance(after,list):return 'unknown','runtime_property_type_conflict'
        found=any(equal(x,v) for x in after)
        return ('pass' if found==(op=='member') else 'fail','observed_membership')
    if op=='contains':
        if not isinstance(after,str):return 'unknown','runtime_property_type_conflict'
        return ('pass' if normalized(v) in normalized(after) else 'fail','literal_containment')
    if op in {'gt','ge','lt','le'}:
        if _type(after)!='number':return 'unknown','runtime_property_type_conflict'
        ok={'gt':lambda:aft>v,'ge':lambda:aft>=v,'lt':lambda:aft<v,'le':lambda:aft<=v};aft=after
        return ('pass' if ok[op]() else 'fail','numeric_comparison')
    if op in {'date','month_day'}:
        if not isinstance(after,str):return 'unknown','runtime_property_type_conflict'
        try:day=datetime.date.fromisoformat(after[:10])
        except ValueError:return 'unknown','unsupported_date_representation'
        target=day.isoformat() if op=='date' else day.strftime('%m-%d')
        return ('pass' if target==v else 'fail','date_field')
    return 'unknown','unsupported_operator'

def _items(value,profile):
    if value is MISSING:return []
    if profile=='singleton':return [(None,value)]
    if isinstance(value,list):return list(enumerate(value))
    if isinstance(value,dict):return list(value.items())
    return None

def _identity(item,key,s):
    profile=s['identity_profile'];field=s['identity_field']
    if profile in {'position','dict_key'}:return key
    if profile=='singleton':return None
    if profile=='scalar_set':return json.dumps(item,sort_keys=True,separators=(',',':'),ensure_ascii=False)
    if profile=='stable_id':
        value=at(item,field,relative=True)
        if value is MISSING or isinstance(value,(list,dict,bool)) or value is None:return MISSING
        return ('id',type(value).__name__,value)
    if profile=='message_multiset':
        values=[at(item,p,relative=True) for p in field]
        if any(v is MISSING for v in values):return MISSING
        return json.dumps(values,sort_keys=True,separators=(',',':'),ensure_ascii=False)
    return MISSING

def state_clause(s,pre,post):
    if post is None:return {'verdict':'unknown','reason':'missing_post_observation'}
    after=at(post,s['path']);before=at(pre,s['path']) if pre is not None else MISSING
    aft=_items(after,s['identity_profile']);bef=_items(before,s['identity_profile'])
    if aft is None or bef is None:return {'verdict':'unknown','reason':'runtime_collection_type_conflict'}
    def selected(item):return all(equal(at(item,x['field'],relative=True),x['value']) for x in s['selector'])
    before_by={};after_ids=[]
    for key,item in bef:
        identity=_identity(item,key,s)
        if identity is MISSING:return {'verdict':'unknown','reason':'unwitnessed_entity_identity'}
        before_by.setdefault(identity,[]).append(item)
    for key,item in aft:
        identity=_identity(item,key,s)
        if identity is MISSING:return {'verdict':'unknown','reason':'unwitnessed_entity_identity'}
        after_ids.append(identity)
    if s['identity_profile']=='stable_id' and (any(len(v)>1 for v in before_by.values()) or len(after_ids)!=len(set(after_ids))):return {'verdict':'unknown','reason':'duplicate_stable_id'}
    # An absent singleton field is observed absence, not missing observation.
    if not aft and s['identity_profile']=='singleton':aft=[(None,MISSING)]
    # Whole-entity deletion: selection constrains the entity, not an empty post-state.
    if all(c['property']=='$value' and c['operator']=='absent' for c in s['checks']) and s['identity_profile']!='singleton':
        if pre is None:return {'verdict':'unknown','reason':'missing_pre_observation'}
        existed=any(selected(item) for _,item in bef);remains=any(selected(item) for _,item in aft)
        return {'verdict':'pass' if existed and not remains else 'fail','reason':'observed_entity_deletion'}
    results=[]
    newness_missing=s['newness']!='none' and pre is None
    after_counts=collections.Counter(after_ids)
    for key,item in aft:
        if not selected(item):continue
        identity=_identity(item,key,s);old=before_by.get(identity,[])
        if s['newness'] in {'pre_id_absence','pre_key_absence','index_absence'} and old:continue
        if s['newness']=='count_increase' and after_counts[identity]<=len(old):continue
        previous=old[0] if old else MISSING
        atoms=[_atom(at(previous,c['property'],True),at(item,c['property'],True),c,pre is not None) for c in s['checks']]
        verdict=aggregate([x[0] for x in atoms]+(['unknown'] if newness_missing else []))
        results.append({'verdict':verdict,'identity':str(identity),'checks':[{'property':c['property'],'verdict':x[0],'reason':x[1]} for c,x in zip(s['checks'],atoms)]})
    if any(x['verdict']=='pass' for x in results):verdict='pass'
    elif any(x['verdict']=='unknown' for x in results) or newness_missing:verdict='unknown'
    else:verdict='fail'
    return {'verdict':verdict,'reason':'same_entity_conjunction','entities':results}

NUMERIC = re.compile(r'-?\d+(?:,\d{3})*(?:\.\d+)?')
def _parse_value(text):
    text=text.strip()
    token=re.match(r'-?\d+(?:,\d{3})*(?:\.\d+)?(?![\w.])',text)
    if token:
        return decimal.Decimal(token.group().replace(',','')),text[token.end():].strip()
    for word,value in [('true',True),('false',False),('null',None)]:
        if text.casefold()==word:return value,''
    return text.strip(),' '

def _query_equal(actual,expected):
    if isinstance(actual,decimal.Decimal):
        if isinstance(expected,bool) or not isinstance(expected,(int,float)):return False
        return actual==decimal.Decimal(str(expected))
    if isinstance(actual,str) and isinstance(expected,str):return normalized(actual)==normalized(expected)
    return equal(actual,expected)

def parse_assertions(output,properties):
    """Closed field-bound grammar; it is deliberately not an LLM semantic judge."""
    if output is None:return {'assertions':[],'unsupported':False,'missing_output':True,'empty_output':False,'complete_entities':[]}
    if not isinstance(output,str):return {'assertions':[],'unsupported':True,'missing_output':False,'empty_output':False,'complete_entities':[]}
    if not output.strip():return {'assertions':[],'unsupported':False,'missing_output':False,'empty_output':True,'complete_entities':[]}
    # Quoted material is mention-only. Supported assertions outside quotes remain usable.
    text=re.sub(r'"[^"\n]*"|“[^”\n]*”|\'[^\'\n]*\'', ' ',output)
    props=sorted(set(properties)-{'name','entity','selected_entity'},key=len,reverse=True)
    aliases={p:p for p in props}
    for p in props:
        aliases[p.replace('_',' ')]=p
    prop_pattern='|'.join(re.escape(x) for x in sorted(aliases,key=len,reverse=True)) or r'(?!)'
    assertions=[];unsupported=False;context=None;context_role=None;complete_entities=[];complete_bindings=[]
    segments=re.split(r'[\n;!?]+|\.(?!\d)',text)
    for raw in segments:
        seg=normalized(raw)
        if not seg:continue
        n=normalized(seg)
        if re.search(r'\b(if|maybe|might|hypothetical|uncertain|unsure|cannot determine|unknown)\b',n):unsupported=True;continue
        selection=re.fullmatch(r'(?:i recommend|i select|selected (?:company|hotel|car|entity) is|the selected (?:company|hotel|car|entity) is)\s+(.+)',seg,re.I)
        if selection and not re.search(prop_pattern,normalized(selection.group(1))):
            entity=selection.group(1).strip();assertions.append({'entity':entity,'property':'name','value':entity,'polarity':'positive','unit':None,'temporal_scope':None});context=entity;context_role=None;complete_entities.append(entity);complete_bindings.append((entity,None));continue
        found=list(re.finditer(r'(?<!\w)('+prop_pattern+r')(?!\w)',n))
        if not found:
            if len(segments)==1 and len(seg)<=120 and not re.search(r'\b(not|no|never|wrong|incorrect|rather than|recommend|is|are|has)\b',n):
                assertions.append({'entity':seg,'property':'name','value':seg,'polarity':'positive','unit':None,'temporal_scope':None});complete_entities.append(seg);complete_bindings.append((seg,None))
            else:unsupported=True
            continue
        prefix=seg[:found[0].start()].strip(' \t—–:-,')
        prefix=re.sub(r'^(?:i recommend|i select|the selected company is|selected company is)\s+','',prefix,flags=re.I)
        prefix=re.sub(r"(?:\s+has(?:\s+a)?|\s+with|\s+is|\s+offers|['’]s)$",'',prefix,flags=re.I).strip()
        if prefix:
            tagged=re.fullmatch(r'\[([A-Za-z_][A-Za-z_0-9]*)\]\s+(.+)',prefix)
            context_role=tagged.group(1) if tagged else None
            prefix=tagged.group(2) if tagged else prefix
            if re.search(r'\b(not|never|no|wrong|incorrect|rather than)\b',normalized(prefix)):unsupported=True;continue
            flight=re.fullmatch(r'flight\s+([A-Za-z][A-Za-z0-9-]*)',prefix,re.I)
            if flight:
                prefix=flight.group(1)
                assertions.append({'entity':prefix,'property':'flight_number','value':prefix,'polarity':'positive','unit':None,'temporal_scope':None,'role':context_role})
            context=prefix
            assertions.append({'entity':context,'property':'name','value':context,'polarity':'positive','unit':None,'temporal_scope':None,'role':context_role})
        if not context:unsupported=True;continue
        start_count=len(assertions);segment_supported=True
        for k,m in enumerate(found):
            tail=seg[m.end():found[k+1].start() if k+1<len(found) else len(seg)].strip(' ,')
            tail=re.sub(r'^(?:is|of|equals|=|:)\s*','',tail,flags=re.I)
            polarity='positive'
            if re.match(r'^(?:not|is not|!=)\b\s*',tail,re.I):
                polarity='negative';tail=re.sub(r'^(?:not|is not|!=)\b\s*','',tail,flags=re.I)
            if not tail:unsupported=True;segment_supported=False;continue
            value,remainder=_parse_value(tail)
            unit=None;temporal=None
            if isinstance(value,decimal.Decimal):
                rem=normalized(remainder).strip(' ,')
                if rem:
                    unit_match=re.fullmatch(r'(usd|eur|gbp|dollars|euros|\$|€|£|points)(?:\s+(?:for|over)\s+(\d+)\s+days?)?',rem)
                    time_match=re.fullmatch(r'(?:for|over)\s+(\d+)\s+(days?|people|persons?|passengers?)',rem)
                    if unit_match:
                        unit={'dollars':'USD','usd':'USD','$':'USD','euros':'EUR','eur':'EUR','€':'EUR','gbp':'GBP','£':'GBP','points':'rating_points'}[unit_match.group(1)]
                        if unit_match.group(2):temporal=unit_match.group(2)+'_days'
                    elif time_match:temporal=time_match.group(1)+('_days' if time_match.group(2).startswith('day') else '_people')
                    else:unsupported=True;segment_supported=False;continue
            assertions.append({'entity':context,'property':aliases[m.group(1)],'value':value,'polarity':polarity,'unit':unit,'temporal_scope':temporal,'role':context_role})
        if segment_supported and len(assertions)>start_count:complete_entities.append(context);complete_bindings.append((context,context_role))
    return {'assertions':assertions,'unsupported':unsupported,'missing_output':False,'empty_output':False,'complete_entities':complete_entities,'complete_bindings':complete_bindings}

def _unit_matches(actual,expected):
    if actual is None or expected is None:return True
    a,e=normalized(actual),normalized(expected)
    if e in {'money_total','money_amount'}:return a in {'usd','eur','gbp','money_total','money_amount'}
    return a==e

def _time_matches(actual,expected):
    if actual is None or expected is None:return True
    a,e=normalized(actual),normalized(expected)
    canonical={'7_days':'seven_day_rental','3_days':'three_day_rental_per_car','4_days':'four_day_rental','2_people':'two_person_flight'}
    return canonical.get(a,a)==e

def _receipt_assertion(a):
    return {k:(str(v) if isinstance(v,decimal.Decimal) else v) for k,v in a.items()}

def query_clause(q,parsed,entity_binding=None):
    if parsed['missing_output']:return {'verdict':'unknown','reason':'missing_output_observation'}
    if parsed['empty_output']:return {'verdict':'fail','reason':'observed_empty_answer'}
    property_name='name' if q['property'] in {'name','entity','selected_entity'} else q['property']
    entity_binding=entity_binding or {}
    aliases={normalized(x):normalized(entity_binding.get('entity_label',q['entity'])) for x in entity_binding.get('accepted_labels',[])}
    entity_key=lambda e:aliases.get(normalized(e),normalized(e))
    role_ok=lambda a:a.get('role') is None or normalized(a['role'])==normalized(q['role'])
    records=[a for a in parsed['assertions'] if entity_key(a['entity'])==entity_key(q['entity']) and a['property']==property_name and role_ok(a)]
    if not records:
        complete=not parsed['unsupported'] and any(entity_key(e)==entity_key(q['entity']) for e in parsed['complete_entities'])
        return {'verdict':'fail' if complete else 'unknown','reason':'observed_property_or_role_omission' if complete else 'no_bound_property_assertion'}
    good=False;contradictions=[]
    for a in records:
        same=_query_equal(a['value'],q['value'])
        # Omitted qualifiers use declared request context; money dimensions do not certify currency.
        scope_wrong=not _unit_matches(a['unit'],q['unit']) or not _time_matches(a['temporal_scope'],q['temporal_scope'])
        expected_positive=q['polarity']=='positive'
        if scope_wrong or (a['polarity']=='positive' and ((expected_positive and not same) or (not expected_positive and same))) or (a['polarity']=='negative' and expected_positive and same):contradictions.append(a)
        if same and a['polarity']==q['polarity'] and not scope_wrong:good=True
    if contradictions:return {'verdict':'fail','reason':'explicit_bound_contradiction','contradictions':[_receipt_assertion(a) for a in contradictions]}
    if good and not parsed['unsupported']:return {'verdict':'pass','reason':'bound_assertion','currency_certified':False if q['unit'] in {'money_total','money_amount'} else None}
    return {'verdict':'unknown','reason':'unsupported_or_incomplete_assertion_grammar'}

def evaluate(contract,pre,post,output,*,public_task=None,packet=None,policy='scope'):
    shape=validate(contract)
    if not shape['valid']:return {'verdict':'error','reason':'construction_invalid','issues':shape['issues'],'obligations':{},'version':VERSION}
    if contract['classification']=='unknown':return {'verdict':'unknown','reason':'builder_abstention','obligations':{},'version':VERSION}
    admission=preflight(contract,public_task,packet,policy) if public_task is not None else {'construction_valid':True,'clauses':{c['obligation_id']:{'admitted':True,'issues':[]} for c in contract['clauses']},'coverage':{'missing':[],'additional':[]},'issues':[],'admitted':True}
    if not admission['construction_valid']:return {'verdict':'error','reason':'construction_invalid','issues':admission['issues'],'obligations':{},'version':VERSION}
    if public_task is not None and contract['scope_id']!=public_task.get('scope_id'):return {'verdict':'unknown','reason':'scope_id_mismatch','admission':admission,'obligations':{},'version':VERSION}
    results={name:{'verdict':'unknown','reason':'missing_obligation'} for name in admission['coverage'].get('missing',[])}
    query_properties=[c['query']['property'] for c in contract['clauses'] if c['kind']=='query']
    parsed=parse_assertions(output,query_properties) if query_properties else None
    for c in contract['clauses']:
        name=c['obligation_id'];gate=admission['clauses'].get(name)
        if gate is None:continue
        if not gate['admitted']:results[name]={'verdict':'unknown','reason':'unsupported_scope_or_source','issues':gate['issues']};continue
        requirement=next((o for o in (public_task or {}).get('obligations',[]) if o['obligation_id']==name),{})
        absent=[obs for obs in requirement.get('observation_requirements',[]) if {'pre_state':pre,'post_state':post,'output':output}.get(obs) is None]
        if absent:results[name]={'verdict':'unknown','reason':'missing_required_observation','missing':absent};continue
        results[name]=state_clause(c['state'],pre,post) if c['kind']=='state' else query_clause(c['query'],parsed,requirement.get('entity_binding'))
    verdict=aggregate([x['verdict'] for x in results.values()])
    if verdict=='pass' and admission['coverage'].get('additional'):verdict='unknown'
    return {'verdict':verdict,'reason':'common_scope_aggregation','admission':admission,'obligations':results,'version':VERSION}

if __name__=='__main__':
    (Path(__file__).parent/'output_schema.json').write_text(json.dumps(SCHEMA,indent=2)+'\n')
