# RESEARCH — `/research`

## Purpose

Interpretation-first research surface. Research ≠ trading screen: the page leads
with what the evidence concludes and how much to trust it; methodology, fingerprints,
and hashes live behind disclosure. After the LAB split (D7/D8), Research hosts the
**Analytics** surface (`/research/analytics`) plus methodology context.

## Primary user questions

1. What does the evidence currently conclude — distributions, outcomes, signals?
2. How much should I trust it (epistemic class, coverage, window)?
3. How were these analytics produced (methodology, authority boundary)?
4. What is research-only vs what could ever influence trading?

## Current-state problems

- `Epistemic class: OBSERVED · Boundary: RESEARCH_ONLY` meta line is code-speak in
  the primary viewport (audit 04 row 21, S4).
- Raw ISO `observation_time` / `prediction_cutoff` in tables (S4).
- No plain-language synthesis — distributions without "what does this mean" (S4).
- `admitted fixture` / `Phase 5R` program vocabulary in footers (S4/S7).
- `SignalTimelineChartPanel` has no tabular summary (audit 05 charts gap);
  `CountBarChartPanel` has one (keep that pattern).
- All three research endpoints fetched eagerly regardless of active tab
  (`ResearchObservability.tsx:19-21`) — after the split, Research fetches only
  analytics.
- Bare "Research analytics unavailable." error (audit 04 warning #18).

## Information hierarchy

- **Primary (L1):** plain-language synthesis strip ("Across the research window,
  {n} signals, {n} abstentions; outcomes skew {…}") + trust summary (epistemic
  class humanized, coverage, window).
- **Secondary (L2):** analytics chart panels (decision distributions, timelines)
  with provenance captions and text summaries.
- **Contextual (L3):** per-panel data tables (existing good pattern), comparison
  views.
- **Advanced:** panel-level methodology notes; replay-window parameters.
- **Technical-Audit (L4):** `authority_boundary` / `epistemic_class` raw values,
  raw timestamps, fixture identifiers — **Methodology disclosure**
  (`TechnicalDetails` labeled "Methodology").

## Wireframe

```
┌──────────────────────────────────────────────────────────────────────┐
│ (AppShell chrome + StatusBar — global)                               │
├──────────────────────────────────────────────────────────────────────┤
│ PageHeader: Research — "Research-only evidence — not tradeable"      │
│   [Methodology] disclosure toggle                                    │
├──────────────────────────────────────────────────────────────────────┤
│ Synthesis strip (L1):                                                │
│  "What the evidence shows" — 2–3 human sentences derived from        │
│  analytics payload + ConfidenceIndicator + window/freshness          │
├──────────────────────────────────────────────────────────────────────┤
│ Chart grid (ChartFrame each, text summary + provenance mandatory):   │
│ ┌ Decision distribution ┐ ┌ Signal timeline ┐ ┌ Outcome mix ┐       │
│ │ (bar) + data table    │ │ (line) + table  │ │ …           │       │
│ └───────────────────────┘ └─────────────────┘ └─────────────┘       │
├──────────────────────────────────────────────────────────────────────┤
│ Methodology (TechnicalDetails, default collapsed):                   │
│  authority_boundary · epistemic_class · fixture ids · raw timestamps │
│  Cross-link: "Strategy P&L attribution lives in Portfolio →"         │
└──────────────────────────────────────────────────────────────────────┘
```

## Components

`PageHeader`, `ChartFrame` (mandatory text summary), `Metric`, `MetricGroup`
(synthesis strip), `ConfidenceIndicator`, `FreshnessIndicator`, `EvidenceSource`,
`DataTable` (chart-adjacent tables), `TechnicalDetails` (Methodology),
`EmptyState`, `LoadingState`, `ErrorState`, `DegradedState`, `CopyableIdentifier`.

## Interactions

- Methodology disclosure toggles L4 content (default collapsed).
- Chart panels expand to their data tables (keyboard-operable disclosure).
- Cross-links: Portfolio → Attribution (strategy profitability's home, D6); Lab →
  model/simulation detail (D7).
- No mutations (all modes read-only on this surface).

## States

- **Empty:** "No research analytics in this window — {why from payload reason}".
- **Loading:** ChartFrame skeletons.
- **Degraded:** partial panels render with DegradedState noting which panels are
  affected and why.
- **Error:** ErrorState with humanized category + retry (replaces bare
  "Research analytics unavailable.").
- **Demo:** full analytics (replay-bound); replay tone.
- **Paper:** same surface + paper tone; strategy-profitability cross-link.
- **Live:** same surface + read-only note (existing `LiveResearchPage` note,
  humanized); live tone.

## Data dependencies

- `researchAnalytics` (`/research/analytics`) — the only endpoint this page fetches
  after the split.
- Removed from this page: `researchModels`, `researchSimulation` (move to LAB);
  `paperStrategyProfitability` (home moves to Portfolio Attribution; cross-link
  only).
- No mutations.

## Responsive behavior

- ≥1440px: chart grid 2–3 columns (`auto-fit minmax(320px, 1fr)`).
- 1024–1439px: 2 columns.
- 720–1023px: 1–2 columns per panel min-width.
- <720px: single column; tables scroll internally.
- Charts size to container (existing ResponsiveContainer pattern).

## Accessibility

- Every ChartFrame ships `role="img"` + `aria-label` + tabular summary (extend the
  `CountBarChartPanel` pattern to `SignalTimelineChartPanel` — closes audit 05 gap).
- Research tone + text label ("Research-only") — never color-only.
- Tables keep `scope="col"` + captions.
- Methodology disclosure is a real `<details>`-style button with `aria-expanded`.

## Implementation notes

- `ResearchObservability` loses its tab bar (tabs move to LAB as routes); the page
  becomes single-purpose Analytics + synthesis.
- Synthesis strip content derives **only** from payload fields (counts, window,
  epistemic class) — no invented conclusions; template sentences via the adapter.
- `ResearchAnalyticsPanel` charts re-themed via `chartTokens.ts` (IMP orange accent,
  token grid/text); keep recharts lazy (out of entry chunk).
- "Phase 5R"/"admitted fixture" copy moves to Methodology; footers use human
  sentences ("Research-only evidence — not tradeable").

## Open questions

- Should the synthesis strip be backend-computed eventually? Default: derive from
  existing payload fields with conservative templates; never fabricate. (Q2-related,
  non-blocking.)
- Does Live mode need Research at all? Default: keep (read-only note), parity.

## Acceptance criteria

1. Page leads with human synthesis + trust summary; epistemic/boundary vocabulary
   only in Methodology; zero raw timestamps above L3.
2. Every chart has a text summary + data table; recharts stays lazy.
3. Only `researchAnalytics` fetched on this page; Lab routes fetch the other two.
4. No page-level horizontal scroll at the 7 widths.
5. `App.test.tsx` updated (Research per mode; Lab routes); npm gates green.
