# Bounded ARE world contract

The starter is a small, runnable kernel for the improvement-system challenge, not a commercial-product clone. Native ARE 1.2.0 Email and Calendar applications store and mutate state; a deterministic adapter owns scheduling and evaluation. No ARE oracle is used.

## Scenario specification

Each JSON world contains `id`, `account`, `operator`, `deadline` (logical seconds), `objective`, `response_plan`, and `final_choices`. Apps start empty at the fixed epoch in `world.py`. These fixtures cover the workflow of requesting a person's review decision, respecting cancellation or timeout, booking only a confirmed slot, and sending the owner an accurate outcome.

`response_plan` entries contain `after` (seconds from request) and `reply`. A reply has `final`; progress replies also supply `status` and `slot`. Final replies obtain `status` and `slot` from the seed-selected `final_choices`: `confirmed` with a datetime string or `cancelled` with a null slot. Choice selection and 0 to 2 second response jitter are deterministic by seed. Ties execute in insertion order. The deadline wins over replies scheduled after it; a final reply at the deadline is available. If no final reply arrives, the correct result is `unresolved` and no booking.

The director only schedules human replies after an actual availability request. Waiting without requesting must not create a response. All native tool timestamps, person events, timeouts and waits share one logical clock. The scheduler jumps to the next due event or deadline; it never sleeps or silently fixes the agent's actions.

The raw specification is a replay/evaluator input, not an agent tool. The director's future reply plan and expected results must not be leaked into agent prompts. New branches are synthetic, not historical facts. All tool results come from current ARE state.

## Action protocol

Call `World.act(action, arguments)`:

- `request`, `{}`: native email request; schedules the response plan once.
- `read`, `{}`: read operator replies actually delivered to the native inbox.
- `book`, `{slot}`: native calendar mutation for a one-hour review.
- `summary`, `{status, slot}`: native email to the owner.
- `wait`, `{}`: advance logical time to the next event or deadline.
- `complete`, `{}`: end the agent run. Further actions are invalid.

Every meaningful action is logged with result and provenance, then the director processes due events. `execute(spec, seed)` runs the frozen baseline; `execute(spec, seed, hook, "candidate", version)` applies a declared hook without rewriting baseline files. Richer candidate policies can emit the same actions on an isolated `World`, then use `world.trace` to export the run. Do not replace the tool implementations or scoring.

Independent success checks inspect actual Calendar and Email state, request/completion status, and whether a final reply or timeout was respected. They do not reward matching a particular tool-call sequence. `verify_trace` independently rebuilds the native world from actions and rejects fabricated messages, outputs, state or scores.

Unseen evaluations vary IDs, accounts, operator addresses, timing, final choices and seeds within this protocol. No undisclosed connector or extra API is required. You may add explicitly labeled regression scenarios, but must still cover every supplied world.
