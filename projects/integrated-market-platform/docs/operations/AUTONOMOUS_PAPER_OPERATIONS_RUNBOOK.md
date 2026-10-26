# Runbook: Autonomous Paper operations (AUTO-01)

**Audience:** operator. **Mode:** internal Paper simulation only. **Authority:** the
architecture contract is [PAPER_AUTOMATION.md](../architecture/PAPER_AUTOMATION.md); this
runbook is the operating procedure and does not restate it. Non-negotiable mode rules are in
[MODE_AUTHORITY.md](../architecture/MODE_AUTHORITY.md). General platform troubleshooting is in
[RUNBOOK.md](RUNBOOK.md).

One server-owned controller runs the existing Screener, AI and Paper authorities unattended.
It adds no decision logic, no risk engine, no simulator and no order route. It submits only
through the canonical Paper path (`preview_paper_order` → pre-trade risk → `submit_paper_order`)
under the same ledger lock the `POST /paper/orders` route holds, and it imports no broker or
live-order module. **Real-money execution is not reachable from this controller.**

## 1. Before you touch anything

- The controller is per **Paper account**. If you see `AUTOMATION_ALREADY_OWNED`, another
  process holds the 180 s lease for that account: find it, do not force the lease.
- Nothing is scheduled while it is disarmed or configured-but-not-armed. Configuring stores a
  policy and arms **nothing**.
- Read the status payload before acting: the primary `status` plus the separate `blockers`
  array can both be meaningful at once (see §4).

## 2. Configure a policy

Every field is required. There are no defaults, unknown fields are refused, and an incomplete
body is answered once with every missing field named
(`AUTOMATION_POLICY_INCOMPLETE:<field>,…`). A policy is immutable, is bound to one account,
one experiment and the ledger's risk-policy hash, and is identified as `PAP-<hash>`.

- `scope` — the Screener query the controller will evaluate. The experimental staged method is
  refused.
- `schedule` — `sessions` (`REGULAR` only), `cadence_seconds` (60–3600),
  `universe_evaluation_interval_seconds` (300–86400),
  `no_new_entries_minutes_before_close`.
- `risk` — `max_position_notional_minor`, `max_aggregate_exposure_minor` (≤ experiment
  capital), `max_open_positions`, `max_daily_loss_minor`, `max_per_trade_risk_minor`,
  `assumed_adverse_move_bps`, `allowed_universes`, `order_types` (`MARKET` only), `allow_long`,
  `allow_short`, `allow_entries`, `allow_exits`.
- `exits` — `on_stop_breach`, `on_thesis_exit`.
- `ai` — `allow_local_inference`, `allow_paid_inference`, `max_paid_requests_per_day`,
  `max_paid_tokens_per_day`.
- `emergency_stop` — `max_consecutive_failures` (1–20).

The governed limits underneath are **not** replaced by the policy: the ledger's
`max_order_shares`, `max_position_shares` and `max_open_orders`, and the deterministic risk
engine's NAV, concentration and exposure fractions, all still apply. A per-trade risk limit
sizes the order; it does not guarantee the loss, and a stop is not a guaranteed fill.

## 3. Arm, then start — two separate acts

1. **Arm** is a recorded authorization of exactly the policy that is configured now. It
   requires the acknowledgement phrase `ARM_PAPER_ONLY_AUTOMATION` and asks for the policy id.
   It starts nothing. The arming record (`PAA-…`) names the policy, account, experiment, time
   and operator. A policy cannot be replaced while armed (`AUTOMATION_ARMED_DISARM_FIRST`): a
   new policy needs a new arming.
2. **Start** takes the lease, attaches the reevaluation loop and begins scheduling.

The `operator` value on an arming request is **informational metadata only** — a label on the
record. It is not authorization: authorization is the caller's `paper.order.submit` capability
check on the route, which the client cannot supply.

## 4. Controls, and what each one really does

| Control | Effect |
|---|---|
| `configure` | Store a complete policy. Refused while armed. Arms nothing. |
| `arm` | Record authorization of the current policy. Starts nothing. |
| `start` | Take the lease, attach the loop, begin scheduling. |
| `pause` / `resume` | Cycles are skipped / run again. The lease and the loop stay. |
| `stop` | Stop scheduling, stop an automation-started AI run, release quotes, loop and lease. |
| `disarm` | Stop, then clear the arming and any emergency latch. |
| `emergency-stop` | Latch first (durably), then stop; cancel working automation orders. **Never liquidates.** |

Pause, Stop, Emergency Stop and Disarm are re-read before every order inside a running cycle,
under the same lock the submission holds, so a control change cannot be overtaken by an order
already in flight. Position limits are never widened by a control.

### Reading the status honestly

