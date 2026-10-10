# Self Improving Agent System

Build the autonomous learning engine described in [AI-CHALLENGE.md](AI-CHALLENGE.md).

The starter supplies stateful ARE tools, a logical clock, a replay broker, a generic executable-workflow interpreter and baseline evidence. It does **not** supply discovery, induction, proposal generation, regression selection or revision logic. The substantive controller must use a real language model for discovery, executable proposals and any required revision; a fully deterministic learner is not an eligible submission.

## Your controller versus the target harness

Choose any model provider, agent framework or architecture for **your learning controller**. Keep the supplied CLI entrypoints, using an adapter if your implementation lives in another language or modules. You must build discovery, hypothesis generation, executable proposals, regression reasoning, revision and compounding logic yourself.

The **target agent** is not arbitrary: it is the supplied company baseline. Its harness versions are complete, content-addressed workflows in the documented `steps` format. Your controller generates and improves these executable versions; the supplied interpreter merely runs them. Internal prompt, skill or memory changes must produce measured workflow changes. This is not a task to patch Claude Code/Codex, provide a report, replace the benchmark or connect prewritten fixes. See the challenge's harness and submission sections for scope and deliverables.

[Starter boundary](docs/starter-boundary.md) identifies supplied mechanics, candidate-owned logic, setup-only legacy files and withheld solutions.

## Keyless setup

Prerequisites: Git, Python 3.12+, and [uv](https://docs.astral.sh/uv/getting-started/installation/). Run from the repository root. Python 3.13 on macOS was verified; no model key, Docker or external service is needed.

```bash
uv sync --locked
uv run replay-challenge prepare
uv run replay-challenge check
uv run replay-challenge smoke --output artifacts/setup-check
uv run python -m replay_challenge.workflow check --output artifacts/learning-check
uv run pytest -q
```

Expected: setup checks pass; the learning check reproduces ten cases with five successes and five intentional baseline failures. See [setup troubleshooting](docs/setup.md).

The small Email/Calendar `core` pack only checks installation. The substantive contract is `tenor-workflow-learning-v3`. The earlier narrow two-effect company exercise has been removed.

## Candidate run

Keep the public demo broker running in one terminal:

```bash
uv run python -m replay_challenge.workflow serve --output .cache/learning
```

Implement `run_improvement_loop` and `decide_promotion` in `src/replay_challenge/candidate.py`, then use a second terminal:

```bash
uv run replay-challenge run --corpus .cache/learning/corpus --scenarios .cache/learning/manifest.json --output artifacts/demo --seeds 7,19,41
uv run python judge/workflow.py --artifact-dir artifacts/demo
uv run replay-challenge safety-check --output artifacts/safety-check
```

A fresh clone intentionally raises `NotImplementedError` on `run` and `safety-check` until you implement the two functions. Setup/baseline checks already work. Safe-first learning runs can pass with zero rejections or revisions; do not manufacture a bad proposal. Rejection safety is tested separately using the same gate your loop calls.

[Artifact shape examples](examples/artifact-shapes.json) contain placeholders only, not learned rules or a completed submission.

Only the full learning run needs model authentication. Choose a provider SDK, model gateway or authenticated coding-agent harness, document its setup and budgets, and never commit credentials. Replay, evaluation and safety gates stay deterministic. Persist linked model-call evidence as specified in the artifact contract; the default judge requires it. `--mechanics-only` is a diagnostic mode, not a valid submission.

See [workflow contract](docs/workflow-contract.md) and [artifact contract](docs/evaluator-contract.md). Public demo definitions are intentionally inspectable for debugging. Hidden policy definitions remain in a separate trusted grader; the engine receives only sanitized evidence and outcome-only replay access.

## Verified solvability, not a distributed solution

[results/model-driven-proof.json](results/model-driven-proof.json) records fresh real-model discovery, executable proposals and measured promotion through the private controller on public and changed-policy evidence, plus a no-change control. It records the precise model coverage and limitations, not a claim that every model will succeed.

[results/learning-proof.json](results/learning-proof.json) is the separate deterministic infrastructure/generalization control across three hidden policy suites and both safe-first and rejection/revision paths. It does not qualify as an agentic candidate submission. The separate gate checks also reject an always-promote negative control. Applying the public learned workflow unchanged fails on hidden policies. The private controllers, policies, raw model responses and generated solutions are withheld.

These are executed synthetic engineering tests, not production data, learned-director quality, live-model intelligence or commercial parity. [BASELINE.md](BASELINE.md) explains the evidence boundary.

Submit a private GitHub repo, invite `muhtasham@heytenor.com` and GitHub users `xmgad` and `luaiabuelsamen` with review access, and attach run artifacts, hours spent and your coding-agent transcript.
