# Autonomous Paper operations (AUTO-01)

One server-owned controller that runs the existing Screener, AI and Paper
authorities unattended, for **internal Paper simulation only**. It is
implemented in `ui_api/paper_automation.py`, with pure policy in
`intelligence/inference/paper_automation.py` and durable state in
`local_state/paper_automation.py`.

It adds an owner policy, an explicit arming record, a schedule and an adapter.
It adds no decision logic, no risk engine, no simulator and no order route.

```text
owner policy -> arm -> start
  every cadence slot, while the session is eligible:
    Paper-only identity check          (account, experiment, mode, provider, env)
    provider health                    (existing live runtime state)
    reconcile working automation orders
    full-universe AI run               (existing run tracker; owner interval; owner spend cap)
      -> adopt only a complete selection
    reevaluation cycle                 (existing OCT1-07 cycle, driven; stops per OCT1-08)
      -> Action Decisions              (existing OCT1-06 gate)
    Paper adapter, exits first         (existing handoff -> preview -> risk -> submit -> ledger)
    record the cycle, every refusal and its reason
```

## What it reuses

| Concern | Authority | Reused as |
|---|---|---|
| Candidate discovery over the whole query | [Full-universe coverage](SCREENER_AI_FULL_UNIVERSE_COVERAGE.md), `AiScreenerRuns` | started or joined by the controller; result read unchanged |
| Recurring evaluation, material change, churn, model caps | [Reevaluation](SCREENER_REEVALUATION.md) | the same cycle, driven instead of threaded |
| ENTER / HOLD / EXIT and every blocker | [Action Decision](SCREENER_ACTION_DECISION.md) | `ScreenerActionService.run` and `handoff` |
| Deterministic stop exits | [SMA trailing stop](PAPER_SMA_TRAILING_STOP.md) | evaluated inside the cycle, as before |
| Entry sizing authority | BUILD 22 pre-trade risk engine via `assess_entry_risk` | may only reduce the adapter's quantity |
| Preview, risk, submit, fills, ledger | [Paper decision lifecycle](PAPER_DECISION_LIFECYCLE.md), `paper_projections` | `preview_paper_order`, `submit_paper_order`, `cancel_paper_order` |
| Account, capital, valuation, P&L | [Paper portfolio experiment](PAPER_PORTFOLIO_EXPERIMENT.md) | the active experiment's portfolio-scoped ledger |
| Sessions | `market_sessions.us_equity_session_label`, the frozen 2025–2026 holiday calendar | regular session only |

## Paper-only boundary

`paper_identity` is evaluated at arm, at start, at the top of every cycle and
again immediately before every order. Any failure blocks with a stable code:

| Code | Condition |
|---|---|
| `LIVE_EXECUTION_ENVIRONMENT_ENABLED` | `IMP_LIVE_EXECUTION` is set |
| `BROKER_PAPER_ENVIRONMENT_ENABLED` | `IMP_BROKER_PAPER_EXECUTION` is set |
| `EXECUTION_MODE_NOT_INTERNAL_SIMULATION` | the ledger is not the internal simulator |
| `EXECUTION_PROVIDER_NOT_INTERNAL` | the ledger's provider is a broker |
| `ACTIVE_PAPER_EXPERIMENT_REQUIRED` | no active portfolio-scoped Paper experiment |
| `AUTOMATION_ACCOUNT_MISMATCH` | the account or experiment is not the one the policy was bound to |
| `PAPER_RISK_POLICY_CHANGED` | the ledger's risk policy changed since the policy was configured |

The controller imports no broker, live-order or gateway module. Its only
submit call is `paper_projections.submit_paper_order`, under the same lock the
`POST /paper/orders` route holds, with the same preview binding, Action
provenance revalidation, pre-trade admission and risk path. The cancel route's
broker branch is refused before it is reached, including on Emergency Stop.
LIVE-001 and every Live gate are unchanged.

## Owner policy `paper-automation-policy/1.0.0`

