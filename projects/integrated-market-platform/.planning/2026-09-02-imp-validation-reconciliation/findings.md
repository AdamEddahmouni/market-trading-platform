# Findings — IMP Validation-Baseline Reconciliation

## Initial repository state

- Canonical Git root: `C:/Users/adame/Desktop/market-trading-platform/integrated-market-platform`.
- Branch: `feat/p6-shadow-run-1-forward-validation`.
- HEAD: `be67b4954cde59ed19c66d9d90b3fe7a4b698bfa`.
- Upstream: `origin/feat/p6-shadow-run-1-forward-validation`.
- Ahead/behind: ahead `1`, behind `0`.
- No staged changes; tracked and untracked work is already present.
- Initial status contained dirty provider/news/IBKR/Finviz work plus IMP
  runtime/contracts/tests and existing root planning files.

## Authority and command evidence

- Repository instructions require CPython 3.11 from `.venv`, `PYTHONPATH=src`,
  `tools/validate.py changed` after edits, and `full` for Paper safety and
  major checkpoints.
- `docs/engineering/VALIDATION_ARCHITECTURE.md` defines manifest ownership,
  structured worker results, changed selection, full-only expansion, and
  `full_suite_required`.
- Root planning files are pre-existing user-owned untracked work and are
  intentionally untouched by this scoped reconciliation.

## Baseline evidence

- Prior exact authoritative commands are retained in the terminal evidence:
  `changed` = `1232 tests, 9 skipped, 1 failure, 91 errors` in `530.542s`;
  `full` = `2209 tests, 9 skipped, 1 failure, 92 errors` in `734.902s`.
  Fresh structured receipts are running with the current worktree.
- Required IMP-focused suites independently passed in a forward order:
  `144 tests, 144 passed, 0 skipped, 0 failures, 0 errors`.
- The same required suites independently passed in reverse order:
  `144 tests, 144 passed, 0 skipped, 0 failures, 0 errors`.
- Fresh-process imports of the recent IMP packages pass. Importing
  `market_platform_foundation.strategy` loads 1703 modules and takes about
  10.8 seconds, while the narrower contract/persistence/paper imports pass in
  about 0.4–2.5 seconds; this is package-init expansion evidence, not a cycle
  by itself.
- The repository venv resolves `tests` to
  `.venv/Lib/site-packages/tests/__init__.py`; the repository `tests/` tree has
  no root or `tests/intelligence/__init__.py`. Direct application imports that
  eagerly load `system_acceptance.golden_lifecycle` therefore reproduce
  `ModuleNotFoundError: No module named 'tests.intelligence'`. A namespace shim
  makes the required IMP suites pass, so this is an import/collection graph
  boundary requiring classification and controlled comparison before repair.
- `MongoSchemaManager` registers `RECORD_CODECS` collections, while
  `ALLOCATION_DECISION_VALIDATOR` and allocation indexes exist separately and
  are not registered in `COLLECTION_SPECS`; the Mongo repository accesses an
  `allocation_decisions` collection directly. This is a concrete schema
  registration gap to verify against history and tests before any repair.

## Authoritative failure inventory

- Stable full baseline: `2209 tests, 9 skipped, 1 failure, 92 errors` in
  `467.654s`. Errors: 84 intelligence collection errors, 4 platform errors,
  1 Finviz error, 1 UI1 error, 1 UI2 error, and 1 validation error. The
  collection errors all terminate with `ModuleNotFoundError: No module named
  'tests.intelligence'` because the venv's regular `tests` package shadows the
  repository namespace package.
- Concurrent changed run: `1232 tests, 9 skipped, 1 failure, 92 errors` in
  `349.859s`; the same 91 collection/related errors as full plus a
  phase-zero `FileExistsError` from two independent invocations racing on
  `.venv-phase0-collector-test`. The prior sequential exact changed command
  was `1232 tests, 9 skipped, 1 failure, 91 errors` in `530.542s`.
