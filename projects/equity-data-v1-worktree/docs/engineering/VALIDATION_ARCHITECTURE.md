# Validation Architecture

This document is the engineering reference for the manifest-driven validation system in `tools/validation_manifest.json`, `tools/validation_manifest.py`, `tools/validation_worker.py`, and `tools/validate.py`. The system is designed to obtain useful correctness evidence quickly while retaining the deterministic offline full suite as the authoritative regression checkpoint.

Run all commands from the repository root.

## Command reference

```powershell
python tools/validate.py fast
python tools/validate.py changed
python tools/validate.py changed --baseline <snapshot.json>
python tools/validate.py domain <domain>
python tools/validate.py full
python tools/validate.py live <provider>
python tools/validate.py live <provider> --deep
python tools/validate.py extended
python tools/validate.py benchmark
```

All modes accept `--json <path>`, `--explain`, `--verbose`, `--fail-fast`, and `--workers <n>`. The measured default worker count is 2 and must be at least 1. `--explain` prints the selection before executing it; it is not a dry-run option. `--json` atomically replaces the destination through a sibling temporary file.

`benchmark` delegates to the benchmark tooling for measurement and reporting. Benchmark results are informational and non-gating: timing variance must not turn a functional validation result into a failure. Use benchmark output to compare runner overhead or representative operations under like-for-like conditions, not as a replacement for FAST, CHANGED, DOMAIN, or FULL correctness evidence.

## Validation modes

### FAST

`fast` runs only the mandatory invariant selectors declared in the manifest. It does not discover or run every owning suite.

Invariants are sorted by manifest `order`, then ID. Invariants marked `isolated` run first in separate serial workers. All `shared` invariants are then batched, in manifest order, into one serial worker. This keeps exact selector coverage while avoiding one interpreter launch per safely shareable invariant. A missing, ambiguous, or zero-test selector is an explicit worker error.

Use FAST for very quick catastrophic-invariant feedback. Normal implementation work should generally use CHANGED because CHANGED includes these invariants for nonempty code/test selections and adds affected suites.

### CHANGED

`changed` discovers tracked unstaged changes, staged changes, tracked deletions, and nonignored untracked files. With `--baseline`, it compares the current safe file inventory with the supplied snapshot instead of using the entire pre-existing Git dirty tree.

Selection is deterministic:

1. Normalize and sort repository-relative paths; reject absolute paths and traversal.
2. Match full invalidators.
3. Match suite `test_globs` and `source_globs`.
4. For direct source ownership only, add declared offline neighbors.
5. If a full checkpoint is required, add broad core diagnostic suites.
6. Add mandatory invariant selectors for a nonempty ordinary selection.
7. Report domains that no selected suite covers.
8. Run cheap documentation or evidence checks when those file types are present.

Direct test changes select their owning suite but do not fan out to neighbors. Direct source changes do fan out. Only offline neighbors are added. Selection reasons are included in `--explain` and JSON output.

Special cases are intentionally cheaper:

- Documentation-only changes perform an encoding/readability check and run no test workers.
- Evidence/report-only changes parse existing JSON files and apply a conservative secret-pattern check; they run no test workers.
- Mixed documentation/evidence and code changes keep the affected test selection and add the applicable cheap checks.
- No changed paths means no suites and no mandatory selectors.

An executable or configuration path under `src/`, `tools/`, `ui/`, or `manifests/` with a recognized code/config suffix that has no manifest owner fails safe. CHANGED adds the broad core diagnostics, records `UNKNOWN_EXECUTABLE_PATH`, and sets `full_suite_required=true`.

### DOMAIN

`domain <name>` runs every suite that is classified `offline`, belongs to the requested domain, and has the `full` tier. Unknown domains fail before discovery. The manifest currently defines:

`core`, `short-intelligence`, `macro`, `energy`, `futures`, `options`, `order-flow`, `participant`, `sec`, and `ui`.

DOMAIN does not add the mandatory selector batch separately; the selected suite directories provide their normal full contents.

### FULL

`full` runs every manifest suite classified `offline` with the `full` tier. It never selects `live`, `extended`, or intentionally absent/excluded entries. FULL is the authoritative deterministic offline regression checkpoint.

FULL does not add the FAST selector batch as separate process launches because the owning offline suites already contain those tests.

### LIVE

`live <provider>` selects only manifest suites classified `live` for that provider. Unknown or unconfigured providers fail before discovery. Current provider identifiers are `cboe`, `cftc`, `eia`, `finra`, `fred`, `moomoo`, `nasdaq`, `nyse`, `sec`, `sec_ftd`, and `weather`; the manifest remains the canonical inventory.

