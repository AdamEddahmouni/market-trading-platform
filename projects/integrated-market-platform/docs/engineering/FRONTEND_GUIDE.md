# Frontend Guide

**Status:** Authoritative UI patterns for IMP.

## Stack

React 18, TypeScript, Vite, React Router 6, TanStack Query 5, Zod, Lightweight Charts.

## Primary nav (shipped)

`NavShell` labels after UIR-01. Keep labels and `App.tsx` routes in lockstep; do not invent paths.

| Label | Route | Meaning |
|-------|-------|---------|
| Command | `/` | Now desk; Signals desk is `?desk=signals` (`/signals` redirects) |
| Radar | `/radar` | Discovery queue (Opportunities + Screeners tabs). `/discover` → `/radar`; `/explore` → `/radar/screeners` |
| Workspace | `/workspace` | Decision desk (Paper submit boundary) |
| Portfolio | `/portfolio` | Orders history |
| Research | `/research` | Research & model labs. `/lab` redirects here; it is not a workspace alias |
| Control | `/control` | Operator control center (was labeled "Risk") |

Operator group: Live Canary `/live-canary`, Settings `/settings`, Diagnostics `/diagnostics/provider`. Paper mode hints: Workspace — Decision desk; Portfolio — Orders history; Research — Research & model labs. Operator URLs: [DEVELOPER_RUNBOOK.md](DEVELOPER_RUNBOOK.md).

## Mode route pattern

```
Mode*Route.tsx
  switch (session.mode)
    DEMO  → Demo*Page
    PAPER → Paper*Page
    LIVE  → Live*Page
```

Each page composes shared `*Observability` + mode-specific controls/copy/CSS (`demo-*`, `paper-*`, `live-*` styles).

## Pure view models

Business logic for display belongs in pure modules (`build*Model.ts`, `*Presentation.ts`, `*Semantics.ts`) — not inline in large components.

## Lazy loading

Heavy routes use `React.lazy` + `LazyBoundary` in `App.tsx`. Do not statically import lane pages on the entry path.

## React Query keys

**Registry:** `ui/src/api/hooks.ts` → `queryKeys`

### Invariants

1. Same key ⇒ same `queryFn` and response shape
2. Include `symbol`, `dataMode`, IDs when response depends on them
3. Add new keys to `queryKeys` — avoid ad-hoc string arrays
4. Intentional shared cache (e.g. `canary-snapshot` across Live routes) must be documented

### Known shared keys

| Key | Shared across |
|-----|---------------|
| `["canary-snapshot"]` | Live portfolio, workspace strips, canary page |
| `["canary-reconciliation"]` | Live portfolio, canary page |

### Invalidation

Mode switch invalidates `context`, `attention`, `instrument` (see `App.tsx`).

## Route state

Paper draft handoffs use React Router `location.state` — short-lived, not a persistence layer.

## Versioned draft state

`paperOrderDraft.ts` — version field, `sourceContext`, provenance parsing. Preserve `initialDraft.sourceContext` through OrderTicket lifecycle.

## API errors

UI API failures use `{ error, reason_code, error_category }`. `error_category` is one of the twelve backend WS05 values in `ui_api/errors.py` (`CanonicalErrorCategory`). Frontend `ui/src/api/errors.ts` is a typed union of those values only — it does not map `reason_code` onto a category and does not invent categories. If the API omits `error_category` or returns an unknown value, parsing fails closed (generic request failure). Classified errors surface as `error_category: reason_code: error`. `fetchJson` dynamically imports the envelope parser so it stays off the initial JS budget; Paper mutation surfaces format classified errors from already-lazy pages.

## Paper cockpit

**Workspace** is the decision desk: `PaperWorkspacePage` → `PaperDecisionCockpit` + `WorkspaceObservability`. **Portfolio** (`/portfolio`) is orders history, not the submit surface. See [PAPER_DECISION_LIFECYCLE.md](../architecture/PAPER_DECISION_LIFECYCLE.md).

