#!/usr/bin/env python3
"""Independent, read-only R18 record audit. No native tool or provider execution.
Usage: python audit_r18_records.py --root EXTRACTED_EDBT_R18_CPU_RESULTS --out summary.json
"""
from __future__ import annotations
import argparse, ast, collections, datetime as dt, hashlib, json
from pathlib import Path
from typing import Any

def load(p: Path) -> Any:
    return json.loads(p.read_text(encoding='utf-8'))
def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()
def ensure(ok: bool, msg: str) -> None:
    if not ok: raise AssertionError(msg)
def differences(a: Any,b: Any,path: tuple=()) -> list[tuple]:
    if type(a) is not type(b): return [path]
    if isinstance(a,dict):
        result=[]
        for key in sorted(a.keys()|b.keys()):
            result += differences(a[key],b[key],path+(str(key),)) if key in a and key in b else [path+(str(key),)]
        return result
    if isinstance(a,list):
        if len(a)!=len(b): return [path+('LENGTH',)]
        return [p for i,(x,y) in enumerate(zip(a,b)) for p in differences(x,y,path+(str(i),))]
    return [] if a==b else [path]
def get_prompt(source: Path, number: int) -> str:
    tree=ast.parse(source.read_text())
    cls=next(c for c in tree.body if isinstance(c,ast.ClassDef) and c.name==f'UserTask{number}')
    for x in cls.body:
        if isinstance(x,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='PROMPT' for t in x.targets):
            return ast.literal_eval(x.value)
    raise ValueError('No literal prompt')
