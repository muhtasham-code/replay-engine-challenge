# What the starter does and does not provide

The assignment is to build the agentic learning controller, not the simulator. Using the supplied mechanics avoids spending the exercise rebuilding tools and clocks. It does not complete the learning loop.

## Supplied mechanics

- `workflow.py`: generic instruction execution, a minimal frozen baseline, temporal reconstruction validation and replay transport. It does not infer a company's policies or generate a workflow.
- `company_tools.py`: stateful tool operations and action-dependent simulated replies. Supporting an approval message is a tool capability, not logic deciding when approval is needed.
- `safety.py` and `judge/workflow.py`: test expectations and independent validation. They do not implement the candidate's promotion function or learning controller. Reading the documented safety contract is allowed; importing the trusted judge or extracting world policies into a submitted learner is not.
- `examples/artifact-shapes.json`: placeholders, not runnable improvements.
- Public histories and world definitions: a transparent debugging fixture, not hidden grading policies. The fixture builder constructs evidence; it is not a learner.

## Candidate-owned logic

Both functions in `src/replay_challenge/candidate.py` raise `NotImplementedError`. The candidate must implement evidence-driven issue discovery and ranking, model context construction, hypothesis and executable proposal generation, regression reasoning, conditional revision, cumulative version management, no-change judgment and their promotion gate. Persist the evidence linking those decisions to real model calls and measured behavior.

An agent framework may provide model calls or orchestration. A report, hard-coded public fix, model narration of a scripted correction, or wrapper around a ready-made solution is insufficient. The unchanged submitted controller must learn from new evidence and changed policies.

## Setup-only legacy files

The Email/Calendar `core` pack, `baseline/controller.py`, `world.py`, `judge/evaluate.py`, `judge/run_hidden.py` and the original release-summary script belong to the installation smoke exercise, not the substantive v3 learner. Core completion hooks cannot solve or satisfy the company-workflow assignment. Use `judge/workflow.py` for the substantive submission.

## What is deliberately withheld

Reference controllers, proposal prompts, policy induction/fix libraries, learned workflows, raw reference model responses and private world definitions are not distributed. Published proof files contain coverage, outcomes and hashes, not an implementation to assemble. The public policy is not secret; passing it alone is not proof of learning.
