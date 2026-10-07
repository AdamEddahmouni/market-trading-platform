# Next-session snapshots and governed reevaluation (OCT1-07)

Status: current software contract. Acceptance is SOFTWARE_CONTROLLED; nothing here
establishes empirical edge, model accuracy, market-data cadence or execution authority.

OCT1-07 has two separate functions that share only the OCT1-06 action decision:

1. **Next-session snapshot** — freeze one action decision for the next market
   session and compare it later with what was observed.
2. **Reevaluation** — an operator-started, bounded, audited loop that re-reads
   evidence on a schedule and asks for a new immutable decision only when
   something material changed.

A schedule is not freshness. A 60-second tick reads whatever each capability's own
clock says; it never relabels reference, publication-based or delayed evidence.

## Reused authorities

| Need | Existing authority reused |
|---|---|
| Decision, evidence snapshot, history, trace | OCT1-06 `ScreenerActionService`, `ActionDecisionV1`, `action_decision_records`, `ACTION_ASSESSED` trace |
| Candidate evidence and reduction | OCT1-04 `ScreenerAiService._packet` / `CandidateReducer` (≤20 intake, ≤5 selected) |
| Per-capability clocks | OCT1-03 `freshness_contract` fields already on every evidence item |
| Lifecycle names and temporal guards | `paper_forward_bridge` `ForwardTestState`, `assert_transition`, `temporal.py` |
| Signal vs execution outcome | `paper_forward_bridge.evaluation.compute_signal_outcome` / `compute_execution_outcome` |
| Session calendar | `shadow.session.session_bounds_ns`, EVIDENCE-01 frozen US holiday set (`is_trading_day`) |
| Position, pending orders, consumed Opportunity | Paper ledger projections, as read by OCT1-06 |
| Engine, paid budget | selected synthesis provider and its `budget_status()`; no fallback provider |
| Persistence | existing local-state SQLite connection (`CREATE TABLE IF NOT EXISTS`, same pattern as OCT1-06) |

The forward-test **service** is not reused: `create_decision` / `lock_decision`
require campaign binding and activation, which is FTEP campaign methodology and
out of scope. No campaign, cohort, manifest or sample-floor code is touched.

There was no reusable scheduler abstraction (each feature owns a daemon thread).
The worker follows the enrichment-outbox lease pattern: owner id plus an expiring
lease that a later owner may reclaim.

## Next-session snapshot

`next-session-decision/1.0.0` references the action decision instead of copying
it: `action_decision_id`, `evidence_snapshot_ref`, `input_hash`,
`decision_trace_id`, plus `instrument_id`, `account_id`, `created_at`,
`decision_cutoff`, `evidence_max_time`, target session fields, `action_state`,
`direction`, `candidate_run_id`, `candidate_rank`, `policy_id`, provider/model/
prompt identity, `position_state`, entry/hold/exit condition ids with their status
at the cutoff, `reference_price` (+`_as_of`), `evaluation_policy`,
`lineage_refs`, `content_hash`, and the lifecycle fields `state`, `lock_state`,
`locked_at`, `validity_state`, `evaluation`.

A snapshot can only be drafted from a real decision of the operator's account.
`REVALIDATION_REQUIRED` decisions are refused (`ACTION_EVALUATION_UNAVAILABLE`);
a candidate with no action state cannot be frozen.

### Target session

"Tomorrow" is the first US regular session that **opens strictly after the
decision cutoff**: weekends and the frozen holiday calendar are skipped, and a
pre-market decision targets the same day. It is never `now + 1 day`.

- Supported: `US_EQUITIES`, `US_ETFS` (`US_EQUITY_RTH`, `America/New_York`).
- Any other universe, or a date outside the calendar's covered years, fails with
  `NEXT_SESSION_CALENDAR_UNAVAILABLE`. No date is guessed.
- The canonical calendar has no early-close list. `early_close_metadata` is
  recorded as `UNAVAILABLE` and the regular 16:00 close is used.

