#!/usr/bin/env python3
"""E1: native, paired reader / replay comparison on the frozen R18 corpus.
Requires the supplied native environment. A BLOCKED receipt is written instead
of substituting a mock engine. No model calls; network sockets are blocked.
"""
from __future__ import annotations
import argparse,copy,json,os,sys,time,traceback,statistics,collections
from pathlib import Path
from common_handoff import load,write,new_out,sha,digest,utc,kit_path,ROOT
from typed_restore import checked_restore,UnsupportedSnapshot
ARMS=('legacy_hydration','guarded_hydration','typed_snapshot','action_replay')

def replay(rn,api,suite,env,steps):
    runtime=api.Runtime(suite.tools)
    states=[]
    with rn.clock():
        for expected in steps:
            call=api.Call(**copy.deepcopy(expected['call']))
            result,error=runtime.run_function(env,call.function,call.args)
            if error!=expected.get('error'):
                raise ValueError('Recorded error mismatch (never ignore unexpected errors)')
            if rn.dump(result)!=expected['result']:
                raise ValueError('Recorded tool result mismatch')
            state=rn.dump(env)
            if state!=expected['state']: raise ValueError('Recorded intermediate state mismatch')
            states.append(state)
    return env,states

def grade(rn,api,suite,task,pre,post,output,calls):
    pre=pre.model_copy(deep=True);post=post.model_copy(deep=True)
    p0=rn.dump(pre);s0=rn.dump(post)
    val=rn.grade(api,suite,task,pre,post,output,calls)
    if rn.dump(pre)!=p0 or rn.dump(post)!=s0: raise ValueError('Evaluator modified its input')
    return val

def jobs(kit,dataset):
    out=[]
    if dataset in ('sweep','both'):
        base=kit/'runs/r18_cpu_01/native/sweep'
        for r in load(base/'rows.json'):
            d=base/'cases'/r['version']/r['suite']/r['task_id']
            out.append(dict(r,dataset='sweep',folder=str(d),
                            expected_label=r['native_official_control_accepted']))
    if dataset in ('replay20','both'):
        for i in range(20):
            tid=f'user_task_{i}';d=kit.parent/'studies/replay20_v2/results_v1'/tid
            src=kit/'inputs/workspace'/tid
            out.append({'version':'v1','suite':'workspace','task_id':tid,
                        'dataset':'replay20','folder':str(d),'input_folder':str(src),
                        'expected_label':load(src/'result.json')['utility']})
    return out

