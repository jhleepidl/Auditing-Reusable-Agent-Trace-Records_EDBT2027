"""One-attempt scoped construction; immutable requests, no oracle, aggregate $30 cap."""
import argparse, concurrent.futures, hashlib, json, os, time
from pathlib import Path
import httpx, tiktoken
from dotenv import dotenv_values
from common21 import ROOT, sha, load, rows, write, now, canonical_sha
RATES={'gpt-4.1-mini-2025-04-14':(.4,.1,1.6),'gpt-4.1-2025-04-14':(2,.5,8)}
PRIOR_USD=8.1957672
def body(r):
    return {'model':r['model'],'messages':[{'role':'system','content':r['system']},{'role':'user','content':json.dumps(r['input'],ensure_ascii=False,sort_keys=True)}],
            'response_format':{'type':'json_schema','json_schema':{'name':'scoped_contract_r21','strict':True,'schema':r['output_schema']}},
            'temperature':.2,'seed':r['seed'],'max_completion_tokens':r['max_output_tokens'],'store':False,'service_tier':'default'}
def cost(model,u):
    a,b,c=RATES[model];cached=u.get('prompt_tokens_details',{}).get('cached_tokens',0)
    return ((u['prompt_tokens']-cached)*a+cached*b+u['completion_tokens']*c)/1e6
def worst(r):
    # Include the structured-output schema in a conservative uncached input bound.
    enc=tiktoken.get_encoding('o200k_base');b=body(r)
    n=sum(len(enc.encode(v['content'])) for v in b['messages'])+len(enc.encode(json.dumps(b['response_format'],ensure_ascii=False)))+1024
    return (n*RATES[r['model']][0]+r['max_output_tokens']*RATES[r['model']][2])/1e6
def accumulated():
    # Count completed runs and interrupted run attempt receipts, with uncertainty reservations.
    total=PRIOR_USD
    for start in (ROOT/'e2').rglob('PROVIDER_START.json'):
        end=start.parent/'PROVIDER_END.json'
        if end.exists():total+=load(end)['budget_spent_or_reserved_usd']
        else:
            # An interrupted run could have billed an attempt before writing its receipt.
            total+=load(start)['run_worst_case_usd']
    return total
def validate_inventory(path,reqs):
    freeze=load(path.parent/'FREEZE.json')
    assert freeze['request_inventory_sha256']==sha(path) and freeze['request_count']==len(reqs)
    assert freeze['protocol_sha256']==sha(ROOT/'e2/PROTOCOL.json')
    assert freeze['scope_inventory_sha256']==sha(ROOT/'e2/reference_author/common_scopes.json')
    assert freeze['source_packet_sha256']==sha(ROOT/'e2/reference_author/source_snapshot/task_packets.json')
    assert freeze['output_schema_sha256']==sha(ROOT/'e2/method_v1/output_schema.json')
    expected_schema=load(ROOT/'e2/method_v1/output_schema.json');expected_schema.pop('$schema',None)
    tasks={t['task_key']:t for t in load(ROOT/'e2/reference_author/common_scopes.json')['tasks']}
    for r in reqs:
        assert canonical_sha({k:v for k,v in r.items() if k!='request_id'})==r['request_id']
        inp=r['input'];t=tasks[r['task_key']]
        assert inp['common_scope']==t and inp['scope_sha256']==t['scope_sha256']
        assert canonical_sha({k:v for k,v in t.items() if k!='scope_sha256'})==t['scope_sha256']
        assert canonical_sha(inp['source_packet'])==inp['source_packet_sha256']==t['source_packet_sha256']
        assert r['output_schema']==expected_schema and r['max_output_tokens']==3000
    assert len({(r['task_key'],r['method'],r['model'],r['seed']) for r in reqs})==len(reqs)
    return freeze
