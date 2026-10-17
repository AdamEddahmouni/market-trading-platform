# PF-01 collection supervision

Status: implemented and verified offline only. Not deployed, not activated, and
no real overnight run has been observed. This page covers the headless
collection-only entry point and its bounded-restart supervisor. Raw news
collection is described in [PF01_RAW_COLLECTION.md](PF01_RAW_COLLECTION.md) and
market persistence in [PF01B_MARKET_PERSISTENCE.md](PF01B_MARKET_PERSISTENCE.md).

## What exists

- `tools/ui1/run_ui_api.py --collect-only` starts only the raw news collector,
  the market writer and, when explicitly enabled, the headless market supply
  described below. It loads no store, private `.env` or saved provider
  settings, serves no HTTP, and never runs Paper recovery, Screener warmup or AI.
  It cannot be combined with `--serve`.
- `tools/platform/pf01_supervisor.py` prints a read-only plan by default. With
  `--run` it owns one `--collect-only` child process and restarts it within a
  bounded budget. `--status` prints the persisted evidence without taking
  ownership. `--reset-restart-budget` is the operator recovery described below.
  It registers no Windows task or service.
- `src/market_platform_foundation/news/supervision.py` holds the supervisor
  logic and its durable evidence row.

## Headless market supply (default off)

The market writer is a sink for observations that existing producers already
receive. In the serving backend those producers are subscribed by
request-driven projections. A collection-only process has no such demand, so by
default it creates no moomoo runtime and no Kraken connection, and its writer
receives nothing and owns nothing (`IDLE`, `ownership: NOT_HELD`).

`market_data/headless_supply.py` can hold that demand instead. It adds no
provider, transport or storage path. It asks the existing subscription
authorities (the OpenD runtime's reference-counted subscription manager and the
Kraken selected-pair stream) for explicitly listed streams under one consumer
id, `pf01-headless-collector`, and records reach the writer through the
existing ingress. It is implemented and verified offline against synthetic
transports only. No real subscription has been requested and no account
entitlement has been verified.

### Configuration

| Variable | Meaning |
|---|---|
| `IMP_MARKET_SUPPLY_ENABLED=1` | Opt in. Default off |
| `IMP_MARKET_SUPPLY_TARGETS` | `source:symbol@CAPABILITY+CAPABILITY`, comma separated. Empty by default. At most 20 targets |
| `IMP_MARKET_SUPPLY_ENTITLED_SOURCES` | Sources (`moomoo`, `kraken`) whose data rights the operator has confirmed. Empty by default |

Example of the format only, not a recommendation of what to collect:
`moomoo:AAPL@US_EQUITY_L1+US_EQUITY_TICKS`.

- moomoo symbols are plain US equity tickers (letters and digits);
  capabilities are `US_EQUITY_L1`, `US_EQUITY_TICKS`, `US_EQUITY_DEPTH`. A
  dotted or hyphenated ticker such as `BRK.B` is refused: the existing feed
  would store it under a different instrument name, so it would be subscribed
  and never persisted. Kraken symbols are the canonical
  `XA01:` instrument ID; capabilities are `CRYPTO_TRADES`, `CRYPTO_BOOK`.
- Every target's source must be in `IMP_MARKET_PERSISTENCE_SOURCES` and its
  symbol in `IMP_MARKET_PERSISTENCE_SYMBOLS`. Supply never subscribes to
  something that is not stored, and nothing is expanded to other instruments.
- moomoo targets need `IMP_LIVE_OBSERVATIONAL=1` and `IMP_MOOMOO_LIVE=1`;
  Kraken targets need `IMP_CRYPTO_LIVE=1`. moomoo supply is refused with
  `IMP_IBKR_LIVE=1`, shadow recording on, `IMP_LIVE_FIXTURE_FEED` set, or
  `IMP_OBSERVATIONAL_PROVIDER` set to anything but `auto` or `moomoo`, because
  the shared runtime would then start another feed, replay a fixture into the
  store, or start no OpenD feed at all.
- A rejected target list ends the child with exit code 78 before any worker
  starts, and the supervisor latches `CHILD_CONFIGURATION_REJECTED`.

1-minute bars (`CURRENT_BAR_1M`) are produced by a request-driven cache in the
serving backend and are not supplied headlessly. IBKR is not supplied.

### Entitlement gate

No provider session is opened and nothing is requested from a source until
both of these hold:

1. The source is listed in `IMP_MARKET_SUPPLY_ENTITLED_SOURCES`. This is the
   operator's statement that the account or the venue's terms permit collecting
   and storing that data. It is not a credential and nothing infers it.
