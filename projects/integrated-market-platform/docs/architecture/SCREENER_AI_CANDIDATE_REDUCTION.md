# Screener AI candidate reduction

Classification: CURRENT_CANONICAL_TRUTH, SOFTWARE_CONTROLLED software contract.
Version: `screener-ai-screener/1.0.0`. Owner milestone: OCT1-04. This document
does not establish empirical provider proof, forecasts, targets, or trading
authority.

## Purpose and boundary

The AI Screener is an explicit operator request that reduces the active
Screener result set to at most five candidates grounded in the rows already
visible to the server. It is a read-only analytical convenience. It cannot
retrieve new information, browse the web, call tools, create orders, size a
position, produce a target or forecast, alter a portfolio, or start an
autonomous loop.

The server owns the scope and evidence boundary:

1. Reconstruct the active settled Screener scope (universe, search, sort,
   direction, filters, view/screen, match count and result-set/snapshot identity).
2. Read no more than the first 50 matching rows. An explicit Run also acquires
   allowlisted observations through the existing OpenD snapshot adapter; Preview
   reads its bounded cache without acquisition.
3. Project only allowlisted numeric quote, technical and dated rates/reference
   row facts into an isolated evidence packet. Other specialist capabilities
   remain explicitly missing; whole specialist payloads are not consumed.
4. Re-evaluate current/reference eligibility at one final UTC decision cutoff.
5. Send the bounded packet to the selected existing News provider and validate
   the response before it reaches the panel.

The panel is lazy-loaded and performs no inference when opened. Preview is a
bounded read-only estimate; the POST run is the sole inference trigger. A
result displays the cutoff, provider/model, runtime, cache/expiry metadata,
supporting and conflicting evidence, missing evidence and uncertainty. A
candidate can be opened in the ordinary Screener/Workspace investigation flow.

## Contracts and route policy

`GET /screener/ai-screener/preview` is `state.read`. It validates the same
scope as the run, reports matched/intake limits and the selected provider
status, and never calls an inference provider. `POST /screener/ai-screener` is
`state.write` because it performs the explicit operator-requested synthesis;
it has no execution side effect.

The POST returns at once with a tracked run (`screener-ai-screener-run/1.0.0`)
and the work continues on the server. `GET /screener/ai-screener/runs/{run_id}`
(`state.read`) returns that run: its stage, per-stage measured time, packet
size, candidate counts and, once finished, the stored result
(`screener-ai-screener/1.0.0`, unchanged). `GET /screener/ai-screener/runs/active`
(`state.read`) returns the account's run in progress and its latest finished
run without result bodies, which is what a reloaded page attaches to. Reading
status never starts a run. There is one run per account: a second POST while a
run is in progress joins it (`joined: true`) and starts nothing.

Stages are reported in the order the work happens: `SCOPE`, `NEWS`,
`EVIDENCE`, `PACKET`, `BUDGET_RESERVED`, `MODEL_CALL`, `VALIDATION`, `STORED`.
News is read before the evidence cutoff is taken, so `NEWS` precedes
`EVIDENCE`. A stage that did not happen is absent: `BUDGET_RESERVED` only when
a paid engine's reservation was actually held, and no model stages for a
cached answer or a refused reservation. The model call is one blocking request
with no streaming, so progress is stages with elapsed time and never a
percentage. `MODEL_CALL` is reported with the request timeout and the median
latency of earlier measured calls to the same model in this server process
(absent until one has been measured). Stage reporting is observation only
(`intelligence/inference/run_progress.py`): it does not change the packet, the
prompt, the call or the result, and callers that do not observe (the
reevaluation loop, Action Decisions, News synthesis) are unaffected.

`runs/active` (`screener-ai-screener-runs/1.2.0`) is also what the Screener's
always-visible AI strip reads. Besides the two runs it states one `state`
(`RUNNING`, `IDLE`, `WAITING_FOR_BUDGET`, `BLOCKED`, `NOT_CONFIGURED`), the
engine (`ai`) and, for a paid engine, the shared daily `budget` in runs-left
terms. The size of a run is the last worst-case reservation actually held for
that model in this server process (`run_size_basis: LAST_RESERVATION`); until
one has been held, `runs_left` is null and the strip shows requests left
instead of inventing a count. `WAITING_FOR_BUDGET` means the engine reports
the budget exhausted, or another run of the measured size does not fit.

