"""Trusted v3 judge: independently execute workflows using private policies."""

import json
from pathlib import Path

from replay_challenge.workflow import BASELINE, CONTRACT, ROOT_VERSION, execute, merge
from replay_challenge.world import digest


def validate_model_evidence(output, run):
    """Structural provenance only; provider authenticity and reasoning need review."""
    calls = run.get("model_calls", [])
    assert calls, "live-model evidence required"
    indexed = {}
    stages = set()
    for call in calls:
        folder = (output / call["path"]).resolve()
        assert folder.is_relative_to(output.resolve())
        assert call["path"] not in indexed
        prompt = (folder / "prompt.txt").read_text()
        response = json.loads((folder / "response.json").read_text())
        metadata = json.loads((folder / "metadata.json").read_text())
        assert (folder / "provider-response.json").stat().st_size > 0
        assert metadata["status"] == "completed"
        assert metadata["provider"] and metadata["model"] and metadata["usage"]
        assert metadata["cost_usd"] >= 0
        assert metadata["prompt_sha256"] == digest(prompt)
        assert metadata["response_sha256"] == digest(response)
        stages.update(call["stages"])
        indexed[call["path"]] = (call, response)
    assert "discovery" in stages, "model-driven discovery required"
    for index, record in enumerate(run["iterations"]):
        call, response = indexed[record["model_call"]]
        proposal = json.loads(
            (output / "iterations" / str(index) / "proposal.json").read_text()
        )
        assert response["workflow"] == proposal["workflow"], (
            "workflow not grounded in model response"
        )
        assert response["selected_issue"] == proposal["issue"]
        stage = "revision" if record.get("revised_from") else "proposal"
        assert stage in call["stages"], "model-driven proposal/revision required"


