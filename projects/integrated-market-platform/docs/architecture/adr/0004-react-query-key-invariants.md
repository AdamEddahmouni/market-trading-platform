# ADR-0004: React Query Key Semantic Invariants

| Field | Value |
|-------|-------|
| Status | Accepted |
| Date | 2026-08-31 |

## Context

Live Canary used a shared query key (`canary-snapshot`) across routes — intentional cache sharing. Ad-hoc duplicate keys with different fetch semantics caused cache collision bugs elsewhere.

## Decision

1. Define keys in `ui/src/api/hooks.ts` as `queryKeys`
2. **Same key ⇒ same `queryFn` semantics and response shape**
3. Include mode-dependent dimensions (symbol, `dataMode`) in key when response differs
4. Document intentional shared keys (e.g. canary across Live surfaces)

## Consequences

- Central registry reduces collision risk
- Not every query migrated — new queries must use `queryKeys`

## References

- [FRONTEND_GUIDE.md](../../engineering/FRONTEND_GUIDE.md#react-query-keys)
- `ui/src/api/hooks.ts`
