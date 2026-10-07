"""Candidate lossless typed snapshot reader for TRUSTED, hash-bound stored states.
This deliberately bypasses model-level initialization validators. It is NOT an
untrusted-input validation API, and correctness must be tested by dump identity,
native grading, and recorded-action continuation. Unsupported types fail closed.
No pickle, eval, source-code modification, or mock native tools are used.
"""
from __future__ import annotations
import types, typing, enum, copy
from collections.abc import Mapping
from pydantic import BaseModel, TypeAdapter

class UnsupportedSnapshot(ValueError): pass

def restore(annotation, value):
    origin=typing.get_origin(annotation);args=typing.get_args(annotation)
    if annotation is typing.Any: return copy.deepcopy(value)
    if origin is typing.Annotated: return restore(args[0],value)
    if annotation in (None,type(None)):
        if value is not None: raise UnsupportedSnapshot('Expected null')
        return None
    if origin in (typing.Union, types.UnionType):
        failures=[]
        # Prefer JSON-native primitive branches to avoid str/int ambiguity.
        ordered=sorted(args,key=lambda t: 0 if t is type(value) else 1)
        for t in ordered:
            try: return restore(t,value)
            except (ValueError,TypeError,UnsupportedSnapshot) as e: failures.append(str(e))
        raise UnsupportedSnapshot('No supported union branch: '+' | '.join(failures))
    if isinstance(annotation,type) and issubclass(annotation,BaseModel):
        if not isinstance(value,dict): raise UnsupportedSnapshot('Model snapshot must be an object')
        fields=annotation.model_fields
        extra=set(value)-set(fields)
        if extra: raise UnsupportedSnapshot(f'Unknown model fields: {sorted(extra)}')
        missing=[k for k,f in fields.items() if f.is_required() and k not in value]
        if missing: raise UnsupportedSnapshot(f'Missing model fields: {missing}')
        vals={k:restore(fields[k].annotation,v) for k,v in value.items()}
        return annotation.model_construct(_fields_set=set(value),**vals)
    if origin in (dict,Mapping,typing.Mapping):
        if not isinstance(value,dict): raise UnsupportedSnapshot('Expected dictionary')
        kt,vt=args or (typing.Any,typing.Any)
        return {restore(kt,k):restore(vt,v) for k,v in value.items()}
    if origin in (list,set,frozenset,tuple):
        if not isinstance(value,(list,tuple)): raise UnsupportedSnapshot('Expected sequence')
        if origin is tuple and args and args[-1] is not Ellipsis:
            if len(args)!=len(value): raise UnsupportedSnapshot('Tuple length mismatch')
            return tuple(restore(t,v) for t,v in zip(args,value))
        t=args[0] if args else typing.Any; xs=[restore(t,v) for v in value]
        return origin(xs)
    if hasattr(annotation,'__supertype__'): return annotation(restore(annotation.__supertype__,value))
    # Dates, enums, primitive scalars, Literal and constrained scalar aliases.
    try: return TypeAdapter(annotation).validate_python(value)
    except Exception as e: raise UnsupportedSnapshot(f'Unsupported/scalar-invalid {annotation}: {e}') from e

def dump(obj): return obj.model_dump(mode='json')

def checked_restore(cls, payload):
    obj=restore(cls,payload)
    if dump(obj)!=payload: raise UnsupportedSnapshot('Reader did not preserve complete serialized values')
    return obj
