# Technical Debt Register

**Status:** Concrete known debts only — not a wishlist.

| ID | Problem | Impact | Evidence | Priority | Direction | Status |
|----|---------|--------|----------|----------|-----------|--------|
| TD-001 | Paper history pagination | Large accounts slow UI | Portfolio loads full history | Medium | Server-side paging on `project_orders` | **Closed** 2026-09-01 — `/paper/order-history` + UI infinite load |
| TD-002 | Lane observation timestamps | `source_time` uses handoff fallback | Lane provenance envelope on workspace APIs + UI | Low | Per-lane canonical timestamps when contracts stable | **Closed** 2026-09-01 — `lane_provenance` on workspace/paper portfolio APIs; `laneProvenance.ts`; ADR-0006 |
| TD-003 | Live lane-specific broker snapshots | Live lanes share canary cache | Mode lane content completion | Low | Lane-scoped snapshots if needed | **Closed** 2026-09-01 — `OperationalIdentity` model, `GET /accounts`, account-scoped canary snapshots/reconciliation, `AccountSnapshotCache`, frontend account-aware query keys; ADR-0007 |
| TD-004 | P4-4C Moomoo paper real-wire | Fixture-only proof | README platformization table | Medium | Record wire contract when OpenD exercised | **Open** (blocked — OpenD TCP unavailable) |
| TD-005 | Auth / multi-user | Enforced via `IMP_AUTH_ENFORCEMENT_MODE` + principals registry | P5 enforcement landed | Medium | Map principals to `OperationalIdentity` ACLs | **Closed** 2026-09-01 — LOOPBACK_TRUST default; ENFORCED mode; session API; route capability + account ACL; frontend AuthProvider; ADR-0008 |
| TD-006 | CI lacks UI vitest/build | UI regressions caught only locally | `imp-validate.yml` Python only | Medium | Authoritative UI CI job | **Closed** 2026-09-01 — `validate-ui`: `npm ci`, `typecheck`, `test`, `build` |
| TD-007 | Research large dependencies | numpy/sklearn/mongo for intelligence BUILD | Cloud install script | Low | Keep isolated from foundation | Accepted |

Update when debts close or new evidence emerges.
