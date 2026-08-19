# Order Flow Read-Only Integration Lane

**Status:** `ACTIVE` — fixture-first CVD + L2 depth on admitted NVDA slices; OF1–OF9 foundation module.

Order Flow owns **observable auction mechanics and reusable microstructure evidence**. Short Squeeze, Options, and Futures **interpret** that evidence — they do not recompute CVD or OFI internally.

## Canonical documents

- [Current state audit](../research/ORDER_FLOW_CURRENT_STATE_AUDIT.md)
- [Target architecture](../research/ORDER_FLOW_TARGET_ARCHITECTURE.md)
- [Glossary](../research/ORDER_FLOW_GLOSSARY.md)
- [Four-lane roadmap reconciliation](../research/FOUR_LANE_ROADMAP_RECONCILIATION.md)

## Admitted fixtures

| Fixture ID | Symbol | Capability |
|---|---|---|
| `ADMITTED-CVD-NVDA-ORDERFLOW-001` | NVDA | Bar-level CVD with aggressor provenance |
| `ADMITTED-L2-NVDA-001` | NVDA | L2 depth + OFI + liquidity dynamics |
| `ADMITTED-L2-ES-001` | ES | Futures depth + OFI + liquidity |

## Workspace API

```powershell
cd integrated-market-platform
python tools/ui1/run_ui_api.py --serve --port 8766
```

- `GET /workspace/NVDA/order-flow` — bars + `cvd_summary` (confidence-weighted)
- `GET /workspace/NVDA/order-book` — snapshots + `latest_l1` + OFI + `latest_liquidity_summary`

## OF4 — Versioned OFI book-flow

Module: `src/market_platform_foundation/order_flow/ofi.py`

| Method | ID | Scope |
|---|---|---|
| BBO Cont-Kukanov-Stoikov delta | `ofi_bbo_delta_v1` | Best bid/ask only (backward-compatible delegate) |
| Multi-level CS sum | `ofi_multilevel_cs_v1` | Rank-based L2 depth (default on fixture ingest) |

Workspace payload fields (order-book + futures depth):

- `latest_ofi_value`, `latest_ofi_method`, `latest_ofi_version`, `latest_book_state_valid`
- Per-snapshot: `ofi_value`, `ofi_method`, `ofi_version`, `book_state_valid`

Golden regression: `tests/fixtures/order_flow/nvda_ofi_expected.json`

**OF-D11 — Sequence-gap invalidation:** When snapshots include `book_sequence`, pair-wise OFI/liquidity requires `curr = prev + 1`. Missing sequence on one side or a gap sets `book_state_valid=false`. Fixtures without `book_sequence` remain backward compatible.

**OF-D10 — Donor-bridge OFI:** `donor_bridge/bridge_depth_state.py` caches the previous bridge snapshot per symbol. First read degrades OFI (`latest_ofi_degraded`, `NO_PREV_SNAPSHOT`); subsequent reads compute `ofi_multilevel_cs_v1`.

## OF6 — Liquidity dynamics (displayed depth)

Module: `src/market_platform_foundation/order_flow/liquidity.py`

| Method | ID | Scope |
|---|---|---|
| Depth delta composite | `liquidity_depth_delta_v1` | Withdrawal/replenishment from L2 snapshot pairs |

Workspace payload fields (order-book + futures depth):

- `latest_liquidity_summary` — `depth_withdrawal`, `depth_replenishment`, `fragility_score`, `resiliency_score`, `liquidity_method`
- Per-snapshot liquidity fields mirror summary shape on ledger rows

Cross-lane signals: `LIQUIDITY_WITHDRAWAL`, `LIQUIDITY_REPLENISHMENT`, `BOOK_FRAGILITY_ELEVATED`

Golden regression: `tests/fixtures/order_flow/nvda_liquidity_expected.json`

## OF7 — Absorption / exhaustion (price response)

Module: `src/market_platform_foundation/order_flow/impact.py`

| Method | ID | Scope |
|---|---|---|
| Aggression vs mid progress | `impact_aggression_price_v1` | Join L2 snapshot pairs with aligned trade-bar delta |

Workspace payload fields (order-book + futures depth):

- `latest_impact_summary` — `impact_regime`, `absorption_score`, `exhaustion_score`, `price_efficiency`, `mid_delta`, `impact_method`
- Per-snapshot impact fields mirror summary shape on ledger rows

Cross-lane signals: `ABSORPTION_BUY`, `ABSORPTION_SELL`, `EXHAUSTION_BUY`, `EXHAUSTION_SELL`

Distinct from Short Squeeze `EXHAUSTION_RISK` (lifecycle fuel proxy).

Golden regression: `tests/fixtures/order_flow/nvda_impact_expected.json`

## OF8 — Short-horizon microstructure forecasts

Module: `src/market_platform_foundation/order_flow/forecast.py`

| Method | ID | Scope |
|---|---|---|
| Heuristic composite | `microstructure_heuristic_v1` | OFI + microprice + QI + bar delta with OF6/OF7 modulation |

**Boundary:** Distinct from SHARED P2 multi-day physical P (`research/distribution/forecast.py`). Do not emit `FORECAST_RV_ELEVATED` from OF8.

