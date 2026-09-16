# Components & Styles Inventory

Audit scope: every component under `ui/src`, the full styling architecture (global CSS, tokens,
typography), a coverage map against the redesign primitive list, a concrete CSS/layout
horizontal-overflow risk audit, and a consistency review of loading / error / empty / degraded
state patterns.

- Codebase: `ui/` (React 18 + TypeScript, Vite 5, react-router-dom v6, TanStack Query 5).
  Read-only audit of branch `ui/operator-redesign-v2` worktree.
- Entry: `ui/src/main.tsx` → `ui/src/App.tsx`. All 26 CSS files are loaded globally:
  25 via static imports in `App.tsx:29-52`, plus `styles/imp-vela-chart-lab.css` imported by the
  lazy lab page at `ui/src/components/charts/ImpVelaChartLabPage.tsx:10`.
- Counts: **157 non-test TSX modules** (154 under `ui/src/components/`, 2 under `ui/src/auth/`,
  plus `App.tsx`) exporting **~185 named components**; **26 global CSS files** (~5,000 lines);
  **23 CSS custom properties** defined in `styles/tokens.css`; **9 var() names referenced but
  never defined**; **2 JS chart-token modules** duplicating palette values.
- No Tailwind, no CSS Modules, no CSS-in-JS. Exactly **2 inline `style={{}}` usages** in the
  entire UI (both progress-bar widths: `components/paper-now/PaperRiskRibbon.tsx:20`,
  `components/demo-now/DemoReplayOverview.tsx:76`).
- Headline finding: the app relies on a large set of "phantom" base classes — `.panel`, `.page`,
  `.muted`, `.metric-list`, `.quality-banner`, `.panel-header`, `.panel-actions`, `.status-grid`,
  `.instrument-selector*`, `.tone-*` and ~60 more — that have **zero CSS rules** anywhere in
  `ui/src/styles`. Verified by exhaustive grep of the styles directory (only scoped hits:
  `.settings-page .panel` at `layout.css:1098`, `.paper-order-history-pagination .muted` at
  `shared-ui.css:136`). Large surfaces (portfolio panels, order ticket, provider diagnostics, live
  canary, lane panels) render with browser-default `<dl>`/`<section>` chrome.

---

## Styling architecture

### Layers

| Layer | Files | How loaded | Notes |
|---|---|---|---|
| Design tokens | `ui/src/styles/tokens.css` (25 lines) | `App.tsx:29` | Single `:root` block; the only token file. |
| Base/layout + legacy page styles | `ui/src/styles/layout.css` (~1,680 lines) | `App.tsx:30` | Reset, shell grid, nav, context bar, drawers, assistant, explore/squeeze/research/portfolio/discover shared classes. Largest file; mixes base + page concerns. |
| Shared primitives | `ui/src/styles/shared-ui.css` (144 lines) | `App.tsx:50` | `.empty-state`, `.page-header`, `.json-detail-*`, order-history pagination. |
| IMP product chrome | `ui/src/styles/imp-product.css` (881 lines) | `App.tsx:52` | Sidebar shell, top bar, command search, KPI strip, opportunity cards, radar dense table, capability strip, shortcuts dialog. |
| Mode session (launcher/auth/transition) | `ui/src/styles/mode-session.css` (452 lines) | `App.tsx:31` | Own `--mode-*` token scope (`.mode-session`, lines 1-12). |
| Operator control center | `ui/src/styles/operator-control.css` (240 lines) | `App.tsx:51` | Blue-accented operator panels. |
| Workspace module shell | `ui/src/styles/workspace-module-mode.css` (154 lines) | `App.tsx:49` | Lane-mode panels, module nav headers. |
| Per-mode page themes | 18 files: `{demo,paper,live}-{now,portfolio,workspace,explore,research,discover}.css` | `App.tsx:32-48` | Each redeclares page-scoped vars (`--demo-accent`, `--paper-accent`, `--live-accent`, `--*-line`). demo-* files ~29 lines each; paper-now 97; live-now 275; paper-portfolio 222. |
| Chart lab | `ui/src/styles/imp-vela-chart-lab.css` (51 lines) | lazy via `ImpVelaChartLabPage.tsx:10` | Only non-`App.tsx` CSS import. |
| JS chart tokens | `ui/src/components/charts/chartTheme.ts`, `ui/src/components/charts/impVelaTheme.ts` | imported by chart components | Hardcoded hex duplicates of the CSS palette (details below). |

### Architecture observations

1. **Everything is global.** All selectors are bare classes (`.paper-panel`, `.data-table`),
   page-scoped only by convention (`.demo-now-page …`). No modules, no layering (`@layer`), no
   naming discipline (BEM only in `paper-strategy-profitability__*`). Specificity collisions are
   handled by import order in `App.tsx:29-52`.
2. **Phantom base classes** (used in JSX, zero CSS rules — verified by grep over
   `ui/src/styles`): `.panel`, `.page`, `.muted`, `.metric-list`, `.quality-banner`,
   `.panel-header`, `.panel-actions`, `.symbol`, `.mono`, `.compact`, `.error`, `.hint`,
   `.loading`, `.tone-neutral/positive/negative/muted`, `.status-grid`, `.control-section`,
   `.live-canary-control-plane`, `.live-safety-header`, `.live-banner-critical`, `.live-mode-row`,
   `.mode-label`, `.mode-separator`, `.live-observability-boundary`, `.health-matrix-table`,
   `.instrument-selector` (+`-label/-input/-results/-primary/-meta/-reason`), `.is-active`,
   `.trade-review-learning-panel`, `.live-health-summary`, `.live-actions`, `.portfolio-provenance`,
   `.unified-workstation`, `.demo-signals-desk` / `.paper-signals-desk` / `.live-signals-desk`,
   `.auth-repair-hint`, `.session-history-panel`, `.account-panel`, `.pnl-panel`, `.exposure-panel`,
   `.risk-panel`, `.positions-panel`, `.orders-panel`, `.fills-panel`, `.data-health-panel`,
   `.paper-order-metrics-panel`, `.paper-order-history-panel`, `.paper-order-row`,
   `.paper-order-details-row`, `.paper-order-type`, `.paper-order-fill`, `.paper-order-source-detail`,
   `.paper-order-expand-cell`, `.paper-forward-test-panel` (+`-mode-badge/-summary/-list/-item*`),
   `.paper-cockpit-note`, `.paper-cockpit-source-hint`, `.paper-handoff-current-context`,
   `.workspace-lane-evidence`, `.lane-mode-provenance`, `.lane-mode-empty-note`,
   `.lane-mode-stale-note`, `.lane-mode-paper-draft`, `.emphasis-*`, `.lane-live-blocked`,
   `.workspace-warning`, `.order-ticket-symbol`, `.paper-position-panel`, `.paper-derivative-preview`,
   `.options-panel`, `.options-research-blocks`, `.options-product-surface`, `.order-flow-panel`,
   `.order-book-panel`, `.futures-panel`, `.futures-product-surface`, `.catalyst-panel`,
   `.disclosure-panel`, `.fund-etf-panel`, `.large-transactions-panel`, `.institutional-flow-panel`,
   `.institutional-family-detail`, `.model-lab-panel`, `.simulation-lab-panel`,
   `.squeeze-catalyst-block/-grid/-note`, `.squeeze-causal-block/-grid/-summary`,
   `.squeeze-mechanisms`, `.squeeze-missing-capabilities`, `.squeeze-horizons-note`,
   `.squeeze-freshness`, `.squeeze-transition-count`, `.squeeze-confidence`, `.state-transition-note`,
   `.transition-hysteresis`, `.outcome-*`, `.cross-lane-evidence-list/-item/-header/-detail/-meta`,
   `.cross-lane-lane`, `.historical-squeeze-context`, `.historical-cohort-meta`,
   `.historical-case-grid`, `.historical-policy-meta`, `.dealer-positioning-block`,
   `.dealer-disclaimer`, `.dealer-quality`, `.strategy-optimizer-block`, `.strategy-disclaimer`,
   `.strategy-outcome`, `.strategy-quality`, `.strategy-replay-hash`, `.execution-simulation-block`,
   `.execution-disclaimer`, `.execution-outcome`, `.execution-quality`, `.execution-replay-hash`,
   `.opportunity-fusion-block`, `.opportunity-components-grid`, `.opportunity-component-panel`,
   `.opportunity-outcome`, `.opportunity-disclaimer`, `.opportunity-replay-hash`,
   `.assistant-history-page`, `.gated-page` (only in compound at `layout.css:257`).
   Representative JSX usage: `OrderTicket.tsx:200` (`panel order-ticket-panel`),
   `PaperPortfolioObservability.tsx:14-22` (`panel account-panel`), `ProviderHealthPanel.tsx:33`
   (`metric-list`), `LiveCanaryControlPlanePage.tsx:58,87,167` (`control-section`, `status-grid`,
   `health-matrix-table`), `CanonicalInstrumentSelector.tsx:44-90` (`instrument-selector-*`),
   `ImpOverviewKpiStrip.tsx:18` (`tone-${tone}`).
3. **Referenced-but-undefined CSS variables** (resolve to fallback or invalid-at-computed-value):
   - `--surface-elevated` — `layout.css:354` (has fallback), `layout.css:862` (**no fallback** →
     `.research-tabs button` background becomes transparent), `layout.css:881` (**no fallback** →
     `.simulation-banner` left accent border drops), `layout.css:963` (**no fallback** →
     `.execution-trace-panel` background transparent), `layout.css:1203` (has fallback).
   - `--accent` — `layout.css:870` (`.research-tabs button.active` border-color → currentColor),
     `layout.css:888` (`.link-button` color → inherited, not accent), `layout.css:1042`
     (`.what-matters-table .link-button`), `layout.css:1213` (`.discover-session` → falls back to
     sky blue `#7dd3fc`).
   - `--radius-sm` — `layout.css:1020, 1089, 1102, 1577`; `imp-product.css:465, 874` (radii → 0).
   - `--radius-lg` — `imp-product.css:350, 488, 829` (radii → 0).
   - `--danger` — `paper-now.css:67, 73`; `live-now.css:174, 177` (all have `#e36d77` fallback).
   - `--muted` — `paper-workspace.css:74` (fallback `#8aa0ad`).
   - `--color-text-muted` / `--color-border` — `imp-vela-chart-lab.css:17, 29, 36` (fallbacks used).
   - `--imp-sidebar-width` — `imp-product.css:2, 669` (fallback `220px`; never actually defined).
