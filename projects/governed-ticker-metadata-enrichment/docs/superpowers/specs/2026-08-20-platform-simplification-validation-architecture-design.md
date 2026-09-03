# Platform Simplification and Validation Architecture

**Status:** Approved for implementation planning  
**Spec date:** 2026-08-20  
**Scope:** Test-performance measurement, manifest-driven validation, safe selection, deterministic process isolation, and measured low-risk simplification  
**Repository:** `integrated-market-platform` at historical HEAD `7d286de34be6dcc051e7cf31c726a5d1cd5bf4bb`

## 1. Purpose

The repository has outgrown an all-tests-after-every-edit workflow. The objective is to minimize the cost of obtaining high-confidence correctness evidence while retaining a canonical comprehensive offline suite and explicit provider live validation.

This package changes engineering infrastructure, not trading behavior. It adds no data source and does not alter signals, strategy thresholds, model formulas, risk, broker behavior, or execution.

## 2. Constraints

- The intentional dirty tree is user-owned. It must not be reset, cleaned, stashed, staged, committed, or pushed.
- Baseline and final figures must be measured from the current repository; historical counts are context, not acceptance evidence.
- Correctness, PIT/bitemporal semantics, provenance, security, provider neutrality, governance, and live/offline separation take priority over speed.
- Existing unique regression tests remain in the full suite unless replacement coverage is demonstrated before removal.
- Provider-specific clocks and semantics remain local to their providers.
- Python standard-library tooling remains the default. Migrating the suite to pytest is out of scope unless measurements prove a decisive benefit; no such migration is planned.
- Network access is forbidden in offline validation.

## 3. Chosen approach

Use a manifest-driven subprocess runner with structured results and conservative suite-level parallelism.

This retains process isolation for tests that mutate globals or environment state, removes repeated configuration lists and text parsing, allows targeted validation, and permits safe parallelism without rewriting existing `unittest` tests.

Rejected as the default:

- One in-process `unittest` run: lower startup cost but unacceptable contamination risk until suite-order experiments prove safety.
- A pytest migration: excessive churn, dependency cost, and dirty-tree conflict for the expected benefit.
- Test-case thread pooling: unsafe for environment, filesystem, singleton, and network-gate mutation.

## 4. Components and responsibilities

### 4.1 `tools/validation_manifest.json`

This is the only canonical suite inventory. It contains:

- `schema_version`
- suite ID and test directory
- offline or live classification
- validation tiers
- domain memberships
- parallel-safety class
- resource weight
- direct source/test path globs
- neighboring integration dependencies
- mandatory invariant test IDs
- full-suite invalidation globs
- intentionally absent or superseded suite records

Allowed safety classes are:

- `PARALLEL_SAFE`
- `SERIAL_REQUIRED`
- `LIVE_EXCLUSIVE`
- `RESOURCE_HEAVY`
- `GLOBAL_STATE_MUTATION`

Every test directory must be classified exactly once as configured, intentionally excluded, or intentionally absent. An existing but unclassified directory is a manifest error. A configured missing directory is a manifest error unless it has an explicit absence classification and reason.

### 4.2 `tools/validation_manifest.py`

This module loads and validates the JSON manifest. It exposes typed immutable records to the CLI, worker orchestration, benchmark tool, and tests. It performs no test discovery and no network or provider initialization at import time.

### 4.3 `tools/validation_worker.py`

A worker receives one suite or an explicit list of selectors, uses `unittest.TestLoader`, and emits one JSON result. Exact selectors use the repository-stable form `tests/path/test_file.py::TestClass::test_method`; the worker discovers the file and filters the resulting suite by class and method rather than requiring test directories to be importable packages. A custom `TestResult` records:

- tests run
- passes
- skips
- failures
- errors
- expected failures and unexpected successes
- wall time
- per-test durations
- discovery duration
- fixture-file opens when profiling is enabled

Human console output is diagnostic only and is never parsed for counts. Worker crashes and malformed output become explicit orchestration failures.

