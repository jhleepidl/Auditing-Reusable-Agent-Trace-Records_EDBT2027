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
ALIASES = {"rating": r"(?:rating|rated|score)", "total": r"(?:total cost|total|cost|price)",
           "amount": r"(?:amount|spending|paid)", "flight_number": r"(?:flight(?: number)?|flight_number|number)"}
QUALIFIER = r"(?:(?P<unit>USD|EUR|GBP|dollars?|euros?|\$|€|£|points)(?:\s+)?|)(?:(?:for|over)\s+(?P<duration>\d+)\s+(?P<period>days?|people|persons?|passengers?))?"


def aggregate(statuses):
    return "fail" if "fail" in statuses else "unknown" if not statuses or "unknown" in statuses else "pass"


def equal(a, b):
    if isinstance(a, bool) or isinstance(b, bool): return type(a) is type(b) and a == b
    if isinstance(a, (int, float, Decimal)) and isinstance(b, (int, float, Decimal)):
        return Decimal(str(a)) == Decimal(str(b))
    return a == b


class Unavailable(Exception):
    pass


class ObservedAbsence(Exception):
    pass


def node(state, *path):
    if state is None: raise Unavailable("whole required snapshot unavailable")
    current = state
    for key in path:
        if not isinstance(current, dict) or key not in current or current[key] is None:
            raise ObservedAbsence("required node absent in fully observed snapshot")
        current = current[key]
    return current


def conjunction(entity, fields):
    if not isinstance(entity, dict): return "fail"
    statuses = []
    for field, expected in fields.items():
        statuses.append("fail" if field not in entity or entity[field] is None else
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
            if any(not isinstance(t, dict) or "id" not in t for t in before + after): raise Unavailable()
            if any(len({t["id"] for t in ts}) != len(ts) for ts in [before, after]): raise Unavailable()
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
            except ObservedAbsence: statuses.append("fail")
            except (Unavailable, TypeError): statuses.append("unknown")
            try:
                channels = node(post, "slack", "user_channels")
                if not isinstance(channels, dict): raise Unavailable()
                if member["user"] not in channels: statuses.append("fail")
                elif channels[member["user"]] is None: statuses.append("fail")
                else: statuses.append("pass" if member["channel"] in channels[member["user"]] else "fail")
            except ObservedAbsence: statuses.append("fail")
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
    except ObservedAbsence:
        return "fail"
    except (Unavailable, KeyError, TypeError):
        return "unknown"


def query_observations(output, records, obligations):
    """Parse only enumerated record syntax; no free-prose entailment."""
    if output is None or not isinstance(output, str): return [], True, False
    if not output.strip(): return [], False, True
    known_entities = {r["entity"].casefold() for r in records}
    known_entities.update(label.casefold() for o in obligations for label in o.get("entity_binding", {}).get("accepted_labels", []))
    facts, unsupported = [], False
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line or line == "Quoted source only:": continue
        polarity, role = "positive", None
        if line.startswith("> "): polarity, line = "quoted", line[2:]
        elif line.startswith("Not: "): polarity, line = "negative", line[5:]
        elif len(line) >= 2 and line[0] == line[-1] == '"': polarity, line = "quoted", line[1:-1]
        role_match = re.match(r"\[([a-z][a-z0-9_]*)\]\s+", line)
        if role_match:
            role, line = role_match.group(1), line[role_match.end():]
        # These are complete bounded omission records, not fact assertions.
        if line.rstrip(".").endswith(" is an option"):
            continue
        if re.fullmatch(r"I (?:recommend|select) [^;?\n]+\.?", line):
            continue
        if line.rstrip(".").casefold() in known_entities:
            continue
        if line.endswith(" —"): line += " "
        if " — " in line:
            entity, body = line.split(" — ", 1)
        else:
            # The sole nondelimited assertion form anchors a known field phrase.
            match = re.fullmatch(r"(.+?)\s+(?:has|is)\s+((?:not\s+)?(?:rating|rated|score|total cost|total|cost|price|amount|spending|paid|flight number|flight_number|flight|number)\b.*)", line, re.I)
            if not match:
                unsupported = True
                continue
            entity, body = match.groups()
        if not entity or entity != entity.strip() or any(c in entity for c in ['"', "'", "`", ";", "?", ">"]):
            unsupported = True
            continue
        if not body.strip(): continue
        for piece in body.split(","):
            parsed = False
            piece = piece.strip().rstrip(".")
            leading_negative = piece.startswith("not ")
            if leading_negative: piece = piece[4:]
            for field, alias in ALIASES.items():
                token = r"[A-Za-z]+\d+" if field == "flight_number" else NUMBER
                pattern = alias + r"\s*(?:(?:is|of|equals|:|=|at)\s*)?(?P<negative>not\s+)?(?P<value>" + token + r")\s*" + QUALIFIER
                match = re.fullmatch(pattern, piece, re.I)
                if match:
                    value = match.group("value") if field == "flight_number" else Decimal(match.group("value"))
                    current_polarity = "negative" if polarity != "quoted" and (leading_negative or match.group("negative")) else polarity
                    duration = match.group("duration")
                    period = match.group("period")
                    temporal = None
                    if duration:
                        n = int(duration)
                        temporal = {(7, "days"): "seven_day_rental", (3, "days"): "three_day_rental_per_car", (4, "days"): "four_day_rental", (2, "people"): "two_person_flight"}.get((n, "days" if period.lower().startswith("day") else "people"), "incompatible_explicit_time")
                    unit = match.group("unit")
                    dimension = None if unit is None else "rating_points" if unit.lower() == "points" else "money"
                    facts.append({"entity": entity, "property": field, "value": value, "polarity": current_polarity,
                                  "role": role, "dimension": dimension, "temporal_scope": temporal})
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
    def conflicts(f):
        required_dimension = "money" if obligation["unit"] in ["money_amount", "money_total"] else obligation["unit"]
        return (f["polarity"] == "negative" or not equal(f["value"], expected) or
                f["role"] is not None and f["role"] != role or
                f["dimension"] is not None and f["dimension"] != required_dimension or
                f["temporal_scope"] is not None and f["temporal_scope"] != obligation["temporal_scope"])
    if any(f["polarity"] != "quoted" and conflicts(f) for f in target_facts): return "fail"
    # Recognized context or quotes cannot suppress a correct bound assertion.
    if any(f["polarity"] == "positive" and not conflicts(f) for f in target_facts): return "pass"
    if unsupported or not completed: return "unknown"
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
