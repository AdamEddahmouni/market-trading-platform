# State & Data Contracts

Audit 03 — state-source tracing, data contracts, enum exposure, contradiction risks.
Branch `ui/operator-redesign-v2`, worktree `market-trading-platform-ui-redesign`.
Path shorthand below: `IMP/` = `projects/integrated-market-platform/`. UI root = `IMP/ui/src/`.
All citations are file:line. `?` marks unverified backend behavior (read-only audit; no runtime probing).

---

## API/hook inventory

### Transport layer

- `IMP/ui/src/api/fetchJson.ts:18-46` — `fetchJson` / `postJson` / `fetchRawJson`. All attach `authHeaders()` (Bearer token from `IMP/ui/src/auth/session.ts:30-34`). Non-2xx goes through `parseError` (`fetchJson.ts:4-16`), which parses the canonical error envelope and throws `ApiRequestError`; otherwise throws generic `Request failed: <path>`.
- `IMP/ui/src/api/errors.ts:3-14` — 12 canonical error categories mirrored from backend PR #90: `VALIDATION_ERROR, PROVIDER_UNAVAILABLE, PROVIDER_REJECTED, STALE_DATA, UNSUPPORTED_CAPABILITY, ACCOUNT_UNAVAILABLE, RISK_BLOCKED, MODE_BLOCKED, AUTH_ERROR, RATE_LIMITED, TIMEOUT, INTERNAL_ERROR`. `parseApiErrorEnvelope` fails closed when `error_category` is missing/unknown (`errors.ts:35-52`).
- `IMP/ui/src/api/endpoints.ts:50-250` — the `api` client object (all schema-validated except where noted).
- `IMP/ui/src/api/client.ts:1-4` — barrel re-exporting schemas + endpoints + hooks (legacy import path used by many components).
- React Query client: `new QueryClient()` with **all defaults** (`IMP/ui/src/App.tsx:155`) → `staleTime: 0`, `refetchOnWindowFocus: true`, default retry. Only hooks that set explicit `staleTime`/`refetchInterval` deviate.
- Vite dev proxy (`IMP/ui/vite.config.ts:29-62`) forwards a fixed allowlist to `127.0.0.1:8766`. **`/canary`, `/opportunities`, `/intelligence`, `/security` are NOT proxied** — canary/opportunity/trade-review calls only work when the UI is served by the backend itself. `/control` proxies to a separate port 8767.

### Query keys (`IMP/ui/src/api/hooks.ts:6-64`) — 44 entries

`context`, `attention`, `opportunitiesSummary` `["opportunities","summary"]`, `opportunityEvidence(rowId)`, `instrument(id)`, `exploreSqueeze`, `exploreSqueezeScanner`, `exploreFutures`, `exploreCatalyst`, `workspaceSqueeze(id, dataMode)`, `workspaceOrderFlow(id)`, `workspaceOptions(id)`, `workspaceLargeTransactions(id)`, `workspaceOrderBook(id)`, `workspaceFutures(id)`, `workspaceCatalyst(id)`, `workspaceFundEtf(id)`, `workspaceDisclosure(id)`, `workspaceInstitutionalFlow(id)`, `workspaceEvidence(id, dataMode)`, `replaySession`, `researchAnalytics`, `researchModels`, `researchSimulation`, `assistantStatus`, `assistantConversations`, `assistantMessages(conversationId)`, `paperPortfolio` `["paper","portfolio"]`, `paperForwardTests(accountId)`, `demoPortfolio` `["demo","portfolio"]`, `paperOrderHistory`, `paperTrace(intentId, orderId, fillId, allocationDecisionId)`, `paperStrategyProfitability(accountId, sessionId)`, `liveCanarySnapshot(laneId, accountId)`, `liveCanaryReconciliation(accountId)`, `providerHealth`, `operatorReadiness`, `symbolSearch(query)`, `instrumentSearch(query, limit)` (compact `["is", q, limit]`), `optionsProduct(id, mode, accountId, provider)` (compact `["op", id, mode, acct, provider]`), `futuresProduct(...)` (compact `["fp", ...]`), `instrumentCapabilities(id)`, `marketState(id)`.

Ad-hoc keys outside `queryKeys`: `["trade-reviews", opportunityId]` (`IMP/ui/src/api/tradeReviewClient.ts:33`), `["canary-reliability"]` (`IMP/ui/src/components/live/LiveCanaryControlPlanePage.tsx:43`). Invalidation-only prefixes: `["paper","strategy-profitability"]`, `["paper","trace"]` (`hooks.ts:308-309`), `["instrument"]` (`App.tsx:263`).

**Parallel unused key system**: `IMP/ui/src/api/queryKeyFactory.ts` + `canonicalQueryKey.ts` define a verbose canonical key DSL (`["pp","m","PAPER","a","unbound"]` etc.). Nothing in the app uses it except `forwardTestQueryKey` (`IMP/ui/src/components/paper-workspace/buildForwardTestPanelModel.ts:58-60`), which is itself never called. Its key shapes are **incompatible** with `hooks.ts` keys for the same resources (e.g. paper portfolio `["pp","m",...]` vs `["paper","portfolio"]`). `deriveQueryMode` (`canonicalQueryKey.ts:6-20`) is also unused by the app. Only the compact helpers `optionsProductKey`/`futuresProductKey`/`instrumentSelectorKey` match `hooks.ts` (pinned by `IMP/ui/src/api/queryKeys.test.ts:36-40`).

### Hooks (`hooks.ts`) — 45 total (40 queries, 5 mutations)

| Hook | Endpoint | Cadence / notes |
|---|---|---|
| `useContextQuery` (67-69) | GET `/context` | no poll; refetch on focus/invalidation |
| `useOperatorReadinessQuery` (70-77) | GET `/operator/readiness` | `staleTime: 60s` |
| `useAttentionQuery` (79-81) | GET `/attention` | — |
| `useInstrumentQuery` (83-88) | GET `/instruments/{id}/overview` | enabled when id non-empty |
| `useExploreSqueezeQuery` (91-92) | GET `/explore/squeeze` | — |
| `useExploreSqueezeScannerQuery` (94-99) | GET `/explore/squeeze/scanner` | — |
| `useExploreFuturesQuery` (102-104) | GET `/explore/futures` | — |
| `useExploreCatalystQuery` (106-108) | GET `/explore/catalyst` | — |
| `useWorkspaceSqueezeQuery` (110-116) | GET `/workspace/{id}/squeeze[?data_mode=current]` | dataMode default `"frozen"` |
| `useWorkspaceOrderFlowQuery` (118-127) | GET `/workspace/{id}/order-flow` | **polls 2s only when `/context` data_mode is `LIVE_OBSERVATIONAL`** |
| `useWorkspaceEvidenceQuery` (129-139) | GET `/workspace/{id}/evidence[?data_mode=current]` | derives dataMode from `/context` (live→`current`, else `frozen`); polls 5s when live |
| `useWorkspaceOptionsQuery` (141-147) | GET `/workspace/{id}/options` | — |
| `useWorkspaceLargeTransactionsQuery` (149-155) | GET `/workspace/{id}/large-transactions` | — |
| `useWorkspaceOrderBookQuery` (157-166) | GET `/workspace/{id}/order-book` | polls 2s when live |
| `useWorkspaceFuturesQuery` (168-174) | GET `/workspace/{id}/futures` | — |
| `useWorkspaceCatalystQuery` (176-182) | GET `/workspace/{id}/catalyst` | — |
| `useWorkspaceFundEtfQuery` (184-190) | GET `/workspace/{id}/fund-etf` | — |
| `useReplaySessionQuery` (192-194) | GET `/replay/session` | — |
| `useResearchAnalyticsQuery` (196-198) | GET `/research/analytics` | — |
| `useResearchModelsQuery` (200-202) | GET `/research/models` | — |
| `useResearchSimulationQuery` (204-206) | GET `/research/simulation` | — |
| `useWorkspaceDisclosureQuery` (208-214) | GET `/workspace/{id}/disclosure` | — |
| `useWorkspaceInstitutionalFlowQuery` (216-222) | GET `/workspace/{id}/institutional-flow` | — |
| `useAssistantStatusQuery` (224-230) | GET `/assistant/status` | enabled flag |
| `useAssistantMessagesQuery` (232-238) | GET `/assistant/conversations/{id}/messages` | — |
| `usePaperPortfolioQuery(viewMode)` (240-247) | GET `/paper/portfolio?view_mode=DEMO\|PAPER` | key switches between `demoPortfolio`/`paperPortfolio` |
| `usePaperForwardTestsQuery` (249-255) | GET `/paper/forward-tests?account_id=` | **fetchRawJson — unvalidated** (`endpoints.ts:147-150`) |
| `usePaperOrderHistoryInfiniteQuery` (257-265) | GET `/paper/order-history?cursor=&limit=` | infinite query, single unscoped key |
| `usePaperTraceQuery` (267-288) | GET `/paper/trace?...` | enabled when any correlation id present |
| `usePaperStrategyProfitabilityQuery` (290-298) | GET `/paper/strategy-profitability` | key embeds account/session but **queryFn passes no params** (`hooks.ts:296`) |
| `useProviderHealthQuery` (348-354) | GET `/provider/health` | **polls 5s unconditionally** |
| `useLiveCanarySnapshotQuery` (356-364) | GET `/canary/snapshot?account_id=` | `staleTime` 15s, polls 15s; default account `fp-canary-local` |
| `useLiveCanaryReconciliationQuery` (366-373) | GET `/canary/reconciliation?account_id=` | polls 15s |
| `useSymbolSearchQuery` (375-381) | GET `/symbols/search?q=` | — |
| `useInstrumentSelectorQuery` (383-389) | GET `/instruments/search?q=&limit=` | — |
| `useOptionsProductQuery` (391-403) | GET `/workspace/{id}/options-product?mode=&account_id=` | — |
| `useFuturesProductQuery` (405-415) | GET `/workspace/{id}/futures-product?mode=&account_id=` | — |
| `useInstrumentCapabilitiesQuery` (417-423) | GET `/instruments/{id}/capabilities` | — |
| `useMarketStateQuery` (425-435) | GET `/market-state/{id}` | **enabled only when live**; polls 2s |
| `usePreviewPaperOrderMutation` (321-323) | POST `/paper/orders/preview` | no invalidation |
| `useSubmitPaperOrderMutation` (325-331) | POST `/paper/orders` | invalidates paper scope (see Mutations) |
| `useOpenPaperSessionMutation` (333-339) | POST `/paper/sessions` (hardcodes `execution_mode: "INTERNAL_SIMULATION"`, `hooks.ts:336`) | invalidates paper scope |
| `useClosePaperSessionMutation` (341-346) | POST `/paper/sessions/close` | invalidates paper scope |
| `useSubscribeMutation` (437-450) | POST `/subscriptions` | invalidates `providerHealth` + `context` |

