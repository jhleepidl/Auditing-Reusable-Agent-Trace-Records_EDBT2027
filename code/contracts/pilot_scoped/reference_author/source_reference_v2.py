"""Authority-only R21B wrapper around immutable source reference semantics.

No parser, source goal, expected value or decision modification. Obligation IDs
remain identical; only explicit public v2 scope headers/evidence hashes change.
"""
from __future__ import annotations
import copy
import json
from pathlib import Path
from source_reference import evaluate as source_semantic_evaluate, SCOPES as SCOPES_V1
HERE=Path(__file__).resolve().parent
SCOPES={s['task_key']:s for s in json.loads((HERE/'common_scopes_v2.json').read_text())['tasks']}


def evaluate(task_key,observed):
    scope=SCOPES[task_key];old=SCOPES_V1[task_key]
    assert old['required_obligation_ids']==scope['required_obligation_ids']
    assert old['source_packet_sha256']==scope['source_packet_sha256']
    result=copy.deepcopy(source_semantic_evaluate(task_key,observed))
    result['scope_id']=scope['scope_id'];result['scope_sha256']=scope['scope_sha256']
    for decision in result['obligation_decisions']:
        decision['evidence']['scope_sha256']=scope['scope_sha256']
    return result
