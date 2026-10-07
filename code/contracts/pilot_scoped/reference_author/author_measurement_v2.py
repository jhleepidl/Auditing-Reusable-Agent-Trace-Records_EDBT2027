"""Source-only value-free R21B scope and oracle-assisted compiler versioning.

Preserves all R21A files. Changes no source packet, source selection, expected
entity/value, obligation ID, reference grammar or reference decision semantics.
No candidate, model, prediction or executor implementation is imported.
"""
from __future__ import annotations
import copy
import hashlib
import json
import sys
from pathlib import Path
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def canonical(v):return hashlib.sha256(json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def write_new(path, value):
    if path.exists():raise SystemExit('Versioned artifact exists; no overwrite: '+str(path))
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')


def main():
    old=json.loads((HERE/'common_scopes.json').read_text())
    new=copy.deepcopy(old)
    new['version']='r21_common_source_scope_v1.2'
    new['previous_public_scope_file']='common_scopes.json'
    new['previous_public_scope_sha256']=sha(HERE/'common_scopes.json')
    new['measurement_revision']='Explicit value-free airline_name entity convention; source goals and reference grammar unchanged.'
    changes=[]
    for task in new['tasks']:
        old_task=next(t for t in old['tasks'] if t['task_key']==task['task_key'])
        task['scope_id']=task['task_key'].replace('/','__')+'__common_source_v2'
        task['supersedes_scope_id']=old_task['scope_id']
        task['supersedes_scope_sha256']=old_task['scope_sha256']
        for obligation in task['obligations']:
            if task['task_key']=='travel/user_task_16' and obligation['binding_role']=='paris_london_flight':
                obligation['entity_form']='airline_name'
                obligation['entity_binding']['source_field']='airline_name'
                obligation['entity_binding']['native_source_path']='/flights/flight_list/*/airline'
                obligation['entity_binding']['source_entity_value_disclosed']=False
                changes.append(obligation['obligation_id'])
        task['scope_sha256']=canonical({k:v for k,v in task.items() if k!='scope_sha256'})
    assert len(changes)==2
    assert all(a['source_packet_sha256']==b['source_packet_sha256'] and a['required_obligation_ids']==b['required_obligation_ids'] for a,b in zip(old['tasks'],new['tasks']))
    write_new(HERE/'common_scopes_v2.json',new)
    from compile_source_sanity import compile_scope
    contracts=[]
    for scope in new['tasks']:
        contract=compile_scope(scope);contract['ir_version']='r21.2'
        for clause in contract['clauses']:
            if clause['query'] and clause['query']['role']=='paris_london_flight':
                clause['support']['schema_paths'].append('/$defs/Flight/properties/airline')
        contracts.append({'task_key':scope['task_key'],'phase':scope['phase'],'source_packet_sha256':scope['source_packet_sha256'],
                          'scope_sha256':scope['scope_sha256'],'designation':'oracle-assisted source compiler sanity; never competitive construction',
                          'contract':contract})
    target=HERE/'compiler_sanity/contracts_v2.jsonl'
    if target.exists():raise SystemExit('Compiler v2 exists; no overwrite.')
    target.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in contracts))
    old_contracts={r['task_key']:r['contract'] for r in [json.loads(s) for s in (HERE/'compiler_sanity/contracts.jsonl').read_text().splitlines()]}
    for row in contracts:
        a,b=row['contract'],old_contracts[row['task_key']]
        assert a['classification']==b['classification'] and a['unknown_reason']==b['unknown_reason']
        assert len(a['clauses'])==len(b['clauses'])
        for x,y in zip(a['clauses'],b['clauses']):
            assert all(x[k]==y[k] for k in ['obligation_id','kind','state','query'])
    report={'version':'r21b_source_compiler_sanity_v2','designation':'oracle-assisted source compiler sanity, not competitive construction or full-task gold',
      'humans':0,'source_only':True,'candidate_or_model_outputs_read':False,'public_expected_values_disclosed':False,
      'tasks':57,'supported_scopes':27,'obligations':43,'changed_obligation_metadata_ids':changes,
      'source_packets_selection_goals_and_compiler_operands_unchanged':True,'reference_parser_and_decision_semantics_unchanged':True,
      'original_scope_sha256':sha(HERE/'common_scopes.json'),'versioned_scope_sha256':sha(HERE/'common_scopes_v2.json'),
      'compiler_contracts_v2_sha256':sha(target),'compiler_version':'r21.2','native_schema_pointer_addition':'/$defs/Flight/properties/airline',
      'confirmation_cases_materialized':0,'schema_preflight':'pending root public r21.2 schema'}
    write_new(HERE/'compiler_sanity/REPORT_v2.json',report)
    print(json.dumps(report))

if __name__=='__main__':main()
