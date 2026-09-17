# Information Architecture

Target IA for the redesign: seven sections — **COMMAND, RADAR, WORKSPACE, PORTFOLIO,
RESEARCH, LAB, CONTROL** — plus global chrome. Names below are canonical; every other
doc in this set uses exactly these names and paths.

Source: audit 01 (25 routes, nav, mode routing) refined against the doctrine. Route
paths that change are paired with redirect aliases in
[migration-map.md](migration-map.md); nothing 404s.

---

## The seven sections

### COMMAND — `/`
**Responsibility:** platform + portfolio state *right now*, per mode. The L1 desk.
**Questions answered:**
- What needs my attention right now?
- What is IMP doing / what mode am I in, and can I trade?
- How is the paper account / live observation performing today?
- Is anything degraded, blocked, or stale — and what do I do about it?
- (Demo) Where am I in the replay and what happened next?

### RADAR — `/radar` (+ `/radar/screeners`)
**Responsibility:** the canonical discovery queue: find → rank → filter → compare →
investigate. Absorbs today's `/discover` (opportunity cockpit) and `/explore` (donor
screener bridges).
**Questions answered:**
- What opportunities exist, ranked, and why now?
- Why is the queue empty/unready — and what unblocks it?
- What changed since I last looked? What confirms/contradicts this idea?
- (Screeners tab) What do the raw donor screens (squeeze cohort, scanner, futures,
  catalyst) show, with provenance?
- Empty states must explain **why** empty (feed UNREADY reason, no candidates passed
  filters, live mode has no opportunity engine, etc.).

### WORKSPACE — `/workspace`, `/workspace/:symbol`, `/workspace/:symbol/{lane}`
**Responsibility:** decision cockpit for one instrument: understand → verify →
construct → risk-check → simulate. Paper order submit lives **only** here, with a
current preview and fail-closed guards. The 10 evidence lanes are tabs of the
instrument, not separate pages conceptually (routes stay deep-linkable).
**Questions answered:**
- What is this instrument doing and what does the evidence say per lane?
- Why does IMP think this (signals, evidence, source agreement)?
- What happens if I trade it (preview: risk, sizing, quality)?
- Is my preview still valid? Am I authorized right now?

### PORTFOLIO — `/portfolio`
**Responsibility:** account truth per mode: NAV/cash/buying power, realized/
unrealized/daily P&L, positions, orders, exposure, risk utilization, concentration,
attribution (strategy profitability), execution trace, session lifecycle.
**Questions answered:**
- What is my account worth, what changed today, and why?
- What am I holding, what is working/failing, and how stale are my marks?
- How much of my risk budget am I using? What blocked?
- Which strategies made/lost money (attribution)?

### RESEARCH — `/research`
**Responsibility:** interpretation-first research surface. Research ≠ trading screen.
Fingerprints/hashes/enums move to a Methodology disclosure.
**Questions answered:**
- What does the evidence currently conclude, and how much should I trust it?
- How were these analytics produced (methodology, authority boundary)?
- What is the distribution of outcomes/signals over the research window?

Landed IA (UIR-01F): Overview (default), Evidence, Validation, Simulation. Current
contracts have no hypothesis, domain, or source-catalog objects — those stay
honest gaps on Overview. See [research-contract-map.md](research-contract-map.md).

### LAB — `/lab` (+ `/lab/simulation`, `/lab/chart-lab`)
**Responsibility (future):** models, strategies, replay/simulation, calibration,
walk-forward, evaluation. **Not built.** `/lab` still redirects to `/research`.
Validation and simulation remain Research evidence records until a Lab increment
splits the workbench. Endpoints stay `/research/models` and `/research/simulation`.

### CONTROL — `/control` (+ `/diagnostics/provider`, `/live-canary`, `/settings`)
**Responsibility:** platform operations: provider health matrix (state / provides /
impact), runtime, config, diagnostics, safety controls, local lifecycle. Normal IMP
components — no default browser controls, no full-reload `<a href>` links.
**Questions answered:**
- Is the local platform healthy? What needs operator action?
- Which providers are connected/degraded/down, what does each provide, and what does
  a failure affect?
- What is the live-canary safety state (kill switches, incidents, reconciliation)?
- What is persisted locally (sessions, captures, watchlist)?

---

## Full route assignment table

"Stays" = keeps URL. "Redirect" = old URL permanently redirects to the canonical one.
"Tab" = presented as a tab inside the parent surface (route kept for deep link where
noted). Mode variants (Demo/Paper/Live) are unchanged per route — the `Mode*Route`
wrapper pattern is preserved (audit 05, FRONTEND_GUIDE lockstep rule).

