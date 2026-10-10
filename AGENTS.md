# AGENTS.md

- Do not commit `.env`, credentials, generated corpus files, raw run outputs, reference solutions, or hidden evaluation material. The immutable core fixtures are intentionally checked in.
- Treat source traces, initial snapshots, and dataset manifests as immutable inputs.
- Keep baseline and candidate runs isolated by scenario, seed, and harness version.
- Do not include oracle agent events, hidden scenario identifiers, expected decisions, or answer keys in agent prompts.
- Do not claim a model, provider, scenario, or change was evaluated unless its saved artifacts exist.
- Before committing, run the unit tests, keyless smoke test, leakage scan, secret scan, and `git diff --check`.
