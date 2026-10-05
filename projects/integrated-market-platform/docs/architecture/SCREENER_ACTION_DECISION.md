# Screener action decisions (OCT1-06)

Status: current software contract. Acceptance is SOFTWARE_CONTROLLED; this layer
does not establish empirical edge or execution authority.

## Ownership and flow

An explicit **Evaluate Decision** request reads a persisted OCT1-04/05 selected
candidate, freezes its admitted point-in-time facts and current Paper ledger
context, and asks the existing News/AI Screener provider for a bounded proposal.
Preview, opening panels, history reads, navigation and the expiry clock never
infer. Candidate reduction retains its separate task and prompt. No new provider,
budget, subscription, scheduler, broker path or risk engine is introduced.

`SCREENER_ACTION_DECISION` uses `screener.action_decision.v1` (prompt 1.0.0),
`action-proposal/1.0.0` and server policy `action-decision-policy/1.0.0`.
Local and hosted adapters use the dedicated JSON schema; hosted calls use the
same persisted daily budget as News and candidate reduction. The browser supplies
only run/instrument IDs and an optional existing Opportunity ID. It cannot supply
an evidence packet, position, model instructions, quantity or risk settings.

## States and position restrictions

| State | Meaning | Position |
|---|---|---|
| NO_ACTION | The current assessment proposes no entry | FLAT |
| CONSIDER_ENTRY | Review a candidate; entry conditions/support remain insufficient | FLAT |
| ENTER | Current bounded conditions support an entry assessment; risk remains independent | FLAT |
| HOLD | Observed direction continues the existing position thesis | LONG or SHORT |
| EXIT | Observed direction reverses the held-position thesis; close current holdings | LONG or SHORT |
| REVALIDATION_REQUIRED | Safety state for expired/stale/unavailable/illegal inputs or invalid proposals | Any |

Each fresh evaluation can transition from any prior assessment to a state legal
for the **current actual ledger position**. ENTER is never proof of a fill.
Only a subsequent held-position snapshot permits HOLD/EXIT. Pending orders,
deferred restoration, unknown/future position clocks or snapshots older than
30 seconds require revalidation. SHORT rows are signed from ledger side and
quantity; a missing row means flat only in the synchronously available ledger.

## Conditions and grounding

The model selects IDs from server-owned conditions; it cannot author expressions
or price levels. CURRENT_QUOTE requires a current admissible positive observed
quote. DIRECTION_SUPPORTED uses current strong signed native flow, otherwise
observed price change. THESIS_CONTINUES / THESIS_REVERSED compare that observed
direction with held-position direction. DECISION_EXPIRED is an invalidation
deadline and yields revalidation, rather than an automatic liquidation.

ENTER needs current strong quote and nonquote support, grounded direction,
both entry condition IDs, and an exit/invalidation plan. Missing support downgrades
to CONSIDER_ENTRY. HOLD needs current continuation evidence and an exit plan.
EXIT needs a met invalidation condition and current quote. Stale quote blocks all
three. The method is MARKET_NOW_IF_GATES_PASS; reference quote is separately
identified from Paper preview price and any simulated fill. Stops, arbitrary
targets, SMA/trailing logic, future-return promises, numeric or spelled-out
monetary/sizing prose and executable fields are rejected. Uncertainties are shown.

Unknown/duplicate refs, weak support and undisclosed deterministic News conflicts
reject the proposal. Missing/weak capability lists must match server evidence.
Unknown or future evidence clocks are excluded with reason codes, including
News availability/retrieval/ingestion clocks. Conflicting News remains inspectable
even when price evidence supports the action. All plan statuses are recalculated
by the server; an ENTER proposal does not imply a PASS risk decision.

## Opportunity and independent Paper risk

Existing OpportunityV1 records are resolved by shared evidence lineage, or by
an **explicit operator-selected existing Opportunity ID** with exact instrument
scope and the existing temporal/side/quality gate. Symbol similarity never
creates an Opportunity. An absent governed record permits an informational
ENTER assessment but blocks entry handoff. Opportunity direction must agree.

