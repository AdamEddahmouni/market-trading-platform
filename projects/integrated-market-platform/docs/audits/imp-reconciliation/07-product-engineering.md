# 07 — Product Surface, Frontend, API, Testing, Developer-System, Documentation, Dependency, Performance, and Repository Audit (WS06)

Status: **COMPLETE (WS06, 2026-09-07)**. Final broad audit before WS07 master
reconciliation. Canonical inputs: WS01–WS05 files (01–06, 08–11, 14–15);
canonical IMP tree at `projects/integrated-market-platform/` (parent
`hardening/sprint-1-3-honesty` @ `d691050`). No code was changed. No deletion,
consolidation, or remediation was performed (all are WS07 work).

WS06 answers: *what remains wrong, incomplete, duplicated, misleading,
inefficient, poorly organized, insufficiently tested, poorly documented,
over-dependent, slow, or operationally awkward across the product surface and
engineering system* — before the master reconciliation program begins.

Not re-litigated (per controller §0): scope authority, donor provenance,
GridIQ disposition, multi-asset authorization, architecture conclusions
(WS05 baseline). WS05 architecture findings are preserved (see §Preserved WS05
architecture truth below) and are referenced, not re-opened.

Finding IDs: UX-001…, API-001…, TEST-001…, DEV-001…, DOC-001…, DEP-001…,
REPO-001…, PERF-001…, OPS-001…. Every material finding carries severity,
evidence, impact, current/desired state, dependencies, recommended
disposition, and confidence.

Severity: P0 safety/destructive · P1 core blocker/severe correctness/critical
developer failure · P2 major product/reliability/maintainability · P3
optimization/usability/debt · P4 polish. Confidence: CONFIRMED ·
HIGH_CONFIDENCE · MODERATE_CONFIDENCE · LOW_CONFIDENCE · UNKNOWN.

---

## 1. Executive product / engineering verdict

IMP's **product surface is a single coherent equity-research + Paper-simulation
workstation** with a mode-first (Demo/Paper/Live) shell, 11 per-symbol
research lanes, a complete internal Paper order/portfolio loop, and an honest
data-freshness vocabulary. The **engineering system is mature (~90%
maturity per WS04)** — canonical commands, manifest validation, mode authority,
docs hierarchy, CI convergence all verified as genuine (KEEP_AS_IS, §26).

The product surface is **not yet multi-asset and not yet a trading product**:
every one of the six mandated later domains (Bonds, Crypto, Gold, Silver,
Commodities, Industry) plus a dedicated Government surface has **no user
workflow**; the four original professor streams (Short Squeeze, CVD/Level 2,
Options, Futures) exist as **read-only research lanes on admitted fixtures**
with gated/unverified live paths; trading is **Paper-only by design**
(LIVE-001 blocked). WS04's authorized-scope completion (~50%) and product
maturity (~40%) figures are corroborated, not corrected, by this audit.

What WS06 adds beyond WS04/WS05: a route/state/schema frontend audit, an API
inventory with dead-endpoint candidates, a `validate changed` under-selection
**proof** (controller §47/§97), a testing map with safety-coverage marks, a
developer-system friction register, dependency/repository classification, and
deletion/consolidation candidate registers for WS07.

**Headline numbers (fresh evidence, WS04 baseline unchanged):** FULL Python
451s (dominated by `platform` 106s, `donor_bridge` 83.5s, `ui1` 79.2s —
MEASURED from `.local/ws04-full.json`); UI 438 tests / 57s; docs links
162/162 OK (rerun); `validate changed` under-selection CONFIRMED in three
distinct ways (§17).

**P0: 0. P1: 0 new** (WS05 architecture P1s stand unchanged — AB-001/002/003,
ARCH-001/002/003). WS06's most severe findings are P2.

---

## 2. Preserved WS05 architecture truth (not re-opened)

- **P1 blockers (preserved):** AB-001 equity-only authoritative
  portfolio/risk ledger; AB-002 missing IBKR L1/L2 runtime adapter;
  AB-003 Level-2 book snapshot-only architecture (ARCH-001/002/003).
- **Other WS05 findings carried:** no CRYPTO class/kind in XA-01; no
  tradable-contract validation at the order boundary; no server-side
  preview→submission binding (TRD-001); buying power display-only (TRD-006);
  USD-only portfolio; workspace lane query keys not mode-scoped (P3, deepened
  in §11); frontend/backend schema duplication (§12); options/futures
  numeric-base inconsistency (MA-003).

These are audited *for product/engineering impact* below; they are **not**
solved here.

---

## 3. Product-surface matrix

Classification: FULL_WORKFLOW · PARTIAL_WORKFLOW · READ_ONLY · RESEARCH_ONLY ·
FIXTURE_ONLY · PLACEHOLDER · MISSING · DUPLICATED · DEAD.

| Surface | Status | Evidence (UI surface) | WS07 note |
|---|---|---|---|
| Dashboard (Now) | FULL_WORKFLOW (per approved compact direction) | `ModeNowRoute` → DemoNowPage / PaperNowPage / LiveNowPage; compact metrics + attention exceptions; no giant tables (§7) | KEEP; mode-scoped query keys (§11) |
| Portfolio | FULL_WORKFLOW (equity, Paper) | demo/paper/live Portfolio pages; positions, cash, order history, trace, strategy profitability | Multi-asset representation later (WS07) |
| Trading Workspace | PARTIAL_WORKFLOW (Paper full; Demo/Live read-only) | `WorkspaceRoute` + 11 lanes via `laneRegistry.ts`; Paper ticket with preview→submit | Server binding = WS05 TRD-001 |
| Orders | PARTIAL_WORKFLOW | Paper order history + trace + cancel; no replace, working-remainder semantics partial (WS05) | Order mgmt UX §10 |
| Research | RESEARCH_ONLY | analytics/models/simulation read-only panels | Coherent enough; provenance visible |
| Analytics | RESEARCH_ONLY | Research Analytics panels (attention tiers, squeeze outcomes, strategy, risk decisions) | Missing cross-asset analytics (scope) |
| Short Squeeze | PARTIAL (RESEARCH_ONLY) | explore/squeeze + scanner + workspace squeeze lane; bridge :8787 not running (skips) | Calibration = WS07 |
| CVD / Level 2 | PARTIAL (RESEARCH_ONLY, FIXTURE-based) | order-flow + order-book workspace lanes; live path gated; IBKR L1/L2 missing (AB-002) | P1 architecture blocker stands |
| Options | PARTIAL (RESEARCH_ONLY, FIXTURE-based) | options workspace lane (O1–O10 analytics) | No live chain (WS05) |
| Futures | PARTIAL (RESEARCH_ONLY, FIXTURE-based) | futures workspace lane + explore/futures | No live runtime (WS05) |
| Bonds / Fixed Income | MISSING (no UI; FRED vertical backend only) | zero routes/components | Authorized domain — WS07 backlog |
| Crypto | MISSING | zero routes/components | Authorized domain — WS07 backlog |
| Gold | MISSING | zero routes/components | Authorized domain — WS07 backlog |
| Silver | MISSING | zero routes/components | Authorized domain — WS07 backlog |
| Commodities | MISSING (UI) / PARTIAL (backend energy groundwork) | macro context surfaces only (market-context lane exists backend-only) | Authorized domain — WS07 backlog |
| Whale / Large-Participant | PARTIAL (RESEARCH_ONLY) | workspace lanes: institutional-flow, fund-etf, large-transactions, disclosure; participant fixtures | No whale cockpit; doctrine D20 open |
| Industry Intelligence | MISSING | zero routes/components | Authorized domain — WS07 backlog |
| Government / Public-Sector | PARTIAL (backend) / MISSING (workflow) | provider health + operator readiness surfaces; FRED/COT/EIA/NOAA/SEC data not surfaced to a user workflow | WS07 backlog |
| Market Context | PARTIAL (RESEARCH_ONLY) | `/workspace/:symbol/market-context` endpoint exists; **no frontend lane** (dead route candidate §15) | See API-004 |

