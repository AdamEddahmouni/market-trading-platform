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
| Portfolio | `/portfolio` | Simulated/observed holdings, P&L, risk context, order history (not the submit surface) |
| Research | `/research` | Interpretation-first evidence workspace: Overview, Evidence, Validation, Simulation sections (routable) |
| Lab | `/lab` | Experimental workbench: Overview, Validation, Simulation, Chart Lab. Inspectable/read-only on current contracts; `/research/vela-chart-lab` redirects to `/lab/chart-lab` |
| Control | `/control` | Operator control center (was labeled "Risk") |

Radar Screeners still host `DiscoverObservability` (the leftover Discover desk). It is **investigation-only**: candidates are not opportunity contracts or trade signals. Demo/Live pass `allowMutations={false}` — GET poll only; refresh, `promote-to-live-analysis`, and `POST /discover/mixed/release` stay off. Paper may mutate those housekeeping endpoints; that is not Live execution (`LIVE-001` remains blocked). Empty screener snapshots use `EmptyState` and do not invent a ranked-queue fault or a trade CTA.

Operator group: Live Canary `/live-canary`, Settings `/settings`, Diagnostics `/diagnostics/provider`. Paper mode hints: Workspace — Decision desk; Portfolio — Paper positions; Research — Evidence & validation. Operator URLs: [DEVELOPER_RUNBOOK.md](DEVELOPER_RUNBOOK.md).

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

**Workspace** is the decision desk: `PaperWorkspacePage` → `PaperDecisionCockpit` + `WorkspaceObservability`. **Portfolio** (`/portfolio`) is the operator view of simulated/observed holdings, exposure, P&L, and order history — not the submit surface. See [PAPER_DECISION_LIFECYCLE.md](../architecture/PAPER_DECISION_LIFECYCLE.md) and [portfolio-contract-map.md](../ui-redesign-v2/portfolio-contract-map.md).

## CSS organization

Mode-specific styles: `ui/src/styles/{demo,paper,live}-*.css`. Shared tokens: `tokens.css`, `layout.css`. Operator design system: `ui/src/components/imp-ui/imp-ui.css` (primitives) + `ui/src/styles/radar.css` (Radar surface) + `ui/src/styles/research.css` (Research surface) + `ui/src/styles/lab.css` (Lab workbench, lazy-imported from Lab pages) + `ui/src/components/opportunity/opportunity.css` (shared opportunity card/queue). Semantic state tones (`--imp-state-{tone}-{fg,bg,border}`) live in `tokens.css`; all enum/state rendering goes through `ui/src/state/semanticState.ts` (`resolveSemanticState`) — translate, never invent; unknown values render neutral with the raw string preserved.

## Opportunity presentation (one language)

Radar, Command, and Paper surfaces share `ui/src/components/opportunity/`:
`opportunityPresentation.ts` (presentation state, evidence/freshness/next-action
derivation, eligibility predicates), `opportunityDetailModel.ts` (L1–L4 detail
sections), `opportunityOperatorBrief.ts` (Radar operator questions from attached
fields only), `OpportunityCard`/`OpportunityQueue`/`OpportunityFeedState` (compact
queue + feed states), used by Radar (dense table + detail) and the Command
overview queue. Page context changes layout, never semantic meaning. Below
1024px the Radar detail opens in an overlay sheet (`RadarDetailSheet`).

Radar detail L1 includes an operator brief that answers: what happened, why IMP
is showing it, freshness (including `freshness_evaluation` reason codes, feed
as-of, and honest UNKNOWN event-vs-receive lag when the same clock is reused),
supporting providers, conflicts, inference vs observation, unknowns, what would
invalidate it, available action, and why action may be refused. Missing live
receive clocks stay `NOT_APPLICABLE` / `LIVE_AS_OF_UNAVAILABLE`; withheld ranked
counts are parsed from the summary payload. Missing contract fields stay
`UNKNOWN` / `UNAVAILABLE`. The brief never invents live execution, calibration,
or Item 9 collection status. Queue rows expose attached providers (or `UNKNOWN`)
beside freshness.

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

## Control (operator platform health)

