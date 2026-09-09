# Phase 4 — Feature table addendum (open item O-3)

**Status:** DRAFT — outcome-blind, written before any Phase 4 fitting; **pending
reviewer confirmation** (open item O-3 in the
[Phase 4 calibration preregistration](phase-4-calibration-preregistration.md)).
Fitting must not start until this addendum is confirmed.
**Version:** `phase_4_feature_table_addendum.v0.1-draft`

## 1. Outcome-blindness statement

The feature list below is the **exact set of evidence inputs the causal evaluator
(`evaluate_squeeze_intelligence`, `squeeze_causal_baseline.v1`) consumes at a
detection boundary**, enumerated from the committed source of truth:

- `src/squeeze_core/intelligence/evaluator.py` — the frozen snapshot dataclasses
  (`RuleSnapshot`, `AdamSnapshot`, `CrossLaneSnapshot`, `FuelHistorySnapshot`,
  `QualitySnapshot`) and the evaluator signature;
- `src/squeeze_core/acquisition/operation_readiness/dependencies.py` — the 25 frozen
  Phase 3A rule ids and the evidence metrics they reference;
- the committed boundary-evaluation fixtures
  (`tests/fixtures/evaluation/*_boundary_evaluation.json`, `*_boundary_evidence.jsonl`)
  that instantiate these inputs per boundary.

**No dataset boundary timestamps and no outcome labels were inspected to choose this
list** — every feature is a field the evaluator already reads, or a deterministic
dimension score the evaluator already computes, at the boundary. Feature *selection by
outcome* remains forbidden (preregistration §5). Any amendment to this addendum must
itself be outcome-blind and recorded in the revision history before any fit.

## 2. Point-in-time construction rule (applies to every feature)

All features are constructed **at the frozen detection boundary** from the
**detection-context evidence window only** (`DETECTION_CONTEXT_PRECEDING_24H` —
1-minute bars with `bar_end` ≤ boundary; `COMPLETED_BAR_AVAILABLE` semantics per
`operation_readiness/evidence_inputs.py`). Nothing from the forward window
(`FORWARD_REQUEST`) and nothing after the boundary enters any feature. A feature the
evaluator treats as `UNKNOWN` or absent at the boundary is **missing** — never
imputed with later or current values (ADRs 0047/0062) — and a **missingness
indicator** is included for it (permitted by preregistration §5).

## 3. The exact feature table

Each feature is a scalar; `D` = derived by the evaluator at the boundary (not a raw
input). Encodings are fixed in §4. The rule-outcome features are listed under their
frozen rule id exactly as emitted by the boundary evaluation (`PASS` / `FAIL` /
`UNKNOWN`).

### 3.1 Rule-outcome features (25 features)

One feature per frozen Phase 3A rule (category in parentheses). Values are the rule
outcomes from the boundary evaluation; `UNKNOWN` → missing + missingness indicator.

