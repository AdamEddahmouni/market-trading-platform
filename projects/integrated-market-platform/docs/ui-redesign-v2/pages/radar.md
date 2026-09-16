# RADAR — `/radar` (+ `/radar/screeners`)

## Purpose

The canonical discovery queue: **find → rank → filter → compare → investigate**.
Two tabs: **Opportunities** (`/radar`, today's discover cockpit) and **Screeners**
(`/radar/screeners`, today's explore donor bridges). Empty states always explain
**why** the queue is empty and what unblocks it.

## Primary user questions

1. What opportunities exist, ranked — and why now?
2. What changed since I last looked? What confirms or contradicts each idea?
3. Why is the queue empty or unready — and what do I do about it?
4. How strong is the evidence, how fresh is it, and what's the next action?
5. (Screeners) What do the raw donor screens show — squeeze cohort, scanner,
   futures, catalyst — with provenance?
6. (Live) What can I subscribe to, and what does my subscription entitle me to see?

## Current-state problems

- Feed banner shows raw `UNREADY {unready_reason}` (audit 04 row 32); error state is
  a bare "Opportunity ranking unavailable." (warning #15, fails 3-question rule).
- Discover candidate pills render raw `data_status` enums; `EXEC NONE` raw in the
  header (`DiscoverObservability.tsx:341`); hardcoded contract literals
  (`SEMI_LIVE`, `INVESTIGATE`) shown raw.
- Evidence popover paints over adjacent rows (absolute positioning, audit 02 §D10).
- Explore pages are labeled "Markets" in nav but "Explore" in H1 (audit 01 concept
  table mismatch); `?q=` from command search is dead (nothing reads it).
- Discover controls row has no wrap + fixed 280px select → overflow risk
  (audit 02 §A5); queue rows are the app's best responsive treatment but use the old
  1100/720 breakpoints.
- Live `LiveObservationalPanel` subscribe flow is embedded in Explore — must survive
  the merge (audit 01 draft map risk).
- Empty states don't explain why (doctrine requirement).

## Information hierarchy

- **Primary (L1):** ranked opportunity queue (dense table) + selected opportunity
  card; feed status as a human sentence; filter bar.
- **Secondary (L2):** why-now / what-changed per row (curated subset of the
  9-field rule); screener sections with per-source freshness; live subscribe panel.
- **Contextual (L3):** full evidence (`EvidenceStack`), confirms/contradicts
  (`ContradictionPanel`), trade-review history, per-screen degradation details.
- **Advanced:** ranking vectors, lane contribution breakdowns, screen definitions.
- **Technical-Audit (L4):** row IDs, reason codes, raw `data_status`/`feed_status`,
  contract literals, raw `received_at` timestamps — TechnicalDetails only.

## Wireframe

```
┌──────────────────────────────────────────────────────────────────────┐
│ (AppShell chrome + StatusBar — global)                               │
├──────────────────────────────────────────────────────────────────────┤
│ PageHeader: Radar — {mode sentence}        [Tabs: Opportunities|Screeners]│
├──────────────────────────────────────────────────────────────────────┤
│ Feed status line (human):                                            │
│  "Opportunity radar is ready · 12 candidates · updated 3s ago"       │
│  or AttentionBanner: "Radar isn't ready: {human reason}.             │
│   Affects: ranked queue.  → Open Control"                            │
├──────────────────────────────────────────────────────────────────────┤
│ FilterBar: [side] [lane] [min evidence] [freshness] [text q]         │
├──────────────────────────────────────────────────────────────────────┤
│ ┌─ RANKED QUEUE (DataTable, dense) ────────┐ ┌─ SELECTED ──────────┐│
│ │ #  Symbol  What/why-now   Score  Fresh   │ │ OpportunityCard     ││
│ │ 1  BIYA    Ignition watch…  ▮▮▮▨  12s     │ │ (full 9-field,      ││
│ │ 2  …                                    │ │  EvidenceStack,     ││
│ │ (internal scroll; keyboard navigable)   │ │  ContradictionPanel,││
│ │ EmptyState explains WHY when empty      │ │  risk, next action) ││
│ └──────────────────────────────────────────┘ └─────────────────────┘│
├──────────────────────────────────────────────────────────────────────┤
│ Screeners tab:                                                       │
│  ┌ Squeeze cohort ┐ ┌ Scanner ┐ ┌ Futures ┐ ┌ Catalyst ┐            │
│  │ DataTable +    │ │ …       │ │ …       │ │ …        │            │
│  │ EvidenceSource │ │         │ │         │ │          │            │
│  └────────────────┘ └─────────┘ └─────────┘ └──────────┘            │
│  (LIVE: + subscribe panel: search → capabilities → [Subscribe])      │
└──────────────────────────────────────────────────────────────────────┘
```

## Components

`PageHeader`, `Tabs`, `FilterBar`, `DataTable` (dense, scroll-contained),
`OpportunityCard` (full density), `OpportunityScore`, `FreshnessIndicator`,
`ConfidenceIndicator`, `EvidenceStack`, `EvidenceSource`, `ContradictionPanel`,
`AttentionBanner`, `EmptyState` (reason mandatory), `LoadingState`, `ErrorState`,
`DegradedState`, `TechnicalDetails`, `CopyableIdentifier`, `Tooltip`,
`CanonicalInstrumentSelector` (live subscribe; restyled — its
`instrument-selector*` classes are phantom today).

## Interactions

- Row select (click / Enter / Space / arrows) → selected card; `aria-selected` on
  proper row semantics within the DataTable pattern.
- Ack actions (watch/dismiss/review) — Paper only, `onAckAllowed` gate preserved
  (`progressiveOpportunityModel.ts:224-225`).
- Paper mutations preserved exactly: POST `/discover/mixed/refresh`, POST
  `/discover/promote-to-live-analysis`, POST `/discover/mixed/release` on unmount
  (`keepalive`), GET `/discover/run?force=1` (mutating GET — flagged debt, D20).
- Server-driven timers preserved: `poll_interval_seconds` (default 3s), refresh
  (default 120s), paused on `document.hidden`.
- Screeners: symbol links → `/workspace/:symbol`; `?q=` pre-filters rows (D16).
- Live: subscribe → POST `/subscriptions` → invalidate `providerHealth` + `context`
  → POST `/operator/recent` → navigate to workspace (existing flow, unchanged).

## States

- **Empty (must say why):** feed EMPTY ("No candidates passed the current screens —
  {filter/coverage detail}"); feed UNAVAILABLE in LIVE ("Live mode has no
  opportunity engine — use Screeners and workspace evidence"); screeners empty per
  donor ("No squeeze candidates in the frozen cohort as of {time}").
- **Loading:** skeleton rows in the dense table; card placeholder.
- **Degraded:** per-screen `status != "PASS"` → DegradedState list ("{screen}:
  {human reason} — affects {lane}"); provider dots → ProviderHealth chips.
- **Error:** ErrorState with humanized category + retry; raw envelope in
  TechnicalDetails.
- **Demo:** read-only; frozen donor bridges; replay tone.
- **Paper:** full mutations; mixed live screener; paper tone.
- **Live:** read-only monitor; subscribe panel; live tone; no opportunity engine
  (by-design empty state).

## Data dependencies

- `opportunitiesSummary` (`/opportunities/summary`), `opportunityEvidence(rowId)`
  (`/opportunities/{id}/evidence`), `["trade-reviews", opportunityId]`
  (`/intelligence/trade-reviews`).
- Screeners: `exploreSqueeze`, `exploreSqueezeScanner`, `exploreFutures`,
  `exploreCatalyst` (`/explore/*`).
- Mixed screener (raw fetch, hand-typed — D20 debt): `/discover/screens`,
  `/discover/mixed`, `/discover/run`, refresh/promote/release POSTs.
- Live: `symbolSearch` (`/symbols/search`), `instrumentCapabilities`
  (`/instruments/{id}/capabilities`), `providerHealth` (5s).
- Mutations: opportunity ack POSTs; discover POSTs (Paper); subscribe POST (Live).

## Responsive behavior

- ≥1440px: queue + selected card split (existing cockpit two-pane, minmax(0,…)).
- 1024–1439px: split preserved; dense table drops to 4 columns (re-mapped from 1100).
- 720–1023px: stacked — selected card becomes a Drawer opened from the row.
- <720px: table 2 columns (symbol + score/what), card full-screen Drawer.
- FilterBar wraps; selects `min-width: 0`; evidence popover is a portal popover that
  never paints over neighbors.

## Accessibility

- Dense table keeps keyboard operation but on a proper grid/row pattern with
  `aria-selected` context (fixes the borderline bare-`<tr>` usage).
- Queue updates announced via `aria-live="polite"` (existing `.discover-queue`
  habit, kept).
- Score/score-band paired (never color-only); data-status pills carry text.
- `CanonicalInstrumentSelector` gains `role="combobox"` + `aria-activedescendant`
  linkage (audit 05 gap).

## Implementation notes

- Build on `OpportunityRadarCockpit` + `OpportunityRadarDensePanel` (structure is
  right); restyle to tokens; replace `.discover-*` one-off hexes with state tokens.
- `ExploreObservability` moves under the Screeners tab mostly intact; H1/nav label
  mismatch resolved ("Radar → Screeners").
- Wire `q` param: read via `useSearchParams` in the Screeners tab (C2-style param
  handling precedent), pre-fill FilterBar text filter.
- Keep the unmount release POST and timer lifecycle byte-identical (C3).
- `OpportunityRadarIntro` explainer becomes collapsible helper text (not a permanent
  banner).

## Open questions

- Should promote-to-live-analysis remain Paper-only (current `allowMutations`)?
  Default: yes — preserved. (Non-blocking.)
- Q4 (`?q=` backend search) — default: client filter only.

## Acceptance criteria

1. `/radar` + `/radar/screeners` render per mode; `/discover` and `/explore`
   redirect with `?q=` carried through; nav "Radar" active state correct.
2. Every empty state explains why; feed UNREADY/UNAVAILABLE render human sentences +
   actions; zero raw enums above L3.
3. Paper mutations incl. unmount release POST verified by test; timers unchanged;
   ack gating unchanged.
4. No page-level horizontal scroll at the 7 widths; evidence popover never overlaps
   neighbors.
5. `App.test.tsx` updated (redirects + per-mode entry); npm gates green; new
   surfaces lazy (Radar chunk ≤ 500 KB raw).
