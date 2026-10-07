"""Freeze source-only common-scope construction requests; no case/reference reads."""
import argparse, copy, json
from pathlib import Path
from common21 import ROOT, BASE, load, write, write_rows, sha, canonical_sha, now
COMMON = '''Construct a conservative partial evaluation contract from the supplied task request and initial state, ONLY for the listed public common_scope obligations. This scope may omit parts of the full request. Do not add them. Public metadata contains permitted kinds, paths, operators, property types, identity profiles, newness and role bindings, not the resolved expected values. You must derive operand values from the source packet. Copy scope_id and each required obligation_id exactly. Emit exactly one clause for each required obligation, with all required state properties jointly checked on the SAME entity. If any selected obligation cannot be derived safely, classify the task unknown with clauses [] and a specific unknown_reason. If no obligations are selected, return unknown; do not expand semantic authority. No post-state or evaluator labels are provided.
Use IR version r21.1. State path is the concrete COLLECTION or singleton pointer, never wildcard syntax. Selector uses {field,value} objects; checks use {property,operator,value}. Public eq maps to equals. Scalar collection members use property $value. Respect identity_field and newness exactly; newly created transactions use stable IDs compared against pre-state, never list index. Public dynamic path/property bindings must hold. A scheduled update must select the initial transaction ID. Slack membership checks jointly bind users membership and user_channels/{that same user} membership. Query clauses bind entity, property, value, unit, temporal_scope, public binding_role and positive polarity (public affirmative). If public entity_label is supplied use that exact protocol subject label; for rental company and flight facts use the source-derived company name or flight number. Numeric values are JSON numbers, not strings. A rating and monetary total are different properties; keep role/unit/temporal scope exact. The unused state/query payload is null. Support must have an exact request substring, concrete initial_state_paths or schema_paths, and reason; these witnesses support a derivation but do not certify semantic necessity. Unknown uses an empty clauses array. Reply only with the strict schema JSON object.'''
ARM = {
 'direct': 'Derive the scoped contract directly from the request and initial state using the common public obligations.',
 'schema_only': 'Use the supplied native state_schema to check paths and JSON operand types while deriving the scoped contract. Schema consistency alone does not determine expected values.',
 'evidence_bound': 'Before emitting each clause, internally identify the exact request span, relevant initial-state facts and the necessary relation for that obligation. Compute source-conditioned amounts/selections explicitly; distinguish evidence from guesses. Check that every check/property belongs to the selected scope. Bind expected fields to one entity and verify stable-ID/newness requirements. Fill support with precise source pointers and a concise calculation/selection reason. If evidence does not justify a complete scoped obligation, abstain.'
}
def main():
 p=argparse.ArgumentParser();p.add_argument('--phase',choices=['smoke','development','confirmation'],required=True);p.add_argument('--version',default='v1');p.add_argument('--out',type=Path,required=True);a=p.parse_args();assert not a.out.exists()
 protocol=load(ROOT/'e2/PROTOCOL.json');scopes=load(ROOT/'e2/reference_author/common_scopes.json');packets=load(ROOT/'e2/reference_author/source_snapshot/task_packets.json');ps={v['task_key']:v['packet'] for v in packets}
 schema_path=ROOT/'e2/method_v1/output_schema.json';schema=load(schema_path);schema.pop('$schema',None)
 tasks=[t for t in scopes['tasks'] if t['task_key']=='banking/user_task_0'] if a.phase=='smoke' else [t for t in scopes['tasks'] if (t['phase']=='development')==(a.phase=='development')]
 seeds=[13] if a.phase!='confirmation' else protocol['confirmation']['seeds'];out=[]
 for t in tasks:
  packet=ps[t['task_key']];assert canonical_sha(packet)==t['source_packet_sha256']
  for model in protocol['models']:
   for arm in protocol['construction_arms']:
    suite=t['task_key'].split('/')[0]
    inp={'source_packet':packet,'source_packet_sha256':t['source_packet_sha256'],'common_scope':t,'scope_sha256':t['scope_sha256']}
    if arm!='direct':inp['state_schema']=load(BASE/f'work/native/EDBT_R18_CPU_RESULTS/EDBT_R18_NO_HUMAN_KIT/inputs/r11/schemas/{suite}.json')
    for seed in seeds:
     r={'phase':a.phase,'version':a.version,'task_key':t['task_key'],'method':arm,'model':model,'seed':seed,'system':COMMON+'\n'+ARM[arm],'input':copy.deepcopy(inp),'output_schema':schema,'max_output_tokens':3000}
     r['request_id']=canonical_sha(r);out.append(r)
 a.out.mkdir(parents=True);write_rows(a.out/'requests.jsonl',out)
 write(a.out/'FREEZE.json',{'utc':now(),'phase':a.phase,'version':a.version,'request_count':len(out),'tasks':len(tasks),'source_packet_sha256':sha(ROOT/'e2/reference_author/source_snapshot/task_packets.json'),'scope_inventory_sha256':sha(ROOT/'e2/reference_author/common_scopes.json'),'protocol_sha256':sha(ROOT/'e2/PROTOCOL.json'),'output_schema_sha256':sha(schema_path),'preparer_sha256':sha(__file__),'request_inventory_sha256':sha(a.out/'requests.jsonl'),'reference_or_cases_loaded':False,'strict_schema_identical_all_arms':True,'tokens_and_calls_identical_maximum_all_arms':True})
 print(json.dumps({'requests':len(out),'tasks':len(tasks),'phase':a.phase}))
if __name__=='__main__':main()