| # | Feature (`rule_id`) | Category |
|---|---|---|
| R01 | `MARKET_DATA_AVAILABLE` | MOMENTUM_DISCOVERY |
| R02 | `COMPLETED_BAR_AVAILABLE` | MOMENTUM_DISCOVERY |
| R03 | `PERCENTAGE_CHANGE_MINIMUM` | MOMENTUM_DISCOVERY |
| R04 | `PRICE_RANGE` | MOMENTUM_DISCOVERY |
| R05 | `RELATIVE_VOLUME_MINIMUM` | MOMENTUM_DISCOVERY |
| R06 | `FLOAT_MAXIMUM` | MOMENTUM_DISCOVERY |
| R07 | `PUBLISHED_SHORT_INTEREST_AVAILABLE` | SHORT_PRESSURE_CONFIRMATION |
| R08 | `SHORT_INTEREST_PERCENTAGE_CHANGE_MINIMUM` | SHORT_PRESSURE_CONFIRMATION |
| R09 | `DAYS_TO_COVER_MINIMUM` | SHORT_PRESSURE_CONFIRMATION |
| R10 | `BORROW_FEE_MINIMUM` | SHORT_PRESSURE_CONFIRMATION |
| R11 | `BORROW_FEE_CHANGE_MINIMUM` | SHORT_PRESSURE_CONFIRMATION |
| R12 | `BORROW_AVAILABILITY_MAXIMUM` | SHORT_PRESSURE_CONFIRMATION |
| R13 | `BORROW_AVAILABILITY_CHANGE_MAXIMUM` | SHORT_PRESSURE_CONFIRMATION |
| R14 | `NEWS_AVAILABLE` | CATALYST_EVIDENCE |
| R15 | `NEWS_AVAILABLE_BEFORE_AS_OF` | CATALYST_EVIDENCE |
| R16 | `NEWS_TIMESTAMP_KNOWN` | CATALYST_EVIDENCE |
| R17 | `SEC_FILING_AVAILABLE` | CATALYST_EVIDENCE |
| R18 | `CORPORATE_ACTION_CONTEXT_AVAILABLE` | CATALYST_EVIDENCE |
| R19 | `REQUIRED_DOMAINS_PRESENT` | EVIDENCE_VALIDITY |
| R20 | `NO_MATERIAL_CONFLICTS` | EVIDENCE_VALIDITY |
| R21 | `POINT_IN_TIME_ELIGIBLE` | EVIDENCE_VALIDITY |
| R22 | `REQUIRED_UNITS_COMPATIBLE` | EVIDENCE_VALIDITY |
| R23 | `REQUIRED_HISTORY_SUFFICIENT` | EVIDENCE_VALIDITY |
| R24 | `NO_DEFAULT_SUBSTITUTION` | EVIDENCE_VALIDITY |
| R25 | `PROVIDER_SCOPE_EXPLICIT` | EVIDENCE_VALIDITY |

### 3.2 Evidence-metric inputs behind the rules (spec §3, §5 groups A–I)

The direct evidence-metric inputs the rules reference, as continuous or presence
features. Values are taken from the boundary evaluation's `observed_value` /
`observed_unit` where the rule is `PASS`/`FAIL`, and are **missing** where the rule is
`UNKNOWN` (e.g. `BORROW_FEE_MINIMUM` when no borrow-fee domain is present).

| # | Feature | Metric / domain it measures | Present in batch-05 fixtures |
|---|---|---|---|
| M01 | `percentage_return` (PERCENTAGE_RETURN) | price-only ratio over the admissible window | yes |
| M02 | `percentage_return_z_score` (PERCENTAGE_RETURN_Z_SCORE) | trailing-window z-score of the return | yes |
| M03 | `relative_volume` (RELATIVE_VOLUME) | volume vs. mean-volume baseline | yes |
| M04 | `volume_z_score` (VOLUME_Z_SCORE) | trailing-window z-score of volume | yes |
| M05 | `mean_volume_baseline` (MEAN_VOLUME_BASELINE) | trailing-window mean volume | yes |
| M06 | `price_range` (PRICE_RANGE) | absolute price level window | no (provider-scope UNKNOWN) |
| M07 | `float_shares` (FLOAT_MAXIMUM) | candidate-snapshot float | no (provider-scope UNKNOWN) |
| M08 | `published_short_interest_pct_change` | short-interest percentage change | no (domain absent) |
| M09 | `days_to_cover` (DAYS_TO_COVER) | published-short-interest-derived days-to-cover | no (domain absent) |
| M10 | `borrow_fee_rate` (BORROW_FEE_MINIMUM) | borrow fee level | no (domain absent) |
| M11 | `borrow_fee_abs_change` (BORROW_FEE_CHANGE_MINIMUM) | borrow fee absolute change | no (domain absent) |
| M12 | `borrow_availability_shares` (BORROW_AVAILABILITY_MAXIMUM) | lendable inventory | no (domain absent) |
| M13 | `borrow_availability_abs_change` (BORROW_AVAILABILITY_CHANGE_MAXIMUM) | lendable inventory change | no (domain absent) |
| M14 | `news_present`, `sec_filing_present`, `corporate_action_present` | catalyst-domain presence flags | no (domains absent) |

