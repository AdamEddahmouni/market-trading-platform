# Lane G — Vela charting spike decision memo

| Field | Value |
|-------|-------|
| **Branch / worktree** | `spike/vela-cockpit` @ `.worktrees/vela-cockpit` |
| **Date** | 2026-09-14 |
| **Decision** | **`ADOPT_WITH_WRAPPER`** |
| **Scope** | Isolated spike only — no merge to `main`, no Lane E preview / Lane J UX edits |

## Question

Can `@luxalgo/vela` replace or augment IMP workspace charting while IMP retains bar identity, governed timestamps, opportunity/event/Paper semantics, and annotations — without embedding PineTS or silently pulling AGPL into core?

## AGPL / license boundary

| Artifact | License | In spike? | IMP core policy |
|----------|---------|-----------|-----------------|
| `@luxalgo/vela` | Apache-2.0 | Yes | Allowed as optional lazy chart engine |
| `@luxalgo/vela-pinets` | AGPL-3.0 | **No** | Do not add to IMP `ui/package.json` without explicit legal/product decision |
| `pinets` (PineTS runtime) | AGPL-3.0 | **No** | **Forbidden** in core path per lane charter |

Vela’s own docs separate the Apache chart core from Pine addons. This spike uses **native indicators only** (`sma`, `rsi`, auto `volume`) — no scripting engine registered.

Official builds may show Vela attribution; plan for visible attribution or Pro/OEM terms if white-label is required.

## Architecture (target integration)

```
IMP governed bars (bar_id, source_time_ns, instrument_id)
        ↓ adapter (wrapper — IMP-owned)
Vela OHLCV projection { time ms, ohlcv }
        ↓
@luxalgo/vela renderer (panes, zoom/pan, native studies)
        ↑
IMP semantic markers → drawings / future host overlay layer
```

IMP must own: bar identity, monotonic `source_time_ns`, marker semantics, Paper/opportunity/catalyst **meaning**. Vela owns: pixels, interaction, native indicator math, volume pane.

## Prototype evidence (`ui/spikes/vela-cockpit`)

| Capability | Status | Notes |
|------------|--------|-------|
| Candlesticks | **Proven** | Offline `data` array, dark theme |
| Incremental update | **Proven (thin)** | Governed synthetic ticks → `setMarket({ bars })` |
| History backfill | **Proven (thin)** | Prepend 50 bars + `setMarket` |
| Volume pane | **Proven** | Native volume auto-attached |
| Indicators | **Partial** | Native SMA + RSI only; no Pine; limited catalog vs workspace |
| Multi-pane / workspace grid | **Not prototyped** | Headless `Vela` only; `VelaWorkspace` deferred |
| IMP semantic markers | **Partial** | opportunity/catalyst/options/paper/stop/target → `drawings` API (callout/hline/text) |
| Zoom / pan | **Proven** | Built-in interaction (not automated in spike) |
| Resize | **Proven** | `ResizeObserver` → `chart.resize()` |
| Mobile / touch | **Partial** | Responsive shell + `viewport-fit`; chart `touch-action: none` |
| Dark IMP chrome | **Partial** | Host CSS tokens on container; Vela internal theme separate |
| Density | **Partial** | `renderer.set({ barSpacing })` toggle |
| Lazy-load | **Proven** | `import('@luxalgo/vela')` → separate Vite chunk |
| Bundle impact | **Measured** | See below |

**Honest gaps:** no round-trip `bar_id` on chart; markers are drawings not typed IMP events; no React bridge; no governed replay scrubber wiring; incremental path not using a custom `MarketDataFeed` port (reloads series); multi-chart sync not evaluated.

## Measurements (2026-09-14, Windows, Vite 5.4 production build)

| Metric | Vela spike (lazy chunk) | IMP today (`lightweight-charts` prod mjs) |
|--------|-------------------------|-------------------------------------------|
| JS gzip (chart lib) | **~245 KiB** (`vela-*.js`) | **~48 KiB** |
| Spike app shell gzip | ~3.4 KiB | — |
| Spike total JS gzip | **~248 KiB** (2 chunks) | — |
| Lazy-load fetch | Dynamic `import()` splits Vela from shell | LWC bundled in main graph today |
| IMP main budget | **203 KiB** initial gzip (`check-bundle-budget.mjs`) | Vela **cannot** ship eager on critical path |

Lazy-load keeps Vela off the workspace first paint **if** route-level code-splitting is enforced and no static imports leak into `App.tsx` entry graph.

## Comparison to `lightweight-charts` (current workspace)

| Dimension | LWC (current) | Vela |
|-----------|---------------|------|
| License | Apache-2.0 | Apache-2.0 (core) |
| Size | Smaller | ~5× gzip vs LWC module |
| Features | Minimal candles + scrub | Panes, drawings, native studies, plugin SDK |
| IMP integration maturity | Shipped in `WorkspaceObservability` | Spike only |
| Marker / annotation model | Custom (limited) | Rich drawings; IMP semantics need wrapper |

## Decision rationale

**`ADOPT_WITH_WRAPPER`** — not bare `ADOPT`, not `REJECT`.

- **Adopt** the Apache-2.0 **headless core** as an optional, lazy-loaded chart engine for advanced workspace / cockpit surfaces.
- **Wrapper required** for IMP bar identity, governed feed adapter, semantic marker layer, React lifecycle, bundle budget, and attribution policy.
- **Reject** adding `@luxalgo/vela-pinets` / `pinets` to IMP core without a separate AGPL compliance track.
- **Do not** eagerly bundle Vela on routes that only need simple replay scrub (keep LWC or a thinner path until budget allows).

### Alternatives considered

| Enum | Why not |
|------|---------|
| `ADOPT` (direct) | Bundle + IMP semantics gap too large without wrapper |
| `LIMITED_USE` | Understates value — viable for lazy advanced chart lane |
| `REJECT` | Capabilities (panes, native volume, drawings) materially exceed LWC for workstation roadmap |

## Recommended next steps (out of spike scope)

1. `ImpVelaChartAdapter` module: `ImpBarRecord` ↔ Vela bars + `MarketDataFeed` incremental port (avoid full `setMarket` reload).
2. Lazy route `/dev/vela-cockpit` behind operator flag (not production nav).
3. Marker policy doc: drawings vs custom renderer layer for Paper stop/target.
4. Evaluate `VelaWorkspace` in a second spike if multi-grid is on roadmap.
5. Legal review if attribution removal or Pine indicators are ever requested.

## Spike commands

```powershell
cd projects/integrated-market-platform/ui/spikes/vela-cockpit
npm install
npm run dev
npm run measure
```
