# Decision Log

Every significant planning decision, with rationale and rejected alternatives.
Defaults are chosen so implementation is never blocked; items marked **→ USER** are
the ones that genuinely need the program owner (see §3).

---

## 1. Decisions (final unless reopened)

### D1 — Mode stays session-scoped React state (not in URL)
Today `selectedMode` is `useState` in `ApplicationBootstrap.tsx:28`; reload returns to
the mode launcher. **Decision: keep.** Rationale: mode is a safety boundary, not
navigation state; a URL that says `/live` cannot grant authority, and encoding mode in
URLs invites false confidence + shared-link confusion. The StatusBar's ModeBadge makes
mode unmissable instead. Rejected: `?mode=` param or `/paper/...` path prefix
(deep-linkable mode) — convenience, but weakens the deliberate-entry doctrine
(Live requires `LiveModeConfirmation`). See Q1.

### D2 — One StatusBar replaces the three stacked bars
`ModeEnvironmentBar` (76px) + `ContextBar` (40px) + `ImpCapabilityStrip` (32px) +
top bar ≈ 205px of stacked chrome, with raw enums at L1 (audit 04 offense #1) and a
stale 84px drawer offset (audit 02 §D6). **Decision:** one 40px StatusBar (ModeBadge,
execution authority, data health + freshness, session status, selected instrument,
disagreement indicator) + details popover for L4. Rationale: L1 compression is the
single highest-leverage change; fixes overflow (ContextBar can't wrap), landmark
duplication (two `<header>`s), and drawer geometry in one move. Rejected: restyling
the three bars in place (keeps 148px of chrome and three vocabularies).

### D3 — Seven semantic tones, one adapter
`SemanticTone = live | paper | replay | research | caution | critical | neutral`, all
rendering via `resolveSemanticState(domain, raw)`. Rationale: five incompatible
health vocabularies (audit 03) cannot be fixed per-component; a pure, unit-tested
adapter is the only enforceable rule. Rejected: per-component tone maps (today's
duplicated ok-sets — the drift source); a 5-tone system (cannot express replay vs
research vs neutral distinctly enough for this product).

### D4 — Paper = IMP orange, Live = green/teal, Replay = purple (token-level remap)
Per doctrine. Current paper-teal/live-amber/demo-cyan conflicts are remapped at the
token layer (component-system §4 flag list), never by hex find-replace. Rationale:
mode color is declared in ≥4 places per mode today; only aliasing through semantic
tokens prevents half-migrated states. Rejected: keeping current colors (fails the
doctrine and leaves paper/live semantically inverted vs convention).

### D5 — System font stack, no webfonts
Inter/JetBrains Mono are declared but never loaded; entry headroom is 0.8 KiB.
**Decision:** system-ui + ui-monospace stacks; weights 400–700; type scale tokens.
Rejected: self-hosting Inter + JetBrains Mono (~100+ KiB, blows budget, offline
packaging burden for a workstation app). Revisit only with an ADR + budget increase.

### D6 — Strategy profitability's single home is PORTFOLIO (Attribution)
Today it lives in both Paper Research and Paper Portfolio
(`PaperResearchPage.tsx:19`, `PaperPortfolioPage.tsx:13`). **Decision:** PORTFOLIO
"Attribution" tab is the home (it is per-strategy P&L lineage — portfolio doctrine:
attribution); Research keeps a cross-link. The `paperStrategyProfitability` query and
its key scoping are unchanged. Rejected: keep both (split-brain); Research home
(research ≠ P&L attribution).

### D7 — LAB is a presentation split of `/research/*`, no new backend
`/lab` becomes a real page hosting Model Lab (`researchModels`), Simulation
(`researchSimulation`), and Chart Lab (synthetic). **Decision:** move the surfaces,
keep the endpoints. Rationale: zero backend invention; the Research/Lab conflation
(nav duplicate, `/lab` redirect) is a UI-level bug. See Q2.

### D8 — Research/Lab tabs become routable
Today's tabs are local `useState` (`ResearchObservability.tsx:17`). **Decision:** LAB
tabs are subroutes (`/lab`, `/lab/simulation`, `/lab/chart-lab`); RESEARCH is a
single-panel page after the split. Accepted behavior change: back button now walks
tab history. Rationale: deep-linkable lab surfaces are worth it; the old in-page tab
state had no deep links at all.

### D9 — RADAR absorbs Explore as the Screeners tab
`/explore` → `/radar/screeners`; `/discover` → `/radar`. Rationale: doctrine's
canonical discovery queue (find→rank→filter→compare→investigate) — screener bridges
are the "find" inputs. Rejected: keep `/explore` as a sibling page (perpetuates two
discovery homes and the Markets/Explore label mismatch).

### D10 — Paper-draft handoff: preserve + formalize `location.state`
See migration-map C1. Rejected: URL params (not shareable intent), backend-persisted
drafts (new backend capability — out of scope).

### D11 — Paper submit consolidates to the Workspace cockpit
Today submit is possible from the Workspace cockpit **and** Paper Portfolio
(`OrderTicket` in both). **Decision:** the order ticket lives only in WORKSPACE;
PORTFOLIO keeps session lifecycle, order history/cancel-paths, and gets an
"Open in Workspace" handoff CTA. Rationale: one construction surface = one guard
path; doctrine's WORKSPACE is the decision cockpit (understand→verify→construct→
risk-check→simulate); matches the program's stated safety contract ("Paper submit
only from Workspace cockpit with current preview"). **Parity risk is real** (Portfolio
submit removed) — flagged → USER in Q7. Default if unanswered: proceed with
consolidation, since the cockpit is strictly safer and one click away.

