#!/usr/bin/env python3
"""E2 builder request export, without importing an evaluator or executing tasks.
Trusted packet producer reads ONLY declarative PROMPT expressions and retained PRE
states; evaluator code, official solutions, post-states and labels are never
included in model input. Run adapters in an isolated environment containing only
these packets when making a source-masking claim.
"""
from pathlib import Path
import argparse,ast,hashlib
from common_handoff import ROOT,load,write,new_out,kit_path,digest,write_jsonl,sha

def literal_prompt(path, class_name):
    """Resolve only declarative string expressions; never import task code.

    Supports constants, local class constant references, string concatenation,
    f-strings, and the pinned TaskCombinator's prompt-only composition rule.
    Final prompt SHA is always checked against the original native inventory.
    """
    tree=ast.parse(path.read_text(encoding='utf-8'))
    classes={n.name:n for n in tree.body if isinstance(n,ast.ClassDef)}
    def assignments(nodes):
        return {t.id:n.value for n in nodes if isinstance(n,ast.Assign)
                for t in n.targets if isinstance(t,ast.Name)}
    module=assignments(tree.body)
    def static(node, env, trail=()):
        if isinstance(node,ast.Constant):return node.value
        if isinstance(node,ast.Name):
            if node.id in trail or node.id not in env:raise ValueError('Unsupported prompt name: '+node.id)
            return static(env[node.id],env,trail+(node.id,))
        if isinstance(node,ast.BinOp) and isinstance(node.op,ast.Add):
            a,b=static(node.left,env,trail),static(node.right,env,trail)
            if not isinstance(a,str) or not isinstance(b,str):raise ValueError('Only string concatenation is supported')
            return a+b
        if isinstance(node,ast.JoinedStr):
            return ''.join(str(static(n,env,trail)) for n in node.values)
        if isinstance(node,ast.FormattedValue):
            v=static(node.value,env,trail)
            if node.conversion==114:v=repr(v)
            elif node.conversion==115:v=str(v)
            elif node.conversion==97:v=ascii(v)
            elif node.conversion!=-1:raise ValueError('Unknown format conversion')
            return format(v,static(node.format_spec,env,trail) if node.format_spec else '')
        raise ValueError('Unsupported declarative prompt expression: '+type(node).__name__)
    def read(name,seen=()):
        if name in seen:raise ValueError('Recursive combined prompt')
        if name in classes:
            c=classes[name];env={**module,**assignments(c.body)}
            if 'PROMPT' in env:
                text=static(env['PROMPT'],env)
                if not isinstance(text,str):raise ValueError('PROMPT is not a string')
                return text
            for b in c.bases:
                if isinstance(b,ast.Name) and b.id in classes:return read(b.id,seen+(name,))
        for expr in tree.body:
            call=expr.value if isinstance(expr,ast.Expr) else None
            if not isinstance(call,ast.Call) or not isinstance(call.func,ast.Attribute) or call.func.attr!='create_combined_task':continue
            if not call.args or not isinstance(call.args[0],ast.Constant) or call.args[0].value!=name:continue
            for k in call.keywords:
                if k.arg=='prompt':return static(k.value,module)
            if len(call.args)!=3:raise ValueError('Unsupported combined task arity')
            children=[]
            for arg in call.args[1:]:
                if not isinstance(arg,ast.Subscript) or not isinstance(arg.slice,ast.Constant):raise ValueError('Unsupported task reference')
                tid=arg.slice.value
                if not isinstance(tid,str) or not tid.startswith('user_task_'):raise ValueError('Bad task ID')
                children.append(read('UserTask'+tid.rsplit('_',1)[1],seen+(name,)))
            return f'Perform the following tasks in the order they are given: 1. {children[0]} 2. {children[1]}'
        raise ValueError('Declarative prompt missing '+name)
    return read(class_name)

def main():
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--phase',choices=['development','prospective_contract_test','compositional_transfer_secondary'],required=True)
    p.add_argument('--models',nargs='+',required=True,help='Exact server model IDs; aliases must be resolved and logged')
    p.add_argument('--seeds',nargs='+',type=int,default=[11,23,37]);a=p.parse_args()
    out=new_out(a.out);kit=kit_path(a.work);tasks=[r for r in load(a.work/'TASK_EXPOSURE_AND_SPLIT.json') if r['split']==a.phase]
    requests=[];mapping=[]
    for r in tasks:
        suite,tid=r['suite'],r['task_id'];idx=int(tid.rsplit('_',1)[1])
        prompt=literal_prompt(kit/f'vendor/agentdojo/src/agentdojo/default_suites/v1/{suite}/user_tasks.py',f'UserTask{idx}')
        if hashlib.sha256(prompt.encode()).hexdigest()!=r['prompt_sha256']:raise ValueError('Prompt source mismatch')
        pre=load(kit/f'runs/r18_cpu_01/native/sweep/cases/v1/{suite}/{tid}/pre_state.json')
        schema=load(kit/f'inputs/r11/schemas/{suite}.json');pid=digest({'suite':suite,'task':tid})[:16]
        mapping.append({'packet_id':pid,'task_key':suite+'/'+tid,'split':a.phase,'prior_exposure':r['prior_exposure']})
        for method in ['direct','schema_only','evidence_bound']:
            packet={'packet_id':pid,'task_request':prompt,'initial_state':pre}
            if method!='direct':packet['state_schema']=schema
            inst=(ROOT/f'prompts/{method}.txt').read_text()
            for model in a.models:
                for seed in a.seeds:
                    requests.append({'request_id':digest({'packet':pid,'method':method,'model':model,'seed':seed}),
                         'packet_id':pid,'method':method,'model':model,'seed':seed,
                         'system':inst,'input':packet,'phase':a.phase})
    write_jsonl(out/'requests.jsonl',requests);write(out/'PRIVATE_TASK_MAPPING.json',mapping)
    write(out/'REQUEST_FREEZE.json',{'requests_sha256':sha(out/'requests.jsonl'),'phase':a.phase,
         'tasks':len(tasks),'calls_requested':len(requests),'actual_calls':0,
         'warning':'Task IDs are contract-development held-out, NOT unseen benchmark tasks. Keep test challenge and reference judgments separate.'})
    print('Wrote',len(requests),'requests. No API calls performed.')
if __name__=='__main__':main()
