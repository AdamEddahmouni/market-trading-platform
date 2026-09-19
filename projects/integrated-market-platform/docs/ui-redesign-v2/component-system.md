# Component System

The component plan for the redesign. Dispositions use audit 02's coverage map
(EXISTS-GOOD 5 / EXISTS-NEEDS-WORK 25 / MISSING 4):

- **BUILD** — no meaningful implementation exists; new component.
- **EXTEND** — an existing component is the base; it gains API/styling and keeps its
  name where possible.
- **MIGRATE** — no single source component; consolidate scattered idioms into the
  named primitive and delete the idioms.
- **KEEP** — use as-is (restyle only).

New primitives live in `ui/src/components/imp-ui/` (lazy-loaded shared chunk(s));
existing components keep their paths until their page phase migrates them. All
interactive/status primitives ship `data-testid` hooks (see §5).

---

## 1. Primitive disposition table (35)

| # | Primitive | Disposition | Base / source (audit 02 refs) | Notes |
|---|---|---|---|---|
| 1 | `AppShell` | EXTEND | `imp-product/ImpProductChrome.tsx:26` + `WorkstationShell` (`App.tsx:186`) | Keep skip link, focus trap, inert management. Remove vestigial `.app-shell` grid; recompute drawer offsets (responsive-contract §3); add page-overflow guard. |
| 2 | `PrimaryNav` | EXTEND | `NavShell.tsx:139` | 7 sections (Command/Radar/Workspace/Portfolio/Research/Lab/Control); resolve Research/Lab duplicate target; rename Risk→Control; remove GATED badge; keep per-mode hints + `aria-label`s. |
| 3 | `StatusBar` | BUILD | consolidates `ModeEnvironmentBar.tsx:17`, `ContextBar.tsx:26`, `ImpCapabilityStrip.tsx:8` | One 40px bar: ModeBadge + execution authority + data health + freshness + session status + selected instrument + disagreement indicator; L4 details popover hosts raw triple, capability matrix, raw timestamps. Fixes ContextBar no-wrap overflow and duplicate `<header>` landmarks. |
| 4 | `ModeBadge` | BUILD | text today in `ImpExecutionPosture.tsx:14`, environment bar, per-page eyebrows | Dedicated badge: tone + human sentence per mode (`resolveSemanticState("mode", …)`). Replaces all eyebrow idioms. |
| 5 | `SystemHealth` | BUILD | quality badge in `ContextBar.tsx:58-62`, `StartupRecoveryBanner`, `LiveSafetySnapshot` | Single aggregate: `/context quality_summary` + provider health + crash recovery → one indicator + sentence; click → `/diagnostics/provider`. Aggregation rule: worst-of, ties broken toward caution; never hides a critical. |
| 6 | `ProviderHealth` | EXTEND | `ImpCapabilityStrip` + `ImpProviderMatrixDrawer.tsx:12` | Consolidates 4 overlapping implementations (panel page, live ribbon, discover dots, capability strip) into one chip-strip + matrix drawer; the `/diagnostics/provider` page reuses the matrix. |
| 7 | `AttentionBanner` | BUILD | idiom from `OpportunityFeedStatusBanner.tsx:16`, `.startup-recovery-banner`, `.mode-restriction-note` | Severity-graded (`tone` prop), 3-question content slots (what/affects/action), optional action link/button. Replaces all banner idioms. |
| 8 | `OpportunityCard` | KEEP | `ProgressiveOpportunityCard.tsx:66` (+ `CompactOpportunityCard` `ImpTopOpportunityCards.tsx:21`) | Strong domain model; restyle to tokens; wire ConfidenceIndicator/FreshnessIndicator/ContradictionPanel; enforce the 9-field content rule (design-principles §4). |
| 9 | `OpportunityScore` | BUILD | text-only today (`ATTN n`, `#rank`) | Visual score: numeric + band label + tone; raw ranking vector in expanded evidence. |
| 10 | `FreshnessIndicator` | BUILD | raw text today (`freshness_label`, `{ms} ms`, stale notes) | Relative time + tone by cadence table (semantic-state-system §6); raw timestamp in TechnicalDetails. |
| 11 | `ConfidenceIndicator` | BUILD | raw text today (`confidence {value}`) | Low/Medium/High bands + numeric in tooltip/details. |
| 12 | `EvidenceStack` | EXTEND | `.reason-codes` (`layout.css:308-316`), `CrossLaneEvidenceBlock.tsx:8`, discover evidence popover (`DiscoverObservability.tsx:475-494`) | Unified per-source evidence list: source, claim, agreement, freshness. Popover becomes portal-based. |
| 13 | `EvidenceSource` | EXTEND | `.source-badge`/`.data-status-pill` (`layout.css:1421-1430,1456-1470`), `ChartProvenance.tsx:6`, `PaperDecisionProvenanceBadge.tsx:7` | One source/provenance pill (3 idioms → 1): label + tone + optional freshness. |
| 14 | `ContradictionPanel` | EXTEND | `PaperDecisionSnapshot.tsx:77-96`, `ProgressiveOpportunityCard.tsx:156-158` | Adds severity + per-side humanized claims; also hosts subsystem-disagreement content (semantic-state-system §4). |
| 15 | `RiskSummary` | KEEP | `PaperRiskRibbon.tsx:6` (`role="meter"`), `PaperRiskContext.tsx:6` | Generalize beyond paper-now; keep meter semantics; token restyle. |
| 16 | `PositionRow` | BUILD | plain `<tr>`s today (`PaperPortfolioObservability.tsx:117-128`, `LivePortfolioPage.tsx:90-96`) | Symbol, qty, avg, mark + `FreshnessIndicator`, P&L (direction tokens), CopyableIdentifier where IDs appear. |
| 17 | `OrderRow` | KEEP | `PaperOrderHistoryRow.tsx:103,13` | Expandable row + status pill + provenance badge is the model; extend to live broker orders (`LivePortfolioPage.tsx:116-121`). |
| 18 | `Metric` | BUILD | raw `<dl>` idiom everywhere; `.metric-list` unstyled | Label + value + optional detail/trend + tone; mono only for market values. |
| 19 | `MetricGroup` | BUILD | CSS-only grids (`.metric-grid`, `.demo-metric-grid`, `.live-safety-grid`) | Responsive auto-fit grid of Metric with consistent label/value/detail structure. |
| 20 | `ChartFrame` | EXTEND | `.chart-panel` + `ChartEmptyState.tsx:5` + `ChartProvenance.tsx:6` | One frame wrapping all 3 chart libs: title, state slots (loading/empty/error), provenance caption, **mandatory text summary** (a11y). |
| 21 | `EmptyState` | EXTEND + MIGRATE adopters | `shared/EmptyState.tsx:10` (1 use today) | Gains reason/action slots ("why empty" is mandatory on Radar); migrate all ad-hoc empties (`.discover-empty`, `.chart-empty`, muted paragraphs…). |
| 22 | `LoadingState` | KEEP + MIGRATE adopters | `shared/LoadingState.tsx:6` (~9 uses vs ~30 ad hoc) | One loading idiom; delete `<p role="status">Loading…</p>` and bare `.app-loading` variants; add skeleton variant for tables/cards. |
| 23 | `DegradedState` | BUILD | scattered (provider dots, data-status pills, stale notes) | Inline degraded surface: tone=caution + 3-question content + link to details. |
| 24 | `ErrorState` | BUILD | 6+ idioms (`role="alert"` paragraphs, `.capability-panel.unavailable`, `.order-ticket-error`, `.discover-error`, `.paper-cockpit-warning`, unstyled `.error`) | One error surface: humanized category sentence + affects + retry/action; raw `category: reason_code` in TechnicalDetails. |
| 25 | `TechnicalDetails` | KEEP | `shared/JsonDetailPanel.tsx:33` | The L4 pattern; enforce default-collapsed everywhere (S9's expanded JSON wall is the anti-pattern); add copy-value per row. |
| 26 | `CopyableIdentifier` | BUILD | none (zero clipboard usage; 4 `slice()…` sites) | Truncate-middle + copy button + full value in details; audit all 18 exposure sites (audit 04). |
| 27 | `PageHeader` | EXTEND + MIGRATE adopters | `shared/PageHeader.tsx:13` (3 uses vs ~15 hand-rolled) | Eyebrow/title/subtitle/meta/actions; migrate every hand-rolled page header. |
| 28 | `SectionHeader` | BUILD | unstyled `.panel-header`/`.panel-actions` idiom | Section title + actions + optional tone; gives lane panels real headers. |
| 29 | `FilterBar` | EXTEND | `PaperOrderHistoryTable.tsx:49-94` filters, `.discover-controls` | Shared labeled filter row; wraps at `BP_SM`; selects get `min-width: 0`. |
| 30 | `DataTable` | EXTEND + MIGRATE | `.data-table` CSS (`layout.css:975-986`) → component | Scroll wrapper + min-width + column-hide pattern (responsive-contract §4.3); sticky header; `scope="col"` + caption required; migrate the 20 uncontained tables. |
| 31 | `Drawer` | BUILD | consolidate `.drawer`, `.inspector-panel`, `.evidence-drawer`, `.assistant-sidecar` (4 overlay idioms + in-flow trace panel) | One primitive on `lib/useFocusTrap.ts` + `LiveModeConfirmation` pattern: focus move/trap/restore, Esc, backdrop option, overlay geometry per responsive-contract §3. |
| 32 | `Modal` | EXTEND | `LiveModeConfirmation.tsx:10`, `ImpKeyboardShortcuts.tsx:17` | Generalize the two solid implementations into one exported Modal. |
| 33 | `Tabs` | BUILD | 4 idioms (`.research-tabs`, `.inspector-tabs`, `.imp-overview-queue-filters`, `.discover-mode-switch`) | Full ARIA tabs pattern (arrow keys, `aria-controls`/`aria-labelledby` — fixes InspectorPanel gaps); routable variant for lane/section tabs. |
| 34 | `Tooltip` | BUILD | none (native `title=` only) | Non-load-bearing only; keyboard/touch accessible; content duplicates visible text or is non-essential. |
| 35 | `CommandPalette` | EXTEND | `ImpCommandSearch.tsx:12` | Real palette: nav actions, mode actions, instrument search (`instrumentSearch` query), recent instruments; fixes the dead `/explore?q=` fallback (routes to `/radar/screeners?q=` with the query actually read). Restores the command discoverability the old modal palette had (audit 04 S3). |

## 2. Token layer design

All tokens in `ui/src/styles/tokens.css` (single `:root`), frozen by a guard test.

**Fix the 9 undefined vars** (audit 02 §3) — define as aliases to real tokens so old
callers heal automatically:

| Undefined today | Definition |
|---|---|
| `--surface-elevated` | `#20262f` (new, above `--surface-2`) |
| `--accent` | `var(--accent-primary)` |
| `--radius-sm` | `var(--imp-radius-sm)` |
| `--radius-lg` | `var(--imp-radius-lg)` |
| `--danger` | `var(--imp-state-critical-fg)` |
| `--muted` | `var(--text-muted)` |
| `--color-text-muted` | `var(--text-muted)` |
| `--color-border` | `var(--border-subtle)` |
| `--imp-sidebar-width` | `220px` |

**Contrast fixes (AA, verify with tooling):**
- `--text-muted: #6b7280` (≈4.0:1 — fails) → **`#8b94a5`** (target ≈4.6:1 on
  `--surface-0`, ≥4.5:1 on `--surface-1`).
- `--direction-short: #c44e52` (≈4.2:1 — borderline) → **`#d96368`** (target ≥4.5:1).
- `--mode-muted: #7a8494` (≈4.3:1) → alias to the fixed `--text-muted`.

**New token groups:**
- Semantic state: `--imp-state-{live|paper|replay|research|caution|critical|neutral}-{fg|bg|border}`
  (21 tokens; values in semantic-state-system §1).
- Spacing: `--imp-space-1..6` = `4 / 8 / 12 / 16 / 24 / 32px`.
- Radii: `--imp-radius-sm 4px` / `--imp-radius-md 6px` / `--imp-radius-lg 10px`.
- Type scale: `--imp-text-micro 0.6875rem` (11px floor) / `-xs 0.75rem` /
  `-sm 0.8125rem` / `-md 0.875rem` / `-lg 1rem` / `-xl 1.25rem` / `-display 1.75rem`.
- Layout: `--imp-topbar-height 48px`, `--imp-statusbar-height 40px`,
  `--imp-drawer-width 360px` (overlay, `min(420px, 100vw)` actual),
  `--imp-sidebar-width 220px` (now really defined), breakpoints documented
  (`720/1024/1440`, see responsive-contract).
- Chart: `--imp-chart-accent: var(--accent-primary)`, `--imp-chart-up/down` =
  direction tokens, grid/text from surface/text tokens.

**Palette freeze:** the 4 ambers and 5 reds (audit 02 observations #4) collapse into
`--imp-state-caution-*` / `--imp-state-critical-*`; scattered one-off hexes
(`#7dd3fc`, `#7eb8ff`, `#8fd48f`, `#f0a070`, `#8ce7da`, `#9fd4ff`…) are replaced by
state/direction tokens as their pages migrate. Guard: a vitest CSS audit fails on any
hex literal in `ui/src/styles/**` outside tokens.css and on any `var(--…)` name not
defined in tokens.css (catches the undefined-var class of bug permanently).

**Chart theme unification:** one module `ui/src/components/charts/chartTokens.ts`
(reads getComputedStyle once, falls back to token hexes) feeding all three chart
stacks — replaces hardcoded hexes in `chartTheme.ts:1-9` (blue `#5b8def` accent →
IMP orange), `impVelaTheme.ts:5-12`, `WorkspacePriceChart.tsx:49-58` (`#141820`
background → `--surface-1`), `ResearchChartPanels.tsx:54-58,127-131`.

## 3. Typography plan

**Decision: deliberate system stack — no webfonts.** Inter/JetBrains Mono are
declared but never loaded (`index.html` has no font links; audit 02 typography), so
production already renders system fonts; self-hosting would cost ~100+ KiB against a
0.8 KiB entry headroom and complicate the offline operator workstation. Therefore:

- `--font-ui: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`
- `--font-mono: ui-monospace, "Cascadia Mono", "JetBrains Mono", Consolas, monospace`
  (JetBrains Mono kept mid-stack for machines that have it)
- Weights: 400/500/600/700 only — non-standard 680/750 (`mode-session.css:89,377`,
  `demo-now.css:196`) map to 600/700.
- Sizes come from the `--imp-text-*` scale; fluid clamp H1s
  (`clamp(2.35rem, 6vw, 5.4rem)` etc.) are replaced by fixed scale steps.
- Mono discipline per doctrine: market values, identifiers, timestamps, raw evidence
  **only**. Mono eyebrows/labels (`.demo-eyebrow`, `.paper-eyebrow`, `.live-eyebrow`,
  `.imp-section-eyebrow`, nav hints, KPI labels) migrate to `--font-ui` +
  letter-spaced uppercase at `--imp-text-micro/xs`.
- The `.mono` utility class gets a real rule (currently phantom — hashes in
  `ModelLabPanel.tsx:32,36` render in sans).

## 4. Mode-color remap plan

Target semantics (semantic-state-system §1) vs current (audit 02 mode-conflict table):

| Mode | From (current) | To (target tone) |
|---|---|---|
| Paper / simulation | teal `#48d6c4` pages, green `#56c596` launcher, green `#5cc48a` header accents | **`paper` = IMP orange** (`--imp-state-paper-*`) |
| Live observation | amber `#f0b45c` pages, orange `#ff8a00` launcher | **`live` = green/teal** (`--imp-state-live-*`) |
| Demo / replay | cyan `#67d8f4` pages, slate `#9aa8b8` launcher, amber replay tint | **`replay` = purple** (`--imp-state-replay-*`) |
| Research accents | blue `#5b8def`/`#7eb8ff` scattered | **`research` = blue/slate** (`--imp-state-research-*`) |

**Every per-mode palette location to migrate** (audit 02 inventory — flag list):
`mode-session.css:1-12` (`--mode-demo/paper/live`), `demo-now.css:1-6`,
`paper-now.css:1-5`, `live-now.css:1-5`, `paper-portfolio.css:1-4`,
`paper-workspace.css:1-4`, `live-portfolio.css:1-4`, `live-workspace.css:1-4`,
`demo-workspace.css:1-4` (+ remaining `demo-*`/`paper-*`/`live-*` page files),
`paper-explore.css:12,33` + paper discover/research header hexes,
`live-explore.css:12` + live discover/research header hexes,
`mode-session.css:200-283` (environment bar hardcodes), `layout.css:1024`
(`.context-segment.mode-live strong #3dd68c`), `layout.css:1046-1052`
(relevance hexes), `workspace-module-mode.css:125-131` (lane decision hints),
`paper-workspace.css:82,135-160` (cockpit warning + handoff blue),
`operator-control.css:26-29,34,105-124,228` (operator blues + status texts),
`paper-portfolio.css:91,111-124` (provenance teal, order statuses),
`chartTheme.ts`, `impVelaTheme.ts`, `WorkspacePriceChart.tsx:49-58`,
`ResearchChartPanels.tsx:54-58,127-131`, `tokens.css --replay-bg`.

**Migration method:** each page-scoped var (`--paper-accent`, `--live-accent`,
`--demo-accent`, `--mode-*`) becomes an alias to the semantic token in one commit,
then usages are replaced by the semantic token directly and the alias deleted. No
blind find-replace of hexes — tone assignment follows the semantic tables, and every
recolored status keeps/gains a text or icon pair.

## 5. Phantom-class remediation strategy

~60 class families in JSX have zero CSS rules (`.panel`, `.metric-list`,
`.status-grid`, `.instrument-selector*`, `.tone-*`… — audit 02 §2). Strategy:

1. **Define the real primitives** (§1) with their own scoped classes
   (`imp-ui-*` prefix) — never resurrect the phantom names.
2. **Adopt per page phase** (phases 2–8): as each page migrates, phantom classes are
   deleted from its JSX and replaced by primitives. A page is "done" only when its
   phantom-class count is zero (grep checklist per page).
3. **Test safety:** existing tests assert on class names and copy
   (`WorkspaceModuleNav.sticky.test.tsx`, `ImpProductChrome.test.tsx`,
   `App.test.tsx`, `smoke/appShell.smoke.test.ts`). Therefore: **expand
   `data-testid` hooks first** (every new primitive and every migrated status/
   interactive element gets one, following the existing
   `workspace-mode-restriction-note` / `live-canary-control-plane` pattern), migrate
   assertions to `data-testid`/role queries, then rename classes. Class renames and
   test updates land in the same PR.
4. **Guard:** add a vitest "no phantom classes" audit — JSX `className` tokens
   (excluding `imp-ui-*`, `data-*`, and test hooks) must exist in some CSS file;
   starts as an allowlist of today's phantoms that only shrinks.

## 6. Loading / error / empty / degraded consolidation

| Idiom | Today (audit 02 state-patterns) | Target |
|---|---|---|
| Loading | 3 idioms: shared `LoadingState`, bare `.app-loading` divs, `<p role="status">` | **One** `LoadingState` (+ skeleton variant for tables/cards); ~30 ad-hoc usages migrate |
| Error | 6+ idioms (`role="alert"` paragraphs, `.capability-panel.unavailable`, `.order-ticket-error`, `.discover-error`, `.paper-cockpit-warning`, unstyled `.error`) | **One** `ErrorState`: humanized category + affects + retry; raw envelope in TechnicalDetails |
| Empty | `EmptyState` used once; ~10 ad-hoc idioms | **One** `EmptyState` with mandatory reason (+action when one exists) |
| Degraded | no primitive; 5+ scattered signals | **One** `DegradedState` (tone=caution, 3-question content) |

All four keep the app's good a11y habits: `role="status"`/`role="alert"`,
`aria-live` where content updates asynchronously.

## 7. Bundle & performance budget

- Entry budget: **203 KiB gzip enforced / 199.17 KiB recorded → ~0.8 KiB headroom.**
  The `imp-ui` primitive library loads as a **lazy shared chunk** imported by lazy
  pages; the shell (AppShell/PrimaryNav/StatusBar) must stay near-zero-added-weight
  (restyle + consolidation of existing chrome, not new dependencies).
- No new runtime dependencies without an ADR. No icon library (inline SVG line-art
  only). No webfonts (§3).
- `recharts` stays out of the entry chunk (existing manualChunks); new chart work
  reuses existing libraries.
- Animations: ≤ 200ms transforms/opacity only, `prefers-reduced-motion` cutoffs
  required (existing pattern — keep).
- Memoization stays query-key-driven; add `useMemo` only where profiling shows need
  (current sparse usage is fine).