Every field is required. Nothing has a default and unknown fields are refused;
an incomplete body is answered once with every missing field named
(`AUTOMATION_POLICY_INCOMPLETE:a,b,…`). A policy is immutable, bound to one
account, one experiment and the ledger risk-policy hash, and identified by
`PAP-<hash>`.

| Section | Fields |
|---|---|
| `scope` | the Screener query (universe, filters, sort); the experimental staged method is refused |
| `schedule` | `sessions` (`REGULAR` only), `cadence_seconds` (60–3600), `universe_evaluation_interval_seconds` (300–86400), `no_new_entries_minutes_before_close` |
| `risk` | `max_position_notional_minor`, `max_aggregate_exposure_minor` (≤ experiment capital), `max_open_positions`, `max_daily_loss_minor`, `max_per_trade_risk_minor`, `assumed_adverse_move_bps`, `allowed_universes` (`US_EQUITIES`, `US_ETFS`), `order_types` (`MARKET` only), `allow_long`, `allow_short` (only if the Paper account allows it), `allow_entries`, `allow_exits` |
| `exits` | `on_stop_breach`, `on_thesis_exit` |
| `ai` | `allow_local_inference`, `allow_paid_inference`, `max_paid_requests_per_day`, `max_paid_tokens_per_day` |
| `emergency_stop` | `max_consecutive_failures` (1–20) |

The existing governed limits stay in force underneath and are not restated by
the policy: the ledger's `max_order_shares`, `max_position_shares` and
`max_open_orders`, and the BUILD 22 NAV, concentration and exposure fractions.

## Arming and controls

Configuring stores a policy and arms nothing. Arming is a separate recorded act:
`{policy_id, acknowledgement: "ARM_PAPER_ONLY_AUTOMATION"}` for exactly the
currently configured policy. The arming record (`PAA-…`) names the policy,
account, experiment, time and operator. A policy cannot be replaced while
armed; a new policy needs a new arming.

`operator` is optional and informational: it is recorded with the arming and
shown to the owner, and it is never an authorization. Authorization is the
request's capability (`paper.order.submit`) checked against the authenticated
principal before the handler runs, plus the controller's own `paper_identity`
check before any action. A client-supplied name therefore does not stand in for
the owner's authorization and cannot widen what the caller may do.

| Control | Effect |
|---|---|
| `configure` | store a complete policy; refused while armed |
| `arm` | record authorization of the current policy; starts nothing |
| `start` | take the lease, attach the reevaluation loop, begin scheduling |
| `pause` / `resume` | cycles are skipped / run again; the lease and the loop stay |
| `stop` | stop scheduling, stop an automation-started AI run, release quotes, loop and lease |
| `disarm` | stop, then clear the arming and any emergency latch |
| `emergency-stop` | latch first, then stop; cancel working automation orders; **never liquidates** |

Pause, Stop, Emergency Stop and Disarm are re-read before every order inside a
running cycle. An emergency latch survives restart and is cleared only by
Disarm. The controller latches it itself after
`max_consecutive_failures` failed cycles.

## Status

One primary state, derived by `derive_status`:

`NOT_CONFIGURED` · `DISARMED` · `STOPPED` · `PAUSED` · `EMERGENCY_STOPPED` ·
`WAITING_FOR_MARKET` · `BLOCKED_BY_AUTHORITY` · `BLOCKED_BY_DATA` ·
`BLOCKED_BY_RISK` · `BLOCKED_BY_BUDGET` · `RUNNING` · `ERROR`

`RUNNING` means this process holds the lease, its worker is alive, the session
is eligible, the last cycle completed without error and no blocker is open. A
controller that should be running but has no live worker here is `ERROR`
(`CONTROLLER_NOT_ALIVE` or `RUNNING_ELSEWHERE`), never `RUNNING`.

The primary state is one label; the same read also returns `blockers`, a list of
independently open `{category, code}` entries. They can be open while the
primary state says something else: outside the configured session the state is
`WAITING_FOR_MARKET`, and the blockers the last evaluating cycle observed are
carried into that read instead of being dropped, so a closed market never hides
a data, risk or spending block that will still be open at the bell. The carry
names the cycle that observed the entries: on the cycle summary they are
`blockers_from_cycle_id` and `blockers_observed_at` (inside `last_cycle`), and
the status read's own `blockers` are those same entries.