Satellite clients: `useOpportunitiesSummaryQuery` / `useOpportunityEvidenceQuery` / `useOpportunityAckMutation` (`IMP/ui/src/api/opportunityClient.ts:67-73, 88-97, 145-151`); `useTradeReviewsQuery` (`tradeReviewClient.ts:31-37`). Inline `useQuery` outside hooks: assistant conversations (`IMP/ui/src/components/AssistantHistoryPage.tsx:6-9`), canary reliability (`LiveCanaryControlPlanePage.tsx:42-46`, 15s poll).

### Endpoints consumed outside the `api` client (raw `fetch`, no zod, **no auth headers**)

- `App.tsx:160` GET `/state/startup` (StartupRecoveryBanner)
- `IMP/ui/src/components/paper-portfolio/PaperPortfolioPage.tsx:38-42` GET `/paper/sessions`
- `IMP/ui/src/components/workspace-shared/WorkspaceObservability.tsx:86-102` POST `/operator/workspace` (fire-and-forget layout persistence on every instrument change)
- `IMP/ui/src/components/live/LiveObservationalPanel.tsx:51-56, 85-102` POST `/operator/recent`, POST `/operator/workspace`
- `IMP/ui/src/components/live-now/LiveSymbolLookup.tsx:86-91` POST `/operator/recent`
- `IMP/ui/src/components/live/LiveCanaryControlPlanePage.tsx:28-34, 43-44` GET `/canary/reliability`
- `IMP/ui/src/components/discover-shared/DiscoverObservability.tsx:122-127, 143-158, 160-177, 179-198, 200-213, 226-234` — GET `/discover/screens`, GET `/discover/mixed`, POST `/discover/mixed/refresh`, GET `/discover/run?screen=&force=1` (**GET with mutating side effect**), POST `/discover/promote-to-live-analysis`, POST `/discover/mixed/release` (unmount, `keepalive`)
- `IMP/ui/src/components/OperatorSettingsPage.tsx:46-47, 61-68, 153-155, 170-181` — GET `/state/startup`, GET `/operator/state`, POST `/operator/watchlist`, GET `/captures`, POST `/captures/replay`
- `IMP/ui/src/auth/AuthProvider.tsx:50-60, 94-110, 113-123` — GET `/auth/status`, GET `/auth/session`, POST `/auth/login`, POST `/auth/logout`
- `IMP/ui/src/components/mode-session/types.ts:7-9` — readiness probe GET `/context` (raw)
- `IMP/ui/src/api/liveCanary.ts:35-38` — canary fetches also omit auth headers
- Even inside `endpoints.ts`, the hand-written POSTs (`scrubReplay` :59, `createAssistantConversation` :124, `submitAssistantPrompt` :133, `subscribeLive` :243) omit `authHeaders()`.

Backend route table (for reference; **not all are UI-consumed**): `IMP/src/market_platform_foundation/ui_api/server.py:150-980` (GET) and `:1088-1520` (POST). Unconsumed-by-UI routes include `/capabilities`, `/accounts`, `/security/readiness`, `/provider/finviz/health`, `/canary/{timeline,incidents,action-inventory,pilot,deployment,authorization/preview,command}`, `/paper/{account,positions,orders GET,fills,risk}`, `/paper/broker/*`, `/paper/forward-tests/{preflight,sessions,decisions,lock,submit,observe,evaluate}`, `/paper/orders/replace`, `/subscriptions/release`, `/operator/preferences`, `/operator/lifecycle/operations/{id}`, `/workspace/{s}/market-context` (schema exists at `schemas.ts:1386-1415` but no hook), `/intelligence/ingest/*`.

---

## State domain traces

### (a) Session state

Five distinct "session" concepts reach the UI:

1. **Replay session** — GET `/replay/session` → `ReplaySessionSchema` (`IMP/ui/src/api/schemas.ts:858-861`: `cursor_index`, `event_count`) → `useReplaySessionQuery` → consumed only in `App.tsx` `WorkstationShell` (`App.tsx:201, 226-231`) to drive scrub slider state; rendered by `DemoReplayOverview` and `WorkspaceObservability` replay controls (`WorkspaceObservability.tsx:122-134`).
2. **Paper session** — embedded in `/paper/portfolio` (`session.session_id`, `execution_mode`, `execution_authority`, `starting_cash_minor`; `schemas.ts:1774-1783`) and opened/closed via POST `/paper/sessions`, `/paper/sessions/close` (`endpoints.ts:162-171`, `PaperSessionResponseSchema` `schemas.ts:1886-1895`). Rendered in `PaperPortfolioPage.tsx:79-85` (header meta) and `PaperNowPage.tsx:130`. A **second, unvalidated source** — raw GET `/paper/sessions` — feeds the "Session history" list (`PaperPortfolioPage.tsx:36-42, 152-166`), refetched only when the portfolio session id changes. A third source: `/operator/state` `sessions[]` in `OperatorSettingsPage.tsx:135-143`.
3. **Auth session** — GET `/auth/status` + `/auth/session` (`AuthProvider.tsx:50-60`); token persisted in `sessionStorage` (`auth/session.ts`); gate is `OperatorLoginGate.tsx`. `permitsCapability` (`AuthProvider.tsx:125-133`) uses hardcoded `ROLE_CAPABILITIES` (`AuthProvider.tsx:26-46`) with a `LOOPBACK_TRUST` bypass (`AuthProvider.tsx:128`).
4. **Live canary session** — `session_state` inside `/canary/snapshot` (`IMP/ui/src/api/liveCanary.ts:6`), rendered raw in `LiveCanaryControlPlanePage.tsx:124` and `LiveSafetySnapshot` via `liveSafetySummary` (`IMP/ui/src/components/live-now/liveDashboardViewModel.ts:166`).
5. **Startup/crash recovery** — GET `/state/startup` read twice: `App.tsx:160-171` (banner keys on `crash_recovery: OPEN_SESSION_DETECTED | CORRUPT_DB`) and `OperatorSettingsPage.tsx:46` (`restore`, `execution_deferred`, `opend`).

### (b) Execution state

