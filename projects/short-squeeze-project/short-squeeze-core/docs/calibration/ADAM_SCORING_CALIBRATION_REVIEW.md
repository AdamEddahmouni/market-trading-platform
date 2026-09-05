# Adam Scoring Calibration Review (Evidence-Gated Prime v1)

**Date:** 2026-08-17  
**Track:** Live screener (`adam_evidence_gated_prime.v1`) — **not** Phase 3B historical policy  
**Status:** Complete — retain 65% minimum dimension weight

## Scope

Counterfactual sweep of `MIN_DIMENSION_WEIGHT` (50%, 55%, 60%, 65%, 70%) against
representative live evidence profiles. Classification thresholds (PRIME/SUBPRIME/WATCH)
were **not** recalibrated in this pass.

## Recommendation

| Parameter | Decision |
|-----------|----------|
| `MIN_DIMENSION_WEIGHT` | **Retain 65%** |
| Lower floors (50%, 55%) | **Reject** — admit partial pressure (SI + DTC without float) as SUBPRIME |
| Higher floor (70%) | **Reject** — blocks Finviz Elite core profile (exactly 65% supported weight per dimension) |
| Classification thresholds | **Complete** — retain baseline gates ([ADR 0070](../adr/0070-adam-classification-threshold-calibration-findings.md)) |

## Rationale

1. **Finviz Elite minimum path:** SI (30%) + DTC (25%) + float (10%) = 65% pressure;
   change (35%) + relvol (30%) = 65% ignition. The 65% floor is the precise threshold
   for evaluable scoring on the typical cloud provider bundle.
2. **Partial pressure withheld:** SI + DTC only (55%) stays `UNEVALUABLE` at baseline —
   intentional withholding until float (or IBKR borrow legs) arrive.
3. **Raising to 70%** forces the Finviz core profile and watch-tier profiles back to
   `UNEVALUABLE`, collapsing live scanner ranking to mostly unevaluable rows.

## Evidence profiles (synthetic)

| Profile | Baseline (65%) | Notes |
|---------|----------------|-------|
| `finviz_pressure_ignition_core` | SUBPRIME, evaluable | Typical Finviz + change + relvol |
| `pressure_si_dtc_only` | UNEVALUABLE | 55% pressure weight — withheld |
| `full_provider_prime` | PRIME | Full nine-field cloud + IBKR profile |
| `ignition_change_only` | UNEVALUABLE | Missing relvol critical leg |
| `watch_not_qualified` | NOT_QUALIFIED | Low scores, sufficient evidence |
| `borrow_conflict` | CONFLICTED | Material borrow fee conflict |

## Artifacts

```powershell
cd short-squeeze-project\short-squeeze-core
python tools/run_adam_calibration.py
```

- Report: `reports/calibration/adam_weight_floor_live_profiles.json`
- Fixture: `tests/fixtures/calibration/adam_live_evidence_profiles.json`
- Policy: `src/squeeze_core/calibration/policies/adam_scoring_calibration_policy_v1.json`
- ADR: [0069](../adr/0069-adam-evidence-gated-prime-calibration-findings.md)

## Governance

- `weights_validated: true` in `evaluate_adam()` metadata when using the default 65% floor
- Methodology remains `provisional: true` — calibration records human-reviewed confirmation,
  not auto-promotion
- No predictive validation claims

## Explicit non-recommendations

- Do not lower the floor to improve live evaluability for partial Finviz legs
- Do not conflate this review with Phase 3D detection/outcome policy calibration
- Classification threshold tuning completed separately — see
  [ADAM_CLASSIFICATION_THRESHOLD_CALIBRATION_REVIEW.md](ADAM_CLASSIFICATION_THRESHOLD_CALIBRATION_REVIEW.md)
  and [ADR 0070](../adr/0070-adam-classification-threshold-calibration-findings.md)
