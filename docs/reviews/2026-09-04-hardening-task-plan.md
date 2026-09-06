# Workspace Hardening Task Plan — 2026-09-04

| Field | Value |
|---|---|
| Created | 2026-09-04 |
| Source | [Hardening review](2026-09-04-hardening-review.md) |
| Purpose | Tracked, checkable backlog produced by the workspace hardening review. Items are grouped P0 → P2. Each item names evidence, the fix, and an acceptance check. |
| Status | In progress — 17/17 P-items closed (P0-1–P0-4, P1-1–P1-8, P2-1–P2-5; 2026-09-04/05). Q-H1 stays open (unfitted fusion/GARCH/HAR/ADAM/logistic only). Q-H1-rate and Q-H1-O10-rate closed. Q-series does not reopen G1–G6. |

**How to use:** tick `[ ]` → `[x]` as items close. Substantive work should also follow the owning repo's conventions (platform work log entry in `integrated-market-platform/docs/engineering/WORK_LOG.md`; short-squeeze work in its own repo; snapshot refreshes through the guarded monorepo import).

---

## P0 — Before any trading / promotion / forward campaign

These items make the machinery behind the (correctly) closed live gates trustworthy. None of them relaxes a gate.

### P0-1 — Forward-validation readiness checklist (gates G1/G3/G4/G5)

- **Problem:** P6 Shadow Run 1 and EVIDENCE-01C are deferred; canary never executed; real-wire adapters unexercised. Reactivation today would be ad hoc.
- **Evidence:** `docs/platform/PROGRAM_STATUS.md`; `docs/engineering/P6_SHADOW_RUN_1_PROTOCOL.md`; `docs/engineering/EVIDENCE_01C*`; BUILD25/29 limitation artifacts; TD-004 (`docs/engineering/TECH_DEBT.md`).
- **Fix:** one checklist document (owner: platform docs) listing the exact prerequisites to reopen each of P6 Shadow Run 1, EVIDENCE-01C, live canary, Tradier sandbox wire, and Moomoo OpenD shakedown — connectivity, env vars, credentials, fixture-state, rollback, and acceptance artifacts.
- **Acceptance:** a reviewer can determine in one page exactly which env/credential/connectivity prerequisites block each campaign today, and what each campaign must produce to count.
- **Closed 2026-09-05** — `docs/engineering/FORWARD_VALIDATION_READINESS_CHECKLIST.md` added (platform tree): per-campaign rows for P6 Shadow Run 1, EVIDENCE-01C, live canary, Tradier sandbox wire, and Moomoo OpenD shakedown with connectivity / env vars / credentials / fixture-state / rollback / acceptance-artifact columns, current blockers pulled from PROGRAM_STATUS + TECH_DEBT. Reviewer can read the blocker column to see exactly what blocks each campaign today. Platform work-log entry added.

### P0-2 — Promotion dry-run harness (champion/challenger machinery proof)

- **Problem:** promotion governance exists but has never been exercised end-to-end; the first real use would be the first test of the machinery.
- **Evidence:** `docs/engineering/CHAMPION_CHALLENGER_PROMOTION_V1.md`; decision-research gate report (no `SUPPORTED` strategy).
- **Fix:** a fixture-driven dry-run that replays recorded paper outcomes through the promotion policy (`strategy/evaluation.py`, promotion engine) and emits an immutable decision record (`PROMOTED` / `NOT_PROMOTED`), proving the ladder without claiming an edge.
- **Acceptance:** test exists in `tests/`; output record references exact preregistration + evidence; docs state the dry run grants no execution authority.
- **Closed 2026-09-05** — `intelligence/promotion/dry_run.py` fixture-driven dry run: replays recorded shadow observations through the promotion engine and emits an immutable decision record (`PROMOTED` / `NOT_PROMOTED` / `INVALID`) referencing the exact champion assignment + preregistration + shadow manifest, with a `dry_run=True` marker so the record grants no execution authority (P1-1 now enforces that separation at the order path). Tests: `tests/intelligence/test_promotion_dry_run.py`, 6 passed. Platform work-log entry added.

