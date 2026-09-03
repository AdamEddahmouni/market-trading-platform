# OF12 — Advanced LOB Baseline (fixture-first, experimental)

**Status:** Implemented  
**Spec date:** 2026-08-19  
**Scope:** M7 engineered LOB feature vector + M8 baseline forecaster with walk-forward OF12-S1 gate vs M1 CVD-only comparator  
**Prerequisites:** OF4–OF11 IMPLEMENTED (fixture), Platform P0 PIT

## 1. Purpose

Advance the Order Flow model ladder to **M8** after M1–M7 baselines validate on admitted fixtures. OF12 assembles a normalized LOB feature vector and produces a calibrated mid-direction baseline. Does not replace OF8 heuristic forecasts — adds versioned `lob_engineered_baseline_v1` metadata for research gates and workspace display.

Order Flow owns LOB semantics only. No squeeze state, participant identity, or cross-lane signal duplication.

## 2. Methods

| Method ID | Role |
|---|---|
| `lob_feature_vector_v1` | Normalize OFI, QI, microprice displacement, fragility, absorption, optional MBO queue-ahead fraction |
| `lob_engineered_baseline_v1` | Weighted stdlib scorer → `mid_up_probability`, `expected_mid_delta`, `baseline_tier=M8` |
| `lob_cvd_only_v1` | M1 comparator using bar_delta / cvd_slope only → `baseline_tier=M1` |

## 3. Output contract

`LobBaselineForecast` fields:

- `lob_model_version` — `lob_engineered_baseline_v1` or `lob_cvd_only_v1`
- `lob_model_version_number` — `1`
- `baseline_tier` — `M1` | `M8`
- `mid_up_probability` — 0..1
- `expected_mid_delta` — signed ticks/spread fraction
- `signal_half_life_ms` — metadata {0, 50, 100, 250} default 100
- `book_state_valid`, `quality_flags`
- `research_only: true`, `experimental: true`

Workspace: `latest_lob_forecast` on order-book + futures depth payloads.

## 4. Capability rules

- L2-only path: queue features omitted; `MBO_UNAVAILABLE` quality flag when queue input absent
- Never fabricate queue depth or exact queue position without MBO
- Invalid book → fail-closed zero confidence (mirror OF8)

## 5. Gate milestone OF12-S1 (fixture scope)

On admitted ES LOB baseline slice:

- **OF-Q1:** M8 directional accuracy or Brier score beats M1 CVD-only on walk-forward folds
- **OF-Q9:** MBO-present passive fill estimate differs from L2-only path on `es_lob_mbo_upgrade_slice.json` (queue model upgrade observable)

Aggregate PASS when all gate_summary entries PASS; INSUFFICIENT_SAMPLE fail-closed.

## 6. Fixtures

| Fixture | Admission |
|---|---|
| `es_lob_baseline_slice.json` | `ADMITTED-LOB-ES-001` — labeled snapshot sequence with `mid_delta_forward` |
| `es_lob_baseline_expected.json` | Golden M8 forecast + gate summary |
| `es_lob_mbo_upgrade_slice.json` | MBO vs L2-only execution comparison |
| `nvda_lob_baseline_slice.json` | NVDA parity regression |

## 7. Out of scope

- Live vendor LOB feeds
- sklearn / external ML libraries
- New cross-lane EvidenceSignal enums (OF8/OF9 remain authoritative for signals)
- Auto-trading or universal LOB score

## 8. Completion definition

OF12 complete when fixture ingest produces deterministic LOB forecasts, PIT adversarial tests pass, OF12-S1 gate tool reports aggregate PASS on admitted fixtures, workspace exposes `latest_lob_forecast`, and full test suite remains green.
