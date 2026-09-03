# IMP Validation-Baseline Reconciliation

## Scope

Reconcile the repository's changed and full validation baselines for the
equity Paper profitability loop (IMP), classify every reachable failure, audit
the recent IMP import/persistence/accounting/attribution/runtime safety
boundaries, and make only evidence-backed direct IMP repairs. Preserve all
unrelated provider/news/IBKR/Finviz work and do not alter roadmap, BUILD, or TD
authority.

## Phases

- [x] 1. Capture repository instructions, exact Git state, and
  categorized dirty-work inventory without modification.
- [x] 2. Run authoritative changed/full validation and independently
  reproduce exact counts and failure selectors.
- [x] 3. Reconcile changed-vs-full-only discrepancies and prove baseline
  ownership with history or controlled isolation.
- [x] 4. Audit IMP imports, persistence/schema boundaries, accounting,
  attribution, runtime, and Paper safety; run all required dependent suites.
- [x] 5. Repair only confirmed direct IMP regressions with regression
  coverage; validate incrementally after each repair.
- [x] 6. Run final validation, UI/build/type/whitespace/docs checks,
  review the targeted diff, and produce the required A–P report.

## Guardrails

- No commit, push, deploy, reset, checkout, stash, or unrelated cleanup.
- No edits during the initial Git-state capture.
- No provider expansion, UI redesign, architecture rewrite, or weakened tests.
- Do not claim green while collection/import/setup/teardown errors remain.
- Root `task_plan.md`, `findings.md`, and `progress.md` are pre-existing
  user-owned dirty files and must not be overwritten.

## Errors encountered

| Error | Attempt | Resolution |
|---|---:|---|
| User-supplied workspace path is not itself a Git root | 1 | Canonical root is the nested `integrated-market-platform` directory |
| Initial Glob with explicit workspace path returned path-not-found | 1 | Used workspace-root-relative discovery, then verified the nested repository |
