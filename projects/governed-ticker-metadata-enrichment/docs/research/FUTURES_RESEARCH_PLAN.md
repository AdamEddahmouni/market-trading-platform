# Futures Research Plan (Deliverable 8)

**Date:** 2026-08-18  
**Status:** Research hypotheses — not architectural truths

---

## 1. Families (prioritized for project scope)

| Family | Priority | Rationale |
|---|---|---|
| EQUITY_INDEX (ES/NQ) | P1 | Existing ES fixture, cross-lane with Options/Squeeze |
| ENERGY (CL/NG) | P2 | Curve/fundamental research value |
| TREASURY (ZN/UB) | P2 | RV + macro event overlap |
| FX | P3 | Rate differential carry |
| METALS | P3 | Gold vs industrial split |
| AGRICULTURE | P3 | Seasonality complexity |
| SHORT_RATE | P3 | Policy path vs forecast |
| CRYPTO_FUTURES | Future | Leverage stress reuse |

---

## 2. Forecast targets (separate labels)

- Outright return (multi-horizon)
- Realized volatility
- Curve slope change
- Calendar spread return
- Basis convergence
- Positioning unwind
- Liquidation event (binary/regime)
- Macro-event reaction
- Microstructure return (seconds–minutes)

Never train one label called "Futures Prediction."

---

## 3. Baseline features

### Trend (F5)
- trend_1m, trend_3m, trend_6m, trend_12m (vol-scaled)
- Breakout/persistence baselines
- Logistic/linear regression before boosting

### Carry (F5)
- Carry level, percentile, change — per family formula
- Not assumed positive carry = positive return

### Curve (F3/F5)
- Slope, curvature, twist, calendar spread momentum
- Mean reversion baselines for commodities

### Positioning (F4)
- COT net percentile, velocity, crowding regimes
- OI change + price joint hypotheses

### Order Flow (consume P1)
- CVD slope, DOM imbalance, session-conditioned RVOL

### Leverage stress (F8)
- Margin change percentile + crowding + liquidity

---

## 4. Models (baseline first)

| Target | Baseline | Advanced (after OOS) |
|---|---|---|
| Direction | Trend + logistic | Gradient boosting |
| Volatility | EWMA, HAR | GARCH, boosting |
| Curve | Slope mean reversion | Factor models |
| Positioning | Percentile regimes | Logistic |
| Microstructure | Logistic on CVD/DOM | Boosting |
| Liquidation | Rule-based stress composite | Validated cascade detector |

---

## 5. Validation

- Chronological / walk-forward only
- Account rolls, expirations, macro clustering
- Embargo/purging for overlapping horizons
- Regime-stratified evaluation
- Cross-contract generalization tests (ES success ≠ CL success)

---

## 6. Metrics

**Forecasts:** RMSE, MAE, log loss, Brier, calibration, QLIKE  
**Trading:** Net PnL, Sharpe, Sortino, max DD, ES, turnover, roll cost, margin usage

---

## 7. Cross-lane research questions (F112)

| ID | Question |
|---|---|
| FQ-1 | Does Options tail risk improve ES forecasts beyond trend/CVD/vol? |
| FQ-2 | Does futures positioning improve Short Squeeze market-regime classification? |
| FQ-3 | Do squeeze clusters predict index futures order flow / vol? |
| FQ-4 | Does negative dealer gamma + futures order flow raise intraday RV? |
| FQ-5 | Does futures CVD confirm estimated dealer hedge flows? |
| FQ-6 | Do margin increases predict liquidation risk controlling for vol? |
| FQ-7 | Does carry retain predictive power after realistic rolls/costs? |
| FQ-8 | Does COT crowding improve reversal/continuation forecasts? |
| FQ-9 | Do inventory/curve interactions beat price-only commodity models? |

---

## 8. Dependencies

- SHARED P2 required for physical distribution consumption (not duplicate in Futures)
- Order Flow P1 for microstructure features
- O2/O3 for Options cross-lane vol context
- F1/F2 before trustworthy backtests
