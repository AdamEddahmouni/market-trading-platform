# Data Contracts

**Status:** Authoritative principles for API/schema evolution.

## General rules

1. **Optional fields** — add as optional with safe defaults; old clients/records remain valid
2. **Never repurpose** — do not change semantic meaning of existing fields
3. **Backend is canonical** — frontend Zod schemas mirror backend contracts
4. **Malformed data** — degrade display safely; do not crash observational surfaces

## Timestamps

| Convention | Detail |
|------------|--------|
| Backend canonical | Epoch **nanoseconds** (`created_time`, `surfaced_time`, `prediction_cutoff`) |
| Legacy / tests | Epoch **milliseconds** (values ≤ 1e15) |
| Frontend parsing | `paperSourceTimestamp.ts`: values > 1e15 → ns (÷ 1e6 for display ms) |
| Timezone | Store UTC epoch; display with `Intl.DateTimeFormat` (operator locale) |

### Semantic distinction (never conflate)

| Field | Meaning |
|-------|---------|
| `source_time` | When decision **source context** was captured |
| `created_time` | When order/intent was **created/submitted** |
| `surfaced_time` | When attention item was **surfaced** (Paper Command) |
| Preview/fill times | Separate lifecycle events |

**Never infer one timestamp from another.**

## IDs and correlation

| ID | Scope |
|----|-------|
| `correlation_id` | Decision thread across draft → trace |
| `client_order_id` | Client-generated order identity |
| `intent_id` / `order_id` | Server-assigned persistence |
| Lane module IDs | Canonical set in `WORKSPACE_LANE_REGISTRY` / `WORKSPACE_LANE_MODULE_IDS` ([laneRegistry.ts](../../ui/src/components/workspace-module-shared/laneRegistry.ts)); UI paper provenance derives from it; backend validates structurally, never enumerates |
| Attention IDs | Backend-assigned attention item identity |

Do not overload `correlation_id` with display labels or reuse for unrelated caches.

## Provenance vs snapshot

| Concept | Content |
|---------|---------|
| **Provenance** | Encoded origin (lane module, attention, encoding in `correlation_id`) |
| **Source snapshot** | Bounded headline/tier/reasons/module at handoff (`decision_source_snapshot`) |
| **Source time** | When that context was captured |

## Raw provider payloads

- Keep provider-specific shapes at adapter boundary
- UI receives projected/canonical shapes only
- Never expose secrets or raw credentials in projections

## Frontend parsing

- Zod schemas in `ui/src/api/schemas.ts`
- JSON schemas in `manifests/ui1/schemas/` for shared contracts
- Parse failures: omit field or show degraded state — not silent coercion

## Versioning

- Draft `version` field for client-side draft contract
- API breaking changes require coordinated backend + frontend + fixtures + tests
- Follow [API_SCHEMA_CHANGE.md](../engineering/sops/API_SCHEMA_CHANGE.md)

## React Query cache contract

Same query key ⇒ same fetch function semantics and response shape. See [FRONTEND_GUIDE.md](../engineering/FRONTEND_GUIDE.md#react-query-keys).
