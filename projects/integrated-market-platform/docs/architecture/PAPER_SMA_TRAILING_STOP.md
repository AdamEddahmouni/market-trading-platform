# SMA trailing-stop risk control (OCT1-08)

A deterministic, server-owned stop **monitor** for open Paper positions. It
keeps a stop level derived from a simple moving average of completed bars,
never lets that level move away from protection, and turns a breach into a
governed EXIT decision. It is a proposed downside-control method that IMP
implements and evaluates; nothing here claims it is profitable or better than
an alternative.

It is **not** a resting broker order. Paper order types remain `MARKET` and
`LIMIT`; there is no native STOP, OCO or bracket order, and no stop was ever
"working in the market". A breach never submits, previews or drafts an order.

```
open Paper position -> completed bars -> stop state -> breach
  -> server EXIT decision -> existing explicit Paper close handoff
```

## Reused authorities

| Need | Authority |
|---|---|
| Position side and quantity | `PaperExecutionLedger.project_positions()` |
| Position episode | `PositionChanged` fill lineage in the same ledger |
| Completed bars | `market_data/current_bars.py` (`CurrentBarsService.read`, complete bars only) |
| Current price | the Screener last-trade quote and its freshness (`L1_EVENT_V1`) |
| Decision record and trace | OCT1-06 `ActionDecisionV1` + `ExecutionDecisionTraceV1` |
| Cadence and safety precedence | OCT1-07 reevaluation cycle |
| Persistence | the existing local-state SQLite database |
| Exit order path | OCT1-06 `handoff` -> Workspace ticket -> preview -> explicit submit |
| Replay bars | pinned `HISTORICAL_DEVELOPMENT` corpus under `evidence/historical-research/` |

No SMA, stop, trailing or tick-rounding code existed before this contract.

## Policy `sma-trailing-stop-policy/1.0.0`

`risk/sma_trailing_stop.py::build_policy`. `policy_id` is `STP-` plus a hash of
every behavioural field, so changing any of them is a new policy; `created_at`
and the display label are not part of the identity.

| Field | Value |
|---|---|
| `sma_window_bars` | operator-bounded integer, 2–200 |
| `bar_interval` | `1m`, `5m` or `15m` |
| `session_scope` | `RTH` |
| `price_basis` | `COMPLETED_BAR_CLOSE` |
| `trigger_basis` | current: `LAST_TRADE_PRICE`; replay: bar low (long) / bar high (short) |
| `tick_rounding_policy` | tick 1 minor unit; long `CEIL_TO_TICK`, short `FLOOR_TO_TICK` |
| `update_timing` | after the bar is available; effective for later observations only |
| `warmup_requirement` | a full window of completed bars |
| `gap_policy` | a missing intraday bar in the window blocks the update; the window may span a session break |
| `evaluation_fill_model` | `stop-exit-bar-conservative/1.0.0` |

`REFERENCE_TEST_CONFIG` is SMA 20 on completed 1-minute bars. It is one
reference software-evaluation configuration fixed before any outcome was read.
It is not optimized, calibrated, recommended or superior, and the SMA-20
research example elsewhere in the repository is not its authority. Operators
may set only the window, the interval and enabled/disabled; no level or formula
can be entered.

## Stop math

Prices are integer minor units. The SMA is the exact integer sum of the last N
completed closes divided by N; no float is involved.

```
LONG   candidate_t = ceil(SMA_t)     active_t = candidate_t               (first stop)
                                     active_t = max(active_t-1, candidate_t)
SHORT  candidate_t = floor(SMA_t)    active_t = candidate_t               (first stop)
                                     active_t = min(active_t-1, candidate_t)
```

A long stop may rise or hold; it never falls. A short stop may fall or hold; it
never rises. When the SMA moves the wrong way the prior level is kept and the
state carries `MONOTONIC_CLAMP`. Rounding is toward protection on both sides,
and the same function produces the level for stored state, API, UI and replay.

The same guard exists in storage: `SmaStopRepository.put` refuses a write that
would loosen an active stop (`STOP_LOOSENING_REJECTED`) or revive a terminal
state (`STOP_STATE_TERMINAL`).

## Bars and time

- Only bars complete and available by the evaluation cutoff are used. Partial
  bars and bars later than the cutoff are excluded and counted.
- Bars are ordered by availability and deduplicated by identity. Two different
  bars claiming one identity or one slot raise `BAR_IDENTITY_CONFLICT`; the
  series is not repaired.
- A missing intraday bar is never replaced by an invented close. If the window
  contains one, no new level is computed (`BAR_GAP_IN_WINDOW`).
