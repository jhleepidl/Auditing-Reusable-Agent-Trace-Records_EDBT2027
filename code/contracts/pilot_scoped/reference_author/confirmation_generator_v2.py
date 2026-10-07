"""Dormant R21B native realization; new versions, unchanged source semantics.

Only --plan is currently authorized. --realize requires root MEASUREMENT_V3_FREEZE
and its exact SHA token. No candidate/model outputs are read or imported.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
from confirmation_generator import plan as original_plan, state_program, query_program, preparation_goal_proof, action


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(name):return json.loads((HERE/name).read_text())
def write_new(path,value):
    if path.exists():raise SystemExit('Refuse versioned artifact overwrite: '+str(path))
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')


def plan():
    old=original_plan();scopes={s['task_key']:s for s in load('common_scopes_v2.json')['tasks']}
    rows=[]
    for oldrow in old['rows']:
        row=copy.deepcopy(oldrow);scope=scopes[row['task_key']]
        row['plan_id']=row['plan_id'].replace('__r21_','__r21b_')
        row['previous_plan_id']=oldrow['plan_id']
        row['scope_id']=scope['scope_id'];row['scope_sha256']=scope['scope_sha256']
        row['realization_revision']='Source-goal-safe extra native read; distinct bounded record order/lexical surface.'
        rows.append(row)
    result=copy.deepcopy(old)
    result.update({'version':'r21b_source_confirmation_plan_v2','rows':rows,
      'designation':'independent R21B pre-realization plan; new realization IDs and read/lexical forms, same retained source scopes and allocation',
      'previous_plan_file':'confirmation_plan.json','previous_plan_sha256':sha(HERE/'confirmation_plan.json'),
      'public_scope_file':'common_scopes_v2.json','public_scope_sha256':sha(HERE/'common_scopes_v2.json'),
      'reference_semantics':'Byte-preserved source_reference.py through authority-only source_reference_v2.py wrapper.',
      'read_variation':'Prepend read-only banking transaction window, Slack listed-channel messages, or complete native rental type lookup. No state changes.',
      'query_variation':'Reverse bounded field/record order, use declared score/cost/flight-number aliases and equals/is connectors, explicit over N days/passengers, quoted contexts as complete double-quoted records.',
      'old_source_packets_goals_expected_values_and_obligation_ids_unchanged':True})
    return result


def extra_read(scope,packet,index):
    suite=scope['task_key'].split('/')[0]
    if suite=='banking':return action('get_most_recent_transactions',n=1+index%5)
    if suite=='slack':return action('read_channel_messages',channel=packet['initial_state']['slack']['channels'][index%len(packet['initial_state']['slack']['channels'])])
    return action('get_car_types_available',company_name=[c['name'] for c in packet['initial_state']['car_rental']['company_list']])


def lexical_revision(output):
    if output is None:return None
    if ' — ' not in output:return 'An incomplete possibility remains to be checked; no bound facts are asserted.'
    transformed=[]
    for original in output.splitlines():
        quoted=original.startswith('> ')
        line=original[2:] if quoted else original
        if ' — ' not in line:
            transformed.append(line);continue
        entity,body=line.split(' — ',1)
        pieces=[]
        for piece in body.split(','):
            piece=piece.strip()
            piece=re.sub(r'^rating\s+','score equals ',piece)
            piece=re.sub(r'^total\s+','cost is ',piece)
            piece=re.sub(r'^flight_number\s+','flight number = ',piece)
            piece=piece.replace(' for ',' over ').replace(' people',' passengers')
            pieces.append(piece)
        line=entity+' — '+', '.join(reversed(pieces))
        transformed.append('"'+line+'"' if quoted else line)
    return '\n'.join(reversed(transformed))


def programs(row,scope,packet,source,index):
    if scope['supported']:
        builder=query_program if scope['obligations'][0]['kind']=='query' else state_program
        prep,actions,output,mask=builder(scope,packet,source['rules'],row['mode'])
        output=lexical_revision(output) if scope['obligations'][0]['kind']=='query' else 'Completed the selected state effects.'
    else:
        suite=scope['task_key'].split('/')[0]
        actions=[action('get_user_info') if suite=='banking' else action('get_channels') if suite=='slack' else action('get_all_car_rental_companies_in_city',city='London' if row['mode'].endswith('b') else 'Los Angeles')]
        if suite=='banking' and row['mode'].endswith('b'):actions=[action('get_scheduled_transactions')]
        if suite=='slack' and row['mode'].endswith('b'):actions=[action('read_inbox',user=packet['initial_state']['slack']['users'][0])]
        prep,output,mask=[],'Read-only source observation completed.',None
    return prep,[extra_read(scope,packet,index)]+actions,output,mask


def realize(token):
    freeze=ROOT/'e2/MEASUREMENT_V3_FREEZE.json'
    if not freeze.exists() or token!=sha(freeze):raise SystemExit('Explicit MEASUREMENT_V3_FREEZE authorization/token required; zero new native cases executed.')
    frozen=load('confirmation_plan_v2.json')
    if frozen!=plan():raise SystemExit('Frozen v2 plan changed; refuse realization.')
    from native_runtime import initialize,execute
    from source_reference_v2 import evaluate
    scopes={s['task_key']:s for s in load('common_scopes_v2.json')['tasks']}
    packets={p['task_key']:p['packet'] for p in load('source_snapshot/task_packets.json')}
    sources={s['task_key']:s for s in load('source_snapshot/r20_source_obligations.json')}
    destination=HERE/'confirmation_v2'
    if destination.exists():raise SystemExit('R21B case directory exists; no overwrite.')
    destination.mkdir();(destination/'inputs').mkdir();(destination/'native_raw').mkdir()
    cases,refs=[],[]
    for index,row in enumerate(frozen['rows']):
        key=row['task_key'];scope,packet,source=scopes[key],packets[key],sources[key]
        prep,actions,output,mask=programs(row,scope,packet,source,index)
        env,rt=initialize(key.split('/')[0],copy.deepcopy(packet['initial_state']))
        prep_receipts=execute(env,rt,prep);pre=env.model_dump(mode='json')
        proof=preparation_goal_proof(key,packet['initial_state'],pre)
        receipts=execute(env,rt,actions);post=env.model_dump(mode='json')
        raw={'source_packet_sha256':scope['source_packet_sha256'],'source_initial_state':packet['initial_state'],
             'preparation_actions':prep,'preparation_receipts':prep_receipts,'actions':actions,'native_receipts':receipts,
             'pre_state':pre,'post_state':post,'output':output,'source_goal_preservation_proof':proof}
        rawpath=destination/'native_raw'/(row['plan_id']+'.json');write_new(rawpath,raw)
        if any(r['error'] for r in prep_receipts+receipts):raise AssertionError(('native v2 realization error',row['plan_id']))
        observed={'task_key':key,'scope_id':scope['scope_id'],'pre_state':pre,'post_state':post,'output':output,
          'native_realization_receipt':{'native_raw_file':str(rawpath.relative_to(ROOT)),'native_raw_sha256':sha(rawpath),
             'source_goal_preservation_proof':proof,'observation_mask':mask}}
        if mask:observed[mask]=None
        result=evaluate(key,observed)
        inputpath=destination/'inputs'/(row['plan_id']+'.json');write_new(inputpath,observed)
        if result['reference_status']!=row['intended_source_status']:raise AssertionError(('source-only v2 realization mismatch',row['plan_id'],result))
        cases.append({**row,'case_id':row['plan_id'],'input_file':str(inputpath.relative_to(HERE)),'input_sha256':sha(inputpath),
          'designation':'new R21B native realization on exposed tasks; common source scope only'})
        refs.append({'case_id':row['plan_id'],'task_key':key,'phase':row['phase'],'input_sha256':sha(inputpath),**result})
    for name,data in [('cases.jsonl',cases),('private_reference.jsonl',refs)]:
        (destination/name).write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in data))
    (HERE/'confirmation_cases_v2_portable.jsonl').write_bytes((destination/'cases.jsonl').read_bytes())
    write_new(destination/'FREEZE.json',{'measurement_method_freeze_sha256':sha(freeze),'source_plan_freeze_sha256':sha(HERE/'SOURCE_MEASUREMENT_V2_FREEZE.json'),
      'plan_sha256':sha(HERE/'confirmation_plan_v2.json'),'scope_sha256':sha(HERE/'common_scopes_v2.json'),'generator_sha256':sha(Path(__file__)),
      'source_reference_semantics_sha256':sha(HERE/'source_reference.py'),'cases':len(cases),'counts':dict(Counter(r['reference_status'] for r in refs)),
      'portable_adapter_sha256':sha(HERE/'confirmation_cases_v2_portable.jsonl'),
      'files':{str(p.relative_to(HERE)):sha(p) for p in destination.rglob('*') if p.is_file()}})
    print(json.dumps({'cases':len(cases),'primary':sum(r['phase']=='test' for r in cases),'composite':sum(r['phase']=='composite' for r in cases),
                     'counts':dict(Counter(r['reference_status'] for r in refs))}))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--plan',action='store_true');parser.add_argument('--realize',action='store_true');parser.add_argument('--authorization-token');args=parser.parse_args()
    if args.realize:realize(args.authorization_token);return
    if not args.plan:parser.error('--plan required; realization separately authorized after measurement freeze.')
    p=HERE/'confirmation_plan_v2.json'
    if p.exists():raise SystemExit('V2 plan exists; no overwrite.')
    write_new(p,plan())
    print(json.dumps({'plan_sha256':sha(p),'planned_cases':len(plan()['rows']),'materialized_cases':0,'native_executions':0}))

if __name__=='__main__':main()
