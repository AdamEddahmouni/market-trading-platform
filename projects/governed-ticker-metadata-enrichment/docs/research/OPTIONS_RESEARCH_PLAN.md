# Options Research Plan (Deliverable 8)

**Status:** Research roadmap — no implementation authorization implied  
**Date:** 2026-08-18  
**Prerequisite:** `OPTIONS_SHORT_SQUEEZE_ROADMAP_RECONCILIATION.md`

---

## 1. Research objectives

Transform Options from unusual-activity plumbing into a **distribution and pricing intelligence engine** that answers:

> Where does our forecast P materially disagree with market-implied Q — in an executable way?

Secondary: publish evidence that improves Short Squeeze ignition/confirmation without collapsing lanes.

---

## 2. Datasets

### 2.1 Phase A (fixture / admitted — now)

| Dataset | ID | Use |
|---|---|---|
| BIYA options activity | `ADMITTED-OPTIONS-BIYA-001` | Contract schema, liquidity gate, cross-lane stub |
| NVDA order flow | Phase 10 fixture | Cross-lane P inputs |
| Bar OHLCV fixtures | Phase 4+ | RV baselines |
| SS historical cohort | `historical_squeeze_cohort_v1.json` | Joint JQ-1–JQ-6 episodic tests |

### 2.2 Phase B (required for O2–O4)

| Dataset | Requirement | Priority |
|---|---|---|
| Single-name full chain snapshots (3–5 symbols) | Surface + IV validation | HIGH |
| 2+ years daily chain history (1 symbol minimum) | Walk-forward vol/surface | HIGH |
| Earnings dates + straddle prices | Event vol (O7) | MEDIUM |
| FRED risk-free rate | Carry | LOW (free) |

**Admission status:** `PENDING` — see [`OPTIONS_PHASE_B_ADMISSION.md`](../engineering/OPTIONS_PHASE_B_ADMISSION.md) and [`manifests/options/phase-b-chain-history-admission.json`](../../manifests/options/phase-b-chain-history-admission.json). O10 Phase B walk-forward scaffolding in `options/research/harness.py` fail-closes until datasets are admitted.

### 2.3 Phase C (O5+)

| Dataset | Requirement |
|---|---|
| Option trade prints with aggressor | Signed flow |
| Intraday chain snapshots | 0DTE (O11) |

### 2.4 Partitioning rules

- All datasets: aligned `event_time`, `available_time`
- Never allow newer Options observation into earlier SS decision
- Centralize PIT joins in platform replay
- Walk-forward chronological only; purge/embargo for overlapping expirations

---

## 3. Independent prediction targets

Do not mix labels.

| Target ID | Variable | Horizon | Primary metrics |
|---|---|---|---|
| T-DIR | Return distribution | 1d, 5d, 14d, 30d | CRPS, quantile loss, calibration |
| T-RV | Realized volatility | 1d, 5d, 20d, 60d | QLIKE, MSE |
| T-IV | ΔIV (ATM) | To next expiry | MAE |
| T-SKEW | 25Δ risk reversal change | Weekly | MAE |
| T-TERM | Term slope change | Monthly | MAE |
| T-EVT | Earnings move | Event | Implied vs realized move |
| T-OPT | Option return | Contract life | Net return after costs |
| T-DH | Delta-hedged return | Daily rebalance | VRP capture |

---

## 4. Features

### 4.1 Native Options features (O2–O6)

- IV level, skew, term structure, curvature
- Volume/OI ratios (not direction alone)
- Signed flow (when available)
- Abnormal flow residuals
- Estimated gamma exposure (proxy, confidence-tagged)
- Event state, implied event move

### 4.2 Cross-lane features (SHARED P3)

From Short Squeeze:
- `squeeze_state`, `ignition_strength`, `remaining_fuel`, `exhaustion_risk`
- Use as P inputs only — never as automatic strategy triggers

From Order Flow:
- CVD slope, aggressive buy pressure

From Catalyst/Attention:
- Event proximity, attention acceleration

### 4.3 Forbidden feature practices

- Call volume as bullish proxy
- OI as directional signal
- OI × gamma as dealer gamma without proxy label
- Missing flow → zero
- Same-timestamp squeeze model output → options model input → squeeze

---

## 5. Models (evidence hierarchy)

### 5.1 Baselines (required before ML)

**Direction / distribution:**
- Quantile regression
- Parametric (skewed-t, mixture)
- Logistic (binary slices only — not primary)

**Volatility:**
- Historical close-to-close
- EWMA
- GARCH(1,1)
- HAR-RV

**Surface:**
- Parametric skew (SVI research path)
- Spline on valid quotes only

**Option returns:**
- Linear factor exposure (delta, vega, vol)