Workspace payload fields (order-book + futures depth):

- `latest_microstructure_forecast` — `direction_bias`, `continuation_probability`, `reversal_probability`, `expected_mid_delta`, `forecast_method`

Cross-lane signals: `MICROSTRUCTURE_CONTINUATION_UP`, `MICROSTRUCTURE_CONTINUATION_DOWN`, `MICROSTRUCTURE_REVERSAL_RISK`

Golden regression: `tests/fixtures/order_flow/nvda_forecast_expected.json`

## OF9 — Execution forecasts

Module: `src/market_platform_foundation/order_flow/execution_forecast.py`

| Method | ID | Scope |
|---|---|---|
| Book-aware heuristic | `execution_book_aware_v1` | Touch-depth fill probability + slippage + adverse selection |

Simulator tier: `execution/book_aware.py` — `simulation.book_aware_l2_v1` (partial fills capped by displayed touch depth; closes OF-D09).

Workspace payload fields (order-book + futures depth):

- `latest_execution_forecast` — `aggressive_fill_probability`, `expected_slippage_spread_fraction`, `adverse_selection_risk`, `execution_method`

Cross-lane signals: `EXECUTION_SLIPPAGE_ELEVATED`, `EXECUTION_FILL_RISK`, `ADVERSE_SELECTION_RISK_ELEVATED`

Golden regression: `tests/fixtures/order_flow/nvda_execution_forecast_expected.json`

## Cross-lane evidence published

| Signal | Meaning |
|---|---|
| `AGGRESSIVE_BUY_PRESSURE` | Net aggressive buy volume elevated |
| `AGGRESSIVE_SELL_PRESSURE` | Net aggressive sell volume elevated |
| `CVD_POSITIVE_SLOPE` / `CVD_NEGATIVE_SLOPE` | CVD momentum |
| `BOOK_IMBALANCE_BID` / `BOOK_IMBALANCE_ASK` | Resting liquidity skew (not aggression) |
| `LIQUIDITY_WITHDRAWAL` | Displayed depth drop between snapshots |
| `LIQUIDITY_REPLENISHMENT` | Displayed depth recovery |
| `BOOK_FRAGILITY_ELEVATED` | Composite fragility score elevated |
| `ABSORPTION_BUY` / `ABSORPTION_SELL` | Book flow absorption — weak price progress under aggression |
| `EXHAUSTION_BUY` / `EXHAUSTION_SELL` | Book flow exhaustion — decaying aggression, stalled progress |
| `MICROSTRUCTURE_CONTINUATION_UP` / `MICROSTRUCTURE_CONTINUATION_DOWN` | Short-horizon continuation bias from microstructure stack |
| `MICROSTRUCTURE_REVERSAL_RISK` | Elevated short-horizon reversal probability |
| `EXECUTION_SLIPPAGE_ELEVATED` | Expected slippage vs spread elevated |
| `EXECUTION_FILL_RISK` | Aggressive fill probability below comfort threshold |
| `ADVERSE_SELECTION_RISK_ELEVATED` | Post-fill adverse selection risk elevated |

## What CVD means here

```text
CVD = Σ (aggressive buy volume − aggressive sell volume)
```

Not buyer count. Not "more buyers than sellers." Positive CVD does not automatically imply bullish price forecast.

## Module entry point

```python
from market_platform_foundation.order_flow import (
    classify_trade,
    compute_cvd_state,
    compute_l1_state,
    compute_liquidity_dynamics,
    compute_impact_dynamics,
    compute_microstructure_forecast,
    compute_execution_forecast,
    compute_multilevel_ofi,
    build_execution_forecast_evidence,
    build_impact_evidence,
    build_liquidity_evidence,
    build_microstructure_forecast_evidence,
    build_order_flow_evidence,
)
```

## Tests

```powershell
python -m unittest tests.order_flow.test_order_flow_engine
python -m unittest tests.order_flow.test_queue
python -m unittest tests.order_flow.test_metaorder
python -m unittest tests.providers.test_order_flow
```

## OF10 — MBO / queue semantics

Module: `src/market_platform_foundation/order_flow/queue.py`

| Method | ID | Scope |
|---|---|---|
| FIFO displayed queue | `fifo_displayed_mbo_v1` | MBO order reconstruction + queue position estimate |

Fixture: `ADMITTED-MBO-ES-001` (`tests/fixtures/providers/order_flow/es_mbo_slice.json`)

Workspace payload fields (ES futures depth):

- `latest_queue_snapshot`, `mbo_capability_available`
- Execution forecast `queue_model_version` upgrades from `none` when MBO present

## OF11 — Metaorder detection primitives

Module: `src/market_platform_foundation/order_flow/metaorder.py`

| Method | ID | Scope |
|---|---|---|
| Persistent aggressive flow | `persistent_aggressive_flow_v1` | Consecutive same-side ClassifiedTrade clustering |

Cross-lane signals: `PERSISTENT_AGGRESSIVE_BUY_FLOW`, `PERSISTENT_AGGRESSIVE_SELL_FLOW`

Fixture regression: `tests/fixtures/providers/order_flow/nvda_metaorder_slice.json`
