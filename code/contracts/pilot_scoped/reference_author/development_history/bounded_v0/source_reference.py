"""Independent source-only R21 per-obligation reference; no executor imports.

Labels concern the frozen common scope, never full-task utility/semantic gold.
Missing observations are unknown; observed absence/empty completed answers fail.
Explicit supported fact violations dominate unknown conditions. Source targets
are always resolved from the immutable base packet's inherited source rules.
"""
from __future__ import annotations

import json
import re
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCOPES = {s["task_key"]: s for s in json.loads((HERE / "common_scopes.json").read_text())["tasks"]}
SOURCE = {s["task_key"]: s for s in json.loads((HERE / "source_snapshot/r20_source_obligations.json").read_text())}
NUMBER = r"[-+]?\d+(?:\.\d+)?"
ALIASES = {"rating": r"(?:rating|rated|score)", "total": r"(?:total|cost|price)",
           "amount": r"(?:amount|spending|cost|paid)", "flight_number": r"(?:flight(?: number)?|flight_number|number)"}


def aggregate(statuses):
    return "fail" if "fail" in statuses else "unknown" if not statuses or "unknown" in statuses else "pass"


def equal(a, b):
    if isinstance(a, bool) or isinstance(b, bool): return type(a) is type(b) and a == b
    if isinstance(a, (int, float, Decimal)) and isinstance(b, (int, float, Decimal)):
        return Decimal(str(a)) == Decimal(str(b))
    return a == b


class Unavailable(Exception):
    pass


def node(state, *path):
    current = state
    for key in path:
        if not isinstance(current, dict) or key not in current or current[key] is None:
            raise Unavailable("required direct observation unavailable")
        current = current[key]
    return current


def conjunction(entity, fields):
    if not isinstance(entity, dict): raise Unavailable("required entity fields unavailable")
    statuses = []
    for field, expected in fields.items():
        statuses.append("unknown" if field not in entity or entity[field] is None else
                        "pass" if equal(entity[field], expected) else "fail")
    return aggregate(statuses)


def source_rule(obligation, key):
    kind = obligation["condition_kind"]
    return next(rule for rule in SOURCE[key]["rules"] if rule["kind"] == kind)


def state_check(obligation, key, observed):
    rule = source_rule(obligation, key)
    kind = rule["kind"]
    pre, post = observed.get("pre_state"), observed.get("post_state")
    try:
        if kind in ["new_payment", "new_schedule"]:
            section = "transactions" if kind == "new_payment" else "scheduled_transactions"
            before, after = node(pre, "bank_account", section), node(post, "bank_account", section)
            if not isinstance(before, list) or not isinstance(after, list): raise Unavailable()
            if any(not isinstance(t, dict) or "id" not in t for t in before): raise Unavailable()
            old_ids = {t["id"] for t in before}
            fields = {"recipient": rule["recipient"], "amount": rule["amount"]} if kind == "new_payment" else rule["fields"]
            possible = []
            for transaction in after:
                if not isinstance(transaction, dict) or "id" not in transaction:
                    possible.append("unknown")
                elif transaction["id"] not in old_ids:
                    possible.append(conjunction(transaction, fields))
            return "pass" if "pass" in possible else "unknown" if "unknown" in possible else "fail"
        if kind == "scheduled_update":
            after = node(post, "bank_account", "scheduled_transactions")
            if not isinstance(after, list): raise Unavailable()
            target = next((t for t in after if isinstance(t, dict) and t.get("id") == rule["id"]), None)
            return "fail" if target is None else conjunction(target, rule["fields"])
        if kind == "account_fields": return conjunction(node(post, "user_account"), rule["fields"])
        if kind == "reservation": return conjunction(node(post, "reservation"), rule["fields"])
        if kind == "user_presence":
            users = node(post, "slack", "users")
            if not isinstance(users, list): raise Unavailable()
            return "pass" if rule["user"] in users else "fail"
        if kind == "memberships":
            index = int(obligation["source_member_role"].rsplit("_", 1)[1]) - 1
            member = rule["members"][index]
            statuses = []
            try:
                users = node(post, "slack", "users")
                statuses.append("pass" if member["user"] in users else "fail")
            except (Unavailable, TypeError): statuses.append("unknown")
            try:
                channels = node(post, "slack", "user_channels")
                if not isinstance(channels, dict): raise Unavailable()
                if member["user"] not in channels: statuses.append("fail")
                elif channels[member["user"]] is None: statuses.append("unknown")
                else: statuses.append("pass" if member["channel"] in channels[member["user"]] else "fail")
            except (Unavailable, TypeError): statuses.append("unknown")
            return aggregate(statuses)
        if kind == "new_messages":
            index = int(obligation["source_message_role"].rsplit("_", 1)[1]) - 1
            message = rule["messages"][index]
            section = "channel_inbox" if message["destination_type"] == "channel" else "user_inbox"
            def count(state):
                buckets = node(state, "slack", section)
                if not isinstance(buckets, dict): raise Unavailable()
                inbox = buckets.get(message["recipient"], [])
                if not isinstance(inbox, list): raise Unavailable()
                return sum(isinstance(m, dict) and m.get("sender") == "bot" and
                           m.get("recipient") == message["recipient"] and m.get("body") == message["body"] for m in inbox)
            return "pass" if count(post) > count(pre) else "fail"
        raise ValueError(kind)
    except (Unavailable, KeyError, TypeError):
        return "unknown"


