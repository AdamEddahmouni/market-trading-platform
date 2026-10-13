# PF-01B market-stream persistence

This extension is default off. It records eligible observations already received
by existing producers. The writer itself does not subscribe to instruments, keep
Kraken demand alive, contact providers, backfill, infer entitlement, dispatch AI,
or change Paper/Live authority. Demand for a headless process is a separate,
also default-off component described in
[PF01_COLLECTION_SUPERVISION.md](PF01_COLLECTION_SUPERVISION.md). PF-01 remains
partial; this code is not overnight acceptance.

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
new incoming record and marks an observed gap. A failed transaction rolls back,
retains its batch and leaves checkpoints unchanged. SQLite writer busy timeout
is 250 ms. Pending gaps remain visible in memory until durable storage is
available; they cannot be promised durable during a storage outage.

Failures are classified:

| Failure | State | Handling |
|---|---|---|
| Database busy or locked, I/O error, store briefly unreadable | `RETRYING` | Same batch retried after 1, 2, 4, 8, 16 s. The sixth consecutive failure is `FAILED` with `WRITER_RETRY_LIMIT_EXCEEDED`. A writer that owns nothing and has nothing queued stays `IDLE` through an outage |
| Run lease lost | `RETRYING` | The run is abandoned and never written again. Ownership is re-acquired through the normal path, which records the abandoned run as `UNCLEAN_RESTART_NO_REPLAY` |
| Store replaced, ceiling reached, disk full, corruption, constraint failure | `FAILED` | Not retried. The worker stops accepting and records `WRITER_FAILURE` |
| A live writer in another process holds ownership | `WAITING_FOR_OWNERSHIP` | Retried every 2 to 30 s without limit; the bounded queue applies meanwhile |

A retry that later succeeds stores every record once (record IDs are
idempotent) and writes no loss gap, because nothing was lost. Records rejected
because the queue filled during the wait are counted in `QUEUE_OVERFLOW`. No
failure creates another database.

### Ownership

At most one writer owns the store. Ownership is two things held together: an
exclusive operating-system lock on the sidecar file
`imp-state.sqlite3.market-writer.lock`, and an open row in `market_stream_runs`
with a 120-second lease renewed on every flush. The file is empty and is created
only beside an existing database.

- The lock is released by the operating system when its process ends. A new
  writer that obtains the lock therefore knows any run still open belongs to a
  dead process, closes it with `UNCLEAN_RESTART_NO_REPLAY` and proceeds at
  once, even if that run's lease has not expired. A backend restarted seconds
  after a crash no longer waits out the lease.
- While another process holds the lock, ownership is refused whatever the lease
  says. A stalled but living owner is never overridden.
- Every flush re-reads its own run inside the write transaction and refuses to
  commit if the run was closed or its lease lapsed, so two writers cannot both
  store records even if the lock were bypassed.
- A writer started by the backend or the headless entry point owns nothing until
  it has an observation or a gap to store (`state: IDLE`,
  `ownership: NOT_HELD`). After 120 seconds with nothing to store it closes its
  run cleanly and releases the lock; the next observation re-acquires. Clean
  downtime between runs is still marked `CAPTURE_DOWNTIME_UNVERIFIED`.
- A backend that starts while another process owns the writer starts normally.
  Its writer reports `WAITING_FOR_OWNERSHIP` with
  `error: MARKET_CAPTURE_OWNER_ACTIVE` and `collecting: false`, and takes over
  automatically when the owner stops.

A lock call that fails for any reason other than contention is a storage
fault and takes the bounded retry path; it is not reported as a live owner.
Each idle release and re-acquisition adds one run row and one downtime gap row,
so very sparse supply grows those two tables by at most one pair per 120
seconds. All writer processes on one store must run this source. The first run has
unknown initial coverage. Provider disconnects, sequence anomalies, invalid
books, ingress rejection and overflow remain visible. No provider replay or
backfill is attempted; a reconnect alone does not establish complete coverage.

Shutdown stops accepting records, joins the owned worker with a bounded wait and
drains pending batches for up to five seconds. A failed/incomplete drain leaves
the run unclosed for recovery diagnosis, and records still queued by a writer
that never obtained ownership are reported as
`MARKET_CAPTURE_UNPERSISTED_AT_SHUTDOWN`. Startup exceptions close resources owned
by that startup. Abrupt process exit loses uncommitted queue contents; restart
evidence marks this uncertainty rather than fabricating those observations.

## Status and operation