- Changed-only validation failure:
  `tests/validation/test_validation_manifest.py::ValidationManifestTests::test_repository_manifest_classifies_every_test_directory`,
  `AssertionError: 50 != 49`; current dirty provider/news additions add one
  offline test directory beyond the stale hard-coded expectation.
- Full-only additional error:
  `tests/ui2/test_ui2_api.py` collection (`_FailedTest::test_ui2_api`), same
  `tests.intelligence` collision. CHANGED excludes it because none of the
  current changed paths directly owns `ui2` and the declared neighbor closure
  reaches `ui1` but not `ui2`; FULL selects every offline suite.
- Shared unrelated validation error:
  `tests/validation/test_repository_closure.py::CanonicalRepositoryClosureAuditTests::test_canonical_audit_is_complete_non_destructive_and_uses_closed_vocabulary`,
  `ClosureAuditError` for `src/market_platform_foundation/news`,
  `src/market_platform_foundation/tests`, `tools/news`, and
  `tools/provider_readiness.py`; these are current dirty provider/news work.
- After adding the repository package markers, isolated `platform` passed
  `425/425` with 2 skips, `finviz` passed `57/57`, `ui1` passed `13/13`,
  `ui2` passed `5/5`; isolated `intelligence` collected and ran
  `1147 tests` with `1120 passed, 25 skipped, 2 failures, 0 errors`. The
  remaining intelligence failures are
  `test_forward_qualification::RunnerTests::test_run_forward_qualification`
  (`INVALID_RUNTIME_INTEGRITY` absent) and
  `test_routing_replay_integration::RoutingReplayIntegrationTests::test_replay_visible_repository_retains_repository_protocol`
  (runtime-checkable protocol assertion), both in unchanged pre-existing
  subsystems.
- Mongo schema repair is now covered by 9 isolated schema tests passing; the
  manager registers the direct `allocation_decisions` sidecar collection and
  its two indexes without adding it to the canonical contract codec registry.
- The required IMP-dependent selection (23 modules, including strategy
  definition/match/scanner, universal opportunity, clustering, comparison,
  allocation persistence, adapters, accounting, attribution, runtime,
  settlement/learning, schema, execution qualification/governance, P0/P1/P3/
  P31, decision snapshots, broker P4, and Moomoo P4c) passed in both orders:
  `253/253`, no skips/failures/errors per order. Per-module receipts are in
  terminal evidence; the aggregate run took 70.1 seconds.
- Static AST import audit across the requested IMP areas found 89 modules,
  341 internal edges, and no cycles. No top-level Mongo/network/file-write
  side effects were found by the targeted side-effect scan. The broad
  `strategy` package `__init__` exports seven submodules (including runtime,
  scanning, and learning), explaining import expansion; the narrower
  contract/opportunity/persistence/paper imports remain bounded.
- The fixed-name phase0 selector was independently rerun in a fresh worker:
  `tests/phase0/test_pipeline.py::EvidenceTests::test_collector_excludes_generated_environment_paths`
  passed (`1/1`, 31.246s). The original `FileExistsError` is therefore a
  concurrent-worker race on `.venv-phase0-collector-test`, not a deterministic
  IMP failure.
- Repaired changed gate completed in `448.381s`: `2170 tests, 34 skipped,
  3 failures, 1 error`; intelligence contributed the two unchanged failures
  above, while validation contributed the manifest count failure and closure
  error above. No `tests.intelligence` collection errors remain.
- Final full gate completed in `794.558s`: `3151 tests, 34 skipped,
  3 failures, 1 error` (`3113` passes). The structured receipt is
  `C:/Users/adame/AppData/Local/Temp/imp-validation-full-repaired.json`.
- Final changed structured receipt is
  `C:/Users/adame/AppData/Local/Temp/imp-validation-changed-final.json`;
  its summary matches the full failure set and reports
  `2170/34/3/1`.
- UI verification passed: 80 test files and 421 tests; build and TypeScript
  typecheck both exited 0. Documentation links passed for 134 governance
  Markdown files; `git diff --check` and targeted Python compilation passed.
