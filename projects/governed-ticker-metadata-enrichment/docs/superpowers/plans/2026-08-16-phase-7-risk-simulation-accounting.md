# Phase 7 — risk, simulation, and accounting (operational plan)

**Status:** Complete  
**Plan date:** 2026-08-16  
**Scope:** Phase 7 only  
**Design spec:** [Phase 7 design spec](../specs/2026-08-16-phase-7-risk-simulation-accounting-design.md)

## 1. Gate state

| Gate | State |
|---|---|
| Phase 0 / 0A / 1 / 2 / 3 / 4 / 5 / 5R / 6 | `PASS` |
| Phase 7 design spec | `APPROVED` |
| Phase 7 implementation authorization | `EFFECTIVE` |
| Phase 7 implementation | `PASS` |

## 2. Work packages

| WP | Deliverable |
|---|---|
| WP-R1 | Governance activation |
| WP-R2 | `risk/*`, `execution/*`, `portfolio/*`, `attribution/*` |
| WP-R3 | Adversarial fixtures and simulation/accounting reports |
| WP-R4 | Assertion registry + evaluator for `EXE-001`, `EXE-002`, `EXE-003`, `SAFE-003` |
| WP-R5 | Postreview gate + `phase7.pass_publication` |

## 3. Hard constraints

- Stdlib-only; no third-party dependencies.
- Risk is independent; strategy cannot override rejection or resize.
- Bar-only conservative fills; no intrabar, queue, or sweep claims.
- Accounting is fill-driven and exact; reconciliation failure blocks reporting.
- Offline guard and `ADR-OFF-001` remain in force.
