# PF-01G release candidate, stop deadline and operational preflight

Prepared 2026-10-13 on top of PF-01F `512d0fac1aca461811ea64821959916e63a528d2`.
Nothing here has been deployed, no canonical store has been migrated and no
provider has been contacted. Every activation step remains an operator
decision. Deployment, rollback and the acceptance window are described in
[PF01F_DEPLOYMENT_ACCEPTANCE.md](PF01F_DEPLOYMENT_ACCEPTANCE.md); this document
records what PF-01G changed and adds the preflight and readiness profiles.

## Stop deadline

The supervisor used to wait a fixed 15 seconds for a child whose own bounded
stop stages add up to far more, so a slow but correct drain was terminated and
recorded as unverified. The supervisor's wait is now derived from the child's
stage constants instead of being a separate number:

| Stage (in stop order) | Bound |
|---|---:|
| Supply reconcile-thread join | 10 s |
| Stalled-reconcile lock wait (only when that join timed out) | 0.25 s |
| OpenD feed: connection join 5 s, processor drain 5 s and join 6 s | 11 s |
| Kraken: receiver join 5 s, unsubscribe drain 5 s | 10 s |
| News worker join | 10 s |
| Market writer: worker join 5 s, final drain 5 s | 10 s |
| Margin for the stages' own bookkeeping | 8 s |
| **Supervisor wait (`child_stop_bound_seconds`)** | **59.25 s** |

The wait is the sum of the stage bounds plus the margin, not a measured
worst case: a stage that overruns its own bound is reported incomplete by the
child, and a child still running at 59.25 s is terminated and given 5 more
seconds. The total stays below the 120-second supervision lease, so a single
stop normally completes while the supervisor still owns the lease; the lease
is not renewed during the stop wait. A contract test fails if any stage
constant changes without the sum following it. No stage bound was raised; three defects that
made the real stop longer or less truthful than its stated bounds were removed:

- A second stop of an OpenD feed whose first stop was incomplete waited the
  full bound again and recorded a second gap. It now returns at once.
- A supply stop whose reconcile thread was stalled waited for that thread's
  lock without limit. It now gives up after 0.25 s, records
  `SUPPLY_SHUTDOWN_INCOMPLETE` and a gap, and leaves the provider tail unknown.
- A stop during an OpenD reconnect backoff slept the whole backoff.

The stop result is still classified, never assumed: a clean stop is
`OPERATOR_STOP` and exit 0; a child that was terminated, exited non-zero, left
no exit code or whose handle failed is `OPERATOR_STOP_CHILD_EXIT_UNVERIFIED`,
and the supervisor CLI now exits 1 for it. The lease is released either way.
Exit 0 from the child is a verified drain of every worker: a news worker still
running after its join now ends the child with `COLLECTION_SHUTDOWN_INCOMPLETE`
instead of exit 0, as an incomplete supply or writer drain already did.

A Ctrl-C that arrives while the supervisor is already stopping a child inside
its own loop (a storage outage or a latched block) no longer loses that child:
the interrupted stop is recorded as `CHILD_STOP_EXIT_GAP_UNVERIFIED`, the
handle is kept, and the operator stop that follows finishes it. Only a child
then seen to exit 0 is reported as `OPERATOR_STOP`.

Known limits. A second Ctrl-C during the operator stop wait abandons the stop:
the lease is then left to expire and the run reads as an abrupt end. A Kraken connect
attempt in progress at stop can hold its receiver for the 10-second connect
timeout, longer than the 5-second join, and is then reported incomplete, not
clean. A Kraken channel whose subscribe was never acknowledged is now
unsubscribed and drained like an acknowledged one. Supply status is read by
path and cannot tell that a store file was replaced while no child ran.

## Shared-connection read defect

The intermittent failure of the real-process supervision test was a product
defect. `LocalStateConnection.execute` returns a cursor after releasing the
connection lock, so `execute(...).fetchone()` steps the shared SQLite
connection outside the lock. When that happened while another thread's
`BEGIN IMMEDIATE` was failing on a held write lock, the failing statement's
result code was overwritten: the news worker saw `OperationalError: not an
error` (code 0), classified it as unrecoverable, and the child exited. In a
direct reproduction the same race also produced a `BEGIN IMMEDIATE` that
reported success without starting a transaction.