Nothing is evaluated outside the session to refresh them, so an entry a later
cycle would clear stays visible until the next evaluating cycle. In particular a
last-observed `AUTHORITY` entry outranks the session check, so it keeps
`BLOCKED_BY_AUTHORITY` as the primary state until then. That is deliberate: the
controller re-checks Paper authority, provider data, risk and budget only inside
a cycle, and it is conservative in the safe direction. Read the state and the
blockers together; the state label alone is not a complete readiness answer.

## Schedule, lease and restart

- Slots are `anchor + n × cadence`. A cycle that overruns skips the slots it
  covered; they are counted as missed, never run late and never overlapped.
- One owner per Paper account: a SQLite lease (180 s) renewed by the worker
  between slots and by the cycle itself at its start, before each order and at
  its end. A second process is refused `AUTOMATION_ALREADY_OWNED`.
- A controller row belongs to one **generation**: the recorded arming plus the
  run that arming started. A cycle reads, acts and writes back only for its own
  generation, compared before every order and again at its write-back. A cycle
  still in flight when the owner disarms, configures, re-arms and starts is
  therefore superseded: it cannot submit under the new authorization, cannot
  renew the old lease, and cannot record its cycle state (`last_cycle`,
  `cycle_count`, failure count, subscriptions, adopted universe) over the new
  run. A new run starts with no inherited cycle outcome, so a superseded
  generation's failure cannot make the new run read as `ERROR`.
- If a superseded cycle's own consecutive failures had tripped the controller
  latch, the latch is not applied to the replacement generation, but it is not
  dropped silently either: it is recorded as `EMERGENCY_LATCH_SUPERSEDED` with
  its cause, failure count and the generation that replaced it. The new run
  counts its own failures from zero.
- Outside the configured session nothing is evaluated, no model is called and
  no run is started. Positions are **not** flattened at the close.
- `resume_on_startup` runs after warmup in `tools/ui1/run_ui_api.py`. It
  continues only a controller that was armed and running, and only if every
  start check passes again. A refusal is recorded (`STARTUP_RESUME_REFUSED`)
  and leaves the controller stopped. Prior authorization never overrides a
  changed safety condition.
- A restart inside the predecessor's lease (the old process exited without
  releasing it) is not a refusal: the resume records
  `STARTUP_RESUME_WAITING_FOR_LEASE` with `lease_until`, waits out the lease
  (at most 180 s plus a few seconds of grace) on a background thread, re-reads
  the controller and then runs the normal start checks. A controller stopped,
  disarmed or emergency-latched during the wait is not resumed; a predecessor
  that is still renewing keeps the lease and the refusal is recorded.
- Downtime is one `NOT_OBSERVED` event with the window and the count of missed
  slots, `evaluations_backfilled: 0` and `orders_backfilled: 0`.
- The day's starting equity is captured at the first cycle of a session date
  and persisted, so a restart inside the day keeps the daily-loss reference.

## AI evaluation

- Candidates come **only** from an adopted full-universe selection. While the
  loop is driven, the first-50 intake reduction is not run and a previous
  intake-head selection is dropped on attach.
