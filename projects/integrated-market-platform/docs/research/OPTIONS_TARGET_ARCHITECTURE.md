# Options Target Architecture (Deliverable 5)

**Status:** Target design — implementation gated by reconciliation doc  
**Date:** 2026-08-18  
**Authority:** Subordinate to `OPTIONS_SHORT_SQUEEZE_ROADMAP_RECONCILIATION.md` for sequencing

---

## 1. Architectural thesis

Options evaluates **what the market prices (Q)** against **what we forecast will happen (P)**, then expresses disagreement through forecast-driven strategy construction — never through a universal score or bullish/bearish collapse.

```text
MARKET + CROSS-LANE DATA
        ↓
PHYSICAL DISTRIBUTION FORECAST (P)          [SHARED P2 — platform]
        ↓
OPTIONS MARKET INTERPRETATION
        ↓
RISK-NEUTRAL IMPLIED DISTRIBUTION (Q)       [OPTIONS O3]
        ↓
P vs Q COMPARISON                           [OPTIONS O4]
        ↓
MISPRICING / EDGE (decomposed)
        ↓
STRATEGY CONSTRUCTION                       [OPTIONS O8]
        ↓
EXPECTED P&L DISTRIBUTION
        ↓
RISK + LIQUIDITY + EXECUTION
        ↓
RANKED OPPORTUNITIES (incl. NO_TRADE)
```

---

## 2. Layer diagram

```text
                         MARKET DATA
                              │
                              ▼
                    PROVIDER ADAPTERS
                    (chain, quotes, flow, OI)
                              │
                              ▼
                 NORMALIZED OPTION CONTRACTS     [O1]
                              │
                              ▼
               QUALITY + PROVENANCE + PIT        [P0]
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
     IV ENGINE           GREEKS ENGINE      REALIZED VOL      [O2]
          │                   │                   │
          └─────────┬─────────┘                   │
                    ▼                             │
            VOLATILITY SURFACE σ(K,T)             │
                    │                             │
                    ▼                             ▼
            RISK-NEUTRAL Q                   PHYSICAL P
                    │                      [SHARED P2]
                    └──────────┬──────────────┘
                               ▼
                        P vs Q ENGINE            [O4]
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
        FLOW ENGINE    DEALER ENGINE    EVENT VOL ENGINE
              [O5]         [O6]              [O7]
              │                │                │
              └────────────────┼────────────────┘
                               ▼
                    CROSS-LANE EVIDENCE BUS      [SHARED P3]
                               │
                               ▼
                    STRATEGY + PAYOFF ENGINE     [O8]
                               │
                               ▼
                    EXECUTION / SIMULATOR        [O9]
                               │
                               ▼
                    EXPLANATION GRAPH
```

---

## 3. Contract flow (O1)

### 3.1 Canonical `OptionContract`

```python
# Target schema (contracts/options.py)
underlying_id: str
option_id: str          # OCC or provider-native + normalization map
call_put: Literal["call", "put"]
strike: Decimal
expiration: date
dte: int
exercise_style: Literal["american", "european", ...]
settlement_style: Literal["physical", "cash", ...]
multiplier: Decimal
deliverable: DeliverableSpec | None

bid, ask, mid, last: Decimal | None
bid_size, ask_size: int | None
volume, open_interest: int | None

intrinsic_value, extrinsic_value: Decimal | None  # DERIVED

provider: str
exchange: str | None
event_time: datetime
available_time: datetime

quality: OptionQualitySnapshot
provenance: ProvenanceRef
```

### 3.2 Corporate actions

Adjusted contracts carry `CORPORATE_ACTION_ADJUSTED` quality flag and explicit `deliverable` spec. Unknown deliverables → `ADJUSTED_DELIVERABLE_UNKNOWN` → exclude from surface fit (`quality_blocks_surface_fit`).

Fixture implementation: `option_contract_builder._resolve_deliverable()` reads `corporate_action_adjusted`, `deliverable_shares`, `deliverable_unknown`, `adjusted_strike` from activity rows. Reference fixture: `tests/fixtures/providers/options/biya_adjusted_option_slice.json` (symbol `BIYA_ADJ`). No live adjustment pipeline in O1 fixture scope.

### 3.3 Chain state

`OptionChainSnapshot`: underlying price, forward estimate, interest rate, dividend assumptions, list of `OptionContract`, chain-level quality summary.

---

## 4. IV flow (O2)

### 4.1 Dual IV track

| Field | Meaning |
|---|---|
| `provider_iv` | As supplied by data vendor |
| `internal_iv` | Recomputed under declared model |

Both carry: `pricing_model`, `solver`, `assumptions`, `input_provenance`, `calculation_version`.

**Rule:** Never compare IV values across methodologies without explicit normalization.

### 4.2 Inputs

Underlying/forward, strike, expiration, rate, dividends, borrow/carry, option price, exercise/settlement style.

### 4.3 Failure modes

`IV_INVALID`, `IV_SOLVER_FAILED` — fail closed; do not substitute zero.