### 4.4 `tools/validate.py`

This is the primary developer interface:

```text
python tools/validate.py fast
python tools/validate.py changed
python tools/validate.py changed --baseline <snapshot.json>
python tools/validate.py domain <name>
python tools/validate.py full
python tools/validate.py live <provider> [--deep]
python tools/validate.py extended
python tools/validate.py benchmark
```

Shared options include `--json <path>`, `--explain`, `--verbose`, `--fail-fast`, and `--workers <n>` where the selected mode permits them.

Default output is concise. Failures include complete diagnostics. JSON output is deterministic apart from documented timestamps and durations and contains selected suites, selection reasons, omitted suites, counts, wall time, and `full_suite_required`.

### 4.5 `tools/run_all_tests.py`

This remains available but becomes a compatibility wrapper for `validate.py full`. Both commands run strictly offline suites. No `tests/live_*` directory is discovered or skipped by full validation.

### 4.6 `tools/benchmark.py`

This non-blocking benchmark tool measures runner overhead and representative production/replay operations. It writes results only when explicitly given an output path. Benchmarks are informational and do not become timing-sensitive functional tests.

## 5. Validation ladder

### FAST

Runs the mandatory invariant IDs first. It is intentionally small and suitable after frequent edits.

### CHANGED

Collects changed tracked and untracked paths, maps them through the manifest, adds mandatory invariants and neighboring boundaries, and reports what was omitted. Unknown code paths fail safe by setting `full_suite_required` and selecting broad core validation.

### DOMAIN

Runs all offline suites assigned to one auditable domain. Initial domains are `core`, `short-intelligence`, `macro`, `energy`, `futures`, `options`, `order-flow`, `participant`, `sec`, and `ui`. The final memberships are derived from imports and current cross-source integration tests during the audit stage.

### FULL

Runs every configured offline suite. It is the canonical comprehensive validation path and is used at major checkpoints and final acceptance.

### LIVE

Runs only explicitly selected `tests/live_*` suites. The command sets provider gates only in child-process environments. Missing credentials or services skip safely; secrets are never emitted. `--deep` selects separately classified deep checks.

### EXTENDED

Runs deterministic expensive replay, adversarial, exhaustive, or benchmark-oriented suites excluded from the common loop. Moving a test here requires evidence that fast/full retain its unique correctness contract or that the test is a genuinely distinct acceptance benchmark.

## 6. Mandatory fast-core invariants

The initial fast suite references precise existing tests so failures remain diagnosable:

| Invariant | Existing test ID |
|---|---|
| No future data / bitemporal version selection | `tests/runtime/test_bitemporal_store.py::BitemporalStoreTests::test_correction_invisible_before_known_from` |
| Provider PIT revision exclusion | `tests/fred/test_fred.py::FredRevisionTests::test_no_lookahead_current_revision` |
| `UNKNOWN != 0` | `tests/fred/test_fred.py::FredNormalizeTests::test_missing_dot_is_unknown_not_zero` |
| Withheld source value is not zero | `tests/eia/test_eia.py::EiaNormalizeTests::test_withheld_value_not_zero` |
| Source failure is not a negative/zero state | `tests/cftc/test_cftc_cot.py::CotSourceOutageTests::test_source_unavailable_not_zero_positions` |
| Unconfigured provider fails closed | `tests/providers/test_providers.py::ProviderContractTests::test_unconfigured_stubs_fail_closed` |
| Provider provenance remains explicit | `tests/market_data/test_observational_boundary.py::MarketDataNormalizationTests::test_provider_ticker_direction_is_not_ground_truth` |
| Observational data is not admitted automatically | `tests/market_data/test_observational_boundary.py::MarketDataNormalizationTests::test_admission_requires_authorization` |
| Live and replay clocks remain separate | `tests/market_data/test_observational_boundary.py::MarketDataNormalizationTests::test_live_and_replay_envelopes_preserve_pit_clocks` |
| Contract serialization round-trip | `tests/contracts/test_futures_contract.py::FuturesCurveTests::test_positioning_snapshot_round_trip` |
| Missing PIT reference data fails closed | `tests/runtime/test_pit_joins.py::PitJoinTests::test_missing_join_fail_closed` |
| Secret findings contain no secret/context | `tests/phase0/test_credential_audit.py::CredentialAuditTests::test_match_output_contains_no_value_or_context` |
| No undeclared live execution authority | `tests/phase0/test_registry.py::RegistryTests::test_unknown_identifier_fails_closed` |
| Offline network access is denied | `tests/phase0/test_offline_guard.py::OfflineGuardTests::test_ipv4_ipv6_loopback_and_dns_are_denied` |

