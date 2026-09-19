# WORKSPACE — `/workspace`, `/workspace/:symbol`, `/workspace/:symbol/{lane}`

## Purpose

The decision cockpit for one instrument: **understand → verify → construct →
risk-check → simulate**. This is the only surface where a paper order can be
submitted (current preview + fail-closed guards). The 10 evidence lanes are tabs of
the instrument; every lane route stays deep-linkable.

## Primary user questions

1. What is this instrument doing right now (price, replay cursor, live quote)?
2. What does each evidence lane say — and which lanes matter now?
3. Why does IMP think this (signals, evidence, source agreement, contradictions)?
4. What happens if I trade it — preview risk, sizing, quality?
5. Is my preview still valid? Am I authorized right now?
6. (Per lane) What does {squeeze, order flow, options, …} evidence show, how fresh
   is it, and is it frozen research or current data?

## Current-state problems

- Lane tables show raw relevance `HIGH/MEDIUM/LOW`, raw `freshness_label`, raw
  state-machine enums (`STATE: PRE_IGNITION`), `2 PASS / 3 FAIL / 1 UNKNOWN` with no
  legend (audit 04 rows 17–19, S2).
- Epistemic chips `OBSERVED/DERIVED/INFERRED` undecoded across all lanes (row 20).
- `UNAVAILABLE — WHALE_NO_ENTITLED_SOURCE` on 8 lanes (row 22; fails 3-question
  rule); "no admitted replay fixture" jargon (row 23).
- Derived-features grid pairs raw `feature_id`s with epistemic chips (S2).
- 10-tab module row is an overflow risk < 1440px (audit 04 runner-up); sticky lane
  nav offset (120px) matches nothing (audit 02 §D6).
