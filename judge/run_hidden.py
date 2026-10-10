from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import shutil
from pathlib import Path
from typing import Any

from evaluate import JSON_FILES, evaluate


def _without_nondeterminism(value: Any) -> Any:
    if isinstance(value, dict):
        ignored = {"run_id", "started_at", "completed_at", "wall_clock_time", "wall_clock_ms", "latency_ms"}
        normalized = {
            key: _without_nondeterminism(item)
            for key, item in value.items()
            if key not in ignored
        }
        inputs = normalized.get("inputs")
        if isinstance(inputs, dict):
            for key in ("corpus", "scenario_manifest"):
                if key in inputs:
                    inputs[key] = f"<{key}>"
        return normalized
    if isinstance(value, list):
        return [_without_nondeterminism(item) for item in value]
    return value


def _material_result(output: Path) -> dict[str, Any]:
    traces = {
        str(path.relative_to(output)): _without_nondeterminism(json.loads(path.read_text(encoding="utf-8")))
        for path in sorted((output / "traces").glob("**/*.json"))
    }
    return {
        name: _without_nondeterminism(json.loads((output / name).read_text(encoding="utf-8")))
        for name in JSON_FILES
    } | {
        "blast-radius.md": (output / "blast-radius.md").read_text(encoding="utf-8"),
        "traces": traces,
    }


def _run(command: list[str], submission: Path, timeout: int) -> None:
    subprocess.run(command, cwd=submission, timeout=timeout, check=True)


def _parse_seeds(value: str) -> tuple[int, ...]:
    seeds = tuple(int(part) for part in value.split(",") if part)
    if len(seeds) < 3 or len(seeds) != len(set(seeds)):
        raise argparse.ArgumentTypeError("provide at least three distinct comma-separated seeds")
    return seeds


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--submission", type=Path, required=True)
    parser.add_argument("--command", default="uv run replay-challenge run")
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--seeds", type=_parse_seeds, default=(7, 19, 41))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=3600)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    args.output.mkdir(parents=True, exist_ok=False)
    relocated_inputs = args.output / "reordered-inputs"
    shutil.copytree(args.manifest.parent, relocated_inputs)
    reversed_manifest = relocated_inputs / args.manifest.name
    reversed_payload = {**manifest, "scenarios": list(reversed(manifest["scenarios"]))}
    reversed_manifest.write_text(json.dumps(reversed_payload, indent=2) + "\n", encoding="utf-8")
    seeds = ",".join(str(seed) for seed in args.seeds)
    outputs = (args.output / "repeat-a", args.output / "repeat-b")
    manifests = (args.manifest, reversed_manifest)
    for output, manifest_path in zip(outputs, manifests, strict=True):
        command = shlex.split(args.command) + [
            "--corpus", str(args.corpus.resolve()),
            "--scenarios", str(manifest_path.resolve()),
            "--seeds", seeds,
            "--output", str(output.resolve()),
        ]
        _run(command, args.submission, args.timeout)
    first = evaluate(outputs[0], manifests[0], args.seeds)
    second = evaluate(outputs[1], manifests[1], args.seeds)
    errors = [*first.get("errors", []), *second.get("errors", [])]
    # Fresh LLM proposals need not be byte-identical. Test simulator isolation
    # on equivalent inputs, not sampling determinism of an unrelated live model.
    def keyed_traces(output):
        result = {}
        for path in (output / "traces").glob("**/*.json"):
            trace = _without_nondeterminism(json.loads(path.read_text()))
            result[(trace["scenario_id"], trace["seed"], trace["side"])] = trace
        return result
    left, right = keyed_traces(outputs[0]), keyed_traces(outputs[1])
    comparisons = 0
    for key in left.keys() & right.keys():
        a, b = left[key], right[key]
        if a["harness_version"] != b["harness_version"]:
            continue
        if a.get("model") != b.get("model"):
            continue
        keyless = a.get("model", {}).get("provider") == "none"
        cassette = a.get("model_response_cassette_hash")
        if keyless or (cassette and cassette == b.get("model_response_cassette_hash")):
            comparisons += 1
            if a != b:
                errors.append(f"equivalent recorded-input simulator replay changed for {key}")
    result = {
        "passed": first.get("passed", False) and second.get("passed", False) and not errors,
        "errors": errors,
        "scenarios": first.get("scenarios", []),
        "repeats": 2,
        "scenario_order_reversed": True,
        "equivalent_input_trace_comparisons": comparisons,
        "live_model_sampling_compared": False,
    }
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
