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
| Opportunity review IDs | `summary_id` plus optional governed `opportunity_id`; HTTP `GET /opportunities/summary` — not an order id |
| Opportunity evidence | `GET /opportunities/{id}/evidence` projects review-row `evidence_class` / promotion reason / family admission / data quality plus persist `created_at_ns`; `items` remains lineage refs. Not an ingest timestamp stamp. |

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

## API error envelope

HTTP JSON errors from `ui_api` and the loopback operator control plane emit:

| Field | Meaning |
|-------|---------|
| `error` | Human-readable message (legacy) |
| `reason_code` | Stable domain code (legacy; unchanged) |
| `error_category` | One of the twelve canonical WS05 categories (`VALIDATION_ERROR`, `MODE_BLOCKED`, …) |

`error_category` is additive. Demo mutation (`DEMO_MUTATIONS_PROHIBITED`) and Live **broker** execution (`LIVE_OBSERVATIONAL_NO_BROKER_EXECUTION` / legacy `LIVE_OBSERVATIONAL_NO_OPPORTUNITY_ENGINE` on order paths) are `MODE_BLOCKED`, not `INTERNAL_ERROR`. Live observational **operator lifecycle** (WATCH/DISMISS/review ack) is allowed without broker execution: it persists operator acks, `ExecutionDecisionTraceV1` (`mode=LIVE_OBSERVATIONAL`), and `TradeReviewV1` via the same SQLite path as Paper when persist-on. Fail-closes: `LIVE_OBSERVATIONAL_ACK_REQUIRES_LIVE_CLOCK`, `LIVE_OBSERVATIONAL_OPERATOR_ACK_DUPLICATE`. Live observational **reads** use `build_ranked_rows` after fixture quarantine. Internal ranking freshness uses the observational receive clock only — never `OpportunityV1.created_at_ns` or leftover fixture `as_of` as a live clock (missing receive → freshness `NOT_APPLICABLE` / `LIVE_AS_OF_UNAVAILABLE`, not `FRESH`). Feed honesty: `EMPTY` (no qualifying rows), `UNREADY` + `withheld_ranked_count` when repository rows exist but no live receive clock, `READY` only with live receive clock and eligible ranked rows — never July fixture cursor as `as_of`. Sep 15 `UNAVAILABLE` had **both** an early ranked-read gate **and** missing unattended EventV1 admission; live OE work is **software** intermediate proof, not empirical RTH. **FTEP `--live-ingress`:** after Finviz fetch, CLI **HTTP POST** to the serving UI API `POST /intelligence/ingest/news` (`IMP_UI_API_BASE_URL`); second hop labels `IngestionMode.HISTORICAL_RECONSTRUCTED` for already-fetched JSON while the **server** stamps receive (body must not send `server_received_time_ns`). Ranked OE on the UI API handler store is **in-memory** and **clears on UI API restart** unless/until a durable intelligence plane exists. FTEP watch `ingress_outcome` is overall (Finviz + cockpit); `FINVIZ_LIVE_INGRESS_SUCCESS` alone does not mean cockpit updated — use `COCKPIT_ADMIT_HTTP_OK` or `COCKPIT_ADMIT_UI_API_UNAVAILABLE`. Mixed discovery is INVESTIGATE / `execution_authority=NONE`, not the Opportunity Engine.

HTTP `_send_json` still fail-closes `UI_SECRET_LEAK_BLOCKED` (500) on real secret-shaped keys with live values. Observational ranked cards must not 500 solely because public `instrument_key` or `decision_support.authority` look secret-shaped (`key` / `auth`). Those names are omitted from the public summary DTO; cards use `instrument_id`. Do not stuff live keys into the cockpit payload. Fixture/replay cards stay off the current book (`DEMO_REPLAY` shelf only).

`LIVE_OBSERVATIONAL` `as_of_time` is `UNAVAILABLE` when no live quote or admitted event receive time exists — including `store.as_of_time()` and inspect EVIDENCE `as_of`. Optional `as_of_provenance` (`LIVE_RECEIVE` / `UNAVAILABLE`) is additive. Attention `replay_shelf` + `replay_shelf_label=DEMO_REPLAY` is additive; current `items` must not present fixture `att-replay-context` / MC9 / ES cards as RTH. Focus-none plus quotes on other symbols still yields `UNAVAILABLE`.

## Versioning

- Draft `version` field for client-side draft contract
- API breaking changes require coordinated backend + frontend + fixtures + tests
- Follow [API_SCHEMA_CHANGE.md](../engineering/sops/API_SCHEMA_CHANGE.md)

## React Query cache contract

Same query key ⇒ same fetch function semantics and response shape. See [FRONTEND_GUIDE.md](../engineering/FRONTEND_GUIDE.md#react-query-keys).
