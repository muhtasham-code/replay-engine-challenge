# Baseline and learning proof

The original `core` pack remains a keyless installation and native ARE Email/Calendar check. Its previous proof is retained in `results/reference-proof.json`; it is not the substantive assignment.

The substantive v3 baseline is an immutable minimal workflow: bind the observed discount, create an offer, send it, await acceptance and report. It has no supplied approval conversation, restriction rule or commercial-adjustment skill.

`challenge_data/learning/` contains ten executed synthetic histories and one transparent public demonstration world. Histories contain partial observations and actual baseline events, not complete company snapshots. Run:

```bash
uv run python -m replay_challenge.workflow check --output artifacts/learning-check
```

This replays the public baseline through the broker and checks recorded events and outcomes.

## Verified learning, not policy memorization

The candidate must build a real model-driven controller. `results/model-driven-proof.json` reports fresh provider calls, complete model-generated workflows, deterministic execution and independent judging. Its live-model coverage is the public demo, one changed-policy corpus and a no-change control. The private reference uses sanitized histories, current replay results and the public workflow protocol; it does not call the deterministic policy inducer or a prewritten workflow-fix library. Protocol mechanics, reconstruction and the promotion gate remain deterministic. A separate revision control starts from an actual unsuccessful model-generated proposal, not a deliberately corrupted patch.

`results/learning-proof.json` records a separate deterministic infrastructure-control learner subprocess solving:

- The public demonstration.
- Three held-out corpora with different approval fields, numerical boundaries/comparators, exception features, restrictions and commercial caps.
- A no-change corpus containing unsupported feedback.

Each learning corpus verifies discovery, executable workflow proposals and three cumulative improvements. Both a safe-first learner with no rejected proposals and a learner that rejects and revises a regressing proposal are independently checked. Neither path is required to fabricate a failure. The learned public workflow applied unchanged fails on hidden policies; relearning from each new corpus passes.

The judge independently re-executes complete traces under the private policies. A separate policy-neutral promotion-gate test verifies regression rejection, no-gain rejection and active-parent retention without forcing a rejection into successful learning. Negative controls test forced promotion, fabricated traces, unsupported evidence and dropped parent lineage. Reference source, private policies and generated workflows remain undistributed.

The deterministic proof is bounded synthetic keyless induction, not live-model capability or an eligible candidate submission. The live-model proof is bounded synthetic execution, not production traces, a learned director or commercial parity. The broker protocol separates candidate inputs from policy definitions; production grading must additionally isolate candidate and grader environments.
