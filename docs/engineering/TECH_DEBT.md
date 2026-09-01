# Technical Debt Register

**Status:** Concrete known debts only — not a wishlist.

| ID | Problem | Impact | Evidence | Priority | Direction | Status |
|----|---------|--------|----------|----------|-----------|--------|
| TD-001 | Paper history pagination | Large accounts slow UI | Portfolio loads full history | Medium | Server-side paging on `project_orders` | **Closed** 2026-09-01 — `/paper/order-history` + UI infinite load |
| TD-002 | Lane observation timestamps | `source_time` uses handoff fallback | Lane provenance envelope on workspace APIs + UI | Low | Per-lane canonical timestamps when contracts stable | **Closed** 2026-09-01 — `lane_provenance` on workspace/paper portfolio APIs; `laneProvenance.ts`; ADR-0006 |
| TD-003 | Live lane-specific broker snapshots | Live lanes share canary cache | Mode lane content completion | Low | Lane-scoped snapshots if needed | **Partially closed** 2026-09-01 — `queryKeys.liveCanarySnapshot(laneId)` mode-scoped keys; lane strip shows `as_of_ns`. Per-broker lane snapshots blocked on backend multi-account API |
| TD-004 | P4-4C Moomoo paper real-wire | Fixture-only proof | README platformization table | Medium | Record wire contract when OpenD exercised | **Open** (blocked — OpenD TCP unavailable) |
| TD-005 | Auth / multi-user | `ROLE_ENFORCEMENT_STATUS=MODEL_ONLY_NOT_ENFORCED` | P5 not started | Low | Separate authorization campaign | Deferred |
| TD-006 | CI lacks UI vitest/build | UI regressions caught only locally | `imp-validate.yml` Python only | Medium | Authoritative UI CI job | **Closed** 2026-09-01 — `validate-ui`: `npm ci`, `typecheck`, `test`, `build` |
| TD-007 | Research large dependencies | numpy/sklearn/mongo for intelligence BUILD | Cloud install script | Low | Keep isolated from foundation | Accepted |

Update when debts close or new evidence emerges.
