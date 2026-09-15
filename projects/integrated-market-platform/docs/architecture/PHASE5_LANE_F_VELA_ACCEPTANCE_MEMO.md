# Phase 5 Lane F — Vela production-default acceptance memo

**Base:** `abced39f126baf97121ba6ebb21d76d9296aac9f`  
**Branch:** `phase5/lane-f-vela-acceptance`  
**Decision label:** `VELA_SHADOW_RETAINED_INCOMPLETE_INTERACTIVE_ACCEPTANCE`  
**Date:** 2026-09-14 (Lane F worker)

## Summary

`@luxalgo/vela` remains **opt-in workspace shadow** (`imp_vela_shadow` / localStorage). **lightweight-charts** stays the production default. Lazy bundle budgets pass on main-line adapter wiring; IMP bar identity and semantic markers remain canonical. Production default was **not** flipped because several **material** acceptance rows lack browser-measured evidence (interaction, scrub-linked workspace replay, mobile, real engine init at 50k–100k bars, memory).

## Bundle performance (measured)

Command: `npm run build` in `projects/integrated-market-platform/ui` (worktree `phase5-lane-f-vela`).

| Metric | Measured | Budget |
|--------|----------|--------|
| Initial JS (gzip) | **201.06 KiB** | ≤ 203.00 KiB |
| Lazy `vela-*` chunk (gzip) | **246.08 KiB** | off entry graph |
| Lazy `vela-*` chunk (raw) | **870.73 KiB** | ≤ 950 KiB |
| Vela on Vite entry static graph | **absent** | required |

Evidence class: **SOFTWARE** (build script `scripts/check-bundle-budget.mjs`).

## IMP projection performance (measured)

Command: `npm test -- impVelaAcceptanceMeasurements.test.ts` (vitest, Node `perf_hooks`).

Numbers are logged as `[lane-f-vela-perf] projection` in test stdout; thresholds guard regressions (&lt;500 ms `toVelaSeries` @ 100k bars).

| Bars | `toVelaSeries` (ms) | `impBarSeriesFingerprint` (ms) |
|------|---------------------|--------------------------------|
| 10k | **2.72** | **0.22** |
| 50k | **9.24** | **0.18** |
| 100k | **38.0** | **0.05** |

Dense marker projection (250 callouts, 5k bars, mock drawings host): **2.60 ms** (`applyImpMarkers`).

**Not measured in this lane:** real `Vela` constructor `ready()` latency, WebGL/canvas init, pan/zoom FPS, heap after 100k bars — requires headed browser harness (out of scope for vitest/jsdom).

## Acceptance matrix

| Criterion | Status | Evidence |
|-----------|--------|----------|
| Desktop interaction (pan/zoom/crosshair) | **BLOCKED** | No headed browser run in lane; adapter mounts with `ResizeObserver` only (unit test) |
| Resize | **PASS (software)** | `ImpVelaChartAdapter` + `ResizeObserver` — `ImpVelaChartAdapter.test.tsx` |
| Large history 10k / 50k / 100k IMP projection | **PASS (software)** | `impVelaAcceptanceMeasurements.test.ts` |
| Large history Vela render | **BLOCKED** | No WebGL/canvas measurement |
| Incremental updates | **PASS (software)** | `setMarket` on fingerprint change — `ImpVelaChartAdapter.test.tsx` |
| Backfill | **PASS (software)** | `governedSyntheticFeed.backfillOlderBars` + lab control — lab page source |
| Replay scrub (workspace) | **PARTIAL** | Scrub slices bars in `WorkspaceObservability`; Vela path uses full `setMarket` — not browser-verified under scrub |
| Multiple chart overlays | **FAIL** | No overlay series API wired in adapter (candles only) |
| Dense event markers | **PASS (software)** | `applyImpMarkers` load test |
| SEC / public record markers | **PASS (software)** | `workspaceSemanticMarkers` + `sec_public_record` kind |
| Congressional PTR markers | **FAIL** | `laneToMarkerKind` has no CONGRESS/PTR mapping |
| Opportunity annotations | **PASS (software)** | `projectWorkspaceEvidenceMarkers` + shadow-only render path |
| Options-flow replay annotations | **FAIL** | No dedicated marker projection |
| Paper fill markers | **PARTIAL** | `projectPaperStopTargetMarkers` exists; not wired into workspace chart props |
| Workspace persistence | **PASS (software)** | Shadow toggle `localStorage` — `impWorkspaceVelaShadow.test.ts`; layout POST unchanged |
| Mobile interaction | **BLOCKED** | Not exercised |
| Semantic parity (bar_id, timestamps, provenance) | **PASS** | `impBarIdentity.ts`, `mapWorkspaceBarsToImpRecords` |
| Eager Vela import | **PASS** | `impVelaLazyRoute.test.ts` |

## Material criteria blocking production default

1. **Interactive / render acceptance incomplete** — matrix rows marked BLOCKED/FAIL above.
2. **Workspace annotation parity** — default lightweight-charts path ignores `markers`; Vela shadow shows markers but congressional / options-flow / paper-fill gaps remain on the IMP projection side.
3. **No measured real-engine chart init** at replay-scale bar counts.

Operator shadow fallback **retained** (`WorkspacePriceChart` toggle + lightweight default).

## Authority / safety

- No changes to MODE_AUTHORITY, OpportunityEngine, Paper submit, or validation manifest.
- Vela limited to rendering; IMP owns `bar_id`, `source_time_ns`, `available_time_ns`, `provenance`, `marker_id`.

## Next safe step

1. Add headed Playwright (or CI browser) harness: workspace replay scrub + Vela shadow, pan/zoom, memory sample at 10k bars.
2. Extend `workspaceSemanticMarkers` for congressional PTR + options-flow replay lanes; wire `projectPaperStopTargetMarkers` into workspace chart when paper context exists.
3. Re-run lane; if matrix green + render perf acceptable, introduce **production default** behind explicit flag flip with lightweight operator fallback.

## References

- Adapter: `ui/src/components/charts/ImpVelaChartAdapter.tsx`
- Workspace gate: `ui/src/components/charts/WorkspacePriceChart.tsx`, `impWorkspaceVelaShadow.ts`
- Lab: `ui/src/components/charts/ImpVelaChartLabPage.tsx` (lazy route `/research/vela-chart-lab`)
- Historical spike: PR #145 (superseded; do not merge)
