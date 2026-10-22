# Paper portfolio experiment

Status: implemented (OCT1-09). Implementation report:
[OCT1-09](../superpowers/plans/2026-10-06-oct1-09-100k-paper-portfolio.md).

A Paper portfolio experiment is one explicit, persistent, simulated-capital
account that starts with exactly $100,000.00 and is shared by every instrument
traded in it. It is fake money on the internal simulator. It never routes to a
broker and never uses live capital.

It is accounting. It is not a strategy result, a performance claim or evidence
of a predictive edge.

## Identity

`PaperPortfolioExperimentV1` (`paper/experiment.py`, schema
`paper-portfolio-experiment/1.0.0`):

| Field | Meaning |
|---|---|
| `experiment_id` | `PPE-<32 hex>`; new for every experiment |
| `paper_account_id`, `paper_session_id` | the experiment's own Paper account and session |
| `initial_capital_minor` | `10_000_000` (USD 100,000.00); any other value is refused |
| `data_mode`, `data_providers` | market-data identity at creation |
| `execution_mode` | `INTERNAL_SIMULATION` only; `LIVE` and `BROKER_PAPER` are refused, not downgraded |
| `risk_policy_id`, `cost_policy_id`, `fill_model_id` | frozen policy, cost and fill-model identity |
| `slippage_model` | `NOT_SEPARATELY_MODELED` (see Costs) |
| `evidence_class` | `PROSPECTIVE_PAPER_WITH_LIVE_OBSERVATIONAL_DATA`, `HISTORICAL_REPLAY` or `SOFTWARE_CONTROLLED`, from the data mode |

The global Paper default (`DEFAULT_RISK_POLICY`, $1,000,000) is unchanged. Only
the experiment contract freezes $100,000.

## Account scope

A legacy Paper session derives its account id from the seed instrument, so each
instrument got its own account and its own starting cash, and all equity fills
pooled into one scalar position.

An experiment account is portfolio scoped. Its account id is derived from
`{account_identity_version: 2, account_scope: "PORTFOLIO", currency,
experiment_id, initial_cash_minor}` and contains no instrument. The ledger is
portfolio scoped only when its own `PaperAccountCreated` event says so, so a
persisted legacy session is never reinterpreted: its account id, pooled
position and single mark are byte-stable.

## Accounting authority

The `PaperExecutionLedger` stays the only authority. State is recomputed from
`FillRecorded` events in integer minor units; nothing is stored as a running
balance and nothing is computed in the UI.

For an experiment account (`portfolio/ledger.py: apply_portfolio_fill`):

- cash, realized P&L, commission and fees are shared;
- each instrument has its own quantity, cost basis, first entry time, latest
  fill time and realized P&L, driven by the existing per-fill arithmetic
  (weighted average cost; a sell realizes P&L only on the quantity it closes);
- a sell larger than the held quantity of that instrument less its working
  sells is refused (`INSUFFICIENT_POSITION`). The experiment does not enable
  shorts or reversal.
- option and future orders are refused (`EXPERIMENT_INSTRUMENT_KIND_UNSUPPORTED`):
  the experiment values share positions only, and a derivative is not
  mis-valued as shares.

### Marks

Marks are keyed by instrument: `{mark_minor, provider, as_of_ns, quality,
freshness_ms}`. A position is valued only at its own mark. It is never valued
at another instrument's mark, at its last fill, or at zero.

In `LIVE_OBSERVATIONAL` mode each held instrument is marked from its own live
quote; an instrument whose quote cannot be read keeps its last price and is
downgraded to `STALE`. A mark read back from disk after a restart is
`RESTORED`. In fixture replay there is no per-instrument mark source, so an
open position reports its mark as unavailable.

### Valuation

`project_valuation()`:

```text
equity        = cash + sum(quantity x own mark)        (no realized P&L added again)
unrealized    = sum(market value - cost basis)
total P&L     = equity - initial capital
buying power  = cash - working-order reservations      (no leverage)
```

Commission and fees are inside cash and realized P&L once; they are not
subtracted a second time.

| Quality | Meaning | Equity |
|---|---|---|
| `CURRENT` | every open position has a current mark (or the account is flat) | shown |
| `DEGRADED` | at least one mark is stale, delayed or restored | shown, flagged not current |
| `PARTIAL` | at least one open position has no mark | unavailable; marked subtotal reported |
| `UNAVAILABLE` | no open position has a mark | unavailable |

### Trades and orders

`project_trades()` is fill level. Each row carries experiment, account, order,
fill, instrument, side, requested and filled quantity, fill price and time,
commission, fees, position effect (`OPEN`, `ADD`, `REDUCE`, `CLOSE`), realized
P&L delta, decision source and lineage references. Every row is
`fill_kind: SIMULATED_FILL`, `is_market_truth: false`.

Rejected, cancelled and working orders are order history, not trades.

`decision_source` is `AI_DECISION_GOVERNED` when the order carried an action
decision reference, otherwise `MANUAL_TEST` (an operator ticket).