### Frozen evaluation policy

Chosen at draft from an allowlist and frozen at lock; the horizon is never picked
afterwards.

| Policy | Observation window |
|---|---|
| `next-session-open-30m/1.0.0` (default) | session open → open + 30 min |
| `next-session-close/1.0.0` | session open → session close |

Both use `reference_price_basis = DECISION_REFERENCE_QUOTE`,
`observed_price_basis = LAST_ADMISSIBLE_QUOTE_IN_WINDOW` and
`decision_state_comparison = LATEST_ACTION_DECISION_AT_EVALUATION`. Target session
start/end and the evaluation horizon are separate fields.

### Lifecycle and immutability

`DRAFT → LOCKED → OBSERVING → EVALUABLE → EVALUATED` (or `INSUFFICIENT_DATA`),
using the forward-test state names and transition table.

- A draft's policy may be replaced. Lock requires: the source decision still
  matches the recorded snapshot/input hash; every evidence `as_of` ≤
  `decision_cutoff`; `decision_cutoff` < observation start; and the lock itself
  happens before observation start.
- After lock every field except the lifecycle fields is frozen. The repository
  compares the frozen content and raises `NEXT_SESSION_LOCKED_IMMUTABLE`; an
  evaluated record raises `NEXT_SESSION_EVALUATION_IMMUTABLE`. There is no
  refresh, re-lock or unlock path.
- Observations are append-only rows. The price is read server-side from the
  current admissible Screener quote; a browser cannot supply one. Guards:
  observed ≥ cutoff, source time ≥ cutoff, source time ≤ observed.
- Evaluation before `observation_end` raises `FORWARD_TEST_HORIZON_NOT_REACHED`.
- Late evidence never enters a locked snapshot. It appears only as a later
  observation or as a new action decision.

### Comparison

An observation, not performance evidence
(`basis = OBSERVATION_ONLY_NOT_PERFORMANCE_EVIDENCE`): frozen state and direction,
decision reference price, first/last in-window observed price, percentage change,
elapsed seconds, the subsequent action state if one exists, current condition
statuses, current position. `signal_outcome` describes market price after the
decision. `execution_outcome` is `NOT_APPLICABLE` unless a Paper order carrying
this decision's `ACTION_DECISION` provenance exists in the ledger; even then only
the order/fill fact is reported. P&L, win rate and any accuracy or profitability
claim belong to OCT1-09 / OCT1-11.

## Reevaluation

### One core cycle

`ReevaluationService.evaluate_cycle(trigger, scheduled_for)` is the only decision
path. **Run Reevaluation Now** and the worker both call it. A non-blocking lock
makes a second concurrent call fail with `CYCLE_IN_PROGRESS`.

Triggers are a closed enum: `MANUAL`, `SCHEDULED_CADENCE`, `SESSION_START`,
`SESSION_END`. The API only ever sends `MANUAL`.

Per cycle:

1. **Evidence check tick.** One deterministic read of the configured Screener
   scope (cache-only News; already-owned flow state; no provider refresh), plus
   one targeted read per held instrument outside the bounded intake (≤3).
2. **Material-change gate** per instrument, against the fingerprint stored at its
   last evaluation.
3. **Existing positions first** (HOLD/EXIT work).
4. **Candidate universe.** The AI Screener reduction runs only if the intake
   fingerprint changed, at most once per `candidate_refresh_min_seconds`, and
   yields `CANDIDATE_ADDED` / `CANDIDATE_REMOVED`. Removed candidates keep their
   history.
5. **Aged-out decisions, then new or changed selected candidates**, up to the
   per-cycle caps; the rest is `DEFERRED` to the next cycle.

