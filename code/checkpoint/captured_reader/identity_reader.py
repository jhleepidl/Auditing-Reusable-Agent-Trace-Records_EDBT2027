"""Restore a trusted typed snapshot using NEW native identity/order evidence.
The witness covers BaseModel real fields, list/dict identity and dictionary order.
It does not claim recovery of private attributes, globals or arbitrary objects.
No pickle/eval/dynamic imports from witness metadata. Native classes must be
reachable from the caller's pinned root schema. A JSON snapshot alone is refused.
"""
from pathlib import Path
import typing,importlib.util,hashlib,json,copy
from pydantic import BaseModel
BASE_PATH=Path(__file__).resolve().parents[1]/'v2/tools/typed_restore.py'
spec=importlib.util.spec_from_file_location('identity_typed_base',BASE_PATH);base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
REV='089ed468cf3ed0322acc66b0211f26d9d90dbf60'
class UnsupportedWitness(ValueError):pass

def name(cls):return cls.__module__+'.'+cls.__qualname__
def canon(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
def digest(x):return hashlib.sha256(canon(x).encode()).hexdigest()
def serialized(x):
    if isinstance(x,BaseModel):return x.model_dump(mode='json')
    if isinstance(x,dict):return {str(k):serialized(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [serialized(v) for v in x]
    return x

def capture(obj):
    if not isinstance(obj,BaseModel):raise UnsupportedWitness('Root must be pinned native BaseModel')
    snapshot=obj.model_dump(mode='json');seen={};models=[];orders=[];aliases=[]
    def walk(node,path):
        if not isinstance(node,(BaseModel,list,dict)):return
        if id(node) in seen:
            aliases.append({'path':path,'target':seen[id(node)],'type':name(type(node))});return
        seen[id(node)]=path
        if isinstance(node,BaseModel):
            models.append({'path':path,'type':name(type(node))})
            for key in type(node).model_fields:walk(getattr(node,key),path+[{'kind':'field','key':key}])
        elif isinstance(node,dict):
            keys=[str(k) for k in node]
            if len(keys)!=len(set(keys)):raise UnsupportedWitness('Ambiguous serialized dictionary keys')
            orders.append({'path':path,'keys':keys,'key_types':[name(type(k)) for k in node]})
            for key,value in node.items():walk(value,path+[{'kind':'key','key':str(key)}])
        else:
            for index,value in enumerate(node):walk(value,path+[{'kind':'index','index':index}])
    walk(obj,[])
    return {'format':'native_model_graph_v1','snapshot_sha256':digest(snapshot),'native_source_revision':REV,'root_type':name(type(obj)),'model_types':models,'dict_orders':orders,'aliases':aliases,'capture_scope':'BaseModel declared real fields and list/dict graph; no private/global/external state'}

def catalog(cls):
    result={};visited=set()
    def collect(a):
        try:
            if a in visited:return
            visited.add(a)
        except TypeError:pass
        if isinstance(a,type) and issubclass(a,BaseModel):
            result[name(a)]=a
            for f in a.model_fields.values():collect(f.annotation)
        else:
            for b in typing.get_args(a):collect(b)
    collect(cls);return result

def key_of(mapping,key):
    matches=[k for k in mapping if str(k)==key]
    if len(matches)!=1:raise UnsupportedWitness('Dictionary path key absent or ambiguous')
    return matches[0]
def get(root,path):
    cur=root
    for step in path:
        kind=step.get('kind')
        if kind=='field' and isinstance(cur,BaseModel) and step['key'] in type(cur).model_fields:cur=getattr(cur,step['key'])
        elif kind=='key' and isinstance(cur,dict):cur=cur[key_of(cur,step['key'])]
        elif kind=='index' and isinstance(cur,list) and 0<=step['index']<len(cur):cur=cur[step['index']]
        else:raise UnsupportedWitness('Invalid native graph path')
    return cur

def set_at(root,path,value):
    if not path:raise UnsupportedWitness('Cannot replace root through witness')
    parent=get(root,path[:-1]);s=path[-1]
    if s['kind']=='field' and isinstance(parent,BaseModel) and s['key'] in type(parent).model_fields:setattr(parent,s['key'],value)
    elif s['kind']=='key' and isinstance(parent,dict):parent[key_of(parent,s['key'])]=value
    elif s['kind']=='index' and isinstance(parent,list) and 0<=s['index']<len(parent):parent[s['index']]=value
    else:raise UnsupportedWitness('Invalid alias/model destination')

def restore(cls,payload,witness):
    if not isinstance(witness,dict) or witness.get('format')!='native_model_graph_v1':raise UnsupportedWitness('Explicit captured native graph witness required')
    if witness.get('snapshot_sha256')!=digest(payload):raise UnsupportedWitness('Snapshot/witness hash mismatch')
    if witness.get('native_source_revision')!=REV or witness.get('root_type')!=name(cls):raise UnsupportedWitness('Pinned native source/root mismatch')
    root=base.restore(cls,copy.deepcopy(payload));classes=catalog(cls)
    for item in sorted(witness['model_types'],key=lambda i:len(i['path'])):
        expected=classes.get(item['type'])
        if expected is None:raise UnsupportedWitness('Witness model type outside pinned root schema')
        node=get(root,item['path'])
        if type(node) is not expected:
            if not isinstance(node,dict):raise UnsupportedWitness('Incompatible captured model type')
            replacement=base.restore(expected,node);set_at(root,item['path'],replacement)
    for item in witness['dict_orders']:
        node=get(root,item['path'])
        if not isinstance(node,dict):raise UnsupportedWitness('Dictionary order path is not a dictionary')
        if len(item['keys'])!=len(node) or set(item['keys'])!={str(k) for k in node}:raise UnsupportedWitness('Dictionary key witness mismatch')
        keys=[key_of(node,k) for k in item['keys']]
        if [name(type(k)) for k in keys]!=item['key_types']:raise UnsupportedWitness('Dictionary key type witness mismatch')
        ordered=[(k,node[k]) for k in keys];node.clear();node.update(ordered)
    for item in witness['aliases']:
        source=get(root,item['target']);target=get(root,item['path'])
        if name(type(source))!=item['type']:raise UnsupportedWitness('Alias target type witness mismatch')
        if digest(serialized(source))!=digest(serialized(target)):raise UnsupportedWitness('Alias cannot link unequal serialized values')
        set_at(root,item['path'],source)
    if digest(root.model_dump(mode='json'))!=digest(payload):raise UnsupportedWitness('Complete canonical snapshot value witness failed')
    if capture(root)!=witness:raise UnsupportedWitness('Reconstructed modeled identity/order graph differs from native witness')
    return root
