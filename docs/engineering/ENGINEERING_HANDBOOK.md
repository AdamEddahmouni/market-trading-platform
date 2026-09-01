# IMP Engineering Handbook

**Status:** Primary human and agent engineering reference.  
**Depth:** Concise — link to SOPs and guides for procedures.

## Repository layout

| Path | Purpose |
|------|---------|
| `src/market_platform_foundation/` | Python domain foundation (stdlib-only) |
| `ui/` | React/Vite frontend |
| `tests/` | Python unittest suites (manifest-owned) |
| `ui/src/**/*.test.ts(x)` | Vitest frontend tests |
| `tools/` | Validation, UI API launcher, phase tools |
| `manifests/` | Schemas, canonical authority |
| `docs/` | Documentation (see [docs/README.md](../README.md)) |

## Architecture principles

1. Source-backed data only — never fabricate market values
2. Fail closed on authority and validation errors
3. Observe under authority loss (history/trace remain readable)
4. Compose mode-specific surfaces from shared observability primitives
5. Distinguish current vs historical context (snapshots, source_time)
6. Immutable provenance once persisted
7. Frontend does not invent authority
8. Backward compatibility by default for schema fields
9. Regression tests for real bugs
10. Measure performance (bundle budget)

## Coding principles

- Inspect before inventing — search existing patterns
- Minimal diff — solve the actual problem
- Match surrounding conventions (naming, types, structure)
- Pure helpers for view-model logic
- Comments only for non-obvious business rules

See [CODING_STANDARDS.md](CODING_STANDARDS.md).

## Frontend conventions

- `Mode*Route` → Demo/Paper/Live pages
- Shared `*Observability` for data tables/metrics
- React Query for server state; router state for handoffs
- Lazy routes for heavy modules
- `canUsePaperActions` for Paper controls

See [FRONTEND_GUIDE.md](FRONTEND_GUIDE.md).

## Backend conventions

- UI API projections separate from domain services
- Event-sourced Paper ledger
- Optional fields for schema evolution
- Epoch ns timestamps in new contracts

See [BACKEND_GUIDE.md](BACKEND_GUIDE.md).

## State ownership

| State type | Owner |
|------------|-------|
| Server data | React Query + backend |
| Route handoff | React Router location state (short-lived) |
| Component UI | Local `useState` |
| Paper draft | Versioned draft object + OrderTicket |
| Persisted decisions | Backend ledger/intents |

## Paper authority rules

See [MODE_AUTHORITY.md](../architecture/MODE_AUTHORITY.md). Paper changes: [PAPER_EXECUTION_CHANGE.md](sops/PAPER_EXECUTION_CHANGE.md).

## Live read-only rules

Live pages never submit orders. Canary is observational.

## Testing standards

Hierarchy in [TESTING.md](TESTING.md). Regression rule: every real bug fix gets a test where practical.

## Performance budgets

200 KiB gzip initial JS — [PERFORMANCE.md](PERFORMANCE.md).

## Accessibility

Semantic HTML, keyboard, labels — [ACCESSIBILITY.md](ACCESSIBILITY.md).

## Logging & observability

Work log for substantive changes; technical logs vs business audit — [OBSERVABILITY.md](OBSERVABILITY.md).

## Documentation requirements

- Substantive work → [WORK_LOG.md](WORK_LOG.md)
- Behavior change → update authoritative architecture doc
- Large feature → completion record in `docs/superpowers/plans/`

## Definition of done

By change class: [DEFINITION_OF_DONE.md](DEFINITION_OF_DONE.md).

## Release expectations

[RELEASE.md](sops/RELEASE.md) — local/manual releases today.

## Validation

| When | Command |
|------|---------|
| After each edit | `python tools/validate.py changed` |
| UI change | `cd ui && npm test && npm run build` |
| Major checkpoint | `python tools/validate.py full` |
| Paper safety | full + UI + authority tests |

Details: [VALIDATION.md](VALIDATION.md).

## SOP index

See [docs/README.md](../README.md#sops).