All live suites are `LIVE_EXCLUSIVE`, so they run serially. The orchestrator removes every known live gate from each child environment and then enables only the gate or gates mapped to the selected provider. Gates are child-process-local; the parent environment is not mutated. Secrets are not printed, and worker/orchestrator diagnostics apply conservative credential redaction.

`--deep` is accepted, but currently has no selection effect because the manifest has no separately owned deep-live suite directories.

### EXTENDED

`extended` selects only suites classified `extended`. These are intended for deterministic expensive, adversarial, replay, or exhaustive checks that do not belong in the common loop. The current manifest contains no extended suites, so the current command completes with zero selected tests. Moving coverage out of FULL requires separate evidence that FULL retains the unique correctness contract.

The manifest owns Python `unittest` directories under `tests/`. The separately configured frontend Vitest surface under `ui/src` was not part of the historical Python runner and remains an explicit external boundary (`cd ui; npm run test`). FULL preserves the complete historical Python offline surface; it does not claim to replace the frontend package's own test command.

## The canonical manifest

`tools/validation_manifest.json` is the only canonical suite inventory. Do not reproduce suite lists in runners or documentation. Each entry owns one test-directory path and declares its classification, tiers, domains, scheduling safety, resource weight, direct source/test globs, neighbors, and live metadata where applicable. The top level also declares domains, full invalidators, and ordered mandatory invariants.

`tools/validation_manifest.py` is a standard-library-only, side-effect-free loader. It returns frozen typed records and, before test discovery, rejects unsafe or ambiguous configuration including:

- duplicate suite IDs or owned paths;
- invalid classifications, safety classes, domains, relative globs, weights, or selector syntax;
- unknown neighbors;
- live suites placed in the offline `full` tier or missing a provider;
- intentionally absent/excluded entries without a reason;
- existing test directories with tests but no owner;
- configured directories that do not exist, or intentionally absent directories that do exist.

Manifest validation checks mandatory selector syntax and statically verifies that each file, class, and method exists without importing test modules. The worker repeats exact runtime resolution when FAST or CHANGED executes the selector.

The allowed safety classes are `PARALLEL_SAFE`, `SERIAL_REQUIRED`, `LIVE_EXCLUSIVE`, `RESOURCE_HEAVY`, and `GLOBAL_STATE_MUTATION`. The allowed classifications are `offline`, `live`, `extended`, `intentionally_absent`, and `intentionally_excluded`.

## Direct ownership, neighbors, and invalidators

`source_globs` and `test_globs` are explicit ownership declarations. A path can match more than one suite when a shared boundary genuinely affects more than one owner. Suites retain manifest order in the final selection.

`neighbors` express integration boundaries. They are one-hop, declared relationships rather than a recursively inferred dependency graph. A neighbor is selected only when a changed path directly matches the source glob of the originating suite. Changing a test file does not trigger neighbors, and live neighbors are never pulled into CHANGED.

`full_invalidators` identify validation infrastructure and shared correctness boundaries whose changes require the authoritative offline checkpoint. The current categories include:

- the manifest, loader, worker, CLI, compatibility runner, and benchmark path;
- canonical and shared contract/provider-envelope code;
- data-quality and offline-network enforcement;
- risk simulation, replay, and dependency-lock boundaries;
- bitemporal store and PIT join implementation.

The exact globs live only in `tools/validation_manifest.json`.

### `full_suite_required` is a gate, not an expansion

CHANGED is not equivalent to FULL when its output contains:

```text
full_suite_required=true
```

This flag is set by a full invalidator or an unknown executable/configuration path. The changed run still executes mandatory invariants, directly affected suites, declared neighbors, and broad core diagnostics. It deliberately does **not** silently expand to every offline suite.

A passing CHANGED result with `full_suite_required=true` is preliminary diagnostic evidence only. The implementation cannot be considered finally validated until `python tools/validate.py full` also passes at the major/final checkpoint. CI and agents must preserve and enforce that distinction.

## Worker and scheduling model

Each suite is one isolated Python subprocess. A controlled selector collection is also one subprocess. A worker uses `unittest.TestLoader` and a custom `unittest.TestResult`; canonical counts never come from scraping console output.

The worker emits exactly one JSON object containing suite/selectors, PID, status, discovery and wall time, exact outcome counts, per-test durations, the ten slowest tests, sanitized failure/error details, and optional fixture-I/O measurements. Suite discovery uses `test_*.py`. Stable explicit selectors have the form:

```text
tests/path/test_file.py::TestClass::test_method
```

