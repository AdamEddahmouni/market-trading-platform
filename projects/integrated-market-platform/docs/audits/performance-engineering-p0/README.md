# Performance Engineering P0 — Forensic Baseline & Developer OS Audit

**Date:** 2026-09-09  
**Program:** Performance Engineering & Test Efficiency Program  
**Phase:** P0 (audit only; no broad optimization)

## Purpose

Measure-first forensic audit of IMP development time, validation cost, developer
operating-system overhead, and safe optimization opportunities. Primary product
work (Paper forward-testing bridge) remains authoritative over this lane.

## Artifacts

| Artifact | Description |
|----------|-------------|
| [P0_FORENSIC_AUDIT_2026-09-09.md](P0_FORENSIC_AUDIT_2026-09-09.md) | Human-readable audit report and closure evidence |
| [PERFORMANCE_BASELINE.json](PERFORMANCE_BASELINE.json) | Machine-readable timing baseline |
| [OPTIMIZATION_LEDGER.json](OPTIMIZATION_LEDGER.json) | Ranked future optimization candidates |
| [INVARIANT_COVERAGE_MAP.json](INVARIANT_COVERAGE_MAP.json) | Critical invariant → test group mapping |
| [PARALLEL_SAFETY_MAP.json](PARALLEL_SAFETY_MAP.json) | Suite concurrency classification |
| [NOTION_DEVELOPMENT_LIFECYCLE.md](NOTION_DEVELOPMENT_LIFECYCLE.md) | Notion startup/closure/sync specification |

## Measurement commands

Run from `projects/integrated-market-platform/` with Python 3.11 venv:

```powershell
$env:PYTHONPATH='src'
.\.venv\Scripts\python.exe tools/imp.py env
.\.venv\Scripts\python.exe tools/imp.py validate fast
.\.venv\Scripts\python.exe tools/benchmark.py --output artifacts/p0-performance-baseline.json --include-fast
```

## Recommended isolation for P1+

Do not mix performance refactors with professor-directed uncommitted work. Use a
dedicated worktree from accepted `main` (`bf0715f…`) for P1 test rationalization
and later phases; keep professor lane dirty tree read-only for profiling only.

## Related backlog

- **BL-0801** validation manifest partitioning → P3 affected/changed optimization
- Prior G15 baseline: `artifacts/g15-validation-performance.json`
