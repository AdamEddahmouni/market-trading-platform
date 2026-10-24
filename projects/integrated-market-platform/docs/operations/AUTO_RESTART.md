# Automatic restart after a reboot or a frozen feed

Owner decision 3 (2026-10-23, [OWNER_DECISIONS_20261023.md](../platform/OWNER_DECISIONS_20261023.md)):
the platform, the collector and Moomoo OpenD restart unattended, the Paper controller resumes, and every
restart is logged for review. Fake money only.

Status: built in rebuild step 4 (2026-10-24) on its branch. **Not deployed.** Nothing described here runs
until the step-10 release. The release steps and the live checks are in
`destination-tests/20261024-auto-restart/RELEASE-NOTES.md` under the portable root.

## The keeper

`tools/platform/imp_keeper.py` is one long-running program, run by the scheduled task `IMP-Keeper`. The task
starts it at sign-in and checks every 5 minutes that it is still running. Every 30 seconds it looks at three
things, in this order, and brings back whatever is down:

| Order | What | Counts as down | What the keeper does |
|---|---|---|---|
| 1 | Moomoo OpenD (the local quote gateway) | No OpenD process; or 3 checks in a row, 60 s apart, where the API port does not answer or the quote login is not valid | Closes OpenD politely, then by force after 20 s, starts it again, and waits up to 240 s for its remembered login |
| 2 | The collector (`collector/RUN_COLLECTOR.py run`) | No such process | Starts it, then checks 15 s later that it is still running |
| 3 | The platform (`RUN_IMP.py start`) | The API does not answer for 3 checks (90 s); or its feed watchdog reports the Moomoo feed `UNRECOVERABLE` while OpenD is healthy | Starts it (stopping it first for a frozen feed), with a 300 s readiness wait |

- **Order matters.** A frozen feed is not "fixed" by restarting the platform while OpenD itself is down. The
  keeper records `WAITING_FOR_OPEND` and brings OpenD back first.
- **The OpenD health check runs in a child process with a 45 s timeout.** A vendor SDK call can block for ever
  (2026-10-19..22), and that must not stop the keeper.
- **It replaces the old OpenD watchdog** (`collector/OPEND_WATCHDOG.py`, outside git) and keeps its rules: a
  check every 60 s, a restart after 3 failures, 4 restarts per 6 h.

## Limits: never a tight loop, never a permanent stop

| Component | Restarts allowed | Gap between tries | When the allowance is spent |
|---|---|---|---|
| OpenD | 4 per 6 h | 1, 2, 4, 8 min | `BUDGET_SPENT`, then wait until the 6-hour window has rolled, at least 1 h; then a fresh allowance |
| Collector | 6 per hour | 1, 2, 4, 8 min | `BUDGET_SPENT`, then wait 1 h; then a fresh allowance |
| Platform | 4 per hour | 1, 2, 4, 8 min | `BUDGET_SPENT`, then wait 1 h; then a fresh allowance |

The collector also has its own supervisor (PF-01) with its own budget. Since step 4, its
`PERSISTENT_CHILD_FAILURE` block clears itself after 2 hours. A `CHILD_CONFIGURATION_REJECTED` block never
does: restarting cannot fix a wrong configuration. The keeper does not start the collector while either block
holds; it records `WAITING` once
([PF01_COLLECTION_SUPERVISION.md](PF01_COLLECTION_SUPERVISION.md)).

## The Paper controller

The keeper **never** arms, starts, pauses or stops the Paper controller. It has no route to do so: it only reads
`GET /paper/automation/status`. After the platform starts, the controller resumes itself only if it was armed
and running before, and only if every safety check passes again. A refusal that time can clear (the old lease,
the reevaluation loop, a busy store) is retried for up to 15 minutes. See
[AUTONOMOUS_PAPER_OPERATIONS_RUNBOOK.md](AUTONOMOUS_PAPER_OPERATIONS_RUNBOOK.md) § 5.

Within 10 minutes of a platform restart, the keeper records the outcome:

- `RESUMED`: running again.
- `REFUSED` with a reason: for example, the risk policy changed since arming.
- `NOT_RUNNING_BEFORE_RESTART`: a stopped or paused controller stays stopped.
- `NOT_ARMED`.
- `EMERGENCY_STOPPED`.
- `NOT_RESUMED_IN_TIME`.

## The restart log

Every action and its outcome is one line in
`projects/integrated-market-platform/.local/keeper/restarts.jsonl`. Each line records:

- what (`PC`, `KEEPER`, `OPEND`, `COLLECTOR`, `PLATFORM`, `PAPER_CONTROLLER`);
- the event;
- the cause (`REBOOT`, `PROCESS_GONE`, `NOT_ANSWERING`, `FEED_UNRECOVERABLE`, `OPEND_NOT_RUNNING`,
  `QUOTE_NOT_LOGGED_IN`, …);
- the outcome;
- the attempt number;
- how long it was down.

A reboot is detected from the PC's boot time and logged as `PC REBOOT`, with how long the PC was off. The file
rotates at 5 MiB and keeps 4 older files, so it can never fill the disk. To read it:

```text
python tools/platform/imp_keeper.py report            # everything, as a table
python tools/platform/imp_keeper.py report --days 7   # the last week
```

## Controls

| Command | Effect |
|---|---|
| `imp_keeper.py pause` | The keeper keeps running but does nothing (a file, `.local/keeper/PAUSED`). Use it before any planned stop; the staged `STOP_PORTABLE.cmd` does this. |
| `imp_keeper.py resume` | Allows actions again; the staged `START_PORTABLE.cmd` does this. |
| `imp_keeper.py stop` | Ends the running keeper (a file, `.local/keeper/STOP`); the task starts a fresh one within 5 minutes. Deploys use it so the new keeper code runs. |
| `imp_keeper.py status` | Its state: per-component counters, last heartbeat, paused or not. |
| `imp_keeper.py once --dry-run` | One pass that says what it would start. It starts nothing, writes nothing and reads no store. |
| `collector\DISABLED` (existing) | The keeper leaves the collector stopped and records `LEFT_STOPPED` once. |

## What it cannot do

- **Sign in to Windows.** Every IMP task runs only while the owner is signed in, and OpenD needs the desktop.
  After a reboot, nothing starts until someone signs in, unless the owner turns on Windows automatic sign-in.
  That is the owner's own decision and action.
- **Sign in to Moomoo.** If OpenD's remembered login has lapsed, the restarts fail (`NOT_RECOVERED`, 4 per 6 h)
  until someone signs in to OpenD.
- **Wake a PC that is off or asleep, or fix the network.**
- **Prove itself before the release.** Every behaviour above is tested with simulated processes only. The live
  checks (reboot, closing OpenD, killing the backend, freezing the feed) are part of the step-10 release.
