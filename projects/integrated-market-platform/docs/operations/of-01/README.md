# OF-01 Ledger Operations

| Field | Value |
|---|---|
| Document ID | `OPS-OF01-README` |
| Version | `1.0-draft` |
| Status | `NORMATIVE_RUNTIME_DRAFT` |
| System | `IMP-OF-01` |
| Consequence | Authority-supporting subsystem operations |
| Runtime availability | `NOT_IMPLEMENTED` |
| Controlling specification | [OF-01 implementation specification](../../superpowers/specs/2026-08-28-imp-of-01-universal-run-artifact-ledger-implementation-spec.md) |

This pack defines how humans and automation will operate the OF-01 ledger. It
is normative for runtime implementation but does not pretend that unimplemented
commands exist. Procedures refer to stable capability IDs such as
`OF01.OP.STATUS`; implementation acceptance MUST bind each ID to an actual
typed API/CLI command and test the documentation against it.

This draft is executable-quality at the capability/decision level, not an
instruction to invent commands before runtime exists. Until Task 14 binds real
syntax and tests it, no operator may translate a capability ID into guessed
shell/API usage or claim a procedure was exercised.

## Document ownership and precedence

1. The controlling implementation specification owns invariants, schemas,
   DDL, typed interfaces, capability/result contracts, roles, and acceptance.
2. `SOPS.md` owns controlled procedure order, authorization, verification,
   recovery, and evidence.
3. `WORKFLOWS.md` owns actor/system orchestration and transaction boundaries and
   refers to SOPs for controlled operations.
4. `RUNBOOK.md` owns symptom diagnosis, classification, and routing; it does not
   override an SOP.
5. `AGENT_OPERATING_RULES.md` narrows automation behavior and never widens a
   role or capability.

When these files disagree, stop and correct the lower owner against the higher
one before acting. Repeated summaries are navigation aids, not new definitions.

## System purpose and authority boundary

OF-01 records immutable run, attempt, outcome, disposition, relationship,
attribution, provenance, and artifact metadata in SQLite and artifact bytes in
a local content-addressed store. One runtime writer is the only ordinary
authoritative mutation path:

```text
typed command -> AuthoritativeLedgerWriter -> one SQLite transaction
```

Mongo and current-state views are derived. Direct authoritative SQL mutation,
history deletion, hash replacement, projection-to-authority writes, and
automatic destructive repair are prohibited.

## Supported deployment

- one SQLite authority and one CAS root on supported local filesystems;
- one active writer process protected by an OS lock;
- local read connections and asynchronous projection consumers; and
- explicit backup/restore custody and activation.

Unsupported: SMB/NFS/network-share SQLite, multiple primaries, automatic
failover, divergent-history merge, and unattended destructive recovery.

## Data locations

The implementation configuration MUST expose system-resolved absolute
identities for the SQLite database, CAS root, lock, backup destination, and
operational evidence root through `OF01.OP.STATUS`. Callers never choose CAS
object paths. Paths and credentials MUST NOT be copied into public incident
channels; use sanitized path identity plus restricted evidence references.

## Health model

| Dimension | Meaning |
|---|---|
| Liveness | Status surface responds. |
| Readiness | Authoritative commands may be admitted safely. |
| Degraded | A noncritical facility such as projection is impaired. |
| Integrity blocked | Authority cannot safely accept writes. |

Modes: `STOPPED`, `STARTING`, `READY`, `DEGRADED`, `MAINTENANCE`,
`WRITE_DISABLED`, `INTEGRITY_BLOCKED`, `SHUTTING_DOWN`.

`OF01.OP.STATUS` returns the specification's `StatusV1`: observation time,
runtime revision/process instance, mode/liveness/readiness and sorted reason
codes, authority/schema/profiles, writer lock/queue/active command, latest
commit, integrity, CAS, backup, and projection summaries. Consequential actors
refresh it immediately before compare-and-act; no fixed freshness duration is
invented.

## Roles