The existing authenticated `/provider/health` payload contains
`market_persistence`: state, selected targets, receipt/commit clocks, last durable
checkpoint, queue backlog/peak, rejection/dedupe counts, known/pending gap classes,
limits, write duration and explicit `OBSERVED_ONLY_NOT_COMPLETE` coverage. It
also reports `ownership`, `collecting`, `transient_failures`, `ownership_waits`
and `idle_releases`.
Received and committed data are separate. No second dashboard, start route,
provider control or credential output is added.

The backend must be restarted into a separately approved accepted deployment to
use this code. No restart, deployment, production migration or activation was
performed during implementation. Closing UI demand can still stop subscriptions;
the writer alone does not collect overnight. Provider entitlement, retention
decisions for higher volumes and actual overnight observation remain separate
PF-01 concerns. A headless child supplies this writer only when the default-off
market supply in [PF01_COLLECTION_SUPERVISION.md](PF01_COLLECTION_SUPERVISION.md)
is enabled and its entitlement gate is open.

### Headless supply load (synthetic)

The real collection-only child was run on the SSD with the maximum 20 selected
targets against synthetic transports, at the shipped limits, 15 seconds per
rate:

| Offered trades/s (20 streams) | Committed/s | Overflow | Database bytes per stored record |
|---|---|---|---|
| 99 | 98 | 0 | 1,578 |
| 284 | 289 | 0 | 1,445 |
| 747 | 740 | 0 | 1,466 |

Higher rates, bursts, depth and real provider payloads were not measured. A
7-second database lock at 60 trades/s per stream did fill the 512-record queue;
the rejected records were counted in `QUEUE_OVERFLOW` and the child kept
running.

Storage is the binding limit, not throughput. At about 1.5 KB per stored
record the 512 MiB ceiling holds roughly 350,000 records, and nothing is ever
deleted. That is about one hour at 100 trades per second. Each L1 target adds a
stored quote snapshot every 2 seconds whether or not the price moved: 20 L1
targets alone are about 36,000 records and 50 MiB per hour, which reaches the
ceiling in about 10 hours. When the ceiling is reached the writer stops with
`MARKET_STORAGE_FULL`; the supervisor blocks on `STORAGE_BOUND_EXCEEDED`. A
retention decision is needed before a selection of that size can run for a
night. These figures come from synthetic payloads and do not qualify live
traffic.

The fixture benchmark measured 10,000 synthetic trades in controlled batches on
the SSD. See the task evidence report for throughput, storage and memory results;
these do not qualify live traffic, all symbols or simultaneous workloads.

## PF-01F observation accounting and shutdown

Process-local writer health exposes `selected_received`, `accepted`, `rejected`,
`normalizing`, `committed`, `duplicates`, `backlog` and `unreconciled`. The
boundary is `SELECTED_WRITER_SUBMIT_THIS_PROCESS`. The invariants are
`selected_received = accepted + rejected + normalizing` and
`accepted = committed + duplicates + backlog`; pending normalization/queue
work is not loss. `unreconciled` is the sum of absolute residuals. Reject/gap
counts must not be subtracted twice, and mixed-capability gaps must be split
before comparing trade-only counters.

Synthetic producer generation/callback/enqueue is a separate boundary from
socket/ingest receipt. The previous high-rate 38-record discrepancy consisted
of 36 OpenD queued ticks and two Kraken inbox trades. Owned-provider shutdown
quiesces callbacks and drains already observed work while selected demand and
the writer remain alive. Socket shutdown is bounded; it does not establish
external exactly-once delivery or invent counts for bytes never observed.
Counters are not a durable ingress journal. Abrupt interruption leaves an
unknown tail and unclean-restart evidence; no replay is promised.

The collection-only child returns failure when final writer drain fails or
supply reports `SUPPLY_SHUTDOWN_INCOMPLETE`. Stopped supply with a drain,
release or close failure reports `BLOCKED`, `shutdown_incomplete=true` and
`shutdown_error=SUPPLY_SHUTDOWN_INCOMPLETE`. Historical reconcile errors alone
do not classify a later successful shutdown as incomplete. A permanently
stuck provider may still require the supervisor's bounded forced termination,
which is unclean rather than a successful graceful stop.

Writer health includes read-only DB/WAL/free-space `capacity` status: `READY`,
`WARNING` or `STOP_REQUIRED`; unavailable/replaced files report `UNAVAILABLE`.
The warning is a resource signal, not collection or entitlement certification.
See [capacity planning](PF01_STORAGE_CAPACITY.md) and
[deployment and acceptance](PF01F_DEPLOYMENT_ACCEPTANCE.md).