The strip sits under the Screener header for every universe that offers the AI
Screener. It shows the stage and measured time of a run in progress, the last
pass with its selection count and an evidence-expiry countdown, the budget,
and the scheduled loop's next cycle (read from
`GET /screener/reevaluation/status`). `Run now` is the same explicit POST as
the panel's Run AI Screener; `Stop automatic passes` is the existing
reevaluation stop; `Open` opens the AI Screener panel. The strip starts
nothing on its own and is not an ARIA live region, because it changes every
second while a model works.

### Engine choice

The engine and model are one machine-wide setting shared by News synthesis,
the AI Screener, Action Decisions and the reevaluation loop.

- **Locked while a loop runs.** `POST /screener/news/synthesis/engine` answers
  409 `SYNTHESIS_ENGINE_LOCKED` while a reevaluation loop holds its lease
  (`REEVALUATION_LOOP_RUNNING`), in this process or another, and saves nothing.
  If the loop state cannot be read the route also refuses
  (`REEVALUATION_STATE_UNKNOWN`). Every Screener response whose `ai` block
  lists `engines` also carries `ai.engine_lock`, so both pickers disable
  themselves and say why; the route is the enforcement.
- **Confirmed before it is sent.** Choosing an option in either picker only
  proposes it. A confirmation states that the change applies to every AI panel
  on this machine and whether the engine is paid; nothing is posted until the
  operator confirms.
- **Packet fit.** Each engine option carries `context_window`: the context
  window IMP starts the managed local model with, and null where none is
  recorded (hosted engines, an operator-run local endpoint). The preview adds
  `engine_fit`, one entry per engine with `packet_size` (the packet's
  estimated input plus the output allowance) and `fits`. `fits` is null when
  either side is unknown, so a hosted engine is never claimed to fit or not to
  fit. A local model too small for the current packet is marked in the picker
  and in the confirmation instead of being silently selectable.

Tracked runs live in the server process (the last 20). A server restart ends
an in-flight run and forgets its tracking record; the stored candidate run
remains the durable record of any result. A run that raises ends as `FAILED`
with a stable reason code and the stage it failed in; no other error text
leaves the process.

The service reuses the News service's selected provider instance, model
catalog, secret handling and shared paid-engine daily budget. Local inference
uses the same provider boundary without a second budget. Provider status and
budget refusal are inherited from News; the AI Screener does not create a new
provider, subscription, model download or network retrieval path.

## Evidence contract

Current quote/technical observations require a valid source event and are
evaluated at the final cutoff. Reference facts (rates, auction, publication
and other dated cross-asset context) remain explicitly reference-only. Finviz
export retrieval is an acquisition timestamp, not proof of a current market
observation; it cannot silently promote a row into current evidence.

The packet carries current/reference facts and `weak`, `missing` and `blocked`
states; validated output resolves supporting and conflicting references. Each
field is joined to its exact source/clock/state group from the canonical
OCT1-03 projection. A different field's fresh status cannot admit its stale
value. Blocked facts are removed before serialization and evidence hashing.
The parser accepts only candidates whose
instrument identity and reference IDs exist in the packet, whose ranking is
bounded, and whose support includes at least two admissible references,
including the current quote plus another strong reference. Unknown references,
weak-only support, conflicting support, malformed output, duplicate/excess candidates and
prohibited action, target, forecast or execution language fail closed. Zero
valid candidates is a valid result.

The equity/ETF row projection now joins canonical cached last price before this
packet is assembled. QUOTE facts may also contain bid, ask and spread when
those exact fields share admissible source clocks. New evidence retains
`received_at` separately from source `as_of`; historical runs remain immutable.
A healthy price alone does not waive the required additional strong support.
Preview is evaluated at its own cutoff; run always rebuilds/re-evaluates at
its final cutoff, so their counts may differ as ticks arrive or evidence ages.

## Limits and lifecycle

The hard limits are `MAX_INTAKE=50`, `MAX_SELECTED=5` and a 320,000-byte packet.
The 50-row intake is not closure of the full-universe blind-spot issue: rows
beyond the first 50 are never seen by the model, and nothing here batches them.

Inference uses a compact wire (`ai-screener-wire/3.0.0`), separate from the
stored result (`ai-screener-output/1.0.0`), which is unchanged:

```text
canonical candidates -> compact packet -> compact model output -> exact decode -> canonical validation -> stored result
```

