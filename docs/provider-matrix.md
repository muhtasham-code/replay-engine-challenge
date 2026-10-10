# Execution status

- Native ARE setup kernel: executed and independently verified, keyless.
- Public v3 baseline: executed synthetic histories and keyless broker check.
- Private reference learner: executed unchanged across public and three different hidden-policy corpora; rejection, revision and cumulative workflow promotion verified.
- Safe-first reference path: executed on public and all changed-policy corpora; zero rejections/revisions accepted.
- Separate safety gate: negative controls executed independently of the learning run, including aggregate-gain regression and always-promote rejection.
- No-change control: executed; misleading feedback did not cause promotion.
- Public-solution overfitting control: executed; the unchanged public workflow fails on hidden policies.
- Trusted judge: independently executes declared workflows and compares actual state, events and outcomes.
- Live-model private controller: fresh calls evaluated on public, one changed-policy corpus and no-change evidence; exact model, costs, decisions and independent replay results in `results/model-driven-proof.json`.
- Candidate learner: intentionally unimplemented and unscored; a deterministic-only learner is not eligible.
- Learned director: not evaluated; the supplied action-dependent director is deterministic.

`results/model-driven-proof.json` is the live-model proof. `results/learning-proof.json` is the separate deterministic control, and `results/reference-proof.json` covers only the original setup kernel. Full reference artifacts and private policy definitions remain private. No production or commercial-parity claim is made.
