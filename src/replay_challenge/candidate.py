from __future__ import annotations

from pathlib import Path


def decide_promotion(
    *, parent_version: str, candidate_version: str, outcomes: list[dict]
) -> dict:
    """Implement the gate used by your loop and the separate safety check.

    Each outcome has scenario_id, seed, parent_success and candidate_success.
    Return decision, active_version, improvements and regressions. See docs.
    """
    raise NotImplementedError("candidate promotion gate required")


def run_improvement_loop(
    *,
    corpus_dir: Path,
    scenario_manifest: Path,
    output_dir: Path,
    seeds: tuple[int, ...],
) -> int:
    """Implement real model-driven discovery, proposals and conditional revision.

    Keep replay and promotion safety deterministic; persist linked model evidence.
    """
    del corpus_dir, scenario_manifest, output_dir, seeds
    raise NotImplementedError(
        "candidate learner required: discover, reconstruct, replay, generate workflows, reject, revise, and promote"
    )