4. **Duplicated hardcoded palettes outside tokens.css**:
   - Chart theme JS: `components/charts/chartTheme.ts:1-9` (`#2a3142`, `#9aa3b5`, `#3d9970`,
     `#c44e52`, `#d4a017`, accent **`#5b8def` blue**, series incl. `#7c6df0` purple).
   - Vela host vars: `components/charts/impVelaTheme.ts:5-12` (repeats surface hexes + `#ff6a00`).
   - lightweight-charts instance: `components/charts/WorkspacePriceChart.tsx:49-58` (`#141820`
     background — not any token, `#e8ecf4`, `#2a3142`, `#3d9970`, `#c44e52`).
   - Recharts tooltip chrome: `components/charts/ResearchChartPanels.tsx:54-58, 127-131`
     (`#141820`, `#2a3142`, `#e8ecf4`).
   - Mode environment bar: `mode-session.css:200-283` hardcodes `#0b1b2b`, `#294158`, `#f4f7fb`,
     `#7f94a9`, `#b9c8d8`, `#f6cf87`, `#10243a`, `#52708c`, `#8cc8ff`, `#91a5b9`, `#e0a94b`.
   - Misc one-offs: `.startup-recovery-banner` `#2a3142` (`layout.css:1028-1031`),
     `.evidence-drawer` `#1a1f2b` (`layout.css:1062` — note: **differs from `--surface-2`
     `#1a1f28` by one hex digit**), `.relevance-high` `#3dd68c` / `.relevance-medium` `#e8c547`
     (`layout.css:1046-1052`), `.context-segment.mode-live strong` `#3dd68c` (`layout.css:1024`),
     `.lane-decision-hint-supports` `#8fd48f` / `-contradicts` `#f0a070`
     (`workspace-module-mode.css:125-131`), `.paper-cockpit-warning` `#f0b35a`
     (`paper-workspace.css:82`), handoff blue `#7eb8ff` (`paper-workspace.css:135-139, 158-160`),
     assistant blue `rgba(96,165,250,0.35)` (`layout.css:111`), module-nav active inset
     `rgba(91,141,239,0.35)` (`layout.css:751`), operator blue `rgba(91,141,239,*)`
     (`operator-control.css:26-29, 34, 228`), operator status text `#7dd3a8` / `#f2ca59` /
     `#f58d91` (`operator-control.css:105-124`), order status `#9fd4ff` / `#8fd9a8` / `#f0a6a6`
     (`paper-portfolio.css:111-124`), provenance teal `#8ce7da` (`paper-portfolio.css:91`).
5. **No global overflow guard.** `html, body, #root` (`layout.css:7-14`) set no
   `overflow-x: clip/hidden`; page-level overflow is only prevented ad hoc.
6. **z-index scale is ad hoc** but consistent: assistant toggle 20 (`layout.css:41`), drawer &
   inspector 20 (`layout.css:409`), evidence drawer 40 (`layout.css:1064`), sidebar backdrop 40 /
   sidebar 50 (`imp-product.css:649, 664`), shortcuts layer 70 (`imp-product.css:956`), skip link
   80 (`imp-product.css:83`), mode dialog 100 (`mode-session.css:385`).
7. **Accessibility media queries present but partial**: `prefers-reduced-motion` in
   `mode-session.css:496`, `demo-now.css:330`, `paper-now.css:100`, `live-now.css:301`,
   `imp-product.css:1021`, `operator-control.css:276`; `forced-colors` in `mode-session.css:511`,
   `demo-now.css:336`, `paper-now.css:104`, `live-now.css:307`. 44px min touch targets enforced in
   `mode-session.css:52-54`, `demo-now.css:181-190`, `paper-now.css:77-79`, `live-now.css:213-222`.

---

## Design tokens found

### `styles/tokens.css` (`:root`, lines 1-25) — the complete token set

| Token | Value | Role |
|---|---|---|
| `--surface-0` | `#0c0e12` | App background |
| `--surface-1` | `#13161c` | Panel/card background |
| `--surface-2` | `#1a1f28` | Raised surface / buttons |
| `--surface-3` | `#10141a` | Sidebar gradient base |
| `--border-subtle` | `#2c323c` | Default border |
| `--border-focus` | `#ff7a1a` | Focus/active border (orange) |
| `--accent-primary` | `#ff6a00` | IMP orange accent |
| `--accent-primary-bright` | `#ff8a00` | Bright orange (active nav, links) |
| `--accent-glow` | `rgba(255, 106, 0, 0.22)` | Orange glow |
| `--text-primary` | `#e8ecf4` | Primary text |
| `--text-secondary` | `#9aa3b5` | Secondary text |
| `--text-muted` | `#6b7280` | Muted text |
| `--direction-long` | `#3d9970` | Long/positive/healthy green |
| `--direction-short` | `#c44e52` | Short/negative/fail red |
| `--warning` | `#d4a017` | Warning amber |
| `--replay-bg` | `rgba(212, 160, 23, 0.08)` | Context-bar amber tint |
| `--font-ui` | `"Inter", system-ui, -apple-system, sans-serif` | Sans stack |
| `--font-mono` | `"JetBrains Mono", ui-monospace, monospace` | Mono stack |
| `--radius-md` | `6px` | Only radius token |
| `--inspector-width` | `360px` | Inspector panel width |
| `--drawer-width` | `360px` | Drawer width |
| `--context-bar-height` | `40px` | Context bar height |
| `--nav-height` | `44px` | Legacy top-nav height |

### Page-scoped mode palettes (NOT in tokens.css)

| Scope | Vars | Values |
|---|---|---|
| `.mode-session` (`mode-session.css:1-12`) | `--mode-bg/panel/panel-raised/line/text/secondary/muted` | `#0a0c10`, `#12161c`, `#1a1f28`, `#2c323c`, `#f0f2f6`, `#b4bcc8`, `#7a8494` |
| | `--mode-demo` / `--mode-paper` / `--mode-live` / `--mode-focus` | `#9aa8b8` slate / `#56c596` green / `#ff8a00` orange / `#ff8a00` |
| `.demo-now-page` (`demo-now.css:1-6`) | `--demo-accent`, `--demo-panel`, `--demo-panel-strong`, `--demo-line` | `#67d8f4` cyan, `rgba(18,26,38,.94)`, `rgba(21,34,49,.98)`, `rgba(128,161,188,.2)` |
| `.paper-now-page` (`paper-now.css:1-5`) | `--paper-accent`, `--paper-accent-soft`, `--paper-line`, `--paper-panel` | `#48d6c4` teal, `rgba(72,214,196,.12)`, `rgba(131,168,188,.24)`, `rgba(15,23,33,.94)` |
| `.live-now-page` (`live-now.css:1-5`) | `--live-accent`, `--live-accent-soft`, `--live-line`, `--live-panel` | `#f0b45c` amber, `rgba(240,180,92,.12)`, `rgba(188,156,112,.24)`, `rgba(24,20,14,.94)` |
| `.paper-portfolio-page` / `.paper-workspace-page` | `--paper-accent`, `--paper-line` | same teal (`paper-portfolio.css:1-4`, `paper-workspace.css:1-4`) |
| paper explore/discover/research headers | hardcoded border | `rgba(92, 196, 138, 0.25)` green (`paper-explore.css:12` etc.) + `--paper-accent` fallback `#5cc48a` (`paper-explore.css:33`) |
| live explore/discover/research headers | hardcoded border | `rgba(245, 166, 35, 0.25)` orange (`live-explore.css:12` etc.) |
| `.live-portfolio-page` / `.live-workspace-page` | `--live-accent`, `--live-line` | same amber (`live-portfolio.css:1-4`, `live-workspace.css:1-4`) |
| `.demo-workspace-page` etc. | `--demo-accent`, `--demo-line` | same cyan (`demo-workspace.css:1-4`) |

### Mode-color conflicts with the planned redesign semantics

| Mode | Planned (redesign brief) | Current launcher (`mode-session.css:9-11`) | Current pages |
|---|---|---|---|
| Live observation | green/teal | `#ff8a00` orange | `#f0b45c` amber |
| Paper/simulation | IMP orange | `#56c596` green | `#48d6c4` teal (+green `#5cc48a` accents) |
| Replay (Demo) | purple | `#9aa8b8` slate | `#67d8f4` cyan; replay tint amber `rgba(212,160,23,0.08)` |
| Research | blue/slate | — | blue accents scattered (`#5b8def` charts, `#7eb8ff` handoff, `rgba(91,141,239,*)` operator) |
| Degraded | amber | — | `--warning #d4a017` + `#f0b35a` + `#e1b85b` + `#f2ca59` (4 ambers) |
| Blocked/failure | red | — | `--direction-short #c44e52` + `#e36d77` + `#f0a6a6` + `#f58d91` + `rgba(180,90,90,*)` (5 reds) |

### Spacing / radii / sizing conventions

- No spacing scale tokens. Gaps/paddings are ad hoc: `4/6/8/10/12/14/16/18/24px` and rem
  equivalents; page gutters `padding: 16px` on `.main-content` (`layout.css:237-239`).
- Radii: only `--radius-md: 6px` defined; `--radius-sm`/`--radius-lg` referenced but undefined
  (see above); hardcoded radii `2px` (pills, `layout.css:1424`), `3px` (`mode-session.css:272`),
  `4px` (`mode-session.css:122`), `5px` (`paper-now.css:79`), `7px` (`demo-now.css:245`), `9px`
  (`paper-now.css:40`), `10px` (`demo-now.css:85`), `999px` pills.
- Page max-widths: `1540px` (demo pages), `1580px` (paper/live now+portfolio+workspace),
  `1600px` (`.discover-page`, `layout.css:1104-1109`), `1440px` (`.operator-control-center`,
  `operator-control.css:1-4`).
- Fixed structural widths: sidebar `220px` (`imp-product.css:2`), drawer/inspector `360px`
  (tokens), evidence drawer `min(420px, 100%)` (`layout.css:1060`).

---

## Typography

- **Families**: `--font-ui: "Inter", system-ui, -apple-system, sans-serif` and
  `--font-mono: "JetBrains Mono", ui-monospace, monospace` (`tokens.css:19-20`). **Neither font is
  loaded**: `ui/index.html:1-11` has no `<link>`/`@font-face`, and a codebase grep for
  `@font-face`/`fonts.googleapis`/`fontsource`/`*.woff` returns nothing. Inter/JetBrains Mono only
  render when installed locally; otherwise the app falls back to system sans / ui-monospace.
- **Non-standard weights** `680` (`mode-session.css:89`) and `750` (`mode-session.css:377`,
  `demo-now.css:196`) require a variable font; with system fallback they are ignored.
- **No type scale tokens.** Sizes are ad hoc per component. Display H1s use fluid clamps:
  mode launcher `clamp(2.35rem, 6vw, 5.4rem)` (`mode-session.css:88-91`), demo-now
  `clamp(2rem, 4vw, 3.65rem)` (`demo-now.css:24-28`), paper/live-now `clamp(2rem, 4vw, 3.4rem)`
  (`paper-now.css:22`, `live-now.css:23-27`), workspace/portfolio headers `clamp(2rem, 4vw, 3.2rem)`
  (e.g. `paper-portfolio.css:20-23`), discover + workspace-module headers
  `clamp(1.65rem, 3vw, 2.35rem)` (`layout.css:1122-1126`, `workspace-module-mode.css:31-37`).
  Body text `0.78–0.95rem`; micro labels `0.62–0.72rem`; dense tables `0.72–0.85rem`.
