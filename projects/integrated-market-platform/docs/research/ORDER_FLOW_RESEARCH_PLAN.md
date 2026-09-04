# Order Flow Research Plan (Deliverable 8)

**Date:** 2026-08-18  
**Validation environment:** ES futures L2 (when admitted), NVDA fixture for regression

---

## Baseline features (M1–M3)

| Feature | Horizon | Normalization |
|---|---|---|
| CVD | bar, session | z-score by session volume |
| CVD slope | 1–5 bars | per-instrument baseline |
| spread | tick | spread_in_ticks |
| queue imbalance | sub-minute | raw + percentile |
| microprice displacement | sub-minute | ticks from mid |

---

## Targets (separate models — no opaque `order_flow_signal`)

### Price
- P(next mid move up) at 1s, 5s, 30s, 1m
- expected mid change

### Volatility
- volatility_burst_probability

### Liquidity
- expected spread, expected depth, liquidity_shock_probability

### Execution
- maker_fill_probability, expected_slippage, adverse_selection_risk

---

## Model progression

1. Logistic regression / calibrated boosting baselines
2. Benchmark each stage against M1 (CVD-only)
3. Advanced LOB ML only after latency-adjusted economic value demonstrated

---

## Latency assumptions

Test at: 0ms, 50ms, 100ms, 250ms, 500ms. Include `signal_half_life` metadata.

---

## Costs

Spread + fees + rebates + slippage + market impact + queue loss + latency.

---

## Cross-lane research questions

| ID | Question |
|---|---|
| OF-Q1 | Does OFI outperform CVD for next ES mid move? |
| OF-Q2 | Does multi-level OFI beat L1 OFI after costs? |
| OF-Q3 | Does liquidity withdrawal improve squeeze ignition beyond CVD? |
| OF-Q4 | Does book fragility improve futures liquidation prediction? |
| OF-Q5 | Does observed flow validate options dealer hedge estimates? |
| OF-Q6 | Does absorption predict reversal after controlling for OFI? |
| OF-Q7 | Does microprice improve squeeze entry timing? |
| OF-Q8 | Does fill-probability forecasting reduce execution costs? |
| OF-Q9 | Does MBO queue modeling beat simpler approximations? |
| OF-Q10 | Can persistent flow identify probable metaorders? |

---

## Walk-forward protocol

Chronological splits; separate sessions, days, volatility regimes, instruments. No random shuffle of microstructure events.
