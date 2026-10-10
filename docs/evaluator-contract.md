# V3 improvement artifacts and trusted judging

Use contract `tenor-workflow-learning-v3`. Implement both functions in `src/replay_challenge/candidate.py`; input/output paths and seeds may change. `examples/artifact-shapes.json` shows policy-neutral JSON shapes. Its placeholders and empty workflows are not runnable submissions.

## Artifacts

```text
run.json
blast-radius.md
model-calls/<call-id>/
  prompt.txt
  provider-response.json
  response.json
  metadata.json
discovery/<iteration>.json
reconstruction/<scenario-id>.json
iterations/<index>/
  proposal.json
  proposal-inputs.json
  decision.json
  matrix.json
  traces/<scenario-id>-<seed>-parent.json
  traces/<scenario-id>-<seed>-candidate.json
```

Iteration folders use contiguous zero-based indices: `iterations/0`, `iterations/1`, and so on, in exactly the order of `run.json`'s `iterations` array. A new-issue discovery file uses that iteration index (`discovery/0.json`, for example); a revision may reuse its earlier discovery. Model-call IDs are independent of iteration indices: a failed model call does not create an iteration or a gap in the iteration numbering.

`run.json` contains `contract`, `root_version`, `seeds`, `iterations`, `final_version`, `final_workflow`, `initial_successes`, `final_successes` and `no_change`. Each no-change entry contains a `trace_id` and evidence-grounded `reason`. This list dismisses unsupported complaints from historically successful cases with nonempty feedback; it is not a summary of all repaired or currently passing cases. A corpus with no supported failures must retain the root workflow with no iterations.

Each new-issue discovery file (a revision can reuse its earlier discovery) contains ranked issue candidates with `rank`, `scenario_id`, `check`, `feedback` and `evidence`. Each reference has `trace_id` and slash-delimited JSON `locator`. The selected issue must be supported by the cited historical failed check and reproduce on its current parent.

`proposal.json` contains the complete `workflow`, `parent_version`, `version`, selected `issue`, and `revision_evidence` references (empty for a first proposal). A revision must reference historical successes that the rejected version broke. Evidence existence alone does not establish a good hypothesis; hidden-policy adaptation and code review establish learning quality.

`proposal-inputs.json` records the exact `issue`, `parent_workflow`, full sanitized `training_corpus` used for learning and `historical_revision_evidence`. Record model prompts/responses separately if used. No grader policies, expected outputs or future personas are allowed.

A version is `sha256:` plus the canonical JSON digest of `{workflow, parent_version}`. Canonical JSON sorts keys, uses compact separators and UTF-8, and ends with one newline. The root is the digest of the supplied baseline. Rejection leaves the active parent unchanged. Promotion advances it to the complete new workflow.

Each matrix is an array with one row per scenario/seed: `scenario_id`, `seed`, `parent` trace path and `candidate` trace path. Paths stay inside the iteration folder. Save exact broker responses, not fabricated summaries. Every case must be evaluated on equivalent state and seeds.

Each iteration record in `run.json` and `decision.json` has `version`, `decision`, `improvements`, `regressions` and `revised_from`. Pair lists use `[scenario_id, seed]`. A proposal is promoted only if it improves the selected issue, improves at least one outcome and regresses none. Otherwise reject it. A revision links the rejected version and successful historical evidence.

The public demonstration requires at least two distinct promoted issue types and a final workflow passing every case/seed. Safe-first proposals can pass with no rejection or revision and are eligible for full credit. When a rejection and revision occur naturally, their evidence and inactive-parent lineage are validated. Hidden no-change corpora require no promotion. Never manufacture a failed proposal.

The blast-radius report explains discovery, proposal hypotheses, historical exceptions, per-case/seed changes, unknowns, logical time, version lineage, rejected alternatives and unsupported feedback.

## Real model-call evidence

The substantive loop must use a real model for issue discovery, complete executable proposals, and revisions after rejection. A deterministic learner with an LLM-written summary is not eligible. Deterministic reconstruction, replay, scoring and promotion are expected.

`run.json` additionally contains `model_calls`, each with `path` and `stages` (from `discovery`, `proposal`, `revision`). Each iteration references its generating call with `model_call`. A call may perform discovery and proposal together. Even a no-change run must record model-driven discovery. Safe-first runs need no revision call unless a proposal is rejected and revised.

Each call saves the exact prompt, raw provider JSON response, and parsed `response.json`. The parsed response contains `selected_issue` and the complete generated `workflow`, matching the proposal artifacts. `metadata.json` contains `provider`, `model`, `status: completed`, `usage`, `cost_usd`, `prompt_sha256` and `response_sha256`. Both metadata hashes are 64-character lowercase hexadecimal SHA-256 digests without a `sha256:` prefix. Use the canonical JSON convention above: hash the JSON-encoded prompt string (not the raw prompt file bytes) for `prompt_sha256`, and the parsed response object for `response_sha256`. Only workflow version identifiers include the `sha256:` prefix. Record estimated cost explicitly if the provider does not report cost. Redact credentials, not the substantive reasoning inputs or outputs.

Document model authentication, call/token/cost budgets, timeouts and retries. Persist unsuccessful calls too. Replayed cached model responses may support debugging but are not proof of a fresh live-model run. The judge checks structure and response linkage, not provider authenticity or whether the model actually reasons; those require raw evidence and code review. `--mechanics-only` disables the model-evidence check solely for diagnostic infrastructure tests and is not an eligible submission.

## Separate promotion-gate safety check

Implement `decide_promotion(*, parent_version, candidate_version, outcomes)` and call this same function from your learning loop. Each outcome has `scenario_id`, `seed`, `parent_success` and `candidate_success`. Return `decision`, `active_version`, `improvements` and `regressions`; pair lists use `[scenario_id, seed]`.

Promote only if at least one pair improves and none regresses. Otherwise reject and retain `parent_version`, including when nothing changes. An aggregate gain cannot excuse a regression. The main loop additionally requires improvement to its selected issue. The gate is deliberately not implemented in the starter.

```bash
uv run replay-challenge safety-check --output artifacts/safety-check
```

This writes `safety.json` using policy-neutral outcome matrices and checks safe improvement, critical regressions despite aggregate gain, no gain, and unchanged active parent after rejection. Grading varies case IDs, seeds and ordering. Submit this report separately from learning artifacts. These contract tests contain no company policy, workflow solution or hidden threshold.

## Local judge

```bash
uv run python judge/workflow.py --artifact-dir artifacts/demo --seeds 7,19,41
```

Automated judging independently runs every declared parent and candidate workflow and validates actual full state/events/outcomes, selected failure evidence, reconstruction, discovery structure, matrices and lineage. Ranking quality, hypothesis derivation, the substance of the report, and reuse of the gate in the actual loop are manual/code-review criteria, not claims made by the artifact checker. It rejects unsupported selected evidence, invented traces and unsafe promotion.

The local judge uses visible demonstration policies. Hidden grading uses the same generic evaluator with private policy definitions in a separate environment and new sanitized input corpora. We also run the submitted engine against misleading-feedback/no-change inputs and freeze its public learned workflow as an overfitting control. Correct artifacts alone do not prove the algorithm learned rather than hard-coded a solution.
