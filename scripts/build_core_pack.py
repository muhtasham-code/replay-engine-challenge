"""Maintainer-only fixture builder. Runs the frozen controller, never oracle actions.

Regenerating fixtures changes their hashes. Candidates should not run this to
rewrite evidence. Native ARE state and full controller actions are recorded.
"""
import hashlib
import json
from pathlib import Path

from replay_challenge.world import ROOT, canonical, digest, execute, write_json


def main():
    baseline = {"schema_version": 1, "components": [
        {"path": path, "sha256": hashlib.sha256((ROOT / path).read_bytes()).hexdigest()}
        for path in ("baseline/controller.py", "baseline/system-prompt.md")
    ]}
    baseline["parent_version"] = "sha256:" + digest(baseline["components"])
    baseline["invariants"] = {"candidate_may_change_baseline_files": False,
                              "same_starting_state": True, "same_seed": True}
    write_json(ROOT / "challenge_data/baseline.json", baseline)
    data = ROOT / "challenge_data/core"
    write_json(data / "baseline.json", baseline)
    manifest = {"schema_version": 1, "contract": "tenor-ARE-core-v1",
                "runtime": {"name": "Meta Agents Research Environments", "version": "1.2.0"},
                "scenarios": [], "evidence_pack": {"kind": "executed_synthetic_controller_runs",
                    "license": "MIT", "is_production_data": False, "files": []}}
    choices = [{"status": "confirmed", "slot": "2026-10-13 14:00:00"},
               {"status": "confirmed", "slot": "2026-10-14 10:00:00"},
               {"status": "cancelled", "slot": None}]
    for identity, plan in (
        ("pending-followup", [{"after": 5, "reply": {"final": False, "status": "pending", "slot": "2026-10-12 09:00:00"}},
                              {"after": 20, "reply": {"final": True}}]),
        ("direct-decision", [{"after": 5, "reply": {"final": True}}]),
        ("no-response", []),
    ):
        spec = {"id": identity, "account": "Acme", "operator": "operator@example.test", "deadline": 60,
                "objective": "Ask the operator for a final review decision. Book only a confirmed slot. If cancelled, do not book. Email the owner the final outcome. If no final decision arrives by 60 seconds, email unresolved and leave the calendar unchanged.",
                "response_plan": plan, "final_choices": choices}
        path = data / "scenarios" / f"{identity}.json"
        write_json(path, spec)
        source_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest["scenarios"].append({"id": identity, "config": "core", "role": "evaluation_case",
                                      "path": f"scenarios/{identity}.json", "source_sha256": source_hash})
        run = execute(spec, 7)
        outcome = "success" if run["success"] else "failure"
        source = {**run, "trace_id": identity + "-seed7", "outcome": outcome,
                  "objective": spec["objective"], "baseline_version": baseline["parent_version"],
                  "initial_state_ref": {"source_sha256": source_hash, "seed": 7},
                  "signals": [{"source": "evaluator", "locator": "checks", "content": run["checks"]}],
                  "fixture_provenance": {"kind": "executed_synthetic_controller_run", "is_production_trace": False,
                                         "generator": "scripts/build_core_pack.py", "oracle_used": False}}
        path = data / "evidence" / f"{identity}.json"
        write_json(path, source)
        manifest["evidence_pack"]["files"].append({"id": source["trace_id"], "scenario_id": identity,
              "outcome": outcome, "path": f"evidence/{identity}.json", "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    write_json(data / "manifest.json", manifest)
    print(json.dumps({"baseline_version": baseline["parent_version"],
                      "outcomes": [(t["scenario_id"], t["outcome"]) for t in manifest["evidence_pack"]["files"]]}, indent=2))


if __name__ == "__main__":
    main()
