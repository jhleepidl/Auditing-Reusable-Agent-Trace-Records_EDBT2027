"""Read-only pinned R20 inputs and real native execution for R21 CPU studies."""
from pathlib import Path
import os,sys,json,copy,hashlib,datetime,importlib.util,importlib.metadata
HERE=Path(__file__).resolve().parent
R20=Path(os.environ.get('EDBT_R20_ROOT',str(HERE.parents[1]/'edbt_r20_followup'))).resolve()
KIT=R20/'work/native/EDBT_R18_CPU_RESULTS/EDBT_R18_NO_HUMAN_KIT'
sys.path.insert(0,str(KIT/'tools'))
import run_native as rn

def module(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
identity=module('r21_frozen_v5',R20/'e1/v5/identity_reader.py')
v4=module('r21_frozen_v4',R20/'e1/v4/tools/typed_restore.py')
canon=identity.canon;digest=identity.digest;capture=identity.capture
def load(p):return json.loads(Path(p).read_text())
def write(p,x):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def new_out(p):
    p=Path(p)
    if p.exists():raise FileExistsError('Never overwrite existing experimental outputs: '+str(p))
    p.mkdir(parents=True);return p
def verify_freeze():
    f=load(HERE/'FREEZE.json')
    for p,h in f['files'].items():assert sha(HERE/p)==h,('new code/plan drift',p)
    for p,h in f['baseline_files'].items():assert sha(R20/p)==h,('R20 input drift',p)
    native=load(R20/'e1/FREEZE.json')
    for p,h in native['files'].items():assert sha(R20/p)==h,('native frozen source drift',p)
    pins=load(KIT/'vendor/r11/ENVIRONMENT.json')['dependency_pins']
    for name,expected in pins.items():assert importlib.metadata.version(name)==expected,('dependency pin',name)
    assert len(pins)==75 and sys.version.split()[0]=='3.11.7'
    return f
def old_programs():
    out=[]
    for group,path in [('repair24','e1/prospective24/PLAN.json'),('confirmation12','e1/v5/CONFIRMATION_PLAN.json')]:
        plan=load(R20/path)
        for p in plan['programs']:out.append({**copy.deepcopy(p),'original_group':group,'initial_state_sha256':plan['initial_state_sha256']})
    assert len(out)==36;return out
def transported(obj):return json.loads(canon(rn.dump(obj)))
def step(api,runtime,env,action):
    call=api.Call(**copy.deepcopy(action));request=rn.dump(call)
    value,error=runtime.run_function(env,call.function,call.args)
    return {'request_call':request,'call':rn.dump(call),'result':rn.dump(value),'error':error,'state':rn.dump(env),'graph_sha256':digest(capture(env))}
def native_program(api,suite,p):
    env=suite.load_and_inject_default_environment({});assert digest(rn.dump(env))==p['initial_state_sha256']
    rt=api.Runtime(suite.tools);trace=[];prefix=None
    with rn.clock():
        for i,action in enumerate(p['steps']):
            s=step(api,rt,env,action);trace.append(s)
            if (s['error'] is not None)!=(i in p['expected_error_indices']):raise RuntimeError('Unexpected/missing native error '+str(i))
            if i+1==p['cut']:prefix=env.model_copy(deep=True)
    if prefix is None:raise RuntimeError('No prefix')
    return prefix,env,trace
def continue_program(api,suite,env,p):
    rt=api.Runtime(suite.tools);out=[]
    with rn.clock():
        for action in p['steps'][p['cut']:]:out.append(step(api,rt,env,action))
    return out
def compare(actual,expected):
    return {'returns_errors_exact':len(actual)==len(expected) and all(a['result']==e['result'] and a['error']==e['error'] for a,e in zip(actual,expected)),
            'suffix_state_exact':len(actual)==len(expected) and all(digest(a['state'])==digest(e['state']) for a,e in zip(actual,expected)),
            'suffix_graph_exact':len(actual)==len(expected) and all(a['graph_sha256']==e['graph_sha256'] for a,e in zip(actual,expected))}
