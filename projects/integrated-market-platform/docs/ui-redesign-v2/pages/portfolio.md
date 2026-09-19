# PORTFOLIO — `/portfolio`

## Purpose

Account truth per mode: NAV/cash/buying power, realized/unrealized/daily P&L,
positions, orders, exposure, risk utilization, concentration, attribution, execution
trace, and paper session lifecycle. Order **construction** lives in Workspace (D11);
Portfolio is for account state, history, and attribution.

## Primary user questions

1. What is my account worth — cash, buying power, NAV — and what changed today?
2. What am I holding; what is each position doing; how fresh are the marks?
3. Realized vs unrealized vs daily P&L — and which strategies drove it
   (attribution)?
4. How much of my risk budget am I using; what blocked and why?
5. What happened to each order (history, trace, provenance)?
6. Which paper session am I in; what happened in previous sessions?

## Current-state problems

- Money in minor units ("cash starting 100000 minor", `Price (minor)` column) and
  ns-epoch timestamps (`mark_as_of_ns`) — audit 04 offense #8, rows 9/11/12.
- Header meta repeats the global context bar a third time (S5); session history rows
  render raw enums + truncated UUIDs without copy (rows 3/10).
- `Data quality STALE` / `Model UNAVAILABLE` fail the 3-question rule (warning #24).
- Raw order `state` strings (`String(order.state ?? …)`) — row 14.
- Session state from three sources (`/paper/portfolio` block vs raw `/paper/sessions`
  list vs `/operator/state`) — stale history rows after archive/new (audit 03 #6).
- `paperStrategyProfitability` key embeds account/session but sends no params
  (audit 03 #7) — documented, transport unchanged (Q9).
- `.portfolio-layout` 360px trace column never collapses (audit 02 §D9); portfolio
  tables partially contained (positions/orders/fills lack wrappers — audit 02 §B).
- Live portfolio depends on canary snapshot/reconciliation with block-reason alerts
  rendered raw (row 33/35).

## Information hierarchy

- **Primary (L1):** account strip (NAV/cash/buying power, daily P&L, realized/
  unrealized); risk utilization + kill-switch state; active session status; block
  banners.
- **Secondary (L2):** positions (with mark freshness), open orders, exposure/
  concentration, attribution summary (strategy P&L leaders/laggards).
- **Contextual (L3):** order history (filterable, expandable), fills, execution
  trace drawer, session history (humanized), strategy profitability detail.
- **Advanced:** risk limits grid, reconciliation detail, per-strategy lineage.
- **Technical-Audit (L4):** session/order/intent/correlation IDs (CopyableIdentifier),
  `mark_as_of_ns`, minor-unit values, raw `data_mode`/`execution_mode` per session,
  raw risk decision payloads — TechnicalDetails / trace drawer.

## Wireframe

```
┌──────────────────────────────────────────────────────────────────────┐
│ (AppShell chrome + StatusBar — global)                               │
├──────────────────────────────────────────────────────────────────────┤
│ PageHeader: Portfolio — {mode sentence}                              │
│   "Paper account · session open since 9:12 AM" [New session] [Archive]│
├──────────────────────────────────────────────────────────────────────┤
│ AttentionBanner (when active): "Mark data is stale — unrealized P&L  │
│  may be inaccurate. Affects: positions, P&L. → Check Providers"      │
├──────────────────────────────────────────────────────────────────────┤
│ MetricGroup (account strip): NAV · Cash · Buying power · Daily P&L · │
│   Realized · Unrealized · Risk utilization (meter) · Kill switch     │
├──────────────────────────────────────────────────────────────────────┤
│ Tabs: Holdings | Orders | Attribution | Sessions                     │
│ ┌ HOLDINGS ─────────────────────────────────────────────────────────┐│
│ │ Positions DataTable: symbol · qty · avg · mark (FreshnessInd.) ·  ││
│ │  unrealized P&L (direction tone)  [row → workspace]               ││
│ │ Exposure / concentration MetricGroup                              ││
│ ├ ORDERS ───────────────────────────────────────────────────────────┤│
│ │ Open orders DataTable (OrderRow) · Order history (FilterBar,      ││
│ │  paginated, expandable → provenance + [View trace → Drawer])      ││
│ ├ ATTRIBUTION ──────────────────────────────────────────────────────┤│
│ │ Strategy profitability DataTable (per-strategy P&L lineage,       ││
│ │  settlement state humanized)                                      ││
│ ├ SESSIONS ─────────────────────────────────────────────────────────┤│
│ │ "Open · started Sep 12 · demo replay / paper" rows [CopyableId]   ││
│ └───────────────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────┘
```

## Components

`PageHeader`, `Tabs`, `Metric`, `MetricGroup`, `RiskSummary`, `DataTable`,
`PositionRow`, `OrderRow`, `FilterBar`, `Drawer` (execution trace),
`AttentionBanner`, `DegradedState`, `ErrorState`, `EmptyState`, `LoadingState`,
`TechnicalDetails`, `CopyableIdentifier`, `FreshnessIndicator`, `EvidenceSource`
(provenance badges). Existing `OrderTicket` **removed from this page** (D11 → Q7);
replaced by "Open in Workspace" handoff CTA carrying the symbol.

## Interactions

- Position row → `/workspace/:symbol`; order row expand → provenance + trace action
  (Drawer with `ExecutionTracePanel` content).
- Paper session open/close mutations preserved (`POST /paper/sessions`,
  `/paper/sessions/close`) with existing `actionEligible` gating and human
  restriction notes.
- Order history: filters + pagination (infinite query) preserved; cancel path
  remains defined-server-side only (`/paper/orders/cancel` has no UI call site — do
  not invent one).
- "Open in Workspace" handoff → `/workspace/:symbol` (no draft state; construction
  happens in the cockpit).

## States

- **Empty:** "No open positions." / "No orders yet — construct one from Workspace."
  (with CTA); attribution empty → "No settled strategy outcomes in this session."
- **Loading:** skeletons per panel; history keeps its own pagination loading.
- **Degraded:** stale marks → DegradedState on the positions panel + banner (P&L
  trust stated explicitly); `RESTORED` → caution ("Session restored — marks wait for
  fresh data"); `DISCONNECTED` → critical.
- **Error:** ErrorState per panel; portfolio unavailable → full-page ErrorState with
  retry ("Simulation account observability unavailable" becomes humanized + action).
- **Demo:** read-only simulated snapshot (labeled); zeroed positions/orders per
  backend demo view; replay tone.
- **Paper:** full surface; session lifecycle actions; paper tone.
- **Live:** broker-observed positions/orders from canary snapshot + reconciliation;
  read-only; block reasons humanized per semantic-state-system §3.6; live tone.

## Data dependencies

- Demo/Paper: `paperPortfolio(viewMode)` (`/paper/portfolio?view_mode=DEMO|PAPER`).
- Paper: `paperOrderHistory` (infinite, `/paper/order-history`), `paperTrace`
  (`/paper/trace`), `paperStrategyProfitability`
  (`/paper/strategy-profitability`), raw GET `/paper/sessions` (session history —
  refetch keyed on session id; document staleness, D20).
- Live: `liveCanarySnapshot("portfolio")`, `liveCanaryReconciliation` (15s polls).
- Mutations: session open/close only (order preview/submit move to Workspace per
  D11).

## Responsive behavior

- ≥1440px: metric strip one row; tabs content multi-column where natural.
- 1024–1439px: metric strip 2 rows (auto-fit); trace becomes Drawer (already the
  design — replaces the never-collapsing 360px column).
- 720–1023px: single column; tables scroll internally with column-hiding (existing
  `paper-portfolio.css:256-265` pattern generalized).
- <720px: metric strip 2×2; tables compact density (min-width 640px internal
  scroll).

## Accessibility

- All tables semantic with `scope="col"` + captions (extend the order-history
  pattern to positions/fills).
- Risk utilization keeps `role="meter"` + `aria-value*`; kill switch state is text +
  tone.
- Session rows: status text + human date; IDs via CopyableIdentifier (focusable,
  keyboard-operable, announced copy confirmation).
- P&L direction never color-only: sign + "gain/loss" text paired with direction
  tone.

## Implementation notes

- Currency formatting helper (`minor → $dollars`) and human-time helper land in
  `ui/src/lib/` with unit tests; applied to every money/time render (also fixes
  Simulation Lab + canary minor-unit leaks).
- `PaperPortfolioObservability` panels rebuilt on Metric/MetricGroup/DataTable;
  phantom `.account-panel`/`.pnl-panel`/`.exposure-panel`/`.risk-panel` etc.
  deleted.
- Session history staleness (raw `/paper/sessions` refetch keyed on session id):
  keep transport; add a manual refresh affordance; document in D20 debt.
- Attribution tab hosts `PaperStrategyProfitabilityObservability` (single home, D6);
  Research cross-links here.
- Live view-model (`livePortfolioViewModel.ts`) ok-sets move into the adapter.

## Open questions

- Q7 — **resolved (UIR-01G):** in-page order submit removed; Workspace handoff CTA.
- Q9 — strategy-profitability params (default: document, no transport change).
- Should Demo portfolio show the simulated account at all, or a pure replay view?
  Default: keep simulated snapshot, labeled "Simulated account" (parity).

## Acceptance criteria

1. All money currency-formatted, all times humanized, all IDs truncate+copy; zero
   raw enums above L3; header no longer repeats the StatusBar.
2. Session open/close works with existing gating; order history/trace/provenance
   intact; attribution tab renders strategy lineage.
3. Live mode read-only with humanized block reasons; Demo labeled simulated.
4. No page-level horizontal scroll at the 7 widths; tables contained with
   column-hiding.
5. `App.test.tsx` per-mode portfolio tests updated; npm gates green.
