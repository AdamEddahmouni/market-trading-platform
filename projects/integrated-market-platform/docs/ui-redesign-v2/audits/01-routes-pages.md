# Routes & Pages Inventory

Audit scope: every route, page component, navigation/shell structure, mode-routing mechanism, and
concept location in the IMP UI, plus a draft migration map into the redesign IA
(COMMAND / RADAR / WORKSPACE / PORTFOLIO / RESEARCH / LAB / CONTROL).

- Codebase: `ui/` (React 18 + TypeScript, Vite, react-router-dom v6 `BrowserRouter`, TanStack Query).
- Entry: `ui/src/main.tsx` → `ui/src/App.tsx`.
- All routes live in exactly two files: `ui/src/App.tsx` (top-level `<Routes>`) and
  `ui/src/components/ModeResearchRoute.tsx` (nested `/research/*` routes). A codebase-wide grep for
  `<Route` / `createBrowserRouter` / `useRoutes` confirms no other routers exist outside tests.
- All data access goes through `ui/src/api/hooks.ts` (`queryKeys`, lines 7–64) and
  `ui/src/api/endpoints.ts` (`api` object, lines 51–250), plus `ui/src/api/opportunityClient.ts`
  (opportunity summary/evidence/ack) and `ui/src/api/tradeReviewClient.ts` (trade reviews).
- Mode (DEMO / PAPER / LIVE) is **React state**, not URL: held in
  `ui/src/components/mode-session/ApplicationBootstrap.tsx:28` (`selectedMode`). Reloading the page
  always returns to the mode launcher. "Switch mode" navigates to `/` and resets to the launcher
  (`App.tsx:317-321`).

Counts: **25 top-level route entries** (23 page paths + `/lab` redirect + `*` catch-all) + **2 nested
research routes**; **42 page/route components** (18 mode pages, 10 workspace-lane route components,
6 standalone pages, 8 route wrappers); **12 nav items** (9 primary + 3 operator) over **11 unique
targets**.

---

## Route table

All routes render inside `WorkstationShell` (`App.tsx:186-588`), wrapped by `ImpProductChrome`
(`App.tsx:351`). "Lazy" below means the page component is behind `React.lazy`; the five
`Mode*Route` wrappers themselves are eagerly imported in `App.tsx:19-22` except where noted.