### 5.2 Advanced (only if baselines beaten OOS)

- Gradient boosting (quantile)
- Random forests
- Mixture density networks
- Normalizing flows

**Primary requirement:** calibrated tails, not architecture novelty.

### 5.3 Validation metrics

| Type | Metrics |
|---|---|
| Probabilities | Brier, log loss, calibration plots |
| Distributions | CRPS, PIT, tail coverage |
| Volatility | QLIKE, MSE, MAE |
| Economic | Net return after spread/commission/slippage |

### 5.4 Walk-forward protocol

- Chronological folds only
- Account for overlapping expirations
- Event clustering (earnings season)
- Regime stratification: low-vol, high-vol, crash, meme, rate shock, 0DTE-heavy

---

## 6. P vs Q research program (O4)

### 6.1 Core comparisons

For each horizon:
- `mean_difference`, `variance_difference`
- `upside_tail_difference`, `downside_tail_difference`
- `skew_difference`, `event_move_difference`

### 6.2 Edge decomposition

Report separately: directional, vol, skew, term, event, tail, flow, dealer, liquidity, execution, model/data confidence.

### 6.3 VRP research

Estimate `E[IV - RV | regime, maturity, event_state, skew, macro]`.

Document: IV ≠ unbiased RV forecast.

### 6.4 Executable edge

After: spread, slippage, commissions, fill probability, legging risk, margin.

---

## 7. Strategy research (O8)

### 7.1 Pipeline

```text
P vs Q → candidate structures → E[PnL] under P → liquidity filter → rank or NO_TRADE
```

### 7.2 Evaluation (every strategy)

- Gross/net return, EV, Sharpe, Sortino, max drawdown
- VaR, expected shortfall
- Win rate **with** average win/loss
- Capital usage, turnover, spread cost, slippage

### 7.3 Path-sensitive extensions

- Gamma scalping with hedging frequency + friction
- Delta-hedged vol edge isolation

---

## 8. Joint Short Squeeze research (JQ-1 – JQ-6)

| ID | Hypothesis | Design |
|---|---|---|
| JQ-1 | SS state → upside IV/skew/RV | Event study on cohort; control price/vol |
| JQ-2 | Signed call demand → ignition | Logistic with/without flow feature |
| JQ-3 | Negative gamma proxy → squeeze magnitude | Conditional on SS ACTIVE state |
| JQ-4 | Rich upside skew → lower call EV during SS setup | P vs Q conditional on SS state |
| JQ-5 | Options flow leads equity ignition | Lead-lag at 1d/3d horizons |
| JQ-6 | SS exhaustion → IV crush | Post-exhaustion IV panel |

**Diagnostics:** GME, AMC — plus high-SI non-squeezes, gamma rallies without covering, false flow signals.

---

## 9. Regime test matrix

| Regime | Test requirement |
|---|---|
| Low volatility | Surface sparsity handling |
| High volatility | IV solver stability |
| Crashes | Tail calibration |
| Meme episodes | Diagnostic only — not design target |
| Earnings seasons | Event vol |
| Liquidity crises | Executable edge gating |
| 0DTE-heavy | Deferred to O11 |

---

## 10. Research milestones

| Milestone | Output | Gate |
|---|---|---|
| R-O1 | Contract schema + quality taxonomy | O1 |
| R-O2 | IV solver accuracy vs vendor on admitted chain | O2 |
| R-O3 | Surface QA rejects bad fixtures | O2 |
| R-O4 | Q extraction on clean surface | O3 |
| R-O5 | P baseline beats naive on RV (QLIKE) | SHARED P2 | **PASS (fixture scope, O10-S5)** — `nvda_bars_slice.json`; Phase B multi-year OOS required for production |
| R-O6 | P vs Q edge correlates with delta-hedged returns | O4 | **PASS (fixture scope, O10-S5)** — `nvda_r_o6_panel_slice.json`; dynamic panel from chain+bars deferred to Phase B |
| R-O7 | Abnormal flow OOS predictability | O5 |
| R-O8 | Proxy gamma OOS vs realized hedge pressure | O6 |
| R-O9 | Earnings IV crush model calibration | O7 |
| R-O10 | Strategy optimizer positive EV after costs (one regime) | O8 |

---

## 11. What not to research yet

- 0DTE intraday before O9 execution
- Distributional ML before baselines
- Dealer true positioning without data
- Universal options score
- Squeeze probability → buy calls mapping

---

## Related documents

- `OPTIONS_TARGET_ARCHITECTURE.md`
- `PLATFORM_COOPERATIVE_MASTER_ROADMAP.md`
- `SHORT_SQUEEZE_CAUSAL_RESEARCH_SPEC.md` (squeeze-core)
