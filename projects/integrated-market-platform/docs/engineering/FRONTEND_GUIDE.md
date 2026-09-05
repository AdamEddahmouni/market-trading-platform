# Frontend Guide

**Status:** Authoritative UI patterns for IMP.

## Stack

React 18, TypeScript, Vite, React Router 6, TanStack Query 5, Zod, Lightweight Charts.

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

## Paper cockpit

`PaperWorkspacePage` → `PaperDecisionCockpit` + `WorkspaceObservability`. See [PAPER_DECISION_LIFECYCLE.md](../architecture/PAPER_DECISION_LIFECYCLE.md).

## CSS organization

Mode-specific styles: `ui/src/styles/{demo,paper,live}-*.css`. Shared tokens: `tokens.css`, `layout.css`.

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