Selector files do not need to be importable packages. The worker loads the file, flattens its discovered suite, and requires exactly one class/method match. Import failures, zero tests, malformed JSON, missing output, abnormal worker exits, and invalid selector matches become explicit errors.

The orchestrator schedules work in this order:

1. Mandatory invariant jobs serially.
2. `SERIAL_REQUIRED`, `GLOBAL_STATE_MUTATION`, and `LIVE_EXCLUSIVE` suites serially.
3. `PARALLEL_SAFE` suites with up to `--workers` concurrent subprocesses.
4. `RESOURCE_HEAVY` suites with at most `min(2, workers)` concurrent subprocesses.

The default is 2 workers. Representative macro-domain medians measured during this package were 23.86 seconds at 1 worker, 7.27 seconds at 2, 7.42 seconds at 4, and 8.03 seconds at 8; 2 is the smallest count within ten percent of the best median. `resource_weight` is retained in job metadata, but the current scheduler does not perform weighted admission; the separate two-worker heavy cap is the active resource control.

`--fail-fast` stops scheduling new jobs after a failure. Already running parallel children are allowed to finish. On `KeyboardInterrupt`, the invocation stops scheduling and terminates only child processes registered by that invocation. Invalid worker output and crashes are reported as orchestration errors. Output result ordering follows mandatory/manifest order, not completion order.

## Snapshot-based change isolation

The public helper `create_baseline_snapshot(repository_root)` returns a snapshot object with `schema_version` and a sorted `files` array. Each file entry contains only:

- repository-relative path;
- SHA-256 hash;
- `tracked` or `untracked` classification.

The inventory uses Git's tracked and nonignored-untracked file lists. It excludes `.env*`, common credential filenames, and common certificate/keystore suffixes. It stores no file contents. Snapshot creation is currently a Python API, not a `validate.py` subcommand; the caller is responsible for serializing it safely.

`changed --baseline <snapshot.json>` validates the snapshot schema, path safety, hashes, and classifications, then compares it with the current inventory. Added, removed, modified, and tracked/untracked classification changes are selected. A snapshot stored inside the repository excludes its own path from the current comparison so it does not self-invalidate.

Use a package baseline only when work must be isolated from a pre-existing dirty tree. Ordinary development should use Git-based CHANGED.

## Offline network policy

FAST, CHANGED, DOMAIN, FULL, and EXTENDED do not enable live provider gates. Before every child launch, the orchestrator removes all known live gates inherited from the parent environment. Only explicit LIVE mode re-enables the selected provider's gates, and only in that provider's child.

The offline network-denial regression is a mandatory FAST invariant and is also part of the offline phase-zero suite exercised by FULL. Tests must use immutable captured fixtures or local deterministic data in offline modes. Adding a skip that masks an offline network attempt is not an acceptable fix.

The gate cleanup prevents accidental live-test authorization; the network guard remains the enforcement layer tested by the invariant. New providers must add both manifest live ownership and an explicit child-gate mapping before LIVE can run them.

## Result interpretation

The concise terminal summary reports overall status, mode, tests, skips, failures, errors, and wall time. Nonpassing workers are printed automatically; `--verbose` prints every worker. JSON output additionally includes changed files, selected suites and reasons, omitted domains, mandatory selectors, `full_suite_required`, global reasons, worker/heavy-worker counts, process launches, structured totals, per-worker results, cheap-check results, suites not run because of fail-fast/interruption, and interruption state.

Timing data is observational. Compare like-for-like mode, worker count, machine load, and fixture-profile settings. Do not convert wall-clock targets into functional assertions or weaken isolation/PIT/security checks to obtain a faster number. Use validation JSON timing fields for runner evidence and benchmark output for non-gating performance analysis.

## Required cadence for future implementation agents

Use this exact validation cadence:

```text
EDIT 1
  -> python tools/validate.py changed

EDIT 2
  -> python tools/validate.py changed

EDIT 3
  -> python tools/validate.py changed

DOMAIN MILESTONE
  -> python tools/validate.py domain <domain>

FINAL IMPLEMENTATION / MAJOR CHECKPOINT
  -> python tools/validate.py full        # once

LIVE PROVIDER MODIFIED
  -> complete the applicable offline validation first
  -> python tools/validate.py live <provider>   # once
```

After every CHANGED run, inspect the exit status and `full_suite_required`. If the flag is true, record that FULL remains required and run FULL once at the final major checkpoint even when CHANGED passed. Do not run FULL after every intermediate edit. If a change crosses several domains, run each applicable domain checkpoint or advance to the final FULL checkpoint. Run LIVE only for a provider whose live boundary changed, after offline validation; LIVE never substitutes for FULL.