| Role | Ordinary authority |
|---|---|
| Ledger runtime | Execute validated typed command transactions only. |
| Ledger operator | Inspect and submit granted typed commands. |
| Maintenance operator | Maintenance, full checks, migration, CAS controls with authorization. |
| Backup/recovery operator | Backup, restore validation, explicit activation and custody. |
| Projection operator | Pause, resume, replay, and rebuild derived projections. |
| Read-only analyst | Typed reads and approved controlled SQL reads. |
| Developer/test operator | Disposable authorities only. |
| Automation/AI agent | Granted typed reads/commands; no self-escalation or autonomous destruction. |

The detailed authority matrix is canonical in the implementation
specification. This pack never grants a role omitted there.

Operational authority does not grant broker, risk, live-session, order,
qualification, model-promotion, or EVIDENCE authority.

## Lifecycle entry points

| Need | Start here | Capability |
|---|---|---|
| Start | [SOP-OF01-001](SOPS.md#sop-of01-001--startup) | startup service + `OF01.OP.STATUS` |
| Stop | [SOP-OF01-002](SOPS.md#sop-of01-002--graceful-shutdown) | `OF01.OP.SHUTDOWN` |
| Inspect | [Runbook](RUNBOOK.md#normal-operation-and-health-inspection) | `OF01.OP.STATUS` |
| Integrity | [SOP-OF01-003](SOPS.md#sop-of01-003--integrity-check) | integrity capabilities |
| Backup | [SOP-OF01-004](SOPS.md#sop-of01-004--verified-backup) | backup capabilities |
| Restore | [SOP-OF01-005](SOPS.md#sop-of01-005--restore-and-activation) | restore capabilities |
| Incident | [Runbook incident handoff](RUNBOOK.md#incident-handoff) | status + forensic integrity |
| Projection | [Projection procedures](SOPS.md#sop-of01-010--projection-rebuild) | projection capabilities |
| CAS | [CAS procedures](SOPS.md#sop-of01-008--cas-orphan-scan) | CAS capabilities |
| Migration/upgrade | [Migration SOP](SOPS.md#sop-of01-012--schema-migration) | migration capabilities |

## SOP index

1. `SOP-OF01-001` Startup
2. `SOP-OF01-002` Graceful shutdown
3. `SOP-OF01-003` Integrity check
4. `SOP-OF01-004` Verified backup
5. `SOP-OF01-005` Restore and activation
6. `SOP-OF01-006` Enter maintenance mode
7. `SOP-OF01-007` Exit maintenance mode
8. `SOP-OF01-008` CAS orphan scan
9. `SOP-OF01-009` CAS garbage collection
10. `SOP-OF01-010` Projection rebuild
11. `SOP-OF01-011` Projection resume
12. `SOP-OF01-012` Schema migration
13. `SOP-OF01-013` Ambiguous command resolution
14. `SOP-OF01-014` Corruption response
15. `SOP-OF01-015` Disk-full/storage-failure response
16. `SOP-OF01-016` Authority clone/development fork
17. `SOP-OF01-017` Disaster-recovery exercise
18. `SOP-OF01-018` Release/upgrade

## Workflow index

`WORKFLOWS.md` defines `WF-OF01-001` through `WF-OF01-018` for domain command
flows, projection/integrity/recovery operations, CAS GC, shutdown, and unexpected
termination recovery. Workflows describe actor/system orchestration; SOPs
describe controlled operator procedures.

## Agent rules

All automated and AI callers MUST read
[`AGENT_OPERATING_RULES.md`](AGENT_OPERATING_RULES.md) before consequential
maintenance. Core rules are typed interfaces only, stable retry identity,
receipt-backed success, evidence preservation, no hidden repair, no secrets, no
projection-as-truth, no authority escalation, and no autonomous destruction.

## Operational evidence

Consequential procedures preserve an operation ID, initiator and role,
authorization reference, tool/source version, ledger authority, safe input
identities, start/end times, result code, verification, and evidence location.
An operational log is not automatically a domain record. OF-03 may later
register these static IDs and evidence references without changing OF-01.
