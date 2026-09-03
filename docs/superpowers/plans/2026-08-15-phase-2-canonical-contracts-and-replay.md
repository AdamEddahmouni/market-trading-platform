# Phase 2 — canonical contracts and replay (operational plan)

**Status:** Complete — Phase 2 `PASS` published  
**Plan date:** 2026-08-15  
**Scope:** Phase 2 only  
**Design spec:** [Phase 2 design spec](../specs/2026-08-15-phase-2-canonical-contracts-and-replay-design.md)

## 1. Gate state

| Gate | State |
|---|---|
| Phase 0 / 0A / 1 | `PASS` |
| Phase 2 design spec | `APPROVED` |
| Phase 2 implementation authorization | `EFFECTIVE` |
| Phase 2 implementation | `PASS` |

## 2. Work packages (planned)

| WP | Deliverable |
|---|---|
| WP-C1 | Governance activation — principal exact-hash approvals |
| WP-C2 | Contract modules under `src/market_platform_foundation/contracts/` |
| WP-C3 | Synthetic adversarial fixture pack |
| WP-C4 | Replay lifecycle stub with deterministic ordering |
| WP-C5 | Assertion registry + evaluator for `TC-*` / `DET-001` |
| WP-C6 | Postreview gate + `phase2.pass_publication` |

## 3. First implementation step after authorization

Extend assertion registry with `TC-001`, `TC-002`, `TC-003`, and `DET-001`
predicates; implement contract round-trip tests on synthetic JSON fixtures only.

## 4. Hard constraints

- Offline guard and `ADR-OFF-001` boundary remain in force.
- No third-party dependencies without new exact-hash authorization.
- Admitted equity fixture may inform semantics but Phase 2 proof uses synthetics first.
