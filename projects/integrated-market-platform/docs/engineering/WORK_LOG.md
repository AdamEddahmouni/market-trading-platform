# IMP Work Log

> **Donor-era entries: SUPERSEDED — HISTORICAL · AUTHORIZATION BASIS SUPERSEDED**
>
> Entries from the donor era (2026-08-14 through the correction) predate the
> professor's donor-identity correction (2026-08-28): Lucas Heller's DS-340W
> and GridIQ materials were **not** intended donor sources for this platform.
> Any native IMP implementation independently reimplemented from a legitimate
> platform requirement remains valid. Donor-era entries are preserved for
> provenance only and must not be used as authorization for future
> implementation.

Chronological record of implementation work on the Integrated Market Platform. Agents and contributors **must append an entry here automatically** after completing substantive changes — no user prompt required (see [AGENTS.md](../../AGENTS.md) and `.cursor/rules/work-logging.mdc`, `alwaysApply: true`).

## How to add an entry

Append a new section at the **top** of [Entries](#entries) (newest first). Use this template:

```markdown
## YYYY-MM-DD — Short title

| Field | Value |
|-------|-------|
| **Status** | `complete` \| `in-progress` \| `planned` |
| **Area** | e.g. `ui/now`, `ui/portfolio`, `ui/workspace`, `backend`, `docs` |
| **Summary** | 1–3 sentences: what changed and why |
| **Key files** | Bullet list of created/modified/deleted paths |
| **Tests** | What was run and result (e.g. `ui: vitest 177 passed`, `build: pass`) |
| **Related** | Links to plans, specs, or prior log entries |
| **Notes** | Optional: follow-ups, known limits, deferred items |
```

For large features, also add or update a completion note under `docs/superpowers/plans/` when a formal plan exists.

---

## Entries

## 2026-09-19 — Weekend Lane L opportunity pipeline provenance

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `intelligence/opportunity`, `ui_api/opportunity_projections` |
| **Summary** | Live ranked-row freshness no longer treats `OpportunityV1.created_at` or leftover fixture `as_of` as a receive clock. Missing live receive is `NOT_APPLICABLE` / `LIVE_AS_OF_UNAVAILABLE` (not `FRESH`). Attention ingest rows stay `accepted=false` when eligibility is `UNAVAILABLE`. Operator feed still withholds unclocked live rows. |
| **Key files** | `src/market_platform_foundation/intelligence/opportunity/freshness.py`, `ingest.py`, `ui_api/opportunity_projections.py`, `docs/architecture/DATA_CONTRACTS.md`, tests for freshness/ingest/opportunity API |
| **Tests** | `python -m unittest` 6 pipeline modules **74 passed**; `python tools/imp.py validate changed` **3792 passed, 42 skipped, 0 failures** |
| **Related** | [DATA_CONTRACTS.md](../architecture/DATA_CONTRACTS.md) |
| **Notes** | **CALENDAR:** Item 9 `2/3` `NOT_CALIBRATED` — no collection this lane. **ENGINEERING:** remaining pipeline gaps (attention `OPEN_WORKSPACE` vs `UNAVAILABLE` eligibility; event vs receive lag not on Radar cards; live receive used as both as_of and last_source when a clock exists). No Item 9, Live, Full30, #222, collector, Radar UI, Control, or `snapshot.py` edits. Merged `origin/main` `61ea8110` (#304) keep-both. |

## 2026-09-19 — Monday Item 9 preflight: composed GO (review)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs/engineering` |
| **Summary** | Review fix on [#304](https://github.com/AdamEddahmouni/market-trading-platform/pull/304): Monday step 4 is composed GO from the software `item9 next-rth-preflight` JSON. Do **not** require CLI `READY_TO_COLLECT` from frozen `fed2d9f7` (no `item9` group). `WRONG_RUNTIME` must not send operators to retarget CURRENT_MAIN onto `.imp-actual-01-phase-d`. `--poll` starts only from frozen `opend_bar_1m_prospective_proof.py` after RTH / SHA / collectors=0 / OpenD / Live OFF. |
| **Key files** | `docs/engineering/MONDAY_ITEM9_PREFLIGHT.md`; this log |
| **Tests** | Docs-only review edit; no `--poll`. Frozen collector not mutated. |
| **Related** | [MONDAY_ITEM9_PREFLIGHT.md](MONDAY_ITEM9_PREFLIGHT.md); PR [#304](https://github.com/AdamEddahmouni/market-trading-platform/pull/304) |
| **Notes** | Merged `origin/main` `b1b3f7e8` (#302) keep-both WORK_LOG. `121031` still forbidden. Item 9 **2/3 IDLE**. Live OFF. PR #222 unmerged. |

## 2026-09-19 — Monday Item 9 preflight runbook (no collection)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs/engineering` |
| **Summary** | Added [MONDAY_ITEM9_PREFLIGHT.md](MONDAY_ITEM9_PREFLIGHT.md) so Monday 2026-09-21 Item 9 Mode B is mechanical: frozen collector `.imp-actual-01-phase-d` @ `fed2d9f7`, read-only preflight, `$rcpt` corpus-status, Live OFF, `121031` backfill forbidden, 2/3 IDLE not DEGRADED, READY_TO_COLLECT vs wait. Points at PROGRAM_STATUS for mutable `origin/main`. Does **not** start `--poll`, calibrate, run Full30, enable Live, or merge #222. |
| **Key files** | `docs/engineering/MONDAY_ITEM9_PREFLIGHT.md`; pointer in `docs/engineering/NEXT_RTH_CAMPAIGN_RUNBOOK.md`; `docs/README.md`; this log |
| **Tests** | `python tools/imp.py env` (healthy; linked venv); `python tools/check_docs_links.py` (251 files OK); `python tools/imp.py test focused` Item9NextRthPreflightTests **8/8**; read-only `item9 next-rth-preflight --json` from this software worktree (`WRONG_RUNTIME`, `rth_active=false`, `active_collector.detected=false`, `does_not_start_collector=true`); corpus-status on frozen `$rcpt` **2/3** `NOT_CALIBRATED`. No `--poll`. |
| **Related** | [NEXT_RTH_CAMPAIGN_RUNBOOK.md](NEXT_RTH_CAMPAIGN_RUNBOOK.md); [IMP_POST_RTH_CLOSE_08_LANE_G.md](IMP_POST_RTH_CLOSE_08_LANE_G.md); PR #294 owns PROGRAM_STATUS CURRENT_MAIN churn |
| **Notes** | Frozen collector worktree not mutated. `ACTIVE_COLLECTORS` inspect-only. |

## 2026-09-19 — Lane K: unique Research Evidence tab name

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui/research` |
| **Summary** | Claim-graph and hop links now use accessible names `Follow <node>` so the Research section tab `Evidence` stays uniquely queryable. Visible hop copy is unchanged. App.test queries the Evidence tab inside `Research sections`. |
| **Key files** | `ui/src/components/research-shared/ResearchClaimGraph.tsx`, `researchPresentation.ts`(+test), `ResearchEvidenceSection.test.tsx`, `App.test.tsx`, `DemoResearchPage.test.tsx` |
| **Tests** | `npm run typecheck` **pass**; `npx vitest run src/App.test.tsx` **74 passed** (includes `navigates Demo Research sections as routes`); research-shared + DemoResearchPage **58 passed**. |
| **Related** | [PR #302](https://github.com/AdamEddahmouni/market-trading-platform/pull/302) validate-ui hold |
| **Notes** | Hypothesis/FTEP remain NOT_EXPOSED; simulation is not a forward test. Did not merge #302. Merged `origin/main` `829316ff` (#299) keep-both. |

## 2026-09-18 — Weekend Wave B Lane G: unit-test env isolation

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `tests` |
| **Summary** | Isolated process-environment leaks so unit tests no longer leave `IMP_FINVIZ_CAPTURE_DIR`, `IMP_PERSIST_STATE`, or `IMP_PAPER_EXECUTION` set for later cases, and stopped pointing Finviz capture roots into the tree. |
| **Key files** | `tests/platform/test_discovery_p33.py`; `tests/finviz/test_finviz_provider.py`; `tests/intelligence/test_ftep_campaign_status.py`; `tests/intelligence/test_build01_22_lifecycle.py`; `tests/intelligence/test_build01_23_lifecycle.py`; `tests/intelligence/test_build01_24_lifecycle.py`; `tests/intelligence/test_paper_execution_qualification.py`; `tests/intelligence/test_paper_execution_governance.py`; `tests/intelligence/test_paper_forward_bridge.py`; `tests/trading_correctness/test_preview_binding.py`; `tests/validation/test_process_env_isolation.py` |
| **Tests** | `python -m unittest` on changed modules **101 passed**; `python tools/imp.py validate changed` **3336 passed**, 31 skipped, 0 fail |
| **Related** | Weekend Wave B Lane G; prior OpenD hermeticity 2026-09-17 |
| **Notes** | Deferred: Lane A snapshot path redaction; Lane D expected-cycle/log paths; tracked `reports/` host paths; `persist_discovery_capture` absolute `artifact_path`; leftover `IMP_PAPER_EXECUTION` leaks outside this increment. No evidence mutation. |

## 2026-09-19 — Weekend Lane H high-value testing coverage

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `tests/platform`, `tests/ui1`, `ui/radar`, `ui/opportunity` |
| **Summary** | Added fail-closed tests at high-value boundaries on landed #295/#296/#300 contracts: Item 9 sample-gate 2/3 insufficient vs 3/3 met without calibration, Live OFF / LIVE_FORBIDDEN, UNKNOWN provider incidents, restart generations, diagnostic redaction, session AUTH_REQUIRED/INVALID, Radar STALE/INELIGIBLE/EXPIRED refusal. No product-code rewrite; did not edit snapshot.py, Control, Lab, Research, or merge #222. |
| **Key files** | Created: `tests/platform/test_weekend_lane_h_high_value_boundaries.py`. Modified: `tests/ui1/test_error_taxonomy.py`; `ui/src/components/opportunity/opportunityEpistemicLayers.test.ts`; `opportunityOperatorBrief.test.ts`; `opportunityPresentation.test.ts`; `ui/src/components/radar/RadarPage.test.tsx`. |
| **Tests** | `python tools/imp.py test focused` 8 selectors **passed 8/0/0**; `.venv python -m unittest` weekend-lane-h + error-taxonomy **25 OK**; vitest opportunity+Radar **43 passed**; `npm run typecheck` **pass**; `python tools/imp.py test affected --workers 2` **PASSED changed: 936 tests, 4 skipped, 0 failures, 0 errors**. |
| **Related** | Landed #295 provider resilience, #296 UI regression, #300 Radar operator brief. |
| **Notes** | Isolated worktree `.worktrees/weekend-lane-h-coverage` on `test/weekend-lane-h-coverage`. Merged `origin/main` `d8a02448` (#301) keep-both. Do not merge #303. Item 9 collection and Live remain off. |

## 2026-09-19 — Weekend Lane K: Research claim navigation

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui/research` |
| **Summary** | Research Overview is now a claim graph (source → hypothesis → strategy → experiment → evidence → contradiction → implementation → forward-test) instead of a gap-list dump. Synthesis sentences and section hops deep-link; `?conflict=1` filters the only contract-backed conflict. Hypothesis/FTEP stay NOT_EXPOSED; simulation is not labeled a forward test; Paper forward tests link to Workspace without fetching them. |
| **Key files** | Created: `ui/src/components/research-shared/ResearchClaimGraph.tsx`. Modified: `researchPresentation.ts`(+test), `ResearchOverviewSection.tsx`(+test), `ResearchEvidenceSection.tsx`(+test), `ResearchValidationSection.tsx`(+test), `ResearchSimulationSection.tsx`(+test), `ResearchSurface.tsx`, `{Demo,Paper,Live}ResearchPage.tsx`, `ui/src/styles/research.css`, `docs/ui-redesign-v2/research-contract-map.md`, `docs/engineering/FRONTEND_GUIDE.md`. |
| **Tests** | `npm run typecheck` **pass**; `npm test --` research-shared + demo/paper/live-research **62 passed / 0 failed**. Browser: Demo `/research` on worktree Vite `127.0.0.1:5298` — claim graph present; Strategy node → `/research/validation` hops; Evidence hops present. (Earlier `:5198` was a different already-bound UI.) |
| **Related** | [research-contract-map.md](../ui-redesign-v2/research-contract-map.md); Weekend Wave C Lane K |
| **Notes** | Did not edit Control, Radar, Lab, `snapshot.py`, or PROGRAM_STATUS. No Item 9 collection, no Full30, no Live, no #222 merge, no collector mutation. Remaining dump-like gaps: Evidence still lists five analytics panels; Validation still shows a full interpretation table; no first-class hypothesis/source-catalog/FTEP endpoints. Merged `origin/main` `d8a02448` (#301 Lab honesty taken as-is; claim graph kept). |

## 2026-09-19 — Lane J Lab honesty refinement

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui/lab`, `docs/ui-redesign-v2` |
| **Summary** | Made Lab a clearer inspectable research/validation workbench: experiment/run IDs stay UNKNOWN, strategy identity and dataset provenance are first-class, recorded parameters and evidence lineage are visible, methodological warnings and a test-vs-forward-test map are explicit, and cost/fill assumptions no longer treat `fill_audit.status` as fill realism. No Lab mutations, no evidence-class upgrades. |
| **Key files** | Created: `ui/src/components/lab-shared/LabFactGrid.tsx`. Modified: `ui/src/components/lab-shared/{labPresentation.ts,LabOverviewSection.tsx,LabValidationSection.tsx,LabSimulationSection.tsx,lab.css}`, `ui/src/components/research-shared/simulationHarnessMetrics.ts`, matching tests, `docs/ui-redesign-v2/lab-contract-map.md`. |
| **Tests** | `npm run typecheck` **pass**; `npx vitest run src/components/lab-shared src/components/research-shared/simulationHarnessMetrics.test.ts` **24 passed / 0 failed**. Browser: Demo `/lab`, `/lab/validation`, `/lab/simulation` on Vite `:5200`. |
| **Related** | [lab-contract-map.md](../ui-redesign-v2/lab-contract-map.md) |
| **Notes** | Isolated worktree `.worktrees/weekend-lane-j-lab` on `ui/weekend-lane-j-lab` from `origin/main` `1f33bf9e` (#295). Remaining honesty gaps: no experiment/run/benchmark/FTEP contracts; many provenance/cost fields stay UNKNOWN until the projection carries them; Lab cannot re-run or change cutoff. No Item 9, Full30, Live, Control, Radar, or `snapshot.py` edits. |

## 2026-09-19 — Lane B review: Live OFF POLICY + Item 9 meaning branch

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui/control` |
| **Summary** | Review fix on #297: Live OFF uses truth class **POLICY** (not **BLOCKED**); BLOCKED stays for real gates such as WRONG_RUNTIME. Item 9 corpus meaning now branches — 2/3 still “needs more dates”, 3/3 says the date gate is complete and does not claim more dates are required. |
| **Key files** | `ui/src/components/control/operatorDiagnosticsPresentation.ts`; `OperatorSystemStatusSection.tsx`; `operatorDiagnosticsPresentation.test.ts`; `ui/src/styles/operator-control.css` |
| **Tests** | `npx tsc --noEmit -p tsconfig.typecheck.json` pass; `node scripts/run-vitest.mjs src/components/control` **50 passed** |
| **Related** | PR [#297](https://github.com/AdamEddahmouni/market-trading-platform/pull/297) |
| **Notes** | Merged `origin/main` @ `1f33bf9e` (#295) first. No collector / Item 9 mutation. |

## 2026-09-18 — Lane B Operator Control UX (trader-readable status)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui/control` |
| **Summary** | Refined Control so a trader can tell waiting vs failure: Item 9 incomplete dates stay **IDLE** (not **DEGRADED**), Live OFF is a policy lock, and diagnostics load errors are labeled as load failures. Canonical tokens remain visible. Did not add a UI route at `/operator/diagnostics` because Vite proxies that path to the API. |
| **Key files** | `ui/src/components/control/OperatorControlCenterPage.tsx`; `ui/src/components/control/OperatorSystemStatusSection.tsx`; `ui/src/components/control/operatorDiagnosticsPresentation.ts`; `ui/src/styles/operator-control.css`; `ui/src/components/control/*.test.ts(x)` |
| **Tests** | `npx tsc --noEmit -p tsconfig.typecheck.json` pass; `node scripts/run-vitest.mjs src/components/control` **49 passed**. Browser: Vite `:5194` Demo Control — load-failure copy, **Live OFF**, **NOT CALIBRATED**, **CALIBRATION FORBIDDEN**; Item 9 **2/3 IDLE** covered by Vitest (API snapshot unavailable in that session). Did not click Restart / collectors. |
| **Related** | `docs/engineering/ACCESSIBILITY.md`; `docs/engineering/OPERATOR_DIAGNOSTICS_MODEL.md` |
| **Notes** | Full `App.test.tsx` showed intermittent lazy-load flakes when run as a heavy suite; Control-focused Vitest is the claimed gate. |

## 2026-09-18 — Radar operator brief (Weekend Lane I)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui/radar` |
| **Summary** | Radar opportunity detail now answers the operator discovery questions from attached fields only (what happened, why shown, freshness, providers, conflicts, inference vs observation, unknowns, invalidation, available action, refusal). Empty conflict/provider/invalidation sets stay `UNKNOWN` instead of “none reported.” Queue rows expose attached providers. No fake live actionability; Demo remains read-only. |
| **Key files** | `ui/src/components/opportunity/opportunityOperatorBrief.ts`; `opportunityOperatorBrief.test.ts`; `opportunityEpistemicLayers.ts`; `opportunityDetailModel.ts`; `ui/src/components/radar/OpportunityDetailCard.tsx`; `RadarQueueTable.tsx`; `RadarPage.test.tsx`; `ui/src/styles/radar.css`; `docs/engineering/FRONTEND_GUIDE.md` |
| **Tests** | `npx vitest run` opportunity brief/epistemic/detail/presentation + `RadarPage.test.tsx`: 43 passed; `npm run typecheck`: pass. Demo Radar on worktree Vite `:5199` against API `:8766`: operator brief present; providers `REPLAY`; conflicts `UNKNOWN`; `live.quotes` UNSUPPORTED. |
| **Related** | [FRONTEND_GUIDE.md](FRONTEND_GUIDE.md); design-principles opportunity 9-field rule |
| **Notes** | Item 9 collection/calibration and Operator Control were not touched. Invalidation criteria remain UNKNOWN unless eligibility, expiry, staleness, supersession, or missing ranking inputs are attached. Branch started at `origin/main` `b16e0bbe`; do not merge. |

## 2026-09-18 — Weekend Lane C UI regression fixes

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui/radar`, `ui/workspace`, `ui/nav`, `ui/diagnostics` |
| **Summary** | Fixed non-Control product defects found in origin/main browser QA: mobile nav backdrop leaked as an unnamed button, provider diagnostics treated loading/error as Live-disabled, Workspace overview assumed Demo replay when `/context` failed, and empty-instrument copy still pointed at retired Explore/Discover routes. Added a tested route error-boundary primitive; it is not wrapped around `LazyBoundary` because that stalls lazy `ImpProductChrome` load. |
| **Key files** | `ui/src/components/imp-product/ImpProductChrome.tsx`, `ui/src/components/live/ProviderHealthPanel.tsx`, `ui/src/components/WorkspaceIndex.tsx`, `ui/src/components/shared/InstrumentSelectionEmpty.tsx`, `ui/src/components/RouteErrorBoundary.tsx` |
| **Tests** | `npx vitest run` ImpProductChrome, InstrumentSelectionEmpty, RouteErrorBoundary, WorkspaceIndex, ProviderHealthPanel, LazyBoundary — **15 passed** (ProviderHealthPanel 4/4 including pre-existing CONNECTED case); `npm run typecheck` — **pass**. Full `App.test.tsx` not re-run (no `App.tsx` change). |
| **Related** | `docs/engineering/FRONTEND_GUIDE.md`, `docs/engineering/ACCESSIBILITY.md` |
| **Notes** | Control inspected only (Lane B). Item 9 2/3 / not calibrated / Live OFF not hidden. Error-boundary wiring around Suspense remains deferred. |

## 2026-09-18 — Lane F provider resilience (offline fixtures)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `providers`, `operations`, `ui_api/errors` |
| **Summary** | Added backend-owned provider incident tokens and operator messages for OpenD down, delayed data, partial staleness, source disagreement, reconnect, timeout, empty/malformed payloads, temporary network failure, restart recovery, and Yahoo-as-hop-L1 fallback blocked. OpenD/Yahoo adapters fail closed on empty/timeout/reset without substituting overlay as primary L1. Item 9 remains IDLE / NOT_CALIBRATED; Live stays OFF. |
| **Key files** | Created: `src/market_platform_foundation/providers/resilience.py`, `tests/providers/test_provider_resilience.py`, `tests/fixtures/providers/resilience/incidents.json`. Modified: `providers/adapters/moomoo_opend_equity_quote.py`, `providers/adapters/yahoo_delayed_equity_quote.py`, `operations/runtime_resilience_diagnostic.py`, `ui_api/errors.py`, `docs/engineering/PROVIDER_READINESS.md`, `tests/providers/test_moomoo_opend_primary_l1.py`, `tests/ui1/test_error_taxonomy.py`. |
| **Tests** | `python tools/imp.py test focused` (10 Lane F selectors) **passed 10/0/0**; `python -m unittest` provider/yahoo/error-taxonomy/diagnostic modules **68 OK**. |
| **Related** | [PROVIDER_READINESS.md](PROVIDER_READINESS.md); runtime resilience diagnostic (Lane B composition consumed by diagnostics snapshot, this lane did not edit `snapshot.py`). |
| **Notes** | Leftover **CALENDAR**: Item 9 `2/3` IDLE not DEGRADED, `NOT_CALIBRATED`. **PROVIDER**: OpenD still unavailable on this workstation; Yahoo overlay remains DELAYED-only. No Item 9 collection, no collector mutation, no #222 merge. |

## 2026-09-18 — Control system status consumes GET /operator/diagnostics

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui/control`, `platform/operator_diagnostics` |
| **Summary** | Wired Control to a single `GET /operator/diagnostics` query for lifecycle, readiness, feed surface, governance, and Item 9 corpus gate presentation; added System status truth hierarchy UI and fixed diagnostics payload secret-leak audit blockers. |
| **Key files** | `ui/src/components/control/OperatorControlCenterPage.tsx`, `OperatorSystemStatusSection.tsx`, `operatorDiagnosticsPresentation.ts`, `ui/src/api/{schemas,endpoints,hooks}.ts`, `platform/operator_diagnostics/snapshot.py`, `operator-shared/governanceStatusPresentation.ts` |
| **Tests** | `ui`: vitest control/governance suites 44 passed; `python -m unittest tests.platform.test_operator_diagnostics_snapshot` 2 passed |
| **Related** | `docs/engineering/OPERATOR_DIAGNOSTICS_MODEL.md` |
| **Notes** | Browser-verified Control on worktree Vite `:5181` + API `:8767`; Radar/Lab spot-check blocked by session gate on cold navigation. Opportunity row count not in diagnostics snapshot (shown explicitly). |

## 2026-09-18 — Canonical status Item 9 prep (Lane A + G docs)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs/platform`, `docs/engineering` |
| **Summary** | Reconciled canonical program status and operator runbooks to `origin/main` @ **`50a1477f`** ([#287](https://github.com/AdamEddahmouni/market-trading-platform/pull/287)–[#289](https://github.com/AdamEddahmouni/market-trading-platform/pull/289)); pinned Item 9 **`2/3`** admitted RTH dates from read-only `corpus-status` on frozen collector receipts; documented **`GET /operator/diagnostics`**, governed receipt path, and fail-closed **`READY_TO_COLLECT`** preflight gates. **No** collection, calibration, or collector mutation. |
| **Key files** | `docs/platform/PROGRAM_STATUS.md`; `docs/engineering/NEXT_RTH_CAMPAIGN_RUNBOOK.md`; `docs/engineering/IMP_POST_RTH_CLOSE_08_LANE_G.md`; `docs/engineering/IMP_DUAL_CORPUS_01_NOTION_SYNC.md`; `docs/engineering/OPERATOR_DIAGNOSTICS_MODEL.md`; `docs/engineering/ITEM9_BAR_OHLCV_PROSPECTIVE_PROOF.md` |
| **Tests** | `python tools/item9_corpus_status.py corpus-status` (frozen collector receipt dir → `2/3`); `python tools/imp.py item9 next-rth-preflight --json` (off-hours `WRONG_RUNTIME`, no active collector); `python tools/check_docs_links.py` (pending in PR) |
| **Related** | [IMP_POST_RTH_CLOSE_08_LANE_G.md](IMP_POST_RTH_CLOSE_08_LANE_G.md); branch `docs/canonical-status-item9-prep` |
| **Notes** | Primary desktop checkout remains detached @ `44b8673e` — untouched. UI redesign isolated on `ui/operator-redesign-lab`. |

## 2026-09-18 — Lane D simulator experiment specs reconciliation (branch absorption)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs/engineering` |
| **Summary** | Compared `research/simulator-experiment-specs-sep18` (`e149b739`) and sibling simulator research branches against `origin/main` @ `270ce2a6` — all fully absorbed (0 unique commits). Routed fill-price realism doc to experiment 06 / #285 without mutating frozen `lane_c_readiness_v1.json` or Cost v4 evidence. Marked drawdown Lane C review as historical provenance only. |
| **Key files** | `docs/engineering/IMP_SIMULATOR_FILL_PRICE_REALISM_V1.md`; `docs/engineering/IMP_SIMULATOR_DRAWDOWN_WIRING_V1_REVIEW.md` |
| **Tests** | `python -m unittest tests.platform.test_simulator_experiment_specs_lane_c_v1` — OK (5 passed) |
| **Related** | Branch `research/simulator-experiment-specs-cleanup`; worktree `.worktrees/simulator-specs-cleanup`; PR [#288](https://github.com/AdamEddahmouni/market-trading-platform/pull/288); merges [#283](https://github.com/AdamEddahmouni/market-trading-platform/pull/283)–[#285](https://github.com/AdamEddahmouni/market-trading-platform/pull/285), Cost v4 [#284](https://github.com/AdamEddahmouni/market-trading-platform/pull/284) |
| **Notes** | Docs-only routing; recommend deleting merged local/remote simulator research branches after operator review. |

## 2026-09-18 — Lane F observability gap wiring + test hermeticity

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend`, `platform`, `operations`, `tests` |
| **Summary** | Wired read-only Item 9 collector log ingestion (`IMP_ITEM9_COLLECTOR_LOG_PATH` or default `artifacts/ftep-v1-002/item9-prospective-collector.log`) into `build_runtime_resilience_diagnostic`, so RTH empirical preflight and `/operator/diagnostics` expected-cycle gap analysis can classify epoch `121031`-class failures when operators capture logs. Stopped `run_frozen_fill_price_realism_v1` integration tests from rewriting tracked fill-price evidence JSON (`persist_canonical_evidence=False`). |
| **Key files** | `platform/artifact_path_resolver.py`; `operations/runtime_resilience_diagnostic.py`; `intelligence/historical_research_harness/fill_price_realism_harness.py`; `tests/platform/test_{artifact_path_resolver,runtime_resilience_diagnostic,fill_price_realism_v1}.py` |
| **Tests** | `PYTHONPATH=src` + main checkout `.venv`: `python -m unittest tests.platform.test_artifact_path_resolver tests.platform.test_runtime_resilience_diagnostic tests.platform.test_fill_price_realism_v1 tests.platform.test_operator_diagnostics_snapshot` — **15 OK** (2 skipped) |
| **Related** | Post-#287/#289 operator diagnostics; branch `fix/obs-hermeticity` |
| **Notes** | Path portability: v3 manifest resolution already centralized in #287; no new unsafe cross-host opens found. Does not mutate frozen collector or historical evidence bytes. |

## 2026-09-18 — Lane B runtime/provider resilience (path resolver + diagnostics)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend`, `platform`, `operations` |
| **Summary** | Centralized manifest path portability (`artifact_path_resolver`) so foreign Windows-absolute v3 `manifest_path` values fail safely on Linux without `OSError`; new v3 pack runs store repo-relative POSIX paths. Added `build_runtime_resilience_diagnostic` (provider connectivity, collector process probe, Item 9 preflight disposition, expected-cycle log gap analysis for epoch `121031` class) wired into `rth_empirical_ops` preflight. No frozen collector/evidence mutation. |
| **Key files** | `src/market_platform_foundation/platform/artifact_path_resolver.py`; `operations/runtime_resilience_diagnostic.py`; `fill_price_realism_harness.py`; `baseline_pack_v3.py`; `rth_empirical_ops.py`; `tests/platform/test_artifact_path_resolver.py`; `tests/platform/test_runtime_resilience_diagnostic.py` |
| **Tests** | `.venv\\Scripts\\python.exe -m unittest tests.platform.test_artifact_path_resolver tests.platform.test_runtime_resilience_diagnostic tests.platform.test_fill_price_realism_v1` — **11 OK** (2 skipped) |
| **Related** | PR [#287](https://github.com/AdamEddahmouni/market-trading-platform/pull/287); PR #285 CI portability; Sep 18 outage closeout `item9-lane0-provider-outage-closeout-20260918.json` (read-only) |
| **Notes** | Lane C may surface `runtime_resilience` DTO from `rth_empirical_ops` preflight; does not auto-restart collectors. |

## 2026-09-18 — Lane E operator UI epistemic depth (UIR-01I)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui/control`, `ui/radar`, `ui/lab`, `ui/research` |
| **Summary** | On `ui/operator-redesign-lab` reconciled to `origin/main` `270ce2a6`: opportunity detail uses epistemic layers + grounded-fact metadata; Control adds governance facts (Live OFF, Item 9 status only when capability_states expose it); known epoch `121031` gap uses precision banner; Lab/Research surface drawdown/cost/fill-realism when simulation contract carries them. |
| **Key files** | `ui/src/components/opportunity/opportunityEpistemicLayers.ts`; `ui/src/components/operator-shared/`; `ui/src/components/control/OperatorControlCenterPage.tsx`; `ui/src/components/research-shared/simulationHarnessMetrics.ts`; `ui/src/components/imp-ui/PrecisionFailureBanner.tsx` |
| **Tests** | `npm test` vitest: operator-shared, epistemic layers, simulationHarnessMetrics, opportunityDetailModel, OperatorControlCenterPage (17) — pass |
| **Related** | [UIR_01_OPERATOR_UI_REDESIGN.md](UIR_01_OPERATOR_UI_REDESIGN.md); worktree `.worktrees/ui-lab-redesign` |
| **Notes** | Browser not re-run this session. Lane C requests: runtime SHA, Item 9 corpus `distinct_rth_dates`/`calibrated` on `/operator/readiness` or `/context`; simulation `max_drawdown` on `/research/simulation`. |

## 2026-09-18 — IMP-POST-RTH-CLOSE-08 Lane G status reconcile (five-package closure)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs/platform`, `docs/engineering` |
| **Summary** | Docs-only closure after **IMP-POST-RTH-CLOSE-08** Sep 18 close and sequential engineering landings [#282](https://github.com/AdamEddahmouni/market-trading-platform/pull/282)–[#285](https://github.com/AdamEddahmouni/market-trading-platform/pull/285). Item 9 **2/3** admitted RTH dates, **188/189** receipts, outage epoch `121031` **not** backfilled, collector `fed2d9f7` stopped **16:00:11 ET**. **CURRENT_MAIN** `d06d57e7` (fill merge includes CI portability hardening @ `a36ab28b`; frozen v3 manifest paths untouched). Cost v4 **APPROVE** @ `7b5e4be9`. |
| **Key files** | `docs/platform/PROGRAM_STATUS.md`; `docs/engineering/IMP_POST_RTH_CLOSE_08_LANE_G.md`; `docs/engineering/AGENT_HANDOFF.md` |
| **Tests** | `python tools/check_docs_links.py` |
| **Related** | Lane 0 closeout JSON (operator tree); branch `docs/imp-post-rth-close-08-status`; merge [#286](https://github.com/AdamEddahmouni/market-trading-platform/pull/286) |
| **Notes** | `ITEM9_CALIBRATED=NO`; `PR222_MERGED=NO`; `LIVE_EXECUTION=OFF`; no receipt rewrite; no fill experiment rerun. |

## 2026-09-18 — Fill-price realism v1 harness + bounded run (IMP-POST-RTH-CLOSE-08 Lane F)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `historical_research_harness`, `tools/research`, `evidence/historical-research` |
| **Summary** | Landed read-only v3 fill-schedule replay + six-arm OHLC repricing harness; contamination auditor PASS; bounded run `pack_run_id` `6A66AE5C50700426F71B3734E6FC6A43` under experiment 06 evidence (`EXECUTED_BOUNDED_HISTORICAL_OBSERVATION`). Costs locked at 5 bps; v3 receipts untouched; validate gross sign unchanged on corpus. |
| **Key files** | `fill_price_realism_harness.py`; `fill_price_realism_v1_cli.py`; `tests/platform/test_fill_price_realism_v1.py`; `evidence/.../fill_price_realism_run_record.json` |
| **Tests** | `python -m unittest tests.platform.test_fill_price_realism_v1` — OK (3 passed, 1 skipped) |
| **Related** | Frozen spec `SPEC_FROZEN=YES`; `EXPERIMENT_HASH` `C4FCD3AB…1149`; merged #285 @ `a36ab28b` |
| **Notes** | `research_code_sha` recorded in run receipt at commit time; no experiment rerun on integration. |

## 2026-09-18 — Fill-price realism v1 spec freeze (IMP-POST-RTH-CLOSE-08 Lane F)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs/research/methodology/fill`, `evidence/historical-research` |
| **Summary** | Froze bounded fill-price realism experiment separate from Lane E cost sensitivity: six predeclared OHLC fill/MTM arms, locked v3 fill schedule + `cost_slippage_bps=5.0`, no Item 9 simulator semantic change. Independent review `APPROVE_FOR_FROZEN_EXECUTION`; historical execution recorded in harness entry (`6A66AE5C…`). |
| **Key files** | `docs/research/methodology/fill/FILL_PRICE_REALISM_V1.md`; `docs/engineering/IMP_INTEGRATE_EXPERIMENT_06_LANE_F_FILL_PRICE_REALISM_V1.md`; `evidence/historical-research/imp-integrate-experiment-06-r1-opend-fill-price-realism-v1/*` |
| **Tests** | `python` canonical hash verify for `EXPERIMENT_HASH` `C4FCD3AB…`; harness tests in follow-up entry |
| **Related** | `LANE-E-HYP-SIMULATOR-FILL-PRICE-REALISM-V1`; v3 hash `81EFC1B1…`; worktree `.worktrees/lane-f-fill-realism` |
| **Notes** | `SPEC_BUNDLE_SHA256=bcf758df…`; numbers frozen — integration updates status text only. |

## 2026-09-18 — Cost sensitivity v4 review follow-up (Lane E readiness)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `historical-research`, `docs/engineering`, `tests/platform` |
| **Summary** | Addressed independent review `65cedf09` REQUEST_CHANGES: added `execution_status_v1.json` (post-exec gates without rewriting pre-registration); refreshed `lane_c_readiness_v1.json`, `IMP_SIMULATOR_COST_SENSITIVITY_V4.md`, and Lane C tests for `EXECUTED_BOUNDED_HISTORICAL_OBSERVATION` with receipt pointers. No re-run; same `pack_run_id` `1DEF586AD729B270E20814B03606A718`. |
| **Key files** | `execution_status_v1.json`, `lane_c_readiness_v1.json`, `test_simulator_experiment_specs_lane_c_v1.py`, `IMP_SIMULATOR_COST_SENSITIVITY_V4.md` |
| **Tests** | `python -m unittest tests.platform.test_simulator_experiment_specs_lane_c_v1 tests.platform.test_historical_cost_sensitivity_v4_prep` — OK (8) |
| **Related** | Review `65cedf09`; merged #284 @ `7b5e4be9` |
| **Notes** | `pre_registered_methodology_v1.json` remains pre-exec artifact (`executed=false`). |

## 2026-09-18 — Cost sensitivity v4 execution (IMP-POST-RTH-CLOSE-08 Lane E)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `historical-research` |
| **Summary** | Confirmed Lane C frozen `pre_registered_methodology_v1.json`; promoted v4 `frozen_experiment_definition.json` (`EXPERIMENT_HASH` `30FB6972…`); executed pre-registered 7-point `cost_slippage_bps` grid on pinned OpenD HIST-DEV-AAPL corpus with v3-locked baselines/splits. All fill/gross invariants held; `bps=5.0` replicates v3 validate economics; contamination PASS. V3 receipts untouched. |
| **Key files** | `cost_sensitivity_v4.py`, `historical_cost_sensitivity_v4_cli.py`, `evidence/.../imp-simulator-cost-sensitivity-v4/*` |
| **Tests** | `unittest tests.platform.test_historical_cost_sensitivity_v4_prep tests.platform.test_simulator_experiment_specs_lane_c_v1` — OK (6) |
| **Related** | `IMP_SIMULATOR_COST_SENSITIVITY_V4.md`; merged #284 |
| **Notes** | `pack_run_id` `1DEF586AD729B270E20814B03606A718`; authority `HISTORICAL_DEVELOPMENT` / `BOUNDED_HISTORICAL_OBSERVATION` only. |

## 2026-09-18 — Simulator experiment specs Lane C (cost / fill / drawdown review)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs/engineering`, `evidence/historical-research`, `tests/platform` |
| **Summary** | Frozen methodology for cost v4 and fill realism; consolidated Lane C readiness in `imp-simulator-experiment-specs-sep18/lane_c_readiness_v1.json` (supersedes standalone `research/simulator-experiment-specs-sep18` landing). Cost v4 **EXECUTED** (#284); drawdown **merged** (#283); fill realism **EXECUTED** on branch pending merge. |
| **Key files** | `docs/engineering/IMP_SIMULATOR_COST_SENSITIVITY_V4.md`, `IMP_SIMULATOR_FILL_PRICE_REALISM_V1.md`, `IMP_SIMULATOR_DRAWDOWN_WIRING_V1_REVIEW.md`; `evidence/historical-research/imp-simulator-experiment-specs-sep18/lane_c_readiness_v1.json` |
| **Tests** | `python -m unittest tests.platform.test_simulator_experiment_specs_lane_c_v1` (3 tests, pass) |
| **Related** | Lane E v3 hypothesis queue; drawdown #283; cost #284; fill realism branch |
| **Notes** | No v3 rerun; no PROGRAM_STATUS edit on this branch. |

## 2026-09-18 — Simulator drawdown wiring v1 (Lane E)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `intelligence/historical_research_harness` |
| **Summary** | Diagnosed v3 `drawdown: null` as missing equity-curve aggregation (simulator read nonexistent `risk_result.portfolio.max_drawdown`). Wired net-MTM PnL curve → `max_drawdown` in fill economics with source `EQUITY_CURVE_NET_MTM`; documented contract; v3 evidence untouched. |
| **Key files** | `simulator_drawdown.py`, `fill_economics.py`, `simulator.py`, `docs/engineering/IMP_SIMULATOR_DRAWDOWN_WIRING_V1.md`, `tests/platform/test_simulator_drawdown_wiring_v1.py` |
| **Tests** | `python -m unittest tests.platform.test_simulator_drawdown_wiring_v1 tests.platform.test_simulator_fill_economics_v3` |
| **Related** | Hypothesis `LANE-E-HYP-SIMULATOR-DRAWDOWN-WIRING-V1`; finding `LANE-E-FND-019`; merged #283 @ `2b194d74` |
| **Notes** | `ACCOUNTING_VERSION` unchanged (`3.0.1`). Promotion needs NEW experiment hash; no v3 manifest backfill. |

## 2026-09-18 — IMP-POST-RTH-CLOSE-08 Lane B+C (rebase + independent fixtures)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `intelligence` / grounded fact SUT integration |
| **Summary** | Rebased approved SUT stack onto current `origin/main` (`2306ff4a`, #281); landed Lane B synthetic fixtures and `test_grounded_fact_independent_fixtures_v1.py` on `feat/grounded-fact-extraction-v1` in worktree `.worktrees/lane-bc-grounded-facts` (merged #282; no smoke rerun on integration step). |
| **Key files** | `tests/intelligence/test_grounded_fact_independent_fixtures_v1.py`, `tests/fixtures/intelligence_benchmark/grounded_fact_independent/*` |
| **Tests** | `python -m unittest tests.intelligence.test_grounded_fact_extraction_v1 tests.intelligence.test_grounded_fact_independent_fixtures_v1` — 31 OK; `python tools/imp.py test focused` (2 representative selectors) — 2 OK |
| **Related** | Lane A receipt `evidence/intelligence-benchmark/imp-post-rth-close-08-lane-a/grounded_fact_extraction_review_v1.json`; historical factual smoke `RUN_ID=ibp-factual-smoke-766E16CAF41F3210` persisted @ `f7486f42`/`90773a41` |
| **Notes** | `PROVENANCE_HYGIENE=skipped` (preserve freeze `SUT_CODE_SHA=b43cfd53`). `GOLD_INSPECTED=NO`. Historical smoke **executed and persisted** (facts 11/11, unknown_handling 11/11); `FULL30_EXECUTED=NO`; no post-`b43cfd53` SUT change — ancestry-only integration must not rerun smoke. |

## 2026-09-18 — Grounded fact extraction v1 (Lanes A+B+C)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `intelligence` / IBP facts SUT |
| **Summary** | Added generic admitted-evidence fact extraction (`question_class` handlers → structured facts → answer or UNKNOWN) and wired `run_ibp_facts_sut` factual protocol path; bumped facts SUT profile to `imp.ibp-facts-sut/1.1.0`. |
| **Key files** | `src/market_platform_foundation/intelligence/benchmark_protocol/grounded_fact_extraction/*`, `facts_sut.py`, `sut_profiles.py`, `tests/intelligence/test_grounded_fact_extraction_v1.py`, `tests/fixtures/intelligence_benchmark/grounded_fact_extraction/*`, nonstub freeze fingerprint refresh |
| **Tests** | `unittest tests.intelligence.test_grounded_fact_extraction_v1` + M4 evaluator (28 OK); `python tools/imp.py validate changed` PASSED (3656 tests) |
| **Related** | `LANE-M5-HYP-GROUNDED-FACT-EXTRACTION-V1`, `LANE-M5-HYP-ANSWERABLE-EVIDENCE-UNKNOWN-V1`, `LANE-M5-HYP-STRUCTURED-FACT-NORMALIZATION-V1` |
| **Notes** | No smoke rerun on integration; historical smoke receipt retained (`ibp-factual-smoke-766E16CAF41F3210`); no evaluator gold read; no Full30; merged #282 |

## 2026-09-18 — IBP factual gold v1 Lane M5 findings (IMP-IBP-FACTUAL-GOLD-V1 closeout)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `evidence/intelligence-benchmark`, `docs/platform`, `docs/engineering` |
| **Summary** | Post–[#280](https://github.com/AdamEddahmouni/market-trading-platform/pull/280) findings lane: registered eight observations from `RUN_ID` `ibp-factual-smoke-28EA7748057E312D` (facts FAIL 11/11; FACT_MISMATCH 5; UNNECESSARY_UNKNOWN 7; unknown_handling FAIL 7/4; other dimensions PASS 11/11). Ranked three **capability-gap** hypotheses only; closed `LANE-E-HYP-IBP-ADMITTED-FACTUAL-GOLD-V1` at methodology observed. `SMOKE10_JUSTIFIED=YES` for `IBP_FACTUAL_SMOKE_V1` only; routing PASS not interpreted as SUT quality. |
| **Key files** | `evidence/intelligence-benchmark/imp-ibp-factual-gold-v1-lane-m5-findings/*`; `docs/engineering/IMP_IBP_FACTUAL_GOLD_V1_LANE_M5_FINDINGS.md`; `docs/platform/PROGRAM_STATUS.md`; `tests/platform/test_imp_ibp_factual_gold_v1_lane_m5_findings.py` |
| **Tests** | `python -m unittest tests.platform.test_imp_ibp_factual_gold_v1_lane_m5_findings` |
| **Related** | Baseline receipt `imp-ibp-factual-gold-v1-lane-m5/factual_smoke_baseline_evidence_receipt.json`; legacy stub `ibp-smoke10-76DDD188CD080365` |
| **Notes** | `IMP_IBP_FACTUAL_GOLD_V1_SOFTWARE_LANDING_SHA=3aa87e51` — not this docs PR commit. `MERGE_PERFORMED=NO` pending independent review. No SUT gold patch, smoke rerun, #222 merge, or Item 9 mutation. |

## 2026-09-18 — IBP factual smoke v1 Lane M5 baseline run (IMP-IBP-FACTUAL-GOLD-V1)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `intelligence/benchmark_protocol`, `evidence/intelligence-benchmark` |
| **Summary** | Lane M5: froze `IBP_FACTUAL_SMOKE_V1` at main `936e233` (11 answerable cases; `IBP-FACTUAL-EXCL-001` excluded) with all pre-run gates PASS, then executed exactly one factual smoke baseline (`RUN_ID` `ibp-factual-smoke-28EA7748057E312D`, `FULL30_EXECUTED=NO`). Contamination audit PASS; facts dimension FAIL 11/11 on grounded facts SUT (failures preserved). Legacy `ibp-smoke10-76DDD188CD080365` untouched. |
| **Key files** | `tests/fixtures/intelligence_benchmark/freeze/ibp_factual_smoke_v1_freeze.json`; `evidence/intelligence-benchmark/imp-ibp-factual-gold-v1-lane-m5/*`; `tools/benchmarks/run_ibp_factual_smoke_m5_lane.py` |
| **Tests** | `python -m unittest tests.intelligence.test_ibp_admitted_factual_gold_m4_evaluator tests.intelligence.test_ibp_admitted_factual_gold_contract` — 25 OK |
| **Related** | [IBP_ADMITTED_FACTUAL_GOLD_V1.md](IBP_ADMITTED_FACTUAL_GOLD_V1.md); Lane D receipt `imp-research-validation-04-lane-d-smoke10` |
| **Notes** | `ITEM9_CALIBRATED=NO`; PR #222 isolated; evidence merged via [#280](https://github.com/AdamEddahmouni/market-trading-platform/pull/280) (`APPROVE_M5_EVIDENCE`); findings closeout is separate docs PR |

## 2026-09-18 — IBP admitted factual gold M1 contract (IMP-IBP-FACTUAL-GOLD-V1 Phase 2)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `intelligence/benchmark_protocol`, `docs/engineering`, `manifests` |
| **Summary** | Lane M1: versioned methodology contract `imp.ibp-admitted-factual-gold/1.0.0` / protocol `IBP_FACTUAL_SMOKE_V1` with validators, SUT/evaluator field partition, UNKNOWN verdict enum, temporal cutoff + contamination invariants, and empty protocol fixture (no cases, no Smoke10). Legacy `ibp-smoke10` stub gold untouched. |
| **Key files** | `src/market_platform_foundation/intelligence/benchmark_protocol/admitted_factual_gold/*`; `manifests/intelligence_benchmark/schemas/ibp_admitted_factual_gold_protocol.schema.json`; `tests/fixtures/intelligence_benchmark/admitted_factual_gold/protocol_ibp_factual_smoke_v1_empty.json`; `tests/intelligence/test_ibp_admitted_factual_gold_contract.py`; `docs/engineering/IBP_ADMITTED_FACTUAL_GOLD_V1.md` |
| **Tests** | `python -m unittest tests.intelligence.test_ibp_admitted_factual_gold_contract` — 10/10 OK; `python tools/imp.py format` / `lint` / `validate changed` |
| **Related** | Hypothesis `LANE-E-HYP-IBP-ADMITTED-FACTUAL-GOLD-V1`; branch `research/ibp-admitted-factual-gold-v1-contract`; worktree `.worktrees/ibp-factual-gold-m1` |
| **Notes** | M2 case builder may use validators, hashing, SUT projection, schema paths, empty protocol template. `REVIEW_VERDICT=APPROVE_M1_CONTRACT` pending independent review; `MERGE_PERFORMED=NO`. |

## 2026-09-18 — NEXT_RTH runbook SHA reconcile (post–Lane F #275)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs/engineering` |
| **Summary** | Reconciled [NEXT_RTH_CAMPAIGN_RUNBOOK.md](NEXT_RTH_CAMPAIGN_RUNBOOK.md) operator SHA table with [PROGRAM_STATUS.md](../platform/PROGRAM_STATUS.md) after [#272](https://github.com/AdamEddahmouni/market-trading-platform/pull/272) / closed [#267](https://github.com/AdamEddahmouni/market-trading-platform/pull/267) and Lane F [#275](https://github.com/AdamEddahmouni/market-trading-platform/pull/275). **ITEM9_FROZEN_COLLECTOR** remains `fed2d9f7`; **ITEM9_CALIBRATED** unchanged. |
| **Key files** | `docs/engineering/NEXT_RTH_CAMPAIGN_RUNBOOK.md` |
| **Tests** | `python tools/check_docs_links.py` (docs-only) |
| **Related** | Lane F OpenD v3 status reconcile; IMP-EVIDENCE-HARDENING-02 Item 9 preflight [#251](https://github.com/AdamEddahmouni/market-trading-platform/pull/251) |
| **Notes** | Software landing pin `e0ab919f`; no collector retarget; no RTH collection |

## 2026-09-18 — OpenD v3 Lane F status reconcile (IMP-IBP-FACTUAL-GOLD-V1 Phase 1D)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs/platform`, `docs/engineering` |
| **Summary** | Reconciled stale `docs/opend-v3-status` narrative against landed `origin/main` @ `e0ab919f` ([#274](https://github.com/AdamEddahmouni/market-trading-platform/pull/274) findings, [#273](https://github.com/AdamEddahmouni/market-trading-platform/pull/273) v3 evidence, [#272](https://github.com/AdamEddahmouni/market-trading-platform/pull/272) SUT, [#271](https://github.com/AdamEddahmouni/market-trading-platform/pull/271) accounting). Pins `ACCOUNTING_ON_MAIN` / `V3_EVIDENCE_ON_MAIN` / `V3_FINDINGS_ON_MAIN` / `SUT_WIRING_ON_MAIN` = **YES**; `SMOKE10_EXECUTED=NO`; `V3_AUTHORITY=HISTORICAL_DEVELOPMENT`. **No** v3 rerun, Smoke10, collector mutation, or #222 merge. |
| **Key files** | `docs/platform/PROGRAM_STATUS.md`; `docs/engineering/WORK_LOG.md`; `docs/engineering/IMP_INTEGRATE_EXPERIMENT_05_LANE_E_V3.md` |
| **Tests** | `python -m unittest tests.platform.test_imp_integrate_experiment_05_lane_e_v3_findings`; `python tools/imp.py env`; `format` / `lint` / `validate changed` |
| **Related** | Branch `docs/opend-v3-status-reconcile`; worktree `.worktrees/v3-status-docs`; superseded draft `docs/opend-v3-status` @ `97a8ec41` |
| **Notes** | `IMP05_V3_SOFTWARE_LANDING_SHA=e0ab919f` — not the docs PR commit (avoid self-pin loop). Next: independent review, then Phase 2 M1 factual gold methodology contract. |

## 2026-09-18 — Lane E v3 findings registry (OpenD fill economics)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `evidence/historical-research`, `tests/platform` |
| **Summary** | Registered bounded Lane E findings from immutable v3 pack `81EFC1B1…` (five AAPL sessions) and intelligence Smoke10 deferral (`SMOKE10_EXECUTED=NO`); closed `LANE-H-HYP-SIMULATOR-FILL-ECONOMICS-V3` at machinery observation without edge/deployability language. v2 `E8C9ADB9…` and v3 execution receipts untouched. |
| **Key files** | `evidence/historical-research/imp-integrate-experiment-05-lane-e-v3-findings/*`; `tests/platform/test_imp_integrate_experiment_05_lane_e_v3_findings.py` |
| **Tests** | `python -m unittest tests.platform.test_imp_integrate_experiment_05_lane_e_v3_findings` — 3/3 OK |
| **Related** | Worktree `research/opend-v3-findings` from v3 HEAD `436a0ed7`; source run `research/opend-fill-economics-v3` |
| **Notes** | No Smoke10 run; no v3 rerun; no PR #222/#267 merge. |

## 2026-09-18 — IMP-SIMULATOR-FILL-ECONOMICS-V3 Lane B freeze + bounded performance

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `evidence/historical-research`, `intelligence/historical_research_harness`, `tools/research` |
| **Summary** | Merged APPROVED Lane A accounting; promoted v3 pre-execution definition to `frozen_experiment_definition.json` with pinned dataset fingerprint; executed one canonical baseline pack + full deterministic rerun (`deterministic_rerun_match`: true). Contamination auditor PASS. v2 evidence untouched. |
| **Key files** | `baseline_pack_v3.py`, `historical_baseline_pack_v3_cli.py`, `evidence/.../imp-integrate-experiment-05-r3-opend-fill-economics-v3/*` |
| **Tests** | `unittest tests.platform.test_historical_baseline_pack_v3_prep`, `test_simulator_fill_economics_v3`; `python tools/imp.py validate changed` |
| **Related** | `LANE-H-HYP-SIMULATOR-FILL-ECONOMICS-V3`; `EXPERIMENT_HASH` `81EFC1B1…` |
| **Notes** | Not profitable/validated/production. Item 9 not calibrated. |

## 2026-09-18 — IBP facts SUT re-review hygiene (Lane C)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs/engineering/lane-notes`, `ui_api/store`, tests |
| **Summary** | Addressed independent re-review REQUEST_CHANGES without gaming gold: refreshed `imp-05-i1-nonstub-sut.md` (limitation, freeze `4720493F…`, 1/10 fixture coverage, synthetic gold vs grounded citations, Smoke10 not justified for facts); hardened `FIXTURE_REPLAY` against live promotion on `load_decoded_snapshot`; documented gold audit (10/10 synthetic). |
| **Key files** | `imp-05-i1-nonstub-sut.md`, `store.py`, `test_replay_store_loading.py` |
| **Tests** | `python -m unittest tests.validation.test_replay_store_loading`; `python tools/imp.py validate changed` |
| **Related** | PR #272 worktree `ui/nonstub-facts-sut-resolvers` |
| **Notes** | Freeze `code_sha` remains `109fd650…` (SUT logic); no Smoke10/Full30. |

## 2026-09-18 — IBP facts SUT historical evidence resolvers (Lane C)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `intelligence/benchmark_protocol`, `ui_api/store`, tests |
| **Summary** | Wired `build_historical_fixture_evidence_context` so `run_ibp_facts_sut` supplies MRA-001-style `resolve_explain` / `resolve_inspect` from Lane B historical fixtures via replay projections; fail-closed `UNKNOWN` when resolvers absent; regenerated nonstub Smoke10 freeze fingerprint. |
| **Key files** | `historical_evidence_context.py`, `facts_sut.py`, `store.py` (`load_decoded_snapshot`), `sut_profiles.py`, `test_intelligence_benchmark_nonstub_sut_protocol.py`, `ibp_smoke10_nonstub_sut_freeze_v1.json` |
| **Tests** | `python -m unittest tests.intelligence.test_intelligence_benchmark_nonstub_sut_protocol` (14 OK); `python tools/imp.py validate changed` (3785 passed, 41 skipped) |
| **Related** | PR #272 worktree `ui/nonstub-facts-sut-resolvers` |
| **Notes** | Smoke10/Full30 not executed; limitation class `BOUNDED_OFFLINE_NO_LLM_GROUNDED_HISTORICAL`. |

## 2026-09-18 — Fill economics V3 pre-fee gross (review fix)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `intelligence/historical_research_harness` |
| **Summary** | Review found policy fees double-subtracted: ledger realized is post-fee while transaction_costs also summed commission/fees. Research gross now adds policy fees back once from ledger totals; net = gross − transaction_costs. ACCOUNTING_VERSION bumped to 3.0.1; fee regression tests added. |
| **Key files** | `fill_economics.py`, `simulator.py`, `test_simulator_fill_economics_v3.py` |
| **Tests** | `unittest tests.platform.test_simulator_fill_economics_v3` (17 OK); `validate changed` |
| **Related** | `research/simulator-fill-economics-v3` follow-up to REQUEST_CHANGES |
| **Notes** | `max_drawdown` / `coverage` labeled `RISK_PORTFOLIO_INHERITED`. V3 performance not executed. |

## 2026-09-18 — Fill economics V3 simulator accounting (Lane A)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `intelligence/historical_research_harness` |
| **Summary** | Prediction-coupled simulator research now applies fills through `portfolio.ledger.apply_fill` (weighted average cost basis), computes gross realized/unrealized PnL, and charges transaction costs from traded notional × bps plus policy fees—not from `abs(gross_pnl)`. Fail-closed invariants and unit/integration tests added for IMP-SIMULATOR-FILL-ECONOMICS-V3. |
| **Key files** | `fill_economics.py` (new), `simulator.py`, `prediction_coupling.py`, `metrics.py`, `tests/platform/test_simulator_fill_economics_v3.py` |
| **Tests** | `python -m unittest tests.platform.test_simulator_fill_economics_v3` (14 OK); `python tools/imp.py validate changed` (2875 passed, 29 skipped) |
| **Related** | Branch `research/simulator-fill-economics-v3` @ base `6d6b27de` |
| **Notes** | `ACCOUNTING_VERSION` / `COST_MODEL_VERSION` / `SIMULATOR_VERSION` (`phase7.bar-conservative/1.1.0`) frozen for Lane B. `estimated_costs` retained as alias of `transaction_costs`. Open-position `max_drawdown` still from risk portfolio summary when present. |

## 2026-09-18 — IMP-SIMULATOR-FILL-ECONOMICS-V3 Lane B pre-execution freeze prep

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `evidence/historical-research`, `docs/engineering`, `tests/platform` |
| **Summary** | Prepared v3 OpenD fill-economics experiment definition on branch `research/opend-fill-economics-v3`: pinned corpus fingerprint verified PASS, pre-execution freeze template and protocol committed with `PENDING_LANE_A` placeholders; no performance run. |
| **Key files** | `evidence/historical-research/imp-integrate-experiment-05-r3-opend-fill-economics-v3/*`; `docs/engineering/IMP_INTEGRATE_EXPERIMENT_05_LANE_B_V3_FILL_ECONOMICS.md`; `tests/platform/test_historical_baseline_pack_v3_prep.py`; `evidence/.../lane-h-findings/hypothesis_queue_v1.json` |
| **Tests** | `python tools/imp.py env` healthy; `python tools/imp.py test focused tests/platform/test_historical_baseline_pack_v3_prep.py` |
| **Related** | [IMP_INTEGRATE_EXPERIMENT_05_LANE_B_V3_FILL_ECONOMICS.md](IMP_INTEGRATE_EXPERIMENT_05_LANE_B_V3_FILL_ECONOMICS.md); `LANE-H-HYP-SIMULATOR-FILL-ECONOMICS-V3` |
| **Notes** | Final `EXPERIMENT_HASH` blocked on Lane A accounting; v2 `E8C9ADB9…` evidence untouched. |

## 2026-09-18 — IMP-INTEGRATE-AND-EXPERIMENT-05 Lane Docs status/documentation closure

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs/platform`, `docs/engineering` |
| **Summary** | Docs-only orchestrator closure at **ENDING_MAIN** / **CURRENT_GIT_MAIN** `0fb32d44`: record IMP-RESEARCH-VALIDATION-04 **merged** @ `7d67d48e`; IMP-INTEGRATE-AND-EXPERIMENT-05 **partial** ([#266](https://github.com/AdamEddahmouni/market-trading-platform/pull/266) R1, [#268](https://github.com/AdamEddahmouni/market-trading-platform/pull/268) OpenD v2 **`BOUNDED_HISTORICAL_OBSERVATION`**, [#269](https://github.com/AdamEddahmouni/market-trading-platform/pull/269) Lane H); **OPEN** [#267](https://github.com/AdamEddahmouni/market-trading-platform/pull/267) (review aborted — do not restart autonomously); non-stub Smoke10 **`NOT_EXECUTED`**; Full30 **`NOT_RUN`**; Item 9 **`NOT_CALIBRATED`** (**1**/3 RTH); #222 **isolated**. **No** merge #267/#222, collector mutation, Smoke10 fabrication, or Live enable. |
| **Key files** | `docs/platform/PROGRAM_STATUS.md`; `docs/engineering/NEXT_RTH_CAMPAIGN_RUNBOOK.md`; `docs/engineering/WORK_LOG.md` |
| **Tests** | `python tools/imp.py format`; `lint`; `validate changed`; `check_docs_links.py` |
| **Related** | IMP-INTEGRATE-AND-EXPERIMENT-05; branch `docs/imp-integrate-experiment-05-status`; [IMP_INTEGRATE_EXPERIMENT_05_LANE_H.md](IMP_INTEGRATE_EXPERIMENT_05_LANE_H.md) |
| **Notes** | Next engineering: **`LANE-H-HYP-SIMULATOR-FILL-ECONOMICS-V3`**. Next intelligence: I1 then non-stub Smoke10; **not** Full30. |

## 2026-09-17 — IMP-RESEARCH-VALIDATION-04 Lane G status/documentation closure

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs/platform`, `docs/engineering` |
| **Summary** | Docs-only orchestrator closure at campaign **STARTING_MAIN** / **CURRENT_GIT_MAIN** `f31e30fa`: pin **CURRENT_SOFTWARE_IMPLEMENTATION** `a1b556f8`, **ITEM9_FROZEN_COLLECTOR** `fed2d9f7`, **SEP15_FROZEN_EMPIRICAL** `7aade60`; record open lanes **A–E** ([#260](https://github.com/AdamEddahmouni/market-trading-platform/pull/260)–[#264](https://github.com/AdamEddahmouni/market-trading-platform/pull/264), [#263](https://github.com/AdamEddahmouni/market-trading-platform/pull/263)); honest gates (`ITEM9_CALIBRATED=NO`, **1/3** RTH dates, `PR222_MERGED=NO`); off-main preflight **`WRONG_RUNTIME`** + off-hours **`NOT_RTH`** expected. **No** lane merges, collector mutation, or Item 9 collection. |
| **Key files** | `docs/platform/PROGRAM_STATUS.md`; `docs/engineering/WORK_LOG.md` |
| **Tests** | `python tools/imp.py format`; `lint`; `validate changed`; `check_docs_links.py` |
| **Related** | IMP-RESEARCH-VALIDATION-04; branch `docs/imp-research-validation-04-status` |
| **Notes** | Recommended next: merge **#260→#261/#262→#264→#263**; fix Smoke10 `FACTS_MISMATCH`; freeze **`LANE-E-HYP-OPEND-MULTI-SESSION-V2`**; RTH Item 9 poll @ frozen collector only. |

## 2026-09-18 — IMP-RESEARCH-VALIDATION-04 Lane E baseline findings queue

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `evidence/historical-research`, `docs/engineering` |
| **Summary** | Structured findings (11) from Lane C baseline pack v1 and Lane D Smoke10 run observations; ranked hypothesis queue (6 proposed, not implemented). No baseline/Smoke10 config edits, retuning, or follow-up experiments. |
| **Key files** | `evidence/historical-research/imp-research-validation-04-lane-e-findings/*`; `docs/engineering/IMP_RESEARCH_VALIDATION_04_LANE_E.md`; `tests/platform/test_imp_research_validation_04_lane_e_findings.py` |
| **Tests** | `python -m unittest tests.platform.test_imp_research_validation_04_lane_e_findings` — 2/2 OK |
| **Related** | IMP-RESEARCH-VALIDATION-04 Lanes C/D/B (read-only artifacts); BUILD 17 research experiment system |
| **Notes** | Frozen collector `.imp-actual-01-phase-d` @ `fed2d9f7` untouched. Language: historical observation / candidate hypothesis only. |

## 2026-09-18 — IMP-RESEARCH-VALIDATION-04 Lane C baseline pack integrity fix

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `intelligence/historical_research_harness`, `evidence/historical-research`, `tools/research` |
| **Summary** | Independent review request-changes: frozen experiment definitions now fail closed on hash tampering (always recompute canonical payload hash), git-tracked receipts under `evidence/historical-research/imp-research-validation-04-lane-c-baseline-pack-v1/`, operator interpretation notes for fixture-pathological metrics and simulator/predictor decoupling (no baseline retune). |
| **Key files** | `baseline_pack.py`, `historical_baseline_pack_v1_cli.py`, `test_historical_baseline_pack_v1.py`, `evidence/historical-research/imp-research-validation-04-lane-c-baseline-pack-v1/*` |
| **Tests** | `python -m unittest tests.platform.test_historical_baseline_pack_v1`; `python tools/research/historical_baseline_pack_v1_cli.py --frozen-definition evidence/.../frozen_experiment_definition.json` |
| **Related** | IMP-RESEARCH-VALIDATION-04 Lane C; reviewer `e50cef56-dc4f-4544-a5d7-fe5db9d32433` |
| **Notes** | **EXPERIMENT_HASH** unchanged (`C2E706…`) — strategy/dataset payload unchanged; `research_code_sha` in frozen file remains base pin `f31e30f` while execution SHA recorded in pack manifest/receipt. Lane F WORK_LOG heading preserved. |

## 2026-09-17 — IMP-RESEARCH-VALIDATION-04 Lane B real historical provider verification

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `market_data/historical_development`, `tools/historical_data` |
| **Summary** | Bounded OpenD verification for AAPL 1m RTH (5 sessions) via `verify_real_historical_providers.py`; fail-closed IBKR gate when TWS/4001 closed and `IMP_IBKR_LIVE` unset. **HISTORICAL_DEVELOPMENT** only; Item 9 admission refused. |
| **Key files** | `src/market_platform_foundation/market_data/historical_development/real_provider_verification.py`, `tools/historical_data/verify_real_historical_providers.py`, `tests/platform/test_real_historical_provider_verification.py` |
| **Tests** | `python -m unittest tests.platform.test_real_historical_provider_verification` — 6 passed; `python tools/imp.py validate changed` — 1899 passed, 3 skipped |
| **Related** | IMP-DUAL-CORPUS-01 Lane B builder; `tools/ibkr/verify_historical_trades_provider.py` |
| **Notes** | Worktree `.worktrees/imp-04-lane-b-provider` @ branch `data/real-historical-verification`. Verified corpus under `artifacts/historical-rth-development-real-provider-verification/`. Frozen collector `.imp-actual-01-phase-d` @ `fed2d9f7` untouched. |

## 2026-09-17 — IMP-RESEARCH-VALIDATION-04 Lane D Smoke10 baseline + evidence pin

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `intelligence/benchmark_protocol`, `evidence` |
| **Summary** | Added governed Smoke10 baseline execution (`smoke10-run`) and git-tracked baseline receipts under `evidence/intelligence-benchmark/imp-research-validation-04-lane-d-smoke10/` pinning RUN_ID `ibp-smoke10-76DDD188CD080365`, frozen config `76DDD188…`, contamination PASS, and per-dimension summaries (no rescoring). Rebased onto Lane A `c2ac4c59` (Lane F WORK_LOG heading preserved). |
| **Key files** | `src/market_platform_foundation/intelligence/benchmark_protocol/smoke10_*.py`, `synthetic_sut.py`; `evidence/intelligence-benchmark/imp-research-validation-04-lane-d-smoke10/*`; `tools/benchmarks/intelligence_cli.py`; `tests/intelligence/test_intelligence_benchmark_smoke10_execution.py` |
| **Tests** | `.venv\\Scripts\\python.exe -m unittest tests.intelligence.test_intelligence_benchmark_smoke10_execution tests.intelligence.test_intelligence_benchmark_harness_adapter`; `python tools/imp.py validate changed` |
| **Related** | IMP-RESEARCH-VALIDATION-04 Lane D; reviewer `114aef56-8cd5-41a4-bdcf-d272c1e0889b`; Lane A `c2ac4c59`; branch `benchmarks/smoke10-baseline` |
| **Notes** | Canonical Smoke10 = `IBP-CASE-001`…`010`. Baseline stub `UNKNOWN` → 10× `facts` FAIL (`FACTS_MISMATCH`); scores frozen in pinned JSON. Ephemeral harness paths redacted in run record. Full30 not executed. Frozen collector untouched. |

## 2026-09-17 — IMP-RESEARCH-VALIDATION-04 Lane A result_kind fail-closed

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `intelligence/benchmark_protocol` |
| **Summary** | IBP historical manifest admissibility now requires an explicit `simulator.result_kind` of `SIMULATOR_RESEARCH_RESULT`; absent or unknown kinds fail closed so historical simulator output cannot be ingested without an explicit research contract. |
| **Key files** | `src/market_platform_foundation/intelligence/benchmark_protocol/contamination.py`; `tests/intelligence/test_intelligence_benchmark_harness_adapter.py`; `docs/engineering/IMP_OFFHOURS_RESEARCH_03_BENCHMARK_HARNESS_INTEGRATION.md` |
| **Tests** | `.venv\\Scripts\\python.exe -m unittest tests.intelligence.test_intelligence_benchmark_harness_adapter` — 10 passed; `python tools/imp.py validate changed` — PASSED 3529 tests, 0 failures |
| **Related** | IMP-RESEARCH-VALIDATION-04 Lane A; IMP-OFFHOURS-RESEARCH-03 Lane E; branch `benchmarks/result-contract-hardening` |
| **Notes** | Evidence class remains `HISTORICAL_DEVELOPMENT` only; no Item 9 / FTEP / Live upgrade paths. |

## 2026-09-18 — IMP-OFFHOURS-RESEARCH-03 Lane F next-RTH dry preflight

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs/engineering`, `tools` |
| **Summary** | Off-hours dry verification from worktree @ **CURRENT_MAIN** `19a5ebd5`: `imp.py item9 next-rth-preflight --json` shows `rth_active=false`, `process_probe_status=COMPLETED`, no active collector, receipt path gate OK; disposition `WRONG_RUNTIME` honest for software SHA vs **ITEM9_FROZEN_COLLECTOR** `fed2d9f7`. Closed process-probe nit: subprocess listing stays in tools wrapper ([#251](https://github.com/AdamEddahmouni/market-trading-platform/pull/251)); governed library `NOT_RUN` without injection is intentional. `tools/item9.py` now delegates preflight to tools wrapper. **COLLECTION_STARTED=NO.** |
| **Key files** | `docs/engineering/{ITEM9_BAR_OHLCV_PROSPECTIVE_PROOF,NEXT_RTH_CAMPAIGN_RUNBOOK,WORK_LOG}.md`; `docs/platform/PROGRAM_STATUS.md`; `tools/item9.py` |
| **Tests** | `python tools/imp.py item9 next-rth-preflight --json` (off-hours); `item9_corpus_status.py corpus-status` (local receipt dir empty; canonical gate still **1/3** distinct RTH dates per PROGRAM_STATUS — not fabricated) |
| **Related** | IMP-OFFHOURS-RESEARCH-03; branch `ops/item9-next-rth-final-check` |
| **Notes** | No `--poll`, receipts, or frozen-collector edits. |

## 2026-09-17 — IMP-OFFHOURS-RESEARCH-03 Lane E IBP harness integration

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `intelligence/benchmark_protocol`, `tools/benchmarks`, `docs` |
| **Summary** | Added minimal greenfield Intelligence Benchmark Protocol v1 adapter from Lane B `historical_research_run_manifest_v1` to IBP run records with contamination stripping, 30-case catalog + Smoke10 invocation contract (no scores executed), and `imp benchmark intelligence` CLI. |
| **Key files** | `src/market_platform_foundation/intelligence/benchmark_protocol/*`, `tools/benchmarks/intelligence_cli.py`, `tests/fixtures/intelligence_benchmark/ibp_suite_catalog_v1.json`, `tests/intelligence/test_intelligence_benchmark_harness_adapter.py`, `docs/engineering/IMP_OFFHOURS_RESEARCH_03_BENCHMARK_HARNESS_INTEGRATION.md` |
| **Tests** | `python -m unittest tests.intelligence.test_intelligence_benchmark_harness_adapter` — 6/6 OK |
| **Related** | [IMP_OFFHOURS_RESEARCH_03_BENCHMARK_HARNESS_INTEGRATION.md](IMP_OFFHOURS_RESEARCH_03_BENCHMARK_HARNESS_INTEGRATION.md), Lane B [#256](https://github.com/AdamEddahmouni/market-trading-platform/pull/256) |
| **Notes** | `BENCHMARK_SMOKE10_READY=YES` when catalog + adapter wiring pass; full 30-case benchmark scores **not** run. Branch `benchmarks/intelligence-harness-integration` stacked on `research/historical-harness-v1`. |

## 2026-09-17 — IMP-OFFHOURS-RESEARCH-03 Lane C multi-session historical expansion

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `market_data/historical_development`, `tools/historical_data`, IBKR observational pagination |
| **Summary** | Bounded multi-session RTH historical-development builds now record `interval.session_dates`, per-session quality summaries, deterministic raw `time_key` ordering before normalization, and richer CLI deliverable JSON (`provider_availability`, session counts, fingerprints). IBKR trade pagination fails closed on same-timestamp full pages (`SUSPECTED_SAME_TIMESTAMP_TRUNCATION`). |
| **Key files** | `market_data/historical_development/{builder,rth_session,quality}.py`; `tools/historical_data/build_cli.py`; `providers/ibkr_observational/historical_trades_pagination.py`; `tests/platform/test_historical_multi_session_build.py`; `docs/engineering/IMP_DUAL_CORPUS_01_LANE_B_HISTORICAL_RTH.md` |
| **Tests** | `unittest` historical multi-session + session quality + g11 pagination suites; `python tools/imp.py validate changed` |
| **Related** | IMP-OFFHOURS-RESEARCH-03; IMP-DUAL-CORPUS-01 Lane B |
| **Notes** | Branch `data/historical-development-expansion`; holidays/early closes operator-declared only. |

## 2026-09-17 — IMP-OFFHOURS-RESEARCH-03 historical research harness v1

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `intelligence/historical_research_harness`, `tools/historical_data`, `docs/engineering` |
| **Summary** | Reusable historical development research pipeline: dataset → PIT features → chronological train/dev-validate/research-test splits → momentum challenger → paper simulator research result → component metrics → `historical_research_run_manifest_v1` with deterministic fingerprints. Authority remains `HISTORICAL_DEVELOPMENT`; labels distinct from POST_HORIZON; holdout consumption fails closed. |
| **Key files** | `src/market_platform_foundation/intelligence/historical_research_harness/*`, `tools/historical_data/harness_cli.py`, `tools/imp.py`, `tests/platform/test_historical_research_harness.py`, `docs/engineering/IMP_OFFHOURS_RESEARCH_03_HISTORICAL_HARNESS.md` |
| **Tests** | `python -m unittest tests.platform.test_historical_research_harness` (see validation) |
| **Related** | [#246](https://github.com/AdamEddahmouni/market-trading-platform/pull/246) Lane D demo, `IMP_OFFHOURS_RESEARCH_03_HISTORICAL_HARNESS.md` |
| **Notes** | Branch `research/historical-harness-v1`; no Item 9 calibration; no PROGRAM_STATUS SHA loop |

## 2026-09-17 — IMP-OFFHOURS-RESEARCH-03 research contamination auditor (Lane D)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `paper/calibration/dual_corpus`, `tools/research` |
| **Summary** | Added reusable research-run contamination auditor composing dual-corpus admission/consumption gates with contractual train/test, feature cutoff, holdout, authority-mixing, fingerprint, and Item 9 admission checks. Emits `CONTAMINATION_STATUS` PASS/FAIL with five canonical questions and evidence language (`AUTHORITY`, `ITEM9_EFFECT`). |
| **Key files** | `dual_corpus/{contamination_auditor,leak_audit,run_manifest}.py`; `tools/research/audit_research_contamination.py`; `tests/platform/test_research_contamination_auditor.py`; `docs/architecture/DUAL_CORPUS_EVIDENCE_CONTRACT.md` |
| **Tests** | `python tools/imp.py` format/lint/validate changed; `unittest` `test_research_contamination_auditor` |
| **Related** | IMP-OFFHOURS-RESEARCH-03 Lane D; dual-corpus contract |
| **Notes** | Contractual leakage properties only; no frozen receipts or Item 9 calibration changes. |

## 2026-09-17 — IMP-OFFHOURS-RESEARCH-03 Lane A holdout guard closure

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `paper/calibration/dual_corpus`, `intelligence/training`, `intelligence/promotion`, `tests/platform` |
| **Summary** | Closed residual training/selection holdout leakage paths: `build_dataset_from_examples`, `build_distillation_dataset`, BUILD 18 sklearn trainers (manifest + baseline), and promotion challenger registration now fail closed on `UNTOUCHED_FORWARD_EVALUATION` / taxonomy-derived protected authorities. Evaluation-only holdout use (validation metrics, promotion ranking) unchanged. |
| **Key files** | `dual_corpus/consumption.py`; `training/{datasets,distillation/dataset,trainers/sklearn_*.py}`; `promotion/engine.py`; `tests/platform/test_holdout_consumption_guards.py` |
| **Tests** | `python tools/imp.py test focused test_holdout_consumption_guards`; `format`; `lint`; `validate changed` |
| **Related** | IMP-OFFHOURS-RESEARCH-03 Lane A; IMP-EVIDENCE-HARDENING-02 Lane B baseline guards |
| **Notes** | No Item 9 split or #222 changes; repository-backed training manifest load at validation remains governed separately (`verify_training_dataset_fingerprint`). |

## 2026-09-17 — IMP-EVIDENCE-HARDENING-02 Lane F docs/status hygiene

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs/platform`, `docs/engineering` |
| **Summary** | Post–dual-corpus + hardening docs sync: distinguish **CURRENT_MAIN** vs **CURRENT_SOFTWARE_IMPLEMENTATION** vs frozen **ITEM9_FROZEN_COLLECTOR** / **SEP15_FROZEN_EMPIRICAL_AUTHORITY** in `PROGRAM_STATUS` v1.40; refresh [NEXT_RTH_CAMPAIGN_RUNBOOK.md](NEXT_RTH_CAMPAIGN_RUNBOOK.md) (was anchored to `6e9e88b`/`73da9fdb`); update Notion-sync summary and Lane C pagination note ([#252](https://github.com/AdamEddahmouni/market-trading-platform/pull/252)). Item 9 gates and #222 isolation unchanged; no receipt or collector retarget. |
| **Key files** | `docs/platform/PROGRAM_STATUS.md`; `docs/engineering/{WORK_LOG,NEXT_RTH_CAMPAIGN_RUNBOOK,IMP_DUAL_CORPUS_01_NOTION_SYNC,IMP_DUAL_CORPUS_01_LANE_C}.md` |
| **Tests** | `python tools/imp.py format`; `lint`; `validate changed` / `check_docs_links` as applicable |
| **Related** | IMP-EVIDENCE-HARDENING-02 Lane F; **CURRENT_SOFTWARE_IMPLEMENTATION** `a1b556f8` ([#251](https://github.com/AdamEddahmouni/market-trading-platform/pull/251)) |
| **Notes** | Docs-only; does not advance **CURRENT_SOFTWARE_IMPLEMENTATION** when merged. |

## 2026-09-17 — Item 9 next-RTH preflight CI fixes (Lane E)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `paper/calibration`, `tools`, `docs` |
| **Summary** | PR #251 review fixes: moved OS process listing for duplicate `--poll` detection from governed `src/` into `tools/item9_next_rth_preflight.py`; classified new Item 9 CLIs in repository-closure audit. Preflight behavior unchanged (read-only, six dispositions). |
| **Key files** | `item9_next_rth_preflight.py` (src + tools), `POST_BUILD35_SUBSYSTEM_CLASSIFICATION.json` |
| **Tests** | `phase0/test_analysis`, `validation/test_repository_closure`, `test_item9_next_rth_preflight`; `validate changed` |
| **Related** | PR #251; IMP-EVIDENCE-HARDENING-02 Lane E |
| **Notes** | Collector / OpenD poll modules untouched. |

## 2026-09-17 — Item 9 next-RTH preflight (Lane E)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `paper/calibration`, `tools`, `docs` |
| **Summary** | Added read-only Item 9 `next-rth-preflight` (library + CLI + `imp.py item9`) for next-RTH prospective collection readiness: RTH calendar, OpenD reachability, frozen collector authority `fed2d9f7…`, receipt path gate, duplicate `--poll` detection, governed invocation hints, and post-run `corpus-status` command. Does not run prospective collection or fit calibration. |
| **Key files** | `src/market_platform_foundation/paper/calibration/item9_next_rth_preflight.py`, `tools/item9_next_rth_preflight.py`, `tools/item9.py`, `tools/imp.py`, `tests/platform/test_item9_next_rth_preflight.py`, `docs/engineering/ITEM9_BAR_OHLCV_PROSPECTIVE_PROOF.md` |
| **Tests** | `python tools/imp.py test focused test_item9_next_rth_preflight`; `validate changed` (PR) |
| **Related** | IMP-EVIDENCE-HARDENING-02 Lane E; frozen collector `.imp-actual-01-phase-d` @ `fed2d9f7` |
| **Notes** | Collector semantics unchanged — preflight is observability only. |

## 2026-09-17 — IMP-EVIDENCE-HARDENING-02 Lane B holdout guard hardening

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `paper/calibration/dual_corpus`, intelligence training/production/fusion |
| **Summary** | Expanded fail-closed `UNTOUCHED_FORWARD_EVALUATION` (and taxonomy-derived forward holdout authorities) guards across Path A production fit/calibrate, BUILD 08 baseline fit, BUILD 14 calibration trainer, BUILD 18 training factory/materialization, and hyperparameter grid expansion. Evaluation-only surfaces (validation inference, calibration apply, promotion ranking) remain unblocked. |
| **Key files** | `paper/calibration/dual_corpus/consumption.py`; `intelligence/production/{training_build,model,calibrator}.py`; `intelligence/fusion/calibrators.py`; `intelligence/baselines/{training,controls/*}.py`; `intelligence/training/{factory,datasets,search,trainers/*}.py`; `tests/platform/test_holdout_consumption_guards.py` |
| **Tests** | `python tools/imp.py format`; `lint`; `validate changed` (4128 passed, 30 skipped); `unittest` `test_holdout_consumption_guards` + `test_dual_corpus_contamination` (26 passed) |
| **Related** | IMP-EVIDENCE-HARDENING-02 Lane B; dual-corpus contract |
| **Notes** | Item 9 split logic untouched; no #222 merge. |

## 2026-09-17 — IMP-EVIDENCE-HARDENING-02 Lane A Path A label linker

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `intelligence/outcomes`, `paper/calibration` |
| **Summary** | Added fail-closed Path A linkage from Item 9 prospective receipts to post-horizon TRADE label evidence IDs without mutating source observation hashes or embedding labels into feature payloads. `build_dataset_row` optionally populates `path_a_label_evidence_ids` when lawful label artifacts are supplied. |
| **Key files** | `src/market_platform_foundation/intelligence/outcomes/path_a_label_linker.py` (created); `src/market_platform_foundation/paper/calibration/item9_calibration_protocol.py`; `tests/intelligence/test_path_a_label_linker.py`; `docs/engineering/IMP_DUAL_CORPUS_01_LANE_C.md` |
| **Tests** | `unittest` `test_path_a_label_linker` + `test_item9_calibration_protocol` + `test_post_horizon_label_evidence` **44 passed**; `python tools/imp.py validate changed` **3901 passed**, 29 skipped, 0 fail |
| **Related** | IMP-EVIDENCE-HARDENING-02 Lane A; `IMP_DUAL_CORPUS_01_LANE_C.md` |
| **Notes** | No #222 file overlap. Item 9 remains NOT_CALIBRATED; no fitting or gate changes. |

## 2026-09-17 — IMP-EVIDENCE-HARDENING-02 Lane D session calendar + quality schema

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `market_data/historical_development` |
| **Summary** | Historical RTH builds now treat declared early-close dates as short tradable sessions (210 expected 1m bars, 13:00 ET close) instead of excluding them or assuming 390-minute grids. Quality reports expose machine-readable session/row counters, session-kind-aware missing intervals, and `quality_status` while preserving legacy v1 field names. |
| **Key files** | `market_data/historical_development/rth_session.py`, `quality.py`, `builder.py`, `shadow/session.py`, `tests/platform/test_historical_session_quality.py`, `docs/engineering/IMP_DUAL_CORPUS_01_LANE_B_HISTORICAL_RTH.md` |
| **Tests** | `unittest` historical/session suites (24 OK); `python tools/imp.py validate changed` (1842 passed, 3 skipped) |
| **Related** | IMP-EVIDENCE-HARDENING-02 Lane D; IMP-DUAL-CORPUS-01 Lane B |
| **Notes** | Shadow-run preflight still excludes early-close dates from full-grid capture; historical development uses `rth_session` session-kind classification. |

## 2026-09-17 — PROGRAM_STATUS after IMP-DUAL-CORPUS-01 #246 merge

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs/platform` |
| **Summary** | Pin `PROGRAM_STATUS` v1.39 to `origin/main` `da237fd14fa60117c50952de79bc20acdad1454d` after optional [#246](https://github.com/AdamEddahmouni/market-trading-platform/pull/246) Lane D (`92d7396e`) **`HISTORICAL_DEVELOPMENT_ONLY`** fixture e2e demo — **not** prospective, **not** `CALIBRATED`, **not** Item 9 evidence. Item 9 protocol floors unchanged; #222 remains isolated; no Moomoo/IBKR live verified claims. |
| **Key files** | `docs/platform/PROGRAM_STATUS.md`, `docs/engineering/WORK_LOG.md` |
| **Tests** | `python tools/imp.py format`; `python tools/imp.py lint`; `python tools/imp.py validate changed`; `python tools/check_docs_links.py` |
| **Related** | [IMP_DUAL_CORPUS_01_HISTORICAL_DEMO.md](IMP_DUAL_CORPUS_01_HISTORICAL_DEMO.md); branch `docs/program-status-after-246` |
| **Notes** | Docs-only follow-up to merged #246; frozen collector SHA `fed2d9f7` unchanged. |

## 2026-09-17 — IMP-DUAL-CORPUS-01 PR D docs/status sync

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs/platform`, dual-corpus architecture |
| **Summary** | Pin `PROGRAM_STATUS` v1.38 to `origin/main` `84d197d2` after IMP-DUAL-CORPUS-01 [#242](https://github.com/AdamEddahmouni/market-trading-platform/pull/242)–[#244](https://github.com/AdamEddahmouni/market-trading-platform/pull/244). Record dual-corpus authority boundaries, Item 9 `NOT_CALIBRATED` sample-gate honesty (floors 20/3/5; epoch **1**/1 below gate), Phase 5.5B #196 superseded by #224, #222 isolated. Add Notion sync summary markdown. |
| **Key files** | `docs/platform/PROGRAM_STATUS.md`; `docs/engineering/IMP_DUAL_CORPUS_01_NOTION_SYNC.md`; `docs/README.md`; `docs/architecture/DUAL_CORPUS_EVIDENCE_CONTRACT.md`; `docs/engineering/IMP_DUAL_CORPUS_01_LANE_{A_RECON,B_HISTORICAL_RTH,C}.md`; `docs/engineering/NEXT_RTH_CAMPAIGN_RUNBOOK.md` |
| **Tests** | `python tools/imp.py format`; `lint`; `validate changed` (docs-heavy) |
| **Related** | [IMP_DUAL_CORPUS_01_NOTION_SYNC.md](IMP_DUAL_CORPUS_01_NOTION_SYNC.md); branch `docs/dual-corpus-status-sync` |
| **Notes** | Did not recalibrate Item 9, merge #222, or mutate frozen receipts. Item 9 counts from canonical PROGRAM_STATUS + protocol constants; operator receipt dir not re-scanned in CI. |

## 2026-09-17 — Lane C post-horizon review fixes + main merge

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `intelligence/outcomes`, IBKR observational query |
| **Summary** | Merged `main` @ `859251ae` (dual-corpus #242) into PR #244; fail-closed IBKR historical TRADE fetch when post-horizon timing omitted; `NO_ELIGIBLE_TRADE` provenance uses filtered terminal candidates only. Item 9 remains `NOT_CALIBRATED`; frozen empirical artifacts untouched; IBKR live still `PROVIDER_UNVERIFIED`. |
| **Key files** | `providers/ibkr_observational/query_provider.py`; `intelligence/outcomes/label_evidence.py`; `docs/engineering/IMP_DUAL_CORPUS_01_LANE_C.md`; `tests/providers/test_g11_historical_trades.py`; `tests/intelligence/test_post_horizon_label_evidence.py` |
| **Tests** | `imp.py format` + `lint` pass; `test affected` / `validate changed` — 0 selected (clean vs merge-base in worktree); focused review tests — **3 passed**, 0 fail |
| **Related** | PR #244 `intelligence/post-horizon-label-evidence` |
| **Notes** | PR #244 not merged; Item 9 linker / feature-pipeline wiring / >1000 tick pagination still deferred. |

## 2026-09-17 — Item 9 persist stamps prospective corpus authority

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `paper/calibration` |
| **Summary** | `persist_receipt` now stamps `corpus_evidence_authority=PROSPECTIVE_FEATURE_EVIDENCE` on new Mode B prospective writes when the field is absent, without upgrading an explicit `HISTORICAL_DEVELOPMENT` stamp. Historical-development output dirs remain refused; frozen `item9-prospective-proof-receipts` artifacts not rewritten. Item 9 stays `PARTIAL_NOT_CALIBRATED`. |
| **Key files** | `src/market_platform_foundation/paper/calibration/bar_ohlcv_prospective_proof.py`; `tests/platform/test_dual_corpus_contamination.py` |
| **Tests** | `imp.py test focused` (3 new persist tests, 3 passed); `imp.py validate changed` — **3810 passed**, 29 skipped, 0 fail |
| **Related** | PR #242 branch `data/dual-corpus-contract` |
| **Notes** | Retrospective transport receipts unchanged (no authority stamp). |

## 2026-09-17 — IMP-DUAL-CORPUS-01 Lane A evidence contract

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `paper/calibration`, architecture docs |
| **Summary** | Land dual-corpus authority taxonomy (`HISTORICAL_DEVELOPMENT`, prospective/post-horizon/untouched classes), versioned historical dataset manifest + provenance validators, Item 9 discovery/persist contamination guards, and training consumption protection for `UNTOUCHED_FORWARD_EVALUATION`. Item 9 remains `PARTIAL_NOT_CALIBRATED`; frozen empirical artifacts untouched. |
| **Key files** | `src/market_platform_foundation/paper/calibration/dual_corpus/*`; `bar_ohlcv_prospective_proof.py`; `intelligence/production/training_build.py`; `docs/architecture/DUAL_CORPUS_EVIDENCE_CONTRACT.md`; `docs/engineering/IMP_DUAL_CORPUS_01_LANE_A_RECON.md`; `manifests/paper/schemas/historical_development_dataset_manifest.schema.json`; `tests/platform/test_dual_corpus_contamination.py` |
| **Tests** | `python tools/imp.py test affected` + `validate changed` — **3847 passed**, 29 skipped, 0 fail |
| **Related** | Branch `data/dual-corpus-contract`; [DUAL_CORPUS_EVIDENCE_CONTRACT.md](../architecture/DUAL_CORPUS_EVIDENCE_CONTRACT.md) |
| **Notes** | Lane B historical CLI and Lane C post-horizon label artifacts deferred. Compatible with unmerged `item9_calibration_protocol` worktree. |

## 2026-09-17 — PROGRAM_STATUS SHA classes: git tip vs frozen collector

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs` |
| **Summary** | Distinguish **current git `origin/main` tip** `03cd7280` (#238/#239/#240/#237) from the **frozen collector / evidence** SHA `fed2d9f7` (Sep 17 Mode B epoch through 16:00 ET) and the Sep 15 **historical pin** `7aade60b`. Item 9 stays **PARTIAL** / **NOT_CALIBRATED**; Item 7 stays **`ITEM7_PENDING_NATURAL_EVIDENCE`**. |
| **Key files** | `docs/platform/PROGRAM_STATUS.md` |
| **Tests** | `python tools/check_docs_links.py` |
| **Related** | [PROGRAM_STATUS.md](../platform/PROGRAM_STATUS.md); prior 2026-09-17 canonical-SHA entry |
| **Notes** | Docs-only. Did not retarget the collector, rewrite receipts, calibrate, or touch Item 7 / PR #222. |

## 2026-09-17 — PROGRAM_STATUS canonical SHA after IMP-ACTUAL-01

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs` |
| **Summary** | Pin **current Canonical** `origin/main` SHA to `fed2d9f7e183aecfcac61a7664df69aafc12ea25` (merge tips [#236](https://github.com/AdamEddahmouni/market-trading-platform/pull/236) `fed2d9f7`, [#235](https://github.com/AdamEddahmouni/market-trading-platform/pull/235) `e2c55dd4`, [#234](https://github.com/AdamEddahmouni/market-trading-platform/pull/234) `f47b449a`). Distinguish that SHA from the Sep 15 **historical pin** `7aade60b…` and from **empirical observation** receipt `runtime_git_sha` values (`aae13fd1…` PATH_PROOF_ONLY; `fed2d9f7…` phase-d Mode B). Item 9 stays **PARTIAL** / **NOT_CALIBRATED**; Item 7 stays **`ITEM7_PENDING_NATURAL_EVIDENCE`**. |
| **Key files** | `docs/platform/PROGRAM_STATUS.md` |
| **Tests** | `python tools/imp.py format`; `python tools/check_docs_links.py` |
| **Related** | [PROGRAM_STATUS.md](../platform/PROGRAM_STATUS.md); IMP-ACTUAL-01 Phase A/B/C entries below |
| **Notes** | Did not calibrate, collect receipts, touch Item 7 / PR #222 / `item7/natural-settlement`, or mutate Sep 17 / Phase D receipt files. |

## 2026-09-17 — Offline unit-test environment hermeticity (Lane B)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `tests`, `backend` |
| **Summary** | Offline provider/platform tests no longer assume OpenD is down on default loopback or that ``moomoo-api`` is absent. Unit cases inject unreachable loopback ports and explicit SDK-absence patches; live loopback reachability moved to ``tests/live_moomoo`` behind ``IMP_MOOMOO_LIVE``. Service-health unit probe uses an ephemeral port plus injected HTTP probe. SQLite forward-test repos and ``LocalStateConnection`` close before temp-dir cleanup on Windows. |
| **Key files** | `tests/support/hermetic_environment.py`; `tests/providers/test_moomoo_opend_primary_l1.py`; `tests/providers/test_opend_hop_interpreter.py`; `tests/platform/test_service_health.py`; `tests/platform/test_calibration_harness.py`; `tests/validation/test_offline_environment_hermeticity.py`; `src/market_platform_foundation/local_state/connection.py`; `src/market_platform_foundation/intelligence/paper_forward_bridge/sqlite_repository.py` |
| **Tests** | Focused unittest on changed modules; `imp.py validate fast` |
| **Related** | IMP-NEXT Lane B; Item 9 collector may keep OpenD on ``127.0.0.1:11111`` |
| **Notes** | Did not stop the collector, mutate Item 7/9 evidence, or merge. |

## 2026-09-17 — Lab Chart Lab accessibility polish

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui/lab` |
| **Summary** | Closed known Lab defects without redesign: Chart Lab tick/backfill and LinkTabs reach the 44px touch floor (including BP_SM), Lab/chart-lab muted/meta copy uses `--imp-text-md` instead of 13px `--imp-text-sm`, and the inner Vela heading is an `h3` aligned with CSS. Canonical `/lab/chart-lab` and `/research/vela-chart-lab` redirect unchanged. |
| **Key files** | `ui/src/styles/lab.css`; `ui/src/styles/imp-vela-chart-lab.css`; `ui/src/components/imp-ui/imp-ui.css`; `ui/src/components/charts/ImpVelaChartLabPage.tsx`; `ui/src/components/lab-shared/labAccessibilityContract.test.ts`; `ui/src/App.test.tsx` |
| **Tests** | Focused UI: 100/100 (`labAccessibilityContract`, `impVelaLazyRoute`, `imp-ui`, `App.test` including `/research/vela-chart-lab` redirect). `npm run typecheck` pass. `npm run build` **200.66 KiB gzip** initial JS (budget 203 KiB unchanged). |
| **Related** | [ACCESSIBILITY.md](ACCESSIBILITY.md); [pages/lab.md](../ui-redesign-v2/pages/lab.md) |
| **Notes** | Browser on `/lab/chart-lab` (vite preview): tick/backfill and LinkTabs measured 44px at 760 and 390; muted/meta 14px; headings `h1` Lab / `h2` playground / `h3` Vela; backfill 120→170; no page overflow at 390. Vela vendor toolbar targets unchanged. Global `--imp-text-sm` unchanged. Item 7/9 out of scope. |

## 2026-09-17 — Item 9 read-only corpus-status CLI (Lane D)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `paper/calibration`, `tools`, `tests/platform` |
| **Summary** | Added governed-receipt corpus status and validation helpers on the frozen Item 9 calibration protocol, plus `tools/item9_corpus_status.py` (`corpus-status`, `classify`, `validate`) for operator read-only scans of `artifacts/ftep-v1-002/item9-prospective-proof-receipts/*.json` with sample-gate progress (never fits or writes receipts). |
| **Key files** | `item9_calibration_protocol.py`, `tools/item9_corpus_status.py`, `tests/platform/test_item9_corpus_status_cli.py`, `POST_BUILD35_SUBSYSTEM_CLASSIFICATION.json` |
| **Tests** | `python -m unittest tests.platform.test_item9_corpus_status_cli tests.platform.test_item9_calibration_protocol` |
| **Related** | `ITEM9_CALIBRATION_PROTOCOL_V1.md`, Item 7 `item7_corpus_collector.py` (separate semantics) |
| **Notes** | Skipped OpenD readiness sidecar (PR #236); not needed for JSON receipt scans. Classified `tools/item9_corpus_status.py` under `qualification-and-operations-tooling` after CI `unclassified path` on `validate-python-changed`. |

## 2026-09-17 — Item 9 Mode B OpenD quote-context reuse (IMP-ACTUAL-01 Phase B)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `paper/calibration`, Item 9 OpenD transport |
| **Summary** | Mode B `--poll` reuses one loopback OpenD quote context for the bounded run (open on first fetch, `finally` close on success/timeout/fail-closed exit). Each poll step still issues one `request_history_kline`; PIT, receipt schema, `raw_provenance_hash`, and fail-closed semantics unchanged. Single-shot `display`/non-poll loads remain open/close per call. |
| **Key files** | `tools/moomoo/opend_quote_transport.py` (`OpendQuoteKlineSession`); `bar_ohlcv_sources.py`, `bar_ohlcv_prospective_proof.py`; `ITEM9_BAR_OHLCV_PROSPECTIVE_PROOF.md`; `tests/providers/test_opend_history_kline_1m.py`, `tests/platform/test_bar_ohlcv_prospective_proof.py` |
| **Tests** | `unittest` `test_bar_ohlcv_prospective_proof` + `test_opend_history_kline_1m` (46 OK); platform `test_bar_ohlcv*` (41 OK); `imp.py format`/`lint` OK |
| **Related** | [ITEM9_BAR_OHLCV_PROSPECTIVE_PROOF.md](ITEM9_BAR_OHLCV_PROSPECTIVE_PROOF.md); Phase A PR #234; base includes Phase C PR #235 (`e2c55dd4`) |
| **Notes** | Item 9 remains `NOT_CALIBRATED`; Item 7 `ITEM7_PENDING_NATURAL_EVIDENCE`. No calibration, no new prospective receipts. Live reconnect smoke not claimed. |

## 2026-09-17 — Governed JSONL discovery scope (IMP-ACTUAL-01 Phase C)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend`, `intelligence`, `docs` |
| **Summary** | Item 7 corpus status no longer recursively scans `artifacts/**/*.jsonl` or `.local/**/*.jsonl`; governed outcome discovery is limited to known `intelligence_records.jsonl` paths under `IMP_STATE_DIR`. Non-governed local JSONL is ignored; governed UTF-8 violations and malformed lines fail closed with explicit errors. |
| **Key files** | `src/market_platform_foundation/intelligence/production/governed_jsonl_discovery.py` (created); `corpus_collector.py`, `corpus_persistence.py`, `corpus_collection_status.py`; `tests/intelligence/test_governed_jsonl_discovery.py`; `docs/engineering/NEXT_RTH_CAMPAIGN_RUNBOOK.md` |
| **Tests** | `python tools/imp.py test focused tests/intelligence/test_governed_jsonl_discovery.py`; `test_item7_corpus_collector.py`; `validate changed` |
| **Related** | IMP-ACTUAL-01 Phase C; Phase A `f47b449a` (PR #234) |
| **Notes** | Item 7 remains `ITEM7_PENDING_NATURAL_EVIDENCE`; no settlement or corpus minting. |

## 2026-09-17 — Item 9 governed calibration protocol V1 (ITEM9-02)

| Field | Value |
|-------|-------|
| **Status** | `complete` — `ITEM9_CALIBRATION_PROTOCOL_READY`; Item 9 remains `PARTIAL / NOT_CALIBRATED` |
| **Area** | `paper/calibration`, Item 9 |
| **Summary** | Froze Item 9 calibration protocol/schema/tests without fitting. Path A 5m labels remain TRADE-only (bars cannot compose them). Future Mode B receipts hash fetched kline rows; the 2026-09-17 path-proof receipt is immutable and `PATH_PROOF_ONLY` due to SHA256(`[]`). |
| **Key files** | `docs/architecture/ITEM9_CALIBRATION_PROTOCOL_V1.md`; `manifests/paper/item9_calibration_dataset_v1.json`; `src/market_platform_foundation/paper/calibration/item9_calibration_protocol.py`; `bar_ohlcv_sources.py`; `bar_ohlcv_prospective_proof.py`; `tests/platform/test_item9_calibration_protocol.py` |
| **Tests** | `PYTHONPATH=src` venv 3.11 `unittest tests.platform.test_item9_calibration_protocol tests.platform.test_bar_ohlcv_prospective_proof` → **42 passed**. `imp.py format` / `lint` pass. `check_docs_links.py` **OK 227 files**. `validate changed` **3779 / 29 skip / 12 fail / 5 err** — OpenD-live + SDK-present provider tests, port-bound health, and Windows SQLite temp cleanup; not Item 9 protocol regressions. |
| **Related** | [ITEM9_CALIBRATION_PROTOCOL_V1.md](../architecture/ITEM9_CALIBRATION_PROTOCOL_V1.md); Sep 17 `ITEM9_PROSPECTIVE_BAR_PATH_PROVEN` |
| **Notes** | Did not calibrate, did not edit the Sep 17 receipt, did not touch Item 7 / PR #222. Connect-churn left as a separate increment. |

## 2026-09-16 — UIR-01 Increment H: Lab experimental workbench

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui`, `docs` |
| **Summary** | Landed `/lab` as IMP's operator experimental workbench on current contracts: Overview, Validation, Simulation, and Chart Lab. Research keeps interpretation of the same `/research/models` and `/research/simulation` GETs. No Lab mutations. FTEP and hypotheses remain explicit gaps. `/lab`→`/research` redirect removed; `/research/vela-chart-lab` redirects to `/lab/chart-lab`. |
| **Key files** | Created: `docs/ui-redesign-v2/lab-contract-map.md`; `ui/src/components/lab-shared/*`; `ui/src/components/{demo,paper,live}-lab/*`; `ui/src/components/ModeLabRoute.tsx`; `ui/src/styles/lab.css`. Modified: `App.tsx`, `App.test.tsx`, `NavShell.tsx`(+test), `ModeResearchRoute.tsx`, Research validation/simulation/overview (Lab handoff links), `ImpVelaChartLabPage.tsx`, `impVelaLazyRoute.test.ts`, `FRONTEND_GUIDE.md`, `UIR_01_OPERATOR_UI_REDESIGN.md`, `pages/lab.md`, `information-architecture.md`, `research-contract-map.md`, `migration-map.md`. |
| **Tests** | Env healthy (worktree). Format pass. Lint/typecheck pass. `ui` vitest **740/740**, build initial **200.66 KiB gzip** (budget 203). `test affected` / `validate changed` **80/80** with CPython 3.11 (first affected run on system 3.10 errored ui1 collection — not a product failure). Docs links **OK 226 files**. Live browser API `:8881` + Vite `:5211`: Demo Lab overview and `/lab/validation` loaded; CDP overflow **ok** at 1440 (`1425/1425`), 768 (`753/753`), 390 (`390/390`). No Run control on validation. |
| **Related** | [lab-contract-map.md](../ui-redesign-v2/lab-contract-map.md), [FRONTEND_GUIDE.md](FRONTEND_GUIDE.md) |
| **Notes** | `item7/natural-settlement` untouched. `IMP_PAPER_EXECUTION` not enabled. **NO LAB MUTATIONS ADDED.** Implemented on Grok 4.6 after Kimi budget exhaustion. |

## 2026-09-16 — UIR-01 Increment G: Portfolio surface redesign

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui`, `docs` |
| **Summary** | Rebuilt `/portfolio` as the operator view of simulated/observed holdings, cash, P&L, risk context, and position-level Workspace handoff on current contracts (`origin/main` `54b82805`). Removed in-page `OrderTicket` so Workspace stays the Paper submit boundary. Buying power is formatted from `buying_power_minor` (never substituted with cash). No NAV, daily P&L, dollar allocation, or frontend risk score. Paper/Demo P&L is labeled simulated; Live is observational broker-reported. Attention reuses `derivePaperExceptions`. Desktop tables / mobile cards; trace overlay instead of a 360px column. |
| **Key files** | Created: `docs/ui-redesign-v2/portfolio-contract-map.md`; `ui/src/components/paper-portfolio/paperPortfolioPresentation.ts`(+test). Modified: `PaperPortfolioPage.tsx`(+test), `PaperPortfolioObservability.tsx`, `{Demo,Live}PortfolioPage.tsx`(+tests), `App.test.tsx`, `NavShell.tsx`(+test), `layout.css`, `{paper,demo,live}-portfolio.css`, `FRONTEND_GUIDE.md`, `DEVELOPER_RUNBOOK.md`, `UIR_01_OPERATOR_UI_REDESIGN.md`, `pages/portfolio.md`, `information-architecture.md`. |
| **Tests** | `ui`: vitest **720/720 passed**, `tsc --noEmit` pass, `vite build` pass (initial **200.60 KiB gzip**). Repo: `imp.py env` healthy, `format` pass, `lint` pass, `test affected` **80/80**, `validate changed` **80/80**, `check_docs_links.py` **OK 226 files**. Browser (worktree API `:8878` + Vite `:5204`): Paper empty/degraded authority at 1440/768/390 with CDP **no page-level overflow** (1425/1425, 753/753, 390/390); StatusBar intact; Workspace `/workspace/BIYA` cockpit still loads. |
| **Related** | [portfolio-contract-map.md](../ui-redesign-v2/portfolio-contract-map.md), [FRONTEND_GUIDE.md](FRONTEND_GUIDE.md), [UIR_01_OPERATOR_UI_REDESIGN.md](UIR_01_OPERATOR_UI_REDESIGN.md) |
| **Notes** | `item7/natural-settlement` untouched. Lab not started. Paper execution remains env-gated (`IMP_PAPER_EXECUTION`). Live populated broker P&L is still canary snapshot only. Remaining UI: Lab. |

## 2026-09-16 — UIR-01 Increment F: Research surface redesign

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui`, `docs` |
| **Summary** | Rebuilt `/research` as an interpretation-first evidence workspace on current IMP contracts (`origin/main` `6f5b6f3e`). Overview synthesizes what the evidence currently shows; Evidence, Validation, and Simulation are deep-linkable sections that fetch only their own endpoints. Claims, state, and honest availability lead; hashes, raw enums, and timestamps stay in methodology disclosures. Hypotheses, domains, source catalogs, supporting/contradictory flags, and FTEP campaign state are disclosed as contract gaps. The only conflict signal rendered is `ABSTAIN_CONFLICTING_EVIDENCE`. Radar Screeners and Opportunity L3 bridge into Research without fabricating relations. `/lab` still redirects here — Lab is unbuilt. |
| **Key files** | Created: `docs/ui-redesign-v2/research-contract-map.md`; `ui/src/components/research-shared/{ResearchSurface,ResearchOverviewSection,ResearchEvidenceSection,ResearchValidationSection,ResearchSimulationSection,researchPresentation}.{ts,tsx}` (+tests); `ui/src/styles/research.css`; `ui/src/components/charts/ResearchChartPanels.test.tsx`. Modified: `ModeResearchRoute.tsx`, `{Demo,Paper,Live}ResearchPage.tsx`(+tests), `App.tsx`/`App.test.tsx`, `NavShell.tsx`(+test), `RadarPage.tsx`(+test), `OpportunityDetailCard.tsx`, `ResearchChartPanels.tsx` (timeline table + claim slot), `semanticState.ts`(+test), `FRONTEND_GUIDE.md`, `UIR_01_OPERATOR_UI_REDESIGN.md`, `pages/research.md`, `information-architecture.md`. Deleted: `ResearchObservability.tsx`, `research/{ModelLabPanel,ResearchAnalyticsPanel,SimulationLabPanel}.tsx`, mode-specific `*-research.css`. |
| **Tests** | `ui`: vitest **713/713 passed** (prior Control baseline 652; +61 net), `tsc --noEmit` pass, `vite build` pass (initial **200.57 KiB gzip**; budget check passed). Repo: `imp.py env` healthy, `format` pass, `lint` pass (UI typecheck), `test affected` **80/80 pass**, `validate changed` **80/80 pass** (first `validate changed` hit a one-off ui1 ERROR; retry and direct `tests/ui1` **57/57 pass**), `check_docs_links.py` **OK 226 files**. |
| **Related** | [research-contract-map.md](../ui-redesign-v2/research-contract-map.md), [FRONTEND_GUIDE.md](FRONTEND_GUIDE.md), [UIR_01_OPERATOR_UI_REDESIGN.md](UIR_01_OPERATOR_UI_REDESIGN.md) |
| **Notes** | `item7/natural-settlement` untouched. No backend rewrite. Live populated visual walkthrough not clicked (protected Live boundary); behavioral coverage includes loading/empty/failure/conflict/deep-link/bridges. Remaining UI: Lab (deferred), Portfolio redesign. |

## 2026-09-16 — BE-01: operator endpoint leak-audit false positives

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend`, `platform/security` |
| **Summary** | Fixed pre-existing `UI_SECRET_LEAK_BLOCKED` 500s on `GET /operator/readiness` and `GET /operator/config` by teaching `leak_audit.scan_snapshot` to treat provider `credential_state` status enums and operator-config `fields[n].key` env-var identifiers as benign metadata (path- and shape-bounded). Real secret-shaped keys with live values and textual `SECRET_SCAN_RULES` matches remain blocked. Opportunity `instrument_key` stays DTO-stripped per RTH15 (`test_opportunity_summary_leak_audit.py`). |
| **Key files** | `src/market_platform_foundation/platform/security/leak_audit.py`; `tests/platform/test_security_foundations_p5.py`, `test_operator_configuration.py`, `test_operator_endpoint_leak_audit.py` (new) |
| **Tests** | `unittest` SecretAuditTest + OperatorConfigurationTests + OperatorEndpointLeakAuditTests (19 cases) pass; `imp.py format`/`lint` pass; `validate changed` hit unrelated Windows baseline noise in platform/providers (sqlite temp cleanup, service health port probe) |
| **Related** | UIR-01E Control isolation note in prior WORK_LOG entry; P5 `leak_audit.py` spec |
| **Notes** | No UI contract rename; `item7/natural-settlement` untouched |

## 2026-09-16 — UIR-01 Increment E: Control center rebuild

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui`, `docs` |
| **Summary** | Rebuilt `/control` from a legacy setup console into the operator's platform-health destination on a fresh worktree off canonical `d5a45b3f`. The page now answers what is wrong / what is affected / how serious / whether it is safe to operate / what to do next, in priority order: Platform status (readiness, runtime, backend context, market data as four distinct real facts — no synthetic health score) with lifecycle actions; Execution & authority (mode, data mode, execution mode, authority as separate concepts with a plain-language capability summary and the Paper account/session line); Needs your attention (only actionable items derived from real contract states); Providers (attention-first rows translating the backend `role` contract into capability + degradation-impact language, refresh actions, inactive providers behind disclosure); Opportunity feed readiness (the same READY/UNREADY/UNAVAILABLE/EMPTY semantics and humanized reasons as Command/Radar, so Command's "Open Control" lands on an explanation of that exact condition); Technical detail (router links + raw states behind disclosures). Sections degrade independently on partial endpoint failure and never render unknown state as healthy. Section anchors (`/control#control-feed`, `/control#control-authority`) make Command/StatusBar degraded-state links resolve into the matching explanation with scroll + highlight. The semantic adapter gained a reusable `platform` domain (lifecycle/readiness/check/update values) and the documented-but-missing providerHealth transport/credential values; readiness rows now surface the backend `role`/`required_credentials` fields the UI schema used to strip. `window.confirm` became an inline two-step confirm; `<a href>` full reloads became router links; the blue off-system styling and raw-enum pills are gone. |
| **Key files** | Created: `ui/src/components/control/{OperatorControlCenterPage.tsx,controlPresentation.ts}` (+2 test files). Modified: `ui/src/state/semanticState.ts`(+test; `platform` domain + providerHealth gaps + deep-link hrefs), `ui/src/api/schemas.ts` (provider `role`, `required_credentials`), `ui/src/api/hooks.ts` (`operatorLifecycleStatus`, `operatorConfig` keys/hooks), `ui/src/components/opportunity/OpportunityFeedState.tsx` (feed deep-link), `ui/src/components/mode-session/StatusBar.tsx`(+test; authority deep-link), `ui/src/components/imp-product/ImpProviderMatrixDrawer.tsx` (stale "Risk control" labels), `ui/src/App.tsx` (lazy import + mode prop), `ui/src/App.test.tsx` (Control route test + hooks mock), `ui/src/styles/operator-control.css` (rewritten on design tokens), `docs/engineering/FRONTEND_GUIDE.md`, `docs/engineering/UIR_01_OPERATOR_UI_REDESIGN.md`. Deleted: `ui/src/components/OperatorControlCenterPage.tsx`(+test) (legacy page). |
| **Tests** | `ui`: vitest **652/652 passed** (baseline 610; +42 net), `tsc --noEmit` pass, `vite build` pass (initial **200.52 KiB gzip ≤ 203 KiB**; baseline 200.41). Repo: `imp.py env` healthy, `format` pass, `lint` pass (UI typecheck), `test affected` **80/80 pass**, `validate changed` pass. Browser review (dedicated worktree API :8866 + vite :5199): Paper Control at 1440/768/390 with CDP-measured **no page-level horizontal overflow** (390/390, 753/753, 1425/1425); Demo Control with provider degradation + feed UNREADY explanation; Paper authority mismatch + Paper account line; Command UNREADY banner → Open Control deep link; in-page hash navigation (`#control-overview`) verified live; Radar regression-checked. |
| **Related** | [UIR_01_OPERATOR_UI_REDESIGN.md](UIR_01_OPERATOR_UI_REDESIGN.md), [FRONTEND_GUIDE.md](FRONTEND_GUIDE.md) |
| **Notes** | `item7/natural-settlement` untouched. **Backend issue isolated (pre-existing on canonical main, not caused by this change):** `GET /operator/readiness` and `GET /operator/config` return 500 `UI_SECRET_LEAK_BLOCKED` — the response secret-leak audit (`platform/security/leak_audit.py scan_snapshot`) flags the secret-shaped key *names* `credential_state` (enum values like `NOT_REQUIRED`) and config `fields[].key` (names like `APCA_API_KEY_ID`) as live secrets. Reproducible in-process on unmodified canonical code; the Control page handles it as designed (independent section error + retry). Fix belongs to the backend lane (e.g. benign-key allowance or payload restructure, mirroring the `/opportunities/summary` instrument_key fix in `tests/ui1/test_opportunity_summary_leak_audit.py`). A stale API server from the `ui-operator-redesign-current` worktree was found double-bound to port 8766; this session's servers were moved to dedicated ports (8866/5199) and this session's 8766 processes were stopped. Remaining: Research/Lab redesign, Portfolio redesign. |

## 2026-09-16 — UIR-01 Increment D: Command overview depth and decision hierarchy

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui`, `docs` |
| **Summary** | Turned Command from a functional summary into an operator command desk on a fresh worktree off canonical `02ac7072`. The KPI strip is now decision-oriented — Opportunity feed trust, Actionable now, Needs review (tier-1 urgent callout), Stale or degraded — derived from the live opportunities/attention contracts with semantic tones (icon + text + accent, never color alone); the phantom `tone-*` classes and the portfolio/live-context KPI duplicates (StatusBar/risk-ribbon overlap) are gone. Attention cards gained decision depth: explicit Signal object class, tier StatePill, a why-now line from human reason labels (raw codes in an L4 disclosure), absolute replay-aware surfaced timing, and an honest signal→opportunity bridge (`summary_id = attention_id` ingest identity) with a `/radar?selected=` deep link that preselects the row (and auto-opens the mobile detail sheet). The overview queue shows both queues by default with subsection headings, tab counts, and the full ARIA tabs keyboard pattern; Paper defaults to ranked because its candidate queue already presents the signals (no double rendering). Feed-UNREADY reasons humanize (`QUALITY_SUMMARY_NOT_HEALTHY` → "market data quality is degraded"); freshness words render operator labels ("Stale", "Replay", "Unavailable" — no mechanical lowercase) and UNAVAILABLE freshness is neutral honesty, not a critical alarm. StatusBar collapses the data/scope segments into the details popover below 720px (scope added to the popover so nothing is lost); Command mobile order is queue → KPIs → mode rows. Fixed a latent Paper-header 768px overflow (nowrap authority pill in squeezed tracks) by stacking the header at BP_MD; Command page breakpoints re-mapped to the contract scale (980/1080 → 1024). |
| **Key files** | Created: `ui/src/components/attentionPresentation.ts`(+test), `ui/src/components/imp-product/ImpOverviewKpiStrip.test.tsx`. Modified: `impOverviewMetrics.ts`(+test rewrite), `ImpOverviewKpiStrip.tsx`, `ImpOverviewBoard.tsx`, `ImpOverviewPrimaryQueue.tsx`(+test), `AttentionFeed.tsx`(+test), `opportunityPresentation.ts`(+test; bridge builder + unready humanizer), `OpportunityFeedState.tsx`, `FreshnessIndicator.tsx`, `imp-ui.css`, `imp-ui.test.tsx`, `{Demo,Paper,Live}NowPage.tsx`(+tests), `PaperCandidateQueue.tsx`, `ModeNowRoute.tsx`, `App.tsx` (attention retry wiring), `RadarPage.tsx`, `RadarOpportunitiesPanel.tsx` (`?selected=` deep link), `StatusBar.tsx`(+test), `imp-product.css` (KPI tones, mobile reorder, StatusBar collapse, dead `.imp-top-opportunities*` removal), `layout.css` (attention card structure), `{demo,paper,live}-now.css` (breakpoint re-map + Paper header stack), `App.test.tsx`. |
| **Tests** | `ui`: vitest **610/610 passed** (baseline 587; +23 net), `tsc --noEmit` pass, `vite build` pass (initial **200.42 KiB gzip ≤ 203 KiB**; baseline 200.40). Repo: `imp.py env` healthy, `format` pass, `lint` pass (UI typecheck), `test affected` **80/80 pass**, `validate changed` pass. Browser review (worktree API :8768 + vite :5176): Demo Command/Signals, Paper Command/Signals, Radar at 1440/768/390; CDP measured **no page-level horizontal overflow** at 390/768/1024/1280/1440; signal→Radar deep link verified end-to-end (desktop inline selection + mobile sheet auto-open); mobile order queue→KPIs→mode rows verified by geometry. |
| **Related** | [UIR_01_OPERATOR_UI_REDESIGN.md](UIR_01_OPERATOR_UI_REDESIGN.md), [FRONTEND_GUIDE.md](FRONTEND_GUIDE.md) |
| **Notes** | `item7/natural-settlement` untouched. Live interactive walkthrough not clicked through (protected boundary); Live non-mutation covered by `LiveNowPage` tests. The Paper-header 768px overflow was latent from Increment C (data-dependent: long authority pill labels) and is now fixed. Remaining: Control center rebuild (next major surface), Research/Lab redesign. |

## 2026-09-16 — UIR-01 Increment C: Command/Paper-Now convergence on the shared opportunity language

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui`, `docs` |
| **Summary** | Converged Command and Paper-Now opportunity presentation onto the Radar semantic primitives from a fresh worktree off canonical `21ab1ac1`. New shared module `ui/src/components/opportunity/` holds the single copy of presentation-state derivation, state label/tone maps, evidence-input summaries, eligibility/workspace/ack predicates, next-action resolution, the L1–L4 detail model (moved from `progressiveOpportunityModel.ts`), the compact `OpportunityCard`, and `OpportunityQueue` + `OpportunityFeedState` (one feed-state presentation: loading / error+retry / UNREADY banner / UNAVAILABLE / empty-why). Command's primary queue and Radar now render identical semantics; Paper-Now's candidate queue holds attention signals only (the dead embedded opportunity list was removed) and its header routes account/session IDs through `CopyableIdentifier` and execution/authority/data-health through `resolveSemanticState`. Provider health (`LiveProviderRibbon`, Live header, Live KPI strip) renders through the semantic adapter — no synthetic scores; `/diagnostics/provider` stays raw L4 by design. `ProgressiveOpportunityCard`, `now/OpportunityReviewCard`, `OpportunityFeedStatusBanner`, `impOpportunityDisplay.ts` (dead `opportunityTags`), and the legacy `progressive-opp-*` CSS are retired. Mobile Radar detail is now an overlay sheet below 1024px (backdrop, focus trap, Escape/close, scroll lock; full-screen below 720px). Action gating is unchanged: Workspace remains the only Paper submit boundary; STOP/INELIGIBLE suppress workspace and ack actions on every surface. |
| **Key files** | Created: `ui/src/components/opportunity/{opportunityPresentation.ts,opportunityDetailModel.ts,opportunityDetailFixtures.ts,researchArtifactEvidenceProjection.ts,OpportunityCard.tsx,OpportunityQueue.tsx,OpportunityFeedState.tsx,opportunity.css}` (+3 test files), `ui/src/components/radar/RadarDetailSheet.tsx`, `ui/src/lib/useMediaQuery.ts`. Modified: `RadarQueueTable.tsx`, `OpportunityDetailCard.tsx`, `RadarOpportunitiesPanel.tsx`, `ImpOverviewPrimaryQueue.tsx`, `ImpOverviewBoard.tsx`, `{Demo,Paper,Live}NowPage.tsx`, `PaperCandidateQueue.tsx`, `LiveProviderRibbon.tsx`, `liveDashboardViewModel.ts`, `impOverviewMetrics.ts`, `semanticState.ts` (ELIGIBLE entry), `App.tsx` (css import), `imp-product.css`, `layout.css`, `radar.css`, `TradeReviewLearningPanel.tsx`, tests for the touched surfaces, `FRONTEND_GUIDE.md`, `UIR_01_OPERATOR_UI_REDESIGN.md`. Deleted: `ProgressiveOpportunityCard.tsx`, `now/OpportunityReviewCard.tsx`(+test), `OpportunityFeedStatusBanner.tsx`(+test), `impOpportunityDisplay.ts`, `progressiveOpportunityModel.ts`, `progressiveOpportunityCockpit.test.ts`. |
| **Tests** | `ui`: vitest **587/587 passed** (baseline 559; +28 net), `tsc --noEmit` pass, `vite build` pass (initial **200.40 KiB gzip ≤ 203 KiB**; A+B was 200.36). Repo: `imp.py env` healthy, `format`/`lint` pass, `test affected` **80/80 pass**, `validate changed` pass. Browser review (worktree API :8768 + vite :5175): Demo Command/Signals/Radar and Paper Command/Signals at 1440/768/390; mobile sheet open/Escape/close verified; CDP measured **no page-level horizontal overflow** at 390/768/1440; Paper ack gating and authority-gated preview verified live. Live interactive walkthrough not clicked through (confirmation gate is a protected boundary); Live non-mutation covered by `LiveNowPage` tests. |
| **Related** | [UIR_01_OPERATOR_UI_REDESIGN.md](UIR_01_OPERATOR_UI_REDESIGN.md), [FRONTEND_GUIDE.md](FRONTEND_GUIDE.md) |
| **Notes** | `item7/natural-settlement` untouched (main checkout left dirty/on-branch as found). Freshness word `REPLAY` renders mechanically ("replay") — acceptable backend translation. Remaining: deeper Command rebuild (KPI tone styling, attention-card evidence), Research/Lab surfaces, Control rebuild (Phase 8). |

## 2026-09-16 — UIR-01 A+B review gate: feed-copy mode fix + mobile overflow fixes

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui` |
| **Summary** | Review-gate fixes on `ui/operator-redesign-current` before PR. (1) `RadarOpportunitiesPanel` rendered the Live by-design copy ("Live mode has no opportunity engine") for `feed_status=UNAVAILABLE` in **all** modes; now mode-aware — Live keeps the by-design explanation, other modes get the generic feed-unavailable empty state with an Open Control action (plus regression test). (2) Fresh CDP measurement at 390px in Paper mode found page-level horizontal overflow (648px) from two pre-existing unbreakable-token surfaces: the Paper-Now header `dl` (raw 64-char account/session hex IDs; `align-items: start` shrink-to-fit sized children to max-content) and the Command overview `ProgressiveOpportunityCard` (`Paper account <code>` hex + raw enum `dd`s). Fixed with `min-width: 0` on the grid/flex chain, `overflow-wrap: anywhere` on the token elements (mirroring the existing `.paper-risk-ribbon dd` rule), and `align-items: stretch` in the ≤720px header media query. No component/API changes; Increment C scope untouched. |
| **Key files** | `ui/src/components/radar/RadarOpportunitiesPanel.tsx`, `ui/src/components/radar/RadarPage.tsx` (pass `mode`), `ui/src/components/radar/RadarPage.test.tsx` (+1 test), `ui/src/styles/paper-now.css`, `ui/src/styles/imp-product.css` |
| **Tests** | `ui`: vitest **567/567 passed**, `tsc --noEmit` pass, `vite build` pass (initial **200.36 KiB gzip ≤ 203 KiB**). Repo: `imp.py format`/`lint` pass, `imp.py test affected` **80/80 pass**, `check_docs_links.py` OK (226 files). Browser re-verified: no page-level horizontal overflow at 390/768/1440 in Demo and Paper; `/signals`→`/?desk=signals`, `/explore?q=GME`→`/radar/screeners?q=GME` (filter note renders), `/discover`→`/radar`, `/lab`→`/research` verified live. |
| **Related** | [UIR_01_OPERATOR_UI_REDESIGN.md](UIR_01_OPERATOR_UI_REDESIGN.md) |

## 2026-09-16 — UIR-01 operator UI redesign: design system + shell + Radar (Increment A+B)

| Field | Value |
|-------|-------|
| **Status** | `complete` (Increment A+B; Increment C partially landed — Command desk tabs + attention card tier/freshness labels) |
| **Area** | `ui`, `docs` |
| **Summary** | Reimplemented the operator shell and discovery workflow on current canonical contracts (`origin/main` `42b1237a`), using `docs/ui-redesign-v2/` recovered plans as design guidance only (the stale `ui/operator-redesign-v2` branch was read as reference, never used as a base). Shipped the semantic design-token layer (7 state tones, spacing/radius/type scales, AA contrast fixes, 9 previously-undefined vars aliased), the pure `resolveSemanticState` adapter (translate-never-invent; unknown → neutral + raw + dev warning), an `imp-ui` primitive set (StatePill, AttentionBanner, FreshnessIndicator, ConfidenceIndicator, EmptyState/ErrorState, LinkTabs, CopyableIdentifier), a consolidated 40px `StatusBar` replacing the stacked ModeEnvironmentBar + ContextBar (raw enums/ISO timestamps moved behind an L4 details disclosure; mismatch/unavailable fail-closed banners preserved), and the new Radar section (`/radar` Opportunities + `/radar/screeners`) replacing `/discover` and `/explore` (redirects preserve deep links; `?q=` now filters screener rows). Opportunity presentation is progressive-disclosure: L1 decision summary always visible; L2 evidence/verification + risk, L3 historical/research, L4 technical (ranking vector, data quality, identifiers) behind disclosures. Paper acks (watch/dismiss/review) are authority-gated via `paperActionsPermitted` from the shell; Discover mixed-screener mutations, unmount release POST, 3s/120s timers, and visibility pause are preserved byte-identical. |
| **Key files** | Created: `ui/src/state/semanticState.ts` (+test), `ui/src/components/imp-ui/{StatePill,AttentionBanner,FreshnessIndicator,ConfidenceIndicator,CopyableIdentifier,FeedbackStates,LinkTabs}.tsx`, `imp-ui.css`, `imp-ui.test.tsx`, `ui/src/components/mode-session/StatusBar.tsx` (+test), `ui/src/components/radar/{RadarPage,RadarOpportunitiesPanel,RadarQueueTable,OpportunityDetailCard}.tsx`, `RadarPage.test.tsx`, `ui/src/components/ModeRadarRoute.tsx`, `ui/src/styles/radar.css`, `ui/src/lib/breakpoints.ts`, `docs/engineering/UIR_01_OPERATOR_UI_REDESIGN.md`. Modified: `ui/src/App.tsx` (routes/redirects/StatusBar/desk param), `NavShell.tsx` (operator IA: Command/Radar/Workspace/Portfolio/Research/Control; GATED badge removed), `ImpCommandSearch.tsx` (text queries → `/radar/screeners?q=`), `ImpExecutionPosture.tsx` (CopyableIdentifier), `ExploreObservability.tsx` (`filterQuery`), `DiscoverObservability.tsx` (human timestamps), `AttentionFeed.tsx` (tier text label, human reason label primary, surfaced freshness), `progressiveOpportunityModel.ts` (human age label), `tokens.css`, `imp-product.css`, `layout.css`, `mode-session.css` (dead CSS removed), `App.test.tsx`, `NavShell.test.tsx`, `ImpProductChrome.test.tsx`, `ImpExecutionPosture.test.tsx`, `docs/engineering/FRONTEND_GUIDE.md`, `docs/engineering/DEVELOPER_RUNBOOK.md`. Deleted: `ModeDiscoverRoute`, `ModeExploreRoute`, `ContextBar`(+test), `ModeEnvironmentBar`(+test), `{Demo,Paper,Live}DiscoverPage`(+tests), `{Demo,Paper,Live}ExplorePage`(+tests), `DiscoverPageSections`(+test), `discoverInspectorActions`, `discoverPageTestActions`, `OpportunityRadarCockpit`, `OpportunityRadarDensePanel`(+test), `OpportunityRadarIntro`, 6 per-mode discover/explore CSS files. |
| **Tests** | `ui`: vitest **566/566 passed** (baseline 526; +40 net), `tsc --noEmit` pass, `vite build` pass with bundle budget (**initial 200.36 KiB gzip ≤ 203 KiB enforced**; baseline was 201.10). Repo: `imp.py env` healthy, `imp.py format` pass, `imp.py lint` pass (UI typecheck), `imp.py test affected` **80/80 pass** (mandatory invariants + ui1). Browser review (local API + vite): Demo/Paper Command, Radar Opportunities/Screeners at 1440/768/390px; fixed two real mobile overflow defects found in review (35-char account id in top bar → CopyableIdentifier; status-bar sentence min-content → wrap ≤720px); verified no page-level horizontal overflow at 768/390 via CDP measurements. |
| **Related** | [UIR_01_OPERATOR_UI_REDESIGN.md](UIR_01_OPERATOR_UI_REDESIGN.md) (contract map + IA), `docs/ui-redesign-v2/` (design guidance), [FRONTEND_GUIDE.md](FRONTEND_GUIDE.md), [DEVELOPER_RUNBOOK.md](DEVELOPER_RUNBOOK.md) |
| **Notes** | `ProgressiveOpportunityCard` remains in use on Command/Paper-Now queues (Increment C convergence candidate). Mobile Radar keeps the dense table with contained internal scroll (drawer-based card is a follow-up). Provider-health chips in the mixed screener still render raw connection enums (adapter migration candidate). No backend changes; no new endpoints; no polling/cadence changes. `item7/natural-settlement` untouched. |

## 2026-09-16 — PROGRAM_STATUS pin after RTH15-00 merge (#224)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs` |
| **Summary** | Pin PROGRAM_STATUS v1.35 to canonical `origin/main` `dbccd92d` after #224 merge. RTH15-00 row is MERGED. No product or evidence change. |
| **Key files** | `docs/platform/PROGRAM_STATUS.md`, `docs/engineering/WORK_LOG.md`, `docs/engineering/AGENT_HANDOFF.md` |
| **Tests** | docs-only pin; `check_docs_links.py` on this worktree |
| **Related** | [#224](https://github.com/AdamEddahmouni/market-trading-platform/pull/224), [RTH15_00_TARGET_STATE.md](RTH15_00_TARGET_STATE.md) |
| **Notes** | Item 7 #222 remains isolated. No evidence mutation. |

## 2026-09-16 — RTH15-00 isolated-work reconciliation

| Field | Value |
|-------|-------|
| **Status** | `complete` (software/docs increment; Item 7 #222 still isolated) |
| **Area** | `evidence_capture`, `ui_api`, `hot_path_telemetry`, `ui`, `docs` |
| **Summary** | Reconciled isolated/post-close RTH-cycle work onto `origin/main` `d06f1f4c`. Recovered the optional evidence capture-context sidecar, ranked-summary leak hygiene, selected UX on current contracts, next-RTH hop catalog, and Sep 15 diagnosis archives. Did not mutate empirical/prospective evidence, Item 7 settlement, or schedulers. |
| **Key files** | `src/market_platform_foundation/evidence_capture/`, `tools/evidence_capture_context.py`, `src/market_platform_foundation/ui_api/opportunity_projections.py`, `src/market_platform_foundation/hot_path_telemetry/next_rth_latency_audit.py`, Discover/NavShell UI hygiene, `docs/engineering/RTH15_00_TARGET_STATE.md`, `docs/engineering/RTH15_00_RECONCILIATION_MATRIX.md` |
| **Tests** | `imp.py format` 0; `imp.py lint` 0 (after worktree `ui/npm ci`); FAST 23/0/0; focused unittest 33/0; docs links OK (223); intelligence worker 1937/0; UI vitest 526/0, typecheck 0, build 0. `validate changed` providers 11 failures = OpenD/SDK `ENVIRONMENT` on this VM (not product). FULL/closure `NOT_RUN`. Benchmark **not executed**. |
| **Related** | [RTH15_00_TARGET_STATE.md](RTH15_00_TARGET_STATE.md), [RTH15_00_RECONCILIATION_MATRIX.md](RTH15_00_RECONCILIATION_MATRIX.md), [AGENT_HANDOFF.md](AGENT_HANDOFF.md), PRs #196 #123 #124 #126 #128 #201 #222 |
| **Notes** | `STAGE_2_APPLIED_AWAITING_NATURAL_CYCLE` **NONE OBSERVED**. Primary `item7/natural-settlement` checkout not mutated. Intelligence Benchmark Protocol not found. |

## 2026-09-16 — OPS-00 canonical agent operating system

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs`, `.cursor/rules`, `.cursor/skills` |
| **Summary** | Established the reusable IMP agent operating system: Composer-first model ladder with Grok 4.6 High escalation, Fast-model prohibition, single-agent default, worktree isolation, evidence-class protection, and skills/runbooks for recon, reconciliation, validation, orchestration, and handoff. RTH15-00 is sequenced after this layer and was not started. |
| **Key files** | Repo-root `.cursor/rules/imp-*.mdc`, `.cursor/skills/imp-*`, `.cursor/model-routing.json`; IMP `docs/engineering/AGENT_OPERATING_SYSTEM.md`, `sops/GIT_WORKTREE.md`, `sops/BRANCH_RECONCILIATION.md`, `templates/AGENT_HANDOFF.md`, `templates/AGENT_TASK_CONTRACT.md`; updates to `AGENTS.md`, `AI_MODEL_STRATEGY.md`, `DEVELOPER_OPERATING_SYSTEM.md`, `docs/README.md` |
| **Tests** | OPS-01 re-ran in `.worktrees/ops-canonical-agent-os`: `git diff --check` clean after trailing-whitespace fix; `python tools/check_docs_links.py` from IMP **OK (210 governance markdown files)**; `model-routing.json` policy assertions passed (Composer/`composer-2.5` default, Grok 4.6 High/`cursor-grok-4.6-high` escalation, Fast forbidden, one-agent default, Composer orchestrator, cheap maps to Composer not Fast, root/IMP rules identical, no nested skill copies); 44 rule/skill/agent files have valid single frontmatter. No product tests, runtime, or FTEP mutation. |
| **Related** | [AGENT_OPERATING_SYSTEM.md](AGENT_OPERATING_SYSTEM.md) |
| **Notes** | Isolated branch `ops/canonical-agent-operating-system` from `origin/main` `b8f1bf86` (unchanged at OPS-01). OPS-01 review removed accidental nested IMP skill copies (`skills/<name>/<name>/SKILL.md`), collapsed duplicate agent frontmatter on `architecture.md`/`implementation.md`, and stripped `git diff --check` trailing whitespace. Did not merge RTH branches or alter Item 7 checkout. |

## 2026-09-15 — Reconstruct launcher/Vite routing onto origin/main (isolated)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `tools/platform`, `ui/vite` |
| **Summary** | Reconstruct the `d588728d`-based launcher/routing candidate (`a2dd6ced`) onto current `origin/main` `7aade60b`. Repo `.venv` only (no `moomoo-api-test` auto-select), sklearn probe, operator URL `http://127.0.0.1:5173/`, Vite HTML bypass for `/discover` plus `/opportunities` `/intelligence` `/canary` proxies, control `port_is_open` instead of HTTP self-probe. **Skipped** `server.py` `normalize_ui_path` unquote because P1 owns that file. |
| **Key files** | `tools/platform/local_launcher.py`, `tools/platform/control_service.py`, `START_PLATFORM.cmd`, `PLATFORM_CONTROL.cmd`, `ui/vite.config.ts`, `tests/platform/test_local_launcher.py`, `tests/platform/test_operator_control_service.py`, `tools/validation_manifest.json`, `README.md`, `ui/README.md`, `docs/engineering/LOCAL_DEVELOPMENT.md`, `docs/superpowers/specs/2026-08-24-local-platform-launcher-design.md` |
| **Tests** | Isolated worktree, primary IMP `.venv`: `python -m unittest tests.platform.test_local_launcher tests.platform.test_operator_control_service` — **24 passed**. Percent-decode explain-ref test **not** run (server.py skipped). |
| **Related** | Source `diagnosis/launcher-routing-20260915` (`9b0781c9` / `a2dd6ced`); new branch `repair/launcher-routing-from-main-20260915`; frozen RTH not edited |
| **Notes** | **NOT FOR MERGE UNTIL 2026-09-15 RTH RECONCILIATION COMPLETE.** Keep stale diagnosis branch; do not merge it. Follow-on: P1 or a tiny separate commit for `normalize_ui_path` unquote. |

## 2026-09-15 — FTEP integrity: resolve gitignored session evidence from operator primary checkout

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `intelligence/paper_forward_bridge`, `rth-ops` |
| **Summary** | Linked worktrees failed `ftep integrity-check` / RTH ops preflight with `governed_session_start_evidence_present` because gitignored `governed-session-start-evidence.jsonl` lives only on the primary IMP checkout. Load session IDs from the operator primary tree when the worktree file is absent or has no `session_id` rows. Does not create empirical locks, copy evidence into git, or flip FTEP empirical gates. |
| **Key files** | `src/market_platform_foundation/intelligence/paper_forward_bridge/ftep_catalyst_watch.py`, `tests/intelligence/test_ftep_catalyst_watch.py`, `docs/engineering/WORK_LOG.md` |
| **Tests** | `python -m unittest tests.intelligence.test_ftep_catalyst_watch tests.intelligence.test_ftep_integrity tests.intelligence.test_rth_empirical_ops tests.intelligence.test_ftep_finviz_prospective_preflight tests.intelligence.test_item7_corpus_collector` **29/29 OK**; Item 9 `tests.platform.test_bar_ohlcv_prospective_proof` + comparator bridge **28/28 OK**. After fix: `ftep integrity-check FTEP-V1-002` **PASS** (`evidence_ids=2` from primary jsonl); `rth_empirical_ops --json preflight` **acceptance_label=RTH_EMPIRICAL_OPS_READY**, `hard_blockers=[]`, `disposition=SOFTWARE_READY_RTH_REQUIRED` (RTH closed). |
| **Related** | Lane B+E Tuesday RTH preflight; [TUESDAY_RTH_OPERATOR_CHECKLIST.md](TUESDAY_RTH_OPERATOR_CHECKLIST.md) |
| **Notes** | Worktree SHA base `d588728d`. Live OFF. No Paper/Live orders. |

## 2026-09-15 — PROGRAM_STATUS: refresh `main` SHA after #197/#198 (Lane J fix)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs`, `platform` |
| **Summary** | Reconcile [#200](https://github.com/AdamEddahmouni/market-trading-platform/pull/200) with live `origin/main` `aa063102468a3ca3dde3bf805f59c4d7d13965ce` after [#197](https://github.com/AdamEddahmouni/market-trading-platform/pull/197) **MERGED** and [#198](https://github.com/AdamEddahmouni/market-trading-platform/pull/198) **MERGED**. Phase 5.5B queue: #195/#196/#199/#200 **OPEN**; four empirical gates **NO**; **no** Tuesday RTH observational results invented. Labels `PHASE5_ENGINEERING_READY` + `RTH_EMPIRICAL_RUN_PENDING` unchanged. |
| **Key files** | `docs/platform/PROGRAM_STATUS.md`, `docs/engineering/WORK_LOG.md` |
| **Tests** | Docs-only |
| **Related** | Independent review REQUEST_CHANGES on #200 (stale `e0c7a923` pin) |
| **Notes** | Merge commit reconciles branch with `origin/main`; safety counters **0**. |

## 2026-09-15 — PROGRAM_STATUS: Phase 5.5B pre-RTH sync (Lane J)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs`, `platform`, `notion-sync` |
| **Summary** | Sync canonical pre-RTH state after Phase 5 close pin `e0c7a923` (#194): `PHASE5_ENGINEERING_READY` + `RTH_EMPIRICAL_RUN_PENDING`; FTEP-V1-002 sessions `fts-6DB7771FD9B3A991` / `fts-D93189A042A1BEF2`; four empirical gates **NO**; Item 7/9 **PARTIAL**; locks **0**; Live OFF; FTEP **not** `EMPIRICAL_ACTIVE`. Record Phase 5.5B **OPEN** software PRs [#195](https://github.com/AdamEddahmouni/market-trading-platform/pull/195)–[#197](https://github.com/AdamEddahmouni/market-trading-platform/pull/197) (**not** on `main`). **No** Tuesday RTH empirical results invented. Notion CURRENT banner payload prepared (MCP insert attempted). |
| **Key files** | `docs/platform/PROGRAM_STATUS.md`, `docs/engineering/WORK_LOG.md` |
| **Tests** | Docs-only |
| **Related** | Phase 5 close [#194](https://github.com/AdamEddahmouni/market-trading-platform/pull/194); [PHASE5_SOFTWARE_CLOSE_MEMO.md](PHASE5_SOFTWARE_CLOSE_MEMO.md) |
| **Notes** | Branch `phase55b/lane-j-notion-sync` from `e0c7a923`. Safety counters **0** (locks, Paper/Live orders, gate flips). |

## 2026-09-15 — PROGRAM_STATUS: Phase 5 software close at `d16511d2`

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs`, `platform` |
| **Summary** | Pin canonical `origin/main` SHA to `d16511d25b6ee1d79b8a5f89784922776b981e31` (merged #184–#193; tip #191). Record Phase 5 engineering merge queue **EMPTY** with lanes **A–J**: #189 `PRODUCTION_ASYNC_INTELLIGENCE_WORKER_READY` (default off; not Grok production); #191 `TRADE_REVIEW_DURABLE_LOOP_READY`; #187 `EXECUTION_DECISION_TRACE_RUNTIME_READY`; #185 `MATLAB_STRATEGY_RUNTIME_READY` (R2026a; CI UNAVAILABLE/fixture); #192 `PINETS_PARTIAL_PARITY_READY` (not FTEP_ELIGIBLE); #184 `VELA_SHADOW_RETAINED_INCOMPLETE_INTERACTIVE_ACCEPTANCE`; #193 `INTELLIGENCE_BOUNDARY_SECURITY_HARDENED`; #188 `RTH_EMPIRICAL_OPS_READY` (no live collection this session); #186 `PUBLIC_RECORD_PRIMARY_SOURCE_VERIFICATION_READY` (congressional NOT_SUPPORTED); #190 `STRATEGY_RESEARCH_PROMOTION_REGISTRY_READY` (in-memory; no auto Paper/Live). Labels `PHASE5_ENGINEERING_READY` + `RTH_EMPIRICAL_RUN_PENDING`. Empirical gates FINVIZ/Item9/Item7/hot-path latency **unearned**. **HOLD:** Item 7/9 **PARTIAL**; FTEP **not** `EMPIRICAL_ACTIVE`; simulator **not** `CALIBRATED`; Live OFF; empirical locks **0**; no Paper/Live orders. |
| **Key files** | `docs/platform/PROGRAM_STATUS.md`, `docs/engineering/WORK_LOG.md`, `docs/engineering/PHASE5_SOFTWARE_CLOSE_MEMO.md` |
| **Tests** | Docs-only; `python tools/check_docs_links.py` on PR |
| **Related** | [PR #184](https://github.com/AdamEddahmouni/market-trading-platform/pull/184)–[#193](https://github.com/AdamEddahmouni/market-trading-platform/pull/193); Phase 4 close at `e2079aac` (#183) |
| **Notes** | Branch `phase5/software-close-pin` from `origin/main` `d16511d2`. Next RTH commands in close memo (`IMP_STATE_DIR=.local`). No empirical lock auto-create. |

## 2026-09-15 — PROGRAM_STATUS: Phase 4 software close at `e2079aac`

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs`, `platform` |
| **Summary** | Pin Canonical origin/main SHA to `e2079aac89c13e6c3db4cded9f6f7f9a32cc6ce8` (merged #171–#182 through #176 tip). Record Phase 4 orchestrator merge queue **EMPTY** with lanes **A–J** + refills: #175 `DURABLE_ASYNC_INTELLIGENCE_OUTBOX_READY`; #173 `SEC_DETECTION_AUTHORITY_CONVERGED`; #171 `PRODUCTION_INGRESS_DEFAULT_ENFORCED` (OpenD materialize only); #177 Item 7 collection software (governed rows **0**, **PARTIAL**); #172 Item 9 `SOFTWARE_READY_RTH_REQUIRED` (not `CALIBRATED`); #176 `CONGRESSIONAL_DISCLOSURE_RUNTIME_READY` (fixture/runtime, not live feed); #180 `MATLAB_CONTRACT_READY`; #174 `STRATEGY_RUNTIME_FOUNDATION_READY`; #178 `TRADE_REVIEW_FOUNDATION_READY` (in-memory); #179 `EXECUTION_DECISION_TRACE_FOUNDATION_READY` (library-only); #181 options UI (not `OPTIONS_FLOW_LIVE`); #182 Edge Stats `EVIDENCE_NOT_PREDICTION`. Label `PHASE4_SOFTWARE_COMPLETE` + `RTH_EMPIRICAL_FOLLOWUP_REQUIRED` (not started; no corpus manufacture). **HOLD:** Item 7/9 **PARTIAL**; FTEP **not** `EMPIRICAL_ACTIVE`; simulator **not** `CALIBRATED`; Live OFF; no Paper/Live orders. |
| **Key files** | `docs/platform/PROGRAM_STATUS.md`, `docs/engineering/WORK_LOG.md` |
| **Tests** | Docs-only; `python tools/check_docs_links.py` on PR |
| **Related** | [PR #171](https://github.com/AdamEddahmouni/market-trading-platform/pull/171)–[#182](https://github.com/AdamEddahmouni/market-trading-platform/pull/182); Phase 3 closure at `8885d38a` (#169) |
| **Notes** | Branch `phase4/status-close` from `origin/main` `e2079aac`. No RTH collection. No empirical claims. |

## 2026-09-15 — PROGRAM_STATUS: Phase 3 burst close at `8885d38a`

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs`, `platform` |
| **Summary** | Pin Canonical origin/main SHA to `8885d38aec2fc08984f357e2ceb86c7d273c5fc2` (merged #159–#169). Record Phase 3 orchestrator merge queue **EMPTY** after burst lanes **I** (#168 options-flow replay) and UI (#169 a11y). Truthful gates unchanged: Item 7/9 **PARTIAL**; FTEP **not** `EMPIRICAL_ACTIVE`; simulator **not** `CALIBRATED`; Live OFF. #168 `OPTIONS_FLOW_REPLAY_EVIDENCE_READY` with `live_feed_claim=NOT_CLAIMED` (replay/fixture only). #169 UI-only; supersedes #114. List pending DRAFT PRs (#145, UX #128/#126/#124/#123, #117, #115). |
| **Key files** | `docs/platform/PROGRAM_STATUS.md`, `docs/engineering/WORK_LOG.md` |
| **Tests** | Docs-only; `python tools/check_docs_links.py` on PR |
| **Related** | [PR #167](https://github.com/AdamEddahmouni/market-trading-platform/pull/167)–[#169](https://github.com/AdamEddahmouni/market-trading-platform/pull/169); prior closure at `3b9e506` (#167) |
| **Notes** | Branch `phase3/status-close-burst` from `origin/main` `8885d38a`. No merge. |

## 2026-09-15 — Phase 3 Lane I: options-flow replay evidence (#168)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `research`, `intelligence/opportunity` |
| **Summary** | Merged replay pipeline for admitted options-flow slice → `OPTIONS_FLOW_REPLAY_EVIDENCE_ARTIFACT` with `authority_class=EVIDENCE_NOT_PREDICTION` and readiness `OPTIONS_FLOW_REPLAY_EVIDENCE_READY`. Opportunity detail attach via research artifact evidence bridge. Golden fixture `FIXTURE-OPTIONS-FLOW-REPLAY-NVDA`; `live_feed_claim=NOT_CLAIMED` — synthetic/replay only, not live whale/options tape. No execution or FTEP authority. |
| **Key files** | `src/market_platform_foundation/research/options_flow_replay/`; `intelligence/opportunity/research_artifact_evidence.py`; `tests/research/test_options_flow_replay_evidence_artifact.py`; `tests/intelligence/test_opportunity_options_flow_replay_evidence.py` |
| **Tests** | Focused unittest modules on PR CI |
| **Related** | [PR #168](https://github.com/AdamEddahmouni/market-trading-platform/pull/168); base `f986f5c551b1624c896d36562867f3136fcad4cb` |
| **Notes** | Does not close Item 7/9 or activate FTEP empirical mode. |

## 2026-09-15 — Phase 3 UI: skip-link, focus trap, keyboard a11y (#169)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui`, `a11y` |
| **Summary** | Merged product chrome skip-link to `#imp-main-content`, mobile nav focus trap, and keyboard-friendly disclosure patterns. UI-only — no Path A hop, opportunity mint, FTEP, Paper, or Live execution changes. Closes UX-01 track; [#114](https://github.com/AdamEddahmouni/market-trading-platform/pull/114) closed as superseded. |
| **Key files** | `ui/src/components/imp-product/ImpProductChrome.tsx`, `ui/src/styles/imp-product.css`, related nav tests |
| **Tests** | UI validation on PR |
| **Related** | [PR #169](https://github.com/AdamEddahmouni/market-trading-platform/pull/169); supersedes #114 |
| **Notes** | Independent of #115 DRAFT (do not merge before RTH). |

## 2026-09-15 — PROGRAM_STATUS: Phase 3 merge queue empty at `3b9e506`

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs`, `platform` |
| **Summary** | Pin Canonical origin/main SHA to `3b9e506` (merged #159–#166). Record Phase 3 orchestrator merge queue **EMPTY** with truthful software gates: SEC evidence foundation (#159) not `SEC_TO_OPPORTUNITY_VERTICAL_READY`; progressive cockpit (#160) `validate-ui` green not operator-smoke merge-candidate; async enrichment (#161) opt-in in-memory outbox; Vela workspace SHADOW (#162, 202.99 KiB gzip); Edge Stats `EVIDENCE_NOT_PREDICTION` (#163); Item 7 corpus COLLECTION (#164) with governed rows **0** / not `PRODUCTION_FORECAST_ARTIFACT_READY`; congressional PREP only (#165); `HOT_PATH_TELEMETRY_SOFTWARE_WIRED` (#166) not `LIVE_HOT_PATH_LATENCY_VALIDATED`. **HOLD:** Item 7/9 **PARTIAL**; FTEP **not** `EMPIRICAL_ACTIVE`; simulator **not** `CALIBRATED`; Live OFF. Phase 2 row at `0eca0c8b` preserved — not reopened. |
| **Key files** | `docs/platform/PROGRAM_STATUS.md`, `docs/engineering/WORK_LOG.md` |
| **Tests** | Docs-only; `python tools/check_docs_links.py` on PR |
| **Related** | [PR #159](https://github.com/AdamEddahmouni/market-trading-platform/pull/159)–[#166](https://github.com/AdamEddahmouni/market-trading-platform/pull/166); [PROGRAM_STATUS.md](../platform/PROGRAM_STATUS.md); Phase 2 closure entry below |
| **Notes** | Branch `phase3/status-close` from `origin/main` `3b9e506`. No merge. No empirical claims. |

## 2026-09-15 — PROGRAM_STATUS: Phase 2 merge queue empty at `0eca0c8b`

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs`, `platform` |
| **Summary** | Pin Canonical origin/main SHA to `0eca0c8b` (merge #153). Record Phase 2 orchestrator merge queue **EMPTY** with merged lanes A/B/C/D/F/G/H (#151–#157), Lane E **NO-GO** (no governed Path A training corpus), ingress default still `put_event` unless `ingress_router=`, SEC vertical honest limits (not `SEC_TO_OPPORTUNITY_VERTICAL_READY`; Market Trackers live **NOT_EXECUTED**), Vela lab-only, Grok detail-only attach. Item 7/9 stay **PARTIAL**; FTEP **not** `EMPIRICAL_ACTIVE`; Live OFF; simulator **not** `CALIBRATED`. FTEP-V1-002 durable sessions **2**, empirical locks **0** unchanged. |
| **Key files** | `docs/platform/PROGRAM_STATUS.md`, `docs/engineering/WORK_LOG.md` |
| **Tests** | `python tools/check_docs_links.py` (pending on docs PR) |
| **Related** | [PR #153](https://github.com/AdamEddahmouni/market-trading-platform/pull/153) tip; Phase 2 merges #151–#157 |
| **Notes** | Docs-only orchestrator closure. Did not mass-rebase Lane I. Did not close #21 or UX stack. Did not claim tomorrow RTH work executed. |

## 2026-09-14 — Lane D PR #154: classify hot_path_telemetry for closure

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `validation`, `repository-closure`, Lane D |
| **Summary** | `validate-python-changed` on PR #154 failed with one closure audit error (`unclassified path: src/market_platform_foundation/hot_path_telemetry`), not perf gating (`perf=INCOMPATIBLE_BASELINE` is OBSERVE_ONLY telemetry). Classified the Lane D package under `rt01-trace-latency` and merged `origin/main` (#152) before re-push. |
| **Key files** | `artifacts/repository-closure/POST_BUILD35_SUBSYSTEM_CLASSIFICATION.json` |
| **Tests** | `python -m unittest tests.validation.test_repository_closure.CanonicalRepositoryClosureAuditTests` → **1 passed**; awaiting IMP Validation on pushed HEAD |
| **Related** | PR #154 `phase2/lane-d-replay-latency-baseline` |
| **Notes** | P7 `INCOMPATIBLE_BASELINE` on changed workload reflects 4 vs 8 logical CPUs on CI; does not affect `validate.py` exit code when tests pass. |

## 2026-09-14 — Phase 1 Lane A: canonical state-path contract (worktrees)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs`, `platform`, `ftep`, `git hygiene` |
| **Summary** | Verified `origin/main` at `f2a38a19`; created clean worktree `.worktrees/phase1-state-path-contract` on `work/phase1-state-path-contract`. Added `python tools/imp.py state-path`, `tools/state_path_diagnostic.py`, and `STATE_PATH_OPERATOR_CONVENTION.md` so linked worktrees cannot treat empty `.local` as missing FTEP sessions; gitignored governed session/release JSONL as local empirical evidence. Confirmed Item 7/9 tools on current main; documented binding `manifest_path` worktree provenance (immutable SQLite). |
| **Key files** | `tools/imp.py`, `tools/state_path_diagnostic.py`, `docs/engineering/STATE_PATH_OPERATOR_CONVENTION.md`, `docs/engineering/CONFIGURATION.md`, `docs/engineering/DEVELOPER_OPERATING_SYSTEM.md`, `tests/platform/test_state_path_diagnostic.py`, `.gitignore` |
| **Tests** | `python -m unittest tests.platform.test_state_path_diagnostic` → **3 passed** |
| **Related** | Canonical `.local/imp-state.sqlite3`; [PROGRAM_STATUS.md](../platform/PROGRAM_STATUS.md) governed-session count doc lag (Lane D) |
| **Notes** | Lane: Phase 1 Lane A (state-path / workspace). No FTEP default persistence behavior change; no SQLite mutation. Independent review: `APPROVE_MERGE_CANDIDATE` @ `9610d477`. |

## 2026-09-14 — Item 7 Lane B PRODUCTION forecast readiness

| Field | Value |
|-------|-------|
| **Status** | `complete` — software readiness; Item 7 **`ITEM7_PARTIAL`** (not complete) |
| **Area** | `intelligence/production`, Item 7 Lane B |
| **Summary** | Fail-closed PRODUCTION contributor/calibration assessment, governed training-manifest build (skip failed feature rows; no hardcoded calibration probability), versioned specialist model JSON store, and `tools/item7_production_readiness.py` (assess / scan-contributors / validate-binding / build). Default assess disposition `PRODUCTION_FORECAST_BLOCKED_NO_GOVERNED_PATH_A_TRAINING_CORPUS`. Does not mint from quotes, weaken floors, or label CONTROL as PRODUCTION. |
| **Key files** | `src/market_platform_foundation/intelligence/production/readiness.py`, `model_store.py`, `training_build.py`, `tools/item7_production_readiness.py`, `tests/intelligence/test_item7_production_readiness.py` |
| **Tests** | `PYTHONPATH=src python -m unittest tests.intelligence.test_item7_production_readiness tests.intelligence.test_item7_production_forecast_progression -v` → **22 passed** |
| **Related** | Item 7 PARTIAL; Lane D `production/progression.py`; Path A `path_a_production_emit` / `path_a_forecast_producer`; branch `work/phase1-item7-production-readiness` @ `4dc4e4bb` |
| **Notes** | Independent review **APPROVE_MERGE_CANDIDATE**. No committed PRODUCTION JSON or training corpora. Empirical Item 7 still requires operator manifest + weekday RTH hop with `--contributor-path` / `--calibration-path`. |

## 2026-09-14 — Item 9 OpenD BAR_OHLCV_1M prospective proof operator (Phase 1 Lane C)

| Field | Value |
|-------|-------|
| **Status** | `complete` — software `ITEM9_PROSPECTIVE_PROOF_TOOL_READY`; empirical prospective 1m `SOFTWARE_READY_RTH_REQUIRED` |
| **Area** | `paper/calibration`, `tools/moomoo`, Item 9 |
| **Summary** | Added `opend_bar_1m_prospective_proof.py` with Mode A `RETROSPECTIVE_TRANSPORT_PROOF` / `NOT_PROSPECTIVE_EVIDENCE` and Mode B prospective (records `signal_time` at start, refuses retrospective `--signal-time-ns`, RTH-gated `--poll`, `POLL_REQUIRED` when RTH active without `--poll`, off-hours `SOFTWARE_READY_RTH_REQUIRED`, versioned JSON receipt with operator `--experiment-id`). Core contract in `bar_ohlcv_prospective_proof.py`. Item 9 stays PARTIAL, NOT_CALIBRATED. |
| **Key files** | `src/market_platform_foundation/paper/calibration/bar_ohlcv_prospective_proof.py`; `tools/moomoo/opend_bar_1m_prospective_proof.py`; `tests/platform/test_bar_ohlcv_prospective_proof.py`; `tests/platform/test_bar_ohlcv_comparator_experiment.py`; `docs/engineering/ITEM9_BAR_OHLCV_PROSPECTIVE_PROOF.md` |
| **Tests** | `PYTHONPATH=src python -m unittest tests.platform.test_bar_ohlcv_prospective_proof tests.platform.test_bar_ohlcv_comparator_experiment` → **35 passed** |
| **Related** | Item 9 PARTIAL; PR (Lane C); [ITEM9_BAR_OHLCV_PROSPECTIVE_PROOF.md](ITEM9_BAR_OHLCV_PROSPECTIVE_PROOF.md); base `origin/main` `f2a38a19` |
| **Notes** | No broker orders; no `CALIBRATED`; tomorrow RTH: `prospective --instrument-id AAPL --poll`. Independent review APPROVE_MERGE_CANDIDATE @ `b3daea2c`. |

## 2026-09-14 — Phase 1 Lane D: FTEP Finviz prospective preflight + durable session truth

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend`, `docs`, FTEP-V1-002 |
| **Summary** | Lane D: Added read-only `ftep_finviz_prospective_preflight` (+ `imp.py ftep finviz-prospective-preflight`) validating canonical `IMP_STATE_DIR`, integrity PASS, two governed SIGNAL_ONLY sessions, zero empirical locks, Finviz credential presence, `IMP_FINVIZ_LIVE` / `IMP_FTEP_PROSPECTIVE_CATALYST_INGRESS` gates, and RTH calendar. Off-hours disposition `SOFTWARE_READY_RTH_REQUIRED` is software-readiness success. Updated `PROGRAM_STATUS` and `SIGNAL_ONLY_LAUNCH_PREP` for durable session truth; catalyst watch distinguishes `LIVE_INGRESS_SUCCESS_ZERO_QUALIFYING_ROWS` vs failed ingress. FTEP not `EMPIRICAL_ACTIVE`. |
| **Key files** | `paper_forward_bridge/ftep_finviz_prospective_preflight.py`, `tools/ftep_finviz_prospective_preflight.py`, `ftep_catalyst_watch.py`, `docs/platform/PROGRAM_STATUS.md`, `artifacts/ftep-v1-002/SIGNAL_ONLY_LAUNCH_PREP.md`, `tools/imp.py` |
| **Tests** | `tests.intelligence.test_ftep_finviz_prospective_preflight` 3 passed; `tests.intelligence.test_ftep_prospective_catalyst_ingress` zero-row live ingress regression |
| **Related** | Phase 1 closed-market empirical readiness; branch `work/phase1-ftep-finviz-readiness` |
| **Notes** | Tomorrow live watch: `python tools/ftep_watch_catalysts.py FTEP-V1-002 --live-ingress --json` with `IMP_STATE_DIR` on primary `.local`; owner-temporary `IMP_FINVIZ_LIVE=1` only |

## 2026-09-14 — Grok intelligence ingest API (Lane I contracts)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs`, `intelligence/contracts` |
| **Summary** | Documented analysis-only Grok/agent Intelligence Ingest API with `AgentEnrichmentEvidenceV1`, forbidden mutation guards, bot role matrix, UI non-blocking timing gate, and Grok workspace config templates (no secrets, no trading authority). |
| **Key files** | `docs/architecture/GROK_INTELLIGENCE_INGEST_API.md`, `docs/architecture/adr/0013-grok-intelligence-ingest-boundary.md`, `docs/engineering/templates/GROK_AGENT_WORKSPACE_CONFIG.md`, `intelligence/contracts/agent_ingest.py`, `intelligence/contracts/ingest_ui_timing.py`, `tests/contracts/test_grok_intelligence_ingest_contract.py` |
| **Tests** | `python -m unittest tests.contracts.test_grok_intelligence_ingest_contract` → **7 passed** |
| **Related** | [GROK_INTELLIGENCE_INGEST_API.md](../architecture/GROK_INTELLIGENCE_INGEST_API.md), ADR-0013 |
| **Notes** | HTTP/persistence ingest adapters deferred; does not touch FTEP/calibration/UI runtime. |

## 2026-09-14 — Observation ingress router foundation (Lane F)

| Field | Value |
|-------|-------|
| **Status** | `in-progress` |
| **Area** | `intelligence`, `docs` |
| **Summary** | Added in-process `ObservationIngressRouter` for idempotent, bounded, deterministic `EventV1` fan-out to typed consumers (store, detector stub, OE evidence, audit/replay journal, enrichment triggers) plus `dispatch_normalization_result` bridge. Documented missing capability gap in `OBSERVATION_INGRESS_ROUTER_V1.md`. Proved dispatch via existing Moomoo BUILD 03 normalization in unit tests only — not yet wired into live normalize paths. |
| **Key files** | `src/market_platform_foundation/intelligence/observation_ingress/**`, `docs/engineering/OBSERVATION_INGRESS_ROUTER_V1.md`, `tests/intelligence/test_observation_ingress_router.py` |
| **Tests** | `python -m unittest tests.intelligence.test_observation_ingress_router -v` |
| **Related** | Lane F observation ingress; PR #140; BUILD 03 normalization; BUILD 07 replay |
| **Notes** | Foundation / draft until normalize-path wiring; no broker subscribers; no FTEP/OpenD ledger edits. |

## 2026-09-14 — Lane E: preview stale server codes → REVALIDATION_REQUIRED

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui/paper-workspace` |
| **Summary** | Reconciled UX-00 P2 #6 onto `reconcile/ux-preview-revalidation-20260914`: removed unreachable `STALE` presentation status; map `PREVIEW_*_STALE`, `PREVIEW_EXPIRED`, `PREVIEW_INTENT_MISMATCH`, and `PREVIEW_REQUIRED` errors to `REVALIDATION_REQUIRED` (supersedes draft PR #127). |
| **Key files** | `ui/src/components/paper-workspace/paperPreviewPresentation.ts`, `PaperPreviewStatus.tsx`, `paperPreviewPresentation.test.ts`, `docs/engineering/WORK_LOG.md` |
| **Tests** | `cd ui && npm run typecheck`; `npm test -- paperPreviewPresentation.test.ts PaperPreviewStatus.test.tsx` |
| **Related** | UX-00 forensic audit §13 P2 #6; supersedes PR #127 |
| **Notes** | No submit authority or backend risk changes. Lane J (#128/#126/#124/#123/#114/#115) untouched. Empirical: NONE. |

## 2026-09-14 — Item 7 Lane D production forecast progression diagnostics

| Field | Value |
|-------|-------|
| **Status** | `in-progress` — diagnostics-only foundation; Item 7 **`ITEM7_PARTIAL`** (not complete) |
| **Area** | `intelligence/production`, Item 7 Lane D |
| **Summary** | Added fail-closed Item 7 progression reporting for lawful quote → grid → pre-existing PRODUCTION `ForecastV1` → ledger → settlement → specialist/calibration empirical floors. Emits machine-readable JSON plus a readable summary with stage vector and first failing stage. Does not mint forecasts from quotes or assert `ITEM7_COMPLETE`. |
| **Key files** | `src/market_platform_foundation/intelligence/production/progression.py`, `tools/item7_forecast_progression_report.py`, `tests/intelligence/test_item7_production_forecast_progression.py` |
| **Tests** | `PYTHONPATH=src python -m unittest tests.intelligence.test_item7_production_forecast_progression -v`; `python tools/imp.py validate fast` |
| **Related** | Item 7 PARTIAL; OpenD capture → ledger bridge (read-only); Path A `path_a_forecast_store` / `path_a_forecast_producer`; draft PR #144 |
| **Notes** | Software diagnostics only — approve-as-draft, not Item 7 closure. Independent of BBO snapshot lane. No edits to `opend_capture_ledger.py`, FTEP, or hop CLI. |

## 2026-09-14 — Item 7 Lane C SNAPSHOT_BBO market-snapshot diagnostic

| Field | Value |
|-------|-------|
| **Status** | `in-progress` |
| **Area** | `tools/moomoo`, `tests/providers`, Item 7 BBO |
| **Summary** | Added read-only Item 7 harness that classifies vendor `get_market_snapshot` bid/ask without synthesizing from `last_price`, under distinct capability `SNAPSHOT_BBO` (not `US_EQUITY_L1`). Fixture tests cover missing/invalid spread/stale/delayed/valid BBO, temporal order, identity, and entitlement failure; live CLI probes only when US RTH and loopback OpenD are available, else honest block. Outcomes are `REAL_SNAPSHOT_BBO_VALIDATED` or `DERIVED_BBO_DESIGN_REQUIRED` only — never `ITEM7_COMPLETE`. Program Item 7 remains **PARTIAL**. |
| **Key files** | `tools/moomoo/item7_bbo_snapshot.py`, `tools/item7_bbo_snapshot_probe.py`, `tests/providers/test_item7_bbo_snapshot.py`, `artifacts/repository-closure/POST_BUILD35_SUBSYSTEM_CLASSIFICATION.json` |
| **Tests** | `PYTHONPATH=src python -m unittest tests.providers.test_item7_bbo_snapshot -v` |
| **Related** | Lane C Item 7; `docs/providers/MOOMOO_OBSERVATIONAL.md`; G5 depth remains separate derived path |
| **Notes** | Did not touch opend_capture_ledger, FTEP, paper/calibration, UI, or L1 adapter semantics. No orders. Classified top-level probe CLI in POST_BUILD35 closure inventory (fixes CI `validation` suite ERROR on unclassified path). |

## 2026-09-14 — Item 9 BAR_OHLCV_1M comparator input reconcile (PR #134)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `paper/calibration`, `providers/moomoo`, `tools` |
| **Summary** | Reconciled `work/item9-bar-ohlcv-1m` onto `origin/main` `0e2d731a` for PR #134. Lawful `BAR_OHLCV_1M` comparator dry-run harness loads admitted BIYA fixture or injected OpenD 1m klines with `available_time` at bar end, preserves signal/bar/provenance timing, and dry-runs `BarConservativeSimulator` without broker orders or `CALIBRATED`. Expanded fail-closed tests for malformed, stale, empty, same-time, and first post-signal fill paths. |
| **Key files** | `src/market_platform_foundation/paper/calibration/bar_ohlcv_sources.py`; `src/market_platform_foundation/paper/calibration/bar_ohlcv_experiment.py`; `tools/providers/run_bar_ohlcv_comparator_experiment.py`; `tools/moomoo/opend_quote_transport.py`; `tests/platform/test_bar_ohlcv_comparator_experiment.py`; `docs/architecture/PAPER_SIMULATOR_CALIBRATION_CONTRACT.md`; `docs/engineering/WORK_LOG.md` |
| **Tests** | `python tools/imp.py validate fast`; `python tools/imp.py test focused test_bar_ohlcv_comparator_experiment` |
| **Related** | [PAPER_SIMULATOR_CALIBRATION_CONTRACT.md](../architecture/PAPER_SIMULATOR_CALIBRATION_CONTRACT.md); PR #134; Item 9 PARTIAL — `COMPARATOR_INPUT_READY` / `RTH_PROOF_PENDING` |
| **Notes** | Alpaca comparator leg unchanged (GET-only). Live RTH OpenD 1m proof remains operator-dependent; no merge. |

## 2026-09-14 — Lane H Market Trackers SEC 3/4/5 adapter prep

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `market_trackers/sec_insider`, `docs/providers`, fixtures |
| **Summary** | Preparation-only adapter for LuxAlgo Market Trackers `insider-transactions`: pinned upstream commits/licenses, schema characterization, external source receipt, PIT clocks (no transaction-date public knowledge), EventV1 map prep with XA-01 fail-closed ticker resolution, deterministic public-record evidence for OE, candidate feature catalog, and golden fixtures — independent of Observation Ingress Router (Lane F). |
| **Key files** | `src/market_platform_foundation/market_trackers/**`, `docs/providers/MARKET_TRACKERS_SEC_INSIDER.md`, `docs/engineering/specs/MARKET_TRACKERS_SEC_INSIDER_ADAPTER_PREP.md`, `tests/fixtures/market_trackers/sec_insider/**`, `tests/market_trackers/test_sec_insider_adapter_prep.py`, `tools/validation_manifest.json` |
| **Tests** | `PYTHONPATH=src python -m unittest tests.market_trackers.test_sec_insider_adapter_prep` → **9 passed** (post review fixes) |
| **Related** | PR #143; Lane H takeover; `docs/providers/SEC_EDGAR.md`; `PROVIDER_NORMALIZATION_V1.md` |
| **Notes** | Live Market Trackers fetch NOT_EXECUTED; no execution dependency; Market Trackers replaceable over EDGAR primary. |

## 2026-09-14 — FTEP-V1-002 prospective Finviz catalyst ingress (PR #133)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `intelligence/paper_forward_bridge`, FTEP-V1-002 SIGNAL_ONLY |
| **Summary** | Opt-in Finviz Elite prospective ingress for read-only `watch-catalysts`: frozen-manifest catalyst pipeline, explicit `attention_data_kind` (FIXTURE vs LIVE_PROSPECTIVE), published vs retrieved timestamps on summaries, session correlation unchanged, no locks or manifest mutation. Gates: `IMP_FTEP_PROSPECTIVE_CATALYST_INGRESS=1` + `IMP_FINVIZ_LIVE` + configured token (env or credential store via `configured_token`); CLI `--live-ingress` only. `--live-ingress` fails closed in FIXTURE_SMOKE (`LIVE_INGRESS_UNAVAILABLE`); failed/zero-row live ingress does not substitute fixture rows. |
| **Key files** | `ftep_prospective_catalyst_ingress.py`, `ftep_catalyst_watch.py`, `opportunity/read_model.py`, `tools/ftep_watch_catalysts.py`, `tests/intelligence/test_ftep_prospective_catalyst_ingress.py`, `artifacts/ftep-v1-002/SIGNAL_ONLY_LAUNCH_PREP.md` |
| **Tests** | `tools/imp.py test focused` on `test_ftep_prospective_catalyst_ingress` + `test_ftep_catalyst_watch`; `validate fast` (rebased on `origin/main` `0e2d731`) |
| **Related** | PR #133; `SIGNAL_ONLY_LAUNCH_PREP.md` |
| **Notes** | SIGNAL_ONLY — not `FTEP_EMPIRICAL_ACTIVE`. Owner RTH live proof still pending operator gates + governed sessions. |

## 2026-09-14 — Merge origin/main (1b60b5a) into PR #136 test-only branch

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs`, merge hygiene |
| **Summary** | Merged `origin/main` at `1b60b5a` (#138 OE-07, atop #137 research) into `work/rebase-pr-118-20260914` for PR #136. Resolved `WORK_LOG.md` by stacking newest-first entries; test-only scope preserved (no branch `src/` changes). |
| **Key files** | `docs/engineering/WORK_LOG.md` |
| **Tests** | Await CI on pushed merge head (PR #136) |
| **Related** | PR #136; Cloud PR #118; PR #138 |
| **Notes** | No force-push. |

## 2026-09-14 — OE-07 API projection of evidence and persist contract fields (rebased)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui_api`, `docs/architecture` |
| **Summary** | `GET /opportunities/summary|{id}` and `GET /opportunities/{id}/evidence` lift review-row evidence, family admission, and dedupe/supersession facts to first-class JSON, and project persist `OpportunityV1.created_at_ns` / expected-edge at read time. Ingest does not stamp `decision_time_ns` onto review-row metadata (OE-05 fail-closed). No `MONITORED` / `OUTCOME_RECORDED` states. |
| **Key files** | `src/market_platform_foundation/ui_api/opportunity_projections.py`, `tests/ui1/test_opportunity_api.py`, `tests/intelligence/test_opportunity_ingest.py`, `manifests/ui1/schemas/opportunity_summary.schema.json`, `manifests/ui1/schemas/opportunity_evidence.schema.json`, `docs/architecture/OPPORTUNITY_CONTRACT.md`, `docs/architecture/DATA_CONTRACTS.md`, `docs/product/OPPORTUNITY_ENGINE_CURRENT_STATE_AND_IMPLEMENTATION_PLAN.md` |
| **Tests** | `PYTHONPATH=src .venv/Scripts/python.exe -m unittest tests.ui1.test_opportunity_api tests.intelligence.test_opportunity_ingest -v` → **18 passed** |
| **Related** | [OPPORTUNITY_CONTRACT.md](../architecture/OPPORTUNITY_CONTRACT.md); OE-04 #106; OE-05 #105; landed PR #138 (supersedes rebased #116) |
| **Notes** | Live off. No hop/OpenD/G7/Path A/FTEP/SQLite schema/V1-002/execution gates. |

## 2026-09-14 — Merge origin/main (79ae537) into PR #136 test-only branch

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs`, merge hygiene |
| **Summary** | Merged `origin/main` at `79ae537` (#132) into `work/rebase-pr-118-20260914` for draft PR #136. Resolved `WORK_LOG.md` conflict only; test-only scope preserved (no `src/` changes on branch). |
| **Key files** | `docs/engineering/WORK_LOG.md` |
| **Tests** | `python tools/imp.py test affected` and `validate fast` (recorded in PR #136 handoff) |
| **Related** | PR #136; Cloud PR #118 |
| **Notes** | Prior merge before #137/#138 landed on main. |

## 2026-09-14 — Non-semantic coverage tests for OE, FTEP, providers, Radar, persistence, comparator

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `tests/intelligence`, `tests/providers`, `tests/platform`, `tests/ui1`, `ui/imp-product` |
| **Summary** | Added fail-closed/wiring tests only: OE ingest timestamps and lifecycle enum bounds; FTEP identity/provenance and V1-002 manifest immutability; provider unknown-profile and coverage-gap serialization; Radar UNREADY/Live/INELIGIBLE surfaces; persist-off and Paper ledger join; comparator binding and threshold schema. No production runtime changes. |
| **Key files** | `tests/intelligence/test_opportunity_non_semantic_contracts.py`, `tests/intelligence/test_ftep_non_semantic_contracts.py`, `tests/providers/test_coverage_gap_fail_closed.py`, `tests/platform/test_persistence_and_comparator_contracts.py`, `tests/ui1/test_opportunity_radar_feed.py`, `ui/src/components/imp-product/OpportunityRadarDensePanel.test.tsx`, `ui/src/components/imp-product/OpportunityFeedStatusBanner.test.tsx` |
| **Tests** | Rebased onto `origin/main` `2e022383` (post #125/#131). `unittest` on new modules + `test_ftep_integrity` + `test_ftep_session_release` → **52 passed**. `ui` vitest on `OpportunityFeedStatusBanner` + `OpportunityRadarDensePanel` → **7 passed**. |
| **Related** | Cloud PR #118; coverage-gap audit receipt `internal/coverage-gap-audit.md` (project store); FTEP durable-state #125, session-release #131; PR #136 |
| **Notes** | Did not mutate FTEP-V1-002 artifacts, hop worktree `1381619`, Path A, G7, OpenD, Alpaca, or production runtime. Live off. Not `EMPIRICAL_ACTIVE` / not `CALIBRATED`. |

## 2026-09-14 — Research Export PIT-PENDING + EXTERNAL_RESEARCH_DATA fail-closed

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `research/export_v1`, `research/wave1`, `research/matlab` |
| **Summary** | Fixture Research Export v1 packages still emit honest `metadata.pit_status=PIT-PENDING` / `NON_EMPIRICAL_FIXTURE`. Loaders now require operator PIT metadata, refuse mixed `EXTERNAL_RESEARCH_DATA` on canonical IMP packages, and Wave 1 OOS stays blocked for fixture, external, and mixed classes. QR-01 MATLAB toolbox schema + UNAVAILABLE example landed (cloud `BLOCKED_NO_MATLAB`; not a production runtime). MATLAB consumes Research Export v1 JSON; overnight Parquet bridge remains historical. |
| **Key files** | `src/market_platform_foundation/research/export_v1.py`, `wave1/export_gate.py`, `wave1/runner.py`, `wave1/harness.py`, `matlab_environment.py`, `research/matlab/**`, `tests/research/test_research_export_v1.py`, `tests/research/test_wave1_experiment_harness.py`, `tests/research/test_matlab_environment.py`, `docs/research/RESEARCH_EXPORT_V1.md`, `docs/README.md`, `tools/research/build_research_export_v1.py`, `tools/validation_manifest.json` |
| **Tests** | Focused: `PYTHONPATH=src .venv/Scripts/python.exe -m unittest tests.research.test_research_export_v1 tests.research.test_wave1_experiment_harness tests.research.test_matlab_environment -v` → **24 passed** (rebase worktree on `origin/main` `2e022383`). |
| **Related** | [RESEARCH_EXPORT_V1.md](../research/RESEARCH_EXPORT_V1.md), QR-01/QR-03 MATLAB lab plan, Wave 1 `export_gate.py`; landed via squash-merge PR #137 (supersedes #119) |
| **Notes** | Did not stamp `PIT-PASS`. Did not run Wave 1 OOS. No hop `1381619`, no FTEP session, Live off. MATLAB not installed on this host. |

## 2026-09-14 — POST_BUILD35 inventory for ci_job_selector (PR #132)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ci`, `validation` |
| **Summary** | `validate-python-changed` failed repository-closure audit with `unclassified path: tools/ci_job_selector.py`. Added the path to the `validation-control-plane` scope in `POST_BUILD35_SUBSYSTEM_CLASSIFICATION.json` (inventory only; no prose rewrite). |
| **Key files** | `artifacts/repository-closure/POST_BUILD35_SUBSYSTEM_CLASSIFICATION.json` |
| **Tests** | `PYTHONPATH=src .venv/Scripts/python.exe -m unittest tests.validation.test_repository_closure.CanonicalRepositoryClosureAuditTests.test_canonical_audit_is_complete_non_destructive_and_uses_closed_vocabulary tests.validation.test_ci_job_selector` → **16 passed** |
| **Related** | PR #132 (`reconcile/ci-skip-slices-20260914`) |
| **Notes** | PR #132 remains draft; PR #121 stays open. |

## 2026-09-14 — CI skips unchanged expensive slices (rebased on main)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ci`, `developer-tooling` |
| **Summary** | Rebased PR #121 onto `origin/main` (includes #130). Path-classified GitHub CI so PRs skip UI `npm ci`/vitest/build, docs-link, and the admitted short-squeeze replay-fixture clone when those trees are unchanged; donor-bridge paths force the fixture clone so `SkipTest` cannot hide required failures. Jobs still report success (required 9/9 preserved). FAST is shallow and never clones the fixture. Push-to-`main` and `workflow_dispatch` pass `--always-run` in `imp-validate.yml` and in `imp-python.yml` changed mode. `python tools/imp.py ci jobs` is the local classifier. No `POST_BUILD35` closure artifact rewrite. |
| **Key files** | `tools/ci_job_selector.py`, `tests/validation/test_ci_job_selector.py`, `tools/imp.py`, `tools/validation_manifest.json`, `.github/workflows/{imp-validate,imp-python,monorepo-guardrails}.yml`, `.github/actions/install-actionlint/action.yml`, `docs/engineering/{VALIDATION,DEVELOPER_RUNBOOK,DEVELOPER_OPERATING_SYSTEM,WORK_LOG}.md`, `AGENTS.md` |
| **Tests** | `PYTHONPATH=src .venv/Scripts/python.exe -m unittest tests.validation.test_ci_job_selector tests.validation.test_imp_cli` → **25 passed** |
| **Related** | [VALIDATION.md](VALIDATION.md); PR #121 |
| **Notes** | Isolated `reconcile/ci-skip-slices-20260914` worktree. No hop/OpenD/G7/Path A/FTEP/persistence/V1-002/execution-gate changes. Live off. |

## 2026-09-14 — Classify capture ledger immutable persist conflicts

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `intelligence/outcomes`, OpenD capture → ledger bridge (Item 7) |
| **Summary** | `materialize_opend_capture_jsonl` now catches `RepositoryConflictError` from `put_event` and records `EVENT_PERSIST_CONFLICT` instead of aborting ingest. Fail-closed semantics preserved: conflicting payloads are refused, not overwritten. Regression test covers cross-file `sequence` reuse with differing quote payloads. |
| **Key files** | `src/market_platform_foundation/intelligence/outcomes/opend_capture_ledger.py`, `tests/intelligence/test_opend_capture_ledger_bridge.py` |
| **Tests** | `python -m unittest tests.intelligence.test_opend_capture_ledger_bridge` → **10 passed**. `python tools/imp.py test affected` → intelligence **passed**; platform suite **5 errors** (unchanged baseline on this host, unrelated paths). |
| **Related** | Item 7 capture→ledger bridge; hop ingest `source_record_id=str(sequence)` collision class |
| **Notes** | Does not create ledger examples, change Path A grid/BBO, mint forecasts, or scope event identity across capture files. Identity scoping remains follow-up. |

## 2026-09-14 — FTEP session-release test closure (PR #131)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `tests/intelligence/test_ftep_session_release.py` |
| **Summary** | Closed remaining PR #131 regression gaps: CLI `--account-id`-only execute refusal, persistence-not-configured execute block, `CAMPAIGN_ID_MISMATCH`, and `imp.py ftep session-release` command delegation wiring. |
| **Key files** | `tests/intelligence/test_ftep_session_release.py`, `docs/engineering/WORK_LOG.md` |
| **Tests** | `python -m unittest tests.intelligence.test_ftep_session_release -v` — 14 passed |
| **Related** | PR #131, prior entry “FTEP session-release fail-closed guards” |
| **Notes** | No runtime behavior change; tests only. |

## 2026-09-14 — FTEP session-release fail-closed guards (PR #131)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ftep`, `tools/ftep_session_release.py`, `tests/intelligence` |
| **Summary** | Hardened governed `session-release` execute: requires an explicit manifest guard (`--expect-manifest-fingerprint`, `--expect-manifest-path-substring`, or `--require-frozen-manifest-fingerprint`), blocks repo `artifacts/forward-test-campaigns/` bindings without those guards, and compares `campaign_slug` to the active binding `campaign_id`. Added regression tests for dry-run immutability, `NO_ACTIVE_BINDING`, frozen-guard happy path, slug mismatch, and unguarded execute refusal. |
| **Key files** | `tools/ftep_session_release.py`, `tests/intelligence/test_ftep_session_release.py` |
| **Tests** | `PYTHONPATH=src .venv/Scripts/python.exe -m unittest tests.intelligence.test_ftep_session_release -v` — 10 passed |
| **Related** | Draft PR #131 |
| **Notes** | Rebased onto `origin/main` at `bcf7be98` when clean; execute path unchanged for operators who already pass frozen/fingerprint guards. |

## 2026-09-14 — FTEP session-release CLI and persist test isolation

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ftep`, `tools/imp.py`, `paper_forward_bridge`, `tests/intelligence` |
| **Summary** | Added governed operator path `python tools/imp.py ftep session-release` wrapping durable `release_binding` with account/session/campaign guards, optional manifest fingerprint and path substring checks, dry-run gates, and JSONL release evidence. Stopped persistence tests from writing default `.local` when `IMP_PERSIST_STATE=1` leaks across cases by isolating `ActivatedForwardTestCase` / API forward-test tests to temp `IMP_STATE_DIR` and restoring env in FTEP session-start tests. |
| **Key files** | `projects/integrated-market-platform/tools/ftep_session_release.py` (new); `tools/imp.py`; `tests/intelligence/test_ftep_session_release.py` (new); `tests/intelligence/forward_test_activation_support.py`; `tests/intelligence/test_paper_forward_bridge.py`; `tests/intelligence/test_ftep_session_start.py`; `docs/engineering/WORK_LOG.md` |
| **Tests** | `unittest discover -s tests/intelligence -p test_ftep*.py` → **43 passed**; `tests.intelligence.test_forward_test_persistence` → **48 passed**; targeted forward-test/FTEP subset → **14 passed**; `python tools/imp.py test affected` → intelligence/runtime **passed**; validation/providers suites reported pre-existing failures on this branch snapshot |
| **Related** | Prior handoff entry documenting leftover `fts-BDF1D132A88A3EDF` fixture binding |
| **Notes** | No frozen manifest edits; no Paper/Live orders in tests. Operator may release the known temp-manifest binding via guarded CLI against primary `.local` state. |

## 2026-09-14 — Alpaca Paper GET-only comparator probe (live host blocked)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `providers/alpaca.paper`, `paper/calibration` |
| **Summary** | Weekday Paper comparator probe is now GET-only (`/v2/account`, `/v2/clock`, `/v2/positions`) via `AlpacaPaperReadOnlyHttpTransport`. `POST`/`DELETE` and `/v2/orders` fail closed as `ALPACA_READONLY_FORBIDDEN` before `urlopen`. Live `https://api.alpaca.markets` remains `LIVE_FORBIDDEN`. Probe always stamps `orders_placed=false` / `fabricated_fills=false`. Harness `--place-sandbox-orders` still cannot place orders or claim `CALIBRATED`. Classifier now converts timezone-aware UTC to `America/New_York` so a UTC VM cannot false-ready premarket as cash RTH. Item 9 stays PARTIAL. |
| **Key files** | `src/market_platform_foundation/providers/adapters/alpaca_paper_http.py`, `src/market_platform_foundation/paper/calibration/runner.py`, `tools/providers/probe_alpaca_paper.py`, `tests/platform/test_alpaca_paper_http.py`, `docs/providers/ALPACA_PAPER.md` |
| **Tests** | `PYTHONPATH=src python3 -m unittest tests.platform.test_alpaca_paper_http tests.platform.test_calibration_harness` → **48 passed**. Focused timezone selector 1/1. `python3 tools/check_docs_links.py` → OK 189 files. Authenticated Paper GET probe: origin `https://paper-api.alpaca.markets`, `clock_is_open=false` (pre-RTH), `orders_placed=false`; harness after TZ fix `WAITING_FOR_MARKET`, `calibrated=false`, `pair_count=0`. |
| **Related** | [ALPACA_PAPER.md](../providers/ALPACA_PAPER.md); Item 9 PARTIAL |
| **Notes** | No orders. Did not touch hop `1381619`, OpenD, G7, Path A, FTEP session, or V1-002 Paper orders. Live off. Not `EMPIRICAL_ACTIVE` / not `CALIBRATED`. |

## 2026-09-14 — Provider-activation DoD item 2 CLOSED (RTH combined hop)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs` |
| **Summary** | Record 2026-09-14 US cash RTH closure of provider-activation DoD item 2 (OpenD primary L1 + Finviz overlay on one Path A hop JSON; `tools/hop_json_gate_check.py` → `ITEM2_FLIP=yes`, `EMIT=run`, checker `FTEP=NOT_READY`). Items 7 and 9 stay PARTIAL; program FTEP stays `FTEP_EMPIRICAL_NOT_READY`. |
| **Key files** | `docs/platform/PROGRAM_STATUS.md`, `docs/providers/MOOMOO_OBSERVATIONAL.md`, `docs/providers/FINVIZ_ELITE.md`, `docs/engineering/WORK_LOG.md` |
| **Tests** | Docs-only; not run on this pass |
| **Related** | `tools/hop_json_gate_check.py`; Path A prospective hop; draft PR from `cursor/item2-closed-rth-d1ba` |
| **Notes** | Honest composer `EMPTY` / `NO_MATCHED_STRATEGY` documented as non-blocking for item 2. Did not hop, merge, or declare `EMPIRICAL_ACTIVE`. |

## 2026-09-14 — Runbook API probe paths

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs` |
| **Summary** | Replaced `DEVELOPER_RUNBOOK` example curl `:8766/diagnostics/provider` (UI route; API 404) with honest read-only probes `/provider/health` and `/context`. Documented UI Diagnostics at `:5173/diagnostics/provider`. |
| **Key files** | `docs/engineering/DEVELOPER_RUNBOOK.md` |
| **Tests** | `python3 tools/check_docs_links.py` (targeted docs) |
| **Related** | Project store `docs/runbook-reconciliation.md`; PR #103 / #110 |
| **Notes** | Docs only. Hop worktree stays `1381619`. No OpenD / FTEP / G7 / Path A runtime / Live changes. |

## 2026-09-14 — Item 7 OpenD capture → BUILD 15 ledger bridge

| Field | Value |
|---|---|
| **Status** | Complete (draft PR) |
| **Area** | Intelligence / BUILD 15 / Item 7 |
| **Summary** | Added `opend_capture_ledger.py` to ingest prospective OpenD `market_data.provider_envelope` JSONL via canonical `normalize_moomoo_capture`, classify raw vs tape-eligible vs Path A grid points, persist `EventV1` idempotently, and optionally register existing forecasts through `PredictionLedgerService` without settlement or synthetic probabilities. |
| **Key files** | `src/market_platform_foundation/intelligence/outcomes/opend_capture_ledger.py`; `tests/intelligence/test_opend_capture_ledger_bridge.py` |
| **Tests** | `PYTHONPATH=src python3 -m unittest tests.intelligence.test_opend_capture_ledger_bridge` — **9 passed** |
| **Related** | Item 7 capture funnel; BUILD 15 ledger/settlement |
| **Notes** | No AdamsGalaxyBook JSONL processed on cloud. Pre-existing normalizer wired; orchestrator is new. |

## 2026-09-14 — FTEP integrity: durable counts when SIGNAL_ONLY started

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend`, `intelligence/paper_forward_bridge` |
| **Summary** | Fixed `signal_only_session_requires_durable_state` to pass when `signal_only_session_started` is true and durable `governed_session_count` is positive (removed committed always-fail stub). Added RTH session-id regression plus negative tests (no sessions, wrong campaign, corrupt/unavailable persistence, authorization unchanged). |
| **Key files** | `src/market_platform_foundation/intelligence/paper_forward_bridge/ftep_integrity.py`, `tests/intelligence/test_ftep_integrity.py` |
| **Tests** | `python -m unittest tests.intelligence.test_ftep_integrity -v` (11 passed) |
| **Related** | RTH integrity checker leftover (`c8471a74`) |
| **Notes** | Does not weaken EMPIRICAL_ACTIVE, auto-record locks, or change V1-002 manifest. |

## 2026-09-14 — Track H leftover: fail-close remaining backend error_category gaps

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui_api`, `tools/platform` |
| **Summary** | Canonical taxonomy now maps Demo/Live opportunity-mutation reason codes to `MODE_BLOCKED` (they previously collapsed to `INTERNAL_ERROR` because they are raised as `PermissionError` rather than `_send_error_json("…")` literals). Loopback control-plane HTTP errors emit additive `error_category` using the same twelve-category envelope. |
| **Key files** | `src/market_platform_foundation/ui_api/errors.py`, `tools/platform/control_service.py`, `tests/ui1/test_error_taxonomy.py`, `tests/platform/test_operator_control_service.py`, `docs/architecture/DATA_CONTRACTS.md` |
| **Tests** | `PYTHONPATH=src python3 -m unittest tests.ui1.test_error_taxonomy tests.platform.test_operator_control_service -v` → **13 passed** after #109 frontend lock; local UI `typecheck` + vitest **476** + `build` (~203 KiB gzip) |
| **Related** | PR #90 error taxonomy; BL-0702 / RC-010; rebased onto `origin/main` `b842f37d` after #112 |
| **Notes** | Did not touch `ui/`, hop CLIs, Path A, G7, OpenD, Alpaca, FTEP, persistence, or research export. Live off. Not `EMPIRICAL_ACTIVE` / not `CALIBRATED`. Kept #112, #109, #110, and #108 WORK_LOG entries. |

## 2026-09-14 — Re-attribute remaining GridIQ / DS-340W mistaken-donor governance

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs` |
| **Summary** | Remaining Heller / GridIQ / DS-340W governance still deferred identity conflicts to hash-bound Revision 3, which names those materials as IMP donors. Current authority is the 2026-09-07 supersession notice (amended): Heller rows are mistaken transfers, not donors; independent `storage/*` stays **ADAPT**. Hash-bound Revision 3 and Phase 0A design spec are listed as notice-only supersessions (bytes unchanged). |
| **Key files** | `docs/superpowers/governance/2026-09-07-donor-authority-supersession-notice.md`, `docs/research/donors/{README,GRID_IQ_NOTES,DS340W_NOTES,DONOR_REUSE_MATRIX}.md`, `docs/architecture/ADR_AND_EVIDENCE_OWNERSHIP.md`, `docs/README.md`, `docs/engineering/WORK_LOG.md` |
| **Tests** | `python3 tools/check_docs_links.py` → OK 189 governance markdown files; `python3 tools/imp.py format` → pass (no Python paths); `python3 tools/imp.py validate changed` → PASSED 0/0/0/0 (docs-only selection); local `ui`: vitest 476 passed / 100 files, typecheck pass, build pass (initial gzip 203.00 KiB). GitHub IMP Validation 9/9 including `validate-ui` pending on this PR. |
| **Related** | [Donor Authority Supersession Notice](../superpowers/governance/2026-09-07-donor-authority-supersession-notice.md); prior-work audit recommendation 4 |
| **Notes** | Did not edit `DEVELOPER_RUNBOOK.md`, `PROGRAM_STATUS` Canonical SHA, hop/FTEP/Path A/G7/Alpaca/`ui/`, or hash-bound Revision 3 / Phase 0A design / ADR-DONOR-001 / ADR-LLM-001 bytes. No code behavior change. Rebased onto `origin/main` @ `46e4e6e1` (keeps #110 runbook P2 and #109 error_category log entries). |

## 2026-09-14 — UI consumes API `error_category` taxonomy

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui/api` |
| **Summary** | Frontend typed union in `ui/src/api/errors.ts` matches the twelve backend WS05 `error_category` values from PR #90. Request failures parse `{ error, reason_code, error_category }` and fail closed when the category is omitted or unknown — no frontend `reason_code` map and no server-map expansion. `fetchJson` dynamically imports the parser so it stays off the initial JS budget; classified Paper preview/submit errors surface `error_category: reason_code: error`. |
| **Key files** | `ui/src/api/errors.ts`, `ui/src/api/fetchJson.ts`, `ui/src/components/paper/OrderTicket.tsx`, `ui/src/components/paper-now/PaperNowPage.tsx`, `ui/src/components/paper-derivative/DerivativePaperPreviewPanel.tsx`, `tests/ui1/test_error_taxonomy.py`, `docs/engineering/FRONTEND_GUIDE.md` |
| **Tests** | `python3 -m unittest tests.ui1.test_error_taxonomy` 6/6; `cd ui && npm run typecheck`; `npm test -- --run` 488 passed; `npm run build` initial **202.96 KiB gzip** (budget 203.00; `errors-*.js` async chunk 0.62 KiB gzip). PR #109 `validate-ui` failed on `04f6dd58` at 203.30 KiB — parser moved off the initial graph. |
| **Related** | PR #90 backend taxonomy; TD-AP1 / API-004 frontend union |
| **Notes** | Opportunity API semantics, board-03 chrome, and `ui_api/errors.py` reason-code map unchanged. |

## 2026-09-14 — Developer runbook P2 nav names

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs` |
| **Summary** | Aligned operator/dev instructions with shipped #108 nav: **Workspace** (decision desk) vs **Portfolio** (orders history); **Lab** → `/research` with `/lab` redirect. Docs-only; no UI/backend or frozen-lane changes. |
| **Key files** | `docs/engineering/DEVELOPER_RUNBOOK.md`, `docs/engineering/FRONTEND_GUIDE.md` |
| **Tests** | `python3 tools/check_docs_links.py` — OK (189 files). UI `npm run typecheck` + `npm test -- --run` + `npm run build` — **476** vitest passed; initial bundle 203.00 KiB gzip. Docs-only; no `validate full`. |
| **Related** | [DEVELOPER_RUNBOOK.md](DEVELOPER_RUNBOOK.md), [FRONTEND_GUIDE.md](FRONTEND_GUIDE.md), PR #108 @ `0cf1c414` |
| **Notes** | Did not invent routes. Live remains off. |

## 2026-09-14 — UX-00 P2 wayfinding and operator trust strip

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui/imp-product`, `ui/nav`, `ui/context` |
| **Summary** | Renamed primary nav **Workspace** (decision desk) vs **Portfolio** (orders history); **Lab** links to `/research` with `/lab` redirect. Sticky workspace lane subnav with `aria-current`. Paper **account chip** on `ContextBar`; read-only **capability strip** and **provider matrix** drawer aggregating context capabilities, operator readiness, and deep links (no new API fields). |
| **Key files** | `NavShell.tsx`, `WorkspaceModuleNav.tsx`, `ContextBar.tsx`, `ImpCapabilityStrip.tsx`, `ImpProviderMatrixDrawer.tsx`, `App.tsx`, `layout.css`, `imp-product.css` |
| **Tests** | `ui` vitest (nav, context, capability, workspace nav) |
| **Related** | Project store `internal/ux-00-p2-wayfinding.md`, `docs/ux-00-followthrough.md` §12 P2 |
| **Notes** | Board-03 chrome preserved; frozen lanes untouched. |

## 2026-09-14 — UX-00 Overview primary queue + mobile sidebar

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui/imp-product`, `ui/now` |
| **Summary** | Unified Demo/Live/Paper Overview into one tabbed **Primary review queue** (Ranked, Attention, Both) via `ImpOverviewPrimaryQueue`, removing duplicate ranked/attention blocks from NOW bodies. Added collapsible sidebar overlay below 900px in `ImpProductChrome`. |
| **Key files** | `ui/src/components/imp-product/ImpOverviewPrimaryQueue.tsx`, `ImpOverviewBoard.tsx`, `ImpProductChrome.tsx`, `imp-product.css`, `DemoNowPage.tsx`, `LiveNowPage.tsx`, `PaperNowPage.tsx` |
| **Tests** | `ui`: vitest **469 passed**, typecheck pass, build pass |
| **Related** | Project store `docs/ux-00-followthrough.md`, `internal/ux-00-overview-queue.md`; UX-00 audit §12 |
| **Notes** | Rebased onto `origin/main` @ `99b7d82e` after #105. No backend or frozen-lane changes. |

## 2026-09-14 — UX-00 followthrough (board-03 wiring)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui/imp-product`, `ui/discover`, `ui/now` |
| **Summary** | Wired ContextBar quality badge to provider diagnostics, split `/signals` into an attention-only desk, structured Discover ranked vs mixed screener sections with drawer actions on dense radar, shared opportunity feed status banner, Paper NOW workspace handoff without requiring PASS preview, Ctrl+K command search focus, and removed duplicate Switch mode from the environment bar. |
| **Key files** | `ui/src/App.tsx`, `ui/src/components/ModeNowRoute.tsx`, `ui/src/components/ModeDiscoverRoute.tsx`, `ui/src/components/imp-product/OpportunityFeedStatusBanner.tsx`, `ui/src/components/discover-shared/DiscoverPageSections.tsx`, mode NOW/discover pages, `ui/src/styles/imp-product.css` |
| **Tests** | `ui`: vitest **468 passed**, typecheck pass, build + bundle budget pass |
| **Related** | Project store `docs/ux-00-forensic-audit.md` §12; PR #104 |
| **Notes** | No backend contract changes; board-03 chrome preserved. |

## 2026-09-14 — Lane G developer runbook (current vs historical)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs` |
| **Summary** | Verified developer workflow against current `origin/main` and added authoritative [DEVELOPER_RUNBOOK.md](DEVELOPER_RUNBOOK.md) with CURRENT setup, launch/shutdown, ports, logs, validation, provider/FTEP dry-run commands, and SQLite-vs-ephemeral persistence clarification. Refreshed stale pinned-SHA landing banners in AGENTS/CURSOR_CLOUD/DEVELOPER_OPERATING_SYSTEM in favor of `git fetch` + Program Status; linked operations troubleshooting runbook to the new sheet. |
| **Key files** | `docs/engineering/DEVELOPER_RUNBOOK.md` (new), `docs/README.md`, `docs/engineering/LOCAL_DEVELOPMENT.md`, `docs/engineering/CURSOR_CLOUD_ENVIRONMENT.md`, `docs/engineering/DEVELOPER_OPERATING_SYSTEM.md`, `docs/operations/RUNBOOK.md`, `AGENTS.md` |
| **Tests** | `python3 tools/check_docs_links.py` OK; `tools/validate.py` fast + `domain core` + `full` (5202/48/0); `ui` typecheck + 468 vitest + build; FTEP dry-run only (`session-start --dry-run`) |
| **Related** | Project store `docs/lane-g-runbook-verification.md`, `internal/lane-g-runbook.md`; PR #103 |
| **Notes** | No governed session, no orders. Rebased onto `origin/main` after #102. |

## 2026-09-14 — Lane D professor source and keyword catalog

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs/research` |
| **Summary** | Added research-only structured JSON catalog (26 sources, catalyst taxonomy), JSON schema doc, and index markdown for professor source/keyword completion without runtime provider changes. |
| **Key files** | `docs/research/PROFESSOR_SOURCE_KEYWORD_CATALOG.json`, `docs/research/PROFESSOR_SOURCE_KEYWORD_CATALOG.schema.json`, `docs/research/PROFESSOR_SOURCE_KEYWORD_CATALOG.md` |
| **Tests** | `python3` JSON parse validation (26 sources) |
| **Related** | Project store `docs/professor-source-keyword-catalog.md`, `internal/lane-d-sources.md`; Wave A `news-data-inventory.json` |
| **Notes** | `access_in_imp_claimed` false for all live sources; CONFIGURED headline wires unchanged in `news/sources.py`. |

## 2026-09-14 — Lane A: reconcile landing-branch docs to git HEAD 5e0ec717

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs` |
| **Summary** | After `git fetch origin main`, updated stale `3bb5aa2f` landing banners in `AGENTS.md`, `CURSOR_CLOUD_ENVIRONMENT.md`, and `DEVELOPER_OPERATING_SYSTEM.md` to git HEAD `5e0ec717` (#100). Clarified that `PROGRAM_STATUS` Canonical SHA **field** remains `a03f94cb` (#95) by policy — no PROGRAM_STATUS pin for #99/#100. |
| **Key files** | `AGENTS.md`, `docs/engineering/CURSOR_CLOUD_ENVIRONMENT.md`, `docs/engineering/DEVELOPER_OPERATING_SYSTEM.md`, `docs/engineering/WORK_LOG.md` |
| **Tests** | Docs-only; no operator CLI changes |
| **Related** | Lane A reconciliation receipt in Project store `internal/lane-a-github-docs.md` |
| **Notes** | Superseded for ongoing SHA pins by Lane G fetch-based banners; Notion hub body/tables may still cite historical SHAs. Item 18 stays PARTIAL. |

## 2026-09-14 — Board 03 overview KPI strip and Opportunity Radar density

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui/imp-product`, `ui/now`, `ui/discover` |
| **Summary** | Finish Track G board-03 product shell on Overview (`/`) and Opportunity Radar discover routes: KPI strip from admitted portfolio or live observational context, compact Top Opportunities cards backed by `/opportunities/summary` (no invented quotes), dense ranked queue table on discover pages, and graphite/orange styling. Empty, error, and unready states remain mock-safe. |
| **Key files** | `ui/src/components/imp-product/*`, `ui/src/components/demo-now/DemoNowPage.tsx`, `ui/src/components/paper-now/PaperNowPage.tsx`, `ui/src/components/live-now/LiveNowPage.tsx`, `ui/src/components/*-discover/*DiscoverPage.tsx`, `ui/src/styles/imp-product.css`, related tests |
| **Tests** | `ui`: vitest 468 passed; `ui`: `npm run build` pass (initial gzip ~202.5 KiB) |
| **Related** | PR #93 board-03 chrome; [ui-concepts board 03](/cursor/stores/bc-81919f43-9489-40d5-b7fe-bae5c3f9d1ba/media/ui-concepts/03-overview-bull-mark.png) |
| **Notes** | No live ticker, no Lovable pack, no backend contract changes. Sharpe/win-rate KPIs omitted until API fields exist. |

## 2026-09-14 — Research Export v1 honest PIT-PENDING metadata

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `research`, `wave1` |
| **Summary** | Fixture-built Research Export v1 packages now emit explicit operator metadata (`pit_status=PIT-PENDING`, `evidence_class=NON_EMPIRICAL_FIXTURE`) so Wave 1 assesses pending classification instead of accidental `PIT-UNKNOWN`, while OOS remains blocked. Written packages add `matlab_handoff_manifest.json` and standalone `validation_dataset_manifest.json` for MATLAB `jsondecode` loaders. |
| **Key files** | `src/market_platform_foundation/research/export_v1.py`, `tests/research/test_research_export_v1.py`, `docs/research/RESEARCH_EXPORT_V1.md` |
| **Tests** | `python3 -m unittest tests.research.test_research_export_v1 tests.research.test_wave1_experiment_harness` → 13/13 OK |
| **Related** | [RESEARCH_EXPORT_V1.md](../research/RESEARCH_EXPORT_V1.md), Wave 1 `export_gate.py` |
| **Notes** | Does not auto-derive `PIT-PASS` from `pit_audit`; operator must classify empirical exports separately. |

## 2026-09-14 — PROGRAM_STATUS Canonical SHA pin after merged #95 (Item 18)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs/platform` |
| **Summary** | Pin Canonical origin/main SHA to live tip `a03f94cb090d4f0dec1a96ae5e262cc24266490f` (merge pull request #95 Wave 1 experiment harness atop #94 `13816192`). Lists hop chain through #63 plus overnight #90–#97. Leftover #43 never landed — DoD item **18 stays PARTIAL** (Notion hub NOW/SYSTEM TRUTH inner SHAs historical). FTEP **`FTEP_EMPIRICAL_NOT_READY`**. Items **2 / 7 / 9** stay **PARTIAL**. Simulator **not** `CALIBRATED`. |
| **Key files** | `docs/platform/PROGRAM_STATUS.md`, `docs/engineering/WORK_LOG.md` |
| **Tests** | GitHub IMP Validation 9/9 incl. validate-ui on Item 18 PR |
| **Related** | [PR #95](https://github.com/AdamEddahmouni/market-trading-platform/pull/95); branch `cursor/item18-pin-1381619-d1ba` |
| **Notes** | Skip #46 superseded. Live forbidden. Wave 1 harness is software-only until lawful export + run. |

## 2026-09-14 — PROGRAM_STATUS Canonical SHA pin after merged #94 (RTH tip Item 18)

| Field | Value |
|-------|-------|
| **Status** | `superseded` |
| **Area** | `docs/platform` |
| **Summary** | Superseded by pin to `a03f94c` (#95) — do not treat `13816192` as canonical tip. |
| **Key files** | — |
| **Tests** | — |
| **Related** | — |
| **Notes** | Coordinator redirect. |

## 2026-09-14 — Research Export v1 (Track D)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `research`, `docs` |
| **Summary** | Implemented immutable Research Export v1 packages with deterministic `export_id` / manifest and table content hashes, PIT-A-001 `pit_export` binding, embedded `ValidationDatasetManifestV1` wrap, leakage firewall, and fixture-backed Profile A (NVDA bars) plus Profile C (ES macro events). Added Python loader, MATLAB parity sidecar, CLI, docs, and regression tests. No Live I/O; no duplicate backtester or provider stores. |
| **Key files** | `src/market_platform_foundation/research/export_v1.py`, `export_v1_audit.py`, `export_v1_profiles.py`, `tests/research/test_research_export_v1.py`, `tools/research/build_research_export_v1.py`, `docs/research/RESEARCH_EXPORT_V1.md` |
| **Tests** | `python3 -m unittest tests.research.test_research_export_v1` (5/5); `python3 tools/imp.py validate full` — IMP Validation 9/9 including validate-ui |
| **Related** | Notion IMP Research Export v1; `docs/engineering/PROVIDER_ACTIVATION_INCREMENT.md`; [PR #96](https://github.com/AdamEddahmouni/market-trading-platform/pull/96) |
| **Notes** | Rebased onto `origin/main` @ `ed80caa4` after #93. Did not touch `PROGRAM_STATUS` SHA field, hop CLI, Alpaca adapter, or `ui/`. |

## 2026-09-14 — Track G: IMP board 03 product shell (UI)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui/shell`, `ui/discover`, `ui/tokens` |
| **Summary** | Applied board 03 graphite/steel + molten orange styling in the existing Vite app: left sidebar with bull mark, command search, execution-off posture, product nav labels (Overview, Markets, Opportunity Radar, …), and Opportunity Radar as the discover surface title. Demo/Paper/Live copy and API wiring unchanged. |
| **Key files** | `ui/src/components/imp-product/*`, `ui/src/components/NavShell.tsx`, `ui/src/App.tsx`, `ui/src/styles/tokens.css`, `ui/src/styles/imp-product.css`, `ui/src/styles/mode-session.css`, discover page headers |
| **Tests** | `ui`: `npm run typecheck`, `npm test` (463 passed), `npm run build` (bundle budget pass) |
| **Related** | Project store `docs/ui-concepts.md`, board 03 reference; [PR #93](https://github.com/AdamEddahmouni/market-trading-platform/pull/93) |
| **Notes** | `/signals` and `/lab` alias overview and workspace index; no backend or live-execution changes. Rebased onto `main` @ `6defaf18` after #90. |

## 2026-09-14 — Path A Monday RTH preflight command (Track B)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend`, `tools`, `docs` |
| **Summary** | Added software-only `tools/path_a_rth_preflight.py` for Monday OpenD Path A / G7 / ForecastV1: aggregate disposition READY / BLOCKED / STALE / MISSING / MARKET_CLOSED covering interpreter/pip, install-opend PIP_MISSING fail-closed, loopback OpenD diagnostics, G7 freshness axes, Yahoo-never-L1 and Finviz overlay-only checks, hop `--mode live` argparse refusal, persist-off default, repository vs operator PRODUCTION JSON paths, and Paper-vs-Live gates. No MATCHED hop and no PRODUCTION mint. |
| **Key files** | `src/market_platform_foundation/strategy/path_a_rth_preflight.py`, `tools/path_a_rth_preflight.py`, `tests/intelligence/test_path_a_rth_preflight.py`, `docs/architecture/PAPER_FORWARD_TESTING_BRIDGE.md` |
| **Tests** | `validate changed` paths-file **2734 passed / 0 fail** after closure + env-isolation fixes; `tests.intelligence.test_path_a_rth_preflight` **8 passed** |
| **Related** | Track B overnight program; [PR #91](https://github.com/AdamEddahmouni/market-trading-platform/pull/91); rebased onto `origin/main` @ `ed80caa4` (#93 merged) |
| **Notes** | Preflight exit 0 for READY and MARKET_CLOSED; exit 1 otherwise. Stale Moomoo capability probe applies only during RTH. |

## 2026-09-14 — Hop JSON Item 2 / EMIT gate checker in tools

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `tools`, `tests/intelligence` |
| **Summary** | Ported Monday cash RTH hop JSON gate classifier from project store into `tools/hop_json_gate_check.py` so operators can run ITEM2_FLIP / EMIT checks without a store-only script. |
| **Key files** | `tools/hop_json_gate_check.py` (created), `tests/intelligence/test_hop_json_gate_check.py` (created) |
| **Tests** | `PYTHONPATH=src python3 -m unittest tests.intelligence.test_hop_json_gate_check -v` — 7 passed |
| **Related** | Track I overnight program; `path_a_prospective_run.py` hop artifact shape |
| **Notes** | FTEP stays NOT_READY; does not run Path A hop or declare EMPIRICAL_ACTIVE. Classified `tools/hop_json_gate_check.py` in repository-closure + `paper_forward_bridge` manifest partition (fixes `validate-python-changed` closure audit error). |

## 2026-09-14 — install-opend BLOCKED when uv venv has no pip

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `tools/moomoo`, `tests/providers` |
| **Summary** | `env install-opend` now probes the target interpreter for `pip` before `python -m pip install`. Fresh `uv venv` (no bundled pip) returns JSON `BLOCKED` with `reason_code` `PIP_MISSING` and operator remediation (`uv pip install pip` / `ensurepip`) instead of a generic pip-install failure. Live stays off; vendor pin unchanged. |
| **Key files** | `tools/moomoo/opend_hop_interpreter.py`, `tests/providers/test_opend_hop_interpreter.py`, `docs/engineering/WORK_LOG.md` |
| **Tests** | `python tools/imp.py validate full` (IMP Validation 9/9 including validate-ui) |
| **Related** | AdamsGalaxyBook weekday OpenD hop dry-run (`weekday-opend-hop-dryrun.md`) |
| **Notes** | Did not activate Live. Did not flip FTEP. Did not weaken OpenD/vendor-pin tests. |

## 2026-09-14 — PROGRAM_STATUS SHA pin after merged #62

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs` |
| **Summary** | Pin Canonical origin/main SHA to live tip `3d2c448` (Merge pull request #62). Lists hop chain #32, #34–#42, #45, #47, #48, #50, #52, #55–#62. Leftover #43 never landed. FTEP remains `FTEP_EMPIRICAL_NOT_READY` — **not** `EMPIRICAL_ACTIVE`. ES-news `BLOCKED_ON_ES_DATA` / `FROZEN_BLOCKED_EXTERNAL_DATA_ENTITLEMENT`. Live forbidden. Item 7 stays PARTIAL. Item 9 stays PARTIAL: Alpaca Paper is the $0 HTTPS comparator on main; Tradier unused; missing keys → `COMPARATOR_NOT_CONFIGURED`. Simulator **not** `CALIBRATED`. |
| **Key files** | `docs/platform/PROGRAM_STATUS.md`, `docs/engineering/WORK_LOG.md` |
| **Tests** | `python3 tools/check_docs_links.py`; GitHub IMP Validation 9/9 including `validate-ui` on this docs PR |
| **Related** | [PR #62](https://github.com/AdamEddahmouni/market-trading-platform/pull/62); merge SHA `3d2c44866f3d937d9a7b3c063438cd391423710d` |
| **Notes** | Docs-only SHA honesty after #62. Did not mint ForecastV1. Did not mock ticks. Did not merge leftover #43 or #46. Did not activate Live. Did not flip DoD items 2/7/9 to complete. |

## 2026-09-14 — PROGRAM_STATUS SHA pin after merged #60

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs` |
| **Summary** | Pin Canonical origin/main SHA to live tip `555c179` (Merge pull request #60). Lists hop chain #32, #34–#42, #45, #47, #48, #50, #52, #55–#60. Leftover #43 never landed. FTEP remains `FTEP_EMPIRICAL_NOT_READY` — **not** `EMPIRICAL_ACTIVE`. ES-news `BLOCKED_ON_ES_DATA` / `FROZEN_BLOCKED_EXTERNAL_DATA_ENTITLEMENT`. Live forbidden. Item 7 stays PARTIAL. Item 9 stays PARTIAL: Tradier sandbox skipped; Alpaca Paper WAITING (no keys). Simulator **not** `CALIBRATED`. |
| **Key files** | `docs/platform/PROGRAM_STATUS.md`, `docs/engineering/WORK_LOG.md` |
| **Tests** | `python3 tools/check_docs_links.py`; GitHub IMP Validation + Guardrails on this docs PR |
| **Related** | [PR #60](https://github.com/AdamEddahmouni/market-trading-platform/pull/60); merge SHA `555c179ec53b5c71184d4e47841250bcf6c34fc9` |
| **Notes** | Docs-only SHA honesty after #60. Did not mint ForecastV1. Did not mock ticks. Did not merge leftover #43 or #46. Did not activate Live. Did not flip DoD items 2/7/9. |

## 2026-09-14 — PROGRAM_STATUS SHA pin after merged #59

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs` |
| **Summary** | Pin Canonical origin/main SHA to `30d34c2` (Merge pull request #59). Lists merged #32, #34–#42, #45, #47, #48, #50, #52, #55–#59. Does **not** list unmerged #33 / #43 / #46. Restores a truncated Path A scan-caller evidence URL and drops a stray `#59` draft fragment. FTEP remains `FTEP_EMPIRICAL_NOT_READY` — **not** `EMPIRICAL_ACTIVE`. Simulator **not** `CALIBRATED`. Live forbidden. Item 7 stays PARTIAL (no empirical hop consuming PRODUCTION JSON). |
| **Key files** | `docs/platform/PROGRAM_STATUS.md`, `docs/engineering/WORK_LOG.md` |
| **Tests** | `python3 tools/check_docs_links.py`; GitHub IMP Validation + Guardrails on this docs PR |
| **Related** | [PR #59](https://github.com/AdamEddahmouni/market-trading-platform/pull/59); merge SHA `30d34c22d2b4d82af2aef4faee04418246ad1a9f` |
| **Notes** | Docs-only SHA honesty. Did not mint ForecastV1. Did not mock ticks. Did not merge #43 or #46. Did not activate Live. |

## 2026-09-13 — Path A PRODUCTION specialist ForecastV1 emitter + temporal calibrator

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `intelligence/production`, `fusion`, `strategy` |
| **Summary** | Fail-closed library emits innate PRODUCTION / `PRODUCTION_RAW` `ForecastV1` from a PIT-legal 5m logistic (snapshot-bound momentum + net-signed-share; not a quote print, not CONTROL `build_forecast_v1`, not research `build_forecast`). Temporally legal `CalibrationModelArtifact` trainer (`LOGISTIC_PROBABILITY` or `ISOTONIC`) uses the BUILD 14 label firewall; `IDENTITY_CONTROL` and Live are rejected. Persist is Paper/Demo JSON only when identity/PIT gates pass; tests use tempdirs. No committed empirical JSON. Default fusion still abstains without hop `--contributor-path` / `--calibration-path`. Item 7 stays **PARTIAL**. Live stays off. FTEP is not `EMPIRICAL_ACTIVE`. |
| **Key files** | `src/market_platform_foundation/intelligence/production/` (new: `emitter.py`, `model.py`, `calibrator.py`, `identity.py`), `src/market_platform_foundation/strategy/path_a_production_emit.py` (new persist gates), `src/market_platform_foundation/intelligence/fusion/types.py` (`PRODUCTION_FORECAST_STAGE`), `tests/intelligence/test_path_a_production_emit.py`, `docs/engineering/FUSION_CALIBRATION_UNCERTAINTY_V1.md`, `docs/engineering/OPPORTUNITY_ENGINE_V1.md`, `docs/architecture/PAPER_FORWARD_TESTING_BRIDGE.md`, `docs/platform/PROGRAM_STATUS.md` |
| **Tests** | `tests.intelligence.test_path_a_production_emit` **13 passed**. Emit + producer + calibration dataset + BUILD 14 lifecycle **35 passed / 0 fail**. `python3 tools/validate.py changed --paths-file` (15 paths vs `#53` `6f0ead8`) **2494 passed / 28 skipped / 0 fail / 0 err**. `python3 tools/check_docs_links.py` **OK (188 files)**. Live still `LIVE_SCAN_CALLER_FORBIDDEN`. |
| **Related** | Stacks on #53 `6f0ead8` (hop `--contributor-path` / `--calibration-path`). Item 7 of the provider activation program. |
| **Notes** | Software emit/persist is not empirical. A real weekday G7-actionable hop must still consume the JSON files. Did not mint from last_price, fixture 0.8, or CONTROL/research constructors. Did not declare FTEP `EMPIRICAL_ACTIVE` or Live. Frozen FTEP-V1-001 JSON not touched. |

## 2026-09-13 — Restack Path A MATCHED produce onto leftover OpenD hop

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `strategy`, `providers`, Path A hop CLI |
| **Summary** | Cherry-picked Path A ForecastV1 load (#49), fail-closed producer (#51), and hop-side `--contributor-path`/`--calibration-path` produce (#53) onto leftover OpenD hop #57. Weekday hops can now run produce + G7 OpenD identity + Finviz leftover overlay on one branch. Conflicts kept OpenD as hop L1, Finviz overlay-only (never L1), leftover leftover-login discovery, one-interpreter `hop_interpreter`, and `diagnose_opend(start=True)`. BOOTSTRAP honesty champion `effective_from_ns=0`. Did not mint ForecastV1 JSON. Did not treat CONTROL/fixture `0.8` as empirical. Item 7 stays **PARTIAL**. FTEP is not `EMPIRICAL_ACTIVE`. Live off. Frozen FTEP-V1-001 JSON not touched. |
| **Key files** | `src/market_platform_foundation/strategy/path_a_forecast_store.py` (new on this stack), `src/market_platform_foundation/strategy/path_a_forecast_producer.py` (new on this stack), `src/market_platform_foundation/strategy/path_a_prospective.py`, `tools/path_a_prospective_run.py` (produce flags kept beside OpenD/Finviz leftover hop JSON), `tests/intelligence/test_path_a_forecast_producer.py`, `tests/intelligence/test_path_a_forecast_store.py`, `docs/architecture/PAPER_FORWARD_TESTING_BRIDGE.md`, `docs/platform/PROGRAM_STATUS.md` |
| **Tests** | `PYTHONPATH=src .venv/bin/python -m unittest tests.intelligence.test_path_a_forecast_producer` **16 passed**. Producer + store **31 passed**. Path A producer + store + prereg + prospective + catalog + scan caller **104 passed**. Leftover leftover-login + OpenD hop interpreter + OpenD Primary L1 + Finviz overlay + producer **106 passed**. Honest CLI OpenD down: `discovery.provider_id=moomoo.opend.observational`, `overlay_provider_id=yahoo.finance.delayed`, `equity_context.discovery.classification=NOT_CONFIGURED`, `auto_fetch_status=CREDENTIALS_ABSENT`, `is_l1=false`, `result.status=PROVIDER_UNAVAILABLE` / `OPEND_UNAVAILABLE`. `--mode live` argparse refused. `.venv/bin/python tools/validate.py changed --paths-file` (13 paths vs #57 `ee32e7a`) **2623 passed / 25 skipped / 0 fail / 0 err** (`core_checkpoint_required=true` from unowned `tools/path_a_prospective_run.py`). `python3 tools/imp.py lint` passed. `python3 tools/check_docs_links.py` **OK (188 files)**. `python` absent; `python3` / `.venv/bin/python` used. GitHub CI on produce restack tip `be2ede4` **9/9 SUCCESS**, mergeable `MERGEABLE`. |
| **Related** | Draft #58 on base `cursor/finviz-leftover-discovery-d1ba`. Source produce from #53 `6f0ead8` (`09edef2` feat). Did not merge #53 onto main. Did not merge #58. |
| **Notes** | Software `MINTED` / `OPPORTUNITY_EMITTED` is not an empirical hop. Item 7 stays PARTIAL until a real PRODUCTION ForecastV1 exists and a weekday G7-actionable MATCHED hop. No mock data. Did not activate Live. GitHub CI 9/9 is software-green, not FTEP `EMPIRICAL_ACTIVE`. |

## 2026-09-13 — Worktree-aware Finviz leftover login discovery

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `finviz`, hop overlay discovery |
| **Summary** | Leftover Elite login discovery now searches the current worktree, the git common-dir main checkout, and the parent of `.worktrees` for `integrated-market-platform/.private/finviz-login.json`. Sibling hops no longer need a junction to the Desktop leftover nested clone. Overlay stays overlay-only (never L1). Live off. FTEP is not `EMPIRICAL_ACTIVE`. Secrets are never printed or committed. |
| **Key files** | `src/market_platform_foundation/git_ref.py` (`git_common_dir`, `main_working_tree`), `src/market_platform_foundation/finviz/config.py` (worktree-aware leftover roots), `src/market_platform_foundation/providers/finviz_context_discovery.py` (search-order docstring), `tests/finviz/test_leftover_login_discovery.py` (new), `tests/platform/test_git_ref.py`, `docs/providers/FINVIZ_ELITE.md` |
| **Tests** | `PYTHONPATH=src .venv/bin/python -m unittest` leftover discovery + git_ref + Finviz overlay autofetch **56 ran / 1 skipped / 0 fail**. Full `tests/finviz` **65 passed**. `.venv/bin/python tools/validate.py changed --paths-file` (7 paths vs #56 `4418b91`) **1526 passed / 14 skipped / 0 fail / 0 err** (`core_checkpoint_required=true` from unowned `git_ref.py`). `python3 tools/imp.py lint` passed. `python3 tools/check_docs_links.py` **OK (188 files)**. |
| **Related** | Stacked on #56 `4418b91` (`cursor/finviz-hop-overlay-d1ba`). Operator-zero after leftover login exists. |
| **Notes** | Did not merge. Did not activate Live. Did not declare FTEP `EMPIRICAL_ACTIVE`. Paper only. |

## 2026-09-13 — Path A hop MATCHED/OE EMIT from fail-closed produce

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `strategy`, `opportunity`, `fusion` |
| **Summary** | Paper/Demo Path A hop now *produces* on the composer/CLI from `--contributor-path` + `--calibration-path` via BUILD 14 `produce_paper_demo_forecast`, then loads the fused artifact. Absent PRODUCTION contributors or calibrator persist nothing (`FORECAST_UNAVAILABLE`). The BOOTSTRAP honesty champion is effective from 0 so a quote-print forecast is not OE-suppressed at receive/as_of. Tests prove composer `MINTED` / `OPPORTUNITY_EMITTED` on a G7-actionable REAL_TIME quote without fixture `probability=0.8`. Catalog evaluators still never call `build_preregistration`. Software MATCHED/OE EMIT is not FTEP `EMPIRICAL_ACTIVE`. Item 7 stays **PARTIAL**. Live stays off. |
| **Key files** | `src/market_platform_foundation/strategy/path_a_forecast_producer.py` (contributor/calibrator load), `src/market_platform_foundation/strategy/path_a_prospective.py`, `src/market_platform_foundation/strategy/path_a_strategy_catalog.py`, `tools/path_a_prospective_run.py` (`--contributor-path` / `--calibration-path`; no `--probability`), `tests/intelligence/test_path_a_forecast_producer.py`, `docs/engineering/OPPORTUNITY_ENGINE_V1.md`, `docs/platform/PROGRAM_STATUS.md`, `docs/architecture/PAPER_FORWARD_TESTING_BRIDGE.md` |
| **Tests** | `tests.intelligence.test_path_a_forecast_producer` **16 passed**. Path A producer + store + prereg + prospective + catalog + scan caller **98 passed / 0 fail**. Live still `LIVE_SCAN_CALLER_FORBIDDEN`. |
| **Related** | Originally stacked on #51 `65e19cd`. Cherry-picked onto leftover OpenD hop #57 so weekday hops can run produce + G7 OpenD identity + Finviz leftover overlay on one branch. Item 7 of the provider activation program. |
| **Notes** | A fused software artifact is not empirical. Default production fusion still has no live specialist contributors on an operator weekday hop unless those JSON inputs exist. Did not declare FTEP `EMPIRICAL_ACTIVE` or Live. Frozen FTEP-V1-001 JSON not touched. |

## 2026-09-13 — Path A fail-closed PRODUCTION ForecastV1 producer

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `strategy`, `opportunity`, `fusion` |
| **Summary** | Paper/Demo Path A can now *produce* a PRODUCTION `ForecastV1` through BUILD 14 `ForecastFusionService` (`strategy/path_a_forecast_producer.py`) and persist it only via `persist_paper_demo_forecast` when fusion emits `EMITTED_CALIBRATED` with `calibration_status=CALIBRATED` and identity/PIT/champion/horizon/account/mode hop gates pass. CONTROL-only, RESEARCH dicts, IDENTITY_CONTROL, missing calibration, uncalibrated contributors, and Live persist nothing (`FORECAST_UNAVAILABLE` / `LIVE_FORBIDDEN`). The hop remains load-only (`--forecast-path`). Catalog evaluators still never call `build_preregistration`. No last_price mint, no fixture `probability=0.8`. Software producer wiring is not FTEP `EMPIRICAL_ACTIVE`. Item 7 stays **PARTIAL**. Live stays off. |
| **Key files** | `src/market_platform_foundation/strategy/path_a_forecast_producer.py` (new), `src/market_platform_foundation/strategy/path_a_forecast_store.py` (`forecast_matches_path_a_hop_policy`), `src/market_platform_foundation/strategy/path_a_prospective.py`, `src/market_platform_foundation/strategy/path_a_strategy_catalog.py`, `tools/path_a_prospective_run.py` (help text only; no `--probability`), `tests/intelligence/test_path_a_forecast_producer.py` (new), `tests/intelligence/test_path_a_forecast_store.py`, `docs/engineering/OPPORTUNITY_ENGINE_V1.md`, `docs/platform/PROGRAM_STATUS.md`, `docs/architecture/PAPER_FORWARD_TESTING_BRIDGE.md` |
| **Tests** | New `tests.intelligence.test_path_a_forecast_producer` **12 passed** (CONTROL-only / missing calibration / IDENTITY_CONTROL / research dict / CONTROL-tagged-as-PRODUCTION / horizon mismatch do not persist; Live forbidden; fused+calibrated persist loads and Path A `MINTED` / OE EMIT — software-only). Store + producer **27 passed**. Focused Path A + catalog + scan caller + freshness + producer **124 passed**. `python3 tools/validate.py changed --paths-file` (10 paths vs `origin/cursor/path-a-forecast-load-d1ba`@`f920ef5`) **2559 passed / 25 skipped / 0 fail / 0 err** (`core_checkpoint_required=true`, same unowned `tools/path_a_prospective_run.py` escalation as prior Path A CLI PRs). `python3 tools/check_docs_links.py` **OK (188 files)**. Live still `LIVE_SCAN_CALLER_FORBIDDEN`. |
| **Related** | Originally stacked on #49 `f920ef5`. Cherry-picked onto leftover OpenD hop #57. Item 7 of the provider activation program. |
| **Notes** | A fused software artifact is not empirical. Default production fusion still has no live specialist contributors on this hop, so the operator path fail-closes without them. Did not declare FTEP `EMPIRICAL_ACTIVE` or Live. Frozen FTEP-V1-001 JSON not touched. |

## 2026-09-13 — Path A loads a previously persisted PRODUCTION ForecastV1

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `strategy`, `opportunity` |
| **Summary** | Paper/Demo Path A CLI no longer pre-builds the invoke before fetch. Composer fetches once (OpenD primary), G7 remains freshness authority, and auto-builds the honesty invoke with the admitted `quote_event` so the catalog is not stuck on `FCAST_NO_QUOTE_OBSERVATION`. `forecast_resolver` loads a previously persisted PRODUCTION `ForecastV1` (`strategy/path_a_forecast_store.py`) only when identity/PIT/champion/horizon/account/mode match Opportunity Engine hop policy; CONTROL, RESEARCH, uncalibrated, or absent artifacts return `None` (`FORECAST_UNAVAILABLE`). Persist is serialization of an already-constructed `ForecastV1`, not a producer. The hop does not mint a probability from last_price, does not call CONTROL `build_forecast_v1`, and does not add a CLI `--probability`. Live stays `LIVE_FORBIDDEN`. Item 7 stays **PARTIAL**. FTEP is not `EMPIRICAL_ACTIVE`. Frozen FTEP-V1-001 JSON not touched. |
| **Key files** | `src/market_platform_foundation/strategy/path_a_forecast_store.py` (new), `src/market_platform_foundation/strategy/path_a_prospective.py`, `src/market_platform_foundation/strategy/path_a_strategy_catalog.py`, `tools/path_a_prospective_run.py` (additive `--forecast-path`; no pre-fetch invoke), `tests/intelligence/test_path_a_forecast_store.py` (new), `tests/intelligence/test_path_a_preregistration_store.py`, `tests/intelligence/test_path_a_prospective.py`, `docs/engineering/OPPORTUNITY_ENGINE_V1.md`, `docs/platform/PROGRAM_STATUS.md`, `docs/architecture/PAPER_FORWARD_TESTING_BRIDGE.md` |
| **Tests** | New `tests.intelligence.test_path_a_forecast_store` **15 passed** (missing → `FORECAST_UNAVAILABLE`; CONTROL/RESEARCH/uncalibrated rejected at load not OE SUPPRESS; research `build_forecast` dict rejected; catalog never calls `build_preregistration`; Live still forbidden; composer threads fetched quote into scan context). Focused Path A + catalog + scan caller + ingest + freshness **112 passed**. `python3 tools/check_docs_links.py` **OK (188 files)**. `python3 tools/validate.py changed --paths-file` vs merge-base `origin/cursor/path-a-prereg-load-d1ba`@`ff139ac` recorded in the follow-up note if a later commit lands counts. Live still `LIVE_SCAN_CALLER_FORBIDDEN`. |
| **Related** | Originally stacked on restacked #48 `ff139ac`. Cherry-picked onto leftover OpenD hop #57 so weekday hops can load ForecastV1 on the G7 OpenD / Finviz leftover stack. Item 7 of the provider activation program. |
| **Notes** | A software-constructed PRODUCTION `ForecastV1` used in tests is not empirical and is not item 7 PROVED. No empirical fused/calibrated producer exists on this hop. Whale alignments still abstain on `ABSTAIN_INSTITUTIONAL_UNAVAILABLE`. Did not declare FTEP `EMPIRICAL_ACTIVE` or Live. |

## 2026-09-13 — Finviz Elite overlay on OpenD Path A hop CLI

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `providers`, Path A hop CLI |
| **Summary** | Joined Finviz Elite screening/news overlay into the OpenD Path A hop CLI on the #55 one-interpreter / G7 OpenD identity base. Hop JSON now includes `equity_context` (overlay classifier). Token absent fail-closes `NOT_CONFIGURED`. Fetched token without `IMP_FINVIZ_LIVE` is `LIVE_DISABLED`. OpenD stays hop L1 (`primary_equity_quote_provider()`). Yahoo stays `overlay_provider_id`. Leftover nested login still repairs into gitignored canonical `.private`. Live off. FTEP is not `EMPIRICAL_ACTIVE`. Item 2 stays PARTIAL. |
| **Key files** | `tools/path_a_prospective_run.py` (`equity_context` hop JSON + observational composition overlay), `providers/adapters/finviz_elite_context.py` (lifted), `providers/finviz_context_discovery.py` (lifted leftover-login auto-fetch), `providers/composition.py` (`with_finviz_elite_*` plus existing `with_moomoo_opend_primary_quote`), `market_data/runtime_composition.py` (`equity_context` slot kept beside OpenD `ingest_one_shot` / G7 snapshot), `market_data/observational_lanes.py` (`build_context_payload`), `tests/intelligence/test_path_a_prospective.py` (hop overlay classifier), `tests/providers/test_finviz_elite_context.py`, `tests/market_data/test_finviz_observational_context.py`, `docs/providers/FINVIZ_ELITE.md`, `docs/providers/MOOMOO_OBSERVATIONAL.md`, `docs/architecture/PAPER_FORWARD_TESTING_BRIDGE.md`, `docs/platform/PROGRAM_STATUS.md` |
| **Tests** | `PYTHONPATH=src python3 -m unittest` Path A hop + Finviz overlay + observational context + OpenD hop interpreter + OpenD Primary L1 + G7 lanes/runtime + providers **168 passed / 0 fail**. Honest CLI OpenD down: `discovery.provider_id=moomoo.opend.observational`, `overlay_provider_id=yahoo.finance.delayed`, `equity_context.discovery.classification=NOT_CONFIGURED`, `auto_fetch_status=CREDENTIALS_ABSENT`, `is_l1=false`, `result.status=PROVIDER_UNAVAILABLE` / `OPEND_UNAVAILABLE`. `--mode live` argparse refused. `python3 tools/validate.py changed --paths-file` (20 paths vs #55 `bb05b7a`) **3205 passed / 39 skipped / 0 fail / 0 err** (`core_checkpoint_required=true`). `python3 tools/imp.py lint` passed. `python3 tools/check_docs_links.py` **OK (188 files)**. |
| **Related** | Stacked on #55 `bb05b7a` (`cursor/hop-one-interpreter-d1ba`). Overlay wiring lifted from #44/`4c2c931` and #54/`87df20f`. Did not stack onto #53 (MATCHED produce) so G7 OpenD identity + one-interpreter stay. |
| **Notes** | Did not merge. Did not mock ticks. Did not declare item 2 PROVED. Cloud VM still has no Elite token and no OpenD. Operator AdamsGalaxyBook overlay FETCHED on #54 is software-join input, not this hop CLI empirical. GitHub CI on feat head `4f9cef3` **9/9 SUCCESS**, mergeable `MERGEABLE`. |

## 2026-09-13 — One-interpreter OpenD hop extra

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `tools`, `providers`, Path A hop |
| **Summary** | Path A hop no longer needs IMP `.venv` plus `PYTHONPATH` into `moomoo-api-test`. Optional extra `python tools/imp.py env install-opend` installs `moomoo-api==10.10.7008` into the IMP interpreter (sklearn already there). `import moomoo` must be vendor `OpenQuoteContext`, never `tools/moomoo`. Missing SDK stays `MOOMOO_SDK_MISSING` (never a mock tick). Cloud/default bootstrap does not install the extra. Live stays off. FTEP is not `EMPIRICAL_ACTIVE`. |
| **Key files** | `tools/moomoo/requirements-opend.txt` (new), `tools/moomoo/opend_hop_interpreter.py` (new), `tools/moomoo/opend_quote_transport.py`, `tools/imp.py` (`env install-opend`), `tools/path_a_prospective_run.py` (`hop_interpreter` JSON), `tests/providers/test_opend_hop_interpreter.py` (new), `tests/validation/test_opend_extra_env.py` (new), `docs/providers/MOOMOO_OBSERVATIONAL.md`, `docs/engineering/DEPENDENCIES.md`, `docs/engineering/DEVELOPER_OPERATING_SYSTEM.md`, `docs/engineering/LOCAL_DEVELOPMENT.md`, `docs/engineering/OPERATOR_PROBE_RUNBOOK.md`, `docs/architecture/PAPER_FORWARD_TESTING_BRIDGE.md`, `docs/platform/PROGRAM_STATUS.md`, `README.md` |
| **Tests** | `python3 -m unittest` hop interpreter + OpenD vendor transport + Path A + G7 + env **116 passed / 0 fail**. Honest CLI with OpenD down: `hop_interpreter.vendor_sdk=false`, `vendor_sdk_is_opend_quote_context=false`, `reason_code=MOOMOO_SDK_MISSING`, `secrets_included=false`; `result.status=PROVIDER_UNAVAILABLE` / `OPEND_UNAVAILABLE`. `python3 tools/validate.py changed --paths-file` (16 paths vs #52 `bf1aaaa`) **1023 passed / 0 skipped / 0 fail / 0 err** (`core_checkpoint_required=true` from unowned hop CLI / extra paths). `python3 tools/imp.py lint` passed. `python3 tools/check_docs_links.py` **OK (188 files)**. |
| **Related** | Stacked on #52 `bf1aaaa`. Operator mix was IMP `.venv` + `PYTHONPATH` to `moomoo-api-test` site-packages. |
| **Notes** | After extra: `$env:PYTHONPATH='src'; .venv\Scripts\python.exe tools\path_a_prospective_run.py --symbol AAPL --mode paper`. Did not merge. Did not mock ticks. Did not touch Finviz auto-fetch or #50–#53. |

## 2026-09-13 — G7 knows OpenD hop L1 identity

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `providers`, G7 selection |
| **Summary** | Registered hop L1 identity `moomoo.opend.observational` (`US_EQUITY_L1`) in G7 `ProviderRegistry` / `RuntimeCapabilityRegistry` so Path A selection no longer fail-closes with `UNKNOWN_PROVIDER:moomoo.opend.observational`. Lane `OBSERVATIONAL_L1` resolves per provider (`US_EQUITY_L1` on OpenD, `IBKR_L1` on IBKR). Yahoo delayed stays overlay-only and is `UNKNOWN_PROVIDER` as hop L1. Unstamped OpenD is `PROVIDER_DOWN` until a hop stamps `HEALTHY` after an admitted fetch; OpenD-down hop fetch still `PROVIDER_UNAVAILABLE` / `OPEND_UNAVAILABLE`. Did not mock ticks. FTEP is not `EMPIRICAL_ACTIVE`. Live stays off. Did not touch ForecastV1 / #51. |
| **Key files** | `src/market_platform_foundation/providers/moomoo_opend_capability.py` (new), `src/market_platform_foundation/providers/runtime_capability.py`, `src/market_platform_foundation/providers/runtime_selection.py`, `src/market_platform_foundation/providers/adapters/moomoo_opend_equity_quote.py`, `tests/providers/test_g7_runtime_capability.py`, `tests/intelligence/test_path_a_prospective.py`, `docs/providers/MOOMOO_OBSERVATIONAL.md`, `docs/architecture/PAPER_FORWARD_TESTING_BRIDGE.md`, `docs/platform/PROGRAM_STATUS.md` |
| **Tests** | `python3 tools/imp.py test focused` G7 OpenD + hop regression **20 passed**. `python3 -m unittest` G7 + OpenD Primary L1 + Path A **127 passed / 0 fail**. `python3 tools/validate.py changed --paths-file` (10 paths vs `origin/cursor/opend-transport-d1ba`@`2c9a4e4`) **2146 passed / 36 skipped / 0 fail / 0 err** (`core_checkpoint_required=false`). `python3 tools/imp.py lint` passed. `python3 tools/check_docs_links.py` **OK (188 files)**. |
| **Related** | Stacked on #50 `2c9a4e4`. Operator hop receipt: AAPL `last_price` 332.27 admitted then `G7_SELECTION_NO_PROVIDER` / `UNKNOWN_PROVIDER:moomoo.opend.observational`. |
| **Notes** | Sunday-stale `STALE_AFTER_THRESHOLD` remains expected and independent. A fresh OpenD tick can now bind G7 selection; that still does not declare FTEP `EMPIRICAL_ACTIVE`. Did not merge. |

## 2026-09-13 — OpenD SDK import ignores tools/ shadow

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `providers`, `tools/moomoo` |
| **Summary** | `python tools/validation_worker.py` (and `python tools/*.py`) put `tools/` on `sys.path[0]`, so `import moomoo` bound the local `tools/moomoo` directory. `sdk_available()` treated that as the vendor SDK, so dummy-TCP tests reported `OPEND_SDK_PRESENT` instead of `MOOMOO_SDK_MISSING`. Import now requires `OpenQuoteContext` and skips the `tools/` shadow so a real site-packages SDK is not hidden. Still fail-closed; never mocks ticks; Yahoo is not hop L1. |
| **Key files** | `tools/moomoo/opend_quote_transport.py`, `tests/providers/test_moomoo_opend_primary_l1.py` |
| **Tests** | Focused Path A + OpenD + live-p21 **107 passed**. `python3 tools/validation_worker.py --suite-id providers` **383 passed / 0 fail**. CI run 34783594336 had failed `test_reachable_loopback_without_sdk_fails_closed_never_mocks` and `test_discovery_reachable_without_sdk_is_sdk_missing`. |
| **Related** | PR #50. Follows fail-closed OpenD vendor quote transport. |
| **Notes** | FTEP is not `EMPIRICAL_ACTIVE`. Item 2 stays **PARTIAL**. Did not merge. |

## 2026-09-13 — Fail-closed OpenD vendor quote transport (Primary L1)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `providers`, `tools/moomoo` |
| **Summary** | Wired quote-only OpenD vendor transport so a reachable loopback OpenD can return a real vendor snapshot through `MoomooOpenDEquityQuoteProvider`. Foundation still does not depend on `moomoo-api`; `tools/moomoo/opend_quote_transport.py` lazy-imports it. Fail closed on non-loopback, missing SDK, auth failure, protocol error, missing `last_price`, and missing vendor timestamp. Never synthesizes `last_price`. Path A hop CLI calls `diagnose_opend(start=True)` before quote fetch (Windows starts `%APPDATA%\\moomoo_OpenD\\moomoo_OpenD.exe` when installed); still-down stays fail-closed and Yahoo is never hop L1. CI without a daemon stays `PROVIDER_UNAVAILABLE` / `OPEND_UNAVAILABLE`. Dummy TCP without SDK is `MOOMOO_SDK_MISSING`. Live Path A CLI still argparse-refused. FTEP is not `EMPIRICAL_ACTIVE`. Item 2 stays **PARTIAL** until an operator OpenD daemon actually yields a tick. |
| **Key files** | `src/market_platform_foundation/providers/adapters/moomoo_opend_equity_quote.py`, `src/market_platform_foundation/providers/equity_quote_discovery.py`, `src/market_platform_foundation/providers/equity_quote_selection.py`, `src/market_platform_foundation/providers/composition.py`, `tools/moomoo/opend_quote_transport.py` (new), `tools/path_a_prospective_run.py` (`diagnose_opend(start=True)` before fetch), `tests/providers/test_moomoo_opend_primary_l1.py`, `tests/intelligence/test_path_a_prospective.py`, `tests/market_data/test_live_p21.py`, `docs/providers/MOOMOO_OBSERVATIONAL.md`, `docs/architecture/PAPER_FORWARD_TESTING_BRIDGE.md`, `docs/platform/PROGRAM_STATUS.md` |
| **Tests** | `tests.providers.test_moomoo_opend_primary_l1` **40 passed**. Combined with Path A hop + live-p21 trade-context + phase0 analysis **43 passed**. Honest CLI with OpenD down: `discovery.provider_id=moomoo.opend.observational`, `overlay_provider_id=yahoo.finance.delayed`, `opend_reachable=false`, `result.status=PROVIDER_UNAVAILABLE`, `reason_codes=["OPEND_UNAVAILABLE"]`, `path_a_status=null`. `--mode live` still argparse-refused. Did not edit Path A `forecast_resolver`, prereg store, or catalog evaluators. |
| **Related** | Stacked on #48 `ff139ac` (OpenD hop + prereg). Follows hop unify #47. |
| **Notes** | Operator OpenD + vendor SDK remain required for an empirical tick. Cloud VM has no loopback `:11111` and no `moomoo-api`. No secrets printed. Did not add paid vendors. Did not merge to main or Wave B. |

## 2026-09-13 — Restack Path A prereg load onto OpenD hop

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `strategy`, `providers`, `tools` |
| **Summary** | Merged `#47` OpenD hop (`a9377a6`) into `#48` prereg load (`fcf6116`) so one hop has OpenD primary L1 and Phase-6 preregistration load. CLI keeps `primary_equity_quote_provider()` and `--preregistration-path` plus `--persist-*`. Yahoo stays overlay-only. Catalog evaluators still never mint. `forecast_resolver` stays `None`. Item 7 stays **PARTIAL**. FTEP is not `EMPIRICAL_ACTIVE`. Live stays off. |
| **Key files** | `tools/path_a_prospective_run.py` (both OpenD primary and `--preregistration-path`), `tests/intelligence/test_path_a_preregistration_store.py` (CLI source assertion now requires both), `docs/architecture/PAPER_FORWARD_TESTING_BRIDGE.md`, `docs/platform/PROGRAM_STATUS.md` |
| **Tests** | Focused Path A + catalog + scan caller + ingest + freshness + OpenD Primary L1 **118 passed** (`test_path_a_preregistration_store` **13**, `test_path_a_prospective` **40**, `test_moomoo_opend_primary_l1` **21**, catalog **8**). Honest CLI with OpenD down: `discovery.provider_id=moomoo.opend.observational`, `overlay_provider_id=yahoo.finance.delayed`, `opend_reachable=false`, `result.status=PROVIDER_UNAVAILABLE`, `reason_codes=["OPEND_UNAVAILABLE"]`, `path_a_status=null`; `--preregistration-path` and `--persist-*` still present. `python3 tools/validate.py changed --paths-file` (10 merge-base paths vs `origin/cursor/opend-hop-unify-d1ba`@`a9377a6`) **2532 passed / 25 skipped / 0 fail / 0 err** (`core_checkpoint_required=true`). `python3 tools/imp.py lint` passed. `python3 tools/check_docs_links.py` **OK (188 files)**. `validate.py changed --plan` with no paths-file on a clean tree: **0 suites**. |
| **Related** | PR #48 restacked onto #47. Stack is `#45` `ce49048` → `#47` `a9377a6` → `#48`. |
| **Notes** | Merge, not rebase/force-push. Four content conflicts: CLI, `WORK_LOG.md`, `PROGRAM_STATUS.md`, `PAPER_FORWARD_TESTING_BRIDGE.md`. Did not mint `ForecastV1`, inject fixture probability, activate Live, declare FTEP `EMPIRICAL_ACTIVE`, merge to main, or merge Wave B / #46 onto main. |

## 2026-09-13 — Path A loads a previously persisted Phase-6 preregistration

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `strategy`, `opportunity` |
| **Summary** | Paper/Demo Path A can persist and later load a Phase-6 `build_preregistration` record. Create is a separate operator step (`persist_paper_demo_preregistration`) that stamps `registered_at` before any hop. `build_paper_demo_path_a_invoke` loads only when identity matches the spec and `registered_at` is before quote `event_time_ns`. Catalog evaluators never call `build_preregistration`; ineligible/absent stores stay `preregistration=None` (honest abstain). `forecast_resolver` still returns `None`, so a lawful scanner MATCHED is `FORECAST_UNAVAILABLE` rather than OE EMIT. Live stays `LIVE_FORBIDDEN`. Item 7 stays **PARTIAL** — no PRODUCTION `ForecastV1`. FTEP is not `EMPIRICAL_ACTIVE`. Frozen FTEP-V1-001 JSON not touched. |
| **Key files** | `src/market_platform_foundation/strategy/path_a_preregistration_store.py` (new), `src/market_platform_foundation/strategy/path_a_prospective.py`, `src/market_platform_foundation/strategy/path_a_strategy_catalog.py`, `tools/path_a_prospective_run.py` (additive `--preregistration-path`), `tests/intelligence/test_path_a_preregistration_store.py` (new), `tests/intelligence/test_path_a_strategy_catalog.py`, `docs/engineering/OPPORTUNITY_ENGINE_V1.md`, `docs/platform/PROGRAM_STATUS.md`, `docs/architecture/PAPER_FORWARD_TESTING_BRIDGE.md` |
| **Tests** | New `tests.intelligence.test_path_a_preregistration_store` **13 passed** (persist+load eligibility; load+PASS scanner MATCHED is `FORECAST_UNAVAILABLE` not MINTED; late/identity-mismatch/absent/no-quote-time abstain; Live still forbidden; catalog never calls `build_preregistration`; CLI `--preregistration-path` additive). Catalog **8 passed**. Focused Path A + catalog + scan caller + ingest + freshness **93 passed**. `python3 tools/validate.py changed --paths-file` (10 merge-base paths vs `origin/cursor/path-a-persist-cli-d1ba`@`ce49048`) **2507 passed / 25 skipped / 0 fail / 0 err** (`core_checkpoint_required=true`, same unowned `tools/path_a_prospective_run.py` escalation as prior Path A CLI PRs). `python3 tools/check_docs_links.py` **OK (188 files)**. Live still `LIVE_SCAN_CALLER_FORBIDDEN`. |
| **Related** | Follows catalog wiring (`df2b66c`) and persist-CLI restack (`ce49048`). Item 7 of the provider activation program. |
| **Notes** | A scanner MATCHED on `baseline_only` last-price is still not a tradable/OE-honest match. Whale alignments still abstain on `ABSTAIN_INSTITUTIONAL_UNAVAILABLE` (no `WhaleLedger`). Did not change adapters, `discover_equity_quote_stack`, or CLI `quote_provider` (owned by the OpenD hop-unify worker). |

## 2026-09-13 — Unify OpenD hop quote_provider (Yahoo overlay-only)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `providers`, `strategy`, `tools` |
| **Summary** | Lifted #46 OpenD/Yahoo adapters, `equity_quote_selection`, `with_moomoo_opend_primary_quote`, and Primary L1 tests onto the #45 persist-CLI tree. Path A hop `quote_provider` is always `primary_equity_quote_provider()` (Moomoo OpenD). `discover_equity_quote_stack()` no longer swaps Yahoo in when OpenD is down; Yahoo stays overlay-only (`US_EQUITY_SNAPSHOT`, ES pre-HTTP reject). Persist CLI, catalog invoke, and Live argparse refusal are unchanged. Honest OpenD-down outcome is `PROVIDER_UNAVAILABLE` / `OPEND_UNAVAILABLE` (or `MOOMOO_TRANSPORT_NOT_IMPLEMENTED` if loopback TCP answers). Did not implement `moomoo-api` transport. FTEP is not `EMPIRICAL_ACTIVE`. Live stays off. Did not fold Finviz HTTP. |
| **Key files** | `src/market_platform_foundation/providers/adapters/moomoo_opend_equity_quote.py`, `src/market_platform_foundation/providers/adapters/yahoo_delayed_equity_quote.py`, `src/market_platform_foundation/providers/equity_quote_selection.py` (new), `src/market_platform_foundation/providers/equity_quote_discovery.py`, `src/market_platform_foundation/providers/composition.py`, `tools/path_a_prospective_run.py`, `tests/providers/test_moomoo_opend_primary_l1.py` (new), `tests/intelligence/test_path_a_prospective.py`, `docs/providers/MOOMOO_OBSERVATIONAL.md`, `docs/architecture/PAPER_FORWARD_TESTING_BRIDGE.md`, `docs/platform/PROGRAM_STATUS.md` |
| **Tests** | `tests.intelligence.test_path_a_prospective` **40 passed**. `tests.providers.test_moomoo_opend_primary_l1` **21 passed** (61 combined). Honest CLI with OpenD down: `discovery.provider_id=moomoo.opend.observational`, `overlay_provider_id=yahoo.finance.delayed`, `opend_reachable=false`, `result.status=PROVIDER_UNAVAILABLE`, `reason_codes=["OPEND_UNAVAILABLE"]`, `path_a_status=null`. `--mode live` still argparse-refused. `python3 tools/validate.py changed --paths-file` (12 merge-base paths vs `origin/cursor/path-a-persist-cli-d1ba`@`ce49048`) **2316 passed / 36 skipped / 0 fail / 0 err** (`core_checkpoint_required=true` from `tools/path_a_prospective_run.py`). `python3 tools/imp.py lint` passed. Docs links OK (188 files). |
| **Related** | Stacked on #45 `ce49048`. Lifts #46 `01dd28e` adapters. Does not push onto #42/#45/#46. |
| **Notes** | Operator OpenD + vendor transport remain empirical blockers after this software wire. Cloud VM has no loopback `:11111`. No secrets printed. |

## 2026-09-13 — Path A CLI can inject the optional PD-09 persist context

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `tools`, `strategy` |
| **Summary** | `tools/path_a_prospective_run.py` now accepts `--persist-account-id`/`--persist-session-id`/`--persist-strategy-id`/`--persist-strategy-version` and, when every value is supplied AND the existing `IMP_STATE_DIR`/`IMP_PERSIST_STATE` persist-on switch is already set, builds a `ForwardTestService` off durable local state and injects `PathAPersistContext` into `PathAProspectiveComposer`. This closes the gap where `ForwardTestService.create_decision` was reachable only inside library tests (PR #42, `91b8889`) but structurally unreachable from the production CLI. The CLI never creates or activates a campaign/session itself — it only wires an operator-supplied, already-governed session (e.g. one created via `tools/ftep_session_start.py`). `--mode` still only accepts `paper`/`demo`; Live stays refused by `argparse` `choices`. Demo MINTED still stays `INTENTIONAL_EPHEMERAL` (composer only writes through for Paper). G7 fail-close (`G7_NOT_ACTIONABLE`) still short-circuits persistence even when a valid context is injected. Persist-off (switch unset) still yields `INTENTIONAL_EPHEMERAL` with no `create_decision` call; persist-on without full session args yields `PERSIST_SKIPPED_NO_SESSION` (unchanged fail-closed default). |
| **Key files** | `tools/path_a_prospective_run.py`, `tests/intelligence/test_path_a_prospective.py` |
| **Tests** | `tests.intelligence.test_path_a_prospective` **35 passed** (27 pre-existing + 8 new `PathACliPersistTests`: persist-off → `INTENTIONAL_EPHEMERAL`/no write; persist-on without session args → `PERSIST_SKIPPED_NO_SESSION`; persist-on Paper with injected fixture session → `create_decision` exercised, `PERSIST_WRITTEN`, one row in `forward_test_decisions`; persist-on Demo stays `INTENTIONAL_EPHEMERAL` with zero rows; G7 fail-close still binds `G7_NOT_ACTIONABLE`/`PERSIST_NOT_MINTED` even with context injected; Live still refused with persist args present; `build_cli_persist_context` requires all four identifiers and the existing persist-on switch). Related intelligence suites (`test_path_a_scan_caller`, `test_opportunity_freshness`, `test_intelligence_contracts`, `test_opportunity_comparison`) **57 passed**. `python3 tools/validate.py changed --paths-file` (2 merge-base paths vs `origin/cursor/provider-real-data-d1ba`@`33e6705`) **2042 passed / 25 skipped / 0 fail / 0 err** (`core_checkpoint_required=true`, escalated by the still-unowned `tools/path_a_prospective_run.py` executable path, same as PR #42's prior CLI changes). `python3 tools/imp.py lint` **passed**. |
| **Related** | PR #42 (`91b8889` persist hop, `44fdcec`/`33e6705` CLI scan-caller invoke). Item 8 of the activation program (canonical hop → optional PD-09 v6 persistence). |
| **Notes** | Real reachability still requires an operator-supplied, already-frozen/activated Forward-Test session (out-of-band, e.g. via `tools/ftep_session_start.py`); the CLI does not fabricate or freeze a campaign, matching the doctrine's "no campaign activation from documentation alone." No MATCHED fixture is minted by default (`build_paper_demo_path_a_invoke` honesty invoke is untouched); MATCHED-fixture cases only exist inside the new tests. FTEP is not `EMPIRICAL_ACTIVE`/`CALIBRATED`. No secrets printed — `persist_context_injected` is a boolean; session/account/strategy identifiers are operator-supplied CLI args, not credentials. |

## 2026-09-13 — Restack Path A hop (#42) onto merged calibration (#41)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs` |
| **Summary** | Rebase `cursor/provider-real-data-d1ba` onto `origin/main` after PR #41 merge `4ba44cf`. Restore the merged Tradier sandbox calibration harness row beside the Path A prospective hop row. Canonical SHA is `4ba44cf` (merged #32–#41). FTEP-V1-001/002 labels unchanged — **not** `EMPIRICAL_ACTIVE`. Simulator **not** `CALIBRATED`. Live remains disabled. Item 7 stays PARTIAL. |
| **Key files** | `docs/platform/PROGRAM_STATUS.md`, `docs/engineering/WORK_LOG.md` |
| **Tests** | Docs-only restack; hop tests not re-run in this increment. CI must go 9/9 on the new head before merge. |
| **Related** | [PR #42](https://github.com/AdamEddahmouni/market-trading-platform/pull/42); [PR #41](https://github.com/AdamEddahmouni/market-trading-platform/pull/41) merge `4ba44cf` |
| **Notes** | Does not activate Live. Does not mint ForecastV1. Does not change the FTEP-V1-001 fingerprint. |

## 2026-09-13 — Path A hop CLI loads a real (non-fixture) baseline strategy catalog

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `strategy`, `opportunity` |
| **Summary** | `build_paper_demo_path_a_invoke` (Paper/Demo only) no longer registers `strategies=()`. It now loads `build_paper_demo_strategy_catalog()` (`strategy/path_a_strategy_catalog.py`): the existing production `FORECAST_MOMENTUM` / `WHALE_ALIGNED` / `WHALE_CONTRARIAN` baseline-only specs (`strategy/evaluation.py`) wired to the real `interpret_strategy` evaluator, using the real fetched quote's last price/timestamp when available. No preregistration authority is wired into this one-shot hop, so every entry legitimately abstains (`ABSTAIN_NO_PREREGISTRATION`; whale alignments also `ABSTAIN_INSTITUTIONAL_UNAVAILABLE` — no `WhaleLedger` configured). Path A therefore still returns honest `EMPTY` / `NO_MATCHED_STRATEGY` on this hop, but from a genuine evaluation of 3 real strategies instead of a trivially empty candidate list. No hardcoded/lambda `MATCHED` is introduced anywhere. Confirmed live against the real Sunday Yahoo delayed overlay: `status=G7_NOT_ACTIONABLE`, `path_a_status=EMPTY`. Item 7 (Opportunity Engine in the hop) remains empirically **PARTIAL** — this closes only the empty-catalog software gap, not an empirical MATCHED. |
| **Key files** | `src/market_platform_foundation/strategy/path_a_strategy_catalog.py` (new), `src/market_platform_foundation/strategy/path_a_prospective.py`, `tests/intelligence/test_path_a_strategy_catalog.py` (new), `tests/intelligence/test_path_a_prospective.py`, `docs/engineering/OPPORTUNITY_ENGINE_V1.md`, `docs/platform/PROGRAM_STATUS.md` |
| **Tests** | New `tests.intelligence.test_path_a_strategy_catalog` **8 passed**. Focused Path A + scan caller + ingest + freshness (PR command + catalog module) **72 passed**. Wider focused Path A + scan caller + ingest + freshness + strategy scanning + equity paper runtime **97 passed**. Manual CLI run against real Yahoo delayed overlay: `discovery.provider_id=yahoo.finance.delayed`, `result.status=G7_NOT_ACTIONABLE`, `result.path_a_status=EMPTY`, `reason_codes` includes `NO_MATCHED_STRATEGY`. Live mode still refused (`--mode live` rejected by argparse; `build_paper_demo_path_a_invoke(mode="live")` raises `LIVE_SCAN_CALLER_FORBIDDEN`). `python3 tools/imp.py validate changed --paths-file` (merge-base `origin/main`, 18 paths) **2854 passed / 36 skipped / 0 fail / 0 err**. Docs links OK (188 files). |
| **Related** | PR #42. Follows Path A CLI invoke (`44fdcec`) and MATCHED OE fixture (`33e6705`). |
| **Notes** | The catalog is a genuine extension point: if a real preregistration authority and/or an entitled institutional (`WhaleLedger`) source are wired into Path A in a future increment, the same evaluator would start producing genuine `MATCHED` dispositions with no change to the scanner or caller. Until then, abstention is the honest outcome regardless of the real quote's price. The CLI (`tools/path_a_prospective_run.py`) still builds its invoke before fetching the quote, so the CLI-run catalog currently evaluates without live quote context (composer-internal auto-build, used by tests, does thread the fetched quote through `quote_event`); this does not change the abstain-always outcome today. |

## 2026-09-13 — Path A MATCHED fixture invokes Opportunity Engine

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `strategy`, `opportunity` |
| **Summary** | Paper/Demo MATCHED fixtures on `PathAProspectiveComposer` now have tests that `PathAScanCaller` enters the MATCHED loop and calls `bridge_strategy_match_to_opportunity` → `OpportunityEngine.assess`. Honest EMPTY still does not call the engine (`NO_MATCHED_STRATEGY`). If G7 fail-closes, overall status stays `G7_NOT_ACTIONABLE` even when Path A is `MINTED`. Live remains `LIVE_FORBIDDEN` and does not assess. Production CLI honesty invoke is unchanged (`strategies=()`). FTEP is not `EMPIRICAL_ACTIVE`. Fills are not fabricated. This is software proof, not an empirical MATCHED hop. |
| **Key files** | `tests/intelligence/test_path_a_prospective.py`, `docs/engineering/OPPORTUNITY_ENGINE_V1.md`, `docs/platform/PROGRAM_STATUS.md`, `docs/architecture/PAPER_FORWARD_TESTING_BRIDGE.md`, `docs/product/OPPORTUNITY_ENGINE_CURRENT_STATE_AND_IMPLEMENTATION_PLAN.md` |
| **Tests** | Focused Path A + scan caller + ingest + freshness **63 passed**. MATCHED Paper/Demo fixtures call `assess`; EMPTY does not; Live does not. `python3 tools/imp.py validate changed --paths-file` (16 merge-base paths vs `origin/main`) **2845 passed / 36 skipped / 0 fail / 0 err**. Docs links OK (188 files). |
| **Related** | PR #42. Prior Path A CLI invoke + persist hop. |
| **Notes** | No new unclassified files. Ingest still does not import the scanner. Not a daemon. Item 7 stays empirically PARTIAL. |

## 2026-09-13 — Path A CLI invokes PathAScanCaller on Paper/Demo

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `strategy`, `tools` |
| **Summary** | Paper/Demo `tools/path_a_prospective_run.py` now injects `PathAScanCaller` via `build_paper_demo_path_a_invoke` instead of running the composer with a null caller. No MATCHED strategies yields honest `EMPTY` / `NO_MATCHED_STRATEGY` (no fixture mint). If G7 fail-closes, overall status stays `G7_NOT_ACTIONABLE` while Path A still runs for that honesty EMPTY. Composer auto-builds the same invoke when tests do not inject a caller. Live remains `LIVE_FORBIDDEN`. FTEP is not `EMPIRICAL_ACTIVE`. Fills are not fabricated. |
| **Key files** | `strategy/path_a_prospective.py`, `tools/path_a_prospective_run.py`, `strategy/__init__.py`, `tests/intelligence/test_path_a_prospective.py`, `docs/engineering/OPPORTUNITY_ENGINE_V1.md`, `docs/platform/PROGRAM_STATUS.md`, `docs/product/OPPORTUNITY_ENGINE_CURRENT_STATE_AND_IMPLEMENTATION_PLAN.md`, `docs/architecture/PAPER_FORWARD_TESTING_BRIDGE.md` |
| **Tests** | Focused Path A + scan caller + ingest + freshness **58 passed**. CLI injects caller; Live argparse refuses `--mode live`. `python3 tools/imp.py validate changed --paths-file` (16 merge-base paths vs `origin/main`) **2840 passed / 36 skipped / 0 fail / 0 err**. Docs links OK (188 files). |
| **Related** | PR #42. Prior Path A persist hop + prospective hop. |
| **Notes** | No new unclassified files. Ingest still does not import the scanner. Not a daemon. |

## 2026-09-13 — Path A optional PD-09 persist hop after MINTED

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `strategy`, `persistence` |
| **Summary** | `PathAProspectiveComposer` writes schema v6 via existing `ForwardTestService.create_decision` after a Paper MINTED result when persist is on and an existing FT session is injected. Payload includes G7 freshness and `opportunity_id` so `forward_test_signal_links` populate. Persist-off minted decisions stay `INTENTIONAL_EPHEMERAL` (no second store). Live still does not mint. FTEP is not `EMPIRICAL_ACTIVE`. Fills are not fabricated. |
| **Key files** | `strategy/path_a_prospective.py`, `tests/intelligence/test_path_a_prospective.py`, `docs/architecture/PAPER_FORWARD_TESTING_BRIDGE.md`, `docs/engineering/OPPORTUNITY_ENGINE_V1.md`, `docs/platform/PROGRAM_STATUS.md` |
| **Tests** | Focused `tests.intelligence.test_path_a_prospective` **15 passed**. Related Path A + freshness **45 passed**. `python3 tools/imp.py validate changed --paths-file` (16 merge-base paths) **2833 passed / 36 skipped / 0 fail / 0 err**. Docs links OK (188 files). |
| **Related** | PR #42. Prior Path A prospective hop + repository-closure CLI classification. |
| **Notes** | Requires an existing Paper FT session; Path A does not auto-activate FTEP. Demo MINTED does not write FT rows. |

## 2026-09-13 — Classify Path A prospective CLI in repository-closure inventory

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `validation`, `tools` |
| **Summary** | PR #42 `validate-python-changed` failed with `ClosureAuditError: unclassified path: tools/path_a_prospective_run.py`. Classified the one-shot Paper/Demo Path A CLI as `RETAINED_SUPPORTING` under `qualification-and-operations-tooling`, matching sibling IMP CLIs (`opportunity_summaries.py`, FTEP operator tools). Live guards and FTEP empirical status unchanged. |
| **Key files** | `artifacts/repository-closure/POST_BUILD35_SUBSYSTEM_CLASSIFICATION.json` |
| **Tests** | Focused `test_canonical_audit_is_complete_non_destructive_and_uses_closed_vocabulary` **passed**. `python3 tools/imp.py validate changed --paths-file` with the same 12 merge-base paths CI used **2830 passed / 36 skipped / 0 fail / 0 err**. |
| **Related** | PR #42. Prior Path A prospective hop entry. |
| **Notes** | Did not declare FTEP `EMPIRICAL_ACTIVE`. Did not substitute mock data as empirical. |

## 2026-09-13 — Path A prospective one-shot hop (Yahoo delayed + OpenD fail-closed)

| Field | Value |
|-------|-------|
| **Status** | `in-progress` |
| **Area** | `providers`, `strategy`, `opportunity` |
| **Summary** | One-shot Paper/Demo composer joins an equity quote adapter through admission, G7 freshness, and Path A. Yahoo delayed is the cloud-reachable prospective overlay (not real-time, not ES). Moomoo OpenD fails closed when the daemon or in-tree transport is absent. Live remains forbidden. FTEP is not EMPIRICAL_ACTIVE. |
| **Key files** | `strategy/path_a_prospective.py`, `providers/adapters/yahoo_delayed_equity_quote.py`, `providers/adapters/moomoo_opend_equity_quote.py`, `providers/equity_quote_discovery.py`, `market_data/runtime_composition.py`, `ui_api/opportunity_projections.py`, `tools/path_a_prospective_run.py`, `tests/intelligence/test_path_a_prospective.py` |
| **Tests** | `PYTHONPATH=src python3 -m unittest tests.intelligence.test_path_a_prospective tests.intelligence.test_path_a_scan_caller tests.intelligence.test_opportunity_ingest tests.intelligence.test_opportunity_freshness tests.ui1.test_opportunity_api tests.market_data.test_g7_runtime_composition -q` — 64 passed |
| **Related** | Canonical start `9cb541c` (PR #40). Does not activate Live or FTEP empirical. |
| **Notes** | ES-news remains BLOCKED_ON_ES_DATA. Yahoo hop is DELAYED_PROSPECTIVE; G7 `DELAYED_WHEN_REALTIME_REQUIRED`. |

## 2026-09-13 — Rebaseline PROGRAM_STATUS SHA to origin/main@9cb541c

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs` |
| **Summary** | Close the item-18 SHA lag that [#43](https://github.com/AdamEddahmouni/market-trading-platform/pull/43) skipped: `PROGRAM_STATUS` canonical origin/main SHA now matches git tip `9cb541cd520721404e1c3d789eba5445c45aae70` (PR #40) plus this draft’s IMPLEMENTED Paper vs Tradier sandbox calibration harness. Path A scan caller remains `MERGED` / `REMOTE VALIDATED` at `6833bf3` (PR #39). FTEP-V1-001/002 labels unchanged — **not** `EMPIRICAL_ACTIVE`. Simulator **not** `CALIBRATED`. Live remains disabled. |
| **Key files** | `docs/platform/PROGRAM_STATUS.md`, `docs/engineering/WORK_LOG.md` |
| **Tests** | `python3 tools/check_docs_links.py` — **188 OK**. Docs-only SHA/prose; calibration harness tests not re-run in this increment. |
| **Related** | [PR #41](https://github.com/AdamEddahmouni/market-trading-platform/pull/41); [PR #40](https://github.com/AdamEddahmouni/market-trading-platform/pull/40) merge `9cb541c`; [PR #43](https://github.com/AdamEddahmouni/market-trading-platform/pull/43) skipped these files |
| **Notes** | Item 18 stays PARTIAL until #41/#42 land and Notion inner SHA callouts match git. Do not merge from this increment. Do not activate Live. |

## 2026-09-13 — IMP vs Tradier sandbox calibration harness

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `paper/calibration`, `providers/adapters/tradier` |
| **Summary** | Finished existing `paper/calibration/*` into a fail-closed IMP simulator vs Tradier sandbox comparator: correlation pairing, honest metrics (N, distributions, median, percentiles; fill/price/latency/partials/rejects/cancels), schema v6 observation persistence, campaign runner that classifies `COMPARATOR_NOT_CONFIGURED` / `WAITING_FOR_MARKET` without fabricating fills. Sandbox HTTPS opt-in only; production and Alpaca live hosts blocked. Simulator stamped `phase7.bar-conservative/1.1.0`. Not CALIBRATED. FTEP not `EMPIRICAL_ACTIVE`. Equity Paper does not validate ES. |
| **Key files** | `src/market_platform_foundation/paper/calibration/{pairing,metrics,persistence,runner,asset_scope,comparator_contract}.py`; `src/market_platform_foundation/providers/adapters/{tradier_paper,tradier_sandbox_http}.py`; `tests/platform/test_calibration_harness.py`; `tools/providers/run_calibration_harness.py`; `docs/architecture/PAPER_SIMULATOR_CALIBRATION_CONTRACT.md`; `docs/providers/TRADIER_PAPER.md` |
| **Tests** | `PYTHONPATH=src python3 -m unittest tests.platform.test_simulator_calibration tests.platform.test_calibration_harness tests.platform.test_broker_paper_p4` — **38 passed** |
| **Related** | [PR #41](https://github.com/AdamEddahmouni/market-trading-platform/pull/41); [PAPER_SIMULATOR_CALIBRATION_CONTRACT.md](../architecture/PAPER_SIMULATOR_CALIBRATION_CONTRACT.md); [TRADIER_PAPER.md](../providers/TRADIER_PAPER.md) |
| **Notes** | No sandbox token on this cloud VM. No Live orders. Alpaca not authenticated. Numeric gates remain UNSET/BLOCKING. |

## 2026-09-13 — Path A scan caller merged (PR #39)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs` |
| **Summary** | PR #39 merged to `main` at `6833bf3`. PROGRAM_STATUS labels Path A Paper/Demo scan caller `MERGED` / `REMOTE VALIDATED`. G7 freshness remains MERGED. FTEP labels unchanged. |
| **Key files** | `docs/platform/PROGRAM_STATUS.md`, `docs/engineering/WORK_LOG.md` |
| **Tests** | GitHub IMP Validation + Guardrails on PR #39 head `75b575f` all pass (`validate-python-changed` 1860 tests / 25 skipped / 0 fail / 0 err). Focused Path A + ingest/operator-loop **24 passed**. FAST **23 passed**. |
| **Related** | [PR #39](https://github.com/AdamEddahmouni/market-trading-platform/pull/39); merge SHA `6833bf3c400ab02f3203f715a6653a23d8e7f6f0` |
| **Notes** | Simulator still not calibrated. FTEP not `EMPIRICAL_ACTIVE`. Live execution disabled. |

## 2026-09-13 — Path A Paper/Demo scan caller

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `strategy` / `intelligence/opportunity` |
| **Summary** | Added bounded `PathAScanCaller`: one `UniversalStrategyScanner` pass → Path A mint (`bridge_strategy_match_to_opportunity`). Paper/Demo only; Live raises `LIVE_SCAN_CALLER_FORBIDDEN`. Honest EMPTY when no MATCHED strategy. Ingest stays a review assembler. Not a daemon, not `StrategyPaperRuntime` workstation wiring, not FTEP. |
| **Key files** | `src/market_platform_foundation/strategy/path_a_scan_caller.py`, `tests/intelligence/test_path_a_scan_caller.py`, `docs/engineering/OPPORTUNITY_ENGINE_V1.md`, `docs/platform/PROGRAM_STATUS.md` |
| **Tests** | `PYTHONPATH=src python3 -m unittest tests.intelligence.test_path_a_scan_caller` plus ingest/operator-loop **24 passed**. FAST **23 passed**. |
| **Related** | G7 freshness MERGED [PR #37](https://github.com/AdamEddahmouni/market-trading-platform/pull/37) at `ea39223`. Docs rebaseline [PR #38](https://github.com/AdamEddahmouni/market-trading-platform/pull/38) at `63962a9`. |
| **Notes** | Simulator still not calibrated. FTEP not `EMPIRICAL_ACTIVE`. Live execution disabled. |

## 2026-09-13 — Opportunity Engine G7 freshness merged (PR #37)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs` |
| **Summary** | PR #37 merged to `main` at `ea39223`. PROGRAM_STATUS labels Opportunity Engine G7 freshness `MERGED` / `REMOTE VALIDATED`. G7 runtime wiring remains COMPLETE. FTEP labels unchanged. Path A not started in this docs PR. |
| **Key files** | `docs/platform/PROGRAM_STATUS.md`, `docs/engineering/WORK_LOG.md` |
| **Tests** | GitHub IMP Validation + Guardrails on PR #37 head `028a564` all pass (`validate-python-changed` 1411 tests / 25 skipped / 0 fail / 0 err). Focused freshness unittest **24 passed**. FAST **23 passed**. |
| **Related** | [PR #37](https://github.com/AdamEddahmouni/market-trading-platform/pull/37); merge SHA `ea39223825486b3c0c4f6bc3dcc88524dc655ed0` |
| **Notes** | Simulator still not externally validated. FTEP not `EMPIRICAL_ACTIVE`. |

## 2026-09-13 — G7 freshness reconstruction test import

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `intelligence/opportunity` |
| **Summary** | GitHub `validate-python-changed` on PR #37 failed with 1 error: `test_reconstruct_surfaces_payload_freshness` referenced `POLICY_VERSION` without importing it from `forward_test_activation_support`. Import added; no production behavior change. |
| **Key files** | `tests/intelligence/test_opportunity_freshness.py` |
| **Tests** | `PYTHONPATH=src python3 -m unittest tests.intelligence.test_opportunity_freshness` **24 passed** including the reconstruction case. FAST **23 passed**. |
| **Related** | [PR #37](https://github.com/AdamEddahmouni/market-trading-platform/pull/37); G7 freshness binding entry below. |
| **Notes** | Does not reopen G7 runtime COMPLETE. Path A not started. FTEP labels unchanged. |

## 2026-09-13 — Opportunity Engine G7 freshness binding

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `intelligence/opportunity` |
| **Summary** | Added a platform Opportunity Engine freshness evaluator that uses G7 runtime capability axes (timeliness/entitlement) plus session/delay/book-invalid awareness. Structured FRESH/STALE/UNKNOWN/NOT_APPLICABLE results are explainable, clock-injectable, fail-closed for STALE/UNKNOWN eligibility, and persisted on `data_quality` plus FT `decision_payload` when present. Does not reopen G7 runtime COMPLETE, start Path A, or flip FTEP empirical labels. |
| **Key files** | `src/market_platform_foundation/intelligence/opportunity/{freshness,data_quality,ingest}.py`, `paper_forward_bridge/reconstruction.py`, `tests/intelligence/test_opportunity_freshness.py`, `docs/platform/PROGRAM_STATUS.md`, `docs/product/OPPORTUNITY_ENGINE_CURRENT_STATE_AND_IMPLEMENTATION_PLAN.md` |
| **Tests** | `PYTHONPATH=src python3 -m unittest tests.intelligence.test_opportunity_freshness` plus honesty/ingest/operator-loop **45 passed**. FAST / `validate changed` recorded after the CI-equivalent run. |
| **Related** | G7 runtime wiring remains COMPLETE. Persistence DoD remainder MERGED as [PR #36](https://github.com/AdamEddahmouni/market-trading-platform/pull/36) at `3e74c49`. |
| **Notes** | Simulator still not calibrated. FTEP not `EMPIRICAL_ACTIVE`. Path A not started. |

## 2026-09-13 — Persistence DoD remainder closed (signal-link restart; persist-off acks)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `intelligence/paper_forward_bridge`, `ui_api/operator_opportunity_state` |
| **Summary** | Closed the two leftover durable-persistence PARTIALs without a second store. Signal links keyed by `decision_payload.opportunity_id` now have a restart/reconstruct test (opportunity → decision → `paper_order_id` → ledger). Persist-off operator acks are documented and tested as `INTENTIONAL_EPHEMERAL`; `persistence_required` campaigns stay `PERSISTENCE_DISABLED`. Does not start Opportunity Engine G7 freshness, Path A, FTEP empirical, or simulator calibration. |
| **Key files** | `src/market_platform_foundation/intelligence/paper_forward_bridge/reconstruction.py`, `src/market_platform_foundation/ui_api/operator_opportunity_state.py`, `tests/intelligence/test_forward_test_persistence.py`, `docs/architecture/PAPER_FORWARD_TESTING_BRIDGE.md`, `docs/platform/PROGRAM_STATUS.md` |
| **Tests** | Persistence unittest **46 passed** (was 39). FAST **23 passed**. Docs links OK. `validate changed` (merge-base paths) **1897 passed / 36 skipped / 0 fail**. GitHub PR #36 checks all pass (`validate-python-changed` 1m58s). FULL/closure not run (`paper/**` untouched). |
| **Related** | PD-09 remains COMPLETE (PR #18). Schema v6 MERGED as [PR #34](https://github.com/AdamEddahmouni/market-trading-platform/pull/34) at `2dd49ea`. Canonical `origin/main` at this writing: `936f44b` ([PR #35](https://github.com/AdamEddahmouni/market-trading-platform/pull/35)). |
| **Notes** | OpportunityV1 objects stay in the intelligence repo; the campaign store persists the link identity only. Simulator still not externally validated. FTEP labels unchanged. |

## 2026-09-13 — Durable forward-test persistence merged (PR #34)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs` |
| **Summary** | PR #34 merged to `main` at `2dd49ea`. PROGRAM_STATUS labels the schema v6 increment `MERGED` / `REMOTE VALIDATED`. PD-09 remains COMPLETE. FTEP labels unchanged. Path A / G7 remain DEFERRED. |
| **Key files** | `docs/platform/PROGRAM_STATUS.md`, `docs/engineering/WORK_LOG.md` |
| **Tests** | `python3 tools/check_docs_links.py`; GitHub `validate` on this docs PR |
| **Related** | [PR #34](https://github.com/AdamEddahmouni/market-trading-platform/pull/34); merge SHA `2dd49ea1a75a45f8eefba79576ac4ac537cbde5d` |
| **Notes** | Simulator still not externally validated. |

## 2026-09-13 — Durable forward-test persistence increment (schema v6)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `local_state`, `intelligence/paper_forward_bridge` |
| **Summary** | Extends PD-09 `local_state` SQLite to schema v6 without a second store: transactional FT writes, atomic paper-submit/evaluation claims (H2/H3), reconstruction from Paper ledger + observations (H7), git SHA + simulator version provenance, campaign/strategy/instrument isolation queries, Paper/Live leak-closed at the repository, unique operator acks. Does not start FTEP empirical sessions or flip campaign labels. |
| **Key files** | `src/market_platform_foundation/local_state/{schema,migrations,connection}.py`, `intelligence/paper_forward_bridge/{sqlite_repository,store,service,evaluation,reconstruction,paper_ledger_join,run_identity}.py`, `ui_api/operator_opportunity_state.py`, `tests/intelligence/test_forward_test_persistence.py` |
| **Tests** | Persistence unittest **39 passed**. Related bridge+policy **20 passed**. FAST **23 passed**. `validate changed` vs `origin/main...HEAD` **2443 passed / 39 skipped / 0 fail** (104s). Docs links OK. GitHub PR #34 checks all pass (`validate-python-changed` 2m27s). FULL/closure not run (`paper/**` untouched). |
| **Related** | PD-09 remains COMPLETE (PR #18). Merged as [PR #34](https://github.com/AdamEddahmouni/market-trading-platform/pull/34) at `2dd49ea`. |
| **Notes** | Simulator is not externally validated. Path A / G7 remain DEFERRED. |

## 2026-09-13 — Opportunity Engine operator review loop (Goal 001)


| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `intelligence/opportunity`, `ui_api`, `ui/now` |
| **Summary** | Landed the Demo/Paper operator review loop on existing `OpportunityV1`: ingest (strip storage `_id`), explainable ranking vector, `GET /opportunities*`, NOW Opportunity Review Card, Paper watch/dismiss, non-ranking `decision_support`, explain/inspect. Live NOW does not query. Honest empty/unready queue is valid. Opportunity Zod/fetch is lazy Demo/Paper only so the initial gzip budget stays 203 KiB. |
| **Key files** | `src/market_platform_foundation/intelligence/opportunity/{ingest,ranking,lifecycle,dedup,data_quality}.py`, `ui_api/opportunity_projections.py`, `ui_api/projections.py`, `manifests/ui1/schemas/opportunity_summary.schema.json`, `ui/src/api/opportunityClient.ts`, `ui/src/components/now/OpportunityReviewCard.tsx`, `ui/src/components/{ModeNowRoute,demo-now/DemoNowPage,paper-now/PaperNowPage,paper-now/PaperCandidateQueue}.tsx`, `tools/validation_manifest.json`, `docs/architecture/OPPORTUNITY_CONTRACT.md`, `docs/engineering/OPPORTUNITY_ENGINE_V1.md`, `docs/product/OPPORTUNITY_ENGINE_CURRENT_STATE_AND_IMPLEMENTATION_PLAN.md` |
| **Tests** | focused intelligence/ui1 opportunity selectors (43 passed); `cd ui && npm test` 92 files / 463 passed; `npm run typecheck` pass; `npm run build` initial **201.23 KiB gzip**; `python tools/imp.py validate fast` 23 passed. `validate changed` is CI; FULL/closure not run (Paper-execution path untouched). |
| **Related** | Goal 001 plan; PR #32 (canonical). Competing draft PR #33 is not the merge target. |
| **Notes** | Path A mint unchanged as fixture library. No production scanner, Live ranking, FTEP sessions, or fabricated MATCHED rows. |

## 2026-09-12 — Post-merge landing banners: origin/main is 3bb5aa2f

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs` |
| **Summary** | Independently verified `origin/main` is `3bb5aa2f` after merging PRs **#29** then **#30**. Replaced leftover current “until #29 merges” landing banners; recorded Last Verified + canonical SHA on PROGRAM_STATUS. Did not rewrite doctrine, did not claim `EMPIRICAL_ACTIVE`, did not claim Notion synced. |
| **Key files** | `docs/platform/PROGRAM_STATUS.md`, `docs/engineering/DEVELOPER_OPERATING_SYSTEM.md`, `AGENTS.md`, `docs/engineering/CURSOR_CLOUD_ENVIRONMENT.md`, `docs/engineering/WORK_LOG.md` |
| **Tests** | `python tools/check_docs_links.py`; required GitHub `validate` on this docs PR |
| **Related** | Merged **#29** (`6f7f1d4d`) then **#30** (`3bb5aa2f`); split PRs **#22–#28** and **#21** left open |
| **Notes** | `588ada8a` remains only in historical snapshot artifacts (e.g. wave-a repo-architecture audit). #21 still has unique blob diffs vs main after the strategy copy. |

## 2026-09-12 — P3/P4 docs and governance coherence for post-#29 clone

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs`, `AGENTS.md`, `.github` |
| **Summary** | Smallest docs/governance pass so a clone of `main` after PR #29 is coherent: copied unique provider-universe strategy from #21; corrected FTEP catalog/PROGRAM_STATUS (V1-001 `MANIFEST_FROZEN` + entitlement blocked / SIGNAL_ONLY not authorized; V1-002 `MANIFEST_FROZEN` + `SIGNAL_ONLY_AUTHORIZED` via receipt, empirical lock via receipt, 0 sessions / not `EMPIRICAL_ACTIVE`); Start-here navigation; snapshot banners; monorepo origin; repo-root AGENTS.md; DoD/PR template no longer force FULL/closure on docs PRs. |
| **Key files** | `docs/engineering/FTEP_CAMPAIGN_CATALOG.md`, `docs/platform/PROGRAM_STATUS.md`, `docs/README.md`, `AGENTS.md` (repo root + IMP), `docs/platform/GLOSSARY.md`, `.github/pull_request_template.md`, `docs/providers/PROVIDER_UNIVERSE_AUDIT_INTEGRATION_STRATEGY.md` |
| **Tests** | `python tools/check_docs_links.py` (intended); required GitHub `validate` on PR #29 after push |
| **Related** | PR **#29**; unique file from PR **#21** (left open) |
| **Notes** | Did not merge split PRs #22–#28; did not commit `p3-plan-cli-check.json` |

## 2026-09-12 — FTEP-V1-002 wave 20 empirical lock receipt gate

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `intelligence/paper_forward_bridge`, `artifacts/ftep-v1-002`, `tests` |
| **Summary** | Resolved `EMPIRICAL_LOCK_NOT_AUTHORIZED` blocker: prospective lock dry-run now honors append-only `empirical-lock-authorization-receipt-*.json` (and optional `empirical_lock_authorized` on signal-only receipts) while frozen manifest `operator_attestation.empirical_lock_authorized` stays false. Recorded owner SIGNAL_ONLY prospective decision-lock authorization; updated launch prep. US_EQUITY_RTH closed — no live locks. |
| **Key files** | `campaign_status.py`, `ftep_prospective_lock.py`, `artifacts/ftep-v1-002/empirical-lock-authorization-receipt-2026-09-12.json`, `SIGNAL_ONLY_LAUNCH_PREP.md`, `tests/intelligence/test_ftep_prospective_lock.py`, `tests/intelligence/test_ftep_campaign_status.py` |
| **Tests** | `unittest tests.intelligence.test_ftep_prospective_lock tests.intelligence.test_ftep_campaign_status` |
| **Related** | FTEP-V1-002 goal @ `e86848fb`; PR **#29** |
| **Notes** | Goal still not complete until first RTH governed session + durable locks; lock dry-run clears auth blocker when receipt present |

## 2026-09-12 — FTEP-V1-002 wave 19 prospective lock dry-run

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `intelligence/paper_forward_bridge`, `tools`, `tests` |
| **Summary** | Wave 19 closed-market work: documented gap (no post-`create_session` auto lock listener; `watch-catalysts` is read-only). Added governed `ftep record-prospective-lock --dry-run` gate + invoke-step plan when all invariants pass; fixture tests assert blockers without durable writes. US_EQUITY_RTH closed — no governed session-start or locks. |
| **Key files** | `ftep_prospective_lock.py`, `tools/ftep_record_prospective_lock.py`, `tools/imp.py`, `tests/intelligence/test_ftep_prospective_lock.py` |
| **Tests** | `unittest tests.intelligence.test_ftep_prospective_lock` (3 passed); `imp.py ftep watch-catalysts --fixture` + `record-prospective-lock --dry-run --json` (manual closed-market) |
| **Related** | FTEP-V1-002 goal wave 19; PR **#29** |
| **Notes** | Goal not complete until first RTH governed session + real decision locks when owner enables `empirical_lock_authorized` |

## 2026-09-12 — FTEP-V1-002 wave 18 RTH bootstrap + provider health

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `scripts`, `artifacts/ftep-v1-002`, `docs` |
| **Summary** | Wave 18 closed-market work: recorded read-only provider health receipt (IMP providers probes + integrity PASS), added `scripts/ftep-rth-session-bootstrap.ps1` consolidating launch prep gates/dry-run/owner-confirmed session-start/watch-catalysts. PR #29 CI green @ `e35ab053`. Campaign progress §30 gap scan: `campaign-status` export + template sufficient. |
| **Key files** | `scripts/ftep-rth-session-bootstrap.ps1`, `artifacts/ftep-v1-002/provider-health-receipt-2026-09-12.json`, `SIGNAL_ONLY_LAUNCH_PREP.md`, `FINAL_EXECUTIVE_REPORT.md` |
| **Tests** | `imp.py ftep campaign-status/integrity-check/providers campaign-readiness+audit --probe-local` (manual); PR #29 checks 9/9 pass |
| **Related** | FTEP-V1-002 goal wave 18; PR **#29** |
| **Notes** | Goal not complete until first RTH governed session + evidence jsonl; no stack merges |

## 2026-09-12 — FTEP-V1-002 wave 17 watch-catalysts + merge stack

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `intelligence/paper_forward_bridge`, `tools`, `artifacts` |
| **Summary** | Wave 17 closed-market work: added read-only `ftep watch-catalysts` (fixture dry-run + session correlation), extended integrity-check for governed-session evidence when durable sessions exist, documented owner-only `gh pr merge` sequence for stack #22–#28 in `MERGE_STACK.md`. RTH remained closed — no governed `session-start`. |
| **Key files** | `ftep_catalyst_watch.py`, `tools/ftep_watch_catalysts.py`, `ftep_integrity.py`, `tools/imp.py`, `SIGNAL_ONLY_LAUNCH_PREP.md`, `MERGE_STACK.md`, `FINAL_EXECUTIVE_REPORT.md` |
| **Tests** | `unittest tests.intelligence.test_ftep_catalyst_watch tests.intelligence.test_ftep_integrity` (5 passed); repository closure audit PASS |
| **Related** | FTEP-V1-002 wave 16 preflight; PR #29 |

## 2026-09-12 — FTEP merge stack wave 15 reconciliation

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs`, merge stack |
| **Summary** | MERGE_STACK wave 15: #25 rebased onto #24 (`c47f1662`), cascade #26–#28 (#28 @ `9c8ccef7`), #29 @ `7c562f74` MERGEABLE CI green. |
| **Key files** | `artifacts/ftep-v1-split/MERGE_STACK.md` |
| **Tests** | n/a (docs only) |
| **Related** | PRs **#25–#29**, `MERGE_STACK.md` |

## 2026-09-12 — FTEP-V1-002 wave 14 verify + empirical prep

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `intelligence`, `docs`, merge stack |
| **Summary** | Wave 14 verification @ `2089a634`: PR #29 CI green; `IMP_PERSIST_STATE=1` integrity-check PASS, campaign-readiness READY, RTH closed — no governed session-start. Documented operator catalyst attention collector in launch prep; gitignored volatile `campaign-progress.json` with committed template. MERGE_STACK wave 14 notes (#25 CONFLICTING vs #24 `64c03de3`, no rebase). |
| **Key files** | `artifacts/ftep-v1-002/SIGNAL_ONLY_LAUNCH_PREP.md`, `campaign-progress.template.json`, `.gitignore`, `artifacts/ftep-v1-split/MERGE_STACK.md`, `artifacts/ftep-v1-002/FINAL_EXECUTIVE_REPORT.md` |
| **Tests** | `imp.py ftep integrity-check/campaign-status/session-start --dry-run` (manual); PR #29 checks green |
| **Related** | PR **#29**, FTEP-V1-002 goal wave 14 |
| **Notes** | Goal not complete until first RTH governed session + evidence jsonl |

## 2026-09-12 — FTEP-V1-002 wave 13 stack #24 + RTH gate

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `intelligence`, `docs`, merge stack |
| **Summary** | Rebased `split/wave-b-calibration` onto PR #23 (`6a15372`), vendored missing activation-core bridge/schema pieces for `validate-python-changed`, pushed `eb52824`. Verified FTEP-V1-002 @ `22d3741`: PR #29 CI green, `integrity-check` PASS, RTH closed — no governed `session-start` (document-only). |
| **Key files** | `artifacts/ftep-v1-split/MERGE_STACK.md`, `artifacts/ftep-v1-002/FINAL_EXECUTIVE_REPORT.md`, `artifacts/ftep-v1-002/notion-sync-payload-2026-09-12.md` |
| **Tests** | Local `validate changed` on #24 path list — 2977 passed; `ftep integrity-check FTEP-V1-002` → PASS |
| **Related** | PR #24, PR #29; wave 12 dual-arm binding |
| **Notes** | `session_ids`: none; `empirical_lock_count`: 0; no merge to `main` |

## 2026-09-12 — FTEP-V1-002 wave 12 dual-arm campaign binding

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ftep-v1-002`, `forward-test`, `paper_forward_bridge` |
| **Summary** | Fixed durable campaign binding so a frozen A/B campaign can open **two** SIGNAL_ONLY sessions (baseline + AI-enhanced) under one ACTIVE binding row; SQLite no longer fails the second arm with `FORWARD_TEST_CONCURRENT_CAMPAIGN_ACTIVE`. Documented dual-arm operator flow in `SIGNAL_ONLY_LAUNCH_PREP.md`. No manifest mutation; V1-001 untouched. |
| **Key files** | `paper_forward_bridge/sqlite_repository.py`, `paper_forward_bridge/campaign_binding.py`, `paper_forward_bridge/store.py`, `tests/intelligence/test_forward_test_persistence.py`, `tests/intelligence/test_ftep_session_start.py`, `artifacts/ftep-v1-002/SIGNAL_ONLY_LAUNCH_PREP.md` |
| **Tests** | `python tools/imp.py validate changed` — 1902 passed, 26 skipped; dual-arm persistence + session-start unit tests |
| **Related** | Wave 11 `ftep session-start`; `PAPER_FORWARD_TESTING_BRIDGE.md` (one ACTIVE campaign per account) |
| **Notes** | Saturday RTH closed — no empirical session or locks; goal completion awaits first open-RTH governed session with evidence. |

## 2026-09-12 — FTEP-V1-002 wave 11 governed session-start

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ftep-v1-002`, `forward-test`, `tools` |
| **Summary** | Added non–dry-run `ftep session-start` path: gates on persistence, integrity, RTH, and readiness, then calls `ForwardTestService.create_session` (SIGNAL_ONLY, no orders) and appends `governed-session-start-evidence.jsonl`. Campaign status now reads governed session/lock counts from durable SQLite; `campaign-status` exports `artifacts/ftep-v1-002/campaign-progress.json`. |
| **Key files** | `tools/ftep_session_start.py`, `tools/ftep_campaign_status.py`, `tools/imp.py`, `paper_forward_bridge/campaign_status.py`, `paper_forward_bridge/ftep_integrity.py`, `tests/intelligence/test_ftep_session_start.py`, `artifacts/ftep-v1-002/campaign-progress.json` |
| **Tests** | `python tools/imp.py validate changed` — 1901 passed, 26 skipped |
| **Related** | `artifacts/ftep-v1-002/SIGNAL_ONLY_LAUNCH_PREP.md` |
| **Notes** | US equity RTH closed on pass date; no production session started. Second cohort arm may record `FORWARD_TEST_CONCURRENT_CAMPAIGN_ACTIVE` until binding supports multiple sessions per campaign. |

## 2026-09-12 — FTEP split PR #28 rebase onto #27

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ftep-v1-split`, `forward-test` |
| **Summary** | Rebased `split/ftep-v1-freeze-readiness` onto **#27** head (`9b86e634`); resolved `test_forward_test_activation.py` add/add while preserving frozen **FTEP-V1-001** fingerprint and production freeze assertions. Updated `MERGE_STACK.md` wave 10 reconciliation. |
| **Key files** | `artifacts/ftep-v1-split/MERGE_STACK.md`, `tests/intelligence/test_forward_test_activation.py` |
| **Tests** | `unittest tests.intelligence.test_forward_test_activation` 12 OK (worktree `.venv`) |
| **Related** | PR **#28**; `MERGE_STACK.md` |
| **Notes** | Force-push required; owner merge only per stack policy. |

## 2026-09-12 — FTEP-V1-002 owner freeze and readiness

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ftep-v1-002`, `forward-test`, `providers` |
| **Summary** | Applied owner OD-2/OD-6/OD-PAPER/OD-11 on **FTEP-V1-002**: universe AAPL/MSFT/NVDA/AMZN/META, SPY benchmark-only, canonical Paper bind, immutable freeze, campaign-bound MOOMOO overlay (G-A6), preflight/readiness **READY**. **FTEP-V1-001** fingerprint unchanged. Stop line: zero sessions/locks/execution. |
| **Key files** | `artifacts/forward-test-campaigns/FTEP-V1-002/ACTIVATION_MANIFEST.json`, `frozen_manifest_verifier.py`, `capability_snapshot.py`, `coverage_gap_engine.py`, `artifacts/ftep-v1-002/frozen-manifest-verification-*.json`, `FINAL_EXECUTIVE_REPORT.md` |
| **Tests** | 16 unittest OK; `imp.py validate fast` 21/0; `imp.py validate changed` 2159/0 |
| **Related** | Section 32 executive result `READY_FOR_FIRST_SIGNAL_ONLY_AUTHORIZATION` |
| **Notes** | Finviz live probe still `LOCAL_PROBE_REQUIRED`; stale export remains authoritative. PR stack #22–#28 not merged. |

## 2026-09-12 — FTEP-V1-002 final executive report

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ftep-v1-002`, `artifacts` |
| **Summary** | Added `FINAL_EXECUTIVE_REPORT.md` at engineering stop line: executive `READY_WITH_OWNER_DECISIONS`, safety block, owner OD index, artifact paths; goal verification re-run (16 unittest, fast, changed, campaign-readiness). |
| **Key files** | `artifacts/ftep-v1-002/FINAL_EXECUTIVE_REPORT.md` |
| **Tests** | 16 unittest OK; `imp.py validate fast` 21/0; `imp.py validate changed` 2159/0 |
| **Related** | `artifacts/ftep-v1-002/owner-decision-packet-2026-09-12.md` |
| **Notes** | Owner freeze/SIGNAL_ONLY remain out-of-band. |

## 2026-09-12 — FTEP-V1-002 pre-freeze closure audit

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ftep-v1-002`, `readiness`, `artifacts` |
| **Summary** | Closed pre-freeze gaps on proposed V1-002 manifest: added `resolved_fields` (incl. FTEP-D006), `authority_resolutions` for OD-1/OD-3, deferred Wave A ingress; trimmed owner packet to four decisions; documented Finviz `LOCAL_PROBE_REQUIRED` without degrading stale capability evidence. |
| **Key files** | `artifacts/forward-test-campaigns/FTEP-V1-002/ACTIVATION_MANIFEST.json`, `artifacts/ftep-v1-002/owner-decision-packet-2026-09-12.md`, `finviz-local-probe-status-2026-09-12.json`, `notion-sync-payload-2026-09-12.md`, `tests/intelligence/test_ftep_v1_002_campaign.py` |
| **Tests** | `unittest` FTEP-V1-002 + finviz + coverage (16 OK); `imp.py validate fast` 21/0; `imp.py validate changed` 2159/0; `campaign-readiness FTEP-V1-002` — WAVE-A-002 deferred (not blocker) |
| **Related** | `artifacts/ftep-v1-002/reconciliation-matrix-2026-09-12.json`, `FTEP_CAMPAIGN_CATALOG.md` |
| **Notes** | Executive: `READY_WITH_OWNER_DECISIONS`. No Notion MCP in repo; sync payload only. Finviz probe attempted — credentials absent; `evidence/market_data/finviz/capability-report.json` restored from git. |

## 2026-09-12 — FTEP-V1-002 validation manifest follow-up

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `validation`, `ftep-v1-002` |
| **Summary** | After orchestrator completion, wired `paper_forward_bridge` changed-validation leaf to include V1-002 campaign tests, frozen-manifest verifier, and governance artifacts so `imp.py validate changed` exercises the pivot. |
| **Key files** | `tools/validation_manifest.json` |
| **Tests** | `python tools/imp.py validate fast` — 21/0; `python tools/imp.py validate changed` — 2159 passed, 0 failures |
| **Related** | [FTEP-V1-002 executive report](../../artifacts/ftep-v1-002/FINAL_EXECUTIVE_REPORT.md) |
| **Notes** | Work remains uncommitted on `work/ftep-v1-002-us-equity-news`; owner freeze decisions still open. |

## 2026-09-12 — FTEP-V1-002 US equity news-catalyst pivot

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ftep-v1-002`, `providers`, `forward-test` |
| **Summary** | Pivoted engineering focus to **FTEP-V1-002** ($0 Moomoo US equity L1 + Finviz Elite news) while preserving **FTEP-V1-001** frozen manifest/fingerprint. Added campaign profile, proposed manifest, catalyst taxonomy contract, frozen-manifest verifier (`FROZEN_BLOCKED_EXTERNAL_DATA_ENTITLEMENT` for V1-001), Moomoo prospective market-evidence bridge, and reconciliation artifacts. No freeze, SIGNAL_ONLY sessions, or empirical collection authorized. |
| **Key files** | `artifacts/forward-test-campaigns/FTEP-V1-002/`, `artifacts/ftep-v1-002/`, `src/.../frozen_manifest_verifier.py`, `src/.../moomoo_prospective_market_evidence.py`, `capability_requirements.py`, `docs/engineering/FTEP_CAMPAIGN_CATALOG.md`, `docs/engineering/ftep/assets/US_EQUITY_PROFILE_V1.md` |
| **Tests** | `python -m unittest tests.intelligence.test_ftep_v1_002_campaign tests.news.test_finviz_news_normalize tests.providers.test_coverage_gap_engine -q` |
| **Related** | [FTEP_CAMPAIGN_CATALOG.md](./FTEP_CAMPAIGN_CATALOG.md), branch `work/ftep-v1-002-us-equity-news` @ `099388f` base |
| **Notes** | PR stack #22–#28 still open on `main`; merge stack unchanged. |

## 2026-09-12 — FTEP-V1 split slices 4–7 and merge stack

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ftep-v1-activation`, `docs`, `providers` |
| **Summary** | Finished split slices 4–7 as stacked PRs **#25–#28** (Wave B closure → ES/news stack → goal audit → freeze/readiness). Published merge order in `artifacts/ftep-v1-split/MERGE_STACK.md`. Closed superseded draft **#19**. Frozen manifest fingerprint unchanged on slice #28; pathway B not authorized. |
| **Key files** | `artifacts/ftep-v1-split/MERGE_STACK.md`; branches `split/ftep-v1-wave-b-closure`, `split/ftep-v1-es-news-stack`, `split/ftep-v1-goal-audit`, `split/ftep-v1-freeze-readiness` |
| **Tests** | Per-slice `imp.py validate fast` pass (slices 4–7 worktrees); slice 4 `test_provider_snapshot_compare` OK; slice 6 observational ingress + PIT export OK; monolith `test_coverage_gap_engine` 6 OK; slice 5 profile-ref tests require merged #22 (documented stack dep) |
| **Related** | PRs #22–#28; closed #19 |
| **Notes** | Merge **#22** before **#28**; rebase each stacked PR onto `main` after its predecessor merges. |

## 2026-09-12 — FTEP pathway-B goal closure verification

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `validation`, `ftep-v1-activation` |
| **Summary** | Post-goal follow-up: re-ran `campaign-readiness` (3 blockers, preflight READY, manifest FROZEN) and full `imp.py closure`. ui1/activation paths green; full suite 4618 tests, 7 platform errors (closure baseline classifies dirty-tree pre-existing). Goal closed at **BLOCKED_EXTERNAL_ENTITLEMENT** ceiling. |
| **Key files** | `artifacts/developer-workflow/closure-report.json` |
| **Tests** | `imp.py providers campaign-readiness FTEP-V1-001 --json` (NOT_READY); `imp.py closure` (full failed on platform errors only) |
| **Related** | FTEP-V1 pathway B readiness goal; PR #19 |
| **Notes** | Owner: enable Moomoo CME ES quote; at pathway B record G-A6 CAMPAIGN_BOUND; merge PR when approved. |

## 2026-09-12 — FTEP post-freeze gap engine and probe overlay

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `providers`, `ui_api`, `artifacts/ftep-v1-activation` |
| **Summary** | Manifest-aware Wave A reconciliation (frozen WAVE-A-001/003; deferred 002/009/010), FTEP Moomoo probe overlay into capability snapshot, fresh probe receipts showing `US_FUTURES_QUOTE` not entitled, and UI-001 explore context REPLAY fix when persisted Paper sidecar is attached. |
| **Key files** | `coverage_gap_engine.py`, `capability_snapshot.py`, `ui_api/projections.py`, `paper_projections.py`, `news-data-inventory.json`, `provider-probe-moomoo-*-2026-09-12.json`, `test_coverage_gap_engine.py` |
| **Tests** | coverage+ui1 unittest 16 OK; forward activation+persistence 24 OK; `imp.py validate fast` pass; `validate changed` ui1/providers pass |
| **Related** | Freeze SHA `de420ea`; PR #19 draft |
| **Notes** | Max readiness **BLOCKED_EXTERNAL_ENTITLEMENT** until Moomoo CME ES quote entitlement; G-A6 binding remains operator step at pathway B. |

## 2026-09-12 — FTEP-V1-001 OD-11 pathway A freeze

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `intelligence/paper_forward_bridge`, `artifacts/ftep-v1-activation`, `artifacts/forward-test-campaigns/FTEP-V1-001` |
| **Summary** | Owner pathway **A**: bound internal-simulation Paper account, recorded OD-1–OD-11 in governed manifest state, froze `ACTIVATION_MANIFEST.json` (fingerprint + `FTCAMP-*` id), ran activation preflight READY with `IMP_PERSIST_STATE=1`, refreshed secret-free Moomoo probe (OpenD reachable; SDK missing). Stopped before first empirical lock or SIGNAL_ONLY session. |
| **Key files** | `artifacts/forward-test-campaigns/FTEP-V1-001/ACTIVATION_MANIFEST.json`, `artifacts/ftep-v1-activation/activation-freeze-receipt-2026-09-12.json`, `artifacts/ftep-v1-activation/activation-preflight-receipt-2026-09-12.json`, `docs/engineering/FORWARD_VALIDATION_READINESS_CHECKLIST.md` |
| **Tests** | `python tools/imp.py validate changed`; forward-test activation + coverage readiness tests |
| **Related** | [FTEP-V1_OWNER_DECISION_PACKET.md](./FTEP-V1_OWNER_DECISION_PACKET.md), [PAPER_FORWARD_TESTING_BRIDGE.md](../architecture/PAPER_FORWARD_TESTING_BRIDGE.md) |
| **Notes** | `campaign-readiness` remains NOT_READY on coverage gaps; calibration numerics still deferred. |

## 2026-09-12 — FTEP-V1 activation lead closure (pre-freeze)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `intelligence/paper_forward_bridge`, `providers`, `artifacts/ftep-v1-activation` |
| **Summary** | Closed CG-01/CG-02 in coverage gap engine and Wave A audit; reconciled OD-1–9 into proposed manifest fields without freeze; marked WAVE-A-004 owner-resolved; added secret-free probe/shakedown/paper-choice artifacts; Moomoo probe shows OpenD down (NEEDS_LOCAL_PRIVATE_PROBE). Stopped before OD-11 freeze and Paper bind. |
| **Key files** | `src/market_platform_foundation/providers/coverage_gap_engine.py`, `artifacts/wave-a-findings/ftep-campaign-audit.json`, `artifacts/wave-a-findings/news-data-inventory.json`, `artifacts/forward-test-campaigns/FTEP-V1-001/ACTIVATION_MANIFEST.json`, `artifacts/ftep-v1-activation/*`, `tests/providers/test_coverage_gap_engine.py` |
| **Tests** | `python tools/imp.py validate fast` (21 pass); `validate changed` (2116 pass); `unittest tests.providers.test_coverage_gap_engine` (6 pass); calibration discover (4 pass) |
| **Related** | [FTEP_V1_ACTIVATION_BLOCKER_REPORT.md](./FTEP_V1_ACTIVATION_BLOCKER_REPORT.md), [OPERATOR_PROBE_RUNBOOK.md](./OPERATOR_PROBE_RUNBOOK.md) |
| **Notes** | Campaign-readiness remains NOT_READY (manifest pending OD-11, probes, entitlements). Local uncommitted delta on branch `work/ftep-v1-activation`. |

## 2026-09-12 — FTEP v1 implementation goal closure audit

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `artifacts`, `docs` |
| **Summary** | Rigorous section-28 remap: all criteria A–Z `IMPLEMENTATION_COMPLETE`; goal audit flags `implementation_objective_complete` and `qualifying_activation_out_of_scope`; refreshed PR body (26/26 MET, `437cd1c` ingress). Qualifying activation remains owner/operator/external. |
| **Key files** | `artifacts/ftep-v1-activation-goal-audit.json`, `artifacts/ftep-v1-activation-PR-BODY.md`, `docs/engineering/FTEP_V1_ACTIVATION_BLOCKER_REPORT.md` |
| **Tests** | `python tools/imp.py validate fast` — 21 passed, 0 failures |
| **Related** | [FTEP_V1_ACTIVATION_BLOCKER_REPORT.md](./FTEP_V1_ACTIVATION_BLOCKER_REPORT.md) |
| **Notes** | UpdateGoal invoked only if parent Cursor goal tool available; no push/freeze/Live. |

## 2026-09-12 — Observational news ingress scaffold (FTEP-ACT-04)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `news`, `docs`, `artifacts` |
| **Summary** | Added gate-gated `observational_ingress.py` (master `IMP_OBSERVATIONAL_NEWS_INGRESS` + existing NewsAPI/Finnhub live gates) that fetches via `NewsAggregator` and normalizes through `aggregator_bridge`; documented known limitations in PAPER_FORWARD_TESTING_BRIDGE and operator probe cross-link. Criterion **O** → MET with implementation-readiness note; campaign connectivity still deferred. |
| **Key files** | `src/market_platform_foundation/news/observational_ingress.py`, `src/market_platform_foundation/news/config.py`, `tests/news/test_observational_ingress.py`, `docs/architecture/PAPER_FORWARD_TESTING_BRIDGE.md`, `docs/engineering/OPERATOR_PROBE_RUNBOOK.md`, `.env.example`, `artifacts/ftep-v1-activation-goal-audit.json` |
| **Tests** | `python -m unittest tests.news.test_observational_ingress -q` — 5 passed; `python tools/imp.py validate changed` — 1909 passed, 26 skipped |
| **Related** | [PAPER_FORWARD_TESTING_BRIDGE.md](../architecture/PAPER_FORWARD_TESTING_BRIDGE.md), manifest `deferred_until_evidence` FTEP-ACT-04 / FTEP-D038 |
| **Notes** | No forward-test auto-wire, Live, push, or freeze. DEFER-FTEP-ACT-04 gap narrowed to campaign bridge wiring only. |

## 2026-09-12 — PIT export, operator probe runbook, goal checkpoint

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `research`, `docs`, `artifacts` |
| **Summary** | Closed PIT-A-001 with `research/pit_export.py` and tests; added secret-free `OPERATOR_PROBE_RUNBOOK.md`; refreshed goal audit to 24 MET / 1 PARTIAL with `engineering_complete: true`; drafted PR body. Qualifying activation still blocked on owner/operator/external actions. |
| **Key files** | `src/market_platform_foundation/research/pit_export.py`, `tests/research/test_pit_export.py`, `docs/engineering/OPERATOR_PROBE_RUNBOOK.md`, `artifacts/ftep-v1-activation-goal-audit.json`, `artifacts/ftep-v1-activation-PR-BODY.md`, `docs/README.md`, `docs/engineering/PROVIDER_ACTIVATION_INCREMENT.md`, `docs/engineering/FTEP_V1_ACTIVATION_BLOCKER_REPORT.md` |
| **Tests** | `python -m unittest tests.research.test_pit_export -q` — 4 passed; `python tools/imp.py validate fast` — 21 passed |
| **Related** | `artifacts/ftep-v1-activation-goal-audit.json`, [FTEP_V1_ACTIVATION_BLOCKER_REPORT.md](./FTEP_V1_ACTIVATION_BLOCKER_REPORT.md) |
| **Notes** | Criterion **O** remains PARTIAL (DEFER-FTEP-ACT-04). No push/freeze/Live. |

## 2026-09-12 — FTEP v1 activation goal audit (section 28 A–Z)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `artifacts`, `docs` |
| **Summary** | Final engineering completion audit for `/goal` section 28 criteria A–Z: machine-readable `ftep-v1-activation-goal-audit.json` (22 MET, 4 PARTIAL), consolidated `FTEP_V1_ACTIVATION_BLOCKER_REPORT.md`, wave-b-closure cross-link; qualifying FTEP-V1-001 activation remains blocked. |
| **Key files** | `artifacts/ftep-v1-activation-goal-audit.json` (created), `docs/engineering/FTEP_V1_ACTIVATION_BLOCKER_REPORT.md` (created), `artifacts/wave-b-closure-report.json` (updated) |
| **Tests** | `python tools/imp.py validate fast` — 21 passed, 0 failures |
| **Related** | `artifacts/wave-b-closure-report.json`, `artifacts/wave-a-findings/reconciliation-gate.json` |
| **Notes** | No UpdateGoal complete; no push/freeze/Live. |

## 2026-09-12 — Wave B closure report sync (fac808f)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `artifacts` |
| **Summary** | Linked Wave B executive closure report to fac808f gap-fill deliverables: `ftep_gap_fill_commit` and authoritative path to ES/news stack selection artifact; corrected activation manifest evidence path casing. |
| **Key files** | `artifacts/wave-b-closure-report.json` |
| **Tests** | Not run (JSON metadata only) |
| **Related** | Commit `2e9c7ac`; prior `fac808f` FTEP gap-fill entry below |
| **Notes** | No push. |

## 2026-09-12 — FTEP gap fill: ES stack artifact, profile refs, imp providers

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `artifacts`, `intelligence`, `developer-tooling`, `docs` |
| **Summary** | Closed remaining safe Wave B / goal gaps without manifest freeze or Live: machine-readable ES/news provider stack selection (goal §11 A–D verdicts from Wave A facts), FTEP profile doc SHA reference module, `imp.py providers` router for capability-matrix and readiness diagnostics, PROGRAM_STATUS activation/blocker update, and committed FTEP validation receipts. |
| **Key files** | `artifacts/ftep-v1-001/es-news-provider-stack-selection.json`, `src/.../paper_forward_bridge/ftep_profile_refs.py`, `tools/imp.py`, `tests/intelligence/test_ftep_profile_refs.py`, `tests/validation/test_imp_cli.py`, `docs/platform/PROGRAM_STATUS.md`, `docs/engineering/PROVIDER_ACTIVATION_INCREMENT.md`, `artifacts/ftep-activation-test.json`, `artifacts/ftep-persistence-test.json` |
| **Tests** | `python tools/imp.py test focused tests.intelligence.test_ftep_profile_refs tests.validation.test_imp_cli`; `python tools/imp.py validate changed` |
| **Related** | [wave-b-closure-report.json](../../artifacts/wave-b-closure-report.json), [reconciliation-gate.json](../../artifacts/wave-a-findings/reconciliation-gate.json) |
| **Notes** | Goal disposition remains PARTIALLY_COMPLETE. Qualifying campaign still blocked on OWNER-OD-1–11, probes, calibration numerics. No push. |

## 2026-09-12 — Wave B post-closure catalog, FULL validate, requirement audit

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs`, `artifacts`, `validation` |
| **Summary** | Committed research-only provider candidate catalog and Wave A cross-links in provider/news docs; corrected decision-research gate `registry_root` to monorepo path. Ran `python tools/imp.py closure --skip-ui` (4606 passed, 49 skipped). Updated `wave-b-closure-report.json` with `requirement_audit` for manifest-freeze tooling, snapshot compare harness, and FTEP profile docs; refreshed reconciliation gate HEAD. |
| **Key files** | `docs/research/PROVIDER_CANDIDATE_CATALOG_2026-09-11.md`, `docs/providers/*.md`, `docs/architecture/NEWS_STRATEGY_EVALUATION.md`, `evidence/research/decision-research-gate-report.json`, `artifacts/wave-b-closure-report.json`, `artifacts/wave-a-findings/reconciliation-gate.json`, `artifacts/developer-workflow/closure-report.json` |
| **Tests** | `python tools/imp.py closure --skip-ui` — FULL passed (4606 tests, 49 skipped, 0 failures) |
| **Related** | `artifacts/wave-b-closure-report.json`, commits `1ab2073` (docs/catalog), `a456110` (FULL closure + requirement audit) |
| **Notes** | No push, no Live, no manifest freeze. Left local `g8`/`g13`/`g14` runtime perf drift and untracked `ftep-*-test.json` out of commits. Wave B disposition remains PARTIALLY_COMPLETE. |

## 2026-09-12 — Wave B closure docs and reconciliation artifacts

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `providers`, `docs`, `artifacts` |
| **Summary** | Closed Wave B increment documentation: added offline frozen provider snapshot compare harness, `PROVIDER_ACTIVATION_INCREMENT.md`, Notion sync payload, and executive `wave-b-closure-report.json`. Materialized Wave A lane JSON artifacts and updated `reconciliation-gate.json` to PARTIALLY_COMPLETE with external blockers (package 3 baseline `613a6b4`). |
| **Key files** | `src/market_platform_foundation/providers/snapshot_compare.py`, `tools/providers/snapshot_compare.py`, `tests/providers/test_provider_snapshot_compare.py`, `docs/engineering/PROVIDER_ACTIVATION_INCREMENT.md`, `artifacts/wave-a-findings/*.json`, `artifacts/wave-b-closure-report.json`, `artifacts/wave-b-notion-sync-payload.md` |
| **Tests** | `python -m unittest tests.providers.test_provider_snapshot_compare -q` (3 passed); `python tools/imp.py validate changed` (850 passed, 12 skipped) |
| **Related** | `artifacts/wave-a-findings/reconciliation-gate.json`, `docs/engineering/PROVIDER_READINESS.md` |
| **Notes** | No push, no Live, no manifest freeze. `validate domain providers` is not a manifest domain; providers suite ran under `validate changed`. |

## 2026-09-11 — Wave B calibration, comparator, and bridge fixes (PKG 3–5)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `paper`, `paper_forward_bridge`, `news`, `artifacts` |
| **Summary** | Added preregisterable paper simulator calibration thresholds (UNSET/BLOCKING), fixture-backed IMP vs comparator metrics, external comparator contract with explicit not-market-truth semantics, and Wave A futures suitability advisory hook. Fixed CG-01 manifest reload via stored campaign slug vs FTCAMP hash, wired sample-floor disposition on lock/evaluate (CG-02), and introduced NewsAggregator→NewsArticleEvent plus recorded-eval forward handoff helpers. Updated reconciliation-gate for PKG-DIAGNOSTICS-READINESS `373e47e` and marked packages 3–5 complete. |
| **Key files** | `src/market_platform_foundation/paper/calibration/**`, `src/market_platform_foundation/news/aggregator_bridge.py`, `src/market_platform_foundation/intelligence/paper_forward_bridge/{service,activation,repository,session_policy,recorded_eval_bridge}.py`, `manifests/paper/schemas/calibration_thresholds.schema.json`, `tests/{platform/test_simulator_calibration,news/test_aggregator_bridge,intelligence/test_forward_test_campaign_slug,intelligence/test_recorded_eval_bridge}.py`, `artifacts/wave-a-findings/reconciliation-gate.json`, `tools/validation_manifest.json` |
| **Tests** | `python -B -m unittest` on new tests (12 passed); `python tools/validate.py changed` (2977 passed, 29 skipped) |
| **Related** | `docs/architecture/PAPER_SIMULATOR_CALIBRATION_CONTRACT.md`, `artifacts/wave-a-findings/reconciliation-gate.json` |
| **Notes** | No manifest freeze, no live probes, FTEP-ACT-06 auto-bridge still deferred. |

## 2026-09-11 — Wave B gap engine and campaign readiness (PKG-DIAGNOSTICS-READINESS)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `providers`, `paper_forward_bridge`, `tools`, `artifacts` |
| **Summary** | Added deterministic coverage-gap resolver and FTEP-V1-001 ES/news requirement profile over the capability snapshot, plus fail-closed campaign readiness composing forward-test preflight and gap output. Extended `provider_readiness.py` with read-only `audit`, `gaps`, and `campaign-readiness` subcommands; emitted validated `capability-matrix-snapshot.json` and marked PKG-CAPABILITY-FOUNDATION complete in reconciliation-gate. |
| **Key files** | `src/market_platform_foundation/providers/capability_requirements.py`, `coverage_gap_engine.py`, `intelligence/paper_forward_bridge/campaign_readiness.py`, `tools/provider_readiness.py`, `tests/providers/test_coverage_gap_engine.py`, `artifacts/wave-a-findings/capability-matrix-snapshot.json`, `artifacts/wave-a-findings/reconciliation-gate.json`, `docs/engineering/PROVIDER_READINESS.md` |
| **Tests** | `python -m unittest tests.providers.test_coverage_gap_engine tests.providers.test_capability_matrix -q` (12 passed); `.venv` `python tools/validate.py changed` (2668 passed, 40 skipped) |
| **Related** | `artifacts/wave-a-findings/reconciliation-gate.json` PKG-DIAGNOSTICS-READINESS, PKG-CAPABILITY-FOUNDATION `60cce0e` |
| **Notes** | No live probes, no manifest freeze, no new provider integrations. Fixed `secrets_included` hygiene in snapshot redaction. |

## 2026-09-11 — Wave B capability matrix foundation (PKG-CAPABILITY-FOUNDATION)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `providers`, `manifests`, `tools`, `artifacts` |
| **Summary** | Added versioned capability-contract types (access states CATALOGED→BLOCKED, campaign roles, dimension semantics, PROMOTED evidence gate) and a deterministic snapshot builder over Wave A inventory/audit JSON plus value-blind readiness rows. Reconciliation index already marks provider-inventory and ibkr-tradier-alpaca lanes PRESENT at canonical paths. |
| **Key files** | `manifests/providers/schemas/capability_matrix_snapshot.schema.json` (created), `src/market_platform_foundation/providers/capability_contract.py` (created), `src/market_platform_foundation/providers/capability_snapshot.py` (created), `tools/providers/capability_matrix.py` (created), `tests/providers/test_capability_matrix.py` (created), `docs/engineering/PROVIDER_READINESS.md` (modified) |
| **Tests** | `python tools/imp.py test focused tests.providers.test_capability_matrix`; `python tools/imp.py validate changed` |
| **Related** | `artifacts/wave-a-findings/reconciliation-gate.json` PKG-CAPABILITY-FOUNDATION, `docs/architecture/MARKET_DATA_CAPABILITY_CONTRACT.md` |
| **Notes** | No live activation, no registry duplication, HTTP/UI matrix projection still deferred (DEFER-UNIFIED-UI-MATRIX). |

## 2026-09-11 — Wave A reconciliation index and parent gate synthesis

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `artifacts` |
| **Summary** | Completed Wave A reconciliation index for all present lane artifacts (including pit-infrastructure) plus absent provider-inventory and ibkr-tradier-alpaca lanes; added parent `reconciliation-gate.json` classifying requirements, minimum implementation packages with worktree boundaries, and ES/news stack verdict from verified Wave A facts only. No code or manifest changes. |
| **Key files** | `artifacts/wave-a-findings/reconciliation-index.json` (modified), `artifacts/wave-a-findings/reconciliation-gate.json` (created) |
| **Tests** | Not run (synthesis-only) |
| **Related** | `artifacts/wave-a-findings/*.json`, `docs/engineering/FTEP_ACTIVATION_GATES.md`, `docs/architecture/MARKET_DATA_CAPABILITY_CONTRACT.md`, `docs/architecture/PAPER_SIMULATOR_CALIBRATION_CONTRACT.md` |
| **Notes** | Qualifying FTEP campaign remains unauthorized; two Wave A lane JSON files still absent on disk. |

## 2026-09-11 — Wave A FTEP campaign audit artifact

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `artifacts`, `docs` |
| **Summary** | Persisted secret-free Wave A `ftep-campaign-audit.json` for FTEP-V1-001 (activation status, satisfied/unsatisfied gates, code/config gaps, OD-1…OD-11 as pending owner decisions, vocabulary, paths, test index). Minimal NEWS_STRATEGY_EVALUATION Paper-boundary correction: bridge exists; campaign not frozen; fixture vs forward paths. No manifest/owner-packet/checklist/empirical changes. |
| **Key files** | `artifacts/wave-a-findings/ftep-campaign-audit.json` (created), `docs/architecture/NEWS_STRATEGY_EVALUATION.md` (Paper execution boundary) |
| **Tests** | None (read-only audit follow-up) |
| **Related** | `artifacts/wave-a-findings/news-data-inventory.json`, `docs/engineering/FTEP-V1_OWNER_DECISION_PACKET.md` |
| **Notes** | Checklist FTEP row deferred (C5); recorded in audit JSON. |

## 2026-09-11 — Wave A UX hooks audit artifact

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs`, `artifacts`, `ui/api` (inventory only) |
| **Summary** | Persisted secret-free Wave A reconciliation JSON for parallel provider/capability type systems, existing React Query hooks vs HTTP endpoints, DISCOVER/NOW/Fusion surface wiring, eleven condensed gaps, and minimum future provider-governance hook set. No UI code changes. |
| **Key files** | `artifacts/wave-a-findings/ux-hooks-audit.json` (created), `docs/engineering/PROVIDER_READINESS.md` (one-line pointer) |
| **Tests** | None (read-only follow-up) |
| **Related** | Wave A goal reconciliation bundle |
| **Notes** | Backend/CLI vocabulary normalization should precede new UI matrix hooks. |

## 2026-09-11 — FTEP-V1 activation manifest runtime gaps (Agent B)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `intelligence`, `ui_api`, `docs`, `forward-test` |
| **Summary** | Completed Agent B minimal plan: `freeze_activation_manifest.py` CLI, protocol SHA-256 verification in manifest validation/preflight, decision provenance campaign binding, durable `forward_test_campaign_bindings` with first-lock timestamp, GET preflight API, and non-campaign empirical path guards. FTEP-V1-001 remains `PENDING_OWNER_DECISIONS`; no empirical evidence. |
| **Key files** | `tools/forward_test/freeze_activation_manifest.py`, `paper_forward_bridge/{protocol_ref,campaign_binding}.py`, `service.py`, `activation.py`, `preflight.py`, `sqlite_repository.py`, `ui_api/{forward_test_projections,server}.py`, forward-test tests, `PAPER_FORWARD_TESTING_BRIDGE.md` |
| **Tests** | `python tools/imp.py validate fast`; `python tools/imp.py test affected`; `python tools/check_docs_links.py` |
| **Related** | Agent B spec; [FTEP-V1_OWNER_DECISION_PACKET.md](FTEP-V1_OWNER_DECISION_PACKET.md) |
| **Notes** | Owner must sign OD-1 … OD-11 before freeze CLI succeeds on FTEP-V1-001. $0 incremental cost. Paper-only. |

## 2026-09-11 — FTEP-V1 P0 activation follow-ups (campaign binding + preflight API)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `intelligence`, `ui_api`, `docs`, `forward-test` |
| **Summary** | Added durable campaign binding (one ACTIVE campaign per account), protocol reference hash verification, GET preflight API, and fail-closed non-campaign session guards. No manifest freeze or empirical campaign start. |
| **Key files** | `paper_forward_bridge/{campaign_binding,protocol_ref}.py`, `service.py`, `preflight.py`, `activation.py`, `sqlite_repository.py`, `store.py`, `ui_api/{forward_test_projections,server}.py`, tests `test_forward_test_{activation,persistence,preflight_api,protocol_ref}.py`, `PAPER_FORWARD_TESTING_BRIDGE.md` |
| **Tests** | `python tools/imp.py validate fast`; `python tools/imp.py test affected`; `python tools/check_docs_links.py` |
| **Related** | Agent A/C P0 gaps; [FTEP-V1_OWNER_DECISION_PACKET.md](FTEP-V1_OWNER_DECISION_PACKET.md) |
| **Notes** | Owner must still sign OD-1 … OD-11 before manifest freeze. $0 incremental cost. Paper-only. |

## 2026-09-11 — FTEP-V1 owner decision packet (OD-1 … OD-11)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs`, `forward-test` |
| **Summary** | Expanded owner decision packet per user spec §16: 28 Agent A inventory rows consolidated into 11 grouped decisions (OD-1 … OD-11) with recommended defaults, precedent table for sample floors, and C3 ES/RTH conflict note. Updated activation manifest skeleton (`PENDING_OWNER_DECISIONS`), protocol ref with doc SHA-256, and FTEP activation status section. No FROZEN status or empirical claims. |
| **Key files** | `docs/engineering/FTEP-V1_OWNER_DECISION_PACKET.md`, `artifacts/forward-test-campaigns/FTEP-V1-001/ACTIVATION_MANIFEST.json`, `artifacts/forward-test-campaigns/FTEP-V1-001/PROTOCOL_REF.json`, `docs/engineering/FORWARD_TEST_EXPERIMENTAL_PROTOCOL_V1.md`, `docs/engineering/WORK_LOG.md` |
| **Tests** | None (docs/artifacts only) |
| **Related** | Agent A audits `c4f6ca28`, `81265595`; [FTEP-V1_OWNER_DECISION_PACKET.md](FTEP-V1_OWNER_DECISION_PACKET.md) |
| **Notes** | Owner must sign OD-1 … OD-11 before manifest freeze. $0 incremental cost; Paper-only. |

## 2026-09-11 — FTEP-V1 activation runtime gates

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `intelligence`, `docs`, `forward-test` |
| **Summary** | Implemented activation manifest load/validate/fingerprint, deterministic preflight, session manifest binding, cohort/strategy/universe validation on decisions, `evidence_class` without auto-promotion, observation `source_time_ns` guard, and schema v3–v4 persistence columns. Commit `58864aa` on `work/ftep-v1-activation`. |
| **Key files** | `paper_forward_bridge/activation.py`, `preflight.py`, `service.py`, `types.py`, `temporal.py`, `repository.py`, `tests/intelligence/test_forward_test_activation.py`, `docs/architecture/PAPER_FORWARD_TESTING_BRIDGE.md` |
| **Tests** | `python tools/imp.py test affected` — 1832 passed, 26 skipped; forward-test 30/30 |
| **Related** | [FTEP-V1_OWNER_DECISION_PACKET.md](FTEP-V1_OWNER_DECISION_PACKET.md), [FORWARD_TEST_EXPERIMENTAL_PROTOCOL_V1.md](FORWARD_TEST_EXPERIMENTAL_PROTOCOL_V1.md) |
| **Notes** | Manifest `PENDING_OWNER_DECISIONS` until owner signs OD-01/ACT-01/ACT-03. $0 incremental cost. Not pushed. |

## 2026-09-11 — FTEP-V1 owner decision packet and activation manifest skeleton

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs`, `forward-test` |
| **Summary** | Created FTEP-V1 owner decision packet and `FTEP-V1-001` activation manifest skeleton per Agent A re-run audit (`c4f6ca28`). Manifest is `PENDING_OWNER_DECISIONS` with 3 minimal-path owner choices (OD-01, ACT-01, ACT-03) and 17 pre-resolved safe/deterministic fields; no FROZEN status or empirical claims. |
| **Key files** | `docs/engineering/FTEP-V1_OWNER_DECISION_PACKET.md` (created), `artifacts/forward-test-campaigns/FTEP-V1-001/ACTIVATION_MANIFEST.json` (created), `artifacts/forward-test-campaigns/FTEP-V1-001/PROTOCOL_REF.json` (created), `docs/engineering/FORWARD_TEST_EXPERIMENTAL_PROTOCOL_V1.md` (header), `docs/engineering/WORK_LOG.md` |
| **Tests** | None (docs/artifacts only) |
| **Related** | [FTEP-V1_OWNER_DECISION_PACKET.md](FTEP-V1_OWNER_DECISION_PACKET.md), Agent A audit `c4f6ca28`, [FORWARD_TEST_EXPERIMENTAL_PROTOCOL_V1.md](FORWARD_TEST_EXPERIMENTAL_PROTOCOL_V1.md) |
| **Notes** | Superseded by activation runtime gates entry above for implementation status. |

## 2026-09-10 — PD-09 verifier persistence follow-up

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `intelligence`, `docs` |
| **Summary** | Addressed independent PD-09 verifier follow-up: extracted shared `assert_observations_append_only` helper for SQLite and in-memory stores, added restart persistence tests for observation tamper rejection and durable evaluation-claim blocking, and updated closure validation counts. |
| **Key files** | `paper_forward_bridge/repository.py`, `paper_forward_bridge/store.py`, `paper_forward_bridge/sqlite_repository.py`, `tests/intelligence/test_forward_test_persistence.py`, `docs/audits/paper-forward-testing-bridge/CLOSURE.json` |
| **Tests** | `python tools/imp.py test focused` — 11/11 persistence tests passed |
| **Related** | [paper-forward-testing-bridge CLOSURE](../audits/paper-forward-testing-bridge/CLOSURE.json), verifier `5cebba20` |
| **Notes** | Artifact JSON under `artifacts/` intentionally excluded from commit. |

## 2026-09-11 — FTEP-V1 forward-test experimental protocol freeze

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs`, `forward-test` |
| **Summary** | Froze the first Paper forward-test experimental protocol (`FTEP-V1/0.1.0-PREREG`) before any empirical evidence run. Document is explicitly PLANNED / PRE-REGISTERED / NOT YET EMPIRICAL EVIDENCE; defines hypothesis, baseline/AI arms, universe/session/cadence rules, Paper execution semantics, metrics, leakage controls, disposition criteria (KEEP/REJECT/REPEAT/MODIFY/BLOCKED), and evidence-class gates. Unresolved choices marked OPEN DECISION — no results invented. |
| **Key files** | `docs/engineering/FORWARD_TEST_EXPERIMENTAL_PROTOCOL_V1.md` (created), `docs/engineering/WORK_LOG.md` |
| **Tests** | `tools/check_docs_links.py`: 172 governance markdown files checked, pass |
| **Related** | [FORWARD_TEST_EXPERIMENTAL_PROTOCOL_V1.md](FORWARD_TEST_EXPERIMENTAL_PROTOCOL_V1.md), [PAPER_FORWARD_TESTING_BRIDGE.md](../architecture/PAPER_FORWARD_TESTING_BRIDGE.md), coordinator goal §14-A (Next A) |
| **Notes** | Next: resolve OPEN DECISIONs in activation manifest; campaign artifacts path planned under `artifacts/forward-test-campaigns/`. EVIDENCE-01B auto-bridge still unwired. |

## 2026-09-10 — PD-09 forward-test durable persistence

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `intelligence`, `local_state`, `docs` |
| **Summary** | Added account-scoped durable forward-test persistence via local SQLite (`local_state` schema v2): `ForwardTestRepository` protocol with in-memory and SQLite implementations, restart recovery for sessions/decisions/observations/evaluations, locked-decision immutability, append-only observations, and durable paper-submission/evaluation claims. Wired through `forward_test_projections` when `IMP_PERSIST_STATE=1`. |
| **Key files** | `paper_forward_bridge/repository.py`, `paper_forward_bridge/sqlite_repository.py`, `local_state/schema.py`, `local_state/migrations.py`, `local_state/startup.py`, `ui_api/forward_test_projections.py`, `tests/intelligence/test_forward_test_persistence.py`, `docs/architecture/PAPER_FORWARD_TESTING_BRIDGE.md` |
| **Tests** | Persistence 9/9 passed; affected 1812 passed, 28 skipped (intelligence suite included) |
| **Related** | [PAPER_FORWARD_TESTING_BRIDGE.md](../architecture/PAPER_FORWARD_TESTING_BRIDGE.md), [paper-forward-testing-bridge audit](../audits/paper-forward-testing-bridge/README.md) |
| **Notes** | Local SQLite only (no MongoDB). Route-policy UI mutation wiring deferred. Branch rebased onto `origin/main` @ `0ac5c03`. |

## 2026-09-10 — Governed Paper forward-testing bridge

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `intelligence`, `paper`, `ui`, `docs` |
| **Summary** | Implemented professor-directed Paper forward-testing bridge on reconciled P2+P7 base: forward-test sessions/decisions with lifecycle and anti-look-ahead guards, governed Paper handoff via `forward_test_decision` snapshots, account-scoped API, Paper Workspace UI panel, tests, architecture doc, and evidence package. |
| **Key files** | `src/market_platform_foundation/intelligence/paper_forward_bridge/**`, `ui_api/forward_test_projections.py`, `paper/decision_source.py`, `ui/.../PaperForwardTestPanel.tsx`, `tests/intelligence/test_paper_forward_bridge.py`, `docs/architecture/PAPER_FORWARD_TESTING_BRIDGE.md` |
| **Tests** | Forward-test 11 passed; UI model 2 passed; FAST 21/0/0; changed 2915/32/0; FULL 4539/49/0; closure docs/typecheck/build green after TS fixes |
| **Related** | [PAPER_FORWARD_TESTING_BRIDGE.md](../architecture/PAPER_FORWARD_TESTING_BRIDGE.md), [evidence package](../audits/paper-forward-testing-bridge/README.md) |
| **Notes** | Remote `main` not pushed/merged. Notion SYNC_PAYLOAD_READY. In-memory store scope; EVIDENCE-01B auto-bridge deferred. |

## 2026-09-10 — Performance Engineering P7 continuous budgets & telemetry

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `developer-tooling`, `validation` |
| **Summary** | Established P7 observe-only performance budgets with canonical manifest, deterministic classification, validation receipt telemetry, `imp env` performance summary, CI telemetry summary, and P2 scheduler integration. Re-measured FAST/domain/FULL local baselines with repeated-run evidence for affordable paths. |
| **Key files** | `manifests/performance_budget.json`, `tools/performance_budget.py`, `tools/performance_telemetry.py`, `tools/perf_baseline_measure.py`, `tools/validate.py`, `tools/imp.py`, `.github/workflows/imp-python.yml`, `tests/validation/test_performance_budget.py`, `docs/audits/performance-engineering-p7/` |
| **Tests** | P7 contract 30 passed; P2 scheduler 13 passed; repository closure passed; FAST 21 passed; FULL 4522 passed (48 skipped) |
| **Related** | `docs/audits/performance-engineering-p7/P7_CLOSURE.json`, P2 `docs/audits/performance-engineering-p2/` |
| **Notes** | Gating remains OBSERVE_ONLY; CI baselines REMOTE_UNMEASURED; changed-validation baseline inherited from P2 at LOW confidence |

## 2026-09-10 — Source-control preservation and P3 lane isolation

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `source-control`, `developer-operating-system` |
| **Summary** | Preserved validated professor-directed IMP work and P0 audit/control-plane changes in two logical local commits on `work/professor-paper-forward-testing`, fixed checkpoint `checkpoint/post-g15-professor-p0-2026-09-09` at `cd145fc`, and created isolated performance lane `perf/p3-validation-selector` in sibling worktree `market-trading-platform-perf-p3`. Remote `main` unchanged; no push/merge/PR. |
| **Key files** | Local branches: `work/professor-paper-forward-testing`, `checkpoint/post-g15-professor-p0-2026-09-09`, `perf/p3-validation-selector`; worktree `../market-trading-platform-perf-p3`; commits `48d64f8`, `cd145fc` |
| **Tests** | Pre-commit: FAST 21 passed; news 26 passed; intelligence inference 24 passed; strategy evaluation 19 passed. FULL 4456/48/0 reused (exact functional equivalence — no post-validation code edits). |
| **Related** | [DEVELOPER_OPERATING_SYSTEM.md](DEVELOPER_OPERATING_SYSTEM.md), [P0 forensic audit](../audits/performance-engineering-p0/P0_FORENSIC_AUDIT_2026-09-09.md) |
| **Notes** | NOTION_SYNC_BLOCKED. P3 not started. Primary next product increment remains governed Paper forward-testing bridge. |

## 2026-09-09 — Performance Engineering P0 forensic audit

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs`, `developer-operating-system`, `performance` |
| **Summary** | P0 measurement-first audit of IMP developer OS, validation tiers, selector behavior, and assurance map. Delivered baseline JSON, optimization ledger, invariant/parallel maps, Notion lifecycle spec, and forensic report. Fixed stale `core_checkpoint_required` terminology and authoritative-docs link. No broad optimization; professor-directed dirty tree preserved. |
| **Key files** | `docs/audits/performance-engineering-p0/*`, `docs/engineering/DEVELOPER_OPERATING_SYSTEM.md`, `.cursor/rules/developer-workflow.mdc`, `.cursor/rules/authoritative-docs.mdc`, `.cursor/skills/imp-testing/SKILL.md`, `.cursor/agents/testing.md`, `artifacts/p0-performance-baseline.json` |
| **Tests** | `validate fast`: 21 passed, 3.447s; `benchmark.py --include-fast`: pass; focused news 0.39s; intelligence news 1.23s; vitest 71.9s |
| **Related** | [P0 forensic audit](../audits/performance-engineering-p0/P0_FORENSIC_AUDIT_2026-09-09.md), [NOTION_DEVELOPMENT_LIFECYCLE.md](../audits/performance-engineering-p0/NOTION_DEVELOPMENT_LIFECYCLE.md) |
| **Notes** | NOTION_CONTEXT_BLOCKED / NOTION_SYNC_BLOCKED. Next performance increment: P3 selector + artifacts evidence classification (BL-0801). Primary lane remains Paper forward-testing bridge. |

## 2026-09-09 — News strategy evaluation laboratory (professor-directed increment 3)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend`, `docs`, `tests` |
| **Summary** | Implemented event-time-safe news intelligence strategy evaluation and Paper-shadow laboratory: feature snapshots, baseline vs AI-enhanced policies, realized outcome measurement, calibration metrics, deterministic replay, and non-executable shadow records. Initial lane ES futures with multi-asset fixture proof. No execution authority. |
| **Key files** | `src/market_platform_foundation/intelligence/news_strategy_evaluation/*`, `tests/intelligence/test_news_strategy_evaluation.py`, `tests/fixtures/news_strategy_evaluation/evaluation_replay_pack.json`, `tools/research/evaluate_news_intelligence.py`, `docs/architecture/NEWS_STRATEGY_EVALUATION.md`, `docs/architecture/adr/0012-news-strategy-evaluation-laboratory.md` |
| **Tests** | `unittest tests.intelligence.test_news_strategy_evaluation` 19 passed; news+intelligence foundation 45 passed |
| **Related** | [NEWS_STRATEGY_EVALUATION.md](../architecture/NEWS_STRATEGY_EVALUATION.md), [ADR-0012](../architecture/adr/0012-news-strategy-evaluation-laboratory.md) |
| **Notes** | Empirical path SOFTWARE_FIXTURE_ONLY; MES deferred; Claude live validation still blocked; Paper forward bridge deferred |

## 2026-09-09 — Canonical news AI intelligence boundary (post-G15 increment 2)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend/intelligence/inference`, `docs` |
| **Summary** | Implemented analysis-only AI intelligence layer over curated deterministic news: `IntelligenceInputPacket`, governed `PromptRegistry`, provider-neutral `InferenceProvider` (`FixtureInferenceProvider`, `AnthropicInferenceProvider`), structured `IntelligenceResult`, replay-safe `InferenceRecord`, `NewsIntelligenceAnalyzer`, and `IntelligenceReplayHarness`. Zero broker/Paper/Live execution authority. |
| **Key files** | `src/market_platform_foundation/intelligence/inference/*`; `tests/intelligence/test_news_inference.py`; `docs/architecture/NEWS_AI_INTELLIGENCE.md`, `adr/0011-news-ai-intelligence-boundary.md` |
| **Tests** | `tests/intelligence/test_news_inference.py` — 24 passed; `tests/news` — 26 passed |
| **Related** | ADR-0011, [NEWS_AI_INTELLIGENCE.md](../architecture/NEWS_AI_INTELLIGENCE.md), ADR-0010 |
| **Notes** | INT-012 → PARTIALLY_INTEGRATED. `CLAUDE_LIVE_VALIDATION_NOT_RUN_EXTERNAL_CREDENTIAL_BLOCKER`. Durable inference persistence deferred. Next: Paper strategy evaluation over recorded intelligence. |

## 2026-09-09 — Canonical news/event deterministic foundation (post-CCN audit)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend/news`, `docs` |
| **Summary** | Extended `market_platform_foundation/news/` with canonical `NewsArticleEvent` contract, separate publication/retrieval timestamps, source-trust catalog, catalyst registry, composable filter chain (recency → source → catalyst), deduplication, event-time-safe replay harness, fixture provider, and read-only `NewsIntelligenceService`. No AI or broker execution. Converges with existing aggregator rather than duplicating architecture. |
| **Key files** | `src/market_platform_foundation/news/contracts.py`, `timestamps.py`, `sources.py`, `catalysts.py`, `dedupe.py`, `normalize.py`, `filters/*`, `pipeline.py`, `replay.py`, `observability.py`, `fixture_provider.py`, `service.py`; `tests/news/test_news_foundation.py`, `test_news_event_time.py`; `tests/fixtures/news/canonical_replay_pack.json`; `docs/architecture/NEWS_EVENT_FOUNDATION.md`, `adr/0010-news-catalyst-deterministic-foundation.md` |
| **Tests** | `python -m unittest discover -s tests/news -q` — 26 passed |
| **Related** | [CCN_FORENSIC_AUDIT_2026-09-09.md](../audits/post-g15-professor-directed/CCN_FORENSIC_AUDIT_2026-09-09.md), ADR-0010 |
| **Notes** | INT-012 remains NOT_YET_INTEGRATED. Live wire providers (PR Newswire, Benzinga, etc.) deferred. Next increment: AI intelligence boundary over curated output. |

## 2026-09-09 — Post-G15 professor-directed CCN forensic audit

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs`, `research`, `donors` |
| **Summary** | Completed forensic audit of authorized Future donor `Claude Code News/` (SRC-006): full artifact inventory, architecture reconstruction, event-time and AI analysis, performance evidence classification, security review, IMP comparison, reuse matrix, and proposed canonical integration architecture. Donor tree left unchanged (gitignored). No IMP runtime code copied. |
| **Key files** | `docs/audits/post-g15-professor-directed/README.md`, `docs/audits/post-g15-professor-directed/CCN_FORENSIC_AUDIT_2026-09-09.md`, `docs/audits/post-g15-professor-directed/CCN_ARTIFACT_INVENTORY.json` |
| **Tests** | `git rev-parse HEAD` (baseline match); `node --check` on 4 donor entrypoints (pass). IMP suite not run — documentation-only increment. |
| **Related** | [CCN forensic audit](../audits/post-g15-professor-directed/CCN_FORENSIC_AUDIT_2026-09-09.md); SRC-006 in [01-source-registry](../audits/imp-reconciliation/01-source-registry.md) |
| **Notes** | Runtime logs absent locally; README P&L claims PARTIALLY VERIFIED only. Next increment: canonical deterministic news/event ingestion foundation (Paper-only). |

## 2026-09-09 — G15 product acceptance (browser E2E, validation perf, archive-first deprecation)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `e2e`, `validation`, `ui_api`, `docs` |
| **Summary** | Playwright product-acceptance harness (equity/derivative Paper, isolation, routing, live safety); `validate e2e` gate; route-ref resolver for product APIs; dead-route census + deprecation headers; FULL **4392/48/0/0**. |
| **Key files** | `tools/e2e/harness.py`, `e2e/tests/*.spec.ts`, `tools/validate.py`, `ui_api/instrument_selector.py`, `artifacts/g15-validation-performance.json`, `docs/audits/imp-reconciliation/14m-g15-current-state-matrix.md` |

## 2026-09-09 — G14 Wave 7 product convergence (selector, query keys, Options/Futures surfaces)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui/api`, `ui/options`, `ui/futures`, `ui_api`, `cross_lane`, `docs/audits` |
| **Summary** | Delivered canonical multi-asset instrument selector (`/instruments/search`), deterministic route codec, G14 Options/Futures product API surfaces backed by G12 runtime + G13 CanonicalPortfolio truth, frontend query-key factory with isolation tests, and product UI layers on Options/Futures workspace routes. Legacy whale research lanes preserved; Live execution remains blocked. |
| **Key files** | `ui_api/instrument_selector.py`, `ui_api/g14_product_projections.py`, `ui_api/instrument_route_codec.py`, `ui/src/api/queryKeyFactory.ts`, `ui/src/components/instrument-selector/CanonicalInstrumentSelector.tsx`, `ui/src/components/options/OptionsProductSurface.tsx`, `ui/src/components/futures/FuturesProductSurface.tsx`, `tests/cross_lane/test_g14_product_convergence.py`, `docs/audits/imp-reconciliation/14l-g14-current-state-matrix.md` |
| **Tests** | Backend G14: 11/11; frontend G14 focused: 16/16; FAST 21/0/0/0; CHANGED 3856/48/0/0; FULL **4391**/48/0/0 (+11); UI typecheck pass; build pass (202.87 KiB gzip) |
| **Related** | G13 baseline; `14l-g14-current-state-matrix.md`; RC-010/RC-011 partial closure |
| **Notes** | Legacy `queryKeys.workspace*` symbol keys retained for equity lanes; G14 product keys use factory. Selector mounted on Options/Futures modules (lazy). Full audit doc sweep deferred to follow-up commit. |

## 2026-09-09 — G14 closure validation pass (query-key wiring, preview panel, audit sweep)

| Field | Value |
|-------|-------|
| **Status** | `complete_with_explicit_exception` |
| **Area** | `ui/api`, `ui/options`, `ui/futures`, `ui/shared`, `docs/audits` |
| **Summary** | Second pass: wired compact G14 query keys in hooks + invalidation; integrated `DerivativePaperPreviewPanel` on product surfaces; restored global lazy selector on `InstrumentSelectionEmpty`; route encoding fixes; audit doc sweep (00/12/15/16/18). |
| **Key files** | `ui/src/api/hooks.ts`, `ui/src/api/canonicalQueryKey.ts`, `ui/src/components/paper-derivative/DerivativePaperPreviewPanel.tsx`, `ui/src/components/shared/InstrumentSelectionEmpty.tsx`, `docs/audits/imp-reconciliation/{00-program-state,12-master-backlog,15-validation-evidence,16-root-cause-register,18-completion-scorecard}.md` |
| **Tests** | Backend G14 **11/11**; CHANGED **3856/48/0/0**; FULL **4391/48/0/0**; UI typecheck pass; build **202.91 KiB gzip** |
| **Related** | `14l-g14-current-state-matrix.md`; RC-011 partial (product keys only) |
| **Notes** | Workspace lane query keys remain legacy for bundle/equity parity. Live execution blocked. |

## 2026-09-09 — G14 final closure (FULL green, route codec sweep)

| Field | Value |
|-------|-------|
| **Status** | `complete_with_explicit_exception` |
| **Area** | `ui/discover`, `ui/live`, `ui/paper-now`, `ui/workspace-module-shared`, `docs/platform` |
| **Summary** | FULL **4391/48/0/0** confirmed; extended `workspacePathForInstrument` to primary shell navigation (Discover, Live, Paper Now, lane shells); classified G14 **COMPLETE_WITH_EXPLICIT_EXCEPTION** (legacy lane query keys + whale research lanes retained). |
| **Key files** | `DiscoverObservability.tsx`, `LiveSymbolLookup.tsx`, `LiveObservationalPanel.tsx`, `PaperNowPage.tsx`, `WorkspaceModuleModeShell.tsx`, `LaneModeContextPanel.tsx`, `buildLaneModeContent.ts`, `PROGRAM_STATUS.md`, `00-program-state.md` |
| **Tests** | Backend G14 **11/11**; frontend G14 **24/24**; UI typecheck pass; build **202.92 KiB gzip** |
| **Related** | [14l-g14-current-state-matrix](../audits/imp-reconciliation/14l-g14-current-state-matrix.md) |
| **Notes** | RC-011 lane-key migration deferred (BL-0701). Live execution blocked. |

## 2026-09-09 — G13 closure validation (FULL green, Wave 7 readiness)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `paper`, `trading_correctness`, `docs/audits` |
| **Summary** | Closure pass: verified 25 G13 acceptance invariants against implementation; reran FAST/CHANGED/FULL and affected domain suites; reconciled test delta +25 (4355→4380); updated audit closure docs; classified margin authority (`MARGIN_INFRASTRUCTURE_COMPLETE` YES, `BROKER_MARGIN_MODEL_AVAILABLE` NO/LIMITED); decided **WAVE_7_READY**. |
| **Key files** | `docs/audits/imp-reconciliation/{00-program-state,14k-g13-current-state-matrix,15-validation-evidence}.md`, `docs/platform/PROGRAM_STATUS.md` |
| **Tests** | G13 **25/0/0/0**; equity parity **7/0/0/0**; preview binding **10/0/0/0**; portfolio **136/0/0/0**; trading_correctness **147/0/0/0**; futures **65/0/0/0**; xa01 **72/0/0/0**; platform **474/2/0/0**; options domain **783/11/0/0**; FAST **21/0/0/0**; CHANGED **3845/48/0/0**; FULL **4380/48/0/0** |
| **Related** | [14k-g13-current-state-matrix](../audits/imp-reconciliation/14k-g13-current-state-matrix.md), [15-validation-evidence](../audits/imp-reconciliation/15-validation-evidence.md) G13 section |
| **Notes** | G14 not started. Performance artifact: `artifacts/g13-runtime-performance.json`. ES margin via `FixtureFuturesMarginProvider` — not live broker margin. |

## 2026-09-09 — G13 closure increment (futures lifecycle, margin preview binding)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `paper`, `trading_correctness`, `docs/audits` |
| **Summary** | Closed remaining G13 gaps: futures partial/replace/cancel lifecycle proven; `margin_facts_revision` bound into preview verify (`PREVIEW_MARGIN_STALE`); futures replace recheck uses margin facts not full notional; settlement-currency fail-closed tests for options/futures. |
| **Key files** | `paper/preview.py`, `paper/execution.py`, `tests/trading_correctness/test_g13_paper_derivatives.py`, `docs/audits/imp-reconciliation/14k-g13-current-state-matrix.md` |
| **Tests** | G13 focused **23/0/0/0**; CHANGED **3843/48/0/0**; FULL **4378/48/0/0** |
| **Related** | [14k-g13-current-state-matrix](../audits/imp-reconciliation/14k-g13-current-state-matrix.md) |
| **Notes** | UI `paper_projections` margin_facts wiring and performance evidence still deferred. Wave 7 NOT_READY. |

## 2026-09-09 — G13 canonical multi-asset Paper execution (options/futures)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `paper`, `portfolio`, `risk`, `trading_correctness`, `docs/audits` |
| **Summary** | Wired option and futures Paper fills through one canonical path (`portfolio/paper_fill.py` → `CanonicalPortfolio`) with explicit `MarginRequirementFacts` admission for futures (fail-closed without facts; no invented brokerage formulas). Option premium uses contracts×price×multiplier; futures debit margin not full notional. Legacy equity Paper ledger parity preserved; `options_ledger` remains non-authoritative. |
| **Key files** | `risk/margin_facts.py`, `portfolio/paper_fill.py`, `paper/ledger.py`, `paper/execution.py`, `risk/pretrade.py`, `tests/trading_correctness/test_g13_paper_derivatives.py`, `docs/audits/imp-reconciliation/14k-g13-current-state-matrix.md` |
| **Tests** | FAST 21/0/0/0; G13 focused 16/0/0/0; FINAL FULL **4371/48/0/0** (+16 from 4355); ibkr canary safety fixed (probe_loopback mock) |
| **Related** | [14k-g13-current-state-matrix](../audits/imp-reconciliation/14k-g13-current-state-matrix.md) |
| **Notes** | MARGIN_INFRASTRUCTURE_COMPLETE; BROKER_MARGIN_MODEL_UNAVAILABLE. Option partial/replace/cancel proven; futures replace/cancel deferred. Crypto secondary. Wave 7 NOT_READY. |

## 2026-09-09 — G12 post-IBKR multi-asset runtime completion

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `cross_lane`, `providers`, `docs/audits` |
| **Summary** | Closed G12 by isolating IBKR L2/TRADES entitlement limits from software backlog, correcting L1 delayed-vs-realtime capability wording, and adding one canonical multi-asset runtime projection path (`multi_asset_runtime.py`) over XA-01 identity, G7 observational lanes, G2/G4 valuation, and G3 fail-closed risk probes. Futures and options are first-priority runtime domains; crypto/bond/commodity semantics preserved. |
| **Key files** | `src/market_platform_foundation/cross_lane/runtime_status.py`, `cross_lane/multi_asset_runtime.py`, `tests/cross_lane/test_g12_multi_asset_runtime.py`, `tools/ibkr/canary.py`, `docs/audits/imp-reconciliation/14j-g12-current-state-matrix.md`, `g11-live-capability-evidence.json` |
| **Tests** | FAST 21/0/0/0; focused G12 25/0/0/0; CHANGED 3820/48/0/0; FULL **4355/48/0/0** (+25 from 4330) |
| **Related** | [14j-g12-current-state-matrix](../audits/imp-reconciliation/14j-g12-current-state-matrix.md), G11.1 live evidence |
| **Notes** | Frontend not touched; futures margin, crypto observational lane, bond execution, and Wave 7 instrument selector remain deferred. L2/TRADES are external entitlement limits only. |

## 2026-09-09 — G11.1 IBKR live Gateway verification and false-blocker correction

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `tools/ibkr`, `providers/live_evidence`, audits |
| **Summary** | Ran bounded read-only live canary against open loopback Gateway (`127.0.0.1:4001`); corrected conflation of `IMP_IBKR_LIVE` unset with `ENVIRONMENT_UNAVAILABLE`; added per-capability live evidence application to `RuntimeCapabilityRegistry`; verified contract/historical/account/L1 live; L2/TRADES `LIVE_CONNECTED_NOT_ENTITLED` (IBKR 10092/10189). Execution boundary unchanged. |
| **Key files** | `tools/ibkr/canary.py`, `src/.../providers/live_evidence.py`, `src/.../providers/runtime_capability.py`, `tests/providers/test_g111_live_evidence.py`, `tests/ibkr/test_g11_canary_safety.py`, `tests/ibkr/test_safety.py`, `docs/audits/imp-reconciliation/14i-g11-live-verification-matrix.md`, `g11-live-*-evidence.json` |
| **Tests** | G11.1 focused 7/0/0; starting FULL **4326/48/0/0**; final FULL **4330/48/0/0** (+4); CHANGED **3791/48/0/0** |
| **Related** | [14i-g11-live-verification-matrix.md](../audits/imp-reconciliation/14i-g11-live-verification-matrix.md) |
| **Notes** | Root cause: `SAFETY_GATE_STATE_MISCLASSIFIED_AS_PROVIDER_ENVIRONMENT_STATE`. Requires `ib_insync` in venv for live canary. L2 depth + tick-by-tick need IBKR market-data subscriptions. |

## 2026-09-09 — G11 IBKR read-only query surface convergence + verification harness

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `providers/ibkr_observational`, `market_data`, `tools/ibkr`, `tests`, `docs/audits` |
| **Summary** | G11 converged IBKR read-only query surfaces through injected outer provider boundary: `IbkrReadOnlyQueryProvider` protocol + `IbkrObservationalQueryService` (contract/secdef, historical bars, read-only account observation) with XA-01 admission, capability gating, capture/replay, and composition attach via `ibkr_query_bridge.py`. Outer `tools/ibkr/query_provider.py` adapts REST/TWS clients; registration via `runtime_bootstrap.py` only (G8 boundary fix removing foundation import from query_provider). Bounded live canary harness (`tools/ibkr/canary.py`) fail-closed. G10 depth TTL + G9 CVD preserved. LIVE_PROVIDER_UNVERIFIED retained. |
| **Key files** | `src/.../providers/ibkr_observational/query_provider.py`; `market_data/ibkr_query_bridge.py`, `runtime_composition.py`, `live_runtime.py`; `tools/ibkr/{query_provider,canary,runtime_bootstrap}.py`; `tests/**/test_g11_*.py`; `docs/audits/imp-reconciliation/14h-g11-current-state-matrix.md` |
| **Tests** | Starting FAST 21/0/0/0; starting FULL 4326/48/2/0 (boundary violation); focused G11 46/0/0/0; final FAST 21/0/0/0; CHANGED 3791/48/0/0; FULL 4326/48/0/0 |
| **Related** | G10 baseline; BL-0301 IMPLEMENTATION_COMPLETE/LIVE_VERIFICATION_PENDING; BL-0305 IMPLEMENTATION_COMPLETE/BLOCKED_BY_LIVE_EVIDENCE; `14h-g11-current-state-matrix.md` |
| **Notes** | No formula ledger bump. No execution enablement. Provider account facts remain READ_ONLY_OBSERVATIONAL. Live canary not executed in this environment. |

## 2026-09-08 — G10 IBKR provider convergence + depth TTL admission

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `providers/ibkr_observational`, `market_data`, `tests`, `docs/audits` |
| **Summary** | G10 converged canonical depth runtime admissibility (BL-0303) via `depth_admission.py`, wired DEPTH TTL into live admission and observational lanes (stale depth cannot yield authoritative OFI/book features), added read-only historical bar and account observation normalization contracts, registered IBKR_HISTORICAL_BARS/ACCOUNT_READ capabilities, hardened adapter/composition shutdown (idempotent, no reconnect after shutdown), and added 30 focused G10 tests. Live provider remains `LIVE_PROVIDER_UNVERIFIED`. |
| **Key files** | `src/.../market_data/depth_admission.py`; `live_admission.py`, `live_config.py`, `observational_lanes.py`, `observational_state.py`, `runtime_composition.py`; `providers/ibkr_observational/{historical_bars,account_observation,capability,adapter,diagnostics}.py`; `providers/runtime_capability.py`; `tests/**/test_g10_*.py`; `docs/audits/imp-reconciliation/14g-g10-current-state-matrix.md` |
| **Tests** | Starting FULL 4250/48/0/0; G10 focused 30/0/0/0; FAST 21/0/0/0 post-change |
| **Related** | G9 baseline; BL-0301/0303/0304/0305; `14g-g10-current-state-matrix.md` |
| **Notes** | BL-0301 still PARTIAL (REST historical/account fetch not live-wired). BL-0305 blocked by live evidence. No formula ledger bump (plumbing only). |

## 2026-09-08 — G9: IBKR tick-by-tick trade tape → CVD + entitlement readiness

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `providers/ibkr_observational`, `tools/ibkr`, `market_data`, `order_flow` |
| **Summary** | Added canonical IBKR tick-by-tick observational path (`IBKR_TRADES` / `subscribe_trades` → `TradePrintFacts` → Lee-Ready classification with L1 context → `apply_classified_trade` → G3 CVD). Extended outer transport with `req_tick_by_tick_data` / `tickByTickAllLast` bridge. Capture/replay TRADE kind, entitlement TRADES readiness, offline gate preserved. LIVE_PROVIDER_UNVERIFIED retained — no live canary run. BL-0304 closed for offline/replay path; BL-0305 partial/blocked by live evidence. |
| **Key files** | `providers/ibkr_observational/trades.py`, `adapter.py`, `contracts.py`, `capability.py`, `capture.py`, `tools/ibkr/observational_transport.py`, `market_data/observational_state.py`, G9 test modules, `docs/audits/imp-reconciliation/14f-g9-current-state-matrix.md` |
| **Tests** | Baseline FULL **4221/48/0/0**; focused G9 **29/0/0/0**; CHANGED **3715/48/0/0**; FULL **4250/48/0/0** (+29) |
| **Related** | [14f-g9-current-state-matrix](../audits/imp-reconciliation/14f-g9-current-state-matrix.md) |
| **Notes** | No native IB aggressor side claimed. Dedup limited to replay composite key. BL-0301/0303 remain PARTIAL. |

## 2026-09-08 — G8 closure correction: remove src→tools/ibkr inversion

| Field | Value |
|-------|-------|
| **Status** | `complete` (working tree; uncommitted) |
| **Area** | `tools/ibkr/runtime_bootstrap.py`, `market_data/{live_runtime,ibkr_runtime_bridge}.py`, G8 structural/performance tests, canonical G8 docs |
| **Summary** | Moved concrete `IbkrObservationalTransport` construction to outer `tools/ibkr/runtime_bootstrap.py`. Canonical `live_runtime` now accepts an injected transport or `IbkrObservationalTransportProvider`; it no longer imports `tools.ibkr`. Added AST boundary scan and four runtime-overhead measurements. Moomoo path unchanged. BL-0301/0304 PARTIAL; BL-0305 PARTIAL/BLOCKED_BY_LIVE_EVIDENCE; LIVE_PROVIDER_UNVERIFIED retained. G9 not started. |
| **Key files** | `tools/ibkr/runtime_bootstrap.py`, `src/.../market_data/live_runtime.py`, `ibkr_runtime_bridge.py`, `tools/ui1/run_ui_api.py`, `tests/market_data/test_g8_src_tools_boundary.py`, `tests/market_data/test_g8_runtime_performance.py`, `tests/ibkr/test_runtime_bootstrap.py`, `docs/audits/imp-reconciliation/14e-g8-current-state-matrix.md` |
| **Tests** | Focused G8 **74** OK; ibkr 63; providers 257; market_data 104; order_flow 148; xa01 72; trading_correctness 122; G5 82; G6 91; G7 39; FAST 21/0/0/0; CHANGED **3686/48/0/0**; FULL 4209/48/0 reused (+12 in CHANGED vs prior G8 3674) |
| **Related** | Prior G8 entry below; [14e-g8-current-state-matrix.md](../audits/imp-reconciliation/14e-g8-current-state-matrix.md) |
| **Notes** | Dynamic import of `tools.ibkr` from src is still inversion; correction uses protocol injection only. |

## 2026-09-08 — G7 closure evidence reconciliation

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | audit docs / test-count accounting |
| **Summary** | Reconciled G7 closure test-count evidence: authoritative FULL/CHANGED delta is **+39** (4107→4146 FULL; 3572→3611 CHANGED). Prior informal per-file listing summed **41** because `test_g7_runtime_composition.py` was recorded as **11**; authoritative count is **9**. No G6→G7 test removals or weakening. Documented capability authority hierarchy: `ProviderRegistry` (metadata) → `RuntimeCapabilityRegistry` (runtime facade) + `VerifiedCapabilityRegistry` (Moomoo probe evidence only). |
| **Key files** | `docs/audits/imp-reconciliation/{15-validation-evidence.md,14d-g7-current-state-matrix.md,00-program-state.md}`, `docs/platform/{PROGRAM_STATUS.md,MASTER_ARCHITECTURE.md}` |
| **Tests** | G7 inventory verified via unittest discover on four `test_g7_*.py` modules: **39/0** (14+14+9+2). No FULL rerun required — existing **4146/48/0** evidence unchanged. |
| **Related** | G7 entry below; [14d-g7-current-state-matrix.md](../audits/imp-reconciliation/14d-g7-current-state-matrix.md) test inventory + capability hierarchy sections |
| **Notes** | Documentation-only reconciliation; no runtime or test semantics changed. G8 may proceed. |

## 2026-09-08 — G8 IBKR runtime convergence / live provider wiring

| Field | Value |
|-------|-------|
| **Status** | `complete` (working tree; uncommitted) |
| **Area** | `tools/ibkr/observational_transport.py`, `market_data/{live_runtime,ibkr_runtime_bridge,runtime_composition}.py`, `providers/ibkr_observational/contract_resolution.py`, G8 tests, `docs/audits/imp-reconciliation/14e-g8-current-state-matrix.md` |
| **Summary** | Converged G6 IBKR adapter + G7 runtime composition with outer TWS transport and `live_runtime.configure()` startup path. Added stdlib-only `IbkrObservationalTransport` callback bridge (operation 0 / side 0 preserved), src-side contract resolution + runtime bridge (no src→tools inversion), capability-state sync from adapter diagnostics, Moomoo path preserved. CVD remains explicit UNAVAILABLE from L1-only (no fabricated trades). LIVE_PROVIDER_UNVERIFIED retained (no live canary in closure environment). |
| **Key files** | See summary paths + `tests/ibkr/test_observational_transport.py`, `tests/providers/test_g8_*.py`, `tests/market_data/test_g8_*.py` |
| **Tests** | G8 focused **63** OK; CHANGED **3674/48/0** (+63 vs G7 3611); FAST 21/0/0 |
| **Related** | `docs/audits/imp-reconciliation/14e-g8-current-state-matrix.md` |
| **Notes** | BL-0301/0304/0305 PARTIAL — observational runtime wired offline; broader adapter scope, tick-by-tick CVD, and live entitlement canary remain open per backlog wording. |

## 2026-09-08 — G7 Runtime wiring / provider capability convergence

| Field | Value |
|-------|-------|
| **Status** | `complete` (working tree; uncommitted alongside pre-existing dirty state) |
| **Area** | `providers/runtime_capability.py`, `providers/runtime_selection.py`, `market_data/{lane_requirements,observational_lanes,runtime_composition}.py`, `cross_lane/runtime_inputs.py`, G7 tests, docs/evidence |
| **Summary** | Converged provider capability truth and observational runtime wiring: multi-axis `RuntimeCapabilityRegistry` facade over `ProviderRegistry` + runtime state (implemented vs entitlement vs timeliness vs health; execution forbidden); deterministic fail-closed `ObservationalProviderSelector`; lane requirement graph; `ObservationalLaneRuntime` wiring canonical `ObservationalStateStore` → L1/CVD/price-aligned OFI/book-features/options/futures analytics with provenance; `ObservationalRuntimeComposition` transport-injection boundary (no src→tools/ibkr); cross-lane `runtime_inputs` bridge; 39 focused G7 tests; LIVE_PROVIDER_UNVERIFIED retained. |
| **Key files** | See summary paths + `tests/providers/test_g7_runtime_capability.py`, `tests/market_data/test_g7_{observational_lanes,runtime_composition}.py`, `tests/cross_lane/test_g7_runtime_inputs.py`, `docs/audits/imp-reconciliation/14d-g7-current-state-matrix.md` |
| **Tests** | G7 focused **39** OK (14+14+9+2 per-file); providers 232 OK; market_data 74 OK; trading_correctness 122 OK; FAST 21/0/0; CHANGED **3611/48/0**; FULL **4146/48/0** — zero failures |
| **Related** | `docs/audits/imp-reconciliation/{14d-g7-current-state-matrix.md, 15-validation-evidence.md G7 section, 00-program-state.md}`; G6 entry below |
| **Notes** | BL-0301 (broader IBKR adapter with account/secdef/bars) NOT closed — G7 is runtime convergence only. Performance: RUNTIME_PERFORMANCE_MEASURED (capability resolution smoke). Live provider LIVE_PROVIDER_UNVERIFIED. |

## 2026-09-08 — G6 IBKR observational L1/L2 provider adapter (BL-0213)

| Field | Value |
|-------|-------|
| **Status** | `complete` (working tree; uncommitted alongside pre-existing dirty state) |
| **Area** | `providers/ibkr_observational/*` (new canonical runtime), `market_data/observational_state.py`, `tests/providers/test_ibkr_observational_*.py` (new), docs/evidence |
| **Summary** | Delivered the canonical provider-neutral IBKR observational adapter: IBKR callback facts → XA-01 identity → L1 quote accumulation and/or L2 `DepthUpdate` → `ObservationalStateStore` → G5 `IncrementalOrderBook`. Verified operation/side mapping (0=INSERT/1=UPDATE/2=DELETE; 0=ASK/1=BID); rank/position→price-keyed translation with price-changing UPDATE and rank-resolved DELETE; no fabricated depth sequence; subscription generation/reconnect/cancel/pacing; entitlement/delayed L1 truthfulness; evidence-backed error normalization; memory-only capture by default with deterministic replay through the adapter path; diagnostics/readiness; no execution capability; offline fail-closed; runtime `src` independent of `tools/ibkr` implementation. |
| **Key files** | `src/market_platform_foundation/providers/ibkr_observational/{adapter,capability,capture,constants,contracts,diagnostics,errors,identity,l1,lifecycle,mapping,pacing,rank,__init__}.py` (new), `src/market_platform_foundation/market_data/observational_state.py`, `tests/providers/test_ibkr_observational_{l1,l2,lifecycle,safety,capture_replay,performance}.py` (new), `tests/providers/ibkr_observational_support.py` (new) |
| **Tests** | ibkr_observational 91 OK, providers 216 OK, market_data 49 OK, order_book 87 OK, trading_correctness 122 OK; FAST 21/0/0; CHANGED **3572/48/0**; FULL **4107/48/0** — zero failures |
| **Related** | `docs/audits/imp-reconciliation/{12-master-backlog.md BL-0213, 14c-g6-current-state-matrix.md, 15-validation-evidence.md G6 section, 00-program-state.md}`; G5 entry below |
| **Notes** | Adapter throughput measured on dev machine (L1 ~33.9k/s, L2 normalize ~29.4k/s, L2→book ~18.6k/s) — ADAPTER_PERFORMANCE_MEASURED, not production IBKR. Live provider LIVE_PROVIDER_UNVERIFIED. G7 (runtime wiring / capability convergence) is next per mandate — not started. |

## 2026-09-08 — G5 canonical incremental L2 order-book engine (BL-0212)

| Field | Value |
|-------|-------|
| **Status** | `complete` (working tree; uncommitted alongside pre-existing dirty state) |
| **Area** | `order_flow/order_book/*` (new canonical domain), `order_flow/{ofi,cvd,contracts,__init__}.py`, `market_data/observational_state.py`, `ui_api/live_projections.py`, `tests/order_flow/test_order_book_*.py` (new), `tests/market_data/test_canonical_book_integration.py` (new), docs |
| **Summary** | Built the one canonical provider-neutral incremental market-by-price book engine resolving AB-003/ARCH-003 (snapshot-only L2), ARCH-006 (rank-pair OFI mis-pairing) and ARCH-009 (hardcoded `book_state_valid: True`). New `order_flow/order_book/` package: `contracts.py` — provider-neutral `DepthUpdate` vocabulary (INSERT/UPDATE/DELETE/RESET × BID/ASK; instrument_id, price/size Decimal-exact via `Decimal(str(v))` boundary normalization, advisory position rank metadata, source/source_time_ns/received_time_ns, optional sequence, subscription identity, provider event id, schema version, provenance) + explicit `ApplyResult` contract (APPLIED/NOOP/DUPLICATE/REJECTED/INVALIDATED/RESET_APPLIED with reason, sequence_state, validity, generation, update_count); `engine.py` — `IncrementalOrderBook` with price-keyed side-ordered levels, explicit insert/update/delete/reset semantics (conflicting duplicate insert invalidates; update-of-missing fails closed; delete can never remove an unrelated rank; RESET is not DELETE — clears levels, advances generation, clears sequence continuity, marks RESET_PENDING), 5-state sequence machine (NO_SEQUENCE/BASE/CONTIGUOUS/DUPLICATE/GAP/REGRESSION — gap/regression fail closed INVALID with recovery required), subscription-generation gate rejecting late old-generation events, derived `book_state_valid`, deterministic `state_hash()`, no wall clock; `freshness.py` — pure `evaluate_book_freshness(book, as_of_time_ns, policy)` → FRESH/STALE/INVALID/UNAVAILABLE (thresholds in policy; INVALID beats STALE; stale never silently collapsed); `projection.py` — deterministic legacy snapshot dict projection with additive `book_status`/`book_status_reason`/`sequence_status`/`generation`/timestamps + `replace_from_snapshot`/`ingest_snapshot_dict` explicit compatibility ingestion (RESET-then-load, never blind UPDATE); `replay.py` — `replay(events)`/`replay_state_hash`/`measure_replay_throughput`, duplicates never double-apply, RESET/gap boundaries replay identically. Order-flow: `ofi.py` adds versioned price-aligned multi-level OFI (`compute_multilevel_ofi_price_aligned`) keyed by exact price — INSERT/DELETE rank shifts can no longer fabricate rank-paired events; legacy rank-sum v1 retained unchanged; formula_ledger entry `of.multilevel_ofi_price_aligned` (96→97). Store/API: `observational_state.py` keeps per-instrument canonical engines, full-book pushes enter via `replace_from_snapshot`, and stored book payloads + `ui_api/live_projections.py` expose derived `book_state_valid` + status/sequence/generation fields (ARCH-009 hardcoded True removed). CVD session authority untouched (BL-0208 anchor/reset metadata preserved with tests). |
| **Key files** | `src/market_platform_foundation/order_flow/order_book/{contracts,engine,freshness,projection,replay,__init__}.py` (new), `src/market_platform_foundation/order_flow/{ofi,cvd,contracts,__init__}.py`, `src/market_platform_foundation/market_data/observational_state.py`, `src/market_platform_foundation/ui_api/live_projections.py`, `tests/order_flow/test_order_book_{basic,operations,sequence,reset_generation,freshness,snapshot,replay,ofi_integration}.py` (new), `tests/market_data/test_canonical_book_integration.py` (new) |
| **Tests** | order_book 82 OK, canonical-book store integration 5 OK, order_flow 66 OK, trading_correctness 122 OK, CVD session 8 OK; FAST 21/0/0; CHANGED **3481/48/0**; FULL **4016/48/0** — zero failures |
| **Related** | `docs/audits/imp-reconciliation/{12-master-backlog.md BL-0212, 14b-g5-current-state-matrix.md, 15-validation-evidence.md G5 section, g5-order-book-replay-evidence.json}`; G4 entry below |
| **Notes** | Replay throughput measured on representative synthetic depth (10/50/100 levels): ~93k/45k/23k events/sec — PERFORMANCE_MEASURED, no production-throughput claim. IBKR `reqMktDepth` mapping is documented for G6 only; no runtime IBKR work here. G6 (IBKR observational L1/L2 provider adapter) is the next increment per current mandate — not started. |

---

## 2026-09-08 — G4 multi-asset accounting kernel (BL-0211)

| Field | Value |
|-------|-------|
| **Status** | `complete` (working tree; uncommitted alongside pre-existing dirty state) |
| **Area** | `portfolio/*` (accounting kernel), `options/execution.py`, `risk/{financial,pretrade}.py`, `paper/*` gates, `tests/trading_correctness/*`, docs |
| **Summary** | Built the canonical multi-asset accounting foundation on the G3.1 baseline. New `portfolio/instrument_economics.py` is a fail-closed economics contract derived from XA-01 identity (quantity unit kind-driven; derivative multipliers explicit and positive; missing multiplier/currency/unknown kind fail closed; multiplier=1 only for equity/ETF). New `portfolio/accounting.py` centralizes exact-Decimal money/notional/P&L/reservation formulas and rejects binary float at the kernel boundary. The canonical portfolio mutation boundary now rejects derivative positions without CONTRACTS unit + positive multiplier. The independent float options ledger (`portfolio/options_ledger.py`) was rewritten Decimal-exact and marked NON-AUTHORITATIVE compatibility over the O9 simulation lane, with a canonical position adapter that aggregates same-identity partial fills (contract quantity truth, exact premium cost basis); `options/execution.py` converts to float only at the JSON presentation boundary (O9 goldens unchanged). Futures exactness (1/multi-contract, long/short sign, no drift, replay) is proven through the kernel + canonical valuation; family/continuous identities remain non-executable. Per-currency working obligations (`working_order_obligations_by_currency`, `currency_available_cash_minor`) and a per-currency financial gate + pretrade context (`currency_cash_minor`) make cash currency-aware; a missing currency bucket fails closed INSUFFICIENT_SETTLEMENT_CURRENCY — never 1:1. Also repaired the G3.1 precondition: three callers of the already-landed fail-closed `register_future_contract` supplied explicit multipliers, plus a spec-less-future fail-closed test. |
| **Key files** | `src/market_platform_foundation/portfolio/{accounting,instrument_economics,canonical,options_ledger}.py`, `src/market_platform_foundation/options/execution.py`, `src/market_platform_foundation/risk/{financial,pretrade}.py`, `src/market_platform_foundation/paper/{execution,broker_paper}.py`, `tests/portfolio/test_instrument_economics.py` (new), `tests/trading_correctness/test_multi_asset_accounting.py` (new), `tests/xa01/test_xa01_derivatives.py` (+2), 3 precondition-test fixes |
| **Tests** | portfolio 136 OK, trading_correctness 122 OK, options 147 OK, platform 474 OK (2 skipped), ui1 13 OK, ui2 5 OK, xa01 72 OK; FAST 21/0/0; CHANGED **3347/48/0**; FULL **3929/48/0** — zero failures |
| **Related** | `docs/audits/imp-reconciliation/{12-master-backlog.md BL-0211, 14a-g4-current-state-matrix.md, 15-validation-evidence.md G4 section}`; G2 portfolio spec; G3.1 entry below |
| **Notes** | Options execution lane stays a non-authoritative simulation projection over the same fills (removal condition documented in the module). Futures gate still fails closed UNSUPPORTED_RISK_MODEL — no margin model invented. Auto-FX settlement and futures margin methodology remain explicit product decisions for later increments. |

---

## 2026-09-08 — G3.1 cross_lane golden-blocker reconciliation (BL-0210)

| Field | Value |
|-------|-------|
| **Status** | `complete` (working tree; uncommitted alongside pre-existing dirty state) |
| **Area** | `cross_lane/fusion.py`, `tests/cross_lane/*`, docs |
| **Summary** | Closed the last known FULL failure — the pre-existing dirty-tree `cross_lane` golden. Hardened `_occurrence_weight` in `fuse_opportunity_v1` so a squeeze-aligned template with no hazard and no occurrence model output fails closed to UNAVAILABLE (`OCCURRENCE_UNAVAILABLE`) instead of silently weighting 1.0; non-squeeze-aligned paths carry an explicit `OCCURRENCE_UNAVAILABLE` quality flag with factor 1.0; named `PAYOFF_ALREADY_NET_TOLERANCE`; bumped formula_ledger + SHARED_P4_EV_OPPORTUNITY_SPEC to fusion v2; regenerated the golden fixture with hash forensics (`.local/g31-hash-forensics.py`) proving the V1→V2 snapshot delta is the intended semantic change. |
| **Key files** | `src/market_platform_foundation/cross_lane/{fusion,opportunity,portfolio}.py`, `tests/cross_lane/test_{opportunity_fusion,portfolio_p5}.py`, `tests/fixtures/providers/opportunity/nvda_opportunity_fusion_expected.json`, `docs/research/{formula_ledger.json,SHARED_P4_EV_OPPORTUNITY_SPEC.md}` |
| **Tests** | tests/cross_lane +9 (6 opportunity-fusion, 3 portfolio-p5); FAST 21 passed; CHANGED 3233/48/0; FULL **3870/48/0** — zero failures, no excluded baseline remains |
| **Related** | `docs/audits/imp-reconciliation/15-validation-evidence.md` (G3.1 section); backlog BL-0210; G3 entry (2026-09-07) |
| **Notes** | No production gate weakened; research-lane honesty only. G4 (multi-asset accounting kernel) is the next structural increment per current mandate. |

---

## 2026-09-07 — G3 trading-correctness increment (BL-0201..BL-0209)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend`, `risk`, `tests`, `docs` |
| **Summary** | Finished the G3 trading-correctness increment on the working tree: BL-0201 server preview binding + strategy prepared-decision authority (server-side PreviewStore with fail-closed verify; prepared idempotency-key binding; prepared risk-reference-price handoff into the final financial recheck), BL-0202 internal + broker-paper cash gates (fail-closed REQUIRED_PRICE_MISSING, conservative bar/live-mark reference, trusted strategy reference price that cannot bypass insufficient cash, currency from canonical metadata, partial-fill/replace reservation recompute), BL-0203 canonical identity admission with closed arbitrary-equity fallback (BIYA/AAPL fixtures canonical), BL-0204 working-remainder projection corrections, BL-0205 replace lifecycle with persisted replace_revision + idempotent retries, BL-0206 cancel-time late-fill reconciliation, BL-0207 per-ledger RLock atomic idempotency+creation boundary (release before broker network call) with thread-barrier proofs, BL-0208 deterministic CVD session semantics, BL-0209 typed `evaluate_pretrade` wired into both executable BUY gates. Completed the last pending change (threading the approved risk-decision reference price through `_submit_prepared`) and added 4 dedicated regression tests (no-bars prepared submit succeeds via risk reference price; no bars + no reference fails closed; reference price cannot bypass insufficient cash; prepared quantity/reference price server-authoritative). |
| **Key files** | Modified: `src/market_platform_foundation/paper/{execution,broker_paper,ledger,contracts,preview}.py`, `src/market_platform_foundation/risk/{pretrade,financial}.py`, `src/market_platform_foundation/intelligence/execution/engine.py`, `src/market_platform_foundation/order_flow/cvd.py`, `src/market_platform_foundation/ui_api/{server,store,paper_projections}.py`, `src/market_platform_foundation/xa01/*`, `tests/trading_correctness/` (10 suites), platform broker fixtures (live marks, CancelDispatch `events=()`, E5 preview-first submit), `tools/validation_manifest.{json,py}`, `tests/validation/test_validation_manifest.py` (offline count 62); workspace evidence: `docs/audits/imp-reconciliation/{12-master-backlog,15-validation-evidence}.md`, `docs/platform/PROGRAM_STATUS.md` |
| **Tests** | `tests/trading_correctness` 91 passed (87 baseline + 4 new); governed intelligence flow green with `bars=[]`; platform broker P4/P44/P4C/reconciliation/status-apply 93 passed; operator surface fixes 16 passed; validation suite 82 passed; FAST **21 passed**; CHANGED **3224 tests, 1 failure** (known pre-existing cross_lane golden baseline only); FULL **3861 tests, 1 failure** (same baseline). |
| **Related** | [15-validation-evidence G3 section](../audits/imp-reconciliation/15-validation-evidence.md); [master backlog BL-0201..BL-0209](../audits/imp-reconciliation/12-master-backlog.md); G2 entry below |
| **Notes** | Production gates never weakened: broker test fixtures now supply live marks (UI-path parity), CancelDispatch fake returns an empty `events` stream, and the E5 parallel test uses preview-first submit with PREVIEW_PORTFOLIO_STALE refresh-retry (never bypasses preview authority, still genuinely concurrent). Cross_lane golden failure is unrelated pre-existing dirty work (occurrence-weight hardening), not caused by G3. |

## 2026-09-06 — Q-H3-usage: stamp q_method on O3 and BL

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend`, `docs` |
| **Summary** | Stamp `q_method` on log-normal O3 (`log_normal_moment_approx`) and discrete BL (`breeden_litzenberger`) payloads so P−Q consumers can see which Q they compared. Default `infer_risk_neutral_distribution` is unchanged. `donor_bridge/projections` and `providers/projections` still call log-normal O3 (no auto-BL). No trade authority. |
| **Key files** | Modified: `src/market_platform_foundation/options/risk_neutral.py`, `src/market_platform_foundation/options/breeden_litzenberger.py`, `tests/options/test_options_o3.py`, `tests/options/test_options_o3_bl.py`, `tests/formulas/test_heuristic_pin_drift.py`, `docs/research/formula_ledger.json`, `docs/research/FORMULA_LEDGER.md`; workspace: `docs/reviews/2026-09-04-hardening-task-plan.md` |
| **Tests** | Python 3.13. `pytest tests/options/test_options_o3.py tests/options/test_options_o3_bl.py tests/formulas/test_heuristic_pin_drift.py tests/formulas/test_formula_goldens.py tests/options/test_options_o4.py`: 41 passed. `imp.py validate domain options`: 583 passed, 11 skipped, 0 failures, 0 errors. |
| **Related** | [Hardening task plan](../../../../docs/reviews/2026-09-04-hardening-task-plan.md) Q-H3-usage; Q-H3 PR |
| **Notes** | G1–G6 stay closed. Not a default Q switch. |

## 2026-09-06 — Q-H1-futures-rate: unused carry r and DTE fallback

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend`, `docs` |
| **Summary** | Spot carry is `ln(F/S)/days×365` and does not use `r`. Dropped silent `risk_free_rate=0.05` and stopped stamping unused r in assumptions. Missing observation date fail-closes (no `"2025-01-01"` DTE fallback). Does not reopen Q-H1 calibration; `CARRY_SCALE=0.05` stays an unfitted tanh pin. Canonical trees only. |
| **Key files** | Modified: `src/market_platform_foundation/futures/carry.py`, `tests/futures/test_f3_basis_carry.py`, `tests/formulas/test_heuristic_pin_drift.py`, `docs/research/formula_ledger.json`, `docs/research/FORMULA_LEDGER.md`; workspace: `docs/reviews/2026-09-04-hardening-task-plan.md` |
| **Tests** | Python 3.13. `pytest tests/futures/test_f3_basis_carry.py tests/futures/test_baselines_engine.py tests/formulas/test_heuristic_pin_drift.py`: 26 passed. `imp.py validate domain futures`: 526 passed, 11 skipped, 0 failures, 0 errors. |
| **Related** | [Hardening task plan](../../../../docs/reviews/2026-09-04-hardening-task-plan.md) Q-H1-futures-rate; Q-H3 PR |
| **Notes** | G1–G6 stay closed. No fusion/GARCH/HAR/ADAM/logistic calibration. |

## 2026-09-06 — Q-H3: discrete Breeden–Litzenberger Q (additive)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend`, `docs` |
| **Summary** | Closed Q-H3 with an additive fail-closed discrete Breeden–Litzenberger path (`infer_risk_neutral_breeden_litzenberger`, `risk_neutral_breeden_litzenberger_v1`) on the IV-reconstructed call curve. Default O3 stays `risk_neutral_log_normal_moment_approx_v1`; no average-IV log-normal fallback; no silent `rate=0.05`. Ledger 88→89 (`options.risk_neutral_q_bl`, `research_baseline`). `donor_bridge/projections` and `providers/projections` still call `infer_risk_neutral_distribution`. G1–G6 stay closed; no trade authority. |
| **Key files** | Created: `src/market_platform_foundation/options/breeden_litzenberger.py`, `tests/options/test_options_o3_bl.py`. Modified: `src/market_platform_foundation/options/risk_neutral.py`, `options/__init__.py`, `tests/formulas/test_heuristic_pin_drift.py`, `docs/research/formula_ledger.json`, `docs/research/FORMULA_LEDGER.md`; workspace: `docs/reviews/2026-09-04-hardening-task-plan.md`, `docs/reviews/2026-09-05-formula-correctness-review.md` |
| **Tests** | Python 3.13. Scoped pytest (`test_options_o3.py`, `test_options_o3_bl.py`, `test_heuristic_pin_drift.py`, `test_formula_goldens.py`): 35 passed. `imp.py validate domain options`: 581 passed, 11 skipped, 0 failures. `imp.py validate full`: 3575 passed, 48 skipped, 0 failures, 0 errors. |
| **Related** | [Hardening task plan](../../../../docs/reviews/2026-09-04-hardening-task-plan.md) Q-H3; [formula correctness review](../../../../docs/reviews/2026-09-05-formula-correctness-review.md) |
| **Notes** | Q-H1 remains open (unfitted scalars). Q-H4 / `SUPPORTED` stay closed. 2-strike O3 fixtures fail BL (`BL_INSUFFICIENT_STRIKES`). Do not treat discrete BL as a trade signal. |

## 2026-09-06 — Pin-drift ADAM import uses canonical squeeze tree

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend` |
| **Summary** | `test_heuristic_pin_drift` imported ADAM from a repo-root `short-squeeze-project` path. CI sparse-checks that location without `apps/`, so `validate changed` collected an ImportError after PR #12. Point the test at `projects/short-squeeze-project` like donor-bridge tests. |
| **Key files** | Modified: `tests/formulas/test_heuristic_pin_drift.py` |
| **Tests** | Python 3.13. `pytest tests/formulas/test_heuristic_pin_drift.py`: 7 passed. |
| **Related** | [PR #12](https://github.com/AdamEddahmouni/market-trading-platform/pull/12) |
| **Notes** | Fast IMP Validation passed on #12; only `validate-python-changed` failed. G1–G6 stay closed. |

## 2026-09-05 — Q-H1-O10-rate: O10 / R-O6 fail-closed rate

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend`, `docs` |
| **Summary** | Closed Q-H1-O10-rate: `delta_hedged_research_snapshot` and `compose_r_o6_research_snapshot` no longer default `rate=0.05`. Missing positive rate (explicit kwarg, else P/Q dict) fail-closes with `RATE_ASSUMPTION_MISSING`. Successful O10 snapshots stamp resolved `rate`. Versions `delta_hedged_research_v2` / `r_o6_research_v2`. Ledger 86→88 with `options.delta_hedged` and `options.r_o6`. Q-H1 stays open for unfitted fusion/GARCH/HAR/ADAM/logistic only. G1–G6 stay closed; no trade authority. |
| **Key files** | Modified: `src/market_platform_foundation/options/delta_hedged.py`, `r_o6.py`, `tests/options/test_options_o10.py`, `tests/formulas/test_heuristic_pin_drift.py`, `docs/research/FORMULA_LEDGER.md`, `docs/research/formula_ledger.json`; workspace: `docs/reviews/2026-09-04-hardening-task-plan.md`, `docs/reviews/2026-09-05-formula-correctness-review.md` |
| **Tests** | Python 3.13. Scoped pytest: 52 passed. `imp.py validate domain options`: 575 passed, 11 skipped, 0 failures. `imp.py validate full`: 3569 passed, 48 skipped, 0 failures, 0 errors (after classifying `src/market_platform_foundation/lanes` in the repository-closure audit). |
| **Related** | [Hardening task plan](../../../../docs/reviews/2026-09-04-hardening-task-plan.md) Q-H1 / Q-H1-O10-rate; [formula correctness review](../../../../docs/reviews/2026-09-05-formula-correctness-review.md) |
| **Notes** | Q-H1 remains open (unfitted scalars). O10/R-O6 no longer pin 0.05. Do not treat delta-hedged path or R-O6 correlation as a trade signal. |

## 2026-09-05 — Q-H1-rate close + P1-3 / P1-6 / P2-1 / P2-2 docs-verify

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend`, `docs` |
| **Summary** | Closed Q-H1-rate (dealer/O2/O3 no silent `rate=0.05`) leftover: O10 inline chain and cross-lane dealer inline rows stamp tape `rate` 0.04; option-chain builder and activity envelopes copy tape `rate` onto contract dicts so workspace dealer snapshots still build. Closed P1-3, P1-6, P2-1, P2-2 in the hardening plan. Q-H1 stays open for unfitted fusion/GARCH/HAR/ADAM/logistic only. G1–G6 stay closed; no trade authority. |
| **Key files** | Modified: `tests/options/test_options_o10_surface_baseline.py`, `src/market_platform_foundation/providers/adapters/option_contract_builder.py`, `fixture_options.py`, `tests/donor_bridge/test_cross_lane_adapter.py`; workspace: `docs/reviews/2026-09-04-hardening-task-plan.md`, `docs/reviews/2026-09-05-formula-correctness-review.md` |
| **Tests** | Python 3.13. Scoped pytest (O2/O3/O5/O6/O10 + goldens + pin-drift + acquisition guard + broker wiring + paper trace): 77 passed. `imp.py validate domain options`: 561 passed, 11 skipped, 0 failures. Full `validate full` not run. |
| **Related** | [Hardening task plan](../../../../docs/reviews/2026-09-04-hardening-task-plan.md) Q-H1 / Q-H1-rate / P1-3 / P1-6 / P2-1 / P2-2; [formula correctness review](../../../../docs/reviews/2026-09-05-formula-correctness-review.md) |
| **Notes** | Q-H1 remains open (unfitted scalars). Q-H1-rate is closed. Dealer/O2/O3 0.05 leftover is not a Q-H1 pin. Do not treat dealer gamma or surface IV as a trade signal. |

## 2026-09-05 — Q-H1 pin + O5 vol/rate fail-closed + O2 strict underlying

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend`, `docs` |
| **Summary** | Named unfitted Q-H1 fusion/GARCH/HAR/logistic constants and added a ledger drift golden (ADAM weights assert-only; no calibration). O5 greeks fail closed without positive vol and rate (`options_signed_flow_v3`). O2 no longer uses strike×1.02/0.98; surface points are skipped and stamped with `underlying_price` (`sigma_kt_v2`); O3/dealer/strategy/event_vol share that fail-closed infer. G1–G6 stay closed; Q-H1 remains open for calibration; no trade authority. |
| **Key files** | Modified: `src/market_platform_foundation/options/{flow,surface,risk_neutral,dealer,strategy,event_vol,edge}.py`, `cross_lane/fusion.py`, `research/distribution/{garch,har_rv}.py`, `research/squeeze_models/logistic_hazard.py`, options O2/O3/O5 tests + goldens, signed-flow fixture, `docs/research/FORMULA_LEDGER.md`, `docs/research/formula_ledger.json`; created: `tests/formulas/test_heuristic_pin_drift.py`; workspace: `docs/reviews/2026-09-04-hardening-task-plan.md`, `docs/reviews/2026-09-05-formula-correctness-review.md` |
| **Tests** | Python 3.13. `pytest tests/options/test_options_o{2,3,5,6}.py tests/formulas/test_formula_goldens.py tests/formulas/test_heuristic_pin_drift.py`: 48 passed. Extra O7/O8: 21 passed (69 combined). `imp.py validate domain options`: 565 passed, 11 skipped. Full `validate full` not run. |
| **Related** | [Hardening task plan](../../../../docs/reviews/2026-09-04-hardening-task-plan.md) Q-H1 / Q-H1-O5 / O2; [formula correctness review](../../../../docs/reviews/2026-09-05-formula-correctness-review.md) |
| **Notes** | Dealer `DEFAULT_RATE=0.05` and O3/O2 IV `rate=0.05` remain Q-H1 pins. Do not treat signed flow or surface IV as a trade signal. |

## 2026-09-05 — Q-H2: O5 signed-flow fail-closed without underlying spot

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend`, `docs` |
| **Summary** | Options O5 greeks-equivalent signed flow no longer defaults spot to 100.0. Spot is explicit or inferred from `underlying_price` (same strict helper as Q7 friction). Missing spot leaves volume/direction intact and sets greeks to `None` with `UNDERLYING_PRICE_ASSUMPTION_MISSING`. `DEFAULT_VOL`/`DEFAULT_RATE` remain unfitted. G1–G6 stay closed; no trade authority. |
| **Key files** | Modified: `src/market_platform_foundation/options/flow.py`, `src/market_platform_foundation/options/edge.py`, `tests/options/test_options_o5.py`, `tests/formulas/test_formula_goldens.py`, `tests/fixtures/providers/options/nvda_signed_flow_slice.json`, `docs/research/FORMULA_LEDGER.md`, `docs/research/formula_ledger.json`; workspace: `docs/reviews/2026-09-04-hardening-task-plan.md`, `docs/reviews/2026-09-05-formula-correctness-review.md` |
| **Tests** | Python 3.13. `pytest tests/options/test_options_o5.py tests/formulas/test_formula_goldens.py`: 21 passed. `imp.py validate domain options`: 550 passed, 11 skipped. Full `validate full` not run. |
| **Related** | [Hardening task plan](../../../../docs/reviews/2026-09-04-hardening-task-plan.md) Q-H2; [formula correctness review](../../../../docs/reviews/2026-09-05-formula-correctness-review.md) |
| **Notes** | Surface O2 `strike * 1.02/0.98` fallback was not changed. Do not treat signed flow as a trade signal. |

## 2026-09-05 — Phase 4: formula correctness verification and reporting

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend`, `docs` |
| **Summary** | Verified Phase 1–3 formula and path work; aligned the 86-row formula ledger so Q is `risk_neutral_log_normal_moment_approx_v1` and options friction has no silent 100.0 underlying. Registered `tests/formulas` in the validation manifest (was unclassified and blocked `validate.py`). Wrote Q-series notes and a correctness review. G1–G6 remain closed; no LIVE-001, shadow, canary, or broker wires; no `SUPPORTED` claim. |
| **Key files** | Modified: `docs/research/FORMULA_LEDGER.md`, `docs/research/formula_ledger.json`, `tools/validation_manifest.json`, `tests/validation/test_validation_manifest.py`; workspace: `docs/reviews/2026-09-04-hardening-task-plan.md`, `docs/reviews/2026-09-05-formula-correctness-review.md` |
| **Tests** | Python 3.13. Targeted pytest 63 passed; broader campaign slice 1881 passed / 27 skipped; `imp.py validate domain options` 545 passed / 11 skipped; `domain order-flow` 525 passed / 11 skipped; squeeze metric/ADAM 49 passed; UI `laneRegistry.test.ts` 9 passed. Monorepo `validate changed` only 21 mandatory tests (path-prefix under-select). Full `validate full` not run. |
| **Related** | [Hardening task plan](../../../../docs/reviews/2026-09-04-hardening-task-plan.md) Q-series, P1-2, P1-4, P1-5, P2-4; [formula correctness review](../../../../docs/reviews/2026-09-05-formula-correctness-review.md) |
| **Notes** | O5 signed-flow still pins `DEFAULT_SPOT=100.0` when spot is omitted; that is not the friction path. Heuristic GARCH/HAR/fusion/ADAM/logistic weights remain unfitted. |

## 2026-09-05 — P1-2 / P1-4 / P1-5 / P2-4: lane and engine path invariants

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend`, `ui`, `docs` |
| **Summary** | Canonical opportunity mint is StrategyMatch → `bridge.py` → OpportunityEngine; older constructions are deprecated and two paths conflict on persist. One tested discovery/workspace/`LaneId` map; `MARKET_CONTEXT` routes to workspace `catalyst` (not `order-book`). Execution-intent runtimes that omit `strategy_eligibility` fail closed; research-only scanners do not construct OrderReadyV1. Unadmitted captures and donor execution entry points cannot reach training, promotion, or OrderReady. LIVE/paper campaign gates remain closed. |
| **Key files** | Created: `src/market_platform_foundation/lanes/vocabulary.py`, `src/market_platform_foundation/intelligence/dataset_admission.py`, `tests/platform/test_lane_vocabulary.py`, `tests/platform/test_unadmitted_and_donor_isolation.py`; modified: opportunity engine/bridge/P4/economic sidecar, `strategy/runtime.py`, `strategy/eligibility.py`, `strategy/scanning.py`, training factory, promotion engine, `PAPER_DECISION_LIFECYCLE.md`, `paperDecisionSemantics.ts`, `laneRegistry.test.ts` |
| **Tests** | Targeted pytest: 41 passed (`test_universal_opportunity.py`, `test_equity_paper_runtime.py`, `test_lane_vocabulary.py`, `test_unadmitted_and_donor_isolation.py`). UI vitest: `laneRegistry.test.ts` 9 passed. Full `validate.py` not run. |
| **Related** | [Hardening task plan](../../../../docs/reviews/2026-09-04-hardening-task-plan.md) P1-2, P1-4, P1-5, P2-4 |
| **Notes** | Did not open LIVE-001, P6 Shadow Run 1, or paper campaign gates. Full `validate.py` not run (targeted only). |

## 2026-09-05 — Monorepo embedding: provenance root resolution (release/qualification gates)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend` |
| **Summary** | When the platform tree is embedded in the parent monorepo (`projects/integrated-market-platform`), git-root resolution climbed to the monorepo root, so release/qualification provenance could not find `phase0-dependency-lock.json` or `artifacts/system-acceptance/*` and ~30 change-control / release-governance / forward-qualification tests errored. `git_ref.repo_root()` and `deployment/source_provenance.get_repository_root()` now prefer the platform-tree root (marker-bounded by `phase0-dependency-lock.json`, never above the git root) when resolved from inside the platform package; in the platform's own repository the anchor is exactly the git root, so behavior is unchanged. First platform-source PR to run `imp.py validate changed` surfaced this. |
| **Key files** | Modified: `src/market_platform_foundation/git_ref.py`, `src/market_platform_foundation/intelligence/live_canary/deployment/source_provenance.py` |
| **Tests** | `imp.py validate changed`: 1691 tests, 27 skipped, 0 failures, 0 errors; change-control/release-governance/forward-qualification/paper-execution-qualification files: 130 passed |
| **Related** | [Hardening task plan](../../../../docs/reviews/2026-09-04-hardening-task-plan.md) |

## 2026-09-05 — P0-4: attribution parity enforced as a fail-closed invariant

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend` |
| **Summary** | `portfolio/attribution_materializer.py` now enforces attribution parity with the authoritative fill-driven ledger: before persisting, a recomputation is compared against every already-persisted attribution for the same allocation. Any fill it already covers that changed accounting, or any coverage regression, records an immutable `ATTRIBUTION_PARITY_VIOLATION` event (`EventV1`, deterministic `ATTR-PARITY-*` id) and raises `AttributionMaterializationError` — the divergence is never silently absorbed. Identical recomputations (dedup path) and legitimate CUMULATIVE coverage growth (later fills appended) remain silent. |
| **Key files** | Modified: `src/market_platform_foundation/portfolio/attribution_materializer.py`; created/extended tests: `tests/platform/test_strategy_attribution.py` (parity fake repo + `AttributionParityInvariantTests`) |
| **Tests** | `tests/platform`: 14 passed, 3 subtests; combined platform/intelligence run 518 passed, 2 skipped |
| **Related** | [Hardening task plan](../../../../docs/reviews/2026-09-04-hardening-task-plan.md) P0-4; [PAPER_DECISION_LIFECYCLE.md](../architecture/PAPER_DECISION_LIFECYCLE.md) |

## 2026-09-05 — P1-1: explicit strategy eligibility gate before OrderReadyV1 execution intent

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend` |
| **Summary** | Added the single checkable predicate — preregistered (identity match on the order path) + promotion state (ACTIVE champion reached through the promotion engine, carrying a promotion decision) + forward-evidence class (evidence tier that reflects post-registration observation) — in `strategy/eligibility.py`. `StrategyPaperRuntime` enforces it on the order-ready path when an execution-eligibility configuration is supplied: unknown/unpromoted strategies cannot reach execution intent — the persisted OrderReadyV1 is stamped BLOCKED with `STRATEGY_EXECUTION_ELIGIBILITY_BLOCKED` plus a `strategy_eligibility` lineage ref to the deterministic record, no paper mutation occurs, and a `STRATEGY_BLOCKED` result is returned. Research/paper runtimes without the configuration keep today's behavior; campaign wiring that claims execution intent must supply it (fail closed by construction). |
| **Key files** | Created: `src/market_platform_foundation/strategy/eligibility.py`; modified: `src/market_platform_foundation/strategy/runtime.py`, `tests/intelligence/test_equity_paper_runtime.py` (`StrategyExecutionEligibilityGateTests`) |
| **Tests** | `StrategyExecutionEligibilityGateTests`: 4 passed; runtime + learning regression 26 passed |
| **Related** | [Hardening task plan](../../../../docs/reviews/2026-09-04-hardening-task-plan.md) P1-1 |

## 2026-09-05 — P0-2: promotion dry-run harness (champion/challenger machinery proof)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend` |
| **Summary** | Fixture-driven promotion dry run (`intelligence/promotion/dry_run.py`) that replays recorded shadow observations through the promotion engine and emits an immutable `PROMOTED` / `NOT_PROMOTED` / `INVALID` decision record referencing the exact preregistration + evidence manifest — proving the ladder end-to-end without claiming an edge or granting execution authority (P1-1's eligibility gate is what separates a dry run from a real promotion). |
| **Key files** | Created: `src/market_platform_foundation/intelligence/promotion/dry_run.py`, `tests/intelligence/test_promotion_dry_run.py` |
| **Tests** | `test_promotion_dry_run.py`: 6 passed |
| **Related** | [Hardening task plan](../../../../docs/reviews/2026-09-04-hardening-task-plan.md) P0-2; [CHAMPION_CHALLENGER_PROMOTION_V1.md](CHAMPION_CHALLENGER_PROMOTION_V1.md) |

## 2026-09-05 — P0-1 / P2-3 / P2-5: readiness checklist and lane-docs hygiene

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs` |
| **Summary** | Added the one-page forward-validation readiness checklist (`docs/engineering/FORWARD_VALIDATION_READINESS_CHECKLIST.md`) listing per-campaign blockers and required acceptance artifacts to reopen P6 Shadow Run 1, EVIDENCE-01C, the live canary, Tradier sandbox, and Moomoo OpenD; superseded headers on the three lane-reconciliation roadmaps plus README pointer fix; per-lane doctrine checklist (no composite score / no fabricated synthesis / cross-lane provenance) added to the cooperative master roadmap conflict section. |
| **Key files** | Created: `docs/engineering/FORWARD_VALIDATION_READINESS_CHECKLIST.md`; modified: `docs/research/THREE_LANE_ROADMAP_RECONCILIATION.md`, `docs/research/FOUR_LANE_ROADMAP_RECONCILIATION.md`, `docs/research/FIVE_LANE_ROADMAP_RECONCILIATION.md`, `docs/research/PLATFORM_COOPERATIVE_MASTER_ROADMAP.md`, `README.md` |
| **Tests** | Platform doc-link check passed |
| **Related** | [Hardening task plan](../../../../docs/reviews/2026-09-04-hardening-task-plan.md) P0-1, P2-3, P2-5 |

## 2026-09-04 — P0-3: canonical lane-module identity (single registry, no drift)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui/workspace`, `backend`, `docs` |
| **Summary** | Unified lane/module identity onto one canonical source: `WORKSPACE_LANE_REGISTRY` in `ui/src/components/workspace-module-shared/laneRegistry.ts`, which now also derives `WORKSPACE_LANE_MODULE_IDS` and `WORKSPACE_LANE_LABELS`. `paperOrderDraft.ts` exports (`LANE_MODULE_IDS`, `LaneModuleId`, `isKnownLaneModuleId`, `laneModuleLabel`) and `paperDecisionSemantics.ts` (`EVIDENCE_LANE_TO_MODULE_ID` typing, `MODULES_WITHOUT_EVIDENCE_LANE` complement) now read from the registry instead of hand-written literals. Removed the dead backend `KNOWN_LANE_MODULES` frozenset in `paper/decision_source.py` (defined, never imported): backend workspace-lane provenance is validated structurally, so it deliberately never enumerates lane modules. Added `laneRegistry.test.ts` equality/closure tests that fail if the derived lists or the evidence map drift from the registry. |
| **Key files** | Modified: `ui/src/components/workspace-module-shared/laneRegistry.ts`, `ui/src/components/paper-now/paperOrderDraft.ts`, `ui/src/components/paper-workspace/paperDecisionSemantics.ts`, `src/market_platform_foundation/paper/decision_source.py`, `docs/architecture/DATA_CONTRACTS.md`, `docs/engineering/sops/ADD_WORKSPACE_LANE.md`, `docs/engineering/FRONTEND_GUIDE.md`; created: `ui/src/components/workspace-module-shared/laneRegistry.test.ts` |
| **Tests** | `ui`: `npm run typecheck` clean; `npm test` — 85 files / 436 tests passed (incl. new `laneRegistry.test.ts`, 7 tests). Backend: `py_compile` of `decision_source.py` OK; grep confirms zero references to removed `KNOWN_LANE_MODULES` in `src`/`tests` (only stale `.pyc`). Full manifest validation (`tools/imp.py validate`) runs in CI on push — local Python 3.10 cannot collect the suite (repo requires 3.11 `StrEnum`/tz db) and the project `.venv` is not test-equipped. |
| **Related** | [Hardening task plan](../../../../docs/reviews/2026-09-04-hardening-task-plan.md) P0-3; [ADD_WORKSPACE_LANE.md](sops/ADD_WORKSPACE_LANE.md) |
| **Notes** | Adding a lane now edits exactly one identity source (`laneRegistry.ts`) plus its per-lane feature surfaces (route component, content builder, backend projection only when a new API is needed). Zero behavior change: derived lists are identical to the prior literals; order of `MODULES_WITHOUT_EVIDENCE_LANE` follows registry nav order (no consumer depends on the old ordering). |

## 2026-09-04 — Full validation green receipt and closure-audit cleanup

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `validation`, `repository` |
| **Summary** | Removed the stray empty untracked directories `src/market_platform_foundation/tests/providers` (created 2026-09-01, empty, unreferenced) that the frozen `POST_BUILD35_SUBSYSTEM_CLASSIFICATION.json` does not classify; the canonical repository-closure audit fails closed on any unclassified path. The prior feature branch had classified the path in an unmerged edit; upstream `main` does not, and the frozen artifact must not be rewritten. With the dirs removed, the closure audit passes and the full validation ladder is green. |
| **Key files** | Deleted (empty dirs only): `src/market_platform_foundation/tests/`, `src/market_platform_foundation/tests/providers/`; receipt: `artifacts/developer-workflow/full-validation-receipt-20260904.json`; `docs/engineering/WORK_LOG.md` (this entry) |
| **Tests** | `tools/validate.py full`: `PASSED — 3487 tests, 43 skipped, 0 failures, 0 errors in 437.328s` across 59 suites (receipt JSON saved). Repository-closure audit (`load_closure_audit` on `POST_BUILD35_SUBSYSTEM_CLASSIFICATION.json`) passes. Assistant-audit evidence files stayed clean through the entire full run, confirming the churn fix holds under the full ladder. |
| **Related** | [Repository closure audit](../engineering/POST_BUILD35_REPOSITORY_CLOSURE_AUDIT.md); prior entries this date (validation unblock, evidence churn fix) |
| **Notes** | No commit, push, deploy, or authority change. The removal is cleanup of untracked empty directories only; tracked content is unchanged. |

## 2026-09-04 — Stop tests from dirtying assistant-audit evidence

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend/ui_api`, `tests`, `evidence` |
| **Summary** | Fixed the recurring dirt on `evidence/ui1/assistant-audit/{conversations,messages}.json`. Root cause: `ReplayStore.load()` defaulted `assistant_audit_root` to the tracked evidence path, so any test constructing a `ReplayStore` (e.g. `test_ui_api.py` "UI test session", the mra001 pipeline invoked by `test_mra001_api.py`) appended fresh time-stamped conversations/messages on every run. `ReplayStore` now defaults to an ephemeral temp root; the intentionally persistent writers (UI API server via `tools/ui1/run_ui_api.py`, and the mra001 evidence pipeline CLI) pass the new `TRACKED_ASSISTANT_AUDIT_ROOT` explicitly, and `build_evidence(output_dir, *, assistant_audit_root=...)` lets tests isolate. Evidence files were restored to their committed form. |
| **Key files** | `src/market_platform_foundation/ui_api/store.py`; `tools/ui1/run_ui_api.py`; `tools/mra001/run_mra001_pipeline.py`; `tests/mra001/test_mra001_api.py`; `docs/engineering/WORK_LOG.md` (this entry) |
| **Tests** | Focused suites via worker: ui1 13, ui2 5, mra001 3, mra002 3, assistant 17, gridiq 11, platform 457, intelligence 1151 — all passed, evidence files clean after every run. Explicit-root persistence verified (write to tracked root works when opted in, then restored). `tools/validate.py changed`: `305 tests, 6 skipped, 0 failures, 0 errors`; evidence clean after the run. `compileall` passed. |
| **Related** | [VALIDATION01 acceptance](../../artifacts/imp-rebase/VALIDATION01/VALIDATION01_ACCEPTANCE_REPORT.md) (prior "restore exactly" workaround); prior handoffs that preserved these files unstaged |
| **Notes** | No commit, push, deploy, or authority change. The server and mra001 CLI keep persisting to the tracked evidence path by explicit opt-in; ad-hoc/tests now use temp roots and never touch tracked evidence. |

## 2026-09-04 — Branch merged into main (paper profitability observability)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `governance`, `repository` |
| **Summary** | Finished `feat/paper-profitability-observability`: confirmed the branch was already merged upstream via the governed PR workflow (child-repo `origin/main` contains `a5506c1 feat(paper): add profitability observability (#11)` plus PRs #12–#14) and that the parent workspace snapshot under `projects/integrated-market-platform` already includes the full branch content. The stale local `main` ref (45a7b12) was fast-forwarded to the merged upstream state (`origin/main` = 3db07a5); the feature branch is now fully merged into `main`. No source files were changed and no new PR was needed. |
| **Key files** | `docs/engineering/WORK_LOG.md` (this entry); ref-only update: `git branch -f main origin/main` in the nested repository |
| **Tests** | `tools/monorepo_guard.py validate`: passed. Full validation baseline remains green (3462 tests, 0 failures/errors from the prior entry). |
| **Related** | [Monorepo workflow](../../../../docs/MONOREPO_WORKFLOW.md); PRs #11–#14 in the archived child repository |
| **Notes** | The child remote is archived (read-only), so the local `main` update is a tracking-sync, not a push. The parent repo requires no further change; its public snapshot intentionally excludes large artifacts per the publish policy. Local branches `feat/paper-profitability-observability`, `feat/rt01-paper-tracing`, and `feat/unify-paper-trading-chain` were subsequently deleted after confirming they are fully merged into `main`; their disposable worktrees were removed (unique regenerated evidence files preserved under `.local/_worktree-evidence-backup/`). |

## 2026-09-04 — Global validation baseline unblocked

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `validation`, `developer-tooling` |
| **Summary** | Cleared the standing dirty-tree/global validation blocker. Root cause was git's dubious-ownership safety check on the nested repository (owned by `CodexSandboxOffline` while validation runs as `adame`): `git rev-parse --show-toplevel` exited 128 inside `intelligence/live_canary` provenance code, erroring 28 deployment-change-control and release-governance tests. Applied git's documented remediation (`git config --global --add safe.directory` for this repository). No source, test, manifest, or authority files were changed. |
| **Key files** | `docs/engineering/WORK_LOG.md` (this entry); environment-only fix (`git config --global --add safe.directory C:/Users/adame/Desktop/market-trading-platform/integrated-market-platform`) |
| **Tests** | All 47 offline full-tier suites probed individually then orchestrated: `tools/validate.py full` passed with `3462 tests, 43 skipped, 0 failures, 0 errors in 591.442s`; `tools/validate.py changed` passed with `21 tests, 0 skipped, 0 failures, 0 errors`. Previously `intelligence` alone reported 28 errors from the git ownership failure. |
| **Related** | [Developer Operating System](DEVELOPER_OPERATING_SYSTEM.md); prior `GLOBAL VALIDATION BLOCKED` handoffs in this log |
| **Notes** | No commit, push, merge, deploy, or product behavior change. The safe.directory entry is machine-local and reversible (`git config --global --unset-all safe.directory`). |

## 2026-09-04 — RT-01 Paper pipeline tracing

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend/paper`, `observability`, `tests`, `docs` |
| **Summary** | Added bounded Paper RT-01 trace handles and latency profiles, instrumented queue/signal/strategy/internal submission seams, and routed broker-paper submission, polling, cancellation, and reconciliation through the composed Paper provider. Broker partial-fill completion/cancel, restart/replay, idempotency, dry-run preview, and trace linkage are covered by fixture-driven tests. |
| **Key files** | `src/market_platform_foundation/rt01/instrumentation/paper.py`; `src/market_platform_foundation/rt01/{profiles.py,baseline.py,workloads.py,tracer.py}`; `src/market_platform_foundation/{market_data/bounded_queue.py,intelligence/signals/engine.py,intelligence/execution/engine.py,paper/{execution.py,broker_paper.py},strategy/runtime.py}`; `src/market_platform_foundation/ui_api/{paper_projections.py,broker_projections.py,server.py}` |
| **Tests** | Focused RT-01/Paper suites and broker/reconciliation regressions passed during implementation. Changed validation: 2,231 tests, 38 skipped, 0 failures/errors. UI: 428 tests passed, typecheck passed, production build and bundle budget passed at 202.26 KiB gzip. Full validation: 3,482 tests, 48 skipped, 1 pre-existing repository-closure error in the validation domain. |
| **Related** | RT-01 Paper tracing implementation plan (local read-only plan); [Paper decision lifecycle](../architecture/PAPER_DECISION_LIFECYCLE.md); [RT-01 operations](../operations/rt-01/README.md) |
| **Notes** | Work is isolated on the `feat/rt01-paper-tracing` child branch. The original child checkout’s unrelated dirty files remain untouched. The pre-existing `provider-composition` closure scope error (`src/market_platform_foundation/tests`, a nonexistent scope path) was subsequently fixed by removing the stale scope from `POST_BUILD35_SUBSYSTEM_CLASSIFICATION.json`; full validation is no longer blocked by that error. |

## 2026-09-04 — Unified internal Paper trading chain

| Field | Value |
|-------|-------|
| **Area** | `backend/ui`, `paper`, `observability`, `tests` |
| **Summary** | Completed the canonical internal strategy Paper business chain by persisting an immutable order-ready decision, carrying one strategy decision correlation through Paper submission, and exposing a read-only trace that joins opportunity, allocation, risk, order-ready, fill-driven portfolio settlement, prediction settlement state, and cumulative attribution. Manual Paper trace anchors and execution authority boundaries remain backward-compatible. |
| **Key files** | `src/market_platform_foundation/intelligence/execution/{types,serialization}.py`; `src/market_platform_foundation/intelligence/persistence/{repository,memory}.py`; `src/market_platform_foundation/intelligence/persistence/mongo/{repository,schema}.py`; `src/market_platform_foundation/strategy/runtime.py`; `src/market_platform_foundation/ui_api/{paper_projections,strategy_runtime_projections,server}.py`; `ui/src/api/{schemas,endpoints,hooks}.ts`; `ui/src/components/paper/ExecutionTracePanel.tsx`; `tests/intelligence/test_equity_paper_runtime.py`; `tests/platform/test_strategy_runtime_observability.py` |
| **Tests** | Focused and expanded Paper/runtime suites: 113 passed; intelligence domain: 1,150 passed, 25 skipped; full UI suite: 429 passed; UI typecheck/build and Python compilation: pass. Corrected `artifacts/repository-closure/POST_BUILD35_SUBSYSTEM_CLASSIFICATION.json` by removing its stale nonexistent scope path. Manifest domain-core validation: 2,727 tests, 48 skipped, 0 failures/errors; full validation: 3,467 tests, 48 skipped, 0 failures/errors. |
| **Related** | [Paper decision lifecycle](../architecture/PAPER_DECISION_LIFECYCLE.md); [Program status](../platform/PROGRAM_STATUS.md) |
| **Notes** | Broker-paper/live transport, OF-01 parent identity, RT-01 technical span persistence, and autonomous settlement remain deferred. The clean implementation worktree contains only this change set; the original checkout’s unrelated changes were preserved. |

## 2026-09-03 — Paper profitability observability

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend/ui`, `observability`, `tests` |
| **Summary** | Exposed the existing strategy-to-Paper lineage through a read-only, Paper-account-scoped projection and GET API, then mounted a shared profitability observability surface in Paper Research and Paper Portfolio. Strategy attribution remains a non-authoritative cumulative P&L sidecar; settlement inspection does not mutate records and Workspace remains the only submission boundary. |
| **Key files** | `src/market_platform_foundation/ui_api/strategy_runtime_projections.py`; `src/market_platform_foundation/ui_api/server.py`; `src/market_platform_foundation/intelligence/persistence/{repository,memory}.py`; `src/market_platform_foundation/intelligence/persistence/mongo/repository.py`; `ui/src/api/{schemas,endpoints,hooks}.ts`; `ui/src/components/paper-strategy-profitability/`; `ui/src/components/paper-{research,portfolio}/`; `tests/platform/test_strategy_runtime_observability.py` |
| **Tests** | Focused backend observability: 8 passed. UI observability/API contracts: 11 passed. Full UI suite with the repository's lazy-route timeout allowance: 428 passed; typecheck and production build passed with 202.26 KiB initial gzip and bundle budget pass. Manifest-driven changed validation: 2,127 tests, 34 skipped, 0 failures/errors. |
| **Related** | `paper_profitability_observability_1ad70e43.plan.md` (local plan, not committed); [Paper decision lifecycle](../architecture/PAPER_DECISION_LIFECYCLE.md) |
| **Notes** | P6 Shadow Run and live provider campaigns were not run. The strategy repository is explicitly injectable on `ReplayStore`; an unbound repository fails closed in the API/UI. |

## 2026-09-03 — Program documentation reconciliation

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs`, `governance` |
| **Summary** | Reconciled the canonical program roadmap and architecture with accepted XA-04 and XA-05 milestones, removed stale “next” language, and recorded P6 Shadow Run 1 as deferred rather than active. Immutable P6 protocol and run artifacts were preserved; no runtime, ledger, or campaign state was changed. |
| **Key files** | `docs/platform/MASTER_ROADMAP.md`; `docs/platform/MASTER_ARCHITECTURE.md`; `docs/platform/PROGRAM_STATUS.md`; `docs/PROJECT_STATUS.md`; `docs/research/PLATFORMIZATION_ROADMAP.md`; `docs/engineering/WORK_LOG.md` |
| **Tests** | `tools/check_docs_links.py`: 161 governance markdown files checked, pass. `git diff --check`: pass. |
| **Related** | [XA-04 acceptance](../../artifacts/imp-rebase/XA04/XA04_ACCEPTANCE_REPORT.json); [XA-05 acceptance](../../artifacts/imp-rebase/XA05/XA05_ACCEPTANCE_REPORT.json); [P6 protocol](P6_SHADOW_RUN_1_PROTOCOL.md) |
| **Notes** | Historical P6 entries below remain unchanged. P6 is deferred until explicitly reactivated. |

## 2026-09-02 — Windows Operator Center and lifecycle UX

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `platform/lifecycle`, `platform/security`, `ui/control`, `developer-setup` |
| **Summary** | Added an idempotent Windows setup entry point, launcher-owned loopback supervisor, authorized lifecycle/configuration/readiness API contracts, guarded fast-forward update workflow, and canonical browser control center. Provider status remains independent and value-masked; Demo, Paper, Live-observational, and live-execution authority boundaries are unchanged. |
| **Key files** | `SETUP_PLATFORM.cmd`; `tools/platform/bootstrap.py`; `tools/platform/control_service.py`; `tools/platform/local_launcher.py`; `src/market_platform_foundation/ui_api/operator_config.py`; `src/market_platform_foundation/ui_api/operator_projections.py`; `ui/src/components/OperatorControlCenterPage.tsx` |
| **Tests** | Platform manifest worker: 436 tests, 434 passed, 2 expected skips, 0 failures/errors. Operator Control Center: 2/2 passed. UI typecheck and production build passed; bundle budget passed at 201.69 KiB gzip. The combined affected gate completed earlier with 2,222 tests, 34 expected skips, and 0 failures/errors. |
| **Related** | [Local development](LOCAL_DEVELOPMENT.md); [Provider readiness](PROVIDER_READINESS.md); [Mode authority](../architecture/MODE_AUTHORITY.md) |
| **Notes** | Supervisor binds to `127.0.0.1:8767`, verifies process identity before termination, and never resets, stashes, overwrites, or force-updates a dirty checkout. Provider secrets remain in the existing `.env`/`.private` stores with allowlisted atomic writes and masked responses. |

## 2026-09-02 — IMP Developer Operating System

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `developer-tooling`, `validation`, `governance`, `ci`, `docs` |
| **Summary** | Added a thin canonical `tools/imp.py` developer command router, explicit validation pyramid routing, merge-base affected-path support for clean CI checkouts, local telemetry, machine-readable repository metadata, closure-report generation, project hooks, scoped agent guidance, reusable skills, specialized subagent prompts, Bugbot safety instructions, and reusable cancellable CI validation. Existing manifest, worker, backend authority, and Demo/Paper/Live safety boundaries remain authoritative. |
| **Key files** | `tools/imp.py`; `tools/validate.py`; `tools/validation_manifest.json`; `.cursor/hooks.json`; `.cursor/rules/developer-workflow.mdc`; `.cursor/skills/`; `.cursor/agents/`; `.cursor/BUGBOT.md`; `manifests/developer-operating-system.json`; `.github/workflows/imp-python.yml`; `docs/engineering/DEVELOPER_OPERATING_SYSTEM.md`; `docs/engineering/DEVELOPER_OPERATING_SYSTEM_AUDIT.md`; `artifacts/developer-workflow/baseline.json` |
| **Tests** | Focused router/selection/hook tests: 16 passed; routed FAST: 21 passed; docs links: 136 governance markdown files checked; JSON manifests and GitHub workflow YAML parsed successfully; final affected validation: 2,176 tests, 34 skipped, 3 failures, 1 error in 425.317s; final closure FULL: 3,157 tests, 34 skipped, 3 failures, 1 error in 575.479s; UI closure: 421 tests passed, typecheck passed, build passed at 201.18 KiB gzip. Aggregate failures remain the dirty-tree baseline. |
| **Related** | [Developer Operating System](DEVELOPER_OPERATING_SYSTEM.md); [Current workflow audit](DEVELOPER_OPERATING_SYSTEM_AUDIT.md); [validation architecture](VALIDATION_ARCHITECTURE.md) |
| **Notes** | Closure report: `artifacts/developer-workflow/closure-report.json`, status `blocked_by_validation` because the pre-existing dirty tree retains three failures and one error. The first closure attempt exposed and then fixed Windows `npm.cmd` lookup; the final closure report was produced successfully. No commit, push, merge, deploy, reset, or product behavior change was performed. |

## 2026-09-02 — Equity Paper loop validation and handoff

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend`, `architecture`, `observability`, `validation` |
| **Summary** | Completed the final Task 7 handoff for the deterministic equity-like Paper loop. Documented the backend-only persisted lineage path, separate allocation/proposal/risk/order/fill quantities, cumulative actual-fill attribution, independent forecast settlement, structured runtime diagnostics, and reconstruction from authoritative records without introducing UI or duplicate authority. |
| **Key files** | `docs/architecture/PAPER_DECISION_LIFECYCLE.md`; `docs/engineering/OBSERVABILITY.md`; `docs/engineering/WORK_LOG.md`; `task_plan.md`; `findings.md`; `progress.md` |
| **Tests** | Focused pass: phase-6 strategy definitions `7/7`; strategy scanning/match `9/9`; baseline forecasts `5/5`; opportunity/bridge, clustering, comparison/allocation, and allocation persistence `31/31`; Paper execution governance `18/18`; runtime integration `11/11` (including the `equity-paper-runtime-suite` validation worker); strategy attribution `12/12`; portfolio accounting `7/7`; outcome settlement `15/15`; strategy learning `8/8`. `PYTHONPATH=src .venv\Scripts\python.exe -m compileall -q src tests`: pass. `git diff --check`: pass, with a non-failing pre-existing CRLF normalization warning. `tools/check_docs_links.py`: 134 governance markdown files checked, pass. `ui`: `npm test -- --reporter=dot --maxWorkers=1` pass; `npm run build` pass, 1085 modules transformed, initial bundle `201.18 KiB gzip`. `tools/validate.py changed`: blocked by dirty baseline (`1232 tests, 9 skipped, 1 failure, 91 errors in 530.542s`). `tools/validate.py full`: blocked by dirty baseline (`2209 tests, 9 skipped, 1 failure, 92 errors in 734.902s`). |
| **Related** | `equity-paper-loop_5c6b4402.plan.md` (local plan, not committed); [Paper decision lifecycle](../architecture/PAPER_DECISION_LIFECYCLE.md); [Observability](OBSERVABILITY.md) |
| **Notes** | Final status is `FOCUSED CLOSED / GLOBAL VALIDATION BLOCKED`. Aggregate failures span `finviz`, `platform`, `intelligence`, `ui1`, `ui2`, and `validation` and are retained as the pre-existing dirty-tree/global validation classification. No commit, push, deploy, reset, clean, plan-file edit, secret, UI authority, allocation authority, attribution authority, or unfinished diagnostic was introduced. |

## 2026-09-02 — Bounded governed strategy learning boundary

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend/strategy`, `tests` |
| **Summary** | Added an immutable, reference-preserving learning observation/join boundary over the existing StrategyDefinition identity, StrategyMatch, ForecastV1, OutcomeV1, and StrategyAttributionV1 records. Versioned policy gates enforce point-in-time lineage, settled/labelable prediction outcomes, evidence allow-lists, minimum samples, account/mode isolation, and optional attributed trading sidecars while preserving independent prediction and trading quality. |
| **Key files** | `src/market_platform_foundation/strategy/learning.py`; `src/market_platform_foundation/strategy/__init__.py`; `tests/intelligence/test_strategy_learning.py` |
| **Tests** | Focused learning boundary `8/8`; StrategyMatch `5/5`; StrategyDefinition `3/3`; StrategyAttribution `7/7`; compileall, package export, and new/modified-file whitespace checks passed. `tools/validate.py changed` completed with the dirty-tree aggregate result: `1206 tests, 9 skipped, 1 failure, 91 errors` across `finviz`, `platform`, `intelligence`, `ui1`, and `validation`. |
| **Related** | `C:/Users/adame/.cursor/plans/imp_universal_opportunity_23f67055.plan.md` (read-only) |
| **Notes** | Research handoffs are fixed non-promotional seeds requiring ResearchHypothesisV1, ExperimentManifestV1, validation, locked holdout, contamination, shadow, and PromotionEngine authorities; they cannot promote, execute, or change a champion. No frozen contract, PromotionEngine, plan, BUILD/TD record, UI, ranking, allocation, risk, broker, or unrelated dirty file was changed. |

## 2026-09-02 — Durable strategy attribution boundary

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend/portfolio`, `backend/persistence`, `tests` |
| **Summary** | Added an immutable strategy-to-realized-P&L attribution sidecar that retains virtual allocation slices and explicit fill lineage independently of broker-netted positions, risk decisions, and the authoritative portfolio ledger. Deterministic canonical identity, integer cost-basis accounting, account/mode/PIT guards, explicitly labeled prediction/trading outcomes, and in-memory/Mongo persistence support durable joins without inferring attribution from net positions. |
| **Key files** | `src/market_platform_foundation/portfolio/attribution.py`; `src/market_platform_foundation/portfolio/__init__.py`; `src/market_platform_foundation/intelligence/persistence/{codec,memory,repository}.py`; `src/market_platform_foundation/intelligence/persistence/mongo/{repository,schema}.py`; `src/market_platform_foundation/intelligence/contracts/common.py`; `tests/platform/test_strategy_attribution.py` |
| **Tests** | Focused attribution `7/7`; authoritative portfolio ledger `6/6`; intelligence contracts `18/18`; Mongo schema bootstrap `8/8`; StrategyMatch `5/5`; compileall and tracked/new-file whitespace checks passed. `tools/validate.py changed` reached `1198 tests, 9 skipped` but reported `1 failure, 91 errors` from the pre-existing dirty repository baseline and direct-script package import assumptions. |
| **Related** | `C:/Users/adame/.cursor/plans/imp_universal_opportunity_23f67055.plan.md` (read-only) |
| **Notes** | No plan, BUILD/TD record, commit, reset, checkout, order/risk decision, authoritative ledger, or unrelated dirty file was changed. |

## 2026-09-02 — Account-scoped opportunity comparison and allocation

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend/intelligence/opportunity`, `tests` |
| **Summary** | Added immutable, bounded account/mode/PIT-scoped comparison inputs and explicit comparison vectors over OpportunityV1 plus required universal economic sidecars. Added deterministic one-expression-per-thesis comparison, duplicate/exclusion reasons, observability counters, and an independent capital allocator that emits capital intents only; risk and execution authorities remain unchanged. |
| **Key files** | `src/market_platform_foundation/intelligence/opportunity/comparison.py`; `src/market_platform_foundation/intelligence/opportunity/__init__.py`; `tests/intelligence/test_opportunity_comparison.py` |
| **Tests** | Focused comparison/allocation `8/8`; thesis clustering compatibility `8/8`; compileall passed; focused whitespace checks produced no diagnostics. `tools/validate.py changed` completed with the pre-existing dirty-tree baseline result: `1151 tests, 9 skipped, 1 failure, 102 errors`. |
| **Related** | `C:/Users/adame/.cursor/plans/imp_universal_opportunity_23f67055.plan.md` (read-only) |
| **Notes** | Changed validation remains blocked by the existing `portfolio.attribution` circular import and other dirty-tree suite failures. No frozen contracts, BUILD/TD records, plan files, UI, proposals, risk decisions, orders, broker calls, or unrelated dirty files were modified. |

## 2026-09-02 — Bounded opportunity thesis clustering

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend/intelligence/opportunity`, `tests` |
| **Summary** | Added an immutable, account/mode/PIT-scoped thesis clustering projection over OpportunityV1, StrategyMatch, and optional universal economic sidecars. Deterministic explicit/fallback thesis identities group duplicate strategies and expressions while preserving lineage; the duplicate view only marks exposure and does not rank, allocate, or collapse opportunities. |
| **Key files** | `src/market_platform_foundation/intelligence/opportunity/clustering.py`; `src/market_platform_foundation/intelligence/opportunity/__init__.py`; `tests/intelligence/test_opportunity_clustering.py` |
| **Tests** | Focused clustering `8/8`; bridge/sidecar regressions `7/7`; StrategyMatch regressions `5/5`; compileall and changed-file whitespace checks passed. |
| **Related** | `C:/Users/adame/.cursor/plans/imp_universal_opportunity_23f67055.plan.md` (read-only) |
| **Notes** | No frozen V1 contracts, BUILD/TD records, plan files, persistence, ranking, allocation, UI, execution, or unrelated dirty files were changed. |

## 2026-09-02 — Universal economic sidecar and opportunity bridge

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend/intelligence/opportunity`, `backend/persistence`, `tests` |
| **Summary** | Added an immutable, dimension-preserving universal economic-assessment sidecar with integer minor-unit money, explicit ns/bps/probability semantics, versioned assumptions, liquidity/capacity, uncertainty, factor exposure, and account actionability. Added a strict SHARED P4 adapter and a canonical MATCHED StrategyMatch bridge that delegates to the existing OpportunityEngine and preserves sidecar/match lineage without changing V1 authorities. |
| **Key files** | `src/market_platform_foundation/intelligence/opportunity/{economic_assessment,p4_adapter,bridge}.py`; `src/market_platform_foundation/intelligence/opportunity/{__init__,identity,serialization,types}.py`; `src/market_platform_foundation/intelligence/persistence/{memory,repository}.py`; `src/market_platform_foundation/intelligence/persistence/mongo/repository.py`; `tests/intelligence/test_universal_opportunity.py` |
| **Tests** | Focused universal sidecar/bridge `7/7`; opportunity and contract regression `54/54`; persistence/strategy regression `31/31`; compileall and bounded `git diff --check` passed. Full changed validation remains blocked by the pre-existing dirty-tree platform baseline (`437 tests, 3 skipped, 0 failures, 4 errors`). |
| **Related** | `C:/Users/adame/.cursor/plans/imp_universal_opportunity_23f67055.plan.md` (read-only) |
| **Notes** | No BUILD/TD records, plan file, commit, reset, checkout, clustering, ranking, allocation, UI, multi-asset accounting, or execution authority was changed. |

## 2026-09-02 — Bounded universal strategy scanning

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend/strategy`, `tests` |
| **Summary** | Added a deterministic one-pass universal strategy scanner with explicit point-in-time universes, capability/context snapshots, Stage A eligibility, Stage B cheap screening, bounded evaluator budgets, trigger metadata, account/mode scope, and immutable StrategyMatch persistence. Coarse screen/evaluator failures remain diagnostics and counters without fabricating decision records. |
| **Key files** | `src/market_platform_foundation/strategy/scanning.py`; `src/market_platform_foundation/strategy/__init__.py`; `tests/intelligence/test_strategy_scanning.py` |
| **Tests** | Focused scanner `3/3`; StrategyMatch contract `5/5`; compileall and focused whitespace checks passed. Repository changed validation was run; final baseline result is reported in the handoff. |
| **Related** | `C:/Users/adame/.cursor/plans/imp_universal_opportunity_23f67055.plan.md` (read-only) |
| **Notes** | No BUILD/TD records, plan file, commit, reset, checkout, UI, economics, ranking, allocation, daemon, or execution behavior was changed. |

## 2026-09-02 — Immutable StrategyMatch contract

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend/intelligence`, `tests` |
| **Summary** | Added an immutable typed `StrategyMatch` evaluation record with explicit MATCHED, REJECTED, ABSTAINED, UNAVAILABLE, and EXPIRED dispositions. Canonical identity/serialization and immutable repository persistence retain source references, condition outcomes, reasons, capability/quality state, context, validity, and lineage without adding scanner or execution behavior. |
| **Key files** | `src/market_platform_foundation/intelligence/contracts/strategy_match.py`; `src/market_platform_foundation/intelligence/contracts/{__init__,common}.py`; `src/market_platform_foundation/intelligence/persistence/{codec,memory,repository}.py`; `src/market_platform_foundation/intelligence/persistence/mongo/{repository,schema}.py`; `tests/intelligence/test_strategy_match.py`; `tests/intelligence/test_persistence_mongo_schema.py` |
| **Tests** | Focused StrategyMatch `5/5`; existing intelligence contracts `18/18`; Mongo schema `8/8`; validator worker persistence selector `1/1`; compileall and tracked-file whitespace check passed. `tools/validate.py changed` completed with `1170 tests, 9 skipped, 1 failure, 90 errors`; failures were across dirty-tree `finviz`, `platform`, `intelligence`, `ui1`, and `validation` suites. |
| **Related** | `C:/Users/adame/.cursor/plans/imp_universal_opportunity_23f67055.plan.md` (read-only) |
| **Notes** | No BUILD/TD records, plan files, commits, resets, checkouts, scanner orchestration, economics, ranking, allocation, UI, or execution behavior were changed. |

## 2026-09-02 — Portfolio fill accounting and settlement scheduler correctness

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend/portfolio`, `backend/intelligence`, `tests` |
| **Summary** | Corrected authoritative fill accounting with signed net-position cost basis, including weighted scale-in/scale-out, long/short closes, and reversals. Due unsettled prediction entries now report `SettlementStatus.DUE` through the scheduler. |
| **Key files** | `src/market_platform_foundation/portfolio/ledger.py`; `src/market_platform_foundation/portfolio/reconciliation.py`; `src/market_platform_foundation/portfolio/__init__.py`; `src/market_platform_foundation/paper/ledger.py`; `src/market_platform_foundation/intelligence/outcomes/scheduler.py`; `tests/platform/test_portfolio_ledger_accounting.py` |
| **Tests** | Focused accounting/scheduler unittest `6/6`; paper compatibility `74/74`; ledger durability `9/9`; reconciliation `18/18`; compileall passed; phase7 validation worker `3/3`; focused manifest selectors `6/6`. `validate.py changed` and `validate.py domain core` remain blocked by unrelated dirty-tree import/auth failures (`1165 tests, 9 skipped, 1 failure, 90 errors`; `431 tests, 3 skipped, 4 errors`). |
| **Related** | `C:/Users/adame/.cursor/plans/imp_universal_opportunity_23f67055.plan.md` (read-only) |
| **Notes** | No BUILD/TD records or plan files were modified. Existing unrelated dirty-tree changes were preserved. |

## 2026-09-01 — Typed strategy identity/catalog boundary

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend/strategy`, `tests` |
| **Summary** | Added an immutable, typed `StrategyDefinition` with versioned optional taxonomy fields for family, style, asset class, and timeframe. Legacy dictionary strategy specs retain their prior identity-hash and serialization behavior when taxonomy is absent, while preregistration, interpretation, and evaluation explicitly accept either representation. |
| **Key files** | `src/market_platform_foundation/strategy/{strategy_spec,preregistration,interpretation,evaluation,__init__}.py`; `tests/phase6/test_strategy_definition.py` |
| **Tests** | Focused typed strategy tests `3/3`; complete strategy subset `7/7`; strategy compile check passed. Repository `tools/validate.py changed` ran `953` tests with `1` failure and `7` errors in unrelated dirty-tree suites (`finviz`, `platform`, `ui1`, `validation`). |
| **Related** | `C:/Users/adame/.cursor/plans/imp_universal_opportunity_23f67055.plan.md` (read-only) |
| **Notes** | No BUILD/TD records, plan file, commit, reset, checkout, or unrelated changes were modified. |

## 2026-09-01 — Multi-source foundation extension and identity hardening

| Field | Value |
|-------|-------|
| **Status** | `in-progress` |
| **Area** | `backend/providers`, `tests`, `docs` |
| **Summary** | Added bounded, structured, deeply immutable provider extensions across observations, envelopes, and normalization, and made raw content identity source-scoped by provider and source instance. Recognized credential patterns remain redacted; opaque strings without markers are documented as caller-prohibited secret input. |
| **Key files** | `src/market_platform_foundation/providers/{observations,raw_records}.py`; `tests/providers/test_multi_source_foundation.py`; foundation provider docs, ADR, and plan |
| **Tests** | Focused foundation `25/25`; complete providers `125/125` after this change. Full/changed validation remains blocked by unrelated dirty-tree suites; current counts are recorded in the plan. |
| **Related** | [implementation plan](../superpowers/plans/2026-09-01-multi-source-data-foundation.md), [ADR-0009](../architecture/adr/0009-multi-source-data-integration-foundation.md) |
| **Notes** | No commit, push, reset, checkout, stash, or unrelated-file overwrite performed. |

## 2026-09-01 — Multi-source foundation remediation

| Field | Value |
|-------|-------|
| **Status** | `in-progress` |
| **Area** | `backend/providers`, `tests`, `docs` |
| **Summary** | Remediated foundation contract gaps without changing execution lifecycle or unrelated provider work. Envelopes now preserve explicit clocks/acquisition/revision lineage; mappings fail closed; raw and normalized records are deeply immutable; planner and reconciliation policies are operational and deterministic. |
| **Key files** | `src/market_platform_foundation/providers/{identity,observations,raw_records,planner,reconciliation,registry,storage}.py`; `tests/providers/test_multi_source_foundation.py`; foundation ADR/provider docs and implementation plan |
| **Tests** | Focused foundation `23/23`; complete providers `123/123`; IBKR `47/47`; news `5/5`; provider-readiness `6/6`; compileall and linter passed. Changed/full repository validation remains blocked by unrelated dirty-tree baseline failures documented in the plan. |
| **Related** | [implementation plan](../superpowers/plans/2026-09-01-multi-source-data-foundation.md), [ADR-0009](../architecture/adr/0009-multi-source-data-integration-foundation.md) |
| **Notes** | No commit, push, reset, checkout, deployment, or unrelated-file overwrite performed. |

## 2026-09-01 — Multi-source data integration foundation

| Field | Value |
|-------|-------|
| **Status** | `in-progress` |
| **Area** | `backend/providers`, `docs`, `tests` |
| **Summary** | Added a stdlib-only provider foundation for operational capability registration, namespaced instrument identity, immutable raw lineage, explicit PIT observation clocks, deterministic planning, bounded storage boundaries, and multi-source reconciliation. Existing runtime composition, paper execution, mode authority, account isolation, and Live execution block were left unchanged. |
| **Key files** | `src/market_platform_foundation/providers/{registry,identity,observations,raw_records,planner,reconciliation,storage,testing}.py`; `tests/providers/test_multi_source_foundation.py`; `docs/providers/MULTI_SOURCE_DATA_FOUNDATION.md`; `docs/architecture/adr/0009-multi-source-data-integration-foundation.md`; `docs/superpowers/plans/2026-09-01-multi-source-data-foundation.md` |
| **Tests** | Focused foundation `13/13`; complete providers `111/111`; fast validation `21` passed; docs links `134` files checked; UI `421/421`, typecheck, and build passed. Full/changed validation remains blocked by existing adjacent dirty-tree finviz/platform/intelligence/ui1/ui2/validation failures; exact evidence is in the plan. |
| **Related** | [implementation plan](../superpowers/plans/2026-09-01-multi-source-data-foundation.md), [ADR-0009](../architecture/adr/0009-multi-source-data-integration-foundation.md) |
| **Notes** | No commit, push, deploy, reset, checkout, or unrelated user-change overwrite performed. Existing IBKR/news/Finviz/readiness/evidence work remains preserved. |

## 2026-09-01 — P6 Shadow Run 1 duplicate-bucket operational check

| Field | Value |
|-------|-------|
| **Status** | `in-progress` |
| **Area** | `shadow`, `tools/research`, `artifacts/shadow-run-1` |
| **Summary** | Completed another 120-second live Moomoo/OpenD collection increment. No new decision rows were emitted because the observed buckets were already recorded; append-only deduplication held, with zero recorder errors. |
| **Key files** | `.local/shadow/experiment.sqlite3`, `.local/shadow/captures/CAP-BIYA-SR1-20260901.jsonl`, `artifacts/shadow-run-1/P6_ACCEPTANCE_MATRIX.json` |
| **Tests** | Acceptance refreshed with environment variables cleared: 15/15 pass; reconciliation 5/5, 0 unreconciled |
| **Related** | [completion](../superpowers/plans/2026-09-01-p6-shadow-run-1-forward-validation-completion.md), [SOP](sops/FORWARD_SHADOW_VALIDATION.md) |
| **Notes** | Stopping rule remains unmet at 12/65 scheduled grid opportunities. |

## 2026-09-01 — P6 acceptance source reproducibility hardening

| Field | Value |
|-------|-------|
| **Status** | `in-progress` |
| **Area** | `shadow`, `tools/research`, `tests` |
| **Summary** | Acceptance now derives P6-AC-002 from the immutable run’s `live_observation` reference and non-empty sealed capture, rather than requiring live environment variables at evaluation time. This keeps acceptance reproducible and prevents a valid stored run from being incorrectly blocked offline. |
| **Key files** | `tools/research/run_shadow_run.py`, `tests/platform/test_shadow_run1_cli.py` |
| **Tests** | Complete `test_shadow_run1*.py` subset — 59 tests passed; acceptance regenerated with environment variables cleared — 15/15 pass |
| **Related** | [completion](../superpowers/plans/2026-09-01-p6-shadow-run-1-forward-validation-completion.md), [SOP](sops/FORWARD_SHADOW_VALIDATION.md) |
| **Notes** | P6 remains `IN_PROGRESS_EVIDENCE_COLLECTION`; stopping rule is not met. |

## 2026-09-01 — P6 Shadow Run 1 live forward evidence (additional bounded session)

| Field | Value |
|-------|-------|
| **Status** | `in-progress` |
| **Area** | `shadow`, `tools/research`, `artifacts/shadow-run-1` |
| **Summary** | Completed an additional 120-second live Moomoo/OpenD observation session for BIYA on the existing preregistered run. The run now contains 10 ACTUAL_FORWARD model outcomes and 10/10 provenance-complete decisions with zero recorder errors; the stopping rule remains unmet. |
| **Key files** | `.local/shadow/experiment.sqlite3`, `.local/shadow/captures/CAP-BIYA-SR1-20260901.jsonl`, `artifacts/shadow-run-1/P6_ACCEPTANCE_MATRIX.json` |
| **Tests** | Complete `test_shadow_run1*.py` subset — 58 tests passed; `git diff --check` clean apart from CRLF normalization warning |
| **Related** | [completion](../superpowers/plans/2026-09-01-p6-shadow-run-1-forward-validation-completion.md), [SOP](sops/FORWARD_SHADOW_VALIDATION.md) |
| **Notes** | Acceptance remains `IN_PROGRESS_EVIDENCE_COLLECTION`; current scheduled grid count is 12/65. |

## 2026-09-01 — P6 legacy provenance reconciliation (P6-AC-005 closure)

| Field | Value |
|-------|-------|
| **Status** | `in-progress` |
| **Area** | `shadow`, `tools/research` |
| **Summary** | Added `reconcile_shadow_provenance.py` to map 5 immutable pre-fix decisions to sealed capture buckets without mutating store rows. Wired acceptance to count reconciled IDs; fixed P6-AC-010 default matrix emission. Honest disposition remains `IN_PROGRESS_EVIDENCE_COLLECTION` (stopping rule not met). |
| **Key files** | `tools/research/reconcile_shadow_provenance.py`, `tools/research/run_shadow_run.py`, `artifacts/shadow-run-1/LEGACY_PROVENANCE_RECONCILIATION.json`, `tests/platform/test_shadow_run1_provenance_reconcile.py` |
| **Tests** | `test_shadow_run1_provenance_reconcile`, `test_shadow_run1_acceptance` — pass |
| **Related** | [completion](../superpowers/plans/2026-09-01-p6-shadow-run-1-forward-validation-completion.md), [SOP](sops/FORWARD_SHADOW_VALIDATION.md) |
| **Notes** | P6 not CLOSED until stopping rule + close/label/report cycle completes. |

## 2026-09-01 — P6 Shadow Run 1 forward-validation evidence phase (preregistration)

| Field | Value |
|-------|-------|
| **Status** | `in-progress` |
| **Area** | `shadow`, `docs`, `tools/research` |
| **Summary** | Preregistered P6 Shadow Run 1 protocol, source availability audit, acceptance evaluator (`shadow/acceptance.py`, CLI `acceptance` subcommand), operator SOP, and reconciled project status docs. Initialized resumable run machinery on Build-35 baseline; forward observations **blocked** (Moomoo/OpenD not configured). Honest disposition: IN_PROGRESS_EVIDENCE_COLLECTION. |
| **Key files** | `artifacts/shadow-run-1/*`, `docs/engineering/P6_SHADOW_RUN_1_PROTOCOL.md`, `docs/engineering/sops/FORWARD_SHADOW_VALIDATION.md`, `src/market_platform_foundation/shadow/acceptance.py`, `tools/research/run_shadow_run.py`, `tests/platform/test_shadow_run1_acceptance.py`, `docs/PROJECT_STATUS.md`, `docs/product/PRODUCT_BACKLOG.md`, `docs/research/PLATFORMIZATION_ROADMAP.md` |
| **Tests** | `test_shadow_run1_acceptance`; targeted shadow suite; `validate.py changed` |
| **Related** | [P6 protocol](P6_SHADOW_RUN_1_PROTOCOL.md), [completion](../superpowers/plans/2026-09-01-p6-shadow-run-1-forward-validation-completion.md) |
| **Notes** | Do not mark P6 CLOSED until ACTUAL_FORWARD observation window completes. Fixture/replay remains infrastructure proof only. |

## 2026-09-01 — P6 Shadow Run 1 live forward evidence (session 1)

| Field | Value |
|-------|-------|
| **Status** | `in-progress` |
| **Area** | `shadow`, `tools/research`, `artifacts/shadow-run-1` |
| **Summary** | Live Moomoo/OpenD forward collection on default-store run `SHRUN-00C5…`: 5 `ABSTAINED_MODEL` decisions, 0 recorder errors. Pinned green `validate.py full` receipt (P6-AC-011), `PREFLIGHT_EVIDENCE.json`, acceptance matrix 15/15 with honest `IN_PROGRESS_EVIDENCE_COLLECTION`. Fixed SQLite thread safety, `event_type` envelope handling, validation flakes, and abstention provenance (`decision_time_ns` / `available_time_ns`) for grid counting. |
| **Key files** | `collect_shadow_observations.py`, `shadow/recording.py`, `shadow/experiment.py`, `PREFLIGHT_EVIDENCE.json`, `P6_VALIDATION_RECEIPT.json` |
| **Tests** | `test_shadow_run1_*`; `validate.py full` green |
| **Related** | [completion](../superpowers/plans/2026-09-01-p6-shadow-run-1-forward-validation-completion.md), [PR #8](https://github.com/AdamEddahmouni/integrated-market-intelligence-platform/pull/8) |
| **Notes** | Stopping rule not met (0 scheduled grid opportunities on legacy abstention rows; recorder fix applies to new decisions). |

## 2026-09-01 — TD-005 operator authentication and account-scoped authorization

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend/security`, `ui_api`, `ui/auth`, `docs` |
| **Summary** | Closed TD-005 by implementing LOOPBACK_TRUST (default) and ENFORCED auth modes, principal registry, session API, route capability + OperationalIdentity account ACL enforcement, security foundation wiring (redaction, leak audit), and frontend AuthProvider/login gate. ADR-0008 records topology and P0 decision 6 local amendment. |
| **Key files** | `platform/security/auth_config.py`, `principals.py`, `sessions.py`, `access_control.py`, `route_policy.py`, `ui_api/request_auth.py`, `ui_api/auth_projections.py`, `ui_api/server.py`, `ui/src/auth/*`, `fixtures/auth/principals.json`, `tests/platform/test_td005_auth_enforcement.py` |
| **Tests** | `test_td005_auth_enforcement`; `test_security_foundations_p5` updated; `validate-python`; `validate-ui` |
| **Related** | [ADR-0008](../architecture/adr/0008-operator-authentication-authorization.md), [ADR-0007](../architecture/adr/0007-operational-account-identity.md) |
| **Notes** | OIDC/hosted IdP deferred. Set `IMP_AUTH_ENFORCEMENT_MODE=ENFORCED` and `IMP_AUTH_PRINCIPALS_PATH` for local multi-user. |

## 2026-09-01 — TD-003 multi-account snapshot architecture and state isolation

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend`, `ui/api`, `docs` |
| **Summary** | Closed TD-003 by introducing `OperationalIdentity`, account discovery (`GET /accounts`), account-scoped canary snapshots/reconciliation, `AccountSnapshotCache` with per-account refresh locks, demo/paper portfolio view isolation, and frontend account-aware query keys. ADR-0007 records the decision. |
| **Key files** | `operational_identity.py`, `account_registry.py`, `account_snapshot_cache.py`, `canary_projections.py`, `paper_projections.py`, `broker_projections.py`, `server.py`, `ui/src/api/hooks.ts`, `ui/src/api/liveCanary.ts`, `tests/platform/test_operational_identity.py`, `tests/platform/test_account_isolation.py` |
| **Tests** | `test_operational_identity 5 passed`; `test_account_isolation 5 passed`; `ui vitest`; `validate.py changed/full` |
| **Related** | [ADR-0007](../architecture/adr/0007-operational-account-identity.md), [completion](../superpowers/plans/2026-09-01-td-003-multi-account-snapshot-completion.md) |
| **Notes** | TD-004 unchanged (OpenD unavailable). No Live execution added. Moomoo adapter conforms to identity contract at interface level only. |

## 2026-09-01 — Operational hardening, data provenance, CI closure, repository consolidation

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend` (lane_provenance, server), `ui` (provenance, query keys, Live strip, primitives), `pipelines/stock_data`, `docs`, `ci` |
| **Summary** | Closed TD-002 (lane `lane_provenance` envelope on workspace APIs + `laneProvenance.ts` + ADR-0006), partially closed TD-003 (mode-scoped `liveCanarySnapshot` keys), closed TD-006 (CI typecheck+test+build). Renamed `pipelines/stock_data/src/ui` → `operator_console`. Fixed `WorkspaceModuleNav` circular type. Added smoke tests. |
| **Key files** | `lane_provenance.py`, `server.py`, `laneProvenance.ts`, `hooks.ts`, `LiveLaneOperationalStrip.tsx`, `LaneModeContextPanel.tsx`, `operator_console/`, `imp-validate.yml`, `tsconfig.typecheck.json`, ADR-0006, completion record |
| **Tests** | `ui: vitest 417 passed`; `ui: typecheck pass`; `ui: build pass (199.89 KiB gzip)`; `test_lane_provenance 4 passed`; `test_repository_closure OK` |
| **Related** | [completion](../superpowers/plans/2026-09-01-operational-hardening-completion.md) |
| **Notes** | TD-003 per-broker lane snapshots remain backend-blocked. TD-004 unchanged. Playwright E2E deferred — Vitest integration smoke sufficient. |

## 2026-09-01 — UI completion & productization pass

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui` (shared primitives, portfolio, settings, discover, trace, diagnostics, workspace routes), `backend` (paper order-history API), `docs` |
| **Summary** | Major UI productization: shared `LoadingState`/`EmptyState`/`PageHeader`/`JsonDetailPanel`/`InstrumentSelectionEmpty`; canonical lane + mode metadata registries; Paper order history server pagination (`GET /paper/order-history`) with infinite-scroll UI (TD-001 closed); instrument-selection dead-ends fixed; raw JSON operational surfaces structured; tests and validation updated. |
| **Key files** | Created: `ui/src/components/shared/*`, `ui/src/styles/shared-ui.css`, `workspace-module-shared/laneRegistry.ts`, `mode-session/modeMetadata.ts`, `ui/src/test/paperOrderHistoryQueryMock.ts`, completion record. Modified: `paper_projections.py`, `server.py`, `PaperOrderHistory*`, `OperatorSettingsPage`, `DiscoverObservability`, `ProviderHealthPanel`, `ExecutionTracePanel`, `WorkspaceEvidenceDrawer`, `WorkspaceIndex`, disclosure/institutional routes, `WorkspaceModuleNav`, `ModeLauncher`, `App.tsx`, tests, `PROJECT_STATUS.md`, `TECH_DEBT.md`. |
| **Tests** | `ui: vitest 407 passed`; `build: pass (199.83 KiB gzip initial)`; `validate.py changed: 860 passed`; `validate.py full: 2970 passed` |
| **Related** | [completion](../superpowers/plans/2026-09-01-ui-completion-productization-completion.md), TD-001 |
| **Notes** | InspectorPanel remains raw JSON (developer inspect). Full PageHeader migration across all routes optional follow-up. |

## 2026-09-01 — Project operating system / engineering governance upgrade

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs`, `AGENTS`, `.cursor/rules`, `tools`, `.github`, `README` |
| **Summary** | Comprehensive governance upgrade: authoritative doc map (`docs/README.md`), architecture (mode authority, Paper lifecycle, data contracts, ADRs), engineering handbook/guides/SOPs/checklists/templates/prompts, AI agent guidance, security/runbook/status/glossary, overhauled AGENTS.md + scoped agent files + Cursor rules, docs link checker, CI UI test/build job, fixed WORK_LOG broken links, completion record. |
| **Key files** | Created: `docs/README.md`, `docs/PROJECT_STATUS.md`, `docs/GLOSSARY.md`, `docs/architecture/*`, `docs/engineering/*` (handbook, guides, SOPs, etc.), `docs/operations/RUNBOOK.md`, `docs/product/PRODUCT_BACKLOG.md`, `ui/AGENTS.md`, `paper/AGENTS.md`, `tools/check_docs_links.py`, `.github/pull_request_template.md`, `.github/ISSUE_TEMPLATE/*`, `.cursor/rules/*.mdc`. Modified: `AGENTS.md`, `README.md`, `WORK_LOG.md` (link fixes), `imp-validate.yml`, `validation_manifest.json`, `POST_BUILD35_SUBSYSTEM_CLASSIFICATION.json`, completion record headers. |
| **Tests** | `ui`: vitest **403 passed**; `npm run build` pass (**199.17 KiB gzip**); `check_docs_links.py` pass (126 files); closure audit test pass; `validate.py changed` **859 passed**; `validate.py full` **2969 passed** |
| **Related** | [OS completion](../superpowers/plans/2026-09-01-project-operating-system-completion.md), [source time completion](../superpowers/plans/2026-09-01-paper-decision-source-time-completion.md) |
| **Notes** | No CHANGELOG/CODEOWNERS. Historical BUILD specs and completion records preserved with forward links. MIGRATION SOP omitted (no migration framework). |

---

## 2026-09-01 — Paper decision source time provenance

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui/paper`, `ui/paper-now`, `ui/paper-workspace`, `ui/paper-portfolio`, `backend/paper`, `backend/ui_api`, `ui/tests`, `docs` |
| **Summary** | Populated trustworthy `source_time` across the full Paper decision lifecycle: optional `AttentionItem.surfaced_time` (epoch ns) from backend projections; `resolvePaperDecisionSourceTime` helper; `sourceContext.source_time` set once at handoff; immutable through preview/submit/intent/projection; semantic labels in cockpit, Portfolio, and execution trace. Legacy records without source time remain valid. |
| **Key files** | Created: `resolvePaperDecisionSourceTime.ts`, `paperSourceTimestamp.ts`, tests, `docs/superpowers/plans/2026-09-01-paper-decision-source-time-completion.md`. Modified: `paperOrderDraft.ts`, `paperDecisionSourceSnapshot.ts`, `OrderTicket.tsx`, `buildPaperHandoffModel.ts`, `PaperHandoffPanel.tsx`, `PaperPersistedSourceContextPanel.tsx`, `schemas.ts`, `attention_item.schema.json`, `ui_api/projections.py`, `donor_bridge/projections.py`, `decision_source.py`, fixtures/tests, completion records. |
| **Tests** | `ui`: vitest **403 passed** (73 files); `npm run build` pass; initial bundle **199.17 KiB gzip**; `validate.py changed` **859 passed**; `validate.py full` **2969 passed** |
| **Related** | [Source time completion](../superpowers/plans/2026-09-01-paper-decision-source-time-completion.md), [Source snapshot completion](../superpowers/plans/2026-08-31-paper-decision-source-snapshot-completion.md) |
| **Notes** | Timestamp units: epoch ns (backend/`surfaced_time`); values ≤1e15 treated as ms in UI formatters. Handoff fallback only when canonical source time absent. No decay/expiry logic. Demo/Live unchanged. |

---

## 2026-08-31 — Paper decision-source snapshot persistence

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui/paper-portfolio`, `ui/paper`, `backend/paper`, `ui/tests`, `docs` |
| **Summary** | Persisted bounded `decision_source_snapshot` on Paper order intents (attention headline/tier/reasons; lane module identity), projected through `project_orders()` into Portfolio history and execution trace. Draft `sourceContext` maps to validated request snapshot; correlation/provenance identity unchanged; mismatch fails closed on write and degrades safely on read. Historical UI labeled *Source context at decision handoff*. |
| **Key files** | Created: `paper/decision_source.py`, `paper/paperDecisionSourceSnapshot.ts`, `PaperPersistedSourceContextPanel.tsx`, tests, `docs/superpowers/plans/2026-08-31-paper-decision-source-snapshot-completion.md`. Modified: `contracts.py`, `execution.py`, `broker_paper.py`, `ledger.py`, `paper_projections.py`, `paperOrderDraft.ts`, `paperDecisionProvenance.ts`, `paperOrderHistoryModel.ts`, `PaperOrderHistoryRow.tsx`, `ExecutionTracePanel.tsx`, `schemas.ts`, `paper-portfolio.css`, completion records. |
| **Tests** | `ui`: vitest **387 passed** (71 files); `npm run build` pass; initial bundle **199.17 KiB gzip**; `validate.py changed` **858 passed**; `validate.py full` **2968 passed** |
| **Related** | [Source snapshot completion](../superpowers/plans/2026-08-31-paper-decision-source-snapshot-completion.md), [Portfolio history](../superpowers/plans/2026-08-31-paper-portfolio-decision-history-completion.md) |
| **Notes** | `source_time` reserved but not populated (AttentionItem lacks timestamp). Lane snapshots omit headline unless added to draft later. Manual/legacy orders unchanged. No analytics attribution. |

---

## 2026-08-31 — Paper Portfolio operational decision history

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui/paper-portfolio`, `ui/paper`, `backend/paper`, `ui/tests`, `docs` |
| **Summary** | Turned Paper Portfolio into the operational review surface for simulated decisions: backend `project_orders()` now preserves optional `correlation_id` and intent fields; frontend adds persisted provenance parser (lane/attention/manual/unknown with client-order default semantics), operational order history tables with badges/filters/metrics/expandable details, and always-available trace navigation aligned with `ExecutionTracePanel`. Demo/Live portfolio unchanged. |
| **Key files** | Created: `paper-portfolio/paperDecisionProvenance.ts`, `paperOrderHistoryModel.ts`, `paperOrderStatusPresentation.ts`, `PaperOrderHistory*.tsx`, `PaperDecisionProvenanceBadge.tsx`, tests, `docs/superpowers/plans/2026-08-31-paper-portfolio-decision-history-completion.md`. Modified: `paper/ledger.py`, `PaperPortfolioPage.tsx`, `PaperPortfolioObservability.tsx`, `ExecutionTracePanel.tsx`, `paper-portfolio.css`, `test_paper_p1.py`. |
| **Tests** | `ui`: vitest **374 passed** (70 files); `npm run build` pass; initial bundle **199.15 KiB gzip**; `validate.py changed` **704 passed**; `validate.py full` **2957 passed** |
| **Related** | [Portfolio history completion](../superpowers/plans/2026-08-31-paper-portfolio-decision-history-completion.md), [Handoff completion](../superpowers/plans/2026-08-31-paper-command-workspace-handoff-completion.md) |
| **Notes** | `sourceContext` remains UI-only for historical rows. Arbitrary correlation strings degrade to UNKNOWN. Manual orders detected when `correlation_id === client_order_id`. |

---

## 2026-08-31 — Paper Command → Workspace unified handoff

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui/paper-now`, `ui/paper-workspace`, `ui/paper`, `ui/tests`, `docs` |
| **Summary** | Unified Paper Command attention handoff with lane-style workspace cockpit: `parsePaperDraftProvenance`, `createAttentionPaperOrderDraft`, `PaperHandoffPanel` (lane/attention/unknown), optional `sourceContext` on version-1 drafts, `correlation_id` on preview/submit for valid provenance, execution trace provenance display. Paper Command navigates with placeholder draft + source context; workspace revalidates preview against current state. |
| **Key files** | Created: `buildPaperHandoffModel.ts`, `PaperHandoffPanel.tsx`, tests, `docs/superpowers/plans/2026-08-31-paper-command-workspace-handoff-completion.md`. Modified: `paperOrderDraft.ts`, `PaperNowPage.tsx`, `PaperCandidateQueue.tsx`, `ModeNowRoute.tsx`, `PaperDecisionCockpit.tsx`, `PaperDecisionSnapshot.tsx`, `OrderTicket.tsx`, `ExecutionTracePanel.tsx`, `paper-workspace.css`, plan docs, `App.test.tsx`. Deleted: `buildLaneHandoffModel.ts`, `LaneHandoffPanel.tsx` (replaced by unified handoff). |
| **Tests** | `ui`: vitest **352 passed** (66 files); `npm run build` pass; initial bundle **199.16 KiB gzip**; `validate.py changed` pass (283 tests) |
| **Related** | [Handoff completion](../superpowers/plans/2026-08-31-paper-command-workspace-handoff-completion.md), [Decision cockpit completion](../superpowers/plans/2026-08-31-paper-workspace-decision-cockpit-completion.md) |
| **Notes** | No backend schema changes. `correlation_id` uses existing Paper API contract (`sourceAttentionId` when valid). `sourceContext` remains UI-only. |

---

## 2026-08-31 — Paper workspace decision cockpit

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui/paper-workspace`, `ui/paper`, `ui/tests`, `docs` |
| **Summary** | Transformed Paper Workspace Overview into a decision cockpit with lane handoff panel, cross-lane decision snapshot (supports/contradicts/unclear/gaps), What Matters Now summary, compact Paper risk context, and first-class preview status synchronized from OrderTicket. Pure view-model helpers classify workspace evidence by direction; all 10 lane IDs supported with safe unknown-lane degradation. Demo/Live unchanged. |
| **Key files** | Created: `paper-workspace/buildLaneHandoffModel.ts`, `paperDecisionSemantics.ts`, `buildPaperDecisionSnapshot.ts`, `buildPaperRiskContext.ts`, `paperPreviewPresentation.ts`, `PaperDecisionCockpit.tsx`, `LaneHandoffPanel.tsx`, `PaperDecisionSnapshot.tsx`, `PaperWhatMattersNow.tsx`, `PaperRiskContext.tsx`, `PaperPreviewStatus.tsx`, tests, `docs/superpowers/plans/2026-08-31-paper-workspace-decision-cockpit-completion.md`. Modified: `PaperWorkspacePage.tsx`, `OrderTicket.tsx`, `paperOrderDraft.ts`, `paper-workspace.css`, `App.test.tsx`, related plan docs. |
| **Tests** | `ui`: vitest **343 passed** (66 files); `npm run build` pass; initial bundle **199.18 KiB gzip** |
| **Related** | [Decision cockpit completion](../superpowers/plans/2026-08-31-paper-workspace-decision-cockpit-completion.md), [Lane content completion](../superpowers/plans/2026-08-31-mode-specific-lane-content-completion.md) |
| **Notes** | No backend changes. Evidence API has 8 lanes — large-transactions/fund-etf documented as data gaps. `sourceAttentionId` remains UI-only. Preview invalidation on edit clears to NOT_PREVIEWED (fail-closed). |

---

## 2026-08-31 — Workspace lane mode-specific product content (all 10 lanes)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui/workspace-modules`, `ui/paper`, `ui/tests`, `docs` |
| **Summary** | Added shared `ModeAwareWorkspaceLane` composition with `buildLaneModeContent` view models and `LaneModeContextPanel` for all 10 workspace lanes. Demo/Paper/Live now render distinct product context from existing API fields—not just shell chrome. Live lanes share `LiveLaneOperationalStrip` (canary snapshot + provider health, `queryKey: ["canary-snapshot"]`). Improved Paper lane draft UX with explicit BUY×1 placeholder notes, lane provenance banners on workspace overview and order ticket. |
| **Key files** | Created: `buildLaneModeContent.ts`, `LaneModeContextPanel.tsx`, `LiveLaneOperationalStrip.tsx`, `ModeAwareWorkspaceLane.tsx`, `laneModeContentTypes.ts`, `laneQueryState.ts`, tests, `docs/superpowers/plans/2026-08-31-mode-specific-lane-content-completion.md`. Modified: all 10 `*WorkspaceObservability.tsx`, all 10 `Mode*WorkspaceRoute.tsx`, `WorkspaceModuleModeShell.tsx`, `paperOrderDraft.ts`, `OrderTicket.tsx`, `PaperWorkspacePage.tsx`, `workspace-module-mode.css`, `App.test.tsx`, `ModeWorkspaceRoutes.test.tsx`. |
| **Tests** | `ui`: vitest **298 passed**; `npm run build` pass; bundle budget pass |
| **Related** | [Lane content completion](../superpowers/plans/2026-08-31-mode-specific-lane-content-completion.md), [Mode-specific surfaces completion](../superpowers/plans/2026-08-31-mode-specific-surfaces-completion.md) |
| **Notes** | No backend changes. Institutional/catalyst builders use actual schema fields (`families`, `catalyst_count`). Live operational strip avoids duplicate canary fetch via shared React Query key. |

---

## 2026-08-31 — UI hardening: settings gating, lane drafts, secondary route tests

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui/settings`, `ui/workspace-modules`, `ui/tests`, `ui/live-canary` |
| **Summary** | Mode-gated operator settings (Demo/Live read-only; Paper mutations only). Added Paper lane → workspace draft shortcuts via `createLanePaperOrderDraft` and `Draft paper order from lane` link on all workspace modules. Added App integration tests for `/settings`, `/live-canary`, `/diagnostics/provider`, `/assistant/history`, and lane draft navigation. Consolidated all 10 `Mode*WorkspaceRoute` tests into `ModeWorkspaceRoutes.test.tsx`. Fixed Live Canary query-cache shape mismatch with Live Portfolio by sharing `fetchLiveCanarySnapshot`. |
| **Key files** | Created: `operator-settings/operatorSettingsMode.ts`, `OperatorSettingsPage.test.tsx`, `workspace-module-shared/ModeWorkspaceRoutes.test.tsx`. Modified: `OperatorSettingsPage.tsx`, `App.tsx`, `WorkspaceModuleModeShell.tsx`, `paperOrderDraft.ts`, `LiveCanaryControlPlanePage.tsx`, `App.test.tsx`. Deleted: `ModeSqueezeWorkspaceRoute.test.tsx`. |
| **Tests** | `ui`: vitest 283 passed; `npm run build` pass |
| **Related** | [Mode-specific surfaces completion](../superpowers/plans/2026-08-31-mode-specific-surfaces-completion.md) |
| **Notes** | Lane draft pre-fills workspace ticket when Paper authority is available; App tests verify navigation only under current context mock. |

---

## 2026-08-31 — App integration tests for remaining workspace lane modules

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui/workspace-modules`, `ui/tests` |
| **Summary** | Extended `App.test.tsx` with table-driven integration tests for the seven remaining workspace lanes (order-book, futures, catalyst, fund-etf, large-transactions, disclosure, institutional-flow) across Demo, Paper, and Live modes. Added missing workspace query hook mocks. All 10 lane modules now have App-level coverage. |
| **Key files** | Modified: `ui/src/App.test.tsx` |
| **Tests** | `ui`: vitest 242 passed (App.test.tsx 52 tests) |
| **Related** | Prior entry "App integration tests for workspace overview and lane routes" |
| **Notes** | Uses `it.each(remainingWorkspaceLanes)` for DRY lane assertions via overview module nav. |

---

## 2026-08-31 — App integration tests for workspace overview and lane routes

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui/workspace`, `ui/tests` |
| **Summary** | Added App-level integration tests for `/workspace/BIYA` overview and order-flow/options lane routes in Demo, Paper, and Live modes. Mocked `lightweight-charts` and `LiveMarketPanel` so workspace observability mounts in jsdom; added `ResizeObserver` stub and `useWorkspaceOptionsQuery` mock. |
| **Key files** | Modified: `ui/src/App.test.tsx` |
| **Tests** | `ui`: vitest 221 passed (App.test.tsx 31 tests) |
| **Related** | Prior entry "Workspace module mode copy + App squeeze integration tests" |
| **Notes** | Lane tests navigate via WORKSPACE nav → module nav. Overview tests use `/workspace` redirect to BIYA. |

---

## 2026-08-31 — Workspace module mode copy + App squeeze integration tests

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui/workspace-modules` |
| **Summary** | Added per-module Paper and Live description hints via `workspaceModuleModeDescription`, a Paper simulation context note on `WorkspaceModuleModeShell`, and App-level integration tests navigating to `/workspace/GME/squeeze` in Demo, Paper, and Live modes. Extended unit tests for squeeze route and description utility. |
| **Key files** | Created: `workspace-module-shared/workspaceModuleModeDescription.ts`, `workspaceModuleModeDescription.test.ts`. Modified: all 10 `Mode*WorkspaceRoute.tsx`, `WorkspaceModuleModeShell.tsx`, `WorkspaceModuleModeShell.test.tsx`, `ModeSqueezeWorkspaceRoute.test.tsx`, `App.test.tsx`. |
| **Tests** | `ui`: vitest 212 passed; `npm run build` pass |
| **Related** | [Mode-specific surfaces completion](../superpowers/plans/2026-08-31-mode-specific-surfaces-completion.md), prior entry "Mode-specific workspace sub-modules" |
| **Notes** | Demo descriptions unchanged (shell restriction note covers Demo). Paper/Live hints are module-specific with sensible defaults. |

---

## 2026-08-31 — Mode-specific workspace sub-modules

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui/workspace-modules` |
| **Summary** | Converted all 10 workspace lane sub-modules (squeeze, order-flow, order-book, futures, catalyst, fund-etf, options, large-transactions, disclosure, institutional-flow) to mode-aware routes via shared `WorkspaceModuleModeShell`. Each module now has `*WorkspaceObservability` (data + panel), `Mode*WorkspaceRoute`, and Demo/Paper/Live chrome with restriction notes, paper overview/portfolio links, and live canary link. Unified overview pages on full `WorkspaceModuleNav`. |
| **Key files** | Created: `workspace-module-shared/WorkspaceModuleModeShell.tsx`, `useWorkspaceInstrumentId.ts`, `styles/workspace-module-mode.css`, per-module `*Observability.tsx` and `Mode*Route.tsx`, tests. Modified: `App.tsx`, `demo-workspace/`, `paper-workspace/`, `live-workspace/`, `WorkspaceObservability.tsx`. Deleted: 10 legacy `*WorkspacePage.tsx` files. |
| **Tests** | `ui`: vitest 202 passed; `npm run build` pass |
| **Related** | [Mode-specific surfaces completion](../superpowers/plans/2026-08-31-mode-specific-surfaces-completion.md) |
| **Notes** | Paper modules link to workspace overview for order ticket. Overview nav now uses complete module list. |

---

## 2026-08-31 — Mode-specific Discover pages

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui/discover` |
| **Summary** | Split shared `DiscoverPage` into Demo, Paper, and Live discover pages via `ModeDiscoverRoute`, with shared `DiscoverObservability`. Paper retains full discovery desk mutations (refresh, promote); Demo and Live are read-only with GET polling only and workspace links instead of promote POST. Added NavShell discover mode hints and App integration tests. |
| **Key files** | Created: `discover-shared/DiscoverObservability.tsx`, `demo-discover/`, `paper-discover/`, `live-discover/`, `ModeDiscoverRoute.tsx`, mode CSS files, per-mode tests. Modified: `NavShell.tsx`, `NavShell.test.tsx`, `App.tsx`, `App.test.tsx`, `layout.css`. Deleted: `DiscoverPage.tsx`, `DiscoverPage.test.tsx` (migrated to `PaperDiscoverPage.test.tsx`). |
| **Tests** | `ui`: vitest 198 passed; `npm run build` pass |
| **Related** | [Mode-specific surfaces completion](../superpowers/plans/2026-08-31-mode-specific-surfaces-completion.md) |
| **Notes** | All primary workstation routes now have mode-specific pages. |

---

## 2026-08-31 — Mode-specific Explore and Research pages + mode-aware NavShell

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui/explore`, `ui/research`, `ui/nav` |
| **Summary** | Split shared `ExplorePage` and `ResearchPage` into Demo, Paper, and Live mode-specific pages via `ModeExploreRoute` and `ModeResearchRoute`, with shared `ExploreObservability` and `ResearchObservability`. Updated `NavShell` to accept session mode and show per-link hints and accessible labels. Added App integration tests for `/explore` and `/research` per mode. |
| **Key files** | Created: `explore-shared/ExploreObservability.tsx`, `demo-explore/`, `paper-explore/`, `live-explore/`, `ModeExploreRoute.tsx`, `research-shared/ResearchObservability.tsx`, `demo-research/`, `paper-research/`, `live-research/`, `ModeResearchRoute.tsx`, `NavShell.test.tsx`, mode CSS files, per-mode tests. Modified: `NavShell.tsx`, `App.tsx`, `App.test.tsx`, `layout.css`. Deleted: `ExplorePage.tsx`, `ResearchPage.tsx`. |
| **Tests** | `ui`: vitest 193 passed; `npm run build` pass |
| **Related** | [Mode-specific surfaces completion](../superpowers/plans/2026-08-31-mode-specific-surfaces-completion.md) |
| **Notes** | Discover remains a shared route. Paper Research defaults to Simulation tab. Live Explore shows `LiveObservationalPanel`. |

---

## 2026-08-31 — Enforce always-automatic work logging

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs` |
| **Summary** | Strengthened work-logging Cursor rule (`alwaysApply: true`) and AGENTS/WORK_LOG wording so logging runs automatically every session without user prompts. |
| **Key files** | `.cursor/rules/work-logging.mdc`, `AGENTS.md`, `docs/engineering/WORK_LOG.md` |
| **Tests** | N/A |
| **Related** | User confirmation that logging must always happen automatically |

---

## 2026-08-31 — Work logging and documentation tracking

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs` |
| **Summary** | Introduced this work log, a mode-surfaces completion record, and a Cursor rule requiring automatic logging after substantive work. |
| **Key files** | `docs/engineering/WORK_LOG.md`, `docs/superpowers/plans/2026-08-31-mode-specific-surfaces-completion.md`, `.cursor/rules/work-logging.mdc`, `AGENTS.md` |
| **Tests** | N/A (documentation only) |
| **Related** | User request to document all work and track future changes automatically |

---

## 2026-08-31 — Mode-specific workspace pages

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui/workspace` |
| **Summary** | Split the monolithic `WorkspacePage` into Demo, Paper, and Live workspace pages with shared `WorkspaceObservability`, mirroring the portfolio and Now dashboard patterns. Paper retains order ticket and execution trace when authority passes; Demo and Live are read-only. |
| **Key files** | Created: `ui/src/components/workspace-shared/WorkspaceObservability.tsx`, `workspace-shared/workspaceHealth.ts`, `demo-workspace/DemoWorkspacePage.tsx`, `paper-workspace/PaperWorkspacePage.tsx`, `live-workspace/LiveWorkspacePage.tsx`, `ModeWorkspacePage.tsx`, `styles/demo-workspace.css`, `paper-workspace.css`, `live-workspace.css`, and per-mode tests. Modified: `WorkspaceRoute.tsx`, `App.tsx`. Deleted: `WorkspacePage.tsx`, `WorkspacePage.test.tsx`. |
| **Tests** | `ui`: vitest 177 passed; `npm run build` pass |
| **Related** | [Mode-specific surfaces completion](../superpowers/plans/2026-08-31-mode-specific-surfaces-completion.md), [Mode-aware workstation plan](../superpowers/plans/2026-08-30-mode-aware-workstation.md) |
| **Notes** | `WorkspaceRoute` still owns instrument/squeeze fetching and Paper draft handoff from router state. |

---

## 2026-08-31 — Mode-specific portfolio pages + App integration tests

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui/portfolio` |
| **Summary** | Replaced single `PortfolioPage` with Demo (read-only simulated), Paper (full simulation controls), and Live (broker-observed canary data) portfolio pages via `ModePortfolioRoute`. Extended `LiveCanarySnapshot` for live portfolio fields. Added App-level `/portfolio` navigation tests per mode. |
| **Key files** | Created: `portfolio-shared/PaperPortfolioObservability.tsx`, `demo-portfolio/`, `paper-portfolio/`, `live-portfolio/`, `livePortfolioViewModel.ts`, `ModePortfolioRoute.tsx`, mode CSS files, tests. Modified: `App.tsx`, `App.test.tsx`, `live-now/liveCanarySnapshot.ts`. Deleted: `PortfolioPage.tsx`, `PortfolioPage.test.tsx`. |
| **Tests** | `App.test.tsx`: Demo/Paper/Live portfolio route tests; unit tests per mode page; vitest 177 passed |
| **Related** | [Mode-specific surfaces completion](../superpowers/plans/2026-08-31-mode-specific-surfaces-completion.md) |
| **Notes** | Live portfolio reads `/canary/snapshot` and `/canary/reconciliation`. Paper session/order controls still gated by `canUsePaperActions`. |

---

## 2026-08-31 — Live Now dashboard (“Live Watch”)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui/now` |
| **Summary** | Replaced generic `NowPage` for Live mode with `LiveNowPage`: provider ribbon, safety/canary snapshot, symbol lookup, and read-only attention feed. Wired through `ModeNowRoute` with canary and provider health queries. |
| **Key files** | Created: `ui/src/components/live-now/` (`LiveNowPage.tsx`, `LiveProviderRibbon.tsx`, `LiveSafetySnapshot.tsx`, `LiveSymbolLookup.tsx`, `liveDashboardViewModel.ts`, `liveCanarySnapshot.ts`, fixtures, tests), `styles/live-now.css`. Modified: `ModeNowRoute.tsx`, `App.tsx`, `App.test.tsx`. |
| **Tests** | `LiveNowPage.test.tsx`, `liveDashboardViewModel.test.ts`, `App.test.tsx` Live mode integration |
| **Related** | [Demo Now plan](../superpowers/plans/2026-08-30-demo-now-dashboard.md), [Paper Now plan](../superpowers/plans/2026-08-31-paper-now-dashboard.md) |
| **Notes** | No separate design spec file; follows Demo/Paper Now patterns. |

---

## 2026-08-31 — Paper Now dashboard (“Paper Command”)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui/now` |
| **Summary** | Paper-only Decision Canvas at `/`: risk ribbon, candidate queue, preview composer, and draft handoff to workspace `OrderTicket`. Shared `paperOrderDraft` contract between Now and workspace. |
| **Key files** | See [Paper Now implementation plan](../superpowers/plans/2026-08-31-paper-now-dashboard.md) file structure section |
| **Tests** | `PaperNowPage.test.tsx`, `paperOrderDraft.test.ts`, `PaperPanels.test.tsx`, `WorkspaceRoute.test.tsx`, `OrderTicket.test.tsx` |
| **Related** | [Paper Now plan](../superpowers/plans/2026-08-31-paper-now-dashboard.md), [Paper Now design](../superpowers/specs/2026-08-31-paper-now-dashboard-design.md) |

---

## 2026-08-30 — Demo Now dashboard (“See the market unfold”)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui/now` |
| **Summary** | Demo-specific landing at `/` with BIYA replay controls, observational portfolio summary, attention feed, and inspect-next guidance. Introduced `ModeNowRoute` and reusable `AttentionFeed`. |
| **Key files** | See [Demo Now implementation plan](../superpowers/plans/2026-08-30-demo-now-dashboard.md) file structure section |
| **Tests** | `DemoNowPage.test.tsx`, `DemoReplayOverview.test.tsx`, `AttentionFeed.test.tsx`, `App.test.tsx` |
| **Related** | [Demo Now plan](../superpowers/plans/2026-08-30-demo-now-dashboard.md), [Demo Now design](../superpowers/specs/2026-08-30-demo-now-dashboard-design.md) |

---

## 2026-08-30 — Mode-aware workstation (launcher + gating)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui/mode-session` |
| **Summary** | Mode Launcher → session mode (Demo/Paper/Live) with fail-closed `modeAuthority`, persistent `ModeEnvironmentBar`, and gating on portfolio/workspace mutations. Replaced placeholder dashboards with full workstation shell. |
| **Key files** | See [Mode-aware workstation plan](../superpowers/plans/2026-08-30-mode-aware-workstation.md) |
| **Tests** | `modeAuthority.test.ts`, `ModeEnvironmentBar.test.tsx`, `ModeSession.test.tsx`, `App.test.tsx` |
| **Related** | [Mode-aware workstation design](../superpowers/specs/2026-08-30-mode-aware-workstation-design.md) |

---

## 2026-09-07 — G0 post-reconciliation baseline (Wave 0: truth + validation control plane)

| Field | Value |
|-------|-------|
| **Status** | `complete` (working tree; uncommitted alongside pre-existing dirty state) |
| **Area** | governance supersession + `validate changed` correctness + repo truth + dev-system corrections |
| **Summary** | Executed G0 per `docs/audits/imp-reconciliation/19-goal-increment-plan.md` §2. Donor-governance records superseded in place (Heller correction; ADR-DONOR-001 handled via the hash-bound supersession notice); `validate changed` now normalizes the `projects/integrated-market-platform/` prefix, owns fixture/config/test-fixture paths by consumer evidence, renames `full_suite_required` → `core_checkpoint_required` with audit-grade `--explain`; short-squeeze snapshot reconciled to child `9de7b2f` with manifest + overlay; roadmap/program status refreshed to the authorized mandate; AGENTS.md states the canonical edit target; `imp.py env` exits non-zero on hard prereq failure; `donor_patterns/` + `tests/gridiq` annotated; empty pytest dir removed; child CI copies replaced with parent-CI pointers. |
| **Key files** | `tools/validate.py`, `tools/validation_manifest.{py,json}`, `tools/imp.py`, `AGENTS.md`, `docs/platform/{MASTER_ROADMAP,PROGRAM_STATUS}.md`, `workspace-manifest.json`, donor-governance docs, `docs/superpowers/governance/2026-09-07-donor-authority-supersession-notice.md` |
| **Tests** | `tests/validation/test_validate_selection.py` (+12 selection-semantics tests), `test_imp_cli.py` (+4 env exit tests), manifest/orchestration updates; full evidence in `docs/audits/imp-reconciliation/15-validation-evidence.md` (G0 section) |
| **Related** | Reconciliation master backlog (`docs/audits/imp-reconciliation/12-master-backlog.md`) BL-0001..0008, BL-0011; recovery roadmap (`13-recovery-roadmap.md`) Wave 0; root-cause register (`16-root-cause-register.md`) RC-012/013/014/020 — parent audit workspace, outside the IMP snapshot |

---

## 2026-09-07 — G1 canonical multi-asset identity foundation (Wave 1: identity slice)

| Field | Value |
|-------|-------|
| **Status** | `complete` (working tree; uncommitted alongside pre-existing dirty state) |
| **Area** | `xa01/*`, `paper/contracts.py`, `xa04/codec.py`, identity tests + docs |
| **Summary** | Executed G1 per `docs/audits/imp-reconciliation/19-goal-increment-plan.md` §5. One canonical asset-class vocabulary: `XaAssetClass` gains `CRYPTO` and `BOND`; `InstrumentKind` gains `CRYPTO_PAIR`, `BOND`, `CONTINUOUS_SERIES`, `COMMODITY_SPOT`; `paper.contracts.ASSET_CLASSES` is deprecated as a backward-compat view. Added explicit `Tradability` semantics (TRADABLE / REFERENCE_ONLY / SYNTHETIC / CONTINUOUS_SERIES) on every canonical identity with a fail-closed guard (`xa01.tradability.assert_executable`, `xa01.resolver.resolve_executable_alias`, and `paper.contracts.build_user_order_intent` rejecting non-executable instrument refs). Added builders: `register_crypto_pair` (base/quote/venue/network), `register_bond` (issuer/CUSIP-ISIN/maturity/coupon/par/credit tier), `register_commodity_spot`, `register_commodity_proxy`, `register_continuous_futures_series`, plus `commodity_sector` on economic commodities. Serialization extended additively (XA-04 codec decodes legacy documents with safe defaults). No portfolio, risk, provider-live, or product-surface migration. |
| **Key files** | `src/market_platform_foundation/xa01/{enums,contracts,identity,compatibility,registry,resolver,errors,tradability}.py`, `src/market_platform_foundation/paper/contracts.py`, `src/market_platform_foundation/xa04/codec.py`, `tests/xa01/test_xa01_{crypto_identity,bond_identity,commodity_identity,tradability_guard,cross_asset_collisions,g1_serialization}.py`, XA-01 spec + MASTER_ARCHITECTURE/PROGRAM_STATUS updates |
| **Tests** | tests/xa01 71 passed (12 existing + 59 new); futures 65, options 147, contracts 38, xa02 21, xa03 31, xa04 30, xa05 15, platform paper/operational-identity 114 — all green; see `docs/audits/imp-reconciliation/15-validation-evidence.md` (G1 section) |
| **Related** | Master backlog BL-0101..0104 (updated in `12-master-backlog.md`); RC-004 materially advanced (16); recovery roadmap (`13`) Wave 1 identity slice; next dependent increment BL-0105 (G2 canonical multi-asset portfolio) remains NOT started |

---

## 2026-09-07 — G2 canonical multi-asset portfolio foundation (Wave 1: portfolio core, BL-0105)

| Field | Value |
|-------|-------|
| **Status** | `complete` (working tree; uncommitted alongside pre-existing dirty state) |
| **Area** | `portfolio/canonical.py`, `portfolio/{admission,valuation,fx,provider_normalization,paper_adapter}.py`, `tests/portfolio/*`, docs |
| **Summary** | Executed G2 per `docs/audits/imp-reconciliation/19-goal-increment-plan.md` (BL-0105). Established ONE canonical multi-asset portfolio model (`portfolio.canonical`) scoped by operational account + mode (`PortfolioKey`) and keyed by canonical XA-01 `instrument_id`, with explicit quantity units (SHARES/CONTRACTS/BASE_UNITS/FACE_VALUE), per-currency `CashBalance` (Decimal), a `ValuationMark` contract (currency + provenance + fresh/stale/missing), asset-aware valuation dispatch (equity qty×mark; options contracts×premium×multiplier; futures notional + mark-to-market P&L, never equity-style cash value; crypto base-units × pair price; bonds face × explicit price basis), an explicit FX conversion boundary (no 1:1 fallback; COMPLETE/PARTIAL/MISSING_FX/STALE aggregation), deterministic serialization, and a controlled mutation boundary (`apply_position_input` / `apply_snapshot` / `apply_cash` / `apply_adjustment`). Admission fails closed on reference identities via XA-01 tradability (continuous futures, family/root, economic commodities, spot references, benchmarks, currencies, FX pairs, reference-only bonds rejected). Provider snapshots normalize through XA-01 alias resolution with `UNRESOLVED_INSTRUMENT` fail-closed. Paper equity behavior preserved bit-identical via a dual-run read-side adapter (`paper_snapshot_to_canonical`) with parity tests; the legacy equity ledger remains the Paper execution parity baseline (BL-0106/0107 options/numeric merge remain separate follow-on items). |
| **Key files** | `src/market_platform_foundation/portfolio/{canonical,admission,valuation,fx,provider_normalization,paper_adapter}.py`, `src/market_platform_foundation/portfolio/__init__.py`, `tests/portfolio/test_{canonical_admission,cash_and_fx,valuation,isolation,provider_normalization,persistence,paper_parity}.py`, `tools/validation_manifest.json` (new `portfolio` suite), G2 portfolio spec (`docs/superpowers/specs/2026-09-07-imp-g2-canonical-multi-asset-portfolio-foundation.md`), `MASTER_ARCHITECTURE.md`, `PROGRAM_STATUS.md` |
| **Tests** | tests/portfolio 109 passed (admission 18, cash/FX 21, valuation 34, isolation 15, provider normalization 12, persistence 9, paper parity 7... exact per-suite counts in the FULL run); FAST 21 passed; phase7/platform regression green; see `docs/audits/imp-reconciliation/15-validation-evidence.md` (G2 section) |
| **Related** | Master backlog BL-0105 (`12-master-backlog.md`, updated); RC-001 materially advanced (16); recovery roadmap (`13`) Wave 1 portfolio core; BL-0106 (options ledger merge) and BL-0107 (futures Decimal) remain NOT started after G2 |

---

## Planned (not started)

| Item | Area | Notes |
|------|------|-------|
| Master-account login before Mode Launcher | `ui/auth` | User idea: single login provisions connected broker/data APIs; not concrete yet |
