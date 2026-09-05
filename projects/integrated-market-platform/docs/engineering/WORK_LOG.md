# IMP Work Log

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
| **Related** | [Monorepo workflow](../../../docs/MONOREPO_WORKFLOW.md); PRs #11–#14 in the archived child repository |
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

## Planned (not started)

| Item | Area | Notes |
|------|------|-------|
| Master-account login before Mode Launcher | `ui/auth` | User idea: single login provisions connected broker/data APIs; not concrete yet |
