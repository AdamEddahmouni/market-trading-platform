# Migration Map

Route-by-route migration, the fragile-contracts register, and the redirect/alias plan.
Pair with [information-architecture.md](information-architecture.md) (target IA) and
[decision-log.md](decision-log.md) (why). Every route change carries the standing
obligations: update `App.test.tsx` (audit 05 FRONTEND_GUIDE rule), keep nav labels and
routes in lockstep, run `npm test` + `npm run typecheck` + `npm run build`.

---

## 1. Route-by-route map

| Current route | Destination | Action | Rationale | Parity risks (must preserve) |
|---|---|---|---|---|
| `/` | COMMAND `/` | Rebuild in place (Phase 2) | Already the per-mode now-desk | Replay scrub shell state (`App.tsx:290-300`); per-mode desk layouts; `attention`/`replaySession`/`context`/`assistantStatus` shell queries |
| `/signals` | `/?desk=signals` | **Redirect** (Phase 2) | One component, two routes, differ only by `desk` prop | Desk flag changes data emphasis (Demo hides portfolio summary) — tab must reproduce both layouts; existing deep links |
| `/explore` | `/radar/screeners` | **Redirect** (Phase 3) | Screener bridges join the discovery section | 4 explore queryKeys keep polling; live subscribe flow (`LiveObservationalPanel`) survives; nav label "Markets" retired |
| `/discover` | `/radar` | **Redirect** (Phase 3) | Canonical discovery queue | Paper-only mutations refresh/promote/release; unmount `keepalive` release POST; server-driven 3s/120s timers; dense-table keyboard operation |
| `/workspace` | WORKSPACE index | Stays (Phase 4) | Smart redirect is useful | Live instrument-selection empty state reachable; `context`-driven redirect logic |
| `/workspace/:symbol` | WORKSPACE overview | Stays, rebuilt (Phase 4) | The cockpit | `location.state` paper-draft handoff (see register C1); layout persistence POST; admitted-instrument fallback (BIYA); replay chart availability |
| `/workspace/:symbol/squeeze` | WORKSPACE lane tab | Stays as route, re-presented (Phase 4) | Deep link | `?data_mode=current` param (C2); frozen-vs-current divergence surfaced, not hidden |
| `/workspace/:symbol/order-flow` | lane tab | Stays (Phase 4) | Deep link | 2s live refetch |
| `/workspace/:symbol/order-book` | lane tab | Stays (Phase 4) | Deep link | 2s live refetch |
| `/workspace/:symbol/futures` | lane tab | Stays (Phase 4) | Deep link | `futuresProduct` mode-scoped query |
| `/workspace/:symbol/catalyst` | lane tab | Stays (Phase 4) | Deep link | — |
| `/workspace/:symbol/fund-etf` | lane tab | Stays (Phase 4) | Deep link | — |
| `/workspace/:symbol/options` | lane tab | Stays (Phase 4) | Deep link | `optionsProduct` mode-scoped query; `CanonicalInstrumentSelector` |
| `/workspace/:symbol/large-transactions` | lane tab | Stays (Phase 4) | Deep link | — |
| `/workspace/:symbol/disclosure` | lane tab | Stays (Phase 4) | Deep link | — |
| `/workspace/:symbol/institutional-flow` | lane tab | Stays (Phase 4) | Deep link | Fans out to 8 other lane queries — heaviest lane; keep lazy |
| `/research` | RESEARCH `/research` | Stays; Model Lab + Simulation tabs move to LAB (Phase 6/7) | Interpretation-first research | Tab state was local `useState`; split makes lab tabs routable — back-button behavior changes (accepted, see decision-log D8) |
| `/research/vela-chart-lab` | `/lab/chart-lab` | **Redirect** (Phase 7) | LAB section | Lazy chunk + synthetic feed; no backend dependency |
| `/lab` | LAB `/lab` | **Repoint redirect → real page** (Phase 7) | Today aliases `/research` | Nav "Lab" now distinct from Research |
| `/portfolio` | PORTFOLIO `/portfolio` | Stays, rebuilt (Phase 5) | Mode portfolio views coherent | Session open/close mutations; infinite order history; trace panel; raw `/paper/sessions` session list; live canary snapshot/reconciliation |
| `/control` | CONTROL `/control` | Stays, rebuilt; nav label Risk→Control (Phase 8) | Resolves name/content mismatch | Lifecycle/credential mutations + gating copy; `window.confirm` on apply_update; `<a href>` links → router links |
| `/live-canary` | CONTROL sub-page | Stays as route (Phase 8) | Safety control plane | Read-only invariant; critical banner; 15s polling of snapshot + reliability |
| `/settings` | CONTROL sub-page | Stays as route (Phase 8) | Operator housekeeping | Paper-only mutation gating; raw-fetch refresh patterns |
| `/diagnostics/provider` | CONTROL sub-page (Providers) | Stays as route (Phase 8) | StatusBar health deep link targets it | 5s poll; deep link must keep working |
| `/assistant/history` | Secondary page | Stays; adds "Resume in assistant" (Phase 2, cheap) | Only resume entry point | Conversation list query; resume flow is a new capability (decision-log Q5) |
| `*` | Redirect `/` | Stays | Safety net | — |

