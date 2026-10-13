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
  bounded budget. It registers no Windows task or service.
- `src/market_platform_foundation/news/supervision.py` holds the supervisor
  logic and its durable evidence row.

## Headless market supply is not provided

The market writer is a sink for observations that existing producers already
receive. Provider subscriptions are acquired only by the serving backend's
request-driven projections. The collection-only process creates no moomoo
runtime, no Kraken connection and no bar polling, so a headless writer receives
nothing. It still owns the single 120-second writer lease, which makes a serving
backend with market persistence enabled refuse to start its own writer.

Until a separately approved source-demand design exists, treat the headless
entry point as news-only and leave `IMP_MARKET_PERSISTENCE_ENABLED=0` for it.
A `RUNNING` supervisor or a `READY` writer is not evidence of market coverage.

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
carries a 120-second lease renewed every tick, the state, a crash counter and
the last 32 events.

- A second supervisor is refused while the lease is live (`SUPERVISOR_OWNER_ACTIVE`).
- After an unclean supervisor exit, the next one records
  `UNCLEAN_SUPERVISOR_RESTART` and waits 120 seconds before spawning.
- A child exit records `CHILD_PROCESS_EXIT_GAP_UNVERIFIED` with the exit code,
  then waits at least 120 seconds before the next start.
- Three child exits or start failures block the supervisor with
  `RESTART_LIMIT_EXCEEDED`. The counter is persisted and never resets, including
  across supervisor restarts. There is no reset command; clearing it is a
  deliberate operator action on the evidence row.
- Missing or replaced storage, the 512 MiB database-plus-WAL guard, a lost
  lease, a disabled flag or an enabled execution gate stop the child.
- A supervisor whose lease expired, for example after host sleep, stops its
  child and does not resume. A new start is required.

The child stops when its parent's lease is lost, when either worker reports
`BLOCKED`, `FAILED` or `STALE`, or when a worker thread is no longer alive. One
failed market flush is enough to stop the child and consume a restart credit, so
the writer's own six-attempt retry budget applies only under the serving
backend. Child output is discarded; the exit code and the durable job rows are
the available cause evidence.

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

Before any migration, take the backup with the previous source or with
SQLite's backup API on a read-only connection. `tools/state/backup.py` and
`tools/state/check.py` in this source open the store through the migrating
connection and would upgrade it.

## Known limits

- No physical drive removal, forced termination of the serving application,
  Windows sleep or real provider failure has been exercised.
- When the writer is enabled in the serving backend, a writer start failure,
  including a live lease within 120 seconds of an unclean exit, stops backend
  startup rather than degrading to a blocked status.
- A news job that returns partial feeds or rejected items backs off
  exponentially, up to one day, like a failed job.