An evaluation is performed by the unchanged OCT1-06 `ScreenerActionService.run`
against a server-authored per-cycle candidate run (`origin = REEVALUATION`, fresh
evidence, deterministic weak/missing/conflict refs). Held positions are therefore
reevaluated even when the AI no longer selects them. The only OCT1-06 changes are
additive: `run(..., revalidation_reason=None)` records a deterministic
`REVALIDATION_REQUIRED` without a model call, and `_authority()` exposes the
existing authority predicate.

### Material fingerprint

No request ids, cutoffs or per-tick clocks. Current-market evidence is summarized
structurally (capability, source, delivery mode, freshness, admissibility, weak);
reference evidence by its immutable evidence id; plus alignment results, quote
availability, observed direction, held-position exit condition, position state and
quantity, pending order, Opportunity id, Paper authority, action/risk policy
identity, and one hysteresis price.

| Reason code | Trigger |
|---|---|
| `FIRST_EVALUATION` | no baseline for this instrument |
| `POSITION_CHANGED` | ledger state or quantity changed |
| `PENDING_ORDER_APPEARED` / `_CLEARED` | pending order projection changed |
| `QUOTE_LOST` / `QUOTE_RESTORED` | current admissible quote condition changed |
| `AUTHORITY_LOST` / `AUTHORITY_RESTORED` | Paper authority changed |
| `EXIT_CONDITION_MET` / `_CLEARED` | `THESIS_REVERSED` on a held position changed |
| `DIRECTION_CHANGED` | observed direction basis changed |
| `EVIDENCE_SET_CHANGED` | capability/status/admissibility set changed |
| `REFERENCE_EVIDENCE_CHANGED` | News/sentiment/reference ids changed |
| `ALIGNMENT_CHANGED`, `OPPORTUNITY_CHANGED`, `POLICY_CHANGED` | as named |
| `PRICE_MOVED` | quote moved ≥ `price_move_bps` from the last *evaluated* price |
| `DECISION_AGED_OUT` | no change, but the latest decision is older than `decision_max_age_seconds` |

No reasons ⇒ `NO_MATERIAL_CHANGE`: no model call, no new decision record, and a
lightweight cycle receipt only.

### Policy `reevaluation-policy/1.0.0`

Operational bounds, not trading thresholds. Overrides are allowlisted integers
within fixed ranges; unknown keys are rejected.

| Field | Default |
|---|---|
| `runtime_min_cadence_seconds` (not overridable) | 60 |
| `model_min_interval_seconds` | 60 |
| `price_move_bps` | 50 |
| `decision_max_age_seconds` | 900 |
| `candidate_refresh_min_seconds` | 300 |
| `min_state_dwell_seconds` | 300 |
| `max_action_calls_per_cycle` | 2 |
| `max_model_calls_per_cycle` | 3 |
| `max_held_per_cycle` | 10 |
| `max_model_calls_per_hour` | 30 |
| `max_model_calls_per_day` | 120 |
| `lease_seconds` (not overridable) | 180 |

### Duplicate-entry control

A cycle never opens a second entry path for the same state:

- held position and a re-proposed ENTER → gate yields `REVALIDATION_REQUIRED`
  (`ILLEGAL_POSITION_ACTION`), classified `DUPLICATE_SUPPRESSED`;
- pending/submitted/partially filled order → deterministic
  `PENDING_ORDER_REVALIDATION`, no model call;
- a still-valid ENTER whose only changes are price drift or age →
  `ACTIVE_ENTER_UNEXPIRED`, no model call, no new record;
- the matched Opportunity already consumed in the ledger →
  `OPPORTUNITY_ALREADY_CONSUMED`, no model call, no new record.

The OCT1-06 handoff, Workspace preview and both Paper boundaries are unchanged and
still revalidate independently.

### Churn control and safety precedence

After a change **into** ENTER, EXIT or HOLD, non-safety reevaluation of that
instrument is held for `min_state_dwell_seconds` and recorded as
`CHURN_SUPPRESSED` (`MIN_STATE_DWELL`) with no model call. Returning to the
evaluated baseline is simply unchanged.