### P0-3 — Single source of truth for lane/module identity

- **Problem:** lane identity is duplicated (backend dead `KNOWN_LANE_MODULES`; UI `LANE_MODULE_IDS`; UI `WORKSPACE_LANE_REGISTRY`; hand-written `EVIDENCE_LANE_TO_MODULE_ID`) with no cross-check test — next lane addition can silently drift.
- **Evidence:** `src/market_platform_foundation/paper/decision_source.py:19` (defined, never imported); `ui/src/components/paper-now/paperOrderDraft.ts:408`; `ui/src/components/workspace-module-shared/laneRegistry.ts`; `ui/src/components/paper-workspace/paperDecisionSemantics.ts`; `docs/architecture/DATA_CONTRACTS.md:39`.
- **Fix:** one canonical lane registry consumed by backend + UI (single JSON or Python module + generated TS), with an equality/closure test; `sops/ADD_WORKSPACE_LANE.md` updated so adding a lane edits exactly one source file.
- **Acceptance:** a test asserts backend set == UI list == evidence map; removing the dead backend frozenset or unifying registries lands with zero behavior change; lane addition is a one-file change.
- **Closed 2026-09-04** — resolved as UI-canonical registry + structural backend (no backend enumeration), rather than a shared JSON + generated TS: `WORKSPACE_LANE_REGISTRY` in `ui/src/components/workspace-module-shared/laneRegistry.ts` is now the single identity source, deriving `WORKSPACE_LANE_MODULE_IDS` / `WORKSPACE_LANE_LABELS`; `paperOrderDraft.ts` (`LANE_MODULE_IDS`, `LaneModuleId`, `isKnownLaneModuleId`, `laneModuleLabel`) and `paperDecisionSemantics.ts` (evidence map typing, `MODULES_WITHOUT_EVIDENCE_LANE` complement) read from it. Dead backend `KNOWN_LANE_MODULES` removed — `decision_source.py` now states backend lane provenance is validated structurally and never enumerated, so there is no backend list to drift. Equality/closure tests in `laneRegistry.test.ts` (7 tests) fail if any derived list or the evidence map disagrees with the registry. Verified: `npm run typecheck` clean; `npm test` 436 passed / 85 files; backend `py_compile` clean and zero references to the removed constant (full manifest validation runs in CI). Platform work-log entry added 2026-09-04.

### P0-4 — Attribution parity as an enforced invariant

- **Problem:** strategy attribution is a P&L sidecar whose parity with the authoritative ledger is expected but not a hard, fail-closed gate on materialization.
- **Evidence:** `src/market_platform_foundation/portfolio/attribution.py`, `attribution_materializer.py`; `PAPER_DECISION_LIFECYCLE.md`.
- **Fix:** materializer fails closed on any mismatch with authoritative fill-driven accounting; mismatch is recorded as an immutable event (mirroring P4-REC semantics), never silently absorbed.
- **Acceptance:** unit test forces a mismatch and asserts fail-closed + event recorded; no legitimate state can produce a silent divergence.
- **Closed 2026-09-05** — `attribution_materializer.py` enforces parity before persisting: recomputation is compared against every already-persisted attribution for the same allocation; any already-covered fill whose authoritative accounting changed, or any coverage regression, records an immutable `ATTRIBUTION_PARITY_VIOLATION` `EventV1` (deterministic `ATTR-PARITY-*` id) and raises `AttributionMaterializationError` — never silently absorbed. Identical recomputations (dedup) and legitimate CUMULATIVE coverage growth stay silent. Tests: `tests/platform/test_strategy_attribution.py` (`AttributionParityInvariantTests`), 14 passed / 3 subtests. Platform work-log entry added.

---

## P1 — Hardening while the live gates stay closed

### P1-1 — Explicit strategy eligibility gate before OrderReadyV1 execution intent

