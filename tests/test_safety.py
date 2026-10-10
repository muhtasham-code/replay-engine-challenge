import json
from pathlib import Path

import pytest

from replay_challenge.safety import check, run


def test_always_promote_gate_is_rejected():
    result = check(
        lambda **args: {
            "decision": "promote",
            "active_version": args["candidate_version"],
            "improvements": [
                [r["scenario_id"], r["seed"]]
                for r in args["outcomes"]
                if not r["parent_success"] and r["candidate_success"]
            ],
            "regressions": [
                [r["scenario_id"], r["seed"]]
                for r in args["outcomes"]
                if r["parent_success"] and not r["candidate_success"]
            ],
        }
    )
    assert not result["passed"] and len(result["cases"]) == 5


def test_always_reject_gate_is_not_sufficient():
    result = check(
        lambda **args: {
            "decision": "reject",
            "active_version": args["parent_version"],
            "improvements": [],
            "regressions": [],
        }
    )
    assert not result["passed"]


def test_safety_inputs_are_policy_neutral_and_order_varied():
    seen = []

    def capture(**args):
        seen.append(args)
        return {}

    check(capture, seed=91)
    assert all(
        set(r) == {"scenario_id", "seed", "parent_success", "candidate_success"}
        for request in seen
        for r in request["outcomes"]
    )
    assert len({r["scenario_id"] for request in seen for r in request["outcomes"]}) > 5


def test_safety_report_and_output_collision(tmp_path):
    folder = tmp_path / "safety"
    result = run(lambda **args: {}, folder)
    assert json.loads((folder / "safety.json").read_text()) == result
    with pytest.raises(ValueError, match="new safety"):
        run(lambda **args: {}, folder)


def test_artifact_examples_are_explicit_placeholders():
    example = json.loads(
        (Path(__file__).parents[1] / "examples/artifact-shapes.json").read_text()
    )
    assert "placeholders" in example["notice"]
    assert example["proposal.json"]["workflow"] == {"steps": []}
