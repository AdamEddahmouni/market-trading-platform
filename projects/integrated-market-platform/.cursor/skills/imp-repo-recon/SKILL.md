---
name: imp-repo-recon
description: Establish IMP Git/repository starting state, locate worktrees, find divergence from origin/main, and produce a concise recon report. Use at session start, before implementation, before reconciliation, or when asked for repo/worktree status.
---

# IMP repository reconnaissance

Run this before mutating the tree. Do not assume a clean checkout.

## Commands

From the monorepo root (the Git common checkout or current linked worktree):

```powershell
git rev-parse --show-toplevel
git rev-parse --abbrev-ref HEAD
git rev-parse HEAD
git status --short --branch
git rev-parse --abbrev-ref @{upstream} 2>$null
git rev-list --left-right --count origin/main...HEAD
git worktree list --porcelain
python projects/integrated-market-platform/tools/imp.py env
```

If already inside `projects/integrated-market-platform`, `python tools/imp.py env` is enough for interpreter/worktree/gate diagnostics.

## Report (keep short)

```markdown
# Repo recon
- repo: <toplevel>
- branch: <name>
- HEAD: <sha>
- upstream: <branch> ahead/behind <n/m> vs origin/main <sha>
- worktree dirty: yes/no (unrelated paths listed, not omitted)
- linked worktrees: <path> <sha> <branch> — purpose if known
- edit target: projects/integrated-market-platform/ (never leftover nested clone)
- evidence-sensitive: running/pending FTEP, RTH, heartbeat, scheduler — or NONE OBSERVED
- next safe action: <one line>
```

## Rules

- Do not reset, clean, stash, or copy unrelated dirty files.
- If the checkout has unrelated work, recommend a dedicated worktree from `origin/main` (`docs/engineering/sops/GIT_WORKTREE.md`).
- Do not start RTH/FTEP reconciliation inside recon.
- Classify missing data as `UNKNOWN` / `UNAVAILABLE`, never as clean.