The server reports **one primary state** plus a **separate `blockers` array**. Read both.
When the primary state is not one of the four `BLOCKED_BY_*` states, other categories can still
be open at the same time — for example the regular session is closed (`WAITING_FOR_MARKET`)
*and* spending is unauthorized (`BUDGET · AUTONOMOUS_SPENDING_NOT_AUTHORIZED`). The UI names
those as open alongside the primary state; neither field is decoration.

| Primary state | Meaning |
|---|---|
| `NOT_CONFIGURED` | No controller row yet. |
| `DISARMED` | Configured, not armed. |
| `STOPPED` | Armed, not scheduling (stopped or never started). |
| `PAUSED` | Armed and leased; cycles are skipped. |
| `EMERGENCY_STOPPED` | Latched. Only Disarm clears it. |
| `WAITING_FOR_MARKET` | Armed; the session is not one the policy schedules. |
| `BLOCKED_BY_AUTHORITY` | Paper identity or account/experiment check failed. |
| `BLOCKED_BY_DATA` | Market data not usable (provider health, stale evidence). |
| `BLOCKED_BY_RISK` | An owner risk limit is reached (entries halt). |
| `BLOCKED_BY_BUDGET` | AI spending not authorized or the budget is exhausted. |
| `RUNNING` | This process holds the lease, its worker is alive, the session is eligible and no blocker is open. |
| `ERROR` | Should be running but is not: `CONTROLLER_NOT_ALIVE`, `RUNNING_ELSEWHERE`, a cycle error, or `CYCLE_OVERDUE`. |

`RUNNING` is never shown for a stalled controller. A controller that should be running but has
no live worker here is `ERROR`, never `RUNNING`.

## 5. Schedule, lease and restart

- Slots are `anchor + n × cadence`. A cycle that overruns skips the slots it covered: they are
  counted as missed, never run late and never overlapped.
- One owner per Paper account, enforced by a 180 s SQLite lease renewed by the worker between
  slots and by the cycle at its start, before each order and at its end.
- Outside the configured session nothing is evaluated, no model is called and no run is
  started. **Positions are not flattened at the close.**
- After a restart, `resume_on_startup` continues only a controller that was armed **and**
  running, and only if every start check passes again. A refusal is recorded
  (`STARTUP_RESUME_REFUSED`) and leaves the controller stopped — prior authorization never
  overrides a changed safety condition. A crash costs at most the lease wait (≤180 s).
- A refusal that time can clear is retried (rebuild step 4, owner decision 3): the
  predecessor's lease or reevaluation loop still held, or a busy store
  (`AUTOMATION_ALREADY_OWNED`, `REEVALUATION_LOOP_ALREADY_OWNED`, `OperationalError`). Retries
  run every 30 s for at most 15 minutes, recorded about once a minute as
  `STARTUP_RESUME_RETRYING`; each re-reads the controller, so a Stop, Pause, Disarm or
  Emergency Stop meanwhile still wins. Every other refusal is final at once, as before.
- Before resuming, the serving process closes full-universe AI runs a dead process left open
  (`ui_api.boot_recovery`), so a stuck run no longer holds the shared AI slot.
- A worker that ends on its own (a cycle error, five store errors in a row) while the
  controller is still armed and running is recorded as `WORKER_EXITED` with its reason and
  started again in-process after 60 s (`WORKER_REVIVED`), at most 3 times an hour
  (`WORKER_REVIVE_BUDGET_SPENT`, then `ERROR` as before). A lost lease, a stop or an emergency
  latch is never revived. A revive is the ordinary start: every check runs again and the gap
  is recorded as `NOT_OBSERVED`.
- The platform itself is brought back by the keeper ([AUTO_RESTART.md](AUTO_RESTART.md)). The
  keeper never arms, starts or stops the controller; it records what the controller did.
- Downtime is recorded as one `NOT_OBSERVED` event with the window and the count of missed
  slots, with `evaluations_backfilled: 0` and `orders_backfilled: 0`.

## 6. AI evaluation, and what it does not authorize

- Candidates come **only** from an adopted, complete full-universe selection. A partial,
  stopped, failed, budget-refused or interrupted run is recorded and contributes nothing.
- Local inference needs `allow_local_inference`; paid inference needs `allow_paid_inference`, a
  readable shared budget, and usage below the tighter of the owner's daily cap and the shared
  allowance. A refusal sends no request and shows as `BLOCKED_BY_BUDGET`.
- An unattended paid run carries a spend cap that refuses a too-large plan **before any hold or
  model call** (`AI_COVERAGE_BUDGET_INSUFFICIENT`, reason `AUTONOMOUS_SPENDING_LIMIT`).
- Every paid call also stays inside the machine's dollar caps (`PAID_AI_DAILY_DOLLAR_CAP` /
  `PAID_AI_MONTHLY_DOLLAR_CAP`, [AI_ENGINE_SWITCH.md](AI_ENGINE_SWITCH.md)). The AI engine is chosen in
  Setup and cannot change while automatic passes hold it. To let Paper use paid AI: pause Paper, choose
  the paid engine in Setup, then re-arm Paper with a policy whose `allow_paid_inference` is on. A policy
  armed without it never sends a paid request, whatever the engine.