- Since 2026-10-24 that run sends the model only the
  [opportunity shortlist](SCREENER_AI_FULL_UNIVERSE_COVERAGE.md#opportunity-shortlist):
  every eligible row is scored without a model, and the top 20 (local engine) or
  50 (paid engine) go to the model, which still makes the final pick. Rows left
  out are `NOT_SHORTLISTED`; they are not "eligible" for the coverage epoch
  below, so they never hold it open.
- A run is started (or an operator's run joined) when
  `universe_evaluation_interval_seconds` has passed. Its terminal coverage is
  recorded as it is: counts, percentage, status, model, tokens.
- On the local engine every run is a **rolling slice**: its first pass ends at
  40% of the scope's `universe_evaluation_interval_seconds`, rows with no recent
  turn go first, then the least recent turn (see
  [coverage](SCREENER_AI_FULL_UNIVERSE_COVERAGE.md#rolling-slices-local-engine-automation-only)).
  Each scope keeps a **coverage epoch** in its controller state: the ids of its
  last 16 finished runs plus compact per-instrument last-evaluation and last-turn indexes derived from immutable ledger outcomes. Those indexes survive pruning and process restart, so full-universe sweeps cannot forget early turns and starve later names. The state also keeps the
  epoch number, its start and the count of completed epochs. A row has had its
  **turn** when the model answered it (`AI_EVALUATED` or `AI_REJECTED`) or it
  could not be sent alone (`UNPROCESSED:BATCH_FAILED:LOCAL_CONTEXT_EXCEEDED`); a
  row only deferred or stopped has not. An epoch completes
  (`UNIVERSE_EPOCH_COMPLETED`, with `eligible`, `evaluated` and `turns`) when
  every row the latest run found eligible has had its turn since the epoch
  began. Under the earlier rule (evaluated only), rows the validator kept
  rejecting held the epoch open and headed every slice, and the rows already
  evaluated were never refreshed (October 17–18). `UNIVERSE_RUN_FINISHED`
  carries the slice and epoch counts, with `evaluated_in_epoch` and
  `turns_in_epoch` apart.
- Only `coverage_complete` and `selection_complete` results, or a
  `SLICE_SELECTION_COMPLETE` result with `slice_complete`, are adopted, and only
  while the selection's state is `CURRENT`. A partial, stopped, failed,
  budget-refused or interrupted run is recorded with `adopted: false` and
  contributes no candidates. A complete run that selected nothing clears the
  selection; a slice that selected nothing does not (it says nothing about rows
  it did not reach) and is not backed off. Held positions stay monitored.
- An adopted selection is a **hypothesis**: it carries its provenance (run,
  status, reduction answer, decision cutoff, evidence expiry, model, prompt,
  slice) and lives two separations. When its lifetime ends without a newer
  adoption, its instruments are removed (`SELECTION_HYPOTHESIS_EXPIRED`). An
  entry still needs a fresh Action Decision on newly acquired evidence, the
  governed opportunity, risk and preview revalidation; adoption grants none of
  them.
- With several scopes, one scope's unfinished run defers the others
  (`SHARED_ACCOUNT_RUN_ACTIVE`): the account has one run tracker slot. Each
  scope is separated from **its own** last start, so time-boxed slices of two
  scopes alternate instead of one scope waiting a full separation after the
  other. Each cycle closes a scope's run handle once that run has finished or
  its owning process is gone, including outside the scope's session; nothing is
  started or evaluated there, and a still-running run keeps deferring the
  others.
- Action Decisions are **not** withheld while a universe run is active. The
  local runtime admits one request at a time, so a decision waits at most for
  the batch in flight and then reads its own fresh evidence.
- `spending_gate` decides whether the selected engine may be called at all:
  local inference needs `allow_local_inference`; paid inference needs
  `allow_paid_inference`, a readable shared budget, and usage below the tighter
  of the owner's daily cap and the shared daily allowance. A refusal sends no
  request and shows as `BLOCKED_BY_BUDGET`.
- An unattended paid run carries a `spend_limit`: the coverage method refuses a
  plan larger than it **before any hold or model call**
  (`AI_COVERAGE_BUDGET_INSUFFICIENT`, reason `AUTONOMOUS_SPENDING_LIMIT`). The
  limit can only refuse; it never widens the shared allowance.
- Per-instrument proposal calls stay under the reevaluation policy's existing
  per-cycle, hourly and daily caps.
- Selected candidates are given a server-owned quote subscription
  (`paper-automation-candidates`) so they do not depend on an open browser
  page. A refused subscription is recorded and the candidate stays unquoted.

## Paper adapter

For each held instrument and each selected candidate, the latest unexpired
Action Decision in `ENTER` or `EXIT` with `PREVIEW_ALLOWED` is walked once
through the canonical path. Exits run before entries.

1. One intent per decision per account: `PAI-<hash(account, decision)>`, which
   is also the order's `client_order_id` and idempotency key.
2. Identity and authority are checked again; then `decision_permitted`.
3. Entries only: `entry_risk_blockers` (entries enabled, open positions,
   current valuation and exposure, daily loss, no working orders, entry window).
4. `ScreenerActionService.handoff` revalidates evidence, expiry, position and
   authority. A changed input defers the intent and asks the loop to decide
   again; a stale decision is never executed as it stands.
5. Entries only: `size_entry` takes the smallest of the owner bounds, buying
   power and the ledger share caps, and names the binding bound.
6. `preview_paper_order`. If the pre-trade risk engine approves less, the
   adapter previews once more at the approved size. Anything other than a
   passing preview blocks.
7. Controls are re-read, then `submit_paper_order` under the ledger lock.
8. A working remainder is cancelled: the simulator fills once at submission.

**One decision is one order, ever.** A crash between the ledger write and the
intent record is recovered by the ledger's idempotency lookup, which adopts the
existing order. An entry whose order was rejected or partly filled is not
chased. An exit whose order ended unfilled leaves risk open, so the loop is
asked for a new decision (`request_redecision`); the new EXIT decision gets its
own single order, spaced by a per-instrument backoff of `cadence × 2ⁿ`, capped
at 900 s.

The order's `decision_source_snapshot` carries the Action Decision and snapshot
(as a manual handoff does) plus `PAPER_AUTOMATION_POLICY` and
`PAPER_AUTOMATION_ARMING`, so every automated order names the policy and the
authorization it was placed under.

`max_per_trade_risk_minor` bounds the size at the owner's assumed adverse move.
It is a sizing bound, not a loss guarantee. A stop is not a guaranteed fill: an
exit fills at the bar the simulator observes, and with no bar it fills nothing.

## Not implemented

- **No liquidation rule.** Reaching the daily-loss limit halts entries. It does
  not close positions, and neither does the session close or Emergency Stop.
  Automatic exits are exactly: a breached SMA trailing stop, and a gated EXIT
  decision.
- **No entry without a governed Opportunity.** The Action Decision gate still
  requires an `OpportunityV1` that shares the candidate's evidence lineage
  (`NO_GOVERNED_OPPORTUNITY`). Nothing here mints one.
- **No strategy feedback.** The report describes outcomes. It changes no
  policy, limit, prompt, model or method.

## Records

| Table | Content |
|---|---|
| `paper_automation_policies` | immutable policy versions |
| `paper_automation_controllers` | one row per account: desired state, arming, emergency latch, day reference, universe run state, lease |
| `paper_automation_events` | append-only audit: configuration, arming, starts, session activation, universe runs, cycles that acted or changed status, every intent outcome, cancels, downtime |
| `paper_automation_intents` | one row per decision; `SUBMITTED` is terminal |

Existing reevaluation receipts, Action Decisions, decision traces, risk
decisions, ledger events and experiment snapshots are written by their own
authorities, unchanged.

## API

All routes are scoped to the Paper ledger account.

| Route | Capability |
|---|---|
| `GET /paper/automation/status` · `/history?limit=&before=&kind=` · `/report` | `audit.read` |
| `POST /paper/automation/arm` · `/start` · `/resume` | `paper.order.submit` |
| `POST /paper/automation/configure` · `/disarm` · `/pause` · `/stop` · `/emergency-stop` | `state.write` |

`GET /paper/automation/report` is `SIMULATED_PAPER_FILLS_NOT_MARKET_TRUTH`:
fills, costs, realized and unrealized P&L, win and loss counts, drawdown over
persisted snapshots, refusals by reason, decision origin and AI usage. It is
accounting of simulated fills, not evidence of a profitable strategy or a
durable edge.

## Governed live forecast admission

The optional `paper_forecast_build.py` path consumes the prospective live
feature corpus, separately from historical development corpora and Item 9
calibration receipts. It splits each instrument chronologically 60/20/20,
embargoes later decisions through earlier label availability, and requires
at least 60 untouched holdout outcomes with strictly positive Brier skill
against the training base rate (`path-a-live-holdout-brier-skill/1`). It does
not change the independent Action Decision, Opportunity, Paper risk or submit
gates. No eligible artifact means no forecast-backed entry Opportunity.

At runtime `LiveForecastHook` checks the stored holdout scores against that
same rule, exact instrument identity, integral sample count, finite skill and
matching reported holdout count before loading the hash-bound specialist and
calibrator. An `eligible` flag alone cannot admit an artifact. Corpus loading
preserves integer labels and nanosecond times without coercion, binds snapshots
to row identity and decision time, and rejects unknown schemas or conflicting
duplicate rows. Identical duplicate rows remain idempotent.

On its first tick after restart, the recorder joins existing decision/label
identities one daily file at a time, retaining only compact references and
capping each recovery index and the pending list at 10,000 decisions. It restores
only unresolved decisions whose horizon is still in the future, with their
original reference and clocks, and restores the last recorded grid to avoid
duplicate capture. A past horizon without the lost window's terminal evidence
is explicitly `UNLABELABLE` with
`RECORDER_RESTART_TERMINAL_EVIDENCE_UNAVAILABLE` and the actual `recovered_at_ns`;
it never becomes a training label. Restored pending rows, grid state and recovery counters become visible only after
the entire scan succeeds. A later-file failure cannot leak pending rows into a
retry; already-appended past outcomes are discovered as existing labels and
preserved. An oversized
recovery file fails closed before that file's recovery outcomes are written.

The current live strategy and recorder are equity-specific: Moomoo quote/trade
observations during the regular US session, with a 300-second feature window,
30-second decision grid, and 300-second direction horizon. The terminal quote
must arrive within the existing 60-second tolerance. This path does not confer
crypto compatibility or relabel historical evidence as prospective evidence.

Regression coverage: `tests/intelligence/test_live_forecast_boundary_checks.py`,
`test_live_forecast_admission_integrity.py`, `test_live_forecast_training.py`
and `test_live_feature_corpus.py`.

## Limitations

- Regular US session, US equities and ETFs, market orders, the experiment
  account only. No early-close list exists in the calendar: the 16:00 ET close
  is used, so the entry window is wrong on half days.
- Single host: the worker is a thread in the UI API process with a SQLite
  lease. After a crash a new process waits out the lease (≤180 s).
- After an entry changes the account, another candidate's pending ENTER is
  decided again and waits out the reevaluation dwell (default 300 s).
- Under the default shared allowance a paid full-universe run completes only
  for small filtered queries; see
  [coverage budget](SCREENER_AI_FULL_UNIVERSE_COVERAGE.md#budget).
- Behaviour is proven with controlled fixtures
  (`tests/trading_correctness/test_paper_automation.py`,
  `tests/intelligence/test_paper_automation_policy.py`,
  `tests/platform/test_paper_automation_universe.py`). Unattended behaviour
  against live providers and a real model in a regular session is
  `NOT_OBSERVED` until a live acceptance run records it.
- A controller self-latch after `max_consecutive_failures` failed cycles is
  written only when the cycle was not superseded. If the owner disarms,
  configures, re-arms and starts during that same failing cycle, the latch is
  not applied to the new run: the superseded generation's latch is recorded as
  `EMERGENCY_LATCH_SUPERSEDED` and each of the new run's own failing cycles is
  counted again from zero. The interleaving is covered in
  `tests/trading_correctness/test_paper_automation.py` by
  `test_a_failing_generation_cannot_latch_or_report_over_the_generation_that_replaced_it`,
  with `test_a_failing_generation_still_latches_its_own_generation` as the
  negative control.
- `derive_status` reports one primary state, and `WAITING_FOR_MARKET` is checked
  before the DATA, RISK and BUDGET blockers, so the primary label alone does not
  name a simultaneous blocker while the session is closed. The blockers
  themselves are returned, and the last evaluating cycle's blockers are carried
  across the closed session rather than cleared, so an operator reading the
  state and the blockers together sees both.
