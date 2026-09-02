# OF-01 Operational Runbook

| Field | Value |
|---|---|
| Document ID | `RUNBOOK-OF01` |
| Version | `1.0-draft` |
| Status | `NORMATIVE_RUNTIME_DRAFT` |
| Required authority | Ledger operator; elevated procedures identify stronger roles |

Use this runbook for diagnosis and lifecycle decisions. Use
[`SOPS.md`](SOPS.md) for controlled execution. Every investigation begins with
structured `OF01.OP.STATUS`; do not infer state from one log line or projection.

## First-response checklist

1. Stop issuing new commands when receipt, integrity, or authority identity is
   uncertain.
2. Capture status, UTC time, tool/source version, configured authority identity,
   latest commit ID/sequence, schema/profile versions, mode, readiness reasons,
   CAS status, projection cursors, and the triggering error code.
3. Preserve logs and files in place. Do not edit SQLite, hashes, CAS bytes, or
   projection cursors.
4. Classify the condition as `AUTHORITATIVE_FATAL`, `OPERATIONAL_DEGRADED`,
   `REBUILDABLE`, or `HOUSEKEEPING`.
5. Follow the matching section/SOP and verify the postcondition with structured
   evidence.

## Normal startup

Expected flow: `STOPPED -> STARTING -> READY` (or `DEGRADED` only for a declared
noncritical dependency). Startup proves configuration, local filesystem,
permissions, authority identity, schema/profiles, WAL/FULL/FKs, writer lock,
CAS publish/verify, and quick integrity. If any mandatory check fails, writes
remain disabled. Use `SOP-OF01-001`.

## Normal operation and health inspection

Inspect at least:

- liveness, readiness, mode, and readiness reason codes;
- authority/schema/profile identity and latest commit;
- queue depth/admission failures, commit latency/rate, SQLite busy count, DB and
  WAL size;
- CAS size/temp/orphan summary and last referenced-object verification;
- last successful integrity/backup and backup class/age; and
- each projection version, cursor, source high-water, lag, and last error.

Projection lag alone is degraded/rebuildable, not authority failure. A missing
referenced CAS object, hash mismatch, database integrity error, authority
identity mismatch, or unsupported schema is authority-blocking.

## Degraded operation

If readiness is true, only explicitly noncritical facilities may be degraded.
Capture the facility/error, confirm required record paths remain durable, and
operate under the owning policy. Never relabel an integrity or CAS-reference
failure as degraded merely to keep writes available.

## Maintenance mode

Enter maintenance for migration, restore activation, destructive CAS GC,
authority reidentification/clone activation, authority filesystem moves, and
full integrity unless a reviewed implementation proves online safety. Entry
closes admission and resolves active work. A maintenance lease is revision- and
authorization-bound. Use `SOP-OF01-006`; exit only through `SOP-OF01-007`.

## Normal shutdown and restart

Shutdown closes admission, drains or rejects queued work under the declared
policy, resolves the active command, checks ambiguous commit state, closes
readers/projectors, checkpoints only when safe, closes SQLite, and releases the
writer lock. On restart, run the complete startup gate; process existence is not
readiness. Use `SOP-OF01-002` then `SOP-OF01-001`.

## Symptom and response matrix

