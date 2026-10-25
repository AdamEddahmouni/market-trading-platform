# AI engine benchmark, 2026-10-24 (rebuild step 5)

The test that picks the free local model and the paid model for owner decision 4
([AI_ENGINE_SWITCH.md](../operations/AI_ENGINE_SWITCH.md)). Run on the owner's PC (RTX 2070 Super 8 GB, 32 GB RAM)
with only `llama-server` running: no platform, collector, OpenD or task. Evidence:
`destination-tests/20261024-switchable-ai/` under the portable root.

## Result

- **Free local: Qwen3-4B stays the default.** No candidate passed the rule fixed before the runs.
- **Paid: Claude Haiku 5.5** is preselected in Setup. **Paid AI stays off.**
- **Paid test cost: $0.3762** of the $3 limit (the benchmark ledger, including one smoke call). OpenAI and Gemini were
  skipped: this PC has no key for either.

## Cases

60 real Action Decisions from the state database (read-only), 2026-10-17 to 10-23: 45 instruments, 28 with news,
all with a flat position. Each case's input hash matched its stored decision, so the evidence, context and
conditions are exactly what production sent. 25 of them were first made with older prompts (v1, v2); every model
here got today's production prompt (v3), schema, 2,000-token output bound and timeout, and was graded with the
production validator (`decode_wire` + `parse_proposal`).

## Table

| Model | Accepted | Typical / slow (p50 / p95) | Generation | Peak VRAM | Cost per decision |
|---|---|---|---|---|---|
| Qwen3-4B (today) | 57 of 60 (95%) | 6.3 / 12.0 s | 79 tok/s | 4.6 GB | free |
| Qwen3-4B-Instruct-2507 | 54 of 60 (90%) | 5.5 / 11.9 s | 78 tok/s | 4.6 GB | free |
| Qwen3-8B | 57 of 60 (95%) | 10.2 / 19.2 s | 50 tok/s | 6.7 GB | free |
| Qwen3-30B-A3B-Instruct-2507 | not started | | | | free |
| Claude Haiku 5.5 | 60 of 60 (100%) | 5.4 / 8.1 s | | | $0.0016 |
| Claude Sonnet 5.5 (10 cases) | 10 of 10 (100%) | 5.6 / 8.2 s | | | $0.028 |
| OpenAI gpt-6-luna | skipped: no `OPENAI_API_KEY` | | | | |
| Gemini 3.5 Flash-Lite | skipped: no `GEMINI_API_KEY` | | | | |

- Every local model missed the same 3 cases with `LOCAL_CONTEXT_EXCEEDED`: those decisions do not fit the 8,192-token
  window. The 2507 model also had 3 malformed answers (`SCHEMA_INVALID`).
- **The 30B model was refused by the memory check** before it started (`LOCAL_RESOURCE_PREDICTED_UNSAFE`). With its
  experts for 38 layers in RAM it needs about 18.9 GiB free; this PC had 17.5 GiB free with everything in IMP off,
  and has less while the platform runs. It is not usable here.
- Load times once the file was cached: 3.5 s (4B), 6.0 s (8B). Before that, the integrity check reads the whole
  file once per process: about 2 minutes for the 4B on the backup disk, 3 minutes for the 8B and 12 minutes for the
  30B.

## How often a model made the same proposal as Claude

Informational; not part of the rule. On the cases both accepted:

| Model | Same as Sonnet 5.5 (10 cases) | Same as Haiku 5.5 (60 cases) |
|---|---|---|
| Claude Haiku 5.5 | 10 of 10 | |
| Qwen3-4B-Instruct-2507 | 7 of 9 | 40 of 54 (74%) |
| Qwen3-4B | 6 of 9 | 32 of 57 (56%) |
| Qwen3-8B | 4 of 9 | 28 of 57 (49%) |

The Claude models never proposed ENTER (Haiku: 41 no action, 19 consider entry). Qwen3-4B proposed ENTER 11 times
(6 of them short) and Qwen3-8B 28 times (14 short). With each case's stored context, the server gate blocked every one:
no governed opportunity, short selling not allowed, or (4 of the 8B's) too little current support, which lowers it to
consider entry. Qwen3-4B once proposed HOLD for a flat position, which the gate refused.

## The rule, applied

A local candidate replaces Qwen3-4B only if it starts within the memory check, its p95 is at most twice Qwen3-4B's
(24.0 s), and its acceptance beats Qwen3-4B's 95% by at least 5 points.

- Qwen3-4B-Instruct-2507: 90%, fails.
- Qwen3-8B: 95%, fails; its p95 of 19.2 s would have passed.
- Qwen3-30B-A3B-Instruct-2507: did not start.

Paid pick: the cheapest model per accepted decision with acceptance at least the local winner's 95%. That is Claude
Haiku 5.5 at $0.0016, against $0.028 for Sonnet 5.5.

## Limits

- 60 cases, one run each; acceptance is close to the ceiling, so the rule can barely separate the models.
- Acceptance means a well-formed, grounded proposal, not a good trading call. Whether a proposal was right is for
  the step-8 evaluation report.
- All cases were flat positions; HOLD and EXIT decisions were not tested.
