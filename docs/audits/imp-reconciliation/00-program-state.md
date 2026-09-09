# 00 — Program State

| Field | Value |
|---|---|
| Program | IMP Reconciliation Program v2 (controller prompt, 2026-09-06) |
| Current workstream | **G15 closed 2026-09-09** — Browser/process product acceptance (Playwright E2E), validation performance measured, dead-route census + archive-first deprecation; E2E **6/0/0/0** + Playwright **10/10**; CHANGED **3857/48/0/0**; FULL **4392/48/0/0**; UI **454** Vitest · bundle **202.94 KiB gzip**; BL-0701 lane keys **still deferred**. Prior: **G14 closed 2026-09-09**. |
| Completed workstreams | BOOTSTRAP (2026-09-06) · WS01 — Source and Provenance Registry (2026-09-06) · WS02 — Scope Authority Reconstruction (2026-09-06) · WS03 — Donor-to-IMP Integration Forensics (2026-09-06) · WS04 — Current-State, Runtime Reality, and Verified Completion Audit (2026-09-06/07) · WS05 — Architecture, Safety, Trading Correctness, and Multi-Asset Target-Fit Audit (2026-09-07) · WS06 — Product Surface, Frontend, API, Testing, Developer-System, Documentation, Dependency, Performance, and Repository Audit (2026-09-07) · **WS07 — Master Reconciliation, Target Architecture Finalization, Backlog, Deletion/Consolidation Plan, and Dependency-Aware Recovery Roadmap (2026-09-07)** |
| Source registry status | COMPLETE (WS01) — [01-source-registry.md](01-source-registry.md) |
| Scope authority status | COMPLETE (WS02) — [02-scope-authority-ledger.md](02-scope-authority-ledger.md) + [02a-original-scope-image-index.md](02a-original-scope-image-index.md) |
| Integration map status | COMPLETE (WS03) — [03-donor-integration-map.md](03-donor-integration-map.md) (17 INT rows, fixture registry, provider coupling, dependency graph, debt TD-P1..P7). WS04 corrected one provenance record: IBKR observational tooling (`tools/ibkr`, 8/24) was present but unrecorded (05 §6) |
| Donor integrations traced | 17 (INT-001..017) |
| Mistaken donor integrations confirmed | GridIQ: patterns only, independent PORT_ADAPT (KEEP code; re-annotate governance); DS-340W: zero code/test influence |
| Authorized donor integrations confirmed | CVD formulas+fixture (INT-005/006), Options lane+fixture+bridge (INT-007/008/009), futuresX patterns (INT-010), squeeze bridge/gates (INT-014/015) |
| Not-integrated donors | Claude Code News (NOT_YET_INTEGRATED), futuresX IBKR runtime, DS-340W (docs-only), GridIQ runtime (n/a) |
| Native replacements required | 0 (GridIQ-derived implementation already independent) |
| Removal candidates | 0 code artifacts; governance re-annotation only (WS07 Wave 1) |
| P0 findings | 0 through WS04 |
| P1 findings | WS04: 2 (P1-1 IBKR L1/L2 CVD data integration missing; P1-2 equity-only portfolio/risk model blocks multi-asset lanes). WS05: 3 P1 architecture findings (ARCH-001 IB L1/L2 adapter missing; ARCH-002 equity-only portfolio/risk; ARCH-003 snapshot-only L2 book — 06 §63). Prior: WS01 items (donor remnant trees; SS snapshot lag) + WS03 items (IB L1/L2 adapter missing for CVD; donor governance docs pre-date Heller correction (TD-P1); `donor_patterns` naming debt (TD-P2/P3)) |
| Architecture findings | WS05: ARCH-001..011 (06 §63) — P0: 0 · P1: 3 · P2: 5 · P3: 3 |
| P0 architecture findings | 0 |
| P1 architecture findings | 3 (ARCH-001/002/003) |
| Safety findings | WS05: SAFE-001..004 (06 §63) — P0: 0 · P2: 2 · P3: 2 |
| Trading correctness findings | WS05: TRD-001..009 (P2: 001/002/003/006/007 · P3: 004/005/008/009) |
| Multi-asset blockers | WS05: MA-001..006 + blocker register AB-001..008 (06 §60/§63) |
| KEEP_AS_IS architectures | WS05 verified (06 §59): operational identity, mode authority + env gates, paper event-sourced ledger + SQLite recovery, market-data envelope/admission/timestamps, Q-series formulas, futures contract/roll/continuous, option contracts, cross-lane evidence/fusion, participant evidence envelopes, FRED vintages, provider capability contracts, IBKR observational client (adapter seed), storage/dataset cache, validation system |
| ADR candidates | WS05: ADR-C-001..010 (06 §61) — inputs to WS07 |
| Target architecture status | WS05 PRELIMINARY Target Architecture vNext — [11-target-architecture.md](11-target-architecture.md); WS07 reconciles with product/engineering findings |
| Open decisions | 18 (see [14-open-decisions.md](14-open-decisions.md)); D5 RESOLVED; D17/D18 added; D19 recommended SEED (WS05); D3/D16 shape recommended (WS05) |
| Validation state | WS04 fresh baseline in [15-validation-evidence.md](15-validation-evidence.md): FAST 21 passed; FULL **3580 tests, 48 skipped, 1 failure (excluded dirty-tree `cross_lane` golden), 0 errors in 451s**; UI 438 passed; typecheck clean. Historical ~2209/1/92 claim superseded (08 FC-01). WS05 used the WS04 baseline (no reruns needed); targeted source-evidence greps recorded in 15 |
| Recommended next workstream | **G8 closed** — next increment per recovery roadmap is **not started** (do not begin G9 in this working tree) |
| Reconciliation status | **COMPLETE (WS07)** |
| Final target architecture | **FINAL (11 §13)** |
| Master backlog | **READY (12)** — 68 items (P0 0 · P1 3 · P2 25 · P3 40 · P4 0) |
| Recovery roadmap | **READY (13)** — 10 waves + dependency graph |
| Deletion plan | **READY (17 §1)** |
| Consolidation plan | **READY (17 §3)** |
| Completion scorecard | **READY (18)** |
| Open decisions | **7 OPEN** (D3/D16, D11, D13, D14, D15, D20 — product/evidence-dependent); 22 resolved/recommended |
| P0/P1/P2/P3/P4 backlog | 0 / 3 / 25 / 40 / 0 |
| Exact next implementation goal | **G8 closed 2026-09-08** (IBKR runtime convergence + src→tools dependency correction); G7/G6/G5 retained; G9 not started |
| Validation state | **G8 closed** — FAST 21/0/0/0; focused G8 **74**; ibkr **63**; providers **257**; market_data **104**; order_flow **148**; xa01 **72**; trading_correctness **122**; G5 order_book **82**; G6 ibkr_observational **91**; G7 **39**; CHANGED **3686/48/0/0**; FULL **4209/48/0/0** reused (+12 new tests proven in CHANGED). LIVE_PROVIDER_UNVERIFIED |
| Confirmed source count | 11 (SRC-001 … SRC-011) |
| Known mistaken donor count | 2 (SRC-001 DS-340W, SRC-002 GridIQ — Lucas Heller) |
| Authorized donor count | 3 confirmed (SRC-003 CVD, SRC-004 Options, SRC-006 Future) + 1 candidate (SRC-005 Eric futuresX) |
| Unverified source count | 1 (SRC-007 L1VolumeBubble — absent locally, no authorization evidence) |
| Original project source count | 4 (SRC-008..011) |
| Tier A image evidence | 7/7 inventoried, 7/7 readable via OCR; index in 02a (0 unreadable; IMG-007 partial) |
| Original requirement IDs | ORG-001..003 (MODERATE confidence; original proposal body not fully in image set) |
| Later professor requirement IDs | LATER-001..013 (verbatim quotes in 02) |
| Current user mandate IDs | MND-001..008 (Bonds, Crypto, Whale, Industry, Government, Gold, Silver, Commodities) |
| P0 findings | 0 raised through WS02 (scope workstreams only) |
| P1 findings | 4: WS01 items (donor remnant trees; GridIQ port `6adeeec`; SS snapshot lag) + WS02 item (mandated-domain details mostly DETAILS_TO_BE_DEFINED — D14) |
| Open decisions | 16 (see [14-open-decisions.md](14-open-decisions.md)); M1 CLOSED_WITH_LIMITATION (images supplied & processed) |
| Validation state | WS01/WS02 evidence in [15-validation-evidence.md](15-validation-evidence.md) (read-only; OCR runs recorded) |
| Recommended next workstream | **WS03 — Donor-to-IMP Integration Forensics** (uses the completed registry + scope ledger as canonical; must not reclassify legitimate later additions as drift) |

