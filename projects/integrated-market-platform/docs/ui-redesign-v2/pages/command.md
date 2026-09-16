# COMMAND — `/`

## Purpose

The L1 desk: platform + portfolio state **right now**, per mode. One screen that
answers "what needs my attention, what is IMP doing, and is anything wrong" before
any navigation. Hosts two tabs: **Overview** (`/`) and **Signals** (`/?desk=signals`,
redirect target of the old `/signals` route).

## Primary user questions

1. What needs my attention right now — and what do I do about each item?
2. What mode am I in, and can I trade? (Also answered globally by the StatusBar.)
3. How is the paper account / live observation doing today (P&L, risk, exposure)?
4. Is any data degraded, stale, or blocked — what does it affect, what's the action?
5. (Demo) Where am I in the replay; what happened at the cursor?
6. (Paper) Which candidates are queued, and how do I construct an order from one?

## Current-state problems

- Raw `DATA/EXEC/AUTH` enums + ISO µs timestamp + `QUALITY STALE` with no cause or
  action on every page — audit 04 offenses #1–#3 (`ContextBar.tsx:31-61`).
- `SESSION CONTEXT` panel duplicated the entire context bar (screenshot S1;
  **[screenshot-only]** chrome — already gone in source, do not reintroduce).
- Attention cards lead with SNAKE_CASE reason chips and omit why-now/what-changed/
  evidence-strength/freshness — audit 04 offense #6 (`AttentionFeed.tsx:36-38`);
  tier is border-color only (`layout.css:264`) — color-only encoding.
- `MARKET PULSE` metric rows have no interpretation (**[screenshot-only]**; current
  `ImpOverviewKpiStrip` `tone-*` classes are unstyled — audit 02 §2).
