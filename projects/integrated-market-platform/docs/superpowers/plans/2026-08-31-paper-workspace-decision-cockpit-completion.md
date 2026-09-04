# Paper Workspace Decision Cockpit — Completion Record

**Date:** 2026-08-31  
**Status:** Complete  
**Tracking:** [WORK_LOG.md](../../engineering/WORK_LOG.md)

## Goal

Transform the Paper Workspace Overview (`/workspace/:symbol`) from a generic order-ticket landing page into a source-backed **decision cockpit** that answers why the operator is looking at a symbol, what evidence supports or contradicts a thesis, what risk context applies, and whether preview/revalidation authorizes submission.

## Before → after workflow

| Before | After |
|--------|-------|
| Lane → workspace → order ticket | Lane evidence → explicit handoff → decision context → preview → simulated order |
| Single lane arrival note in header | Dedicated `LaneHandoffPanel` with placeholder disclosure and provenance |
| Top-4 context lanes on ticket only | Cross-lane `Decision snapshot` + `What matters now` summary |
| Preview state buried in ticket | First-class `PaperPreviewStatus` synchronized via `onPreviewStateChange` |
| No portfolio context on overview | Compact `PaperRiskContext` (buying power, exposure, symbol position, authority) |
| Direct workspace entry had no framing | Neutral “No lane handoff” entry with full observational cockpit |

## Architecture

```
PaperWorkspacePage
  └── PaperDecisionCockpit
        ├── LaneHandoffPanel          (lane/attention draft only)
        ├── PaperDecisionSnapshotPanel
        ├── PaperWhatMattersNow
        ├── PaperRiskContext
        ├── PaperPreviewStatus        ← OrderTicket onPreviewStateChange
        └── OrderTicket               (showLaneBanner=false in cockpit)
  └── WorkspaceObservability          (unchanged full evidence UI)
```

Pure view-model layer in `ui/src/components/paper-workspace/`:

| File | Role |
|------|------|
| `buildLaneHandoffModel.ts` | Lane/attention provenance, placeholder disclosure, unknown/malformed handling |
| `paperDecisionSemantics.ts` | Evidence lane → module ID mapping; direction → hint classification |
| `buildPaperDecisionSnapshot.ts` | Supports / contradicts / unclear / data gaps from workspace evidence API |
| `buildPaperRiskContext.ts` | Compact symbol-aware portfolio/risk context (reuses `paperRiskMetrics`) |
| `paperPreviewPresentation.ts` | Preview state machine → presentation states |

Extended `paperOrderDraft.ts` with `LANE_MODULE_IDS`, `isKnownLaneModuleId`, and safer `parseLaneProvenance` (unknown lane degradation).

## Source-backed behavior

- Decision classification uses `WorkspaceEvidenceLane.direction` (`POSITIVE`/`NEGATIVE`/`NEUTRAL`/`UNKNOWN`) — no invented confidence scores
- Evidence lane mapping covers 8 backend lanes; `large-transactions` and `fund-etf` appear as documented data gaps
- Source lane emphasized as “Primary handoff evidence” without greater truth value
- No historical handoff snapshot — current-vs-origin copy is truthful only

## Safety model

- Paper simulation-only; `canUsePaperActions` unchanged
- Preview/submit remain fail-closed via existing `OrderTicket` generation guard + `confirmedRequestIsCurrent`
- Authority loss: observational cockpit remains readable; ticket hidden with explicit warnings
- Demo/Live workspace pages unchanged — no Paper cockpit mutation UI
- Unknown provenance (`lane:unknown`) degrades safely

## Preview states

`NOT_PREVIEWED`, `PREVIEWING`, `ACCEPTED`, `REJECTED`, `REVALIDATION_REQUIRED`, `AUTHORITY_UNAVAILABLE`, `ERROR` — derived from actual `OrderTicket` internals via `derivePreviewPresentationState`.

## Test coverage

```text
cd ui
npm test    # 343 passed (66 files)
npm run build   # pass; initial bundle 199.18 KiB gzip
```

New tests: `buildLaneHandoffModel`, `buildPaperDecisionSnapshot`, `paperPreviewPresentation`, `buildPaperRiskContext`, `LaneHandoffPanel`, `PaperDecisionSnapshot`, `PaperPreviewStatus`, `PaperDecisionCockpit`; extended `PaperWorkspacePage`, `OrderTicket`, `App.test.tsx`.

## Deferred backend capabilities

- `sourceContext` (headline/tier/reasons) mapped to persisted `decision_source_snapshot` on preview/submit — see [source snapshot completion](2026-08-31-paper-decision-source-snapshot-completion.md)
- No evidence snapshot at handoff time — cannot claim evidence “changed since handoff”
- Workspace evidence has 8 lanes, not 10
- Evidence `direction` is coarser than per-lane `buildLaneModeContent` hints inside lane modules

**Update (2026-08-31 handoff increment):** `sourceAttentionId` is now sent as `correlation_id` on preview/submit when provenance is valid. See [Paper Command handoff completion](2026-08-31-paper-command-workspace-handoff-completion.md).

**Update (2026-09-01 source time increment):** Cockpit handoff panel displays semantic source timestamps (`Attention surfaced` / `Lane handoff created`) — see [source time completion](2026-09-01-paper-decision-source-time-completion.md).

## Related

- [Paper Command handoff completion](2026-08-31-paper-command-workspace-handoff-completion.md)
- [Mode-specific surfaces completion](2026-08-31-mode-specific-surfaces-completion.md)
- [Lane content completion](2026-08-31-mode-specific-lane-content-completion.md)

## Best next increment

**Portfolio orders provenance column:** surface `formatPaperDraftSourceLabel` / trace link from persisted `correlation_id` on the Paper Portfolio orders list.
