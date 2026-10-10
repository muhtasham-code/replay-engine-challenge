from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .world import baseline_version, execute, load_spec, verify_trace, write_json


def prepare(manifest_path: Path, cache: Path):
    manifest = json.loads(manifest_path.read_text())
    baseline_version()
    scenarios = {row["id"]: load_spec(manifest_path, row) for row in manifest["scenarios"]}
    normalized = cache / "corpus/normalized"
    normalized.mkdir(parents=True, exist_ok=True)
    # Reject stale evidence instead of silently mixing old and new releases.
    wanted = {row["id"] + ".json" for row in manifest["evidence_pack"]["files"]}
    for stale in normalized.glob("*.json"):
        if stale.name not in wanted:
            stale.unlink()
    for row in manifest["evidence_pack"]["files"]:
        path = (manifest_path.parent / row["path"]).resolve()
        if not path.is_relative_to(manifest_path.parent.resolve()):
            raise ValueError("evidence path escapes manifest")
        payload = path.read_bytes()
        if hashlib.sha256(payload).hexdigest() != row["sha256"]:
            raise ValueError("evidence checksum mismatch")
        source = json.loads(payload)
        if source["baseline_version"] != baseline_version():
            raise ValueError("evidence is not from the pinned baseline")
        run = {key: source[key] for key in execute(scenarios[row["scenario_id"]], source["seed"])}
        verify_trace(scenarios[row["scenario_id"]], run)
        write_json(normalized / (row["id"] + ".json"), source)
    return {"scenarios": len(scenarios), "traces": len(wanted), "baseline_executions_reverified": True}


def check(manifest_path, cache):
    manifest = json.loads(manifest_path.read_text())
    for row in manifest["evidence_pack"]["files"]:
        payload = (cache / "corpus/normalized" / (row["id"] + ".json")).read_bytes()
        if hashlib.sha256(payload).hexdigest() != row["sha256"]:
            raise ValueError("normalized evidence changed")
    for row in manifest["scenarios"]:
        load_spec(manifest_path, row)
    baseline_version()
    return {"status": "passed", "contract": manifest["contract"]}


def smoke(manifest_path, output):
    manifest = json.loads(manifest_path.read_text())
    output.mkdir(parents=True, exist_ok=False)
    results = []
    for row in manifest["scenarios"]:
        spec = load_spec(manifest_path, row)
        run = execute(spec, 7)
        verify_trace(spec, run)
        write_json(output / (row["id"] + ".json"), run)
        results.append({"scenario": row["id"], "score": run["score"], "checks": run["checks"]})
    if not any(row["score"] == 0 for row in results) or not any(row["score"] == 1 for row in results):
        raise ValueError("baseline proof must contain failure and historically correct behavior")
    return {"status": "passed", "proof": "executed frozen baseline, not oracle", "results": results}