| Symptom | Diagnosis/evidence | Immediate action | Verification/escalation |
|---|---|---|---|
| Queue depth rising / backpressure | queue, latency, rate, busy counters | stop retry storms; reduce admissions; inspect writer | stable queue and receipts; capacity review if persistent |
| SQLite busy | writer lock owner, active operation, busy count | resolve receipts; bounded retry only | one writer; commits/latency recover |
| Second writer rejected | lock owner identity and startup evidence | keep second process stopped | confirm intended writer/custody; investigate duplicate launch |
| Network filesystem detected | path/filesystem identity | keep writes disabled | migrate by verified backup/restore to supported local storage |
| Disk pressure | DB/WAL/CAS/free-space trend | stop nonessential producers; create capacity | readiness and writes proven; preserve files |
| Disk full | active command/receipt, SQLite/CAS errors | close admission; no deletion guesswork; `SOP-OF01-015` | integrity quick/full as prescribed, command resolution |
| CAS temp accumulation | temp ages/owners; active command list | non-destructive scan; clean only proven abandoned temps | repeated scan stable; no referenced bytes affected |
| CAS orphan | orphan manifest at stable high-water | housekeeping/quarantine; no immediate deletion | authorized GC only if retention/backup safe |
| Referenced CAS missing/mismatch | exact artifact/content/commit IDs | integrity block; preserve evidence | verified byte restore then full integrity |
| Projection lag | source high-water/cursor/error | keep authority running; pause/resume/replay | cursor advances idempotently |
| Projection stale/corrupt | sampled record/hash/version comparison | mark rebuild required | full rebuild matches source high-water |
| Backup failed | operation ID, partial destination, missing coverage | do not publish verified manifest/prune prior backup | rerun after cause; verify manifest |
| Backup old | policy-owned age state | schedule authorized backup | state becomes `VERIFIED`; restore-test separately |
| Schema newer/unsupported | DB version and runtime supported set | keep writes disabled | deploy compatible runtime or governed restore/migration |
| Migration failed | source/destination, backup ID, step evidence | remain maintenance/write-disabled | declared rollback/restore, then full verification |
| Integrity/hash/FK failure | full finding IDs and affected identities | `SOP-OF01-014`; no auto-repair | recovery operator decision; full restore verify |
| Writer crash loop | startup gates, lock, last command/commit | keep admission closed; capture each stable error once | resolve root cause, not repeated blind restarts |
| Permission failure | sanitized path identity, OS code, service identity | keep writes disabled; restore least required permission | startup write/publish verification passes |

## SQLite busy conditions

`SQLITE_BUSY` is transient only when authority integrity and one-writer custody
are proven. Record command ID/hash before retry, query receipt after any commit-
boundary ambiguity, use bounded backoff, and stop when the configured retry
budget is exhausted. Persistent busy with another process is a custody issue;
never add an independent writer or weaken durability.

## CAS pressure and garbage collection

Space recovery order is: stop unnecessary producers; inspect growth; protect
active temps; take stable high-water orphan scan; apply retention/backup/
quarantine holds; generate dry-run manifest; obtain explicit authorization;
execute manifest-bound GC; rescan and verify. Never delete by age, filename, or
operator intuition. Referenced bytes are never GC candidates.

## Projection operations

Pause preserves cursor. Resume validates projection name/version/source
authority and last applied commit before consumption. Cursor advances only
after durable apply. Invalid cursor, wrong authority, unsupported projection
version, or content divergence requires rebuild. Rebuild initializes an empty
target and replays authority; it never modifies SQLite history.

## Backup state

`UNVERIFIED` means bytes may exist but recovery is unproven. `VERIFIED` means
snapshot, manifest, high-water, and CAS coverage passed. `RESTORE_TESTED` means
a controlled restore drill also proved identity, hashes, CAS, projection
rebuild, and writer readiness. Never report a higher class without its evidence.

## Integrity failure and corruption

Authoritative structural, FK, uniqueness, membership, schema/profile, record
hash, commit hash, or referenced-CAS defects are fatal. The runtime moves to
`INTEGRITY_BLOCKED`. Preserve original DB/WAL/SHM/CAS and logs, capture a
read-only forensic report, identify the last verified backup and high-water,
and hand off. Do not run update/delete, recompute stored hashes, delete bad rows,
or copy a live DB folder over the evidence.

## Disaster recovery

Recovery is not failover. Select a verified backup under custody, stop the
authority, validate the candidate offline, restore SQLite/CAS, prove authority
identity and high-water, run full restore integrity, explicitly activate one
lineage, start and prove readiness, rebuild projections, and retain the exercise
evidence. If two restored copies accepted writes, stop both and escalate; merge
is unsupported.

## Incident handoff

Preserve before destructive remediation:

```text
operation/incident reference; UTC timeline; initiator/role; source/tool version;
ledger_authority_id; schema/profile versions; latest verified commit and command;
affected record/artifact/content IDs; sanitized path identities; configuration identity;
mode/readiness; integrity findings; projection cursor; backup/restore IDs;
logs and OS/storage error codes; actions already attempted and their results
```

Objective technical condition classes are used; OF-01 does not invent
organization-wide severity levels. OF-03 may later register the handoff.

## Escalation boundaries

Escalate immediately to a recovery operator for authoritative fatal findings,
failed restore verification, suspected divergent authority, or loss of custody.
Escalate to a maintenance operator for persistent storage/permission problems,
migration failure, or destructive CAS work. Projection-only failures go to the
projection operator. No role may grant itself authority because an incident is
urgent.