- Canonical source: `/context` `as_of_context.execution_mode` / `execution_authority` (zod enums, `schemas.ts:99-100`). Backend derives them in `IMP/src/market_platform_foundation/ui_api/live_projections.py:283-299` (`resolve_live_operating_modes`) and `IMP/src/market_platform_foundation/operating_modes.py:54-84` (`build_operating_context`, validated against `EXECUTION_MODES`/`EXECUTION_AUTHORITIES`).
- Rendered: `ContextBar.tsx:16-23, 36-42` (raw enums; `INTERNAL_SIMULATION` hardcoded to label "INTERNAL SIMULATION · PAPER ONLY" regardless of authority); `ModeEnvironmentBar.tsx` via `evaluateModeContext`; `PaperPortfolioPage.tsx:78` and `DemoPortfolioPage.tsx:41-44` render `account.execution_mode`/`account.execution_authority` from **the portfolio payload** (ledger fields, `paper_projections.py:190-205`) — a different source object than `/context`.
- Preview/submit echo: `PaperOrderPreviewResponseSchema.preview.execution_mode/execution_authority` (`schemas.ts:1835-1837`) and trace `execution_mode/execution_authority/execution_provider` (`schemas.ts:1942-1946`), rendered raw in `ExecutionTracePanel.tsx:170-175`.
- Canary: `execution_mode_label` (free string, `liveCanary.ts:4`) rendered at `LiveCanaryControlPlanePage.tsx:65`.
- Discover: hardcoded contract `execution_authority: "NONE"` (`DiscoverObservability.tsx:79`), rendered `DiscoverObservability.tsx:341`.

### (c) Authority (incl. `modeAuthority.ts`)

`IMP/ui/src/components/mode-session/modeAuthority.ts`:
- `hasPaperAuthority` (17-24): `execution_mode === "INTERNAL_SIMULATION" && execution_authority ∈ {PAPER_ONLY, AUTHORIZED}`.
- `evaluateModeContext` (26-56): DEMO compatible ⇔ data_mode ∈ {FIXTURE_REPLAY, HISTORICAL_CAPTURE} ∧ exec NONE/BLOCKED; PAPER ⇔ `hasPaperAuthority`; LIVE ⇔ data_mode ∈ {LIVE_OBSERVATIONAL, BROKER_DELAYED} ∧ exec NONE/BLOCKED. Emits `status: compatible|mismatch|unavailable` and the raw summary string `DATA <data_mode> · EXEC <execution_mode> · AUTH <execution_authority>` (53).
- `canUsePaperActions` (58-64): `mode === "PAPER" && globalPaperPermission && hasPaperAuthority(actionContext)`.

Call sites and their divergences:
- `App.tsx:210-214` — `paperActionsPermitted` = `evaluateModeContext(mode, /context).paperActionsPermitted` AND'd with `auth.permitsCapability("paper.order.submit")` (defaults **true** when auth absent, `App.tsx:214`).
- `PaperPortfolioPage.tsx:66` — `canUsePaperActions("PAPER", paperActionsPermitted, account)` where `account` is the **portfolio** account (ledger-sourced mode/authority), not `/context`.
- `PaperWorkspacePage.tsx:47-51` — same pattern, gates the cockpit `OrderTicket`.
- `OrderTicket.tsx:66-68` — re-derives `authorized` from props (portfolio account fields): `(AUTHORIZED || PAPER_ONLY) && INTERNAL_SIMULATION`.
- `PaperNowPage.tsx:61` — **stricter**: requires `execution_authority === "PAPER_ONLY"` exactly (excludes `AUTHORIZED`, which `hasPaperAuthority` permits).
- `OptionsProductSurface.tsx:44` and `FuturesProductSurface.tsx:38` — call `canUsePaperActions(mode, paperActionsPermitted, undefined)`; `hasPaperAuthority(undefined)` is always false → **the derivative paper preview panel can never render through these surfaces** (fail-closed, possibly unintended).
- `IMP/ui/src/components/operator-settings/operatorSettingsMode.ts:5-7` — operator settings mutations allowed only in client-side PAPER mode.
- Lane draft links: `LaneModeContextPanel.tsx:110-126` shows "Draft paper order from lane" whenever `mode === "PAPER"` and query not errored — **no authority check at all** (authority is enforced later at the workspace ticket).

### (d) Provider health

- GET `/provider/health` (`ProviderHealthResponseSchema`, `schemas.ts:260-332`; note `.passthrough()` on `lifecycle` :284 and `provider_summary` :312, and free-record `execution_gate` :313, `finviz` :331). Polled every 5s (`hooks.ts:353`). Consumers: `ProviderHealthPanel.tsx` (route `/diagnostics/provider`), `LiveNowRoute` → `LiveProviderRibbon` + `LiveSymbolLookup` + KPIs (`ModeNowRoute.tsx:59, 77-78`), `LiveObservationalPanel.tsx:12`, `LiveLaneOperationalStrip.tsx:11`.
- GET `/operator/readiness` (`OperatorReadinessSchema`, `schemas.ts:52-58`; providers carry `credential_state`/`gate_state`/`transport_state`/`freshness`/`next_action`, `schemas.ts:40-50`). Two consumers with different cadences: `useOperatorReadinessQuery` (staleTime 60s, `hooks.ts:70-77`) and `OperatorControlCenterPage.tsx:23-41` (manual local state, refetch on demand).
- `/discover/mixed` embeds its own `provider_health[]` (`DiscoverObservability.tsx:36-43`), polled on a server-driven interval (default 3s, `DiscoverObservability.tsx:241`) — a third, independently-cadenced provider-health view.
- Backend connection-state enum: `ProviderConnectionState` — `DISABLED, CONNECTING, CONNECTED, CONNECTED_DEGRADED, DEGRADED, DISCONNECTED, RECONNECTING, ENTITLEMENT_MISSING, ERROR` (`IMP/src/market_platform_foundation/market_data/provider_lifecycle.py:10-19`), rendered raw in `ProviderHealthPanel.tsx:32, 43`, `liveDashboardViewModel.ts:50`, `LiveNowPage.tsx:110`, `LiveObservationalPanel.tsx:31`, `LiveLaneOperationalStrip.tsx:46`.
- UI-derived channel health: `UNAVAILABLE | HEALTHY | DEGRADED` from `(account_entitled, runtime_tested)` booleans — duplicated logic in `ProviderHealthPanel.tsx:5-7` and `liveDashboardViewModel.ts:20-23`.

### (e) Data health / freshness

- `/context` `quality_summary.state` — unconstrained `z.string()` (`schemas.ts:138-142`). Backend replay vocabulary: `GOOD | PARTIAL | DEGRADED | STALE | UNAVAILABLE` (`IMP/src/market_platform_foundation/ui_api/projections.py:73-83`); live override vocabulary: `PASS | UNAVAILABLE | STALE | DEGRADED` (`live_projections.py:137-146`) — **two different vocabularies for the same field**. Rendered raw in `ContextBar.tsx:60` (label switches QUALITY↔HEALTH by mode, :59).
- Paper portfolio `data_health.state` — `PASS` when fixture replay, else `UNKNOWN`, else live mark quality (`paper_projections.py:1319-1323`); live mark quality can be `STALE`, `DISCONNECTED` (`IMP/src/market_platform_foundation/market_data/live_runtime.py:594-601`), or `RESTORED` after crash recovery (`IMP/src/market_platform_foundation/local_state/startup.py:200`). Rendered raw in `PaperPortfolioPage.tsx:76`, `DemoPortfolioPage.tsx:41-42`, `PaperNowPage.tsx:134`, `PaperPortfolioObservability.tsx:213`.
- Workspace evidence lanes: per-lane `quality`, `freshness_label`, `reason_codes` (`WorkspaceEvidenceLaneSchema`, `schemas.ts:1980-2001`), rendered in `WhatMattersNowPanel.tsx:52-54`; plus client-computed staleness from `lane_provenance` with a 5-minute threshold (`IMP/ui/src/components/workspace-module-shared/laneProvenance.ts:90-97`, `laneQueryState.ts:24-36`).
- Live market: `freshness_ms` + `quote.quality` (`MarketStateResponseSchema`, `schemas.ts:334-343`) in `LiveMarketPanel.tsx:41-43`.
- Discover: per-candidate `data_status: LIVE|DELAYED|SNAPSHOT|STALE|UNAVAILABLE` and `freshness_label` (hand-typed, `DiscoverObservability.tsx:61-72`), plus per-screen `status != "PASS"` degradation list (`DiscoverObservability.tsx:290, 370-384`).
- `workspaceHealth.formatDataHealthLabel` (`IMP/ui/src/components/workspace-shared/workspaceHealth.ts:9-10`) checks `data_mode === "CAPTURE_REPLAY"` — **a value that does not exist** in the backend `DATA_MODES` enum (`FIXTURE_REPLAY | HISTORICAL_CAPTURE | LIVE_OBSERVATIONAL | BROKER_DELAYED`, `operating_modes.py:8-13`). Dead branch; `HISTORICAL_CAPTURE` falls through to raw underscore replacement.

### (f) Mode (Demo / Paper / Live)

