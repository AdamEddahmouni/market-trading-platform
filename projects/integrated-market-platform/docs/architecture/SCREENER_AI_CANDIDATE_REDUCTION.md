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
2. Read no more than the first 20 matching rows.
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

The hard limits are `MAX_INTAKE=20`, `MAX_SELECTED=5` and a 96,000-byte packet.
Intake is the first 20 rows of the server's existing sorted/filtered result,
independent of which page the browser has loaded; no additional ranking model
or source retrieval is introduced.
Packets are content-hashed for cache/deduplication and expire conservatively;
expired current evidence withdraws rather than being reused. The hash includes
scope/result-set/snapshot identity, admitted evidence and deadlines, prompt
content hash, provider and model. Volatile cutoff, snapshot/evaluation display
clocks and age are excluded from cache identity; material source clocks and
evidence deadlines remain bound. Expiry is the earliest admitted evidence deadline or the
30-minute cap, whichever comes first. Inflight requests deduplicate; failures
are also cached to avoid automatic rebilling. Scope changes withdraw results
and discard late responses. No expiry or scope event automatically runs a model.

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
