# TD-003 Multi-Account Snapshot Architecture — Completion Record

| Field | Value |
|-------|-------|
| **Date** | 2026-09-01 |
| **Status** | Complete |
| **Starting commit** | `be0b0f1` |
| **Goal** | Backend multi-account snapshot architecture and end-to-end state isolation |

## Repository state discovered

- HEAD at `be0b0f1` on `cloud/build-35-release-governance-operational-acceptance`
- TD-003 partially closed: frontend mode-scoped canary keys only
- Single global `_OPERATOR_CTX` for live canary; Demo/Paper shared `["paper","portfolio"]` query key
- Paper ledger uses content-derived `paper_account_id`; canary used hardcoded `fp-canary-local`

## Canonical account identity decision

`OperationalIdentity` (`mode`, `broker`, `account_id`, optional `portfolio_id`, `environment`):

- **Paper:** `paper_account_id` from ledger
- **Demo:** synthetic `demo:{paper_account_id}` read-only view
- **Live canary:** `account_ref` per `OperatorControlContext`

## Backend API changes

| Endpoint | Change |
|----------|--------|
| `GET /accounts` | New — operational account discovery |
| `GET /canary/snapshot?account_id=` | Account-scoped snapshot with `operational_identity` |
| `GET /canary/reconciliation?account_id=` | Account-scoped reconciliation |
| `GET /paper/portfolio?view_mode=DEMO\|PAPER` | Explicit view identity |
| Paper/broker payloads | `operational_identity` envelope added |

## Broker adapter changes

- Interface-level identity attachment in `broker_projections.py`
- Multi-account fixture contexts: `fp-canary-local`, `fp-canary-alt`
- TD-004 Moomoo real-wire unchanged

## Cache/state isolation changes

- `AccountSnapshotCache` — SHA256 keys from identity dimensions
- Per-account refresh locks (no global refresh lock)
- Explicit stale/refresh_failed semantics on canary snapshots

## Portfolio and risk changes

- Paper portfolio/risk owned by `paper_account_id`
- Live canary owned by per-context `account_ref`
- Demo view identity distinct from Paper mutations

## Frontend changes

- `queryKeys.demoPortfolio` vs `queryKeys.paperPortfolio`
- `queryKeys.liveCanarySnapshot(laneId, accountId)`
- `queryKeys.liveCanaryReconciliation(accountId)`
- `fetchLiveCanarySnapshot(accountId)` / `fetchLiveCanaryReconciliation(accountId)`
- `DemoPortfolioPage` uses `useDemoPortfolioQuery`

## TD-003 disposition — **CLOSED**

Platform architecture complete for supported internal broker/runtime paths. Evidence: isolation tests, account discovery, account-scoped APIs, cache keys, frontend propagation.

## TD-004 disposition — **OPEN**

Moomoo OpenD real-wire blocked on external connectivity. Adapter interface improved; no fake connectivity.

## Safety checks

- No Live execution capability added
- Demo/Paper/Live mode separation preserved
- Paper lifecycle guards unchanged
- Unknown account fails closed (`OPERATIONAL_ACCOUNT_UNKNOWN`)

## Tests added

- `tests/platform/test_operational_identity.py` (5 tests)
- `tests/platform/test_account_isolation.py` (5 tests)
- `ui/src/api/queryKeys.test.ts` (account isolation cases)
- `ui/src/smoke/appShell.smoke.test.ts` (demo/paper key isolation)

## Validation

Run at completion — see WORK_LOG for exact results.

## Remaining blockers

- TD-004 Moomoo OpenD TCP connectivity
- TD-005 auth/multi-user enforcement
- LIVE-001 production execution authorization

## Final git status

Branch `feat/td-003-multi-account-snapshot-isolation` with implementation changes pending commit.