`/control` (`ui/src/components/control/`) answers "can IMP operate correctly and
safely right now?" — operating state, execution authority, provider/data health,
opportunity-feed readiness, and legitimate corrective actions. It is not
Diagnostics (raw telemetry stays on `/diagnostics/provider`) and not Settings
(persistent configuration stays on `/settings`; credential forms live behind the
Advanced disclosure for parity). Rules:

- Every state renders through `resolveSemanticState` (`platform` domain covers
  lifecycle/readiness/check/update values); unknown or failed endpoints render
  honestly (neutral "Unavailable" + per-section retry), never as healthy.
- Sections degrade independently — one failing endpoint never collapses the page.
- Sections carry stable anchors (`controlPresentation.CONTROL_SECTIONS`);
  Command/StatusBar degraded-state links deep-link to `/control#control-feed` /
  `/control#control-authority`, and the page scrolls to and marks the target.
- Lifecycle actions (restart / check_update / apply_update) manage the local
  workstation only; apply-update is confirm-gated inline. No trading authority
  is granted or implied anywhere on the page.
- Queries: `operatorReadiness` (60s), `operatorLifecycleStatus` (30s),
  `operatorConfig` (60s), plus shared `context` / `opportunitiesSummary` /
  `paperPortfolio` caches.

## Research (interpretation-first evidence)

`/research` (`ui/src/components/research-shared/`) is a claim-navigation
workspace: Overview leads with a graph from source → hypothesis → strategy →
experiment → evidence → contradiction → implementation → forward-test. Missing
contracts stay `NOT_EXPOSED` / Not on this surface. Never prediction, ranked
opportunity, or execution. Contract map:
[docs/ui-redesign-v2/research-contract-map.md](../ui-redesign-v2/research-contract-map.md).

Routable sections (one fetch family per section; Overview synthesizes all three):

| Route | Section | Endpoints |
|-------|---------|-----------|
| `/research` | Overview | analytics + models + simulation (claim graph scoped by `?claim=`) |
| `/research/evidence` | Evidence | `/research/analytics` (`?panel=` deep-link) |
| `/research/validation` | Validation | `/research/models` (`?conflict=1` filters ABSTAIN_CONFLICTING_EVIDENCE) |
| `/research/simulation` | Simulation | `/research/simulation` |
| `/research/vela-chart-lab` | (redirect) | → `/lab/chart-lab` |

Lab workbench (`/lab`, see [lab-contract-map.md](../ui-redesign-v2/lab-contract-map.md)):

| Route | Section | Endpoints |
|-------|---------|-----------|
| `/lab` | Overview | models + simulation (workflow status) + `GET /operator/diagnostics` (Item 9 / Live honesty only) |
| `/lab/validation` | Validation workbench | `/research/models` |
| `/lab/simulation` | Simulation workbench | `/research/simulation` + shared operator diagnostics (calibration honesty) |
| `/lab/chart-lab` | Chart Lab | none (local synthetic) |

Research keeps interpretation; Lab inspects process. Claim-to-implementation hops
are finding-scoped: walk-forward strategy outcomes land on `/lab/validation`,
risk-decision findings land on `/lab/simulation`, and squeeze/attention findings
stay honest gaps (no Lab process contract). Unscoped Overview implementation
points at `/lab`. **NO LAB MUTATIONS.** Item 9 / Live
honesty stays mounted when Overview dual-loads fail or Simulation snapshot errors;
diagnostics failures stay `UNAVAILABLE` (never a minted 2/3). Hypotheses,
domains, source catalogs, supporting/contradictory flags, and FTEP campaign
state have **no UI contract**. They appear as claim-graph nodes with honest gap
labels, not as fabricated objects. Overview `?claim=<panel_key>` scopes the
eight-node thread to one analytics finding (source/evidence deep-link to that
panel; off-path nodes stay visible and unlabeled as action). The only conflict
signal is `ABSTAIN_CONFLICTING_EVIDENCE` on walk-forward interpretations
(`?conflict=1`). Paper forward tests stay on Workspace; Research does not fetch
them. Radar Screeners deep-link to `/research/evidence?panel=squeeze_outcomes`;
Opportunity L3 links to `/research/evidence` without fabricating per-opportunity
relations. Presentation: `researchPresentation.ts` + `research` domain in
`semanticState.ts`.

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
