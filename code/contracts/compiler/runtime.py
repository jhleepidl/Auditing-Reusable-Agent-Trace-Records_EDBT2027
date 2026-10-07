"""Public-scope scalar scaffolding; delegates DAG execution to frozen V1.

No task dispatch, answer constants, semantic reference, or observation access.
"""
from __future__ import annotations
import copy
import hashlib
import importlib.util
import json
import re
from pathlib import Path
from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent
CORE_PATH = HERE.parent / 'derivation' / 'runtime.py'
CORE_SHA256 = '14d48bf9dae94e73d1f98f0464068553979f2ade010fc8dfcbe73de55ff14aed'
if hashlib.sha256(CORE_PATH.read_bytes()).hexdigest() != CORE_SHA256:
    raise RuntimeError('frozen_V1_DAG_runtime_hash_mismatch')
_spec = importlib.util.spec_from_file_location('r22_frozen_derivation_core', CORE_PATH)
core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(core)
VERSION = 'r22.2'


def _type(declaration):
    name = declaration.get('operand_type', declaration.get('value_type', declaration.get('type', 'string')))
    aliases = {'int':'integer', 'float':'number', 'bool':'boolean'}
    name = aliases.get(name, name)
    if name not in ('number','integer','string','boolean'):
        raise ValueError('scalar_endpoint_type_required:' + str(name))
    return name


def _placeholder(kind):
    return {'number':0, 'integer':0, 'string':'', 'boolean':False}[kind]


def _name(text):
    text = re.sub(r'[^a-z0-9]+', '_', text.lower()).strip('_')
    return text or 'value'


def build_scaffold(public_scope):
    """Generate only public structural fields and typed zero/empty placeholders.

    The argument is a single public task scope, never a source packet. Every
    nonstructural scalar is an endpoint; no source value is resolved here.
    """
    obligations = public_scope.get('obligations', [])
    kinds = {o['kind'] for o in obligations}
    if len(kinds) > 1:
        raise ValueError('ordinary_contract_requires_one_classification')
    classification = next(iter(kinds), 'unknown')
    if not public_scope.get('supported', bool(obligations)):
        classification = 'unknown'
        obligations = []
    contract = {'ir_version':'r22.1', 'scope_id':public_scope['scope_id'],
                'classification':classification, 'clauses':[], 'unknown_reason':''}
    endpoints = {}

    def endpoint(i, label, target, declaration, obligation, **extra):
        base = f'o{i}_' + _name(label)
        key = base
        serial = 2
        while key in endpoints:
            key = base + '_' + str(serial); serial += 1
        scalar_type = _type(declaration)
        endpoints[key] = {'target':target, 'scalar_type':scalar_type,
                          'obligation_id':obligation['obligation_id'],
                          'binding_role':obligation.get('binding_role', ''),
                          'placeholder':_placeholder(scalar_type), **extra}
        return _placeholder(scalar_type)

    for i, obligation in enumerate(obligations):
        prefix = f'/clauses/{i}'
        clause = {'obligation_id':obligation['obligation_id'], 'kind':obligation['kind'],
                  'state':None, 'query':None,
                  'support':{'request_quote':public_scope.get('task_request',''),
                             'initial_state_paths':[''], 'schema_paths':[''],
                             'reason':'Public scope fixes this obligation structure; source operands remain model claims or executable derivations.'}}
        if obligation['kind'] == 'state':
            target = obligation['target']
            state = {'path':target.get('path', target.get('path_pattern','')),
                     'identity_profile':target['identity_profile'],
                     'identity_field':copy.deepcopy(target.get('identity_field')),
                     'newness':obligation.get('newness','none'), 'selector':[], 'checks':[]}
            for j, requirement in enumerate(obligation.get('selector_requirements', [])):
                field = requirement['field']
                value = endpoint(i, 'selector_' + field, prefix + f'/state/selector/{j}/value', requirement, obligation)
                state['selector'].append({'field':field,'value':value})
            for j, requirement in enumerate(obligation.get('required_properties', [])):
                prop = requirement.get('property', requirement.get('property_pattern'))
                if prop is None: raise ValueError('required_property_missing')
                label = prop if 'property' in requirement else prop.split('{',1)[0].rstrip('/')
                value = endpoint(i, label, prefix + f'/state/checks/{j}/value', requirement, obligation,
                                 property=prop, operator=requirement['operator'])
                state['checks'].append({'property':prop,
                                        'operator':'equals' if requirement['operator']=='eq' else requirement['operator'],
                                        'value':value})
                if 'property_pattern' in requirement:
                    endpoint(i, 'dynamic_property', prefix + f'/state/checks/{j}/property',
                             {'type':'string'}, obligation, pattern=prop,
                             capture_bindings=copy.deepcopy(requirement.get('binding',{})))
            if 'path_pattern' in target:
                endpoint(i, 'dynamic_path', prefix + '/state/path', {'type':'string'}, obligation,
                         pattern=target['path_pattern'], capture_bindings=copy.deepcopy(target.get('path_bindings',[])))
            clause['state'] = state
        elif obligation['kind'] == 'query':
            entity = endpoint(i, 'entity', prefix + '/query/entity', {'type':'string'}, obligation,
                              entity_binding=copy.deepcopy(obligation.get('entity_binding',{})))
            value = endpoint(i, obligation['property'], prefix + '/query/value', obligation, obligation)
            clause['query'] = {'entity':entity, 'property':obligation['property'], 'value':value,
                               'unit':obligation.get('unit'), 'temporal_scope':obligation.get('temporal_scope'),
                               'role':obligation.get('binding_role',''),
                               'polarity':'positive' if obligation.get('polarity','affirmative') in ('affirmative','positive') else 'negative'}
        else:
            raise ValueError('unsupported_public_obligation_kind')
        contract['clauses'].append(clause)
    # Keep dynamic placeholders scalar and value-free; patterns are public metadata.
    for endpoint_data in endpoints.values():
        core.put(contract, endpoint_data['target'], endpoint_data['placeholder'])
    required = set(core.required_binding_targets(contract, public_scope))
    # Dynamic-property recognition in V1 uses the public literal prefix. The
    # placeholder is empty, so explicitly include the public declared target.
    required.update(e['target'] for e in endpoints.values() if 'pattern' in e)
    if required != {e['target'] for e in endpoints.values()}:
        raise ValueError('public_scaffold_endpoint_coverage_mismatch')
    return {'derivation_version':VERSION, 'contract_template':contract,
            'endpoints':endpoints,
            'designation':'public structure supplied; source operand construction evaluated, specification discovery not evaluated'}