## Repository truth (captured 2026-09-06, unchanged from bootstrap)

- Parent workspace root: `C:\Users\adame\Desktop\market-trading-platform\`
  (this repository). Public repo `AdamEddahmouni/market-trading-platform`.
- Parent branch: `hardening/sprint-1-3-honesty` @ `d691050`.
- Canonical IMP tree in the monorepo: `projects/integrated-market-platform/`
  (tracked snapshot; parent CI `.github/workflows/imp-validate.yml`,
  `imp-python.yml` with `working-directory: projects/integrated-market-platform`).
- Child repo `integrated-market-platform/` (own `.git`, branch `main` @
  `072e62e`, remote → archived `integrated-market-intelligence-platform.git`)
  is in sync with the snapshot (only `__pycache__` bytes differ).
- Other governed child trees (own `.git`): `short-squeeze-project/` (branch
  `fix/frozen-followups` @ `9de7b2f`, clean), `governed-ticker-metadata-enrichment/`
  (`feat/governed-ticker-metadata-enrichment` @ `1398da3`),
  `equity-data-v1-worktree/` (`feat/equity-data-v1` @ `ad54fb8`); snapshots
  under `projects/` per `workspace-manifest.json` (GTM and EQ match; SS lags —
  see P1 finding 3).

## Dirty / untracked state (unchanged, left untouched)

| Path | Kind | Note |
|---|---|---|
| `projects/integrated-market-platform/src/market_platform_foundation/cross_lane/fusion.py` | M | Pre-existing main-workspace modification, excluded from audit baseline |
| `projects/integrated-market-platform/src/market_platform_foundation/cross_lane/opportunity.py` | M | Same |
| `projects/integrated-market-platform/artifacts/developer-workflow/formula-hardening-changed-explain.json` | ?? | Formula-hardening evidence artifact |
| `Claude Code News/` | ?? | AUTHORIZED_FUTURE_DONOR material (Lucas Bichara); full source present; `node_modules/` present (hygiene item D7) |
| `docs/audits/` | ?? | This audit workspace (canonical program record) |

## Prior forensic run state (reconciled, not replaced)

- Worktree: `.worktrees/imp-forensic-reconciliation/`, branch
  `codex/imp-forensic-reconciliation` @ `d691050`.
- Prior planning scratch (untracked, worktree-local):
  `projects/integrated-market-platform/.planning/2026-09-06-forensic-reconciliation/`.
  Phase 1 was in progress; nothing committed. Facts carried into
  15-validation-evidence. This workspace is the canonical program record; the
  `.planning/` files remain scratch history (not migrated, not deleted).

## Key WS01 findings (evidence in 01-source-registry.md)

1. Donor local trees SRC-002/003/004/005 are INCOMPLETE REMNANTS (source code
   absent; artifacts only). SRC-006 (Claude Code News) arrived complete.
2. External repos verified (HTTP 200): lucasheller22 GridIQ + DS-340W,
   RumiaKitinari tradingCVDBubble, Strzalaa internship-project. SRC-005/006/007
   external origins unknown.
3. Git history contains donor-integration commits: `6adeeec` (GridIQ port),
   `4dc6ca0` (CVD NVDA fixture), `3fe0b96` (donor bridge lanes), `d169cb8`
   (donor integration lanes), `68d0069`/`64cb64e`/`db3a7fb` (revision-3 donor
   governance) — WS03 trace anchors.
4. Existing donor governance is partly stale: permissions record predates the
   Heller correction; reuse matrix cites donor files absent locally. Both
   preserved, flagged superseded in 01.
5. Future sources (SRC-005/006): SEPARATE_FUTURE_STRATEGIES at source level
   (Tradovate+Node news-trader vs IBKR+Python L2 research); complementary
   roles possible; no shared lineage evidenced.
6. Professor guidance stands: CVD/Level2 requires IB L1+L2 (SRC-003);
   Short Squeeze + CVD/Level2 + Options + Future are authorized streams.

## WS04 completion summary (2026-09-06/07)

- **Fresh validation baseline established** (M6/M7 CLOSED): env + FAST (21 passed)
  + FULL (3580 tests, 48 skipped, 1 failure, 0 errors, 451s; sole failure is the
  pre-existing dirty `cross_lane` golden test excluded from baseline) + UI (438
  passed, typecheck clean) + domain runs (options 583, futures 526, order-flow
  539, short-intelligence 64, participant 503, sec 37, macro 304, energy 324,
  ui 759, core 2808 — all 0 errors). Historical ~2209/1/92 claim reproduced and
  classified (08 FC-01): it was the 09-02 dirty-tree baseline, honestly labeled
  BLOCKED, superseded since 09-04.
- **Every authorized major capability classified** (05 matrix; 04 summary):
  Platform foundation COMPLETE_VERIFIED (V3); market data / Demo-Paper-Live /
  API COMPLETE_UNVERIFIED (live paths gated); Short Squeeze, CVD/L1/L2, Options,
  Futures, Whale, Government, Research, Analytics, Portfolio, Multi-account,
  Trading, Risk, UX all PARTIAL; Bonds/Crypto/Gold/Silver/Industry MISSING;
  Commodities PARTIAL (energy groundwork) / MISSING (domain).
- **CVD/L1/L2 reality stated explicitly**: formulas + NVDA/ES fixtures
  COMPLETE_VERIFIED_FOR_REPLAY; live Moomoo observational CVD path exists but is
  gated/unverified; **professor-required IBKR L1/L2 runtime data integration is
  MISSING (P1-1)** — observational L1 tooling exists (8/24, corrected provenance)
  with no depth and no CVD wiring.
- **Provider reality**: all providers CONFIGURED+IMPLEMENTED+TESTED with live
  gates closed; no RUNTIME_VERIFIED wire; Tradier wire FIXTURE_ONLY; IBKR L2
  absent; crypto/bond providers absent.
- **Completion metrics** (04 §10): implementation presence ~76%, functionally
  verified ~67%, authorized-scope completion ~50%, production readiness ~29%,
  product maturity ~40%, engineering-system maturity ~90% (all MODERATE/HIGH
  confidence).
- **P0: 0. P1: 2** (P1-1 IBKR L1/L2 CVD integration; P1-2 equity-only
  portfolio/risk model). Missing-scope register ranked (04 §7); KEEP_AS_IS
  register populated (04 §9); false-completion register populated (08, 16 rows).
- **Key corrections**: WS03 provenance map missed the IBKR observational tooling
  (05 §6); MASTER_ROADMAP predates the mandate (new domains absent — MS-13).

## WS06 completion summary (2026-09-07)

- **WS06 = COMPLETE.** Full audit file: [07-product-engineering.md](07-product-engineering.md).
- **Product-surface matrix populated** (07 §3): Dashboard FULL (approved compact+exceptions preserved); Portfolio FULL (equity/Paper); Trading Workspace PARTIAL (Paper full, Demo/Live read-only); Orders PARTIAL; Research/Analytics READ_ONLY; Short Squeeze/CVD-L2/Options/Futures PARTIAL (RESEARCH_ONLY, fixture-based); Whale PARTIAL (read-only lanes); **Bonds/Crypto/Gold/Silver/Commodities/Industry MISSING (no user surface)**; Government backend-only (no workflow).
- **Frontend**: route matrix complete; 184 components, 11-lane registry; draft-carry typed + fingerprint-gated (approved behavior preserved); query keys NOT mode-scoped (UX-009 P2 recommendation); 2,000-line manual Zod layer with passthrough erosion (UX-011 P2); no fixture data masquerading as live (truthfulness verified); dashboard compactness verified; accessibility gaps = modal focus trap + chart alternatives (ACC-001).
- **API**: ~90 routes inventoried; dead-candidate register (DEL-01..07): `/paper/{account,positions,fills,risk,orders-GET}`, `/workspace/:symbol/market-context` (no lane), `/capabilities` (duplicate of context); error taxonomy ad-hoc (API-004 P2); `src`→`tools` inversion + unbounded CORS (P3).
- **Testing**: backend 3580 deep; UI 438/85 files, no real E2E (TEST-001 P2); safety coverage marks recorded (07 §18a); **`validate changed` under-selection PROVEN in 3 ways** (07 §17 / FC-18): monorepo `projects/` prefix → 21 tests only; fixtures/config/test-fixtures → zero suites; shared modules → blunt core escalation; `full_suite_required` mislabeled (FC-19).
- **Developer system**: canonical commands verified + telemetry analyzed (validate domain 22 runs/2463s dominant); `imp.py env` informational-only (DEV-004); edit-tree ambiguity = #1 fresh-developer friction (DEV-003 P2); CI/local/closure converge (CI strips `projects/` prefix → unaffected by under-selection); child-repo CI copies STALE-labeled.
- **Documentation**: authority hierarchy KEEP; **zero production-ready claims found**; donor-governance supersession scope enumerated (DOC-003, 9+ docs, WS07 Wave 1); docs links 162/162 OK (rerun); ADR triplication (DOC-004).
- **Dependencies**: Python core stdlib-only + numpy/sklearn (justified) + pymongo/ib_insync/anthropic optional; Node all-used, no unused majors; two chart libs coexist (keep).
- **Repository**: SS snapshot lag CONFIRMED stale (REPO-001 P2, three truths); empty pytest dirs + STALE CI copies = cleanup candidates; donor remnants untouched (read-only).
- **Performance**: MEASURED 451s FULL dominated by platform 106s / donor_bridge 83.5s / ui1 79.2s; UI build gated by 203KB gzip budget (KEEP); L2 runtime throughput PERFORMANCE_UNVERIFIED (FUTURE CAPACITY RISK, no live adapter).
- **Deletion candidates**: DEL-01..07 (none deleted). **Consolidation candidates**: CON-01..10. **KEEP_AS_IS register**: 12 verified areas (07 §27).
- **Severity**: P0 0 · P1 0 new (WS05 P1s stand) · P2 15 · P3 24 across UX/API/TEST/DEV/DOC/DEP/REPO/PERF/OPS (07 findings + TD-UE*/AP*/TS*/DV*/DO*/DP*/RP*/PF*/OP* debt rows in 10).
- **Tech-debt updated** (10: TD-UE1..OP1, root causes only); **false-completion updated** (08: FC-17 market-context unreachable, FC-18 validate-changed, FC-19 flag mislabel); **capability matrix updated** (05: product-surface fields, no re-scoring); **open decisions updated** (14: D7 closed, D10/D12 statused, D21..D29 added, D23..D28 engineering-recommended).
- No code changed; no deletions; no remediation begun. WS06 closure criteria met (controller §102) — see 07.

## WS05 completion summary (2026-09-07)

- **WS05 = COMPLETE.** Canonical domain ownership matrix populated (06 §3);
  multi-asset identity assessed (MULTI_ASSET_PARTIAL — kernel strong, runtime
  boundary equity-defaulting); operational identity/accounts/modes verified
  (identity + account-scoped cache keys + process-level mode authority =
  KEEP_AS_IS); Demo/Paper/Live assessed CORRECT at backend (no crossover
  plausible; frontend lane query keys not mode-scoped, P3); provider
  architecture PARTIAL (capability Protocols + composition correct; IBKR L1/L2
  CVD adapter absent, P1); IBKR target architecture defined (one adapter,
  separated market-data/execution sessions, seeded from `tools/ibkr`, D19
  RECOMMENDED); Tradovate/CCN target fit assessed (bracket semantics
  product-relevant, browser-driven execution not canonical); market-data
  envelope/admission/timestamp architecture CORRECT with two gaps (depth
  staleness, CVD session anchors); CVD math CORRECT_WITH_LIMITATIONS;
  Level-2 book snapshot-only = P1 (ARCH-003); Options/Futures contract models
  KEEP_AND_HARDEN; Bonds/Crypto/Gold/Silver/Commodities readiness assessed
  (identity extensions, shared primitives, no silos); portfolio BLOCKING for
  multi-asset (P1-2); order lifecycle PARTIALLY_CORRECT (preview binding
  TRD-001, replace absent, partial fills one-shot); risk PARTIAL (buying
  power DISPLAY_ONLY); cross-lane fusion KEEP_AS_IS (dirty-tree state
  environmental); formula ownership mapped (options-ledger float exception);
  numeric precision classified (int minor-units equity; float gaps flagged);
  cache/query-key/frontend-state assessed; API/error contracts PARTIAL;
  reliability/recovery/concurrency assessed (single-process assumptions
  documented); observability/secrets clean (no exposure); KEEP_AS_IS register
  verified; blocker register AB-001..008; ADR candidates ADR-C-001..010;
  Target Architecture vNext drafted (11). No code changed; no P0 containment
  required.

## WS03 completion summary (2026-09-06) All donor-derived components are independent
  reimplementations (PORT_ADAPT) with honest docstrings.
- **GridIQ**: pattern port under ADR-GRIDIQ-001 (8/16) → dataset projection/cache
  subsystem, assistant audit store, UI patterns; independent implementation, zero
  donor identifiers → KEEP code, re-annotate governance.
- **DS-340W**: zero code/test influence (docs-only).
- **CVD/Options/futuresX**: authorized concept integration (`donor_patterns/`
  lane formulas) + research-only admitted fixtures; paid donor providers never
  adopted; no provider leakage (Unusual Whales/iVolatility/Topstep/Gemini = 0).
- **Claude Code News**: NOT_YET_INTEGRATED.
- **IBKR**: no client in IMP; CVD L1/L2 runtime adapter is MISSING authorized
  capability (WS04/WS05).
- Full evidence: 03-donor-integration-map.md; debt: 10-technical-debt.md (TD-P1..P7).

## Missing evidence (full list in 14-open-decisions.md)

- Original project-goal screenshots (Tier A) — pending from Adam (blocks WS02).
- Professor brief / meeting transcript — personal files kept OUT of repo.
- DS-340W and L1VolumeBubble trees absent locally (external DS-340W verified).
- SRC-005 / SRC-006 external origins unknown; Claude Code News authorship unproven.

## WS07 completion summary (2026-09-07)

- **WS07 = COMPLETE. Reconciliation status: COMPLETE.** Files: [16-root-cause-register.md](16-root-cause-register.md) (20 RC), [12-master-backlog.md](12-master-backlog.md) (68 items), [13-recovery-roadmap.md](13-recovery-roadmap.md) (10 waves + dependency graph), [17-deletion-consolidation-plan.md](17-deletion-consolidation-plan.md), [18-completion-scorecard.md](18-completion-scorecard.md), [19-goal-increment-plan.md](19-goal-increment-plan.md) (11 increments + exact G0); [11-target-architecture.md](11-target-architecture.md) finalized (§13); registers reconciled below.
- **Final target architecture: FINAL.** Master backlog: READY. Recovery roadmap: READY. Deletion plan: READY. Consolidation plan: READY. Completion scorecard: READY.
- **Open decisions: 7 remain open or product-dependent** (D3/D16 provider choice, D11 author unknown, D13 IB purchase, D14 domain details, D15 proposal screenshots, D20 family elevation); D2/D17/D18/D19/D21..D29 resolved or recommended in 14.
- **Backlog: P0 0 · P1 3 (BL-0105 multi-asset portfolio, BL-0301 IBKR adapter, BL-0302 depth engine) · P2 25 · P3 40 · P4 0** (68 items; 12 §summary).
- **Completion (18):** IMPLEMENTATION_PRESENCE ~76% (MODERATE) · FUNCTIONALLY_VERIFIED ~67% (MODERATE) · AUTHORIZED_SCOPE ~50% (MODERATE) · ARCHITECTURAL_READINESS ~55% (MODERATE) · PRODUCT_SURFACE ~40% (MODERATE) · PRODUCTION_READINESS ~29% (MODERATE) · ENGINEERING_SYSTEM_MATURITY ~90% (HIGH).
- **Root causes:** 20 (RC-001..020); every WS04/WS05/WS06 finding owns exactly one RC; AB-001..003 → RC-001/002/003.
- **Exact next implementation goal: G2 — Canonical Multi-Asset Portfolio Foundation** (BL-0105) — full description in [19-goal-increment-plan.md](19-goal-increment-plan.md) §5; identity prerequisite (G1) is executed and evidenced in 15 (G1 section).
- **Validation state:** unchanged (WS04 fresh baseline 3580/48/1-excluded/0 stands; WS07 ran no product validation — planning-only, targeted reads recorded in 15).
- **No code changed in WS07**; no deletions; no remediation begun.

## Execution discipline (standing)

- Baseline for isolated audit work: parent `d691050`.
- Preserve unrelated dirty-tree work; never reset/clean/stash/copy it.
- No broad remediation during discovery phases.
- Do not modify donor trees (read-only inspection only).
- Every conclusion: evidence + confidence label; unresolved → 14-open-decisions.