The audit may add an existing test only when it closes a named invariant gap. It may not replace this set with an opaque mega-test.

## 7. Changed-file selection

Default `changed` uses Git porcelain status with untracked files included. Selection operates in this order:

1. Normalize repository-relative paths and reject paths outside the repository.
2. Apply full-suite invalidation rules.
3. Map direct source and test paths to suites.
4. Add domain neighbors and cross-source boundaries.
5. Add the mandatory invariant IDs.
6. Order critical invariants before affected suites.
7. Explain every selected suite and every intentionally omitted domain.

Documentation-only changes run JSON/schema/reference checks without market simulation tests. Evidence-only changes run format, schema, and sanitization checks. Test-only changes run the owning suite plus relevant invariants. Unknown executable/configuration paths fail safe.

Shared-core changes set `full_suite_required: true`. Changed mode still provides fast diagnostic feedback; the subsequent full run is an explicit checkpoint rather than being silently launched after every edit. CI or agents must treat the flag as a required final gate.

Full invalidators include the manifest and runner, P0 store/join code, canonical temporal contracts, global serialization, common provider envelopes/transport, quality engine, offline guard, and simulation core.

## 8. Dirty-tree baseline

The current dirty tree predates this package. A baseline snapshot records repository-relative changed paths and SHA-256 content hashes for non-ignored, non-secret files. It excludes `.env`, credential-like paths, ignored files, and file contents.

`validate.py changed --baseline <snapshot>` compares current hashes with that snapshot so final acceptance can validate only this package's edits. Ordinary future use requires no snapshot and compares against Git state.

## 9. Runner execution model

Each suite remains a process-isolation unit. The orchestrator runs:

1. mandatory invariant IDs serially and fail-first;
2. `SERIAL_REQUIRED` and `GLOBAL_STATE_MUTATION` suites serially;
3. `PARALLEL_SAFE` suites in a bounded process pool;
4. `RESOURCE_HEAVY` suites with a separately capped concurrency;
5. live suites only in explicit live mode.

Worker count is selected from measured 1-, 2-, and 4-worker representative runs plus a capped logical-CPU candidate. The default is the smallest count within ten percent of the best median time, favoring lower resource use and determinism. A user override remains available.

The baseline full run uses the existing runner once. Architecture stabilization uses one full parallel run. Final acceptance uses one additional full parallel run. This satisfies the requested maximum of three full-suite executions while providing two optimized parallel runs for flakiness comparison.

## 10. Failure and interruption behavior

- Invalid manifest: exit before discovery with actionable validation errors.
- Unknown changed code path: run fast/broad core and set `full_suite_required`.
- Worker crash, timeout, or malformed result: mark the suite errored and return nonzero.
- Keyboard interrupt: stop scheduling, terminate only child workers started by the current command, and return nonzero.
- `--fail-fast`: stop scheduling new work after the first failure; it is never forced for full validation.
- JSON write: write atomically through a sibling temporary file and replace only after successful serialization.
- Diagnostic sanitization: use existing credential redaction rules; never include environment values.

## 11. Measurement architecture

`evidence/performance/test-baseline.json` and `test-final.json` contain:

