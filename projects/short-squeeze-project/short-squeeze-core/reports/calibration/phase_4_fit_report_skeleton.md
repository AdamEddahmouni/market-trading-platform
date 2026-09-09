# Phase 4 — Baseline fit report (item 1.3)

- Report: `phase_4_fit_report_skeleton.v1`
- Preregistration: `phase_4_calibration_preregistration.v0.6-draft`
- Walk-forward diagnostics: `phase_4_walkforward_harness.v1`
- Verdict: **NOT_CALIBRATED**
- RESEARCH_ONLY retained: **yes**
- Fit attempted: **no**

## Outcome counts (historical rows only; SYN excluded per ADR-0053)

| Quantity | Count |
|---|---:|
| Positives (Y_1 = 1, upward predicate) | 3 |
| Negatives (Y_1 = 0) | 27 |
| Downward mirror (not the squeeze target) | 5 |
| Unevaluable for this target | 0 |
| Total evaluable | 30 |
| Unique symbols | 33 |
| Positive base rate | 0.1000 |

## Feasibility gates (preregistration §8.1)

| Gate | Rule | Observed | Verdict |
|---|---|---|---|
| F-1 | evaluable positives (Y_1 = 1 at horizon 1) — >= 10 | 3 positives < 10 required | **FAIL** |
| F-2 | evaluable negatives (Y_1 = 0 at horizon 1) — >= 10 | 27 negatives >= 10 required | PASS |
| F-3 | non-empty chronological evaluation folds (prereg §7) — >= 2 | 2 non-empty evaluation folds >= 2 required | PASS |
| F-4 | owned forward-path data for any horizon k > 1 to be calibrated (O-1) — owned multi-day forward paths for each calibrated horizon k > 1 | no owned multi-day forward-path data (O-1 open): horizons 3/5/10/20 stay RESEARCH_ONLY; only horizon 1 is directly supportable | NOT_EVALUABLE (owner data feasibility, O-1) |

## Horizon coverage (prereg §2.3 no-backfill rule)

- Horizon  1d: owned data = yes — slot status `RESEARCH_ONLY`
- Horizon  3d: owned data = no — slot status `RESEARCH_ONLY`
- Horizon  5d: owned data = no — slot status `RESEARCH_ONLY`
- Horizon 10d: owned data = no — slot status `RESEARCH_ONLY`
- Horizon 20d: owned data = no — slot status `RESEARCH_ONLY`

## Notes

- Feasibility gate(s) failed: F-1. The Phase 4 result is reported as NOT_CALIBRATED with the failing gate(s) named (preregistration §8.2); the evaluator's RESEARCH_ONLY slots are retained and nothing is force-flipped to CALIBRATED.

## Fit blockers (preregistration §10)

- O-2: regime cutpoints + purge/embargo addendum — reviewer confirmation pending
- O-3: feature table addendum — reviewer confirmation pending
- O-4: reference cost set addendum — owner confirmation pending
- O-6: preregistration owner review (status -> approved or amended) pending
- feasibility: F-1

## Limitations

- HISTORICAL_CASE_BOUNDARIES_NOT_INDEPENDENT
- DETECTION_EVALUABILITY_LIMITED
- SINGLE_HORIZON_SUPPORTABLE_WHILE_O1_OPEN
- COUNTERFACTUAL_EXPLORATION_ONLY
- SMALL_SAMPLE_WARNING
- REPORT_SKELETON_NO_FIT_NO_PROBABILITY

This is a reporting skeleton, not a fit result: no model was estimated and no probability was produced. Fitting starts only when every feasibility gate passes **and** preregistration §10 is locked; until then `HorizonModelSnapshot.hazard_by_horizon` slots stay `RESEARCH_ONLY`.
