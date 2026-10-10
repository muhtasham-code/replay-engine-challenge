# Workflow and replay contract

## Harness boundary and framework choice

The candidate chooses the model provider and framework for the learning controller, not a different target task. The target harness is the supplied company agent's versioned executable workflow. A proposal contains a complete `steps` workflow and parent lineage; it is not arbitrary Python/JavaScript code or an external framework configuration. Internal learned prompts, skills or memories must produce that executable workflow for replay. Keep the supplied interpreter, world, baseline and evaluator unchanged. The `harness` argument to `ReplayClient.evaluate` is a version identifier used in trace provenance, not the name of a framework.

The broker executes actions and reports outcomes. It does not mine traces, rank issues, choose model context, generate hypotheses or proposals, select historical regressions, revise fixes or manage active versions for the candidate. Those decisions and their evidence are the candidate's implementation.

## Evidence and reconstruction

The v3 manifest contains `contract`, `broker_url`, an ephemeral `broker_token`, the frozen `baseline`, `root_version` and sanitized `scenarios`. Each scenario has `id`, `task`, `fields` and partial `observations`. It never contains private grading predicates or future personas.

Each observation has `id`, `account_ref`, `field`, `value`, `at` and `source`. Reconstruct each declared field using only the matching account and observations at or before zero. Use the latest timestamp; conflicting latest values and missing fields remain unknown. Produce `{value, status, evidence}` with sorted supporting IDs. Status is `observed` or `unknown`. Display name is not identity. The broker validates this reconstruction.

Histories contain `trace_id`, `scenario_id`, partial observations, declared fields, task, actual events, outcome checks, success/failure, feedback and provenance. No complete starting or final snapshot is supplied. Do not assume every complaint identifies a real failure.

## Generic executable workflows

A workflow is `{steps: [...]}`, not a named policy effect or fix hook. The interpreter supplies mechanics, not policy or skill selection.

Supported instructions:

- `set`: `name`, `value`; bind a variable or change an amount.
- `call`: `action`, `args`, optional `save`; execute a real tool action and bind its result. A saved dictionary also exposes `save.key` variables.
- `if`: `test`, `then`, optional `else`; conditional nested instruction lists.
- `await`: `intent`; fast-forward to the next matching incoming reply or deadline. Reply fields bind as `reply.key`; clarified facts refresh. If no reply arrives, the runtime ends unresolved.
- `finish`: `status`; write the owner report and end the run.

Completion/report statuses for `finish` and `summary(status)` are `renewed` (a completed accepted renewal), `suppressed` (outreach withheld because the applicable restriction requires it), and `unresolved` (the job has not reached a successful resolution). The status must match the actual executed state, not merely the intended action. These are reporting labels, not instructions about which policy applies; infer the appropriate behavior from the supplied evidence. `finish` performs both `summary` and `complete`, so do not also emit a duplicate summary for the same completion.

Arguments may use `{var: "variable.name"}`. Starting variables are the reconstructed field values. Predicates use `{field, op, value}` with `eq, ne, gt, ge, lt, le`, or nested `all`, `any`, `not`. Unknown numeric comparisons are false. Maximum 100 instructions and 500 tool/director events per replay.

The baseline only binds the observed discount, creates an offer, sends it, awaits acceptance and reports. It contains no approval skill, suppression policy, commercial correction or exception-learning logic. Proposed workflows can change control flow, tool arguments, recipient/intent, waiting and completion behavior. You must generate those changes.

## Tools and director

Actions are `lookup(service)`, `inbox()`, `offer(discount)`, `message(to, intent, ...)`, `summary(status)`, `wait()` and `complete()`. Services are CRM, billing, usage and mail. Recipients are operator and customer. Message intents:

- `approve` with `discount` and nonempty `reason`: operator replies with `approved`.
- `clarify` with `field: contact.allowed`: operator supplies consent.
- `offer` with an actual `offer_id` and matching `discount`: customer may accept or decline.

Reply intents are `approve` (not `approved`), `clarify`, and `accepted` or `declined`. `await` matches the reply intent exactly. Predicate `value` is a literal, not a variable reference; `{var: ...}` is supported in tool arguments and set values only. Inspect actual replay events when debugging an unsuccessful generated workflow.

Approval replies mutate approval records; acceptance mutates the actual offer; clarified facts affect subsequent reads. The director observes each action, schedules responses based on the actual message and world state, and shares the same logical clock as native ARE email and custom business records. It does not choose the candidate's actions.

`ReplayClient(manifest).evaluate(scenario_id, seed, workflow, reconstruction, harness)` returns complete executed traces plus outcome checks. Construct the client with `json.loads(manifest_path.read_text())`. Import it from `replay_challenge.workflow`. No model key is required.

Checks concern authorization, restrictions, commercial terms, duplicate side effects, completion, outcomes and truthful reporting. These are result categories, not universal company policy. Hidden predicates differ.

## Trust and limits

The local public demo file is not secret. It provides a transparent debugging example, not the policy to memorize. Hidden worlds and grading predicates are held in broker memory in a separate grader environment; candidate files contain only sanitized evidence. The supplied Python client is not a security sandbox. Grading must isolate the candidate process from the grader filesystem/processes; attempts to bypass this boundary invalidate the submission.

The grading broker allows 1,000 replay requests per corpus. All scenarios and seeds count. Use evidence-guided hypotheses, not exhaustive scorer search. No extra undocumented tools or connectors are required.
