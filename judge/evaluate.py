from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


JSON_FILES = ("run.json", "issues.json", "replay-case.json", "change.json", "matrix.json", "decision.json")
REQUIRED_FILES = {*JSON_FILES, "blast-radius.md"}


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _schema_errors(bundle: dict[str, Any], root: Path) -> list[str]:
    schema = _load(root / "challenge_data" / "artifact.schema.json")
    validator = Draft202012Validator(schema)
    return [
        f"artifact schema: {'/'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}"
        for error in sorted(validator.iter_errors(bundle), key=lambda item: list(item.absolute_path))
    ]


def _safe_artifact_path(artifact_dir: Path, relative: str, required_parent: str | None = None) -> Path | None:
    try:
        resolved = (artifact_dir / relative).resolve(strict=False)
        base = (artifact_dir / required_parent).resolve() if required_parent else artifact_dir.resolve()
        if not resolved.is_relative_to(base):
            return None
        return resolved
    except (OSError, RuntimeError, ValueError):
        return None


def _expected_severity(baseline_score: float, candidate_score: float) -> str:
    regression = baseline_score - candidate_score
    if regression <= 0:
        return "none"
    if regression <= 0.05:
        return "low"
    if regression <= 0.15:
        return "medium"
    if regression <= 0.30:
        return "high"
    return "critical"


