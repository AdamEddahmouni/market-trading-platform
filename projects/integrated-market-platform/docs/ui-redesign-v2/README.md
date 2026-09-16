# IMP UI/UX Redesign v2 — Program Plan

> **RTH15-00 recovery:** planning/docs only. Implementation remains isolated on
> `ui/operator-redesign-v2` (`5726238d`, incomplete shell). These files are not
> current production UI architecture. Do not treat them as shipped chrome.

Operator-first redesign of the Integrated Market Platform (IMP) UI: from engineering
console to operator-first market intelligence, decision, simulation, research, and
portfolio platform.

This directory is the **authoritative plan**. Implementation workers should treat these
documents as their only required context: route names, token names, component names,
semantic tone names, and queryKeys are used identically across all 16 files.

- Audits (inputs, read-only): [audits/01-routes-pages.md](audits/01-routes-pages.md),
  [audits/02-components-styles.md](audits/02-components-styles.md),
  [audits/03-state-data.md](audits/03-state-data.md),
  [audits/04-screenshot-terminology.md](audits/04-screenshot-terminology.md),
  [audits/05-a11y-responsive-tests.md](audits/05-a11y-responsive-tests.md)
- Plan (this set):
  1. [information-architecture.md](information-architecture.md) — 7 sections, route
     assignment, shell contents.
  2. [design-principles.md](design-principles.md) — L1–L4 hierarchy, language rule,
     warning/opportunity templates, density, visual direction.
  3. [semantic-state-system.md](semantic-state-system.md) — canonical semantic tones,
     state domains, full backend-enum → tone/language mapping, subsystem disagreement.
  4. [responsive-contract.md](responsive-contract.md) — one breakpoint scale, 7
     verification widths, containment rules, page-overflow contract.
  5. [component-system.md](component-system.md) — 35 primitives (BUILD/EXTEND/MIGRATE/KEEP),
     token layer, typography, mode-color remap, phantom-class remediation.
  6. [migration-map.md](migration-map.md) — route-by-route map, fragile contracts
     register, redirect/alias plan, per-phase order.
  7. [decision-log.md](decision-log.md) — decisions + rationale + open questions.
  8. Page specs: [pages/](pages/README.md) — [Command](pages/command.md),
     [Radar](pages/radar.md), [Workspace](pages/workspace.md),
     [Portfolio](pages/portfolio.md), [Research](pages/research.md),
     [Lab](pages/lab.md), [Control](pages/control.md).

---

## Base state

- **Worktree:** `C:\Users\adame\Desktop\market-trading-platform-ui-redesign`
- **Branch:** `ui/operator-redesign-v2`
- **Base SHA:** `d588728d60b139ae44b5a3667a8e120d1e21ee1c` (local `main` HEAD; the
  operational runtime build).