def evaluate(
    output: Path, worlds, histories, seeds, require_learning=True, require_agentic=False
):
    count = 0
    try:
        run = json.loads((output / "run.json").read_text())
        if require_agentic:
            validate_model_evidence(output, run)
        assert run["contract"] == CONTRACT and run["root_version"] == ROOT_VERSION
        assert run["seeds"] == list(seeds)
        parent, active = ROOT_VERSION, BASELINE
        corpus = {h["trace_id"]: h for h in histories}
        rejected = {}
        promoted_issues = set()
        revisions = 0
        for index, record in enumerate(run["iterations"]):
            folder = output / "iterations" / str(index)
            artifact = json.loads((folder / "proposal.json").read_text())
            workflow = artifact["workflow"]
            assert artifact["parent_version"] == parent
            version = "sha256:" + digest(
                {"workflow": workflow, "parent_version": parent}
            )
            assert artifact["version"] == version
            issue = artifact["issue"]
            if not record.get("revised_from"):
                ranked = json.loads(
                    (output / "discovery" / (str(index) + ".json")).read_text()
                )
                assert [item["rank"] for item in ranked] == list(
                    range(1, len(ranked) + 1)
                )
                assert issue in ranked, "selected issue absent from discovery"
            assert issue["evidence"], "no evidence"
            for ref in issue["evidence"]:
                value = corpus[ref["trace_id"]]
                for key in ref["locator"].split("/"):
                    value = value[int(key)] if isinstance(value, list) else value[key]
            assert any(
                corpus[ref["trace_id"]]["scenario_id"] == issue["scenario_id"]
                and corpus[ref["trace_id"]]["checks"].get(issue["check"]) is False
                for ref in issue["evidence"]
            ), "evidence does not support selected failure"
            inputs = json.loads((folder / "proposal-inputs.json").read_text())
            assert inputs["issue"] == issue and inputs["parent_workflow"] == active
            assert (
                inputs["historical_revision_evidence"] == artifact["revision_evidence"]
            )
            assert sorted(
                inputs["training_corpus"], key=lambda h: h["trace_id"]
            ) == sorted(histories, key=lambda h: h["trace_id"])
            assert not any(
                key in json.dumps(inputs)
                for key in (
                    '"grading"',
                    '"people"',
                    '"response_plan"',
                    '"expected_outcomes"',
                )
            )
            matrix = json.loads((folder / "matrix.json").read_text())
            pairs = {(r["scenario_id"], r["seed"]) for r in matrix}
            assert len(matrix) == len(pairs) and pairs == {
                (i, s) for i in worlds for s in seeds
            }
            improvements, regressions = [], []
            selected_failed = False
            for row in matrix:
                identity, seed = row["scenario_id"], row["seed"]
                spec = worlds[identity]
                reconstruction = json.loads(
                    (output / "reconstruction" / (identity + ".json")).read_text()
                )
                assert reconstruction == merge(
                    spec["observations"], spec["task"]["account_ref"], spec["fields"]
                )
                results = []
                for side, code, harness in (
                    ("parent", active, parent),
                    ("candidate", workflow, version),
                ):
                    result = execute(spec, seed, code, reconstruction, harness)
                    path = (folder / row[side]).resolve()
                    assert path.is_relative_to(folder.resolve())
                    assert json.loads(path.read_text()) == result, "invented trace"
                    results.append(result)
                    count += 1
                assert digest(results[0]["initial_state"]) == digest(
                    results[1]["initial_state"]
                )
                old, new = results
                if (
                    identity == issue["scenario_id"]
                    and not old["checks"][issue["check"]]
                ):
                    selected_failed = True
                if new["score"] > old["score"]:
                    improvements.append([identity, seed])
                if new["score"] < old["score"]:
                    regressions.append([identity, seed])
            assert selected_failed, "selected issue did not reproduce"
            decision = "promote" if improvements and not regressions else "reject"
            assert json.loads((folder / "decision.json").read_text()) == record
            assert (
                record["decision"] == decision and record["regressions"] == regressions
            )
            assert (
                record["improvements"] == improvements and record["version"] == version
            )
            if decision == "reject":
                rejected[version] = regressions
            else:
                assert any(pair[0] == issue["scenario_id"] for pair in improvements)
                if record.get("revised_from"):
                    assert record["revised_from"] in rejected
                    assert artifact.get("revision_evidence")
                    for ref in artifact["revision_evidence"]:
                        assert corpus[ref["trace_id"]]["outcome"] == "success"
                    historical_cases = {
                        corpus[ref["trace_id"]]["scenario_id"]
                        for ref in artifact["revision_evidence"]
                    }
                    assert {
                        pair[0] for pair in rejected[record["revised_from"]]
                    } <= historical_cases
                    revisions += 1
                promoted_issues.add(issue["check"])
                active, parent = workflow, version
        assert run["final_version"] == parent and run["final_workflow"] == active
        final = [
            execute(
                w,
                s,
                active,
                merge(w["observations"], w["task"]["account_ref"], w["fields"]),
                parent,
            )
            for w in worlds.values()
            for s in seeds
        ]
        assert all(t["success"] for t in final), "final workflow fails private policy"
        assert run["final_successes"] == len(final)
        if require_learning:
            assert len(promoted_issues) >= 2, (
                "two distinct compounding improvements required"
            )
        else:
            assert not run["iterations"] and parent == ROOT_VERSION, (
                "unnecessary change"
            )
        flagged = [
            h["trace_id"]
            for h in histories
            if h.get("feedback") and h["outcome"] == "success"
        ]
        dismissed = {r["trace_id"] for r in run["no_change"] if r["reason"]}
        assert set(flagged) <= dismissed, "misleading feedback not accounted for"
        assert dismissed <= set(flagged), (
            "no-change claim lacks supporting successful history"
        )
        assert (output / "blast-radius.md").stat().st_size > 200
        return {
            "passed": True,
            "independent_traces": count,
            "final_pairs": len(final),
            "promoted_issue_types": len(promoted_issues),
            "revisions": revisions,
            "rejections": len(rejected),
            "no_change": len(dismissed),
        }
    except (AssertionError, KeyError, ValueError, OSError, TypeError) as error:
        return {"passed": False, "error": str(error)}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument(
        "--worlds",
        type=Path,
        default=Path("challenge_data/learning/public-demo-worlds.json"),
    )
    parser.add_argument(
        "--histories", type=Path, default=Path("challenge_data/learning/histories.json")
    )
    parser.add_argument("--seeds", default="7,19,41")
    parser.add_argument("--no-change", action="store_true")
    parser.add_argument(
        "--mechanics-only",
        action="store_true",
        help="diagnostic only; not an eligible agentic submission",
    )
    args = parser.parse_args()
    result = evaluate(
        args.artifact_dir,
        json.loads(args.worlds.read_text()),
        json.loads(args.histories.read_text()),
        tuple(map(int, args.seeds.split(","))),
        not args.no_change,
        not args.mechanics_only,
    )
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] else 1)
