# SOP: Add Workspace Lane

## 1. Route

`Mode{Lane}WorkspaceRoute` lazy-loaded in `App.tsx`.

## 2. Observability

`*WorkspaceObservability` — shared data tables/charts.

## 3. Mode content

`WorkspaceModuleModeShell` + `buildLaneModeContent` for Demo/Paper/Live copy.

## 4. Lane IDs

The single canonical source is `WORKSPACE_LANE_REGISTRY` in
`ui/src/components/workspace-module-shared/laneRegistry.ts` (ids, labels,
routes). Derived consumers (`LANE_MODULE_IDS`, `isKnownLaneModuleId`,
`laneModuleLabel`, evidence maps in `paperDecisionSemantics.ts`) read from it.
Adding a lane edits that one registry plus its per-lane feature surfaces
(route components, content builders, backend projection when a new API is
needed) — never a second module-id list. A lane-registry equality test
(`laneRegistry.test.ts`) fails if the derived lists drift.

## 5. Navigation

Workspace index and nav links if operator-facing.

## 6. Paper provenance

`createLanePaperOrderDraft(instrumentId, moduleId)` for handoff.

## 7. Demo / Paper / Live semantics

Demo/Live read-only notes; Paper simulation context.

## 8. App integration tests

`/workspace/BIYA/{lane}` in Demo, Paper, Live.

## 9. Backend APIs

Projection + hook + `queryKeys.workspace*` if new endpoint.

## 10. Docs

Update [FRONTEND_GUIDE.md](../FRONTEND_GUIDE.md) lane list if needed.

Validation: vitest + `validate.py changed` (ui domain if backend).
