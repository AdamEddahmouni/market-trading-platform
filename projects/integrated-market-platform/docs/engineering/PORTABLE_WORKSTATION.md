# IMP portable workstation (external SSD)

| Field | Value |
|---|---|
| Document ID | `IMP-PORTABLE-WORKSTATION-RUNBOOK` |
| Classification | `RUNBOOK` |
| Primary Truth Class | `CURRENT_CANONICAL_TRUTH` |
| Canonical Subject | Source, runtime, backup, and development boundaries of the owner's portable SSD installation |
| Establishing Milestone | Portable migration and recovery, PRs [#490](https://github.com/AdamEddahmouni/market-trading-platform/pull/490)–[#493](https://github.com/AdamEddahmouni/market-trading-platform/pull/493) |
| Version | `1.1` |
| Last Verified | `2026-10-23` (location, services and release practice; the rest unchanged from 2026-10-11) |
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

### Current location and services (2026-10-23)

Since 2026-10-21 both folders live on the owner's PC under `D:\IMP\` (copied
off the E: SSD; the SSD was returned). Everything IMP-related belongs under
`D:\IMP\`; Oct 9 PC-setup leftovers are filed in
`D:\IMP\_legacy-pc-setup-20261009\`. The live Moomoo OpenD is started from
`%APPDATA%\moomoo_OpenD`, a junction to `D:\IMP\IMP-tools\Moomoo-OpenD`. On
2026-10-23 an earlier session moved that folder into the legacy area without
seeing the junction. On 2026-10-24 the folder was moved back, but the junction
itself is **missing** until it is recreated from an ordinary Command Prompt
(staged as `FIX_OPEND_SHORTCUT.cmd` for the release). An agent started from
the Claude desktop app cannot do it: that app's packaging redirects writes
under `%APPDATA%` into its own private copy, which no other program sees.
Never move the folder without re-pointing the junction. Its remembered login
is kept in `%APPDATA%\com.moomoo.OpenD`.

- **The backup is a runtime dependency.** Launchers load the `.venv`
  site-packages and the FinBERT / Qwen weights from the backup's `payload/`.
  Never archive, move or delete it.
- **Store identity pin.** `collector/RUN_COLLECTOR.py` pins the
  `(st_dev, st_ino)` of `state-normal/imp-state.sqlite3`. A copy to another
  volume refuses to start (`CANONICAL_STORE_MISSING_OR_REPLACED`) until the
  pin is updated on purpose.
- **Scheduled tasks.** `IMP-Platform`, `IMP-PF01-Collector`,
  `IMP-OpenD-Watchdog`, `IMP-Local-Intelligence`, `IMP-AI-Journal`,
  `IMP-Evidence-Capture`. On 2026-10-23 the owner stopped everything and all
  six are **disabled** until the rebuild is approved
  ([Program Status](../platform/PROGRAM_STATUS.md#current-operating-state-2026-10-23)).
- **Stop / start.** `RUN_IMP.py stop` (or `STOP_PORTABLE.cmd`) and
  `RUN_COLLECTOR.py stop`; start through the scheduled tasks. The launcher's
  readiness wait is 60–300 s depending on how the API fails; a slow first
  start can be reported as a failure while the API is still coming up.
- **Automatic restart (rebuild step 4, not yet deployed).** From the step-10
  release one task, `IMP-Keeper`, runs `tools/platform/imp_keeper.py`. It
  brings back OpenD, the collector and the platform, and logs every restart.
  It replaces the triggers of `IMP-Platform`, `IMP-PF01-Collector` and
  `IMP-OpenD-Watchdog`. Pause it before any planned stop
  (`imp_keeper.py pause`; the staged `STOP_PORTABLE.cmd` does this), or it
  starts the platform again within about 90 s. See
  [AUTO_RESTART.md](../operations/AUTO_RESTART.md).
- `development/monorepo/` itself sits on an old branch
  (`codex/portable-workstation-readiness`, 2026-10-09); do not read its docs
  as current. Work happens in the task worktrees.

### Disk load while collecting

`D:` is a SATA hard drive, about 90% full. The live store, the worktrees, the
backup and the model weights all share it. From 2026-10-21 to 10-23 heavy disk
work saturated that drive while the collector ran, and every write to the
store stalled (`database is locked`). Triggers seen:
- a 32-thread `robocopy`;
- `grep -r` and `du` over the whole `D:\IMP` tree;
- worktree creation, `vitest` and `npm run build`;
- `validate changed`;
- 2.5 GB local-model loads;
- full-table scans of `market_stream_records`.

See [PF-01 collection supervision](../operations/PF01_COLLECTION_SUPERVISION.md#storage-contention).

The collector writes around the clock: Kraken is 24/7, and Moomoo collects
from 04:00 to 20:00 ET on trading days. The writer now waits out up to
10 minutes of contention, but a saturated drive still delays every write.

**From 04:00 to 20:00 ET on trading days, while the collector runs:**
- Search inside a named folder only. Never search or measure the whole
  `D:\IMP` tree.
- Do not run builds, `validate`, bulk copies, backups or large model loads.
  Run them outside those hours, or stop collection first with the owner's OK.

**Always:**
- Never scan `market_stream_records` in full (`count(*)`, `GROUP BY symbol`).
- Use `max(rowid)` (rows are never deleted) and `market_stream_checkpoints`
  instead.

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

**Practice since 2026-10-14 (recorded, not endorsed).** Paper releases R1–R13
were deployed from unmerged local branches, not from `main`, with
owner-approved per-release tooling (prepare → rehearse → deploy with rollback
→ hash-verify) kept in `destination-tests/<run>/release-*/`, preimages in
`release-backups/<date>-<name>/` and staging copies in `r-*/`. As a result the
running copy is ahead of `main`; the branch is pushed as a draft backup PR
rather than merged. Restoring step 1 (merge first, then deploy) is part of the
owner's rebuild plan.

## Limits

Physical remount on a different PC is unproven. GPU drivers, Windows
permissions, provider authentication, and entitlements remain host
prerequisites. OpenD currently runs from its existing host installation.

## Related authorities

- [DEVELOPER_RUNBOOK.md](DEVELOPER_RUNBOOK.md) — commands and validation pyramid
- [sops/GIT_WORKTREE.md](sops/GIT_WORKTREE.md) — worktree rules
- [PROGRAM_STATUS.md](../platform/PROGRAM_STATUS.md) — current program state
- [performance-engineering-p8](../audits/performance-engineering-p8/README.md) — baseline comparability and import-boundary evidence
