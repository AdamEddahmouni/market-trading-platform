---
name: imp-reconciliation
description: Compare isolated IMP branches/worktrees against current origin/main, build a disposition matrix, and protect evidence-sensitive state. Use for RTH15-00, branch catch-up, cherry-pick vs reimplement decisions, or competing implementations.
---

# IMP branch reconciliation

Do not merge first and inspect later. Read the runbook and recon the trees.

## Required reads

1. Skill `imp-repo-recon` (starting state)
2. [BRANCH_RECONCILIATION.md](../../../docs/engineering/sops/BRANCH_RECONCILIATION.md)
3. Current `origin/main` program status

## Procedure

1. Fetch `origin/main`. Record canonical SHA.
2. For each isolated branch/worktree, record: purpose, owner, base SHA, unique commits, overlapping paths, evidence-sensitive files, tests.
3. Classify each delta:

| Disposition | When |
|---|---|
| **MERGE** | Clean, current, no evidence rewrite, tests exist |
| **CHERRY-PICK** | Small unique commits that apply cleanly onto main |
| **REIMPLEMENT** | Idea is right; code is stale or conflicts architecturally |
| **DEFER** | Valuable but blocked or out of sequence |
| **DROP** | Duplicate, superseded, or unsafe |

4. Protect prospective/RTH/FTEP artifacts: never relabel, overwrite, or substitute runs.
5. Integrate only through the primary owner onto an `reconcile/...` worktree. Never mutate several worktrees into main in parallel.
6. Validate the integrated result (`imp-validation`). Handoff with `imp-handoff`.

## Hard stops

- Do not restart prospective runs to “make the branch look current.”
- Do not treat historical completion records as current architecture.
- Do not skip evidence gates because a branch is locally green on an old SHA.