def query_observations(output, records, obligations):
    if output is None or not isinstance(output, str): return [], True, False
    if not output.strip(): return [], False, True
    source_fields = {r["entity"].casefold(): list(r["facts"]) for r in records}
    for obligation in obligations:
        for label in obligation.get("entity_binding", {}).get("accepted_labels", []):
            source_fields.setdefault(label.casefold(), []).append(obligation["property"])
    source_fields = {entity: list(dict.fromkeys(fields)) for entity, fields in source_fields.items()}
    all_fields = list(dict.fromkeys(f for r in records for f in r["facts"]))
    all_fields += [f for f in ["rating", "total", "amount", "flight_number"] if f not in all_fields]
    facts, unsupported = [], False
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line or line == "Quoted source only:": continue
        if re.fullmatch(r"Unrelated option is not rated " + NUMBER + r"\.", line): continue
        polarity = "positive"
        if line.startswith("> "): polarity, line = "quoted", line[2:]
        elif line.startswith("Not: "): polarity, line = "negative", line[5:]
        if line.endswith(" is an option.") and line[:-len(" is an option.")].casefold() in source_fields:
            continue
        if line.endswith(" —"): line += " "  # completed empty record after whitespace trimming
        if " — " not in line:
            unsupported = True
            continue
        entity, body = line.split(" — ", 1)
        if not entity or entity != entity.strip() or any(c in entity for c in ['"', "'", "`", ";", "?", ">"]):
            unsupported = True
            continue
        if not body.strip(): continue  # recognized completed empty/partial record
        fields = source_fields.get(entity.casefold(), all_fields)
        for piece in body.split(","):
            parsed = False
            for field in fields:
                token = r"[A-Za-z]+\d+" if field == "flight_number" else NUMBER
                pattern = ALIASES[field] + r"\s*(?:is|of|:|=|at)?\s*(?:EUR|euros?|€|\$)?\s*(" + token + ")"
                match = re.fullmatch(pattern, piece.strip(), re.I)
                if match:
                    value = match.group(1) if field == "flight_number" else Decimal(match.group(1))
                    facts.append({"entity": entity, "property": field, "value": value, "polarity": polarity})
                    parsed = True
                    break
            if not parsed: unsupported = True
    return facts, unsupported, True


def query_check(obligation, key, observed):
    rule = SOURCE[key]["rules"][0]
    role = obligation["binding_role"]
    roles = list(dict.fromkeys(o["binding_role"] for o in SCOPES[key]["obligations"]))
    record = rule["records"][roles.index(role)]
    field, expected = obligation["property"], record["facts"][obligation["property"]]
    facts, unsupported, completed = query_observations(observed.get("output"), rule["records"], SCOPES[key]["obligations"])
    accepted = obligation.get("entity_binding", {}).get("accepted_labels", [record["entity"]])
    target_facts = [f for f in facts if f["entity"].casefold() in [label.casefold() for label in accepted] and f["property"] == field]
    if any(f["polarity"] == "negative" or
           (f["polarity"] == "positive" and not equal(f["value"], expected)) for f in target_facts): return "fail"
    if unsupported or not completed: return "unknown"
    if any(f["polarity"] == "positive" and equal(f["value"], expected) for f in target_facts): return "pass"
    return "fail"


def evaluate(task_key, observed):
    scope = SCOPES[task_key]
    decisions = []
    for obligation in scope["obligations"]:
        status = state_check(obligation, task_key, observed) if obligation["kind"] == "state" else query_check(obligation, task_key, observed)
        decisions.append({"obligation_id": obligation["obligation_id"], "status": status,
                          "evidence": {"source_packet_sha256": scope["source_packet_sha256"], "scope_sha256": scope["scope_sha256"],
                                       "source_binding": obligation["source_binding"],
                                       "observation_requirements": obligation["observation_requirements"]}})
    return {"scope_id": scope["scope_id"], "scope_sha256": scope["scope_sha256"],
            "source_packet_sha256": scope["source_packet_sha256"], "reference_status": aggregate([d["status"] for d in decisions]),
            "obligation_decisions": decisions, "designation": "source-scoped reference, not full-task gold"}
