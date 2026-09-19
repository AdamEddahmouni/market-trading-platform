# Fill-price realism methodology v1 (research only)

**Status:** FROZEN (2026-09-18, Lane F IMP-POST-RTH-CLOSE-08)  
**Authority:** `HISTORICAL_DEVELOPMENT` / `BOUNDED_HISTORICAL_OBSERVATION`  
**Increment:** `IMP-SIMULATOR-FILL-PRICE-REALISM-V1`

## Purpose

Bounded diagnostic experiment answering whether **documented bar-OHLC fill and MTM references** explain decoupling between directional accuracy and gross PnL on the same OpenD v3 corpus — without retuning strategies, without varying declared costs, and without changing Item 9 / `BarConservativeSimulator` semantics.

**Sibling lane:** cost sensitivity (`LANE-E-HYP-SIMULATOR-COST-SENSITIVITY-V4`) varies **bps only** at locked fill semantics. This lane varies **fill/MTM OHLC references only** at locked `cost_slippage_bps=5.0`.

## Question (allowed)

Does the sign of forward-return labels correlate with gross PnL differently under predeclared, lawful OHLC fill/MTM references on identical fill **schedules**?

## Questions (forbidden)

- Which fill assumption makes a baseline profitable?
- Which arm should be promoted to Paper or Item 9?
- Post-hoc arm selection using validate net_pnl ordering.

## Governed references

All arms use **only** bar fields on the **same fill bar** (or last bar for MTM) already admitted in historical development. No quote-touch, no mid-price, no tuned slippage overlays.

| Arm ID | Fill price at fill bar | MTM for open exposure |
|---|---|---|
| `REF_BASELINE_V3` | `BAR_ADVERSE_TOUCH` (long→high, short→low) | `MTM_LAST_BAR_CLOSE` |
| `REF_FILL_OPEN_MTM_CLOSE` | `BAR_OPEN` | `MTM_LAST_BAR_CLOSE` |
| `REF_FILL_CLOSE_MTM_CLOSE` | `BAR_CLOSE` | `MTM_LAST_BAR_CLOSE` |
| `REF_FILL_ADVERSE_MTM_OPEN` | `BAR_ADVERSE_TOUCH` | `MTM_LAST_BAR_OPEN` |
| `REF_FILL_OPEN_MTM_OPEN` | `BAR_OPEN` | `MTM_LAST_BAR_OPEN` |
| `REF_FILL_CLOSE_MTM_OPEN` | `BAR_CLOSE` | `MTM_LAST_BAR_OPEN` |

`BAR_ADVERSE_TOUCH` is the production research simulator policy (`phase7.bar-conservative/1.1.0`). Other arms are **counterfactual repricing** on the v3 fill schedule; they may be more or less conservative than adverse touch and are **not** candidates for optimistic promotion.

## Invariants

1. **Fill schedule locked:** reuse per-fill timestamps, quantities, and intent IDs from frozen v3 pack manifest (`imp-integrate-experiment-05-r3-opend-fill-economics-v3`). Do not re-run risk/simulator to change fill counts.
2. **Costs locked:** `simulator-research/notional-linear-bps/1.0.0` at `cost_slippage_bps=5.0` for every arm.
3. **Item 9:** no changes to `execution/simulator.py`, calibration protocol, or prospective collector semantics.
4. **v3 immutability:** do not edit or rerun v3 evidence JSON.
5. **Dataset:** fingerprint `355FDBB852B94B964B62331839B58C3A336D1B52DB2F17FA05D30BA31389885B` (v3 corpus pin).

## Primary metrics

- `directional_accuracy` (unchanged from v3 label contract)
- `gross_pnl`, `gross_realized_pnl`, `gross_unrealized_pnl` per arm
- `gross_realized_pnl_vs_directional_accuracy_correlation` (validate split; descriptive)
- Per-fill audit: `fill_reference_id`, `mtm_reference_id`, `fill_price_minor`, `mark_price_minor`, `bar_available_time`

## Evidence class

`HISTORICAL_DEVELOPMENT` simulation research. Never upgrade to prospective, paper-calibrated, or live labels.

## Experiment identity

| Field | Value |
|---|---|
| `HYPOTHESIS_ID` | `LANE-E-HYP-SIMULATOR-FILL-PRICE-REALISM-V1` |
| `EXPERIMENT_ID` | `imp-integrate-experiment-06-r1-opend-fill-price-realism-v1` |
| Engineering index | [IMP_INTEGRATE_EXPERIMENT_06_LANE_F_FILL_PRICE_REALISM_V1.md](../../../engineering/IMP_INTEGRATE_EXPERIMENT_06_LANE_F_FILL_PRICE_REALISM_V1.md) |