| # | Path | Component (file) | Lazy? | Purpose (1 sentence) | Mode variants | Data hooks / queryKeys | Mutations | Notable UI |
|---|------|------------------|-------|----------------------|---------------|------------------------|-----------|------------|
| 1 | `/` | `ModeNowRoute` desk="overview" (`components/ModeNowRoute.tsx:89-94`) → `DemoNowPage` / `PaperNowPage` / `LiveNowPage` | Wrapper eager; pages lazy (`ModeNowRoute.tsx:6-14`) | Mode-specific "what matters now" overview desk (KPI strip + attention queue + opportunities). | DEMO: replay overview + portfolio summary (`demo-now/DemoNowPage.tsx:103-142`); PAPER: "Paper Command" candidate queue + draft composer (`paper-now/PaperNowPage.tsx:118-137`); LIVE: "Live Watch" provider ribbon + safety snapshot (`live-now/LiveNowPage.tsx:85-116`) | `attention`, `replaySession`, `context`, `assistantStatus` (shell, `App.tsx:200-203`); `paperPortfolio` (Demo/Paper routes, `ModeNowRoute.tsx:26,36`); `providerHealth`, `liveCanarySnapshot("now")` (Live, `ModeNowRoute.tsx:58-60`); `opportunitiesSummary` (all three pages) | PAPER only: order preview (`usePreviewPaperOrderMutation`), opportunity ack (`useOpportunityAckMutation`) (`PaperNowPage.tsx:47-48`); replay scrub POST `/replay/scrub` via shell (`App.tsx:290-300`) | `ImpOverviewBoard` KPI strip + primary queue, `AttentionFeed`, replay scrub slider (Demo), `PaperCandidateQueue`/`PaperPreviewComposer`/`PaperRiskRibbon` (Paper), `LiveProviderRibbon`/`LiveSafetySnapshot`/`LiveSymbolLookup` (Live) |
| 2 | `/signals` | `ModeNowRoute` desk="signals" (`App.tsx:348`) → same three Now pages | Same as `/` | Same component as `/` with `desk="signals"`: attention-queue-centric "Signals desk" variant. | All three modes (per-mode Signals desk copy, e.g. `DemoNowPage.tsx:108-113`) | Same as `/` | Same as `/` (PAPER preview/ack) | Same building blocks; hides portfolio summary in Demo, keeps `AttentionFeed` |
| 3 | `/explore` | `ModeExploreRoute` (`components/ModeExploreRoute.tsx:25-29`) → `DemoExplorePage` / `PaperExplorePage` / `LiveExplorePage` | Wrapper eager; pages lazy | "Markets" in nav, "Explore" in page H1: read-only donor screener bridges (squeeze cohort, scanner, futures, catalyst). | DEMO/PAPER/LIVE pages are thin shells over shared `ExploreObservability` (`explore-shared/ExploreObservability.tsx:90`); LIVE adds `LiveObservationalPanel` (`live-explore/LiveExplorePage.tsx:29`) | `exploreSqueeze`, `exploreSqueezeScanner`, `exploreFutures`, `exploreCatalyst` (`ExploreObservability.tsx:91-94`); Live panel: `symbolSearch`, `instrumentCapabilities`, `providerHealth` (`live/LiveObservationalPanel.tsx:10-12`) | LIVE panel only: `useSubscribeMutation` POST `/subscriptions`, POST `/operator/recent` (`LiveObservationalPanel.tsx:13,51-55`) | Screener tables with symbol links to workspace, provenance grids, `CountBarChartPanel`, disclaimers; live symbol search + subscribe panel |
| 4 | `/discover` | `ModeDiscoverRoute` (`components/ModeDiscoverRoute.tsx:25-29`) → `DemoDiscoverPage` / `PaperDiscoverPage` / `LiveDiscoverPage` | Wrapper eager; pages lazy | "Opportunity Radar": ranked opportunity queue cockpit + mixed live screener. | DEMO read-only (`demo-discover/DemoDiscoverPage.tsx:34-40`); PAPER full discovery desk with mutations (`paper-discover/PaperDiscoverPage.tsx:28-38`); LIVE read-only monitor | `opportunitiesSummary`, `opportunityEvidence(rowId)` (`imp-product/OpportunityRadarCockpit.tsx:29,49-52`); mixed screener via raw fetch in `discover-shared/DiscoverObservability.tsx` | PAPER only (`allowMutations`): POST `/discover/mixed/refresh`, POST `/discover/promote-to-live-analysis`, POST `/discover/mixed/release` on unmount (`DiscoverObservability.tsx:165-168,203-206,228-231`) | `OpportunityRadarCockpit` (dense table + `ProgressiveOpportunityCard` detail), `OpportunityFeedStatusBanner`, mixed screener candidate table |
| 5 | `/workspace` | `WorkspaceIndex` (`components/WorkspaceIndex.tsx:8-28`) | Lazy (`App.tsx:147-149`) | Index redirect: LIVE → active/scoped instrument workspace or instrument-selection empty state; otherwise → admitted replay instrument workspace. | Mode-aware via `context` (`data_mode === "LIVE_OBSERVATIONAL"`) | `context` (`WorkspaceIndex.tsx:9`) | None | `LoadingState`, `InstrumentSelectionEmpty`, `<Navigate>` redirects |
| 6 | `/lab` | `<Navigate to="/research" replace>` (`App.tsx:404`) | n/a | Redirect alias; nav "Lab" points at `/research` directly. | n/a | n/a | n/a | n/a |
| 7 | `/workspace/:symbol` | `WorkspaceRoute` (`components/WorkspaceRoute.tsx:21-81`) → `ModeWorkspacePage` → `DemoWorkspacePage` / `PaperWorkspacePage` / `LiveWorkspacePage` | Lazy (`App.tsx:144-146`); mode pages lazy (`ModeWorkspacePage.tsx:6-19`) | Instrument workspace overview (cockpit): chart/replay, lane evidence ("what matters now"), squeeze panel; PAPER adds decision cockpit with order ticket. | DEMO read-only (`demo-workspace/DemoWorkspacePage.tsx:14-44`); PAPER `PaperDecisionCockpit` + forward tests (`paper-workspace/PaperWorkspacePage.tsx:64-109`); LIVE read-only (`live-workspace/LiveWorkspacePage.tsx:14-44`) | `instrument(symbol)` (replay instrument only), `workspaceSqueeze(symbol)` (`WorkspaceRoute.tsx:46-47`); `context`, `workspaceEvidence(symbol)` (`workspace-shared/WorkspaceObservability.tsx:39-40`); PAPER: `paperPortfolio`, `paperForwardTests` (`PaperWorkspacePage.tsx:38,41`); LIVE market panel: `marketState`, `workspaceOrderFlow` (`live/LiveMarketPanel.tsx:14-15`) | PAPER only: order preview/submit/session-open in `OrderTicket` (`paper/OrderTicket.tsx:61-64`); fire-and-forget POST `/operator/workspace` layout persistence (`WorkspaceObservability.tsx:87-101`); replay scrub via shell | `WorkspaceModuleNav` (11-tab lane nav), `WhatMattersNowPanel`, `WorkspacePriceChart` + replay slider, derived-features grid, `SqueezeWorkspacePanel` compact, `WorkspaceEvidenceDrawer`, `PaperDecisionCockpit` (handoff/snapshot/risk/ticket), `PaperForwardTestPanel`, `ExecutionTracePanel` |
| 8 | `/workspace/:symbol/squeeze` | `ModeSqueezeWorkspaceRoute` (`components/squeeze/ModeSqueezeWorkspaceRoute.tsx:19-42`) | Lazy (`App.tsx:64-68`) | Short-squeeze lane module (state transitions, historical context, causal/catalyst blocks). | Mode shell headers + restriction notes via `WorkspaceModuleModeShell`; content `SqueezeWorkspaceObservability` | `workspaceSqueeze(symbol, dataMode)`; supports `?data_mode=current` query param (`ModeSqueezeWorkspaceRoute.tsx:21-23`) | None (read-only lane) | `WorkspaceModuleNav`, mode restriction note, state-transition block, historical context, cross-lane evidence |
| 9 | `/workspace/:symbol/order-flow` | `ModeOrderFlowWorkspaceRoute` (`components/orderflow/ModeOrderFlowWorkspaceRoute.tsx`) | Lazy (`App.tsx:69-73`) | Order-flow lane module. | Same shell pattern | `workspaceOrderFlow(symbol)` (`orderflow/OrderFlowWorkspaceObservability.tsx:17`); 2s refetch when live (`hooks.ts:125`) | None | Lane panels per module shell |
| 10 | `/workspace/:symbol/order-book` | `ModeOrderBookWorkspaceRoute` (`components/orderbook/ModeOrderBookWorkspaceRoute.tsx`) | Lazy (`App.tsx:85-89`) | Order-book (L2 depth) lane module. | Same shell pattern | `workspaceOrderBook(symbol)`; 2s refetch when live (`hooks.ts:161-164`) | None | Lane panels |
| 11 | `/workspace/:symbol/futures` | `ModeFuturesWorkspaceRoute` (`components/futures/ModeFuturesWorkspaceRoute.tsx`) | Lazy (`App.tsx:90-94`) | Futures lane module (incl. governed product view). | Same shell pattern | `workspaceFutures(symbol)`, `futuresProduct(symbol, mode)` (`futures/FuturesWorkspaceObservability.tsx:25-26`) | None | Lane panels |
| 12 | `/workspace/:symbol/catalyst` | `ModeCatalystWorkspaceRoute` (`components/catalyst/ModeCatalystWorkspaceRoute.tsx`) | Lazy (`App.tsx:95-99`) | Catalyst lane module. | Same shell pattern | `workspaceCatalyst(symbol)` (`catalyst/CatalystWorkspaceObservability.tsx:17`) | None | Lane panels |
| 13 | `/workspace/:symbol/fund-etf` | `ModeFundEtfWorkspaceRoute` (`components/fundetf/ModeFundEtfWorkspaceRoute.tsx`) | Lazy (`App.tsx:100-103`) | Fund/ETF lane module. | Same shell pattern | `workspaceFundEtf(symbol)` (`fundetf/FundEtfWorkspaceObservability.tsx:17`) | None | Lane panels |
| 14 | `/workspace/:symbol/options` | `ModeOptionsWorkspaceRoute` (`components/options/ModeOptionsWorkspaceRoute.tsx`) | Lazy (`App.tsx:74-78`) | Options lane module (chain + governed product view). | Same shell pattern | `workspaceOptions(symbol)`, `optionsProduct(symbol, mode)` (`options/OptionsWorkspaceObservability.tsx:30-31`) | None | Lane panels |
| 15 | `/workspace/:symbol/large-transactions` | `ModeLargeTransactionsWorkspaceRoute` (`components/largetransactions/ModeLargeTransactionsWorkspaceRoute.tsx`) | Lazy (`App.tsx:79-83`) | Large-transactions lane module. | Same shell pattern | `workspaceLargeTransactions(symbol)` (`largetransactions/LargeTransactionsWorkspaceObservability.tsx:17`) | None | Lane panels |
| 16 | `/workspace/:symbol/disclosure` | `ModeDisclosureWorkspaceRoute` (`components/disclosure/ModeDisclosureWorkspaceRoute.tsx`) | Lazy (`App.tsx:104-108`) | Disclosure lane module. | Same shell pattern | `workspaceDisclosure(symbol)` (`disclosure/DisclosureWorkspaceObservability.tsx:16`) | None | Lane panels |
| 17 | `/workspace/:symbol/institutional-flow` | `ModeInstitutionalFlowWorkspaceRoute` (`components/institutional/ModeInstitutionalFlowWorkspaceRoute.tsx`) | Lazy (`App.tsx:109-113`) | Institutional-flow lane module; aggregates cross-lane rows for related symbols. | Same shell pattern | `workspaceInstitutionalFlow(symbol)` (`institutional/InstitutionalFlowWorkspaceObservability.tsx:16`); panel also fans out to disclosure/order-flow/order-book/options/large-transactions/futures/catalyst/fund-etf queries for related symbols (`institutional/InstitutionalFlowWorkspacePanel.tsx:81-88`) | None | Lane panels, cross-lane aggregate table |
| 18 | `/research/*` | `ModeResearchRoute` (`components/ModeResearchRoute.tsx:36-45`) | Lazy (`App.tsx:150-153`) | Research home per mode with tabbed Analytics / Model Lab / Simulation. | `DemoResearchPage` / `PaperResearchPage` / `LiveResearchPage` over shared `ResearchObservability` (`research-shared/ResearchObservability.tsx:16`) | `researchAnalytics`, `researchModels`, `researchSimulation` (`ResearchObservability.tsx:19-21`); PAPER adds `paperStrategyProfitability` (`paper-research/PaperResearchPage.tsx:19`) | None | Tab bar (Analytics / Model Lab / Simulation), `ResearchAnalyticsPanel`, `ModelLabPanel`, `SimulationLabPanel`, `PaperStrategyProfitabilityObservability` (Paper) |
| 18a | `/research/vela-chart-lab` | `ImpVelaChartLabPage` (`components/charts/ImpVelaChartLabPage.tsx:15`) | Lazy (nested route, `ModeResearchRoute.tsx:40`) | Lane F lab: Vela chart adapter playground on a governed synthetic feed. | Mode-independent (rendered for all modes) | None (local synthetic feed) | None (local state only) | Chart adapter, tick-sim/backfill buttons |
| 19 | `/portfolio` | `ModePortfolioRoute` (`components/ModePortfolioRoute.tsx:44-48`) → `DemoPortfolioPage` / `PaperPortfolioPage` / `LivePortfolioPage` | Wrapper eager; pages lazy | Portfolio per mode: demo read-only snapshot, paper simulation account + order ticket + history, live broker-observed positions/orders. | DEMO (`demo-portfolio/DemoPortfolioPage.tsx`); PAPER (`paper-portfolio/PaperPortfolioPage.tsx:29`); LIVE (`live-portfolio/LivePortfolioPage.tsx:22`) | DEMO/PAPER: `paperPortfolio(viewMode)`; PAPER: `paperOrderHistory` (infinite), `paperTrace`, `paperStrategyProfitability`, raw GET `/paper/sessions`; LIVE: `liveCanarySnapshot("portfolio")`, `liveCanaryReconciliation` (`ModePortfolioRoute.tsx:26-27`) | PAPER only: open/close session, order preview/submit (`PaperPortfolioPage.tsx:31-32`, `OrderTicket.tsx:61-64`) | `PageHeader` with provenance meta, `OrderTicket`, `PaperPortfolioObservability`, `PaperOrderHistory`, `ExecutionTracePanel`, strategy profitability; LIVE: account summary grid, positions/orders tables, block-reason alerts |
| 20 | `/live-canary` | `LiveCanaryControlPlanePage` (`components/live/LiveCanaryControlPlanePage.tsx:40`) | Lazy (`App.tsx:139-143`) | Live canary control plane: real-money safety state, kill switches, incidents, reliability matrix, action queue (read-only). | Mode-aware copy; content identical across modes | `liveCanarySnapshot("canary-plane")`, raw `["canary-reliability"]` GET `/canary/reliability` (15s poll) (`LiveCanaryControlPlanePage.tsx:41-47`) | None (explicitly read-only; "No generic ENABLE LIVE button", line 209) | Critical banner "LIVE CANARY — REAL MONEY", status grids, health-matrix table, incident list |
| 21 | `/settings` | `OperatorSettingsPage` (`components/OperatorSettingsPage.tsx:35`) | Lazy (`App.tsx:115-118`) | Operator settings: provider/OpenD status, persistence state, paper sessions, captures, watchlist, safety env. | Mutations gated to PAPER via `canMutateOperatorSettings` (`operator-settings/operatorSettingsMode.ts:4-6`); read-only note in DEMO/LIVE | Raw fetch GET `/state/startup`, `/operator/state`, `/captures` (`OperatorSettingsPage.tsx:45-50`) | PAPER only: POST `/operator/watchlist`, POST `/captures/replay` (lines 61-73, 170-183) | Panels with metric lists, `JsonDetailPanel` raw JSON, watchlist input, capture replay buttons |
| 22 | `/control` | `OperatorControlCenterPage` (`components/OperatorControlCenterPage.tsx:14`) | Lazy (`App.tsx:129-133`) | "Operator center" (nav label: **Risk**): local platform lifecycle, readiness checks, provider readiness + credentials. | Mode-independent (no mode prop) | Raw via `api`: `getOperatorReadiness`, `getOperatorLifecycleStatus`, `getOperatorConfig` (no React Query keys) (lines 27-33) | Lifecycle actions (restart/check_update/apply_update), provider refresh, save provider config (lines 96-115, 44-57, 246-258) | Hero status panel, readiness check list, provider cards with per-provider refresh, credential forms (password inputs), related-links `<a href>` full-reload nav (lines 119-121) |
| 23 | `/diagnostics/provider` | `ProviderHealthPanel` (`components/live/ProviderHealthPanel.tsx:9`) | Lazy (`App.tsx:134-138`) | Provider diagnostics: Moomoo lifecycle, capability channel states (HEALTHY/DEGRADED/UNAVAILABLE), lag/quota metrics, Finviz auth state. | Mode-independent | `providerHealth` (5s poll, `hooks.ts:351-353`) | None | Metric list, active subscriptions list, `JsonDetailPanel` execution gate, Finviz section with CLI repair hint |
| 24 | `/assistant/history` | `AssistantHistoryPage` (`components/AssistantHistoryPage.tsx:5`) | Lazy (`App.tsx:55-59`) | Assistant conversation history; self-described "Secondary route — audited research prompts, not primary navigation" (line 14). | Mode-independent | `assistantConversations` (lines 6-9) | None | Simple list of conversations |
| 25 | `*` | `<Navigate to="/" replace>` (`App.tsx:539`) | n/a | Catch-all redirect to overview. | n/a | n/a | n/a | n/a |

