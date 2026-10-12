# P8 — Baseline comparability, import boundaries, and validation hygiene

**Status:** COMPLETE (local evidence, one workstation)
**Branch:** `codex/performance-organization-20261011`
**Parent SHA:** `a1f9a3a1bfcfcd21e5407f48b2c1c2feb8c99bcd` (PR #493)
**Budget version:** unchanged (`manifests/performance_budget.json` not edited)
**Recorded:** 2026-10-11

## Objective

Make validation timing reports trustworthy and remove measured, behavior-neutral
overhead from imports and validation. No product behavior, Screener
methodology, trading gate, or budget baseline changed.

## Host and method

Ryzen 5 3600, 32 GB RAM, Windows 10, portable Python 3.11 on a USB SSD. FULL
used 2 workers and FAST 1 worker (router defaults). Every run used isolated
state, cache, and secret directories and a short temporary path; no network,
provider, or broker session. Before and after were measured on the same host
from two short-path worktrees: unchanged `a1f9a3a1` and this branch.

## Findings

| # | Finding | Evidence |
|---|---|---|
| 1 | The reporter compared runs against a baseline taken on a different workload: FULL 8,513 tests versus a 4,528-test reference, FAST 23 versus 21. It reported `SEVERE_REGRESSION` (+163%) for a run that had not regressed. | Unchanged-source FULL receipt |
| 2 | A worktree nested under `development/monorepo/.worktrees/` exceeded the Windows 260-character path limit. The same source produced 16 errors there and 0 from a short path. | Deep-path and short-path FULL receipts |
| 3 | Importing any intelligence contract initialized the whole package (providers, runtime, engine). | Import samples |
| 4 | Six model modules imported scikit-learn at module scope, pulling scipy, pandas, and joblib into every backend API start and most test workers. | `-X importtime` profile |
| 5 | After a failed Finviz credential recovery, concurrent callers kept polling for the full 60 s window. In validation this left two threads alive for 48 s after the suite finished; in the application it stalls concurrent Finviz requests. | Isolated suite probe |
| 6 | Five tests rewrote tracked evidence files with host-specific timings on every FULL run, dirtying every checkout. | `git status` after unchanged-source FULL |

## Changes

| Area | Change | Regression coverage |
|---|---|---|
| `tools/performance_budget.py`, `tools/validate.py` | Workload identity (test and skip counts) is checked whenever the baseline records it. A mismatch reports `INSUFFICIENT_DATA` with the reason, keeps both raw timings, and computes no ratio. | `tests/validation/test_performance_budget.py` |
| `tools/performance_telemetry.py` | Slowest suites rank by process wall time and show discovery, execution, and process overhead separately. | same |
| `intelligence/__init__.py`, `intelligence/opportunity/__init__.py` | PEP 562 lazy exports. Public names, objects, `dir()`, and patchability unchanged. | `tests/intelligence/test_intelligence_import_boundary.py` |
| `fusion/calibrators.py`, `baselines/controls/*`, `production/model.py`, `training/trainers/sklearn_*` | scikit-learn is imported inside the fit/train function that constructs the estimator. | same file; existing fit/train suites |
| `finviz/credential_manager.py` | A waiting caller returns the final outcome when the in-flight recovery releases its lock. | `tests/finviz/test_auth_lifecycle.py` |
| `tools/tracked_evidence.py` and five tests | Tests that reproduce tracked evidence write to the temporary directory unless `IMP_REFRESH_TRACKED_EVIDENCE=1`. | `tests/validation/test_tracked_evidence.py` |

The baseline in `manifests/performance_budget.json` is preserved as recorded.
Re-baselining FULL and FAST on the current workload is a separate, deliberate
decision and was not taken here.

## Measurements

Medians of fresh-process samples unless noted; same host, alternating trees.

| Measure | Before (`a1f9a3a1`) | After | Change |
|---|---:|---:|---:|
| FULL wall, 2 workers (single run each) | 523.6 s, 8,513 tests | 434.9 s, 8,528 tests | −16.9% |
| FULL summed discovery | 125.3 s | 39.6 s | −68% |
| FULL summed worker process time | 967.8 s | 784.8 s | −18.9% |
| `finviz` suite process time | 63.4 s | 3.0 s | −95% |
| FAST total, warm (5 samples) | 4.05 s | 3.45 s | −15% |
| Import `tools.ui1.run_ui_api` (7 samples) | 3.78 s | 1.47 s | −61% |
| Import `market_platform_foundation.strategy` (7) | 2.84 s | 0.76 s | −73% |
| Import `intelligence.fusion` (7) | 2.24 s | 0.36 s | −84% |
| Import `intelligence.contracts` (7) | 0.69 s | 0.33 s | −52% |
| Import opportunity `GlobalOpportunityComparator` (7) | 2.71 s | 0.35 s | −87% |
| FULL classification | `SEVERE_REGRESSION` (invalid comparison) | `INSUFFICIENT_DATA`, reason stated | corrected |
| Tracked files modified by FULL | 6 | 0 | — |

Both FULL runs passed with 59 skips, 0 failures, 0 errors. The after run has 15
more tests (new regressions). FULL figures are single runs and the baseline run
overlapped a few short focused test invocations, so treat the FULL delta as
approximate; the import and suite-level figures are controlled.

## Not changed, and why

| Area | Result |
|---|---|
| Scheduler defaults (workers) | Unchanged. The budget reference is 2 workers; changing it would invalidate history. |
| Live Screener, provider latency, FinBERT/Qwen inference, paid Claude inference | Not measured in this pass: measuring requires live provider sessions, model loads against the owner's running installation, or paid calls. No optimization claimed. |
| Frontend bundle and render | Not measured in this pass. No change. |
| Storage and startup of the running application | Only the import cost above was measured. The first model fit in a process now pays the scikit-learn import once (about 1.5–2 s warm on this host). |

## Evidence

Receipts, logs, and raw samples for this pass are stored with the portable
installation under `destination-tests/performance-organization-20261011/`
(not in the repository): `clean-full-base*`, `clean-full-after-3*`,
`fast-base-*`, `fast-after-*`, `api-import-controlled.json`,
`api-importtime*.log`, `finviz-probe.log`, `finviz-waiter-red/green.*`,
`sklearn-boundary-red/green.*`, `before/after-imports-controlled.*`,
`protected-state-*.json`, `worktree-inventory-final.json`.

## Related

- [P7 — budgets and telemetry](../performance-engineering-p7/README.md)
- [Portable workstation runbook](../../engineering/PORTABLE_WORKSTATION.md)