- **UI mode is pure client state**: `selectedMode` in `ApplicationBootstrap.tsx:28` (React state; not in URL, not persisted, not sent to backend). `ModeLauncher` → `ModeTransition` (readiness task is a no-op default, `types.ts:10`) → `WorkstationShell mode=...`.
- **Backend mode is independent**: `/context` `as_of_context.mode` is a legacy derived label (`legacy_mode_label`, `operating_modes.py:38-51`: LIVE/REPLAY/SIMULATION/PAPER) alongside the orthogonal `data_mode`/`execution_mode`/`execution_authority`.
- Reconciliation is advisory only: `evaluateModeContext` (`modeAuthority.ts:26-56`); mismatch renders an alert in `ModeEnvironmentBar.tsx:33-39` ("UI mode selection does not change backend authority") but every page still renders mode-selected chrome (e.g. `PaperWorkspacePage.tsx:69` eyebrow "Paper-only simulation", `WorkspaceModuleModeShell.tsx` per-mode headers).
- Mode copy: `modeMetadata.ts:11-38` (DEMO "Historical replay", PAPER "Simulated execution", LIVE "Read-only market data"); `ImpExecutionPosture.tsx:8-12` + hardcoded "Live off" chip (:26-28).
- `deriveQueryMode` (`canonicalQueryKey.ts:6-20`) exists for cache isolation but is unused — **workspace lane keys do not include mode**, so the same lane key serves DEMO and PAPER and LIVE content (e.g. `["workspace", id, "order-flow"]`).

### (g) Portfolio state (positions / orders / P&L / exposure)

- GET `/paper/portfolio?view_mode=DEMO|PAPER` → `PaperPortfolioResponseSchema` (`schemas.ts:1720-1798`): `account` (cash/buying_power/realized pnl + **ledger-sourced** `data_mode`, `execution_mode`, `execution_authority`, providers, :1734-1738), `positions[]` (with `mark_quality`, `mark_source`, `mark_provider`, `mark_as_of_ns`, :1740-1755), `orders`/`fills` as **untyped `z.record(z.unknown())`** (:1756-1757), `risk` (:1757-1767), `data_health` (:1768-1772), `session`, `active_instrument`/`active_instrument_source` (:1784-1785), `exposure` (:1786-1790), `pnl` (:1791-1797). Backend builder: `paper_projections.py:149-230` (demo view zeroes positions/orders/fills and forces `NONE`/`BLOCKED`, :163-189).
- Consumers: `ModePortfolioRoute.tsx` (DEMO→`DemoPortfolioPage` with `view_mode=DEMO`; PAPER→`PaperPortfolioPage`; LIVE→canary-based `LivePortfolioPage`), `ModeNowRoute.tsx:26-55` (both Demo and Paper now-pages), `PaperWorkspacePage.tsx:39`, `ImpExecutionPosture.tsx:15` (enabled only in PAPER), `OrderTicket.tsx:63`, `DerivativePaperPreviewPanel.tsx:26`, `usePaperStrategyProfitabilityQuery` key derivation (`hooks.ts:291-293`).
- Orders/history: `/paper/order-history` infinite query (`PaperOrderHistoryPageSchema`, `schemas.ts:1802-1811`; terminal states `FILLED|CANCELLED|REJECTED|EXPIRED|RISK_REJECTED`, `paper_projections.py:85`) → `PaperOrderHistory`. Trace: `/paper/trace` → `ExecutionTracePanel`.
- Strategy P&L: `/paper/strategy-profitability` (`schemas.ts:2069-2096`; `authority_boundary` literal `PAPER_OBSERVABILITY_READ_ONLY` :2071, settlement enum `SETTLED|PENDING|UNAVAILABLE` :2064) → `PaperStrategyProfitabilityObservability.tsx` (also embedded in `PaperResearchPage.tsx:19`).
- Forward tests: `/paper/forward-tests` via `fetchRawJson` (unvalidated), cast in `PaperWorkspacePage.tsx:42-43` → `PaperForwardTestPanel`.
- Live "portfolio": `/canary/snapshot` `live_positions`/`open_broker_orders` (`liveCanary.ts:18-19`) + `/canary/reconciliation` → `LivePortfolioPage.tsx` via view-model `livePortfolioViewModel.ts`.
- KPI derivations: `IMP/ui/src/components/imp-product/impOverviewMetrics.ts:19-61` (paper) and :63-117 (live).

### (h) Opportunity / discovery state

- GET `/opportunities/summary` → `OpportunitiesSummaryResponseSchema` (`opportunityClient.ts:49-58`): `feed_status`, `reason`, `unready_reason`, `next_action`, `items[]` (`OpportunityReviewRowSchema` :7-47, `.passthrough()`, with `eligibility_state`, `lifecycle_state`, `next_safe_action`, `ranking_vector`, `decision_support{authority, kill_switch, reason_codes}`). Backend: `opportunity_projections.py:150-159` — `feed_status ∈ READY | UNREADY | EMPTY | UNAVAILABLE | DISMISSED`; **in LIVE mode the feed is always `UNAVAILABLE` with reason `LIVE_OBSERVATIONAL_NO_OPPORTUNITY_ENGINE`** (:200-207), yet `LiveNowPage.tsx:44` and `DemoNowPage.tsx:33` and `PaperNowPage.tsx:35` all query it unconditionally.
- Consumers: `PaperNowPage` (PaperCandidateQueue + ImpOverviewBoard), `LiveNowPage`, `DemoNowPage`, `OpportunityRadarCockpit.tsx:29` + `OpportunityRadarDensePanel.tsx:28` (Discover pages), `OpportunityFeedStatusBanner.tsx` (renders `UNREADY` + `unready_reason` raw, links `next_action` → `/control`).
- Detail/evidence: GET `/opportunities/{rowId}`, GET `/opportunities/{rowId}/evidence` (`opportunityClient.ts:137-143`) → `ProgressiveOpportunityCard`. Trade reviews: GET `/intelligence/trade-reviews?opportunity_id=` (`tradeReviewClient.ts:26-29`) → `TradeReviewLearningPanel`.
- Ack mutations: POST `/opportunities/{rowId}/{watch|dismiss|review}` (`opportunityClient.ts:75-97`).
- Discovery desk: `/discover/*` family (hand-rolled, see API inventory). Contract claims `mode: "SEMI_LIVE"`, `candidate_role: "INVESTIGATE"`, `execution_authority: "NONE"` (`DiscoverObservability.tsx:78-80`). Enums `market.status`/`data_status`: `LIVE|DELAYED|SNAPSHOT|STALE|UNAVAILABLE` (:61-70).
- Attention feed: GET `/attention` (`AttentionResponseSchema`, `schemas.ts:345-352`; items `schemas.ts:123-133` with `priority_rank`, `reasons[{code,label}]`, `tier`, `surfaced_time`) → `App.tsx:200` → all three Now pages (`AttentionFeed.tsx`).

### (i) Research / lab state

- GET `/research/analytics` (`schemas.ts:963-975`: `authority_boundary`, `epistemic_class`, 5 panels), `/research/models` (`schemas.ts:1644-1661`), `/research/simulation` (`schemas.ts:1663-1684`: `mode_label`, `risk_policy_id`, `ledger_summary`, `risk_decisions`, `fills`, `orders`, `intents`, `attributions`, `reconciliation`). All three fetched eagerly by `ResearchObservability.tsx:19-21` regardless of active tab; rendered via `ResearchAnalyticsPanel` / `ModelLabPanel` / `SimulationLabPanel`. `authority_boundary` and `epistemic_class` rendered raw (`ResearchObservability.tsx:68-70`).
- Pages are mode-skinned only: `DemoResearchPage` / `PaperResearchPage` / `LiveResearchPage` all mount the same `ResearchObservability`; Live adds a read-only note (`LiveResearchPage.tsx:20-23`).
- `/research/vela-chart-lab` route: `ImpVelaChartLabPage` uses a local `setInterval` tick (its own timer, `ImpVelaChartLabPage.tsx:33`) — not backend realtime.

### (j) Risk state