## 2. Fragile contracts register

Each contract: what it is, the decision, and the obligation.

### C1 — Paper-draft handoff via `location.state` — **FORMALIZE (preserve mechanism)**
Paper Now drafts intent and navigates PUSH-only to `/workspace/:symbol` carrying a
`PaperOrderDraft` in router state; validated by `parsePaperOrderDraft`
(`paper-now/paperOrderDraft.ts:140-166`), consumed and cleared at
`WorkspaceRoute.tsx:36-44`. Refresh/back loses the draft by design.
- **Decision:** preserve the mechanism; formalize it. The draft type, validator, and
  lifecycle move to a documented module (`paperOrderDraft.ts` already exists — promote
  it to the contract home), and `App.test.tsx` gains explicit handoff coverage per
  mode (partial coverage exists today).
- **Rejected alternative:** URL query params (drafts contain side/qty/limit intent —
  not shareable/bookmarkable state; PUSH-only router state matches the
  "deliberate action" safety posture).
- **Obligation:** any Workspace IA change must keep the handoff working end-to-end;
  lane-level draft CTAs (`LaneModeContextPanel.tsx:110-126`) keep their current
  authority-deferred behavior (ticket enforces authority).

### C2 — Squeeze `?data_mode=current` — **PRESERVE**
`ModeSqueezeWorkspaceRoute.tsx:21-23` reads the param; overview always uses `frozen`;
evidence lane derives from `/context`. The redesign keeps the param and **surfaces**
the frozen/current distinction with `EvidenceSource` pills instead of hiding it.

### C3 — Discover unmount release POST — **PRESERVE**
`POST /discover/mixed/release` with `keepalive` on unmount
(`DiscoverObservability.tsx:226-234`), plus server-driven poll/refresh timers
(3s/120s, paused on `document.hidden`). Radar keeps the lifecycle exactly; the raw
fetch may be wrapped for auth headers (hardening, separate commit) but semantics stay.

### C4 — `laneRegistry.ts` order contract — **PRESERVE ORDER**
`WORKSPACE_LANE_REGISTRY` order (`laneRegistry.ts:3-25`) feeds backend paper
provenance (registry comment lines 47-52) and has a drift test. **Do not reorder or
relabel in the registry.** Operator-priority ordering in the lane Tabs UI comes from a
new presentational `LANE_NAV_ORDER` map keyed by lane id — registry untouched.

### C5 — Polling cadences — **PRESERVE EXACTLY**
Provider health 5s (`hooks.ts:353`); canary snapshot/reconciliation/reliability 15s
(`hooks.ts:363,372`, `LiveCanaryControlPlanePage.tsx:45`); order-flow/order-book/
market-state 2s live-only (`hooks.ts:125,164,433`); workspace evidence 5s live
(`hooks.ts:137`); discover server-driven 3s + 120s refresh. New components subscribe
to the same queryKeys — no new polls, no cadence changes.