- `available_time` (bar end) is the bar authority. Source adapters map vendor
  timestamps explicitly: live bars treat the vendor key as bar end, the
  historical corpus as bar start.
- **No same-bar look-ahead.** A stop computed from bar k records
  `effective_after = bar k available_time`. `effective_stop(state, t)` returns
  the level that was already in force at `t`: the new level for `t` at or after
  that time, otherwise the previous level, otherwise none. Bar k's own range is
  therefore never tested against the level bar k produced, and a quote older
  than the newest level is judged against the level before it.
- A new episode starts from the latest completed bar. History before activation
  is never folded into it.

## State `sma-trailing-stop-state/1.0.0`

One state per `(account, instrument, position epoch, policy)`: identity, side,
ledger quantity at last evaluation, activation time and reason, SMA, candidate,
active and previous stop, the bar that produced them, counters, status, reason
codes, and trigger time, price and evidence.

| Status | Meaning |
|---|---|
| `NOT_CONFIGURED` | no enabled policy for the account; nothing is monitored |
| `WARMING_UP` | fewer than N admissible completed bars; no stop exists |
| `ACTIVE` | a stop exists and bars are current |
| `STALE` | a stop exists but cannot currently be updated (`STOP_UPDATE_STALE` plus the cause); the last legitimate level is kept and still enforced |
| `BLOCKED` | no stop exists and one cannot be computed, or the ledger position is unavailable |
| `BREACHED` | the stop was crossed by an admissible observation; terminal until the position closes |
| `CLOSED` | the episode ended (flat, reversed, epoch changed, disabled) |

`trigger_state` is separate: `NOT_ARMED`, `ARMED`, `TRIGGER_UNAVAILABLE`,
`BREACHED`.

### Position episode

A stop belongs to a position episode, never to a ticker. The episode id is
derived from the ledger: the `PositionChanged` event whose fill took the net
position from flat, or from the opposite side, to the current side
(`LEDGER_OPENING_FILL`). A partial reduction or an add keeps the episode; going
flat or reversing ends it. A projected position with no fill lineage is counted
from the flat and reversal observations the monitor itself made
(`LEDGER_POSITION_WITHOUT_FILL_LINEAGE`).

| Event | Behaviour |
|---|---|
| Flat -> long/short | new episode; `POSITION_OPENED` if the monitor observed the flat state, else `LATE_ACTIVATION` with the exact activation time |
| Position remains | the stop keeps trailing |
| Partial reduction | same episode; quantity is read from the ledger each time |
| -> Flat | `CLOSED` (`POSITION_FLAT`) |
| Reversal | old episode `CLOSED` (`POSITION_REVERSED`); a new episode on the new side |
| Restart | state, policy and epoch are read back; a different ledger epoch closes the old state (`POSITION_EPOCH_CHANGED`) and it is never applied |
| Downtime | one `MONITORING_GAP` event (`NOT_OBSERVED`, `updates_backfilled: 0`); the stop resumes from the latest completed bar |

Short stop math is implemented and tested. It does not grant Paper short
authority, which is unchanged.

### Initial validity

If the first stop is already through the current price the state is `BREACHED`
with `IMMEDIATE_EXIT_CONDITION`. No stop on the wrong side of the market is
stored as protection.

### Configuration changes

Changing the policy while a stop is active is rejected
(`STOP_POLICY_CHANGE_REJECTED_WHILE_ACTIVE`) and recorded. Disabling is
explicit and closes the stop. Re-enabling on the same position carries the
earlier level forward, so a slower window cannot be used to lower a long stop
or raise a short one.

## Trigger

| Context | Rule |
|---|---|
| Current, long | admissible last-trade price `<=` effective stop |
| Current, short | admissible last-trade price `>=` effective stop |
| Replay, long | `bar.low <=` a stop effective at the bar's start |
| Replay, short | `bar.high >=` a stop effective at the bar's start |

Last trade is the only current-price authority; bid, ask and mark are not
mixed in. A stale or inadmissible quote yields `TRIGGER_UNAVAILABLE` with
`REVALIDATION_REQUIRED`: the stop is neither confirmed breached nor confirmed
safe. The current monitor tests the price at each evaluation; it does not infer
a breach from a bar range between evaluations.

A gap through the stop is recorded with the stop level and the bar's open, high
and low. The trigger never names a fill price, and a bar's internal order is
recorded as unknown.

## Deterministic EXIT

`SMA_TRAILING_STOP_BREACHED` is a server condition with source
`SERVER_RISK_CONTROL`, present only while a stop is configured for the
position.

- `action_decision.py::gate_proposal`: a met condition on the held side yields
  `EXIT` with no model proposal. Degraded inputs (pending order, lost authority,
  stale quote, stale position snapshot) become preview blockers; they never
  erase the EXIT.
