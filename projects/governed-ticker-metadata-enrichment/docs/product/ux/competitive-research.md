# Competitive & Interaction Research

**Status:** `PROPOSED`  
**Method:** Official documentation, product pages, and publicly available interface descriptions. No product cloning. Facts distinguished from design inference.

## Summary synthesis

| Adopt (modified) | Avoid |
|---|---|
| Synchronized multi-instrument context (TradingView linking) | Blank-first dashboard (OpenBB without defaults) |
| Widget/group parameter sync (OpenBB) | Provider-coupled AI (GridIQ/Gemini pattern) |
| Dense flow tables with explainable filters (Unusual Whales) | Emoji/sentiment shorthand without provenance |
| Heatmap + volume decomposition (Bookmap) | "Hidden intent" marketing language |
| Screener → watchlist → deep-dive pipeline (Koyfin) | Universal buy/sentiment scores |
| Saved layout templates (TradingView, Koyfin) | Treating layout customization as first-run requirement |
| Replay/time sync across panels (Bookmap, TradingView) | Full feature parity on mobile for DOM/heatmap |

---

## TradingView

**Sources:**
- [Layout options blog (May 2025)](https://www.tradingview.com/blog/en/more-chart-layout-options-52228/)
- [Layouts support doc](https://www.tradingview.com/support/solutions/43000692404-layouts-charts-drawings-indicators-and-their-interaction/)
- [Features page](https://www.tradingview.com/features/)
- [Desktop tab sync (2025)](https://www.tradingview.com/blog/en/tradingview-desktop-updated-new-tab-and-sync-58473/)

### Facts observed
- Layouts save chart workspaces (1–16 charts by tier); watchlists and alerts are separate.
- Multi-chart sync dimensions: symbol, interval, time, date range, crosshair, drawings.
- Watchlist sidebar is persistent; screeners, news, calendars available as separate products.
- Alert system supports multi-condition combinations across price, indicators, drawings.

### Useful concepts (inference)
- **Linked context groups** — color-tagged tabs syncing time + symbol is directly applicable to ES/NQ/SPY comparison and replay.
- **Layout as workflow** — distinct saved layouts per task (scanning vs deep analysis) matches our default workspace strategy.
- **Separation of attention tools** — watchlists/alerts exist everywhere but don't dominate chart area.

### Weaknesses
- Easy to build chart walls with no explanation hierarchy.
- Drawing/indicator sync complexity can confuse novices.
- No native epistemic layering — indicators treated uniformly.

---

## Bookmap

**Sources:**
- [Features](https://bookmap.com/features/)
- [DOM visualization blog](https://bookmap.com/blog/navigating-the-visual-landscape-of-depth-of-market-dom)
- [Main chart KB](https://bookmap.com/knowledgebase/docs/KB-SettingUpAndOperating-HeatmapMainChart)
- [Volume visualization KB](https://bookmap.com/knowledgebase/docs/KB-SettingUpAndOperating-HeatmapTradedVolumeVisualization)

### Facts observed
- Single view combines heatmap, volume dots, volume bars, BBO, last price.
- Components toggle via visible-components menu.
- Volume bar clustering modes: Smart, Volume, Time, Aggregation by Price.
- BBO display modes trade precision vs clutter; auto-hide when zoomed out.
- DOM Pro add-on provides price ladder + execution.

### Useful concepts
- **Composable density** — users enable/disable layers rather than receiving fixed wall.
- **Clustering controls** — aggregation policy is explicit (relevant to tick batching UX).
- **Fullscreen/maximize** for microstructure workspace.

### Weaknesses
- Steep learning curve; heatmap intensity can overwhelm without salience hierarchy.
- Marketing language implies "hidden intent" — conflicts with our epistemic model.
- Real-time focus; replay/historical knowability less prominent in UX.

---

## OpenBB Workspace

**Sources:**
- [Dashboards docs](https://docs.openbb.co/workspace/analysts/dashboards)
- [Widgets.json reference](https://docs.openbb.co/workspace/developers/json-specs/widgets-json-reference)
- [Apps.json reference](https://docs.openbb.co/workspace/developers/json-specs/apps-json-reference)
- [Workspace MCP tools](https://docs.openbb.co/agents/workspace-mcp-tools)

### Facts observed
- 40-column grid layout; widgets draggable/resizable.
- Parameter `groups` synchronize ticker/date across widgets.
- `apps.json` defines tabs, layouts, suggested AI prompts with widget references.
- Agent integration reads workspace snapshot for dashboard context.

### Useful concepts
- **Parameter groups** — maps to our linked workspace sync dimensions.
- **AI grounded in visible widgets** — precedent for contextual sidecar (not silo chat).
- **apps.json as shareable workspace artifact** — maps to export/share research bundles.

### Weaknesses
- Blank dashboard first-run can intimidate.
- Widget proliferation risks dashboard sprawl without attention hierarchy.
- Financial terminal density without mandatory quality/provenance layer.

---

## Koyfin

**Sources:**
- [My Dashboards help](https://www.koyfin.com/help/mydashboards-myd/)
- [Stock screener feature](https://www.koyfin.com/features/stock-screener/)
- [LLM info page](https://www.koyfin.com/llm-info/)

### Facts observed
- Custom dashboards from widget templates or blank.
- Table/watchlist widgets support saved column templates.
- Screener: 500+ metrics, save results to watchlist, use across platform.
- Drag ticker from sidebar to analyze.

### Useful concepts
- **Screener → watchlist → instrument pipeline** — matches EXPLORE → WORKSPACE flow.
- **Column templates** — power user customization with sensible defaults.
- **Macro + equity bundled dashboards** — precedent for regime context on NOW page.

### Weaknesses
- Research/fundamental bias; weak order-flow/DOM native patterns.
- Dashboard-centric; less emphasis on state-transition alerts.

---

## Unusual Whales

**Sources:**
- [Options flow docs](https://docs.unusualwhales.com/features/2-options-flow/)
- [Flow FAQ](https://docs.unusualwhales.com/faq/items/4-flow/)
- [Product page](https://unusualwhales.com/)

### Facts observed
- Real-time flow table with customizable/reorderable columns.
- Filters for premium, DTE, ticker, trade type; pause live feed.
- Flow status indicator (green/yellow/red) based on active filters.
- Side determination explained (bid/ask proximity heuristic).
- "Mr. Whale" AI companion for market questions.
- Super Flow: modular multi-window dashboard.

### Useful concepts
- **Explainable filter match** — user knows why row appears (maps to screener "Why matched?").
- **Pause live feed** — attention protection during inspection.
- **In-window drill-down** without navigation loss.

### Weaknesses
- Emoji/sentiment shorthand can obscure methodology.
- "Institutional grade" marketing without provenance chain in UI.
- AI companion risks becoming siloed authority (Mr. Whale branding).

---

## Additional reference platforms (brief)

| Platform | Relevant pattern | Caution |
|---|---|---|
| Interactive Brokers TWS | Modular panels, market scanner | Extreme density; poor progressive disclosure |
| thinkorswim | Flexible grids, Study/Strategy separation | Learning curve; indicator ≠ strategy clarity |
| Quantower / Sierra Chart | DOM, footprint, replay | Expert-only; weak mobile |
| Bloomberg Terminal | `HL` help, security context, drill-down | Not replicable; good inspiration for command + context |
| Options analysis (ORATS, etc.) | Chain-centric layouts | Often IV-centric without flow provenance |

---

## HCI & accessibility references

| Source | Application |
|---|---|
| [Shneiderman 1996 — Visual Information Seeking Mantra](https://doi.org/10.1109/vl.1996.545307) | Overview → zoom/filter → details-on-demand |
| [W3C WCAG 2.2](https://www.w3.org/WAI/WCAG22/quickref/) | AA baseline target |
| [IBM Carbon — Data visualization](https://carbondesignsystem.com/data-visualization/overview/) | Accessible chart patterns, color palettes |
| [Google PAIR — People + AI Guidebook](https://pair.withgoogle.com/guidebook/) | Human-AI interaction, explanation, uncertainty |
| [Microsoft HAX Toolkit](https://www.microsoft.com/en-us/haxtoolkit/) | AI capability/limitation disclosure |

**Design inference:** Generic SaaS dashboard patterns (card grids, KPI walls) are insufficient for real-time financial interfaces. Prefer task-specific workspaces with explicit mode and quality context over decorative metric cards.