- `/` and `/signals` are one component with a `desk` prop — route sprawl
  (audit 01 §observations #3).
- Bare dead-ends: "Attention feed unavailable.", "Replay status unavailable." —
  audit 04 warnings #13/#14 (fail 3-question rule).
- Paper Now's draft composer authority check is stricter than the workspace ticket's
  (`PAPER_ONLY` exactly vs `PAPER_ONLY || AUTHORIZED` — audit 03 contradiction #1);
  the divergence must be surfaced, not hidden.

## Information hierarchy

- **Primary (L1):** attention/opportunity queue (human headline, why-now, freshness,
  next action); account/risk strip (NAV or cash, daily P&L, risk utilization,
  kill-switch state); active system problems (`AttentionBanner` stack).
- **Secondary (L2):** what each attention item means (confidence, evidence strength,
  implication); Paper candidate queue with "Draft in Workspace" handoff; Demo replay
  progress + scrub; Live provider/safety summary.
- **Contextual (L3):** evidence per item (`EvidenceStack`), source agreement,
  supports/contradicts preview.
- **Advanced (L3/L4 boundary):** opportunity ranking vectors, tier definitions,
  per-lane contribution.
- **Technical-Audit (L4):** reason codes, row IDs, session UUIDs, raw timestamps,
  raw quality/authority enums — `TechnicalDetails` / StatusBar details popover only.

## Wireframe

```
┌──────────────────────────────────────────────────────────────────────┐
│ AppShell: PrimaryNav │ Top bar (CommandPalette · ? · Switch mode)     │
│                      │ StatusBar (ModeBadge · authority · data health │
│                      │  · freshness · session · instrument · ⚠)       │
├──────────────────────┴───────────────────────────────────────────────┤
│ PageHeader: Command — {mode sentence}            [Tabs: Overview|Signals]│
├──────────────────────────────────────────────────────────────────────┤
│ AttentionBanner stack (only when active):                            │
│  ⚠ Market data is partially degraded — discovery may be incomplete.  │
│    Affects: Radar, Workspace evidence.  → Check Providers            │
├──────────────────────────────────────────────────────────────────────┤
│ ┌─ WHAT MATTERS NOW ────────────────────┐ ┌─ ACCOUNT / RISK ────────┐│
│ │ OpportunityCard (review density) ×N   │ │ MetricGroup:            ││
│ │  · headline (human)                   │ │  NAV/cash · daily P&L   ││
│ │  · why now · what changed             │ │  risk utilization (meter)││
│ │  · ConfidenceIndicator FreshnessInd.  │ │  exposure · kill switch ││
│ │  · [Open workspace] [Why?] [Evidence] │ │ RiskSummary             ││
│ │  (EmptyState explains WHY if empty)   │ │ (Demo: replay progress) ││
│ └───────────────────────────────────────┘ └─────────────────────────┘│
├──────────────────────────────────────────────────────────────────────┤
│ Mode row (one of, by mode):                                          │
│  DEMO:  replay scrub slider + "what happened next" panel             │
│  PAPER: candidate queue → [Draft in Workspace] handoff CTA           │
│  LIVE:  ProviderHealth strip + safety snapshot + symbol lookup       │
└──────────────────────────────────────────────────────────────────────┘
```

## Components

`PageHeader`, `Tabs` (Overview/Signals), `AttentionBanner`, `OpportunityCard`
(review density), `OpportunityScore`, `ConfidenceIndicator`, `FreshnessIndicator`,
`EvidenceStack`, `Metric`, `MetricGroup`, `RiskSummary`, `EmptyState`,
`LoadingState`, `ErrorState`, `DegradedState`, `TechnicalDetails`, `ModeBadge`
(via StatusBar), `ProviderHealth` (Live), `Drawer` (evidence/inspector).

## Interactions

- Tab switch Overview ↔ Signals updates `?desk=` (replace navigation); deep link
  `/signals` redirects to `/?desk=signals`.
- Attention card actions: Open workspace (→ `/workspace/:symbol`), Why?/Explain
  (ExplanationDrawer), Inspect (InspectorPanel), Evidence (EvidenceStack expand).
- Paper: candidate select → "Draft in Workspace" → PUSH navigate with
  `PaperOrderDraft` in `location.state` (contract C1 — preserved).
- Demo: replay scrub slider (shell-level scrub POST `/replay/scrub` → `refreshAll`
  invalidation — unchanged).
- Live: symbol lookup → subscribe (POST `/subscriptions`) → navigate to workspace.
- Opportunity ack (watch/dismiss/review) where permitted (Paper only).

## States

- **Empty:** attention queue empty → EmptyState with reason ("No attention items —
  all lanes quiet as of {time}"); opportunities EMPTY → why ("no candidates passed
  the current filters/coverage"); Live mode → opportunity feed is UNAVAILABLE by
  design: "Live mode has no opportunity engine — use Radar and workspace evidence."
- **Loading:** `LoadingState` skeletons for queue + metric strip (no bare
  "Loading…" paragraphs).
- **Degraded:** `DegradedState` per affected widget with 3-question content; feed
  UNREADY → AttentionBanner with humanized `unready_reason` + "Open Control" action.
- **Error:** `ErrorState` per widget (humanized category + retry); shell context
  error → StatusBar "Backend context unavailable — execution controls locked" +
  Control link.
- **Demo:** replay tone; read-only; scrub controls; portfolio summary is simulated
  (labeled "Simulated account"). Signals desk hides portfolio summary (parity).
- **Paper:** paper tone; candidate queue + draft handoff; risk ribbon live from
  `paperPortfolio`; session status in StatusBar.
- **Live:** live tone; read-only observation; provider ribbon + safety snapshot;
  opportunity feed replaced by the by-design empty state above.

## Data dependencies

- Shell (existing, unchanged): `context`, `attention`, `replaySession`,
  `assistantStatus` (`App.tsx:200-203`).
- All modes: `opportunitiesSummary` (`/opportunities/summary`);
  `paperPortfolio`/`demoPortfolio` (`/paper/portfolio?view_mode=…`,
  `ModeNowRoute.tsx:26,36`).
- Live adds: `providerHealth` (5s poll), `liveCanarySnapshot("now")` (15s).
- Paper adds: order preview mutation (`usePreviewPaperOrderMutation`), opportunity
  ack (`useOpportunityAckMutation`).
- Mutations: replay scrub POST `/replay/scrub` (shell); no new endpoints.

## Responsive behavior

- ≥1440px: queue + account/risk two-column; mode row full width below.
- 1024–1439px: two-column preserved with `minmax(0,…)`; metric groups auto-fit.
- 720–1023px: single column; account/risk strip collapses to a 2×2 MetricGroup.
- <720px: single column; queue cards stack; scrub controls full width.
- No page-level horizontal scroll at any of the 7 verification widths; KPI strip
  uses auto-fit `minmax(160px, 1fr)`, never fixed columns.

## Accessibility

- One H1 (`PageHeader`); tabs use the full ARIA tabs pattern (`Tabs` primitive).
- Attention queue is a list with real buttons (no `tabIndex` divs); tier shown as
  text ("Tier 1 — act now") + tone, never color alone.
- Scrub slider: `role="slider"` equivalents with keyboard steppers (existing
  Previous/Next buttons retained); `role="progressbar"` + `aria-value*` kept.
- Banners: `role="alert"` only for critical; others `role="status"`.
- All async updates in `aria-live="polite"` regions (existing habit, kept).

## Implementation notes

- Rebuild on `ImpOverviewBoard` composition (KPI strip + primary queue) — the
  structure is right; replace contents with the primitives above.
- Delete the `desk`-prop route duplication: `ModeNowRoute` reads `?desk=`; `/signals`
  becomes `<Navigate to="/?desk=signals" replace>`.
- Reason chips → human labels via `resolveSemanticState` + reason-label map; raw
  codes move to the card's TechnicalDetails.
- `ImpOverviewKpiStrip` `tone-*` phantom classes replaced by Metric tones.
- Keep `paperActionsPermitted` gating exactly; surface the stricter PaperNow check
  divergence as a DegradedState note ("Drafting limited: backend reports
  {human authority}") rather than silently failing — see decision-log D18/Q8-adjacent.

## Open questions

- Should the Signals desk remain a separate tab long-term, or fold into Overview
  filters? Default: keep tab (parity), revisit after usage evidence. (Non-blocking.)
- Q1 (mode-in-URL) affects nothing here — StatusBar carries mode.

## Acceptance criteria

1. `/` renders per mode with human-language L1; zero raw enums/IDs/ISO timestamps
   above L3; `/signals` redirects and the Signals tab preserves both desk layouts.
2. Every banner/warning on the page passes the 3-question rule; every empty state
   says why.
3. Paper draft handoff works end-to-end (C1 test green); replay scrub unchanged;
   Live has zero mutations.
4. No page-level horizontal scroll at 2560/1920/1600/1440/1366/1280/1024.
5. `App.test.tsx` updated (per-mode entry + redirect); `npm test`, `npm run
   typecheck`, `npm run build` green; entry chunk within 203 KiB.