def schema_for_scope(public_scope):
    scaffold = build_scaffold(public_scope)
    operand_properties = {}
    for key, metadata in scaffold['endpoints'].items():
        operand_properties[key] = {
            'type':'object', 'properties':{
                'claim':{'type':metadata['scalar_type']},
                'node':{'type':['string','null'], 'pattern':'^[a-z][a-z0-9_]{0,31}$'}},
            'required':['claim','node'], 'additionalProperties':False}
    return {'type':'object', 'properties':{
        'derivation_version':{'type':'string','enum':[VERSION]},
        'classification':{'type':'string','enum':['state','query','unknown']},
        'unknown_reason':{'type':'string'},
        'operands':{'type':'object','properties':operand_properties,
                    'required':list(operand_properties),'additionalProperties':False},
        'nodes':copy.deepcopy(core.SCHEMA['properties']['nodes'])},
        'required':['derivation_version','classification','unknown_reason','operands','nodes'],
        'additionalProperties':False}


output_schema = schema_for_scope


def normalize_annotation(annotation, public_scope, *, mode='derived'):
    """Validate fixed endpoints and mechanically produce a V1 annotation."""
    if mode not in ('literal','derived','verified'):
        raise ValueError('invalid_compilation_mode')
    errors = sorted(Draft202012Validator(schema_for_scope(public_scope)).iter_errors(annotation), key=lambda e:str(list(e.path)))
    if errors:
        raise ValueError('schema:' + str(list(errors[0].path)) + ':' + errors[0].message)
    scaffold = build_scaffold(public_scope)
    contract = copy.deepcopy(scaffold['contract_template'])
    classification = annotation['classification']
    if classification != 'unknown' and classification != contract['classification']:
        raise ValueError('classification_disagrees_with_public_scope')
    if classification != 'unknown' and annotation['unknown_reason']:
        raise ValueError('supported_classification_requires_empty_unknown_reason')
    if classification == 'unknown':
        if not annotation['unknown_reason'].strip():
            raise ValueError('abstention_requires_reason')
        if annotation['nodes'] or any(v['node'] is not None for v in annotation['operands'].values()):
            raise ValueError('abstention_requires_empty_program_and_null_nodes')
        contract.update(classification='unknown',clauses=[],unknown_reason=annotation['unknown_reason'])
        return {'derivation_version':'r22.1','contract':contract,'nodes':[],'bindings':[]}
    bindings = []
    for key, metadata in scaffold['endpoints'].items():
        operand = annotation['operands'][key]
        core.put(contract, metadata['target'], copy.deepcopy(operand['claim']))
        if mode == 'literal':
            if operand['node'] is not None:
                raise ValueError('literal_mode_requires_null_endpoint_nodes')
        else:
            if operand['node'] is None:
                raise ValueError('derived_mode_requires_every_endpoint_node:' + key)
            bindings.append({'target':metadata['target'],'node':operand['node']})
    if mode == 'literal' and annotation['nodes']:
        raise ValueError('literal_mode_requires_empty_program')
    return {'derivation_version':'r22.1','contract':contract,
            'nodes':copy.deepcopy(annotation['nodes']),'bindings':bindings}


def compile_annotation(annotation, packet, public_scope, *, mode='derived', public_facts=None):
    """Return the V1 receipt plus an auditable scaffold/normalization receipt."""
    try:
        normalized = normalize_annotation(annotation, public_scope, mode=mode)
        scaffold = build_scaffold(public_scope)
        targets = [e['target'] for e in scaffold['endpoints'].values()]
        result = core.compile_annotation(normalized, packet, public_scope, mode=mode,
                                         public_facts=public_facts, required_targets=targets)
        if result['status'] == 'ok' and normalized['contract']['classification'] != 'unknown':
            for key, metadata in scaffold['endpoints'].items():
                value = core.get(result['contract'],metadata['target'],allow_none=True)
                if not Draft202012Validator({'type':metadata['scalar_type']}).is_valid(value):
                    raise ValueError('derived_endpoint_scalar_type_mismatch:' + key)
        result.setdefault('provenance',{})['normalization'] = {
            'version':VERSION, 'input_annotation_sha256':core.digest(annotation),
            'normalized_annotation_sha256':core.digest(normalized),
            'scaffold_sha256':core.digest(scaffold), 'schema_sha256':core.digest(schema_for_scope(public_scope)),
            'core_runtime_sha256':CORE_SHA256, 'endpoint_count':len(targets),
            'endpoint_targets':{k:v['target'] for k,v in scaffold['endpoints'].items()}}
        return result
    except (ValueError, KeyError, TypeError, core.InvalidIR, core.UnknownDerivation) as error:
        return {'status':'error','contract':None,'provenance':{'normalization_version':VERSION,'core_runtime_sha256':CORE_SHA256},
                'diagnostics':[{'kind':'construction_error','reason':str(error)}]}
