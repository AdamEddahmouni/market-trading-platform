# IMP simulator cost sensitivity (Lane E)

**Hypothesis:** `LANE-E-HYP-SIMULATOR-COST-SENSITIVITY-V4`  
**Source finding:** `LANE-E-FND-016`  
**Authority:** `HISTORICAL_DEVELOPMENT` only — not Item 9 calibration, not broker-fee truth.

## Status (Lane C — Sep 18)

| Gate | Value |
|------|-------|
| `SPEC_READY` | **YES** |
| `IMPLEMENTATION_READY` | **NO** (methodology frozen; v4 experiment pack + runner not landed) |
| `EXECUTED` | **NO** |

## Frozen methodology (pre-registered)

### Parent experiment (immutable reference)

| Field | Frozen value |
|-------|----------------|
| Parent `experiment_id` | `imp-integrate-experiment-05-r3-opend-fill-economics-v3` |
| Parent `experiment_definition_hash` | `81EFC1B1E2650010962F81F5B58B7E614E1AC1C2232E7862890CBB37BF5F3F61` |
| Parent receipts | **Do not rewrite** |

### Dataset (locked)

| Field | Value |
|-------|-------|
| `dataset_fingerprint` | `355FDBB852B94B964B62331839B58C3A336D1B52DB2F17FA05D30BA31389885B` |
| `dataset_id` | `HIST-DEV-AAPL` |
| `instrument` | `AAPL` |
| `corpus_evidence_authority` | `HISTORICAL_DEVELOPMENT` |
| `session_dates` | `2026-09-10` … `2026-09-16` (five RTH sessions per frozen v3 definition) |
| Corpus pin | `evidence/historical-research/imp-integrate-experiment-05-r3-opend-fill-economics-v3/corpus_pin` |

No session re-selection conditioned on v3 validate PnL. No in-place edits to the v3 frozen JSON.

### Baselines (locked)

Reuse frozen v3 `baseline_strategies` unchanged:

- `baseline_0_no_trade_v1`
- `baseline_1_momentum_5m_sign_v1`
- `baseline_2_mean_reversion_5m_sign_v1`
- `baseline_3_volume_momentum_5m_v1`

`feature_version`: `historical-research-bar-features/1.0.0`  
`prediction_coupled_simulator`: **true**  
`simulator_version`: `phase7.bar-conservative/1.1.0` (fill path unchanged — cost grid must not alter fill counts).

### Cost model (canonical units from repo)

| Constant | Value | Code authority |
|----------|-------|----------------|
| `ACCOUNTING_VERSION` | `simulator-research-fill-economics/3.0.1` | `fill_economics.py` |
| `COST_MODEL_VERSION` | `simulator-research/notional-linear-bps/1.0.0` | `fill_economics.py` |
| v3 baseline `cost_slippage_bps` | **5.0** | `frozen_experiment_definition.json` → `run_parameters` |
| `transaction_cost_model` id (legacy label) | `linear_slippage_on_gross_pnl` | frozen v3 definition |

**Slippage formula (native currency):**

```text
fill_notional_native = abs(fill_quantity) * (fill_price_minor / price_scale)
slippage_cost_native = fill_notional_native * (cost_slippage_bps / 10_000)
```

**Policy commission/fees (research harness default `DEFAULT_RISK_POLICY`):**

| Field | Value |
|-------|-------|
| `commission_minor_per_share` | `0` |
| `fee_minor_per_order` | `0` |
| `price_scale` | `100` |
| `initial_cash_minor` | `1_000_000_00` |

**Transaction costs:**

```text
transaction_costs = sum(slippage_cost_native per fill) + policy commission + policy fees
net_pnl = gross_pnl − transaction_costs
```

Slippage does **not** depend on PnL sign. Varying only `cost_slippage_bps` must leave `fills`, `trade_intents`, and `gross_pnl` identical to the parent run at the same bps=0 reference; at bps>0, `gross_pnl` unchanged, `net_pnl` monotone non-increasing in bps holding fills fixed.

### Pre-registered cost grid (`cost_slippage_bps`)

Fixed set (**7** points — no post-hoc expansion):

| Grid index | `cost_slippage_bps` |
|------------|---------------------|
| 0 | `0.0` |
| 1 | `1.25` |
| 2 | `2.5` |
| 3 | `5.0` (v3 baseline — replication anchor) |
| 4 | `7.5` |
| 5 | `10.0` |
| 6 | `20.0` |

**No-tuning policy:** grid fixed before any v4 execution. Do not add/remove points using validate `net_pnl`. Do not tune strategies, features, splits, or simulator fill internals.

### Split policy (locked)

From v3 `run_parameters.split_policy`:

| Split | Role |
|-------|------|
| `HISTORICAL_TRAIN` | `train_fraction` = 0.6 chronological |
| `HISTORICAL_DEVELOPMENT_VALIDATE` | `development_validate_fraction` = 0.2 — **primary** simulator + economics metrics |
| `HISTORICAL_RESEARCH_TEST` | holdout remainder — **descriptive labels only** (same as v3: no simulator PnL on test unless a separate hypothesis changes policy) |

`allow_shuffle`: **false**

### Metrics

| Tier | Metric |
|------|--------|
| Primary | `net_pnl` on `HISTORICAL_DEVELOPMENT_VALIDATE` per baseline × grid point |
| Secondary | `estimated_costs` / `transaction_costs`, `gross_pnl`, `simulated_fills`, `traded_notional` |
| Invariant checks | `fills` and `gross_pnl` equal to bps=0 sibling run; `CONTAMINATION_STATUS` PASS |

**Forbidden claims:** production fee calibration, broker truth, strategy winner from validate ordering.

### Proposed v4 experiment identity (not executed)

| Field | Proposed value |
|-------|----------------|
| `increment_id` | `IMP-SIMULATOR-COST-SENSITIVITY-V4` |
| `experiment_id` | `imp-simulator-cost-sensitivity-v4-lane-e` |
| `evidence_label` | `HISTORICAL_COST_SENSITIVITY_V4` |
| Definition artifact | `evidence/historical-research/imp-simulator-cost-sensitivity-v4/pre_registered_methodology_v1.json` |

Execution requires a **NEW** `experiment_definition_hash` after implementation lands; provider-heavy OpenD replay only when Item 9 collector is not contended.

## Machine-readable freeze

`evidence/historical-research/imp-simulator-cost-sensitivity-v4/pre_registered_methodology_v1.json`

## Related

- v3 execution: `IMP_INTEGRATE_EXPERIMENT_05_LANE_B_V3_FILL_ECONOMICS.md`
- Lane E queue: `imp-integrate-experiment-05-lane-e-v3-findings/hypothesis_queue_v1.json`
