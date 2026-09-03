# Phase 6 — preregistered strategy (operational plan)

**Status:** In progress  
**Plan date:** 2026-08-16  
**Scope:** Phase 6 only  
**Design spec:** [Phase 6 design spec](../specs/2026-08-15-phase-6-preregistered-strategy-design.md)

## 1. Gate state

| Gate | State |
|---|---|
| Phase 0 / 0A / 1 / 2 / 3 / 4 / 5 / 5R | `PASS` |
| Phase 6 design spec | `APPROVED` |
| Phase 6 implementation authorization | `EFFECTIVE` |
| Phase 6 implementation | `PASS` |

## 2. Work packages

| WP | Deliverable |
|---|---|
| WP-S1 | Governance activation |
| WP-S2 | `strategy/*` spec, preregistration, interpretation, abstention, evaluation |
| WP-S3 | Adversarial fixtures and strategy evaluation reports |
| WP-S4 | Assertion registry + evaluator for `STRAT-001`, `ABST-001`, `PIT-STRAT-001`, `DET-001`, `SAFE-003` |
| WP-S5 | Postreview gate + `phase6.pass_publication` |

## 3. Hard constraints

- Stdlib-only; no third-party dependencies.
- Preregistration identity is strategy-spec-rooted and required before interpretation.
- Abstention is explicit with reason codes; no silent signal generation.
- Whale-aligned strategies abstain when institutional evidence is unavailable.
- Offline guard and `ADR-OFF-001` remain in force.
