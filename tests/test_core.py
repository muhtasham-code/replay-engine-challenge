import copy
import json
from pathlib import Path

import pytest

from replay_challenge.core import prepare, check
from replay_challenge.world import World, execute, load_spec, verify_trace

ROOT = Path(__file__).parents[1]
MANIFEST = ROOT / "challenge_data/core/manifest.json"


def cases():
    manifest = json.loads(MANIFEST.read_text())
    return [load_spec(MANIFEST, row) for row in manifest["scenarios"]]


def test_pack_reproduces_executed_baseline(tmp_path):
    assert prepare(MANIFEST, tmp_path)["baseline_executions_reverified"]
    assert check(MANIFEST, tmp_path)["status"] == "passed"


@pytest.mark.parametrize("seed", [7, 19, 41, 2, 3, 101])
def test_baseline_failure_and_historical_successes(seed):
    for spec in cases():
        before = execute(spec, seed)
        assert before["success"] == (spec["id"] != "pending-followup")
        verify_trace(spec, before)


def test_unsafe_change_has_critical_regression():
    spec = next(spec for spec in cases() if not spec["response_plan"])
    assert execute(spec, 7)["success"]
    unsafe = execute(spec, 7, {"suppress_unresolved_summary": True})
    assert not unsafe["success"]
    assert not unsafe["checks"]["correct_summary"]


def test_action_replay_detects_fabricated_state_and_score():
    spec = cases()[0]
    run = execute(spec, 7)
    fake = copy.deepcopy(run)
    fake["score"] = 1
    with pytest.raises(ValueError, match="independent"):
        verify_trace(spec, fake)
    fake = copy.deepcopy(run)
    fake["final_state"]["apps"]["Calendar"]["events"] = {}
    with pytest.raises(ValueError, match="independent"):
        verify_trace(spec, fake)


def test_isolation_scenario_order_and_clock():
    specs = cases()
    forward = {spec["id"]: execute(spec, 19) for spec in specs}
    backward = {spec["id"]: execute(spec, 19) for spec in reversed(specs)}
    assert forward == backward
    world = World(specs[0], 7)
    assert world.pending == []
    world.act("wait", {})  # Waiting without requesting must NOT create replies.
    assert world.replies() == []
    assert world.now == world.deadline
    assert world.mail.time_manager.time() == world.calendar.time_manager.time() == world.clock.time()
    world.act("request", {})
    assert world.replies() == []  # A late request must not deliver past-dated replies.
    assert all(event["due"] > world.deadline for event in world.pending)


def test_unseen_identity_and_timeout_branch():
    spec = copy.deepcopy(cases()[2])
    spec["id"] = "renamed-evaluation-case"
    spec["account"] = "Different account"
    result = execute(spec, 41)
    assert result["success"]
    assert result["final_state"]["logical_time"] == 60


def test_simultaneous_events_have_stable_order():
    spec = copy.deepcopy(cases()[0])
    spec["response_plan"][1]["after"] = 5
    first = execute(spec, 19)
    assert first == execute(spec, 19)
