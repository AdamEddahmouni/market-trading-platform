# LAB — `/lab` (+ `/lab/simulation`, `/lab/chart-lab`)

## Purpose

Models, strategies, replay/simulation, calibration, walk-forward, evaluation — the
experiment bench. Dense but legible. Presentation split of existing `/research/*`
endpoints (**no backend change**, D7): Model Lab (`researchModels`), Simulation
(`researchSimulation`), Chart Lab (synthetic Vela playground).

## Primary user questions

1. What models/strategies exist — family, alignment, preregistration status?
2. Is this model any good — walk-forward folds, abstentions, at-cutoff behavior?
3. What is it allowed to influence (authority boundary, humanized)?
4. How did the simulation ledger behave — decisions, fills, reconciliation?
5. (Chart Lab) How does the Vela adapter behave on a governed synthetic feed?

## Current-state problems

- Two full-length mono hashes (`strategy_identity_hash`, `dataset_fingerprint`) in
  the primary viewport — L4 content at L2 (audit 04 S7, identifier rows 8/9); the
  `.mono` class they use has no CSS rule (audit 02 typography).
- `Boundary: RESEARCH_ONLY · Epistemic: OBSERVED` meta + `Phase 5R` footer +
  `Walk-forward folds` unexplained (S7).
- No human summary of model quality ("is this model any good? what can it
  influence?") — S7.
- Simulation tables render raw `intent_id`s and minor-unit prices (identifier
  row 14, jargon row 12); `risk_policy_id` raw.
- `/lab` today redirects to `/research`; nav "Lab" duplicates "Research"
  (audit 01 observation #1); Model Lab/Simulation are local-state tabs with no deep
  links.
- Options-lab blocks render `STRATEGY_UNAVAILABLE`-style raw fallbacks and
  `Replay hash: {hash}` in primary view (audit 04 row 25) — those blocks surface in
  Workspace options lane; same humanization applies wherever they render.
- Bare "Model Lab unavailable." / "Simulation Lab unavailable." errors
  (warning #18).

## Information hierarchy

- **Primary (L1):** model quality summary in words ("Model family {x} · {n}
  walk-forward folds · preregistered · {n} signals / {n} abstentions"); simulation
  ledger headline (decisions/fills/reconciliation state humanized).
- **Secondary (L2):** interpretations table (humanized outcomes, human times);
  decision/fill tables; per-model metric grids.
- **Contextual (L3):** fold-by-fold detail, abstention reasons, reconciliation
  detail, attribution rows.
- **Advanced:** risk policy linkage, alignment detail, chart adapter diagnostics.
- **Technical-Audit (L4):** `strategy_identity_hash`, `dataset_fingerprint`,
  `risk_policy_id`, `intent_id`s, replay hashes, raw enums — Methodology/Audit
  disclosure (`TechnicalDetails`), each with CopyableIdentifier.

## Wireframe

```
┌──────────────────────────────────────────────────────────────────────┐
│ (AppShell chrome + StatusBar — global)                               │
├──────────────────────────────────────────────────────────────────────┤
│ PageHeader: Lab — "Experiment bench · no trade authority"            │
│   [Tabs: Model Lab | Simulation | Chart Lab]  (routable)             │
├──────────────────────────────────────────────────────────────────────┤
│ MODEL LAB (/lab):                                                    │
│ ┌ Quality summary (L1): "Walk-forward evaluated · 5 folds ·          ││
│ │   preregistered · 12 signals / 3 abstentions" + ConfidenceIndicator││
│ ├ MetricGroup: family · alignment · folds · preregistration ·        ││
│ │   signals/abstentions/at-cutoff                                    ││
│ ├ Interpretations DataTable: time(human) · outcome(human) · cutoff · ││
│ │   alignment                                                        ││
│ └ Methodology (TechnicalDetails): identity hash [copy] · dataset     ││
│    fingerprint [copy] · boundary raw · phase/fixture ids             ││
│ SIMULATION (/lab/simulation):                                        │
│ ┌ Ledger headline: "1,240 decisions · 312 fills · reconciliation:    ││
│ │   clean" (tone from adapter)                                       ││
│ ├ Decisions / fills DataTables (currency-formatted, human times,     ││
│ │   intent ids → CopyableIdentifier + trace link)                    ││
│ └ Audit (TechnicalDetails): risk_policy_id · raw ledger fields       ││
│ CHART LAB (/lab/chart-lab):                                          │
│ └ Vela adapter playground (synthetic feed; existing page, re-themed) ││
└──────────────────────────────────────────────────────────────────────┘
```

## Components

`PageHeader`, `Tabs` (routable), `Metric`, `MetricGroup`, `DataTable`,
`ConfidenceIndicator`, `FreshnessIndicator`, `TechnicalDetails`,
`CopyableIdentifier`, `EmptyState`, `LoadingState`, `ErrorState`, `DegradedState`,
`ChartFrame` (Chart Lab), `EvidenceSource`.

## Interactions

- Tab switch = route navigation (`/lab`, `/lab/simulation`, `/lab/chart-lab`);
  `/research/vela-chart-lab` redirects to `/lab/chart-lab`.
- Interpretation/decision rows expand for L3 detail; intent IDs link to trace where
  a trace exists (paper trace query) — otherwise copy-only.
- Chart Lab keeps its local tick-sim/backfill buttons (local state only; no backend).
- No mutations anywhere in LAB.

## States

- **Empty:** "No models admitted in this build" / "No simulation ledger in this
  window" — with why (fixture scope) and a cross-link to Research.
- **Loading:** skeletons per panel.
- **Degraded:** partial payload → per-panel DegradedState ("interpretations
  unavailable — {human reason}; metrics intact").
- **Error:** ErrorState humanized + retry (replaces bare "… unavailable.").
- **Demo:** full surfaces (fixture-bound); replay tone.
- **Paper:** same surfaces; paper tone; strategy-profitability lives in Portfolio
  (cross-link only).
- **Live:** same surfaces + read-only note; live tone.

## Data dependencies

- `researchModels` (`/research/models`), `researchSimulation`
  (`/research/simulation`) — fetched by their respective tabs only (today all three
  research endpoints fire eagerly; the split fixes that).
- Chart Lab: none (local synthetic feed + local interval, unchanged).
- No mutations.

## Responsive behavior

- ≥1440px: metric grids multi-column; tables full density.
- 1024–1439px: 2-column grids; tables contained.
- 720–1023px: single column; tables scroll internally.
- <720px: single column; compact table density.
- Chart Lab keeps container-sizing (ResizeObserver).

## Accessibility

- Hash/ID values via CopyableIdentifier (focusable, announced).
- Tables with `scope="col"` + captions; human times with raw ISO in
  TechnicalDetails (not tooltips — tooltips are non-load-bearing).
- Tabs full ARIA pattern (routable variant).
- "No trade authority" boundary is text + research tone, never color-only.

## Implementation notes

- New `ModeLabRoute` wrapper mirrors the `Mode*Route` pattern (Demo/Paper/Live page
  skins over shared observability) per FRONTEND_GUIDE lockstep; `/lab` redirect
  removed; nav "Lab" targets `/lab` (no longer a duplicate).
- `ModelLabPanel` / `SimulationLabPanel` move from `research/` scope to Lab
  presentation; endpoints and queryKeys unchanged.
- `.mono` utility gets a real rule (hashes currently render in sans) — then hashes
  move behind CopyableIdentifier anyway.
- Humanize `STRATEGY_UNAVAILABLE` / `EXECUTION_UNAVAILABLE` / `FUSION_UNAVAILABLE` /
  `DEALER_POSITION_UNKNOWN` fallbacks via adapter templates wherever those blocks
  render (Workspace options lane included); replay hashes to Audit details.
- Chart Lab re-themed via `chartTokens.ts`; `vela-*` chunk stays lazy (950 KB cap).

## Open questions

- Q2 — will backend ever split research vs lab endpoints? Default: no; presentation
  split only.
- Should Chart Lab remain under Lab long-term? Default: yes (it is experiment
  tooling).

## Acceptance criteria

1. `/lab` is a real page with three routable tabs; `/research/vela-chart-lab`
   redirects; nav Lab/Research are distinct with correct active states.
2. Hashes/fingerprints/IDs behind Methodology/Audit with copy; model quality has a
   human summary; zero raw enums above L3.
3. Only the active tab's endpoint is fetched; no mutations; chart lab unchanged
   functionally.
4. No page-level horizontal scroll at the 7 widths.
5. `App.test.tsx` updated (Lab per mode + redirect); npm gates green; all Lab
   surfaces lazy.