- **Where mono is used** (all `var(--font-mono)` unless noted): market values & metric `dd`s
  (`paper-now.css:28`, `live-now.css:70-73`, `demo-now.css:230-234`), identifiers in `<code>`
  (reason codes `layout.css:313-315`), raw JSON (`layout.css:449-451`, `shared-ui.css:121-124`),
  eyebrow/label microcopy (`.demo-eyebrow` `demo-now.css:38-45`, `.paper-eyebrow`
  `paper-now.css:24`, `.live-eyebrow` `live-now.css:36-41`, `.imp-section-eyebrow`
  `imp-product.css:284-290`, `.discover-eyebrow` `layout.css:1128-1134`, `.lane-mode-eyebrow`
  `workspace-module-mode.css:93-99`, `.operator-panel-kicker` `operator-control.css:47-54`),
  nav mode hints (`layout.css:198-205`), sidebar footer (`imp-product.css:186-194`), KPI labels
  (`imp-product.css:326-332`), posture lock/account (`imp-product.css:145-154, 696-702`),
  provider-state dots text (`layout.css:1256-1262`), discover queue numbers/symbols/scores
  (`layout.css:1370-1411`), badges/pills (`paper-portfolio.css:79-87, 104-110`),
  `kbd` (`imp-product.css:1015-1019`), mode launcher card index/descriptor/action
  (`mode-session.css:151-157, 167-174, 190-194`), environment bar identity
  (`mode-session.css:233-247`), big operator status (`operator-control.css:71-76`).
  Note: mono is used heavily for **UI labels/eyebrows**, not just market values/identifiers/
  timestamps/raw evidence as the redesign doctrine reserves it for — a deliberate decision needed.
- `.mono` utility class is used in JSX (`research/ModelLabPanel.tsx:32, 36`) but **has no CSS
  rule** — those hashes render in sans.

---

## Component inventory

"Generic" = reusable primitive/shared building block; "Page" = page- or mode-specific;
"Lane" = workspace-lane module; "Shell" = app chrome/routing. Files under `ui/src/components/`
unless noted. Internal (non-exported) subcomponents are indented under their parent.

### Shell / chrome / routing

| Component | File | Purpose | Used by | Type |
|---|---|---|---|---|
| `App` / `WorkstationShell` / `StartupRecoveryBanner` | `ui/src/App.tsx:186, 158, 590` | Root providers, route table, drawer/inspector/assistant orchestration, crash-recovery banner | all pages | Shell |
| `ImpProductChrome` | `imp-product/ImpProductChrome.tsx:26` | App shell: sidebar nav, top bar (search, posture, shortcuts, switch mode), mobile nav w/ focus trap, keyboard shortcuts | `WorkstationShell` | Shell (generic) |
| `NavShell` (+`NavItem`) | `NavShell.tsx:139, 115` | Primary + operator nav links with per-mode hints and GATED badge | `ImpProductChrome` | Shell (generic) |
| `ImpBullMark` | `imp-product/ImpBullMark.tsx:6` | Inline SVG brand mark (orange gradient bull) | `ImpProductChrome` | Shell |
| `ImpCommandSearch` | `imp-product/ImpCommandSearch.tsx:12` | Top-bar search; ticker pattern → workspace, else explore | `ImpProductChrome` | Generic |
| `ImpExecutionPosture` | `imp-product/ImpExecutionPosture.tsx:14` | Mode copy + paper account id + "Live off" pill | `ImpProductChrome` | Shell |
| `ImpKeyboardShortcuts` | `imp-product/ImpKeyboardShortcuts.tsx:17` | Shortcuts modal (focus-trapped) | `ImpProductChrome` | Generic |
| `ModeEnvironmentBar` | `mode-session/ModeEnvironmentBar.tsx:17` | Session environment banner (mode, boundary, backend alignment) | `WorkstationShell` (`App.tsx:357`) | Shell |
| `ContextBar` | `ContextBar.tsx:26` | Data/execution/auth/as-of/scope/quality strip | `WorkstationShell` (`App.tsx:364`) | Shell |
| `ImpContextTrustLayer` | `imp-product/ImpContextTrustLayer.tsx:10` | Composes capability strip + provider matrix drawer | `WorkstationShell` (`App.tsx:369`) | Shell |
| `ImpCapabilityStrip` | `imp-product/ImpCapabilityStrip.tsx:8` | Capability chips row (ok/warn/blocked tones) | `ImpContextTrustLayer` | Generic |
| `ImpProviderMatrixDrawer` | `imp-product/ImpProviderMatrixDrawer.tsx:12` | Read-only provider/capability/readiness drawer | `ImpContextTrustLayer` | Generic |
| `LazyBoundary` | `LazyBoundary.tsx:9` | Suspense wrapper with `LoadingState` fallback | `App.tsx` routes | Generic |
| `ModeNowRoute` (+3 internal route fns) | `ModeNowRoute.tsx:89` | Mode → Now page dispatch + data wiring | `App.tsx:347-348` | Shell |
| `ModeExploreRoute` / `ModeDiscoverRoute` / `ModePortfolioRoute` / `ModeResearchRoute` | `ModeExploreRoute.tsx:25`, `ModeDiscoverRoute.tsx:25`, `ModePortfolioRoute.tsx:44`, `ModeResearchRoute.tsx:36` | Mode → page dispatch (research adds nested `/research/vela-chart-lab` route) | `App.tsx` | Shell |
| `WorkspaceRoute` | `WorkspaceRoute.tsx:21` | Symbol param decode, instrument/squeeze queries, draft handoff | `App.tsx:407` | Shell |
| `ModeWorkspacePage` | `ModeWorkspacePage.tsx:28` | Mode → workspace page dispatch | `WorkspaceRoute` | Shell |
| `WorkspaceIndex` | `WorkspaceIndex.tsx:8` | `/workspace` redirect logic | `App.tsx:403` | Shell |
| `WorkspaceModuleNav` | `WorkspaceModuleNav.tsx:17` | Sticky 11-item lane nav from `WORKSPACE_LANE_REGISTRY` | workspace pages + module shells | Generic |
| `WorkspaceModuleModeShell` (+3 mode headers + `ModeRestrictionNote`) | `workspace-module-shared/WorkspaceModuleModeShell.tsx:144` | Shared lane-module page frame (header, nav, restriction note) | all 10 `Mode*WorkspaceRoute` | Generic |
| `ModeAwareWorkspaceLane` | `workspace-module-shared/ModeAwareWorkspaceLane.tsx:19` | Lane frame: context panel + live strip + evidence | all lane observability components | Generic |
| `LaneModeContextPanel` | `workspace-module-shared/LaneModeContextPanel.tsx:31` | Mode-aware lane summary/limitations/draft CTA | `ModeAwareWorkspaceLane` | Generic |
| `LiveLaneOperationalStrip` | `workspace-module-shared/LiveLaneOperationalStrip.tsx:10` | Live provider/canary status strip per lane | `ModeAwareWorkspaceLane` (LIVE) | Generic |
| `ExplanationDrawer` | `ExplanationDrawer.tsx:6` | Fixed right drawer for explanation payload | `WorkstationShell` | Generic |
| `InspectorPanel` | `InspectorPanel.tsx:8` | Fixed right tabbed JSON inspector | `WorkstationShell` | Generic |
| `AuthProvider` / `useAuth` / `useOptionalAuth` | `ui/src/auth/AuthProvider.tsx:62` | Session context, role capabilities | `App.tsx:592` | Shell |
| `OperatorLoginGate` | `ui/src/auth/OperatorLoginGate.tsx:4` | Principal/secret login form over mode-session styling | `App.tsx:593` | Shell |

### Mode session (launcher / bootstrap)

| Component | File | Purpose | Used by | Type |
|---|---|---|---|---|
| `ApplicationBootstrap` | `mode-session/ApplicationBootstrap.tsx:21` | Startup readiness → launcher → transition → app | `App.tsx:596` | Shell |
| `ModeLauncher` | `mode-session/ModeLauncher.tsx:12` | 3-card mode picker | `ApplicationBootstrap` | Page |
| `LiveModeConfirmation` | `mode-session/LiveModeConfirmation.tsx:10` | Live-entry confirmation dialog (focus trap) | `ModeLauncher` | Generic (modal) |
| `ModeTransition` | `mode-session/ModeTransition.tsx:15` | Per-mode readiness progress/failure surface | `ApplicationBootstrap` | Page |

### Shared primitives (`components/shared/`)

| Component | File | Purpose | Used by | Type |
|---|---|---|---|---|
| `EmptyState` | `shared/EmptyState.tsx:10` | Title/description/action empty block | only `InstrumentSelectionEmpty` | Generic |
| `LoadingState` | `shared/LoadingState.tsx:6` | `.app-loading` status text | `LazyBoundary`, `WorkspaceRoute`, `ExecutionTracePanel`, `LiveLaneOperationalStrip`, `PaperPortfolioPage`, `PaperOrderHistory`, `PaperStrategyProfitabilityObservability`, `LiveCanaryControlPlanePage`, `WorkspaceIndex` | Generic |
| `PageHeader` | `shared/PageHeader.tsx:13` | Eyebrow/title/subtitle/meta/actions/restriction header | `OperatorControlCenterPage`, `OperatorSettingsPage`, `PaperPortfolioPage` | Generic |
| `JsonDetailPanel` (+`JsonDetailRows`) | `shared/JsonDetailPanel.tsx:33` | Collapsible flattened JSON + raw view | `WorkspaceEvidenceDrawer`, `ExecutionTracePanel`, `ProviderHealthPanel`, `OperatorSettingsPage`, `DiscoverObservability` | Generic |
| `InstrumentSelectionEmpty` | `shared/InstrumentSelectionEmpty.tsx:40` | Mode-aware "select an instrument" empty page w/ selector | `WorkspaceIndex`, lane shells (via buildLaneModeContent paths) | Generic |

### Now desks (Overview / Signals)