| # | Current route | Current nav label | Destination | How | Rationale / parity risk |
|---|---|---|---|---|---|
| 1 | `/` | Overview | COMMAND `/` | Stays | Already the per-mode "now" desk. Replay scrub stays shell-level. |
| 2 | `/signals` | Signals | COMMAND, Signals tab `/?desk=signals` | Redirect | Same component as `/` with `desk` prop; tab must preserve both desk layouts per mode (Demo hides portfolio summary). |
| 3 | `/explore` | Markets | RADAR, Screeners tab `/radar/screeners` | Redirect | Screener bridges are discovery-adjacent; live `LiveObservationalPanel` subscribe flow must survive; dead `?q=` param gets wired (see decision-log). |
| 4 | `/discover` | Opportunity Radar | RADAR `/radar` | Redirect | Already the discovery cockpit. Paper-only mutations (refresh/promote/release incl. unmount keepalive POST) preserved exactly. |
| 5 | `/workspace` | Workspace | WORKSPACE index `/workspace` | Stays | Smart redirect (live active instrument / admitted replay instrument / selection empty state) preserved. |
| 6 | `/lab` | Lab | LAB `/lab` | Repoint | Today redirects to `/research`; becomes a real page. |
| 7 | `/workspace/:symbol` | — | WORKSPACE overview | Stays | The cockpit. `location.state` paper-draft handoff preserved (formalized); layout persistence POST `/operator/workspace` preserved. |
| 8–17 | `/workspace/:symbol/{squeeze, order-flow, order-book, futures, catalyst, fund-etf, options, large-transactions, disclosure, institutional-flow}` | (lane tab bar) | WORKSPACE lane tabs | Stays (routes), re-presented as Tabs | Deep links kept; `?data_mode=current` on squeeze kept; `laneRegistry.ts` order **not** reordered (backend provenance contract); 2s/5s live polling cadences kept. |
| 18 | `/research` | Research | RESEARCH `/research` | Stays; loses Model Lab + Simulation tabs to LAB | Analytics remains; tab state was local `useState` — split makes tabs routable under `/lab`. |
| 18a | `/research/vela-chart-lab` | — | LAB `/lab/chart-lab` | Redirect | Self-contained synthetic-feed playground; lazy chunk retained. |
| 19 | `/portfolio` | Portfolio | PORTFOLIO `/portfolio` | Stays | Account/holdings/P&L operator view; Paper session open/close; order history (infinite); trace overlay; strategy profitability; Workspace handoff. No in-page OrderTicket. |
| 20 | `/live-canary` | Live Canary (operator) | CONTROL, Canary sub-page `/live-canary` | Stays (route), re-parented under Control | Read-only invariant + critical banner preserved; 15s polling preserved. |
| 21 | `/settings` | Settings (operator) | CONTROL, Settings sub-page `/settings` | Stays (route), re-parented | Paper-only mutation gating preserved; raw-fetch patterns documented for later hardening. |
| 22 | `/control` | Risk | CONTROL `/control` | Stays; nav label renamed **Control** | Resolves Risk/Operator-center mismatch; `<a href>` related links converted to router links. |
| 23 | `/diagnostics/provider` | Diagnostics (operator) | CONTROL, Providers sub-page `/diagnostics/provider` | Stays (route), re-parented | StatusBar health indicator deep-links here (replaces ContextBar QUALITY click); 5s poll kept. |
| 24 | `/assistant/history` | (not in nav) | Secondary route, unchanged; gains "Resume in assistant" action | Stays | Self-declared secondary route; resume path added (open existing conversation in sidecar instead of always creating new — see decision-log). |
| 25 | `*` | — | Redirect to `/` | Stays | Safety net. |

### Nav assignment (PrimaryNav, in order)

| # | Label | Target | Notes |
|---|---|---|---|
| 1 | Command | `/` | `end` matching |
| 2 | Radar | `/radar` | |
| 3 | Workspace | `/workspace` | |
| 4 | Portfolio | `/portfolio` | |
| 5 | Research | `/research` | GATED badge removed (no gate logic exists — copy only; see decision-log) |
| 6 | Lab | `/lab` | No longer a duplicate of Research |
| 7 | Control | `/control` | Replaces "Risk"; operator sub-pages grouped inside |

