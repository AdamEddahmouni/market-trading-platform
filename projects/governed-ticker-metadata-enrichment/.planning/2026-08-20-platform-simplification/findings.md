# Platform Simplification Findings

## Requirements

- Preserve or strengthen correctness, PIT/bitemporal semantics, security, provenance, provider neutrality, live/offline separation, governance, and regression protection.
- Measure before optimizing; no fabricated baselines or reductions.
- Preserve canonical comprehensive offline validation while making changed and domain validation first-class.
- Add a small mandatory invariant suite, auditable changed-file mapping, explicit full-suite invalidation, structured results, and safe live/extended separation.
- Benchmark process models and worker counts; reject flaky or unsafe parallelism.
- Do not reset, clean, stash, commit, push, add data sources, or modify donor/reference projects.

## Repository Truth

- Canonical repository: `C:/Users/adame/Desktop/market-trading-platform/integrated-market-platform`.
- Branch: `main`.
- HEAD: `7d286de34be6dcc051e7cf31c726a5d1cd5bf4bb`.
- Working tree is intentionally large and dirty; `tools/run_all_tests.py` already has user changes.
- Current `tools/run_all_tests.py` hard-codes 53 directories, iterates serially, launches `python -m unittest discover` once per existing directory, captures text output, and derives counts by parsing console lines.
- Filesystem inspection found 51 test directories. `live_moomoo` exists but is not configured. The configured list includes three absent phase directories (`phase9`, `phase10`, `phase11`), so reported 53 configured / 50 discovered is consistent with current code while omitting one existing live suite.
- The runner's current 53-entry state is itself part of the user's uncommitted work: the committed runner had fewer suites and approximate stdout-only counting. Any runner refactor must preserve those additions while replacing fragile parsing.
- The suite already has an offline socket/subprocess guard (`tests/phase0/test_offline_guard.py`) and provider-specific PIT/security regression tests that can seed the mandatory fast-core set.
- Static inspection found one explicit offline sleep (`tests/short_intelligence/test_short_intelligence.py`, 50 ms), repeated per-test fixture reads in short-intelligence/order-flow suites, and many correctly scoped temporary-directory tests. These are hypotheses for profiling, not yet proven dominant costs.

## Initial Design Implications

- A single canonical manifest should classify suites by mode, domain, safety, and dependency impact.
- A compatibility-preserving full runner should consume structured worker results instead of parsing human output.
- Changed selection must always add explicit critical-invariant suites and fan out shared-core changes.
- Process isolation is the safest initial boundary; in-process execution should be adopted only after order-contamination measurements.
- Production/provider simplification is downstream of measured bottlenecks and should remain out of the initial runner/selector stage.
- `FULL OFFLINE` versus legacy live-suite discovery is the first design question because it changes backward compatibility and canonical test counts.
- Decision: both `tools/run_all_tests.py` and `tools/validate.py full` will be strictly offline. Live suites will be reachable only through explicit `validate.py live <provider>` commands.
- Approved architecture: canonical JSON manifest, typed loader, structured subprocess worker, conservative suite-level parallelism, auditable changed selection, and exact existing test IDs for fast-core invariants.

## Issues Encountered

| Issue | Resolution |
|---|---|
| No private subagent/delegation tool is exposed | Run independent read-only command audits concurrently and integrate edits centrally |
| First large prompt/repository probe was truncated | Use smaller line-ranged reads and persist findings here |
| Initial guesses for `tests/contracts/test_reference_contract.py` and `tests/market_data/test_market_data_p0.py` were wrong | Enumerated actual files and used `test_futures_contract.py`, `test_observational_boundary.py`, and runtime PIT tests instead |