- Portfolio risk block: `risk.kill_switch_active`, `open_order_count`, `reconciliation_status`, `limits{max_open_orders, max_order_shares, max_position_shares}`, `last_decision` (untyped record) (`schemas.ts:1757-1767`). Rendered in `PaperPortfolioObservability.tsx:66-97` and derived into exceptions by `paperDashboardViewModel.ts:64-94` with **client-side vocabularies**: healthy health set `{PASS, HEALTHY, CURRENT, AVAILABLE}` (:8), reconciled set `{PASS, HEALTHY, CLEAN, RECONCILED, INTERNAL_AUTHORITATIVE}` (:9), healthy risk decisions `{PASS, ALLOW, APPROVE, RESIZE}` (:10), problem order regex `BLOCKED|REJECTED|WAITING|FAILED` (:11) → `PaperRiskRibbon` / `PaperExceptionsPanel`.
- Preview risk: `preview.risk_status` (`PASS|BLOCKED`, backend `IMP/src/market_platform_foundation/paper/execution.py:274`), `decision` (`APPROVE|RESIZE|…` ?), `reason_codes[]`, `quality_state ∈ PASS | WAITING_FOR_ELIGIBLE_LIVE_EVENT | NO_EXECUTABLE_BAR` (`execution.py:278-282`), `risk_limits`, `risk_utilization` (`schemas.ts:1815-1868`). Presentation state machine: `paperPreviewPresentation.ts:3-10` (`NOT_PREVIEWED|PREVIEWING|ACCEPTED|REJECTED|REVALIDATION_REQUIRED|AUTHORITY_UNAVAILABLE|ERROR`) with server-marker matching `PREVIEW_EXPIRED|PREVIEW_INTENT_MISMATCH|PREVIEW_PORTFOLIO_STALE|PREVIEW_POLICY_STALE|PREVIEW_MARGIN_STALE|PREVIEW_REQUIRED` (:13-20).
- Live risk: canary `kill_switch_global/program/session`, `live_blocked`, `block_reasons[]`, `incident_summary`, `unresolved_critical_incidents` (`liveCanary.ts:3-25`); client-side alert thresholds in `liveDashboardViewModel.ts:91-152` (kill-switch "ok" values `OFF|INACTIVE|CLEAR` :108; broker health ok set `HEALTHY|OK|PASS` :116; reconciliation ok set `HEALTHY|OK|PASS|RECONCILED` :128).
- Error taxonomy surfaces risk blocks as `RISK_BLOCKED` / `MODE_BLOCKED` envelopes (`errors.ts:10-11`), formatted `CATEGORY: reason_code: message` (`errors.ts:69-71`) and shown raw in ticket/composer error lines (`OrderTicket.tsx:149, 323`).

---

## Enum/jargon reaching the UI

Typed = zod/TS-constrained; raw = unconstrained string rendered verbatim.

| Enum / jargon | Values | Typed at | Rendered at |
|---|---|---|---|
| `as_of_context.mode` | `LIVE, REPLAY, SIMULATION, PAPER` | `schemas.ts:97` (zod enum); backend `operating_modes.py:38-51` | `ContextBar.tsx:32` (title), mode copy elsewhere |
| `data_mode` | `FIXTURE_REPLAY, HISTORICAL_CAPTURE, LIVE_OBSERVATIONAL, BROKER_DELAYED` | `schemas.ts:98`; `operating_modes.py:8-13` | `ContextBar.tsx:9-13` (underscores stripped), `LiveNowPage.tsx:99`, `impOverviewMetrics.ts:91`, `PaperPortfolioPage.tsx:76`, `OrderTicket.tsx:215` |
| `execution_mode` | `NONE, INTERNAL_SIMULATION, BROKER_PAPER, LIVE` | `schemas.ts:99`; `operating_modes.py:15-20` | `ContextBar.tsx:16-23`, `PaperPortfolioPage.tsx:78`, `PaperNowPage.tsx:131`, `ExecutionTracePanel.tsx:171` |
| `execution_authority` | `BLOCKED, AUTHORIZED, PAPER_ONLY` | `schemas.ts:100`; `operating_modes.py:21-25` | **raw** in `ContextBar.tsx:41`, `PaperPortfolioPage.tsx:78`, `PaperNowPage.tsx:132-133`, `ExecutionTracePanel.tsx:174`, `OrderTicket.tsx:214-219` (partially translated to "PAPER ONLY") |
| `quality_summary.state` | replay: `GOOD, PARTIAL, DEGRADED, STALE, UNAVAILABLE`; live: `PASS, UNAVAILABLE, STALE, DEGRADED` | **untyped** `z.string()` `schemas.ts:139`; backend `projections.py:77-83`, `live_projections.py:137-146` | `ContextBar.tsx:60`, `useWorkspaceContext` (`WorkspaceObservability.tsx:46`) |
| Provider connection state | `DISABLED, CONNECTING, CONNECTED, CONNECTED_DEGRADED, DEGRADED, DISCONNECTED, RECONNECTING, ENTITLEMENT_MISSING, ERROR` | untyped in UI (`schemas.ts:266`); backend `provider_lifecycle.py:10-19` | `ProviderHealthPanel.tsx:32, 43`, `liveDashboardViewModel.ts:50`, `LiveNowPage.tsx:110`, `LiveObservationalPanel.tsx:31`, `LiveLaneOperationalStrip.tsx:46` |
| Channel health (UI-derived) | `UNAVAILABLE, HEALTHY, DEGRADED` | `ProviderHealthPanel.tsx:5-7`, `liveDashboardViewModel.ts:20-23` (duplicated) | both panels/ribbons |
| `execution_use` / eligibility | `INTERNAL_PAPER_ELIGIBLE, DISPLAY_ONLY` (+ raw `execution_eligibility`) | `ProviderHealthPanel.tsx:28`, `liveDashboardViewModel.ts:44-45` | `ProviderHealthPanel.tsx:66-68` |
| Capability `state` | observed: `AVAILABLE, GATED, UNSUPPORTED` (+ backend others ?) | untyped `z.string()` `schemas.ts:110, 249`; `paper_projections.py:54`, `projections.py:138-302` | `ImpCapabilityStrip` via `capabilityPresentation.ts:7-14` (tone map: ok = READY/AVAILABLE/ENABLED/AUTHORIZED/PASS; warn = DEGRADED/LIMITED/PARTIAL/WARN/WARNING; **everything else blocked**), `LiveObservationalPanel.tsx:69`, `LiveSymbolLookup.tsx:69` |
| Canonical error categories | 12 values | `errors.ts:3-14` | `formatApiRequestError` output in ticket/composer/preview error text |
| Opportunity `feed_status` | `READY, UNREADY, EMPTY, UNAVAILABLE, DISMISSED` | untyped `z.string()` `opportunityClient.ts:52`; backend `opportunity_projections.py:150-159, 203, 266` | `OpportunityFeedStatusBanner.tsx:36-42` (UNREADY only), `impOverviewMetrics.ts:110` (raw `Radar <status>`), `PaperNowPage.tsx:154` |
| Opportunity `next_safe_action` | `OPEN_WORKSPACE, STOP, NONE` | untyped `opportunityClient.ts:18`; backend `intelligence/opportunity/ingest.py:101, 228`, `read_model.py:118` | gates CTA in `progressiveOpportunityModel.ts:107-108, 229` |
| Opportunity `eligibility_state` / `lifecycle_state` | e.g. `INELIGIBLE, UNAVAILABLE, NORMALIZED_AWAITING_FORECAST` (+ lifecycle enum values ?) | untyped `opportunityClient.ts:15-16`; backend `ingest.py:94, 225` | `progressiveOpportunityModel.ts:107` |
| Preview `risk_status` | `PASS, BLOCKED` | untyped `schemas.ts:1820`; backend `execution.py:274` | `OrderTicket.tsx:330`, `PaperPreviewComposer.tsx:56-58`, `paperPreviewPresentation.ts:100-116` |
| Preview `decision` | `APPROVE, RESIZE, REJECT` ? (only APPROVE/RESIZE verified) | untyped `schemas.ts:1821`; backend `execution.py:274, 290` | same as above |
| Preview `quality_state` | `PASS, WAITING_FOR_ELIGIBLE_LIVE_EVENT, NO_EXECUTABLE_BAR` | untyped `schemas.ts:1838`; backend `execution.py:278-282` | `OrderTicket.tsx:335-341` (partially translated), `PaperPreviewComposer.tsx:63` |
| Preview revalidation markers | `PREVIEW_EXPIRED, PREVIEW_INTENT_MISMATCH, PREVIEW_PORTFOLIO_STALE, PREVIEW_POLICY_STALE, PREVIEW_MARGIN_STALE, PREVIEW_REQUIRED` | `paperPreviewPresentation.ts:13-20` (client-side substring match) | `PaperPreviewStatus` |
| Order side / type | `BUY, SELL` / `MARKET, LIMIT` | `schemas.ts:1960-1963` (TS literal) | ticket controls |
| Order states | terminal: `FILLED, CANCELLED, REJECTED, EXPIRED, RISK_REJECTED`; others untyped | backend `paper_projections.py:85`; UI regex `paperDashboardViewModel.ts:11` | `PaperPortfolioObservability.tsx:156` (raw `order.state`), `PaperOrderHistory` |
| Portfolio `data_health.state` | `PASS, UNKNOWN, STALE, DISCONNECTED, RESTORED` (+ live quote quality ?) | untyped `schemas.ts:1769`; backend `paper_projections.py:1319-1323`, `live_runtime.py:594-601`, `startup.py:200` | `PaperPortfolioPage.tsx:76`, `DemoPortfolioPage.tsx:42`, `PaperNowPage.tsx:134`, `PaperPortfolioObservability.tsx:213` |
| Position `mark_quality` | same source as above | untyped `schemas.ts:1749` | `PaperPortfolioObservability.tsx:124` |
| `reconciliation_status` | untyped; client ok-set `{PASS, HEALTHY, CLEAN, RECONCILED, INTERNAL_AUTHORITATIVE}` | `schemas.ts:1760, 1773`; `paperDashboardViewModel.ts:9, 71` | `PaperExceptionsPanel` |
| Kill switch values | ok: `OFF, INACTIVE, CLEAR`; anything else alerts | untyped `liveCanary.ts:12-14`; `liveDashboardViewModel.ts:108` | `LiveCanaryControlPlanePage.tsx:106-111`, `LiveSafetySnapshot` |
| `broker_health` / `reconciliation_health` | ok: `HEALTHY, OK, PASS` / `+ RECONCILED` | untyped `liveCanary.ts:10-11`; `liveDashboardViewModel.ts:116, 128` | `LiveCanaryControlPlanePage.tsx:94-97`, `LiveLaneOperationalStrip.tsx:52` |
| Discover `data_status` / `market.status` | `LIVE, DELAYED, SNAPSHOT, STALE, UNAVAILABLE` | hand-typed `DiscoverObservability.tsx:61-70` | `DiscoverObservability.tsx:441-460` (raw pills) |
| Discover contract literals | `mode: SEMI_LIVE`, `candidate_role: INVESTIGATE`, `execution_authority: NONE` | `DiscoverObservability.tsx:78-80` | `DiscoverObservability.tsx:302-304, 341` |
| Settlement state | `SETTLED, PENDING, UNAVAILABLE` | `schemas.ts:2064` (zod enum) | `PaperStrategyProfitabilityObservability.tsx:122-124` |
| `authority_boundary` | `PAPER_OBSERVABILITY_READ_ONLY` (literal), `PAPER_OBSERVABILITY`, others free string | `schemas.ts:2071` (literal), `schemas.ts:1723, 1645, 1664` (string) | `ResearchObservability.tsx:69` |
| `InstrumentSelectionAction` | `OPEN_EQUITY_WORKSPACE, OPEN_OPTIONS_WORKSPACE, OPEN_FUTURES_WORKSPACE, OPEN_FUTURE_FAMILY_REFERENCE, OPEN_CONTINUOUS_REFERENCE, OPEN_CRYPTO_REFERENCE, OPEN_OPTION_CHAIN, REFERENCE_ONLY, UNSUPPORTED_INSTRUMENT, OPEN_WORKSPACE` | `instrumentIdentity.ts:21-30` (TS); backend `instrument_selector.py` ? | `CanonicalInstrumentSelector.tsx` via `selectionDisabledReason` (`instrumentIdentity.ts:58-73`) |
| UI `Mode` | `DEMO, PAPER, LIVE` | `types.ts:1` | everywhere (chrome) |
| `LaneSourceKind` | `lane_payload, context_as_of, retrieved_at, unknown` | `laneProvenance.ts:3` | `LaneModeContextPanel.tsx:53` via `laneProvenanceSummary` |
| Preview presentation status | `NOT_PREVIEWED, PREVIEWING, ACCEPTED, REJECTED, REVALIDATION_REQUIRED, AUTHORITY_UNAVAILABLE, ERROR` | `paperPreviewPresentation.ts:3-10` (UI-only) | `PaperPreviewStatus` |
| Mode context evaluation | `compatible, mismatch, unavailable` | `modeAuthority.ts:11` | `ModeEnvironmentBar.tsx:21-45` |
| Crash recovery | `OPEN_SESSION_DETECTED, CORRUPT_DB` | untyped; `App.tsx:163-168` | `StartupRecoveryBanner` |
| Operator readiness `status` | `READY, ACTION_REQUIRED` (+ preflight statuses ?) | untyped `schemas.ts:54`; backend `operator_projections.py:128-130` | `OperatorControlCenterPage.tsx:93-95, 134-136` |
| Provider readiness states | credential: `CONFIGURED, MISSING, NOT_REQUIRED`; gate: `ENABLED, DISABLED, CONFIGURED, OPTIONAL`; transport: `IMPLEMENTED, IMPLEMENTED_READ_ONLY, FIXTURE_ONLY, UNAVAILABLE, BLOCKED_NON_LOOPBACK, HTTPS_PAPER_HOST, COMPARATOR_NOT_CONFIGURED, IMPLEMENTED_OPTIONAL, IMPLEMENTED_PUBLIC` | untyped `schemas.ts:43-46`; backend `tools/provider_readiness.py:192-458` | `OperatorControlCenterPage.tsx:170-184` (raw) |
| Lifecycle actions | `setup, start, stop, restart, open, check_update, apply_update` | `schemas.ts:11-19` (zod enum) | `OperatorControlCenterPage.tsx:98-115` |
| Update status | `AVAILABLE` gate | untyped `schemas.ts:22`; `OperatorControlCenterPage.tsx:111` | same |
| Sentiment label | `positive, negative, neutral, mixed, unknown` | `schemas.ts:1346` (zod enum) | market-context payload (no current UI hook) |
| Workspace/evidence `data_mode` | `frozen, current` | `schemas.ts:418, 609` (zod enum); hook param `hooks.ts:17-18, 30` | `ModeSqueezeWorkspaceRoute.tsx:22-24` |
| Explore row jargon | `outcome_status`, `evidence_coverage`, `research_detection`, `freshness`, `mode_label`, `capability_state`, `epistemic_class` — all free strings | `schemas.ts:390-403` | `ExploreObservability.tsx:65-67` (raw table cells) |
| Assistant `authority_boundary`, `epistemic_class` | free strings | `schemas.ts:884-885` | `AssistantSidecar` ? |
| Admitted instrument constants | `BIYA` (replay), `NVDA` (options/order-flow/fund-etf), `ES` (futures), `BOXL` (catalyst), `AVTX` (frozen demo ref) | `schemas.ts:1713-1718` | `WorkspaceRoute.tsx:34, 40`, `WorkspaceObservability.tsx:156-159`, `ExploreObservability.tsx` |

