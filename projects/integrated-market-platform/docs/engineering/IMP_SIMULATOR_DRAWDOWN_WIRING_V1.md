# IMP simulator drawdown wiring (Lane E)

**Hypothesis:** `LANE-E-HYP-SIMULATOR-DRAWDOWN-WIRING-V1`  
**Source finding:** `LANE-E-FND-019` (v3 pack manifest `drawdown: null`)

## Diagnosis (read-only)

V3 baseline pack metrics expose `drawdown` via `compute_component_research_metrics` →
`simulator_summary.max_drawdown`. The prediction-coupled simulator set
`max_drawdown` from `risk_result["portfolio"]["max_drawdown"]` with source
`RISK_PORTFOLIO_INHERITED`, but `run_risk_simulation_from_signal_interpretations`
returns ledger/fills only — **no `portfolio` summary**. Fill-economics V3 (`3.0.1`)
computes PnL/costs but did not emit drawdown. Frozen v3 JSON manifests remain
unchanged; null drawdown there is an observed reporting gap, not a rerun.

## Proposed wiring

| Stage | Responsibility |
|-------|----------------|
| `aggregate_fill_economics` | Build net-MTM PnL equity curve (0 → per-fill → terminal mark); compute `max_drawdown` |
| `simulator_drawdown.py` | Mark-at-time helpers, peak-to-trough, version constants |
| `run_historical_development_simulator_research` | Surface `max_drawdown`, `max_drawdown_source`, `drawdown_metrics_version`, `equity_curve_point_count` from execution economics |
| `metrics.py` / baseline pack | Unchanged mapping: `drawdown` ← `max_drawdown` |

**Curve definition:** cumulative net mark-to-market PnL in native currency (same
units as `net_pnl`), **not** total cash equity. Source token:
`EQUITY_CURVE_NET_MTM`. Metrics version: `simulator-research/net-mtm-drawdown/1.0.0`.
`ACCOUNTING_VERSION` stays `3.0.1`.

**Limitation (v1):** curve samples at fill times plus terminal bar mark; intra-hold
bar paths between fills are not walked (document before promotion experiments).

## Evidence / experiment policy

- Do **not** backfill drawdown into v3 manifests or relabel v3 runs.
- Promotion requires a **NEW** experiment hash after merge; validate non-null
  drawdown when validate `net_pnl` variance > 0.

## Tests

`tests/platform/test_simulator_drawdown_wiring_v1.py` — unit + integration.

## Next increment (optional)

- Bar-granularity equity curve for open-position drawdown during holds.
- Align `coverage` with a research-native definition (still inherited from absent
  risk portfolio today).