Safety reasons always bypass the dwell (`SAFETY_PRECEDENCE`):
`POSITION_CHANGED`, `PENDING_ORDER_APPEARED`, `QUOTE_LOST`, `AUTHORITY_LOST`,
`EXIT_CONDITION_MET`, `SMA_TRAILING_STOP_BREACHED`. Becoming unsafe bypasses; recovering does not, so
`HOLD → EXIT` is immediate while the flip back is held.

Precedence inside one instrument: dwell/safety → deterministic fail-safe
(pending, stale quote, authority loss; no model) → duplicate checks → engine and
budget caps → model evaluation.

### Stop monitor in the cycle (OCT1-08)

For every held instrument the cycle first evaluates the
[SMA trailing stop](PAPER_SMA_TRAILING_STOP.md): position, completed bars,
stop, breach check. `SMA_TRAILING_STOP_BREACHED` is a safety reason: it
bypasses the dwell, the deterministic fail-safe and the model availability and
budget gates, and appends a server-authored EXIT with no model call. The same
breach on the same holding is not recorded twice
(`STOP_EXIT_ALREADY_RECORDED`). Stop initialization, tightening, staleness and
resumption enter the material fingerprint but are recorded as
`DETERMINISTIC_STOP_UPDATE` without a model call; an unchanged stop is not a
change. Stops whose position is no longer held are closed at the start of the
cycle.

### Transition classification

`UNCHANGED`, `MATERIAL_EVIDENCE_CHANGED`, `STATE_CHANGED`, `POSITION_CHANGED`,
`CANDIDATE_ADDED`, `CANDIDATE_REMOVED`, `DUPLICATE_SUPPRESSED`,
`CHURN_SUPPRESSED`, `REVALIDATION_REQUIRED`, plus the runtime outcomes
`BUDGET_BLOCKED`, `MODEL_UNAVAILABLE` and `DEFERRED`.

### Model and provider bounds

- Model calls are counted from persisted receipts per cycle, and per rolling
  hour and rolling day across **every loop of the Paper account**, so
  reconfiguring the scope does not start a fresh budget. The provider's own
  daily request/token budget still applies. Exhausted ⇒ `BUDGET_BLOCKED`, deterministic checks continue, no
  request is sent, the baseline is not advanced so the work is retried.
- No configured engine ⇒ `MODEL_UNAVAILABLE`. The loop never switches provider.
- Deterministic fail-safe revalidation needs no model and is never blocked.
- The loop never refreshes shared News providers (`refresh_news=False`); it
  observes material changes in the shared News state.
- Evidence reads per cycle are constant in the number of candidates.

### Cycle receipt `reevaluation-cycle/1.0.0`

Bounded (≤32 kB, ≤24 transitions): `cycle_id`, `loop_id`, `trigger`,
`scheduled_for`, `started_at`, `completed_at`, `start_drift_ms`, `duration_ms`,
`requested_cadence_seconds`, `effective_cadence_seconds`, `session_state`,
`session_date`, `scope_ref`, `evidence_cutoff`, `position_count`,
`candidate_count`, `intake_count`, `material_change_count`, `unchanged_count`,
`model_call_count`, `missed_ticks_before`, `counters` (proposed, accepted,
duplicate suppressions, churn suppressions, model calls avoided), `transitions[]`
(prior/new decision refs and states, reasons, model call, safety),
`provider_states[]`, `readiness`, `budget_state`, `not_observed`, `cycle_status`,
`reason_codes[]`.

`cycle_status`: `NO_MATERIAL_CHANGE`, `MATERIAL_CHANGE`, `BUDGET_BLOCKED`,
`MODEL_UNAVAILABLE`, `FAILED`, `NOT_OBSERVED`.

## Cadence truthfulness

`effective = max(requested, runtime minimum, model minimum interval)`; the
limiting constraint is named and `degraded` is set when effective > requested.
Both values are on every receipt and in the UI.