Global overlays rendered outside `<Routes>` but inside the shell (`App.tsx:544-583`):
`AssistantSidecar` (lazy; `assistantStatus`, `assistantMessages` queries; creates conversation +
submits prompts via POST), `ExplanationDrawer` (explain refs), `InspectorPanel` (inspect refs with
tabbed JSON), assistant toggle button. Esc closes all (`App.tsx:233-243`).

---

## Navigation & shell

### Shell composition

`App` (`App.tsx:590-604`): `AuthProvider` → `OperatorLoginGate` → `QueryClientProvider` →
`BrowserRouter` → `ApplicationBootstrap` → `WorkstationShell`.

`WorkstationShell` renders `ImpProductChrome`
(`components/imp-product/ImpProductChrome.tsx:26-212`):

- **Sidebar** (`<aside>`, lines 146-175): brand block (`ImpBullMark` + "IMP / Integrated Market
  Platform" wordmark), `NavShell` (sidebar layout), footer "UI v1 · board 03 · Ctrl+K · ?".
  Mobile (≤900px) converts to an overlaid dialog with backdrop, focus trap, inert toggling.
- **Top bar** (lines 178-205): Menu toggle, `ImpCommandSearch`, `ImpExecutionPosture`, keyboard
  shortcuts `?` button, "Switch mode" button.
- **Top stack** (`App.tsx:355-378`): `ModeEnvironmentBar`, `ContextBar` (only when context loaded;
  fallback "Backend context is not available."), lazy `ImpContextTrustLayer`, `StartupRecoveryBanner`.
- **Dialogs**: `ImpKeyboardShortcuts` (shortcuts: Ctrl/Cmd+K, `/`, `A`, `Esc`, `?` —
  `ImpKeyboardShortcuts.tsx:4-9`).

### Primary nav (`components/NavShell.tsx:13-89`, rendered sidebar layout)

Order and labels (primary group, `nav-primary-group`):

| # | Label | Target | Notes |
|---|-------|--------|-------|
| 1 | Overview | `/` | `end` matching |
| 2 | Markets | `/explore` | mode hints: DEMO "Frozen bridges" / PAPER "Candidate discovery" / LIVE "Live scanner" |
| 3 | Opportunity Radar | `/discover` | `emphasis: "radar"` styling class |
| 4 | Signals | `/signals` | mode hints: "Replay attention" / "Attention queue" / "Live attention" |
| 5 | Research | `/research` | `gated: true` → renders "GATED" badge (`NavShell.tsx:131`) |
| 6 | Portfolio | `/portfolio` | |
| 7 | Workspace | `/workspace` | |
| 8 | Risk | `/control` | label/content mismatch — page is "Operator center" |
| 9 | Lab | `/research` | **duplicate target of #5** |

Operator group (`nav-operator-group`, `NavShell.tsx:90-102`), all `operatorOnly` styled:

| # | Label | Target |
|---|-------|--------|
| 10 | Live Canary | `/live-canary` |
| 11 | Settings | `/settings` |
| 12 | Diagnostics | `/diagnostics/provider` |

Every item shows a mode-dependent hint (`modeHint`) under the label. `/assistant/history` is
deliberately absent from nav.

### Workspace lane nav (`components/WorkspaceModuleNav.tsx` + `workspace-module-shared/laneRegistry.ts:3-25`)

Sticky tab bar on all 11 workspace surfaces, order fixed by `navOrder`:
Overview → Institutional Flow → Disclosure → Short Squeeze → Order Flow → Order Book → Futures →
Catalyst → Fund / ETF → Options → Large Transactions. Links are router `Link`s to
`/workspace/:symbol<suffix>`; squeeze preserves `?data_mode=current`.

### Status badges and what drives them

| Badge / strip | Where rendered | Driven by |
|---------------|----------------|-----------|
| Active environment (DEMO/PAPER/LIVE + boundary copy "Historical research · No execution" etc.) | `ModeEnvironmentBar` (`mode-session/ModeEnvironmentBar.tsx:10-14,49-60`) | `mode` prop + `evaluateModeContext(mode, context.as_of_context)` |
| "Backend aligned · DATA … · EXEC … · AUTH …" / "Backend context unavailable. Execution controls remain locked." / mismatch alert | `ModeEnvironmentBar` (lines 20-45) | `evaluateModeContext` (`mode-session/modeAuthority.ts:27-56`) comparing UI mode vs backend `data_mode`/`execution_mode`/`execution_authority` |
| ContextBar segments: DATA (e.g. "LIVE OBSERVATIONAL · MOOMOO"), EXECUTION, AUTH, MARKET/AS OF, SCOPE, QUALITY/HEALTH badge | `ContextBar` (`components/ContextBar.tsx:26-63`) | `useContextQuery()` payload; QUALITY/HEALTH shows `quality_summary.state` and click → `/diagnostics/provider` (`App.tsx:364-367`) |
| Execution posture: "Demo · historical research" / "Paper · internal simulation" / "Live · observation only" + paper account id + "Live off" lock | `ImpExecutionPosture` (`imp-product/ImpExecutionPosture.tsx:8-29`) | `mode` + `usePaperPortfolioQuery("PAPER", mode==="PAPER")`; lock is static copy |
| Capability chips (●/◐/○ ok/warn/muted) + "Provider matrix" button | `ImpCapabilityStrip` via `ImpContextTrustLayer` (`imp-product/ImpContextTrustLayer.tsx:10-25`) | `context.capability_states`; drawer `ImpProviderMatrixDrawer` adds `operatorReadiness` (enabled when open) |
| Startup recovery banner ("Previous paper session detected…" / "Local state database failed integrity check…") | `StartupRecoveryBanner` (`App.tsx:157-179`) | Raw GET `/state/startup` `crash_recovery` field |
| Page-level mode eyebrows/badges: "Demo · Historical research" + "Observational …" badge; "Paper-only simulation"; "Live · Read-only observational" | Each mode page header + `WorkspaceModuleModeShell` headers (`workspace-module-shared/WorkspaceModuleModeShell.tsx:29-104`) | `mode` prop only |
| Live canary critical banner "LIVE CANARY — REAL MONEY — HUMAN CONFIRMATION REQUIRED" | `LiveCanaryControlPlanePage.tsx:60-72` | Static + snapshot fields |
| Provider channel states HEALTHY / DEGRADED / UNAVAILABLE | `ProviderHealthPanel.tsx:5-8` | `account_entitled` + `runtime_tested` per capability |

### Command search & shortcuts

`ImpCommandSearch` (`imp-product/ImpCommandSearch.tsx:12-43`): ticker-pattern input →
`/workspace/:symbol`; anything else → `/explore?q=<query>`. **No component reads `q`** (grep for
`useSearchParams`/`location.search` across `ui/src/components` finds only squeeze `data_mode` and a
chart shadow util) — the `/explore?q=` fallback currently lands on a page that ignores the query.

---

## Mode routing

- Mode selection happens **before** any route renders: `ApplicationBootstrap`
  (`mode-session/ApplicationBootstrap.tsx:20-107`) runs a readiness task, shows `ModeLauncher`
  (three mode cards; LIVE requires `LiveModeConfirmation` dialog, `ModeLauncher.tsx:34-42`), then
  `ModeTransition` (per-mode readiness), then mounts `WorkstationShell` with the chosen `mode`.
- Mode is **not in the URL and not persisted**: `selectedMode` is `useState`
  (`ApplicationBootstrap.tsx:28`); reload → launcher. "Switch mode" → `navigate("/", {replace:true})`
  + reset (`App.tsx:317-321`).
- Every mode-aware route uses the same wrapper pattern: `Mode*Route` switches on `mode` and renders
  `Demo*` / `Paper*` / `Live*` page variants (e.g. `ModeNowRoute.tsx:89-94`,
  `ModeExploreRoute.tsx:25-29`, `ModeDiscoverRoute.tsx:25-29`, `ModePortfolioRoute.tsx:44-48`,
  `ModeWorkspacePage.tsx:27-45`, `ModeResearchRoute.tsx:30-34`).
- Backend-authority guard: `evaluateModeContext` (`mode-session/modeAuthority.ts:27-56`) compares
  the selected mode against backend context; mismatch → alert banner, paper actions locked.
  `paperActionsPermitted` = PAPER mode + compatible backend + auth capability `paper.order.submit`
  (`App.tsx:209-213`; role capabilities in `auth/AuthProvider.tsx:26-47`: VIEWER/OPERATOR/ADMIN).
- Auth gate: `OperatorLoginGate` (`auth/OperatorLoginGate.tsx`) blocks the app behind principal
  sign-in only when `/auth/status` reports `session_required`.
- Paper order submit is possible only from the Workspace cockpit (`OrderTicket` inside
  `PaperDecisionCockpit`) and Paper Portfolio, with a current preview; Paper Now drafts intent and
  navigates to the workspace carrying a `PaperOrderDraft` in router `location.state`
  (`paper-now/PaperNowPage.tsx:94-106` → `WorkspaceRoute.tsx:36-39` `parsePaperOrderDraft`, PUSH-only,
  cleared after read at `WorkspaceRoute.tsx:42-44`).
- Operator settings mutations are Paper-only (`operator-settings/operatorSettingsMode.ts:4-6`);
  Discover mutations are Paper-only (`allowMutations` prop); Live surfaces are read-only by
  convention (no mutations) plus explicit copy.

---

## Concept locations

| Concept | Today's route | Today's component(s) | Notes |
|---------|---------------|----------------------|-------|
| Overview | `/` | `ModeNowRoute` desk="overview" → `DemoNowPage` / `PaperNowPage` ("Paper Command") / `LiveNowPage` ("Live Watch") with `ImpOverviewBoard` | Exists |
| Markets / Explore | `/explore` (nav label "Markets", H1 "Explore") | `ModeExploreRoute` → mode Explore pages → `ExploreObservability` | Exists; label mismatch (Markets vs Explore) |
| Opportunity Radar / Discover | `/discover` (nav + H1 "Opportunity Radar") | `ModeDiscoverRoute` → mode Discover pages → `OpportunityRadarCockpit` + `DiscoverObservability` | Exists |
| Signals | `/signals` | Same `ModeNowRoute` with `desk="signals"` ("Signals desk") | Exists, but is a **desk variant of `/`**, not an independent page |
| Workspace | `/workspace` (index redirect) + `/workspace/:symbol` + 10 lane routes | `WorkspaceIndex`, `WorkspaceRoute` → `ModeWorkspacePage` → mode workspace pages; lanes via `Mode*WorkspaceRoute` × 10 | Exists |
| Research | `/research` | `ModeResearchRoute` → mode Research pages → `ResearchObservability` (tabs: Analytics / Model Lab / Simulation) | Exists |
| Portfolio | `/portfolio` | `ModePortfolioRoute` → mode Portfolio pages | Exists |
| Risk | `/control` (nav label "Risk") | `OperatorControlCenterPage` (H1 "Operator center") | **Name/content mismatch**: page is local platform control (lifecycle, providers, credentials), not a risk surface; risk-adjacent content actually lives in `PaperRiskRibbon`, `PaperRiskContext`, live canary kill switches |
| Lab / Model Lab | nav "Lab" → `/research`; `/lab` redirects to `/research`; Model Lab is a **tab** inside Research; `/research/vela-chart-lab` subroute | `ModelLabPanel`, `SimulationLabPanel`, `ImpVelaChartLabPage` | Exists only as tabs/alias, not a standalone section |
| Diagnostics | `/diagnostics/provider` | `ProviderHealthPanel` | Exists (operator group); also reached via ContextBar QUALITY/HEALTH click |
| Settings | `/settings` | `OperatorSettingsPage` | Exists (operator group) |
| Live Canary | `/live-canary` | `LiveCanaryControlPlanePage` | Exists (operator group) |
| Assistant | global sidecar (no nav item) + `/assistant/history` | `AssistantSidecar`, `AssistantHistoryPage` | Exists as overlay + secondary route |
| Command palette | top-bar `ImpCommandSearch` (not a route) | — | Exists in primitive form (ticker → workspace, else dead `?q=`) |

---

## Draft migration map

Target IA: COMMAND, RADAR, WORKSPACE, PORTFOLIO, RESEARCH, LAB, CONTROL. "Stays-as-route" keeps a
deep-linkable URL; "tab"/"drawer"/"panel" demote into a parent surface. `?` = uncertainty — no
backend capability invented.

| Current route | Proposed destination | Rationale | Functional-parity risks |
|---------------|----------------------|-----------|-------------------------|
| `/` (Overview) | **COMMAND** primary page (stays-as-route, e.g. `/` or `/command`) | Already the "what matters now" desk per mode; matches L1 principle | Mode-specific desk variants (Demo replay scrubber, Paper command composer, Live watch) must all survive; replay scrub is shell-level state (`App.tsx:290-300`) |
| `/signals` | **COMMAND** tab/state ("Signals desk") + redirect-alias `/signals` | Same component as `/` with `desk` flag; a route per desk variant is sprawl | Existing deep links; desk flag currently changes data emphasis (hides portfolio summary in Demo) — tab must preserve both layouts |
| `/explore` (Markets) | **RADAR** tab "Markets / Screeners" (redirect-alias `/explore`) ? | Screener bridges are discovery-adjacent; merging with Radar unifies discovery IA. Alternative: keep as RADAR sibling page if table density demands it | Live `LiveObservationalPanel` subscribe flow is embedded here; four explore queryKeys must keep polling behavior; dead `?q=` param could be fixed or dropped |
| `/discover` (Opportunity Radar) | **RADAR** primary page (stays-as-route) | Already the operator discovery cockpit | Paper-only mutations (refresh/promote/release) incl. unmount release POST must be preserved; cockpit two-pane layout is dense |
| `/workspace` | **WORKSPACE** index (stays-as-route, redirect logic preserved) | Smart redirect to active/admitted instrument is useful | LIVE instrument-selection empty state must remain reachable |
| `/workspace/:symbol` | **WORKSPACE** primary page (stays-as-route) | The cockpit; paper order submit lives here | `location.state` paper-draft handoff (PUSH-only) is fragile — redesign should keep or formalize it; replay chart only for admitted instrument BIYA; layout persistence POST `/operator/workspace` |
| `/workspace/:symbol/squeeze` (+ `?data_mode=current`) | **WORKSPACE** tab (stays-as-route for deep link) | Already presented as lane tab via `WorkspaceModuleNav` | `data_mode=current` query param must survive; lane nav order/provenance labels derive from `laneRegistry.ts` (backend provenance contract — see registry comment lines 47-52) |
| `/workspace/:symbol/order-flow` | WORKSPACE tab (stays-as-route) | Lane tab | 2s live refetch cadence |
| `/workspace/:symbol/order-book` | WORKSPACE tab (stays-as-route) | Lane tab | 2s live refetch cadence |
| `/workspace/:symbol/futures` | WORKSPACE tab (stays-as-route) | Lane tab | `futuresProduct` mode-scoped query |
| `/workspace/:symbol/catalyst` | WORKSPACE tab (stays-as-route) | Lane tab | — |
| `/workspace/:symbol/fund-etf` | WORKSPACE tab (stays-as-route) | Lane tab | — |
| `/workspace/:symbol/options` | WORKSPACE tab (stays-as-route) | Lane tab | `optionsProduct` mode-scoped query |
| `/workspace/:symbol/large-transactions` | WORKSPACE tab (stays-as-route) | Lane tab | — |
| `/workspace/:symbol/disclosure` | WORKSPACE tab (stays-as-route) | Lane tab | — |
| `/workspace/:symbol/institutional-flow` | WORKSPACE tab (stays-as-route) | Lane tab | Fans out to 8 other lane queries for related symbols — heaviest lane |
| `/research` (home) | **RESEARCH** primary page (stays-as-route) | Replay-bound analytics surface | Tab state is local `useState` (`ResearchObservability.tsx:17`) — making tabs routable changes back-button behavior |
| `/research` → Analytics tab | RESEARCH tab | Fits RESEARCH | — |
| `/research` → Model Lab tab | **LAB** tab "Model Lab" ? | Target IA separates LAB from RESEARCH; current app conflates (nav "Lab" → `/research`) | Splitting means moving `researchModels` surface; `PaperResearchPage` defaults to simulation tab — default-tab wiring per mode must be rethought |
| `/research` → Simulation tab | **LAB** tab "Simulation Lab" ? | Simulation lab is experiment tooling | Same split concern |
| `/research/vela-chart-lab` | **LAB** page/tab "Chart Lab" (stays-as-route or redirect-alias) | Self-contained lab playground | Lazy chunk + synthetic feed; no backend dependency |
| `/lab` redirect | Repoint to **LAB** primary (currently → `/research`) | Today it aliases the conflated page | Trivial redirect change; update nav |
| Paper strategy profitability (in Paper Research + Portfolio) | RESEARCH advanced panel or PORTFOLIO tab ? | Sits awkwardly in both today (`PaperResearchPage.tsx:19`, `PaperPortfolioPage.tsx:13`) | Decide single home; keep `paperStrategyProfitability` query scoping |
| `/portfolio` | **PORTFOLIO** primary page (stays-as-route) | Mode portfolio views already coherent | Paper session open/close mutations + order ticket + infinite order history + trace panel must all survive; LIVE view depends on canary snapshot/reconciliation |
| `/control` (nav "Risk") | **CONTROL** primary page (rename nav to "Control") | Page is operator control center; target IA has CONTROL | Resolves Risk/Operator-center mismatch; lifecycle/credential mutations need operator gating copy preserved; `<a href>` links cause full reloads — convert to router links |
| `/live-canary` | **CONTROL** page "Live Canary" (stays-as-route, operator group) | Safety control plane belongs in CONTROL | Read-only invariant + critical banner must remain; 15s polling of snapshot + reliability |
| `/settings` | **CONTROL** tab/page "Settings" (stays-as-route or tab) | Operator housekeeping | Paper-only mutation gating per mode; raw fetch (non-React-Query) refresh patterns |
| `/diagnostics/provider` | **CONTROL** tab "Diagnostics" + keep route (ContextBar deep link) | ContextBar QUALITY/HEALTH badge navigates here (`App.tsx:364-367`) | Deep link must keep working or badge retargeted; 5s poll |
| `/assistant/history` | Drawer/panel inside assistant sidecar, or RESEARCH advanced panel; redirect-alias the route | Self-declared secondary route | Conversation list is the only resume entry point — sidecar currently creates a **new** conversation each open (`App.tsx:245-255`); parity requires a resume path |
| `*` catch-all | Keep → redirect to COMMAND | Safety net | — |
| Global: assistant sidecar, explanation drawer, inspector panel, command search, mode bar, context bar, capability strip | Global chrome in new shell (not section-scoped) | Cross-cutting provenance/explainability primitives | Esc/shortcut handling, focus traps, and the `A`/`?`/`Ctrl+K` shortcuts must be preserved |

---

## Observations & risks

1. **Research/Lab conflation**: nav has both "Research" (badged GATED) and "Lab" pointing to
   `/research`; `/lab` redirects there too (`NavShell.tsx:45-52,80-89`; `App.tsx:404`). The redesign's
   RESEARCH vs LAB split has no current counterpart — the Model Lab and Simulation "tabs" are local
   state, not routes.
2. **"Risk" nav label → Operator center**: `/control` renders local platform lifecycle/provider
   credential management (`OperatorControlCenterPage.tsx`), not risk. Actual risk UX is scattered
   (`PaperRiskRibbon`, `PaperRiskContext`, canary kill switches). CONTROL must absorb or cross-link
   these.
3. **`/` vs `/signals` duplication**: one route component, two routes, differ only by `desk` prop
   (`App.tsx:347-348`). Natural tab consolidation, but the two desks have genuinely different layouts
   per mode.
4. **Mode is invisible in the URL and lost on reload**: `selectedMode` is React state
   (`ApplicationBootstrap.tsx:28`); refresh → mode launcher. Deep links cannot encode mode; the
   redesign must decide whether mode stays session-scoped (current doctrine) or becomes URL-visible.
5. **Dead search fallback**: command search non-ticker queries navigate to `/explore?q=…`, but no
   component reads `q` (grep-verified). Either wire it or change the fallback target.
6. **Workspace lane sprawl**: 10 lane routes + overview, all real routes with a sticky tab nav whose
   order (Institutional Flow first, Squeeze fourth — `laneRegistry.ts:3-25`) doesn't match operator
   priority. `laneRegistry.ts` is a documented cross-boundary contract (backend paper provenance
   derives lane lists from it, lines 47-52) — reordering/relabeling lanes is not purely cosmetic.
7. **Paper draft handoff via router state**: Paper Now → Workspace order drafts ride
   `location.state` on PUSH navigation only, cleared immediately (`WorkspaceRoute.tsx:36-44`).
   Refresh/back loses drafts; any IA change to WORKSPACE must preserve or formalize this contract.
8. **Admitted-instrument hardcoding**: replay chart exists only for `BIYA`
   (`ADMITTED_REPLAY_INSTRUMENT_ID`, `api/schemas.ts:1712`; fallback in `WorkspaceRoute.tsx:33`);
   futures/catalyst demo instruments `ES`/`BOXL`, frozen reference `AVTX` (lines 1715-1718).
   Non-admitted symbols get an "UNAVAILABLE" replay panel.
9. **Operator surfaces fragmented**: `/control`, `/settings`, `/diagnostics/provider`, `/live-canary`
   are four flat siblings; `OperatorControlCenterPage` links to the others via full-reload `<a href>`
   (lines 119-121). CONTROL grouping fixes this; keep ContextBar → diagnostics deep link working.
10. **Mutation inventory is small and well-gated** (all Paper-only except operator/auth): paper order
    preview/submit/cancel, paper session open/close, opportunity ack, discover refresh/promote/release,
    live subscribe, operator lifecycle/provider/config, watchlist/capture-replay, replay scrub,
    assistant conversation/prompt, auth login/logout, workspace-layout persistence. Live mode has zero
    mutations by construction — this boundary must survive the redesign.
11. **Polling contracts to preserve**: provider health 5s; canary snapshot/reliability/reconciliation
    15s; order-flow/order-book/market-state 2s live; workspace evidence 5s live
    (`api/hooks.ts:125,164,353,363,372,432`; `LiveCanaryControlPlanePage.tsx:46`).
12. **Unknowns / needs backend or product confirmation (?)**: whether RESEARCH/LAB split has backend
    support beyond existing `/research/*` endpoints; whether nav "GATED" badge on Research maps to a
    real entitlement (no gate logic found in UI — likely copy only ?); whether mode-in-URL is
    acceptable to the session doctrine; whether `/explore?q=` search is planned backend functionality;
    whether assistant conversation resume (history → sidecar) is a supported flow.