In the packet each candidate carries `candidate_key`, its position in this
request, and each of its evidence items carries `reference_index`, its position
in that candidate's own list (current market first, then reference). A model
pick is `candidate_key`, `rank`, `rationale`, `supporting_refs`,
`conflicting_refs` and `uncertainties`, where the two reference lists hold that
candidate's `reference_index` values. An index is looked up only in the list of
the candidate the pick names, so no value on the wire can name another
instrument's evidence. `candidate_key` is generated from the request, never
stored on the canonical candidate, and decoded only against this request's
candidates. A key or index that is not an in-range integer fails with
`WIRE_CANDIDATE_KEY_INVALID` or `WIRE_REFERENCE_INDEX_INVALID`; nothing is
clamped, repaired, matched by symbol or looked up elsewhere. The model no
longer states weak references or missing capabilities: the decoder takes both
from the packet candidate, so the stored lists are exactly the packet's. Every
canonical gate then runs on the decoded pick, including the ownership, weak
support and missing-list checks. A rejection records `validation.stage`:
`DECODE` or `CANONICAL_VALIDATION`. Output already in the stored shape is still
accepted by the parser and passes the same canonical gates.

Prompt `screener.ai_candidate_reduction.v3` describes this wire. It lists the
output fields by name, and a regression compares that list with the schema and
checks that every field name in the prompt exists in the schema or the packet.
Prompts v1 and v2 are unchanged for the runs stored under them. Each run
records `wire_schema_version`, `output_schema_hash`, `prompt_id`,
`prompt_version` and `prompt_hash`; all of them, with the provider and model,
are part of cache identity. Shared news refresh precedes acquisition of
short-lived market snapshots, so slow news providers cannot age newly acquired
snapshots before the decision cutoff.
Intake is the first 50 rows of the server's existing sorted/filtered result,
independent of which page the browser has loaded; no additional ranking model
is introduced. An explicit equity/ETF Run also reads one bounded OpenD
market snapshot for this intake using the existing snapshot adapter. Its
dedicated cache never alters the Screener's universe ordering or result chain.
Preview reads this cache only. Price, volume, bid/ask/spread and change versus
previous close carry the provider's row observation clock; `change_basis` is
`PREVIOUS_CLOSE`. The unchanged 60-second L1 policy is independently evaluated
at the final cutoff. Snapshot retrieval time never substitutes for a missing,
stale or future provider clock. News instrument providers remain cache-only.

The model output schema is flat with bounded integer enums: large branching
schemas and long reference enums exceed the vendor grammar compiler's size
limits. The reference enum is the longest single candidate's list, so the
schema does not grow with the intake. Claude candidate reduction uses strict tool inputs; the application parser still
checks every evidence, ranking, language and freshness invariant. Unsupported
strict numerical/array bounds are expressed in descriptions and enforced by
the unchanged parser. The output-schema hash participates in cache identity
and is recorded in the receipt. A missing-list rejection records bounded
canonical capability diagnostics, never raw model text or provider bodies.

After successful validation, result lifetime is bounded by the evidence cited
by selected candidates, including their current quote and all cited weak or
conflicting evidence. An unrelated unselected observation cannot expire that
selection. Expired selected evidence still returns `EXPIRED`. Every deployment
changing acquisition, intake or schema is a new software/method epoch and must
retain the preceding epoch's immutable receipts.
When a news packet exceeds the byte bound, packing first removes detailed
provider coverage from candidates with no admitted story, in descending
instrument-ID order, and records `GLOBAL_PACKET_STATUS_CAP`. Only then are
stories removed by the existing deterministic ordering. After each removal,
NEWS, SENTIMENT and alignment references are rebuilt; newly empty candidates
release their provider coverage before another story is removed. Current
market facts, evidence IDs, source clocks and admission rules are unchanged.
Packets that fit retain all coverage detail. If admitted evidence still cannot
fit, inference remains blocked by `EVIDENCE_PACKET_BOUND_EXCEEDED`.
Packets are content-hashed for cache/deduplication and expire conservatively;
expired current evidence withdraws rather than being reused. The hash includes
scope/result-set/snapshot identity, admitted evidence and deadlines, prompt
content hash, provider and model. Volatile cutoff, snapshot/evaluation display
clocks and age are excluded from cache identity; material source clocks and
evidence deadlines remain bound. Expiry is the earliest admitted evidence deadline or the
30-minute cap, whichever comes first. Inflight requests deduplicate; failures
are also cached to avoid automatic rebilling. A result is drawn only under the
Screener query it answered (universe, view, saved screen, search, sort and
filters); under any other query it is withheld. A refresh of the Screener list
does not withdraw it: the result states its own cutoff and the UI notes that
the list has refreshed since. No expiry or scope event automatically runs a
model.

