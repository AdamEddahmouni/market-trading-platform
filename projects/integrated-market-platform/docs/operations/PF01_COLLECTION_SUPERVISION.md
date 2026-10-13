# PF-01 collection supervision

Status: implemented and verified offline only. Not deployed, not activated, and
no real overnight run has been observed. This page covers the headless
collection-only entry point and its bounded-restart supervisor. Raw news
collection is described in [PF01_RAW_COLLECTION.md](PF01_RAW_COLLECTION.md) and
market persistence in [PF01B_MARKET_PERSISTENCE.md](PF01B_MARKET_PERSISTENCE.md).

## What exists

- `tools/ui1/run_ui_api.py --collect-only` starts only the raw news collector and
  the market writer. It loads no store, private `.env` or saved provider
  settings, serves no HTTP, and never runs Paper recovery, Screener warmup or AI.
  It cannot be combined with `--serve`.
- `tools/platform/pf01_supervisor.py` prints a read-only plan by default. With
  `--run` it owns one `--collect-only` child process and restarts it within a
  bounded budget. `--status` prints the persisted evidence without taking
  ownership. `--reset-restart-budget` is the operator recovery described below.
  It registers no Windows task or service.
- `src/market_platform_foundation/news/supervision.py` holds the supervisor
  logic and its durable evidence row.

## Headless market supply is not provided

The market writer is a sink for observations that existing producers already
receive. Provider subscriptions are acquired only by the serving backend's
request-driven projections. The collection-only process creates no moomoo
runtime, no Kraken connection and no bar polling, so a headless writer receives
nothing.

A writer that receives nothing owns nothing. It takes the owner lock and the run
lease only when it has an observation or a gap to store, so an unsupplied
headless process reports `IDLE` with `ownership: NOT_HELD` and does not stand in
the way of a serving backend's writer. Enabling `IMP_MARKET_PERSISTENCE_ENABLED`
for the headless entry point is therefore harmless but still collects nothing.
A `RUNNING` supervisor or an `IDLE` writer is not evidence of market coverage;
`collecting: true` in `market_persistence` is the only state that says
observations are being stored.

## Activation requirements

All of the following must hold; each is checked before a child is spawned:

- `IMP_PF01_SUPERVISION_ENABLED=1` and the `--run` flag.
- `IMP_PERSIST_STATE=1` and an absolute `IMP_STATE_DIR` whose
  `imp-state.sqlite3` already exists.
- The store is already at the current schema. Both the supervisor and the
  collection-only entry point check this through a read-only connection and
  refuse with `APPROVED_SCHEMA_MIGRATION_REQUIRED`; neither migrates a store.
- At least one of `IMP_NEWS_COLLECTION_ENABLED=1` or
  `IMP_MARKET_PERSISTENCE_ENABLED=1`.
- Every execution gate off (`IMP_PAPER_EXECUTION`, `IMP_BROKER_PAPER_EXECUTION`,
  `IMP_MOOMOO_PAPER_EXECUTION`, `IMP_LIVE_EXECUTION`,
  `IMP_BROKER_LIVE_EXECUTION`, `IMP_LIVE_INTERNAL_SIMULATION`) and controlled
  replay off.

The collection-only entry point does not check `IMP_LIVE_OBSERVATIONAL`; each
news provider keeps its own live gate and credentials. The child inherits the
supervisor's environment except Anthropic, OpenAI, Azure OpenAI and Gemini
variables. Supply only the settings the collectors need.

## Supervision behavior

The supervisor keeps one reserved row, `__pf01_supervision__`, in
`news_collection_jobs`. It is control evidence, not a provider job. The row
carries a 120-second lease renewed every tick, the state, the restart history
and the last 32 events.

- A second supervisor is refused while the lease is live
  (`SUPERVISOR_OWNER_ACTIVE`). `--run` waits up to 150 seconds for a dead
  supervisor's lease to expire, says why it is waiting, then gives up.
- After an unclean supervisor exit, the next one records
  `UNCLEAN_SUPERVISOR_RESTART` and waits 120 seconds before spawning, or longer
  if a backoff was already running.
- A disabled flag or an enabled execution gate stops the child and the
  supervisor.

### Restart budget

| Setting | Value | Meaning |
|---|---|---|
| `RESTART_LIMIT` | 3 | Automatic restarts allowed in one rolling window |
| `RESTART_WINDOW_SECONDS` | 3,600 | The rolling window |
| Backoff | 120, 240, 480 s | Doubles with each restart in the window |
| `HEALTHY_RESET_SECONDS` | 1,800 | Continuous child uptime that restores the full allowance |
| `COOLDOWN_LIMIT` | 3 | Exhausted windows in a row before the block latches |
| `STORAGE_GRACE_SECONDS` | 900 | How long the supervisor waits for unavailable storage |

These are constants in `news/supervision.py`; there is no environment override.

- A child exit or a failed start records `CHILD_PROCESS_EXIT_GAP_UNVERIFIED`
  (with the exit code) or `CHILD_START_FAILED`, then backs off. The 120-second
  floor is one lease interval, so a dead child's job leases have expired.
