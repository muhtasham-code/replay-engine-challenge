"""Summarize executed private reference artifacts without publishing the solution."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

from replay_challenge.world import ROOT, baseline_version, digest, write_json


def judge(output, manifest, seeds):
    spec = importlib.util.spec_from_file_location("trusted_judge", ROOT / "judge/evaluate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.evaluate(output, manifest, seeds)
    if not result["passed"]:
        raise ValueError(result["errors"])
    return result


def summary(output):
    matrix = json.loads((output / "matrix.json").read_text())["results"]
    rows = []
    for identity in sorted({row["scenario_id"] for row in matrix}):
        cases = [row for row in matrix if row["scenario_id"] == identity]
        rows.append({"scenario_id": identity, "seeds": [row["seed"] for row in cases],
                     "baseline_successes": sum(row["baseline"]["success"] for row in cases),
                     "candidate_successes": sum(row["candidate"]["success"] for row in cases),
                     "regression_severities": [row["severity"] for row in cases]})
    return {"scenarios": rows, "decision": json.loads((output / "decision.json").read_text())["decision"],
            "aggregate": {"baseline_successes": sum(row["baseline"]["success"] for row in matrix),
                          "candidate_successes": sum(row["candidate"]["success"] for row in matrix), "total": len(matrix)},
            "trace_sha256": {str(path.relative_to(output)): hashlib.sha256(path.read_bytes()).hexdigest()
                             for path in sorted((output / "traces").glob("*.json"))}}


def main(positive, negative, repeats):
    seeds = (7,19,41)
    positive_manifest = ROOT / "challenge_data/core/manifest.json"
    negative_manifest = negative.parent / "inputs/manifest.json"
    positive_judge = judge(positive, positive_manifest, seeds)
    negative_judge = judge(negative, negative_manifest, seeds)
    assert json.loads((positive / "decision.json").read_text())["decision"] == "promote"
    assert json.loads((negative / "decision.json").read_text())["decision"] == "reject"
    repeated = [repeats / "repeat-a", repeats / "repeat-b"]
    for output, manifest in zip(repeated, (positive_manifest, repeats / "reordered-inputs/manifest.json")):
        judge(output, manifest, seeds)
    traces_a = summary(repeated[0])["trace_sha256"]
    traces_b = summary(repeated[1])["trace_sha256"]
    assert traces_a == traces_b
    attacks = json.loads((ROOT / "artifacts/attack-results.json").read_text())
    assert all(not result["passed"] for result in attacks.values())
    proof = {"schema_version": 1, "verified_at": "2026-10-10", "runtime": "Meta ARE 1.2.0 native Email/Calendar",
             "provider": "none", "mode": "synthetic frozen controller plus private evidence-driven reference loop",
             "baseline_version": baseline_version(),
             "source_manifest_sha256": hashlib.sha256(positive_manifest.read_bytes()).hexdigest(),
             "runtime_sha256": hashlib.sha256((ROOT / "src/replay_challenge/world.py").read_bytes()).hexdigest(),
             "positive": {**summary(positive), "independent_judge": positive_judge},
             "negative": {**summary(negative), "independent_judge": negative_judge},
             "repeatability": {"separate_processes": True, "reversed_scenario_order": True,
                               "identical_trace_digests": True, "compared_traces": len(traces_a)},
             "negative_verification": {"forced_unsafe_promotion_rejected": True,
                                       "rehashing_fabricated_state_rejected": True},
             "limitations": ["Not a live-model evaluation", "Not production evidence", "Not a commercial-product parity claim",
                             "Candidate solution remains unimplemented; reference source and full outputs withheld"]}
    write_json(ROOT / "results/reference-proof.json", proof)
    print(json.dumps({"positive": proof["positive"]["aggregate"], "negative": proof["negative"]["aggregate"],
                      "negative_decision": proof["negative"]["decision"], "repeatability": proof["repeatability"]}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--positive", type=Path, required=True)
    parser.add_argument("--negative", type=Path, required=True)
    parser.add_argument("--repeats", type=Path, required=True)
    args = parser.parse_args()
    main(args.positive, args.negative, args.repeats)