- **Problem:** no single checkable predicate "this strategy may drive OrderReadyV1 with execution intent" is enforced at runtime.
- **Evidence:** `src/market_platform_foundation/strategy/runtime.py` (order-ready construction path); learning boundary tests (`tests/intelligence/test_strategy_learning.py`).
- **Fix:** small explicit eligibility predicate (preregistered + promotion state + forward-evidence class) enforced on the order-ready path and by test.
- **Acceptance:** per-order intent is auditable to the strategy's eligibility record; unknown/unpromoted strategies cannot reach execution intent.
- **Closed 2026-09-05** — `strategy/eligibility.py` adds the single predicate (preregistered identity + promotion state + forward-evidence class) returning an immutable, deterministically-addressed `StrategyEligibilityRecordV1`. `StrategyPaperRuntime` enforces it on the order-ready construction path when an execution-eligibility configuration is supplied: ineligible/unknown strategies produce a persisted BLOCKED OrderReadyV1 stamped `STRATEGY_EXECUTION_ELIGIBILITY_BLOCKED` plus a `strategy_eligibility` lineage ref to the record (per-order intent auditable), a `STRATEGY_BLOCKED` result, and zero paper mutation; fully eligible (preregistered + ACTIVE PROMOTION champion + forward evidence tier) runs READY/FILLED. Research runtimes without the configuration keep current behavior; execution-intent wiring must supply it (fail closed by construction). Tests: `StrategyExecutionEligibilityGateTests` in `tests/intelligence/test_equity_paper_runtime.py`, 4 passed; runtime/learning regression 26 passed. Platform work-log entry added.

### P1-2 — Canonical opportunity path enforcement (retire path multiplicity)

- **Problem:** OpportunityEngine vs. new scanner + economic sidecar + bridge constructions coexist; only docs currently say which is canonical.
- **Evidence:** `src/market_platform_foundation/intelligence/opportunity/` (`engine.py`, `bridge.py`, `p4_adapter.py`, `economic_assessment.py`); 2026-09-01→04 `WORK_LOG.md` entries.
- **Fix:** designate one canonical construction path in `PAPER_DECISION_LIFECYCLE.md` + code docstrings; deprecate the older construction; add negative tests for cross-path identity collisions (same decision via two paths must conflict, not duplicate).
- **Acceptance:** docs and code name one canonical builder; a test proves two paths cannot produce duplicate authoritative records.
- **Closed 2026-09-05** — canonical mint is `StrategyMatch` → `intelligence/opportunity/bridge.py` → `OpportunityEngine.assess` → persist once (`PAPER_DECISION_LIFECYCLE.md`). Direct engine construction, the P4 adapter, and the universal economic sidecar are not alternate builders; two constructions of the same identity with different lineage conflict on persist (`IMMUTABLE_CONFLICT`). Execution-intent `StrategyPaperRuntime` that omits `strategy_eligibility` fails closed (`omitted_execution_eligibility_record`); research-only scanners emit matches only and do not construct `OrderReadyV1`. Tests: `tests/intelligence/test_universal_opportunity.py`, `tests/intelligence/test_equity_paper_runtime.py`. Did not open LIVE-001 or paper campaign gates.

### P1-3 — RT-01 spans for broker-paper submission/poll/reconcile seams

- **Problem:** paper pipeline tracing landed 2026-09-04, but broker/reconciliation technical spans and full opportunity→risk→order_ready tracing remain follow-ons.
- **Evidence:** `WORK_LOG.md` 2026-09-04 RT-01 paper tracing entry; `docs/platform/PROGRAM_STATUS.md` RT-01 limitation line.
- **Fix:** extend `rt01/instrumentation/` to broker-paper submission, polling, cancellation, and reconciliation seams (fixture-driven), consistent with existing trace semantics; no new tracing before measured need beyond these seams.
- **Acceptance:** trace IDs flow across the broker-paper seams in tests; `PROGRAM_STATUS.md` limitation updated when closed.
- **Closed 2026-09-05** — fixture test `test_fixture_pipeline_shares_one_trace_id` in `tests/platform/test_broker_runtime_wiring.py`: one bound root context through opportunity → risk → order_ready → submit → poll → cancel/reconcile with a single `trace_id` (`InMemoryTraceCollector` / `configure_tracer` / `bind_context`). `PROGRAM_STATUS.md`, `artifacts/imp-rebase/RT01/RT01_KNOWN_LIMITATIONS.json`, and `CANONICAL_TRUTH_MAP.md` RT-01 rows match measured fixture seams. No live brokers; G5 observational campaign stays closed.