---

## 5. Greeks flow (O2)

Minimum: delta, gamma, theta, vega, rho.

Extended (when useful): vanna, charm, vomma, speed.

Support `provider_greeks` and `internal_greeks`. All internal Greeks reproducible from stored inputs + version.

**Rule:** Delta is **not** physical probability. Document P vs Q distinction in glossary and UI.

---

## 6. Surface flow (O2)

### 6.1 Representation

σ(K, T) across strike × expiration.

Coordinates: forward moneyness, log moneyness, delta — not raw strikes only.

### 6.2 Summary metrics

ATM IV, put/call skew, 25Δ risk reversal, 25Δ butterfly, skew slope/curvature, term slope/curvature, surface level, anomalies.

### 6.3 Surface QA (before any fit)

Reject: crossed markets, zero bids (where invalid), stale quotes, wide spreads, arbitrage violations, sparse expirations.

Quality flags: `SURFACE_SPARSE`, `SURFACE_ARBITRAGE_VIOLATION`.

---

## 7. P forecast flow (SHARED P2)

**Not Options-only.** Platform module consumed primarily by Options, also by Short Squeeze (magnitude), eventually Futures/Crypto.

### 7.1 Inputs

Price, returns, RV, volume, CVD, L1/L2, liquidity, news, catalysts, attention, macro, **SqueezeEvidence**, options flow, futures context.

### 7.2 Outputs

```text
Q01, Q05, Q10, Q25, Q50, Q75, Q90, Q95, Q99
mean, variance, skew
upside_tail_probability, downside_tail_probability
horizon, model_version, confidence
```

### 7.3 Modeling hierarchy

Baselines first: historical vol, EWMA, GARCH, HAR-RV, quantile regression.

Advanced ML only with out-of-sample evidence (QLIKE, CRPS, economic value).

---

## 8. Q inference flow (O3)

```text
Option Surface
    → No-Arbitrage Cleaning
    → Surface Representation (SVI-type research path)
    → Risk-Neutral Density
    → Q(S_T)
```

Expose: risk-neutral mean/variance/skew/kurtosis, upside/downside tail probabilities — only when chain quality sufficient.

---

## 9. P vs Q flow (O4) — intellectual core

For each horizon h:

```text
Δ_mean, Δ_variance, Δ_upside_tail, Δ_downside_tail, Δ_skew, Δ_event_move
```

Decomposed edges (never collapsed to one score):

```text
directional_edge
volatility_edge
skew_edge
term_structure_edge
event_edge
tail_edge
flow_information
dealer_amplification
liquidity_quality
execution_quality
model_confidence
data_confidence
```

Interpretation examples:
- "Model sees greater upside than market"
- "Market prices more downside tail risk"
- "Upside calls appear especially rich" (squeeze may already be priced)

Include volatility risk premium: `IV - ForecastRV` is informative but **not** automatic sell-vol signal.

Distinguish `TheoreticalEdge` vs `ExecutableEdge` after spread, slippage, commissions, legging risk.

---

## 10. Flow flow (O5)

Distinguish call/put volume from signed flow.

Where data permits: buyer/seller initiated, opening/closing, customer/dealer, single-leg/complex, premium paid, delta/gamma/vega equivalents.

Where unavailable: `FLOW_DIRECTION_UNCERTAIN`, `OPEN_CLOSE_UNKNOWN` — **fail closed**.

Abnormal flow: `ObservedFlow - ExpectedFlow` conditioned on underlying, DTE, moneyness, time-of-day, event state, regime.

---

## 11. Dealer flow (O6)

Separate uncertainty-aware subsystem.

Outputs: `estimated_dealer_delta/gamma/vega`, `gamma_regime`, `hedging_pressure_estimate`, `gamma_flip_estimate`.

Terminology: `estimated_gamma_exposure` — **not** `dealer_gamma` unless participant data justifies.

Every value: `method`, `assumptions`, `confidence`.

**Never:** OI × Gamma = true dealer gamma.

Publish to cross-lane for Order Flow confirmation and Short Squeeze reflexivity.

**Implementation (fixture scope):** `options/dealer.py` — method `OI_GAMMA_PROXY_V1`, confidence `LOW`, fail-closed on missing OI or invalid IV. Workspace field `dealer_snapshot`; cross-lane signals `GAMMA_AMPLIFICATION_POTENTIAL` and `ESTIMATED_HEDGING_PRESSURE`. Terminology remains `estimated_dealer_gamma` — not `dealer_gamma`.

---

## 12. Event volatility flow (O7)

### 12.1 Event state machine (Options-specific)

```text
NO_EVENT → EVENT_APPROACHING → EVENT_IMMINENT → EVENT_RESOLUTION → POST_EVENT_NORMALIZATION
```

### 12.2 Per-event outputs

`event_type`, `event_time`, `implied_event_move`, `forecast_event_move`, `event_volatility_premium`, `expected_post_event_IV`, `expected_IV_crush`, `vega_risk`.