`provider_states[]` carries one row per capability with its own provider, delivery
mode, freshness status and policy, latest `as_of`, age, next useful refresh, and:

| `cadence_semantics` | Meaning |
|---|---|
| `CURRENT` | current-market role, non-delayed delivery |
| `DELAYED` | current-market role from a delayed provider |
| `REFERENCE` | reference context (for example News) |
| `PUBLICATION_BASED` | source-publication cadence (for example Treasury) |
| `BLOCKED` | not admissible at the cutoff |

`within_requested_cadence` is true only for `CURRENT` evidence whose age is within
the requested cadence. Readiness is `REEVALUATION_READY`, `_DEGRADED` (delayed or
older quote, a blocked capability, or a slower effective cadence) or `_BLOCKED`
(no admissible quote, engine unavailable, budget exhausted). Reference
capabilities are never required to tick.

A stale quote on a scheduled tick produces `REVALIDATION_REQUIRED`
(`QUOTE_STALE_OR_UNAVAILABLE`) with no model call and no handoff authority.

## Worker, lease and liveness

- **Operator controlled.** Configure, Start, Stop, Run Once, Status. Nothing
  starts when the app or a panel opens, or after a restart.
- **Schedule.** Slots are `anchor + n × effective`. One thread. If a cycle runs
  past later slots those slots are **skipped** (never run late, never overlapped);
  the next receipt carries `missed_ticks_before` and `CYCLE_OVERRAN`, and the long
  cycle carries `CYCLE_EXCEEDED_CADENCE`.
- **Single owner.** One loop per (account, scope hash, policy). `acquire_lease` is
  atomic; a live lease held by another owner rejects Start, Stop and Run Once with
  `REEVALUATION_LOOP_ALREADY_OWNED`. The worker heartbeats while waiting; a lease
  that is not renewed expires after `lease_seconds` and can be taken over without
  manual cleanup. A displaced owner's scheduled cycle fails `REEVALUATION_LEASE_LOST`.
- **Liveness.** `worker_state` is `NOT_CONFIGURED`, `STOPPED`, `RUNNING`,
  `DELAYED` (no completion for more than two cadences), `STALLED` (lease held but
  worker not alive), `RUNNING_ELSEWHERE` or `INTERRUPTED` (should be running, no
  live owner). Recorded: last scheduled/started/completed/successful tick, last
  status, last error, missed ticks, heartbeat, lease expiry.
- **Downtime stays downtime.** On Start after a gap one `NOT_OBSERVED` receipt is
  written with the interval, the count of scheduled slots missed and the reason
  (`PROCESS_DOWNTIME`, `OPERATOR_STOPPED`, `RUNTIME_STALLED`);
  `decisions_backfilled` is always 0. The loop resumes at the restart instant.
- **Failures** are recorded as `FAILED` receipts with a stable code; a dead worker
  shows as `STALLED` with `last_error`.

## Persistence

Tables on the existing local-state database: `next_session_records`,
`next_session_observations`, `reevaluation_cycles`, `reevaluation_loops`.
Configuration, loop baselines, locked snapshots, observations, receipts and (via
OCT1-06) action history survive restart. With persistence off the same contract
runs in memory and reports `INTENTIONAL_EPHEMERAL`.

History is newest-first, limited to 100 per request, with a `before` cursor and a
session-date filter.

## Execution safety

Reevaluation produces decisions and receipts only. It has no preview, handoff,
order or submit path and imports none. Paper execution remains the explicit
OCT1-06 handoff through Workspace; Live authority is unchanged. Position is always
read from the current Paper ledger, never inferred from a prior decision.

## API

All routes are scoped to the Paper ledger account. Reads use `audit.read`;
mutations use `state.write`. None carries `paper.order.submit`.

