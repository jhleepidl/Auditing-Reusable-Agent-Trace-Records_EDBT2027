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
        computed=annotation.model_computed_fields
        extra=set(value)-set(fields)-set(computed)
        if extra: raise UnsupportedSnapshot(f'Unknown model fields: {sorted(extra)}')
        missing=[k for k,f in fields.items() if f.is_required() and k not in value]
        if missing: raise UnsupportedSnapshot(f'Missing model fields: {missing}')
        # Computed aliases are regenerated from typed fields, then the complete
        # JSON dump must match. Inconsistent derived values are rejected.
        vals={k:restore(fields[k].annotation,v) for k,v in value.items() if k in fields}

        # Native seed-to-mapping constructors and append-only numeric IDs have
        # ordering semantics that JSON object equality cannot represent. Support
        # only these three pinned native schemas; validate the full JSON witness
        # and all recorded continuations separately. This is corpus-bound policy.
        seed_map={
            ('agentdojo.default_suites.v1.tools.email_client','Inbox'):('initial_emails','emails'),
            ('agentdojo.default_suites.v1.tools.calendar_client','Calendar'):('initial_events','events'),
            ('agentdojo.default_suites.v1.tools.cloud_drive_client','CloudDrive'):('initial_files','files'),
        }.get((annotation.__module__,annotation.__name__))
        if seed_map:
            seed_field,map_field=seed_map
            members=vals[map_field]
            initial_ids=[item.id_ for item in vals[seed_field]]
            if len(initial_ids)!=len(set(initial_ids)):
                raise UnsupportedSnapshot('Duplicate seed IDs in ordered native mapping')
            initial_keys=[key for key in initial_ids if key in members]
            added=[key for key in members if key not in set(initial_ids)]
            if any(not str(key).isdigit() for key in added):
                raise UnsupportedSnapshot('Unsupported nonnumeric appended native ID')
            # Native constructors share seed instances with the live mapping.
            # Recreate that schema-specific link only when the stored complete
            # item values agree; leave unequal instances distinct. JSON alone
            # cannot prove general identity and this policy is corpus-bound.
            for item in vals[seed_field]:
                if item.id_ in members and item.model_dump(mode='json')==members[item.id_].model_dump(mode='json'):
                    members[item.id_]=item
            order=initial_keys+sorted(added,key=lambda key:int(str(key)))
            vals[map_field]={key:members[key] for key in order}
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