Workflow-level verdict: the **launch → mode → workspace → research → draft →
preview → submit → monitor → portfolio** loop is complete and typed in Paper
mode; the **donor-stream handoffs** (Squeeze/CVD/Options/Futures → Workspace)
work as read-only research; the **cross-market intelligence → opportunity**
handoff is only partially wired (cross-lane fusion exists backend-side; the
UI exposes `opportunity_snapshot` inside the squeeze lane only).

---

## 4. Frontend route matrix (summary; full detail in §Appendix)

Routes (`ui/src/App.tsx`): `/` (Now/Dashboard), `/explore`, `/discover`,
`/workspace`, `/workspace/:symbol`, `/workspace/:symbol/{squeeze, order-flow,
order-book, futures, catalyst, fund-etf, options, large-transactions,
disclosure, institutional-flow}`, `/research`, `/portfolio`, `/live-canary`,
`/settings`, `/control`, `/diagnostics/provider`, `/assistant/history`,
`*` → redirect `/`.

Findings from the route pass:

- **Route structure is mode-agnostic** — mode is app-level state
  (`ApplicationBootstrap`), which is the correct IA (one product, not three).
  All routes are reachable from `NavShell`/`WorkspaceModuleNav`; no orphan
  routes found. `WorkspaceIndex` at `/workspace` is a landing page.
- **Lane routes are hard-coded** in `App.tsx` (11 explicit `<Route>` entries)
  while the lane *registry* lives in `laneRegistry.ts` — a second source of
  truth for the same lane set. `laneRegistry.test.ts` only checks registry
  internal consistency, **not** that App routes match the registry (a lane
  added to the registry but not App.tsx would be invisible to tests).
  → UX-007 (P3): route/registry drift risk.
- `/workspace/:symbol` accepts **any** symbol string; demo replay chart only
  exists for `ADMITTED_REPLAY_INSTRUMENT_ID`; other symbols show the same
  lanes with fixture/gated data or `available:false` reasons — acceptable
  degrade, but the "no instrument" / "unknown symbol" distinction is
  symbol-string-based, not instrument-identity-based (see UX-004).
- `/diagnostics/provider` and `/live-canary` are operator surfaces behind the
  login gate; `/settings`/`/control` are operator pages — all reachable via
  nav.

Route count by mode is uniform (same routes, mode-routed components) — this is
**intentional boundary** (mode is a cross-cutting concern), but it multiplies
components (§6).

---

## 5. Component inventory

- **184 component files** under `ui/src/components` (85 test files, 438
  tests). Largest: `DiscoverObservability.tsx` (587 lines),
  `FuturesWorkspacePanel.tsx` (446), `ExploreObservability.tsx` (354),
  `paper/OrderTicket.tsx` (341). No single component is pathological; the
  large ones are shared observability surfaces.
- **Mode×page near-duplication is the dominant pattern**: `demo-*`,
  `paper-*`, `live-*` directories exist for discover/explore/now/portfolio/
  research/workspace (18 page directories). Many share view-model code
  (`liveDashboardViewModel`, `livePortfolioViewModel`,
  `paperDashboardViewModel`, `portfolio-shared/PaperPortfolioObservability`,
  `workspace-shared/WorkspaceObservability`, `workspace-module-shared/*`),
  which is the right direction, but the per-mode page components remain
  largely hand-rolled. Classified `LEGACY_DUPLICATION` (UX-006, P3): not
  harmful today, but it is the main reason six more asset domains would
  produce "six unrelated applications" unless a shared shell is adopted
  (UX-005).
- **Workspace lane panels** (`orderflow/`, `orderbook/`, `options/`,
  `futures/`, `institutional/`, `fundetf/`, `catalyst/`, `disclosure/`,
  `squeeze/`, `largetransactions/`) are one panel per lane with shared
  `workspace-module-shared/ModeAwareWorkspaceLane` scaffolding — well
  factored for extension.
- **Dead components:** none found by import-census; `ModeDiscoverRoute`,
  `ModeExploreRoute` etc. are all reachable. No orphan components detected.

---

## 6. Frontend data truthfulness

