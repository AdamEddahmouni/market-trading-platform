# PF-01 storage capacity and explicit workload planning

PF-01 preserves selected observations in the existing shared local-state SQLite
store. The shipped ceiling remains **512 MiB for database plus WAL**, with an
8 MiB batch reserve. This is a bounded capture budget, not indefinite retention.
No expiry, deletion, production compaction, automatic sampling, target selection,
or archive transition is enabled by this work.

## Existing storage and evidence semantics

Schema 13 stores market records with provider, symbol, capability, native/receipt
identity, immutable revision hash, event/provider/receipt/normalization/persistence
times, and raw payload. A history index and primary-key index add physical cost.
Checkpoints, runs, and gap evidence are separate tables. Schema 12 news records
preserve provider/source and publication/retrieval/ingestion times, plus durable
jobs. Paper, research references and operator state share the database and budget.
Payload bytes alone therefore underestimate required storage.

`LocalStateConnection` uses WAL with NORMAL synchronization; the market writer
uses FULL on its own connection. SQLite's normal automatic checkpoint behavior
remains in force. WAL allocation can persist after a checkpoint; long readers can
pin growth. Capacity counts the physical WAL even when some pages duplicate the
database. No forced checkpoint or vacuum is introduced by the capacity tool.

Existing historical-development artifacts already separate raw, normalized,
manifest and quality files. `ObservationalRecorder` has bounded JSONL captures
and optional part rotation. It does not provide an atomic, restart-safe archive
of this shared SQLite store with a complete verified manifest for every part.
The inference cache has expiry/eviction semantics for reusable computations;
those semantics do not authorize deleting historical evidence. No compatible
compressed/partitioned SQLite evidence transition was found in the inspected
market capture infrastructure. Adding an independent history store or enabling
retention expiry would require a separately approved policy and transition design.

## Implemented capacity contract

`market_data.capacity.capacity_status` is a cheap pure helper for runtime health.
It counts database plus WAL, subtracts the existing 8 MiB emergency reserve,
and optionally limits remaining growth by actual disk-free bytes. States are
`READY`, `WARNING` at 80% of the shared ceiling, and `STOP_REQUIRED` when the
reserve cannot fit. It accepts only ceilings from 2 MiB through 512 MiB.
The preservation action is `PRESERVE_ALL_STOP_BEFORE_BOUND`.

`inspect_storage` opens an existing database with SQLite `mode=ro` and
`query_only`, never the migration-capable application connection. It reports
exact transactional counts and UTF-8 payload bytes per provider/capability,
including news, operational row counts, and table/index page allocation when
SQLite supports `dbstat`. Scans are bounded by VM steps, elapsed time and group
count; exceeding a limit reports a failure, never zero/partial counts. SQLite
readers can participate in shared-memory coordination. The tool does not issue
migrations, writes, checkpoint, expiry, vacuum or provider calls.
Database/WAL/free-disk measurements are separate non-atomic observations, so a
concurrent writer can change them after inspection. Use the pure helper for
frequent status, not full database scans.

`forecast` uses explicitly declared rates per target, physical bytes per record,
and maximum active seconds in any rolling 24 hours (`active_seconds_per_day`).
This is stronger than a per-calendar-date limit: a short window can cross
midnight. Declare continuous activity if the rolling bound is unknown.
It includes all updates and revisions,
additional shared-state growth and a default 25% growth margin. Partial-day
windows can contain a whole session: it uses the session upper bound rather than
a daily average that would understate a short window. It reports per-source/type
growth, shortfall, continuous peak growth and time to the bound at peak rate.
It never infers holidays, session alignment, entitlements or source eligibility.
An inactive model is `NO_ACTIVITY_MODELED`, not a sustainability guarantee.

## Operator dry run

From the application root, inspect an explicitly named existing store:

```powershell
python tools/market_data_capacity.py --database X:\explicit-state\imp-state.sqlite3
python tools/market_data_capacity.py --database X:\explicit-state\imp-state.sqlite3 --profile X:\profiles\selected.json --hours 12
```

Without `--database`, a profile forecast declares an empty store and does not
measure actual disk or existing shared state. The report labels that assumption.
Exit 0 means modeled fit/ready inspection; exit 2 means insufficient capacity,
capacity warning, or no activity modeled; exit 1 means blocked input/inspection.
Every result sets `activation_authorized=false`. A modeled fit grants no provider,
trading, deployment or collection authority. `--max-database-bytes` may lower the
shipped bound, never raise it.

Example profile, hypothetical counts only; no symbols are selected:

```json
{
  "name": "three-target-l1-synthetic-rth",
  "evidence_basis": "MEASURED_SYNTHETIC",
  "growth_margin": 1.25,
  "other_bytes_per_day": 1048576,
  "workloads": [{
    "source": "moomoo",
    "capability": "US_EQUITY_L1",
    "targets": 3,
    "records_per_second": 0.5,
    "bytes_per_record": 1600,
    "active_seconds_per_day": 23400
  }]
}
```