Corrections: `fetchone`/`fetchall` helpers fetch inside the lock and are used by
the collection child's status and lease reads; a transaction that did not start
raises instead of running its body in autocommit; and a storage error whose
code was lost is retried within the existing bounded retry rather than treated
as corruption. Other callers of `execute(...).fetchone()` on a connection
shared between threads have the same exposure and were not changed in this
sprint; inside a `transaction()` block or under the connection lock the pattern
is safe.

## Operational preflight

```
python tools/platform/pf01_supervisor.py --preflight
```

Run it in the collector's own clean environment (never the serving launcher's).
It reads the environment, opens the existing store read-only and reads the
existing capability-report file. It opens no provider connection, takes no
lease or write lock, migrates nothing and starts nothing. The read-only open
takes SQLite's ordinary shared read lock for the length of each query and, on
a WAL store with no reader open, may create the `-shm` sidecar (and an empty
`-wal`); the store file itself is not written.

UNKNOWN means a fact the tool should have read but could not. NOT VERIFIED
means only the operator's own evidence can settle it. Exit codes: 0 every check
READY, 1 any BLOCKED, 2 any UNKNOWN, 3 only NOT VERIFIED items remain. Because
provider access and data rights are never READY, the best result for an enabled
collector is NOT VERIFIED (exit 3): a list for the operator to sign off, not a
go signal.

| Check | READY means | Otherwise |
|---|---|---|
| `build_identity` | every file hash in the manifest named by `IMP_PF01_RELEASE_MANIFEST` matches this source tree | NOT VERIFIED without a manifest, BLOCKED on any difference |
| `execution_gates` | no Paper, broker or Live execution gate is set | BLOCKED |
| `supervision_gate`, `collection_mode` | supervision on, durable state, a collector enabled, no replay | BLOCKED with the refusal the supervisor would give |
| `storage` | explicit absolute state directory holding an existing store; the volume serial is reported for the operator to compare | BLOCKED; nothing is created |
| `schema` | store is at the current schema | BLOCKED `APPROVED_SCHEMA_MIGRATION_REQUIRED`; UNKNOWN if unreadable |
| `capacity` | DB+WAL and free disk leave room under the 512 MiB bound | NOT VERIFIED at the warning level, BLOCKED at the stop level |
| `supervisor_owner`, `market_writer_owner` | no unexpired owner and no latched block | BLOCKED |
| `news_jobs`, `market_targets` | the configured selection parses | BLOCKED with the configuration refusal |
| `news_provider_access` | never | NOT VERIFIED: no news provider is contacted, and keys and terms are not judged |
| `market_persistence` | stored sources are within moomoo/kraken and 1 to 20 symbols are named | BLOCKED `MARKET_CAPTURE_TARGETS_INVALID`, the refusal the child would give |
| `data_rights` | never: an operator attestation cannot be checked by a tool | NOT VERIFIED when attested, BLOCKED when not |
| `moomoo_entitlement` | never: the recorded report is not re-checked | NOT VERIFIED when the report is current and entitled; BLOCKED when missing, stale or not entitled |
| `provider_connectivity` | never | NOT VERIFIED: no provider is contacted |
| `collection_schedule` | the session calendar covers today; each source's current session is listed | UNKNOWN when the calendar does not cover the date. A closed market is reported, not blocked |

The report's `not_inspected` list names what is outside the tool by design and
is not part of the overall state: host power and sleep policy, provider account
and subscription quota, and provider terms for local archival.

A preflight with an enabled collector therefore cannot be READY overall. That is
intended: an open port, a configured key or a current report is not proof of
entitlement, and the existing moomoo probe that would re-check it subscribes
and requests history, so it is not run from here. The preflight does not model
growth; use `tools/market_data_capacity.py` with the selected profile.

## Capacity readiness profiles