- **origin/main** is 3 commits ahead, backend-only: `7aade60b` (FTEP integrity #202),
  `64f1cb42` (corpus validator #199), `3daab7f2` (Finviz validator #195). Zero `ui/` /
  `e2e/` delta — **rebase at integration time**, no mid-program rebase needed.
- **Screenshot ↔ source drift caveat:** the 10 current-UI screenshots in audit 04 were
  captured from the running production build, which **predates this base**. The branch
  already ships a partially redesigned chrome (`ImpProductChrome` sidebar,
  `ModeEnvironmentBar` human boundary sentences). Page bodies match source exactly;
  chrome strings in screenshots (`DEMO REPLAY · READ-ONLY` pill, `Session 6a2f1c…` chip,
  `MARKET OVERVIEW/PULSE/SESSION CONTEXT`, modal command palette) are from the older
  build and **do not exist in source**.
- **Safety constraint:** a live market trading session runs on this machine from a
  different checkout. No dev servers, no npm installs, no e2e runs, no port/process/DB
  touches during planning. UI verification commands (`npm test`, `npm run typecheck`,
  `npm run build`) are for implementation workers when safe; Playwright e2e requires
  real backend ports 8766/8767 and must stay off during trading sessions.
- **Bundle budget:** initial JS ≤ 200 KiB gzip documented / **203 KiB enforced** by
  `ui/scripts/check-bundle-budget.mjs`; last recorded **199.17 KiB** (2026-09-01) →
  **~0.8 KiB headroom**. Lazy chunks ≤ 500 KB raw (`vela-*` ≤ 950 KB, banned from entry
  graph). **All new surfaces MUST stay lazy**; the entry chunk may not grow materially.
  Budget increases require an ADR + budget-script update (`docs/engineering/PERFORMANCE.md`).

## Doctrine summary

1. **Simplify presentation, not truth.** Preserve backend behavior, provenance,
   paper/live safety, and evidence contracts exactly. Never fabricate operational data;
   fixtures only if isolated and unmistakably marked.
2. **Information hierarchy L1→L4.** L1 *what matters now* → L2 *what does it mean* →
   L3 *why does IMP think this* → L4 *technical/audit* (UUIDs, hashes, session IDs,
   fingerprints, raw timestamps, enums — only behind Technical/Audit/Methodology/
   Evidence/Diagnostics disclosure).
3. **Language rule.** Human sentences primary ("Paper trading active", "Market data is
   partially degraded. Some discovery sources are unavailable."); raw enums only inside
   detail surfaces.
4. **Every warning answers:** what happened / what it affects / what to do.
5. **Every opportunity answers:** what is it / why now / what changed / evidence
   strength / freshness / confirms / contradicts / risk / next action. First card shows
   a curated subset; raw features in expanded evidence.
6. **Visual direction.** Near-black/graphite, frosted-glass surfaces, restrained
   borders, warm orange/lava IMP accent, minimal line-art, compact terminal density.
   No generic SaaS, no excessive glow/gradients/rounding. Monospace only for market
   values, identifiers, timestamps, raw evidence.
7. **Semantic state system.** 7 tones: LIVE OBSERVATION = green/teal; PAPER/SIMULATION
   = IMP orange; REPLAY = purple; RESEARCH = blue/slate; DEGRADED/CAUTION = amber;
   BLOCKED/FAILURE/CRITICAL = red; NEUTRAL/HISTORICAL/INFO = graphite. Color is never
   the sole encoder. Semantic tokens, not blind recoloring.
8. **Target IA.** COMMAND, RADAR, WORKSPACE, PORTFOLIO, RESEARCH, LAB, CONTROL —
   see [information-architecture.md](information-architecture.md).
9. **Responsive.** No page-level horizontal scroll at 2560/1920/1600/1440/1366/1280/
   1024; grids may scroll internally; `min-width:0`, ellipsis, copy buttons, detail
   drawers, responsive grids, table containment.
10. **Accessibility.** Landmarks, keyboard nav, visible focus, tab order, accessible
    forms, tooltips not load-bearing, no color-only status, AA contrast, chart text
    summaries, semantic tables.
11. **Performance.** No material slowdown; all new surfaces lazy; restrained animation.

## Audit digest

### Audit 01 — Routes & pages
25 top-level routes + 2 nested research routes; 42 page/route components; 12 nav items
over 11 targets. Decisive findings: **mode is React state, not URL** (reload → mode
launcher); `/` and `/signals` are one component with a `desk` prop; nav "Research" and
"Lab" both target `/research`; nav "Risk" opens the **operator center**, not risk;
paper order submit exists only in the Workspace cockpit and Paper Portfolio with a
current preview; Paper Now drafts ride **`location.state` (PUSH-only, cleared after
read)**; squeeze lane honors `?data_mode=current`; discover fires a **`keepalive`
release POST on unmount**; `laneRegistry.ts` order is a **backend provenance
contract**, not cosmetic; polling cadences (provider health 5s, canary 15s, order-flow/
order-book/market-state 2s live, workspace evidence 5s live) must be preserved.

### Audit 02 — Components & styles
157 TSX modules, ~185 components, 26 global CSS files, 23 tokens. Decisive findings:
**~60 phantom class families** (`.panel`, `.metric-list`, `.status-grid`, `.tone-*`…)
have zero CSS rules — large surfaces render as browser defaults; **9 referenced CSS
vars are undefined** (`--surface-elevated`, `--accent`, `--radius-sm/lg`, `--danger`,
`--muted`, `--color-text-muted`, `--color-border`, `--imp-sidebar-width`); mode colors
conflict with the target semantics in ≥4 places per mode; 3 chart stacks with 3
hardcoded theme sources (blue `#5b8def` accent conflicts with IMP orange); fonts
(Inter/JetBrains Mono) declared but **never loaded**; drawer/inspector fixed
`top: 84px` geometry is **stale** (real top stack ≈205px — drawers overlap the status
bars); ContextBar cannot wrap; 12+ uncontained tables; 3 loading + 6 error idioms;
missing primitives: `CopyableIdentifier`, `ErrorState`, `DegradedState`, `Tooltip`,
real `CommandPalette`. Tests assert on class names — expand `data-testid` hooks.

### Audit 03 — State & data
~80 endpoints, 45 hooks, 44 queryKeys. Decisive findings: **5 incompatible
health/quality vocabularies** (`quality_summary.state` has *two* backend vocabularies,
plus paper `data_health.state`, client ok-sets, discover `data_status`); **triple-sourced
paper authority** (`/context` vs portfolio ledger vs `PaperNowPage`'s stricter check —
they can disagree); **dead derivative preview path** (`canUsePaperActions(..., undefined)`
is fail-closed forever in options/futures product surfaces); **split-brain instrument
selection** (route param vs fire-and-forget backend persistence); `coherence_warning` +
`research_context_execution_authority` on workspace evidence are the backend's existing
"subsystems disagree" anchor; ~30 enum vocabularies rendered raw; fail-closed guards
(preview-required submit, stale-preview block, schema boundary, unknown-category
fail-closed) must be preserved; several raw-fetch surfaces skip auth headers/schema.

### Audit 04 — Screenshots & terminology
10 screenshot analyses (with the drift caveat above), 43-row jargon map, 27 warnings
scored against the 3-question rule — **17 fail, 9 partial, 1 passes**; 18 identifier
exposures (9 with no truncation at all). Top offenses: raw `DATA/EXEC/AUTH` enum bar on
every page; `QUALITY STALE` badge with no cause/impact/action; raw ISO µs timestamps;
session UUID in chrome; RISK nav → IT-ops console; SNAKE_CASE reason chips at L1;
debug-console diagnostics; money in minor units and ns epochs; research vocabulary +
full hashes at L2; bare "X unavailable." dead-ends. Existing strengths to standardize:
`JsonDetailPanel` (correct L4 pattern), Operator Center label/detail/next-action checks
(best 3-question compliance), `ModeEnvironmentBar` human boundary sentences.

### Audit 05 — A11y, responsive, tests & tooling
Decisive findings: **drawer focus gap** (ExplanationDrawer, InspectorPanel,
ImpProviderMatrixDrawer — no focus move/trap/restore) is the top a11y defect; workspace
price chart has **no text alternative**; `--text-muted #6b7280` (~4.0:1) and
`--direction-short #c44e52` (~4.2:1) fail/borderline AA; **9 distinct breakpoint
values** across 12 files; the **901–1100px band** (inline 220px sidebar + 360px drawer
grid column) is the highest-risk range; no a11y/visual/viewport automation (jsdom never
lays out; breakpoints pinned by CSS string assertions); bundle headroom ~0.8 KiB.
Green bar for a UI-only branch: `npm test`, `npm run typecheck`, `npm run build` in
`ui/`, plus `python tools/imp.py lint` and `python tools/imp.py validate changed` at
repo root; `closure` before merge.

## Phase plan

| Phase | Scope | Primary docs | Exit criteria |
|---|---|---|---|
| **1 — Foundation** | Tokens, typography, spacing/density, semantic state system + adapter, AppShell/PrimaryNav/StatusBar, global Loading/Error/Degraded/Empty, CopyableIdentifier, responsive primitives | [component-system.md](component-system.md), [semantic-state-system.md](semantic-state-system.md), [responsive-contract.md](responsive-contract.md) | Token freeze; adapter unit-tested against every enum table; new shell renders all existing routes; bundle ≤ 203 KiB; no route behavior change |
| **2 — Command** | `/` (+ `/signals` redirect) per [pages/command.md](pages/command.md) | page spec | Mode desks consolidated; L1 queue answers 9-fields subset; warnings pass 3-question rule |
| **3 — Radar** | `/radar` + `/radar/screeners`; `/discover`,`/explore` redirects | [pages/radar.md](pages/radar.md) | Discover mutations (refresh/promote/release) preserved; empty states explain WHY |
| **4 — Workspace** | `/workspace/:symbol` + 10 lane tabs | [pages/workspace.md](pages/workspace.md) | Paper cockpit guards intact (preview-required, fail-closed); `location.state` draft handoff preserved; `?data_mode=current` intact; lane registry order untouched |
| **5 — Portfolio** | `/portfolio` per mode | [pages/portfolio.md](pages/portfolio.md) | Session open/close + order history + trace survive; money/time humanized; live view from canary snapshot/reconciliation |
| **6 — Research** | `/research` interpretation-first | [pages/research.md](pages/research.md) | Fingerprints/hashes moved to Methodology disclosure; analytics keep provenance |
| **7 — Lab** | `/lab` real page (Model Lab, Simulation, Chart Lab); `/research/vela-chart-lab` redirect | [pages/lab.md](pages/lab.md) | Dense but legible; no backend change (still `/research/*` endpoints) |
| **8 — Control** | `/control` + Providers/Canary/Settings sub-pages | [pages/control.md](pages/control.md) | Provider health matrix state/provides/impact; read-only canary invariant; ContextBar→diagnostics deep link retargeted |
| **9 — Responsive/a11y pass** | 7-width sweep, keyboard sweep, chart text alternatives, contrast verification | [responsive-contract.md](responsive-contract.md) | No page-level horizontal scroll at any verification width; axe clean on new primitives |

Phases 2–8 each end with: `App.test.tsx` updated (route/nav obligation), `npm test`,
`npm run typecheck`, `npm run build` (budget), and diff review against
[migration-map.md](migration-map.md) parity risks.

## Foundation implementation plan

Strictly ordered; each step lands green (tests + typecheck + build) before the next:

1. **Design tokens** — freeze palette in `ui/src/styles/tokens.css`: define the 9
   undefined vars (as aliases to real tokens), fix `--text-muted` and
   `--direction-short` to AA, add spacing scale, radii, type scale, layout constants,
   and the 7×3 semantic state tokens (`--imp-state-{tone}-{fg|bg|border}`). Add
   stylelint (or a vitest CSS audit) guard against unknown custom properties.
2. **Typography** — deliberate system-stack decision (no webfont download; see
   [component-system.md](component-system.md#typography-plan)); replace ad-hoc sizes
   and fluid clamp H1s with the type scale; restrict `--font-mono` to market
   values/identifiers/timestamps/raw evidence; drop weights 680/750 → 600/700.
3. **Spacing/density** — adopt `--imp-space-*` in shell + one pilot page; define
   compact/comfortable density modifiers for DataTable/MetricGroup.
4. **Semantic status system** — author the tone tokens' usage CSS (pills, badges,
   banners, borders, icons) with text/icon pairing (never color-only).
5. **Canonical UI state adapter** — new pure module `ui/src/state/semanticState.ts`:
   `resolveSemanticState(domain, rawValue)` → `{ tone, label, sentence, affects?,
   action? }` covering every enum table in
   [semantic-state-system.md](semantic-state-system.md); unit-test every mapped value
   plus unknown-value fallback (neutral, never invent).
6. **App shell / nav / status bar** — EXTEND `ImpProductChrome` → AppShell; EXTEND
   `NavShell` → PrimaryNav (7 sections, resolve Research/Lab duplicate, rename
   Risk→Control); BUILD the unified `StatusBar` (consolidates `ModeEnvironmentBar` +
   `ContextBar` + `ImpCapabilityStrip` into one 40px bar + popover details); fix the
   duplicate `<header>` banner landmarks; recompute drawer geometry (kill `top: 84px`).
7. **Global loading/error/degraded patterns** — one `LoadingState`, one `ErrorState`,
   one `DegradedState`, one `EmptyState`; migrate the 3 loading + 6 error idioms;
   `AttentionBanner` (severity-graded, 3-question slots).
8. **Identifier handling** — BUILD `CopyableIdentifier` (truncate-middle + copy +
   full value in TechnicalDetails); audit every ID render site from audit 04's
   18-row exposure list.
9. **Responsive primitives** — one breakpoint scale (`720/1024/1440`), `Drawer`
   overlay behavior, `DataTable` containment pattern (from `paper-portfolio.css`),
   page-overflow guard; fix the 901–1100px band.
10. **Command page** — first page implementation ([pages/command.md](pages/command.md)),
    proving the full stack end-to-end before the remaining page phases.

**Bundle-budget lazy-loading constraint (binding):** the entry chunk has ~0.8 KiB
headroom against the 203 KiB enforced budget. All new page surfaces and all new
primitives beyond the shell must load lazily (`React.lazy` + `LazyBoundary`, shared
chunks via Vite `manualChunks` where needed); the adapter and tokens are pure
CSS/TS and must be near-zero-cost on the entry path. If a step would grow the entry
chunk materially, split it before landing. Budget increases require an ADR.