The UI shows engine/model, shared daily budget where available, packet/cost
estimate, selected/intake counts, cutoff and expiry. Supporting, conflicting,
weak, missing, blocked and uncertainty sections are inspectable. Candidate
navigation uses the existing investigation callback even outside the loaded
table page. Controlled browser evidence is recorded in the existing
[OCT1-04 plan](../superpowers/plans/2026-10-02-oct1-04-ai-screener.md).

This contract is SOFTWARE_CONTROLLED and remains subject to provider
availability, source clocks, unknown publication cadence and workstation
clock limitations. No empirical claim is made by a passing fixture or local
provider test. [OCT1-05](../superpowers/plans/2026-10-03-oct1-05-news-evidence-integration.md)
adds bounded canonical NEWS/SENTIMENT references and deterministic comparisons,
with prompt `screener.ai_candidate_reduction.v2` and mandatory grounded conflict
disclosure. Cached coverage and story/model provenance are inspectable; News
drilldown selects the candidate in Screener even outside the loaded page.
OCT1-06 remains outside this implementation.

## Lifecycle view (OCT1-10)

Each selected candidate is rendered in the AI Screener panel as a lifecycle card
that adds its action decision, Paper entry, position, stop, exit and P&L. That
view is a read-only projection over this run record and the other authorities;
it does not change selection, evidence or prompts. Contract:
[SCREENER_TRADE_LIFECYCLE.md](SCREENER_TRADE_LIFECYCLE.md).

## Claude request compatibility

`intelligence/inference/anthropic_models.py` is the one table of what each
hosted Claude model accepts, and builds the request from it. It serves every
task on the Claude engine (News synthesis, AI Screener, Action Decisions).

| Model | Temperature | Forced tool call | Strict tool schema | Reasons by default | Context |
| --- | --- | --- | --- | --- | --- |
| `claude-haiku-4-5-20251001` | sent as 0 | sent | yes | no | 200,000 |
| `claude-sonnet-5-5` | omitted (rejected) | omitted (rejected) | yes | yes | 1,000,000 |
| `claude-opus-5-5` | omitted (rejected) | omitted (rejected) | yes | yes | 1,000,000 |

An optional parameter the model rejects is omitted. Where the tool call cannot
be forced, the request uses `tool_choice: auto` limited to one call and the
system text requires the call; a reply without the tool call is
`ANTHROPIC_TOOL_NOT_CALLED` and its text is never parsed. A model that reasons
by default gets 8,192 extra output tokens, reserved against the daily budget,
because `max_tokens` bounds reasoning and answer together. That figure has not
been measured against a real run.

The AI Screener requires a strict tool schema. A model that cannot provide it,
or that has no row in the table, is refused before any reservation or request
with `MODEL_REQUEST_CONTRACT_UNSUPPORTED`, and the result's `compatibility`
states the selected model, the required contract and the unsupported
capability. No other model is used in its place. The Haiku request is byte for
byte what was sent before requests became model-aware. A saved Claude model
that is no longer in the catalog selects no provider
(`SYNTHESIS_MODEL_NOT_IN_CATALOG`) instead of the default. `DEFAULT_MODEL`
applies only when neither the saved choice nor
`IMP_SYNTHESIS_ANTHROPIC_MODEL` names a model. The engine options list
`model_contracts` for the Claude engine, and the picker says when a model
cannot run the AI Screener.

`AnthropicSynthesisProvider.preflight` sends the generation request, minus
`max_tokens` and `temperature`, to the token-count endpoint: it bills and
generates nothing and reports the input tokens, whether the provider accepts
the body, and whether tokens plus the output bound fit the model's window. It
is a diagnostic; a run does not call it. A token count does not compile a
strict schema's grammar: only a generation request does.
`tools/ai_screener_provider_contract.py` writes
`artifacts/ai-screener-provider-contract-closure.json`; with `--probe` it runs
the token count on the exact 50-candidate request and a zero-output grammar
probe for every selectable model.
