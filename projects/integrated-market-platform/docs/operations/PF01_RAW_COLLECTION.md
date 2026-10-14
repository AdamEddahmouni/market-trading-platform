# PF-01 raw collection operation

Status: implementation verified offline; not deployed or
activated. Actual unattended overnight observation is required separately.

This lifecycle collects existing raw headline/filing inputs. It never requests
sentiment, AI synthesis, opportunities, strategy optimization, or orders.
Existing equity/crypto market transports and research collectors are unchanged.

## Prerequisites and activation boundary

An accepted deployment and explicit user approval are required before applying
the schema migration to the normal store or activating unattended collection.
Do not start the existing portable launcher as a test: it owns the user's Paper
and saved-provider state. Use disposable state for verification.

Keep both SSD sibling folder names unchanged. Existing portable launchers resolve
state and dependencies relative to their roots; do not embed a drive letter in
saved collection configuration. Collection requires the launcher's absolute
`IMP_STATE_DIR` to name an already existing database. It refuses missing storage
before normal application startup, preventing a replacement empty store.

After separately approved integration, configuration is supplied to the existing
backend environment. Leave `IMP_NEWS_COLLECTION_ENABLED=0` until provider rights,
no-cost entitlement and persistence permissions are confirmed. To choose jobs:

```text
IMP_NEWS_COLLECTION_ENABLED=1
IMP_NEWS_COLLECTION_PROVIDERS=rss
IMP_NEWS_COLLECTION_UNIVERSES=US_EQUITIES,US_ETFS,FUTURES,BONDS,CRYPTO
```

This example is prospective configuration, not a command executed in this task.
It also requires the existing `IMP_NEWS_RSS_LIVE` gate and applicable SEC contact
identity. Existing gates for Finviz, Finnhub, NewsAPI and SEC remain independent.
Do not enable them just to silence a blocked status. Symbol providers require
`IMP_NEWS_COLLECTION_SYMBOLS`; this selects explicit equity symbols, not a
whole-universe poll. `sec_filings` retains the official-filing source type.

Providers supported by this lifecycle are exactly `finviz`, `rss`, `newsapi`,
`finnhub`, `sec_filings`. Per-provider `IMP_NEWS_COLLECTION_<PROVIDER>_SECONDS`
overrides must be at least 120 / 300 / 900 / 600 / 600 seconds respectively, and
no more than 86,400 seconds. No full article bodies or new social sources are
acquired.

Every source is its own job with its own schedule, lease, failure count and gap
evidence. `rss` creates one job per catalog feed that belongs to a selected
universe (job ID `rss:<feed>:<universe>`, under the first selected universe
that lists the feed), so each feed is requested once per interval however many
universes include it. The universes still select feeds; a single feed cannot be
selected or excluded by name. The job ID contains the first selected universe
that lists the feed, so reordering `IMP_NEWS_COLLECTION_UNIVERSES` starts those
feeds as new jobs. With all ten catalog feeds, `finviz` and the three symbol
providers selected, the 64-job bound allows 17 symbols.

