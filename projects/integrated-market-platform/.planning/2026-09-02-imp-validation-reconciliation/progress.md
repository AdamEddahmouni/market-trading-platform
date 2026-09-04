# Progress — IMP Validation-Baseline Reconciliation

## 2026-09-02

- Read repository instructions, scoped Paper instructions, authority docs,
  validation docs, testing guidance, and existing planning files.
- Captured canonical Git state before making any repository changes.
- Created this isolated scoped planning set; existing root planning files remain
  untouched.
- Next: run authoritative changed/full validation and retain complete result
  evidence.

## Validation and import investigation

- Independently ran the required IMP suite set in forward order: `144/144`
  passed, `0` skipped, `0` failed, `0` errors.
- Re-ran the same set in reverse order: `144/144` passed, `0` skipped,
  `0` failed, `0` errors.
- Reproduced the venv `tests` package collision and the eager
  `system_acceptance` import failure without changing source.
- Identified a likely Mongo registration gap: allocation decision validators
  and indexes are declared but not included in the codec-backed collection
  bootstrap.

## Root-cause repairs

- Added repository `tests` and `tests.intelligence` package markers plus a
  regression test so the venv's unrelated site-packages `tests` package cannot
  shadow IMP fixture imports.
- Confirmed isolated platform, Finviz, UI1, and UI2 suites collect and pass
  after the package-boundary repair. Intelligence now collects fully; two
  unchanged historical subsystem tests remain failing.
- Registered the allocation-decision sidecar validator and indexes in
  `MongoSchemaManager`; the isolated Mongo schema suite passes `9/9`.
- Next: rerun required IMP suites with the schema repair, then the sequential
  authoritative changed gate and final full checkpoint.

## Final checkpoint

- Required IMP suites passed in forward and reverse order (`253/253` each).
- Final full validation: `3151` tests, `34` skipped, `3` failures, `1`
  error, `3113` passes.
- Final changed validation: `2170` tests, `34` skipped, `3` failures, `1`
  error.
- UI tests (`421`), UI build, UI typecheck, docs links, whitespace, and
  targeted compile checks passed.
- Worktree remains uncommitted and preserves the pre-existing provider/news/
  IBKR/Finviz changes.