### P1-4 — Discovery-lane → workspace-module → research-family mapping

- **Problem:** three "lane" vocabularies coexist (screener `MOMENTUM/SQUEEZE/CATALYST/SWING`, workspace modules, research families) with partial hand maps.
- **Evidence:** `docs/research/PLATFORM_COOPERATIVE_MASTER_ROADMAP.md`; `artifacts/live-screener/continuation-state.md`; `src/market_platform_foundation/discovery/mixed.py`; `ui/.../paperDecisionSemantics.ts`.
- **Fix:** glossary entry + one tested mapping table; keep the concepts distinct (a discovery lane is not a workspace module is not a research family).
- **Acceptance:** a single documented + tested mapping covers all three vocabularies; no hand-written per-component map remains unverified.
- **Closed 2026-09-05** — one mapping table in `lanes/vocabulary.py` (tested by `tests/platform/test_lane_vocabulary.py`): discovery (`MOMENTUM`/`SQUEEZE`/`CATALYST`/`SWING`) ≠ workspace kebab (`squeeze`, `order-flow`, `catalyst`) ≠ evidence `LaneId` (`short_squeeze`, `market_context`). UI `EVIDENCE_LANE_TO_MODULE_ID` in `paperDecisionSemantics.ts` maps `MARKET_CONTEXT` → workspace **`catalyst`**, not `order-book`. UI registry tests: `laneRegistry.test.ts` (9 passed).

### P1-5 — Provider admission guard tests

- **Problem:** live opt-in provider captures are "not admitted research datasets"; doctrine forbids model retraining on them, but no guard test pins the boundary.
- **Evidence:** root README ADR table; `PROVIDER_READINESS.md`; ADR-LIVE-001 / ADR-SHORT-001 fixtures.
- **Fix:** guard/negative tests asserting unadmitted live captures cannot feed model training or promotion paths.
- **Acceptance:** a test proves an unadmitted capture is rejected by training/promotion entry points.
- **Closed 2026-09-05** — `intelligence/dataset_admission.py` rejects unadmitted live-opt-in captures at training, promotion, and OrderReady entry points. Tests: `tests/platform/test_unadmitted_and_donor_isolation.py` (`UnadmittedCaptureGuardTests`). No `SUPPORTED` strategy and no live-capture admission.

### P1-6 — CI canonicalization (parent snapshot workflows authoritative)

- **Problem:** identical workflow names exist in the archived nested repo and the parent (which validates `projects/integrated-market-platform`); ambiguity about the canonical gate.
- **Evidence:** `integrated-market-platform/.github/workflows/imp-validate.yml` vs `.github/workflows/imp-validate.yml` (parent); parent `imp-python.yml` working-directory `projects/integrated-market-platform`.
- **Fix:** declare parent workflows canonical in docs; mark nested workflow copies stale or remove them in the nested repo (child repo is archived read-only — document-only decision may suffice).
- **Acceptance:** a reader can tell which CI gate is authoritative; no duplicated workflow is presented as current without a stale marker.
- **Closed 2026-09-05** — parent `.github/workflows/imp-validate.yml` and `imp-python.yml` (`working-directory: projects/integrated-market-platform`) are the canonical monorepo gate. Nested copies under `projects/integrated-market-platform/.github/workflows/` carry a `STALE` header stating they are not the gate. `CANONICAL_TRUTH_MAP.md` / `TEST_AND_EVALUATION_STANDARD.md` point at the parent paths. Nested files were not deleted.

### P1-7 — Fix git dubious-ownership failure in `equity-data-v1-worktree`

