import copy
import importlib.util
import json
from pathlib import Path

import pytest

from replay_challenge.workflow import (
    BASELINE,
    ROOT_VERSION,
    ReplayClient,
    broker,
    check_demo,
    execute,
    materialize,
    merge,
    public_case,
)

ROOT = Path(__file__).parents[1]
WORLDS = json.loads(
    (ROOT / "challenge_data/learning/public-demo-worlds.json").read_text()
)
HISTORIES = json.loads((ROOT / "challenge_data/learning/histories.json").read_text())


def test_baseline_history_reproduces_without_key(tmp_path):
    proof = check_demo(WORLDS, HISTORIES, tmp_path / "check")
    assert proof["baseline_successes"] == 5 and proof["baseline_failures"] == 5


def test_broker_does_not_disclose_policy_or_people(tmp_path):
    with broker(WORLDS, "test-token") as (url, _):
        manifest = materialize(WORLDS, HISTORIES, tmp_path, url, "test-token")
        raw = manifest.read_text()
        assert '"grading"' not in raw and '"people"' not in raw
        client = ReplayClient(json.loads(raw))
        spec = next(iter(WORLDS.values()))
        trace = client.evaluate(
            spec["id"],
            7,
            BASELINE,
            merge(spec["observations"], spec["task"]["account_ref"], spec["fields"]),
            ROOT_VERSION,
        )
        assert '"grading"' not in json.dumps(
            trace
        ) and '"approval_limit"' not in json.dumps(trace)


def test_candidate_reconstruction_boundary():
    spec = WORLDS[
        next(h["scenario_id"] for h in HISTORIES if not h["checks"]["authorization"])
    ]
    facts = merge(spec["observations"], spec["task"]["account_ref"], spec["fields"])
    assert facts["offer.discount"]["value"] == 24
    facts["offer.discount"]["value"] = 99
    with pytest.raises(ValueError, match="reconstruction"):
        execute(spec, 7, BASELINE, facts, ROOT_VERSION)


def test_changed_policy_changes_outcome_not_tool_state():
    spec = copy.deepcopy(
        WORLDS[
            next(
                h["scenario_id"] for h in HISTORIES if not h["checks"]["authorization"]
            )
        ]
    )
    facts = merge(spec["observations"], spec["task"]["account_ref"], spec["fields"])
    original = execute(spec, 7, BASELINE, facts, ROOT_VERSION)
    spec["grading"]["approval"]["value"] = 99
    changed = execute(spec, 7, BASELINE, facts, ROOT_VERSION)
    assert original["events"] == changed["events"]
    assert (
        not original["checks"]["authorization"] and changed["checks"]["authorization"]
    )


def test_workflow_changes_actual_offer_amount():
    # Test tool semantics, not a worked policy correction or a passing solution.
    spec = next(iter(WORLDS.values()))
    code = copy.deepcopy(BASELINE)
    facts = merge(spec["observations"], spec["task"]["account_ref"], spec["fields"])
    amount = facts["offer.discount"]["value"] + 1
    code["steps"][0]["value"] = amount
    trace = execute(spec, 7, code, facts, "test")
    assert trace["final_state"]["apps"]["billing"]["offers"][0]["discount"] == amount


def test_generic_predicates_and_partial_unknowns():
    spec = copy.deepcopy(next(iter(WORLDS.values())))
    spec["observations"] = [
        r for r in spec["observations"] if r["field"] != "contract.signed"
    ]
    facts = merge(spec["observations"], spec["task"]["account_ref"], spec["fields"])
    assert facts["contract.signed"] == {
        "value": None,
        "status": "unknown",
        "evidence": [],
    }


def test_workflow_budget_and_unknown_instruction():
    spec = next(iter(WORLDS.values()))
    facts = merge(spec["observations"], spec["task"]["account_ref"], spec["fields"])
    with pytest.raises(ValueError, match="unsupported workflow"):
        execute(spec, 7, {"steps": [{"op": "named-fix"}]}, facts, "test")


def test_stable_seed_and_order():
    def run(worlds):
        return {
            i: execute(
                s,
                19,
                BASELINE,
                merge(s["observations"], s["task"]["account_ref"], s["fields"]),
                ROOT_VERSION,
            )
            for i, s in worlds.items()
        }

    assert run(WORLDS) == run(dict(reversed(list(WORLDS.items()))))