- timestamp and Python/platform versions
- manifest/configured/discovered suite counts
- executed, pass, skip, failure, and error counts
- total wall, discovery, and orchestration time
- per-suite and slowest-test timings
- interpreter launches and measured startup distribution
- estimated serial compute and parallelizable compute
- fixture opens/bytes for repository test fixtures when profiling is enabled
- worker-count benchmark results

Import audits use standard `-X importtime` and focused timing harnesses. Fixture I/O uses worker-local Python audit events for repository fixture paths, avoiding changes to production file APIs. Production benchmarks use immutable fixtures and fixed decision times for PIT lookup, macro state, energy context, short-pressure state, registry lookup, and representative simulation operations.

## 12. Simplification stages

1. Capture baseline and bottleneck evidence without changing behavior.
2. Add manifest/parser/worker/CLI with test-first behavior.
3. Adopt measured safe parallelism and the compatibility wrapper.
4. Optimize proven fixture, import, sleep, or repeated-initialization costs.
5. Build duplication matrices for tests and provider infrastructure.
6. Extract only stable shared primitives with regression coverage.
7. Remove dead code only with static references, replacement evidence, and targeted tests.

No test consolidation or provider refactor occurs merely because code looks repetitive. Shared testing mechanics may be extracted; provider clock semantics remain local.

## 13. Testing strategy

New validation infrastructure is developed test-first under `tests/validation` using temporary synthetic repositories and tiny synthetic suites. Tests cover:

- manifest schema and inventory drift
- precise structured counts
- changed-path mapping and explanations
- untracked files and dirty-tree snapshots
- mandatory invariant fan-out
- full invalidation flags
- documentation/evidence/test-only paths
- offline/live separation and child-only live gates
- worker crash and interruption handling
- deterministic ordering and JSON output
- parallel safety classification
- compatibility-wrapper delegation

Controlled mutation checks must prove the fast suite catches a PIT leak, `UNKNOWN -> 0`, secret leakage, wrong authority routing, FRED V1/V2 timing confusion, and EIA period/availability confusion. Each mutation is temporary and immediately reverted without using destructive Git commands.

## 14. Acceptance

Acceptance requires measured evidence that:

- baseline, slowest tests, startup, discovery, import, fixture I/O, and worker-count results exist;
- fast, changed, domain, full, live, and extended modes are explicit and documented;
- the three absent configured directories and omitted `live_moomoo` directory are classified;
- structured test counts replace text parsing;
- fast passes three consecutive runs;
- optimized parallel full passes twice within the three-run package budget;
- changed validation explains selection and reports omissions;
- full offline includes every configured offline suite and no live suite;
- live gates remain explicit and offline network denial remains covered;
- PIT, bitemporal, FRED, CFTC, EIA, unknown/missing, provenance, admission, and security invariants remain covered;
- production/trading fixture outputs and canonical hashes remain unchanged unless a separately versioned schema change is approved;
- nothing is staged, committed, or pushed.

Performance targets are evaluated only after the baseline exists. Missing a speed target is reported honestly and does not justify weakening correctness.

## 15. Documentation and agent workflow

`docs/engineering/VALIDATION_ARCHITECTURE.md` documents commands, tiers, domains, selection, invalidators, live rules, and benchmark interpretation. Repository guidance will direct future agents to:

```text
edit -> validate changed
domain checkpoint -> validate domain <name>
major/final checkpoint -> validate full once
live provider change -> validate live <provider> once after offline validation
```

## 16. Deliberate tradeoffs

- Process isolation is retained even where in-process execution might be faster until contamination testing proves otherwise.
- The manifest is explicit and somewhat verbose because opaque inference would create unsafe under-testing.
- Full invalidation is reported rather than automatically launched during every changed run, preserving fast feedback while keeping the required final gate visible.
- The initial package adds no caching across decision times or source versions; any later cache requires a complete PIT-safe key and benchmark evidence.
- Existing unique tests and provider-specific semantics are retained even when consolidation would reduce line count.