### 3.3 Evaluator snapshot inputs (exact fields)

The remaining fields of the evaluator's evidence inputs, verbatim from the committed
dataclasses. All optional (`None` → missing + missingness indicator).

| # | Feature | Snapshot | Type |
|---|---|---|---|
| S01 | `pressure` | `AdamSnapshot` | float |
| S02 | `ignition` | `AdamSnapshot` | float |
| S03 | `classification` | `AdamSnapshot` | categorical (`NOT_QUALIFIED` / `WATCH` / …) |
| S04 | `coverage_label` | `AdamSnapshot` | categorical |
| S05 | `order_flow_cvd_slope` | `CrossLaneSnapshot` | float |
| S06 | `order_flow_aggressive_buy` | `CrossLaneSnapshot` | bool |
| S07 | `order_flow_aggressive_sell` | `CrossLaneSnapshot` | bool |
| S08 | `options_call_demand_anomaly` | `CrossLaneSnapshot` | bool |
| S09 | `options_gamma_amplification` | `CrossLaneSnapshot` | bool |
| S10 | `options_hedging_pressure` | `CrossLaneSnapshot` | float |
| S11 | `options_flow_reversal` | `CrossLaneSnapshot` | bool |
| S12 | `options_gamma_decay` | `CrossLaneSnapshot` | bool |
| S13 | `borrow_normalization_score` | `CrossLaneSnapshot` | float |
| S14 | `attention_acceleration` | `CrossLaneSnapshot` | float |
| S15 | `catalyst_strength` | `CrossLaneSnapshot` | float |
| S16 | `thesis_invalidation_score` | `CrossLaneSnapshot` | float |
| S17 | `lending_fee_rate` | `CrossLaneSnapshot` | float |
| S18 | `lending_shares_available` | `CrossLaneSnapshot` | int |
| S19 | `lending_utilization_rate` | `CrossLaneSnapshot` | float |
| S20 | `lending_shares_on_loan` | `CrossLaneSnapshot` | int |
| S21 | `borrow_utilization_velocity` | `CrossLaneSnapshot` | float |
| S22 | `previous_remaining_fuel` | `FuelHistorySnapshot` | float |
| S23 | `previous_cvd_slope` | `FuelHistorySnapshot` | float |
| S24 | `previous_reflexivity` | `FuelHistorySnapshot` | float |
| S25 | `stale_fields` | `QualitySnapshot` | set → count + membership |
| S26 | `unavailable_capabilities` | `QualitySnapshot` | set → count + membership |
| S27 | `provider_conflicts` | `QualitySnapshot` | bool |
| S28 | `frozen_snapshot` | `QualitySnapshot` | bool |

Per-lane availability flags (`order_flow_available`, `options_available`,
`attention_available`, `catalyst_available`, `lending_available`) are **not separate
features**: each is the missingness indicator for its lane's fields (§4), which the
evaluator already models as such.

### 3.4 Derived dimension scores (the evaluator's boundary outputs)

The six causal dimension scores the evaluator computes at the boundary (spec §3;
`SqueezeIntelligenceResult` fields) are included **as features** exactly as the
evaluator computes them (`squeeze_causal_baseline.v1`), because they are the
dimension-level inputs the calibration must explain (preregistration §5). They are
deterministic functions of §3.1–§3.3; no variant definitions are permitted.

