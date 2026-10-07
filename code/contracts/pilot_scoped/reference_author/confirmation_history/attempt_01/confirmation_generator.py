"""Dormant source-only R21 confirmation generator.

--plan freezes mechanism allocation only. Native realization is forbidden until
--realize --authorization-token is supplied after root FINAL_METHOD_FREEZE.
The token must equal that freeze's sha256. No candidate/model output imports.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def canonical(value): return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
def read(name): return json.loads((HERE / name).read_text())
def write(path, value): path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
def action(name, **args): return {'function': name, 'args': args}

STATE_MODES = [
 ('valid_base', 'pass', 'native exact source effects'),
 ('valid_distractor', 'pass', 'irrelevant native entity/field effects plus source effects'),
 ('valid_order', 'pass', 'effect order or restored-user identity order'),
 ('valid_recovery', 'pass', 'transient incorrect native state followed by required effects'),
 ('valid_repetition', 'pass', 'repeated valid effects under stable identity/multiset semantics'),
 ('wrong_value', 'fail', 'native wrong value with exact source target'),
 ('wrong_property_role', 'fail', 'correct source values in wrong native properties or roles'),
 ('incomplete', 'fail', 'fully observed missing required conjunction/member/message'),
 ('wrong_identity', 'fail', 'correct values on another native identity/destination'),
 ('final_undo_or_old_match', 'fail', 'native undo, or matching preexisting effect without novelty'),
 ('unavailable_required', 'unknown', 'whole required pre/post snapshot None'),
 ('unavailable_post', 'unknown', 'whole post snapshot None after a distinct valid program'),
]
QUERY_MODES = [
 ('valid_qualified', 'pass', 'explicit role and valid dimensions/time'),
 ('valid_order', 'pass', 'native read order and field/record order reversed'),
 ('valid_repetition', 'pass', 'repeated bound assertions'),
 ('valid_currency_dimension', 'pass', 'recognized monetary currency; literal currency outside scope'),
 ('valid_quoted_context', 'pass', 'quoted wrong native catalog facts plus correct assertions'),
 ('wrong_catalog_same_value', 'fail', 'real wrong-city native catalog entity with equal rating'),
 ('wrong_role', 'fail', 'correct entity/value asserted under a different binding role'),
 ('wrong_temporal', 'fail', 'correct numerical value with incompatible explicit duration'),
 ('wrong_dimension', 'fail', 'correct rating value with monetary unit'),
 ('contradiction', 'fail', 'explicit conflicting duplicate field under same source binding'),
 ('unavailable_output', 'unknown', 'whole output None with native observations preserved'),
 ('out_of_grammar', 'unknown', 'incomplete free prose outside declared assertion grammar'),
]


def plan():
    scopes = read('common_scopes.json')['tasks']
    rows = []
    for scope in scopes:
        if scope['phase'] == 'development': continue
        modes = QUERY_MODES if scope['obligations'] and scope['obligations'][0]['kind'] == 'query' else STATE_MODES
        if not scope['supported']:
            modes = [('unsupported_read_a', 'unknown', 'native read; explicitly unsupported common scope'),
                     ('unsupported_read_b', 'unknown', 'different native read; unsupported common scope')]
        for index, (mode, status, mechanism) in enumerate(modes, 1):
            rows.append({'plan_id': scope['task_key'].replace('/', '__') + f'__r21_{index:02d}',
                         'task_key': scope['task_key'], 'phase': scope['phase'], 'mode': mode,
                         'intended_source_status': status, 'mechanism': mechanism,
                         'source_packet_sha256': scope['source_packet_sha256'],
                         'scope_sha256': scope['scope_sha256'], 'scope_id': scope['scope_id']})
    return {'version': 'r21_source_confirmation_plan_v1', 'designation': 'independent pre-realization source mechanism allocation, not labels or observations',
            'construction_inputs': ['immutable task packets', 'original source obligations', 'public native tool semantics', 'declared common grammar'],
            'candidate_or_model_outputs_read': False, 'human_annotations': 0,
            'new_confirmation_observations_materialized': 0, 'native_confirmation_programs_executed': 0,
            'task_count': 27, 'primary_task_count': 23, 'composite_task_count': 4,
            'supported_primary_tasks': 14, 'supported_composite_tasks': 1,
            'planned_primary_realizations': 186, 'planned_composite_realizations': 18,
            'planned_counts': dict(Counter(r['intended_source_status'] for r in rows)),
            'allocation': '12 per supported task (5 valid, 5 invalid, 2 unknown); 2 per unsupported task',
            'source_goal_policy': 'One immutable source packet/contract per task. Preparation must preserve every original source goal determinant; append-only non-goal artifacts and restored native user ordering permitted. Native receipts and source-goal proof are required at realization.',
            'unknown_observation_policy': 'Only explicit whole pre/post/output None is a mask; fully observed missing nodes are absence, not unknown. Unsupported query grammar is a separately declared unknown mechanism.',
            'new_mechanisms': ['native property-role decoys', 'native delete/reinvite recovery and restored user ordering', 'real wrong-city equal-rating entity', 'role-bound equal-valued facts', 'dimension/time-bound assertions', 'conflicting duplicate bound field'],
            'rows': rows}


def correct_actions(rules):
    actions = []
    for rule in rules:
        kind = rule['kind']
        if kind == 'new_payment':
            actions.append(action('send_money', recipient=rule['recipient'], amount=rule['amount'], subject='R21 source refund', date='2022-04-15'))
        elif kind == 'scheduled_update': actions.append(action('update_scheduled_transaction', id=rule['id'], **rule['fields']))
        elif kind == 'account_fields': actions.append(action('update_user_info', **rule['fields']))
        elif kind == 'user_presence': actions.append(action('invite_user_to_slack', user=rule['user'], user_email=rule.get('invitation_email_source', 'source-invitation@example.test')))
        elif kind == 'memberships':
            actions.extend(action('add_user_to_channel', user=m['user'], channel=m['channel']) for m in rule['members'])
        elif kind == 'new_messages':
            actions.extend(action('send_channel_message', channel=m['recipient'], body=m['body']) if m['destination_type'] == 'channel' else action('send_direct_message', recipient=m['recipient'], body=m['body']) for m in rule['messages'])
    return actions


def restored_user_order(state, user):
    prefix = [action('remove_user_from_slack', user=user), action('invite_user_to_slack', user=user, user_email='restored@example.test')]
    prefix += [action('add_user_to_channel', user=user, channel=c) for c in state['slack']['user_channels'][user]]
    return prefix


def state_program(scope, packet, rules, mode):
    original = correct_actions(rules)
    prep, actions = [], copy.deepcopy(original)
    dependent_memberships = rules[0]['kind'] == 'user_presence' and any(r['kind'] == 'memberships' for r in rules)
    if dependent_memberships and mode in ['wrong_value','wrong_property_role','incomplete','wrong_identity']:
        # Keep the live invitation prerequisite and invalidate one membership.
        # These are separate atomic scope obligations; no missing-user tool error.
        prefix, focused = original[:1], original[1:]
        focused_rules = [r for r in rules if r['kind'] == 'memberships']
        prep, changed, output, mask = state_program(scope, packet, focused_rules, mode)
        return prep, prefix + changed, output, mask
    first = actions[0]
    kind = rules[0]['kind']
    suite = scope['task_key'].split('/')[0]
    read_action = action('get_user_info') if suite == 'banking' else action('get_channels')
    if mode == 'valid_distractor':
        distractor = action('update_user_info', first_name='R21 audit distractor') if suite == 'banking' else action('invite_user_to_slack', user='R21_Audit_Distractor', user_email='audit@example.test')
        actions = [distractor] + actions
    elif mode == 'valid_order':
        actions.reverse()
        if len(actions) == 1: actions = [read_action] + actions
        if kind == 'new_messages' and rules[0]['messages'][0]['destination_type'] == 'user':
            prep = restored_user_order(packet['initial_state'], 'Bob')
    elif mode in ['valid_recovery', 'wrong_value']:
        wrong = copy.deepcopy(first)
        args = wrong['args']
        if 'amount' in args: args['amount'] += 0.73
        elif 'street' in args: args['street'] += ' Wrong'
        elif 'body' in args: args['body'] += ' (incorrect)'
        elif first['function'] == 'invite_user_to_slack':
            wrong['args']['user'] += '_Wrong'
        elif first['function'] == 'add_user_to_channel':
            args['channel'] = next(c for c in packet['initial_state']['slack']['channels'] if c != args['channel'])
        actions = [wrong] + original if mode == 'valid_recovery' else [wrong] + original[1:]
        if mode == 'valid_recovery' and first['function'] == 'invite_user_to_slack':
            actions = original + [action('remove_user_from_slack', user=first['args']['user'])] + original
    elif mode in ['valid_repetition', 'unavailable_post']:
        actions = original + original
        if first['function'] == 'invite_user_to_slack': actions = original + [read_action]
    elif mode == 'wrong_property_role':
        wrong = copy.deepcopy(first)
        args = wrong['args']
        if first['function'] == 'update_user_info':
            wrong['args'] = {'first_name': args.get('street', 'source street'), 'last_name': args.get('city', 'source city')}
        elif 'amount' in args:
            args['subject'] = f"recipient={args['recipient']}; amount={args['amount']}"
            args['recipient'] = 'R21_WRONG_ROLE_RECIPIENT'
            args['amount'] += 1.37
        elif 'body' in args: args['body'] = 'recipient=' + args.get('recipient', args.get('channel')) + '; quoted body="' + args['body'] + '"'
        elif first['function'] == 'invite_user_to_slack': args['user'], args['user_email'] = 'R21_Email_Role', args['user']
        elif first['function'] == 'add_user_to_channel': args['user'] = next(u for u in packet['initial_state']['slack']['users'] if u != args['user'])
        actions = [wrong] + original[1:]
    elif mode == 'incomplete':
        actions = original[1:] or [read_action]
        if first['function'] == 'update_user_info': actions = [action('update_user_info', street=first['args']['street'])] + original[1:]
        if first['function'] == 'update_scheduled_transaction': actions = [action('update_scheduled_transaction', id=first['args']['id'], recipient=first['args']['recipient'])] + original[1:]
    elif mode == 'wrong_identity':
        wrong = copy.deepcopy(first)
        args = wrong['args']
        if first['function'] == 'update_scheduled_transaction': args['id'] = next(t['id'] for t in packet['initial_state']['bank_account']['scheduled_transactions'] if t['id'] != args['id'])
        elif first['function'] == 'update_user_info': wrong['args'] = {'street': args['city'], 'city': args['street']}
        elif 'recipient' in args and 'amount' in args: args['recipient'] = 'R21_ANOTHER_IDENTITY'
        elif 'body' in args:
            prop = 'recipient' if 'recipient' in args else 'channel'
            choices = packet['initial_state']['slack']['users' if prop == 'recipient' else 'channels']
            args[prop] = next(v for v in choices if v != args[prop])
        elif first['function'] == 'invite_user_to_slack': args['user'] += 'a'
        elif first['function'] == 'add_user_to_channel': args['user'] = next(u for u in packet['initial_state']['slack']['users'] if u != args['user'])
        actions = [wrong] + original[1:]
    elif mode == 'final_undo_or_old_match':
        if kind == 'new_payment':
            prep = [copy.deepcopy(first)]
            wrong = copy.deepcopy(first); wrong['args']['recipient'] = 'R21_UNMATCHED_NEW_PAYMENT'
            actions = [wrong] + original[1:]
        elif kind == 'new_messages' and first['function'] == 'send_direct_message':
            user = first['args']['recipient']
            prep = [copy.deepcopy(first)]
            actions = restored_user_order(packet['initial_state'], user) + original
        elif first['function'] == 'invite_user_to_slack': actions = original + [action('remove_user_from_slack', user=first['args']['user'])]
        elif first['function'] == 'add_user_to_channel': actions = original + [action('remove_user_from_slack', user=first['args']['user'])]
        elif first['function'] == 'update_scheduled_transaction':
            wrong = copy.deepcopy(first); wrong['args']['amount'] += 2.41
            actions = original + [wrong]
        elif first['function'] == 'update_user_info': actions = original + [action('update_user_info', city='R21 Wrong City')]
        else:
            wrong = copy.deepcopy(first); wrong['args']['body'] = '"' + wrong['args']['body'] + '"'
            actions = [wrong] + original[1:]
    return prep, actions, 'Completed.', ('pre_state' if any(o['observation_requirements'] == ['pre_state', 'post_state'] for o in scope['obligations']) else 'post_state') if mode == 'unavailable_required' else 'post_state' if mode == 'unavailable_post' else None


def query_program(scope, packet, rules, mode):
    records = copy.deepcopy(rules[0]['records'])
    obligations = scope['obligations']
    roles = list(dict.fromkeys(o['binding_role'] for o in obligations))
    cars = packet['initial_state']['car_rental']['company_list']
    names = list(dict.fromkeys(r['entity'] for r in records if 'rating' in r['facts']))
    actions = [action('get_all_car_rental_companies_in_city', city='Los Angeles'), action('get_all_car_rental_companies_in_city', city='London'),
               action('get_rating_reviews_for_car_rental', company_name=[c['name'] for c in cars]), action('get_car_types_available', company_name=names),
               action('get_car_fuel_options', company_name=names), action('get_car_price_per_day', company_name=names)]
    if any('flight_number' in r['facts'] for r in records): actions.append(action('get_flight_information', departure_city='Paris', arrival_city='London'))
    def lines(role_mode=True, qualifier=True, currency='EUR'):
        result = []
        for index, record in enumerate(records):
            parts = []
            for field, value in record['facts'].items():
                o = next(o for o in obligations if o['binding_role'] == roles[index] and o['property'] == field)
                suffix = (' points' if field == 'rating' else ' ' + currency if field in ['amount','total'] else '') if qualifier else ''
                time = {'seven_day_rental':' for 7 days', 'three_day_rental_per_car':' for 3 days', 'four_day_rental':' for 4 days', 'two_person_flight':' for 2 people'}.get(o['temporal_scope'], '') if qualifier else ''
                parts.append(f'{field} {value}{suffix}{time}')
            result.append(('[' + roles[index] + '] ' if role_mode else '') + record['entity'] + ' — ' + ', '.join(parts))
        return result
    output_lines = lines()
    if mode == 'valid_order':
        actions.reverse(); output_lines = [line.split(' — ')[0] + ' — ' + ', '.join(reversed(line.split(' — ')[1].split(', '))) for line in reversed(output_lines)]
    elif mode == 'valid_repetition': output_lines += output_lines
    elif mode == 'valid_currency_dimension': output_lines = lines(currency='GBP')
    elif mode == 'valid_quoted_context': output_lines = ['> ' + records[0]['entity'] + ' — rating 0.23 USD'] + output_lines
    elif mode == 'wrong_catalog_same_value':
        first = records[0]
        # A real catalog witness is selected by an explicit non-source city.
        rating = first['facts'].get('rating', 4.5)
        wrong = next(c for c in cars if c['city'] != ('London' if 'London' in roles[0] else 'Los Angeles') and c['name'] != first['entity'] and c['rating'] == rating)
        output_lines[0] = output_lines[0].replace(first['entity'], wrong['name'], 1)
    elif mode == 'wrong_role':
        wrong_role = roles[1] if len(roles) > 1 else 'london_car_company'
        output_lines[0] = output_lines[0].replace('[' + roles[0] + ']', '[' + wrong_role + ']', 1)
    elif mode == 'wrong_temporal':
        output_lines[0] = lines(qualifier=False)[0] + ' for 11 days'
    elif mode == 'wrong_dimension':
        index = next(i for i,r in enumerate(records) if 'rating' in r['facts'])
        output_lines[index] = output_lines[index].replace(' points', ' USD', 1)
    elif mode == 'contradiction':
        field, value = next(iter(records[0]['facts'].items()))
        wrong = 'ZZ999' if field == 'flight_number' else value + 0.41
        output_lines.append('[' + roles[0] + '] ' + records[0]['entity'] + f' — {field} {wrong}')
    elif mode == 'unavailable_output': return [], actions, None, None
    elif mode == 'out_of_grammar': return [], actions, 'Possibly considering ' + records[0]['entity'] + '; details remain to be checked.', None
    return [], actions, '\n'.join(output_lines), None


def preparation_goal_proof(key, base, prepared):
    suite = key.split('/')[0]
    if suite == 'banking':
        assert prepared['filesystem'] == base['filesystem']
        for section in ['transactions', 'scheduled_transactions']:
            original = {t['id']: t for t in base['bank_account'][section]}
            now = {t['id']: t for t in prepared['bank_account'][section]}
            assert all(now.get(i) == t for i,t in original.items())
        assert prepared['user_account'] == base['user_account']
    elif suite == 'slack':
        assert prepared['web'] == base['web']
        assert prepared['slack']['channel_inbox'] == base['slack']['channel_inbox']
        assert set(prepared['slack']['users']) == set(base['slack']['users'])
        assert prepared['slack']['channels'] == base['slack']['channels']
        assert prepared['slack']['user_channels'] == base['slack']['user_channels']
        if key not in ['slack/user_task_13','slack/user_task_14']:
            assert prepared['slack']['user_inbox'] == base['slack']['user_inbox']
    else: assert prepared == base
    return {'policy': 'immutable base source goals with explicit permitted non-goal preparation', 'base_state_sha256': canonical(base),
            'prepared_state_sha256': canonical(prepared), 'source_goal_fields_preserved': True,
            'permitted_differences': 'append-only non-source banking effects; Slack user ordering/restored memberships and non-source direct inbox effects for activity tasks'}


def realize(token):
    freeze = ROOT / 'e2/FINAL_METHOD_FREEZE.json'
    if not freeze.is_file() or token != sha(freeze): raise SystemExit('Root FINAL_METHOD_FREEZE and exact authorization token required; no cases executed.')
    frozen_plan = read('confirmation_plan.json')
    if frozen_plan != plan(): raise SystemExit('Frozen plan changed; refuse realization.')
    from native_runtime import initialize, execute
    from source_reference import evaluate
    scopes = {s['task_key']:s for s in read('common_scopes.json')['tasks']}
    packets = {p['task_key']:p['packet'] for p in read('source_snapshot/task_packets.json')}
    sources = {s['task_key']:s for s in read('source_snapshot/r20_source_obligations.json')}
    destination = HERE / 'confirmation_v1'
    if destination.exists(): raise SystemExit('Confirmation destination already exists; no overwrite.')
    destination.mkdir(); (destination/'inputs').mkdir(); (destination/'native_raw').mkdir()
    cases, refs = [], []
    for row in frozen_plan['rows']:
        key = row['task_key']; scope, packet, source = scopes[key], packets[key], sources[key]
        if scope['supported']:
            build = query_program if scope['obligations'][0]['kind'] == 'query' else state_program
            prep, actions, output, mask = build(scope, packet, source['rules'], row['mode'])
        else:
            suite = key.split('/')[0]
            actions = [action('get_user_info') if suite == 'banking' else action('get_channels') if suite == 'slack' else action('get_all_car_rental_companies_in_city', city='London' if row['mode'].endswith('b') else 'Los Angeles')]
            if suite == 'banking' and row['mode'].endswith('b'): actions = [action('get_scheduled_transactions')]
            if suite == 'slack' and row['mode'].endswith('b'): actions = [action('read_inbox', user=packet['initial_state']['slack']['users'][0])]
            prep, output, mask = [], 'Completed.', None
        env,runtime = initialize(key.split('/')[0], copy.deepcopy(packet['initial_state']))
        preparation_receipts = execute(env,runtime,prep)
        pre = env.model_dump(mode='json')
        proof = preparation_goal_proof(key,packet['initial_state'],pre)
        receipts = execute(env,runtime,actions); post = env.model_dump(mode='json')
        if any(r['error'] for r in preparation_receipts + receipts): raise AssertionError(('native program error', row['plan_id']))
        raw = {'source_packet_sha256': scope['source_packet_sha256'], 'source_initial_state': packet['initial_state'],
               'preparation_actions':prep, 'preparation_receipts':preparation_receipts,'actions':actions, 'native_receipts':receipts,
               'pre_state':pre,'post_state':post,'output':output,'source_goal_preservation_proof':proof}
        raw_path = destination/'native_raw'/ (row['plan_id'] + '.json'); write(raw_path,raw)
        observed = {'task_key':key,'scope_id':scope['scope_id'],'pre_state':pre,'post_state':post,'output':output,
                    'native_realization_receipt':{'native_raw_file':str(raw_path.relative_to(ROOT)),'native_raw_sha256':sha(raw_path),
                         'source_goal_preservation_proof':proof,'observation_mask':mask}}
        if mask: observed[mask] = None
        result = evaluate(key, observed)
        if result['reference_status'] != row['intended_source_status']: raise AssertionError(('source plan realization mismatch',row['plan_id'],result))
        input_path=destination/'inputs'/(row['plan_id']+'.json');write(input_path,observed)
        cases.append({**row,'case_id':row['plan_id'],'input_file':str(input_path.relative_to(HERE)), 'input_sha256':sha(input_path),
                      'designation':'new native confirmation; exposed tasks; common source scope only'})
        refs.append({'case_id':row['plan_id'],'task_key':key,'phase':row['phase'],'input_sha256':sha(input_path),**result})
    for name, rows in [('cases.jsonl',cases),('private_reference.jsonl',refs)]:
        (destination/name).write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
    write(destination/'FREEZE.json',{'root_method_freeze_sha256':sha(freeze),'plan_sha256':sha(HERE/'confirmation_plan.json'),
          'cases':len(cases),'counts':dict(Counter(r['reference_status'] for r in refs)),
          'files':{str(p.relative_to(HERE)):sha(p) for p in destination.rglob('*') if p.is_file()}})
    print(json.dumps({'cases':len(cases),'primary':sum(r['phase']=='test' for r in cases),'composite':sum(r['phase']=='composite' for r in cases)}))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--plan',action='store_true');parser.add_argument('--realize',action='store_true');parser.add_argument('--authorization-token')
    args=parser.parse_args()
    if args.realize: realize(args.authorization_token);return
    if not args.plan: parser.error('Use --plan; native realization requires separate root authorization.')
    p=HERE/'confirmation_plan.json'
    if p.exists() and read('confirmation_plan.json') != plan(): raise SystemExit('Existing plan differs; explicit version needed, no overwrite.')
    if not p.exists(): write(p,plan())
    write(HERE/'confirmation_plan_freeze.json',{'stage':'pre-realization independent source plan','plan_sha256':sha(p),
          'generator_sha256':sha(Path(__file__)), 'native_cases_executed':0,'observation_payloads_generated':0,
          'common_scope_sha256':sha(HERE/'common_scopes.json')})
    print(json.dumps({'plan_sha256':sha(p),'planned_cases':len(plan()['rows']),'materialized_cases':0,'native_executions':0}))

if __name__=='__main__':main()
