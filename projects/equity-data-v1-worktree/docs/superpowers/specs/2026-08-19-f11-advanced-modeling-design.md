# F11 — Advanced Modeling Baseline (fixture-first, experimental)

**Status:** Implemented  
**Spec date:** 2026-08-19  
**Scope:** EQUITY_INDEX engineered feature vector + family-conditioned baseline with walk-forward F11-S1 gates vs F5 trend-only comparator  
**Prerequisites:** F1–F10 IMPLEMENTED (fixture), Platform P0 PIT

## 1. Purpose

Advance the Futures model ladder after F5 interpretive baselines and F6 family context reads. F11 produces a versioned research forecast for **outright direction** (primary) and **curve steepen** (secondary). It does not replace F5/F6 context payloads and does not publish new directional cross-lane `EvidenceSignal` enums.

Futures owns curve/carry/positioning/leverage semantics only. No squeeze state, options P vs Q, or order-flow LOB scoring.

## 2. Methods

| Method ID | Role |
|---|---|
| `futures_feature_vector_v1` | Normalize vol-scaled trend, carry, curve slope/momentum, COT crowding, leverage dampener, macro-window flag |
| `futures_family_engineered_v1` | Weighted stdlib scorer → `outright_up_probability`, `curve_steepen_probability`, `baseline_tier=M8` |
| `futures_trend_only_v1` | F5 trend-3m comparator → `baseline_tier=M1` |

Labels remain separate. Never a single “Futures Prediction.”

## 3. Output contract

`FuturesBaselineForecast` fields:

- `futures_model_version` — `futures_family_engineered_v1` or `futures_trend_only_v1`
- `futures_model_version_number` — `1`
- `baseline_tier` — `M1` | `M8`
- `outright_up_probability` — 0..1
- `curve_steepen_probability` — 0..1
- `direction_bias` — `UP` | `DOWN` | `NEUTRAL`
- `family` — `EQUITY_INDEX` | `ENERGY` when supported
- `family_supported` — false fail-closes TREASURY/METALS/other unimplemented plugins
- `model_confidence`
- `quality_flags`
- `research_only: true`, `experimental: true`

Workspace: `latest_futures_forecast` on ES futures payloads.

## 4. Capability rules

- EQUITY_INDEX (ES) and ENERGY (CL/NG/RB/HO) supported in v1 extension. Unimplemented family → `FAMILY_MODEL_UNIMPLEMENTED`, zero confidence
- ENERGY uses carry/curve-heavy weighting vs EQUITY_INDEX trend-heavy weighting (same `futures_feature_vector_v1` inputs)
- Missing COT → omit crowding; `POSITIONING_UNKNOWN` / `COT_PUBLICATION_PENDING`; never invent net percentile
- COT visibility uses publication time (`available_time`), not observation Tuesday
- Missing margin/macro → omit those terms with quality flags
- Stdlib only — no sklearn / gradient boosting

## 5. Gate milestone F11-S1 (fixture scope)

On admitted ES F11 baseline slice:

- **FQ-7 analogue:** M8 directional accuracy or Brier beats M1 trend-only on walk-forward folds (next-bar outright label; embargo 1 bar)
- **FQ-8 analogue:** COT-present engineered probability differs from COT-omitted path on `es_cot_positioning_divergent_slice.json` (crowding upgrade observable)

Aggregate PASS when all gate_summary entries PASS; INSUFFICIENT_SAMPLE fail-closed.

## 6. Fixtures

| Fixture | Admission |
|---|---|
| `es_f11_baseline_slice.json` | `ADMITTED-F11-ES-001` — thin manifest over admitted ES bars/COT/margin/macro |
| `es_f11_baseline_expected.json` | Golden M8 forecast + gate summary |
| `es_f11_cot_upgrade_slice.json` | Crowded-short vs COT-omitted comparison |
| `cl_f11_baseline_slice.json` | `ADMITTED-F11-CL-001` — admitted CL bars/COT/margin/macro |
| `cl_f11_baseline_expected.json` | Golden M8 ENERGY forecast + gate summary |
| `cl_f11_cot_upgrade_slice.json` | CL crowding upgrade comparison |

## 7. Out of scope

- Live CME / vendor feeds
- sklearn / external ML libraries
- TREASURY/METALS family plugins
- New cross-lane EvidenceSignal enums (F8/F9 remain authoritative)
- Auto-trading or universal Futures Score

## 8. Completion definition

F11 complete when fixture ingest produces deterministic forecasts, PIT adversarial tests pass, F11-S1 gate tool reports aggregate PASS on admitted fixtures, workspace exposes `latest_futures_forecast`, and full test suite remains green.
