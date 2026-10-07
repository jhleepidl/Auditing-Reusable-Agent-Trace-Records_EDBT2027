"""Source->typed IR compiler sanity; explicitly oracle-assisted, noncompetitive.

Resolved source facts come only from immutable inherited source rules. These
contracts are not model constructions and must never become a builder arm.
No executor, candidate, prediction or utility implementation is imported.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCOPES = json.loads((HERE / "common_scopes.json").read_text())["tasks"]
SOURCE = {s["task_key"]: s for s in json.loads((HERE / "source_snapshot/r20_source_obligations.json").read_text())}


def source_paths(key):
    if key.startswith("banking/"):
        suffix = int(key.rsplit("_", 1)[1])
        if suffix == 0: return ["/filesystem/files/bill-december-2023.txt"]
        if suffix in [2, 12]: return ["/filesystem/files/landlord-notices.txt", "/bank_account/scheduled_transactions"]
        if suffix == 13: return ["/filesystem/files/address-change.txt"]
        if suffix == 15: return ["/user_account", "/bank_account/scheduled_transactions", "/bank_account/transactions"]
        return ["/bank_account/transactions"]
    if key.startswith("slack/"): return ["/slack", "/web/web_content"]
    return ["/car_rental/company_list", "/flights/flight_list"] if key.endswith("_16") else \
           ["/hotels/hotel_list"] if key.endswith("_0") else ["/car_rental/company_list"]


def schema_paths(key, obligation):
    suite = key.split("/")[0]
    kind = obligation["condition_kind"]
    if kind in ["new_payment", "new_schedule", "scheduled_update"]:
        model, fields = "Transaction", [p["property"] for p in obligation["required_properties"]]
    elif kind == "account_fields": model, fields = "UserAccount", ["street", "city"]
    elif kind in ["user_presence", "memberships"]: model, fields = "Slack", ["users", "user_channels"]
    elif kind == "new_messages": model, fields = "Message", ["sender", "recipient", "body"]
    elif kind == "reservation": model, fields = "Reservation", [p["property"] for p in obligation["required_properties"]]
    elif suite == "banking": model, fields = "Transaction", ["amount", "date", "subject"]
    elif obligation["binding_role"] == "paris_london_flight": model, fields = "Flight", ["flight_number", "price"]
    else: model, fields = "CarRentalCompany", ["name", "rating", "price_per_day", "city", "car_types_available", "fuel_options"]
    return [f"/$defs/{model}/properties/{field}" for field in fields]


def compile_scope(scope):
    key = scope["task_key"]
    clauses = []
    roles = list(dict.fromkeys(o["binding_role"] for o in scope["obligations"] if o["kind"] == "query"))
    for obligation in scope["obligations"]:
        clause = {"obligation_id": obligation["obligation_id"], "kind": obligation["kind"], "state": None, "query": None,
                  "support": {"request_quote": scope["task_request"], "initial_state_paths": source_paths(key),
                              "schema_paths": schema_paths(key, obligation), "reason": obligation["description"]}}
        if obligation["kind"] == "query":
            record = SOURCE[key]["rules"][0]["records"][roles.index(obligation["binding_role"])]
            entity = obligation.get("entity_binding", {}).get("entity_label", record["entity"])
            clause["query"] = {"entity": entity, "property": obligation["property"],
                "value": record["facts"][obligation["property"]], "unit": obligation["unit"],
                "temporal_scope": obligation["temporal_scope"], "role": obligation["binding_role"], "polarity": "positive"}
        else:
            kind = obligation["condition_kind"]
            rule = next(r for r in SOURCE[key]["rules"] if r["kind"] == kind)
            target = obligation["target"]
            selector, fields = [], None
            path = target.get("path")
            if kind == "new_payment": fields = {"recipient": rule["recipient"], "amount": rule["amount"]}
            elif kind in ["new_schedule", "scheduled_update", "account_fields", "reservation"]: fields = rule["fields"]
            if kind == "scheduled_update": selector = [{"field": "id", "value": rule["id"]}]
            if kind == "user_presence":
                selector = [{"field": "$value", "value": rule["user"]}]
                fields = {"$value": rule["user"]}
            if kind == "memberships":
                index = int(obligation["source_member_role"].rsplit("_", 1)[1]) - 1
                member = rule["members"][index]
                checks = [{"property": "users", "operator": "member", "value": member["user"]},
                          {"property": "user_channels/" + member["user"], "operator": "member", "value": member["channel"]}]
            elif kind == "new_messages":
                index = int(obligation["source_message_role"].rsplit("_", 1)[1]) - 1
                message = rule["messages"][index]
                path = target["path_pattern"].replace("{recipient}", message["recipient"])
                fields = {"sender": "bot", "recipient": message["recipient"], "body": message["body"]}
                checks = [{"property": f, "operator": "equals", "value": value} for f, value in fields.items()]
            else:
                checks = [{"property": f, "operator": "equals", "value": value} for f, value in fields.items()]
            clause["state"] = {"path": path, "selector": selector, "checks": checks,
                               "identity_profile": target["identity_profile"], "identity_field": target["identity_field"],
                               "newness": obligation["newness"]}
        clauses.append(clause)
    return {"ir_version": "r21.1", "scope_id": scope["scope_id"],
            "classification": scope["obligations"][0]["kind"] if scope["supported"] else "unknown",
            "clauses": clauses, "unknown_reason": "" if scope["supported"] else "No common source obligation selected; full task is ungraded."}


def main():
    folder = HERE / "compiler_sanity"
    folder.mkdir(exist_ok=True)
    rows = [{"task_key": scope["task_key"], "phase": scope["phase"],
             "source_packet_sha256": scope["source_packet_sha256"], "scope_sha256": scope["scope_sha256"],
             "designation": "oracle-assisted source compiler sanity; not a competitive builder arm",
             "contract": compile_scope(scope)} for scope in SCOPES]
    (folder / "contracts.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))
    (folder / "REPORT.json").write_text(json.dumps({"designation": "oracle-assisted source compiler sanity, not model construction/competition",
        "source_only": True, "humans": 0, "tasks": 57, "supported": 27, "clauses": 43,
        "candidate_or_new_model_outputs_read": False, "confirmation_cases_generated": 0,
        "builder_prompt_input": False, "execution_status": "prepared; executor verification is separately performed by root"}, indent=2) + "\n")
    print(json.dumps({"contracts": len(rows), "clauses": sum(len(r["contract"]["clauses"]) for r in rows), "designation": "oracle-assisted sanity only"}))


if __name__ == "__main__": main()