def audit(root: Path) -> dict:
    kit=root/'EDBT_R18_NO_HUMAN_KIT'; native=kit/'runs/r18_cpu_01/native'
    manifest=root/'FILE_SHA256SUMS_R18_RESULTS'; seen=set()
    for line in manifest.read_text().splitlines():
        h,name=line.split(None,1);path=(root/name).resolve()
        ensure(path.is_relative_to(root.resolve()),'Unsafe manifest path')
        ensure(name not in seen,'Duplicate manifest entry');seen.add(name)
        ensure(sha(path)==h,f'Hash mismatch {name}')
    actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and p!=manifest and '__pycache__' not in p.parts}
    # Python bytecode may have been produced by explicitly run unit tests, never payload.
    ensure(actual==seen,f'Unexpected/missing payload: {actual^seen}')
    sweep=load(native/'sweep/rows.json');sel=load(native/'sweep/selection_before_execution.json')['cases']
    ensure(len(sweep)==len(sel)==291,'Sweep count')
    versions=['v1','v1.1.1','v1.2.2'];byver=[];affected=[];suite_table=[]
    for r,m in zip(sweep,sel):
        ensure(all(r[k]==m[k] for k in ['version','suite','task_id','prompt_sha256']),'Selection mismatch')
        ensure('error' not in r and 'roundtrip_error' not in r,'Unexpected execution error')
        folder=native/'sweep/cases'/r['version']/r['suite']/r['task_id']
        ensure(load(folder/'result.json')==r,'Case/row mismatch')
        pre,post,hydr=map(load,[folder/'pre_state.json',folder/'post_state.json',folder/'roundtrip_post_state.json'])
        trace=load(folder/'trace.json')
        ensure(all(t['error'] is None for t in trace),'Unreported tool error')
        ensure((trace[-1]['state'] if trace else pre)==post,'Final trace binding')
        ensure(bool(differences(post,hydr))==r['roundtrip_state_changed'],'Wrong hydration flag')
        ensure((r['roundtrip_label']!=r['native_official_control_accepted'])==r['roundtrip_label_changed'],'Wrong label-change flag')
        ensure(not r['roundtrip_pre_changed'],'Unexpected initial-state drift')
        if r['roundtrip_state_changed']:
            affected.append((r['version'],r['suite'],r['task_id']))
        if r['roundtrip_label_changed']:
            ensure(r['native_official_control_accepted'] and not r['roundtrip_label'],'Non pass-to-fail change')
    affected_sets=[]
    for v in versions:
        sub=[r for r in sweep if r['version']==v]
        ensure(len({(r['suite'],r['task_id']) for r in sub})==97,'Duplicated/missing task')
        for s,count in [('workspace',40),('banking',16),('slack',21),('travel',20)]:
            ss=[r for r in sub if r['suite']==s]
            ensure({r['task_id'] for r in ss}=={f'user_task_{i}' for i in range(count)},f'ID census {v}/{s}')
            suite_table.append(dict(version=v,suite=s,n=count,live_accept=sum(r['native_official_control_accepted'] for r in ss),post_changed=sum(r['roundtrip_state_changed'] for r in ss),label_changed=sum(r['roundtrip_label_changed'] for r in ss)))
        byver.append(dict(version=v,n=len(sub),official_accept=sum(r['native_official_control_accepted'] for r in sub),official_reject=sum(not r['native_official_control_accepted'] for r in sub),post_changed=sum(r['roundtrip_state_changed'] for r in sub),label_changed=sum(r['roundtrip_label_changed'] for r in sub),hydrated_accept=sum(r['roundtrip_label'] for r in sub)))
        affected_sets.append({(s,t) for vv,s,t in affected if vv==v})
    ensure(affected_sets[0]==affected_sets[1]==affected_sets[2],'Different affected task sets')
    ensure([r['post_changed'] for r in byver]==[24,24,24],'State counts')
    ensure([r['label_changed'] for r in byver]==[23,24,24],'Label counts')

    replay=load(root/'studies/replay20_v2/results_v1/rows.json');calls=errors=0;changed=[]
    partial=load(native/'replay20/rows.json')
    ensure([r['task_id'] for r in partial if 'error' in r]==['user_task_2','user_task_17'],'Parent error history')
    ensure(len(replay)==20 and len({r['task_id'] for r in replay})==20,'Replay census')
    for r in replay:
        ensure('error' not in r,'Corrected replay failed')
        tid=r['task_id'];src=kit/'inputs/workspace'/tid;dst=root/'studies/replay20_v2/results_v1'/tid
        ensure(load(dst/'pre_state.json')==load(src/'pre_state.json'),'Initial state')
        ensure(load(dst/'post_state.json')==load(src/'post_state.json'),'Final state')
        expected=[x for x in load(src/'trace.json') if x['role']=='tool'];trace=load(dst/'trace.json')
        ensure(len(trace)==len(expected)==r['tool_calls'],'Tool count')
        for a,b in zip(trace,expected):
            ensure(a['call']==b['tool_call'] and a['error']==b.get('error'),'Recorded call/error binding')
            ensure(a['formatted_result_matches'],'Recorded formatter mismatch')
            # Formatter regeneration requires native model types: this flag is a run receipt.
            calls+=1;errors+=int(a['error'] is not None)
        ensure(r['native_v1']==load(src/'result.json')['utility'],'Old endpoint binding')
        if r['native_v1']!=r['native_v1_1_1_same_trace']:changed.append(tid)
    ensure((calls,errors)==(44,2) and changed==['user_task_7','user_task_18'],'Replay aggregates')

    fieldrows=load(native/'state-repair/rows.json');plans=load(native/'state-repair/challenge_before_execution.json')['targets']
    ensure(len(fieldrows)==48 and len(plans)==3,'Field census');fieldtable=[];negative_isolation=0
    srcdir=kit/'vendor/agentdojo/src/agentdojo/default_suites/v1'
    for target in plans:
        suite,tid=target['suite'],target['task_id'];spec=target['spec']
        prompt=get_prompt(srcdir/suite/'user_tasks.py',int(tid.split('_')[-1]))
        ensure(spec['prompt_literal'] in prompt,'Not a literal requirement')
        if spec['kind']=='event_date':ensure(spec['required']=='2024-04-25' and 'April 25th 2024' in prompt,'Date evidence')
        else:ensure(spec['required'] in spec['prompt_literal'],'Recipient evidence')
        sub=[x for x in fieldrows if (x['suite'],x['task_id'])==(suite,tid)]
        ensure(len(sub)==16 and len({x['variant'] for x in sub})==16,'Field variants')
        paths=native/'state-repair/cases'/suite/tid;anchor=load(paths/'positive_0/post_state.json');ain=load(paths/'positive_0/evaluator_input.json');a_pre=load(paths/'positive_0/pre_state.json')
        poshash=set();allhash=set();pc=nv=0
        for r in sub:
            ensure('error' not in r,'Field run error')
            folder=paths/r['variant'];pre,post,ev,trace=map(load,[folder/'pre_state.json',folder/'post_state.json',folder/'evaluator_input.json',folder/'trace.json'])
            ensure(pre==a_pre and trace[-1]['state']==post,'Field state binding')
            ensure([t['call'] for t in trace]==ev['actions'] and all(t['error'] is None for t in trace),'Field action binding')
            if spec['kind']=='bank_recipient':
                items=post['bank_account']['scheduled_transactions'][len(pre['bank_account']['scheduled_transactions']):]
                ensure(len(items)==1,'Bank object binding');value=items[0]['recipient'];ok=value==spec['required']
                allow=lambda p:p[:2]==('bank_account','scheduled_transactions') and p[-1]=='recipient'
                action_allow=lambda p:p[-1]=='recipient'
            elif spec['kind']=='email_recipient':
                items=[v for k,v in post['inbox']['emails'].items() if k not in pre['inbox']['emails']]
                ensure(len(items)==1,'Email object binding');value=items[0]['recipients'];ok=spec['required'] in value
                allow=lambda p:p[:2] in [('inbox','emails'),('inbox','sent')] and p[-2:]==('recipients','0')
                action_allow=lambda p:p[-2:]==('recipients','0')
            else:
                items=[v for k,v in post['calendar']['events'].items() if k not in pre['calendar']['events']]
                ensure(len(items)==1,'Calendar object binding');event=items[0];value=event['start_time'][:10];ok=value==spec['required']
                new_mail=[v for k,v in post['inbox']['emails'].items() if k not in pre['inbox']['emails']]
                ensure(len(new_mail)==1 and new_mail[0]['attachments']==[event] and post['inbox']['sent'][-1]['attachments']==[event],'Invitation mirrors event')
                allow=lambda p:(p[:2]==('calendar','events') or (p[:2] in [('inbox','emails'),('inbox','sent')] and p[-3:-1]==('attachments','0'))) and p[-1] in ['start_time','end_time']
                action_allow=lambda p:p[-1] in ['start_time','end_time']
            ensure(ok==r['scope_satisfied']==r['expected_scope_satisfied'],'Realized reference')
            ensure(r['native'] is True and r['scoped_supplemented']==(r['native'] and ok),'Supplement calculation')
            ensure(load(folder/'result.json')==r,'Field row/case mismatch')
            h=sha(folder/'post_state.json');allhash.add(h)
            if ok:pc+=1;poshash.add(h)
            else:
                d=differences(anchor,post);da=differences(ain['actions'],ev['actions'])
                ensure(d and all(allow(p) for p in d),'Unintended state change')
                ensure(da and all(action_allow(p) for p in da) and ev['output']==ain['output'],'Unintended action/output change')
                negative_isolation+=1;nv+=1
        fieldtable.append(dict(suite=suite,task_id=tid,controls=pc,violations=nv,native_accepted_violations=nv,supplement_accepted_violations=0,retained_native_positive_controls=pc,unique_control_post_states=len(poshash),unique_all_post_states=len(allhash)))

    q=load(native/'query-crosscheck/rows.json');localq=load(kit/'runs/r18_cpu_01/local/query_rows.json')
    ensure(len(q)==3044 and len({r['case_id'] for r in q})==3044,'Query IDs')
    lm={r['case_id']:r for r in localq}
    ensure(set(lm)=={r['case_id'] for r in q},'Query local/native census')
    ensure(all(r['native']==r['kernel'] and r['matches'] and r['native']==(lm[r['case_id']]['native_kernel']=='pass') for r in q),'Kernel/native mismatch')
    qs=load(kit/'runs/r18_cpu_01/local/query_summary.json')
    querytable=[]
    for t,n,fa in [('2',1488,0),('5',1440,2),('10',100,18)]:
        x=qs['by_task'][t]['finite_canonical_domain']
        sub=[r for r in localq if r['task_id']==int(t) and r['group']=='finite_canonical_domain']
        ensure(len(sub)==n and sum(r['reference']=='fail' and r['native_kernel']=='pass' for r in sub)==fa,'Independent query rows')
        ensure(sum(r['reference']=='fail' and r['patched_scoped']=='pass' for r in sub)==0,'Typed counterexample')
        ensure(sum(r['reference']=='pass' and r['patched_scoped']=='pass' for r in sub)==1,'Canonical positive retained')
        ensure(x['n']==n and x['native_kernel']['false_accept']==fa and x['patched_scoped']['false_accept']==0,'Query aggregate')
        querytable.append(dict(task_id='user_task_'+t,canonical_inputs=n,native_false_accept=fa,typed_false_accept=0,retained_canonical_correct_values=x['patched_scoped']['true_positive_retained']))
    result={'status':'PASS_RECORD_LEVEL_AUDIT_NOT_FULL_NATIVE_RERUN','checked_payload_files':len(seen),'sweep':{'unique_tasks':97,'task_version_executions':291,'versions':byver,'suites':suite_table,'same_24_affected_ids_across_versions':True,'unique_affected_tasks':sorted([f'{s}/{t}' for s,t in affected_sets[0]]),'unchanged_snapshots':219,'affected_label_masked_by_prior_failure':[f'{r["version"]}/{r["suite"]}/{r["task_id"]}' for r in sweep if r['roundtrip_state_changed'] and not r['roundtrip_label_changed']]},'field_supplement':{'rows':48,'tables':fieldtable,'negative_state_and_action_isolation_checks':negative_isolation,'unique_controls':sum(x['unique_control_post_states'] for x in fieldtable),'unique_all_states':sum(x['unique_all_post_states'] for x in fieldtable),'full_semantic_accuracy_measured':False},'query':{'full_engine_agreement_from_record':3044,'canonical_rows':3028,'format_profile_rows_separate':16,'tables':querytable},'replay20':{'n':20,'original_preserved_error_tasks':['user_task_2','user_task_17'],'tool_calls_verified':calls,'expected_errors_bound':errors,'native_v1_pass':sum(r['native_v1'] for r in replay),'native_v1_1_1_pass':sum(r['native_v1_1_1_same_trace'] for r in replay),'same_trace_version_changes':changed,'formatted_response_regeneration':'recorded PASS inspected; native model-type formatter not rerun locally'},'scope':{'new_model_calls_in_review':0,'new_human_annotations_in_review':0,'native_runtime_rerun_in_review':False,'native_execution_support':'uploaded result files, frozen implementation, provided fresh-replay validation receipt','full_field_correctness':'not inferred from necessary-field controls','not_claimed':['global evaluator correctness','natural defect prevalence','independent version replication','automatic repair performance','AgentRx superiority']}}
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    result=audit(a.root.resolve());a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False,indent=2))