Explicit Prepare Paper Preview / Prepare Paper Exit produces the existing
version-1 Workspace draft with bounded ACTION_DECISION and ACTION_SNAPSHOT refs.
Entry starts with the existing one-unit technical placeholder; the operator
owns editing and confirmation. EXIT derives opposite side and exact close
quantity from current holdings. Neither operation submits or closes an order.

Both existing Paper preview and submit revalidate action expiry, account,
portfolio/policy input digest, authority, instrument, side and close quantity.
The existing preview binding also binds action source refs, so stripping or
replacing them after preview cannot reuse its approval. Manual drafts retain
their existing contracts. Internal Paper authority requires IMP_PAPER_EXECUTION
and INTERNAL_SIMULATION plus an existing allowed Paper authority; Live/broker
authority is never granted by this layer.

Governed ENTER previews additionally reuse BUILD 22 PreTradeRiskEngine,
snapshot_from_paper_ledger, policy/proposal/risk contracts and the existing
repository. Existing BUILD 22 policy defaults govern NAV/exposure/concentration;
ledger hard caps/short/open-order policy are also projected into the canonical
policy. The operator's desired quantity enters the existing sizing pipeline.
The interactive Paper risk/simulator path still evaluates independently. Any
REJECT, FAIL_CLOSED or approved quantity below the operator quantity blocks
submit; a reduction is displayed and requires a fresh preview for the edited
quantity. Submit recomputes the independent entry risk and recognizes submitted
Opportunity provenance in existing order source/correlation fields. Idempotent
retries return the prior acknowledgement; fresh submissions recheck action,
preview and authority again after waiting for an eligible bar. EXIT reuses existing
Paper close risk; it never fabricates a new entry Opportunity for liquidation.

## Immutable evidence, history and API

ActionDecisionV1 (`action-decision/1.0.0`) contains action/previous state and IDs,
cutoff/evaluation/deadline, candidate identity/hash/rank, complete bounded evidence
facts, support/conflict/weak/missing refs, position/account/session, Opportunity,
deep-copied risk policy, portfolio revision, rationale/uncertainties, conditions,
reference quote, provider/model/prompt/hash/tokens/latency/request IDs and trace.
In-flight material input changes persist a blocked revalidation record with the
**original** frozen evidence. The model cannot rewrite the policy snapshot.

The local-state SQLite companion stores immutable canonical JSON, bounded to
512 kB per candidate receipt and 128 kB per action record. Reads return detached
objects. ACTION_ASSESSED ExecutionDecisionTraceV1 links the companion and snapshot
IDs; when both use the same SQLite connection, one transaction publishes both or
neither. Existing Paper preview/submit traces and entry risk records carry later
authority; the earlier assessment's NOT_PREVIEWED risk fields remain historical.
Persistence-off mode is explicitly ephemeral. History returns the latest 100
records, filtered to the current account. Equivalent still-current latest inputs
reuse the latest decision without another model call, including A → B → A
transitions; changed or expired inputs append.

| API | Purpose | Account-scoped permission |
|---|---|---|
| POST /screener/action-decision/preview | Capture context/conditions and eligible existing Opportunity options; no inference | state.read |
| POST /screener/action-decision/run | Explicit bounded proposal and immutable gated assessment | state.write |
| GET /screener/action-decisions?instrument=… | Read current-account history | audit.read |
| POST /screener/action-decision/handoff | Fresh validated existing Workspace draft | paper.order.submit |

Frontend request generations/abort guards isolate late candidate/scope responses.
The display expiry timer never reevaluates. Expired records retain their history,
and handoff revalidates again even if authority changes after rendering.

Acceptance and integration evidence:
[OCT1-06 report](../superpowers/plans/2026-10-04-oct1-06-action-decision.md).
OCT1-07 scheduling, OCT1-08 SMA stops and OCT1-09 experimental Paper campaign are
outside this contract.