| Component | File | Purpose | Used by | Type |
|---|---|---|---|---|
| `DemoNowPage` | `demo-now/DemoNowPage.tsx:33` | Demo overview/signals desk | `ModeNowRoute` | Page |
| `DemoReplayOverview` | `demo-now/DemoReplayOverview.tsx:39` | Replay progress + scrub controls | `DemoNowPage` | Page-specific |
| `DemoPortfolioSummary` | `demo-now/DemoPortfolioSummary.tsx:17` | 4-metric simulated portfolio card | `DemoNowPage` | Page-specific |
| `DemoInspectNext` | `demo-now/DemoInspectNext.tsx:20` | Guided 3-step inspect path | `DemoNowPage` | Page-specific |
| `PaperNowPage` | `paper-now/PaperNowPage.tsx:33` | Paper Command desk (queue + composer + exceptions) | `ModeNowRoute` | Page |
| `PaperCandidateQueue` | `paper-now/PaperCandidateQueue.tsx:21` | Radio-selectable attention candidate cards | `PaperNowPage` | Page-specific |
| `PaperPreviewComposer` | `paper-now/PaperPreviewComposer.tsx:33` | Side/quantity draft + preview result | `PaperNowPage` | Page-specific |
| `PaperRiskRibbon` | `paper-now/PaperRiskRibbon.tsx:6` | 5-metric risk ribbon w/ utilization meters | `PaperNowPage` | Generic-ish |
| `PaperExceptionsPanel` | `paper-now/PaperExceptionsPanel.tsx:7` | Severity-coded exception list | `PaperNowPage` | Page-specific |
| `LiveNowPage` | `live-now/LiveNowPage.tsx:29` | Live Watch desk | `ModeNowRoute` | Page |
| `LiveProviderRibbon` | `live-now/LiveProviderRibbon.tsx:8` | 4-metric connection summary | `LiveNowPage` | Generic-ish |
| `LiveSafetySnapshot` | `live-now/LiveSafetySnapshot.tsx:10` | Canary safety grid + alerts | `LiveNowPage` | Page-specific |
| `LiveSymbolLookup` | `live-now/LiveSymbolLookup.tsx:15` | Symbol search + capability list + subscribe | `LiveNowPage` | Page-specific |
| `AttentionFeed` | `AttentionFeed.tsx:13` | Attention cards w/ reason codes + actions | Demo/Paper/Live now pages, `ImpOverviewPrimaryQueue` | Generic |
| `OpportunityReviewCard` / `OpportunityReviewList` | `now/OpportunityReviewCard.tsx:33, 71` | Review-density opportunity card/list over `ProgressiveOpportunityCard` | `ImpOverviewPrimaryQueue`, `PaperCandidateQueue` | Generic |
| `ImpOverviewBoard` | `imp-product/ImpOverviewBoard.tsx:29` | KPI strip + primary queue + body composition | all three Now pages | Generic |
| `ImpOverviewKpiStrip` | `imp-product/ImpOverviewKpiStrip.tsx:8` | KPI card grid (tone classes unstyled) | `ImpOverviewBoard` | Generic |
| `ImpOverviewPrimaryQueue` | `imp-product/ImpOverviewPrimaryQueue.tsx:37` | Ranked/Attention/Both tabbed queue | `ImpOverviewBoard` | Generic |

### Discover (Opportunity Radar)

| Component | File | Purpose | Used by | Type |
|---|---|---|---|---|
| `DemoDiscoverPage` / `PaperDiscoverPage` / `LiveDiscoverPage` | `demo-discover/DemoDiscoverPage.tsx:10`, `paper-discover/PaperDiscoverPage.tsx:10`, `live-discover/LiveDiscoverPage.tsx:10` | Radar page per mode (mutations only in Paper) | `ModeDiscoverRoute` | Page |
| `OpportunityRadarCockpit` | `imp-product/OpportunityRadarCockpit.tsx:20` | Dense table + selected progressive card split | discover pages | Generic |
| `OpportunityRadarDensePanel` | `imp-product/OpportunityRadarDensePanel.tsx:19` | Ranked queue table (scroll-contained) | `OpportunityRadarCockpit` | Generic |
| `ProgressiveOpportunityCard` (+`MetaGrid`, `Section`) | `imp-product/ProgressiveOpportunityCard.tsx:66` | Full progressive-disclosure opportunity card (evidence/verification/contradictions/history/risk/actions) | `OpportunityRadarCockpit`, `OpportunityReviewCard` | Generic |
| `ImpTopOpportunityCards` (+`CompactOpportunityCard`) | `imp-product/ImpTopOpportunityCards.tsx:71, 21` | Compact top-N opportunity cards | (overview surfaces) | Generic |
| `OpportunityFeedStatusBanner` | `imp-product/OpportunityFeedStatusBanner.tsx:16` | Loading/error/UNREADY feed banner | radar + review lists | Generic |
| `OpportunityRadarIntro` | `imp-product/OpportunityRadarIntro.tsx:6` | Radar explainer banner | discover pages | Generic |
| `TradeReviewLearningPanel` | `imp-product/TradeReviewLearningPanel.tsx:8` | Durable trade-review list per opportunity | `ProgressiveOpportunityCard` | Generic |
| `DiscoverObservability` | `discover-shared/DiscoverObservability.tsx:130` | Mixed live screener (raw fetch, polling, refresh/promote mutations) | discover pages | Page-specific |
| `DiscoverRankedQueueSection` / `DiscoverMixedScreenerSection` | `discover-shared/DiscoverPageSections.tsx:8, 22` | Section wrappers w/ eyebrows | discover pages | Generic |

### Explore / Research

| Component | File | Purpose | Used by | Type |
|---|---|---|---|---|
| `DemoExplorePage` / `PaperExplorePage` / `LiveExplorePage` | `demo-explore/DemoExplorePage.tsx:8`, `paper-explore/PaperExplorePage.tsx:9`, `live-explore/LiveExplorePage.tsx:9` | Explore page per mode | `ModeExploreRoute` | Page |
| `ExploreObservability` (+`ExploreSqueezeTable`) | `explore-shared/ExploreObservability.tsx:90, 44` | Donor bridge sections (squeeze cohort, scanner, futures, catalyst) + charts | explore pages | Page-specific |
| `LiveObservationalPanel` | `live/LiveObservationalPanel.tsx:7` | Live subscribe/search panel | `ExploreObservability` (live) | Page-specific |
| `DemoResearchPage` / `PaperResearchPage` / `LiveResearchPage` | `demo-research/DemoResearchPage.tsx:4`, `paper-research/PaperResearchPage.tsx:4`, `live-research/LiveResearchPage.tsx:4` | Research page per mode | `ModeResearchRoute` | Page |
| `ResearchObservability` | `research-shared/ResearchObservability.tsx:16` | Analytics/Model Lab/Simulation tabs | research pages | Generic |
| `ResearchAnalyticsPanel` | `research/ResearchAnalyticsPanel.tsx:8` | 6 chart panels grid | `ResearchObservability` | Page-specific |
| `ModelLabPanel` | `research/ModelLabPanel.tsx:7` | Model manifest metrics + interpretations table | `ResearchObservability` | Page-specific |
| `SimulationLabPanel` | `research/SimulationLabPanel.tsx:17` | Sim ledger metrics + decision/fill tables | `ResearchObservability` | Page-specific |

### Portfolio

| Component | File | Purpose | Used by | Type |
|---|---|---|---|---|
| `DemoPortfolioPage` / `PaperPortfolioPage` / `LivePortfolioPage` | `demo-portfolio/DemoPortfolioPage.tsx:4`, `paper-portfolio/PaperPortfolioPage.tsx:29`, `live-portfolio/LivePortfolioPage.tsx:22` | Portfolio per mode | `ModePortfolioRoute` | Page |
| `PaperPortfolioObservability` | `portfolio-shared/PaperPortfolioObservability.tsx:9` | Account/P&L/exposure/risk/positions/orders/fills panels | Demo+Paper portfolio | Generic |
| `PaperOrderHistory` | `paper-portfolio/PaperOrderHistory.tsx:30` | Metrics + open orders + paginated history | `PaperPortfolioPage` | Page-specific |
| `PaperOrderHistoryTable` | `paper-portfolio/PaperOrderHistoryTable.tsx:27` | Filterable, expandable, paginated order table (scroll-contained) | `PaperOrderHistory` | Generic |
| `PaperOrderHistoryRowView` / `PaperOrderHistoryRowDetails` | `paper-portfolio/PaperOrderHistoryRow.tsx:103, 13` | Order row + expanded detail (full IDs) | table | Generic |
| `PaperDecisionProvenanceBadge` | `paper-portfolio/PaperDecisionProvenanceBadge.tsx:7` | Source-category pill | order rows | Generic |
| `PaperPersistedSourceContextPanel` | `paper-portfolio/PaperPersistedSourceContextPanel.tsx:8` | Saved source-time context block | order details, trace panel | Generic |
| `PaperStrategyProfitabilityObservability` | `paper-strategy-profitability/PaperStrategyProfitabilityObservability.tsx:6` | Strategy P&L lineage table (scroll-contained) | `PaperPortfolioPage`, `PaperResearchPage` | Page-specific |
| `OrderTicket` | `paper/OrderTicket.tsx:38` | Paper order ticket (preview/submit/session) | `PaperPortfolioPage`, `PaperDecisionCockpit` | Generic |
| `ExecutionTracePanel` | `paper/ExecutionTracePanel.tsx:89` | Trace stages + provenance + JSON details | `PaperPortfolioPage`, `PaperDecisionCockpit` | Generic |

### Workspace (overview + shared)

| Component | File | Purpose | Used by | Type |
|---|---|---|---|---|
| `DemoWorkspacePage` / `PaperWorkspacePage` / `LiveWorkspacePage` | `demo-workspace/DemoWorkspacePage.tsx:10`, `paper-workspace/PaperWorkspacePage.tsx:32`, `live-workspace/LiveWorkspacePage.tsx:10` | Workspace overview per mode | `ModeWorkspacePage` | Page |
| `WorkspaceObservability` (+`useWorkspaceContext`) | `workspace-shared/WorkspaceObservability.tsx:57` | What-matters panel, live market, replay slider, price chart, features, squeeze compact, evidence drawer | all 3 workspace pages | Generic |
| `WhatMattersNowPanel` | `workspace/WhatMattersNowPanel.tsx:17` | Lane relevance table | `WorkspaceObservability` | Generic |
| `WorkspaceEvidenceDrawer` | `workspace/WorkspaceEvidenceDrawer.tsx:10` | Lane evidence detail drawer | `WorkspaceObservability` | Generic |
| `LiveMarketPanel` | `live/LiveMarketPanel.tsx:13` | Live quote/book/CVD panel | `WorkspaceObservability` | Generic |
| `PaperDecisionCockpit` | `paper-workspace/PaperDecisionCockpit.tsx:36` | Handoff + snapshot + what-matters + risk + ticket composition | `PaperWorkspacePage` | Page-specific |
| `PaperHandoffPanel` | `paper-workspace/PaperHandoffPanel.tsx:24` | Lane/attention handoff provenance | cockpit | Page-specific |
| `PaperDecisionSnapshotPanel` | `paper-workspace/PaperDecisionSnapshot.tsx:33` | Supports/contradicts/unclear/gaps grid | cockpit | Generic-ish |
| `PaperWhatMattersNow` | `paper-workspace/PaperWhatMattersNow.tsx:13` | Top-5 lane bullets | cockpit | Page-specific |
| `PaperRiskContext` | `paper-workspace/PaperRiskContext.tsx:6` | Portfolio risk context | cockpit | Page-specific |
| `PaperPreviewStatus` | `paper-workspace/PaperPreviewStatus.tsx:18` | Preview state panel (7 statuses) | cockpit | Generic |
| `PaperForwardTestPanel` | `paper-workspace/PaperForwardTestPanel.tsx:10` | Forward-test records list | `PaperWorkspacePage` | Page-specific |

### Workspace lane modules (10 lanes; identical route → observability → panel pattern)

