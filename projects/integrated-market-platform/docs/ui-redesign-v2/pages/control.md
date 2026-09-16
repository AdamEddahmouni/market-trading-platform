# CONTROL — `/control` (+ `/diagnostics/provider`, `/live-canary`, `/settings`)

## Purpose

Platform operations: provider health matrix (state / provides / impact), runtime,
config, diagnostics, safety controls, local lifecycle. One section, four sub-pages:
**Overview** (`/control`), **Providers** (`/diagnostics/provider`), **Live Canary**
(`/live-canary`), **Settings** (`/settings`). Normal IMP components throughout — no
default browser controls, no full-reload `<a href>` navigation.

## Primary user questions

1. Is the local platform healthy? Does anything need operator action right now?
2. Which providers are connected/degraded/down — what does each provide, and what
   does a failure affect?
3. What is the live-canary safety state — kill switches, incidents, reconciliation,
   reliability?
4. What is persisted locally (sessions, captures, watchlist) and is any of it
   unhealthy?
5. How do I repair a provider (credentials, gate, transport) — in-UI first, CLI as
   advanced fallback?

## Current-state problems

- Nav label "Risk" opens this IT-ops console — mislabeled wayfinding is a safety
  issue (audit 04 offense #5); fixed by IA (nav → "Control").
- Diagnostics is a raw wire-state wall: `Role MARKET_DATA`, `DISPLAY_ONLY`,
  `US_EQUITY_L1 · refs 1`, `Last auth error NONE`, raw `connection_state`, raw
  provider generation id (audit 04 S8 rows 26–30); the decision-relevant fact
  ("this provider can never route orders") is buried mid-list.
- Expanded `Internal simulation gate` JSON block in the primary viewport (S9) —
  must default-collapsed "Audit details".
- Finviz repair is CLI-only copy (`python tools/finviz/auth.py repair`) — needs an
  in-UI path first, CLI as advanced fallback (audit 04 observations #6).
- Settings renders raw filesystem path, schema integer, `Restore … · NONE`,
  `Execution deferred NO`, full untruncated capture IDs, and a raw JSON "Safety env"
  dump (S10 rows 5/41) — safety config deserves a human summary.
- Operator center links to sibling surfaces via `<a href>` full reloads
  (`OperatorControlCenterPage.tsx:119-121`).
- Provider health has four overlapping implementations and three cadences (audit 03
  #3) — consolidated into `ProviderHealth` (component-system #6).
- Readiness checks are the app's best 3-question implementation (label + detail +
  next action) — **keep and generalize** (audit 04, the single ✅).

## Information hierarchy

- **Primary (L1):** platform status hero (human: "Platform running · all checks
  pass" / "{n} checks need action"); provider health matrix summary (n healthy /
  n degraded / n down); canary safety headline (kill switches, unresolved critical
  incidents); active `AttentionBanner`s.
- **Secondary (L2):** readiness checklist (label/detail/next-action — existing
  pattern); provider cards with state/provides/impact + next action; canary kill
  switches + reconciliation + incidents; settings summaries (persistence, sessions,
  captures, watchlist) in words.
- **Contextual (L3):** per-channel telemetry (lag p50/p95, quota, reconnects),
  reliability matrix, lifecycle action history, capture list.
- **Advanced:** credential forms (gated), lifecycle actions (restart/update),
  provider refresh, transport detail.
- **Technical-Audit (L4):** execution-gate JSON, connection-state enums, capability
  IDs, generation IDs, account fingerprints, `as_of_ns`, filesystem paths, schema
  versions, safety-env raw JSON — TechnicalDetails ("Audit details",
  default-collapsed).

## Wireframe

```
┌──────────────────────────────────────────────────────────────────────┐
│ (AppShell chrome + StatusBar — global; health indicator → Providers) │
├──────────────────────────────────────────────────────────────────────┤
│ PageHeader: Control — "Local platform operations"                    │
│   [Sub-nav Tabs: Overview | Providers | Live Canary | Settings]      │
├──────────────────────────────────────────────────────────────────────┤
│ OVERVIEW (/control):                                                 │
│ ┌ Hero: "Platform running · 12 checks pass · 1 needs action"        ││
│ │  [Restart platform] [Check updates] [Apply update*] (*confirm)    ││
│ ├ Readiness checklist: ✓/! rows (label · detail · next action)      ││
│ ├ Provider readiness cards: state pill · provides · impact ·        ││
│ │  "Next: {action}" [Refresh]                                       ││
│ └ Local configuration (credential forms, gated) — Advanced section  ││
│ PROVIDERS (/diagnostics/provider):                                   │
│ ┌ ProviderHealth matrix: provider · state(human+tone) · provides ·  ││
│ │  impact-if-down · freshness                                       ││
│ ├ Per-provider detail: channels ("US equities — basic quotes:       ││
│ │  working/degraded/not in subscription — affects {lane}") · lag ·  ││
│ │  quota · "Market data only — cannot route orders" callout         ││
│ ├ Finviz: auth state human + [Repair in Settings] (CLI in details)  ││
│ └ Audit details (TechnicalDetails, collapsed): gate JSON, raw enums ││
│ LIVE CANARY (/live-canary):                                          │
│ ┌ Critical banner: "LIVE CANARY — REAL MONEY — HUMAN CONFIRMATION   ││
│ │   REQUIRED" (unchanged, restyled to tokens)                       ││
│ ├ Safety grid: kill switches (human states) · block reasons         ││
│ │  (one sentence each + action) · reconciliation · incidents        ││
│ └ Reliability matrix (DataTable, contained; was unstyled phantom)   ││
│ SETTINGS (/settings):                                                │
│ ├ Human summaries: "Persistence on · crash recovery: none needed ·  ││
│ │  execution startup: normal" · safety summary in words             ││
│ ├ Paper sessions (humanized rows) · Captures (name/date + copyable  ││
│ │  id + Replay) · Watchlist (Paper-gated)                           ││
│ └ TechnicalDetails: state dir path, schema version, safety-env JSON ││
└──────────────────────────────────────────────────────────────────────┘
```

## Components

`PageHeader`, `Tabs` (section sub-nav; routes kept), `ProviderHealth` (matrix +
chips — the consolidated implementation), `SystemHealth` (hero aggregate),
`Metric`, `MetricGroup`, `DataTable` (reliability matrix, channels, captures),
`AttentionBanner`, `DegradedState`, `ErrorState`, `EmptyState`, `LoadingState`,
`TechnicalDetails`, `CopyableIdentifier`, `Modal` (update confirm replaces
`window.confirm`), `FilterBar` (captures/incidents), `FreshnessIndicator`.

## Interactions

- Sub-nav switches routes (`/control`, `/diagnostics/provider`, `/live-canary`,
  `/settings`) via router links — `<a href>` full reloads removed.
- Lifecycle actions (restart/check_update/apply_update) preserved; `apply_update`
  confirm moves from `window.confirm` to `Modal` (same gate, accessible).
- Provider refresh + credential save mutations preserved with existing gating copy;
  "Live execution remains locked" boundary note preserved verbatim in spirit.
- Settings mutations stay Paper-only (`canMutateOperatorSettings`); read-only note
  humanized per mode (existing good pattern, kept).
- Capture replay buttons preserved (capture must be `AVAILABLE`).
- StatusBar health indicator deep-links to `/diagnostics/provider` (replaces
  ContextBar QUALITY click — same target).

## States

- **Empty:** "No captures stored" / "No incidents" / "No active subscriptions" —
  each with why/what-appears-here.
- **Loading:** skeletons; readiness checks show "Checking…" state (humanized).
- **Degraded:** provider DEGRADED/CONNECTED_DEGRADED → caution rows with impact;
  channel UNAVAILABLE → "Not in your subscription — {lane} disabled" (neutral, not
  red); readiness ACTION_REQUIRED → caution with next action.
- **Error:** control center unreadable → keep today's model copy ("The control
  center could not read local platform status. Start the local platform, then check
  again." — the ✅ reference); provider health unavailable → ErrorState + retry.
- **Demo:** settings read-only note; canary page mode-aware copy; replay tone.
- **Paper:** settings mutations enabled; paper tone.
- **Live:** settings read-only; canary surface primary; live tone. Live mode adds
  zero mutations everywhere in Control.

## Data dependencies

- Overview: `api.getOperatorReadiness` / `getOperatorLifecycleStatus` /
  `getOperatorConfig` (manual fetch today — keep pattern, D20); lifecycle/provider/
  config POSTs (`/operator/lifecycle/actions`, `/operator/providers/{p}/refresh`,
  `/operator/config/provider`).
- Providers: `providerHealth` (5s poll, `/provider/health`); `operatorReadiness`
  (60s staleTime) when the matrix drawer opens.
- Canary: `liveCanarySnapshot("canary-plane")` (15s), `["canary-reliability"]`
  (raw GET `/canary/reliability`, 15s), `liveCanaryReconciliation` (15s).
- Settings: raw GET `/state/startup`, `/operator/state`, `/captures`; POST
  `/operator/watchlist`, `/captures/replay` (Paper-gated).
- Read-only invariant on `/live-canary`: no mutations (preserved; "No generic
  ENABLE LIVE button").

## Responsive behavior

- ≥1440px: hero + checklist + provider cards multi-column (2-col grid, minmax(0,…)).
- 1024–1439px: 2-column; matrix table contained.
- 720–1023px: single column (fixes the 821–1094px overflow from
  `operator-control.css` min-654px grid).
- <720px: single column; credential forms full width; tables scroll internally.
- Health matrix becomes a real contained `DataTable` (currently an unstyled
  phantom-class table).

## Accessibility

- One banner landmark (StatusBar); page hero is a `<section>` with heading, not a
  banner.
- Readiness rows: ✓/! icons always paired with text; `role="status"` for check
  updates.
- Credential forms: labels + `autocomplete` + announced errors (extend the
  `OperatorLoginGate` form pattern); password inputs keep visibility toggle
  keyboard-operable.
- Kill-switch states: text + tone, never color-only; critical banner is
  `role="alert"`.
- Modal confirm: focus trap + restore (the new `Modal` primitive).

## Implementation notes

- `OperatorControlCenterPage` rebuilt on primitives; readiness-check rendering
  extracted as the reference 3-question pattern (shared sub-component used by
  AttentionBanner stories/tests).
- `ProviderHealthPanel` page content merges with `ImpProviderMatrixDrawer` into the
  Providers sub-page (one matrix, one detail treatment); channel-state derivation
  (`ProviderHealthPanel.tsx:5-7` + `liveDashboardViewModel.ts:20-23` duplicates)
  moves into the adapter.
- Operator blues (`operator-control.css:26-29,34,228`) and status hexes
  (`#7dd3a8/#f2ca59/#f58d91`) replaced by state tokens; the page stops looking like
  a separate blue product.
- Settings human summaries derive only from existing payload fields (`restore`,
  `execution_deferred`, `opend`, persistence) — no invented state.
- Finviz repair: primary action links to Settings provider section; CLI command
  stays in TechnicalDetails (no in-UI repair mutation is invented — none exists
  backend-side).

## Open questions

- Should credential forms move from Overview to Settings (security-UX smell noted in
  audit 04 S6)? Default: keep on Control Overview (parity), add Settings
  cross-link; moving is a follow-up. (Non-blocking.)
- In-UI Finviz auth repair would need a backend endpoint — none exists. Default:
  CLI-in-details (above). **→ USER-adjacent** (backend wishlist, not blocking).

## Acceptance criteria

1. Nav shows "Control" (no "Risk"); all four routes render inside the Control
   sub-nav; `<a href>` full reloads gone; ContextBar-successor health indicator
   deep-links to Providers.
2. Provider matrix shows state/provides/impact in human language; "cannot route
   orders" callout prominent; gate JSON default-collapsed; zero raw enums above L3.
3. Canary page keeps read-only invariant + critical banner; kill switches and block
   reasons humanized; 15s polls unchanged.
4. Settings shows human summaries; Paper-only gating intact; capture/session IDs
   truncate+copy.
5. No page-level horizontal scroll at the 7 widths; `App.test.tsx` updated
   (control/settings/diagnostics/canary per mode); npm gates green.
