# A11y, Responsive, Tests & Tooling

Audit of `ui/src` (React 18 + TS + Vite) for the operator-first redesign
(`ui/operator-redesign-v2`). Read-only static audit — no servers, tests, or
builds were executed (live trading session constraint). All citations are
relative to `projects/integrated-market-platform/`.

## Binding engineering requirements

**`docs/engineering/ACCESSIBILITY.md`** mandates:
- Semantic HTML (`button`, `nav`, `main`, `table`, headings) and keyboard
  operability for all interactive controls (lines 7-8).
- Visible focus indicators driven by theme tokens (line 9).
- Form labels via `htmlFor` / `aria-label` (line 10); live regions for dynamic
  status (line 11); `th` scope + captions on tables (line 12); focus trap +
  Escape dismiss on modals/dialogs (line 13).
- Color must never be the sole state indicator — use text/icons/badges
  (line 14); `aria-label` on mode-specific nav descriptions (line 15);
  restriction notes readable without color (line 19).
- Tests prefer `getByRole` / `getByLabelText` (line 23).
- UI Definition of Done: keyboard-reachable interactives, labeled icons,
  error states announced or visible in text (lines 28-30), and see
  `docs/engineering/checklists/UI_CHANGE.md` (adds: mode implications,
  `App.test.tsx` when routes/nav change, `npm run build`, "Accessibility
  basics", `validate.py changed`).

**`docs/engineering/PERFORMANCE.md`** mandates:
- Initial JS ≤ **200 KiB gzip**, enforced by `ui/scripts/check-bundle-budget.mjs`
  on `npm run build`; lazy chunks ≤ 500 KB raw (lines 5-9). Last recorded:
  **199.17 KiB gzip on 2026-09-01** (line 12) — only ~0.8 KiB of documented
  headroom.
- Lazy-load lane routes, assistant, settings, provider health, canary page
  (line 16); no eager Paper-only imports on Demo/Live entry paths (line 17);
  prefer Lightweight Charts, keep `recharts` off the initial path (lines 18-19).
- Budget increases require an ADR + budget-script update (lines 23-25).

**`docs/engineering/FRONTEND_GUIDE.md`** mandates:
- Stack: React 18, TS, Vite, React Router 6, TanStack Query 5, Zod,
  Lightweight Charts (line 6).
- Nav labels and `App.tsx` routes stay in lockstep; no invented paths
  (lines 10-19). Mode route pattern `Mode*Route.tsx` switching
  Demo/Paper/Live (lines 22-30). Pure view models (`build*Model.ts`,
  `*Presentation.ts`) instead of inline logic (line 34).
- Heavy routes use `React.lazy` + `LazyBoundary`; no static lane imports on
  the entry path (line 39).
- React Query keys registered in `ui/src/api/hooks.ts` `queryKeys`; documented
  shared keys (lines 42-57); mode switch invalidates `context`, `attention`,
  `instrument` (line 61).
- CSS organization: mode styles `ui/src/styles/{demo,paper,live}-*.css`;
  shared tokens in `tokens.css`, `layout.css` (lines 80-81).
- New mode-aware surfaces and workspace lanes must add `App.test.tsx`
  navigation per mode and run vitest + build (lines 95-108, 111-126).

**`docs/engineering/sops/ADD_MODE_AWARE_SURFACE.md`**: route wrapper →
Demo/Paper/Live pages → shared `*Observability` primitives → per-mode CSS →
lazy wiring in `App.tsx` → NavShell mode hints + `aria-label` for primary nav
(line 26) → authority gating (`canUsePaperActions`; Live no mutations; Demo
read-only, line 28) → `App.test.tsx` per-mode navigation (line 31) →
vitest + build + `validate changed` (line 34).

**`docs/engineering/sops/ADD_WORKSPACE_LANE.md`**: lane IDs live only in
`WORKSPACE_LANE_REGISTRY` (`ui/src/components/workspace-module-shared/laneRegistry.ts`,
lines 17-27) with a drift test (`laneRegistry.test.ts`); lazy
`Mode{Lane}WorkspaceRoute`; `WorkspaceModuleModeShell` + `buildLaneModeContent`;
Paper handoff via `createLanePaperOrderDraft`; App integration tests for all
three modes at `/workspace/BIYA/{lane}` (line 41); validation = vitest +
`validate.py changed` (line 53).

## Accessibility audit

### Landmarks — mostly solid
- Skip link first in DOM targeting `#imp-main-content`:
  `ui/src/components/imp-product/ImpProductChrome.tsx:137-139`; target
  `<main className="main-content" id="imp-main-content" tabIndex={-1}>` at
  `ui/src/App.tsx:383`. Covered by test `App.test.tsx:1067-1084`.
- Primary nav `<nav aria-label="Primary">` with per-mode `aria-label`
  ("Label — hint"): `ui/src/components/NavShell.tsx:109-135,141`. Workspace
  lane nav `<nav aria-label="Workspace modules">` with `aria-current="page"`:
  `ui/src/components/WorkspaceModuleNav.tsx:21-33`.
- Assistant sidecar is a labeled complementary: `<aside aria-label="AI research
  assistant">` (`ui/src/components/AssistantSidecar.tsx:58`); mode launcher and
  login gate use `<main>` + `aria-labelledby` sections
  (`ui/src/components/mode-session/ModeLauncher.tsx:16-21`,
  `ui/src/auth/OperatorLoginGate.tsx:40-44`).
- **Duplicate banner landmarks**: `<header className="imp-top-bar">`
  (`ImpProductChrome.tsx:178`) is a page-level banner, and `ContextBar` adds
  an explicit `<header role="banner">` (`ui/src/components/ContextBar.tsx:29`).
  Two banners on one page is landmark noise for screen-reader rotor users.

### Focus management & visible focus
- Good reference implementations exist: `ui/src/lib/useFocusTrap.ts` (trap +
  restore), used by the shortcuts dialog (`ImpKeyboardShortcuts.tsx:19,28-31`,
  `role="dialog" aria-modal`) and the mobile nav overlay
  (`ImpProductChrome.tsx:40,152-153` conditional `role="dialog" aria-modal`,
  with `inert` toggling at lines 55-56 and focus restore at 60-63).
  `LiveModeConfirmation.tsx:15-59` hand-rolls trap + Escape + focus restore.
- **Gap: the three always-available drawers have no dialog semantics or focus
  management.** `ExplanationDrawer.tsx:10` (`<aside aria-label="Explanation">`),
  `InspectorPanel.tsx:28` (`<aside aria-label="Evidence Inspector">`), and
  `ImpProviderMatrixDrawer.tsx:24` render conditionally but never move focus
  in, never trap, and never restore focus on close. Escape works only via a
  global window handler (`App.tsx:234-243`). Keyboard users must tab through
  the entire page to reach drawer content (drawers render last in
  `.app-body`, `App.tsx:574-583`). This violates the ACCESSIBILITY.md focus
  trap/escape line 13 for anything treated as a dialog.
- Visible focus styles exist but are per-page, not global:
  `paper-now.css:82`, `live-now.css:258-263`, `demo-now.css:205-207`,
  `mode-session.css:57-60,279-281`, `layout.css:1230-1236,1317-1319`,
  `imp-product.css:93-97,126-128,178-182,476`, `shared-ui.css:26`,
  `operator-control.css:147`. **Any new component outside those scopes has no
  guaranteed visible focus** — the redesign needs one token-driven global
  `:focus-visible` rule.
- `forced-colors: active` overrides exist only in `paper-now.css:104-109`,
  `live-now.css:308+`, `demo-now.css:336+`, `mode-session.css:511+`.

### Keyboard navigation & tab order
- Global shortcuts: Ctrl/Cmd+K and `/` focus command search, `?` toggles
  shortcut dialog, `A` toggles assistant, Escape closes layers
  (`ImpProductChrome.tsx:76-119`), with typing-target guard
  (`ui/src/lib/isTypingTarget.ts`, tested). Covered by `App.test.tsx:1067-1099`.
- Command search is a real `role="search"` form with sr-only label and
  `type="search"` input (`ImpCommandSearch.tsx:28-42`).
- Instrument selector implements listbox/options with ArrowUp/Down/Enter
  (`CanonicalInstrumentSelector.tsx:52-68,72-91`) — but the input lacks
  `role="combobox"`/`aria-activedescendant` linkage, so screen readers get a
  listbox detached from the text field.
- Dense radar rows are keyboard-operable via `tabIndex={0}` + Enter/Space on
  `<tr>` (`OpportunityRadarDensePanel.tsx:80-96`) — non-idiomatic (rows aren't
  in a grid role) but functional; `aria-selected` on a plain `<tr>` without
  row selection context is borderline.
- **InspectorPanel tabs**: `role="tablist"`/`role="tab"`/`aria-selected`
  (`InspectorPanel.tsx:36-47`) but no Left/Right arrow handling and no
  `aria-controls`/`aria-labelledby` linkage to the `role="tabpanel"` div
  (line 49). ARIA tabs pattern is incomplete.
- **`aria-selected` on `<article>`** (`PaperCandidateQueue.tsx:52`) — invalid
  without an owning `role="listbox"`/`role="option"` structure.

### Semantic tables vs div-grids
- ~25 real `<table>` instances across portfolio, order history, all workspace
  lanes, research, discover, live canary (e.g. `PaperOrderHistoryTable.tsx:101`,
  `PaperPortfolioObservability.tsx:103,141,185`, `OrderBookWorkspacePanel.tsx:262`,
  `LiveCanaryControlPlanePage.tsx:167`). **Zero** ARIA grid/div-table usages.
- Inconsistent header semantics: only some tables use `scope="col"`
  (`PaperOrderHistoryTable.tsx:104-120`,
  `PaperStrategyProfitabilityObservability.tsx:83-88` plus sr-only caption at
  line 80, `ImpKeyboardShortcuts.tsx:43-58` with caption + `scope="row"`,
  `OpportunityRadarDensePanel.tsx:61-66`). Most lane tables have bare `<th>`
  without scope (e.g. `OrderFlowWorkspacePanel.tsx:87-92`,
  `CatalystWorkspacePanel.tsx:82-88`, `WhatMattersNowPanel.tsx:37-40`) —
  violates ACCESSIBILITY.md line 12 in spirit.

### Forms
- Generally good: wrapping `<label>` + inputs (`OrderTicket.tsx:240,281`,
  `PaperPreviewComposer.tsx:43-44` with `fieldset`/`legend`,
  `OperatorLoginGate.tsx:46-65` with autocomplete + required + `role="alert"`
  error at 67-71, `PaperOrderHistoryTable.tsx:49-91` labeled selects),
  sr-only `htmlFor` labels (`ImpCommandSearch.tsx:29-31`,
  `AssistantSidecar.tsx:121-123`).

### Live regions / status announcements
- Strong coverage: `role="status"`/`role="alert"` on loading, error, and
  warning states across paper cockpit, live, discover (`PaperPreviewStatus.tsx:22`
  uses `aria-live="polite"`; `ModeTransition.tsx:61`; `ModeEnvironmentBar.tsx:23-35`;
  `StartupRecoveryBanner` at `App.tsx:174-177`). Mode restriction notes use
  `role="note"` (`WorkspaceModuleModeShell.tsx:109,120,132`).

### Tooltip reliance for critical info
- `title=`-only information exists at: `ImpExecutionPosture.tsx:22,26`
  ("Paper simulation account", "Broker execution remains disabled in this UI
  build" — posture detail is tooltip-only), `OperatorControlCenterPage.tsx:112`
  (lifecycle update detail), `ContextBar.tsx:32` (raw mode enum; visible label
  carries the formatted value — low risk). `CanonicalInstrumentSelector.tsx:83`
  duplicates its tooltip as visible text at line 89 (good pattern).

### Color-only state encoding
- **Tier is border-color only**: `.attention-card.tier-1 { border-color:
  rgba(212,160,23,0.4) }` (`layout.css:264-266`) with no visible tier text in
  `AttentionFeed.tsx:29-56`; same pattern in `PaperCandidateQueue.tsx:52`.
  Fails ACCESSIBILITY.md line 14 where tier matters.
- Mostly OK elsewhere: order status pills render text labels
  (`PaperOrderHistoryRow.tsx:116`), capability chips pair border tone with
  state text (`ImpProviderMatrixDrawer.tsx:42-46`, styles at
  `imp-product.css:741-753`), discover badges carry text
  (`DiscoverObservability.tsx:445`).

### Contrast risks (computed WCAG ratios vs `--surface-0 #0c0e12`)
- **`--text-muted: #6b7280` (`tokens.css:13`) ≈ 4.0:1 on `#0c0e12`, ≈ 3.7:1 on
  `--surface-1 #13161c`** — fails AA 4.5:1 for normal text, yet used at
  0.62rem-10px sizes: wordmark tag (`imp-product.css:64-70`), capability strip
  label (`imp-product.css:716-721`), capability reason (`imp-product.css:770-776`),
  radar feed status (`imp-product.css:503-509`).
- **`--direction-short: #c44e52` (`tokens.css:16`) ≈ 4.2:1** — borderline fail
  for normal-size short/negative values in tables.
- `--mode-muted: #7a8494` (`mode-session.css:8`) ≈ 4.3:1 on `#0a0c10` —
  borderline.
- Pass: `--text-secondary #9aa3b5` ≈ 7.6:1; `--accent-primary #ff6a00` ≈ 6.7:1;
  `--direction-long #3d9970` ≈ 5.5:1; `--warning #d4a017` ≈ 8.1:1; chart text
  `#9aa3b5` (`chartTheme.ts:3`) fine; paper primary button `#061513` on
  `#48d6c4` (`paper-now.css:80`) fine.

### Charts
- Recharts panels: `role="img"` + `aria-label` + provenance, and
  `CountBarChartPanel` adds a full tabular summary table with caption
  (`ResearchChartPanels.tsx:47,63-79`). **`SignalTimelineChartPanel` has no
  tabular summary** (`ResearchChartPanels.tsx:110-143`).
- **The main workspace price chart has no accessible alternative**:
  `WorkspacePriceChart.tsx:89` renders a bare `<div className="price-chart">`
  for lightweight-charts — no role, no label, no text summary. The Vela
  adapter path carries an aria-label (`WorkspacePriceChart.tsx:144`) but the
  default path does not.

## Responsive audit

### Breakpoints / media queries (28 CSS blocks, 12 files, 9 distinct widths)
- Width breakpoints in use: **640** (`shared-ui.css:140`), **720**
  (`workspace-module-mode.css:180`, `paper-now.css:90`, `mode-session.css:453`,
  `live-now.css:275`, `layout.css:1631`, `demo-now.css:293`), **820**
  (`operator-control.css:270`), **900/901** (`imp-product.css:657,688`),
  **960** (`paper-portfolio.css:256` max; `paper-workspace.css:37` min),
  **980** (`demo-now.css:286`), **1080** (`paper-now.css:84`,
  `live-now.css:265` max; `imp-product.css:820` min), **1100**
  (`layout.css:1620`). Plus `prefers-reduced-motion` in 5 files and
  `forced-colors` in 4 files (see above).
- One JS-driven breakpoint: `MOBILE_NAV_MAX_PX = 900` matchMedia collapses the
  sidebar into a focus-trapped overlay (`ImpProductChrome.tsx:12,24-29,42-50`;
  CSS at `imp-product.css:657-686`).
- CSS-existence tests pin some breakpoints: `PaperNowPage.test.tsx:270-273`,
  `LiveNowPage.test.tsx:132-134`, `DemoNowPage.test.tsx:125-128` (string-match
  the stylesheet), plus `WorkspaceModuleNav.sticky.test.tsx` for sticky CSS.
  **No test resizes a viewport** — jsdom matchMedia is mocked
  (`App.test.tsx:420-432`).

### Layout primitives
- App shell: `.imp-product-shell` grid `220px sidebar + minmax(0,1fr)`
  (`imp-product.css:1-6`); `.app-body` grid `1fr auto` with
  `.main-content { min-width: 0 }` (`layout.css:23-35`) — correct overflow
  hygiene at the top level.
- Content containers: `max-width` 1440-1600px per page family
  (`workspace-module-mode.css:4` 1540px, `paper-workspace.css:4` 1580px,
  `operator-control.css:2` 1440px, `layout.css:1107` 1600px) — desktop-first,
  centered at 2560px.
- Auto-fit grids wrap naturally: `layout.css:489-490,545-546,583-584,647-648,
  758-759,905-912,1069-1071` (`repeat(auto-fit, minmax(140-280px, 1fr))`).
- Data grids scroll internally as allowed: `.paper-order-table-wrap
  { overflow-x: auto }` + `min-width: 960px` table (`paper-portfolio.css:70-75`),
  second table `min-width: 860px` (`paper-portfolio.css:225-230`),
  `.imp-radar-dense-table-wrap { overflow-x: auto }` (`imp-product.css:511-512`).
  Column-hiding pattern at ≤960px drops Type/Fill/Detail/Time and relaxes to
  `min-width: 640px` (`paper-portfolio.css:256-265`).
- No `100vw` usage anywhere; no root `overflow-x: hidden` guard (relying on
  grid `minmax(0,…)` + `min-width: 0`).

### Narrow-width behavior & risks at 1024-1366px
- **Fixed 360px drawers squeeze content**: `--inspector-width` /
  `--drawer-width: 360px` (`tokens.css:21-22`); sidecar/drawers are grid
  columns, not overlays (`layout.css:45-50`, `App.tsx:544-583`). At 1024px:
  220px sidebar + 360px drawer leaves ~444px for main content. Tight but
  scroll-free; at 901-1024px the sidebar is still inline (overlay starts at
  ≤900px), so 1024-1080px is the tightest band.
- **Most page stylesheets have zero media queries**: all `demo-*`, `live-*`,
  `paper-*` workspace/research/explore/discover/portfolio files except the
  ones listed above rely solely on max-width + auto-fit grids. Behavior at
  1024-1366px is unverified for workspace lanes, research, explore, discover.
- Discover queue rows: 6-column grid with min ~802px (`layout.css:1338`),
  collapsing to 4 columns at ≤1100px (`layout.css:1620-1628`) and 2 at ≤720px
  (`layout.css:1652-1660`) — the most complete responsive treatment in the app.
- `white-space: nowrap` risks: `.demo-state-badge` (`demo-now.css:113`,
  relaxed at ≤720px via `demo-now.css:316`), `operator-control.css:102`;
  ellipsis pattern done right at `imp-product.css:773-776`.
- Density assumptions: `.data-table` 13px/6-8px padding (`layout.css:975-986`),
  dense radar 0.78rem (`imp-product.css:517`) — desktop-density; no
  coarse-pointer target sizing except mode launcher (44px,
  `mode-session.css:52-55`).

## Test inventory & coverage map

### Runner & config
- **Vitest 2.1.3 + jsdom 29 + @testing-library/react 16.3 + jest-dom 7**
  (`ui/package.json:24-33`). `npm test` → `node scripts/run-vitest.mjs`, a
  programmatic `startVitest` wrapper (run mode, globals, jsdom, `css: true`,
  setup `./src/test/setup.ts`) — `ui/scripts/run-vitest.mjs:1-16`. Setup
  registers jest-dom matchers + auto cleanup (`ui/src/test/setup.ts`).
- `vite.config.ts:22-26` carries an equivalent `test` block; the script
  passes `config: false` and re-declares everything inline.
- No coverage tooling, no axe/jest-axe/pa11y, no visual-regression tooling
  anywhere in the repo (grep-verified).

### UI test files: 113 total (44 `.test.ts` + 69 `.test.tsx`)
- **Integration**: `ui/src/App.test.tsx` (1170 lines, ~50 tests) — mode
  launcher gate; Demo/Paper/Live entry for Now, Portfolio, Explore, Research,
  Discover; all 10 workspace lanes × 3 modes (via `it.each`,
  `App.test.tsx:980-1013`); settings × 3 modes; live canary; diagnostics;
  assistant history; skip-link + Ctrl+K/`?`/`A` shortcuts; scrub confirm +
  failure; lane draft handoffs; attention handoff; mode-switch route reset.
  Heavy fetch/hook mocking (`App.test.tsx:198-413`).
- **Smoke**: `ui/src/smoke.test.ts` (chartTransforms + research schema),
  `ui/src/smoke/appShell.smoke.test.ts` (query-key isolation invariants).
- **Component tests (`.test.tsx`)**: mode-session (ModeSession,
  ModeEnvironmentBar), paper-now (PaperNowPage incl. CSS media assertions,
  PaperPanels, PaperCandidateQueue), paper workspace (PaperWorkspacePage,
  PaperDecisionCockpit, PaperDecisionSnapshot, PaperHandoffPanel,
  PaperPreviewStatus), paper-portfolio (PaperPortfolioPage,
  PaperOrderHistory), paper-research, paper-explore, paper-discover,
  demo-now/…/demo-discover (6), live-now/…/live-discover (6+),
  live (ProviderHealthPanel, LiveCanaryControlPlanePage), workspace-module-shared
  (WorkspaceModuleModeShell, ModeWorkspaceRoutes, LaneModeContextPanel,
  paperLaneAuthority), squeeze (3), options (2), futures, institutional,
  imp-product (8: chrome, KPI strip, queues, capability strip, posture,
  feed banner, dense panel, top cards), now/OpportunityReviewCard,
  research/SimulationLabPanel, shared/InstrumentSelectionEmpty,
  paper/OrderTicket + ExecutionTracePanel, WorkspaceModuleNav.sticky.
- **Pure-logic tests (`.test.ts`)**: api layer (schemas, queryKeys,
  queryKeyFactory, fetchJson, errors, paperStrategyProfitability),
  workspace-module-shared (laneRegistry drift guard, buildLaneModeContent,
  laneProvenance, laneQueryState, workspaceModuleModeDescription),
  paper-workspace builders (5), paper-now (paperOrderDraft,
  paperDashboardViewModel), paper-portfolio models (2), paper provenance/
  timestamps (3), live view models (2), imp-product (3), charts (3),
  mode-session (modeAuthority, modeMetadata), operator-settings,
  lib/isTypingTarget, exploreCatalyst, squeezeWorkspace.

### E2E package (`projects/integrated-market-platform/e2e`)
- Playwright 1.49, single Chromium project, `workers: 1`, retries only in CI,
  baseURL `http://127.0.0.1:5173` (`e2e/playwright.config.ts`); expects the
  Vite dev server proxying to a real backend at `127.0.0.1:8766` and control
  plane at `8767` (`ui/vite.config.ts:5-7,28-62`).
- 6 specs: `routing.spec.ts` (G15 route round-trip equity/option/futures),
  `product-status.spec.ts`, `paper-equity.spec.ts`, `paper-derivative.spec.ts`,
  `live-safety.spec.ts`, `isolation.spec.ts`; `helpers.ts` drives mode entry,
  client-side nav, paper order preview/submit. No a11y or viewport-matrix
  coverage. **Do not run during the live trading session** (real backend +
  ports).

## Build/lint/CI gates

Exact commands (repo root unless noted):
- UI tests: `cd ui && npm test` (vitest run).
- UI typecheck: `cd ui && npm run typecheck` (`tsc --noEmit -p
  tsconfig.typecheck.json`).
- UI build + budget: `cd ui && npm run build` (`vite build && node
  scripts/check-bundle-budget.mjs`).
- Repo lint: `python tools/imp.py lint` — Python `compileall` plus UI
  typecheck when changed files touch `ui/` (`tools/imp.py:1047-1072`).
- Manifest validation: `python tools/imp.py validate changed` — the
  `frontend_ui` partition maps `ui/src/**`, `ui/package.json`,
  `ui/vite.config.ts`, `ui/tsconfig*.json` to owner suite `ui1`
  (`tools/validation_manifest.json:2446-2457`), which is the **Python** UI-API
  pytest suite (`tests/ui1`, manifest lines 1065-1092) — it does not run
  vitest.
- Closure: `python tools/imp.py closure` — full validation + `git diff
  --check` + docs-link check +, when `ui/` changed, `npm test -- --run`,
  `npm run typecheck`, `npm run build` (`tools/imp.py:1132-1186`); writes
  `artifacts/developer-workflow/closure-report.json`.
- E2E (only when safe): `cd e2e && npm test`.

**A UI-only branch is green when**: `npm test`, `npm run typecheck`,
`npm run build` (budget passes) in `ui/`, plus `python tools/imp.py lint` and
`python tools/imp.py validate changed` at repo root; `closure` before merge.

**200 KiB budget mechanics**: `ui/scripts/check-bundle-budget.mjs` reads
`dist/.vite/manifest.json`, walks the single entry's static import graph,
gzips each initial file, and fails if the sum exceeds **203 × 1024 bytes
(203 KiB)** (line 6) — note the documented budget is 200 KiB
(`PERFORMANCE.md:7`), so there is a 3 KiB enforcement cushion. Lazy chunks
fail above 500 KB raw, except `vela-*` chunks (950 KB) which are also banned
from the entry graph (lines 8, 45-48, 61-64). Last recorded baseline:
**199.17 KiB gzip (2026-09-01)** (`PERFORMANCE.md:12`) — ~0.8 KiB under the
documented budget. `vite.config.ts:14-18` manualChunks isolates `recharts`,
`victory-vendor` (`chart-primitives`), and `@luxalgo/vela`.

## Performance guards

- **Polling** (`ui/src/api/hooks.ts`): workspace order-flow/order-book 2s and
  evidence 5s, live-mode only (lines 125, 137, 164, 433); provider health 5s
  unconditional (line 353); canary snapshot/reconciliation 15s with
  `staleTime` + `enabled` gating (lines 356-373); `LiveCanaryControlPlanePage.tsx:45`
  15s; discover mixed mode 3s poll + 120s refresh with `visibilitychange`
  pause (`DiscoverObservability.tsx:237-276`); chart lab tick interval
  (`ImpVelaChartLabPage.tsx:33`).
- **Memoization is sparse**: only ~10 files use `useMemo`/`useCallback`
  (notably `AuthProvider.tsx`, `DiscoverObservability.tsx`,
  `OpportunityRadarCockpit.tsx`, `WorkspacePriceChart.tsx`); no `React.memo`
  found. Re-render cost is handled by query-key discipline rather than memo.
- **Charts**: `lightweight-charts` 4.2 (primary), `recharts` 2.15 (research
  panels, lazy), `@luxalgo/vela` 0.7.1 (lazy shadow engine)
  (`ui/package.json:14-21`).
- **Lazy loading**: all lane routes, assistant sidecar/history, settings,
  control center, provider health, canary, research, context trust layer are
  `React.lazy` (`App.tsx:53-154`); `fetchJson` dynamically imports the error
  envelope parser to keep it off the entry chunk (FRONTEND_GUIDE.md:72-76).
- **Animations are restrained**: mode-rise 420-480ms + progress sweep
  (`mode-session.css:81,125,322,433-444`), sidebar 0.2s
  (`imp-product.css:671`), risk-meter 160-180ms (`paper-now.css:37`,
  `demo-now.css:171`); all have `prefers-reduced-motion` cutoffs.

## Observations & risks

1. **Drawer focus gap is the top a11y defect**: ExplanationDrawer,
   InspectorPanel, ImpProviderMatrixDrawer open without focus movement, trap,
   or restore (`ExplanationDrawer.tsx:10`, `InspectorPanel.tsx:28`,
   `ImpProviderMatrixDrawer.tsx:24`). The redesign's overlay/drawer system
   must build on `useFocusTrap.ts` + the `LiveModeConfirmation.tsx` pattern.
2. **Chart accessibility is half-done**: tabular summary exists for bar
   charts only (`ResearchChartPanels.tsx:63-79`); the primary workspace price
   chart has no text alternative at all (`WorkspacePriceChart.tsx:89`).
3. **Palette needs token-level contrast fixes before restyle**:
   `--text-muted #6b7280` (~4.0:1) and `--direction-short #c44e52` (~4.2:1)
   fail/borderline-fail AA at the sizes used (`tokens.css:13,16`).
4. **Breakpoint sprawl**: 9 distinct width values across 12 files with no
   shared scale; most page stylesheets have no media queries; the 901-1100px
   band (sidebar inline + possible 360px drawer) is the highest-risk range
   for the 1024/1280/1366 targets.
5. **No automated a11y or visual/viewport regression testing**: responsive
   behavior is pinned only by CSS string assertions
   (`PaperNowPage.test.tsx:270-273`); jsdom never lays out. The redesign's
   hard requirements (no horizontal scroll at 7 widths, WCAG landmarks) need
   new automation — e.g. axe-core in vitest and Playwright viewport-matrix +
   axe runs (to be executed only when no live session is running).
6. **Tier encoding is border-color only** (`layout.css:264-266`,
   `AttentionFeed.tsx:29`) — add visible tier text/badge in the redesign.
7. **Budget headroom is razor-thin**: 199.17 KiB recorded vs 200 KiB
   documented / 203 KiB enforced. Any new initial-path dependency will trip
   the build; keep everything new lazy.
8. **Unknowns**: contrast ratios were computed manually (verify with a tool);
   no runtime verification was possible (live session constraint);
   `validate changed` on a UI-only branch exercises the Python `ui1` suite,
   not the React app, so UI workers must run the npm gates explicitly;
   e2e specs require real backend ports 8766/8767 and must stay off during
   trading sessions.
