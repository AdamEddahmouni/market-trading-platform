# Market Trading Platform Workspace

This private repository is the workspace index for the related trading,
research, and coursework projects stored under this directory.

## Repository boundaries

- `integrated-market-platform/` is maintained as the private
  `integrated-market-intelligence-platform` repository.
- `governed-ticker-metadata-enrichment/`, `equity-data-v1-worktree/`, and
  `short-squeeze-project/` retain their own repository histories and remotes.
- `.worktrees/` contains disposable development worktrees and is intentionally
  excluded from this workspace repository.

The integrated platform repository is the canonical source for the main
trading platform. Its remote `main` was realigned to the integrated local
history on 2026-09-03 after a remote-history mismatch; the previous remote
history is preserved on
`backup/remote-main-before-repair-2026-09-03`.

The workspace repository tracks the surrounding notes, documentation, project
artifacts, and source trees that do not already belong to a nested repository.
Local environments, generated output, and credentials are excluded.

Several futures data files are present only as Git-LFS pointer stubs in this
checkout; their underlying objects are not available locally. Those paths are
excluded from the workspace snapshot rather than being published as unusable
data. The associated source code and metadata remain tracked.