2. For moomoo, the existing capability probe report is present, younger than
   `IMP_MOOMOO_PROBE_STALENESS_SEC` (24 hours by default) and marks that
   capability `account_entitled`. A missing or stale report, or a capability
   the probe did not verify, keeps that stream `BLOCKED`. The report file is
   read before the OpenD runtime is created and re-read while the child runs: a
   report that ages past the limit releases the streams it allowed, and a
   refreshed report is picked up without a restart. Running the probe contacts
   OpenD and is a separate decision.

   The platform's live runtime (Paper authority, health, capability rows) does
   the same: it re-reads and re-ages its report at most every 30 seconds, so a
   report past the limit fails closed without a restart, a renewed report takes
   effect without one, and a report older than the loaded one never replaces
   it while the loaded one is still fresh. The SSD launcher (`RUN_COLLECTOR.py`,
   operator file) renews the read-only quote probe whenever it is older than
   `probe_max_age_hours` and OpenD answers, in or out of a market session, and
   publishes it atomically to the collector's report and to the platform's
   default report path (only when newer); a failed renewal is retried after
   `retry_minutes`.

Kraken public market data has no account, so only the first condition applies.
The first Kraken request resolves the pair through the existing resolver, which
fetches Kraken's public `AssetPairs` catalog once over HTTPS (retried at most
every 30 seconds on failure) before the WebSocket is opened.
A configured key, a reachable OpenD or a passing synthetic test satisfies
neither. A closed gate does not end the child: news keeps running and the
supply reports `BLOCKED` with the reason.

### Lifecycle

- Start: the child validates the target list, starts the writer and collector,
  then reconciles demand every 5 seconds.
- Provider loss: reconnect is the existing runtime's. Kraken retries with
  backoff 1, 2, 4, 8, 16, 30 s (jittered, capped at 30 s) and resubscribes every
  demanded channel on the new connection. The OpenD feed retries on its
  configured schedule and resubscribes from the subscription manager. Each lost
  session writes one `KRAKEN_DISCONNECT_NO_REPLAY` or
  `MOOMOO_DISCONNECT_NO_REPLAY`; failed retries write nothing more, so an
  unreachable provider does not keep an idle writer owning the store. Nothing
  is backfilled.
- One provider failing does not stop the other or the news collector.
- Restart: a restarted child subscribes again from the same configuration. The
  writer records the dead run as `UNCLEAN_RESTART_NO_REPLAY`.
- Stop: demand is released first, then the provider sessions this process
  opened are closed, then the writer drains.
- Target changes take effect by changing the configuration and restarting the
  child. There is no runtime control route.
- A provider refusal is reported as `REFUSED` and recorded once as a
  `SUPPLY_SUBSCRIPTION_REFUSED` gap. The existing feed retries a refused OpenD
  subscription every 15 seconds, not on every sync.

### Ownership with a serving backend

The serving backend and a headless child are separate processes with separate
provider sessions; neither can remove the other's subscriptions. Only one
process can own the market writer. While another living process owns it, the
headless supply releases its demand and reports `STANDBY`, so it never holds
subscriptions it could not store. It subscribes again within one reconcile
interval after that owner stops or releases. An owner that died inside its
lease is recognised through the owner lock and does not cause a standby.

While the serving backend owns the writer it stores only what its own screens
demand. To make the headless child the collector, leave
`IMP_MARKET_PERSISTENCE_ENABLED` off in the serving backend.

### Sessions

Subscriptions are held continuously; the provider decides when data flows.
Market hours are used only to decide whether silence is a fault. US equities
expect data in the pre-market, regular and after-hours sessions on trading days
in the repository's holiday calendar. Overnight quotes are stored if they
arrive, and their absence is not reported as stale. Kraken is continuous, with
venue maintenance as its own state. No AI or trading window applies to
collection. The calendar has no early-close list and covers 2025 and 2026 only;
outside those years the session is `CALENDAR_UNAVAILABLE` and silence is not
flagged.

### Status

`/provider/health` gains `market_supply`, and `pf01_supervisor.py --status`
prints the same object. The child saves it in a reserved row,
`__pf01_market_supply__`, at most every 30 seconds or on a state change; a row
not refreshed for 120 seconds is shown as `STALE`.

