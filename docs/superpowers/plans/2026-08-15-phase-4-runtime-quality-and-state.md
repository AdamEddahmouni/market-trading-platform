# Phase 4 — runtime quality and state (operational plan)

**Status:** Complete — Phase 4 `PASS` published  
**Plan date:** 2026-08-15  
**Scope:** Phase 4 only  
**Design spec:** [Phase 4 design spec](../specs/2026-08-15-phase-4-runtime-quality-and-state-design.md)

## 1. Gate state

| Gate | State |
|---|---|
| Phase 0 / 0A / 1 / 2 / 3 | `PASS` |
| Phase 4 design spec | `APPROVED` |
| Phase 4 implementation authorization | `EFFECTIVE` |
| Phase 4 implementation | `PASS` |

## 2. Work packages

| WP | Deliverable |
|---|---|
| WP-Q1 | Governance activation |
| WP-Q2 | `state/bar_book.py`, `data_quality/*`, `storage/dataset_cache.py` |
| WP-Q3 | `replay/quality_lifecycle.py` and corruption fixtures |
| WP-Q4 | Assertion registry + evaluator for `TC-001`, `TC-003`, `DET-001`, `SAFE-003` |
| WP-Q5 | Postreview gate + `phase4.pass_publication` |

## 3. Hard constraints

- Bar capability only; reject unsupported fidelity upgrades.
- Cache hits must not change replay root hash.
- Offline guard and `ADR-OFF-001` remain in force.
- Two clean network-denied runs on the admitted fixture.