---

## 13. Strategy flow (O8)

### 13.1 Taxonomy (economic exposure)

Directional, long vol, short vol, skew, term structure, tail protection — implemented as arbitrary multi-leg compositions, not hard-coded names only.

### 13.2 Generation pipeline

```text
P vs Q differences → candidate strategies → E[PnL] distribution
    → capital/risk/liquidity → best expression OR NO_CLEAR_EDGE
```

Bullish P may yield: stock, call, call spread, put spread, or nothing — depending on Q.

### 13.3 Payoff engine

`PnL(S_T)` for arbitrary legs; pre-expiration valuation via models or replayed marks.

### 13.4 Expected P&L metrics

`E[PnL]`, median, `P(PnL>0)`, VaR, ES, max loss/gain, capital requirement, return on capital.

**Never optimize win rate alone.**

---

## 14. Execution flow (O9)

Extend **shared** simulator (not parallel Options-only sim):

Single/multi-leg, stock-option combos, NBBO, spread crossing, partial fills, commissions, assignment, exercise, expiration.

American early exercise: deep ITM calls, dividends, low extrinsic.

**Implementation (fixture scope):** `options/execution.py` — method `NBBO_CONSERVATIVE_V1`; `execution/options_conservative.py` registered as `simulation.options_conservative`. Conservative spread crossing (long pays ask, short receives bid), multi-leg liquidity gating, expiration/assignment lifecycle via `portfolio/options_ledger.py`. Workspace field `execution_snapshot`; cross-lane signals `OPTIONS_EXECUTION_SIMULATED` and `ASSIGNMENT_RISK`. Equity `run_risk_simulation_evaluation` unchanged — options harness is separate for fixture scope.

---

## 15. Explanation flow

Every ranked strategy exposes evidence path:

```text
Strategy rank → edge components → P vs Q at horizon → surface points
    → liquidity cost → model/data confidence → source refs
```

Cross-lane contributions explicitly tagged:

```text
Native: flow, surface, IV term
Cross-Lane: squeeze ignition, CVD, catalyst
```

---

## 16. Cross-lane interfaces

### 16.1 Options publishes

See `OPTIONS_SHORT_SQUEEZE_ROADMAP_RECONCILIATION.md` §5.1.

Transport: `NormalizedLaneEvidence` via evidence bus — never direct imports.

### 16.2 Options consumes

`SqueezeEvidence`: state, probabilities, stress, fuel, exhaustion — as **features into P**, not as automatic call-buying rules.

### 16.3 Circular dependency prevention

Evidence tagged: `RAW | DERIVED | MODEL_OUTPUT | CROSS_LANE_MODEL_OUTPUT`.

Decision-time DAG validation. No same-timestamp self-reinforcement.

---

## 17. UI architecture (O4+)

Progressive disclosure card (target):

```text
MARKET EXPECTATION / MODEL EXPECTATION / PRIMARY FINDING
DIRECTION (distribution, not label-only)
SURFACE summary / FLOW / DEALER / BEST EXPRESSION / WHY
DATA CONFIDENCE / MODEL CONFIDENCE
```

Chain grid and surface charts behind disclosure layers.

---

## 18. Quality taxonomy

See `OPTIONS_DISCREPANCY_REGISTER.md` O-22 and implementation in `contracts/options_quality.py`.

Missing data → quality flag + unavailable — never silent zero.

---

## 19. Research targets (independent)

| Problem | Target | Validation |
|---|---|---|
| Direction | Return distribution | CRPS, quantile loss, calibration |
| Realized vol | RV_1d..RV_60d | QLIKE, MSE |
| IV | ΔIV | MAE, economic value |
| Surface | Future skew/term | Surface RMSE |
| Option returns | Contract/strategy return | Net return after costs |
| Delta-hedged | Vol edge isolation | VRP capture |

Walk-forward only. No random shuffle. Purge/embargo for overlapping windows.

---

## 20. Package layout (proposed)

```text
src/market_platform_foundation/
  contracts/
    options.py              # O1 canonical contract
    options_quality.py      # O1 quality flags
  options/                  # NEW package — lane-owned logic
    iv.py                   # O2
    greeks.py               # O2
    surface.py              # O2
    surface_qa.py           # O2
    risk_neutral.py         # O3
    edge.py                 # O4 P vs Q
    flow.py                 # O5
    dealer.py               # O6
    event_vol.py            # O7
    strategy.py             # O8
    payoff.py               # O8
  research/
    distribution/           # SHARED P2 — not under options/
      forecast.py
  cross_lane/
    evidence.py             # extended signals
  donor_bridge/
    cross_lane_adapter.py   # options publisher
```

---

## Related documents

- `OPTIONS_SHORT_SQUEEZE_ROADMAP_RECONCILIATION.md`
- `OPTIONS_DISCREPANCY_REGISTER.md`
- `OPTIONS_RESEARCH_PLAN.md`
- `CROSS_LANE_BOUNDARY_MATRIX.md`