- Frozen vs current evidence divergence for the same symbol is invisible
  (audit 03 #4): overview fetches squeeze `frozen`, squeeze lane can show `current`.
- Paper-draft handoff rides `location.state` PUSH-only (C1) — fragile, must be
  formalized; lane draft CTAs appear without authority check (authority enforced
  later at the ticket — keep, but say so).
- Derivative paper preview is permanently fail-closed via
  `canUsePaperActions(..., undefined)` (audit 03 #1) — possible latent bug (Q8).
- Layout persistence POST `/operator/workspace` is fire-and-forget; silent failure
  diverges backend focus from the visible workspace (audit 03 #8).

## Information hierarchy

- **Primary (L1):** instrument header (symbol, human price/change, freshness);
  what-matters-now lane summary (humanized); Paper: decision cockpit (preview state,
  risk, ticket); active warnings.
- **Secondary (L2):** price chart + replay scrub; lane relevance with why-tooltips;
  supports/contradicts/unclear/gaps snapshot; handoff provenance ("drafted from
  Radar candidate …").
- **Contextual (L3):** per-lane evidence tabs (the 10 lanes), evidence stacks,
  cross-lane agreement, forward tests.
- **Advanced:** derived-features grid (labeled, decoded), execution trace, governed
  product surfaces (options/futures).
- **Technical-Audit (L4):** feature IDs, state-machine values, reason codes,
  `replay_hash`es, correlation/intent/order IDs, raw timestamps — TechnicalDetails /
  InspectorPanel / ExecutionTracePanel.

## Wireframe

```
┌──────────────────────────────────────────────────────────────────────┐
│ (AppShell chrome + StatusBar — global; instrument chip = this symbol)│
├──────────────────────────────────────────────────────────────────────┤
│ Instrument header: BIYA · $4.32 ▲2.1% · updated 2s ago               │
│   [EvidenceSource: frozen snapshot | current data]  [Why?] [Inspect] │
├──────────────────────────────────────────────────────────────────────┤
│ Lane Tabs (routable): Overview | Squeeze | Order Flow | Order Book | │
│   Options | Futures | Catalyst | Large Tx | Inst. Flow | Disclosure |│
│   Fund/ETF        ← order from LANE_NAV_ORDER (registry untouched)   │
├──────────────────────────────────────────────────────────────────────┤
│ OVERVIEW TAB:                                                        │
│ ┌─ ChartFrame: price chart + replay scrub ────────────┐ ┌ WHAT ────┐│
│ │ (text summary mandatory)                            │ │ MATTERS  ││
│ │                                                     │ │ NOW:     ││
│ │                                                     │ │ lane     ││
│ │                                                     │ │ relevance││
│ │                                                     │ │ +why +fr.││
│ └─────────────────────────────────────────────────────┘ └──────────┘│
│ ┌─ PAPER ONLY: DECISION COCKPIT ───────────────────────────────────┐│
│ │ Handoff provenance │ Decision snapshot (supports/contradicts/    ││
│ │  unclear/gaps)     │ RiskSummary │ Preview status │ ORDER TICKET ││
│ │ [Preview] → "Preview accepted — ready to submit" → [Submit]      ││
│ │ Authority lost → ticket hidden, observability stays + banner     ││
│ └──────────────────────────────────────────────────────────────────┘│
│ LANE TAB (e.g. Squeeze):                                             │
│ ┌ Lane header: human state ("Squeeze state: pre-ignition") +        ││
│ │   FreshnessIndicator + EvidenceSource (frozen|current)           ││
│ │   [?data_mode=current toggle preserved]                           ││
│ │ Blocks: transitions · causal · catalyst · cross-lane · historical ││
│ │ "2 of 6 checks passing" + rule links (was 2 PASS/3 FAIL/1 UNKNOWN)││
│ └───────────────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────┘
```

## Components

`PageHeader` (instrument variant), `Tabs` (routable lane tabs), `ChartFrame`,
`Metric`, `MetricGroup`, `FreshnessIndicator`, `ConfidenceIndicator`,
`EvidenceStack`, `EvidenceSource`, `ContradictionPanel`, `RiskSummary`,
`AttentionBanner`, `DegradedState`, `ErrorState`, `EmptyState`, `LoadingState`,
`TechnicalDetails`, `CopyableIdentifier`, `Drawer` (evidence drawer, trace panel),
`DataTable` (lane tables), `Tooltip`, `FilterBar` (lane tables with filters),
existing `OrderTicket` (restyled, guards untouched), `PaperDecisionCockpit`
composition (rebuilt on primitives), `CanonicalInstrumentSelector`.

## Interactions

- Lane tab switch = route navigation (deep links preserved); squeeze preserves
  `?data_mode=current` through tab switches.
- Paper flow (unchanged semantics): draft arrives via `location.state` (C1) →
  composer pre-filled → Preview (POST `/paper/orders/preview`) → submit enabled only
  with current matching preview (`confirmedRequestIsCurrent`, `preview_id` required,
  generation counter discards stale responses) → Submit (POST `/paper/orders`) →
  `useInvalidatePaper`.
- "Why?"/"Inspect" open global drawers; evidence rows open WorkspaceEvidenceDrawer
  (rebuilt on `Drawer`).
- Replay scrub (Demo) via shell; chart markers anchor evidence.
- Lane "Draft paper order from lane" CTA preserved; copy adds "authority is checked
  at the ticket" clarity.

## States

- **Empty:** no instrument selected → `InstrumentSelectionEmpty` (restyled;
  selector with combobox semantics); lane empty → reason ("No order-flow bars in
  this window"); non-admitted replay symbol → "No replay data for {symbol} in this
  demo build. Admitted: {list}."
- **Loading:** `LoadingState` skeletons per panel; lane panels keep individual
  loading (no full-page spinner).
- **Degraded:** lane stale → DegradedState ("Lane evidence is stale — last updated
  {relative}"); live lane operational problems → humanized block reasons (one
  sentence each + action); frozen-vs-current divergence → `EvidenceSource` pair +
  note, never silent.
- **Error:** per-panel ErrorState (humanized + retry); preview errors keep
  fail-closed submit.
- **Demo:** read-only; replay controls; frozen evidence; replay tone.
- **Paper:** full cockpit; forward tests; paper tone; authority loss → ticket hidden,
  observability retained + AttentionBanner ("Trading authority unavailable — ticket
  locked. Evidence remains visible.").
- **Live:** read-only; live market panel (2s polling); live tone; lane strips show
  provider/canary state.

## Data dependencies

- Route: `instrument(symbol)` (`/instruments/{id}/overview`), `workspaceSqueeze(
  symbol, dataMode)` (`/workspace/{id}/squeeze[?data_mode=]`).
- Overview: `context`, `workspaceEvidence(symbol)` (5s live), `marketState(symbol)`
  (2s live), `workspaceOrderFlow(symbol)` (2s live).
- Lanes: `workspaceOrderFlow`, `workspaceOrderBook` (2s live), `workspaceFutures`,
  `workspaceCatalyst`, `workspaceFundEtf`, `workspaceOptions`,
  `workspaceLargeTransactions`, `workspaceDisclosure`,
  `workspaceInstitutionalFlow`; product surfaces `optionsProduct`, `futuresProduct`;
  `instrumentSearch` (selector).
- Paper: `paperPortfolio`, `paperForwardTests(accountId)` (raw, unvalidated — D20),
  preview/submit/session mutations; `paperTrace` for ExecutionTracePanel.
- Shell: replay scrub POST `/replay/scrub`; layout persistence POST
  `/operator/workspace` (fire-and-forget, preserved).

## Responsive behavior

- ≥1440px: chart + what-matters two-column; cockpit 3-column (handoff/snapshot |
  risk/preview | ticket) — replaces the `paper-now.css` min-882px grid.
- 1024–1439px: cockpit 2-column; lane tabs scroll internally.
- 720–1023px: single column; cockpit stacks (ticket last, always reachable);
  evidence drawer = overlay.
- <720px: single column; lane tabs horizontal scroll strip; chart keeps container
  sizing.
- Lane tables all in `DataTable` containment (the 12+ uncontained lane tables from
  audit 02 §B migrate).

## Accessibility

- Lane tabs: full ARIA tabs pattern with routable variant; active tab scrolled into
  view.
- Chart: `ChartFrame` ships a text summary (last/change/range + "markers: N
  evidence events") — closes the audit 05 gap (workspace price chart has no
  alternative today).
- Order ticket: existing label/fieldset structure kept; preview status in
  `aria-live="polite"` (existing `PaperPreviewStatus` habit); submit disabled state
  explained in text, not just disabled styling.
- `aria-selected` misuse on `<article>` (PaperCandidateQueue pattern) not repeated;
  selection semantics via proper roles.

## Implementation notes

- `WorkspaceObservability` composition survives; panels rebuilt on primitives.
- `WorkspaceModuleNav` → routable `Tabs`; order from new `LANE_NAV_ORDER`
  (decision-log D12); `laneRegistry.ts` untouched (C4); `WorkspaceModuleNav.sticky`
  test updated for token-derived offset (88px).
- Formalize C1: `paperOrderDraft.ts` documented as the contract home; handoff test
  per mode in `App.test.tsx`.
- `workspaceHealth.formatDataHealthLabel` dead `CAPTURE_REPLAY` branch removed;
  adapter owns labels (semantic-state-system §3.5).
- Options/futures product surfaces: keep the fail-closed derivative preview gate
  as-is; add copy "Derivative paper preview is not available in this build" (Q8).
- Instrument header price uses direction tokens (up/down), never state tones.

## Open questions

- Q8 (derivative preview gate: bug or intended?) — default: preserve + copy.
- Should live instrument selection stay split-brain (route + backend persistence)?
  Default: yes (preserve); surface divergence via disagreement indicator.
  (Non-blocking; hardening candidate.)

## Acceptance criteria

1. All 11 workspace routes render per mode with humanized lane states; zero raw
   enums/IDs above L3; `?data_mode=current` works; frozen/current source is visible.
2. Paper submit only with current matching preview; `PREVIEW_REQUIRED` fail-closed;
   authority loss hides ticket, keeps observability (test per mode).
3. C1 handoff test green; lane registry unchanged (drift test green); polling
   cadences unchanged.
4. Chart has a text alternative; lane tables contained; no page-level horizontal
   scroll at the 7 widths.
5. `App.test.tsx` per-mode lane navigation updated; npm gates green; lane chunks
   stay lazy.
