# UI — Agent Instructions

Parent: [AGENTS.md](../AGENTS.md)

## Patterns

- `Mode*Route` → `Demo|Paper|Live*Page` + shared `*Observability`
- React Query: `ui/src/api/hooks.ts` → `queryKeys` — **never** duplicate semantics under same key
- Paper: `canUsePaperActions` from `mode-session/modeAuthority.ts`
- Lazy routes in `App.tsx` for lanes and heavy pages

## Tests

```powershell
cd ui
npm test
npm run build   # includes 200 KiB gzip budget
```

From the repository root, `python tools/imp.py lint` runs the UI typecheck
when UI paths are affected, and `python tools/imp.py closure` runs the final
UI test, typecheck, and build gates when UI changes are present.

Update `App.test.tsx` when routes, nav, or mode handoffs change.

## Guides

- [FRONTEND_GUIDE.md](../docs/engineering/FRONTEND_GUIDE.md)
- [ADD_MODE_AWARE_SURFACE.md](../docs/engineering/sops/ADD_MODE_AWARE_SURFACE.md)
- [ADD_WORKSPACE_LANE.md](../docs/engineering/sops/ADD_WORKSPACE_LANE.md)
- [ACCESSIBILITY.md](../docs/engineering/ACCESSIBILITY.md)
- [PERFORMANCE.md](../docs/engineering/PERFORMANCE.md)

## Paper UI safety

- Order submit only from Workspace cockpit with current preview
- Preserve `initialDraft.sourceContext` through OrderTicket lifecycle
- Authority loss: hide ticket, keep observability