| Lane | Route | Observability | Panel(s) | Notes |
|---|---|---|---|---|
| Squeeze | `squeeze/ModeSqueezeWorkspaceRoute.tsx:19` | `squeeze/SqueezeWorkspaceObservability.tsx:17` | `squeeze/SqueezeWorkspacePanel.tsx:19` + blocks | Supports `?data_mode=current` |
| Order flow | `orderflow/ModeOrderFlowWorkspaceRoute.tsx:17` | `orderflow/OrderFlowWorkspaceObservability.tsx:15` | `orderflow/OrderFlowWorkspacePanel.tsx:13` | 2s live refetch (`hooks.ts:125`) |
| Order book | `orderbook/ModeOrderBookWorkspaceRoute.tsx:17` | `orderbook/OrderBookWorkspaceObservability.tsx:15` | `orderbook/OrderBookWorkspacePanel.tsx:11` | 8-col table |
| Futures | `futures/ModeFuturesWorkspaceRoute.tsx` | `futures/FuturesWorkspaceObservability.tsx` | `futures/FuturesWorkspacePanel.tsx:11`, `futures/FuturesProductSurface.tsx:21` | Largest metric-grid (~50 dt/dd) |
| Catalyst | `catalyst/ModeCatalystWorkspaceRoute.tsx` | `catalyst/CatalystWorkspaceObservability.tsx` | `catalyst/CatalystWorkspacePanel.tsx:11` | 7-col table |
| Fund/ETF | `fundetf/ModeFundEtfWorkspaceRoute.tsx` | `fundetf/FundEtfWorkspaceObservability.tsx` | `fundetf/FundEtfWorkspacePanel.tsx:11` | 7-col table |
| Options | `options/ModeOptionsWorkspaceRoute.tsx:18` | `options/OptionsWorkspaceObservability.tsx:28` (+`OptionsModuleHeaderExtra`) | `options/OptionsWorkspacePanel.tsx:29`, `options/OptionsProductSurface.tsx:26` + 4 blocks | 10-col activity table; adds `CanonicalInstrumentSelector` |
| Large transactions | `largetransactions/ModeLargeTransactionsWorkspaceRoute.tsx` | `largetransactions/LargeTransactionsWorkspaceObservability.tsx` | `largetransactions/LargeTransactionsWorkspacePanel.tsx:11` | 7-col table |
| Disclosure | `disclosure/ModeDisclosureWorkspaceRoute.tsx` | `disclosure/DisclosureWorkspaceObservability.tsx` | `disclosure/DisclosureWorkspacePanel.tsx:39` | 4-col + 8-col tables |
| Institutional flow | `institutional/ModeInstitutionalFlowWorkspaceRoute.tsx` | `institutional/InstitutionalFlowWorkspaceObservability.tsx` | `institutional/InstitutionalFlowWorkspacePanel.tsx:58` (+`FamilyStatusRow`) | Aggregator: embeds the other 8 lane panels via family tabs |

Squeeze sub-blocks: `StateTransitionBlock` (`squeeze/StateTransitionBlock.tsx:14` + internal
`CausalTransitionLog`/`TransitionLog`/`CriterionList`), `CausalIntelligenceBlock`
(`squeeze/CausalIntelligenceBlock.tsx:7`), `CatalystAttentionBlock`
(`squeeze/CatalystAttentionBlock.tsx:7`), `CrossLaneEvidenceBlock`
(`squeeze/CrossLaneEvidenceBlock.tsx:8`), `HistoricalSqueezeContextBlock`
(`squeeze/HistoricalSqueezeContextBlock.tsx:9`). Options sub-blocks: `DealerPositioningBlock`
(`options/DealerPositioningBlock.tsx:7`), `StrategyOptimizerBlock`
(`options/StrategyOptimizerBlock.tsx:8`), `ExecutionSimulationBlock`
(`options/ExecutionSimulationBlock.tsx:19`), `OpportunityFusionBlock`
(`options/OpportunityFusionBlock.tsx:56` + internal `ComponentPanel`; also reused by
`SqueezeWorkspacePanel.tsx:60`). Derivative preview: `DerivativePaperPreviewPanel`
(`paper-derivative/DerivativePaperPreviewPanel.tsx:16`, lazy-loaded by options/futures product
surfaces).

### Charts

| Component | File | Purpose | Used by | Type |
|---|---|---|---|---|
| `WorkspacePriceChart` (+`LightweightWorkspaceChart`) | `charts/WorkspacePriceChart.tsx:92, 40` | lightweight-charts candle chart + optional Vela shadow toggle | `WorkspaceObservability` | Generic |
| `ImpVelaChartAdapter` | `charts/ImpVelaChartAdapter.tsx:27` | Lazy `@luxalgo/vela` adapter w/ markers, ResizeObserver | `WorkspacePriceChart`, lab page | Generic |
| `ImpVelaChartLabPage` | `charts/ImpVelaChartLabPage.tsx:15` | Vela playground on synthetic feed | `/research/vela-chart-lab` | Page |
| `CountBarChartPanel` / `SignalTimelineChartPanel` | `charts/ResearchChartPanels.tsx:27, 97` | Recharts bar/line panels w/ data table + provenance | research + explore | Generic |
| `ChartEmptyState` | `charts/ChartEmptyState.tsx:5` | Dashed empty chart block | chart panels | Generic |
| `ChartProvenance` | `charts/ChartProvenance.tsx:6` | Source/method caption | chart panels | Generic |

### Operator / assistant / misc pages

| Component | File | Purpose | Used by | Type |
|---|---|---|---|---|
| `OperatorControlCenterPage` (+`ProviderConfigCard`) | `OperatorControlCenterPage.tsx:14, 237` | Lifecycle, readiness checks, provider cards, credential forms | `/control` | Page |
| `OperatorSettingsPage` | `OperatorSettingsPage.tsx:35` | Provider/state/paper/storage/UI/safety panels | `/settings` | Page |
| `LiveCanaryControlPlanePage` | `live/LiveCanaryControlPlanePage.tsx:40` | Live canary safety plane (kill switches, incidents, reliability matrix) | `/live-canary` | Page |
| `ProviderHealthPanel` | `live/ProviderHealthPanel.tsx:9` | Moomoo/Finviz diagnostics | `/diagnostics/provider` | Page |
| `AssistantSidecar` | `AssistantSidecar.tsx:23` | Right sidecar chat w/ quick actions + citations | `WorkstationShell` | Generic |
| `AssistantHistoryPage` | `AssistantHistoryPage.tsx:5` | Conversation list | `/assistant/history` | Page |
| `CanonicalInstrumentSelector` | `instrument-selector/CanonicalInstrumentSelector.tsx:21` | Keyboard-navigable instrument search listbox | `InstrumentSelectionEmpty`, `OptionsWorkspaceObservability` | Generic (unstyled) |

Non-component logic modules (view-model/presentation layers, no JSX): `imp-product/impOverviewMetrics.ts`,
`imp-product/capabilityPresentation.ts`, `imp-product/impOpportunityDisplay.ts`,
`imp-product/progressiveOpportunityModel.ts`, `imp-product/researchArtifactEvidenceProjection.ts`,
`paper-now/paperDashboardViewModel.ts`, `paper-now/paperOrderDraft.ts`, `live-now/liveDashboardViewModel.ts`,
`live-now/liveCanarySnapshot.ts`, `live-portfolio/livePortfolioViewModel.ts`,
`paper-portfolio/paperOrderHistoryModel.ts`, `paper-portfolio/paperDecisionProvenance.ts`,
`paper-portfolio/paperOrderStatusPresentation.ts`, `paper-workspace/build*.ts` (4),
`paper-workspace/paperPreviewPresentation.ts`, `paper-workspace/paperDecisionSemantics.ts`,
`paper-strategy-profitability/paperStrategyProfitabilityModel.ts`,
`workspace-module-shared/buildLaneModeContent.ts` / `laneQueryState.ts` / `laneRegistry.ts` /
`laneProvenance.ts` / `workspaceModuleModeDescription.ts` / `useWorkspaceInstrumentId.ts`,
`workspace-shared/workspaceHealth.ts`, `mode-session/modeAuthority.ts` / `modeMetadata.ts` / `types.ts`,
`operator-settings/operatorSettingsMode.ts`, `shared/jsonDetailPresentation.ts`,
`discover-shared/discoverInspectorActions.ts`, `now/nowDeskVariant.ts`, `lib/*` (4),
`charts/chartTransforms` consumers, `api/*` (11 modules incl. React Query hooks).

---

## Needed-primitive coverage map

Legend: **EXISTS-GOOD** = present and reusable as-is; **EXISTS-NEEDS-WORK** = present but
partial/scattered/unstyled; **MISSING** = no meaningful implementation.

