# AI Challenge: Build a Self Improving Agent System

AI that owns real outcomes must improve its own harness without sacrificing previously correct behavior. Build a system that discovers failures from company evidence, reconstructs and replays them, generates executable workflow changes, finds regressions, revises its changes and promotes only what the measurements support.

A static report, hand-written policy, deterministic policy inducer, or wrapper around known fixes is not a solution. Build a model-driven agentic learning controller, not only a rules engine.

## What we supply

Use the [starter repository](https://github.com/muhtasham-code/replay-engine-challenge). It supplies stateful tools backed by Meta ARE, an action-dependent simulated director, one virtual clock, a deliberately imperfect baseline workflow and ten executed synthetic company histories with partial CRM, billing, usage and email evidence.

We supply infrastructure, not the learning engine. The baseline does not implement approval conversations, outreach restrictions or commercial corrections for you. Your generated workflow must add the actions, branching, variable changes and waiting behavior the evidence calls for. There are no issue-specific fix flags or two-effect memory interface.

This is a bounded engineering exercise, not a requirement to build enterprise connectors, OAuth, a UI or a commercial simulator. No production data or credentials are required.

## Which harness are you improving?

There are two separate systems: **your learning controller**, which discovers and tests improvements, and **the company agent being improved**, which executes work in the supplied world.

Choose your own model provider, agent framework and controller architecture. You may organize your implementation in new modules or another language behind the supplied CLI adapter. The two functions in `candidate.py` are entrypoints, not a complete architecture you must follow. Using an existing agent framework is welcome, but its orchestration alone is not the solution.

The improvement target is fixed: the supplied company agent's baseline workflow. In this exercise, a harness version is a complete, content-addressed workflow in the documented `steps` format, including its parent version. Your controller must generate, replay and promote changed workflows. It may use prompts, skills or memory internally, but those must lead to an executed workflow improvement. The grader does not run arbitrary framework internals or unrestricted generated code. You are not being asked to modify Claude Code, Codex or an unrelated agent, or replace the benchmark with your own easier task.

You build the substantive logic: evidence-driven discovery and ranking, model context and hypothesis generation, executable proposals, regression reasoning, conditional revision, cumulative version management and no-change judgment. We supply no learning controller, proposal prompts, policy inducer, fix templates or reference solution. Reusing simulation, replay and validation primitives is expected; calling them without building this learning logic is insufficient.

## Setup

You need Git, Python 3.12 or newer, and [uv](https://docs.astral.sh/uv/getting-started/installation/). Run commands from the repository root. The clean-checkout checks were verified with Python 3.13 on macOS; no Windows-specific implementation is required.

```bash
git clone https://github.com/muhtasham-code/replay-engine-challenge.git
cd replay-engine-challenge
uv sync --locked
uv run replay-challenge prepare
uv run replay-challenge check
uv run replay-challenge smoke --output artifacts/setup-check
uv run python -m replay_challenge.workflow check --output artifacts/learning-check
```

Expected results: both setup checks report success; the learning check reports ten executed cases, five baseline successes and five baseline failures. Those baseline failures are intentional. No model key, Docker daemon or external service is needed. The checks do not solve the assignment.

For the substantive loop, keep this local replay broker running in one terminal:

```bash
uv run python -m replay_challenge.workflow serve --output .cache/learning
```

In another terminal, implement `run_improvement_loop` and `decide_promotion` in `src/replay_challenge/candidate.py`, then run the learning entrypoint:

```bash
uv run replay-challenge run \
  --corpus .cache/learning/corpus \
  --scenarios .cache/learning/manifest.json \
  --output artifacts/demo \
  --seeds 7,19,41
```

Before implementing the two functions, `run` and `safety-check` intentionally raise `NotImplementedError`; this is not a broken setup. Use a fresh output directory for each run. The broker manifest is valid only while its server is running. See `docs/workflow-contract.md` for the supported tools, workflow instructions and replay client, and `docs/evaluator-contract.md` for artifacts and local judging.

## Build the learning engine

One command must do the following without human editing between stages:

1. **Discover:** search histories, feedback, failed outcome checks and environmental signals. Rank supported issues with precise evidence. Feedback is not automatically correct; identify unsupported complaints too.
2. **Reconstruct and replay:** recover the relevant state from partial evidence, preserving identity, temporal boundaries, lineage and unknowns. Reproduce the selected failure on the current active parent.
3. **Propose:** generate an executable workflow change from that evidence. It may add a skill, conditional tool sequence, approval conversation, commercial adjustment or stopping behavior. Persist the complete immutable version and its actual proposal inputs.
4. **Measure the blast radius:** compare parent and candidate across all supplied cases and seeds on equivalent starting state. Search historical successes for implicit behavior the new workflow could break.
5. **Handle unsafe proposals:** if a proposal regresses, reject it and derive any revision from the historical behavior it broke. Safe-first proposals are welcome; do not deliberately propose a worse version to manufacture a rejection.
6. **Promote and compound:** promote only measured improvements without regressions. Solve further distinct issues while preserving prior gains. Rejected versions must never become active parents.
7. **Know when not to change:** misleading feedback or a corpus without supported failures must not cause an unnecessary promotion.

The public demonstration must include at least two distinct compounding improvements, with its final workflow passing every supplied case and seed. Zero rejections or revisions is valid and eligible for full credit when your first proposals are safe. A no-change corpus must retain the baseline and explain why.

Test your promotion gate separately:

```bash
uv run replay-challenge safety-check --output artifacts/safety-check
```

This policy-neutral negative-control test checks a regressing proposal even when its aggregate improves, a safe improvement, no improvement, and retention of the active parent after rejection. Use the same `decide_promotion` function in your learning loop. See `docs/evaluator-contract.md` and `examples/artifact-shapes.json`; the examples contain placeholders, not learned fixes.

## Generalization is the central test

The public demo's policy is visible for local debugging. Copying it into your engine does not satisfy the assignment.

During grading, the same submitted engine receives new sanitized evidence and a replay broker for worlds with different approval fields, numerical boundaries, inclusive or exclusive comparisons, historical exceptions, outreach restrictions and commercial terms. These are policy changes, not merely renamed accounts.

You must infer the new behavior from feedback, observations and historical decisions without modifying your engine. The private grading predicates, future persona definitions and expected outputs are unavailable to candidate inputs. They stay in the trusted grader environment. Use only the supplied corpus, public manifest and outcome-only replay API; no evaluator imports, filesystem inspection or policy extraction.

The replay budget is 1,000 executions per grading corpus, including all scenario/seed comparisons. Document hypothesis selection and evidence use. Exhaustively probing the scorer, hard-coded visible policies and scenario-ID dispatch are not learning.

## Simulation and safety

The world must react to actual actions, not play a fixed transcript. New messages, recipients, amounts, waits and state mutations must have consistent consequences. Tools and people share one logical clock; skip idle days without sleeping. Fixed seeds and equivalent recorded inputs reproduce simulation behavior, not fresh model sampling.

Keep observed facts, simulated facts and inferred decisions distinct. Missing or contradictory facts must remain unknown. The trusted temporal merger is a validation primitive; you must produce candidate reconstruction artifacts. Do not copy a final snapshot into the starting state.

Evaluate complete traces and actual final state. A critical regression blocks promotion even when the aggregate improves. Preserve cumulative version lineage and record why each rejection, revision and promotion occurred.

The substantive learning loop must call a real language model to discover and rank issues, generate executable proposals, and revise rejected proposals when needed. The model must reason from the supplied evidence and measured replay results; using it only to narrate deterministic fixes does not count. Safe-first solutions remain eligible without a forced revision.

Keep reconstruction mechanics, replay, clocks, outcome evaluation and the promotion gate deterministic. Setup and `safety-check` remain keyless. The full learning run requires your chosen model provider or authenticated coding-agent harness; document authentication, model, call limits, timeout/retry behavior and estimated cost without committing credentials. Record exact prompts, raw provider responses, parsed proposals, usage and reported cost, and link each proposal/revision to its model call. See the artifact contract for the required layout.

## Evaluation

- Evidence-driven discovery, proposals and hypothesis refinement: 30%
- Adaptation to previously unseen policy semantics: 25%
- Regression discovery, no-change judgment and blast radius: 20%
- Safe promotion and compounding version lineage: 15%
- Reconstruction, tests and reproducible developer experience: 10%

Automated checks validate artifact structure, model-response linkage, selected failure evidence, executed state/outcomes, version lineage, hidden-policy adaptation and the separate safety gate. Provider-call authenticity, model reasoning, ranking quality, report substance and whether the loop actually uses that gate are reviewed manually. We may ask you to explain a hidden-case adaptation. The starter contains no reference learner or hidden policy definitions.

## Submission

Submit a private GitHub repository and invite `muhtasham@heytenor.com` with review access. Deliver:

- Your implemented agentic learning system, with one command driving discovery through measured promotion without human-authored fixes between stages.
- A demonstration of at least two distinct compounding improvements, and a separate deterministic promotion-safety report. Safe-first solutions need not manufacture a rejection.
- Evidence-linked issues, reconstruction artifacts, linked real model calls, immutable workflow versions, full replay traces and before/after matrices, promotion decisions and a blast-radius report.
- Exact setup, model-authentication, demonstration and safety commands; tests, architecture, limitations and hours spent. The unchanged engine must also work with new supplied evidence and policies, not only the public demo.

Attach your coding-agent transcript so we can understand how you worked with AI. Export with `/export` in Claude Code or Pi, use the Codex CLI session transcript, or provide an equivalent export from your coding-agent harness. Redact credentials and sensitive information.