- **Mode truthfulness is strong**: `ModeEnvironmentBar` (persistent,
  mode + boundary text + backend-alignment status), per-mode eyebrows
  ("Demo · Historical research", "Paper-only simulation", "Live · Read-only
  observational"), portfolio provenance badges
  (`DATA: {data_mode} · {provider} · QUALITY {state} · EXEC {mode} · AUTH
  {authority}`), and `epistemic_class` fields through lane payloads.
- **No fixture data masquerades as live truth** found. Live pages surface
  `LIVE_OBSERVATIONAL` explicitly; Demo surfaces `FIXTURE_REPLAY`/replay
  context; Paper surfaces `INTERNAL_SIMULATION`. The `StartupRecoveryBanner`
  distinguishes crash-recovery and corrupt-DB states honestly.
- **UX-001 (P3, CONFIRMED):** `DemoNowPage` header hardcodes
  `BIYA / REPLAY` — truthful but instrument-specific sample labeling baked
  into the Demo dashboard; belongs in context payload, not markup.
- **UX-002 (P3, CONFIRMED):** several "Unavailable" empty states carry no
  remediation guidance (e.g., portfolio unavailable → "Simulated portfolio
  unavailable." with no next action; provider panels show state without a
  "what to do" pointer in some spots). Not misleading, but not actionable
  (OPS link).
- **UX-003 (P3, CONFIRMED):** live `LiveSymbolLookup` searches any string;
  when nothing is configured the UI degrades to "Unavailable" states that are
  honest but not diagnostic of *which* gate is closed. See OPS-002.

Verdict: the fixture/live/demo/paper boundary is **truthful in the UI** —
this is KEEP_AS_IS (§26) and was verified, not assumed.

---

## 7. Dashboard findings (approved behavior preserved)

Approved direction: **Dashboard = compact metrics + exceptions**; full
operational tables live on dedicated pages. Verified:

- `DemoNowPage` = replay progress + compact portfolio summary + attention
  feed (exceptions) + inspect-next. ✓ no tables.
- `PaperNowPage` ("Paper Command") = risk ribbon + candidate queue +
  preview composer + exceptions panel — compact, action-focused, and it is
  the **draft entry point**, not a portfolio table. ✓
- `LiveNowPage` ("Live Watch") = provider ribbon + safety snapshot + symbol
  lookup + attention feed; read-only. ✓
- Full tables live on `/portfolio` (mode-specific) and `/paper/order-history`
  + trace. ✓

**UX-004 (P3, CONFIRMED):** Paper Command mixes *dashboard* and *order-entry*
responsibilities in one page (candidate queue + preview composer). This is a
deliberate approved flow (draft → workspace carry), so it is a finding on
*clarity*, not a design rejection: the "preview ≠ submitted order" boundary
is well communicated (fingerprint-gated "Continue to workspace", explicit
`risk_status: PASS` requirement, placeholder-draft notes), and this is the
approved draft-carry UX. Verdict: behavior preserved; only note that Paper
Command renders a full order composer on the dashboard page, which must stay
compact as more attention sources arrive. No change recommended beyond WS07
IA review.

---

## 8. Trading workspace / draft-carry findings

WS05 conclusion (frontend mostly correct; server binding missing) —
**re-verified at the UX level, not re-opened:**

- Draft carry is a **typed, versioned router-state object**
  (`paperOrderDraft.ts`, `version:1`, strict key allowlist, instrument match
  against route symbol, provenance parse `lane:`/`attention:`/`MANUAL`).
  `PaperNowPage` → `continueToWorkspace` → `WorkspaceRoute` re-reads via
  `parsePaperOrderDraft(location.state)` only on `PUSH` navigation; workspace
  `PaperWorkspacePage` re-runs preview against current portfolio/risk state;
  submit enabled only after a fresh `risk_status === "PASS"` preview whose
  fingerprint matches the current draft. This matches the approved carry
  semantics. **UX-005 (P3, CONFIRMED):** after `continueToWorkspace` the
  draft is carried via router `state` — refresh of the target page loses the
  draft (state is not persisted). Acceptable (safe degrade: user re-enters),
  but a refresh mid-carriage silently drops provenance context.
- Placeholder drafts (`BUY × 1 MARKET`) are honestly labeled
  (`LANE_DRAFT_PLACEHOLDER_NOTE`, `ATTENTION_DRAFT_PLACEHOLDER_NOTE`). ✓
- Server-side binding absence (TRD-001) is invisible to the user: preview
  success does not guarantee the submitted order derives from that preview.
  This remains a WS05 P2 architecture item; UX cannot fully compensate
  (fingerprint gating mitigates accidental drift, not server-side replay).
- `LEDGER_ROUTE_LOCK` + idempotency (`client_order_id`/`idempotency_key` from
  one attempt key per preview) verified — duplicate submission protected.

---

## 9. Portfolio UX findings

- Mode-specific portfolio pages (`DemoPortfolioPage`, `PaperPortfolioPage`,
  `LivePortfolioPage`) do **not** duplicate the dashboard: they are the full
  operational surfaces (positions, cash/buying-power, order history, trace,
  strategy profitability) per the approved separation. ✓
- Backend-authoritative values (positions/cash/P&L come from
  `/paper/portfolio`, not client-derived) — KEEP_AS_IS.
- **UX-006 (P2, CONFIRMED):** equity-only representation. Positions are
  share-denominated; buying power is display-only (TRD-006); there is no
  options/futures position table (options ledger is float, separate). The
  multi-asset portfolio redesign (AB-001) will necessarily replace this page
  family's data model — WS07 design input, not a UI bug today.
- **Empty/error states** handled per page (`loading` role=status, unavailable
  panel, authority note). ✓

---

## 10. Order-management UX findings

- Paper order history exposes open/working/partial/filled/cancelled/rejected/
  cancelled-pending statuses via `paperOrderStatusPresentation.ts` + trace
  panel. Cancel exists (`cancelPaperOrder`). ✓
- **UX-007 (P3, CONFIRMED):** no Replace action anywhere (backend has no
  replace — WS05 TRD-007); working-remainder semantics are one-shot (a
  partially-filled order's remainder is not re-workable). The UI does not
  misrepresent these as supported, but it also does not tell the user they
  are unsupported — a disabled/absent affordance with no explanatory note.
- **UX-008 (P3, CONFIRMED):** after submit, success feedback is the order
  appearing in history/trace; there is no explicit "order accepted at $X"
  confirmation surface on the ticket. Functional, but thin.

---

## 11. Frontend state / query-key findings

- Query keys (`ui/src/api/hooks.ts`) are **not mode-scoped** (WS05 P3,
  deepened): `["workspace", symbol, lane]`, `["context"]`, `["attention"]`,
  `["paper", ...]`, `["explore", ...]`. Mode is read *inside* hooks
  (`contextQuery.data?.as_of_context.data_mode` to decide
  `refetchInterval`), so switching DEMO→PAPER→LIVE with the same browser
  session can **reuse another mode's cached lane data** (stale-data reuse
  risk) and can race: a LIVE refetch and a DEMO read share one cache entry.
  Live canary keys ARE account-scoped; paper portfolio split by view mode —
  partial scoping exists, confirming the pattern works.
  **UX-009 (P2, CONFIRMED, WS07):** introduce a mode (and account, provider,
  as-of) dimension in query keys. WS05 classified P3; WS06 upgrades the
  practical impact note (mode switching is a first-class UX in this app).
- **Local-state ownership** is largely correct: router state carries drafts;
  server truth stays in the query cache; preferences in operator endpoints.
  No duplicated server truth in useState/localStorage found for portfolio or
  positions. `chartStates.test.ts`/`paperDashboardViewModel` cover derived
  state. ✓
- **UX-010 (P3, CONFIRMED):** `queryKeys.instrument(id)` is invalidated via
  `["instrument"]` prefix in `refreshAll` — correct; but `refreshAll` does
  not invalidate workspace lane keys after scrub, so scrubbing the replay
  cursor can leave lane panels stale until their own refetch. Verified:
  `scrub()` → `refreshAll()` invalidates context/attention/instrument only.
  (Lane hooks keyed by symbol would need invalidation on scrub.)

---

## 12. Frontend schema findings (WS05 PARTIAL, evidenced)

`ui/src/api/schemas.ts` is **2,000 lines, ~70 Zod schemas** manually
mirroring backend projections:

- **Enum duplication:** `data_mode` re-declared as a frontend enum
  (`FIXTURE_REPLAY | HISTORICAL_CAPTURE | LIVE_OBSERVATIONAL |
  BROKER_DELAYED`) and `execution_mode`/`execution_authority` duplicated —
  drift between backend strings and frontend enums is checked only by
  `schemas.test.ts` against recorded fixtures, not against backend code.
- **Passthrough erosion:** `ProviderHealthResponseSchema` (`.passthrough()`),
  `MarketStateResponseSchema` (`z.record(z.unknown())`),
  `OpportunityInputComponentSchema`, `StrategyCandidateSchema`, and several
  `z.record(z.unknown())` blocks mean the *largest, most dynamic* payloads
  are effectively untyped — the contract layer protects the small schemas and
  passes through the big ones.
- **`/explain/:ref` and `/inspect/:ref` use `fetchRawJson` with no schema at
  all** — the evidence-drawer/panel payloads (the core "why" UX) are the
  least validated surface.
- No schema versioning; no shared/generated contract.
- **UX-011 (P2, CONFIRMED, WS07):** generated/shared API contracts
  (OpenAPI or a codegen from backend projection builders) is the recommended
  target per §34/§100; not implemented here. Frontend `schemas.test.ts`
  (369 lines) is a reasonable interim guard — KEEP until contracts land.

---

## 13. Loading / empty / error / stale-state findings

- **Good:** `LazyBoundary` for route chunks; `LoadingState`; per-page
  `role="status"`/`role="alert"`; `StartupRecoveryBanner`; attention/portfolio/
  replay state machines (`loading|ready|error`); workspace squeeze readiness
  block (`readiness.freshness_state`, `provenance_admissible`).
- **UX-012 (P3, CONFIRMED):** no explicit **stale** presentation for lane
  payloads whose backend time model says stale (backend exposes
  source/available timestamps and quality, but the UI mostly shows values
  without staleness chips except squeeze readiness). WS05 established a strong
  backend freshness model; the UI exposes it *in the workspace lanes*
  (`readiness`), but the now/portfolio surfaces show quality state rather
  than per-field staleness — acceptable per controller §15 (don't overwhelm
  with timestamps), but operator-critical panels (provider health) are the
  right place for it and already carry lag percentiles. No change before
  WS07 IA.
- **UX-013 (P3, CONFIRMED):** `ModeEnvironmentBar` on mismatch says "UI mode
  selection does not change backend authority" — correct, but there is no
  path to fix the mismatch from the bar (must switch mode via launcher).
  Minor.

---

## 14. API inventory verdict

Backend: `ui_api/server.py` (1,071 lines) — a stdlib HTTP router delegating to
~20 projection modules (paper, live, operator, canary, broker, strategy,
discovery, mixed-discovery, workspace-evidence, lane-provenance, auth,
assistant). **~90 GET/POST routes.** Frontend callers via
`ui/src/api/endpoints.ts` (47 functions) + direct `fetch` for replay scrub,
assistant, subscriptions.

Ownership: routes are organized **around page/projection families
(`workspace/*`, `paper/*`, `operator/*`, `canary/*`, `discover/*`)**, not
domain responsibilities. Business logic lives in projection modules (good),
but route *families* mirror historical phases/pages (paper/ broker-paper/
canary/ operator/ discovery/ mixed/). Classified PARTIAL per WS05 with the
following concrete evidence:

- **API-001 (P3, CONFIRMED):** projection modules import `tools.platform`
  modules (`tools/platform/control_service.py`) from inside `src/.../ui_api`
  — a `src`→`tools` dependency inversion (`server.py` lines importing
  `tools.platform.control_service`). Works, but couples the API layer to the
  tooling layer.
- **API-002 (P3, CONFIRMED):** `Access-Control-Allow-Origin: *` on every
  response (local loopback server — low risk, but unbounded).
- **API-003 (P2, CONFIRMED):** business logic in route handlers exists for
  small cases (`/subscriptions` parses/validates body inline,
  `/operator/providers/:p/refresh` inline), but the material logic is in
  projections — overall clean; flag only the exceptions.

Route/endpoint inventory and status are in §Appendix; dead/duplicate
candidates in §15.

---

## 15. Dead / duplicate API candidates

Evidence = zero non-test frontend references (greps of `ui/src`, excluding
test files) + no other caller found in `tools/`/`tests/` non-fixture usage.

| Candidate | Route(s) | Evidence | Classification | Recommended disposition |
|---|---|---|---|---|
| Paper sub-account endpoints | `/paper/account`, `/paper/positions`, `/paper/fills`, `/paper/risk` | 0 non-test frontend refs; frontend uses `/paper/portfolio` + `/paper/order-history` + `/paper/trace` + `/paper/strategy-profitability` | CANDIDATE-DEAD (superseded by `/paper/portfolio`) | WS07: verify test coverage (ui1/ui2 may cover), then ARCHIVE or mark deprecated; do not delete before WS07 evidence |
| `/paper/orders` GET | same family | 1 non-test ref (the POST path is used for submit) | likely superseded | same |
| Market-context workspace lane | `/workspace/:symbol/market-context` | 1 non-test ref (string match, not an API call — no `getWorkspaceMarketContext` in endpoints/hooks; no lane in `laneRegistry.ts`) | CANDIDATE-DEAD (backend-only lane; WS04 recorded "market-context" as an 11th lane concept that is NOT in the 11-lane registry) | WS07: either wire a real lane or archive; **do not delete** (backend capability `providers/projections.build_workspace_market_context_payload` + sentiment/event engines are live research value) |
| `/capabilities` GET | server.py | not called by endpoints.ts (context supplies capability_states) | CANDIDATE-DUPLICATE of `/context` capability_states | WS07: confirm and unify |
| `/explain/:ref` / `/inspect/:ref` | — | actively used (drawer/panel) | ACTIVE but schema-less | keep; add schema (UX-011) |
| `/discover/run`, `/discover/screens`, `/discover/mixed` | — | used by discover pages | ACTIVE | keep |
| `/captures`, `/captures/replay` | — | used by operator control center | ACTIVE | keep |
| `/canary/*` (10 routes) | — | used by live-canary control plane | ACTIVE | keep |
| `/operator/*` (10 routes) | — | used by operator pages | ACTIVE | keep |

Rule applied: a route is DEAD only with evidence of non-use; each candidate
keeps a WS07 verification step (test coverage + caller grep) before any
action. No deletion performed.

---

## 16. API contract / error-taxonomy findings

- **API-004 (P2, CONFIRMED):** error responses are `{"error": msg,
  "reason_code": code}` with ad-hoc codes (`UI_REQUEST_INVALID`,
  `PAPER_ORDER_SUBMIT_FAILED`, `OPERATIONAL_ACCOUNT_UNKNOWN`,
  `PAPER_EXECUTION_NOT_AUTHORIZED`, `LIVE_OBSERVATIONAL_DISABLED`,
  `CANARY_COMMAND_FAILED`, …). **None of the WS05 target categories
  (`VALIDATION_ERROR`, `PROVIDER_UNAVAILABLE`, `PROVIDER_REJECTED`,
  `STALE_DATA`, `UNSUPPORTED_CAPABILITY`, `ACCOUNT_UNAVAILABLE`,
  `RISK_BLOCKED`, `MODE_BLOCKED`, `AUTH_ERROR`, `RATE_LIMITED`, `TIMEOUT`,
  `INTERNAL_ERROR`) exist as a canonical taxonomy.** Some map cleanly by name
  (PAPER_EXECUTION_NOT_AUTHORIZED ≈ MODE_BLOCKED; OPERATIONAL_ACCOUNT_UNKNOWN
  ≈ ACCOUNT_UNAVAILABLE), most do not. Frontend `ApiRequestError` surfaces
  `code: message` as a string — the taxonomy is string-parsing, not typed.
  WS07: one canonical error contract + frontend type union.
- **API-005 (P3, CONFIRMED):** request/response validation is backend
  one-sided (handlers validate ad hoc; frontend Zod parses responses). No
  shared contract, no versioning, nullable/default mismatches exist between
  Zod `.optional()` and backend `None` serialization (`default=str` in
  `_send_json` means None becomes "None" strings in some payloads — a
  real nullable-mismatch risk in dynamic payloads).
- **API-006 (P3, CONFIRMED):** `_send_json(default=str)` serializes
  `None`/objects loosely; combined with passthrough schemas, type drift
  between backend and frontend is invisible until runtime. Evidence:
  `MarketStateResponseSchema` fields are all optional records.

---

## 17. `validate changed` findings (controller §47/§97 — proven, not assumed)

`tools/validate.py::select_changed` maps changed paths → suites via
`test_globs`/`source_globs`; unmatched paths escalate to full only if
`_is_executable_or_config` (root in {src,tools,ui,manifests} + known suffix).
**CONFIRMED under-selection in three distinct ways** (all reproduced with
`python tools/validate.py changed --paths-file … --explain`):

1. **Monorepo path prefix** (TD-W9 confirmed with fresh evidence): a change
   reported by git inside the parent snapshot arrives as
   `projects/integrated-market-platform/src/...`. No suite glob matches
   (`src/...` patterns), and `projects` is not in `EXECUTABLE_ROOTS`, so
   **no suite is selected and `full_suite_required=false`** — only the 21
   mandatory invariants run (WS04 measured 21 tests / 1.8s). CI strips the
   prefix (`sed` in `imp-python.yml`) so CI is unaffected; **local monorepo
   development is silently under-validated**. Severity P2 (developer-system
   correctness; no production safety path — CI catches it).
2. **Fixture/config/test-fixture changes**: `fixtures/**`, `config/**`,
   `tests/fixtures/**` are not executable-or-config by `_is_executable_or_config`
   (roots only src/tools/ui/manifests) and match no globs → silent
   no-selection (reproduced: `full_suite_required=false`, zero suites).
   Fixtures are exactly the files whose edits break lane tests.
   Severity P2.
3. **Shared modules** (`numeric.py`, `clock.py`, `errors.py`, `assertions.py`,
   `authority.py`, `evidence.py`, `market_sessions.py`) appear in **zero**
   suite `source_globs` (grep evidence: 0 hits each; only `canonical.py`,
   `operating_modes.py` are covered, both via full_invalidators/one suite).
   A shared-module change *does* escalate (any unmatched `src/**` path is
   `UNKNOWN_EXECUTABLE_PATH` → broad core diagnostics), so this is
   fail-safe-but-blunt: it triggers the 5 core suites rather than the true
   dependents. Severity P3 (safe, but wasteful and imprecise).

Also verified: `full_suite_required=true` **does not run the full suite** —
it runs `_offline_core_diagnostics` (validation/phase0/contracts/runtime/
providers) + mandatory (telemetry: `validate changed` avg ≈ 74s, consistent
with 5 core suites, not the 451s full). The name over-promises; a developer
seeing `full_suite_required=true` may believe the full suite ran.

**Disproven aspect:** within the child repo (own `.git`, paths relative to
the child root), direct test/source globs select correctly; deleted/renamed
files are captured (`--name-only` includes deletions); test-only changes
correctly skip neighbor expansion. The neighbor mechanism works for covered
direct-source suites.

**Target correction (WS07):** (a) normalize the `projects/integrated-market-platform/`
prefix when running inside the monorepo snapshot; (b) add `fixtures/**`,
`config/**`, `tests/fixtures/**` ownership (map to consuming suites or force
full); (c) add shared-module dependency mapping OR rename the flag to
`core_checkpoint_required` with output stating what actually ran.

---

## 18. Validation pyramid / parallel-testing / CI / hooks findings

- **Pyramid** (FAST → focused/affected → domain → changed → FULL): commands
  exist and telemetry (`.local/developer-workflow/telemetry.jsonl`) shows
  agents use them: validate fast ×4, validate domain ×22, validate full ×4,
  test focused ×5, validate changed ×6. **DEV-001 (P3, CONFIRMED):** domain
  validation dominates (2,464s total across 22 runs ≈ 112s avg) and `validate
  changed` escalates to core diagnostics when dirty state triggers
  UNKNOWN_EXECUTABLE_PATH (≈74s avg) — the pyramid's *cheap* tier is not
  actually cheap in the monorepo layout, pushing agents toward domain/full
  runs.
- **Parallelism:** suites carry `parallel_safety` (PARALLEL_SAFE /
  SERIAL_REQUIRED / GLOBAL_STATE_MUTATION / RESOURCE_HEAVY / LIVE_EXCLUSIVE);
  workers=2 default. **DEV-002 (P3, CONFIRMED):** the slowest suites are
  GLOBAL_STATE_MUTATION (platform 106s, ui1 79s, phase0 9s, phase8 14s,
  gridiq 12s, mra002 14s, ui2) or RESOURCE_HEAVY (donor_bridge 83.5s,
  integration 50s, providers 39s, postroot, assistant 15s) — serial groups
  run first (sum ≈ 200s+) then heavy parallel at min(2, workers). The
  design already avoids unsafe parallelism (SQLite/ports/process globals are
  the reason for GLOBAL_STATE_MUTATION — verified classification, not
  laziness). No parallelization recommendation beyond WS07: consider
  splitting `platform`/`ui1` or raising heavy-worker count to 2–4 on
  resource-safe runners.
- **CI:** parent-root `imp-validate.yml` + `imp-python.yml` +
  `monorepo-guardrails.yml`. Local canonical commands, CI, and closure
  **converge** (same `tools/imp.py validate` path, same manifest; CI runs
  fast + changed + docs + UI typecheck/test/build; closure adds full +
  docs + UI build). Divergence: **CI never runs FULL** (time cost) and does
  not run closure; the `projects/`-prefix bug does not affect CI (stripped).
  The child-repo `.github/workflows/*.yml` copies are **explicitly labeled
  STALE** (verified headers) — a duplication candidate (REPO-003) but
  correctly disclaimed.
- **Hooks:** no git pre-commit/pre-push hooks found; `.cursor/hooks.json`
  (beforeShellExecution policy.py failClosed + afterFileEdit, non-fatal) +
  monorepo guardrails in CI. No duplicate-validation or slow hooks found.
  Missing high-value check: no cheap `format`/`lint` gate in CI changed job
  (CI runs validation but not `imp.py format`/`lint`) — minor.

---

## 18a. Testing architecture / safety coverage / provider contract / E2E findings

Testing map (actual counts): Python 451 test files → 60 manifest suites →
3,580 tests (WS04 FULL); UI 85 test files → 438 tests; mandatory invariants
21 (FAST). Layers present: unit (per-module), formula (options 147, futures
65, order_flow 66, formulas 30), provider adapter (per-provider offline
suites), API (ui1/ui2), frontend component (Vitest), domain integration
(per-domain). Layers **absent**: real E2E (browser/process), provider
contract tests against live wire (gated), performance tests (benchmark tool
exists, no gate).

- **TEST-001 (P2, CONFIRMED): no genuine E2E tests exist.** The 438 UI tests
  are Vitest+jsdom component tests; backend routes are exercised by ui1/ui2
  API suites; there is **no browser-level or process-level workflow test**
  (mode launch → research → draft → preview → submit → portfolio, account
  switching, order cancel) that spans frontend+backend. WS07: decide
  Playwright for the Paper workflow; distinguish real E2E from API
  integration in the manifest (`e2e` classification).
- **TEST-002 (CONFIRMED): critical safety coverage is largely COVERED at the
  backend unit level but with gaps.** Verified marks: Demo/Paper/Live
  isolation — COVERED (`tests/phase0` offline-guard, `tests/paper`
  governance/qualification, `MODE_AUTHORITY` tests); account isolation —
  COVERED (identity-scoped cache keys + `/accounts` tests); cache isolation —
  COVERED (account_snapshot_cache); query-key isolation — MISSING (no test
  asserts frontend keys are mode-scoped — the keys are not scoped, UX-009);
  stale preview invalidation — PARTIAL (frontend fingerprint tests; no
  server-side binding to test, TRD-001); duplicate order submission —
  COVERED (idempotency tests); partial fills — COVERED at ledger level
  (one-shot semantics tested); cancel races — PARTIAL (cancel tests exist;
  cancel-vs-fill race unmodeled per TRD-005); replace — MISSING (not
  implemented, TRD-004); provider reconnect — COVERED (live_admission
  reconnect tests); stale L2 book — MISSING (no staleness control —
  ARCH-009); IBKR entitlement loss — MISSING (no IB adapter); book reset —
  MISSING (snapshot-only, ARCH-003); multi-asset identity — PARTIAL (xa01
  tests; no CRYPTO); multi-asset portfolio — MISSING (AB-001).
- **TEST-003 (CONFIRMED): provider contract testing is strong offline, live
  suites exist but are gated.** Moomoo (live_moomoo, gated), Tradier
  (recorded-sandbox fixture tests, `BROKER_TRANSPORT_NOT_IMPLEMENTED`
  fail-closed), IBKR tooling (`tests/ibkr` 47, no L2), FinViz (57),
  FRED/ALFRED (30 + live_fred), CFTC (20 + live_cftc), EIA (23 +
  live_eia), NOAA/weather (41 + live_weather), SEC/EDGAR (21 + live_sec),
  CBOE (46 + live_cboe/live_cboe_options), Anthropic (assistant tests +
  AbstainingInferenceStub default). Live suites are `LIVE_EXCLUSIVE` and
  stripped offline (safe); no RUNTIME_VERIFIED wire exists (WS04) — that is
  a coverage *classification* fact, not a test-quality defect.
- **TEST-004 (P3, CONFIRMED): UI test quality is good but workflow-gapped.**
  Assertion-light/snapshot-only tests: none found by spot check; tests
  assert behavior (draft fingerprint, risk gating, mode routing, lane
  registry). Gap: route↔registry drift is untested (a lane added to
  `laneRegistry.ts` without an App.tsx route passes `laneRegistry.test.ts`),
  and loading/error states for several lanes are asserted only in the shared
  scaffold, not per lane.
- **TEST-005 (CONFIRMED): validation manifest is self-validating and
  accurate** — `_validate_inventory` fails on any test dir with `test_*.py`
  absent from the manifest and any configured-but-missing suite path;
  `_validate_invariant_targets` statically verifies mandatory selectors.
  No test is duplicated across command paths; FAST/mandatory/domain/full
  are subsets, not duplicates. KEEP_AS_IS.
- **TEST-006 (CONFIRMED): no flaky/slow-test evidence in history or fresh
  runs**; the dominant latency is suite *size* (PERF-001), not flakiness.
  Skips are explained (donor-bridge servers not running, live gates).

## 19. Developer operating system findings

- **DEV-003 (P2, CONFIRMED): fresh-developer friction #1 is workspace
  topology**: developers must know the canonical edit target is the tracked
  snapshot `projects/integrated-market-platform/` *or* the child repo
  `integrated-market-platform/` (own `.git`, remote → archived repo) *or* the
  worktree — and that `validate changed` only works correctly from the child
  repo layout (per §17.1). Nothing in AGENTS.md tells a fresh developer
  which tree is canonical to edit. This is the dominant tribal-knowledge cost
  (DEV-007 register).
- **DEV-004 (P3, CONFIRMED): `imp.py env` is informational-only**: it prints
  the Python version (WS04 reproduced 3.10-first discovery vs the required
  3.11) and node/npm availability, but **always exits 0** — agents cannot
  gate on a bad environment (`if imp.py env; then …` never fails). Desired:
  non-zero exit for wrong Python/version + missing npm when UI work is
  planned; keep optional providers informational.
- **DEV-005 (P3, CONFIRMED):** handoff-file sprawl — `task_plan.md`,
  `progress.md`, `findings.md` at IMP root + `docs/engineering/WORK_LOG.md` +
  `docs/platform/PROGRAM_STATUS.md` + `docs/README.md` authority + this audit
  workspace. Five parallel "current state" documents; the docs authority map
  mitigates but does not eliminate. Consolidation candidate (WS07): keep
  WORK_LOG + docs authority; demote planning scratch.
- **DEV-006 (P3, CONFIRMED):** `.cursor/rules` (8 mdc files) + `.cursor/agents`
  (7) + AGENTS.md + docs/engineering handbook + SOPs (10+) + superpowers
  governance JSON — layered and mostly non-conflicting (authority map works),
  but rules repeat across layers (e.g., no-fabricated-data / paper-execution-
  safety / react-query-keys each appear in `.cursor/rules` *and* AGENTS.md
  safety invariants). Wasteful context, not contradictory. Consolidation at
  WS07: AGENTS.md remains the router; rules point, not duplicate.
- **DEV-007 (register, §24):** repeated manual work observed/implied:
  locating the correct repo tree (frequent, high error risk),
  re-running expensive validation when changed under-selects (frequent),
  resolving worktree/snapshot state (occasional), manual fixture diagnosis
  (rare).

---

## 20. Documentation findings

- **DOC-001 (KEEP_AS_IS, CONFIRMED):** docs authority hierarchy
  (`docs/README.md` — safety > AGENTS > scoped agents > architecture >
  handbook/SOP > specs > completion records > work log) is explicit and
  correct. Completion records are labeled historical. This is the model for
  the whole monorepo.
- **DOC-002 (CONFIRMED):** **no production-ready/live-ready claim exists**
  in IMP docs (grep of docs/ + README for production-ready/production ready/
  LIVE_READY/… returned zero hits). PROGRAM_STATUS/MASTER_ARCHITECTURE
  honestly disclaim; LIVE-001 blocked is documented as a boundary. Current
  truth docs are truthful.
- **DOC-003 (P2, CONFIRMED — carried from 03):** 9+ donor-governance docs
  still treat GridIQ/DS-340W as legitimate (pre-Heller-correction):
  `2026-08-14-donor-code-permissions.json`, ADR-GRIDIQ-001, phase-gate,
  ADR-DONOR-001, DONOR_REUSE_MATRIX, GRID_IQ_NOTES, DS340W_NOTES, revision-3
  donor plans, PROVIDER_DUPLICATION_AUDIT, fixture inventory (TD-P1).
  Exact WS07 Wave 1 action: add superseded headers + correction context in
  place; never delete (per controller §55/§104). No broad rewriting needed
  because current authority pages are already honest.
- **DOC-004 (P3, CONFIRMED):** ADR duplication across three homes:
  `docs/architecture/*.md` (3), `docs/superpowers/decisions/*.json` (20+),
  and `docs/research/donors/*` (ADR-DONOR/GRIDIQ). WS07: choose one canonical
  ADR owner (suggest `docs/architecture/` markdown with JSON as
  machine-readable mirrors).
- **DOC-005 (P3, CONFIRMED):** MASTER_ROADMAP is stale vs the mandate
  (FC-16/MS-13; zero Bonds/Crypto/Gold/Silver/Commodities/Whale/Industry/
  Government) — roadmap truth, not completion claim; update at WS07.
- **DOC-006 (CONFIRMED):** docs links validate clean — `check_docs_links.py`
  rerun: **162/162 OK**. No broken links/moved files found.
- **DOC-007 (P3, CONFIRMED):** documentation duplication of rules across
  `docs/superpowers/specs/` (46 plans incl. completion records) and
  `docs/engineering/*_V1.md` build specs — historical by design; authority
  map already separates them; no consolidation needed beyond DOC-004.

---

## 21. Dependency findings

- **DEP-001 (CONFIRMED):** Python core is **stdlib-only**
  (dataclasses/enum/pathlib/typing dominate; grep of third-party imports in
  `src/` returns only `numpy` + `scikit-learn` in `intelligence/features`
  trainers and `assistant` inference; `pymongo` in `intelligence/
  persistence/mongo` + `xa04/mongo` repositories and `tools/platform/
  bootstrap.py`; `ib_insync` only in `tools/ibkr/tws_client.py` optional
  TWS path; `anthropic` in assistant inference behind the
  `AbstainingInferenceStub` default). This matches the documented
  `.venv` contents (numpy/pymongo/scikit-learn + tzdata). Classification:
  numpy/sklearn JUSTIFIED (model training); pymongo OPTIONAL (Mongo
  persistence repositories are fallback/alternate paths; SQLite is the
  canonical store); ib_insync OPTIONAL (TWS observational, seed for the
  WS07 IB adapter); anthropic OPTIONAL (stub default).
- **DEP-002 (CONFIRMED):** Node deps are all used: react/react-dom/
  react-router-dom/@tanstack/react-query/zod/recharts/lightweight-charts
  (charts in workspace/replay); dev: vite/vitest/ts/testing-library/jsdom.
  **No unused majors found.** Two chart libraries (recharts +
  lightweight-charts) coexist — REPLACEABLE-adjacent but different use cases
  (analytics charts vs financial charts); keep, revisit at WS07 if bundle
  budget tightens.
- **DEP-003 (P3, CONFIRMED):** no heavy/unused dependency candidates of
  material weight. `node_modules/` present in IMP `ui/` (ignored) and in
  `Claude Code News/` (untracked; parent `.gitignore` has `**/node_modules/`
  — D7: verified covered, no action needed beyond keeping it ignored).
- **DEP-004 (P3):** provider-SDK strategy is inconsistent by design and
  *appropriately so*: official SDK where stable (ib_insync optional TWS),
  raw REST elsewhere (Client Portal), recorded-fixture transport for broker
  paper (Tradier), no browser automation in IMP (CCN Tradovate CDP is donor,
  not canonical per WS05 D3). Verdict: no forced unification; WS07 IB
  adapter should follow the `tools/ibkr` REST core + optional SDK, per D19.

---

## 22. Repository topology findings

Parent `market-trading-platform/` classification (WS01 base + WS06):

| Path | Class | Evidence |
|---|---|---|
| `projects/integrated-market-platform/` | CANONICAL_SOURCE (tracked snapshot) | parent CI working-directory; audit baseline |
| `integrated-market-platform/` (child repo) | INTERNAL_WORKTREE/child (own .git, in sync with snapshot) | WS01; only `__pycache__` differs |
| `projects/short-squeeze-project/` | SNAPSHOT (stale) | manifest `78b7467` vs child `9de7b2f` vs plan `41f52bb` (TD-P5) |
| `projects/governed-ticker-metadata-enrichment/`, `projects/equity-data-v1-worktree/` | SNAPSHOT (in sync) | manifest matches child HEADs |
| `short-squeeze-project/`, `governed-ticker-metadata-enrichment/`, `equity-data-v1-worktree/` | INTERNAL_WORKTREE (child repos) | own .git |
| `DS-440-CAPSTONE-GridIQ-main/` | MISTAKEN_DONOR (remnant) | WS01 SRC-002; 0 source files |
| `tradingCVDBubble-main (1)/`, `internship-project-main/`, `Eric_futuresX-main/` | AUTHORIZED_DONOR (remnants) | WS01 SRC-003/004/005 |
| `Claude Code News/` | AUTHORIZED_FUTURE_DONOR (full source) | WS01 SRC-006; node_modules hygiene D7 |
| `project-scope-images/` | GENERATED/evidence (Tier A images) | 02a index |
| `pytest-equity-premerge-20260824/`, `pytest-equity-postmerge-20260824c/` | TEST_ARTIFACT (empty) | 0 files; REPO-002 |
| `.worktrees/` | INTERNAL_WORKTREE (forensic/lineage) | WS01 |
| `tests/`, `tools/`, `.github/`, `docs/` (parent) | CANONICAL_SOURCE (monorepo governance) | — |
| `docs/audits/imp-reconciliation/` | GENERATED (canonical program record) | this workspace |

- **REPO-001 (P2, CONFIRMED):** short-squeeze snapshot lag is **stale, not
  intentional** (WS01/TD-P5): manifest says `main@78b7467`, child is on
  `fix/frozen-followups@9de7b2f`, hardening plan references `41f52bb` — three
  different truths. Do not resync during WS06; WS07 refresh via guarded
  import.
- **REPO-002 (P3, CONFIRMED):** empty `pytest-equity-*` dirs at parent root —
  TEST_ARTIFACT cleanup candidates (evidence: `find` shows no files).
- **REPO-003 (P3, CONFIRMED):** child-repo `.github/workflows/*.yml` are
  STALE copies (explicit headers) — duplicates of parent-root canonical CI;
  archive or delete with a pointer at WS07.
- **REPO-004 (P3):** donor remnant trees are large (tens of thousands of
  cache/venv files) but must **not** be cleaned during WS06 (controller §64);
  WS07 deletion policy applies with evidence of non-use.

---

## 23. Performance findings

Classification per controller §101 (MEASURED / STRONGLY_INDICATED /
SPECULATIVE / PERFORMANCE_UNVERIFIED).

- **PERF-001 (MEASURED):** FULL validation = 451s; slowest suites
  (`.local/ws04-full.json`): platform 106.1s, donor_bridge 83.5s, ui1 79.2s,
  intelligence 52.2s, integration 50.1s, providers 38.9s, assistant 14.7s,
  mra002 14.5s, phase8 13.8s, gridiq 12.1s, phase0 9.4s, finviz 6.9s. Top 3
  ≈ 268s. Causes: GLOBAL_STATE_MUTATION suites serialize (platform/ui1/
  phase0/phase8/gridiq/mra002/ui2), RESOURCE_HEAVY suites load large
  fixtures (donor_bridge/integration/providers/postroot/assistant). Safe
  WS07 candidates: split platform/ui1 by concern; raise heavy parallelism on
  resource-safe runners; fixture caching (STRONGLY_INDICATED — no measurement
  of per-suite setup vs fixture load performed).
- **PERF-002 (MEASURED):** UI test 57s / 438 tests; UI build enforced by
  `scripts/check-bundle-budget.mjs` (initial gzip ≤ 203KB, chunk raw ≤
  500KB) — a real, gating budget. KEEP.
- **PERF-003 (PERFORMANCE_UNVERIFIED):** runtime Level-2 throughput — no live
  L2 adapter exists (ARCH-003), so no numbers exist; classify as
  **FUTURE CAPACITY RISK** for the WS07 IB adapter, not an optimization now
  (controller §101).
- **PERF-004 (STRONGLY_INDICATED):** live-mode polling: order-flow/order-book/
  market-state refetch at 2s, evidence at 5s, provider health at 5s when
  LIVE_OBSERVATIONAL; a push feed exists (Moomoo) but the UI polls REST —
  acceptable at this scale, but 4+ simultaneous 2s polls on a workspace page
  is the future live-mode hotspot. No change now.
- **PERF-005 (STRONGLY_INDICATED):** memory/cache bounds are designed
  (live-runtime subscription quota test, account-snapshot cache per-entry
  locks, bounded deques in observational buffers — `live_runtime.py` quota
  test passes). No leak evidence; no unbounded growth found in read pass.
- **PERF-006 (MEASURED):** FAST validation 9.3s (WS04), mandatory-only
  changed runs ~0.2s selection + worker time; UI typecheck clean.

---

## 24. Reliability / operability / accessibility / responsiveness findings

- **OPS-001 (KEEP_AS_IS, CONFIRMED):** diagnostics surface is strong:
  `/state/startup` (crash recovery + corrupt-DB), `/operator/state`,
  `/operator/readiness` (preflight checks + provider credential/gate/
  transport states + next_action), `/provider/health` (lifecycle, lag
  percentiles, quota, execution gates), `/diagnostics/provider` panel,
  `/operator/lifecycle/status` + actions. A user/operator **can** diagnose
  provider-offline, entitlement-missing, bad-credentials, and gate-closed
  states.
- **OPS-002 (P3, CONFIRMED):** several read-only panels show
  `Unavailable`/`reason` without the operator `next_action` that the
  readiness payload already carries — bridging those would make errors
  actionable (link UX-002/UX-003).
- **OPS-003 (CONFIRMED):** Windows-first assumptions handled: `npm.cmd`
  dispatch, `.cmd` platform scripts, `os.name == "nt"` checks; donor launchd
  artifacts live only in `Claude Code News/` (macOS donor, out of IMP).
  `imp.py` uses bash/POSIX in docs examples but dispatches correctly on
  Windows. No Unix-only commands in the canonical path.
- **ACC-001 (P3, CONFIRMED):** accessibility spot-check of the material
  workflows: buttons are real `<button>`s with labels; `role="status"` /
  `role="alert"` / `aria-live` used on loading/error states;
  `aria-labelledby` on panels; the replay scrub is a button stepper
  (keyboard-accessible); the assistant toggle has `title` + Escape and "A"
  keyboard shortcuts; focus is not trapped in the modal `LiveModeConfirmation`
  (no focus trap found — P3, modal focus management missing); charts
  (lightweight-charts/recharts) have **no text alternative** (no
  `aria-label`/summary for chart content — color-only + graphic-only
  communication for charted metrics); status chips use color + text
  (acceptable). Verdict: good base, two concrete gaps (modal focus trap,
  chart alternatives) — product correctness per controller §104, not polish.
- **RESP-001 (SPECULATIVE):** fixed multi-panel grids
  (`paper-decision-grid`, `demo-now-grid`, workspace lane grids) were not
  runtime-tested below ~1280px; no media queries found in the mode/lane css
  beyond basic layout. Classified SPECULATIVE (no measurement); desktop +
  smaller laptop expected fine; tablet likely cramped. WS07 responsive pass
  only if a tablet target is required.

---

## 25. Deletion candidate register (no deletion during WS06)

| ID | Artifact | Why removable | Dependencies | Risk | Validation needed | Action |
|---|---|---|---|---|---|---|
| DEL-01 | `/paper/account`, `/paper/positions`, `/paper/fills`, `/paper/risk`, `/paper/orders` GET | 0 non-test frontend refs; superseded by `/paper/portfolio` + `/paper/order-history` | ui1/ui2 tests may assert these routes | Low (API surface change) | grep callers incl. tests; confirm ui1/ui2 coverage | WS07: ARCHIVE or deprecate header first |
| DEL-02 | `/workspace/:symbol/market-context` route | no lane, no frontend caller | backend sentiment/event engines feed nothing | Low | confirm no other consumer (tests/bridge) | WS07: wire lane or archive route; keep backend modules |
| DEL-03 | `pytest-equity-premerge-20260824/`, `pytest-equity-postmerge-20260824c/` (parent root) | empty artifact dirs | none | None | `find` census (0 files) | WS07: remove |
| DEL-04 | Child-repo `.github/workflows/imp-*.yml` (STALE copies) | explicit STALE headers; canonical at parent root | none | None | verify parent CI still canonical | WS07: replace with pointer or delete |
| DEL-05 | `/capabilities` GET | duplicate of `/context` capability_states; no caller | none | Low | confirm endpoints.ts usage | WS07: unify |
| DEL-06 | `tools/run_all_tests.py` / duplicate command paths in manifest full_invalidators | 2nd test runner vs `validate.py` (full_invalidator lists it) | tests may invoke it | Medium | confirm no agent/CI path depends on it | WS07: KEEP if used; else deprecate |
| DEL-07 | `market_platform_foundation/analysis.py` pymongo path + `xa04/mongo`, `intelligence/persistence/mongo` | SQLite canonical; Mongo repositories are alternate persistence | tests may cover | Medium | confirm tests + docs treat Mongo as optional | WS07: mark optional or isolate |

## 26. Consolidation candidate register (no consolidation during WS06)

| ID | Area | Multiple implementations | Target | Boundary to preserve |
|---|---|---|---|---|
| CON-01 | Asset-class vocabularies | `paper/contracts.ASSET_CLASSES` (incl. CRYPTO) vs `xa01.enums.XaAssetClass` (no CRYPTO) vs futures family registry | one canonical identity vocabulary (ADR-C-004) | WS05 MA-004; keep runtime boundary types distinct |
| CON-02 | Frontend/backend schemas | `ui/src/api/schemas.ts` (2,000 lines) vs backend projection builders | generated/shared contracts (§12/UX-011) | none — replacement only |
| CON-03 | Error contracts | ad-hoc reason codes across server.py projections | canonical taxonomy (§16/API-004) | none — additive first |
| CON-04 | Query-key factories | inline keys in hooks.ts + `useInvalidatePaper` prefix invalidation | one factory with mode/account dimension (§11) | none |
| CON-05 | Portfolio ledgers | `portfolio/ledger.py` (equity minor-int) vs `portfolio/options_ledger.py` (float) vs futures sim floats | canonical multi-asset ledger (AB-001, ADR-C-001) | WS05 numeric-base (MA-003) |
| CON-06 | Evidence models | `cross_lane/evidence.py` + `participant/evidence.py` + `intelligence/contracts/evidence.py` + `donor_patterns/*_lane.py` | single evidence contract | WS05 evidence chain KEEP_AS_IS; unify only metadata |
| CON-07 | ADR homes | `docs/architecture/*.md` + `docs/superpowers/decisions/*.json` + `docs/research/donors/*` | one canonical ADR owner (DOC-004) | keep JSON as machine-readable mirrors |
| CON-08 | Provider capability metadata | `providers/contracts.py` protocols + `live_runtime` capability registry + operator readiness providers | one capability registry | none |
| CON-09 | Current-state docs | WORK_LOG + PROGRAM_STATUS + task_plan/progress/findings + docs authority | WORK_LOG + docs authority as canonical (DEV-005) | preserve audit workspace separately |
| CON-10 | Chart libs | recharts + lightweight-charts | evaluate at WS07 if budget tightens (DEP-002) | keep both until then |

## 27. KEEP_AS_IS register (verified in WS06)

| Area | Evidence |
|---|---|
| Canonical developer command interface (`tools/imp.py`) | commands exist, thin facade, telemetry; verified §18 |
| Validation manifest + validator (inventory self-check, mandatory invariants, live-gate stripping, suite safety classes) | `load_manifest` validates test-dir inventory; ALL_LIVE_GATES stripped per child run — verified §17/§18 |
| Mode authority UI (launcher, transition, environment bar, mismatch messaging) | §6/§7/§13 — truthful, persistent, keyboard-accessible |
| Typed paper draft flow (versioned router-state carry, fingerprint-gated preview, placeholder notes) | §8 |
| Backend-authoritative portfolio values | §9 |
| Market-data freshness vocabulary (epistemic_class, readiness blocks, provider health lag) | §6/§13 |
| Existing safety regression suites (mandatory invariants: PIT, offline denial, credential redaction, fail-closed admission, quota) | manifest §mandatory_invariants; WS04 21-test FAST |
| Docs authority hierarchy + link validator | §20 DOC-001/DOC-006 (162/162 OK) |
| UI bundle budget gate (203KB gzip / 500KB chunk) | §23 PERF-002 |
| Dashboard compact-metrics + exceptions behavior | §7 |
| Monorepo guardrails CI + history ledger | §18/§22 |
| Offline/live separation in validation child environments | §18 (`_child_environment` strips ALL_LIVE_GATES) |

## 28. WS06 inputs to WS07

Ordered by dependency (WS07 master reconciliation consumes):

1. **ARCHITECTURE (carried):** AB-001..008, ARCH-001..011, SAFE-001..004,
   TRD-001..009, MA-001..006 (06) + Target Architecture vNext (11).
2. **PRODUCT:** product-surface matrix (§3) — 6 authorized domains MISSING as
   user surface; lane/route matrix (§4); multi-asset UX readiness (shared
   shell + specialized modules, no silos); instrument-selector requirement
   (asset-aware, per §10 of the controller brief: equity symbol input is
   insufficient for options contracts/futures contracts/bonds/crypto pairs).
3. **FRONTEND:** query-key factory with mode/account scope (UX-009);
   shared/API-contract generation (UX-011); route↔registry drift guard
   (UX-007); market-context lane wiring or archive (API-004/DEL-02).
4. **API:** canonical error taxonomy (API-004); dead-endpoint register
   (§25); CORS tighten (API-002); `src`→`tools` inversion note (API-001).
5. **TESTING:** `validate changed` corrections (§17); E2E strategy decision
   (TEST-001 — no real E2E exists, §18a); per-suite slow-test split
   candidates (PERF-001); safety-coverage gap closure (TEST-002);
   accessibility test additions (modal focus, chart alternatives — ACC-001).
6. **DEVELOPER SYSTEM:** canonical edit-tree statement in AGENTS.md
   (DEV-003); `imp.py env` exit-code policy (DEV-004); handoff-file
   consolidation (DEV-005); rules de-duplication (DEV-006).
7. **DOCS:** donor-governance supersession headers (DOC-003, Wave 1);
   MASTER_ROADMAP refresh (DOC-005); ADR canonical owner (DOC-004).
8. **DEPS/REPO:** snapshot refresh guard (REPO-001); artifact cleanup
   (REPO-002/DEL-03); STALE CI copies (REPO-003/DEL-04); Mongo/pymongo
   optionality decision (DEP-001/DEL-07).
9. **PERF/OPS:** full-validation split candidates (PERF-001); runtime L2
   throughput capacity plan for the IB adapter (PERF-003 — FUTURE CAPACITY
   RISK, not optimization); operator next_action surfacing (OPS-002).

## Appendix — API inventory (compact)

Route families (all under `ui_api/server.py`): `/context`, `/attention`,
`/capabilities`, `/instruments/{id}/overview`, `/instruments/{id}/capabilities`,
`/market-state/{id}`, `/symbols/search`, `/explain/{ref}`, `/inspect/{ref}`,
`/replay/session` (+POST `/replay/scrub`), `/research/{analytics,models,
simulation}`, `/workspace/{symbol}/{lane}` × 11 (+`/market-context` — dead
candidate), `/explore/{squeeze, squeeze/scanner, futures, catalyst}`,
`/paper/{sessions, sessions/close, orders, orders/preview, orders/cancel,
order-history, portfolio, trace, strategy-profitability, account*, positions*,
fills*, risk*, broker/*}` (* = dead candidates), `/canary/*` × 10,
`/operator/*` × 10, `/discover/*` × 3 (+ mixed × 2), `/captures` +
`/captures/replay`, `/provider/health` (+ `/provider/finviz/health`),
`/assistant/*` × 5, `/auth/*` × 3, `/security/readiness`, `/state/startup`,
`/accounts`, `/subscriptions` (+ `/subscriptions/release`). ~90 routes;
classification in §14/§15. Full per-route table (method/path/purpose/caller/
domain/status) is recorded in this file's register above; a machine-readable
list can be regenerated from `server.py` at WS07.

## Workflow matrix (core traces, §5 of the controller brief)

| Workflow | Status | Handoff note |
|---|---|---|
| Launch → choose mode → workspace → research → draft → preview → submit → monitor → portfolio | FULL (Paper) | workspace is canonical submit boundary; refresh drops draft state (UX-005) |
| Short Squeeze → Workspace | WORKS (read-only) | squeeze lane + explore scanner; bridge :8787 not running (skips) |
| CVD → Workspace | WORKS (fixture/research) | live path gated; IBKR L1/L2 missing (AB-002) |
| Options → Workspace | WORKS (fixture/research) | no live chain (WS05) |
| Futures → Workspace | WORKS (fixture/research) | no live runtime (WS05) |
| Whale evidence → Research/Opportunity | PARTIAL | participant lanes exist; fusion exposure in UI minimal (opportunity_snapshot in squeeze lane only) |
| Market Context → Research/Decision | BROKEN HANDOFF | backend engine exists; no UI lane (API-004/DEL-02) |
| Government/Industry/Bonds/Crypto/Gold/Silver/Commodities → any workflow | MISSING | no surface (§3) |