### D12 — Lane registry order untouched; presentational order separate
`laneRegistry.ts` is a backend provenance contract. Lane Tabs display order comes
from a new `LANE_NAV_ORDER` map (operator priority: Overview, Squeeze, Order Flow,
Order Book, Options, Futures, Catalyst, Large Transactions, Institutional Flow,
Disclosure, Fund/ETF). Rejected: reorder the registry (breaks a documented
cross-boundary contract).

### D13 — Breakpoint scale 720 / 1024 / 1440
See responsive-contract §1. Rejected: keep 900px sidebar breakpoint (leaves the
901–1100px tight band); a 4-value scale (more churn, no observed need).

### D14 — Drawers become overlays at all widths
Fixes the stale `top: 84px` geometry and the 360px-grid-column squeeze. Drawer width
`min(420px, 100vw)`, `top` derived from `--imp-topbar-height + --imp-statusbar-height`
tokens. Rejected: keep grid-column drawers ≥1440px (two geometry systems to
maintain; overlay is uniform and simpler).

### D15 — GATED badge removed from Research nav
No gate logic exists in the UI (audit 01 unknowns) — the badge is copy-only.
**Decision:** remove. If a real entitlement exists backend-side, it must arrive as
data before any badge returns. See Q3.

### D16 — CommandPalette replaces ticker-only search; `?q=` gets wired
`ImpCommandSearch` non-ticker fallback lands on `/explore?q=` which nothing reads
(grep-verified dead). **Decision:** CommandPalette routes text queries to
`/radar/screeners?q=…`, and the Screeners tab reads `q` to pre-filter; instrument
queries hit `instrumentSearch`. This also restores the command discoverability the
old modal palette had (audit 04 S3 regression note). See Q4.

### D17 — Assistant conversation resume added
The sidecar creates a **new** conversation every open (`App.tsx:245-255`);
`/assistant/history` is the only list. **Decision:** history rows gain "Resume in
assistant" which opens the sidecar on the existing conversation id. Small, additive,
no backend change (messages endpoint already takes a conversation id). See Q5.

