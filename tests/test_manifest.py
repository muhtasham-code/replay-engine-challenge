import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).parents[1]


def test_core_manifest_matches_documented_contract():
    manifest = json.loads((ROOT / "challenge_data/core/manifest.json").read_text())
    schema = json.loads((ROOT / "challenge_data/scenario-set.schema.json").read_text())
    Draft202012Validator(schema).validate(manifest)
    assert len(manifest["scenarios"]) == 3
    assert len(manifest["evidence_pack"]["files"]) == 3
    assert {row["outcome"] for row in manifest["evidence_pack"]["files"]} == {"failure", "success"}
    assert manifest["evidence_pack"]["kind"] == "executed_synthetic_controller_runs"
    assert all("oracle" not in row for row in manifest["scenarios"])