def main():
    p=argparse.ArgumentParser();p.add_argument('--requests',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--workers',type=int,default=4);p.add_argument('--preflight-only',action='store_true');a=p.parse_args()
    a.requests=a.requests.resolve();reqs=rows(a.requests);assert len({r['request_id'] for r in reqs})==len(reqs);freeze=validate_inventory(a.requests,reqs)
    bound=sum(worst(r) for r in reqs);prior=accumulated()
    receipt={'utc':now(),'requests_sha256':sha(a.requests),'request_inventory_relative_path':str(a.requests.relative_to(ROOT)),'request_freeze_sha256':sha(a.requests.parent/'FREEZE.json'),'runner_sha256':sha(__file__),'requested_calls':len(reqs),'temperature':.2,'workers':a.workers,'cost_ceiling_usd':30,'prior_spent_or_reserved_usd':prior,'run_worst_case_usd':bound,'rates_per_million_tokens':RATES,'pricing_sources':['https://developers.openai.com/api/docs/models/gpt-4.1-mini','https://developers.openai.com/api/docs/models/gpt-4.1'],'pricing_checked_utc':'2026-10-04','no_retries':True,'same_call_budget_all_arms':True,'visible_source':'value-free common scope and immutable request/initial packet; no reference decisions, poststate or native utility labels','seed_policy':'best-effort API seed; seeds are repeats within a task, not independent tasks'}
    assert prior+bound<=30,(prior,bound,'Aggregate authorized US$30 ceiling')
    if a.preflight_only:print(json.dumps(receipt));return
    a.out.mkdir(parents=True,exist_ok=False);write(a.out/'PROVIDER_START.json',receipt)
    conf=dotenv_values(ROOT.parent/'.env');key=conf.get('OPENAI_API_KEY') or os.getenv('OPENAI_API_KEY');assert key,'Approved local configuration unavailable'
    url=(conf.get('OPENAI_BASE_URL') or 'https://api.openai.com/v1').rstrip('/');assert url=='https://api.openai.com/v1','Unexpected endpoint'
    def invoke(r):
        b=body(r);raw=json.dumps(b,ensure_ascii=False,separators=(',',':')).encode();t=time.perf_counter()
        row={k:r[k] for k in ['request_id','task_key','method','model','seed','phase']}
        row.update(request_sha256=hashlib.sha256(raw).hexdigest(),started_utc=now(),status='error',api_attempted=False,cost_usd=0,trustworthy_usage_priced=False)
        write(a.out/'requests'/(r['request_id']+'.json'),b)
        try:
            with httpx.Client(timeout=120,trust_env=False) as client:
                row['api_attempted']=True
                response=client.post(url+'/chat/completions',headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},content=raw)
            row['http_status']=response.status_code;row['provider_request_id']=response.headers.get('x-request-id');data=response.json();row['raw_response']=data
            if response.status_code!=200:row['error']=data.get('error',{}).get('code') or ('HTTP_'+str(response.status_code))
            else:
                assert data['model']==r['model'],'Snapshot mismatch'
                u=data['usage'];assert all(type(u.get(k)) is int and u[k]>=0 for k in ['prompt_tokens','completion_tokens'])
                cached=u.get('prompt_tokens_details',{}).get('cached_tokens',0);assert type(cached) is int and 0<=cached<=u['prompt_tokens']
                row['cost_usd']=cost(r['model'],u);row['trustworthy_usage_priced']=True;choice=data['choices'][0];row['finish_reason']=choice['finish_reason']
                assert choice['finish_reason']=='stop','Truncated or incomplete response'
                assert not choice['message'].get('refusal'),'Provider refusal'
                ann=json.loads(choice['message']['content']);assert isinstance(ann,dict)
                row.update(status='completed',annotation=ann,usage=data['usage'],resolved_model_id=data['model'],system_fingerprint=data.get('system_fingerprint'))
        except Exception as ex:
            row['error']=type(ex).__name__+': '+str(ex).replace(key,'[REDACTED]')
        if row['api_attempted'] and not row['trustworthy_usage_priced']:row['uncertain_cost_reserve_usd']=worst(r)
        row['wall_seconds']=time.perf_counter()-t;assert key not in json.dumps(row,ensure_ascii=False)
        write(a.out/'responses'/(r['request_id']+'.json'),row);return row
    completed=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as pool:
        for i,row in enumerate(pool.map(invoke,reqs),1):
            completed.append(row)
            if i%12==0 or i==len(reqs):print(json.dumps({'attempts_completed':i,'errors':sum(v['status']!='completed' for v in completed),'usage_cost_usd':round(sum(v['cost_usd'] for v in completed),6)}),flush=True)
    spend=sum(v['cost_usd'] for v in completed);reserve=sum(v.get('uncertain_cost_reserve_usd',0) for v in completed)
    write(a.out/'PROVIDER_END.json',{'utc':now(),'requests':len(completed),'api_attempts':sum(v['api_attempted'] for v in completed),'successful_candidates':sum(v['status']=='completed' for v in completed),'errors':sum(v['status']!='completed' for v in completed),'usage_cost_usd':spend,'uncertain_cost_reserve_usd':reserve,'budget_spent_or_reserved_usd':spend+reserve,'aggregate_authorized_spend_or_reserve_usd':prior+spend+reserve,'all_attempts_retained':True})
if __name__=='__main__':main()
