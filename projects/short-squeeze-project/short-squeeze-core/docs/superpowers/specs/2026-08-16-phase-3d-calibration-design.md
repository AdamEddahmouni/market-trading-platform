# Phase 3D Evidence Calibration Pipeline

**Status:** APPROVED  
**Date:** 2026-08-16

## Purpose

Provide a governed, repeatable framework for **counterfactual policy experiments**
against labeled research cohorts. Phase 3D sits alongside Phase 3C (descriptive
analysis) and does not auto-promote winning thresholds to production.

## Non-goals

- No predictive validation claims
- No threshold auto-promotion
- No Adam weight tuning in v1
- No fabricated historical evidence

## Architecture

`squeeze_core/calibration/` orchestrates:

1. Load experiment definition (JSON)
2. Load Phase 3B research dataset
3. Filter cohort (synthetic / historical)
4. Apply policy variants (detection ablation, outcome sensitivity)
5. Run Phase 3C `run_research_analysis` per variant
6. Emit comparison report (JSON + Markdown)

## Experiment types (v1)

| Type | Input | Transform |
|------|-------|-----------|
| `DETECTION_ABLATION` | Stored rule outcomes | Vary `required_rule_ids` |
| `OUTCOME_SENSITIVITY` | Stored move observations | Vary outcome thresholds |

## Governance

`policies/phase_3d_calibration_policy_v1.json` forbids `THRESHOLD_AUTO_PROMOTION`
and requires calibration-specific limitations on every report.

## CLI

```powershell
python tools/run_calibration_experiment.py \
  --experiment tests/fixtures/calibration/detection_ablation_baseline.json \
  --output reports/calibration/result.json
```
