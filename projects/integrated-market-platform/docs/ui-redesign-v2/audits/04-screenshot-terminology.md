# Screenshot & Terminology Audit

**Scope:** Current-UI screenshot audit (10 attachments, S1–S10) + terminology/jargon exposure audit of the UI source.
**Source tree audited:** `projects/integrated-market-platform/ui/src` in the `ui/operator-redesign-v2` worktree (`market-trading-platform-ui-redesign`). All `file:line` refs below are relative to `projects/integrated-market-platform/` in that worktree.
**Method note (important):** The screenshots show the *running production build* during a live session. That build **predates the current source tree** — the worktree already contains a redesigned chrome (sidebar `ImpProductChrome`, `ModeEnvironmentBar`, new nav labels, new Overview). Page-*body* components (Portfolio, Diagnostics, Settings, Operator Center, Model Lab, Research, Workspace panels, attention cards) still match the screenshots closely, so jargon citations for those are exact. Screenshot-visible chrome strings that no longer exist in source are marked **[screenshot-only]**. See *Observations & risks*.

---

## Per-screenshot analysis

### S1 — OVERVIEW (route `/`, Demo replay mode)

**What is displayed:** Persistent top context bar: `DATA FIXTURE_REPLAY` · `EXEC INTERNAL_SIMULATION` · `AUTH PAPER_ONLY` · `AS OF 2026-08-29T20:59:58.984238+00:00` · `SCOPE —` · `QUALITY STALE` (amber). Top-right: orange `DEMO REPLAY · READ-ONLY` pill and a `Session 6a2f1c…` chip. Horizontal nav: OVERVIEW / WORKSPACE / RESEARCH / PORTFOLIO / RISK / LAB / DIAGNOSTICS / SETTINGS. Page body: `MARKET OVERVIEW` heading; left column `WHAT MATTERS NOW` attention cards (symbol chip e.g. BIYA, headline, monospace SNAKE_CASE reason-code chips, buttons *Why here? / Explain / Inspect / Open workspace*); right column `MARKET PULSE` metric rows and a `SESSION CONTEXT` panel.

**What works:**
- L1 intent is right: the attention queue is the first thing on the page, and every card carries evidence drill-down actions (*Why here? / Explain / Inspect / Open workspace*) — matches `ui/src/components/AttentionFeed.tsx:43-55`.
- Read-only boundary is visible at all times via the `DEMO REPLAY · READ-ONLY` pill.
- Consistent dark graphite panel system; no page-level horizontal overflow at 1920px.

**Confusing / redundant / missing:**
- `SESSION CONTEXT` repeats the entire top context bar (data mode, exec, authority, as-of, scope, quality) a second time in the L1 viewport — pure duplication, zero new information.
- `MARKET PULSE` is unlabeled metric rows with no interpretation (no "what changed", no thresholds, no "so what").
- Attention cards show *what* (headline + reason codes) but not *why now*, *what changed*, evidence strength, freshness, or next action — the opportunity 9-question rule is mostly unmet at L1; everything is behind buttons.
- `SCOPE —` renders an empty scope as a bare dash, which reads as "broken" rather than "no instrument selected" (`ui/src/components/ContextBar.tsx:49-57`).

**Overexposed technical detail:** Full SNAKE_CASE enums in the persistent bar (`FIXTURE_REPLAY`, `INTERNAL_SIMULATION`, `PAPER_ONLY`, `STALE`); raw ISO-8601 timestamp with microseconds and `+00:00` offset; truncated session UUID in chrome; reason-code chips rendered as raw `<code>` (`ui/src/components/AttentionFeed.tsx:37`). `MARKET OVERVIEW` / `MARKET PULSE` / `SESSION CONTEXT` / badge / session chip are **[screenshot-only]** strings — not present in worktree source.

**Status decodability:** A human cannot decode "is this live? can I trade? is my data healthy?" without backend vocabulary. `QUALITY STALE` is color-accented text with no cause, no affected surface, no action.

### S2 — WORKSPACE (route `/workspace/BIYA`, Demo replay)

**What is displayed:** Instrument header for BIYA; a 10-item module tab row (SQUEEZE, ORDER FLOW, ORDER BOOK, OPTIONS, LARGE TRANSACTIONS, FUTURES, CATALYST, FUND/ETF, DISCLOSURE, INSTITUTIONAL FLOW); replay scrubber (`Replay cursor N / M` + range slider — `ui/src/components/workspace-shared/WorkspaceObservability.tsx:122-133`); `WHAT MATTERS NOW` lanes table (Lane / Relevance / State / Freshness); price chart; `Derived features` grid with epistemic chips; squeeze panel with `STATE: …`, `Freshness: …`, evidence cards and a `2 PASS / 3 FAIL / 1 UNKNOWN`-style phase summary.

**What works:**
- The lanes table is a genuine L1→L2 bridge: lane, relevance, plain-ish summary, freshness (`ui/src/components/workspace/WhatMattersNowPanel.tsx:34-58`).
- Direct-manipulation replay scrubber with Previous/Next; chart anchors evidence markers.
- Lane names are humanized with underscore replacement (`WhatMattersNowPanel.tsx:48`) — the right instinct, applied inconsistently elsewhere.

**Confusing / redundant / missing:**
- Relevance `HIGH/MEDIUM/LOW` rendered raw with no criteria or tooltip (`WhatMattersNowPanel.tsx:52`); `Freshness` shows `STALE` with no "stale since when" (`:55`).
- `STATE: PRE_IGNITION`-style raw state-machine enums and `Freshness: STALE` in the squeeze block (`ui/src/components/squeeze/StateTransitionBlock.tsx:19-20`).
- `2 PASS / 3 FAIL / 1 UNKNOWN` (`ui/src/components/squeeze/SqueezeWorkspacePanel.tsx:97`; fixture example `ui/src/components/squeeze/fixtures.ts:16`) — pass/fail of *what rules*? No link, no legend, no consequence.
- `Derived features` grid pairs raw `feature_id` snake_case names with epistemic-class chips (`OBSERVED`/`DERIVED`) that no operator can decode (`WorkspaceObservability.tsx:141-151`).
- The 10-tab module row is dense and a horizontal-overflow risk below ~1440px (fits at 1920px in the screenshot).

**Overexposed technical detail:** ignition state enums, epistemic classes, feature IDs, `phase3a_summary` ("Phase 3A" program vocabulary), raw freshness labels.

**Status decodability:** Moderate for "what lane matters", poor for "can I trust this evidence" — that requires knowing what `OBSERVED` vs `DERIVED` vs `INFERRED` means.

### S3 — WORKSPACE with command palette (Ctrl+K)

**What is displayed:** Centered modal command palette over the dimmed workspace: search input ("type a command or search"), a grouped command list dominated by navigation actions (Go to Overview/Workspace/Research/Portfolio/Risk/Lab/Diagnostics/Settings, module/workspace openers, replay Previous/Next, assistant toggle), and a keyboard-hint footer (arrows navigate, Enter selects, Esc closes).

