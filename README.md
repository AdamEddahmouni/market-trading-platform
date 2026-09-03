# Market Trading Platform Workspace

This private repository is the workspace index for the related trading,
research, and coursework projects stored under this directory.

## Repository boundaries

- This repository contains a monorepo snapshot of every project directory in
  this workspace under `projects/`, including the integrated platform,
  governed ticker metadata, equity data, and short-squeeze projects.
- The original child repositories remain at the workspace root with their
  histories, remotes, and visibility settings unchanged. The snapshots under
  `projects/` are the private workspace copy.
- `.worktrees/` contains disposable development worktrees and is intentionally
  excluded from this monorepo.

The integrated platform repository is the canonical source for the main
trading platform. Its remote `main` was realigned to the integrated local
history on 2026-09-03 after a remote-history mismatch; the previous remote
history is preserved on
`backup/remote-main-before-repair-2026-09-03`.

The workspace repository tracks the surrounding notes, documentation, project
artifacts, and source trees. Local environments, generated output, and
credentials are excluded.

Several futures data files are present only as Git-LFS pointer stubs in this
checkout; their underlying objects are not available locally. Those paths are
excluded from the workspace snapshot rather than being published as unusable
data. The associated source code and metadata remain tracked.

## Safe synchronization

The source-to-snapshot mapping and exact imported commits are recorded in
`workspace-manifest.json`. Use the guarded workflow in
[`docs/MONOREPO_WORKFLOW.md`](docs/MONOREPO_WORKFLOW.md) and run:

```powershell
python tools/monorepo_guard.py validate --remote
```

Imports must be performed from a non-`main` parent branch. The guard refuses
dirty parent trees, verifies child refs and visibility, rejects Gitlink
snapshots, and confirms that child repositories are unchanged. Parent `main`
is protected and requires the `Monorepo Guardrails / validate` check.