Modelled with the existing offline tool on an empty store, 25% margin, 1 MiB
per day of other growth, 1,600 B per trade/L1/bar/news record and 2,300 B per
ten-level depth/book record. Rates are planning assumptions, not measured live
rates, and no symbol is chosen. "Fits" means the modelled growth stays under
the 512 MiB bound less its 8 MiB reserve; it is not operational qualification.

| Profile | 8 h | 12 h | 3 d | 7 d | Hours to bound at continuous peak |
|---|---|---|---|---|---:|
| Small: 3 L1 at 0.5/s in regular hours, news | 68 MiB, fits | 68 MiB, fits | 210 MiB, fits | 489 MiB, fits | 48.4 |
| Moderate: 10 L1, 2 crypto trade pairs at 1/s, news | 334 MiB, fits | 389 MiB, fits | 1,667 MiB, no | 3,890 MiB, no | 10.5 |
| 20 L1 at 0.5/s in regular hours, news | 447 MiB, fits | 448 MiB, fits | 1,348 MiB, no | 3,145 MiB, no | 7.3 |
| Trades and quotes: 5 targets, ticks 2/s, L1 0.5/s | 558 MiB, no | 559 MiB, no | 1,677 MiB, no | 3,914 MiB, no | 5.9 |
| Trades, quotes and depth: 3 targets, depth 2/s | 720 MiB, no | 720 MiB, no | 2,163 MiB, no | 5,047 MiB, no | 4.5 |
| Bar-oriented: 20 targets, one revision per minute | 15 MiB, fits | 16 MiB, fits | 48 MiB, fits | 113 MiB, fits | 215.3 |
| Overnight crypto: 2 pairs, trades 1/s, book 5/s, news | 901 MiB, no | 1,351 MiB, no | 8,104 MiB, no | 18,910 MiB, no | 4.5 |

Reading the table: under the shipped bound only the small profile lasts a week,
the 20-target L1 profile fills in under two regular sessions, and any raw
trade, depth or continuous crypto book profile needs a shorter window, fewer
targets, a measured lower rate, or a separately approved storage design. The
8-hour and 12-hour L1 figures are equal because at most one 6.5-hour regular
session is assumed in either window. The bar profile is hypothetical: headless
supply does not offer a bar-only capability, and the existing collector stores
every changed revision. The bound is not raised, nothing is deleted, and
retention stays preserve-all-then-stop.

## Provider prerequisites

None of these is established by this sprint. Each needs the owner's evidence
before the matching source is enabled.

- moomoo/OpenD: OpenD running and logged in under the owner's account; the
  account's quote rights for each requested capability (L1, ticks, depth) and
  market; subscription quota sufficient for the target count; a current
  capability report produced by an owner-authorised probe run; the provider's
  terms permitting local archival of the captured data.
- Kraken: public WebSocket market data, no account; the venue's terms
  permitting local archival; canonical instrument identifiers for each pair.
- News: for each enabled provider, the key or feed access it needs, its rate
  limits, and its terms for storing headlines and metadata.
- All sources: the source listed in `IMP_MARKET_SUPPLY_ENTITLED_SOURCES` only
  after the owner has confirmed the right to collect and keep that data.

## Attended acceptance sequence

1. Deploy the approved release and migrate the approved store by the PF-01F
   procedure, with the serving application's own configuration unchanged.
2. Fill a copy of [PF01F_ACCEPTANCE.env.example](PF01F_ACCEPTANCE.env.example)
   with the owner's sources, targets, rights and state directory. Keep every
   execution gate at 0.
3. Forecast the chosen profile for the window with
   `tools/market_data_capacity.py --database <store> --profile <file> --hours <n>`.
4. Run `--preflight`. Resolve every BLOCKED and UNKNOWN check. Review each
   NOT VERIFIED check and each `not_inspected` item against the owner's own
   evidence and record the decision.
5. Start `pf01_supervisor.py --run` in a dedicated attended terminal. Watch
   `--status` from a second terminal.
6. Stop with one Ctrl-C and wait up to about 65 seconds. Exit 0 with
   `OPERATOR_STOP` is a verified drain; exit 1 is an unverified one and the
   recorded reason and gaps say what is unknown.
7. Preserve the evidence listed in the PF-01F document before any further run.

No scheduled task or service is registered by any of these steps.