Operator group is dissolved into Control. Per-mode nav hints are kept (short human
phrases, e.g. Radar: DEMO "Replay discovery" / PAPER "Candidate discovery" / LIVE
"Live monitor"). `/assistant/history` stays out of nav by design.

### What becomes page / tab / drawer / panel / redirect

| Concept (audit 01 concept table) | Becomes |
|---|---|
| Overview `/` | **Page** — Command |
| Signals `/signals` | **Tab** of Command + redirect |
| Markets/Explore `/explore` | **Tab** of Radar (Screeners) + redirect |
| Discover `/discover` | **Page** — Radar (canonical `/radar`) |
| Workspace + 10 lanes | **Page** + **Tabs** (routes kept) |
| Research home | **Page** — Research (Analytics) |
| Model Lab / Simulation tabs | **Tabs** of Lab (routable) |
| Vela chart lab | **Tab** of Lab + redirect |
| Portfolio | **Page** — Portfolio |
| Operator center `/control` | **Page** — Control overview |
| Live Canary | **Sub-page** of Control (route kept) |
| Settings | **Sub-page** of Control (route kept) |
| Provider diagnostics | **Sub-page** of Control (route kept) |
| Assistant history | **Page** (secondary, unnav'd) + sidecar resume |
| Assistant sidecar, explanation drawer, inspector panel | Global **Drawers** (one Drawer primitive) |
| Command search | Global **CommandPalette** (upgraded from ticker-only input) |
| Mode bar + context bar + capability strip | Global **StatusBar** (one consolidated bar) |
| Startup recovery banner | Global **AttentionBanner** instance in shell |

---

## Global shell contents

One `AppShell` (extended `ImpProductChrome`) containing:

1. **PrimaryNav** (sidebar; overlay dialog < 1024px — see
   [responsive-contract.md](responsive-contract.md)): brand block, 7 sections, footer
   with version + shortcut hints.
2. **Top bar**: menu toggle (< 1024px), **CommandPalette** trigger/input (Ctrl/Cmd+K,
   `/`), **notifications/attention indicator** (count from `attention` query; opens
   Command), keyboard-shortcuts button (`?`), **Switch mode** button.
3. **StatusBar** (single 40px bar, replaces ModeEnvironmentBar + ContextBar +
   ImpCapabilityStrip; ~205px of stacked chrome → ~88px total with top bar):
   - **ModeBadge** — human sentence + tone: "Demo replay — trading disabled" /
     "Paper trading active — simulated fills" / "Live observation — read-only".
   - **Execution authority** — human: "Paper orders only" / "No trading authority" /
     "Trading blocked"; tone from the semantic system.
   - **Data health** — human sentence + `FreshnessIndicator` ("Market data is
     partially degraded · updated 2m ago"); click → `/diagnostics/provider`.
   - **Session status** — human: "Paper session open · started 9:12 AM" (id behind
     CopyableIdentifier in the details popover); replay cursor in Demo.
   - **Selected-instrument context** — current instrument chip (from route /
     `/context` `active_instrument`), click → Workspace.
   - **Degradation / subsystem-disagreement indicator** — appears only when
     `coherence_warning` or a mode/backend mismatch exists; opens a ContradictionPanel.
   - Everything raw (enums, ISO µs timestamps, session UUIDs, capability list) moves
     into the StatusBar's **details popover/drawer** (L4), which also hosts the
     capability matrix (today's `ImpProviderMatrixDrawer`).
4. **Global drawers** (all built on one `Drawer` primitive with focus trap + restore):
   AssistantSidecar, ExplanationDrawer, InspectorPanel, provider matrix.
5. **Global banners**: `StartupRecoveryBanner` re-rendered as `AttentionBanner`
   (tone=caution/critical) with 3-question content.
6. **Mode routing is unchanged**: `ApplicationBootstrap` → `ModeLauncher` →
   `ModeTransition` → shell. Mode stays session-scoped React state (not URL) — default
   decision, tracked in [decision-log.md](decision-log.md).

### Shell invariants (binding)

- Paper submit only from the Workspace cockpit with a current preview; authority loss
  hides the ticket but **keeps observability**; fail-closed guards untouched.
- Live mode has zero mutations by construction; Demo is read-only.
- Esc closes layers; Ctrl/Cmd+K, `/`, `A`, `?` shortcuts preserved; skip link first in
  DOM; exactly one banner landmark.
- Polling cadences (5s provider health, 15s canary, 2s live market lanes, 5s live
  workspace evidence, discover server-driven 3s/120s) are not altered by shell work.