def _validate_trace(
    trace: dict[str, Any],
    *,
    scenario_id: str,
    seed: int,
    side: str,
    harness_version: str,
    outcome: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    for field, expected in (
        ("scenario_id", scenario_id),
        ("seed", seed),
        ("side", side),
        ("harness_version", harness_version),
        ("score", outcome.get("score")),
        ("success", outcome.get("success")),
    ):
        if trace.get(field) != expected:
            errors.append(f"trace {field} does not match matrix outcome for {scenario_id}/{seed}/{side}")

    events = trace.get("events")
    if not isinstance(events, list) or not events:
        return [*errors, f"trace has no ordered events for {scenario_id}/{seed}/{side}"]
    sequences = [event.get("sequence") for event in events if isinstance(event, dict)]
    if sequences != list(range(len(events))):
        errors.append(f"trace events are not contiguous and zero based for {scenario_id}/{seed}/{side}")
    logical_times = [event.get("logical_time") for event in events if isinstance(event, dict)]
    if len(logical_times) != len(events) or any(not isinstance(value, (int, float)) for value in logical_times):
        errors.append(f"trace logical times are invalid for {scenario_id}/{seed}/{side}")
    elif logical_times != sorted(logical_times):
        errors.append(f"trace logical times are not monotonic for {scenario_id}/{seed}/{side}")

    if _digest(trace.get("initial_state")) != outcome.get("initial_state_hash"):
        errors.append(f"initial state hash mismatch for {scenario_id}/{seed}/{side}")
    if _digest(trace.get("final_state")) != outcome.get("final_state_hash"):
        errors.append(f"final state hash mismatch for {scenario_id}/{seed}/{side}")
    if _digest(events) != outcome.get("ordered_event_hash"):
        errors.append(f"ordered event hash mismatch for {scenario_id}/{seed}/{side}")
    return errors


def evaluate(
    artifact_dir: Path,
    scenario_manifest: Path,
    expected_seeds: tuple[int, ...] | None = None,
) -> dict[str, Any]:
    missing = sorted(name for name in REQUIRED_FILES if not (artifact_dir / name).is_file())
    if not (artifact_dir / "traces").is_dir():
        missing.append("traces/")
    if missing:
        return {"passed": False, "errors": [f"missing artifact: {name}" for name in missing]}

    root = Path(__file__).parents[1]
    bundle = {
        name.removesuffix(".json").replace("-", "_"): _load(artifact_dir / name)
        for name in JSON_FILES
    }
    errors = _schema_errors(bundle, root)
    if errors:
        return {"passed": False, "errors": errors}
    run = bundle["run"]
    issues = bundle["issues"]
    replay_case = bundle["replay_case"]
    change = bundle["change"]
    matrix = bundle["matrix"]
    decision = bundle["decision"]
    manifest = _load(scenario_manifest)
    scenario_rows = manifest.get("scenarios", [])
    required_scenarios = {item["id"] for item in scenario_rows}
    if not required_scenarios:
        errors.append("scenario manifest must contain a nonempty scenarios array")
    if replay_case.get("scenario_id") not in required_scenarios:
        errors.append("replay case scenario_id is not in the supplied manifest")

    ranked = issues.get("ranked_candidates", [])
    if run.get("selected_issue_id") not in {item.get("id") for item in ranked}:
        errors.append("selected issue is not present in the ranked issue list")
    if replay_case.get("issue_id") != run.get("selected_issue_id"):
        errors.append("replay case issue_id does not match the selected issue")
    ranks = [item.get("rank") for item in ranked]
    if ranks and ranks != list(range(1, len(ranks) + 1)):
        errors.append("issue ranks must be contiguous and ordered from 1")
    if manifest.get("contract") == "tenor-ARE-core-v1":
        source_traces = {}
        from replay_challenge.world import load_spec
        for source in manifest.get("evidence_pack", {}).get("files", []):
            path = _safe_artifact_path(scenario_manifest.parent, source["path"])
            if path is None or not path.is_file():
                errors.append("trusted evidence path missing or escapes manifest")
                continue
            payload = path.read_bytes()
            if hashlib.sha256(payload).hexdigest() != source["sha256"]:
                errors.append("trusted evidence checksum mismatch")
                continue
            source_traces[source["id"]] = json.loads(payload)
        def evidence_exists(reference):
            value = source_traces.get(reference["trace_id"])
            if value is None:
                return False
            try:
                for segment in reference["locator"].strip("/").split("/"):
                    value = value[int(segment)] if isinstance(value, list) else value[segment]
                return True
            except (KeyError, ValueError, IndexError, TypeError):
                return False
        for reference in [*(ref for item in ranked for ref in item["evidence"]), *replay_case["observed_evidence"]]:
            if not evidence_exists(reference):
                errors.append("evidence reference does not resolve to a trusted trace locator")
        if not any(source_traces.get(ref["trace_id"], {}).get("scenario_id") == replay_case["scenario_id"]
                   for ref in replay_case["observed_evidence"]):
            errors.append("selected issue evidence is not linked to its replay scenario")

    if change.get("parent_version") != run.get("parent_version"):
        errors.append("change parent_version does not match run")
    if change.get("candidate_version") != run.get("candidate_version"):
        errors.append("change candidate_version does not match run")
    if run.get("parent_version") == run.get("candidate_version"):
        errors.append("parent and candidate versions must differ")
    baseline_manifest = _load(root / "challenge_data" / "baseline.json")
    if run.get("parent_version") != baseline_manifest.get("parent_version"):
        errors.append("run parent_version does not match the pinned baseline")
    for component in baseline_manifest.get("components", []):
        component_path = root / component["path"]
        digest = hashlib.sha256(component_path.read_bytes()).hexdigest()
        if digest != component.get("sha256"):
            errors.append(f"pinned baseline component hash mismatch: {component['path']}")

    declared_hook = None
    if "diff" in change:
        change_digest = hashlib.sha256(change["diff"].encode()).hexdigest()
    else:
        change_path = _safe_artifact_path(artifact_dir, change.get("artifact_path", ""))
        if change_path is None or not change_path.is_file():
            change_digest = None
            errors.append("change artifact_path must reference a file inside the artifact directory")
        else:
            change_digest = hashlib.sha256(change_path.read_bytes()).hexdigest()
    if manifest.get("contract") == "tenor-ARE-core-v1" and change["kind"] == "hook":
        try:
            if "diff" in change:
                declared_hook = json.loads(change["diff"])
            else:
                declared_hook = _load(change_path)
            if not isinstance(declared_hook, dict) or any(
                key not in {"require_final_reply", "suppress_unresolved_summary"} or type(value) is not bool
                for key, value in declared_hook.items()
            ):
                raise ValueError("unsupported declarative controller hook")
        except (ValueError, TypeError, OSError) as exc:
            errors.append(f"declared hook must be a supported JSON controller configuration: {exc}")
            declared_hook = None
    if change_digest is not None and change.get("artifact_hash") != change_digest:
        errors.append("change artifact_hash does not match the declared diff or artifact file")
    expected_version = "sha256:" + _digest(
        {
            "artifact_hash": change.get("artifact_hash"),
            "kind": change.get("kind"),
            "parent_version": change.get("parent_version"),
        }
    )
    if change.get("candidate_version") != expected_version:
        errors.append("candidate_version is not the content address of the declared change")

    submitted_seeds = tuple(run.get("inputs", {}).get("seeds", []))
    if expected_seeds is not None and submitted_seeds != expected_seeds:
        errors.append(f"run seeds do not match evaluator requested seeds: {list(expected_seeds)}")
    seeds = expected_seeds if expected_seeds is not None else submitted_seeds
    expected_pairs = {(scenario_id, seed) for scenario_id in required_scenarios for seed in seeds}
    rows = matrix.get("results", [])
    actual_pairs = [(item.get("scenario_id"), item.get("seed")) for item in rows]
    if len(actual_pairs) != len(set(actual_pairs)):
        errors.append("scenario matrix contains duplicate scenario and seed rows")
    if set(actual_pairs) != expected_pairs:
        missing_pairs = sorted(expected_pairs - set(actual_pairs))
        extra_pairs = sorted(set(actual_pairs) - expected_pairs)
        if missing_pairs:
            errors.append(f"scenario matrix is missing pairs: {missing_pairs}")
        if extra_pairs:
            errors.append(f"scenario matrix has unexpected pairs: {extra_pairs}")

    trace_refs: set[str] = set()
    trace_configs: dict[tuple[str, int, str], tuple[Any, Any, Any]] = {}
    for item in rows:
        scenario_id = item.get("scenario_id")
        seed = item.get("seed")
        baseline_score = item.get("baseline", {}).get("score")
        candidate_score = item.get("candidate", {}).get("score")
        if isinstance(baseline_score, (int, float)) and isinstance(candidate_score, (int, float)):
            expected = _expected_severity(float(baseline_score), float(candidate_score))
            if item.get("severity") != expected:
                errors.append(f"regression severity must be {expected} for {scenario_id}/{seed}")
        for side, harness_version in (("baseline", run.get("parent_version")), ("candidate", run.get("candidate_version"))):
            outcome = item.get(side, {})
            trace_ref = outcome.get("trace_ref")
            if not isinstance(trace_ref, str):
                continue
            trace_refs.add(trace_ref)
            trace_path = _safe_artifact_path(artifact_dir, trace_ref, "traces")
            if trace_path is None:
                errors.append(f"trace reference escapes traces directory: {trace_ref}")
                continue
            if not trace_path.is_file():
                errors.append(f"missing referenced trace: {trace_ref}")
                continue
            trace = _load(trace_path)
            if not isinstance(trace, dict):
                errors.append(f"trace is not an object: {trace_ref}")
                continue
            errors.extend(
                _validate_trace(
                    trace,
                    scenario_id=scenario_id,
                    seed=seed,
                    side=side,
                    harness_version=harness_version,
                    outcome=outcome,
                )
            )
            if manifest.get("contract") == "tenor-ARE-core-v1":
                from replay_challenge.world import execute, load_spec, verify_trace
                try:
                    spec_row = next(row for row in scenario_rows if row["id"] == scenario_id)
                    spec = load_spec(scenario_manifest, spec_row)
                    verify_trace(spec, trace)
                    if side == "candidate" and declared_hook is not None:
                        if execute(spec, seed, declared_hook, "candidate", harness_version) != trace:
                            raise ValueError("candidate actions do not implement the declared hook")
                except Exception as exc:
                    errors.append(f"independent ARE verification failed for {scenario_id}/{seed}/{side}: {exc}")
            trace_configs[(scenario_id, seed, side)] = (
                trace.get("model"),
                trace.get("budgets"),
                trace.get("evaluator"),
            )
            if outcome.get("initial_state_hash") != item.get("initial_state_hash"):
                errors.append(f"matrix initial state hash mismatch for {scenario_id}/{seed}/{side}")
        baseline_config = trace_configs.get((scenario_id, seed, "baseline"))
        candidate_config = trace_configs.get((scenario_id, seed, "candidate"))
        if baseline_config is not None and candidate_config is not None and baseline_config != candidate_config:
            errors.append(f"baseline and candidate model, budgets, or evaluator differ for {scenario_id}/{seed}")

    report = (artifact_dir / "blast-radius.md").read_text(encoding="utf-8")
    if len(report.strip()) < 200:
        errors.append("blast-radius.md is too short to preserve scenario-level evidence")
    for scenario_id in required_scenarios:
        if scenario_id not in report:
            errors.append(f"blast-radius.md does not mention scenario: {scenario_id}")

    policy = decision.get("policy", {})
    if manifest.get("contract") == "tenor-ARE-core-v1":
        selected_rows = [row for row in rows if row.get("scenario_id") == replay_case.get("scenario_id")]
        if not selected_rows or not any(row.get("baseline", {}).get("score") == 0 for row in selected_rows):
            errors.append("selected baseline failure did not reproduce")
        if decision.get("decision") == "promote" and not any(
            row["candidate"]["score"] > row["baseline"]["score"] for row in selected_rows
        ):
            errors.append("promotion did not improve the selected failure")
        source_row = next((row for row in scenario_rows if row["id"] == replay_case.get("scenario_id")), {})
        if replay_case.get("source_state_hash") != source_row.get("source_sha256"):
            errors.append("replay source_state_hash does not match pinned scenario")
    maximum_regression = policy.get("maximum_allowed_regression")
    minimum_score = policy.get("minimum_candidate_score")
    disqualifiers: list[str] = []
    if isinstance(maximum_regression, (int, float)):
        for item in rows:
            baseline_score = item.get("baseline", {}).get("score")
            candidate_score = item.get("candidate", {}).get("score")
            if isinstance(baseline_score, (int, float)) and isinstance(candidate_score, (int, float)):
                if baseline_score - candidate_score > maximum_regression:
                    disqualifiers.append("maximum_allowed_regression")
                    break
    if any(item.get("severity") in {"high", "critical"} for item in rows):
        disqualifiers.append("high_severity_regression")
    if isinstance(minimum_score, (int, float)) and rows:
        average = sum(item.get("candidate", {}).get("score", 0) for item in rows) / len(rows)
        if average < minimum_score:
            disqualifiers.append("minimum_candidate_score")
    if decision.get("decision") == "promote" and disqualifiers:
        errors.append(f"promotion violates policy: {', '.join(sorted(set(disqualifiers)))}")
    if decision.get("decision") == "promote" and not any(
        row.get("candidate", {}).get("score", 0) > row.get("baseline", {}).get("score", 0) for row in rows
    ):
        errors.append("promotion requires a measured improvement")

    return {
        "passed": not errors,
        "errors": errors,
        "scenarios": sorted({item.get("scenario_id") for item in rows if item.get("scenario_id")}),
        "trace_count": len(trace_refs),
    }


def _parse_seeds(value: str) -> tuple[int, ...]:
    seeds = tuple(int(part) for part in value.split(",") if part)
    if len(seeds) < 3 or len(seeds) != len(set(seeds)):
        raise argparse.ArgumentTypeError("provide at least three distinct comma-separated seeds")
    return seeds


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--scenario-manifest", type=Path, required=True)
    parser.add_argument("--seeds", type=_parse_seeds, required=True)
    args = parser.parse_args()
    result = evaluate(args.artifact_dir, args.scenario_manifest, args.seeds)
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
