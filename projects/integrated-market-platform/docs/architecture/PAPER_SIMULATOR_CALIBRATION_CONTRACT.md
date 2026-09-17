# Paper Simulator Calibration & Validation Contract

**Classification:** `CURRENT_CANONICAL_ARCHITECTURE`  
**Purpose:** prevent internal Paper execution from being treated as market ground truth without measured calibration.

## Evidence model

Calibration compares three distinct layers where available:

1. **Market Evidence** — prospective observations from admitted real market sources.
2. **IMP Simulation** — IMP hypothetical order/fill/position/P&L behavior.
3. **External Comparator** — a suitable broker/vendor Paper, sandbox, replay or simulator.

The external comparator is never ground truth. It is an independent challenge model with its own limitations.

## Calibration unit

Each calibration record must bind at least:

- asset class and venue;
- instrument or instrument family;
- market-data capability contract(s);
- IMP simulator version/source SHA;
- comparator/environment version and account mode, if used;
- order type/policy;
- session/calendar rules;
- sizing assumptions;
- cost/fee/margin rules;
- sample window/cohort;
- metric definitions and thresholds.

Do not generalize calibration from one materially different asset/order/data regime to another without evidence.

**Hard rule:** US-equity Paper/sandbox (including Tradier sandbox) does **not**
validate ES futures fill realism. Cross-asset reuse of a calibration pass is
prohibited.

## Current harness (not a pass)

IMP Paper submit uses `BarConservativeSimulator`
(`phase7.bar-conservative/1.1.0`) as a synchronous one-shot. LIMIT does not
constrain fill price; STOP is unimplemented; book-aware L2 is not on the
Paper path. Pairing joins IMP vs comparator on
`forward_test:{forward_test_id}` (and an explicit pairing table when echo fails).
Observations persist on PD-09 schema v6 `forward_test_observations` — no
second campaign DB.

The campaign runner classifies `COMPARATOR_NOT_CONFIGURED` or
`WAITING_FOR_MARKET` when credentials are absent or the session is closed.

**BAR_OHLCV_1M dry-run (Item 9):** `tools/providers/run_bar_ohlcv_comparator_experiment.py`
loads lawful 1m bars (`ADMITTED-SHORTSQ-BIYA-BARS-001` fixture or loopback OpenD
`K_1M` via quote context), reports signal/bar timestamps and provenance, and
dry-runs `BarConservativeSimulator` without broker orders or `CALIBRATED`.
Missing or mistimed bars classify `EXPERIMENT_CONTRACT_MISMATCH` (including
`SIM_NO_POST_SIGNAL_BAR` when `available_time` is not strictly after signal time).
Alpaca Paper (`https://paper-api.alpaca.markets`, stdlib urllib, no SDK import)
is the no-fee HTTPS comparator; missing keys stay `COMPARATOR_NOT_CONFIGURED`
with `orders_placed=false` and `fabricated_fills=false`. Live
`api.alpaca.markets` is `LIVE_FORBIDDEN` before `urlopen`. Tradier `#41` remains
in tree and fail-closed. The runner does not fabricate empirical fills, does not
declare `CALIBRATED`, and does not flip FTEP to `EMPIRICAL_ACTIVE`. Numeric
gates remain `UNSET/BLOCKING`. Item 9 stays PARTIAL until a later governed
calibration run satisfies [ITEM9_CALIBRATION_PROTOCOL_V1.md](ITEM9_CALIBRATION_PROTOCOL_V1.md).
Operator Paper keys in gitignored `.private` are required only for
execution-claim comparator pairing, not for protocol freeze or corpus
accumulation.

## Required comparison metrics

Use every metric material to the campaign claim:

| Dimension | Example measurement |
|---|---|
| acceptance/rejection | disagreement rate and reason mapping |
| trigger/submit/ack timing | absolute/percentile timing error |
| fill/no-fill | disagreement rate |
| fill price | absolute ticks/bps/currency error |
| slippage | distribution difference vs reference/comparator |
| partial fills | completion ratio and fill-path divergence |
| spread behavior | crossing/passive-fill consistency |
| stop/limit/market semantics | trigger/fill outcome disagreement |
| cancel/replace | state-transition and late-fill disagreement |
| session handling | overnight/auction/closed-session divergence |
| fees/commissions | per-order and aggregate difference |
| margin/collateral | acceptance and requirement difference |
| positions | quantity/cost-basis reconciliation |
| realized/unrealized P&L | monetary/tick tolerance |
| stale/missing data | fail-closed behavior consistency |
| latency assumptions | sensitivity and observed gap |
| capacity/liquidity | claimed-vs-observable limitations |

## Numeric acceptance gates

Before an execution-bearing campaign starts, the frozen activation manifest must provide justified numeric thresholds for every material metric. At minimum:

- maximum fill/no-fill disagreement rate;
- maximum fill-price/slippage error;
- maximum timing error when timing affects the hypothesis;
- position/P&L reconciliation tolerance;
- maximum unexplained material-divergence rate.

There are intentionally no universal default numbers in this document. Thresholds depend on asset, order policy, market-data granularity and intended claim. If a defensible threshold cannot yet be specified, the field is `UNSET/BLOCKING` and the affected execution claim cannot be activated.

## Divergence taxonomy

Every material mismatch is retained as one of:

- `WITHIN_TOLERANCE`
- `EXPLAINED_DIVERGENCE`
- `UNEXPLAINED_DIVERGENCE`
- `NOT_OBSERVABLE`

Do not silently overwrite IMP results with comparator results or choose the more favorable fill.

## Calibration outcome

A calibration closes as:

- `PASS_FOR_DECLARED_SCOPE`
- `PASS_WITH_LIMITATIONS`
- `RECALIBRATE`
- `BLOCKED_BY_DATA`
- `BLOCKED_BY_COMPARATOR`
- `FAIL`

A pass applies only to the bound scope. It does not establish Live execution quality, market impact realism, queue realism, or capacity outside what was actually observed and tested.

## Shakedown vs qualifying evidence

Calibration/shakedown observations must be tagged and excluded from a campaign's qualifying primary cohort unless they were explicitly preregistered as qualifying before observation. Learning from shakedown may inform a new frozen campaign version; it may not be back-applied to improve the current campaign's apparent result.

## Asset-profile expectations

- **Futures:** contract month, tick/multiplier, exchange session, roll/expiry, margin and contract-month liquidity must be explicit.
- **Options:** contract/series identity, spread/depth, expiration, assignment/exercise and multi-leg assumptions must be explicit.
- **Equities:** halts/corporate actions and short-sale/borrow assumptions must be explicit when relevant.
- **Crypto:** venue-specific book, fee/funding and 24/7 session assumptions must be explicit.

## Promotion rule

Strategy Paper results may support implementability claims only when the execution-model calibration state required by that strategy's readiness vector is satisfied. Signal-quality evidence may be analyzed separately when execution realism is deliberately out of scope and labeled `SIGNAL_ONLY`.
