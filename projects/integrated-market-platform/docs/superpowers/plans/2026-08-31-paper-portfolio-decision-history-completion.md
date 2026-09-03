# Paper Portfolio Decision History — Completion Record

**Date:** 2026-08-31  
**Status:** Complete  
**Tracking:** [WORK_LOG.md](../../engineering/WORK_LOG.md)

## Goal

Turn Paper Portfolio into the authoritative operational-history surface for simulated Paper decisions — closing the lifecycle **Discover → Decide → Preview → Submit → Observe → Review**.

## Before → after lifecycle

| Before | After |
|--------|-------|
| Portfolio showed a minimal orders table (side/qty/state/filled) | Operational order history table with provenance, status, fills, filters, and expandable details |
| `correlation_id` stored on intents but not projected to portfolio orders | `project_orders()` preserves optional `correlation_id` (+ intent quantity/symbol/timestamp fields) |
| Trace available only when Paper actions permitted | Trace navigation always available; history readable under authority loss |
| No distinction between correlation and decision provenance in portfolio | `parsePersistedPaperDecisionProvenance` classifies lane/attention/manual/unknown; client-order default → manual |
| Execution trace could label manual client correlation as Paper Command | Trace uses persisted parser; manual/default correlations hide decision provenance label |

## Persisted provenance contract

| Source | Persisted `correlation_id` | Portfolio badge | Source detail |
|--------|---------------------------|-----------------|---------------|
| Workspace lane | `lane:{moduleId}` | Lane title (e.g. ORDER FLOW) | Lane id |
| Paper Command | `{attention_id}` or `attention:{id}` | PAPER COMMAND | Attention id |
| Manual / legacy | equals `client_order_id` or absent | MANUAL | No recorded decision source |
| Unknown external | other non-matching values | UNKNOWN | Raw correlation (technical) |

Attention id heuristics for persisted values: `attention:`, `attention-`, `att-`, `ATT-` prefixes. Arbitrary strings (e.g. `corr-p3-trace`) degrade to UNKNOWN — not Paper Command.

## Correlation vs provenance

- **Decision correlation**: machine identifier on intent/events (may equal `client_order_id` for manual orders).
- **Decision provenance**: known IMP source contract (lane / Paper Command attention). UI shows provenance only when `isDecisionProvenance` is true; correlation always available in technical details / trace.

## Operational table architecture

```
PaperPortfolioPage
  PaperPortfolioObservability (account/positions/fills; orders hidden)
  PaperOrderHistory
    metrics summary
    Open orders table (non-terminal)
    Order history table + filters (status/source/symbol)
      PaperOrderHistoryRow → PaperDecisionProvenanceBadge + expandable details
  ExecutionTracePanel (query-selected intent/order)
```

Pure helpers: `paperDecisionProvenance.ts`, `paperOrderHistoryModel.ts`, `paperOrderStatusPresentation.ts`.

## Trace linkage

Portfolio row **View trace** sets `traceIntentId` / `traceOrderId` → existing `ExecutionTracePanel`. Provenance label in trace matches portfolio semantics via shared persisted parser.

## Backend change

`PaperExecutionLedger.project_orders()` enriches submitted orders from linked intent metadata:

- optional `correlation_id`
- `created_time`, `desired_quantity`, `symbol`, `instrument_id`

Backward compatible — older records without correlation remain valid.

## Authority behavior

- Paper authority invalid: order history, provenance, trace navigation remain visible; ticket/session controls fail closed.
- Demo/Live portfolio: unchanged basic `PaperPortfolioObservability` orders table; no Paper provenance UI.

## UI-only limitations (updated 2026-08-31 source-snapshot increment)

- `decision_source_snapshot` now persists headline/tier/reasons for Paper Command and lane module identity for workspace lanes — see [source snapshot completion](2026-08-31-paper-decision-source-snapshot-completion.md).
- Legacy orders without snapshot: provenance via correlation only; no error state.
- No strategy attribution / win rates / lane performance analytics (deferred).

## Tests

- Frontend: vitest **387 passed** (71 files) — parser, model, table, trace, authority, portfolio page, source snapshot
- Backend: `test_project_orders_preserves_decision_correlation`, `test_project_orders_preserves_decision_source_snapshot`, `test_paper_decision_source_snapshot.py`
- Build: pass; initial bundle **199.17 KiB gzip** (budget pass)
- `validate.py changed`: **858 passed**
- `validate.py full`: **2968 passed**
- `validate.py full`: **2957 passed**

## Deferred

- Strategy/lane performance attribution dashboards
- Backend-side order history filtering/pagination

> **Update 2026-09-01:** Persisted `decision_source_snapshot.source_time` now renders in expanded details and execution trace — see [source time completion](2026-09-01-paper-decision-source-time-completion.md).
