# SOP: Add Workspace Lane

## 1. Route

`Mode{Lane}WorkspaceRoute` lazy-loaded in `App.tsx`.

## 2. Observability

`*WorkspaceObservability` — shared data tables/charts.

## 3. Mode content

`WorkspaceModuleModeShell` + `buildLaneModeContent` for Demo/Paper/Live copy.

## 4. Lane IDs

Use canonical module ID (`LANE_MODULE_IDS` / `isKnownLaneModuleId`).

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
