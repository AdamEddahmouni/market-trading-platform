# Order Flow Read-Only Integration Lane

**Status:** `ACTIVE` — fixture-first CVD + L2 depth on admitted NVDA slices; OF1–OF3 foundation module.

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
| `ADMITTED-L2-NVDA-001` | NVDA | L2 depth snapshots + BBO OFI |
| `ADMITTED-L2-ES-001` | ES | Futures depth (validation lab) |

## Workspace API

```powershell
cd integrated-market-platform
python tools/ui1/run_ui_api.py --serve --port 8766
```

- `GET /workspace/NVDA/order-flow` — bars + `cvd_summary` (confidence-weighted)
- `GET /workspace/NVDA/order-book` — snapshots + `latest_l1` (microprice, QI)

## Cross-lane evidence published

| Signal | Meaning |
|---|---|
| `AGGRESSIVE_BUY_PRESSURE` | Net aggressive buy volume elevated |
| `AGGRESSIVE_SELL_PRESSURE` | Net aggressive sell volume elevated |
| `CVD_POSITIVE_SLOPE` / `CVD_NEGATIVE_SLOPE` | CVD momentum |
| `BOOK_IMBALANCE_BID` / `BOOK_IMBALANCE_ASK` | Resting liquidity skew (not aggression) |

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
    build_order_flow_evidence,
)
```

## Tests

```powershell
python -m unittest tests.order_flow.test_order_flow_engine
python -m unittest tests.providers.test_order_flow
```
