# Phase 5 — capability-supported features (operational plan)

**Status:** Complete — Phase 5 `PASS` published  
**Plan date:** 2026-08-15  
**Scope:** Phase 5 only  
**Design spec:** [Phase 5 design spec](../specs/2026-08-15-phase-5-capability-supported-features-design.md)

## 1. Gate state

| Gate | State |
|---|---|
| Phase 0 / 0A / 1 / 2 / 3 / 4 | `PASS` |
| Phase 5 design spec | `APPROVED` |
| Phase 5 implementation authorization | `EFFECTIVE` |
| Phase 5 implementation | `PASS` |

## 2. Work packages

| WP | Deliverable |
|---|---|
| WP-F1 | Governance activation |
| WP-F2 | `features/*` and `replay/feature_lifecycle.py` |
| WP-F3 | Adversarial fixtures and institutional vocabulary report |
| WP-F4 | Assertion registry + evaluator for `CAP-001`, `PIT-FEAT-001`, `WHALE-001`, `DET-001`, `SAFE-003` |
| WP-F5 | Postreview gate + `phase5.pass_publication` |

## 3. Hard constraints

- Bar-derived features only; reject unsupported capability upgrades.
- Institutional families remain `unavailable` without entitled sources.
- Feature replay root hash must not change between clean network-denied runs.
- Offline guard and `ADR-OFF-001` remain in force.