def summarize(rows):
    result={}
    for dataset in sorted({r['dataset'] for r in rows}):
        result[dataset]={}
        for arm in ARMS:
            rr=[r for r in rows if r['dataset']==dataset and r['arm']==arm]
            good=[r for r in rr if r['status']=='completed']
            latency=[r['reader_ms'] for r in good]
            cont=[r for r in rr if r.get('continuation_attempted')]
            result[dataset][arm]={
                'attempted':len(rr),'completed':len(good),
                'unsupported_or_blocked':sum(r['status']=='unsupported' for r in rr),
                'errors':sum(r['status']=='error' for r in rr),
                'exact_pre_and_post':sum(r.get('exact_state',False) for r in rr),
                'label_agreement':sum(r.get('same_label',False) for r in rr),
                'faithful_scored_records':sum(r.get('exact_state',False) and r.get('same_label',False) for r in rr),
                'mismatched_states_scored':sum(not r['exact_state'] for r in good),
                'continuation_attempted':len(cont),
                'continuation_exact':sum(r.get('continuation_exact',False) for r in cont),
                'reader_ms_median':statistics.median(latency) if latency else None,
                'reader_ms_max':max(latency) if latency else None,
                'semantic_accuracy':'NOT_MEASURED',
                'unit':'task-version for sweep; record for replay20; versions repeat task identities'}
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--dataset',choices=['sweep','replay20','both'],default='both')
    p.add_argument('--allow-dependency-drift',action='store_true')
    p.add_argument('--limit',type=int,help='Smoke only; any limit disqualifies a full-corpus result')
    a=p.parse_args();out=new_out(a.out);kit=kit_path(a.work)
    sys.path.insert(0,str(kit/'tools'))
    rn=None
    write(out/'START.json',{'utc':utc(),'script_sha256':sha(__file__),
        'reader_sha256':sha(ROOT/'tools/typed_restore.py'),'protocol_sha256':sha(ROOT/'protocols/E1.json'),
        'dataset':a.dataset,'smoke_only':a.limit is not None,'api_calls':0})
    try:
        import run_native as rn
        rn.check_freeze();rn.check_followup()
        with rn.no_network():api=rn.setup(a.allow_dependency_drift)
        write(out/'environment.json',rn.environment())
        write(out/'environment_admission.json',{'dependency_drift':api.dependency_drift,
             'replication_status':'new-environment' if api.dependency_drift else 'original-pins'})
    except Exception as e:
        write(out/'BLOCKED.json',{'status':'BLOCKED_BEFORE_NATIVE_RUN',
            'error':type(e).__name__+': '+str(e),'api_calls':0,
            'note':'Install vendor/r11/requirements.lock in an isolated environment. No mock substitution.'})
        print('BLOCKED:',e);return 2
    plan=jobs(kit,a.dataset)
    if a.limit is not None:plan=plan[:a.limit]
    write(out/'selection_before_execution.json',plan)
    rows=[];baseline_errors=[]
    with rn.no_network():
        for index,j in enumerate(plan):
            d=Path(j['folder']);cid=f"{j['dataset']}/{j['version']}/{j['suite']}/{j['task_id']}"
            try:
                stored_pre=load(d/'pre_state.json');stored_post=load(d/'post_state.json');steps=load(d/'trace.json')
                suite,task,env,pre=rn.init(api,j['version'],j['suite'],j['task_id'])
                if rn.dump(pre)!=stored_pre:raise ValueError('Fresh initial state differs from frozen record')
                env,states=replay(rn,api,suite,env,steps)
                if rn.dump(env)!=stored_post:raise ValueError('Native replay differs from frozen final state')
                calls=[api.Call(**s['call']) for s in steps]
                output=(rn.text_output(load(Path(j['input_folder'])/'evaluator_input.json'))
                        if j['dataset']=='replay20' else task.GROUND_TRUTH_OUTPUT)
                base=grade(rn,api,suite,task,pre,env,output,calls)
                if base!=j['expected_label']:raise ValueError('Native replay label differs from frozen label')
            except Exception as e:
                baseline_errors.append({'case':cid,'error':str(e)})
                for arm in ARMS:rows.append({**{k:j[k] for k in ('dataset','suite','task_id','version')},
                    'case':cid,'arm':arm,'status':'error','error':'BASELINE: '+str(e)})
                continue
            for arm in ARMS:
                row={**{k:j[k] for k in ('dataset','suite','task_id','version')},'case':cid,
                     'arm':arm,'native_label':base,'pre_sha256':digest(stored_pre),'post_sha256':digest(stored_post)}
                try:
                    t=time.perf_counter_ns()
                    if arm in ('legacy_hydration','guarded_hydration'):
                        rp=type(pre).model_validate(copy.deepcopy(stored_pre))
                        rs=type(env).model_validate(copy.deepcopy(stored_post))
                        if arm=='guarded_hydration' and (rn.dump(rp)!=stored_pre or rn.dump(rs)!=stored_post):
                            raise UnsupportedSnapshot('Snapshot-value witness failed')
                    elif arm=='typed_snapshot':
                        rp=checked_restore(type(pre),stored_pre);rs=checked_restore(type(env),stored_post)
                    else:
                        _,_,rs,rp=rn.init(api,j['version'],j['suite'],j['task_id'])
                        rs,_=replay(rn,api,suite,rs,steps)
                    row['reader_ms']=(time.perf_counter_ns()-t)/1e6
                    row['exact_state']=rn.dump(rp)==stored_pre and rn.dump(rs)==stored_post
                    t=time.perf_counter_ns();value=grade(rn,api,suite,task,rp,rs,output,calls)
                    row.update(status='completed',label=value,same_label=value==base,
                               grade_ms=(time.perf_counter_ns()-t)/1e6)
                    # After a nonempty prefix, resume the original suffix through REAL native tools.
                    # One-call/zero-call runs cannot test a nontrivial post-action continuation.
                    row['continuation_attempted']=len(steps)>=2
                    if len(steps)>=2:
                        cut=max(1,len(steps)//2);payload=steps[cut-1]['state']
                        try:
                            if arm in ('legacy_hydration','guarded_hydration'):
                                mid=type(env).model_validate(copy.deepcopy(payload))
                                if arm=='guarded_hydration' and rn.dump(mid)!=payload:
                                    raise UnsupportedSnapshot('Intermediate snapshot-value witness failed')
                            elif arm=='typed_snapshot':mid=checked_restore(type(env),payload)
                            else:
                                _,_,mid,_=rn.init(api,j['version'],j['suite'],j['task_id'])
                                mid,_=replay(rn,api,suite,mid,steps[:cut])
                            mid,_=replay(rn,api,suite,mid,steps[cut:])
                            row['continuation_exact']=rn.dump(mid)==stored_post
                        except Exception as ce:
                            row['continuation_exact']=False;row['continuation_error']=str(ce)
                    write(out/'cases'/cid/(arm+'.json'),row)
                except UnsupportedSnapshot as e:row.update(status='unsupported',error=str(e))
                except Exception as e:row.update(status='error',error=type(e).__name__+': '+str(e))
                rows.append(row)
            if (index+1)%20==0:print('Processed',index+1,'/',len(plan),flush=True)
    write(out/'rows.json',rows);write(out/'SUMMARY.json',summarize(rows))
    write(out/'RUN_STATUS.json',{'status':'INVALID_BASELINE' if baseline_errors else 'COMPLETED',
          'baseline_errors':baseline_errors,'smoke_only':a.limit is not None,
          'candidate_failures_retained':True,'new_model_calls':0,'full_semantic_accuracy':False})
    return 1 if baseline_errors else 0
if __name__=='__main__':raise SystemExit(main())