---

## Contradiction & divergence risks

1. **Three different authority derivations for the same "can I paper-trade?" question.**
   - `App.tsx:210-214`: `/context` + `evaluateModeContext` + auth capability.
   - `PaperPortfolioPage.tsx:66` / `PaperWorkspacePage.tsx:47-51`: `canUsePaperActions` against the **portfolio account's** ledger-sourced `execution_mode`/`execution_authority` (`paper_projections.py:190-205`) — a different payload than `/context` (`live_projections.py:283-299`). The two can disagree (e.g. ledger says `PAPER_ONLY` while store context says `BLOCKED` after `execution_deferred`, `live_projections.py:293-295`).
   - `PaperNowPage.tsx:61` additionally narrows to `PAPER_ONLY` only, while `OrderTicket.tsx:66-68` and `hasPaperAuthority` (`modeAuthority.ts:17-24`) also accept `AUTHORIZED`. A draft can be previewable in Paper Command but re-gated in the workspace, or vice versa.
   - `OptionsProductSurface.tsx:44` / `FuturesProductSurface.tsx:38` pass `undefined` context → permanently closed gate (dead UI path to `DerivativePaperPreviewPanel`).

2. **"Health/quality" is four vocabularies on one screen.** `ContextBar` shows `/context` `quality_summary.state` (GOOD/PARTIAL/DEGRADED/STALE/UNAVAILABLE or PASS/STALE/DEGRADED/UNAVAILABLE depending on live override, `projections.py:77-83` vs `live_projections.py:137-146`); paper pages show `data_health.state` (PASS/UNKNOWN/STALE/DISCONNECTED/RESTORED); `PaperExceptionsPanel` judges health with its own ok-set `{PASS,HEALTHY,CURRENT,AVAILABLE}` (`paperDashboardViewModel.ts:8`) — `GOOD` is **not** in it, and `CURRENT`/`AVAILABLE` are never emitted by the audited backend sources (?). Discover shows a fifth (`LIVE/DELAYED/SNAPSHOT/STALE/UNAVAILABLE`). The redesign's "Market data is partially degraded…" adapter must unify these without inventing truth.

