"""Structural tests only; synthetic metadata is not live-model proof."""

import importlib.util
from pathlib import Path

import pytest

from replay_challenge.world import digest, write_json

spec = importlib.util.spec_from_file_location(
    "model_judge", Path(__file__).parents[1] / "judge/workflow.py"
)
judge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(judge)


def fixture(tmp_path):
    folder = tmp_path / "model-calls/0"
    folder.mkdir(parents=True)
    prompt = "Synthetic structural-test input, not a provider invocation."
    response = {"selected_issue": {}, "workflow": {"steps": []}}
    (folder / "prompt.txt").write_text(prompt)
    write_json(folder / "provider-response.json", {"synthetic_test": True})
    write_json(folder / "response.json", response)
    write_json(
        folder / "metadata.json",
        {
            "provider": "synthetic-test",
            "model": "test",
            "status": "completed",
            "usage": {"tokens": 1},
            "cost_usd": 0,
            "prompt_sha256": digest(prompt),
            "response_sha256": digest(response),
        },
    )
    write_json(
        tmp_path / "iterations/0/proposal.json",
        {"workflow": response["workflow"], "issue": {}},
    )
    return {
        "model_calls": [{"path": "model-calls/0", "stages": ["discovery", "proposal"]}],
        "iterations": [{"model_call": "model-calls/0"}],
    }


def test_model_evidence_required(tmp_path):
    with pytest.raises(AssertionError, match="live-model"):
        judge.validate_model_evidence(tmp_path, {"iterations": []})


def test_structural_linkage_accepts_matching_shapes(tmp_path):
    judge.validate_model_evidence(tmp_path, fixture(tmp_path))


def test_narration_cannot_replace_workflow_linkage(tmp_path):
    run = fixture(tmp_path)
    write_json(
        tmp_path / "iterations/0/proposal.json",
        {"workflow": {"steps": [{"op": "finish", "status": "test"}]}, "issue": {}},
    )
    with pytest.raises(AssertionError, match="workflow not grounded"):
        judge.validate_model_evidence(tmp_path, run)