NewsAPI's Developer plan is development/testing only, delayed by 24 hours, and
limited to 100 requests/day. Existing IMP guard is 90; a failed persisted quota
write refuses acquisition. It is not an approved production entitlement.
See [NewsAPI pricing and use restrictions](https://newsapi.org/pricing).
Finnhub and Finviz configured credentials alone do not establish account rights;
confirm the existing account before activation. SEC requires declared contact
identity and its existing Fair Access throttle.

## Start, inspect, stop and recover

The existing UI API `serve` lifecycle starts the raw collection thread after
loading a compatible live-observational store. Replay and disabled settings do
not construct it. This adds no persistent OS registration and does not arm any
Paper controller. Existing unrelated startup behavior retains its own policy.

Inspect `GET /provider/health` → `raw_collection`. The worker reports its actual
thread liveness, heartbeat, scheduling state, pending count, job checkpoint and
provider state. `BLOCKED`, `STALE`, `RETRYING`, `BACKOFF`, `PARTIAL`, `PENDING`,
`HEALTHY` and `PAUSED` must be read with their job details. A running backend
with failed jobs is not healthy coverage. Raw status reads do not start a
collector or refresh news.

`sources` counts jobs by state and `coverage` summarizes each source's last
finished poll: `COMPLETE` only when every one fully succeeded, `PARTIAL` when
some did, `NONE` when none did, `UNKNOWN` before any has finished. It describes
the last poll, not how recent it was; read `last_success` for that. One failing source never changes another source's schedule.

| Source result | Job state | Next poll |
|---|---|---|
| Complete response | `HEALTHY` | The normal interval |
| Some items stored, some rejected or missing | `PARTIAL` (`last_success` not advanced, `rejected_total` kept) | The normal interval |
| Unreachable, malformed or server error | `BACKOFF`, `PROVIDER_UNAVAILABLE` | Doubling from twice the interval, at most one hour |
| Authentication failure, rate limit, missing configuration or live gate off | `BACKOFF` with the specific reason | Doubling, at most one day |
| Adapter still fetching | `PENDING` | 5 seconds, lease kept |

A response whose items were all rejected is a failure; an empty but complete
response is `HEALTHY`. The failure class is kept when a feed that worked earlier
starts returning a rate limit or an authentication error.
Backoff only ever lengthens a source's interval; no source is polled more often
than its configured interval.

A storage failure is not a provider failure. If the fetched batch cannot be
written because the database is busy or briefly unreadable, the collector keeps
that one batch, reports `RETRYING`, makes no provider call and retries the write
after 1, 2, 4, 8 and 16 seconds. After six consecutive failures it reports
`BLOCKED` (`COLLECTION_STORAGE_RETRY_LIMIT_EXCEEDED`) and keeps probing every 30
seconds. A batch whose job lease expired meanwhile is not committed; the job
records `unpersisted_count`. A replaced store and corruption block without
retrying and stay blocked until the process is restarted; the storage bound
blocks until space is available.

Normal backend shutdown signals stop, allows the current bounded call/transaction
to finish, then prevents further jobs. To disable collection for subsequent
starts, set the enable flag to zero. No new UI control or remote mutation route
is introduced. A crashed backend requires the existing operator lifecycle to
restart it; a job that was mid-poll at the crash keeps its lease for up to 120
seconds, and the other jobs run meanwhile.

Records and progress share one SQLite transaction. A write failure never claims
success. Duplicate records retain their first acquisition/publication clocks.
Only one overdue rolling-window request is made, with normal quotas and backoff;
missing historical coverage stays an explicit gap. This is not a guaranteed
catch-up archive or an AI catch-up scheduler.

Missing/replaced SSD database and the 512 MiB database-plus-WAL bound block
acquisition. No fallback store or deletion is performed. Human storage policy is
needed before raising that bound or introducing retention. Stop IMP and vendor
processes safely before ejecting SSD; this task does not test physical ejection.

The backend must remain running, the SSD mounted, the host awake and providers
available. Closing the browser or stopping Vite alone does not stop collection.
Logoff, process crash, sleep, power loss and absent SSD interrupt it. True
unattended operation may need an approved existing-process supervision / Windows
service integration; none is installed or activated here. A default-off headless
entry point with bounded restarts is described in
[PF01_COLLECTION_SUPERVISION.md](PF01_COLLECTION_SUPERVISION.md).

## Schema migration and rollback

Schema v12 is additive: two raw collection tables and a retrieval-time index.
Existing Paper, intelligence and research records are not rewritten. Migration
and empty-table rollback are tested only on disposable v11 fixtures.

Before separately approved deployment, take a consistent SQLite backup with IMP
stopped, using the previous source or SQLite's backup API on a read-only
connection; preserve the old source and the backup. Do not use this source's
`tools/state/backup.py` or `tools/state/check.py` for that: they open the store
through the migrating connection and would upgrade it first. Older source
refuses schema v12. For rollback after collection has written records, preserve
the v12 database and its evidence, then restore the consistent v11 backup to the
old runtime. Do not drop populated collection tables or delete schema metadata
in canonical state. The empty-table downgrade exercised in tests is not an
operator instruction to delete evidence.

## Verification limits

Unit/local integration cover overnight clock, absence of AI/catalog calls,
SQLite reopen, first-receipt dedupe, unknown time, leases, backoff, faults,
storage bounds and fixture migration preservation. Simulated relocation verifies
path independence; a different physical drive letter/PC remains unobserved.

No real provider smoke test or overnight observation is implied. Market capture
is still conditional on existing recorder attachment; this raw news lifecycle
does not make every quote, corporate action, macro publication or sentiment
source a continuously captured feed. These remain explicit PF-01 coverage limits.
