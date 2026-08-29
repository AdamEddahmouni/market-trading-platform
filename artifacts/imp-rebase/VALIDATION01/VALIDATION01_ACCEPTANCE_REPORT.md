# IMP-VALIDATION-01 Baseline Suite Root-Cause & Repair Report

Disposition: `IMP_VALIDATION_01_COMPLETE`

Campaign: baseline full-suite failure/error isolation after IMP-OF-01.
Repair branch: `fix/imp-validation-01-baseline-suite`
Starting HEAD: `36cf53b60cfdf1ea48d19312fef1918573ba3375`

## Repository isolation

```text
Repository:           C:\Users\adame\Desktop\market-trading-platform\integrated-market-platform
Original checkout:    C:\Users\adame\Desktop\market-trading-platform\integrated-market-platform
Original branch:      cloud/build-35-release-governance-operational-acceptance
Original HEAD:        44800d2e210e58ff5759c44cc343dd4578c0b821
Original dirty state: preserved (BUILD33 artifacts, README, roadmap, evidence/ui1, untracked reports)

Repair worktree:      .worktrees/imp-validation-01
Repair branch:        fix/imp-validation-01-baseline-suite
Starting HEAD:        36cf53b60cfdf1ea48d19312fef1918573ba3375

Base comparison:      .worktrees/imp-validation-01-base (detached)
Base comparison HEAD: 1e967613da2316cb2a821b3ac5c77745ae3ca440
```

Preserved worktrees include the original checkout, `imp-of-01-runtime`, `imp-of-01-design`, `imp-of-01-spec-review`, REBASE worktrees, `imp-adapt-00-learning-ecosystem`, and other existing linked worktrees. None were reset, cleaned, force-checked-out, or force-pushed.

Environment used in both comparison worktrees:

```text
Python: C:\Users\adame\Desktop\market-trading-platform\integrated-market-platform\.venv\Scripts\python.exe
Version: CPython 3.11.15
Platform: Windows-10-10.0.26200-SP0
PYTHONPATH: src
```

## Triggering anomaly

```text
Original validation command: tools/validate.py changed --explain
Why it escalated:             tools/validation_manifest.json is a full invalidator
Original test count:          712
Original skips:               6
Original failures:            1
Original errors:              1
Duration:                     299.703s
Worker clue:                  validation: failed (52 tests)
```

`FULL_INVALIDATOR` was legitimate: OF-01 edited `tools/validation_manifest.json`, which is listed under `full_invalidators`.

`UNKNOWN_EXECUTABLE_PATH` was also legitimate under current selection rules. Matching a full invalidator does not mark the path as suite-owned, and `tools/validation_manifest.json` is an executable-root `.json` that is not in the validation suite `source_globs` (those globs are mostly `tools/validation_*.py` plus related Python). Escalation was correct. OF-01's manifest update registered `tests/of01` and `src/market_platform_foundation/of01/**`; it did not need to change invalidator semantics.

Important: `full_suite_required=true` on `changed` selects core diagnostics plus owned suites; it is not `validate.py full`. The 712-test run omitted domains `short-intelligence,sec`. Canonical full is the larger offline suite.

## Exact target identities

```text
Failure test:
tests/validation/test_validation_manifest.py::ValidationManifestTests::test_repository_manifest_classifies_every_test_directory

Error test:
tests/validation/test_repository_closure.py::CanonicalRepositoryClosureAuditTests::test_canonical_audit_is_complete_non_destructive_and_uses_closed_vocabulary
```

Both lived in the `validation` worker (`52 tests, 1 failure, 1 error`), which matches the truncated original log line.

## Base-vs-current reproduction

| Target | `1e967613` | `36cf53b` | Signature equivalent? |
|---|---|---|---|
| Failure | PASS | FAIL `AssertionError: 50 != 49` | OF-01 only |
| Error | PASS | ERROR `ClosureAuditError: unclassified path: src/market_platform_foundation/of01` | OF-01 only |

```text
Failure reproduces at 1e967613: NO
Failure reproduces at 36cf53b:  YES
Same signature:                 N/A (absent on base)

Error reproduces at 1e967613: NO
Error reproduces at 36cf53b:  YES
Same signature:               N/A (absent on base)

Attribution: OF01_REGRESSION
```

The earlier OF-01 closure claim that these were pre-existing at base `1e967613` is disproved. They are incomplete OF-01 inventory registration, not baseline health debt and not OF-01 ledger-semantic regressions.

## Failure root cause

```text
classification: TEST_DEFECT
cause:          OF-01 added offline suite `of01` (manifest 49 -> 50 offline suites) without updating the inventory pin in test_repository_manifest_classifies_every_test_directory.
evidence:       Base manifest has 49 offline suites and the test expects 49 (PASS). OF-01 HEAD has 50 offline suites and still expects 49 (FAIL 50 != 49). Fails in isolation, twice, and inside the validation module.
OF-01 causal:   YES
```

Signature: `AssertionError: 50 != 49` at `tests/validation/test_validation_manifest.py:175`.

OF-01 did not cause this by changing ledger semantics. It caused it by adding a classified suite and leaving the count pin stale. The pin exists specifically to force a conscious inventory update.

## Error root cause

