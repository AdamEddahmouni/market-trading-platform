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

## Historical paper trail

The complete committed-history audit is under
[`docs/history/INDEX.md`](history/INDEX.md). It is intentionally layered:

- `INDEX.md` gives the coverage summary and navigation.
- `repositories/*.md` gives an understandable chronological timeline for each
  repository.
- `WORK_LEDGER.jsonl` preserves every captured commit body, parent, identity,
  ref, timestamp, and changed path.
- `REFS.json` records every local ref and its exact tip at generation time.

Regenerate it locally after fetching any new child refs:

```powershell
python tools/generate_history_ledger.py generate
python tools/generate_history_ledger.py validate
```

The three integrated-platform workspace entries share one underlying Git
history because two are worktrees. They remain separate in the audit so each
workspace path and ref set is traceable. The ledger records committed work
only; uncommitted files remain in the source repositories and are not given
invented dates or rationale.
