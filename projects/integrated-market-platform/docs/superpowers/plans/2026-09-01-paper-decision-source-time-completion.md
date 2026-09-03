# Paper Decision Source Time — Completion Record

> **Current architecture:** [PAPER_DECISION_LIFECYCLE.md](../../architecture/PAPER_DECISION_LIFECYCLE.md) · [DATA_CONTRACTS.md](../../architecture/DATA_CONTRACTS.md)

**Date:** 2026-09-01  
**Status:** Complete (historical delivery record)  
**Tracking:** [WORK_LOG.md](../../engineering/WORK_LOG.md)

## Goal

Populate and preserve trustworthy `source_time` on Paper `decision_source_snapshot` records so historical review can answer *when* decision context was captured — without implying signal quality, decay, or performance.

## What `source_time` means

**The timestamp associated with the source context captured for this decision.**

- Paper Command: when the attention item was surfaced (`AttentionItem.surfaced_time`), or handoff time if absent
- Workspace lane: lane handoff creation time when no stronger lane observation timestamp exists

## What `source_time` does NOT mean

- Order creation/submission time (`created_time`)
- Preview time, fill time, signal expiry, freshness window, holding period
- Market regime start or strategy event time unless explicitly the canonical source timestamp

## Timestamp units

| Layer | Convention |
|-------|------------|
| Backend `created_time`, `prediction_cutoff`, `surfaced_time` | Epoch **nanoseconds** |
| Legacy fixtures / some tests | Epoch **milliseconds** (values ≤ 1e15) |
| Frontend parsing | Values > 1e15 → ns (÷ 1e6 to ms); otherwise treated as ms |

Contract documented in `paperSourceTimestamp.ts` and `PaperDraftSourceContext.source_time` comment.

## Canonical source priority

`resolvePaperDecisionSourceTime({ canonicalSourceTime, handoffTime })`:

1. `AttentionItem.surfaced_time` (server-derived when available)
2. Lane/attention handoff creation time (`handoffTimeFromNow`)
3. Absent (legacy/manual — valid)

Never fabricate an earlier timestamp from unrelated fields.

## AttentionItem contract change

Optional `surfaced_time?: number` (epoch ns) added to:

- `AttentionItemSchema` (frontend)
- `manifests/ui1/schemas/attention_item.schema.json`
- Backend attention projections where canonical timestamps exist:
  - Strategy signals → `observation_time`
  - Replay context / quality / futures → `prediction_cutoff`
  - MC9 catalyst attention → `available_time` (ISO → epoch ns)

Squeeze/catalyst bridge items without stable timestamps omit `surfaced_time`; frontend uses handoff fallback.

## Draft / sourceContext

`PaperDraftSourceContext` gains optional `source_time` (set once at draft creation):

- `createAttentionPaperOrderDraft(item, { now })`
- `createLanePaperOrderDraft(instrumentId, moduleId, { now })`
- `attentionSourceContextFromItem(item, { handoffTime })`

Version-1 draft compatibility preserved; old drafts without `source_time` remain valid.

## Immutability

Source time is chosen **once** at handoff/draft creation, stored in `sourceContext.source_time`, mapped to `decision_source_snapshot.source_time` on preview/submit, and never regenerated on:

- Workspace re-render
- Preview / revalidation
- Side/quantity edits
- Submit

`OrderTicket` now preserves `initialDraft.sourceContext` through preview/submit.

## Persistence path

```
AttentionItem.surfaced_time / handoff now
  → sourceContext.source_time (draft)
  → buildPaperDecisionSourceSnapshot(draft)
  → preview/submit request.decision_source_snapshot.source_time
  → build_user_order_intent(...)
  → project_orders()
  → Portfolio / ExecutionTracePanel
```

## Presentation semantics

| Context | Label |
|---------|-------|
| Paper Command (active cockpit) | Attention surfaced |
| Lane handoff (active cockpit) | Lane handoff created |
| Portfolio / trace (historical) | Source context captured |

Absolute timestamps via `Intl.DateTimeFormat` (operator locale/timezone). Relative age not used as primary display.

## Legacy / missing / malformed

- Absent `source_time` → row omitted; record remains valid
- Invalid values (≤0, NaN, absurd magnitude) → omitted at parse; rest of snapshot shown
- `created_time` remains distinct from `source_time` in portfolio details

## Validation / tests

| Suite | Result |
|-------|--------|
| Vitest | **403 passed** (73 files) |
| `validate.py changed` | **859 passed** |
| `validate.py full` | **2969 passed** |
| Build / bundle | pass; initial **199.17 KiB gzip** (unchanged) |

New: `resolvePaperDecisionSourceTime.test.ts`, `paperSourceTimestamp.test.ts`; extended draft/snapshot/portfolio/trace/cockpit/OrderTicket/backend tests.

## Deferred

- Signal-decay scoring, freshness analytics, time-to-fill, automatic invalidation by source age
- Lane-specific observation timestamps from individual lane APIs (future when contracts stabilize)
- Per-lane headline at handoff

## Related completion records

- [Paper decision-source snapshot](2026-08-31-paper-decision-source-snapshot-completion.md) — updated
- [Paper Command handoff](2026-08-31-paper-command-workspace-handoff-completion.md) — updated
- [Paper Workspace cockpit](2026-08-31-paper-workspace-decision-cockpit-completion.md) — updated
- [Paper Portfolio decision history](2026-08-31-paper-portfolio-decision-history-completion.md) — updated