- When the window's restarts are used up the state is `COOLDOWN`
  (`RESTART_LIMIT_EXCEEDED`). The supervisor keeps running and keeps its lease
  but starts nothing until the oldest restart leaves the window.
- A child that stays up for 30 minutes clears the window and the cooldown count
  (`RESTART_BUDGET_RESET_AFTER_HEALTHY_PERIOD`). "Healthy" means the process
  stayed alive; the child ends itself when a worker gives up, as described below.
- Three exhausted windows without a healthy period latch `BLOCKED` with
  `PERSISTENT_CHILD_FAILURE`. A child that exits with code 78 has refused its
  own configuration (execution gate, a store read successfully at the wrong
  schema, invalid market targets or news selection); that latches
  `CHILD_CONFIGURATION_REJECTED` at once and spends no restart. A store that
  could not be read at child start is an ordinary failure, not a rejection.
- A latched block survives supervisor restarts. Nothing restarts until the
  operator clears it.

A child that fails immediately every time is started at most six times in
about 70 minutes (the first start, three restarts, then one after each of two
cooldowns) before the block latches. It is never restarted in a tight loop.

### Storage and lease loss

- Storage that cannot be read (for example a drive that is briefly absent)
  stops the child and puts the supervisor in `STORAGE_WAIT` for up to 15
  minutes. If the same database returns, the supervisor re-owns its row only
  when no other supervisor claimed it, records
  `SUPERVISION_OUTAGE_GAP_UNVERIFIED`, charges one restart and backs off. After
  15 minutes it blocks.
- A replaced database (`STORAGE_REPLACED`) or the 512 MiB database-plus-WAL
  guard (`STORAGE_BOUND_EXCEEDED`) blocks at once. Neither is ever adopted or
  retried.
- A lease that lapsed without being claimed, for example after host sleep,
  stops the child and is handled the same way as a storage outage
  (`SUPERVISOR_LEASE_LAPSED`). A lease claimed by another supervisor is
  `OWNERSHIP_LOST` and final.
- A database that is briefly busy does not stop the child. If the supervisor
  cannot write its evidence for 60 seconds, half the lease, it stops the child
  and waits as for a storage outage (`SUPERVISION_EVIDENCE_UNAVAILABLE`).

### What ends the child

The child stops when its parent's lease is lost, when a worker reports
`BLOCKED`, `FAILED` or `STALE`, or when a worker thread is no longer alive.
`RETRYING`, `IDLE` and `WAITING_FOR_OWNERSHIP` do not end it: those are the
workers' own bounded recovery and standby states. A locked database or a
briefly unreadable store is retried by the worker (six attempts over about 30
seconds for the market writer, the same for news storage) and reaches the
supervisor only if the worker gives up. A replaced store, the 512 MiB ceiling,
a full disk, corruption and constraint failures are not retried. Child output is discarded; the exit
code and the durable job rows are the available cause evidence.

## Status

The serving backend's `/provider/health` adds `collection_supervision`, read
from the evidence row through a read-only connection. An expired lease is shown
as `STALE`. `health_basis` is `PERSISTED_PARENT_LEASE_NOT_SOURCE_COVERAGE`: it
describes the supervising process, not provider or feed coverage. The headless
process exports no queue, backlog or provider diagnostics of its own.

## Stop and recovery

Stop the foreground supervisor with Ctrl-C. It writes `stop` to the child's
stdin, waits up to 15 seconds, then terminates only that child. Closing the
parent's pipe also stops the child, so an orphan cannot continue unattended.
A blocked or disabled state keeps its original reason when the lease is released.

To recover from a latched block, first find and correct the cause, using
`--status` and the job rows. Then, with no supervisor running:

```text
python tools/platform/pf01_supervisor.py --reset-restart-budget
```

This clears the restart window, the cooldown count and the latch, records
`OPERATOR_RESTART_BUDGET_RESET` with the reason it cleared, and keeps the crash
total and event history. It is refused while a supervisor owns the lease, it
needs the same `IMP_STATE_DIR` and current schema as `--run`, and it starts
nothing. A `COOLDOWN` needs no action: it ends by itself.

Before any migration, take the backup with the previous source or with
SQLite's backup API on a read-only connection. `tools/state/backup.py` and
`tools/state/check.py` in this source open the store through the migrating
connection and would upgrade it.

## Known limits

- No physical drive removal, forced termination of the serving application,
  Windows sleep or real provider failure has been exercised. Storage outages
  and lease lapses are simulated.
- A child that fails repeatedly but only after 20 minutes or more never uses up
  a window, and one that survives 30 minutes resets its allowance. Either is
  restarted about twice an hour indefinitely.
- `STORAGE_WAIT` recovery is exercised only in simulation. After a real drive
  removal Windows invalidates the open database handles, so expect the
  supervisor to block after the grace period and need a restart.
- A supervisor that dies while its child is running does not charge a restart
  for the next supervisor's first start. Whatever restarts the supervisor
  itself is outside this budget.
- A clock set backwards delays a pending backoff, cooldown or lease expiry by
  the size of the jump.
- An invalid market-persistence configuration still stops serving-backend
  startup. Only a live owner or a busy database is deferred.
- The restart thresholds are not configurable without a code change.
