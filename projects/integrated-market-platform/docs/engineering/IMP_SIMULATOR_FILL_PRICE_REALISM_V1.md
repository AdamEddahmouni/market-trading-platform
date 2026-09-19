# IMP simulator fill-price realism (Lane E)

**Hypothesis:** `LANE-E-HYP-SIMULATOR-FILL-PRICE-REALISM-V1`  
**Source finding:** `LANE-E-FND-017`  
**Authority:** `HISTORICAL_DEVELOPMENT` diagnostic only — not Paper/Item 9 fill calibration.

## Doc routing (do not duplicate)

| Role | Authoritative path |
|------|-------------------|
| Lane C pre-exec methodology (frozen) | `evidence/historical-research/imp-simulator-fill-price-realism-v1/methodology_v1.json` |
| Lane C readiness snapshot (Sep 18) | `evidence/historical-research/imp-simulator-experiment-specs-sep18/lane_c_readiness_v1.json` |
| Post-freeze experiment + execution (#285) | [IMP_INTEGRATE_EXPERIMENT_06_LANE_F_FILL_PRICE_REALISM_V1.md](IMP_INTEGRATE_EXPERIMENT_06_LANE_F_FILL_PRICE_REALISM_V1.md), [FILL_PRICE_REALISM_V1.md](../research/methodology/fill/FILL_PRICE_REALISM_V1.md) |

This document remains the **simulator binding and problem statement** reference; execution receipts live under experiment 06 evidence.

## Status (Lane C snapshot — Sep 18, frozen)

| Gate | Value |
|------|-------|
| `SPEC_READY` | **YES** |
| `IMPLEMENTATION_READY` | **NO** (per-fill audit fields + alternate fill policies not implemented) |
| `EXECUTED` | **NO** |

## Status (post close — merged [#285](https://github.com/AdamEddahmouni/market-trading-platform/pull/285))

| Gate | Value |
|------|-------|
| `SPEC_READY` | **YES** (frozen methodology + experiment 06 protocol) |
| `IMPLEMENTATION_READY` | **YES** (`fill_price_realism_harness.py`, CLI, tests) |
| `EXECUTED` | **YES** (`EXECUTED_BOUNDED_HISTORICAL_OBSERVATION`) |

| Field | Value |
|-------|-------|
| `experiment_id` | `imp-integrate-experiment-06-r1-opend-fill-price-realism-v1` |
| `experiment_definition_hash` | `C4FCD3AB6CA6AEE57C91A0D709EC8D77EBFA6AA774542BF9AAD9FC761C2D1149` |
| `pack_run_id` | `6A66AE5C50700426F71B3734E6FC6A43` |
| Run record | `evidence/historical-research/imp-integrate-experiment-06-r1-opend-fill-price-realism-v1/fill_price_realism_run_record.json` |

## Problem statement (bounded)

On the frozen OpenD v3 validate split, `directional_accuracy` (forward-return label alignment) can rank baselines differently from `gross_pnl` / `net_pnl` because simulated economics use **bar-conservative execution prices** and open exposure, not label midpoints.

This spec documents the **current** fill and mark policies and **lawful historical-research alternatives** exercised in experiment 06 (separate hash). It does **not** change `phase7.bar-conservative/1.1.0` internals used by v3 receipts or Item 9.

## Frozen dataset and baselines

Same pins as cost sensitivity v4:

- `dataset_fingerprint`: `355FDBB852B94B964B62331839B58C3A336D1B52DB2F17FA05D30BA31389885B`
- Baselines: frozen v3 four-pack (`baseline_0` … `baseline_3`)
- Split: chronological v3 policy; primary analysis on `HISTORICAL_DEVELOPMENT_VALIDATE`
- `simulator_version` (current production of fills): `phase7.bar-conservative/1.1.0`

## Current conservative fill policy (`phase7.bar-conservative/1.1.0`)

Implementation: `market_platform_foundation.execution.simulator.BarConservativeSimulator`

| Stage | Rule |
|-------|------|
| Signal time | `intent.created_time` (prediction decision time) |
| Activation | First `BAR_OHLCV_1M` with `available_time` **strictly after** signal time |
| Fill bar | First bar at or after `activation_time` on the scoped bar path |
| Fill price | **Long:** `high` of fill bar. **Short:** `low` of fill bar. |
| Fill time | `available_time` of fill bar |
| Size | `min(approved_qty, participation_cap_remaining_on_bar)` |
| Provenance | `SIMULATOR_VERSION` = `phase7.bar-conservative/1.1.0`, `source_capability` = `BAR_OHLCV_1M` |

**Mark-to-market (economics v3):** terminal and unrealized PnL use **last bar close** on the scoped event path (`fill_economics._mark_price_minor_from_events`), not the conservative fill extreme.

**Audit fields today (per fill in `fill_economics`):** `fill_price`, `fill_price_minor`, `fill_quantity`, `direction`, slippage component — **no** explicit `fill_price_policy_id` or bar OHLC snapshot in v3 manifests.

## Current vs label decoupling (diagnostic intent)

| Quantity | Definition |
|----------|------------|
| `directional_accuracy` | Agreement between baseline prediction sign and forward-return label on the research split |
| `gross_pnl` | Market realized + unrealized from ledger marks and conservative fills |
| Expected tension | Higher label accuracy does not imply better simulated entry/exit prices when fills lean adverse within the bar |

## Alternative fill assumptions (historical research only)

Each alternative is a **separate simulator policy id** in a **NEW** experiment hash. None may replace v3 receipts or Item 9 calibration stamps.

| Policy id (proposed) | Fill price on fill bar | Lawfulness notes |
|----------------------|------------------------|------------------|
| `historical-research/bar-conservative/1.1.0` | long→high, short→low | **Current** — alias of `phase7.bar-conservative/1.1.0` research binding |
| `historical-research/bar-close/1.0.0` | `close` of fill bar | Mid-bar close proxy; still causal on bar availability |
| `historical-research/bar-open/1.0.0` | `open` of fill bar | More optimistic than conservative; still bar-local |
| `historical-research/bar-mid/1.0.0` | `(high + low) / 2` | Deterministic mid-bar; documents sensitivity to intra-bar path |
| `historical-research/bar-conservative-plus-close-mtm/1.0.0` | Fill unchanged (conservative) | Mark unrealized at **close** at each fill time (explicit audit) — isolates MTM vs fill |

**Out of scope:** tick-level matching, lookahead using future bars, retroactive fill adjustment from validate outcomes, Paper comparator hosts, Item 9 `fill_price_long` / `fill_price_short` calibration features.

## Required instrumentation (future implementation)

Per simulated fill, emit audit record:

| Field | Purpose |
|-------|---------|
| `fill_price_policy_id` | Which row of the table above |
| `fill_bar_available_time_ns` | Causal timestamp |
| `fill_bar_open` / `high` / `low` / `close` | OHLC at fill bar (string decimals) |
| `fill_price_minor` | Applied price |
| `mark_price_minor_at_fill` | Close (or policy) used if MTM sampled at fill |
| `label_forward_return_sign` | For correlation diagnostics only |

## Metrics (pre-registered)

| Tier | Metric |
|------|--------|
| Primary | Spearman or Pearson correlation across baselines: `directional_accuracy` vs `gross_realized_pnl` (validate) — **descriptive**, not a winner test |
| Secondary | `gross_unrealized_pnl`, `exposure`, `simulated_fills` |
| Failure | Claiming profitability from v3 validate net signs |

**No-tuning:** do not pick fill policy post-hoc from validate PnL ordering.

## Experiment identity

### Lane C pre-registration (not executed — frozen JSON)

| Field | Value |
|-------|-------|
| `experiment_id` (label) | `imp-simulator-fill-price-realism-v1-lane-e` |
| Artifact | `evidence/historical-research/imp-simulator-fill-price-realism-v1/methodology_v1.json` |

### Executed bounded run (experiment 06 — authoritative)

See **Status (post close)** above and `IMP_INTEGRATE_EXPERIMENT_06_LANE_F_FILL_PRICE_REALISM_V1.md`.

## Related

- Execution simulator: `src/market_platform_foundation/execution/simulator.py`
- Economics: `fill_economics.py` (`ACCOUNTING_VERSION` `3.0.1`)
- Paper calibration contract (distinct authority): `PAPER_SIMULATOR_CALIBRATION_CONTRACT.md`
