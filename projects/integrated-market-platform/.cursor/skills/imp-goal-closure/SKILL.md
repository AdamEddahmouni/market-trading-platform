---
name: imp-goal-closure
description: Close an IMP development goal with requirement-by-requirement evidence, baseline separation, full validation, risk status, and a machine-readable closure report. Use when finishing a goal or release checkpoint.
---

# IMP goal closure

1. Re-read the objective and enumerate every explicit deliverable.
2. Inspect the final diff and run `python tools/imp.py env`.
3. Run `python tools/imp.py closure` once; include UI gates when UI paths
   changed and retain the generated JSON report.
4. Verify each requirement against authoritative files, command output, and
   runtime evidence. A passing focused/changed result cannot prove FULL closure.
5. Distinguish pre-existing dirty-tree failures from newly introduced failures.
6. Update authoritative architecture, observability, work log, and any
   completion record required by the repository.
7. Report unresolved risk plainly; never claim completion without fresh evidence.