**What works:**
- Keyboard-first operation is real: Ctrl+K opens, hints are visible, Esc closes. The worktree retains this via `ui/src/components/imp-product/ImpProductChrome.tsx:93-99` plus a `?` shortcuts dialog (`ImpKeyboardShortcuts`).
- Palette is the one place commands are *grouped and labeled* rather than enum-tagged.

**Confusing / redundant / missing:**
- The list is mostly nav duplication — the same 8 destinations already visible in the nav bar; few context-aware actions (no "New paper session", "Archive session", "Refresh provider" despite those existing on pages).
- No visible fuzzy matching or recent/frequent ordering; long command lists will not scale.
- **[screenshot-only]** The modal palette itself no longer exists in worktree source; it was replaced by a top-bar search input (`ui/src/components/imp-product/ImpCommandSearch.tsx:27-42`) that only routes ticker patterns to `/workspace/:symbol` and everything else to `/explore?q=`. That is a *regression in command discoverability* relative to S3 — flag for the redesign program.

### S4 — RESEARCH (route `/research`, Analytics tab)

**What is displayed:** Tab row ANALYTICS / MODEL LAB / SIMULATION; a meta line `Epistemic class: OBSERVED · Boundary: RESEARCH_ONLY`; disclaimer paragraph; analytics charts (decision-distribution bar charts); tables with raw timestamps.

**What works:**
- Tabs separate L2/L3 content cleanly (`ui/src/components/research-shared/ResearchObservability.tsx:33-62`).
- Disclaimers are present and the read-only nature of research is stated.

**Confusing / redundant / missing:**
- The `Epistemic class: … · Boundary: …` meta line is internal classification vocabulary in the primary viewport (`ResearchObservability.tsx:68`).
- Tables render raw ISO `observation_time` / `prediction_cutoff` values (`ui/src/components/research/ModelLabPanel.tsx:67-70`).
- No plain-language synthesis: the page shows distributions but never says "what does the model currently conclude, and how much should I trust it?"
- `admitted fixture` jargon appears in footers/hints (e.g. `ModelLabPanel.tsx:77` "Phase 5R — admitted fixture only. No trade authority.").

**Overexposed technical detail:** epistemic class, authority boundary, phase IDs, raw cutoff timestamps.

### S5 — PORTFOLIO (route `/portfolio`, Paper mode)

**What is displayed:** `PAPER PORTFOLIO` header with eyebrow `PAPER-ONLY SIMULATION` and a meta line `DATA: FIXTURE REPLAY · <provider> · QUALITY STALE · EXEC: INTERNAL SIMULATION · AUTH PAPER_ONLY · Session 6a2f1c4d… · cash starting 100000 minor` (`ui/src/components/paper-portfolio/PaperPortfolioPage.tsx:76-83`); *Archive session* / *New Paper Session* buttons; Account / P&L / Exposure / Risk metric panels; Positions, Orders, Fills tables (all empty in this session, with empty-state copy); `Data / execution health` panel (`Data quality STALE`, `Model UNAVAILABLE` + detail); `Session history` rows like `OPEN · 6a2f1c4d-… · FIXTURE_REPLAY / INTERNAL_SIMULATION` (`PaperPortfolioPage.tsx:159-162`).

**What works:**
- Complete account snapshot on one screen; empty states are explicit ("No open positions." — `ui/src/components/portfolio-shared/PaperPortfolioObservability.tsx:101`).
- Session actions are authority-gated with a human-readable restriction note when not eligible (`PaperPortfolioPage.tsx:109-115`).
- Risk limits (max order / max position) and kill-switch state are visible (`PaperPortfolioObservability.tsx:70-93`).

