import hashlib
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("judge_evaluate", ROOT / "judge" / "evaluate.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)
ZERO = json.loads((ROOT / "challenge_data/baseline.json").read_text())["parent_version"].removeprefix("sha256:")


def _canonical_digest(value: object) -> str:
    payload = (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()
    return hashlib.sha256(payload).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _complete_artifacts(tmp_path: Path, seeds: tuple[int, ...] = (7, 19, 41)) -> Path:
    manifest = tmp_path / "scenarios.json"
    _write_json(manifest, {"scenarios": [{"id": "hidden-a"}]})
    diff = "+ policy\n"
    artifact_hash = hashlib.sha256(diff.encode()).hexdigest()
    parent_version = f"sha256:{ZERO}"
    candidate_version = "sha256:" + _canonical_digest(
        {"artifact_hash": artifact_hash, "kind": "memory", "parent_version": parent_version}
    )
    _write_json(
        tmp_path / "run.json",
        {
            "run_id": "run-a",
            "selected_issue_id": "issue-a",
            "parent_version": parent_version,
            "candidate_version": candidate_version,
            "inputs": {"corpus": "/input/corpus", "scenario_manifest": "/input/scenarios.json", "seeds": list(seeds)},
            "started_at": "2026-01-01T00:00:00Z",
            "completed_at": "2026-01-01T00:01:00Z",
        },
    )
    _write_json(
        tmp_path / "issues.json",
        {
            "ranked_candidates": [
                {"id": "issue-a", "rank": 1, "summary": "Primary", "evidence": [{"trace_id": "trace-a", "locator": "conversation/2", "observation": "Failure"}]},
                {"id": "issue-b", "rank": 2, "summary": "Secondary", "evidence": [{"trace_id": "trace-b", "locator": "conversation/4", "observation": "Weakness"}]},
            ]
        },
    )
    _write_json(
        tmp_path / "replay-case.json",
        {
            "issue_id": "issue-a",
            "scenario_id": "hidden-a",
            "source_state_hash": ZERO,
            "observed_evidence": [{"trace_id": "trace-a", "locator": "conversation/2"}],
            "assumptions": ["The world can expose the same failure mode."],
            "unknowns": ["The original historical database is unavailable."],
            "failure_mode": "The agent acts on an unsupported assumption.",
            "failure_predicate": "The baseline mutates state before resolving the ambiguity.",
        },
    )
    _write_json(
        tmp_path / "change.json",
        {
            "kind": "memory",
            "summary": "Remember the policy",
            "parent_version": parent_version,
            "candidate_version": candidate_version,
            "artifact_hash": artifact_hash,
            "evidence": ["trace-a"],
            "diff": diff,
        },
    )
    rows = []
    model = {"provider": "test", "name": "fixed"}
    budgets = {"turns": 20, "tokens": 1000}
    evaluator = {"name": "state-check", "version": "1"}
    for seed in seeds:
        initial_state = {"scenario": "hidden-a", "seed": seed, "records": []}
        initial_hash = _canonical_digest(initial_state)
        outcomes = {}
        for side, score, success, version in (
            ("baseline", 0.0, False, parent_version),
            ("candidate", 1.0, True, candidate_version),
        ):
            final_state = {**initial_state, "result": side}
            events = [
                {"sequence": 0, "logical_time": 0, "kind": "agent_action", "payload": {"side": side}, "provenance": ["trace-a"]},
                {"sequence": 1, "logical_time": 1, "kind": "evaluation", "payload": {"score": score}, "provenance": ["state-check"]},
            ]
            trace = {
                "scenario_id": "hidden-a",
                "seed": seed,
                "side": side,
                "harness_version": version,
                "model": model,
                "budgets": budgets,
                "evaluator": evaluator,
                "initial_state": initial_state,
                "final_state": final_state,
                "score": score,
                "success": success,
                "events": events,
            }
            trace_ref = f"traces/hidden-a-{seed}-{side}.json"
            _write_json(tmp_path / trace_ref, trace)
            outcomes[side] = {
                "score": score,
                "success": success,
                "trace_ref": trace_ref,
                "initial_state_hash": initial_hash,
                "final_state_hash": _canonical_digest(final_state),
                "ordered_event_hash": _canonical_digest(events),
            }
        rows.append(
            {
                "scenario_id": "hidden-a",
                "seed": seed,
                "initial_state_hash": initial_hash,
                "baseline": outcomes["baseline"],
                "candidate": outcomes["candidate"],
                "severity": "none",
            }
        )
    _write_json(tmp_path / "matrix.json", {"results": rows})
    _write_json(
        tmp_path / "decision.json",
        {
            "decision": "promote",
            "summary": "All seeded comparisons improved without regressions.",
            "policy": {"minimum_candidate_score": 0.8, "maximum_allowed_regression": 0.0, "block_on_high_severity_regression": True},
            "evidence": ["matrix.json"],
        },
    )
    (tmp_path / "blast-radius.md").write_text("# Blast radius\n\n## hidden-a\n\n" + "Candidate improved from 0 to 1 with equivalent initial state and seed. " * 4, encoding="utf-8")
    return manifest


def test_judge_accepts_complete_cross_product(tmp_path: Path) -> None:
    manifest = _complete_artifacts(tmp_path)
    result = MODULE.evaluate(tmp_path, manifest, (7, 19, 41))
    assert result["passed"] is True, result["errors"]
    assert result["trace_count"] == 6


def test_judge_rejects_evaluator_seed_substitution(tmp_path: Path) -> None:
    manifest = _complete_artifacts(tmp_path, (101, 102, 103))
    result = MODULE.evaluate(tmp_path, manifest, (7, 19, 41))
    assert result["passed"] is False
    assert any("requested seeds" in error for error in result["errors"])


def test_judge_rejects_missing_seed_coverage(tmp_path: Path) -> None:
    manifest = _complete_artifacts(tmp_path)
    matrix = json.loads((tmp_path / "matrix.json").read_text(encoding="utf-8"))
    matrix["results"].pop()
    _write_json(tmp_path / "matrix.json", matrix)
    result = MODULE.evaluate(tmp_path, manifest, (7, 19, 41))
    assert result["passed"] is False
    assert any("missing pairs" in error for error in result["errors"])


def test_judge_rejects_fabricated_trace_hash(tmp_path: Path) -> None:
    manifest = _complete_artifacts(tmp_path)
    matrix = json.loads((tmp_path / "matrix.json").read_text(encoding="utf-8"))
    matrix["results"][0]["baseline"]["ordered_event_hash"] = "1" * 64
    _write_json(tmp_path / "matrix.json", matrix)
    result = MODULE.evaluate(tmp_path, manifest, (7, 19, 41))
    assert result["passed"] is False
    assert any("ordered event hash mismatch" in error for error in result["errors"])


def test_judge_rejects_unbound_candidate_version(tmp_path: Path) -> None:
    manifest = _complete_artifacts(tmp_path)
    change = json.loads((tmp_path / "change.json").read_text(encoding="utf-8"))
    change["candidate_version"] = "sha256:" + "1" * 64
    _write_json(tmp_path / "change.json", change)
    run = json.loads((tmp_path / "run.json").read_text(encoding="utf-8"))
    run["candidate_version"] = change["candidate_version"]
    _write_json(tmp_path / "run.json", run)
    result = MODULE.evaluate(tmp_path, manifest, (7, 19, 41))
    assert result["passed"] is False
    assert any("content address" in error for error in result["errors"])


def test_judge_rejects_trace_path_traversal(tmp_path: Path) -> None:
    manifest = _complete_artifacts(tmp_path)
    matrix = json.loads((tmp_path / "matrix.json").read_text(encoding="utf-8"))
    matrix["results"][0]["baseline"]["trace_ref"] = "traces/../../outside.json"
    _write_json(tmp_path / "matrix.json", matrix)
    result = MODULE.evaluate(tmp_path, manifest, (7, 19, 41))
    assert result["passed"] is False
    assert any("artifact schema" in error or "escapes" in error for error in result["errors"])


def test_judge_rejects_different_baseline_and_candidate_configs(tmp_path: Path) -> None:
    manifest = _complete_artifacts(tmp_path)
    trace_path = tmp_path / "traces" / "hidden-a-7-candidate.json"
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    trace["budgets"] = {"turns": 200, "tokens": 10000}
    _write_json(trace_path, trace)
    result = MODULE.evaluate(tmp_path, manifest, (7, 19, 41))
    assert result["passed"] is False
    assert any("model, budgets, or evaluator differ" in error for error in result["errors"])


def test_judge_blocks_unsafe_promotion(tmp_path: Path) -> None:
    manifest = _complete_artifacts(tmp_path)
    matrix = json.loads((tmp_path / "matrix.json").read_text(encoding="utf-8"))
    row = matrix["results"][0]
    row["baseline"]["score"] = 1.0
    row["candidate"]["score"] = 0.0
    row["severity"] = "critical"
    trace_path = tmp_path / row["candidate"]["trace_ref"]
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    trace["score"] = 0.0
    trace["events"][-1]["payload"]["score"] = 0.0
    row["candidate"]["ordered_event_hash"] = _canonical_digest(trace["events"])
    _write_json(trace_path, trace)
    _write_json(tmp_path / "matrix.json", matrix)
    result = MODULE.evaluate(tmp_path, manifest, (7, 19, 41))
    assert result["passed"] is False
    assert any("promotion violates policy" in error for error in result["errors"])
