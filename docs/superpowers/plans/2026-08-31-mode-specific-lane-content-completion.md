# Workspace Lane Mode-Specific Product Content — Completion Record

**Date:** 2026-08-31  
**Status:** Complete  
**Tracking:** [WORK_LOG.md](../../engineering/WORK_LOG.md)

## Goal

Move workspace lane modules beyond shared observability + mode chrome into three purpose-built operating environments (Demo / Paper / Live) with truthful, data-backed mode context across all 10 lanes.

## Architecture

```
Mode*WorkspaceRoute
  └── WorkspaceModuleModeShell (mode header, restriction note, Paper draft link)
        └── *WorkspaceObservability (mode prop)
              └── ModeAwareWorkspaceLane
                    ├── LaneModeContextPanel  ← buildLaneModeContent(mode, moduleId, API data)
                    ├── LiveLaneOperationalStrip (Live only; shared canary/provider cache)
                    └── *WorkspacePanel (unchanged evidence UI)
```

Shared layer lives in `ui/src/components/workspace-module-shared/`:

| File | Role |
|------|------|
| `laneModeContentTypes.ts` | Content/query state types |
| `laneQueryState.ts` | React Query → loading/error/degraded phases |
| `buildLaneModeContent.ts` | Per-lane Demo/Paper/Live view models from existing API fields |
| `LaneModeContextPanel.tsx` | Renders headline, sections, Paper decision hints, limitations |
| `LiveLaneOperationalStrip.tsx` | Shared Live broker/canary operational strip (`queryKey: ["canary-snapshot"]`) |
| `ModeAwareWorkspaceLane.tsx` | Composition wrapper for all lanes |

No new backend APIs. Missing richer fields (e.g. live lane-specific broker snapshots) remain documented as follow-ups inside builders where UI uses best-effort existing payloads.

## Mode behavior summary

| Lane | Demo emphasis | Paper emphasis | Live emphasis |
|------|---------------|----------------|---------------|
| Squeeze | Replay cohort, ignition interpretation, Phase 3A learning | Decision readiness, provenance draft workflow | Broker-observed state, freshness, canary links |
| Order Flow | CVD education, aggressor unknown | Flow confirmation vs thesis, draft workflow | Observational CVD, provider/quality |
| Order Book | Depth/imbalance education | Liquidity/fragility for simulation sizing | Observational DOM, stale/invalid book |
| Catalyst | Event replay interpretation | Thesis timing for simulation | Read-only bridge, no causality claims |
| Options | Activity/skew education | Confirmation score context | Observational chain/activity |
| Futures | Macro/ES interpretation | Regime backdrop for simulation | Observational depth, no execution |
| Large Transactions | Print size interpretation | Prints vs thesis | Observational prints, no intent claims |
| Disclosure | Filing interpretation | Materiality for simulation | Delayed read-only filings |
| Institutional Flow | Whale doctrine / families | Family availability as thesis context | Observational families |
| Fund / ETF | Proxy education | Cross-asset simulation context | Observational proxy flows |

## Paper draft workflow improvements

- `createLanePaperOrderDraft` unchanged contract (`sourceAttentionId: lane:<moduleId>`, BUY × 1 placeholder)
- Shell exposes explicit placeholder note + provenance before navigation
- `PaperWorkspacePage` + `OrderTicket` show lane arrival context; **Paper workspace decision cockpit** (2026-08-31) consolidates handoff, cross-lane evidence summary, risk context, and preview status
- Preview/revalidation unchanged (automatic preview on authorized workspace ticket)
- Demo/Live never expose draft mutation path

## Validation

```text
cd ui
npm test          # 298 passed (2026-08-31)
npm run build     # pass (bundle budget pass)
```

## Follow-ups (backend/data)

- Live lane modules still consume the same workspace lane APIs as Demo/Paper; deeper Live-only broker snapshots would need backend support
- Institutional flow builder uses `families[]` not event streams — richer whale event payloads would improve Paper hints
- Catalyst builder uses `catalyst_count` / `latest_headline` — event-level Paper timing could be stronger with richer fields

## Related

- [Mode-specific surfaces completion](2026-08-31-mode-specific-surfaces-completion.md)
- [Mode-aware workstation](2026-08-30-mode-aware-workstation.md)
- [Paper workspace decision cockpit](2026-08-31-paper-workspace-decision-cockpit-completion.md)