| # | Feature (D) | Evaluator definition (committed) |
|---|---|---|
| D01 | `vulnerability` | = `pressure` when evaluable, else missing |
| D02 | `constraint_pressure` | short-pressure cascade output (borrow/lending evidence) |
| D03 | `short_stress` | short-pressure rules + Adam pressure aggregation |
| D04 | `ignition_strength` | ignition rules + Adam ignition aggregation |
| D05 | `reflexivity_strength` | reflexivity/feedback-loop evidence aggregation |
| D06 | `remaining_fuel` | fuel-history/CVD aggregation |

`exhaustion_risk` is **not** a feature: it is a post-hoc state-machine diagnostic over
transition history (`previous_state` + hysteresis), not a boundary evidence input.

## 4. Fixed encodings

- **Rule outcomes** (`R01`–`R25`): `PASS` → 1, `FAIL` → 0, `UNKNOWN` → missing, plus
  one missingness indicator per rule.
- **Continuous metrics** (`M01`–`M13`): value as measured (no rescaling fixed here;
  any standardization is fit on training folds only), missing when the backing rule is
  `UNKNOWN`, plus indicator.
- **Presence flags** (`M14`): 0/1, missing when the domain itself is absent.
- **Snapshot scalars** (`S01`–`S24`): value or missing + indicator. Booleans: 0/1.
- **Set-valued quality fields** (`S25`–`S26`): count of entries + per-known-capability
  membership indicators; empty set → count 0, all memberships 0 (a *known* absence,
  not missing).
- **Categoricals** (`S03`, `S04`): one-hot against the committed enum values with an
  explicit `UNKNOWN` bucket; never ordinal.
- **Dimensions** (`D01`–`D06`): as computed; missing + indicator where the evaluator
  returns null.
- No outcome-informed resampling or class-weight tuning (preregistration §9).

## 5. Explicit non-features

- **`horizon_model` / `HorizonModelSnapshot`** — the calibrated model output, never an
  input; using it as a feature would be circular.
- **`previous_state`** — transition/hysteresis context, not boundary evidence; it is
  also constant (`None`) for first-observation boundaries, so it carries no signal.
- **`reason` strings, diagnostics, deterministic ids, observation ids** — identity and
  provenance only.
- **Raw bar series** — only the derived metrics in §3.2 enter the matrix; bars remain
  in the dataset for PIT re-checks.
- **Any forward-window value, any outcome-derived quantity** (preregistration §5).

## 6. Consequences for the current cohort

Measured from the committed batch-05 boundary evaluations (e.g.
`tests/fixtures/evaluation/aacb_boundary_evaluation.json`: 7 `PASS` / 2 `FAIL` /
16 `UNKNOWN` across the 25 rules), only the market-bar rules and the
`EVIDENCE_VALIDITY` meta-rules carry `PASS`/`FAIL` outcomes today — the
short-pressure, catalyst, and most momentum rules (`PRICE_RANGE`, `RELATIVE_VOLUME_MINIMUM`,
`FLOAT_MAXIMUM`) are `UNKNOWN` because only `MARKET_BARS` is present in the
detection-context evidence set (`DETECTION_CONTEXT_PRESENT_DOMAINS == {MARKET_BARS}`,
`operation_readiness/dependencies.py`). The feature table above is **not trimmed to
what is non-missing today**: absent features stay in the matrix with missingness
indicators, and any fit reports the per-feature missingness rate. Feasibility gate F-1
(positive events ≥ 10) still governs whether any fit is attempted at all.

## Revision history

| Date | Change |
|---|---|
| 2026-09-05 | Initial draft (v0.1): exact feature list enumerated from the committed evaluator evidence-input contracts and boundary-evaluation fixtures; outcome-blind; pending reviewer confirmation (O-3) |
| 2026-09-05 | Audit correction (same date, no version bump): §6 consequence claim corrected — `EVIDENCE_VALIDITY` meta-rules also carry `PASS`/`FAIL` (5 PASS + 1 FAIL in the AACB fixture), not only market-bar rules; measured counts (7 PASS / 2 FAIL / 16 UNKNOWN) stated explicitly |