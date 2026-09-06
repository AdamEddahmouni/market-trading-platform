# Formula ledger (Phase 0)

Machine-readable source of truth: [`formula_ledger.json`](formula_ledger.json) (`formula_ledger_v1`, 2026-09-05, 89 rows).

This inventory pins **units, windows, variance convention, fail-closed behavior, and capability class**. It does not claim predictive edge. Trading gates G1–G6 stay closed.

Canonical trees: `projects/integrated-market-platform`, `projects/short-squeeze-project`.

## Capability classes

| Class | Meaning |
|---|---|
| `exact_metric` | Specified arithmetic; golden-testable against this spec |
| `research_baseline` | Honest estimator / last-value / Gaussian P — not an edge |
| `heuristic_unconstrained` | Unfitted weights/scalars, pinned as versioned constants (not calibrated here) |

## Variance mix (do not unlabeled-fuse)

- **Population `/n`:** squeeze Decimal σ (ADR 0033), BVC, futures carry/spread z
- **Sample `/n−1`:** `realized_vol.py`, intel `realized_vol`, jump detect, HAR component RV
- **n/a:** prices, ratios, scores, EWMA/GARCH recursions

## ADAM return-definition split

Squeeze `PERCENTAGE_RETURN` is **Decimal close-to-close** (`close_to_close_completed.v1`).

ADAM ignition is **not** that metric:

- `current_percentage_change` is screener `percentage_change` evidence
- `completed_bar_acceleration` is **float open→close** percent vs a trimmed mean of prior open→close percents (`squeeze.bar_acceleration`)

Do not compare ignition to return z-scores or physical P as if they shared a return definition.

## Families (counts)

See JSON `formulas[]` for rows. Summary at generation:

| Family | What is pinned |
|---|---|
| Squeeze Decimal | Returns, gaps, ranges, volume/return baselines, z-scores, SI/borrow/DTC, bar acceleration |
| ADAM | Pressure/ignition weights, linear maps, classification thresholds |
| CVD / OFI / L1 / impact | CS-OFI, BVC, CVD, L1 microprice/QI, liquidity/impact heuristics |
| Vol / physical P | Close-to-close RV, Parkinson, EWMA λ=0.94, unfitted GARCH/HAR, Gaussian P (mean ≡ 0) |
| Options IV/Greeks/Q/P−Q | BSM, Newton IV, greeks day-count, default Q `risk_neutral_log_normal_moment_approx_v1`, additive discrete BL `risk_neutral_breeden_litzenberger_v1` (not the O3 default), friction fail-closed without underlying price, O10/R-O6 fail-closed without rate |
| Fusion P4 EV | Product formula plus pinned 0.85/1.05 liquidity and futures regime scalars |
| Futures | Vol-scaled trend, calendar carry, population carry/spread z, tanh feature scales |
| Fast signals | Window momentum, sample vol, rvol, spread, depth, CVD |
| Strategy interpretation | Naive last-value + FORECAST_MOMENTUM / whale alignments as `research_baseline` |
| Squeeze models | Unfitted logistic hazard weights `(0.8, 0.5, 0.3)` |

## Pinned heuristic constants (not calibrated)

Named in JSON `pinned_constants` on the parent formula. Notable:

- Fusion liquidity: support **1.05**, oppose **0.85**, plus fragility/fill/slippage haircuts
- GARCH(1,1): ω=**1e-6**, α=**0.05**, β=**0.90**
- HAR-RV: **0.3 / 0.4 / 0.3** on 5 / 22 / 66
- Squeeze logistic: weights **(0.8, 0.5, 0.3)**
- Options friction: no silent `underlying_price_assumption` of 100.0; fail closed unless assumed or inferred from activities
- Options signed-flow (O5) greeks-equivalent aggregation: no silent `DEFAULT_SPOT`, `DEFAULT_VOL`, or `DEFAULT_RATE`; fail closed (`UNDERLYING_PRICE_ASSUMPTION_MISSING` or `BSM_VOL_OR_RATE_ASSUMPTION_MISSING`, `net_*_flow=None`) unless explicit/inferred spot **and** positive tape/kwarg rate **and** vol
- Options O2 surface: no silent `strike × 1.02/0.98`; skip the point without positive underlying or positive rate; stamp both when present (`sigma_kt_v3`). O2/O3/dealer have no silent `rate=0.05` (fail closed: skip / `BSM_VOL_OR_RATE_ASSUMPTION_MISSING` / `RATE_ASSUMPTION_MISSING`)
- Options O10 / R-O6: no silent `rate=0.05`; missing positive rate (kwarg else P/Q dict) → `RATE_ASSUMPTION_MISSING` (`delta_hedged_research_v2` / `r_o6_research_v2`)
- Options discrete BL: `min_unique_strikes=5`, density mass band `[0.85, 1.15]`, tail threshold `0.05` (`risk_neutral_breeden_litzenberger_v1`)

## Phase 1 naming / fail-closed (applied)

1. Default Q version is `risk_neutral_log_normal_moment_approx_v1`. Discrete Breeden–Litzenberger is a separate fail-closed path (`risk_neutral_breeden_litzenberger_v1`); it is not the O3 default and does not fall back to average-IV log-normal.
2. OFI consumers must use `usable_ofi_value` / `book_state_valid` (invalid books still encode 0.0 on the primitive)
3. Fusion subtracts friction from gross `expected_pnl` unless already equal to `net_expected_pnl`
4. Physical P mean is identically 0; P−Q `directional_edge` is stamped `vs_zero_drift_baseline`
5. Strategy identities remain `baseline_only` interpretations of naive last-value

Golden tests live in `tests/formulas/` (validation suite id `formulas`). O5 signed-flow greeks require explicit/inferred spot plus tape/kwarg vol and rate. O2 skips points without a positive underlying or positive rate. Dealer greeks require the same rate resolve order (`options_dealer_proxy_v2`). O10/R-O6 research snapshots require the same fail-closed rate (no silent 0.05). Heuristic pins are drift-guarded by `tests/formulas/test_heuristic_pin_drift.py` (unfitted fusion/GARCH/HAR/ADAM/logistic; dealer/Q/O10/R-O6 rate pins removed).
