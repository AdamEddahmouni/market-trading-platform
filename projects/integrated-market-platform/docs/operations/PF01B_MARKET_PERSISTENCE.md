# PF-01B market-stream persistence

This extension is default off. It records eligible observations already received
by existing producers. It does not subscribe to instruments, keep Kraken demand
alive, contact providers, backfill, infer entitlement, dispatch AI, or change
Paper/Live authority. PF-01 remains partial; this code is not overnight acceptance.

## Sources and selection

`IMP_MARKET_PERSISTENCE_ENABLED=1` opts in at the existing backend `serve`
lifecycle. An explicit absolute `IMP_STATE_DIR` containing the existing
`imp-state.sqlite3` is required. Storage is validated before store loading; the
writer uses SQLite `mode=rw`, never a missing-file fallback. Deployment and the
additive schema-13 migration require separate operator authorization.

`IMP_MARKET_PERSISTENCE_SOURCES` is an explicit comma-separated subset of
`moomoo,kraken`. `IMP_MARKET_PERSISTENCE_SYMBOLS` contains at most 20 exact
instrument IDs or provider symbols. For example, an equity uses `AAPL`; a Kraken
pair can use `BTC/USD` while its canonical XA01 instrument ID is preserved in
the record. These settings select persistence only, not subscriptions or rights.

Supported received paths:

- `LiveObservationalRuntime.ingest_record`: moomoo L1, ticks and depth at the
  existing admission boundary, preserving quality/admission evidence.
- `CurrentBarsService._load_1m`: normalized completed 1m bars on an actual cache
  refresh. Forming bars and repeated cache reads are excluded; 5m/15m derived
  views do not create redundant capture streams. Each refresh returns the
  provider's whole rolling window, so the writer queues only bars or revisions it
  has not already accepted for a selected symbol, newest first. After a restart
  the first window can exceed the queue; the remainder is counted as overflow
  and offered again on the next refresh.
- `KrakenStreamRuntime`: validated native trades and checksum-valid book
  snapshots/updates from the existing selected-pair connection. Books retain
  message type and subscription anchor; missing provider event time stays null.

IBKR uses its separate adapter/state/callback-journal path; it does not pass
through the moomoo runtime ingress. IBKR, Kraken REST snapshots/OHLC,
full-universe screener snapshots, macro/release feeds and historical corpus
builders are not newly connected here. Existing explicit archives remain intact.

## Persistence contract

Schema 13 adds `market_stream_records`, `market_stream_checkpoints`,
`market_stream_runs` and `market_stream_gaps` to the existing local-state database.
It retains news schema 12 and all prior tables. No new database family is created.

Every record keeps provider identity, canonical instrument, provider symbol,
capability and raw/normalized source payload. Event time, provider time, local
receipt, existing normalization time and persistence time are separate integer
UTC epoch-nanosecond fields. Unavailable event/provider/normalization time is
null. Kraken Decimal values become exact strings, preserving all digits;
consumers should parse those values as decimals. Runtime span handles are excluded
from provider evidence; serializable trace metadata remains available.

Trade keys use provider/instrument/provider-symbol/capability, native payload
sequence or Kraken trade ID, and an immutable payload/event-clock revision hash.
When no native trade identity exists, exact local receipt is the observation key.
Quote/depth keys include local receipt; identical prices received at distinct
times remain distinct. Bar keys use provider, instrument, 1m resolution and bar
end plus revision hash. Exact replay is idempotent; corrections append versions
and never overwrite an earlier receipt. Historical readers must select the
appropriate revision as known at the requested receipt/persistence cutoff rather
than sum trade revisions or assume the latest value was known earlier.

One `BEGIN IMMEDIATE` transaction inserts a bounded batch, advances committed
watermarks, saves pending gap evidence and renews writer ownership. Uniqueness
constraints enforce replay dedupe. A record is acknowledged as committed only
after `COMMIT` succeeds with WAL and writer-local `synchronous=FULL`. Shared
transactions release their lock after a failed begin and roll back a failed
commit. Other connections retain their existing synchronous policy.

Checkpoints are committed event/receipt watermarks plus the last inserted record
and commit time. They are not provider replay cursors, a contiguous sequence
guarantee or a certificate of historical completeness. Late observations cannot
regress the maximum event/receipt clocks.

## Bounds and failures

Defaults: 512 queued records, 64 records/transaction, 128 KiB/record, 2 MiB/batch,
one writer thread, at most 20 selected targets and a 512 MiB database-plus-WAL
acquisition ceiling with an 8 MiB conservative batch-growth reserve. The ceiling
is a pre-write acquisition guard, not an exact filesystem quota. Default queued
payload is bounded by 64 MiB plus Python/container overhead. No automatic
deletion, compaction or retention policy is introduced.

Producer enqueue never waits for a database transaction. Overflow rejects the
new incoming record and marks an observed gap. A failed transaction retains its
batch for bounded retries, leaves checkpoints unchanged and reports `FAILED`.
Retries wait one second after failure. SQLite writer busy timeout is 250 ms.
Disk disappearance/replacement or ceiling exhaustion refuses writes without
creating another database. Pending gaps remain visible in memory until durable
storage is available; they cannot be promised durable during a storage outage.

One durable writer owns a 120-second lease. Concurrent owners are refused.
The worker renews its heartbeat even when idle. After an expired unclosed lease,
a new owner records `UNCLEAN_RESTART_NO_REPLAY`; clean downtime is still marked
unverified. The first run has unknown initial coverage. Provider disconnects,
sequence anomalies, invalid books, ingress rejection and overflow remain visible.
No provider replay/backfill is attempted. An expired owner fails closed and
requires a valid restart; a reconnect alone does not establish complete coverage.

Shutdown stops accepting records, joins the owned worker with a bounded wait and
drains pending batches for up to five seconds. A failed/incomplete drain leaves
the run unclosed for recovery diagnosis. Startup exceptions close resources owned
by that startup. Abrupt process exit loses uncommitted queue contents; restart
evidence marks this uncertainty rather than fabricating those observations.

## Status and operation

The existing authenticated `/provider/health` payload contains
`market_persistence`: state, selected targets, receipt/commit clocks, last durable
checkpoint, queue backlog/peak, rejection/dedupe counts, known/pending gap classes,
limits, write duration and explicit `OBSERVED_ONLY_NOT_COMPLETE` coverage.
Received and committed data are separate. No second dashboard, start route,
provider control or credential output is added.

The backend must be restarted into a separately approved accepted deployment to
use this code. No restart, deployment, production migration or activation was
performed during implementation. Closing UI demand can still stop subscriptions;
the writer alone does not collect overnight. Provider entitlement, retention
decisions for higher volumes and actual overnight observation remain separate
PF-01 concerns. The headless supervisor in
[PF01_COLLECTION_SUPERVISION.md](PF01_COLLECTION_SUPERVISION.md) does not supply
market observations to this writer.

The fixture benchmark measured 10,000 synthetic trades in controlled batches on
the SSD. See the task evidence report for throughput, storage and memory results;
these do not qualify live traffic, all symbols or simultaneous workloads.