- **Problem:** git commands fail in this worktree on this machine (repo owned by `CodexSandboxOffline`, running as `adame`), which can break the guarded import/validate workflow.
- **Evidence:** `git -C equity-data-v1-worktree status` ownership error; same issue was fixed for `integrated-market-platform` on 2026-09-04 via `git config --global --add safe.directory`.
- **Fix:** add the safe.directory entry for `equity-data-v1-worktree`; run `python tools/monorepo_guard.py validate` to confirm both worktrees readable.
- **Acceptance:** `git -C equity-data-v1-worktree status` and `monorepo_guard.py validate` succeed locally.
- **Closed 2026-09-04** — added `C:/Users/adame/Desktop/market-trading-platform/equity-data-v1-worktree` to `git config --global safe.directory` (same fix already applied to `integrated-market-platform`). Verified: `git -C equity-data-v1-worktree status` exit 0 and `python tools/monorepo_guard.py validate` → `monorepo validation passed`. No commits made; the two dirty assistant-audit files in that worktree predate this change and were left untouched (child repo, immutable boundary).

### P1-8 — Commit + snapshot-refresh the short-squeeze working tree

- **Problem:** 213 modified files (~6.5k insertions / ~3.1k deletions) on `phase/3e-historical-acquisition` exist only in the working tree; the parent snapshot points at the older committed `0b40834`.
- **Evidence:** `git -C short-squeeze-project status --short` (213 files); `workspace-manifest.json` source_commit `0b408349…`.
- **Fix:** complete the short-squeeze work in its own repo (commit + PR per its own workflow), then refresh the parent snapshot through the guarded import (`docs/MONOREPO_WORKFLOW.md`).
- **Acceptance:** short-squeeze repo is clean or has a tracked branch/PR; parent snapshot commit updated via import; `monorepo_guard.py validate` passes.
- **Closed 2026-09-04** — child repo: reviewed all 213 changed files (70 modified + 143 untracked, all under `short-squeeze-core/`, one coherent Phase 3F acquisition/calibration phase; secret scan clean; all changed `.py` pass `py_compile`) and committed as `8a5e43e` on `phase/3e-historical-acquisition` (224 files, working tree clean). Parent: refreshed `projects/short-squeeze-project` to `8a5e43e` and bumped `workspace-manifest.json` `source_commit` in `8c9fd56` on branch `chore/import-short-squeeze-8a5e43e`; `python tools/monorepo_guard.py validate` → `monorepo validation passed`. Note: `monorepo_guard.py import` (git subtree pull) cannot be used for this project because the short-squeeze snapshot was included as plain files (`b73150f`) with no subtree metadata — the sync mirrors the established pattern for the platform snapshot (`1d52896 merge: sync integrated-market-platform snapshot to …`). Pending: push `phase/3e-historical-acquisition` and open its PR per the child repo's workflow; push `chore/import-short-squeeze-8a5e43e` and open the parent PR.

