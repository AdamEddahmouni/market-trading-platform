# ADR-0007: Operational Account Identity and Snapshot Isolation

| Field | Value |
|-------|-------|
| Status | Accepted |
| Date | 2026-09-01 |

## Context

TD-003 required backend account/broker snapshot isolation. The platform previously used:

- A single global canary operator context (`fp-canary-local` only)
- Shared React Query keys between Demo and Paper portfolio (`["paper","portfolio"]`)
- Snapshot APIs that did not expose which account produced the data
- Cache keys that omitted account dimensions

Multi-account, multi-broker, and future authenticated workflows need explicit operational identity without conflating user authentication with account identity.

## Decision

### Canonical identity model

Introduce `OperationalIdentity` with dimensions that materially affect data:

| Field | Required | Purpose |
|-------|----------|---------|
| `mode` | Yes | `DEMO`, `PAPER`, or `LIVE` |
| `broker` | Yes | Broker/runtime producing state |
| `account_id` | Yes | Stable, cache-safe identifier |
| `portfolio_id` | No | When portfolio scope differs from account |
| `environment` | Yes | `fixture`, `local`, `canary`, `observational` |

### Synthetic demo identity

Demo reads the same internal ledger as Paper but uses a synthetic account ID (`demo:{paper_account_id}`) so cache keys and API envelopes never collide with Paper mutations.

### Account discovery

`GET /accounts` returns discoverable operational accounts with display labels, capability state, and availability — no secrets.

### Account-scoped snapshots

- `GET /canary/snapshot?account_id=...` — per-account live canary snapshot
- `GET /canary/reconciliation?account_id=...` — per-account reconciliation
- `GET /paper/portfolio?view_mode=DEMO|PAPER` — explicit view identity

All account-scoped responses include `operational_identity` envelope.

### Cache isolation policy

`AccountSnapshotCache` keys include `mode`, `broker`, `account_id`, and `environment`. Per-account refresh locks prevent cross-account refresh coalescing. Stale serve-on-failure is explicit (`stale`, `refresh_failed` fields).

### Portfolio and risk ownership

Paper portfolio/risk state is owned by `paper_account_id`. Live canary state is owned by `account_ref` in `OperatorControlContext`. No silent aggregation across accounts.

### Frontend query keys

Per ADR-0004, keys include account dimensions:

- `["demo","portfolio"]` vs `["paper","portfolio"]`
- `["live","canary-snapshot", laneId, accountId]`
- `["live","canary-reconciliation", accountId]`

## Rejected alternatives

- **Display labels as identity** — unsafe for cache keys and API routing
- **Global `"default"` account bucket** — enables cross-account leakage
- **Mode-only scoping without account_id** — insufficient when multiple live accounts exist
- **Full multi-user auth in this increment** — out of scope; identity model is auth-ready

## Live safety impact

No Live execution capability added. Account-aware snapshots are read-only infrastructure. Live canary command paths preserve existing guards.

## Future auth relationship

Future authorization should gate access to `OperationalIdentity` contexts. This ADR defines operational identity only — not user ownership or RBAC.

## References

- [TECH_DEBT.md](../../engineering/TECH_DEBT.md) TD-003
- [operational_identity.py](../../../src/market_platform_foundation/operational_identity.py)
- [ADR-0004](0004-react-query-key-invariants.md)