| Route | Purpose |
|---|---|
| `POST /screener/next-session/draft` | `{decision_id, evaluation_policy?}` |
| `POST /screener/next-session/lock` · `/observe` · `/evaluate` | `{snapshot_id}` |
| `GET /screener/next-session?id=` · `?instrument=` | one view · bounded history |
| `POST /screener/reevaluation/configure` | `{scope, requested_cadence_seconds, policy?}` |
| `POST /screener/reevaluation/start` · `/stop` · `/run-once` | `{}` |
| `GET /screener/reevaluation/status[?readiness=1]` | liveness, cadence, engine, readiness |
| `GET /screener/reevaluation/history?limit=&before=&session_date=` | bounded receipts |

## Hardening (OCT1-12)

- **Held positions are never dropped.** Every held instrument is evaluated each
  cycle, least recently seen first, up to `max_held_per_cycle`; above the bound
  the rest rotate in on the following cycles and the receipt carries
  `HELD_POSITION_CAP_EXCEEDED`. A held instrument outside the bounded intake or
  no longer selected gets its own targeted evidence read. Evidence that stays
  unavailable is noted again every `decision_max_age_seconds`
  (`HELD_INSTRUMENT_EVIDENCE_UNAVAILABLE`), not once.
- **Held instruments keep a quote subscription without a page.** Each cycle
  refreshes the held-position marks and their `paper-portfolio-marks`
  subscription. It never creates the live runtime and never touches the
  execution gate; failure is `HELD_QUOTE_SUBSCRIPTION_FAILED` on the receipt.
  Selected candidates that are not held are **not** subscribed by the loop:
  their quote is current only while a Screener window owns it.
- **A failed evidence read is not a skipped stop.** If the Screener read raises,
  the cycle ends `REEVALUATION_BLOCKED` with `EVIDENCE_READ_FAILED`: no model
  call, no baseline change, and the SMA stop monitor still runs for every held
  instrument from its own bar and quote sources.
- **Lease fencing.** A scheduled cycle writes loop state only while it still
  owns the lease, and renews the lease before each model call. A cycle displaced
  mid-flight records a `FAILED` receipt with `REEVALUATION_LEASE_LOST` (any model
  call it already made stays counted), leaves the new owner's baselines
  untouched and ends its worker.
- **Quote recovery is dwelled.** `QUOTE_RESTORED` waits `min_state_dwell_seconds`
  from the recorded loss, and a repeated loss inside that window is not
  re-recorded: a quote flapping around the freshness window costs at most one
  model call per dwell per instrument.
- A duplicate receipt id is `REEVALUATION_RECEIPT_IMMUTABLE` on both backends.

### Operator requirement for a live session

**KEEP THE SCREENER OPEN DURING THE LIVE CANDIDATE-SELECTION PHASE.** A selected
candidate that is not held has a current quote only while a Screener window owns
its subscription; with the window closed its quote goes `STALE` and ENTER is
blocked. Held Paper positions do not need the window: the loop keeps their quote
subscription and SMA stop monitor on the server.

## Limitations

- Calendar coverage is 2025–2026 with no early-close list; next-session supports
  US equities and ETFs only.
- The worker is a thread in the UI API process with a SQLite lease: single host.
  After a crash a new process waits out the previous lease (≤180 s).
- Model-call caps are per Paper account on this host's local-state database.
- A quote is `STALE` when the feed has delivered nothing for 5 s or the provider
  event is older than 60 s. A selected candidate with no Screener window open is
  therefore blocked from ENTER; only held instruments are subscribed by the loop.
- `price_move_bps`, dwell and age defaults are operational choices that have not
  been tuned against real market sessions.
- One-minute behaviour against live providers and a real model runtime has not
  been empirically validated; see the OCT1-07 report. OCT1-12 exercised the
  cycle on the real Screener row/cache evidence path under a controlled clock
  (`tests/platform/test_reevaluation_live_evidence.py`); a regular-session run
  is still `NOT_OBSERVED`.