| Field | Says |
|---|---|
| `enabled`, `configured` | Supply was explicitly enabled with a valid target list |
| `providers.<source>.entitlement_confirmed` | The operator confirmation for that source |
| `providers.<source>.available`, `recovery_pending`, `maintenance` | Connected, reconnecting, or venue maintenance |
| `targets[].subscription_requested`, `subscription_active` | Asked of the authority; acknowledged by the provider |
| `targets[].last_received_ns`, `last_commit_ns` | From the durable checkpoint for that stream |
| `targets[].state` | `BLOCKED`, `STANDBY`, `REQUESTED`, `REFUSED`, `ACTIVE_NO_DATA`, `COLLECTING`, `STALE`, `SESSION_CLOSED`; `UNKNOWN` once the saved row has expired |
| `writer`, `writer_degraded` | The writer's own state, backlog, rejections and commit clocks |
| `state` | `BLOCKED`, `STANDBY`, `DEGRADED`, `RECOVERY_PENDING`, `STALE`, `COLLECTING`, `SUBSCRIBED_NO_DATA`, `WAITING`, `STOPPED` |

`COLLECTING` requires a commit for that stream within the last 300 seconds and
since this child requested it; a checkpoint left by an earlier run or another
process does not count. A subscription is `subscription_active` only while its
provider is connected. A
running process, a requested subscription or an active subscription is never
reported as collecting on its own. `STALE` means a stream was active for more
than 300 seconds in a session that expects data and nothing was committed; for
a thinly traded instrument that can be normal.

## Activation requirements

All of the following must hold; each is checked before a child is spawned:

- `IMP_PF01_SUPERVISION_ENABLED=1` and the `--run` flag.
- `IMP_PERSIST_STATE=1` and an absolute `IMP_STATE_DIR` whose
  `imp-state.sqlite3` already exists.
- The store is already at the current schema. Both the supervisor and the
  collection-only entry point check this through a read-only connection and
  refuse with `APPROVED_SCHEMA_MIGRATION_REQUIRED`; neither migrates a store.
- At least one of `IMP_NEWS_COLLECTION_ENABLED=1` or
  `IMP_MARKET_PERSISTENCE_ENABLED=1`. Market supply additionally needs the
  settings in the section above; without them the child holds no provider
  demand.
- Every execution gate off (`IMP_PAPER_EXECUTION`, `IMP_BROKER_PAPER_EXECUTION`,
  `IMP_MOOMOO_PAPER_EXECUTION`, `IMP_LIVE_EXECUTION`,
  `IMP_BROKER_LIVE_EXECUTION`, `IMP_LIVE_INTERNAL_SIMULATION`) and controlled
  replay off.

The collection-only entry point does not itself check `IMP_LIVE_OBSERVATIONAL`;
each news provider keeps its own live gate and credentials, and market supply
checks the provider gates listed above. The child inherits the
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
| `UNHEALTHY_FAILURE_LIMIT` | 9 | Child failures with no healthy period between them before the block latches (`RESTART_LIMIT` x `COOLDOWN_LIMIT`) |
| `STORAGE_GRACE_SECONDS` | 900 | How long the supervisor waits for unavailable storage |

These are constants in `news/supervision.py`; there is no environment override.

- A child exit or a failed start records `CHILD_PROCESS_EXIT_GAP_UNVERIFIED`
  (with the exit code) or `CHILD_START_FAILED`, then backs off. The 120-second
  floor is one lease interval, so a dead child's job leases have expired.
- When the window's restarts are used up the state is `COOLDOWN`
  (`RESTART_LIMIT_EXCEEDED`). The supervisor keeps running and keeps its lease
  but starts nothing until the oldest restart leaves the window.
- A child that stays up for 30 minutes clears the window, the cooldown count
  and the failure streak (`RESTART_BUDGET_RESET_AFTER_HEALTHY_PERIOD`). "Healthy" means the process
  stayed alive; the child ends itself when a worker gives up, as described below.
- Three exhausted windows without a healthy period latch `BLOCKED` with
  `PERSISTENT_CHILD_FAILURE`. So do nine child exits or failed starts with no
  healthy period between them, however far apart. A child that fails after 16
  to 29 minutes never fills a window (its restarts leave the hour before a
  third joins them), so the window alone restarted it for ever; the streak
  stops it after nine starts, about four to five hours. Stops the supervisor
  itself causes (storage outage, lapsed lease) are charged to the window but
  not to the streak.
