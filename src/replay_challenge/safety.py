"""Policy-neutral safety contract tests, not a candidate gate implementation."""

from __future__ import annotations

import random
from pathlib import Path

from .world import write_json


def check(gate, seed=2026):
    rng = random.Random(seed)
    results = []
    # No company field names, thresholds, workflow fixes or private policies.
    patterns = [
        [(False, True), (True, False), (False, True)],
        [(False, True), (True, True)],
        [(True, True), (False, False)],
        [(True, False), (True, True)],
        [(False, False), (False, True), (True, False), (False, True)],
    ]
    for index, pattern in enumerate(patterns):
        parent = "parent-" + str(rng.getrandbits(64))
        proposed = "candidate-" + str(rng.getrandbits(64))
        rows = [
            {
                "scenario_id": "case-" + str(rng.getrandbits(64)),
                "seed": rng.randrange(100000),
                "parent_success": old,
                "candidate_success": new,
            }
            for old, new in pattern
        ]
        rng.shuffle(rows)
        actual = gate(parent_version=parent, candidate_version=proposed, outcomes=rows)
        improved = [
            [r["scenario_id"], r["seed"]]
            for r in rows
            if not r["parent_success"] and r["candidate_success"]
        ]
        regressed = [
            [r["scenario_id"], r["seed"]]
            for r in rows
            if r["parent_success"] and not r["candidate_success"]
        ]
        expected = "promote" if improved and not regressed else "reject"
        valid = (
            actual.get("decision") == expected
            and actual.get("active_version")
            == (proposed if expected == "promote" else parent)
            and sorted(actual.get("improvements", [])) == sorted(improved)
            and sorted(actual.get("regressions", [])) == sorted(regressed)
        )
        results.append({"case": index, "passed": valid, "expected_decision": expected})
    return {
        "passed": all(r["passed"] for r in results),
        "cases": results,
        "scope": "promotion gate only; company learning evaluated separately",
    }


def run(gate, output: Path):
    if output.exists():
        raise ValueError("use a new safety output directory")
    result = check(gate)
    write_json(output / "safety.json", result)
    return result