## CSS organization

Mode-specific styles: `ui/src/styles/{demo,paper,live}-*.css`. Shared tokens: `tokens.css`, `layout.css`. Operator design system: `ui/src/components/imp-ui/imp-ui.css` (primitives) + `ui/src/styles/radar.css` (Radar surface) + `ui/src/components/opportunity/opportunity.css` (shared opportunity card/queue). Semantic state tones (`--imp-state-{tone}-{fg,bg,border}`) live in `tokens.css`; all enum/state rendering goes through `ui/src/state/semanticState.ts` (`resolveSemanticState`) — translate, never invent; unknown values render neutral with the raw string preserved.

## Opportunity presentation (one language)

Radar, Command, and Paper surfaces share `ui/src/components/opportunity/`:
`opportunityPresentation.ts` (presentation state, evidence/freshness/next-action
derivation, eligibility predicates), `opportunityDetailModel.ts` (L1–L4 detail
sections), `OpportunityCard`/`OpportunityQueue`/`OpportunityFeedState` (compact
queue + feed states), used by Radar (dense table + detail) and the Command
overview queue. Page context changes layout, never semantic meaning. Below
1024px the Radar detail opens in an overlay sheet (`RadarDetailSheet`).

## Attention signals (one language)

Attention items are signals, not opportunities. `ui/src/components/attentionPresentation.ts`
holds the shared signal language (tier urgency, why-now from reason labels);
`AttentionFeed` renders it on Command Overview, the Signals desk, and (as the
drafting variant `PaperCandidateQueue`) Paper. The signal→opportunity bridge is
`attentionOpportunityLinks(rows)` in `opportunityPresentation.ts`: the backend
ingests attention rows with `summary_id = attention_id`, so an exact key match
is the only supported link — linked signals deep-link to `/radar?selected=<id>`.
Command's KPI strip is decision-oriented (`overviewDecisionKpis`): feed trust,
actionable count, attention load, degradation — never portfolio/account metrics
(those live in the risk ribbon and page headers).

## Testing patterns

- Pure helper: `*.test.ts` colocated or in same folder
- Component: `@testing-library/react`
- Integration: `App.test.tsx` navigates routes per mode

## Bundle budget

`npm run build` enforces 200 KiB gzip initial. See [PERFORMANCE.md](PERFORMANCE.md).

---

## Checklist: new mode-aware surface

1. Inspect existing `Mode*Route` pattern
2. Create Demo/Paper/Live pages (or extend existing family)
3. Extract shared observability if tables/metrics overlap
4. Wire route in `App.tsx` (lazy if heavy)
5. Update `NavShell` hints if primary nav
6. Apply `evaluateModeContext` / `canUsePaperActions` for Paper controls
7. Add `App.test.tsx` navigation per mode
8. Run vitest + build
9. Update docs if behavior is novel

Full SOP: [ADD_MODE_AWARE_SURFACE.md](sops/ADD_MODE_AWARE_SURFACE.md).

---

## Checklist: new workspace lane

0. Add the lane to `WORKSPACE_LANE_REGISTRY` in
   `workspace-module-shared/laneRegistry.ts` — the single canonical module-id
   source. Derived lists (`LANE_MODULE_IDS`, evidence maps) follow it.
1. Create `Mode*WorkspaceRoute` (lazy in App)
2. Add `*WorkspaceObservability` + `WorkspaceModuleModeShell`
3. Add `buildLaneModeContent` entries for Demo/Paper/Live copy
4. Register route path (`/workspace/:symbol/<lane>`)
5. Add `queryKeys.workspace*` + hook if new API
6. Paper: lane draft handoff via `createLanePaperOrderDraft`
7. App integration tests for all three modes
8. Backend projection if new API needed

Full SOP: [ADD_WORKSPACE_LANE.md](sops/ADD_WORKSPACE_LANE.md).