- The AI pipeline never places an order. A model ENTER or EXIT is only a candidate: the Action
  Decision gate, preview, pre-trade risk and the submit lock all stand between it and the
  ledger.

## 7. Orders, exits and duplicates

- One accepted decision is one order, ever. The decision's identity is the order's
  `client_order_id` and idempotency key; a crash between the ledger write and the intent record
  is recovered by adopting the existing order.
- Exits run before entries. An entry whose order was rejected or partly filled is not chased.
- An exit that ended unfilled leaves risk open: a new EXIT decision is requested, spaced by a
  per-instrument backoff of `cadence × 2ⁿ`, capped at 900 s.
- Every automated order's provenance names the policy and the arming it was placed under
  (`PAPER_AUTOMATION_POLICY`, `PAPER_AUTOMATION_ARMING`).

## 8. Reporting

`GET /paper/automation/report` is labelled `SIMULATED_PAPER_FILLS_NOT_MARKET_TRUTH`. Fills,
costs, realized and unrealized P&L, win/loss counts, drawdown over persisted snapshots,
refusals by reason, decision origin and AI usage are **accounting of simulated fills**, not
evidence of a profitable strategy or a durable edge. The report changes no policy, limit, model
or method.

## 9. Not implemented — do not assume it

- **No liquidation rule.** Reaching the daily-loss limit halts entries. It does not close
  positions, and neither does the session close nor Emergency Stop. Automatic exits are exactly
  a breached SMA trailing stop and a gated EXIT decision.
- **No entry without a governed Opportunity.** The Action Decision gate still requires an
  `OpportunityV1` sharing the candidate's evidence lineage (`NO_GOVERNED_OPPORTUNITY`).
- **No strategy feedback.** The report describes outcomes; it changes nothing.
- Regular US session for US equities and ETFs; Continuous session for USD-settled crypto pairs
  only. Market orders, the experiment account, no other quote currency. There is no early-close
  list, so the US entry window is wrong on half days. The local reduction is context-bounded:
  exact preflight, hierarchical split, and a bounded comparison compaction for pairs/singles that
  keeps current-market evidence; a call/time bound defers the rest explicitly. The earlier
  `LOCAL_CONTEXT_EXCEEDED` limitation is repaired in source; operational verification is recorded
  in the repair receipt.

## 10. Common refusals and what they mean

| Code | What to check |
|---|---|
| `AUTOMATION_POLICY_INCOMPLETE:<fields>` | The listed fields are missing. Nothing was stored. |
| `AUTOMATION_ARMED_DISARM_FIRST` | Disarm before configuring a replacement policy. |
| `AUTOMATION_ARM_ACKNOWLEDGEMENT_REQUIRED` | The arm body has an unknown field, the acknowledgement is not exactly `ARM_PAPER_ONLY_AUTOMATION`, or `policy_id`/`operator` has the wrong type or length. |
| `AUTOMATION_POLICY_NOT_CURRENT` | `policy_id` is not the policy configured right now; arm exactly what is stored. |
| `AUTOMATION_ALREADY_ARMED` | Already armed; Disarm before arming again. |
| `AUTOMATION_EMERGENCY_STOPPED_DISARM_FIRST` | The latch is set. Only Disarm clears it. |
| `AUTOMATION_ALREADY_OWNED` / `AUTOMATION_LEASE_LOST` | Another process owns the account, or this one lost the lease. |
| `AUTOMATION_STATE_TRANSITION_INVALID` | Pause/Resume was asked for from the wrong state. |
| `AUTOMATION_NOT_RUNNING_START_FIRST` | Resume needs a live worker; Start it first. |
| `ACTIVE_PAPER_EXPERIMENT_REQUIRED` | No active portfolio-scoped Paper experiment. |
| `PAPER_RISK_POLICY_CHANGED` | The ledger's risk policy changed since the policy was configured; reconfigure and re-arm. |
| `AUTOMATION_ACCOUNT_MISMATCH` | The policy is bound to a different account or experiment. |

## 11. Arming unattended trading — the owner gate

Do **not** arm unattended Paper trading against the owner's canonical experiment until the
required policy, capital/risk limits and a one-time operator authorization have been explicitly
established. Those settings are owner decisions; do not invent them. This controller never
trades real capital regardless, and `LIVE-001` and every Live gate are unchanged.

## Escalation

Record an incident in [WORK_LOG.md](../engineering/WORK_LOG.md) if it is significant. Keep the
audit history: `paper_automation_events`, intents, decision traces and ledger events are
append-only and are not rewound to tidy up. A test that touches ordering must use disposable
state, never the owner's Paper account.
