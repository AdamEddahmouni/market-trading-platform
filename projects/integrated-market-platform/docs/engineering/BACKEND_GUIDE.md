# Backend Guide

**Status:** Authoritative Python/UI API patterns.

## Package layout

```
src/market_platform_foundation/
├── contracts/       # Shared types
├── paper/           # Execution, ledger, intents, decision_source
├── ui_api/          # HTTP handlers, projections
├── platform/        # Operating context, modes
├── providers/       # External adapters
├── local_state/     # SQLite persistence (P3)
└── [domains]/       # Lanes, intelligence, market_data, etc.
```

## Domain boundaries

- **UI API** — HTTP translation, projection to JSON shapes UI expects
- **Domain services** — business logic, no HTTP concerns
- **Providers** — external data; fail closed when unconfigured

## Contract locations

| Layer | Location |
|-------|----------|
| Python types | `contracts/`, domain modules |
| JSON schemas | `manifests/ui1/schemas/` |
| Frontend Zod | `ui/src/api/schemas.ts` |

Keep these aligned on API changes — [API_SCHEMA_CHANGE.md](sops/API_SCHEMA_CHANGE.md).

## Paper execution flow

Preview → validate → submit → `UserOrderIntent` event → ledger append → `project_orders()` / trace projections.

Authority checked on every mutation. See `paper/` module and [PAPER_DECISION_LIFECYCLE.md](../architecture/PAPER_DECISION_LIFECYCLE.md).

## Event / intent / ledger model

- Append-only events
- Intents carry metadata (`correlation_id`, `decision_source_snapshot`)
- Projections are rebuildable from ledger

## Provider boundaries

Fixture-first; live gates per provider (`IMP_*_LIVE=1`). See `docs/providers/`.

## Reconciliation / canary

P4-4B reconciliation events; intelligence canary projections for Live UI.

## Validation

Python tests under `tests/` — manifest-owned. Run via `tools/validate.py`.

## Error handling

- Validation errors → structured HTTP response
- Authority failure → fail closed, no partial mutation
- Malformed legacy records → degrade projection field, not entire response

---

## Add a new API endpoint

1. Identify canonical contract (schema + types)
2. Add handler in `ui_api/`
3. Implement projection/service in domain module
4. Add frontend `api` method + Zod schema + hook
5. Fixtures and tests (backend + UI if consumed)
6. Update docs if public behavior changes

## Change request schema

1. Add optional fields first (backward compatible)
2. Update Python parser, projection, Zod, JSON schema
3. Timestamp unit check (ns vs ms)
4. Tests for old payloads still parsing

## Change a projection

1. Identify consumers (UI hooks, tests)
2. Preserve optional fields for old ledger records
3. Add/update unittest in owning suite

## Modify Paper intent metadata

1. Follow [PAPER_EXECUTION_CHANGE.md](sops/PAPER_EXECUTION_CHANGE.md)
2. Optional fields only unless migration authorized
3. Test legacy intents without new fields

## Add optional backward-compatible fields

Default absent/None; projection omits when missing; frontend treats as optional.