Lineage references recorded on experiment orders: `ACTION_DECISION`,
`ACTION_SNAPSHOT`, `CANDIDATE_RUN`, `OPPORTUNITY`, `DECISION_TRACE`,
`REEVALUATION_CYCLE`, `SMA_STOP_STATE`, `SMA_STOP_POLICY`, `POSITION_EPOCH`,
`PAPER_PREVIEW`, `PAPER_EXPERIMENT`, plus the governed `risk_decision_id`.

### Costs

Fill model `simulation.bar_conservative@phase7.bar-conservative/1.1.0`: a buy
fills at the high and a sell at the low of the first completed bar strictly
after the order, capped at 1/100 of that bar's volume. Commission and fees
follow the frozen risk policy (currently zero). There is no separate slippage
term: adverse execution is embedded in the conservative bar fill, and the
contract says `NOT_SEPARATELY_MODELED` rather than inventing a number.

## Lifecycle

`ACTIVE -> CLOSED`.

- **Create** is explicit (`POST /paper/experiments`). It fails closed when
  internal Paper simulation is not authorized, when another experiment is
  active, or when any execution mode other than `INTERNAL_SIMULATION` is asked
  for.
- **Restore.** On start an `ACTIVE` experiment's ledger is rebuilt from its own
  events and stored policy. Cash is never re-seeded or topped up, the stored
  data mode is never swapped for replay, and execution stays deferred until the
  existing execution-health gate releases it. A restart never creates a new
  experiment.
- **Orders** are refused when the experiment is closed, when the execution mode
  is not internal simulation, or when the running data mode is not the
  experiment's data mode (`EXPERIMENT_MARKET_DATA_UNAVAILABLE`). The portfolio
  stays readable.
- **Close** is refused while positions (`OPEN_POSITIONS_REMAIN`) or working
  orders (`WORKING_ORDERS_REMAIN`) remain. It never liquidates. Final cash,
  equity, realized P&L and trade count are frozen on the record, and history
  stays readable.
- **New experiment** after close is a new experiment id, account id, session id
  and a fresh $100,000.00. The earlier experiment is immutable.
- The legacy `POST /paper/sessions` and `/paper/sessions/close` routes refuse
  while an experiment is active, so it cannot be silently replaced or archived.

## Persistence

`local_state/paper_experiments.py` owns two additive tables created on demand
(the pattern used by the OCT1-08 stop repository; no global schema version
bump): `paper_experiments` (immutable creation record, status, closing values)
and `paper_equity_snapshots` (append-only, unique on experiment and state
hash). Ledger events stay in the existing session/event tables. The per-
instrument marks are saved with the session snapshot.

Equity snapshots are written on creation, on every fill, on close, and on a
material mark change at most once a minute. Reading the portfolio repeatedly
never appends identical rows.

## API

All routes are loopback UI API routes under the existing route policy.

| Route | Capability | Purpose |
|---|---|---|
| `POST /paper/experiments` | `state.write` | create |
| `GET /paper/experiments` | `state.read` | bounded list (max 100) |
| `GET /paper/experiments/current` | `state.read` | active experiment, valuation, assumptions, boundary |
| `GET /paper/experiments/{id}` | `state.read` | one experiment, including a closed one |
| `POST /paper/experiments/{id}/close` | `state.write` | close when flat |
| `GET /paper/trades?cursor&limit&experiment_id` | `state.read` | newest-first trade page (max 100) |
| `GET /paper/equity-history?before&limit&experiment_id` | `state.read` | newest-first snapshot page (max 100) |

`GET /paper/portfolio` gains additive `experiment`, `valuation`, `assumptions`
and `boundary` blocks. A preview response gains `experiment_context` (experiment,
account, initial capital, cash, reserved cash, buying power, current position).

`boundary` records market-data identity and execution identity independently:
`market_data {mode, provider, running_mode, state}`, `execution {mode,
provider, execution_authority, fill_kind}`, `capital {kind: SIMULATED,
live_capital: false}`.

## UI

Paper Portfolio shows the experiment header, the data/execution boundary, the
summary (initial capital, cash, reserved cash, buying power, position value,
realized, unrealized, total equity, total Paper P&L, return), valuation
quality, positions with their own marks, trade history with decision
drilldown, assumptions and equity history. With no active experiment it shows
"No active Paper experiment" and the explicit create action; a closed
experiment stays readable.

The boundary headline is derived from the running state: it says "LIVE/CURRENT
MARKET DATA + SIMULATED PAPER EXECUTION" only when the experiment's data mode
is live observational and running, and otherwise names the actual state. It
never describes execution as live. A missing value renders as "Unavailable",
never `$0.00`; signs are in the text and the accessible label.

Paper Workspace shows the experiment context (status, initial capital, cash,
buying power, current position in the instrument) above the order ticket, or
states that no experiment is active.

## Boundaries

- No live-capital order path exists in this feature.
- The experiment does not change candidate thresholds, freshness policy, the
  action gate, pre-trade risk or the simulator.
- Win rate, expectancy, profit factor, drawdown and strategy comparison are not
  part of this contract.
