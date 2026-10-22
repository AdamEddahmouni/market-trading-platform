# IMP portable workstation (external SSD)

| Field | Value |
|---|---|
| Document ID | `IMP-PORTABLE-WORKSTATION-RUNBOOK` |
| Classification | `RUNBOOK` |
| Primary Truth Class | `CURRENT_CANONICAL_TRUTH` |
| Canonical Subject | Source, runtime, backup, and development boundaries of the owner's portable SSD installation |
| Establishing Milestone | Portable migration and recovery, PRs [#490](https://github.com/AdamEddahmouni/market-trading-platform/pull/490)–[#493](https://github.com/AdamEddahmouni/market-trading-platform/pull/493) |
| Version | `1.0` |
| Last Verified | `2026-10-11` |
| Supersedes | None |
| Superseded By | None |

Environment-scoped procedure for one workstation layout. It grants no runtime,
Paper, or execution authority; executable gates and
[MODE_AUTHORITY.md](../architecture/MODE_AUTHORITY.md) control behavior.

## Identity

Resolve the installation by folder identity, never by drive letter. The drive
letter is assigned by Windows and can change between mounts and hosts.

| Role | Location (relative to the SSD volume root) | What it is |
|---|---|---|
| Portable root | `IMP-PORTABLE-<timestamp>-<id>/` (exactly one folder containing `RUN_DEV.py`) | Launchers, runtime copy, state, caches, development worktrees |
| Migration backup | sibling `IMP-MIGRATION-BACKUP-<timestamp>-<id>/` | Preserved original payload, Python dependencies, models. Read-only source of reuse; never duplicated or edited |

Both folder names are fixed. Keep them side by side.

## Which tree is which

| Tree | Path under the portable root | Git | Purpose | May agents edit it? |
|---|---|---|---|---|
| Accepted source | GitHub `AdamEddahmouni/market-trading-platform`, branch `main` | canonical | The only source authority | Through protected PRs only |
| Running application | `projects/integrated-market-platform/` | **not a Git checkout** | The copy the launchers start. Carries runtime-specific configuration | No. Update it only by synchronizing files from an accepted `main` commit |
| Development repository | `development/monorepo/` | Git, with linked worktrees | Shared object store for all worktrees on the SSD | Per worktree rules below |
| Default developer worktree | `dev/` | linked worktree | Target of `DEV_PORTABLE.cmd` / `RUN_DEV.py` | Yes, on its own branch |
| Task worktrees | short folders directly under the portable root, for example `w-perf/` | linked worktrees | Isolated task branches | Yes, one owner per worktree |

The running application is a deployed copy. A merged PR does not change it.
Runtime synchronization is a separate, recorded step (see below).

## State, credentials, and models

| Area | Path under the portable root | Rule |
|---|---|---|
| Historical state | `state-history/` | Preserved evidence. Never opened for writing, never used by tests |
| Normal operating state | `state-normal/` | Owner's live-data and Paper state. Mutated only by the running application |
| Observational / replay state | `state-observational/` and the replay profile's state | Separate profiles; never selected automatically |
| Credentials | `private/` | Never read into logs, never copied, never overwritten |
| Models and Python dependencies | sibling backup payload, discovered by `RUN_DEV.py` | Reused in place; do not rebuild or copy |
| Disposable caches | `cache/` | Test and developer scratch. `cache/t/` holds short temporary directories |
| Acceptance evidence | `destination-tests/<run>/` | Receipts, logs, and reports per recovery or sprint. Append, do not rewrite |

## Development on the SSD

Run the canonical router through the portable launcher so the interpreter,
dependencies, and safe gates come from the SSD:

```powershell
.\DEV_PORTABLE.cmd env
.\DEV_PORTABLE.cmd validate fast
```

`RUN_DEV.py` strips provider and execution variables from the environment,
forces every live, Paper, and broker gate off, and points state, cache, and
secrets at disposable directories under `cache/development/`. Pass
`--app <worktree>\projects\integrated-market-platform` to target a task
worktree.

### Worktree paths must be short

Windows long-path support is disabled on this host and is left that way. A
worktree nested under `development/monorepo/.worktrees/<name>/` makes fixture
and temporary paths exceed the 260-character limit: an otherwise passing FULL
run reported 16 errors in packaging, frozen-corpus, and restart tests from that
depth, and the same tests passed from a short path on unchanged source.

- Create task worktrees directly under the portable root with a short name:
  `git -C development/monorepo worktree add ../../w-<task> -b <branch> origin/main`.
- Keep `TEMP`/`TMP` short as well (`cache/t/<short-id>`).
- `RUN_DEV.py` manages the UI dependency link and the replay fixture copy only
  for the default `dev/` worktree. A task worktree needs its own independent
  copy of the fixture files listed in `DEVELOPMENT-CONFIG.json`
  (`replay_fixture_files`) under `projects/short-squeeze-project/`, and its own
  ordinary `ui/node_modules` directory installed from its lockfile, before FULL validation.
  Never create a worktree junction to protected runtime dependencies.
- Do not move the running application or enable long paths globally to work
  around a deep development path.

### Junctions and Git

Use independently owned development dependencies. Historical worktrees may
contain a junction to runtime data; inspect reparse points before Git operations.
Never let checkout, cleanup, sparse-cone changes, or worktree removal traverse
such a link. This sprint recovered without creating a runtime junction.

The worktrees use sparse checkout. The replay fixture copy lives at tracked
paths outside the sparse cone, so `git stash`, `git checkout -- <path>` across
the cone, or `git sparse-checkout reapply` can silently remove it. Suites then
fail with `UI_STORE_SOURCE_MISSING`. Restore the copy from the fixture source
named in `DEVELOPMENT-CONFIG.json`; prefer a temporary commit over a stash.

### Validation hygiene

- Tests never touch `state-history/`, `state-normal/`, or `private/`. Record
  hashes of protected state before and after a validation campaign.
- Tests that reproduce a tracked evidence artifact write to the temporary
  directory. Set `IMP_REFRESH_TRACKED_EVIDENCE=1` only when deliberately
  re-recording that evidence for a commit.
- Run one heavy validation at a time; timings taken while another suite runs
  are not baselines.

## Updating the running application

1. The change is merged to `main` through the protected PR workflow and the
   merged commit is verified.
2. Stop IMP with `STOP_PORTABLE.cmd`.
3. Copy only the files changed between the previously synchronized commit and
   the new one from a clean worktree at the merged commit into
   `projects/integrated-market-platform/`. Do not copy `.git`, `ui/node_modules`,
   `.local/`, state, credentials, or configuration written by the launchers.
4. Record the source commit and the per-file hashes in the run's
   `destination-tests/<run>/` folder.
5. Start with `START_PORTABLE.cmd`, check `STATUS_PORTABLE.cmd`, and confirm the
   startup profile is live data with Paper internal simulation only.

## Limits

Physical remount on a different PC is unproven. GPU drivers, Windows
permissions, provider authentication, and entitlements remain host
prerequisites. OpenD currently runs from its existing host installation.

## Related authorities

- [DEVELOPER_RUNBOOK.md](DEVELOPER_RUNBOOK.md) — commands and validation pyramid
- [sops/GIT_WORKTREE.md](sops/GIT_WORKTREE.md) — worktree rules
- [PROGRAM_STATUS.md](../platform/PROGRAM_STATUS.md) — current program state
- [performance-engineering-p8](../audits/performance-engineering-p8/README.md) — baseline comparability and import-boundary evidence