| Primitive | Status | Evidence / gaps |
|---|---|---|
| AppShell | EXISTS-NEEDS-WORK | `ImpProductChrome` (`imp-product/ImpProductChrome.tsx:26`) + `WorkstationShell` (`App.tsx:186`) are solid (skip link, focus trap, inert management). But `.app-shell` grid is vestigial (`grid-template-rows: auto auto auto 1fr` for one child, `layout.css:17-21`), drawer offsets are stale (see overflow audit), and there is no page-level overflow guard. |
| PrimaryNav | EXISTS-NEEDS-WORK | `NavShell` (`NavShell.tsx:139`) with mode hints + GATED badge. Two items target the same path (`Research` and `Lab` both → `/research`, `NavShell.tsx:46-52, 81-89`) so active state is ambiguous; no icons; horizontal layout variant is dead code in the current chrome. |
| StatusBar | EXISTS-NEEDS-WORK | Three stacked bars instead of one: `ModeEnvironmentBar` (76px, `mode-session.css:200-216`), `ContextBar` (`ContextBar.tsx:26`), `ImpCapabilityStrip` (`ImpCapabilityStrip.tsx:8`). No unified status bar; ContextBar cannot wrap or scroll (overflow risk). |
| ModeBadge | EXISTS-NEEDS-WORK | No dedicated badge component. Mode is conveyed by `ImpExecutionPosture` text (`ImpExecutionPosture.tsx:14`), environment-bar identity, per-page eyebrows (`.demo-eyebrow`/`.paper-eyebrow`/`.live-eyebrow`), `.demo-state-badge`. Colors conflict across layers (see token conflicts). |
| SystemHealth | EXISTS-NEEDS-WORK | Quality badge inside `ContextBar` (`ContextBar.tsx:58-62`), `StartupRecoveryBanner` (`App.tsx:158-179`), `LiveSafetySnapshot`. No single system-health primitive; no aggregation rule. |
| ProviderHealth | EXISTS-NEEDS-WORK | Four overlapping implementations: `ProviderHealthPanel` page (`live/ProviderHealthPanel.tsx:9`), `LiveProviderRibbon` (`live-now/LiveProviderRibbon.tsx:8`), discover provider dots (`DiscoverObservability.tsx:346-357` + `layout.css:1250-1290`), `ImpCapabilityStrip`/`ImpProviderMatrixDrawer`. Consolidation candidate. |
| AttentionBanner | EXISTS-NEEDS-WORK | `OpportunityFeedStatusBanner` (`imp-product/OpportunityFeedStatusBanner.tsx:16`) is the closest; plus `.startup-recovery-banner`, `.discover-error`, `.mode-restriction-note` asides, `.simulation-banner`. No shared severity-graded banner component. |
| OpportunityCard | EXISTS-GOOD | `ProgressiveOpportunityCard` (`imp-product/ProgressiveOpportunityCard.tsx:66`) with cockpit/review densities + `CompactOpportunityCard` (`ImpTopOpportunityCards.tsx:21`). Strong domain model; styling is serviceable but dense. |
| OpportunityScore | EXISTS-NEEDS-WORK | Only text treatments: `ATTN n` in discover rows (`DiscoverObservability.tsx:423`, `.discover-score` `layout.css:1407-1411`) and `#rank` labels (`impOpportunityDisplay.ts:16-19`). No visual score component. |
| FreshnessIndicator | EXISTS-NEEDS-WORK | Freshness appears as raw text: `freshness_label` (`WhatMattersNowPanel.tsx:54`), `freshness {ms} ms` (`LiveMarketPanel.tsx:41`), discover `data-status-pill` (`layout.css:1476-1493`), stale notes (`LaneModeContextPanel.tsx:69-73`, class `.lane-mode-stale-note` unstyled). No shared component, no relative-time formatting, no staleness color scale. |
| ConfidenceIndicator | EXISTS-NEEDS-WORK | Raw text only: `confidence {value}` (`StateTransitionBlock.tsx:39`), `Confidence` rows (`CatalystWorkspacePanel.tsx:70-73`, `WorkspaceEvidenceDrawer.tsx:34-37`). No component. |
| EvidenceStack | EXISTS-NEEDS-WORK | Reason-code lists (`.reason-codes`, `layout.css:308-316`), `CrossLaneEvidenceBlock`, discover evidence popover (`DiscoverObservability.tsx:475-494`). No unified stack w/ per-source structure. |
| EvidenceSource | EXISTS-NEEDS-WORK | `.source-badge`/`.data-status-pill` (`layout.css:1421-1430, 1456-1470`), `ChartProvenance` (`charts/ChartProvenance.tsx:6`), `PaperDecisionProvenanceBadge` (`paper-portfolio/PaperDecisionProvenanceBadge.tsx:7`). Three different idioms. |
| ContradictionPanel | EXISTS-NEEDS-WORK | `PaperDecisionSnapshotPanel` supports/contradicts grid (`PaperDecisionSnapshot.tsx:77-96`), `ProgressiveOpportunityCard` "Contradictions" section (`ProgressiveOpportunityCard.tsx:156-158`). No severity, no deep styling. |
| RiskSummary | EXISTS-GOOD | `PaperRiskRibbon` (`paper-now/PaperRiskRibbon.tsx:6`) with `role="meter"` utilization bars; `PaperRiskContext` (`paper-workspace/PaperRiskContext.tsx:6`); risk panel in `PaperPortfolioObservability.tsx:70-97`. |
| PositionRow | EXISTS-NEEDS-WORK | Plain `<tr>`s (`PaperPortfolioObservability.tsx:117-128`, `LivePortfolioPage.tsx:90-96`). No component, no truncation/copy, ns timestamps raw. |
| OrderRow | EXISTS-GOOD | `PaperOrderHistoryRowView` + details (`PaperOrderHistoryRow.tsx:103, 13`) — expandable, status pill, provenance badge, trace action. Live orders remain plain rows (`LivePortfolioPage.tsx:116-121`). |
| Metric | EXISTS-NEEDS-WORK | No component. Universal idiom is raw `<dl><div><dt/><dd/></div></dl>`; `.metric-list` is **unstyled**; `.metric-grid` is CSS-only (`layout.css:988-992`). `ImpOverviewKpiStrip` (`imp-product/ImpOverviewKpiStrip.tsx:8`) is the closest to a Metric but its `tone-*` classes have no rules. |
| MetricGroup | EXISTS-NEEDS-WORK | CSS-only grids: `.metric-grid`, `.demo-metric-grid` (`demo-now.css:210-218`), `.live-safety-grid` (`live-now.css:150-156`), `.paper-risk-ribbon dl` (`paper-now.css:32-37`). No React component, no consistent label/value/detail structure. |
| ChartFrame | EXISTS-NEEDS-WORK | `.chart-panel` + `ChartEmptyState` + `ChartProvenance` cover recharts panels (`ResearchChartPanels.tsx:44-82`); `WorkspacePriceChart` and `ImpVelaChartAdapter` are separate stacks with their own loading/error text. Three chart libraries (`lightweight-charts`, `recharts`, `@luxalgo/vela`; `package.json:14-21`). |
| EmptyState | EXISTS-NEEDS-WORK | `shared/EmptyState.tsx:10` exists but is used only by `InstrumentSelectionEmpty`. All other empty states are ad hoc (`.unavailable` text, `.discover-empty`, `.chart-empty`, `.paper-strategy-profitability__empty`, `.state-transition-empty`, `.demo-empty-path`, muted paragraphs). |
| LoadingState | EXISTS-NEEDS-WORK | `shared/LoadingState.tsx:6` exists; ~30 ad-hoc `<p role="status">Loading…</p>` / `<div className="app-loading">` idioms coexist (see State-pattern consistency). |
| DegradedState | MISSING | No dedicated primitive. Degraded signals scattered: `.provider-degraded` dot (`layout.css:1284-1286`), `data-status` pills, UNREADY banner, `.lane-live-operational-strip.degraded` (`workspace-module-mode.css:152-154`), `.paper-preview-status.preview-stale`. |
| ErrorState | MISSING | No shared error component. Ad hoc: `role="alert"` paragraphs, `.capability-panel.unavailable`, `.order-ticket-error`, `.discover-error`, `.paper-cockpit-warning`, `<p className="error">` (`LiveCanaryControlPlanePage.tsx:52` — class unstyled). |
| TechnicalDetails | EXISTS-GOOD | `JsonDetailPanel` (`shared/JsonDetailPanel.tsx:33`) — flattened rows + nested details + raw JSON, word-break on values (`shared-ui.css:111`). |
| CopyableIdentifier | MISSING | Zero clipboard usage in the codebase (grep for `clipboard` finds none). IDs are truncated via `slice()` with no copy path: `session_id.slice(0, 12)…` (`PaperPortfolioPage.tsx:82, 161`), `order_id.slice(0, 8)…` (`PaperPortfolioObservability.tsx:200`), `shortId()` (`PaperStrategyProfitabilityObservability.tsx:147-149`). Full UUIDs render unbroken in `PaperOrderHistoryRowDetails` (`PaperOrderHistoryRow.tsx:58-76`) and `ExecutionTracePanel.tsx:130-134`. |
| PageHeader | EXISTS-NEEDS-WORK | `shared/PageHeader.tsx:13` (eyebrow/title/subtitle/meta/actions/restriction) used by only 3 pages. Every other page hand-rolls a header (`.demo-now-intro`, `.paper-now-header`, `.live-now-header`, `.discover-header`, `.demo-*-header`, `.paper-*-header`, `.live-*-header`, workspace headers). |
| SectionHeader | EXISTS-NEEDS-WORK | `.panel-header`/`.panel-actions` pattern used by all lane panels but **unstyled**; `.imp-discover-section-header` (`imp-product.css:575-586`); `.paper-panel > header` (`paper-now.css:41`). No component. |
| FilterBar | EXISTS-NEEDS-WORK | `PaperOrderHistoryTable` filters (`PaperOrderHistoryTable.tsx:49-94`), `.discover-lane-summary` buttons, `.discover-controls` select, `.imp-overview-queue-filters`. No shared FilterBar. |
| DataTable | EXISTS-NEEDS-WORK | `.data-table` is CSS-only (`layout.css:975-986`): no sticky header, no sorting, no density control, and **no overflow containment** in 12+ usages (see overflow audit). Only 3 tables have scroll wrappers. |
| Drawer | EXISTS-NEEDS-WORK | Five overlay idioms: `.drawer` (`ExplanationDrawer`, `ImpProviderMatrixDrawer`), `.inspector-panel` (`InspectorPanel`), `.evidence-drawer` (`WorkspaceEvidenceDrawer`), `.assistant-sidecar`, `.execution-trace-panel` (in-flow panel, not overlay). Three positioning systems; fixed offsets reference stale `--nav-height`/`--context-bar-height` (see overflow audit). |
| Modal | EXISTS-GOOD | `LiveModeConfirmation` (`mode-session/LiveModeConfirmation.tsx:10`) and `ImpKeyboardShortcuts` (`imp-product/ImpKeyboardShortcuts.tsx:17`) — both focus-trapped, Escape handling, backdrop. No generic Modal export, but two solid implementations to generalize. |
| Tabs | EXISTS-NEEDS-WORK | Four tab idioms: `.research-tabs` (`ResearchObservability.tsx:34-62`, `InstitutionalFlowWorkspacePanel.tsx:119-133`), `.inspector-tabs` (`InspectorPanel.tsx:36-48`), `.imp-overview-queue-filters` (`ImpOverviewPrimaryQueue.tsx:70-85`), `.discover-mode-switch`. No shared Tabs component; only some have proper `role="tablist"/tab/tabpanel` wiring. |
| Tooltip | MISSING | No tooltip component; only native `title` attributes (`ImpExecutionPosture.tsx:22-25`, `ContextBar.tsx:32`, `OperatorControlCenterPage.tsx:111`, `CanonicalInstrumentSelector.tsx:83`). |
| CommandPalette | EXISTS-NEEDS-WORK | `ImpCommandSearch` (`imp-product/ImpCommandSearch.tsx:12`) is a search input with ticker-pattern routing — no results list, no commands, no palette UI. Ctrl+K / `/` focus it (`ImpProductChrome.tsx:93-110`). |

Summary: **EXISTS-GOOD 5** (OpportunityCard, RiskSummary, OrderRow, TechnicalDetails, Modal) ·
**EXISTS-NEEDS-WORK 25** · **MISSING 4** (DegradedState, ErrorState, CopyableIdentifier, Tooltip).

---

## Overflow & layout risk audit

Hard requirement: zero page-level horizontal overflow; grids may scroll internally; long
identifiers truncate with copy buttons. Findings ordered by severity. Line numbers refer to files
under `ui/src/`.

### A. Confirmed page-level overflow risks

1. **ContextBar cannot wrap or scroll.** `.context-bar` is `display: flex; gap: 16px; height:
   var(--context-bar-height); padding: 0 16px` with **no `flex-wrap`, no `overflow-x`, no
   `min-width: 0` on segments** (`styles/layout.css:208-216`). It renders 5-6 segments including
   `scope_symbols.join(", ")` and a quality detail string (`components/ContextBar.tsx:29-63`).
   With the 220px sidebar (`imp-product.css:2`) and any long scope/quality text, the bar overflows
   the viewport. No media query covers it.
2. **ModeEnvironmentBar minimum width ~614px, collapses only ≤720px viewport.**
   `grid-template-columns: minmax(230px, 0.9fr) minmax(320px, 1.8fr) auto` + 1rem gaps + 2rem
   padding (`styles/mode-session.css:207-216`); single-column fallback only at
   `@media (max-width: 720px)` (`mode-session.css:485-491`). With the 220px sidebar, viewports
   ~721-840px overflow horizontally.