Evidence basis is the caller's declaration, explicitly unverified by the tool.
Only the documented fields are accepted; sampling/retention fields fail closed.
Raw trades/quotes/depth need measured source-specific rates and payload sizes.
For `CURRENT_BAR_1M`, the existing collector preserves changing current-bar
revisions; **one record per minute is a hypothetical rate, not completed-only
capture**. Size that profile for all revisions. News rates refer to immutable
record/revision arrivals, not polling attempts. Include checkpoints/gaps/runs and
all other shared growth, or conservatively declare them separately.

## Synthetic calibration, 2026-10-13

An isolated existing-writer benchmark based on `3578d5b08a809af6d957e6aa74a4c880b674564a`
stored 4,096 records per type, 28,672 total, with 64-record batches. There was no
network/provider supply. News used the schema's real insert/index path; it did
not benchmark a provider poller. Depth/book payloads had ten levels per side.

| Observation type | Payload B/record | Logical page/index growth B/record | CPU ms/record |
|---|---:|---:|---:|
| Equity ticks | 468 | 829 | 0.44 |
| Kraken trades | 495 | 827 | 0.41 |
| Equity L1 | 480 | 825 | 0.48 |
| Equity depth | 745 | 1,168 | 0.67 |
| Kraken book | 793 | 1,167 | 0.72 |
| Current-bar revisions | 566 | 961 | 0.47 |
| News | 835 | 1,083 | 0.08 |

Measured process working set was 28.4–29.1 MiB; cumulative process peak was
35.6–36.3 MiB. Traced Python peaks were 28–162 KB. These include tracing and
inspection overhead in one reused process, and exclude provider transports,
supervisor/child/UI overhead and larger real payloads. They cannot establish
total deployed memory use. At the measured 0.72 ms/record, 100 records/s would
consume about 7.2% of one CPU core; this is a linear model, not a concurrency
benchmark. Peak database plus WAL was 6.9–8.6 MiB during each 4,096-row trial.

These payloads are smaller than PF-01E's prior synthetic payloads (~926 B),
which measured ~1,446–1,568 database B/record. The planning table below therefore
uses **1,600 B/record**, 25% margin, 1 MiB/day of explicitly assumed other shared
growth, and an assumed 204 KiB initial database. About 503.8 MiB remains after
the 8 MiB reserve. No live rate or full-universe guarantee is established.

| Model | Targets | 12h growth MiB | 7d growth MiB | 30d growth MiB |
|---|---:|---:|---:|---:|
| L1, 0.5/s, at most 6.5h/day | 1 | 22.9 | 165.0 | 707.0 |
| Same | 3 | 67.6 | 477.4 | 2,045.9 |
| Same | 10 | 223.8 | 1,570.9 | 6,732.3 |
| Same | 20 | 446.9 | 3,133.0 | 13,427.1 |
| Trades, 5/s, continuous | 1 | 412.6 | 5,776.6 | 24,756.7 |
| Same | 3 | 1,236.6 | 17,312.2 | 74,195.2 |
| Same | 10 | 4,120.5 | 57,687.0 | 247,229.9 |
| Same | 20 | 8,240.4 | 115,365.2 | 494,422.3 |
| Bar model, 1/min, at most 6.5h/day | 1 | 1.4 | 14.0 | 59.8 |
| Same, excluding extra revisions | 3 | 2.9 | 24.4 | 104.4 |
| Same, excluding extra revisions | 10 | 8.1 | 60.8 | 260.7 |
| Same, excluding extra revisions | 20 | 15.5 | 112.9 | 483.8 |

The apparent 20-target L1 12h fit assumes no more than 6.5 active hours anywhere
in that window. At continuous activity, the same modeled selection grows about
824.6 MiB in 12h and reaches the reserve in about 7.3h. One continuous 5/s trade
target reaches it in about 14.7h; twenty reach it in about 44 minutes. A nearly
full profile must not be treated as adequate real acceptance headroom. Longer
sessions, bursts, greater depth and revisions can invalidate every modeled fit.
The evidence also includes 180 conservative forecasts across observation types,
one/three/ten/twenty targets and RTH/extended/continuous activity assumptions.
Session and entitlement validity remain separate prerequisites.

## Remaining operating decisions

Use an approved explicit capture granularity and source/target selection, obtain
rights, measure that workload, inspect actual shared state/free SSD space, and
require suitable headroom before activation. A workload that cannot fit must
remain blocked or stop before the bound while preserving accepted evidence.
There is no approved retention policy that makes high-volume raw capture
indefinite. Archive transitions, a larger ceiling, sampling or expiry must be
chosen and verified separately before they become operating policy.

See [PF-01 collection supervision](PF01_COLLECTION_SUPERVISION.md) for the
default-off activation and shutdown boundaries.
