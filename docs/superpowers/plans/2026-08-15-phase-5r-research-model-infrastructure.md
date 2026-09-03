# Phase 5R — research/model infrastructure (operational plan)

**Status:** In progress  
**Plan date:** 2026-08-15  
**Scope:** Phase 5R only  
**Design spec:** [Phase 5R design spec](../specs/2026-08-15-phase-5r-research-model-infrastructure-design.md)

## 1. Gate state

| Gate | State |
|---|---|
| Phase 0 / 0A / 1 / 2 / 3 / 4 / 5 | `PASS` |
| Phase 5R design spec | `APPROVED` |
| Phase 5R implementation authorization | `EFFECTIVE` |
| Phase 5R implementation | `PASS` |

## 2. Work packages

| WP | Deliverable |
|---|---|
| WP-R1 | Governance activation |
| WP-R2 | `research/*` dataset, targets, forecast, baseline, walk-forward, serialization |
| WP-R3 | Adversarial fixtures and walk-forward reports |
| WP-R4 | Assertion registry + evaluator for `DATASET-001`, `MODEL-001`, `PIT-WF-001`, `FCAST-001`, `DET-001`, `SAFE-003` |
| WP-R5 | Postreview gate + `phase5r.pass_publication` |

## 3. Hard constraints

- Stdlib-only; no third-party ML dependencies.
- Dataset identity is manifest-rooted and append-only.
- Walk-forward folds store cutoff boundaries; reject leakage adversarial cases.
- Forecast probability remains null until explicit calibration.
- Offline guard and `ADR-OFF-001` remain in force.