### C6 — `App.test.tsx` update obligation — **STANDING**
Every route/nav/surface change updates `App.test.tsx` (mode entry per section, lane
navigation per mode, shortcuts, skip link) in the same PR. Class-name-asserting tests
migrate to `data-testid`/role queries as components are renamed (component-system §5).

### C7 — Bundle budget — **STANDING**
200 KiB documented / **203 KiB enforced** (`check-bundle-budget.mjs`); 199.17 KiB
recorded. All new surfaces lazy; lazy chunks ≤ 500 KB raw (`vela-*` 950 KB, banned
from entry). Budget increases need an ADR + script update.

### C8 — Mutation guards — **PRESERVE (fail-closed)**
From audit 03's mutation table: preview-required submit (`PREVIEW_REQUIRED`
fail-closed), `confirmedRequestIsCurrent` matching, generation counter discarding
stale previews, `canUsePaperActions` gating, Live = zero mutations, Demo read-only,
operator-settings Paper-only gating, `window.confirm` on `apply_update`, unknown
error category fail-closed, schema mismatch throws at the zod boundary. The redesign
re-words these surfaces but never weakens a guard.

### C9 — Mode switch reset — **PRESERVE**
"Switch mode" → `navigate("/", {replace:true})` + bootstrap reset
(`App.tsx:317-321`); mode switch invalidates `context`, `attention`, `instrument`.
Mode stays out of the URL (decision-log Q1).

## 3. Redirect / alias plan

| From | To | Type |
|---|---|---|
| `/signals` | `/?desk=signals` | `<Navigate replace>` |
| `/explore` | `/radar/screeners` | `<Navigate replace>` (preserve `?q=` → carried through) |
| `/discover` | `/radar` | `<Navigate replace>` |
| `/research/vela-chart-lab` | `/lab/chart-lab` | `<Navigate replace>` |
| `/lab` (today → `/research`) | real LAB page | redirect removed; page added |
| `*` | `/` | unchanged |

No other aliases. Old bookmarks/deep links all land; `App.test.tsx` asserts each
redirect.

## 4. Per-phase migration order

Phases match README §phase-plan. Within each phase: primitives first, page second,
tests/redirects last.

1. **Phase 1 — Foundation** (README §foundation-implementation-plan steps 1–9).
   No route changes. Ships tokens, adapter, shell, StatusBar, Drawer, state
   primitives, CopyableIdentifier, responsive primitives.
2. **Phase 2 — Command** `/`; land `/signals` redirect; assistant resume action.
3. **Phase 3 — Radar** `/radar` + `/radar/screeners`; land `/discover`,`/explore`
   redirects; wire `?q=`.
4. **Phase 4 — Workspace** `/workspace/:symbol` + 10 lane tabs; formalize C1; keep
   C2/C4/C5.
5. **Phase 5 — Portfolio** `/portfolio`; humanize money/time; Attribution tab
   (strategy profitability single home — decision-log D6).
6. **Phase 6 — Research** `/research` interpretation-first; Methodology disclosure.
7. **Phase 7 — Lab** `/lab` real page + `/lab/validation` + `/lab/simulation` + `/lab/chart-lab`; land
   `/research/vela-chart-lab` redirect; `/lab`→`/research` redirect removed (UIR-01H).
8. **Phase 8 — Control** `/control` + sub-pages; nav Risk→Control; retarget StatusBar
   health indicator to `/diagnostics/provider`.
9. **Phase 9 — Responsive/a11y pass** per responsive-contract; axe + viewport matrix
   (when no trading session).

**Merge/integration note:** base is `d588728d`; origin/main is 3 backend-only commits
ahead (`7aade60b`, `64f1cb42`, `3daab7f2`) with zero `ui/`/`e2e/` delta — rebase at
integration time; no mid-program rebase required.