3. **OperatorControlCenter grid minimum ~654px, collapses only ≤820px.**
   `grid-template-columns: minmax(280px, 0.8fr) minmax(360px, 1.2fr)` + 14px gap
   (`styles/operator-control.css:13-19`); collapse at `max-width: 820px`
   (`operator-control.css:270-274`). With the sidebar, viewports ~821-1094px overflow.
4. **PaperNow decision grid minimum ~882px in 3-col band.**
   `grid-template-columns: minmax(260px, 0.9fr) minmax(340px, 1.35fr) minmax(250px, 0.8fr)` +
   2×16px gaps (`styles/paper-now.css:39`); 2-col at ≤1080px, 1-col at ≤720px
   (`paper-now.css:85-97`). With sidebar + page padding, viewports ~1081-1150px can overflow by a
   few px.
5. **Discover controls row has no wrap + fixed 280px select.** `.discover-controls { display:
   flex; gap: 12px; align-items: flex-end; }` (`styles/layout.css:1539-1543`) with
   `.discover-controls select { min-width: 280px; }` (`layout.css:1556-1560`); only fixed at
   ≤720px (`layout.css:1670-1677`). `.discover-meta` also lacks wrap (`layout.css:1562-1567`) and
   carries long `received_at` timestamps (`DiscoverObservability.tsx:534-540`).

### B. Tables without containment (content-driven overflow)

`.data-table { width: 100%; border-collapse: collapse; }` (`styles/layout.css:975-986`) has **no
`overflow-x` wrapper** in these usages — wide content or unbroken strings push the page wide:

| Table | Columns | File:line |
|---|---|---|
| Options unusual activity | 10 | `components/options/OptionsWorkspacePanel.tsx:106-136` |
| Disclosure events | 8 (+4-col participant table) | `components/disclosure/DisclosureWorkspacePanel.tsx:126-152, 99-124` |
| Order book snapshots | 8 | `components/orderbook/OrderBookWorkspacePanel.tsx:263-289` |
| Paper positions (incl. 19-digit `mark_as_of_ns`) | 8 | `components/portfolio-shared/PaperPortfolioObservability.tsx:103-130` |
| Futures snapshots | 7 | `components/futures/FuturesWorkspacePanel.tsx:419-443` |
| Catalyst rows | 7 | `components/catalyst/CatalystWorkspacePanel.tsx:79-104` |
| Fund/ETF events | 7 | `components/fundetf/FundEtfWorkspacePanel.tsx:76-101` |
| Large transactions | 7 | `components/largetransactions/LargeTransactionsWorkspacePanel.tsx:67-91` |
| Order flow bars | 6 | `components/orderflow/OrderFlowWorkspacePanel.tsx:85-108` |
| Paper orders / fills | 5 / 4 | `components/portfolio-shared/PaperPortfolioObservability.tsx:141-176, 186-204` |
| Live broker positions / orders | 3 / 2 | `components/live-portfolio/LivePortfolioPage.tsx:82-98, 107-124` |
| Model interpretations | 4 | `components/research/ModelLabPanel.tsx:57-75` |
| Simulation decisions / fills | 4 / 4 | `components/research/SimulationLabPanel.tsx:71-112` |
| What-matters lane table | 4 | `components/workspace/WhatMattersNowPanel.tsx:35-59` |
| Institutional family table | 5 | `components/institutional/InstitutionalFlowWorkspacePanel.tsx:135-149` |
| Options exec fills / strategy candidates | 6 / 3 | `components/options/ExecutionSimulationBlock.tsx:91-113`, `StrategyOptimizerBlock.tsx:80-94` |
| Explore squeeze / catalyst tables (`.explore-table`, `layout.css:459-470`) | 7 / 4 | `components/explore-shared/ExploreObservability.tsx:44-85, 302-335` |
| Squeeze rules (`.squeeze-rules-table`, `layout.css:630-640`) | 4 | `components/squeeze/SqueezeWorkspacePanel.tsx:113-132` |
| Health matrix (`.health-matrix-table` — **entirely unstyled**) | 3 | `components/live/LiveCanaryControlPlanePage.tsx:167-185` |

Tables that DO have containment (the pattern to generalize):
`.paper-order-table-wrap { overflow-x: auto }` + `min-width: 960px`
(`styles/paper-portfolio.css:71-74`), `.paper-strategy-profitability__table-wrap`
(`paper-portfolio.css:224-230`, `min-width: 860px`), `.imp-radar-dense-table-wrap`
(`styles/imp-product.css:512-514`).

### C. Long unbroken strings (identifiers, hashes, timestamps)

- Full UUIDs/IDs with no truncation or wrapping: `PaperOrderHistoryRowDetails`
  (`components/paper-portfolio/PaperOrderHistoryRow.tsx:58-76` — client order id, order id,
  intent id, correlation id inside an **unstyled** `.metric-list` whose `dd`s keep browser
  defaults), `ExecutionTracePanel` correlation (`components/paper/ExecutionTracePanel.tsx:130-134`),
  `ProviderHealthPanel` generation/last-error (`components/live/ProviderHealthPanel.tsx:48, 110-112`),
  `LiveCanaryControlPlanePage` account fingerprint / `as_of_ns` / backup id in unstyled
  `.status-grid` (`components/live/LiveCanaryControlPlanePage.tsx:92-99, 163`),
  `AssistantHistoryPage` `<code>{conversation_id}</code>`
  (`components/AssistantHistoryPage.tsx:27`), `AssistantSidecar` selection/citation `<code>`s
  (`components/AssistantSidecar.tsx:76, 108-112`).
- Manual truncation without copy (violates the "truncate **with copy button**" requirement):
  `session_id.slice(0, 12)…` (`components/paper-portfolio/PaperPortfolioPage.tsx:82, 161`),
  `String(fill.order_id).slice(0, 8)…` (`components/portfolio-shared/PaperPortfolioObservability.tsx:200`),
  `shortId()` (`components/paper-strategy-profitability/PaperStrategyProfitabilityObservability.tsx:147-149`).
- Strategy identity hash / dataset fingerprint use class `.mono` which has no CSS rule
  (`components/research/ModelLabPanel.tsx:32, 36`).
- Good existing containment to reuse: `.json-detail-row dd { word-break: break-word }`
  (`styles/shared-ui.css:110-112`), `.progressive-opp-meta-row dd { word-break: break-word }`
  (`styles/imp-product.css:934-937`), `overflow-wrap: anywhere` on ribbon `dd`s
  (`styles/paper-now.css:34`, `styles/live-now.css:102`, `styles/operator-control.css:259`),
  `.imp-capability-reason` ellipsis (`styles/imp-product.css:772-776`).

### D. Fixed/absolute positioning & stale offsets

6. **Drawer/inspector top offset is stale.** `.drawer, .inspector-panel { position: fixed; top:
   calc(var(--nav-height) + var(--context-bar-height)); }` = 84px (`styles/layout.css:402-419`,
   tokens `tokens.css:22-24`). The actual chrome stack above main content is now
   `.imp-top-bar` (~57px) + `ModeEnvironmentBar` (min 76px, `mode-session.css:210`) + `ContextBar`
   (40px) + `ImpCapabilityStrip` (min 32px, `imp-product.css:710`) ≈ **205px**. Drawers/inspector
   open at 84px and **overlap the environment bar, context bar, and capability strip**
   (z-index 20). Same staleness in `.workspace-module-nav-sticky { top: calc(44px + 40px + 36px)
   }` (`layout.css:717-728`) — the sticky lane nav parks 120px from the viewport top even though
   the top bar scrolls away, leaving a dead gap.
7. **Vestigial shell grid.** `.app-shell { grid-template-rows: auto auto auto 1fr; }`
   (`layout.css:17-21`) describes the pre-chrome 4-row layout; the current markup has a single
   `.app-body` child (`App.tsx:381-384`). Harmless but misleading.
8. **Assistant sidecar has no mobile treatment.** `.app-body { grid-template-columns: 1fr auto }`
   (`layout.css:28-31`) + fixed 360px `.assistant-sidecar` (`layout.css:45-51`,
   `tokens.css:22-23`): on a 400px viewport the sidecar leaves ~40px for main content. No
   breakpoint converts it to an overlay.
9. **`.portfolio-layout` never collapses.** `grid-template-columns: minmax(0, 1fr) 360px`
   (`layout.css:905-909`) with no media query — the 360px trace column persists at all widths
   (no overflow thanks to `minmax(0, 1fr)`, but unusably cramped).
10. **Discover evidence popover overlaps neighbors by design.** `.discover-queue-row { overflow:
    visible }` + absolutely positioned `.discover-evidence { width: min(440px, 80vw); right: 0;
    z-index: 5 }` (`layout.css:1343, 1510-1518`) — fine horizontally, but it paints over adjacent
    rows; worth a real popover/portal in the redesign.

### E. Things already safe (do not regress)

- `.app-body .main-content { min-width: 0 }` (`layout.css:34-36`), `.imp-product-main { min-width:
  0 }` (`imp-product.css:75`), `.imp-product-shell` sidebar grid uses `minmax(0, 1fr)`
  (`imp-product.css:2`), `.portfolio-main { min-width: 0 }` (`layout.css:917`),
  `.paper-panel`/`.demo-now-panel`/`.live-panel` `min-width: 0` (`paper-now.css:40`,
  `demo-now.css:82`, `live-now.css:123`), `.operator-panel` (`operator-control.css:22`).
- Charts size to container: lightweight-charts via `clientWidth` + window resize
  (`components/charts/WorkspacePriceChart.tsx:50-51, 62-66`), recharts `ResponsiveContainer
  width="100%"` (`components/charts/ResearchChartPanels.tsx:47, 114`), Vela via `ResizeObserver`
  (`components/charts/ImpVelaChartAdapter.tsx:71-74`).
- Discover queue rows have explicit responsive breakpoints
  (`layout.css:1620-1678`); `.demo-now-grid-*` use `minmax(0, …)` (`demo-now.css:72-79`);
  auto-fit grids (`.metric-grid`, `.explore-provenance-grid`, `.squeeze-detail-grid`,
  `.ignition-evidence-grid`, `.state-transition-grid`, `.chart-grid`) degrade gracefully.
- `pre` blocks wrap or scroll: `.inspector-body pre { white-space: pre-wrap }`
  (`layout.css:449-451`), `.trace-step pre { overflow: auto }` (`layout.css:970-972`),
  `.discover-evidence pre { white-space: pre-wrap }` (`layout.css:1525-1528`),
  `.json-detail-raw pre { max-height: 16rem; overflow: auto }` (`shared-ui.css:121-124`).
- `.execution-trace-panel { max-height: 80vh; overflow: auto }` (`layout.css:962-967`).

---

## State-pattern consistency

### Loading — 3 idioms, inconsistent

1. Shared `LoadingState` (`components/shared/LoadingState.tsx:6`) — used by `LazyBoundary`,
   `WorkspaceRoute.tsx:50-55`, `ExecutionTracePanel.tsx:108`, `LiveLaneOperationalStrip.tsx:24`,
   `PaperPortfolioPage.tsx:48`, `PaperOrderHistory.tsx:89`, `PaperStrategyProfitabilityObservability.tsx:12`,
   `LiveCanaryControlPlanePage.tsx:48`, `WorkspaceIndex.tsx:17`.
