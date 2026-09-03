# Parent Monorepo Workflow

The private repository
[`AdamEddahmouni/market-trading-platform`](https://github.com/AdamEddahmouni/market-trading-platform)
is a workspace monorepo. It contains snapshots under `projects/`; it does not
replace the source repositories that remain beside it.

## Immutable source boundary

The root-level child repositories are independently owned and versioned. The
parent workflow must not:

- change a child repository's visibility;
- commit, reset, rebase, or force-push a child repository;
- change a child repository's remotes or branches; or
- add a child repository as a Git submodule/gitlink.

The public short-squeeze source repository stays public. Its private parent
snapshot is an additional copy, not a privacy change.

## Importing a snapshot

Create a branch in the parent repository, keep the parent working tree clean,
and run:

```powershell
git switch -c chore/import-<project>-<ref>
python tools/monorepo_guard.py import <project-id> --source-ref <ref>
python tools/monorepo_guard.py validate --remote
git push -u origin HEAD
```

The importer uses `git subtree` to update only
`projects/<project>/`. It records the exact source commit in
`workspace-manifest.json`, checks that the child repository is unchanged, and
refuses to run on `main`. Open a pull request and merge it after the
`Monorepo Guardrails` check passes.

Project IDs and the source branches currently tracked are in
`workspace-manifest.json`. The source commit must be updated by the importer,
not edited manually.

## Validation

Run the local check before opening a pull request:

```powershell
python tools/monorepo_guard.py validate
python -m unittest tests.test_monorepo_guard -v
```

The guard verifies that:

- the parent remote and private-parent contract are correct;
- every manifest project has a non-empty ordinary-file snapshot;
- no snapshot contains a `160000` Gitlink;
- the original child paths are ignored by the parent;
- local child refs, remotes, and source commits match the manifest; and
- optional `--remote` checks preserve each child's declared visibility.

CI repeats the snapshot checks without requiring the root-level child
repositories to be present in a hosted checkout.
