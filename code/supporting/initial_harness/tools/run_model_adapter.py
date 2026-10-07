#!/usr/bin/env python3
"""Provider-neutral model launcher. Adapter contract: one request JSON on stdin,
one response JSON on stdout. No shell and no implicit retries. All failures stay
in the output. Actual API authentication belongs to the server adapter/env, not
this ZIP. This file is NOT a bundled provider implementation.
"""
import argparse,subprocess,shlex,json,time
from pathlib import Path
from common_handoff import load,read_jsonl,write,new_out,sha,utc

def main():
    p=argparse.ArgumentParser();p.add_argument('--requests',type=Path,required=True)
    p.add_argument('--adapter-command',required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--max-calls',type=int,required=True);p.add_argument('--timeout',type=float,default=180)
    a=p.parse_args();reqs=read_jsonl(a.requests)
    if len(reqs)>a.max_calls:raise ValueError('Explicit call budget is smaller than request inventory')
    out=new_out(a.out);cmd=shlex.split(a.adapter_command)
    write(out/'START.json',{'requests_sha256':sha(a.requests),'started_utc':utc(),
          'request_count':len(reqs),'adapter_executable':cmd[0],
          'no_retry':True,'note':'Do not put credentials in adapter command line or stdout/stderr.'})
    for r in reqs:
        t=time.perf_counter();row={k:r[k] for k in ['request_id','packet_id','method','model','seed','phase']}
        try:
            proc=subprocess.run(cmd,input=json.dumps(r),text=True,capture_output=True,timeout=a.timeout,check=False)
            # Keep full raw output, but the adapter MUST NOT print secrets.
            row.update(returncode=proc.returncode,raw_stdout=proc.stdout,raw_stderr=proc.stderr)
            if proc.returncode:raise RuntimeError('Adapter exited nonzero')
            response=json.loads(proc.stdout)
            if 'resolved_model_id' not in response or 'annotation' not in response:
                raise ValueError('Adapter requires resolved_model_id and annotation')
            row.update(status='completed',response=response)
        except Exception as e:row.update(status='error',error=type(e).__name__+': '+str(e))
        row['wall_seconds']=time.perf_counter()-t;write(out/'responses'/(r['request_id']+'.json'),row)
    write(out/'END.json',{'completed_utc':utc(),'all_attempts_retained':True})
if __name__=='__main__':main()
