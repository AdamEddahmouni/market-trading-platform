# Market Trading Platform Workspace

This private repository is the workspace index for the related trading,
research, and coursework projects stored under this directory.

## Repository boundaries

- This repository contains the full integrated trading platform with its
  complete commit history merged under `projects/integrated-market-platform`
  (consolidated from the former `integrated-market-intelligence-platform`
  repository on 2026-09-04), plus monorepo snapshots of the governed ticker
  metadata, equity data, and short-squeeze projects under `projects/`.
- The remaining child repositories are unchanged at the workspace root with
  their histories, remotes, and visibility settings intact. The snapshots
  under `projects/` are the workspace copy.
- `.worktrees/` contains disposable development worktrees and is intentionally
  excluded from this monorepo.

The integrated trading platform lives entirely in this repository now; the
former child repository is archived and its `main` history is preserved as
part of this repository's history.

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

The historical paper trail begins at
[`docs/history/INDEX.md`](docs/history/INDEX.md). It records every commit
reachable from every captured child-repository ref, with readable timelines and
the complete JSONL ledger.