3. **Same endpoint, different cadence/cache.**
   - Provider health: React Query 5s poll (`hooks.ts:353`) vs Discover's server-driven ~3s poll with its own embedded `provider_health[]` (`DiscoverObservability.tsx:241, 346-355`) vs operator readiness 60s staleTime (`hooks.ts:75`) vs `OperatorControlCenterPage` manual fetch (`OperatorControlCenterPage.tsx:23-41`). Discover can show "Moomoo CONNECTED" while the diagnostics page shows `RECONNECTING` simply due to timing.
   - Canary snapshot: same account but **four different lane ids** (`"now"` `ModeNowRoute.tsx:60`, `"portfolio"` `ModePortfolioRoute.tsx:26`, `"canary-plane"` `LiveCanaryControlPlanePage.tsx:41`, per-lane `LiveLaneOperationalStrip.tsx:12`) → four cache entries (`hooks.ts:50-52`) polling at 15s, unsynchronized; two panels on screen can show different broker snapshots.

4. **Frozen vs current evidence divergence for the same instrument.** Workspace overview always fetches squeeze `frozen` (`WorkspaceRoute.tsx:46` default, `hooks.ts:110-116`); the dedicated squeeze lane reads `?data_mode=current` from the URL (`ModeSqueezeWorkspaceRoute.tsx:21-24`, `SqueezeWorkspaceObservability.tsx:19-21`); the evidence lane independently derives `current` when `/context` is live (`hooks.ts:130-137`). Overview and lane can simultaneously present different cohorts (frozen research vs ephemeral scanner) for one symbol.

5. **UI mode vs backend mode.** Client-side `selectedMode` (`ApplicationBootstrap.tsx:28`) drives all page chrome; backend `/context` drives `ContextBar`/`ModeEnvironmentBar`. On mismatch, `ModeEnvironmentBar.tsx:33-39` warns, but e.g. Paper pages still render "Paper-only simulation" eyebrows and the lane draft link (`LaneModeContextPanel.tsx:110`) appears on PAPER chrome regardless of authority. `ContextBar` can simultaneously show `DATA LIVE OBSERVATIONAL` + `AUTH BLOCKED` while the page says "Paper · Simulation context" (`WorkspaceModuleModeShell.tsx:64-66`).

6. **Portfolio session state from three sources.** `/paper/portfolio` session block (zod) vs raw `/paper/sessions` list (`PaperPortfolioPage.tsx:38-42`, no schema, refetch keyed on session id change only) vs `/operator/state` sessions (`OperatorSettingsPage.tsx:135-143`). After `Archive session`/`New Paper Session`, the React-Query portfolio invalidates (`hooks.ts:341-346`) but the raw session list only refetches when the session id changes — stale history rows persist.

7. **Dual query-key systems.** `hooks.ts` keys vs unused `queryKeyFactory` (`queryKeyFactory.ts:13-128`) with incompatible shapes for the same resources; `useInvalidatePaper` (`hooks.ts:301-319`) prefix-invalidates `["paper","strategy-profitability"]` / `["paper","trace"]`, which would not match factory keys. Any future code using the factory silently escapes invalidation. Also `usePaperStrategyProfitabilityQuery` embeds account/session in the key but sends no params (`hooks.ts:290-298`) — key implies isolation the request doesn't have; and it fires with `"unbound"` key before the portfolio loads.

8. **Active-instrument propagation is split-brain.** UI route param is local truth; backend persists its own active instrument via fire-and-forget POSTs (`WorkspaceObservability.tsx:86-102` on every instrument change; `LiveObservationalPanel.tsx:51-56`; `LiveSymbolLookup.tsx:86-91`) resolved through a 7-level fallback chain (`IMP/src/market_platform_foundation/ui_api/operator_instrument.py:78-122`: ticket > workspace > explore > paper-session > scope > fixture/none) and surfaced as `/context` `active_instrument`/`active_instrument_source` (`schemas.ts:144-145`), used by `WorkspaceIndex.tsx:12-24` redirects and live as-of-time focus (`projections.py:43-54`). Silent POST failure (`.catch(() => undefined)`) leaves backend focus diverged from the visible workspace.

9. **Raw-fetch surfaces skip auth, schema, and React Query.** Discover, canary, operator settings/state, startup, workspace-layout, recent-instrument, and even `endpoints.ts` hand-written POSTs (`scrubReplay` :59, `createAssistantConversation` :124, `submitAssistantPrompt` :133, `subscribeLive` :243) omit `authHeaders()`. Under enforced (non-`LOOPBACK_TRUST`) auth these surfaces 401 while the rest of the app works — presenting as contradictory "some panels broken" states. They also never produce `ApiRequestError`, so error taxonomy rendering is inconsistent.

10. **`/explore?q=` dead param.** `ImpCommandSearch.tsx:24` navigates to `/explore?q=...` for non-ticker input, but no component reads `q` (only `data_mode` is read via `useSearchParams`, `ModeSqueezeWorkspaceRoute.tsx:21-22`). Search context is silently dropped.

11. **Dead/mismatched mode label branch.** `workspaceHealth.ts:9` checks `CAPTURE_REPLAY`, which is not a backend `DATA_MODES` value (`operating_modes.py:8-13`); the intended `HISTORICAL_CAPTURE` case renders as raw "HISTORICAL CAPTURE".

12. **Paper order-history key is unscoped.** `["paper","order-history"]` (`hooks.ts:41`) has no account/mode dimension; `queryKeyFactory.paperOrderHistory` would scope by mode+account (`queryKeyFactory.ts:68-69`). Account switches (new session) rely solely on invalidation (`hooks.ts:307`).

---

## Realtime mechanisms & selected-instrument context

**No websocket or SSE anywhere in the UI** (grep for `WebSocket|EventSource` across `ui/src` = 0 matches). All freshness is polling:

- React Query `refetchInterval`: provider health 5s (`hooks.ts:353`); canary snapshot + reconciliation 15s (`hooks.ts:363, 372`); canary reliability 15s (`LiveCanaryControlPlanePage.tsx:45`); workspace order-flow / order-book / market-state 2s **only when `/context` says `LIVE_OBSERVATIONAL`** (`hooks.ts:125, 164, 433`); workspace evidence 5s when live (`hooks.ts:137`).
- Hand-rolled timers: `DiscoverObservability.tsx:239-265` — `setInterval` poll at server-provided `poll_interval_seconds` (default 3s) + refresh at `refresh_interval_seconds` (default 120s), paused on `document.hidden`, with a `keepalive` POST `/discover/mixed/release` on unmount (:226-234). `ImpVelaChartLabPage.tsx:33` local tick timer (non-backend).
- Everything else: default React Query refetch-on-window-focus + explicit invalidation after mutations (`useInvalidatePaper`, `hooks.ts:301-319`; subscribe invalidation, `hooks.ts:446-449`; scrub → `refreshAll`, `App.tsx:257-264`).

**Selected-instrument context propagation:**
1. Route param `:symbol` → decoded by `useWorkspaceInstrumentId` (`IMP/ui/src/components/workspace-module-shared/useWorkspaceInstrumentId.ts:4-9`) or inline (`WorkspaceRoute.tsx:33-34`); fallback `ADMITTED_REPLAY_INSTRUMENT_ID` ("BIYA").
2. URL query `?data_mode=current` — squeeze lane only.
3. React Router `location.state` — `PaperOrderDraft` handoff (validated by `parsePaperOrderDraft`, `IMP/ui/src/components/paper-now/paperOrderDraft.ts:140-166`; consumed `WorkspaceRoute.tsx:36-39`, cleared after read :42-44).
4. Backend-persisted operator state: POST `/operator/recent` (recents + explore-selection preference, `operator_projections.py:196-208`), POST `/operator/workspace` (layout incl. `selected_instrument`, `operator_projections.py:211-219`), paper-session preferred instrument (`operator_instrument.py:13, 67-75`) → resolved by `resolve_active_operator_instrument` → `/context` `active_instrument` + `scope_symbols` → `WorkspaceIndex` redirect and live quote focus.
5. No global client store (no Redux/Zustand); cross-page state is React Query cache + router + backend persistence.

---

## Mutation paths & guards

Redesign must preserve these exactly.