```text
classification: MANIFEST_DEFECT
cause:          OF-01 added src/market_platform_foundation/of01, which coverage_rules discover as a child directory of src/market_platform_foundation. The post-BUILD35 closure inventory did not classify that path, so load_closure_audit raised ClosureAuditError during the canonical completeness test (ERROR, not assertion FAILURE).
evidence:       Only unclassified discovered path at 36cf53b is src/market_platform_foundation/of01. Same test PASSes at 1e967613, where that directory does not exist. Fails in isolation and is deterministic.
OF-01 causal:   YES
```

Signature: `tools.repository_closure.ClosureAuditError: unclassified path: src/market_platform_foundation/of01`.

Primary defective layer is the closure inventory artifact, not OF-01 runtime code. The test is enforcing required completeness.

## Repair

### Failure

```text
files: tests/validation/test_validation_manifest.py
behavior before: assertEqual(len(offline), 49)
behavior after:  assertEqual(len(offline), 50)
why minimal:     the pin is the intended control; OF-01 legitimately added one offline suite.
```

### Error

```text
files: artifacts/repository-closure/POST_BUILD35_SUBSYSTEM_CLASSIFICATION.json
behavior before: of01 child directory discovered and unclassified
behavior after:  new CANONICAL entry of01-run-and-artifact-ledger owns src/market_platform_foundation/of01
why minimal:     OF-01 is unique run/artifact-ledger authority; it does not belong under temporal-data-plane or execution-risk. Inventory completeness is restored without changing OF-01 code or historical POST-BUILD35 narrative markdown.
```

Existing tests already captured both defects. No additional regression tests were added.

`classification_time_changes` remains `NONE` because this is a later inventory completion, not a rewrite of the original closure campaign's classification-time product edits.

## Manifest/validator analysis

```text
FULL_INVALIDATOR correct:        YES (validation_manifest.json)
UNKNOWN_EXECUTABLE_PATH correct: YES (manifest JSON is executable-root and unmatched by suite source_globs)

manifest changes required:   NO
validator changes required:  NO
```

The OF-01 manifest update already registered the of01 suite. This campaign only completed the leftover count pin and closure inventory.

## OF-01 preservation

```text
OF-01 semantics changed: NO
Invariants 1–75 changed: NO
OF-01 suite:             83 tests, 0 failures, 3 skipped
```

## Protected surfaces

```text
EVIDENCE changed:                 NO (full-run ui1 audit fixtures restored to HEAD)
prediction/settlement changed:    NO
risk/execution changed:           NO
ADAPT changed:                    NO
provider semantics changed:       NO
```

## Validation history

| Attempt | Scope | Result | Meaning |
|---|---|---|---|
| 1 | OF-01 count test | FAIL `50 != 49` | failure reproduced |
| 2 | Base count test | PASS | not pre-existing |
| 3 | OF-01 validation module | 52 tests, 1 fail, 1 error | both targets in `validation` worker |
| 4 | OF-01 error test | ERROR unclassified `of01` | error reproduced |
| 5 | Base error test | PASS | not pre-existing |
| 6 | Base validation module | 52 tests OK | base validation worker green |
| 7–9 | Repaired targets x2 | PASS | deterministic fix |
| 10 | Validation module | 52 tests OK | neighboring regression |
| 11 | OF-01 suite | 83 OK, 3 skipped | OF-01 surface preserved |
| 12 | `validate.py changed --explain` | 73 tests, 0 fail, 0 error | candidate selection; `full_suite_required=false` |
| 13 | `validate.py full` | 3039 tests, 42 skipped, 0 fail, 0 error | repository-wide proof |

## Final full-suite result

```text
Command:  .venv\Scripts\python.exe tools\validate.py full --json %TEMP%\imp-validation-01-full.json
Tests:    3039
Pass:     2997
Skip:     42
Failure:  0
Error:    0
Duration: 698.249s
```

After this run, `evidence/ui1/assistant-audit/conversations.json` and `messages.json` were modified. Those files are written by `src/market_platform_foundation/assistant/audit_store.py` during `ui1`/`assistant` tests. They were compared to HEAD and restored exactly. They are not part of the repair.

## Candidate comparison

| Target | Base `1e967613` | OF-01 pre-repair `36cf53b` | Final candidate |
|---|---|---|---|
| Original failure | PASS | FAIL `50 != 49` | PASS |
| Original error | PASS | ERROR unclassified `of01` | PASS |

## Files changed

```text
tests/validation/test_validation_manifest.py
artifacts/repository-closure/POST_BUILD35_SUBSYSTEM_CLASSIFICATION.json
artifacts/imp-rebase/VALIDATION01/VALIDATION01_ACCEPTANCE_REPORT.md
```

## Effect on OF-01 disposition

```text
OF-01 disposition remains:
IMP_OF_01_COMPLETE_WITH_LIMITATIONS
```

That historical classification remains accurate for the OF-01 runtime campaign: the ledger implementation was complete with stated limitations, and the broad-suite red result was not understood then. The underlying inventory gaps are resolved here without rewriting OF-01 history or reopening Invariants 1–75.

## Next gate

```text
IMP-OF-02 — Existing-System Run & Artifact Attribution Adapters
```

## Final status

```text
IMP_VALIDATION_01_COMPLETE
```
