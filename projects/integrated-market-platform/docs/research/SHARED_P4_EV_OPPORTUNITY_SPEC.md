# SHARED P4 — EV / Opportunity Layer Spec

**Status:** COMPLETE (fixture scope)  
**Date:** 2026-08-18  
**Authority:** Platform-owned fusion; lanes supply inputs only

---

## Objective

Single cross-lane framework fusing **probability × payoff × costs × liquidity** into an auditable opportunity snapshot. Lanes do **not** own separate EV engines.

## Architecture boundary

| Layer | Owner | Responsibility |
|---|---|---|
| Short Squeeze | SS lane | Occurrence probability, magnitude, fuel (inputs) |
| Options | Options lane | Strategy payoff, friction, liquidity gates (inputs) |
| Order Flow | OF lane | CVD confidence, book imbalance (inputs) |
| SHARED P2 | Platform | Physical P quantiles (input to O8 payoff) |
| **SHARED P4** | **Platform** | **Fusion semantics and workspace snapshot** |

Evidence bus (SHARED P3) publishes lane signals; SHARED P4 sits **downstream** and does not replace `STRATEGY_OPPORTUNITY_RANKED`.

## Module layout

```text
cross_lane/opportunity.py   — input/fusion dataclasses + version constants
cross_lane/extractors.py    — snapshot dict → input contracts
cross_lane/fusion.py        — fuse_opportunity_v1, build_opportunity_snapshot
donor_bridge/opportunity_adapter.py — evidence publish + bundle builder
```

## Fusion formula (v1)

```text
gross_ev = expected_pnl - friction_cost
occurrence_weight = squeeze_hazard_probability when squeeze-aligned template else 1.0
liquidity_factor = 0.0 if liquidity gates failed else f(cvd_confidence, book_imbalance)
fused_net_ev = gross_ev × occurrence_weight × liquidity_factor
```

**Squeeze-aligned templates:** `long_call_atm`, `bull_call_spread`, `long_otm_call` when squeeze state is elevated (`VULNERABLE`, `IGNITION_WATCH`, `ACTIVE_SQUEEZE`, `LIVE_CONFIRMATION`).

## Anti double-counting

1. Options O8 already maps physical-P quantiles to payoff scenarios via `expected_pnl_under_physical_p`.
2. SHARED P4 **does not** re-run physical-P payoff math.
3. SS probability applies only as `occurrence_weight` for squeeze-aligned bullish templates.
4. Friction is subtracted once in `gross_ev`; costs block exposes `friction_cost` and `entry_cost` explicitly.

## Outcomes

| Outcome | Meaning |
|---|---|
| `RANKED` | `fused_net_ev > 0` |
| `NO_ACTIONABLE_EDGE` | Valid research outcome (liquidity blocked or EV ≤ 0) |
| `UNAVAILABLE` | Fail-closed — missing strategy/payoff inputs |

## Evidence signals

| Signal | Provenance | When |
|---|---|---|
| `CROSS_LANE_OPPORTUNITY_FUSED` | `CROSS_LANE_MODEL_OUTPUT` | `fused_net_ev > 0` |
| `OPPORTUNITY_NO_ACTIONABLE_EDGE` | `CROSS_LANE_MODEL_OUTPUT` | No actionable fused edge |

## Workspace wiring

- `build_workspace_opportunity_payload` in `providers/projections.py`
- `opportunity_snapshot` attached to options and squeeze workspace payloads
- Disclaimer: research decomposition, not a trade recommendation

## Fixture scope (NVDA)

Golden regression: `tests/fixtures/providers/opportunity/nvda_opportunity_fusion_expected.json`

Cooperative path uses:

- `nvda_strategy_optimizer_slice.json` (O8 strategy)
- Squeeze causal `ACTIVE_SQUEEZE` + order-flow aggression fixture

## Deferred

| Item | Blocker |
|---|---|
| Futures outright/curve fusion | F8–F10 incomplete | **DONE** (fixture scope; `FuturesInput` + regime factor) |
| Order Flow OF9 execution forecasts | DONE — `latest_execution_forecast` + P4 v1.2 liquidity enrichment |
| Calibrated walk-forward strategy EV | R-O10 |
| SHARED P5 portfolio ranking | Separate milestone |
| Per-lane EV engines | Architectural violation |

## Tests

- `tests/cross_lane/test_opportunity_fusion.py`
- `tests/cross_lane/test_opportunity_evidence.py`
- `tests/donor_bridge/test_cross_lane_integration.py` (NVDA end-to-end)
