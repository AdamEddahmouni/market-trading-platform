# Paper Decision Lifecycle

**Status:** Authoritative end-to-end architecture.  
**Supersedes** scattered descriptions in completion records for *current* behavior — those records remain historical evidence.

> Current architecture: this document. Historical delivery detail: completion records linked below.

## Flow

```mermaid
flowchart LR
  A[Paper Command / Lane] --> B[Draft + provenance]
  B --> C[sourceContext + source_time]
  C --> D[Workspace cockpit]
  D --> E[Preview]
  E --> F{Revalidation?}
  F -->|yes| E
  F -->|no| G[Submit]
  G --> H[Intent event]
  H --> I[Ledger]
  I --> J[Projection]
  J --> K[Portfolio / Trace]
```

## Stages

### 1. Attention / lane origin

- **Paper Command:** `AttentionItem` from backend projections; optional `surfaced_time` (epoch ns)
- **Workspace lane:** `createLanePaperOrderDraft` with module provenance
- **Handoff:** router state carries placeholder draft + `sourceContext`

### 2. Draft (`paperOrderDraft.ts`)

- Version-1 draft contract with optional `sourceContext`
- `correlation_id` encodes provenance (lane, attention, manual)
- `source_time` set **once** at handoff via `resolvePaperDecisionSourceTime`
- Legacy drafts without `source_time` remain valid

### 3. Workspace cockpit (`PaperDecisionCockpit`)

- Handoff panel, decision snapshot, risk context, preview status
- Order ticket embedded; `showLaneBanner=false` in cockpit
- Observability layer (`WorkspaceObservability`) unchanged below

### 4. Preview

- Server validates draft against current state
- States: `NOT_PREVIEWED`, `PREVIEWING`, `ACCEPTED`, `REJECTED`, `REVALIDATION_REQUIRED`, `AUTHORITY_UNAVAILABLE`, `ERROR`
- Accepted upstream preview **cannot** authorize submission if draft changed

### 5. Submit

- Requires current accepted preview (`confirmedRequestIsCurrent`)
- Request includes `decision_source_snapshot` (bounded fields)
- `correlation_id` preserved through intent

### 6. Intent → ledger → projection

- `build_user_order_intent` persists snapshot on intent metadata
- Ledger append-only events
- `project_orders()` → Portfolio history, execution trace

## Key identifiers

| Field | Role |
|-------|------|
| `correlation_id` | End-to-end decision linkage |
| `client_order_id` | Per-order client identifier; manual orders may equal correlation |
| `intent_id` / `order_id` | Backend persistence IDs |
| `decision_source_snapshot` | Immutable handoff context at submit time |

See [DATA_CONTRACTS.md](DATA_CONTRACTS.md) for timestamp and ID rules.

## Immutability rules

| Data | Mutable? |
|------|----------|
| `sourceContext` on draft after handoff | No — preserve `initialDraft.sourceContext` through preview/submit |
| `source_time` | No — chosen at handoff only |
| `decision_source_snapshot` on intent | No — written at submit |
| Current workspace evidence | Yes — may trigger revalidation |

## Failure behavior

- Authority loss: observe, do not submit
- Schema mismatch on snapshot: fail closed on write; degrade safely on read
- Missing `source_time`: omit display; record still valid
- Unknown provenance: degrade to `UNKNOWN` badge

## Legacy compatibility

- Orders without snapshot or `source_time`
- Manual orders (`correlation_id === client_order_id`)
- Old draft versions without `sourceContext`

## Completion records (historical)

- [Command → Workspace handoff](../superpowers/plans/2026-08-31-paper-command-workspace-handoff-completion.md)
- [Decision cockpit](../superpowers/plans/2026-08-31-paper-workspace-decision-cockpit-completion.md)
- [Portfolio history](../superpowers/plans/2026-08-31-paper-portfolio-decision-history-completion.md)
- [Source snapshot](../superpowers/plans/2026-08-31-paper-decision-source-snapshot-completion.md)
- [Source time](../superpowers/plans/2026-09-01-paper-decision-source-time-completion.md)

## Code map

| Area | Location |
|------|----------|
| Draft / snapshot builders | `ui/src/components/paper/` |
| Cockpit | `ui/src/components/paper-workspace/` |
| Backend intent | `src/market_platform_foundation/paper/` |
| Projections | `ui_api/projections.py`, `paper_projections.py` |
