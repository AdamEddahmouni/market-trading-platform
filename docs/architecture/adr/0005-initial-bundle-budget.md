# ADR-0005: Initial JavaScript Bundle Budget

| Field | Value |
|-------|-------|
| Status | Accepted |
| Date | 2026-08-30 |

## Context

UI grew with mode-specific surfaces and lazy lanes; unbounded initial bundle would harm local dev and startup.

## Decision

- **200 KiB gzip** initial JavaScript budget (static import closure from Vite entry)
- **500 KB raw** max per lazy chunk
- Enforced in `ui/scripts/check-bundle-budget.mjs` on `npm run build`
- Heavy routes/components lazy-loaded via `React.lazy`

## Consequences

- Must lazy-load lanes, assistant, settings, provider health
- Avoid eager Paper-only imports on Demo/Live entry paths

## References

- [PERFORMANCE.md](../../engineering/PERFORMANCE.md)
- `ui/scripts/check-bundle-budget.mjs`