### D18 — Subsystem disagreement anchors on backend `coherence_warning`
Plus `research_context_execution_authority`, plus client-detected mode/authority
divergence presented as disagreement (never silently resolved). Strictest source
gates mutations. See semantic-state-system §4. Rejected: picking `/context` as the
single winner and hiding the ledger source (hides real split-brain, audit 03 #1).

### D19 — `data-testid`-first test migration
Tests assert on class names today. **Decision:** expand `data-testid` hooks on all
new/migrated primitives, migrate assertions, then rename classes — same PR per page.
Rejected: big-bang class rename (breaks ~50 integration tests at once).

### D20 — Raw-fetch surfaces documented, not hardened in this program
Discover/canary/settings/startup/assistant POSTs skip auth headers and zod (audit 03
#9). **Decision:** the redesign re-presents these surfaces but does not change their
transport; a follow-up hardening task wraps them in `fetchJson`/`postJson` (recorded
as technical debt, not silently fixed mid-redesign). Rationale: scope control +
behavior preservation; touching transport under enforced auth risks 401 regressions
that need a live backend to verify — impossible during trading sessions.

## 2. Open questions (with recommended defaults — implementation not blocked)

| # | Question | Recommended default | Needs |
|---|---|---|---|
| Q1 | Should mode become URL-visible (`?mode=`)? | **No** (D1) — keep session-scoped; revisit after v2 ships | **→ USER** (doctrine-level) |
| Q2 | Will backend ever differentiate RESEARCH vs LAB beyond `/research/*`? | **No new endpoints** — LAB is a presentation split (D7); if backend later splits, routes already isolate the change | **→ USER** (product direction) |
| Q3 | Does nav "GATED" map to a real entitlement? | **Remove badge** (D15); restore only if entitlement data arrives | **→ USER** (no gate logic found in UI) |
| Q4 | Is `/explore?q=` search planned backend functionality? | **Wire client-side** (D16): Screeners tab reads `q` as a filter; no backend assumption | Default sufficient |
| Q5 | Is assistant conversation resume a supported flow? | **Yes, client-side** (D17): sidecar opens existing conversation id; messages endpoint already supports it | Default sufficient |
| Q6 | Is the backend enum inventory complete? (capability states, order states beyond terminal set, lifecycle_state, session.status, market_session, mode_label, mark_quality from live quotes) | **Adapter unknown-value rule** (neutral + raw in details + dev warning) covers gaps; schedule a backend enum inventory task to complete the mapping tables | Default sufficient; inventory task recommended |
| Q7 | Confirm removing Paper Portfolio's in-page order submit (D11) | **Proceed** — cockpit-only submit; Portfolio gets "Open in Workspace" handoff | **→ USER** (visible behavior change) |
| Q8 | Dead derivative preview path (`canUsePaperActions(..., undefined)` in options/futures product surfaces — fail-closed forever): intended or bug? | **Preserve as-is** (fail-closed is safe); do not "fix" without backend/product confirmation — if intended, add copy "Derivative paper preview is not available in this build" | **→ USER** (possible latent bug) |
| Q9 | `usePaperStrategyProfitabilityQuery` key embeds account/session but sends no params (`hooks.ts:290-298`) — key implies isolation the request doesn't have | **Leave transport; document**; when backend accepts params, wire them (no UI blocker) | Default sufficient |
| Q10 | Should the StatusBar health click keep targeting `/diagnostics/provider`? | **Yes** (route kept under Control) | Default sufficient |

## 3. What genuinely needs the user

Only **Q1** (mode-in-URL doctrine), **Q2** (Research/Lab backend direction), **Q3**
(GATED entitlement), **Q7** (Portfolio submit removal), **Q8** (derivative preview:
bug or intended?). Everything else has a safe default recorded above. None block
Phase 1; Q7 lands in Phase 5, Q8 surfaces in Phase 4 copy.

## 4. Contradictions found in the audits (and resolutions)

1. **Audit 01 vs audit 03 on paper submit surfaces.** Audit 01's mode-routing section
   says submit is possible from Workspace cockpit *and* Paper Portfolio; the program
   doctrine says "Paper submit only from Workspace cockpit". Resolution: D11 —
   consolidate to Workspace, flag to user (Q7).
2. **Audit 04 screenshot chrome vs source.** Screenshots show a modal command palette
   and session chip that no longer exist in source (drift caveat). Resolution: plan
   against **source**, treat screenshot-only chrome as historical; the palette
   regression is real and addressed by D16.
3. **Audit 03 dual query-key systems.** `queryKeyFactory.ts` exists but is unused and
   incompatible with `hooks.ts` keys. Resolution: redesign standardizes on
   `hooks.ts` `queryKeys` (the live system); the factory is out of scope but flagged
   as deletion/hardening debt (D20-adjacent).
4. **Health vocabulary count differs between audits** ("4 vocabularies on one screen"
   vs "5 incompatible"). Resolution: the mapping tables in semantic-state-system §3
   cover the full union (both `quality_summary` vocabularies, portfolio `data_health`,
   client ok-sets, discover `data_status`, lane quality) — count doesn't matter,
   coverage does.
5. **Budget: 200 KiB documented vs 203 KiB enforced.** Resolution: plan against the
   stricter practical constraint — recorded 199.17 KiB vs 203 KiB enforced ≈ 0.8 KiB
   documented headroom; treat 200 KiB as the design target (README, C7).