**Confusing / redundant / missing:**
- `cash starting 100000 minor` — money in integer minor units (cents) instead of `$100,000.00` (`PaperPortfolioPage.tsx:83`); same pattern in the Fills `Price (minor)` column (`PaperPortfolioObservability.tsx:190,199`).
- Header meta repeats the global context bar a *third* time (after top bar and Overview's session panel).
- `Data quality STALE` / `Model UNAVAILABLE` — which model? what does stale marks do to my P&L? The detail line exists (`PaperPortfolioObservability.tsx:220`) but the headline states fail the 3-question rule.
- Positions table has `Mark quality` and `Mark as of` columns that render raw `STALE` and a raw nanosecond epoch (`mark_as_of_ns`, `PaperPortfolioObservability.tsx:123-124`) when populated.
- Session history rows render raw `data_mode` / `execution_mode` enums with underscores (`PaperPortfolioPage.tsx:160`).

**Overexposed technical detail:** truncated session UUIDs in two places, raw enums, minor units, ns timestamps, `simulation_model ?? "UNAVAILABLE"` (`:216-217`).

### S6 — RISK (nav RISK → route `/control`, "Operator center")

**What is displayed:** Page titled *Operator center* with kicker `LOCAL PLATFORM CONTROL`: an `AT A GLANCE` hero (big lifecycle status, e.g. RUNNING, + readiness badge), buttons *Restart platform* / *Check for updates* / *Apply fast-forward update* (disabled with title), a `PROJECT SETUP / Ready to work` checklist (✓ / ! rows with label, detail, next action), `DATA CONNECTIONS / Provider readiness` cards (transport state badge; Credentials / Gate / Freshness rows; `Next: …` line; *Refresh* button), and `LOCAL CONFIGURATION / Provider credentials` forms (`ui/src/components/OperatorControlCenterPage.tsx:59-231`).

**What works:**
- **Best 3-question compliance in the app**: every readiness check has label + detail + `next_action` (`OperatorControlCenterPage.tsx:139-148`); every provider card has an explicit `Next: {provider.next_action}` (`:186`).
- Destructive update action is confirm-gated (`:105-111`); the "Live execution remains locked" boundary note is explicit (`:122-124`).

**Confusing / redundant / missing:**
- **Navigation semantics mismatch**: the nav label is RISK but the page is local-platform lifecycle/credentials IT-ops. An operator looking for the *trading* risk surface (kill switch, exposure, governor decisions) gets "Restart platform". Route map: `ui/src/components/NavShell.tsx:71-78` → `/control` → `ui/src/App.tsx:536`.
- Statuses are raw enums: lifecycle `status`, readiness `PASS`/`CHECKING`, `transport_state`, `credential_state`, `gate_state` (`OperatorControlCenterPage.tsx:90-93,133-135,170-183`).
- `Apply fast-forward update` is developer vocabulary; provider credential *forms* living under "Risk" is a security-UX smell (credential entry belongs in Settings).

**Overexposed technical detail:** raw state enums throughout; update channel jargon.

### S7 — LAB (nav LAB → `/research` Model Lab tab)

**What is displayed:** `Model Lab` panel: meta `Boundary: RESEARCH_ONLY · Epistemic: OBSERVED`; metric grid — Model family, Alignment type, **Strategy identity** (full mono hash), **Dataset fingerprint** (full mono hash), Walk-forward folds, Preregistration; `Signals: N · Abstentions: N · At cutoff: N`; interpretations table (Observation time / Outcome / Cutoff / Alignment, raw timestamps); footer `Phase 5R — admitted fixture only. No trade authority.` (`ui/src/components/research/ModelLabPanel.tsx:14-77`). In the worktree, `/lab` redirects to `/research` (`ui/src/App.tsx:403`) and the Lab nav item points at `/research` (`NavShell.tsx:80-88`) — the screenshot's separate RESEARCH and LAB items map to tabs of one page.

**What works:**
- Research-integrity concepts (preregistration status, walk-forward fold count, abstention counts) are surfaced at all — rare and valuable (`ModelLabPanel.tsx:40-53`).
- Explicit "No trade authority" footer.

**Confusing / redundant / missing:**
- Two full-length hashes in mono in the primary viewport (`strategy_identity_hash`, `dataset_fingerprint` — `ModelLabPanel.tsx:33-37`). Pure L4 content at L2.
- `Phase 5R` is internal program vocabulary; `Walk-forward folds` is unexplained quant jargon; `Boundary: RESEARCH_ONLY` / `Epistemic: OBSERVED` meta is code-speak (`ModelLabPanel.tsx:18`).
- No human summary of model quality ("is this model any good? what is it allowed to influence?").

### S8 — DIAGNOSTICS (route `/diagnostics/provider`, top)

**What is displayed:** `Provider diagnostics` h1; `MOOMOO · CONNECTED` h2 (raw `connection_state`); a long metric `<dl>`: Provider, `Role MARKET_DATA`, OpenD, Generation (raw provider generation id), Market session, `Basic quote HEALTHY`, `Trades HEALTHY`, `L2 depth UNAVAILABLE`, `Execution eligibility DISPLAY_ONLY`, Quote/Trade/Book lag p50/p95, Queue high-water, Dropped events, Duplicates, Reconnect count, Quota n/n, Last error; then an `ACTIVE SUBSCRIPTIONS` list of `BIYA · US_EQUITY_L1 · refs 1`-style rows (`ui/src/components/live/ProviderHealthPanel.tsx:30-121`).

**What works:**
- Comprehensive per-channel telemetry (entitlement × runtime-test per channel), lag percentiles, quota and reconnect counters — the *data* needed for diagnosis is all here (`ProviderHealthPanel.tsx:55-112`).
- Channel states derive from a clear rule (`channelState`: `UNAVAILABLE` if unentitled, else `HEALTHY`/`DEGRADED` — `ProviderHealthPanel.tsx:5-7`).

**Confusing / redundant / missing:**
- Debug-console appearance: every value is a raw wire enum. The single most important operator fact — `Execution eligibility DISPLAY_ONLY` ("this provider can never route orders") — is buried mid-list in code-speak (`ProviderHealthPanel.tsx:28,67`).
- `HEALTHY`/`DEGRADED`/`UNAVAILABLE` per channel with no "what does L2 depth being unavailable *affect*?" and no "do I need to do anything?" (`:56-64`).
- `Last error —` with no timestamp; `Generation` (a raw provider generation id) is meaningless to operators (`:47`).
- Capability IDs `US_EQUITY_L1` / `US_EQUITY_TICKER` / `US_EQUITY_DEPTH` rendered raw in headings logic and subscription rows (`:25-27,118-120`).

### S9 — DIAGNOSTICS (scrolled): simulation-gate JSON + FINVIZ block

**What is displayed:** The `Internal simulation gate` JSON detail block (expanded key/value tree of the execution gate payload), then `FINVIZ ELITE · <connection>` h2 with rows: `Role DISCOVERY / CONTEXT`, Authentication, Credential source, Credential generation, Recovery mode, `Last auth error NONE`; conditionally the hint `Finviz authentication requires operator action. Run: python tools/finviz/auth.py repair` (`ui/src/components/live/ProviderHealthPanel.tsx:123-160`).

**What works:**
- The JSON block uses the right L4 pattern — a collapsible `<details>` with a further-collapsed `Raw JSON` leaf (`ui/src/components/shared/JsonDetailPanel.tsx:39-49`). This is the progressive-disclosure mechanism the redesign should standardize on.
- The auth-repair hint answers "what happened / what to do" when shown (`ProviderHealthPanel.tsx:153-158`).

**Confusing / redundant / missing:**
- In the screenshot the gate block is expanded in the primary viewport, presenting as a giant internal-metadata wall — it should default closed and be labeled `Audit details`.
- `Credential generation` (a bare number), `Recovery mode`, `Last auth error NONE` are raw backend fields (`ProviderHealthPanel.tsx:143-152`).
- The repair action is a repo-relative CLI command — assumes the operator has a shell + repo; no in-UI alternative is offered.

### S10 — SETTINGS (route `/settings`)

**What is displayed:** `SETTINGS` h1 with `OPERATOR` eyebrow; a read-only restriction note (`Operator settings are read-only in DEMO mode.` + reason); `Provider` panel (OpenD status, `Ready for live observational No`, collapsible `OpenD technical details`); `State` panel (`Persistence ON`, `State dir C:\Users\…` filesystem path, `Schema` version number, `Restore … · NONE`, `Execution deferred NO`); `Paper` session list (`OPEN · 6a2f1c4d…` rows); `Storage` panel (full capture IDs + status + provider + *Replay* buttons); `UI` panel (recent instruments, default watchlist); `Safety env (read-only)` raw JSON (`ui/src/components/OperatorSettingsPage.tsx:77-220`).

**What works:**
- The mode-based read-only restriction is explained in a human sentence with the reason (`OperatorSettingsPage.tsx:79-84`; `ui/src/components/operator-settings/operatorSettingsMode.ts:13`).
- Technical payloads are behind `<details>` panels (`:103`, `:218-219`) — right pattern.
- Watchlist and recent-instrument management exist and are mutation-gated in Demo.

**Confusing / redundant / missing:**
- Raw filesystem path, schema integer, `Restore … · NONE`, `Execution deferred NO` — none of these answer "does anything need my attention?" (`:111-130`).
- Paper sessions are `status · truncated-uuid` with no started-when, no human name (`:138-140`); storage capture rows render **full untruncated capture IDs** (`:163-164`).
- `Safety env (read-only)` is a raw JSON dump — safety configuration is exactly what an operator *would* want summarized in words ("kill switch armed: no; max order: 500 sh").

---

## Enum/jargon exposure map

User-facing renderings of backend enums/jargon found in `ui/src` (test files excluded). "Detail surface" = where the raw value should live under progressive disclosure.

| # | Rendered string (example) | Location (file:line) | Page / surface | Human-language replacement | Raw value retained in |
|---|---|---|---|---|---|
| 1 | `DATA FIXTURE_REPLAY` / `LIVE OBSERVATIONAL · MOOMOO` | `ui/src/components/ContextBar.tsx:9-12,31-33` | Global context bar (S1–S10) | "Demo replay (recorded data)" / "Live market data · Moomoo (read-only)" | Audit details: `data_mode`, `data_provider` |
| 2 | `EXEC INTERNAL_SIMULATION` / `INTERNAL SIMULATION · PAPER ONLY` | `ui/src/components/ContextBar.tsx:15-23,35-37` | Global context bar (S1–S10) | "Paper trading (simulated fills)" / "No execution" | Audit details: `execution_mode` |
| 3 | `AUTH PAPER_ONLY` (raw, underscores intact) | `ui/src/components/ContextBar.tsx:39-42` | Global context bar (S1–S10) | "Paper orders only" | Audit details: `execution_authority` |
| 4 | `AS OF 2026-08-29T20:59:58.984238+00:00` (raw ISO µs) | `ui/src/components/ContextBar.tsx:44-47` | Global context bar (S1–S10) | "Data as of 4:59 PM ET · updated 2m ago" | Technical details: raw ISO |
| 5 | `QUALITY STALE` (raw `quality_summary.state`) | `ui/src/components/ContextBar.tsx:58-61` | Global context bar (S1–S10) | "Market data is stale — quotes may be delayed." + link | Technical details: state + `detail` |
| 6 | `SCOPE —` / `SELECT AN INSTRUMENT` | `ui/src/components/ContextBar.tsx:49-57`; `ui/src/components/paper/OrderTicket.tsx:233,249` | Context bar; order ticket | "No instrument selected" | — |
| 7 | `DATA … · EXEC … · AUTH …` mismatch/aligned summary | `ui/src/components/mode-session/modeAuthority.ts:54` → `ui/src/components/mode-session/ModeEnvironmentBar.tsx:34-43` | Mode environment banner | "Backend is in demo replay with execution disabled" | Audit details |
| 8 | `DATA: FIXTURE REPLAY · … · QUALITY STALE · EXEC: INTERNAL SIMULATION · AUTH PAPER_ONLY` | `ui/src/components/paper-portfolio/PaperPortfolioPage.tsx:76-77` | Portfolio header meta (S5) | "Paper account · demo data · data stale" | Audit details |
| 9 | `cash starting 100000 minor` | `ui/src/components/paper-portfolio/PaperPortfolioPage.tsx:83` | Portfolio header (S5) | "Starting cash $100,000.00" | Technical details: minor units |
| 10 | `OPEN · 6a2f1c4d-… · FIXTURE_REPLAY / INTERNAL_SIMULATION` | `ui/src/components/paper-portfolio/PaperPortfolioPage.tsx:159-162` | Portfolio session history (S5) | "Open · started Sep 12 · demo replay / paper" | Audit details: full session id |
| 11 | `Mark quality STALE`, `Mark as of <ns epoch>` | `ui/src/components/portfolio-shared/PaperPortfolioObservability.tsx:123-124` | Positions table (S5) | "Price stale · last updated 12m ago" | Technical details: `mark_quality`, `mark_as_of_ns` |
| 12 | `Price (minor)` / raw `fill_price_minor` | `ui/src/components/portfolio-shared/PaperPortfolioObservability.tsx:190,199`; `ui/src/components/research/SimulationLabPanel.tsx:37,45,107`; `ui/src/components/live/LiveCanaryControlPlanePage.tsx:132` | Fills; Simulation Lab; canary | Format as currency | Technical details |
| 13 | `Data quality STALE` / `Model UNAVAILABLE` | `ui/src/components/portfolio-shared/PaperPortfolioObservability.tsx:213-220` | Portfolio data-health panel (S5) | "Mark data is stale — unrealized P&L may be inaccurate." | Technical details: `data_health.state`, `simulation_model` |
| 14 | Raw order `state` (`String(order.state)`) | `ui/src/components/portfolio-shared/PaperPortfolioObservability.tsx:155`; `ui/src/components/paper-portfolio/paperOrderHistoryModel.ts:161` (`UNKNOWN`) | Orders tables | Human order states ("Filled", "Rejected") | Audit details |
| 15 | `<code>SQUEEZE_IGNITION_WATCH</code>`-style reason chips | `ui/src/components/AttentionFeed.tsx:36-38`; `ui/src/components/paper-now/PaperCandidateQueue.tsx:57`; `ui/src/components/paper-workspace/PaperHandoffPanel.tsx:68-70`; `ui/src/components/paper-portfolio/PaperPersistedSourceContextPanel.tsx:58-60` | Attention cards (S1), candidate queues | Human reason label primary ("Ignition watch triggered") | Technical details: `reason.code` |
| 16 | `tier-1`/`tier-2` color-only card class | `ui/src/components/AttentionFeed.tsx:29`; `ui/src/styles/layout.css:264` | Attention cards (S1) | Add textual tier label ("Tier 1 — act now") | — |
| 17 | `HIGH`/`MEDIUM`/`LOW` relevance, raw `freshness_label`, `evidence {mix_summary}` | `ui/src/components/workspace/WhatMattersNowPanel.tsx:31,52,55`; `ui/src/components/paper-workspace/PaperWhatMattersNow.tsx:30,44-47` | Workspace lanes table (S2) | "High relevance" + why-tooltip; "updated 5m ago" | Audit details |
| 18 | `STATE: PRE_IGNITION` / `Freshness: STALE` / `{from} → {to}` raw states | `ui/src/components/squeeze/StateTransitionBlock.tsx:19-20,87,112` | Squeeze panel (S2) | "Squeeze state: pre-ignition" | Audit details: state machine values |
| 19 | `2 PASS / 3 FAIL / 1 UNKNOWN`; raw `outcome_status` / `evidence_coverage` / `research_detection` | `ui/src/components/squeeze/SqueezeWorkspacePanel.tsx:85-97`; `ui/src/components/squeeze/HistoricalSqueezeContextBlock.tsx:26` | Squeeze panel (S2) | "2 of 6 checks passing · 3 failing · 1 unknown" + rule links | Audit details |
| 20 | Epistemic chips `OBSERVED` / `DERIVED` / `INFERRED` | `ui/src/components/workspace-shared/WorkspaceObservability.tsx:146`; `ui/src/components/orderflow/OrderFlowWorkspacePanel.tsx:59`; `ui/src/components/orderbook/OrderBookWorkspacePanel.tsx:88`; `ui/src/components/options/OptionsWorkspacePanel.tsx:92`; `ui/src/components/options/OpportunityFusionBlock.tsx:86`; `ui/src/components/largetransactions/LargeTransactionsWorkspacePanel.tsx:62`; `ui/src/components/futures/FuturesWorkspacePanel.tsx:95`; `ui/src/components/fundetf/FundEtfWorkspacePanel.tsx:56`; `ui/src/components/disclosure/DisclosureWorkspacePanel.tsx:93`; `ui/src/components/catalyst/CatalystWorkspacePanel.tsx:56`; `ui/src/components/squeeze/SqueezeWorkspacePanel.tsx:105` | Workspace lanes + derived features (S2) | "From provider data" / "Calculated by IMP" / "IMP inference — unverified" | Audit details: `epistemic_class` |
| 21 | `Epistemic class: OBSERVED · Boundary: RESEARCH_ONLY` | `ui/src/components/research-shared/ResearchObservability.tsx:68`; `ui/src/components/research/ModelLabPanel.tsx:18`; banner `ui/src/components/research/SimulationLabPanel.tsx:24-26` | Research (S4), Lab (S7) | "Research-only evidence — not tradeable" | Audit details |
| 22 | `UNAVAILABLE — WHALE_NO_ENTITLED_SOURCE` | `ui/src/components/orderflow/OrderFlowWorkspacePanel.tsx:28`; `ui/src/components/orderbook/OrderBookWorkspacePanel.tsx:26`; `ui/src/components/options/OptionsWorkspacePanel.tsx:57`; `ui/src/components/largetransactions/LargeTransactionsWorkspacePanel.tsx:26`; `ui/src/components/futures/FuturesWorkspacePanel.tsx:26`; `ui/src/components/fundetf/FundEtfWorkspacePanel.tsx:26`; `ui/src/components/disclosure/DisclosureWorkspacePanel.tsx:52`; `ui/src/components/catalyst/CatalystWorkspacePanel.tsx:26` | All whale-data workspace lanes | "Not available with your current data subscription — this lane is disabled." | Technical details: `reason` code |
| 23 | `UNAVAILABLE — no admitted replay fixture for {symbol}` | `ui/src/components/workspace-shared/WorkspaceObservability.tsx:156` | Workspace price/replay panel | "No replay data for {symbol} in this demo build." | Technical details |
| 24 | `UNAVAILABLE — no PIT-eligible market-context signals at cutoff` | `ui/src/components/squeeze/CatalystAttentionBlock.tsx:22` (+ `UNAVAILABLE` fallbacks `:36-90`) | Catalyst attention block | "No point-in-time-safe context signals at this replay point." | Technical details |
| 25 | `STRATEGY_UNAVAILABLE` / `EXECUTION_UNAVAILABLE` / `FUSION_UNAVAILABLE` / `DEALER_POSITION_UNKNOWN` fallbacks; `Replay hash: {hash}` | `ui/src/components/options/StrategyOptimizerBlock.tsx:17-18,72`; `ui/src/components/options/ExecutionSimulationBlock.tsx:28-29,81-82`; `ui/src/components/options/OpportunityFusionBlock.tsx:65-66,126-127`; `ui/src/components/options/DealerPositioningBlock.tsx:17` | Options workspace blocks | Human outcome sentences; drop hash from primary view | Audit details: reason + `replay_hash` |
| 26 | `MOOMOO · CONNECTED` / `FINVIZ ELITE · {connection}` (raw `connection_state`, may be `CONNECTED_DEGRADED`) | `ui/src/components/live/ProviderHealthPanel.tsx:32,128` | Diagnostics (S8/S9) | "Moomoo — connected" / "Moomoo — connected with problems" | Technical details: `connection_state` |
| 27 | `HEALTHY` / `DEGRADED` / `UNAVAILABLE` channel states | `ui/src/components/live/ProviderHealthPanel.tsx:5-7,56-64`; `ui/src/components/live-now/liveDashboardViewModel.ts:21-22,66-76` | Diagnostics (S8); live ribbon | "Working" / "Degraded — quotes may lag" / "Not in your subscription" + affect | Technical details |
| 28 | `Role MARKET_DATA` · `Execution eligibility DISPLAY_ONLY` / `INTERNAL_PAPER_ELIGIBLE` | `ui/src/components/live/ProviderHealthPanel.tsx:28,40,67` | Diagnostics (S8) | "Market data only — cannot route orders" | Audit details |
| 29 | `US_EQUITY_L1` / `US_EQUITY_TICKER` / `US_EQUITY_DEPTH` capability IDs (+ `refs n`) | `ui/src/components/live/ProviderHealthPanel.tsx:25-27,118-120` | Diagnostics subscriptions (S8) | "US equities — basic quotes / trades / L2 depth" | Audit details |
| 30 | `Last auth error NONE`; `Run: python tools/finviz/auth.py repair` | `ui/src/components/live/ProviderHealthPanel.tsx:152-158` | Diagnostics FINVIZ (S9) | "No recent sign-in errors"; "Finviz sign-in needs repair — Settings → Providers (advanced: run …)" | Technical details |
| 31 | `EXEC NONE` | `ui/src/components/discover-shared/DiscoverObservability.tsx:341` | Discover header | "Trading disabled" | — |
| 32 | `Radar unready ({unready_reason})`; `Feed {feed_status}` (`UNREADY`) | `ui/src/components/imp-product/OpportunityFeedStatusBanner.tsx:36-40`; `ui/src/components/imp-product/OpportunityRadarDensePanel.tsx:39-41` | Overview/Radar feed banner | "Opportunity radar isn't ready: {human reason}." + action link | Technical details: `feed_status`, `unready_reason` |
| 33 | `Live blocked: {block_reasons.join(", ")}` raw codes | `ui/src/components/workspace-module-shared/LiveLaneOperationalStrip.tsx:59`; `ui/src/components/live/LiveCanaryControlPlanePage.tsx:80-86` | Live lanes; canary | Map each code to a sentence ("Live trading is blocked: daily loss limit reached") | Audit details: `block_reasons` |
| 34 | `Program {state} · Session {state}` (`UNKNOWN`), raw `broker_health` / `reconciliation_health` | `ui/src/components/workspace-module-shared/LiveLaneOperationalStrip.tsx:44-55`; `ui/src/components/live/LiveCanaryControlPlanePage.tsx:95-99,122-126` | Live lanes; canary | Human states ("Broker connection: healthy") | Audit details |
| 35 | Kill-switch raw states; `authorization_status ?? "NONE"` | `ui/src/components/live/LiveCanaryControlPlanePage.tsx:106-112,126`; `ui/src/components/live-portfolio/livePortfolioViewModel.ts:40`; `ui/src/components/live-now/liveDashboardViewModel.ts:169` | Canary; live portfolio/now | "Global kill switch: on" / "Not authorized" | Audit details |
| 36 | `Operational Reliability (BUILD 32)`; raw `observability_state` / SLO / `persistence_health.disposition`; raw `as_of_ns` | `ui/src/components/live/LiveCanaryControlPlanePage.tsx:154-164` | Canary reliability | "Operational reliability" + human states + human time | Technical details: build no., ns |
| 37 | `GATED` nav badge | `ui/src/components/NavShell.tsx:131` | Primary nav | "Locked in this mode" + reason on hover | — |
| 38 | `IMP_PAPER_EXECUTION=1` / `IMP_LIVE_OBSERVATIONAL=1` env vars in copy | `ui/src/components/paper/OrderTicket.tsx:223`; `ui/src/components/live/LiveObservationalPanel.tsx:22`; `ui/src/components/live-now/LiveSymbolLookup.tsx:37` | Order ticket; live panels | "Paper execution is off. Enable it in Settings → Safety." | Technical details: env var name |
| 39 | Inspector tab names `SUMMARY` / `TIMELINE` raw + raw JSON body | `ui/src/components/InspectorPanel.tsx:11,45,51` | Evidence inspector drawer | Title-case tabs; JSON behind a "Raw" tab | Raw JSON (already present) |
| 40 | `broker_order_id ?? "NONE"` | `ui/src/components/paper/ExecutionTracePanel.tsx:185` | Execution trace | "Not sent to broker" | Technical details |
| 41 | `Restore … · NONE` / `Execution deferred NO` / raw OpenD status / `State dir C:\…` / `Schema n` | `ui/src/components/OperatorSettingsPage.tsx:95,111-130` | Settings (S10) | "Crash recovery: none needed" / "Execution startup: normal" | Technical details |
| 42 | `PAPER · READ ONLY` badge; `READ-ONLY` variants | `ui/src/components/paper-strategy-profitability/PaperStrategyProfitabilityObservability.tsx:44` (+ 20 "read-only" copy sites, mostly human sentences) | Strategy profitability; misc | Mostly fine — keep sentence form ("Paper simulation — read-only") | — |
| 43 | `DEMO REPLAY · READ-ONLY` pill; `Session 6a2f1c…` chip; `MARKET OVERVIEW` / `MARKET PULSE` / `SESSION CONTEXT` headings; modal command palette | **[screenshot-only]** — not found in worktree source; produced by the older running build | Global chrome (S1–S10); Overview (S1); palette (S3) | "Demo replay — trading disabled"; human session label; see Observations | Audit details: full session id + copy |

---

## Warning quality vs 3-question rule

Rule: every warning/degraded/blocked/stale/unknown/failed condition must answer (1) **What happened?** (2) **What does it affect?** (3) **Do I need to do anything?** Verdicts: ✅ all three · ⚠️ partial · ❌ fails.

| # | State / message | Where | Q1 What | Q2 Affects | Q3 Action | Verdict | What's missing |
|---|---|---|---|---|---|---|---|
| 1 | `QUALITY STALE` badge | S1–S10; `ContextBar.tsx:58-61` | partial ("STALE") | ❌ | ❌ | ❌ | Cause, affected surfaces (marks? discovery? chart?), action. (`quality_summary.detail` exists but is unstructured and often absent.) |
| 2 | `DATA FIXTURE_REPLAY` / `EXEC INTERNAL_SIMULATION` / `AUTH PAPER_ONLY` | S1–S10; `ContextBar.tsx:31-42` | coded | ❌ | n/a | ⚠️ | Not warnings per se, but system state undecodable without backend knowledge. |
| 3 | `UNAVAILABLE — WHALE_NO_ENTITLED_SOURCE` | 8 lane panels (map row 22) | coded | implied (lane dead) | ❌ | ❌ | Human cause ("not in your subscription"), whether anything can enable it. |
| 4 | `UNAVAILABLE — no admitted replay fixture for {symbol}` | `WorkspaceObservability.tsx:153-160` | ✅ (jargon) | ✅ (chart) | ⚠️ hint "open one from EXPLORE" | ⚠️ | De-jargon "admitted replay fixture"; say which symbols do work. |
| 5 | `Paper execution is gated. Set IMP_PAPER_EXECUTION=1…` | `OrderTicket.tsx:221-227` | ✅ | ✅ | ⚠️ (env var + shell) | ⚠️ | In-UI path (Settings toggle) before CLI; env var to Technical details. |
| 6 | `Backend context unavailable. Execution controls remain locked.` | `ModeEnvironmentBar.tsx:27-31` | ✅ | ✅ | ❌ | ⚠️ | Recovery action ("check the local platform / retry"). |
| 7 | `Selected {mode}; backend reports DATA X · EXEC Y · AUTH Z…` | `ModeEnvironmentBar.tsx:33-38` + `modeAuthority.ts:54` | ✅ (raw enums) | ✅ | ❌ | ⚠️ | Human summary; what to do (switch mode or restart backend). |
| 8 | `Radar unready ({unready_reason}). Open Control Center` | `OpportunityFeedStatusBanner.tsx:36-43` | ⚠️ raw reason code | ✅ (no ranked opportunities) | ✅ link | ⚠️ | Humanize `unready_reason`. |
| 9 | `Live blocked: {block_reasons}` | `LiveLaneOperationalStrip.tsx:59`; `LiveCanaryControlPlanePage.tsx:80-86` | ⚠️ raw codes | ✅ | ❌ per reason | ❌ | Sentence per block reason + required action. |
| 10 | `Operational context unavailable. Provider health and canary snapshot could not be loaded for lane {id}.` | `LiveLaneOperationalStrip.tsx:29-36` | ✅ | ⚠️ | ✅ links | ⚠️ | Say evidence is untrusted/lower-confidence (it does in the sibling branch `:62`); lane id jargon. |
| 11 | `Previous paper session detected ({restore}). Positions restore from events; live marks wait for fresh Moomoo evidence.` | `App.tsx:163-166` | ✅ | ✅ | ❌ | ⚠️ | Whether operator must act (probably no — say so). |
| 12 | `Local state database failed integrity check. Original file was preserved.` | `App.tsx:166-168` | ✅ | ⚠️ | ❌ | ⚠️ | What still works / whether to contact support / where the file is. |
| 13 | `Replay status unavailable.` | `DemoReplayOverview.tsx:57-58` | bare | ❌ | ❌ | ❌ | Everything. |
| 14 | `Attention feed unavailable.` | `AttentionFeed.tsx:24` | bare | ❌ | ❌ | ❌ | Everything. |
| 15 | `Opportunity ranking unavailable.` | `OpportunityFeedStatusBanner.tsx:30-34` | bare | ❌ | ❌ | ❌ | Cause + action (link exists only for UNREADY, not error). |
| 16 | `Provider health unavailable.` | `ui/src/components/live-now/LiveProviderRibbon.tsx:14` | bare | ❌ | ❌ | ❌ | Everything. |
| 17 | `Simulation account observability unavailable.` | `PaperPortfolioPage.tsx:56-58` | bare | ❌ | ❌ | ❌ | Everything. |
| 18 | `Research analytics unavailable.` / `Model Lab unavailable.` / `Simulation Lab unavailable.` | `ResearchObservability.tsx:74,80,86` | bare | ❌ | ❌ | ❌ | Everything. |
| 19 | `The control center could not read local platform status.` + `Start the local platform, then check again.` | `OperatorControlCenterPage.tsx:37,79-83` | ✅ | ✅ | ✅ | ✅ | Model to copy. |
| 20 | `Finviz authentication requires operator action. Run: python tools/finviz/auth.py repair` | `ProviderHealthPanel.tsx:153-158` | ✅ | ⚠️ (discovery degraded — implied) | ✅ (CLI only) | ⚠️ | Say what loses freshness; offer in-UI repair. |
| 21 | `Session open failed` | `OrderTicket.tsx:190` | bare | ❌ | ❌ | ❌ | Cause + retry. |
| 22 | `Watchlist update failed` | `OperatorSettingsPage.tsx:70` | bare | ❌ | ❌ | ❌ | Cause + retry. |
| 23 | `Replay could not move. The last confirmed event remains visible.` | `DemoReplayOverview.tsx:102-104` | ✅ | ✅ | ❌ | ⚠️ | Why it failed / retry affordance. |
| 24 | `Mark quality STALE` (positions), `Data quality STALE` / `Model UNAVAILABLE` (health panel) | S5; `PaperPortfolioObservability.tsx:123,213-220` | coded | ❌ (P&L trust unstated) | ❌ | ❌ | "Unrealized P&L may be inaccurate"; refresh path. |
| 25 | `L2 depth UNAVAILABLE`, channel `DEGRADED` states | S8; `ProviderHealthPanel.tsx:56-64` | coded | ❌ | ❌ | ❌ | Per-channel "what stops working" + entitlement action. |
| 26 | `{outcome ?? UNAVAILABLE}` + `STRATEGY_UNAVAILABLE`-style reasons | options blocks (map row 25) | coded | ❌ | ❌ | ❌ | Human outcome + reason + whether retryable. |
| 27 | `UNAVAILABLE — no PIT-eligible market-context signals at cutoff` | `CatalystAttentionBlock.tsx:22` | ✅ (jargon) | ⚠️ | ❌ | ⚠️ | De-jargon "PIT-eligible"; say attention score is unavailable, not the world ending. |

**Score: 27 conditions evaluated — 1 ✅ pass, 9 ⚠️ partial, 17 ❌ fail.**

---

## Identifier exposure

Long identifiers (session IDs, UUIDs, hashes, fingerprints, internal IDs) rendered in primary UI surfaces. Redesign rule: truncate (`B74B…C9A2 [copy]`) and move full values to Audit/Technical details.

| # | Identifier | Where rendered | Surface | Truncation today | Recommendation |
|---|---|---|---|---|---|
| 1 | Session UUID chip `Session 6a2f1c…` | Global top bar, every page (S1–S10) — **[screenshot-only]** chrome of running build | L1 chrome | Truncated, no copy, no label meaning | Remove from chrome; if kept: "Paper session · started 9:12 AM" + Audit details |
| 2 | `Session {session_id.slice(0,12)}…` | `ui/src/components/paper-portfolio/PaperPortfolioPage.tsx:82` | Portfolio header (S5) | 12-char slice, no copy | Human label + truncated id with copy button |
| 3 | `{status} · {session_id.slice(0,12)}… · {data_mode} / {execution_mode}` | `PaperPortfolioPage.tsx:159-162` | Session history (S5) | 12-char slice | Date-based label; id to Audit details |
| 4 | `{session.status} · {session.session_id.slice(0,12)}…` | `ui/src/components/OperatorSettingsPage.tsx:138-140` | Settings → Paper (S10) | 12-char slice | Same |
| 5 | Full `capture_id` (untruncated) + status + provider | `OperatorSettingsPage.tsx:163-164` | Settings → Storage (S10) | **None** | Truncate + copy; human capture name/date primary |
| 6 | `{order_id.slice(0,8)}…` | `ui/src/components/portfolio-shared/PaperPortfolioObservability.tsx:200` | Fills table (S5) | 8-char slice, no copy | Keep short id but add copy + full id in trace drawer |
| 7 | `mark_as_of_ns` raw nanosecond epoch | `PaperPortfolioObservability.tsx:124` | Positions table (S5) | None | Human time ("12:00:01 ET · 2m ago"); ns to Technical details |
| 8 | `strategy_identity_hash` full mono | `ui/src/components/research/ModelLabPanel.tsx:33` | Lab (S7) | None | `B74B…C9A2 [copy]`; full value to Audit details |
| 9 | `dataset_fingerprint` full mono | `ModelLabPanel.tsx:37` | Lab (S7) | None | Same |
| 10 | `account_fingerprint` raw | `ui/src/components/live/LiveCanaryControlPlanePage.tsx:92-93`; `ui/src/components/live-portfolio/livePortfolioViewModel.ts:29-31` | Canary; live portfolio | None | Truncate + copy; Audit details |
| 11 | `as_of_ns` raw ns epoch (×2) | `LiveCanaryControlPlanePage.tsx:99,161` | Canary | None | Human time |
| 12 | Unresolved critical incident IDs raw | `LiveCanaryControlPlanePage.tsx:143-147`; `liveDashboardViewModel.ts:144` | Canary; live alerts | None | Incident title primary; id to Audit details |
| 13 | `Replay hash: {replay_hash}` / `execution_replay_hash` | `ui/src/components/options/StrategyOptimizerBlock.tsx:72`; `OpportunityFusionBlock.tsx:126-127`; `ExecutionSimulationBlock.tsx:81-82` | Options blocks | None | Remove from primary; Audit details |
| 14 | `intent_id` raw in risk-decisions table | `ui/src/components/research/SimulationLabPanel.tsx:86` | Lab simulation tab | None | Truncate + link to trace; Audit details |
| 15 | `provider_generation_id` / `provider_generation` raw | `ui/src/components/live/ProviderHealthPanel.tsx:46-47` | Diagnostics (S8) | None | Technical details |
| 16 | `correlation_id`, `broker_order_id` | `ui/src/components/paper/ExecutionTracePanel.tsx:16-31,185` | Execution trace drawer | None | Acceptable (drawer is L4) — add copy buttons |
| 17 | Expanded `Internal simulation gate` JSON (contains internal IDs/keys) | `ProviderHealthPanel.tsx:123-124` + S9 | Diagnostics primary viewport | n/a | Default-collapsed `Audit details` (pattern exists in `JsonDetailPanel.tsx:39-49`) |
| 18 | Filesystem path `State dir C:\Users\…` | `OperatorSettingsPage.tsx:115` | Settings (S10) | None | Technical details (or mono + ellipsis) |

**Total: 18 identifier-exposure sites (16 in worktree source, 2 screenshot-only chrome items), 9 of them with no truncation at all.**

---

## Top 10 UX offenses

Ranked by operator impact. Rules referenced: L1/L4 hierarchy, language rule, 3-question rule, opportunity 9-fields, no-overflow, no-debug-console, no color-only status.

1. **Raw backend enums as the persistent system-state bar** — `DATA FIXTURE_REPLAY · EXEC INTERNAL_SIMULATION · AUTH PAPER_ONLY` on every page (S1–S10; `ContextBar.tsx:31-42`). The three most important facts (is this real? can I trade? whose money?) require decoding three backend enums. *Violates: language rule, L1 hierarchy.*
2. **`QUALITY STALE` badge with no cause, impact, or action** (S1–S10; `ContextBar.tsx:58-61`). The only global data-health signal fails all three questions; operators learn to ignore it — alert fatigue on the worst possible signal. *Violates: 3-question rule.*
3. **Raw ISO-8601 microsecond timestamp in the global header** (S1–S10; `ContextBar.tsx:44-47`). `2026-08-29T20:59:58.984238+00:00` is unparsable at a glance and carries no freshness ("how old is my data *right now*?"). *Violates: L1 hierarchy, language rule.*
4. **Session-UUID chip in global chrome** (S1–S10, **[screenshot-only]**). An L4 identifier occupies the most permanent L1 slot on every screen, truncated without copy. *Violates: L1/L4 hierarchy, identifier rule.*
5. **RISK nav opens an IT-ops console, not trading risk** (S6; `NavShell.tsx:71-78` → `App.tsx:536` → `OperatorControlCenterPage.tsx`). An operator reacting to a risk event gets "Restart platform / Apply fast-forward update / provider credential forms" instead of kill switch, exposure, and governor state. *Violates: information hierarchy; mislabeled wayfinding is a safety issue.*
6. **SNAKE_CASE reason-code chips on the L1 attention queue** (S1; `AttentionFeed.tsx:36-38`). The "what matters now" cards — the top of the information pyramid — lead with `<code>` tokens instead of human sentences, and omit why-now/what-changed/evidence-strength/freshness. *Violates: language rule, opportunity 9-fields.*
7. **Diagnostics is a raw wire-state wall, plus an expanded JSON block in the primary viewport** (S8–S9; `ProviderHealthPanel.tsx:30-160`). `Role MARKET_DATA`, `DISPLAY_ONLY`, `US_EQUITY_L1 · refs 1`, `Last auth error NONE`, and an open `Internal simulation gate` JSON tree — the definition of debug-console appearance; the one decision-relevant fact ("this provider can never route orders") is buried. *Violates: no-debug-console, L4 progressive disclosure, 3-question rule.*
8. **Money and time in machine units** (S5; `PaperPortfolioPage.tsx:83` "100000 minor", `PaperPortfolioObservability.tsx:124` ns epochs, `:190` "Price (minor)", `SimulationLabPanel.tsx:37,45`). Operators must mentally convert cents and nanoseconds to know their own cash and mark times. *Violates: language rule.*
9. **Internal research vocabulary and full hashes at L2** (S4, S7; `ResearchObservability.tsx:68`, `ModelLabPanel.tsx:18,33-37,77`). `Epistemic class`, `Boundary`, `Phase 5R`, `admitted fixture`, plus two full mono hashes — audit metadata presented as page content. *Violates: L1/L4 hierarchy, language rule.*
10. **Bare "X unavailable." dead-ends and color-only tier encoding** (S1–S2; `AttentionFeed.tsx:24,29`, `DemoReplayOverview.tsx:58`, `ResearchObservability.tsx:74-86`, `PaperPortfolioPage.tsx:58`). Seventeen warning/empty states give no cause or next step, and attention-card tier is encoded only by border color (`layout.css:264`). *Violates: 3-question rule, no color-only status.*

*Runner-up:* the 10-tab workspace module row (S2) is a horizontal-overflow risk at <1440px — no overflow is visible at 1920px in any screenshot, but density is high and untested at narrower widths.

---

## Observations & risks

1. **Screenshot↔source drift (highest-risk caveat).** The running production build in S1–S10 predates the audited source. The worktree (`ui/operator-redesign-v2`, HEAD `d588728d`) already ships a redesigned chrome: sidebar navigation with new labels (`ui/src/components/NavShell.tsx:13-101`), `ImpProductChrome` top bar with search/`?`/Switch-mode (`ui/src/components/imp-product/ImpProductChrome.tsx:130-211`), `ModeEnvironmentBar` with human boundary sentences (`ui/src/components/mode-session/ModeEnvironmentBar.tsx:12-15`), and a new Overview (`ImpOverviewBoard`, "See the market unfold"). Screenshot-only strings (`IMP · MARKET WORKSTATION`, `DEMO REPLAY · READ-ONLY`, `Session 6a2f1c…`, `MARKET OVERVIEW/PULSE/SESSION CONTEXT`, the modal command palette) **do not exist in the audited source** — exact file:line for those must be taken from the running session's checkout, which was off-limits. Page bodies (S2, S4–S10) match current source closely, so those citations are exact.
2. **Partial humanization already underway — standardize, don't reinvent.** Underscore-replacement exists but is scattered (`ContextBar.tsx:12,22`, `workspaceHealth.ts:6-12`, `WhatMattersNowPanel.tsx:31,48`, `capabilityPresentation.ts:18`); `JsonDetailPanel` is the correct L4 pattern but is used inconsistently (expanded by default in S9's screenshot); `OperatorControlCenterPage`'s label/detail/next-action checks are the best in-app model of the 3-question rule.
3. **Possible regression in the new chrome:** the modal command palette (S3) was replaced by a single search input that only understands tickers (`ImpCommandSearch.tsx:20-24`) — command discoverability may have regressed in the branch already.
4. **Unverified at other viewports.** All screenshots are 1920px desktop; no narrow/zoomed evidence. The 10-tab module row (S2) and wide data tables (S5, S7) are the likely first overflow offenders. No page-level horizontal overflow is visible in any provided screenshot.
5. **Color-only status is limited but real:** attention-card tier (`AttentionFeed.tsx:29` + `layout.css:264`) and live/replay context-segment tint (`ContextBar.tsx:30`) — most other statuses pair color with text.
6. **Env-var and CLI leakage is a recurring pattern** (`IMP_PAPER_EXECUTION=1`, `IMP_LIVE_OBSERVATIONAL=1`, `python tools/finviz/auth.py repair`): the UI treats "edit your shell environment" as a first-class operator action. The redesign needs an in-UI settings path for each, with the CLI kept as advanced fallback.
7. **Audit limitations:** static read-only audit (live session running; no dev server, no interaction, no runtime DOM measurement). Screenshot micro-text (small metric values) transcribed at high but not perfect confidence; every claim that matters is backed by a code citation. Backend payloads (`quality_summary.detail`, `unready_reason`, `block_reasons`, `connection_state` values such as a possible `CONNECTED_DEGRADED`) are typed as free strings (`ui/src/api/schemas.ts:98-100,138`), so the full enum vocabulary rendered at runtime could not be enumerated from the UI tree alone — recommend a backend enum inventory to complete the replacement map.
