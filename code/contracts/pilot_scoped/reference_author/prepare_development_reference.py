"""Versioned references on exposed R20 development observations; no new cases.

Payload/native receipt bytes stay identical. R20 reference decisions are read
only after R21 source decisions are assigned, solely to report policy changes.
"""
import hashlib
import json
from collections import Counter
from pathlib import Path

from author_common_scopes import BASE, HERE
from source_reference import evaluate


def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    old = BASE / "e2/reference_author"
    cases = [json.loads(line) for line in (old / "development_cases_portable.jsonl").read_text().splitlines()]
    common = {s["task_key"]: s for s in json.loads((HERE / "common_scopes.json").read_text())["tasks"]}
    for folder in ["inputs", "native_raw", "private_reference"]: (HERE / folder).mkdir(exist_ok=True)
    new_cases, references, bytes_verified = [], [], []
    for case in cases:
        cid, key = case["case_id"], case["task_key"]
        original_input = old / case["input_file"]
        target_input = HERE / "inputs" / original_input.name
        target_input.write_bytes(original_input.read_bytes())
        observed = json.loads(target_input.read_text())
        raw_relative = Path(observed["native_realization_receipt"]["native_raw_file"])
        original_raw = BASE / raw_relative
        target_raw = HERE / "native_raw" / original_raw.name
        target_raw.write_bytes(original_raw.read_bytes())
        assert digest(target_input) == digest(original_input) == case["input_sha256"]
        assert digest(target_raw) == digest(original_raw) == observed["native_realization_receipt"]["native_raw_sha256"]
        bytes_verified.extend([target_input, target_raw])
        scope = common[key]
        row = {**case, "historical_r20_scope_id": case["scope_id"], "scope_id": scope["scope_id"],
               "scope_sha256": scope["scope_sha256"], "source_packet_sha256": scope["source_packet_sha256"],
               "input_file": str(target_input.relative_to(HERE)),
               "designation": "exposed inherited development diagnostic, not R21 confirmation"}
        result = evaluate(key, observed)
        ref = {"case_id": cid, "task_key": key, "phase": "development", "mechanism": case["mechanism"],
               "input_sha256": case["input_sha256"], **result,
               "reference_evidence": [{"reason": "Independent source-only per-obligation decision under versioned R21 direct-observation policy",
                    "source_packet_sha256": scope["source_packet_sha256"], "scope_sha256": scope["scope_sha256"]}]}
        new_cases.append(row)
        references.append(ref)
    old_refs = {r["case_id"]: r for r in [json.loads(line) for line in (old / "private_reference/development_reference_v2.jsonl").read_text().splitlines()]}
    transitions = [{"case_id": r["case_id"], "r20_status": old_refs[r["case_id"]]["reference_status"],
                   "r21_status": r["reference_status"], "reason": "Observed empty answer now proves missing affirmative fact; unavailable answer remains unknown"}
                  for r in references if r["reference_status"] != old_refs[r["case_id"]]["reference_status"]]
    (HERE / "development_cases_portable.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in new_cases))
    (HERE / "private_reference/development_reference_v1.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in references))
    policy = {"designation": "versioned exposed development diagnostic; not confirmation or competitive construction",
              "cases": len(references), "observation_and_native_bytes_unchanged": True,
              "r20_labels_unchanged": True, "counts": dict(Counter(r["reference_status"] for r in references)),
              "changed_decisions": transitions, "confirmation_cases_generated": 0}
    (HERE / "development_policy_transitions.json").write_text(json.dumps(policy, indent=2) + "\n")
    freeze_files = bytes_verified + [HERE / "development_cases_portable.jsonl", HERE / "private_reference/development_reference_v1.jsonl",
                                    HERE / "development_policy_transitions.json", HERE / "source_reference.py"]
    (HERE / "development_case_freeze.json").write_text(json.dumps({"stage": "exposed development references, separate from future confirmation",
        "files": {str(p.relative_to(HERE)): digest(p) for p in freeze_files}, "cases": 204,
        "source_only_assigned_before_r20_label_comparison": True, "confirmation_cases": 0}, indent=2) + "\n")
    print(json.dumps({"cases": len(references), "counts": policy["counts"], "policy_transitions": transitions}))


if __name__ == "__main__": main()
