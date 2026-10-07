"""After-exposure information ablations; no repairs selected from outcomes."""
import copy,pickle,secrets,hashlib
from pydantic import BaseModel
from common21 import identity,digest,capture,v4,rn
ARMS=['json_only','type_order','alias_endpoint_types','full_witness','trusted_pickle','v4_control']

class UnsupportedAblation(ValueError):pass
class TrustedCheckpoint:
    """Only capture_live creates a registered checkpoint. Raw/external bytes refused.
    Same-process experiment capability, not a cryptographic security boundary.
    The baseline never accepts an external pickle file or byte payload.
    """
    __slots__=('token','payload','snapshot_hash','graph')
    def __init__(self,*args):raise TypeError('Use capture_live on a trusted native object')
_LIVE={}
def capture_live(obj):
    if not isinstance(obj,BaseModel):raise TypeError('Trusted native BaseModel required')
    c=object.__new__(TrustedCheckpoint);c.token=secrets.token_hex(24)
    c.payload=pickle.dumps(obj,protocol=5);c.snapshot_hash=digest(rn.dump(obj));c.graph=capture(obj)
    _LIVE[c.token]=(c,hashlib.sha256(c.payload).digest());return c
def restore_live(c):
    if type(c) is not TrustedCheckpoint or c.token not in _LIVE:raise UnsupportedAblation('External/raw checkpoint refused')
    registered,h=_LIVE[c.token]
    if registered is not c or hashlib.sha256(c.payload).digest()!=h:raise UnsupportedAblation('Checkpoint capability/payload mismatch')
    obj=pickle.loads(c.payload) # Only bytes newly generated from trusted live objects above.
    if digest(rn.dump(obj))!=c.snapshot_hash or capture(obj)!=c.graph:raise UnsupportedAblation('Trusted checkpoint value/graph changed')
    return obj
def release(c):_LIVE.pop(c.token,None)
def validate(cls,payload,w):
    if not isinstance(w,dict) or w.get('format')!='native_model_graph_v1':raise UnsupportedAblation('Captured witness required')
    if w.get('snapshot_sha256')!=digest(payload):raise UnsupportedAblation('Snapshot/witness mismatch')
    if w.get('native_source_revision')!=identity.REV or w.get('root_type')!=identity.name(cls):raise UnsupportedAblation('Pinned source/root mismatch')
def restore_partial(cls,payload,w,arm):
    validate(cls,payload,w);root=identity.base.restore(cls,copy.deepcopy(payload));classes=identity.catalog(cls)
    if arm=='type_order':
        for item in sorted(w['model_types'],key=lambda i:len(i['path'])):
            expected=classes.get(item['type'])
            if expected is None:raise UnsupportedAblation('Unreachable native type')
            node=identity.get(root,item['path'])
            if type(node) is not expected:
                if not isinstance(node,dict):raise UnsupportedAblation('Incompatible model type')
                identity.set_at(root,item['path'],identity.base.restore(expected,node))
        for item in w['dict_orders']:
            node=identity.get(root,item['path'])
            if not isinstance(node,dict) or len(item['keys'])!=len(node) or set(item['keys'])!={str(k) for k in node}:raise UnsupportedAblation('Invalid order witness')
            keys=[identity.key_of(node,k) for k in item['keys']]
            if [identity.name(type(k)) for k in keys]!=item['key_types']:raise UnsupportedAblation('Invalid order key type')
            items=[(k,node[k]) for k in keys];node.clear();node.update(items)
    elif arm=='alias_endpoint_types':
        # Alias type is part of the captured edge; global model_types/orders unused.
        seen=set()
        for item in w['aliases']:
            key=repr(item['path'])
            if key in seen or item['path']==item['target']:raise UnsupportedAblation('Duplicate/self alias')
            seen.add(key);source=identity.get(root,item['target']);target=identity.get(root,item['path'])
            if identity.name(type(source))!=item['type']:
                expected=classes.get(item['type'])
                if expected is None or not isinstance(source,dict):raise UnsupportedAblation('Alias endpoint native type unsupported')
                source=identity.base.restore(expected,source);identity.set_at(root,item['target'],source)
            if digest(identity.serialized(source))!=digest(identity.serialized(target)):raise UnsupportedAblation('Unequal alias endpoint values')
            identity.set_at(root,item['path'],source)
    else:raise UnsupportedAblation('Unknown partial reader')
    return root
def restore_arm(arm,cls,payload,witness,checkpoint=None):
    if arm=='json_only':return identity.base.restore(cls,copy.deepcopy(payload))
    if arm in ('type_order','alias_endpoint_types'):return restore_partial(cls,payload,witness,arm)
    if arm=='full_witness':return identity.restore(cls,payload,witness)
    if arm=='trusted_pickle':return restore_live(checkpoint)
    if arm=='v4_control':return v4.checked_restore(cls,copy.deepcopy(payload))
    raise UnsupportedAblation('Unknown arm')
