# SOP: Branch reconciliation onto current main

**Status:** Authoritative procedure for isolated/post-close work.

**Skill:** `imp-reconciliation`.

**Default base:** current `origin/main`.

RTH15-00 uses this SOP. Do not start it as a side effect of unrelated work.

## Goal

Land unique value from isolated branches onto current `main` without
contaminating evidence, discarding unique work, or merging stale architecture
as if it were current.

## Inputs

- Recon report (skill `imp-repo-recon`)
- List of candidate branches/worktrees (purpose, owner, SHA)
- Evidence constraints (FTEP/RTH/scheduler/prospective)

## Matrix

For each candidate, fill:

| Field | Value |
|---|---|
| Branch / worktree | |
| Tip SHA | |
| Merge-base with `origin/main` | |
| Unique commits | |
| Overlapping paths with other candidates | |
| Tests present | |
| Evidence-sensitive | yes/no + what |
| Disposition | MERGE / CHERRY-PICK / REIMPLEMENT / DEFER / DROP |
| Reason | |

## Disposition rules

- **MERGE** only when the branch is based on current enough main, applies without
  architectural rewrite, and does not relabel evidence.
- **CHERRY-PICK** unique small commits that remain correct on current main.
- **REIMPLEMENT** when the idea is right but the snapshot is stale or conflicts
  with current architecture.
- **DEFER** when blocked on authorization, evidence, or sequencing.
- **DROP** duplicates, superseded spikes, or unsafe experiments.

## Integration

1. Primary owner works in `reconcile/<purpose>` from current `origin/main`.
2. Workers do not merge to `main`.
3. Validate with skill `imp-validation` on the integrated tree.
4. Preserve failed or incomplete prospective observations under their original labels.
5. Handoff with skill `imp-handoff`.

## Forbidden

- Restarting a prospective run to replace results while keeping the original label
- Concurrent mutation of candidate worktrees “to help the merge”
- Treating a green test run on an old SHA as proof on current main
- Enabling live real-money execution
