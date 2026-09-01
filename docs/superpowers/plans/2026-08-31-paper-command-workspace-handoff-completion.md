# Paper Command → Workspace Handoff — Completion Record

**Date:** 2026-08-31  
**Status:** Complete  
**Tracking:** [WORK_LOG.md](../../engineering/WORK_LOG.md)

## Goal

Unify Paper Command attention/candidate entry with the Paper Workspace decision cockpit handoff flow used by lane drafts — explicit provenance, Attention Handoff panel, source vs current context separation, workspace preview revalidation, and safe `correlation_id` persistence where backend contracts support it.

## Before → after workflow

| Before | After |
|--------|-------|
| Paper Command "Open workspace" navigated without draft/provenance | `createAttentionPaperOrderDraft` → route state with `sourceAttentionId` + optional `sourceContext` |
| Lane handoff only in cockpit | Unified `PaperHandoffPanel` (lane, attention, unknown provenance) |
| `sourceAttentionId` UI-only through submit | `correlation_id` on preview/submit when provenance is valid (`lane:*` or attention id) |
| Paper Command preview PASS could imply workspace authority | Workspace still auto-revalidates; upstream preview never bypasses ticket |
| Lane-only provenance helpers | `parsePaperDraftProvenance` single source of truth |

## Source → draft → cockpit → preview → submit → trace

```
Paper Command attention / lane link / direct workspace
  → PaperOrderDraft (version 1)
  → WorkspaceRoute (PUSH state, cleared after read)
  → PaperDecisionCockpit
        → PaperHandoffPanel (lane | attention | unknown)
        → PaperDecisionSnapshot (current evidence; source hint when attention)
        → OrderTicket (subordinate provenance cue; correlation_id on request)
  → preview / submit (INTERNAL_SIMULATION only)
  → ExecutionTracePanel (decision provenance + correlation from intent metadata)
```

## Provenance architecture

| Field | Lane | Attention | Manual | Unknown |
|-------|------|-----------|--------|---------|
| `sourceAttentionId` | `lane:{moduleId}` | `{attention_id}` or `attention:{id}` | absent | malformed / unsupported prefix |
| `sourceContext` | optional (usually absent) | headline, tier, reasons | absent | may be partial |
| `parsePaperDraftProvenance().type` | `LANE` | `ATTENTION` | `MANUAL` | `UNKNOWN` |
| Handoff panel | Handoff from {lane} | Attention handoff | hidden | Unknown provenance |
| `correlation_id` on API | `lane:{moduleId}` | attention id | omitted (client_order_id fallback server-side) | omitted |

Pure helpers in `paper-now/paperOrderDraft.ts` and `paper-workspace/buildPaperHandoffModel.ts`.

## Fields persisted server-side

- `correlation_id` on Paper order intent/events when UI sends it (existing `paper_projections._parse_order_body` contract)
- `decision_source_snapshot` on intent — bounded headline/tier/reasons for Paper Command; lane module for workspace lanes ([source snapshot completion](2026-08-31-paper-decision-source-snapshot-completion.md))
- Lane: `lane:squeeze` etc.
- Attention: raw `attention_id` (e.g. `ATT-123`, `attention-biya`)

## UI-only

- Full `sourceContext` draft object — only validated subset persists as `decision_source_snapshot`
- Source-time evidence snapshot — no historical workspace evidence archive
- Cannot claim evidence "changed since handoff" without comparing to current cockpit (snapshot is historical only)

## `correlation_id` semantics

Backend already accepts optional `correlation_id` on preview/submit; defaults to `client_order_id` when absent. UI now sets `correlation_id` to `sourceAttentionId` for valid lane/attention provenance only — not overloaded with display prose. Trace UI reads `intent.correlation_id` from step metadata.

## Authority behavior

- `canUsePaperActions` unchanged
- Authority loss: handoff and observational cockpit remain readable; ticket/preview/submit gated
- Demo/Live: no Paper mutation paths added

## Reload / navigation behavior

- Draft consumed on PUSH via `WorkspaceRoute` `useState` initializer; route state cleared with `replace`
- Browser refresh / direct URL: no draft → manual entry cockpit (no fake handoff)
- Paper Command need not stay mounted

## Malformed provenance

- `lane:` empty, `attention:` empty, unsupported prefixes → `UNKNOWN`, safe degradation, observational workspace usable

## Tests

```text
cd ui
npm test    # 352 passed (66 files)
npm run build   # pass; initial bundle 199.16 KiB gzip
```

New/updated: `paperOrderDraft.test.ts`, `buildPaperHandoffModel.test.ts`, `PaperHandoffPanel.test.tsx`, cockpit/workspace/App integration tests, `OrderTicket.test.tsx`, `PaperNowPage.test.tsx`.

## Deferred

- Dedicated backend provenance metadata field beyond `correlation_id`
- Attention lifecycle (expired/resolved) — not in AttentionItem schema
- Historical source-vs-current evidence diff

> **Update 2026-09-01:** `AttentionItem.surfaced_time` and draft `sourceContext.source_time` carry source timestamps through handoff — see [source time completion](2026-09-01-paper-decision-source-time-completion.md).

## Next increment

Paper execution history list surfacing decision provenance labels from `correlation_id` on the Portfolio orders table with link to execution trace.