**Verification continuation (2026-09-04/05):** full child suite re-run after the committed phase found it not green (~96 failing + 9 errors). Two follow-up commits landed on `phase/3e-historical-acquisition`: `d935434` (7 files: cohort/isolation/guard-exemption fixes, fixture-metadata regeneration) and `41f52bb` (23 files: `tests/analysis/*` + app tests aligned to the expanded 29-symbol / 43-registry-cohort computed values — runner counts, cohort memberships, BIYA's third row (`BIYA_ARTIFACT_DISCOVERY`), sample-size `LIMITED` band, env-var surfaces; six stale `tests/fixtures/acquisition/phase_3d_*` files regenerated from `build_phase3d_fixture_documents`; `start_cloud.py` import-time `os.environ`/`os.chdir` side effects moved into the entry block, which was leaking `SQUEEZE_APP_MODE=CLOUD_PROVIDER_MODE` into every test session and flipping IBKR HALTS capability to NOT CONFIGURED). Final full-suite result: **2718 passed / 73 failed-or-error, all environmental** — 27 `tests/compatibility/*` need the git baseline commit absent from this clone; 6 `tests/tools/ibkr_historical_export/test_collector.py` need a live IB Gateway; 11 `tests/acquisition/test_operation_readiness.py` need `batch07/synthetic-batch05/raw` data that was never committed; 29 across `test_frozen_research_mode` / `test_meeting_demo_smoke` / `test_current_guards` / `test_prior_artifact_integrity` / `test_batch08` / `test_batch09` need the canonical 13-case Batch 01 freeze + frozen preview inputs (the local `intake/local-bars/ibkr-batch-05` root currently holds a stale 5-case freeze from 2026-08-17). Parent snapshot re-synced to `41f52bb` in `1ce490d`; `monorepo_guard.py validate` passes. Remaining before PR: owner must provide the frozen Batch 08/09 data (or a fixture decision) for the 29 app/acquisition tests; everything else is CI-only (baseline history) or IB-Gateway-only.

---

## P2 — Hygiene and documentation

### P2-1 — Idea → experiment → evidence → learning registry (non-authoritative)

- **Problem:** product ideas are an informal short list; decision-research cards are formal but narrow; nothing traverses idea → hypothesis → card → outcome → learning as one record.
- **Evidence:** `docs/product/PRODUCT_BACKLOG.md`; decision-research card registry (`evidence/research/experiment-cards/`); `docs/engineering/CONTROLLED_ADAPTATION_V1.md`.
- **Fix:** lightweight machine-readable idea/experiment registry reusing OF-03 capability/SOP/workflow patterns; explicitly non-authoritative.
- **Acceptance:** an idea can be traced to its preregistered experiment card and outcome; registry is documented as non-authoritative.
- **Closed 2026-09-05** — `docs/product/idea_registry/` index: `manifest.json` (`non_authoritative: true`), `ideas.json` linking `PRODUCT_BACKLOG` ids → optional experiment-card hashes / outcome refs, README stating the index never grants trading, promotion, or execution. OF-03 *shape* only; no capability binding. G1–G6 stay closed.

### P2-2 — Data-acquisition boundary guard

- **Problem:** `pipelines/stock_data` scraper output is explicitly non-admitted SQLite; nothing mechanically prevents accidental reference by admitted research paths.
- **Evidence:** `pipelines/stock_data/README.md`; `docs/data/EQUITY_DATA_ACQUISITION.md`.
- **Fix:** namespace/import convention + CI check so non-admitted stores cannot be imported by admitted research code.
- **Acceptance:** a CI test proves admitted research modules cannot import the acquisition subsystem.
- **Closed 2026-09-05** — `tests/platform/test_acquisition_import_guard.py` AST-walks admitted trees (`src/market_platform_foundation/research/` and other admitted consumers) and fails on `import` / `from` `pipelines.stock_data` / `stock_data`. Complementary to `pipelines/stock_data/tests/test_monorepo_boundary.py`. Orthogonal to P1-5 dataset admission. No calibration of fusion/GARCH/HAR/ADAM/logistic.

### P2-3 — Supersede layered docs (roadmaps, README vs PROGRAM_STATUS, public/private wording)

- **Problem:** THREE/FOUR/FIVE-lane reconciliations + cooperative master lack superseded headers; root README still carries whole-program status; `docs/MONOREPO_WORKFLOW.md` calls the public repo "private".
- **Evidence:** `docs/research/{THREE,FOUR,FIVE}_LANE_ROADMAP_RECONCILIATION.md`; root `README.md`; `docs/MONOREPO_WORKFLOW.md`; `docs/platform/PROGRAM_STATUS.md`.
- **Fix:** add superseded headers with forward links; route status readers to canonical docs; correct public/private wording.
- **Acceptance:** `tools/check_docs_links.py` passes; each superseded doc links to its current replacement.
- **Closed 2026-09-05** — superseded headers with forward links added to the THREE/FOUR/FIVE-lane reconciliations; root `README.md` annotates the stale reconciliation link; `docs/MONOREPO_WORKFLOW.md` no longer calls the public repo private and documents the plain-file snapshot sync path actually used. `tools/check_docs_links.py`: OK (162 governance files).

### P2-4 — Donor isolation verification

- **Problem:** donors are local-only by policy and can submit paper/live-style orders; they must never enter the platform execution path.
- **Evidence:** `.gitignore`; publish commit `cfdebaa`; `PROJECT_NOTES_INDEX.md` cautions.
- **Fix:** verify no platform adapter imports donor execution entry points; optionally tag any donor-derived logic with provenance.
- **Acceptance:** a search/CI check confirms donor execution modules are unreachable from platform code.
- **Closed 2026-09-05** — `tests/platform/test_unadmitted_and_donor_isolation.py` fails if platform source imports donor execution fragments (`eric_futuresx`, `futuresx-main`, internship / bubble modules) or if donor-bridge modules reference `OrderReadyV1` / `PaperExecutionOrchestrator` / `submit_prepared` / `TradeProposalV1`. Donor logic stays research-bridged; it does not enter the execution path.

### P2-5 — Per-lane doctrine verification (no code change)

- **Problem:** none (preventative) — confirm each new lane preserves "no composite score / no fabricated synthesis / no universal news score" and cross-lane evidence provenance.
- **Evidence:** SHARED P2/P3/P4 specs; ADR-0006; decision-research synthesis rules.
- **Fix:** add a checklist item in the conflict-detection section of `PLATFORM_COOPERATIVE_MASTER_ROADMAP.md`.
- **Acceptance:** the conflict checklist includes the doctrine bullets.
- **Closed 2026-09-05** — conflict-detection section of `PLATFORM_COOPERATIVE_MASTER_ROADMAP.md` now carries the per-lane doctrine bullets (no composite score / no fabricated synthesis / no universal news score; cross-lane evidence provenance; ADR-0006 decision-research synthesis).

---

## Item cross-reference

| Priority item | Review finding |
|---|---|
| P0-1 | Gates G1/G3/G4/G5, finding P1/D1 |
| P0-2 | S1 |
| P0-3 | L1 |
| P0-4 | S4 |
| P1-1 | S3 |
| P1-2 | S2 |
| P1-3 | P3 |
| P1-4 | L2 |
| P1-5 | D2 |
| P1-6 | V2 |
| P1-7 | H1 |
| P1-8 | H2 |
| P2-1 | P2 |
| P2-2 | P4 |
| P2-3 | H3/L3 |
| P2-4 | H4 |
| P2-5 | L4/D3 |

---

## Q-series — Quantitative correctness (2026-09-05)

Companion: [formula correctness review](2026-09-05-formula-correctness-review.md). Ledger: platform `docs/research/FORMULA_LEDGER.md` + `formula_ledger.json` (88 rows). This series pins **spec-correct math and fail-closed numerics**. It does **not** claim predictive edge, promote a champion, or open G1–G6 / LIVE-001 / P6 Shadow Run 1 / broker wires.

| Item | Status | What closed it |
|---|---|---|
| Q0 Formula ledger (units, windows, variance convention, capability class) | Closed | 88-row ledger (O10/R-O6 rows added 2026-09-05); Phase 4 aligned Q naming and friction fail-closed wording (MD family table no longer says Breeden–Litzenberger or a friction 100 default) |
| Q1 Risk-neutral Q name matches math | Closed | `MODEL_VERSION = risk_neutral_log_normal_moment_approx_v1`; not Breeden–Litzenberger |
| Q2 Labeled variance estimators | Closed | `variance_estimator` on outputs; `tests/formulas/test_variance_estimator_mixing.py` |
| Q3 Invalid OFI is not a tradable 0 | Closed | Consumers use `usable_ofi_value` / `book_state_valid` |
| Q4 Fusion friction once | Closed | `fuse_opportunity_v1` subtracts friction from gross `expected_pnl` unless already `net_expected_pnl`; fusion goldens |
| Q5 ADAM vs squeeze return definition | Closed (documented split, not unified) | Ledger + ADAM spec: ignition uses float open→close bar acceleration; squeeze `%` return is Decimal close-to-close |
| Q6 Physical P mean ≡ 0 | Closed | P−Q `directional_edge` stamped `vs_zero_drift_baseline` |
| Q7 Options friction underlying | Closed | No silent `underlying_price_assumption: 100.0`; fail closed without a positive underlying |
| Q8 Strategy identity honesty | Closed | FORECAST_MOMENTUM / whale alignments tagged `baseline_only` / `research_baseline` (naive last-value) |
| Q9 Golden numeric fixtures | Closed | `tests/formulas/test_formula_goldens.py` + squeeze/ADAM goldens; suite registered as `formulas` in `tools/validation_manifest.json` |
| Q-H2 Options O5 `DEFAULT_SPOT=100.0` | Closed | Greeks-equivalent aggregation fail-closed without positive explicit/inferred spot (`UNDERLYING_PRICE_ASSUMPTION_MISSING`, `net_*_flow=None`); volume/direction still classifies |
| Q-H1-O5 Options O5 silent `DEFAULT_VOL`/`DEFAULT_RATE` | Closed | Greeks require positive explicit/inferred vol and rate (`BSM_VOL_OR_RATE_ASSUMPTION_MISSING`); `FLOW_VERSION=options_signed_flow_v3`. Dealer/O2/O3 silent `0.05` leftover closed separately as Q-H1-rate (this row stays closed). |
| O2 surface strike×1.02/0.98 leftover | Closed | `infer_underlying_price` is fail-closed; points skipped without positive underlying; O3/dealer/strategy/event_vol no longer reconstruct spot via strike multiples. Surface version later `sigma_kt_v3` under Q-H1-rate. |
| Q-H1-rate Dealer / O2 / O3 silent `rate=0.05` | Closed | Fail-closed: missing rate → dealer `BSM_VOL_OR_RATE_ASSUMPTION_MISSING`, O3 `RATE_ASSUMPTION_MISSING`, O2 skip point. `DEALER_VERSION=options_dealer_proxy_v2`; `SURFACE_VERSION=sigma_kt_v3`; tape `rate` 0.04 on chain fixtures including O10 inline chain; chain builder stamps tape `rate` onto contract dicts (same pattern as `underlying_price`). No fusion/GARCH/HAR/ADAM/logistic calibration. |
| Q-H1-O10-rate O10 / R-O6 silent `rate=0.05` | Closed | `delta_hedged_research_snapshot` / `compose_r_o6_research_snapshot` take `rate: float \| None = None`; missing positive rate after path/strike/IV checks → `RATE_ASSUMPTION_MISSING`. Successful O10 snapshots stamp resolved `rate`. `DELTA_HEDGED_VERSION=delta_hedged_research_v2`; `R_O6_VERSION=r_o6_research_v2`. `simulate_delta_hedged_path` still requires `rate` with no default. No fusion/GARCH/HAR/ADAM/logistic calibration. |

**Still open (not edge, not trade authority):**

| Item | Why it stays open |
|---|---|
| Q-H1 Unfitted heuristic constants | Fusion 0.85/1.05, GARCH ω/α/β, HAR 0.3/0.4/0.3, ADAM weights, squeeze logistic (0.8, 0.5, 0.3) remain pinned named constants, not calibrated. Drift-guard goldens assert code matches the ledger only. Dealer/O2/O3 silent `0.05` leftover is **closed** (Q-H1-rate); O10/R-O6 silent `0.05` leftover is **closed** (Q-H1-O10-rate). Q-H1 itself stays open for those unfitted scalars only. |
| Q-H3 No Breeden–Litzenberger Q | Intentionally not implemented; Q is a log-normal moment approximation |
| Q-H4 No `SUPPORTED` / forward edge | Phase-6 scores remain naive last-close; G1–G6 stay closed |

P1-3, P1-6, P2-1, and P2-2 closed 2026-09-05 (see item sections). G1–G6 stay closed. This work grants no trade authority.
