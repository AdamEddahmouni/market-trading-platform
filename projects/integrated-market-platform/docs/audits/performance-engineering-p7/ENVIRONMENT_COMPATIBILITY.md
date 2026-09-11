# P7 Environment Compatibility Policy

Two validation performance measurements may be compared only when all required
dimensions match within declared tolerance.

## Required dimensions

| Dimension | Policy |
|-----------|--------|
| OS family | Must match when `require_matching_os_family` is true |
| Python minor version | Must match baseline provenance (e.g. 3.11) |
| Worker count | Must match workload `reference_workers` |
| Validation mode | Must map to same canonical workload |
| Scheduler version | Must match `p2-bl-0901-1` for P7 baselines |
| Local vs CI | Not comparable (`allow_local_vs_ci_comparison: false`) |
| Logical CPU count | Within `cpu_count_tolerance_ratio` (0.5) |

## Workload identity (changed validation)

Changed-validation comparisons require matching `tests_run` within
`changed_workload_test_count_tolerance` (2%). Different selections must not
produce precision claims — classification returns `INSUFFICIENT_DATA`.

## Measurement claims

- **MEASURED**: direct repeated-run evidence in P7 worktree
- **DERIVED**: computed from P2/P6 inherited baselines with documented formula
- **PROJECTED**: estimated from partial data (not used for gating)
- **UNMEASURED**: remote CI (explicit `REMOTE_UNMEASURED`)