- The model cannot select the condition (`UNSUPPORTED_CONDITION`), cannot name a
  stop, SMA, trailing rule or number in its text
  (`UNSUPPORTED_EXECUTION_OR_LEVEL`), and cannot veto the exit. The OCT1-06
  validator is unchanged.
- `screener_action.py::run` appends a new immutable decision with no model
  call: prior state, `EXIT`, policy id, active and previous stop, trigger price
  and time, quote evidence, position and reason code, plus an
  `ExecutionDecisionTraceV1` whose rule evaluations and config refs name the
  stop policy and stop state. Earlier decisions are not modified.
- `reevaluation.py`: the condition is a `SAFETY_REASON`, so it bypasses the
  anti-churn dwell. In the cycle the stop is evaluated for every held
  instrument before any model is considered, and a breach also bypasses the
  model-availability and model-budget gates. Routine tightening, staleness and
  resumption are recorded as deterministic updates without a model call; an
  unchanged stop changes nothing.
- `Evaluate Stop Now` calls the same service method the cycle calls.

Stop facts are attached to the decision context as read-only `risk_control`
evidence. They are deliberately not added to the candidate capability list.

## Paper handoff

Unchanged. An EXIT decision enables the existing `Prepare Paper Exit`; the
draft quantity is the current ledger holding and the side is the opposite of
the position. `validate_order_source` still rejects a changed quantity at
preview and at submit. The stop owns no quantity. Preview and submit remain
explicit in the Workspace ticket.

## Persistence

`local_state/sma_trailing_stop.py`, tables `sma_stop_records` and
`sma_stop_events` in the existing database. Policies and events are immutable;
state advances under the guards above. Persist-off keeps the same contract in
process memory and reports `INTENTIONAL_EPHEMERAL`. History reads are newest
first, at most 100 per request, with a `before` cursor.

## API

| Route | Capability | Purpose |
|---|---|---|
| `GET /paper/risk-control/sma-stop?instrument=` | `audit.read` | persisted stop state; never advances or triggers |
| `GET /paper/risk-control/sma-stop/config` | `audit.read` | policy, bounds, reference configuration |
| `GET /paper/risk-control/sma-stop/history?instrument=&limit=&before=` | `audit.read` | bounded stop events |
| `GET /paper/risk-control/sma-stop/evaluation` | `audit.read` | bounded replay receipt |
| `POST /paper/risk-control/sma-stop/configure` | `state.write` | enabled, window, interval only |
| `POST /paper/risk-control/sma-stop/evaluate` | `state.write` | Evaluate Stop Now |

None carries `paper.order.submit`.

## Replay evaluation

`research/sma_stop_evaluation.py`. The definition in
`evidence/historical-research/oct1-08-sma-trailing-stop-replay-v1/` was
committed before any comparison was run and is verified against the code
before every run.

- Methods: `SMA_TRAIL`, `RAW_PRICE_TRAIL`, `FIXED_INITIAL_STOP`, `NO_TRAIL`.
- Matched initial risk: `D = |entry reference - initial SMA stop|` for all
  three stop methods.
- Entries: fixed outcome-blind schedule; entry at the open of the bar after the
  signal bar. Entries whose initial stop is not protective are counted and
  excluded.
- Fill model, separate from the trigger: a stop exit fills at the trigger bar's
  worst price, never at the stop level; the horizon exit is the session's last
  close. Gross and cost-adjusted returns are reported separately.
- Conclusion vocabulary: `INSUFFICIENT_EVIDENCE`, `NO_CLEAR_DIFFERENCE`,
  `SMA_REDUCED_DOWNSIDE_WITH_RETURN_TRADEOFF`, `SMA_UNDERPERFORMED_REFERENCE`.
  No token asserts superiority. Below 20 sessions or 3 instruments the
  conclusion is `INSUFFICIENT_EVIDENCE`.
- Evidence class `HISTORICAL_REPLAY`, status `REPLAY_EVALUATED`, calibration
  `NOT_CALIBRATED`. It is not prospective, Paper or live evidence.

Results and limits: [OCT1-08 report](../superpowers/plans/2026-10-06-oct1-08-sma-trailing-stop.md).

## Limitations

- The stop is checked when the reevaluation loop runs or the operator asks. If
  IMP is not running it is not observed, and no protection is claimed.
- A price that crosses and recovers between two evaluations is not a breach.
- The Paper equity projection is one net position per session, so the monitor
  follows that position.
- An EXIT decision needs admissible candidate evidence for the instrument; the
  breach itself is recorded on the stop state regardless.
- No holiday calendar: bar freshness is the existing completed-bar policy.