2. `<div className="app-loading">…</div>` — `ExploreObservability.tsx:98`,
   `ResearchObservability.tsx:30`, and all lane panels (`OrderFlowWorkspacePanel.tsx:21`,
   `OrderBookWorkspacePanel.tsx:19`, `FuturesWorkspacePanel.tsx:19`, `CatalystWorkspacePanel.tsx:19`,
   `DisclosureWorkspacePanel.tsx:44`, `FundEtfWorkspacePanel.tsx:19`,
   `LargeTransactionsWorkspacePanel.tsx:19`, `InstitutionalFlowWorkspacePanel.tsx:96`,
   `OptionsWorkspacePanel.tsx:37`).
3. Bare `<p role="status">Loading…</p>` — `AttentionFeed.tsx:23`, `OpportunityReviewCard.tsx:85`,
   `PaperCandidateQueue.tsx:46`, `PaperRiskRibbon.tsx:10`, `LiveProviderRibbon.tsx:13`,
   `LiveSafetySnapshot.tsx:24`, `LiveSymbolLookup.tsx:38,49,64`, `DemoReplayOverview.tsx:56,101`,
   `DemoPortfolioSummary.tsx:29`, `PaperExceptionsPanel.tsx:12`, `PaperWhatMattersNow.tsx:34`,
   `PaperRiskContext.tsx:12`, `PaperDecisionSnapshot.tsx:39`, `PaperForwardTestPanel.tsx:20`,
   `LivePortfolioPage.tsx:43`, `DemoPortfolioPage.tsx:11`, `AssistantHistoryPage.tsx:18`,
   `FuturesProductSurface.tsx:26`, `OptionsProductSurface.tsx:31`,
   `CanonicalInstrumentSelector.tsx:69`, `ProgressiveOpportunityCard.tsx:149`,
   `TradeReviewLearningPanel.tsx:19`, `ModeEnvironmentBar.tsx:23`, `DiscoverObservability.tsx:357`.
   No skeletons, no spinners, no progress indication anywhere except the mode-session progress
   sweep (`mode-session.css:317-324`) and replay/risk bars.

### Error — 6+ idioms, no shared component

- `<p role="alert">…unavailable.</p>`: `AttentionFeed.tsx:24`, `OpportunityReviewCard.tsx:86`,
  `PaperCandidateQueue.tsx:47`, `PaperPreviewComposer.tsx:54`, `DerivativePaperPreviewPanel.tsx:80`,
  `CanonicalInstrumentSelector.tsx:70`, `OpportunityFeedStatusBanner.tsx:31`,
  `ModeEnvironmentBar.tsx:29-37`, `ProgressiveOpportunityCard.tsx:149`, `OperatorLoginGate.tsx:69`.
- `.capability-panel.unavailable` blocks: `ExploreObservability.tsx:104, 120, 170, 220, 275`,
  `LiveObservationalPanel.tsx:21`, `LiveMarketPanel.tsx:23`, all lane panels' UNAVAILABLE branches,
  `OrderTicket.tsx:223`, `PaperPortfolioPage.tsx:57-60`, `LivePortfolioPage.tsx:45-48`,
  `DemoPortfolioPage.tsx:20-23`, `WorkspaceObservability.tsx:154-161`.
- `.discover-error` (`DiscoverObservability.tsx:319-322`), `.order-ticket-error`
  (`OrderTicket.tsx:323`, `ExecutionTracePanel.tsx:109`, `OperatorSettingsPage.tsx:86`),
  `.paper-cockpit-warning` (paper-workspace panels), `<p className="error">`
  (`LiveCanaryControlPlanePage.tsx:52` — **class has no CSS rule**), `.unavailable` text
  (`layout.css:398-400`).

### Empty — shared component exists but is barely used

`EmptyState` (`shared/EmptyState.tsx:10`) is used once (`InstrumentSelectionEmpty.tsx:47-55`).
Everything else is ad hoc: `.unavailable` paragraphs, `.discover-empty` (`layout.css:1532-1537`),
`.chart-empty` (`layout.css:680-688` via `ChartEmptyState`), `.paper-strategy-profitability__empty`
(`paper-portfolio.css:214-222`), `.state-transition-empty` (`layout.css:834-837`),
`.demo-empty-path` (`demo-now.css:281-284`), `.imp-top-opportunity-tags-empty`
(`imp-product.css:454-457`), and many `<p className="muted">No …</p>` one-offs
(e.g. `PaperPortfolioObservability.tsx:101, 138, 183`, `LivePortfolioPage.tsx:79, 104, 164`).

### Degraded — no primitive, scattered signals

Provider dots (`.provider-degraded`, `layout.css:1284-1286`), data-status pills
(`layout.css:1476-1493`), UNREADY feed banner (`OpportunityFeedStatusBanner.tsx:36-43`),
`.lane-live-operational-strip.degraded` (`workspace-module-mode.css:152-154`),
`.paper-preview-status.preview-stale` (`paper-workspace.css:115-117`), lane stale notes
(`LaneModeContextPanel.tsx:69-73`, class unstyled), degraded screen outcomes details
(`DiscoverObservability.tsx:371-384`), capability warn chips (`ImpCapabilityStrip`).

### Accessibility semantics are the most consistent layer

`role="status"` / `role="alert"` are used reliably for async state; `aria-live="polite"` on
`.discover-queue` (`DiscoverObservability.tsx:412`), `PaperPreviewStatus`
(`PaperPreviewStatus.tsx:23`), `.assistant-messages` (`AssistantSidecar.tsx:91`);
`role="progressbar"` + `aria-value*` on replay/risk meters (`DemoReplayOverview.tsx:66-76`,
`PaperRiskRibbon.tsx:19-20`); `role="meter"` on risk utilization; focus traps in modal/shortcuts/
mobile nav (`lib/useFocusTrap.ts`, `LiveModeConfirmation.tsx:30-48`, `ImpProductChrome.tsx:40`);
skip link (`ImpProductChrome.tsx:137-139`); `inert` management for mobile nav
(`ImpProductChrome.tsx:53-56`).

---

## Observations & risks

1. **Phantom-class debt is the dominant styling problem.** ~60 class families used in JSX have no
   CSS rules (full list in Styling architecture §2). The redesign should not assume existing
   visuals for `.panel`, `.metric-list`, `.quality-banner`, `.panel-header`, `.status-grid`,
   `.instrument-selector*`, `.tone-*`, etc. — those surfaces currently render as unstyled browser
   defaults, and any "current look" screenshots of lane panels, portfolio, provider diagnostics,
   live canary, or the instrument selector are mostly unstyled DOM.
2. **Undefined-token references silently break intended styling.** `--surface-elevated`,
   `--accent`, `--radius-sm`, `--radius-lg`, `--danger`, `--muted`, `--color-text-muted`,
   `--color-border`, `--imp-sidebar-width` are referenced but never defined; several resolve to
   transparent/initial (research tab buttons, simulation banner accent border, execution trace
   panel background, discover session label in sky blue `#7dd3fc`). A token freeze + `var()`
   linting (or a stylelint `no-unknown-custom-properties` rule) would catch these.
3. **Mode color semantics conflict with the redesign target.** Paper is teal/green today
   (`#48d6c4` pages, `#56c596` launcher), Live is amber/orange (`#f0b45c` pages, `#ff8a00`
   launcher), Demo/replay is cyan/slate with an amber context-bar tint — versus the planned
   live=green/teal, paper=IMP orange, replay=purple. This is a full re-map, not a tweak; mode
   color is currently declared in at least 4 places per mode (launcher tokens, page CSS vars,
   header border hexes, chart accents).
4. **Status-color sprawl.** At least 4 ambers (`#d4a017`, `#f0b35a`, `#e1b85b`, `#f2ca59`) and 5
   reds (`#c44e52`, `#e36d77`, `#f0a6a6`, `#f58d91`, `rgba(180,90,90,*)`) encode
   degraded/blocked; greens split between `#3d9970`, `#3dd68c`, `#8fd48f`, `#7dd3a8`, `#8fd9a8`,
   `#48d6c4`. Consolidation into the planned 7-semantics palette is high-value.
5. **Fonts are declared but never loaded.** Inter/JetBrains Mono silently fall back to system
   fonts (`tokens.css:19-20`, `index.html:1-11`); non-standard weights 680/750 no-op. Decide:
   bundle the fonts (self-host for offline operator workstation) or embrace the system stack.
6. **Drawer/inspector geometry is stale after the chrome redesign.** Fixed `top: 84px` overlaps
   the current ~205px top stack; sticky lane nav offset (120px) matches nothing. Any redesign of
   the top stack must recompute these or move drawers into the grid.
7. **CopyableIdentifier is a greenfield addition.** No clipboard code exists anywhere; current
   truncation is `slice(0, n)…` in 4 places. The redesign requirement (truncate + copy) needs a
   new primitive plus an audit of every ID render site (order history details, trace panel,
   provider diagnostics, canary page, assistant refs, session lists).
8. **Three chart stacks with three theme sources.** lightweight-charts (hardcoded hexes in
   `WorkspacePriceChart.tsx:49-58`), recharts (`chartTheme.ts` with blue `#5b8def` accent),
   `@luxalgo/vela` (`impVelaTheme.ts`). A single ChartFrame + theme mapping would unify them;
   note the blue chart accent conflicts with the IMP-orange identity.
9. **Duplicate nav targets.** "Research" and "Lab" both link to `/research`
   (`NavShell.tsx:46-52, 81-89`); `NavLink` active state cannot distinguish them. The redesign IA
   (COMMAND/RADAR/WORKSPACE/… per audit 01) resolves this.
10. **State primitives exist but adoption is the problem.** `EmptyState` (1 use), `LoadingState`
    (~9 uses vs ~30 ad hoc), `PageHeader` (3 uses vs ~15 hand-rolled headers). The redesign should
    expect resistance-free consolidation — the patterns are already half-built — but must delete
    or restyle the ad-hoc variants to actually converge.
11. **Unknowns / not verified (read-only audit):** actual rendered pixels (no dev server run per
    safety constraints — a live trading session is running from another checkout); whether any
    phantom classes are styled by browser extensions or by the API-served pages outside `ui/src`;
    bundle budget details (`ui/scripts/check-bundle-budget.mjs` referenced in `package.json:8` but
    not read); backend-driven class hooks (e.g. `data-*` attributes consumed by tests only);
    whether `--imp-sidebar-width` is meant to be operator-configurable (referenced with fallback
    at `imp-product.css:2, 669`, never set).
12. **Test coupling note for the redesign:** many smoke/unit tests assert on current class names
    and copy (e.g. `WorkspaceModuleNav.sticky.test.tsx`, `ImpProductChrome.test.tsx`,
    `App.test.tsx`, `smoke/appShell.smoke.test.ts`). Class renames will need coordinated test
    updates; `data-testid` hooks exist for some surfaces (`workspace-mode-restriction-note`,
    `live-canary-control-plane`) and are the safer selectors to expand.
