# IMP Glossary

Concise definitions for terms used across architecture and engineering docs.

| Term | Definition |
|------|------------|
| **Demo** | UI session mode for fixture replay exploration. Read-only; no execution authority. |
| **Paper** | UI session mode for internal simulated execution. Requires backend `INTERNAL_SIMULATION` + `PAPER_ONLY` authority and env gates. |
| **Live** | UI session mode for broker-observed read-only data. No order submission. |
| **Authority** | Backend-declared permission to act (`execution_authority`, env gates). Frontend gating is UX only — never trusted for safety. |
| **Attention** | Paper Command queue item surfacing a candidate symbol/thesis from backend projections. |
| **Lane** | Workspace module (squeeze, order-flow, options, etc.) with mode-specific content and observability. |
| **Workspace** | Canonical Paper decision boundary — `/workspace/:symbol` with decision cockpit. |
| **Provenance** | Encoded origin of a Paper draft (`correlation_id`, lane module, attention ID). Distinct from snapshot content. |
| **Source snapshot** | Immutable `decision_source_snapshot` persisted on intent — headline/tier/reasons/module identity at handoff. |
| **Source time** | `source_time` on snapshot — when source context was captured (not order/preview/fill time). Epoch ns preferred. |
| **Correlation ID** | Stable identifier linking draft → preview → submit → intent → trace. |
| **Intent** | Backend `UserOrderIntent` event representing operator decision to trade (Paper). |
| **Preview** | Server-side validation/simulation preview before submit; must be current for submission. |
| **Revalidation** | Required when draft or market state changes after an accepted preview. |
| **Ledger** | Event-sourced Paper execution record (orders, fills, positions). |
| **Projection** | Derived read model from ledger/events (portfolio, orders, trace). |
| **Canary** | Live observational health/reconciliation control plane (`/live-canary`). |
| **Reconciliation** | Broker vs ledger comparison (P4-4B); mismatches are events, never silently absorbed. |
| **Observability** | Shared read-only UI components surfacing API data (tables, metrics, health). |
| **Fixture** | Admitted test dataset with governance binding — not live capture. |
| **Mode route** | `Mode*Route` component switching Demo/Paper/Live page by session mode. |
| **Query key** | React Query cache identifier — same key implies same fetch semantics and shape. |

See [DATA_CONTRACTS.md](architecture/DATA_CONTRACTS.md) for ID/timestamp semantics and [MODE_AUTHORITY.md](architecture/MODE_AUTHORITY.md) for safety boundaries.