- A child that exits with code 78 has refused its own configuration (execution
  gate, a store read successfully at the wrong schema, a corrupt store, invalid
  market targets, supply targets or news selection); that latches
  `CHILD_CONFIGURATION_REJECTED` at once and spends no restart. A corrupt store
  is reported as `SCHEMA_CHECK_STORAGE_INVALID`, not as a missing migration. A
  store that could not be read at child start is an ordinary failure, not a
  rejection.
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
`BLOCKED`, `FAILED` or `STALE`, or when a worker thread (including the supply
reconciler) is no longer alive. Blocked, standby or stale market supply is
reported and does not end the child.
`RETRYING`, `IDLE` and `WAITING_FOR_OWNERSHIP` do not end it: those are the
workers' own bounded recovery and standby states. A locked database or a
briefly unreadable store is retried by the worker (six attempts over about 30
seconds for the market writer, the same for news storage) and reaches the
supervisor only if the worker gives up. A replaced store, the 512 MiB ceiling,
a full disk, corruption and constraint failures are not retried. A writer that
owns nothing and has nothing to store ignores a storage outage instead of
spending its retries on it. Child output is discarded; the exit
code and the durable job rows are the available cause evidence.

## Status

The serving backend's `/provider/health` adds `collection_supervision`, read
from the evidence row through a read-only connection. An expired lease is shown
as `STALE`. `health_basis` is `PERSISTED_PARENT_LEASE_NOT_SOURCE_COVERAGE`: it
describes the supervising process, not provider or feed coverage. Market
supply, the writer's queue and provider state are reported separately in
`market_supply` (see above).

## Stop and recovery

Stop the foreground supervisor with Ctrl-C. It writes `stop` to the child's
stdin, waits up to the child's own summed stop bound (59.25 seconds), then
terminates only that child and exits 1 with
`OPERATOR_STOP_CHILD_EXIT_UNVERIFIED`. `--preflight` reports the operational
prerequisites read-only before a run; both are described in
[PF01G_RELEASE_CANDIDATE.md](PF01G_RELEASE_CANDIDATE.md). Closing the
parent's pipe also stops the child, so an orphan cannot continue unattended.
A blocked or disabled state keeps its original reason when the lease is released.

To recover from a latched block, first find and correct the cause, using
`--status` and the job rows. Then, with no supervisor running:

```text
python tools/platform/pf01_supervisor.py --reset-restart-budget
```

This clears the restart window, the cooldown count, the failure streak and the latch, records
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
- A child that survives 30 minutes before each failure counts as healthy every
  time and is restarted about twice an hour indefinitely. That is the meaning
  of the 30-minute threshold; changing it is an operating decision. The
  lifetime `crashes` count and the event history show it.
- Headless market supply has run only against synthetic transports. OpenD and
  Kraken behaviour under real load, real entitlement refusals and real session
  changes are not observed.
- The Kraken pair resolver and its public catalog request are replaced by a
  fixed table in every test, so that path and its failure handling are not
  exercised here.
- Stopping a child whose supply is mid-request can take longer than the
  supervisor's 15-second wait. The child is then terminated; the writer's run
  is recorded as `UNCLEAN_RESTART_NO_REPLAY` on the next start and the status
  row expires to `STALE`.
- After the moomoo probe goes stale the OpenD session this child already opened
  stays open with no subscriptions until the child stops.
- The supply status row is written without the writer's store-identity check.
- With L1 selected, the existing feed polls a quote snapshot every 2 seconds per
  subscribed symbol and every snapshot is stored. See the capacity figures in
  [PF01B_MARKET_PERSISTENCE.md](PF01B_MARKET_PERSISTENCE.md) before selecting
  many L1 targets.
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

## PF-01F capacity and acceptance preparation

Read-only shared-store accounting and explicit workload forecasts are available
through `python tools/market_data_capacity.py`. See
[storage capacity](PF01_STORAGE_CAPACITY.md) for rates, record sizing, warning
and stop semantics, and [deployment/acceptance](PF01F_DEPLOYMENT_ACCEPTANCE.md)
for the inert configuration, protected source/state integration, migration,
rollback and real overnight prerequisites. Forecasts do not activate a source
or certify an account entitlement. The shared DB+WAL ceiling stays 512 MiB;
all history is preserved and collection stops before the existing reserve.

## Child exit on a requested stop

Exit 0 is the child's only confirmation that producers drained and the final
commit landed. When the supervisor stops its child (operator stop, storage
outage, lapsed lease, disabled configuration or a latched block) and the child
exits non-zero, or its handle fails to stop it, the supervisor records
`CHILD_STOP_EXIT_GAP_UNVERIFIED` with the exit code. An operator stop then ends
`STOPPED` with reason `OPERATOR_STOP_CHILD_EXIT_UNVERIFIED` instead of
`OPERATOR_STOP`. The event does not count against the restart budget. A console
interrupt of a standalone `--collect-only` process is a stop request and no
longer hides an incomplete drain behind exit 0.