| Mutation | Path | Client guards | Post-action |
|---|---|---|---|
| Preview paper order | POST `/paper/orders/preview` (`endpoints.ts:158-159`, zod `PaperOrderPreviewResponseSchema`) | `OrderTicket.tsx`: `authorized` (authority+mode props, :66-68), `canPreview` = symbol ∧ 1 ≤ qty ≤ `maxOrderShares` (:75); `PaperNowPage.tsx:61` stricter authority; draft validation `createPaperOrderDraft` (`paperOrderDraft.ts:124-138`); idempotency: `client_order_id`/`idempotency_key` = per-attempt UUID (`paperOrderDraft.ts:340-355, 357-359`) | none (local state only) |
| Submit paper order | POST `/paper/orders` (`endpoints.ts:160-161`) | `OrderTicket.handleSubmit` (:160-183): requires current preview, `risk_status === "PASS"`, `confirmedRequestIsCurrent` (instrument/side/qty/MARKET/limits match, :77-85), **`preview_id` required — else `PREVIEW_REQUIRED` fail-closed** (:163-166); submit disabled otherwise (:316-320); generation counter discards stale preview responses (:59, 135-149) | `useInvalidatePaper` (`hooks.ts:301-319`): invalidates paperPortfolio, demoPortfolio, paperOrderHistory, `["paper","strategy-profitability"]`, `["paper","trace"]`, `["context"]`, + options/futures product keys when scoped |
| Open paper session | POST `/paper/sessions` body `{execution_mode: "INTERNAL_SIMULATION", preferred_instrument?}` (`endpoints.ts:162-170`, `hooks.ts:336`) | shown when `!authorized` (`OrderTicket.tsx:221-228`) or when `actionEligible` (`PaperPortfolioPage.tsx:89-105`) | invalidate + portfolio refetch |
| Close paper session | POST `/paper/sessions/close` (`endpoints.ts:171`) | `actionEligible` gate (`PaperPortfolioPage.tsx:90-96`) | invalidate |
| Cancel paper order | POST `/paper/orders/cancel` (`endpoints.ts:172-173`) | **defined but no UI call site** | — |
| Replay scrub | POST `/replay/scrub` `{cursor_index}` (`endpoints.ts:58-66`; `App.tsx:290-301`) | none beyond scrub state machine | `refreshAll` invalidates context/attention/opportunities/`["instrument"]` |
| Live subscribe | POST `/subscriptions` `{instrument_id, capabilities, consumer_id}` (`endpoints.ts:242-250`, `hooks.ts:437-450`) | selection required; health `available` gate in panels (`LiveObservationalPanel.tsx:16-26`) | invalidates providerHealth + context; POSTs `/operator/recent` + `/operator/workspace`; navigates to workspace |
| Opportunity ack | POST `/opportunities/{rowId}/{watch|dismiss|review}` (`opportunityClient.ts:75-97`) | `paperActions && !readOnly && onAckAllowed(row)` (`progressiveOpportunityModel.ts:224-225`) | invalidates opportunitiesSummary |
| Discover refresh | POST `/discover/mixed/refresh`; GET `/discover/run?force=1` (mutating GET); POST `/discover/promote-to-live-analysis`; POST `/discover/mixed/release` | `allowMutations` prop — true only on `PaperDiscoverPage.tsx:37`; Demo/Live discover read-only | local state |
| Operator lifecycle | POST `/operator/lifecycle/actions` `{action}` (zod enum); POST `/operator/providers/{p}/refresh`; POST `/operator/config/provider` (`endpoints.ts:236-241`) | `window.confirm` for `apply_update` (`OperatorControlCenterPage.tsx:105-113`); update gate `update.status === "AVAILABLE"` | manual refresh |
| Operator settings | POST `/operator/watchlist`; POST `/captures/replay`; GET `/captures` reindex (`OperatorSettingsPage.tsx:61-74, 151-181`) | `canMutateOperatorSettings` = client mode === PAPER only (`operatorSettingsMode.ts:5-7`); capture must be `AVAILABLE` | manual refresh |
| Workspace layout / recents | POST `/operator/workspace`; POST `/operator/recent` | none; fire-and-forget, errors swallowed | none |
| Auth | POST `/auth/login`, `/auth/logout` (`AuthProvider.tsx:94-123`) | — | token to sessionStorage |
| Assistant | POST `/assistant/conversations`; POST `/assistant/conversations/{id}/prompt` (`endpoints.ts:123-144`) | conversation auto-created on open (`App.tsx:246-255`) | invalidates assistant messages/conversations |

Fail-closed behaviors to preserve: authority loss hides the ticket but keeps observability (`PaperDecisionCockpit.tsx:84-108`); stale preview blocks submit (`paperPreviewPresentation.ts:88-98`); schema mismatch throws at the zod boundary (`fetchJson.ts:22-23`); unknown error categories fail closed (`errors.ts:41-42`); unknown capability states render as blocked (`capabilityPresentation.ts:13`); unknown lane provenance degrades the draft handoff with warnings (`paperOrderDraft.ts:206-236, 289-303`).

---

## Type/schema boundaries

- **Hand-written zod schemas, no codegen.** All UI contracts live in `IMP/ui/src/api/schemas.ts` (≈2100 lines) plus satellite schemas in `opportunityClient.ts` / `tradeReviewClient.ts`. There is no OpenAPI/JSON-schema generation from the Python backend; parity is maintained by hand and by contract tests (`IMP/ui/src/api/schemas.test.ts`, backend `IMP/tests/ui1/`). Backend validation exists only for the operating-mode tuple (`operating_modes.py:65-74`).
- **Validation at the boundary**: `fetchJson`/`postJson` run `schema.parse` (throw on mismatch) for ~40 endpoints. **Unvalidated holes**: `getExplain`/`getInspect` (`fetchRawJson`, `endpoints.ts:56-57`), `getPaperForwardTests` (`endpoints.ts:147-150`), `subscribeLive` (returns `response.json()` untyped, `endpoints.ts:249`), `scrubReplay` (:65), assistant create/prompt (parsed with schemas but no auth headers, :124-144), all of `liveCanary.ts` (type-cast only), `LiveCanaryControlPlanePage` reliability payload (hand-typed, :6-26), all of `DiscoverObservability` (hand-typed, :6-93), `OperatorSettingsPage` (hand-typed, :10-30), `AuthProvider` payloads (hand-typed, `AuthProvider.tsx:5-14`), `App.tsx` startup payload (:160-171), `PaperPortfolioPage` sessions (:17-24).
- **Deliberately loose fields**: `orders`/`fills` are `z.record(z.unknown())` in portfolio/history/preview (`schemas.ts:1756-1757, 1806-1807, 1840`); `position`/`identity`/`margin` records in G14 product schemas (:200-210, 226-235); `.passthrough()` on opportunity rows (`opportunityClient.ts:47`), provider `lifecycle`/`provider_summary` (`schemas.ts:284, 312`), several snapshot schemas. UI components read these with `String(row.state ?? "—")`-style coercion (`PaperPortfolioObservability.tsx:151-156`) — order/fill field names are conventions, not contracts.
- **Duplicate/parallel type definitions**: `liveDashboardViewModel.ts:5` re-derives `ProviderHealthResponse` from the zod schema (fine), but `live-now/liveCanarySnapshot.ts` is just a re-export barrel; `LiveCanaryControlPlanePage.tsx:6-26` re-declares a reliability payload type locally.
- **Constants duplicated UI-side**: admitted instrument ids (`schemas.ts:1713-1718`), role capabilities (`AuthProvider.tsx:26-46`), healthy-state sets (`paperDashboardViewModel.ts:8-11`, `liveDashboardViewModel.ts:108-128`, `capabilityPresentation.ts:8-12`) — all client-side mirrors of backend semantics that can drift.

---

## Observations & risks

- The redesign's semantic-state adapter should treat `/context` `as_of_context` + `quality_summary` + `capability_states` as the backbone, but must reconcile: portfolio account authority (ledger-sourced), canary safety strings, discover `data_status`, and per-lane `quality`/`freshness_label` — five overlapping state axes with different vocabularies and cadences (see Contradictions #1-#4).
- Genuine backend disagreement already has precedents to model: `WorkspaceEvidenceResponse.coherence_warning` (`schemas.ts:2007`) and `research_context_execution_authority` (`schemas.ts:2012`) — the backend already emits a "contexts disagree" signal on the evidence endpoint; the adapter's "Subsystem disagreement" concept should reuse this rather than inventing a new one. (Consumers: `buildPaperDecisionSnapshot` ? — verify rendering path.)
- `evaluateModeContext.actualSummary` (`modeAuthority.ts:53`) is the de-facto raw triple `DATA … · EXEC … · AUTH …` shown in `ModeEnvironmentBar` — the single best insertion point for the human-language adapter.
- Polling gaps after mutations: subscribe invalidates context+providerHealth but not `marketState`/lane queries (they self-heal on the next 2s tick only when live).
- `StartupRecoveryBanner` (`App.tsx:157-179`) and `OperatorSettingsPage` both read `/state/startup`; only the banner translates `crash_recovery` into language.
- Unknowns (`?`): full value sets for backend `capability_states[].state`, `mark_quality` from live quotes, order `state` strings beyond the terminal set, opportunity `lifecycle_state` enum, assistant `authority_boundary` values, `session.status` values in `/paper/sessions`, `market_session` values, `mode_label` values on squeeze/explore rows, whether `/canary/*` routes require auth under enforcement, and whether the UI is ever served behind the vite proxy in normal operation (canary/opportunities routes are absent from the proxy allowlist).
