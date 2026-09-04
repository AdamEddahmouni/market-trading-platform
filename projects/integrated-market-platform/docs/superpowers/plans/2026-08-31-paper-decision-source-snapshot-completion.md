# Paper Decision Source Snapshot — Completion Record

> **Current architecture:** [PAPER_DECISION_LIFECYCLE.md](../../architecture/PAPER_DECISION_LIFECYCLE.md)

**Date:** 2026-08-31  
**Status:** Complete  
**Tracking:** [WORK_LOG.md](../../engineering/WORK_LOG.md)

## Goal

Persist a lightweight, immutable **decision-source snapshot** with Paper simulated intents so historical Portfolio and execution trace rows can answer *why* a decision was created — without strategy attribution, analytics, or implying current market truth.

## Persisted schema (`decision_source_snapshot`)

Stored on Paper order **intent** (optional) and projected to portfolio orders via `project_orders()`.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `source_type` | `"paper_command_attention"` \| `"workspace_lane"` | yes | Aligns with provenance classification |
| `source_id` | string (≤128) | yes | Attention id or lane module id |
| `source_module` | string (≤64) | lane only | Same as `source_id` for lanes |
| `headline` | string (≤240) | no | Attention headline or optional lane summary |
| `tier` | int ≥0 | no | Paper Command tier when present |
| `reasons` | `{code,label}[]` (≤5) | no | Bounded attention reasons |
| `source_time` | int | no | Epoch ns (or ms legacy fixtures): when source context was captured at handoff |

### Fields intentionally not persisted

- `priority_rank`, `explanation_ref` — not stable decision context
- Presentation/CSS fields (`headlineColor`, etc.)
- Full lane API payloads, order books, option chains, filings
- Current workspace evidence, preview output, risk state
- Arbitrary `metadata` bags

### UI-only (unchanged at handoff)

- Live workspace evidence in cockpit
- Preview/risk revalidation results
- `sourceContext` on drafts remains the handoff carrier; only the validated subset maps to `decision_source_snapshot` on preview/submit

## Identity semantics

| Concept | Answers | Mutable? |
|---------|---------|----------|
| `correlation_id` | Which decision chain/source identity? | Set at submit; identity anchor |
| Provenance parser | Lane / Paper Command / manual / unknown classification | Derived from `correlation_id` |
| `decision_source_snapshot` | What minimal descriptive context existed at handoff? | **Immutable** after intent creation |

Snapshot must match correlation on write (`validate_snapshot_against_correlation`). On read, mismatch → snapshot hidden (`snapshotMismatch`).

## Lifecycle

```
Draft sourceContext (UI)
  → buildPaperDecisionSourceSnapshot(draft)
  → preview/submit request.decision_source_snapshot
  → build_user_order_intent(..., decision_source_snapshot=...)
  → OrderIntentCreated event
  → project_orders() enriches order
  → Paper Portfolio / ExecutionTracePanel (historical label)
```

Preview does not mutate the snapshot.

## Backend storage

- **Location:** intent body field `decision_source_snapshot`
- **Validation:** `paper/decision_source.py` — parse, bound, correlation match
- **Projection:** `PaperExecutionLedger.project_orders()` copies from linked intent
- **API:** optional field on preview/submit body via `paper_projections._parse_order_body`

## Frontend presentation

- **Table row:** provenance badge + concise `tableSourceSummary` (headline when persisted)
- **Expanded details:** `PaperPersistedSourceContextPanel` — headline, tier, reasons, source time; labeled *Source context at decision handoff*
- **Trace:** same panel once in trace summary (not repeated per step)
- **Legacy orders:** no snapshot → omit source detail gracefully
- **Manual orders:** no fake snapshot generated

## Mismatch / malformed handling

- Backend: reject write when snapshot conflicts with `correlation_id`
- Frontend: `parsePaperDecisionSourceSnapshot` fails soft; mismatch hides snapshot with explicit message

## Privacy / data minimization

Market-decision context only. No credentials, conversation content, or large evidence archives.

## Tests

| Suite | Result |
|-------|--------|
| Vitest | **387 passed** (71 files) |
| `validate.py changed` | **858 passed** |
| `validate.py full` | **2968 passed** |
| Build / bundle | pass; initial **199.17 KiB gzip** |

New: `test_paper_decision_source_snapshot.py`, snapshot/provenance/history/trace UI tests.

## Deferred

- Lane headline from lane mode content at handoff
- Strategy performance / win rates / source P&L attribution

> **Update 2026-09-01:** `source_time` population completed — see [source time completion](2026-09-01-paper-decision-source-time-completion.md).

## Related completion records

- [Paper Portfolio decision history](2026-08-31-paper-portfolio-decision-history-completion.md) — updated
- [Paper Command handoff](2026-08-31-paper-command-workspace-handoff-completion.md) — updated
- [Paper Workspace cockpit](2026-08-31-paper-workspace-decision-cockpit-completion.md) — updated
