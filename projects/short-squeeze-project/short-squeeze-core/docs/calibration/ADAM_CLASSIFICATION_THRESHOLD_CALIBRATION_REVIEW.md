# Adam Classification Threshold Calibration Review

**Date:** 2026-08-17  
**Track:** Live screener (`adam_evidence_gated_prime.v1`) — **not** Phase 3B historical policy  
**Status:** Complete — retain baseline PRIME/SUBPRIME/WATCH gates

## Scope

Counterfactual sweep of classification thresholds against representative live evidence
profiles. Complements the weight-floor calibration in
[ADAM_SCORING_CALIBRATION_REVIEW.md](ADAM_SCORING_CALIBRATION_REVIEW.md) (ADR-0069).

## Recommendation

| Parameter | Decision |
|-----------|----------|
| PRIME gates (70/70) | **Retain** |
| SUBPRIME gates (70/50 asymmetric) | **Retain** |
| WATCH gate (50) | **Retain** |
| HIGH coverage for PRIME (85%) | **Retain** |
| Lower HIGH coverage to 65% | **Reject** — Finviz core becomes PRIME without full provider bundle |
| Raise PRIME to 75/75 | **Reject** — demotes marginal PRIME profiles without evidence gain |

## Rationale

1. **PRIME requires full provider weight:** Finviz-only rows score 100/100 on pressure and
   ignition but have 65% average weight coverage (LOW). They correctly land SUBPRIME.
   Lowering HIGH coverage to 65% would promote them to PRIME.
2. **Full provider path stays PRIME:** Nine-field cloud + IBKR profiles with HIGH coverage
   (100% weight) remain PRIME at baseline gates.
3. **Boundary stability:** SUBPRIME pressure-led (75/55) and WATCH mid (60/60) profiles
   stay in their tiers at baseline; watch-tier low scores remain NOT_QUALIFIED.

## Evidence profiles (synthetic)

| Profile | Baseline | Notes |
|---------|----------|-------|
| `full_provider_prime` | PRIME | Nine fields, HIGH coverage |
| `finviz_pressure_ignition_core` | SUBPRIME | Max scores, LOW coverage (65% weight) |
| `moderate_coverage_strong` | SUBPRIME | Seven fields, MODERATE coverage (82.5%) |
| `subprime_pressure_led` | SUBPRIME | 75/55 dimension scores |
| `watch_mid` | WATCH | 60/60 dimension scores |
| `watch_not_qualified` | NOT_QUALIFIED | Below WATCH gates |
| `prime_boundary_72` | PRIME | Marginal PRIME; flips at 75/75 gate |

## Artifacts

```powershell
cd short-squeeze-project\short-squeeze-core
python tools/run_adam_threshold_calibration.py
# or
python tools/run_adam_calibration.py --mode classification-thresholds
```

- Report: `reports/calibration/adam_classification_threshold_live_profiles.json`
- Fixture: `tests/fixtures/calibration/adam_classification_threshold_profiles.json`
- ADR: [0070](../adr/0070-adam-classification-threshold-calibration-findings.md)

## Governance

- `thresholds_optimal: true` in `evaluate_adam()` metadata when using default thresholds
- Methodology remains `provisional: true` — calibration records human-reviewed confirmation,
  not auto-promotion
- No predictive validation claims

## Explicit non-recommendations

- Do not lower HIGH coverage to promote Finviz-only rows to PRIME for scanner sort inflation
- Do not conflate this review with Phase 3D detection/outcome policy calibration
