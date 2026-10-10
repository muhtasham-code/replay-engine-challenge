# Setup and expected behavior

Prerequisites: Git, Python 3.12 or newer, and uv. Install uv using the official guide linked in the README. Run commands from the repository root; `uv sync --locked` installs the pinned project and test dependencies. If a compatible Python is missing, `uv python install 3.13` installs one. First-time dependency installation needs internet access. The checks themselves need no provider credentials, Docker or external API.

## Before implementation

The README's setup commands must pass. `prepare` reports three core traces, `check` reports passed, and the core smoke reports one intentional baseline failure and two successes. The learning check reports ten executed cases, five successes and five intentional baseline failures. The test suite passes even though the candidate functions are empty.

Edit `src/replay_challenge/candidate.py`. Until you implement `run_improvement_loop` and `decide_promotion`, the corresponding `run` and `safety-check` commands intentionally raise `NotImplementedError`. Do not try to fix this by modifying the baseline or evaluator.

## Two terminals

Start the broker as shown in the README. It prints `ready: true` with manifest and corpus paths and keeps running. Leave that terminal open; use another terminal for candidate runs. Stop the broker with Ctrl+C. Restarting it rewrites its ephemeral endpoint/token, so reload the manifest for each run. A connection-refused error normally means the broker stopped or your process cached an old manifest.

## Outputs

Use a new output directory for each check or run; existing artifact folders are intentionally refused. If a broker output has stale corpus files, start it with a fresh output path and pass the corresponding corpus/manifest paths to `run`. No cleanup command or broad directory deletion is required.

After implementation, run the main loop, the trusted local judge, and `safety-check`. Both judges should report `passed: true`. The safety report is separate from the learning report. An all-safe learning run is valid with zero rejections or revisions. Artifact examples document shapes only and will not pass a judge without real evidence and executed results.

## Model authentication is separate

The main learning command requires a real model provider or authenticated coding-agent harness chosen by you. Setup, baseline replay, tests and `safety-check` do not. Document a small provider smoke command, required environment variable names or harness login, and call/cost limits. `.env.example` illustrates optional gateway names, not a supplied gateway implementation. Keep credentials outside artifacts and Git. Missing model credentials must not break the keyless checks.
