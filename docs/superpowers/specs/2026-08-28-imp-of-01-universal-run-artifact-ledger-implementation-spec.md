# IMP-OF-01 Universal Append-Only Run and Artifact Ledger — Implementation Specification

| Field | Value |
|---|---|
| Document ID | `IMP-OF-01-SPEC` |
| Classification | `ACTIVE_SUPPORTING` |
| Truth class | `APPROVED_FUTURE_DESIGN` |
| Review state | `APPROVED_FOR_IMPLEMENTATION` |
| Version | `1.0` |
| Last verified | `2026-08-28` |
| Establishing milestone | `IMP-OF-01 written-spec and operational-hardening review` |
| Design baseline | `0f922645fc26dd7c91ed4c501aa475f1a4bd8ea6` |
| Approved standards baseline | `f4a66becb25a947d3ac789fa16c3af5539d927d5` |
| Runtime implementation | `NOT_STARTED` |

This document is the controlling implementation authority for IMP-OF-01. The
accepted design remains preserved as design history. This specification does
not claim that the described modules, database, CLI, CAS, or projections exist
yet. Runtime implementation may not silently change Invariants 1–75.

## Purpose and authority

OF-01 will provide one local, append-preserving authority for consequential IMP
runs, attempts, transitions, outcomes, dispositions, relationships,
attribution, provenance, artifacts, commands, and commit order. It will also
provide the subsystem-specific controls required to start, stop, inspect,
maintain, back up, restore, migrate, and recover that authority safely.

Authority is narrow:

```text
authoritative records       SQLite WAL on a supported local filesystem
ordinary mutation path      typed command -> AuthoritativeLedgerWriter
write topology              one logical writer, one active process
artifact bytes              immutable local content-addressed store (CAS)
transaction/order envelope  ledger_commits + ledger_commit_items
current state               derived and rebuildable
Mongo                       optional non-authoritative projection
multi-host writers          unsupported in v1
```

OF-01 does not decide domain truth, evidence admission, model promotion, risk,
broker, order, or live-session authority. It does not implement OF-03's global
workflow, SOP, capability, incident, problem, or debt registries.

## Baseline and precedence

Use this precedence when sources conflict:

1. current executable repository truth;
2. accepted canonical `docs/platform/` standards at REBASE-02;
3. this implementation specification;
4. the accepted OF-01 design;
5. review prompts and commentary.

The review worktree began at `0f922645fc26dd7c91ed4c501aa475f1a4bd8ea6`
on branch `docs/imp-of-01-spec-review`. The original dirty checkout and every
pre-existing worktree are outside this change surface.

## Scope

Runtime implementation includes:

- versioned immutable Python command and record contracts;
- deterministic identifiers, canonicalization, and golden hashes;
- SQLite schema, ordered migrations, writer process lock, serialized command
  admission, command receipts, commit journal, and typed readers;
- run/attempt lifecycle, outcomes, dispositions, artifacts, relationships,
  source attribution, and provenance;
- durable local CAS publication and verification;
- integrity, backup, restore, activation, migration, maintenance, and health;
- rebuildable current-state and Mongo projection contracts;
- structured operator interfaces and stable error codes;
- fault injection, operational drills, documentation conformance, and
  acceptance evidence; and
- the subsystem operations pack at `docs/operations/of-01/`.

## Out of scope

OF-01 v1 MUST NOT implement multiple authoritative writers, network-share
SQLite, consensus, automatic failover, PostgreSQL migration, divergent-history
merge, an event-sourcing JSON payload store, a durable job queue, provider or
broker side effects inside transactions, authoritative-history purge, secret
capture, EVIDENCE retrofit, ADAPT-specific records, or a platform-wide
workflow/SOP registry.

## Normative language

`MUST`, `MUST NOT`, `SHOULD`, `SHOULD NOT`, and `MAY` are normative. Every
runtime error, status result, and operator result MUST expose a stable code and
structured data; free-form prose is supplementary.

## Invariants 1–75

The following table preserves all accepted design invariants and adds the
operational invariants approved by this review. The short statements are
normative; later sections provide their exact realization.

| No. | Normative invariant | Realization |
|---:|---|---|
| 1 | One accepted writer command creates at most one authoritative commit. | Receipt uniqueness and writer transaction |
| 2 | One commit is exactly one SQLite transaction. | `BEGIN IMMEDIATE` through `COMMIT` |
| 3 | A commit contains one or more typed immutable records. | Command plan and manifest |
| 4 | Every domain record belongs to exactly one commit. | Composite item foreign key plus integrity reverse check |
| 5 | Every commit has a deterministic ordered record manifest. | Item ordinal contract |
| 6 | Commit sequence means local persistence order only. | Reader and projection contracts |
| 7 | Domain clocks remain distinct from ledger order. | Integer-nanosecond semantic fields |
| 8 | Typed relational tables carry canonical domain content. | No generic payload authority |
| 9 | The journal carries transaction, receipt, order, and integrity lineage only. | No duplicate domain JSON |
| 10 | Current state is derived and rebuildable. | Views/query logic/projections |
| 11 | Artifact bytes live outside SQLite. | Local CAS |
| 12 | Artifact metadata and references commit atomically. | Typed command transaction |
| 13 | Mongo and external views are replayable projections. | One-way commit stream |
| 14 | Idempotent retry cannot duplicate history. | Same command ID/hash returns receipt |
| 15 | Authoritative history is never silently rewritten. | No public update/delete path |
| 16 | Physical row identifiers are not domain identities. | `WITHOUT ROWID` where useful; UUID text identities |
| 17 | Multi-host authoritative writers are outside v1. | Startup topology check and custody rule |
| 18 | Caller-stable command ID and hash determine retry/conflict behavior. | Authority-scoped command uniqueness |
| 19 | `ledger_commits` is the sole durable command receipt. | Failures before commit are telemetry only |
| 20 | Callers allocate new domain IDs before submission. | Command validation and hashing |
| 21 | Record hash covers type, version, ID, and all semantic fields. | Record canonical profile |
| 22 | Command, record, and commit hashing is versioned and deterministic. | Profile registry and vectors |
| 23 | Commit items bind ordinal, record identity/schema/profile, and hash. | DDL and commit builder |
| 24 | Commit hash covers envelope and ordered manifest; no prior-hash chain exists. | Commit vector |
| 25 | Authority scopes commands; writer allocates commit ID, sequence, and time. | Singleton metadata and transaction allocator |
| 26 | Lifecycle or interpretation changes append new typed records. | Immutable tables |
| 27 | Run/attempt definitions are separate from transition history; closed is terminal. | State machines |
| 28 | State-dependent preconditions are rechecked in the transaction. | Command executor |
| 29 | One logical writer serializes local producers. | Bounded queue and OS process lock |
| 30 | SQLite uses WAL, FULL sync, foreign keys, busy timeout, integrity checks, and local storage. | Connection profile |
| 31 | CAS content is durably published and verified before reference. | Publish-before-transaction |
| 32 | Referenced CAS loss/mismatch is fatal; an orphan is housekeeping. | Integrity classification |
| 33 | Schema and hash interpretation are explicit and fail closed. | Migration/profile registries |
| 34 | Only typed versioned semantic commands reach authority. | Public API boundary |
| 35 | Ambiguous commit status is resolved by receipt lookup before retry. | Resolution workflow |
| 36 | External side effects never run inside ledger transactions. | Dependency boundary tests |
| 37 | Projections consume commit sequence then item ordinal. | Stream contract |
| 38 | Mongo preserves source lineage and has no reverse authority path. | Projection schema |
| 39 | Run state, disposition, attempt summary, and artifact inventory are read models. | Typed query service |
| 40 | Integrity checks detect and report; they never rewrite semantic history. | Read-only checker |
| 41 | Backup binds consistent DB snapshot, authority, high-water mark, schema, CAS coverage, and hashes. | Verified manifest |
| 42 | v1 has no history TTL/purge; CAS GC deletes only proven-unreferenced content. | GC authorization and holds |
| 43 | Secrets are rejected before durable write and paths are system-derived. | Schema/redaction gate |
| 44 | One writer `recorded_at_ns` belongs to each commit; wall-clock regression does not affect order. | Envelope contract |
| 45 | Relationships, corrections, and supersessions are explicit typed immutable records. | Endpoint and graph validation |
| 46 | Replay uses bounded ordered commit ranges. | `stream_commits` |
| 47 | Submission queues are bounded and ephemeral; shutdown drains/rejects cleanly. | Runtime lifecycle |
| 48 | Fault injection covers command, CAS, transaction, response, restart, integrity, projection, migration, and recovery. | Acceptance plan |
| 49 | Capacity is measured without invented SLA. | Metrics and benchmark report |
| 50 | Distributed authority requires a separately governed topology migration. | Known limitation and trigger |
| 51 | Operability, recovery, procedures, agent rules, fault handling, and evidence are part of completeness. | Operations acceptance gate |
| 52 | OF-01 owns only ledger-subsystem procedures; OF-03 later registers/generalizes them. | Static IDs and metadata only |
| 53 | All normal mutations use typed command -> writer -> SQLite transaction. | Permission and API tests |
| 54 | Routine direct DB access is read-only; mutation is break-glass only. | Role matrix and incident procedure |
| 55 | Startup validates all mandatory authority prerequisites and fails closed. | Startup workflow |
| 56 | Shutdown closes admission, resolves active work, and leaves complete commit or rollback. | Shutdown state machine |
| 57 | Liveness, readiness, degradation, and integrity failure are distinct. | Health model |
| 58 | Quiescent operations use explicit maintenance mode. | Maintenance lease/state |
| 59 | Backup is a verified SOP, not a file copy. | SOP-OF01-004 |
| 60 | Restore preserves authority and is fully validated before activation. | SOP-OF01-005 |
| 61 | Recovery is verified restore/resume, not automatic failover. | DR workflow |
| 62 | Quick, full, restore, backup, and forensic integrity checks have procedures and classes. | Checker modes |
| 63 | Corruption disables writes, preserves evidence, and is never silently repaired. | Integrity block |
| 64 | CAS health, temp/orphan handling, verification, GC, backup, and restore have procedures. | CAS operations |
| 65 | Projection start/pause/resume/replay/rebuild/version upgrade is operationally defined. | Projection operations |
| 66 | Migration requires source/destination compatibility, backup, quiescence, validation, and recovery plan. | Migration SOP |
| 67 | Runtime, operator, maintenance, recovery, projection, analyst, developer, automation, and AI roles are explicit. | Authority matrix |
| 68 | AI/automation receives least authority and typed interfaces only. | Agent rules and negative tests |
| 69 | Automated callers preserve command/domain IDs and semantic content across retry. | Retry rule tests |
| 70 | Operational success claims require corresponding evidence. | Structured result contracts |
| 71 | Every workflow defines preconditions, steps, evidence, success/failure, retry, and recovery. | Workflow template |
| 72 | Incident handoff preserves logs, identities, paths, configuration, versions, and times before remediation. | Corruption/runbook procedures |
| 73 | Destructive maintenance requires explicit consequence-appropriate authorization. | Confirmation token and role checks |
| 74 | Operational metrics have stable names/semantics before thresholds. | Observability contract |
| 75 | Procedures must be exercised in a controlled environment before runtime acceptance. | Operational acceptance suite |

## Package architecture

Runtime code MUST use this focused package unless a later reviewed plan proves a
lossless repository-conventional mapping:

```text
src/market_platform_foundation/of01/
  __init__.py                 public types only
  ids.py                      UUID validation/allocation
  canonical.py                profile registry and strict canonical bytes
  errors.py                   stable runtime/operation codes
  commands.py                 immutable typed command envelopes
  records.py                  immutable domain record schemas
  protocols.py                backend-independent writer/read/CAS protocols
  state_machine.py            run/attempt and relationship validation
  sqlite_schema.py            DDL v1 constants only
  migrations.py               ordered physical migrations
  sqlite_store.py             connections and typed persistence internals
  writer.py                   process lock, queue, transaction coordinator
  readers.py                  typed queries and commit stream
  cas.py                      local immutable CAS
  integrity.py                read-only quick/full/forensic checks
  backup.py                   snapshot/manifest/verification
  restore.py                  validation and activation preparation
  maintenance.py              service modes and authorization leases
  projections.py              projection cursor/source contracts
  health.py                   liveness/readiness/status model
  operations.py               operation capability service
  cli.py                      structured operator adapter
tests/of01/                   isolated authority tests
```

Domain packages MUST depend on `commands.py`, `records.py`, or `protocols.py`,
never on `sqlite3`, physical CAS paths, Mongo types, or maintenance internals.

## Identity and encoding

All authority, command, domain, content-independent record, and commit IDs are
lowercase canonical RFC 4122 UUID strings (`8-4-4-4-12`, 36 ASCII characters).
New caller/writer IDs use UUIDv4. Imported deterministic identities MAY use
UUIDv5 only when the owning adapter declares its namespace and retrospective
qualifier. Parsers reject braces, uppercase, compact hex, nil UUID, whitespace,
and noncanonical spellings. UUID lexical or version order has no semantics.

Hashes use `imp-sha256-uppercase-hex-v1`: SHA-256 as exactly 64 uppercase ASCII
hex characters. Content hashes identify bytes only; artifact IDs identify
logical artifacts.

## Canonicalization

The three profile IDs are:

- `imp-of01-command-canonical-json-v1`;
- `imp-of01-record-canonical-json-v1`;
- `imp-of01-commit-canonical-json-v1`.

Each profile extends repository `canonical_bytes()` with schema validation
before serialization. Output is UTF-8 JSON with Unicode unescaped, keys sorted
by code point, separators `,` and `:`, and one final LF. Objects reject unknown
or duplicate keys. Null is JSON `null`; optional fields are always present and
use `null` when absent. Booleans are JSON booleans. Integers are base-10 JSON
integers within signed 64-bit range. Floats and JSON numbers with fractional or
exponent form are prohibited. Decimal quantities use schema-normalized strings.
Timestamps are UTC epoch nanoseconds as integers. Enums use exact uppercase
tokens. Maps are used only with a schema-fixed key set. Lists are ordered when
order is semantic; set-like inputs are normalized to sorted unique lists before
hashing. Strings preserve Unicode code points but reject ASCII controls other
than schema-permitted LF/TAB, lone surrogates, and non-normalized paths.

`command_hash` excludes `command_id`, transport, trace, process, retry, and
writer-result metadata. `record_hash` includes type, schema version, profile,
record ID, and every semantic field. `commit_hash` includes the complete final
envelope and ordered item manifests but excludes itself. There is no general
semantic-content hash and no previous-commit hash.

## Public contracts

All public values are frozen dataclasses or `StrEnum`/`Protocol` types.

```python
@dataclass(frozen=True, slots=True)
class CommandEnvelope:
    command_id: str
    command_type: str
    command_schema_version: int
    command_canonicalization_profile: str
    command_hash: str
    command: LedgerCommand

@dataclass(frozen=True, slots=True)
class CommitReceipt:
    ledger_authority_id: str
    command_id: str
    command_hash: str
    commit_id: str
    commit_sequence: int
    commit_hash: str
    records: tuple[CommittedRecordRef, ...]
    was_existing: bool

class AuthoritativeLedgerWriter(Protocol):
    def submit(
        self,
        envelope: CommandEnvelope,
        prepared_artifacts: Mapping[str, PreparedArtifactToken] = {},
    ) -> CommitReceipt: ...
    def resolve_command(self, command_id: str) -> CommitReceipt | None: ...

class LedgerReader(Protocol):
    def get_record(self, record_type: str, record_id: str) -> AuthoritativeRecord | None: ...
    def get_run(self, run_id: str, disposition_policy: DispositionSelectionPolicyV1) -> RunView | None: ...
    def get_attempt(self, attempt_id: str) -> AttemptView | None: ...
    def get_commit(self, commit_sequence: int) -> LedgerCommit | None: ...

class CommitStreamReader(Protocol):
    def stream_commits(self, after_sequence: int, through_sequence: int | None = None) -> Iterator[CommitBundle]: ...

class CASStore(Protocol):
    def prepare(self, source: BinaryIO, expected_hash: str | None = None) -> PreparedObject: ...
    def publish(self, prepared: PreparedObject) -> PublishedObject: ...
    def open_verified(self, content_hash: str) -> BinaryIO: ...
    def inventory(self) -> Iterator[CASObjectInfo]: ...
```

`ArtifactIngestService.prepare(source, expected_hash)` returns an opaque
process-local `PreparedArtifactToken` containing a system-derived temp handle,
computed content hash, byte size, and ownership operation ID. The token is not
canonical command content. The caller builds artifact metadata containing that
hash/size, then passes a mapping keyed by `artifact_id` to `submit`. The writer
resolves an existing receipt first, verifies every token matches the hashed
artifact record, publishes it, and only then opens the SQLite transaction.
Unused/failed tokens are temp cleanup inputs. No public caller path exists.

### Exact command schemas and record plans

Every command canonical object includes command type/profile/version plus the
fields below. `expected_*` values are hashed semantic preconditions. Record
order is normative.

| Command | Exact command fields | Ordered authoritative records |
|---|---|---|
| `RegisterRun` | `run`, `initial_transition` (`to_state=REGISTERED`, same run/time, caller transition ID) | RUN, RUN_TRANSITION |
| `RegisterAttempt` | `attempt`, `initial_transition` (`to_phase=PENDING`, same attempt, caller transition ID), `expected_run_transition_id` | ATTEMPT, ATTEMPT_TRANSITION |
| `AppendRunTransition` | `transition`, `expected_predecessor_transition_id` | RUN_TRANSITION |
| `AppendAttemptTransition` | `transition`, `expected_predecessor_transition_id`, `expected_parallel_active_count` when parallel | ATTEMPT_TRANSITION |
| `RecordOutcome` | `outcome`, nullable `relationship` required when correction/supersession relation is not encoded by the outcome's explicit predecessor | OUTCOME, then optional RELATIONSHIP |
| `AppendDisposition` | `disposition`, `expected_prior_disposition_id` | DISPOSITION |
| `CloseRun` | `disposition`, `terminal_transition`, `expected_run_transition_id` | DISPOSITION, RUN_TRANSITION |
| `RegisterArtifact` | `artifact`; matching prepared token is noncanonical transport input | ARTIFACT |
| `AttachArtifact` | `relationship` whose source/target includes an existing ARTIFACT and whose relation is `PRODUCES_ARTIFACT`,`CONSUMES_ARTIFACT`, or `HAS_ARTIFACT` | RELATIONSHIP |
| `CreateRelationship` | `relationship` | RELATIONSHIP |
| `AttachSourceAttribution` | `source_attribution`; optional co-committed capsule/proof artifacts and matching prepared-token transport | zero or more ARTIFACT records in listed role order, then SOURCE_ATTRIBUTION |
| `AttachProvenanceReference` | `provenance_reference`; nullable relationship linking an artifact | PROVENANCE_REFERENCE, then optional RELATIONSHIP |

`RegisterArtifact`'s producer run/attempt fields are its primary atomic
reference. `AttachArtifact` creates only an additional typed relationship; it
does not recreate or mutate artifact metadata. Commands reject records or
prepared tokens not declared by their exact schema/plan. No public `save`,
`update`, arbitrary record, SQL, or caller-path API exists.

`DispositionSelectionPolicyV1` requires a target scope (`RUN` or exact
`OUTCOME`), allowed authority types, and allowed action categories. It selects
the unique disposition in that filtered scope that is not named as
`prior_disposition_id` by another selected disposition. Zero heads returns no
current disposition; more than one returns `OF01_DISPOSITION_AMBIGUOUS`. It
never breaks ties by timestamp. `RunView` always includes the complete ordered
disposition set and the policy/result used.

## Common record envelope

Every canonical typed record carries these common logical fields in addition to
family fields. Physical typed tables store the family primary key (for example
`run_id`) as the sole value from which canonical `record_id` is derived; they do
not duplicate it in a second column. The canonical builder and integrity
checker MUST prove `record_id == <family primary key>` before hashing. Commit
items store that same value as their generic `record_id`.

| Field | Type | Constraint |
|---|---|---|
| `record_id` | canonical UUID text | derived canonical alias of primary family identity |
| `record_type` | closed token | table-specific `CHECK` |
| `record_schema_version` | integer | exactly `1` in v1 |
| `record_canonicalization_profile` | text | v1 record profile |
| `record_hash` | uppercase SHA-256 | complete record hash |
| `commit_sequence` | integer | manifest membership |
| `item_ordinal` | integer | manifest membership |

The semantic canonical record excludes `commit_sequence` and `item_ordinal`.
Those fields prove membership, not domain meaning.

## Exact v1 record schemas

Fields listed as nullable remain present as JSON `null` in canonical records.
All unbounded prose fields are prohibited; code fields are 1–128 printable
ASCII characters and labels/reasons are 1–1024 Unicode scalar values after
control-character rejection.

V1 uses these closed/shared vocabularies and bounds:

| Concept | V1 values / rule |
|---|---|
| Actor type | `HUMAN`,`CI`,`SCHEDULER`,`SYSTEM`,`WORKFLOW`,`AGENT`,`PROVIDER_EVENT`,`RECONCILER` |
| Trigger type | `OPERATOR_REQUEST`,`SCHEDULE`,`PULL_REQUEST`,`WORKFLOW_RUN`,`POLICY_DECISION`,`PRIOR_RUN`,`PROVIDER_EVENT`,`SYSTEM_EVENT` |
| Failure reason family | `ENVIRONMENT_FAILURE`,`TIMEOUT`,`CANCELLATION`,`INTERRUPTION`,`PROVIDER_UNAVAILABLE`,`INTEGRITY_DEFECT`,`POLICY_BLOCK`,`UNCLASSIFIED_FAILURE` |
| Retention | `RET_EPHEMERAL`,`RET_BOUNDED_DIAGNOSTIC`,`RET_OPERATIONAL`,`RET_REPRODUCIBILITY`,`RET_HISTORICAL_EVIDENCE`,`RET_AUTHORITY_POLICY` |
| Artifact mutability | `IMMUTABLE_EVIDENCE`,`APPEND_ONLY_JOURNAL`,`REGENERABLE_OUTPUT`,`MUTABLE_STATUS`,`EPHEMERAL_SCRATCH`,`CACHE` |
| Reproducibility | `R5_BIT_EXACT`,`R4_DETERMINISTIC_REPLAY`,`R3_INPUT_REPLAYABLE`,`R2_ATTRIBUTABLE_NONDETERMINISTIC`,`R1_OBSERVATION_ONLY`,`R0_NON_REPRODUCIBLE_DECLARED` |
| Evidence strength | `E3_DOMAIN_ADMITTED`,`E2_GOVERNED_SYNTHETIC`,`E1_DIAGNOSTIC`,`E0_UNDECLARED` |
| Consequence | `C0_EPHEMERAL`,`C1_OPERATIONAL`,`C2_GOVERNED`,`C3_EVIDENCE_CRITICAL`,`C4_AUTHORITY_CRITICAL` |
| Stable reference | 1–512 Unicode scalar values; no controls, leading/trailing whitespace, credentials, or absolute filesystem path; owning `reference_kind` defines interpretation |
| Code/token | 1–128 printable ASCII, `[A-Z][A-Z0-9_.:-]*` unless a closed enum above |
| Objective | 1–2048 Unicode scalar values |
| Limitation/reason prose | 1–4096 / 1–1024 Unicode scalar values |
| Logical name/role | 1–512 / 1–128 Unicode scalar values |
| Repository/root identity | 1–512 Unicode scalar values, normalized by source-attribution schema |

V1 relation registry:

| Relation | Allowed endpoint families | Acyclic |
|---|---|---:|
| `PARENT_OF` | RUN -> RUN | Yes |
| `TRIGGERED_BY` | RUN -> RUN | Yes |
| `RESUMES_FROM` | RUN -> RUN or ATTEMPT -> ATTEMPT | Yes |
| `SUPERSEDES` | RUN -> RUN, OUTCOME -> OUTCOME, DISPOSITION -> DISPOSITION, ARTIFACT -> ARTIFACT | Yes |
| `PRODUCES_ARTIFACT` | RUN/ATTEMPT -> ARTIFACT | Yes |
| `CONSUMES_ARTIFACT` | RUN/ATTEMPT -> ARTIFACT | Yes |
| `HAS_ARTIFACT` | OUTCOME/DISPOSITION -> ARTIFACT | Yes |
| `CORRECTS` | OUTCOME -> OUTCOME or DISPOSITION -> DISPOSITION | Yes |
| `RELATED_TO` | any domain family except RELATIONSHIP -> any domain family except RELATIONSHIP | No |

Relationship-to-relationship endpoints are prohibited in v1. Endpoint family
and same-owner rules are revalidated inside the command transaction.

### Run

| Field | Type / vocabulary | Null |
|---|---|---:|
| `run_id` | UUID | No |
| `operation_class` | stable ASCII code | No |
| `objective` | bounded Unicode | No |
| `consequence_profile` | `C0_EPHEMERAL`…`C4_AUTHORITY_CRITICAL` | No |
| `reproducibility_class` | `R5_BIT_EXACT`…`R0_NON_REPRODUCIBLE_DECLARED` | No |
| `evidence_strength` | `E3_DOMAIN_ADMITTED`…`E0_UNDECLARED` | No |
| `initiator_class` | `HUMAN`,`CI`,`SCHEDULER`,`SYSTEM`,`WORKFLOW`,`AGENT`,`PROVIDER_EVENT` | No |
| `initiator_ref` | stable non-secret reference | Yes |
| `trigger_type`,`trigger_ref` | typed trigger | Yes together |
| `registered_at_ns` | nonnegative integer | No |
| `attempt_concurrency` | `SEQUENTIAL`,`EXPLICIT_PARALLEL` | No |
| `parallel_capacity` | positive integer only for parallel | Yes |
| `provenance_qualifier` | `NATIVE`,`LEGACY_PARTIAL`,`RETROSPECTIVE_INDEX` | No |
| `retention_class` | REBASE-02 retention token | No |
| `sensitivity_class` | `PUBLIC`,`INTERNAL`,`RESTRICTED` | No |
| `evaluation_protocol_ref` | stable reference | Yes |
| `temporal_cutoff_bundle_ref` | provenance reference ID | Yes |

### Attempt

| Field | Type / vocabulary | Null |
|---|---|---:|
| `attempt_id`,`run_id` | UUIDs | No |
| `attempt_sequence` | integer >= 1, unique in run | No |
| `invocation_ref`,`environment_ref` | stable provenance refs | No |
| `predecessor_attempt_id`,`checkpoint_ref_id` | UUID | Yes |
| `parallel_group` | bounded ASCII, parallel runs only | Yes |
| `expected_start_after_ns`,`expected_end_before_ns` | nonnegative ns | Yes |
| `retention_class`,`sensitivity_class` | closed tokens | No |

### Run transition

| Field | Type / vocabulary | Null |
|---|---|---:|
| `transition_id`,`run_id` | UUIDs | No |
| `predecessor_transition_id` | UUID; null only for initial transition | Yes |
| `from_state` | null initially, otherwise run state | Yes |
| `to_state` | `REGISTERED`,`ACTIVE`,`SUSPENDED`,`CLOSED` | No |
| `effective_at_ns` | nonnegative ns | No |
| `actor_type`,`actor_ref`,`policy_ref`,`reason_code` | typed bounded values | actor/policy refs may be null |
| `terminal_disposition_id` | UUID; required only for `CLOSED` | Yes |

### Attempt transition

| Field | Type / vocabulary | Null |
|---|---|---:|
| `transition_id`,`attempt_id` | UUIDs | No |
| `predecessor_transition_id` | UUID; null only for initial `PENDING` | Yes |
| `from_phase` | null initially, then attempt phase | Yes |
| `to_phase` | `PENDING`,`RUNNING`,`TERMINAL` | No |
| `terminal_result` | `COMPLETED`,`FAILED`,`TIMED_OUT`,`CANCELLED`,`INTERRUPTED`,`LOST`,`NOT_STARTED` | required only for terminal |
| `reason_family`,`reason_code` | closed family + bounded code | family required for non-completed terminal |
| `started_at_ns` | required on first `RUNNING` | Yes |
| `ended_at_ns` | required on `TERMINAL` | Yes |
| `actor_type`,`actor_ref`,`evidence_ref` | typed references | refs may be null |

### Outcome and disposition

| Record | Exact semantic fields |
|---|---|
| Outcome | `outcome_id`, `run_id`, nullable `attempt_id`, `outcome_type`, `result_ref`, `validity` (`VALID`,`INVALID`,`INDETERMINATE`,`NOT_EVALUATED`), `evaluated_at_ns`, nullable `effective_at_ns`, nullable `protocol_ref`, nullable `supersedes_outcome_id`, nullable `limitations`, retention and sensitivity |
| Disposition | `disposition_id`, `run_id`, nullable `outcome_id`, `decision_at_ns`, `authority_type`, `authority_ref`, nullable `policy_ref`, `action_category` (`ACCEPT`,`REJECT`,`DEFER`,`RETRY`,`INVALIDATE`,`CANCEL`,`ABANDON`,`SUPERSEDE`,`NO_ACTION`), `domain_code`, nullable `prior_disposition_id`, nullable `limitations`, retention and sensitivity |

### Artifact

| Field | Type / vocabulary | Null |
|---|---|---:|
| `artifact_id` | UUID | No |
| `logical_role`,`logical_name` | bounded values | name may be null |
| `content_hash`,`hash_profile`,`byte_size` | SHA-256/profile/nonnegative integer | No |
| `media_type`,`content_type` | normalized ASCII | content type may be null |
| `producer_run_id`,`producer_attempt_id` | UUID | attempt may be null |
| `completeness` | `PARTIAL`,`COMPLETE`,`UNKNOWN` | No |
| `producer_terminal_result` | attempt terminal result | Yes |
| `validation_state` | `NOT_VALIDATED`,`VALID`,`INVALID`,`INDETERMINATE` | No |
| `use_restriction` | `UNRESTRICTED`,`DIAGNOSTIC_ONLY`,`REVIEW_REQUIRED`,`PROHIBITED` | No |
| `mutability_class` | REBASE-02 mutability token | No |
| `retention_class`,`sensitivity_class` | closed tokens | No |
| `cas_locator_profile` | `imp-of01-local-cas-v1` | No |
| `redaction_state` | `NOT_APPLICABLE`,`REDACTED_BEFORE_WRITE`,`RESTRICTED_REFERENCE_ONLY` | No |

### Relationship, source attribution, and provenance

| Record | Exact semantic fields |
|---|---|
| Relationship | `relationship_id`, `source_record_type`, `source_record_id`, `relation_type`, `target_record_type`, `target_record_id`, nullable `effective_at_ns`, `acyclicity_class` (`ACYCLIC`,`CYCLES_ALLOWED`), nullable schema-bounded `relation_code` |
| Source attribution | `source_attribution_id`, `run_id`, `repository_identity`, `root_identity`, nullable `base_revision`, `source_state` (`CLEAN_COMMITTED`,`DIRTY_ATTRIBUTABLE`,`UNATTRIBUTABLE`), nullable `scope_manifest_artifact_id`, nullable `capsule_artifact_id`, nullable `outside_scope_proof_artifact_id`, nullable `limitations` |
| Provenance reference | `provenance_ref_id`, `run_id`, nullable `attempt_id`, `reference_kind` (`CONFIGURATION`,`DATA`,`MODEL`,`POLICY`,`ENVIRONMENT`,`CHECKPOINT`,`GRAPH`,`RETRIEVAL_SNAPSHOT`,`TEMPORAL_CUTOFF`), `canonical_identity`, nullable `canonical_version`, nullable `canonical_hash`, nullable `available_at_ns`, nullable `coverage_start_ns`, nullable `coverage_end_ns`, nullable `artifact_id`, nullable `limitations` |

Relationship endpoints MUST already exist or be co-committed. `PARENT_OF`,
`TRIGGERED_BY`, `RESUMES_FROM`, and `SUPERSEDES` are acyclic. `RELATED_TO` may
cycle. A schema-owned relation registry determines endpoint types; arbitrary
relation strings are rejected.

## SQLite DDL v1

The migration owns exact SQL strings and validates existing objects through
`sqlite_master`, `PRAGMA table_info`, `foreign_key_list`, and index metadata.
SQLite `STRICT` tables are required; startup rejects a SQLite library too old
to support them. All authority connections set `journal_mode=WAL`,
`synchronous=FULL`, `foreign_keys=ON`, `trusted_schema=OFF`, and a configured
bounded `busy_timeout`. The timeout is configuration, not a semantic constant;
zero is forbidden and acceptance measures the selected value.

The proposed v1 DDL is:

```sql
CREATE TABLE ledger_metadata (
  singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
  ledger_authority_id TEXT NOT NULL UNIQUE,
  database_schema_version INTEGER NOT NULL CHECK (database_schema_version = 1),
  commit_schema_version INTEGER NOT NULL CHECK (commit_schema_version = 1),
  command_profile TEXT NOT NULL,
  record_profile TEXT NOT NULL,
  commit_profile TEXT NOT NULL,
  hash_profile TEXT NOT NULL,
  cas_locator_profile TEXT NOT NULL,
  created_at_ns INTEGER NOT NULL CHECK (created_at_ns >= 0),
  deployment_topology TEXT NOT NULL CHECK (deployment_topology = 'SINGLE_LOCAL_WRITER')
) STRICT;

CREATE TABLE ledger_commits (
  commit_sequence INTEGER PRIMARY KEY CHECK (commit_sequence >= 1),
  ledger_authority_id TEXT NOT NULL,
  commit_id TEXT NOT NULL UNIQUE,
  commit_schema_version INTEGER NOT NULL CHECK (commit_schema_version = 1),
  commit_canonicalization_profile TEXT NOT NULL,
  hash_profile TEXT NOT NULL,
  command_type TEXT NOT NULL,
  command_schema_version INTEGER NOT NULL CHECK (command_schema_version >= 1),
  command_canonicalization_profile TEXT NOT NULL,
  command_id TEXT NOT NULL,
  command_hash TEXT NOT NULL CHECK (length(command_hash) = 64),
  recorded_at_ns INTEGER NOT NULL CHECK (recorded_at_ns >= 0),
  record_count INTEGER NOT NULL CHECK (record_count >= 1),
  commit_hash TEXT NOT NULL CHECK (length(commit_hash) = 64),
  UNIQUE (ledger_authority_id, command_id),
  FOREIGN KEY (ledger_authority_id) REFERENCES ledger_metadata(ledger_authority_id)
) STRICT;

CREATE TABLE ledger_commit_items (
  commit_sequence INTEGER NOT NULL,
  item_ordinal INTEGER NOT NULL CHECK (item_ordinal >= 0),
  record_type TEXT NOT NULL,
  record_id TEXT NOT NULL,
  record_schema_version INTEGER NOT NULL CHECK (record_schema_version >= 1),
  record_canonicalization_profile TEXT NOT NULL,
  record_hash TEXT NOT NULL CHECK (length(record_hash) = 64),
  PRIMARY KEY (commit_sequence, item_ordinal),
  UNIQUE (record_type, record_id),
  UNIQUE (record_type, record_id, commit_sequence, item_ordinal),
  FOREIGN KEY (commit_sequence) REFERENCES ledger_commits(commit_sequence)
    DEFERRABLE INITIALLY DEFERRED
) STRICT, WITHOUT ROWID;

CREATE TABLE runs (
  run_id TEXT PRIMARY KEY,
  record_type TEXT NOT NULL CHECK (record_type = 'RUN'),
  record_schema_version INTEGER NOT NULL CHECK (record_schema_version = 1),
  record_canonicalization_profile TEXT NOT NULL,
  record_hash TEXT NOT NULL CHECK (length(record_hash) = 64),
  commit_sequence INTEGER NOT NULL,
  item_ordinal INTEGER NOT NULL,
  operation_class TEXT NOT NULL,
  objective TEXT NOT NULL,
  consequence_profile TEXT NOT NULL,
  reproducibility_class TEXT NOT NULL,
  evidence_strength TEXT NOT NULL,
  initiator_class TEXT NOT NULL,
  initiator_ref TEXT,
  trigger_type TEXT,
  trigger_ref TEXT,
  registered_at_ns INTEGER NOT NULL CHECK (registered_at_ns >= 0),
  attempt_concurrency TEXT NOT NULL CHECK (attempt_concurrency IN ('SEQUENTIAL','EXPLICIT_PARALLEL')),
  parallel_capacity INTEGER CHECK (parallel_capacity >= 1),
  provenance_qualifier TEXT NOT NULL CHECK (provenance_qualifier IN ('NATIVE','LEGACY_PARTIAL','RETROSPECTIVE_INDEX')),
  retention_class TEXT NOT NULL,
  sensitivity_class TEXT NOT NULL,
  evaluation_protocol_ref TEXT,
  temporal_cutoff_bundle_ref TEXT,
  CHECK ((trigger_type IS NULL) = (trigger_ref IS NULL)),
  CHECK ((attempt_concurrency = 'SEQUENTIAL' AND parallel_capacity IS NULL)
      OR (attempt_concurrency = 'EXPLICIT_PARALLEL' AND parallel_capacity IS NOT NULL)),
  FOREIGN KEY (run_id,temporal_cutoff_bundle_ref)
    REFERENCES provenance_references(run_id,provenance_ref_id)
    DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY (record_type,run_id,commit_sequence,item_ordinal)
    REFERENCES ledger_commit_items(record_type,record_id,commit_sequence,item_ordinal)
    DEFERRABLE INITIALLY DEFERRED
) STRICT;

CREATE TABLE attempts (
  attempt_id TEXT PRIMARY KEY,
  record_type TEXT NOT NULL CHECK (record_type = 'ATTEMPT'),
  record_schema_version INTEGER NOT NULL CHECK (record_schema_version = 1),
  record_canonicalization_profile TEXT NOT NULL,
  record_hash TEXT NOT NULL CHECK (length(record_hash) = 64),
  commit_sequence INTEGER NOT NULL,
  item_ordinal INTEGER NOT NULL,
  run_id TEXT NOT NULL,
  attempt_sequence INTEGER NOT NULL CHECK (attempt_sequence >= 1),
  invocation_ref TEXT NOT NULL,
  environment_ref TEXT NOT NULL,
  predecessor_attempt_id TEXT,
  checkpoint_ref_id TEXT,
  parallel_group TEXT,
  expected_start_after_ns INTEGER CHECK (expected_start_after_ns >= 0),
  expected_end_before_ns INTEGER CHECK (expected_end_before_ns >= 0),
  retention_class TEXT NOT NULL,
  sensitivity_class TEXT NOT NULL,
  UNIQUE (run_id, attempt_sequence),
  UNIQUE (run_id, attempt_id),
  FOREIGN KEY (run_id) REFERENCES runs(run_id),
  FOREIGN KEY (predecessor_attempt_id) REFERENCES attempts(attempt_id),
  FOREIGN KEY (run_id,environment_ref)
    REFERENCES provenance_references(run_id,provenance_ref_id)
    DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY (run_id,checkpoint_ref_id)
    REFERENCES provenance_references(run_id,provenance_ref_id)
    DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY (record_type,attempt_id,commit_sequence,item_ordinal)
    REFERENCES ledger_commit_items(record_type,record_id,commit_sequence,item_ordinal)
    DEFERRABLE INITIALLY DEFERRED
) STRICT;

CREATE TABLE run_transitions (
  transition_id TEXT PRIMARY KEY,
  record_type TEXT NOT NULL CHECK (record_type = 'RUN_TRANSITION'),
  record_schema_version INTEGER NOT NULL CHECK (record_schema_version = 1),
  record_canonicalization_profile TEXT NOT NULL,
  record_hash TEXT NOT NULL CHECK (length(record_hash) = 64),
  commit_sequence INTEGER NOT NULL,
  item_ordinal INTEGER NOT NULL,
  run_id TEXT NOT NULL,
  predecessor_transition_id TEXT,
  from_state TEXT,
  to_state TEXT NOT NULL CHECK (to_state IN ('REGISTERED','ACTIVE','SUSPENDED','CLOSED')),
  effective_at_ns INTEGER NOT NULL CHECK (effective_at_ns >= 0),
  actor_type TEXT NOT NULL,
  actor_ref TEXT,
  policy_ref TEXT,
  reason_code TEXT NOT NULL,
  terminal_disposition_id TEXT,
  UNIQUE (run_id, transition_id),
  CHECK ((to_state = 'CLOSED') = (terminal_disposition_id IS NOT NULL)),
  FOREIGN KEY (run_id) REFERENCES runs(run_id),
  FOREIGN KEY (run_id,predecessor_transition_id)
    REFERENCES run_transitions(run_id,transition_id),
  FOREIGN KEY (terminal_disposition_id) REFERENCES dispositions(disposition_id)
    DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY (record_type,transition_id,commit_sequence,item_ordinal)
    REFERENCES ledger_commit_items(record_type,record_id,commit_sequence,item_ordinal)
    DEFERRABLE INITIALLY DEFERRED
) STRICT;

CREATE TABLE attempt_transitions (
  transition_id TEXT PRIMARY KEY,
  record_type TEXT NOT NULL CHECK (record_type = 'ATTEMPT_TRANSITION'),
  record_schema_version INTEGER NOT NULL CHECK (record_schema_version = 1),
  record_canonicalization_profile TEXT NOT NULL,
  record_hash TEXT NOT NULL CHECK (length(record_hash) = 64),
  commit_sequence INTEGER NOT NULL,
  item_ordinal INTEGER NOT NULL,
  attempt_id TEXT NOT NULL,
  predecessor_transition_id TEXT,
  from_phase TEXT,
  to_phase TEXT NOT NULL CHECK (to_phase IN ('PENDING','RUNNING','TERMINAL')),
  terminal_result TEXT,
  reason_family TEXT,
  reason_code TEXT NOT NULL,
  started_at_ns INTEGER CHECK (started_at_ns >= 0),
  ended_at_ns INTEGER CHECK (ended_at_ns >= 0),
  actor_type TEXT NOT NULL,
  actor_ref TEXT,
  evidence_ref TEXT,
  UNIQUE (attempt_id, transition_id),
  CHECK ((to_phase = 'TERMINAL') = (terminal_result IS NOT NULL)),
  CHECK (to_phase != 'RUNNING' OR started_at_ns IS NOT NULL),
  CHECK (to_phase != 'TERMINAL' OR ended_at_ns IS NOT NULL),
  FOREIGN KEY (attempt_id) REFERENCES attempts(attempt_id),
  FOREIGN KEY (attempt_id,predecessor_transition_id)
    REFERENCES attempt_transitions(attempt_id,transition_id),
  FOREIGN KEY (record_type,transition_id,commit_sequence,item_ordinal)
    REFERENCES ledger_commit_items(record_type,record_id,commit_sequence,item_ordinal)
    DEFERRABLE INITIALLY DEFERRED
) STRICT;

CREATE TABLE outcomes (
  outcome_id TEXT PRIMARY KEY,
  record_type TEXT NOT NULL CHECK (record_type = 'OUTCOME'),
  record_schema_version INTEGER NOT NULL CHECK (record_schema_version = 1),
  record_canonicalization_profile TEXT NOT NULL,
  record_hash TEXT NOT NULL CHECK (length(record_hash) = 64),
  commit_sequence INTEGER NOT NULL,
  item_ordinal INTEGER NOT NULL,
  run_id TEXT NOT NULL,
  attempt_id TEXT,
  outcome_type TEXT NOT NULL,
  result_ref TEXT NOT NULL,
  validity TEXT NOT NULL CHECK (validity IN ('VALID','INVALID','INDETERMINATE','NOT_EVALUATED')),
  evaluated_at_ns INTEGER NOT NULL CHECK (evaluated_at_ns >= 0),
  effective_at_ns INTEGER CHECK (effective_at_ns >= 0),
  protocol_ref TEXT,
  supersedes_outcome_id TEXT,
  limitations TEXT,
  retention_class TEXT NOT NULL,
  sensitivity_class TEXT NOT NULL,
  UNIQUE (run_id, outcome_id),
  FOREIGN KEY (run_id) REFERENCES runs(run_id),
  FOREIGN KEY (run_id,attempt_id) REFERENCES attempts(run_id,attempt_id),
  FOREIGN KEY (supersedes_outcome_id) REFERENCES outcomes(outcome_id),
  FOREIGN KEY (record_type,outcome_id,commit_sequence,item_ordinal)
    REFERENCES ledger_commit_items(record_type,record_id,commit_sequence,item_ordinal)
    DEFERRABLE INITIALLY DEFERRED
) STRICT;

CREATE TABLE dispositions (
  disposition_id TEXT PRIMARY KEY,
  record_type TEXT NOT NULL CHECK (record_type = 'DISPOSITION'),
  record_schema_version INTEGER NOT NULL CHECK (record_schema_version = 1),
  record_canonicalization_profile TEXT NOT NULL,
  record_hash TEXT NOT NULL CHECK (length(record_hash) = 64),
  commit_sequence INTEGER NOT NULL,
  item_ordinal INTEGER NOT NULL,
  run_id TEXT NOT NULL,
  outcome_id TEXT,
  decision_at_ns INTEGER NOT NULL CHECK (decision_at_ns >= 0),
  authority_type TEXT NOT NULL,
  authority_ref TEXT NOT NULL,
  policy_ref TEXT,
  action_category TEXT NOT NULL CHECK (action_category IN ('ACCEPT','REJECT','DEFER','RETRY','INVALIDATE','CANCEL','ABANDON','SUPERSEDE','NO_ACTION')),
  domain_code TEXT NOT NULL,
  prior_disposition_id TEXT,
  limitations TEXT,
  retention_class TEXT NOT NULL,
  sensitivity_class TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES runs(run_id),
  FOREIGN KEY (run_id,outcome_id) REFERENCES outcomes(run_id,outcome_id),
  FOREIGN KEY (prior_disposition_id) REFERENCES dispositions(disposition_id),
  FOREIGN KEY (record_type,disposition_id,commit_sequence,item_ordinal)
    REFERENCES ledger_commit_items(record_type,record_id,commit_sequence,item_ordinal)
    DEFERRABLE INITIALLY DEFERRED
) STRICT;

CREATE TABLE artifacts (
  artifact_id TEXT PRIMARY KEY,
  record_type TEXT NOT NULL CHECK (record_type = 'ARTIFACT'),
  record_schema_version INTEGER NOT NULL CHECK (record_schema_version = 1),
  record_canonicalization_profile TEXT NOT NULL,
  record_hash TEXT NOT NULL CHECK (length(record_hash) = 64),
  commit_sequence INTEGER NOT NULL,
  item_ordinal INTEGER NOT NULL,
  logical_role TEXT NOT NULL,
  logical_name TEXT,
  content_hash TEXT NOT NULL CHECK (length(content_hash) = 64),
  hash_profile TEXT NOT NULL,
  byte_size INTEGER NOT NULL CHECK (byte_size >= 0),
  media_type TEXT NOT NULL,
  content_type TEXT,
  producer_run_id TEXT NOT NULL,
  producer_attempt_id TEXT,
  completeness TEXT NOT NULL CHECK (completeness IN ('PARTIAL','COMPLETE','UNKNOWN')),
  producer_terminal_result TEXT,
  validation_state TEXT NOT NULL CHECK (validation_state IN ('NOT_VALIDATED','VALID','INVALID','INDETERMINATE')),
  use_restriction TEXT NOT NULL CHECK (use_restriction IN ('UNRESTRICTED','DIAGNOSTIC_ONLY','REVIEW_REQUIRED','PROHIBITED')),
  mutability_class TEXT NOT NULL,
  retention_class TEXT NOT NULL,
  sensitivity_class TEXT NOT NULL,
  cas_locator_profile TEXT NOT NULL,
  redaction_state TEXT NOT NULL,
  FOREIGN KEY (producer_run_id) REFERENCES runs(run_id),
  FOREIGN KEY (producer_run_id,producer_attempt_id)
    REFERENCES attempts(run_id,attempt_id),
  FOREIGN KEY (record_type,artifact_id,commit_sequence,item_ordinal)
    REFERENCES ledger_commit_items(record_type,record_id,commit_sequence,item_ordinal)
    DEFERRABLE INITIALLY DEFERRED
) STRICT;

CREATE TABLE relationships (
  relationship_id TEXT PRIMARY KEY,
  record_type TEXT NOT NULL CHECK (record_type = 'RELATIONSHIP'),
  record_schema_version INTEGER NOT NULL CHECK (record_schema_version = 1),
  record_canonicalization_profile TEXT NOT NULL,
  record_hash TEXT NOT NULL CHECK (length(record_hash) = 64),
  commit_sequence INTEGER NOT NULL,
  item_ordinal INTEGER NOT NULL,
  source_record_type TEXT NOT NULL,
  source_record_id TEXT NOT NULL,
  relation_type TEXT NOT NULL,
  target_record_type TEXT NOT NULL,
  target_record_id TEXT NOT NULL,
  effective_at_ns INTEGER CHECK (effective_at_ns >= 0),
  acyclicity_class TEXT NOT NULL CHECK (acyclicity_class IN ('ACYCLIC','CYCLES_ALLOWED')),
  relation_code TEXT,
  FOREIGN KEY (source_record_type,source_record_id)
    REFERENCES ledger_commit_items(record_type,record_id)
    DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY (target_record_type,target_record_id)
    REFERENCES ledger_commit_items(record_type,record_id)
    DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY (record_type,relationship_id,commit_sequence,item_ordinal)
    REFERENCES ledger_commit_items(record_type,record_id,commit_sequence,item_ordinal)
    DEFERRABLE INITIALLY DEFERRED
) STRICT;

CREATE TABLE source_attributions (
  source_attribution_id TEXT PRIMARY KEY,
  record_type TEXT NOT NULL CHECK (record_type = 'SOURCE_ATTRIBUTION'),
  record_schema_version INTEGER NOT NULL CHECK (record_schema_version = 1),
  record_canonicalization_profile TEXT NOT NULL,
  record_hash TEXT NOT NULL CHECK (length(record_hash) = 64),
  commit_sequence INTEGER NOT NULL,
  item_ordinal INTEGER NOT NULL,
  run_id TEXT NOT NULL,
  repository_identity TEXT NOT NULL,
  root_identity TEXT NOT NULL,
  base_revision TEXT,
  source_state TEXT NOT NULL CHECK (source_state IN ('CLEAN_COMMITTED','DIRTY_ATTRIBUTABLE','UNATTRIBUTABLE')),
  scope_manifest_artifact_id TEXT,
  capsule_artifact_id TEXT,
  outside_scope_proof_artifact_id TEXT,
  limitations TEXT,
  FOREIGN KEY (run_id) REFERENCES runs(run_id),
  FOREIGN KEY (scope_manifest_artifact_id) REFERENCES artifacts(artifact_id),
  FOREIGN KEY (capsule_artifact_id) REFERENCES artifacts(artifact_id),
  FOREIGN KEY (outside_scope_proof_artifact_id) REFERENCES artifacts(artifact_id),
  FOREIGN KEY (record_type,source_attribution_id,commit_sequence,item_ordinal)
    REFERENCES ledger_commit_items(record_type,record_id,commit_sequence,item_ordinal)
    DEFERRABLE INITIALLY DEFERRED
) STRICT;

CREATE TABLE provenance_references (
  provenance_ref_id TEXT PRIMARY KEY,
  record_type TEXT NOT NULL CHECK (record_type = 'PROVENANCE_REFERENCE'),
  record_schema_version INTEGER NOT NULL CHECK (record_schema_version = 1),
  record_canonicalization_profile TEXT NOT NULL,
  record_hash TEXT NOT NULL CHECK (length(record_hash) = 64),
  commit_sequence INTEGER NOT NULL,
  item_ordinal INTEGER NOT NULL,
  run_id TEXT NOT NULL,
  attempt_id TEXT,
  reference_kind TEXT NOT NULL,
  canonical_identity TEXT NOT NULL,
  canonical_version TEXT,
  canonical_hash TEXT,
  available_at_ns INTEGER CHECK (available_at_ns >= 0),
  coverage_start_ns INTEGER CHECK (coverage_start_ns >= 0),
  coverage_end_ns INTEGER CHECK (coverage_end_ns >= 0),
  artifact_id TEXT,
  limitations TEXT,
  UNIQUE (run_id, provenance_ref_id),
  FOREIGN KEY (run_id) REFERENCES runs(run_id),
  FOREIGN KEY (run_id,attempt_id) REFERENCES attempts(run_id,attempt_id),
  FOREIGN KEY (artifact_id) REFERENCES artifacts(artifact_id),
  FOREIGN KEY (record_type,provenance_ref_id,commit_sequence,item_ordinal)
    REFERENCES ledger_commit_items(record_type,record_id,commit_sequence,item_ordinal)
    DEFERRABLE INITIALLY DEFERRED
) STRICT;

CREATE TABLE projection_cursors (
  projection_name TEXT NOT NULL,
  projection_version TEXT NOT NULL,
  ledger_authority_id TEXT NOT NULL,
  last_applied_commit_sequence INTEGER NOT NULL CHECK (last_applied_commit_sequence >= 0),
  last_applied_commit_id TEXT,
  last_success_at_ns INTEGER,
  last_error_code TEXT,
  PRIMARY KEY (projection_name, projection_version, ledger_authority_id)
) STRICT, WITHOUT ROWID;

CREATE TABLE runtime_control (
  singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
  mode TEXT NOT NULL CHECK (mode IN ('STOPPED','STARTING','READY','DEGRADED','MAINTENANCE','WRITE_DISABLED','INTEGRITY_BLOCKED','SHUTTING_DOWN')),
  revision INTEGER NOT NULL CHECK (revision >= 0),
  changed_at_ns INTEGER NOT NULL CHECK (changed_at_ns >= 0),
  reason_code TEXT NOT NULL,
  authorization_ref TEXT
) STRICT;
```

Migration v1 then executes these exact indexes in the displayed order (PK and
UNIQUE constraints already own commit/command/record/attempt identity indexes):

```sql
CREATE INDEX idx_run_transitions_run_effective ON run_transitions(run_id,effective_at_ns,transition_id);
CREATE INDEX idx_run_transitions_predecessor ON run_transitions(run_id,predecessor_transition_id);
CREATE INDEX idx_attempt_transitions_attempt_phase ON attempt_transitions(attempt_id,to_phase,transition_id);
CREATE INDEX idx_attempt_transitions_predecessor ON attempt_transitions(attempt_id,predecessor_transition_id);
CREATE INDEX idx_outcomes_run_evaluated ON outcomes(run_id,evaluated_at_ns,outcome_id);
CREATE INDEX idx_outcomes_attempt ON outcomes(attempt_id,outcome_id);
CREATE INDEX idx_dispositions_run_decision ON dispositions(run_id,decision_at_ns,disposition_id);
CREATE INDEX idx_dispositions_outcome ON dispositions(outcome_id,disposition_id);
CREATE INDEX idx_artifacts_content ON artifacts(content_hash,artifact_id);
CREATE INDEX idx_artifacts_producer ON artifacts(producer_run_id,producer_attempt_id,artifact_id);
CREATE INDEX idx_artifacts_role ON artifacts(logical_role,completeness,artifact_id);
CREATE INDEX idx_relationships_source ON relationships(source_record_type,source_record_id,relation_type,relationship_id);
CREATE INDEX idx_relationships_target ON relationships(target_record_type,target_record_id,relation_type,relationship_id);
CREATE INDEX idx_source_attributions_run ON source_attributions(run_id,source_attribution_id);
CREATE INDEX idx_provenance_run_kind ON provenance_references(run_id,reference_kind,canonical_identity,provenance_ref_id);
```

For each table in the closed ordered list `ledger_metadata`, `ledger_commits`,
`ledger_commit_items`, `runs`, `attempts`, `run_transitions`,
`attempt_transitions`, `outcomes`, `dispositions`, `artifacts`, `relationships`,
`source_attributions`, `provenance_references`, migration v1 creates these exact
generated trigger forms, substituting the closed identifier for `{table}`:

```sql
CREATE TRIGGER trg_{table}_append_only_update
BEFORE UPDATE ON {table}
BEGIN SELECT RAISE(ABORT,'OF01_APPEND_ONLY_UPDATE_PROHIBITED'); END;

CREATE TRIGGER trg_{table}_append_only_delete
BEFORE DELETE ON {table}
BEGIN SELECT RAISE(ABORT,'OF01_APPEND_ONLY_DELETE_PROHIBITED'); END;
```

Generation from arbitrary/caller table names is prohibited. Migration tests
compare every expanded name and normalized SQL string. `runtime_control` and
`projection_cursors` are explicitly non-authoritative mutable operational
state and do not receive these triggers or appear in commit items/authority
hashes.

These two mutable tables are updated only by typed `OperationalStateStore`
methods on a separate short-transaction connection owned by the runtime or
projection operator. They do not pass through the domain writer queue because
Invariant 53 governs authoritative mutations. No public arbitrary SQL method
is exposed; their failure may affect readiness/projection state but cannot
create or alter domain history.

SQLite cannot enforce contiguous item ordinals, reverse polymorphic membership,
transition legality, concurrency, or graph acyclicity alone. The writer checks
them before commit and the integrity checker recomputes them independently.

## Transaction and writer lifecycle

For each command the writer MUST:

1. validate schema, IDs, semantic fields, sensitivity, and preconditions;
2. recompute `command_hash` and reject mismatch;
3. resolve an existing receipt before any CAS work;
4. prepare, fsync, publish, and verify required CAS bytes;
5. acquire the single-writer coordinator and execute `BEGIN IMMEDIATE`;
6. repeat receipt lookup to close duplicate races;
7. recheck IDs, references, state, predecessor, concurrency, terminality, and
   graph rules inside the transaction;
8. allocate UUIDv4 `commit_id`, next sequence, and one UTC `recorded_at_ns`;
9. build records and hashes in command-defined item order;
10. build the final commit hash, insert envelope/items/typed rows, and validate
    exact counts/membership/constraints;
11. commit or roll back wholly; and
12. resolve any ambiguous commit acknowledgement by `command_id` lookup before
    returning failure or permitting retry.

The queue is bounded, ephemeral, and configurable. Capacity, busy timeout, and
drain deadline have documented safe positive bounds and are selected from load
measurement; they are not hashes or persisted domain semantics. Queue-full
admission is `OF01_ADMISSION_BACKPRESSURE`. A timed-out caller MUST still query
the receipt before using the same identity again.

## Golden canonicalization vectors

The following vector is normative and MUST be frozen as a UTF-8 fixture. The
displayed JSON is one physical line followed by LF. The em dash and `é` are the
literal UTF-8 characters `E2 80 94` and `C3 A9`, not escapes or replacement
characters.

Command canonical JSON:

```json
{"command_canonicalization_profile":"imp-of01-command-canonical-json-v1","command_schema_version":1,"command_type":"RegisterRun","initial_transition":{"actor_ref":"github-actions","actor_type":"CI","effective_at_ns":1787923200000000000,"from_state":null,"policy_ref":null,"predecessor_transition_id":null,"reason_code":"RUN_REGISTERED","run_id":"11111111-1111-4111-8111-111111111111","terminal_disposition_id":null,"to_state":"REGISTERED","transition_id":"44444444-4444-4444-8444-444444444444"},"run":{"attempt_concurrency":"SEQUENTIAL","consequence_profile":"C2_GOVERNED","evaluation_protocol_ref":null,"evidence_strength":"E2_GOVERNED_SYNTHETIC","initiator_class":"CI","initiator_ref":"github-actions","objective":"Run validation — café","operation_class":"VALIDATION","parallel_capacity":null,"provenance_qualifier":"NATIVE","registered_at_ns":1787923200000000000,"reproducibility_class":"R4_DETERMINISTIC_REPLAY","retention_class":"RET_REPRODUCIBILITY","run_id":"11111111-1111-4111-8111-111111111111","sensitivity_class":"INTERNAL","temporal_cutoff_bundle_ref":null,"trigger_ref":"refs/pull/42","trigger_type":"PULL_REQUEST"}}
```

```text
command_hash = 05CA616A07C5AEC41D1FDFC362B690FB0B095DC1B62D7446B16444A0AB970F34
```

Record canonical JSON:

```json
{"attempt_concurrency":"SEQUENTIAL","consequence_profile":"C2_GOVERNED","evaluation_protocol_ref":null,"evidence_strength":"E2_GOVERNED_SYNTHETIC","initiator_class":"CI","initiator_ref":"github-actions","objective":"Run validation — café","operation_class":"VALIDATION","parallel_capacity":null,"provenance_qualifier":"NATIVE","record_canonicalization_profile":"imp-of01-record-canonical-json-v1","record_id":"11111111-1111-4111-8111-111111111111","record_schema_version":1,"record_type":"RUN","registered_at_ns":1787923200000000000,"reproducibility_class":"R4_DETERMINISTIC_REPLAY","retention_class":"RET_REPRODUCIBILITY","run_id":"11111111-1111-4111-8111-111111111111","sensitivity_class":"INTERNAL","temporal_cutoff_bundle_ref":null,"trigger_ref":"refs/pull/42","trigger_type":"PULL_REQUEST"}
```

```text
record_hash = 988D0DF7D34AA7B0884B73082010D3FA289AEC80D39BF2089BCCF15867689F84
```

Initial transition canonical JSON:

```json
{"actor_ref":"github-actions","actor_type":"CI","effective_at_ns":1787923200000000000,"from_state":null,"policy_ref":null,"predecessor_transition_id":null,"reason_code":"RUN_REGISTERED","record_canonicalization_profile":"imp-of01-record-canonical-json-v1","record_id":"44444444-4444-4444-8444-444444444444","record_schema_version":1,"record_type":"RUN_TRANSITION","run_id":"11111111-1111-4111-8111-111111111111","terminal_disposition_id":null,"to_state":"REGISTERED","transition_id":"44444444-4444-4444-8444-444444444444"}
```

```text
initial_transition_record_hash = E52EEB8D1895637CDEBC9D0C4E35C98DC85E40234F7735A4487204E1462E7922
```

The commit vector uses authority `aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa`, command
ID `22222222-2222-4222-8222-222222222222`, commit ID
`33333333-3333-4333-8333-333333333333`, sequence `1`, recorded time
`1787923201000000000`, a RUN at ordinal zero, and its initial transition at
ordinal one:

```json
{"command_canonicalization_profile":"imp-of01-command-canonical-json-v1","command_hash":"05CA616A07C5AEC41D1FDFC362B690FB0B095DC1B62D7446B16444A0AB970F34","command_id":"22222222-2222-4222-8222-222222222222","command_schema_version":1,"command_type":"RegisterRun","commit_canonicalization_profile":"imp-of01-commit-canonical-json-v1","commit_id":"33333333-3333-4333-8333-333333333333","commit_schema_version":1,"commit_sequence":1,"hash_profile":"imp-sha256-uppercase-hex-v1","items":[{"item_ordinal":0,"record_canonicalization_profile":"imp-of01-record-canonical-json-v1","record_hash":"988D0DF7D34AA7B0884B73082010D3FA289AEC80D39BF2089BCCF15867689F84","record_id":"11111111-1111-4111-8111-111111111111","record_schema_version":1,"record_type":"RUN"},{"item_ordinal":1,"record_canonicalization_profile":"imp-of01-record-canonical-json-v1","record_hash":"E52EEB8D1895637CDEBC9D0C4E35C98DC85E40234F7735A4487204E1462E7922","record_id":"44444444-4444-4444-8444-444444444444","record_schema_version":1,"record_type":"RUN_TRANSITION"}],"ledger_authority_id":"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa","record_count":2,"recorded_at_ns":1787923201000000000}
```

```text
commit_hash = A08BB047E6D935E02114C64C50E9C1103A8A355434603262EC58911A898668E7
```

Tests MUST additionally freeze empty/null fields, ordered lists, normalized
set-like lists, fixed-key maps, min/max signed integers, enum tokens, UUID
rejections, Unicode, and all unknown/duplicate/non-finite/fractional-number
failures.

## Lifecycle and relational rules

Run creation co-commits the initial `REGISTERED` transition. `C2+` registration
MUST complete before technical execution. `REGISTERED -> ACTIVE`,
`ACTIVE -> SUSPENDED`, `SUSPENDED -> ACTIVE`, and any nonterminal state to
`CLOSED` are the only run transitions. `CLOSED` is terminal. Closing requires a
terminal disposition already present or co-committed; `CloseRun` orders the
disposition before the transition in the manifest.

Attempt creation co-commits initial `PENDING`. `PENDING -> RUNNING`,
`PENDING -> TERMINAL/NOT_STARTED`, and `RUNNING -> TERMINAL/<result>` are the
only attempt transitions. Later success creates a new attempt. Sequential runs
permit at most one nonterminal started attempt. Explicit-parallel runs enforce
the registered capacity and group precondition. Every transition names its
exact predecessor; a compare-and-append mismatch fails with
`OF01_PRECONDITION_CHANGED`.

Zero-attempt runs may close only with `CANCEL`, `ABANDON`, or `SUPERSEDE` and a
`NOT_EVALUATED` or explicitly partial outcome. Outcome validity is independent
of analytical sign. Corrections append a new outcome/relationship. Current
disposition is a policy-specific read query over explicit lineage, never a
mutable column or last-timestamp rule.

## CAS implementation and platform durability

CAS root and SQLite authority MUST be on supported local filesystems. CAS temp
and object roots MUST share the same filesystem. The locator is derived only
from uppercase content hash:

```text
objects/imp-sha256-uppercase-hex-v1/<first-two-hex>/<64-hex-hash>
temporary/<exclusive-random-name>.tmp
quarantine/<operation-id>/<system-derived-name>
locks/<first-two-hex>/<64-hex-hash>.lock
```

Publication streams to an exclusive temp file, computes hash/size, flushes and
calls `os.fsync(file)`, validates any expected hash, and closes. It then acquires
a per-content-hash inter-thread lock and an exclusive lock file created with
`O_CREAT|O_EXCL`. Under that cooperative publisher lock it verifies an existing
final object or, only when the final path is absent, performs same-filesystem
`os.replace(temp, final)`. It never calls replace when a final object exists.
The CAS root permissions prohibit non-runtime publishers; any unexplained final
path appearing under the lock is verified or treated as an integrity incident.
After publish it reopens and verifies size/hash before the database transaction,
then releases/removes the lock. Crash-left lock recovery requires proof that its
owning process/operation is absent and is handled like temp cleanup; age alone
does not grant deletion.

On POSIX, implementation MUST fsync the containing directory after rename when
the filesystem/runtime supports it. On Windows, CPython provides file flush and
`fsync` plus atomic same-volume replace but no portable directory-fsync
contract; v1 therefore requires post-publish reopen/hash verification and a
fault-tested statement of this residual metadata-durability limitation. It MUST
NOT claim POSIX directory durability on Windows.

Temp cleanup and orphan scanning are idempotent. Destructive GC takes a stable
ledger high-water mark, inventories references from that snapshot, excludes
objects under retention/backup/recovery/quarantine holds, emits a dry-run
manifest, then requires an explicit authorization reference bound to that exact
manifest. A changed inventory invalidates authorization. GC never deletes a
referenced object or authoritative metadata.

## Read APIs and projections

Primary reads query typed tables. `stream_commits(after_sequence,
through_sequence=None)` yields complete commit bundles in sequence and ordinal
order from a read transaction. `after_sequence < 0`, a range inversion, or a
requested cursor belonging to another authority fails with a typed code.

Current `RunView` contains immutable run data, derived state and transition,
attempt summaries, outcomes, policy-selected disposition, artifact inventory,
relationships, and `as_of_commit_sequence`. It MUST expose source record IDs
and MUST NOT present projection state as authority.

Every projection reports:

```text
projection_name, projection_version, source_ledger_authority_id,
last_applied_commit_sequence, last_applied_commit_id, source_high_water,
lag_commits, last_success_at_ns, last_error_code, state
```

Projection states are `STOPPED`, `RUNNING`, `PAUSED`, `DEGRADED`, and
`REBUILD_REQUIRED`. Cursor advancement occurs only after durable idempotent
application. Mongo documents include projection version, source authority,
commit ID/sequence, record type/ID/schema/hash, and projected content. The
projector never imports the writer protocol. Default repair is reset/rebuild
and replay; no projection defect authorizes ledger mutation.

## Schema migration

Physical schema version, command/record version, and hash profile version are
independent. Startup accepts exactly supported versions and refuses unknown
newer versions. Each migration declares source, destination, transactional
behavior, required maintenance state, minimum backup class, postconditions,
hash-preservation query, and restore rollback boundary.

Routine migration may add compatible objects, indexes, nullable fields, or
derived projection state. It MUST NOT recanonicalize prior rows, change stored
hashes, reuse IDs, rewrite semantics, or silently upcast authoritative history.
Readers dispatch by stored version. An upcast view identifies the source
version and never masquerades as the committed record. Semantic migration
requires a design amendment and append/new-authority strategy.

## Integrity checker

Integrity modes are:

| Mode | Quiescence | Required checks |
|---|---|---|
| `QUICK` | No; consistent read snapshot | schema/profile support, metadata, `quick_check`, foreign keys, latest commit/item, referenced CAS sample/policy |
| `FULL` | Maintenance by default | `integrity_check`, every FK/member/ordinal/hash/schema/record/commit, all referenced CAS bytes, projection cursors |
| `FORENSIC` | Write-disabled | all FULL checks plus bounded evidence export; never repair |
| `BACKUP_VERIFY` | Snapshot/offline | full snapshot authority/hash/CAS coverage checks |
| `RESTORE_VERIFY` | Offline candidate | full checks plus manifest, high-water, identity, activation eligibility |

Findings use `AUTHORITATIVE_FATAL`, `OPERATIONAL_DEGRADED`, `REBUILDABLE`, or
`HOUSEKEEPING`. Any authoritative fatal finding atomically transitions the
runtime to `INTEGRITY_BLOCKED`, rejects new commands, preserves the original
files, and returns an incident reference. A hash mismatch is evidence; the
checker MUST NOT recompute and store a replacement.

## Backup and restore contracts

Backup identity is UUIDv4. A canonical backup manifest contains source
authority, backup/tool/profile versions, database schema and hash profiles,
snapshot byte hash/size, highest commit sequence/ID/hash, exact referenced CAS
inventory and coverage, creation time, destination identity, limitations, and
verification results. Backup state is `UNVERIFIED`, `VERIFIED`, or
`RESTORE_TESTED`; only the corresponding completed procedure may advance the
label.

The backup service uses SQLite's backup API to produce a consistent snapshot,
reads the high-water mark from that snapshot, inventories referenced objects
from the snapshot, copies/verifies those bytes, then publishes the manifest
last. Raw copying an active DB/WAL pair is prohibited. Failure leaves no
verified manifest and never prunes an older backup.

Restore occurs with the authority stopped and target inactive. It verifies the
manifest, database, IDs, schema/profiles, all record and commit hashes, high
water, and CAS coverage before activation. Recovery preserves
`ledger_authority_id`; a development clone is read-only by default and MUST be
explicitly reinitialized with a new authority before any writes. Activation
requires recovery-operator authorization, exclusive-lock proof, configuration
identity, and a successful `RESTORE_VERIFY`. Divergent authority copies are not
merged.

## Runtime service and health model

Operational modes are `STOPPED`, `STARTING`, `READY`, `DEGRADED`,
`MAINTENANCE`, `WRITE_DISABLED`, `INTEGRITY_BLOCKED`, and `SHUTTING_DOWN`.
These are mutable service state, not domain history.

- Liveness means the process/status surface responds.
- Readiness means all mandatory prerequisites permit authoritative writes.
- Degraded means noncritical capability is impaired while declared authority
  behavior remains safe.
- Integrity blocked means authority cannot safely accept writes.

`READY_FOR_AUTHORITATIVE_WRITES` requires valid configuration and paths,
supported local filesystem, required permissions, matching authority identity,
supported schema/profiles, WAL/FULL/foreign-key settings, writer exclusivity,
CAS read/write/publish verification, successful startup quick integrity, no
fatal unresolved finding, and non-maintenance mode. Projection availability is
reported separately and does not normally block the writer.

Startup performs those checks in that order and fails closed. Graceful shutdown
changes to `SHUTTING_DOWN`, closes admission, rejects or drains queued commands
under the configured policy, resolves the active command to receipt/commit or
rollback, resolves an ambiguous commit, closes readers/projectors, checkpoints
WAL only when safe, closes the writer, releases the lock, and records `STOPPED`.

Maintenance entry closes admission, resolves the active transaction, and issues
a revision-bound maintenance lease with initiator, authority, purpose, time,
and authorization reference. Schema migration, restore activation, destructive
CAS GC, authority cloning/reidentification, and authority filesystem moves
require maintenance. Quick checks, verified online backup, reads, projection
replay, and dry-run scans do not. Full integrity defaults to maintenance unless
the implementation proves a consistent nonblocking mode and records it.

## Required operator capabilities

The runtime MUST implement these stable capability IDs. CLI spelling is an
adapter detail and MUST be copied into the operations docs only after the CLI
exists and documentation-conformance tests bind it.

| Capability ID | Structured result |
|---|---|
| `OF01.OP.STATUS` | mode, health dimensions, authority, schema/profiles, latest commit, CAS, projection, backup summary |
| `OF01.OP.LEDGER_METADATA` | authority and compatibility metadata |
| `OF01.OP.COMMAND_RESOLVE` | authoritative receipt or proven absence |
| `OF01.OP.WRITE_DISABLE` | revision-bound containment result and reason; cannot re-enable writes |
| `OF01.OP.INTEGRITY_QUICK` / `FULL` / `FORENSIC` | finding set, high-water, evidence ref |
| `OF01.OP.BACKUP_CREATE` / `VERIFY` | backup ID, manifest, coverage, state |
| `OF01.OP.BACKUP_ATTEST_RESTORE_TEST` | exercise evidence binding and `RESTORE_TESTED` transition |
| `OF01.OP.RESTORE_VALIDATE` / `ACTIVATE` | candidate identity, verification, activation result |
| `OF01.OP.MAINTENANCE_ENTER` / `EXIT` | lease/revision and readiness result |
| `OF01.OP.CAS_VERIFY` / `ORPHAN_SCAN` / `GC_DRY_RUN` / `GC_EXECUTE` | stable inventory/manifest/result |
| `OF01.OP.PROJECTION_STATUS` / `START` / `PAUSE` / `RESUME` / `REBUILD` / `UPGRADE` | projection identity/cursor/version/result |
| `OF01.OP.MIGRATION_STATUS` / `APPLY` | source/destination, backup, result |
| `OF01.OP.AUTHORITY_CLONE_VALIDATE` / `REIDENTIFY` | isolated target proof, source/clone identities, write eligibility |
| `OF01.OP.SHUTDOWN` | admission/drain/active-command resolution |

All capabilities support canonical JSON output. Consequential operations emit
an operational evidence envelope containing operation ID, initiator/role,
authorization reference, tool/source version, target authority, timestamps,
inputs by safe identity, outcome code, verification, and evidence location.
These envelopes are operational artifacts, not automatically domain records.

### Structured operational contracts

`StatusV1` contains `observed_at_ns`, monotonic `runtime_revision`,
`process_instance_id`, `mode`, `liveness`, `ready_for_authoritative_writes`,
sorted `readiness_reason_codes`, authority/database/profile identities, writer
lock owner, queue/active-command summary, latest commit identity, integrity
state/last-success/report reference, CAS filesystem/write-probe/inventory
summary, backup state/ID/time, and sorted `ProjectionStatus` values. A caller
MUST reject status older than its owning workflow's action boundary and refresh
immediately before compare-and-act operations; no universal numeric freshness
threshold is invented.

`OperationEvidenceV1` contains `schema_version`, UUID `operation_id`,
`capability_id`, `initiator_type`, `initiator_ref`, `role`, nullable
`authorization_ref`, `tool_identity`, `source_revision`, target authority,
`started_at_ns`, `completed_at_ns`, canonical safe `input_identities`,
`outcome_code`, sorted verification results, nullable `evidence_parent_ref`, and
`content_hash`. It is canonical JSON using the repository hash profile, stored
under the configured restricted operational-evidence root by operation ID, with
retention/sensitivity supplied by deployment policy. OF-01 does not sign these
artifacts in v1 and does not implement an organization-wide catalog.

`BackupManifestV1` contains backup ID/state, source authority, schema/profile/
tool/source identities, creation time, snapshot hash/size, high-water
sequence/ID/hash, sorted CAS entries (`content_hash`,`byte_size`,`coverage_type`,
`coverage_ref`), destination identity, limitations, verification operation ID,
and manifest hash. `coverage_type` is `COPIED_OBJECT` or
`VERIFIED_EXTERNAL_IMMUTABLE_OBJECT`; the latter requires a content-addressed
immutable destination and verification performed during this backup. The
manifest publishes by same-filesystem atomic replacement after all entries
verify. Resume is permitted only when backup ID, snapshot hash, high-water, and
existing entry hashes match exactly.

`CASScanManifestV1` contains scan ID, authority/high-water, CAS inventory cut,
sorted referenced/missing/mismatched/orphan/temp entries, hold inventory
identity, tool/source identity, completion state, and hash. A temp object is
deletion-eligible only when no live process/operation lease owns it and its
creation operation is proven terminal/absent; age alone is insufficient.
Retention, legal, quarantine, and recovery holds come from configured policy
inputs named and hashed in the manifest.

`CASGCDryRunV1` binds a complete CAS scan hash, authority/high-water, hold
inventory hash, sorted candidate hashes/sizes/reasons, excluded counts/reasons,
and total candidate bytes. `CASGCExecutionV1` binds the dry-run hash and exact
authorization reference, records each candidate result, then records
`OF01.OP.CAS_VERIFY` and `OF01.OP.INTEGRITY_QUICK` results. Any changed
high-water, scan, holds, or candidates invalidates the authorization.

OF-01 validates but does not issue external authorization references. The
deployment security authority issues/revokes a consequence-scoped reference;
OF-01 binds it to capability, target authority, input manifest/hash, initiator,
and configured validity interval. Maintenance leases are OF-01-local mutable
operational controls with UUID, runtime revision, authority, purpose,
authorization reference, owner, issue/expiry times, and closed state. Expiry
closes admission and requires a new authorization; it never auto-exits
maintenance or authorizes rollback.

The injected boundary is exact:

```python
class AuthorizationVerifier(Protocol):
    def verify(
        self,
        reference: str,
        *,
        capability_id: str,
        ledger_authority_id: str,
        input_hash: str,
        initiator_ref: str,
        observed_at_ns: int,
    ) -> AuthorizationGrant: ...
```

`AuthorizationGrant` is frozen and contains issuer/trust-source identity,
reference, capability, authority, input hash, initiator, allowed role,
not-before/expiry, and revocation state/version. The verifier reads a configured
deployment trust/revocation source; callers cannot supply grant claims. Any
mismatch, expiry, revocation, unavailable trust source, or stale revocation
version fails closed with `OF01_AUTHORIZATION_REQUIRED`. Offline tests inject a
fake verifier and never contact external security systems.

## Stable error and status categories

| Family | Required codes |
|---|---|
| Command | `OF01_INVALID_COMMAND`, `OF01_COMMAND_ID_CONFLICT`, `OF01_DOMAIN_ID_CONFLICT`, `OF01_PRECONDITION_CHANGED`, `OF01_INVALID_TRANSITION`, `OF01_MISSING_REFERENCE`, `OF01_UNSUPPORTED_COMMAND_SCHEMA`, `OF01_DISPOSITION_AMBIGUOUS` |
| Storage | `OF01_SQLITE_BUSY`, `OF01_STORAGE_UNWRITABLE`, `OF01_UNSUPPORTED_FILESYSTEM`, `OF01_MULTIPLE_WRITERS`, `OF01_AMBIGUOUS_COMMIT`, `OF01_APPEND_ONLY_UPDATE_PROHIBITED`, `OF01_APPEND_ONLY_DELETE_PROHIBITED` |
| CAS | `OF01_CAS_PREPARE_FAILED`, `OF01_CAS_HASH_MISMATCH`, `OF01_CAS_REFERENCED_OBJECT_MISSING`, `OF01_CAS_ORPHAN_FOUND`, `OF01_CAS_GC_AUTHORIZATION_MISMATCH` |
| Integrity | `OF01_INTEGRITY_FATAL`, `OF01_SCHEMA_UNSUPPORTED`, `OF01_RECORD_HASH_MISMATCH`, `OF01_COMMIT_HASH_MISMATCH`, `OF01_MEMBERSHIP_MISMATCH`, `OF01_FOREIGN_KEY_MISMATCH` |
| Backup/restore | `OF01_BACKUP_INCOMPLETE`, `OF01_BACKUP_VERIFY_FAILED`, `OF01_RESTORE_VERIFY_FAILED`, `OF01_AUTHORITY_IDENTITY_MISMATCH`, `OF01_ACTIVATION_PROHIBITED` |
| Migration | `OF01_MIGRATION_PATH_UNSUPPORTED`, `OF01_MIGRATION_BACKUP_REQUIRED`, `OF01_MIGRATION_VERIFY_FAILED` |
| Projection | `OF01_PROJECTION_UNAVAILABLE`, `OF01_PROJECTION_CURSOR_INVALID`, `OF01_PROJECTION_REBUILD_REQUIRED` |
| Runtime | `OF01_NOT_READY`, `OF01_MAINTENANCE_REQUIRED`, `OF01_AUTHORIZATION_REQUIRED`, `OF01_ADMISSION_BACKPRESSURE`, `OF01_SHUTDOWN_IN_PROGRESS` |

## Roles and authority matrix

`A` means allowed by the typed interface; `C` means consequence-specific
explicit authorization; `R` means read-only; `—` means prohibited.

| Operation | Runtime | Ledger operator | Maintenance operator | Recovery operator | Projection operator | Analyst | Automation/AI |
|---|---:|---:|---:|---:|---:|---:|---:|
| Read record / stream commits | R | R | R | R | R | R | R when granted |
| Submit typed writer command | A | A when granted | A when granted | — | — | — | A only scoped |
| Inspect status/quick integrity | R | R | R | R | R | R | R |
| Full/forensic integrity | — | — | C | C | — | — | request only |
| Backup create/verify | — | — | C | C | — | — | request only |
| Restore validate/activate | — | — | — | C | — | — | validate only; no activation |
| Migration | — | — | C | C | — | — | plan/inspect only |
| CAS scan / GC dry-run | — | R | C | C | — | — | scan only when granted |
| CAS GC execute | — | — | C | C | — | — | prohibited autonomously |
| Projection rebuild | — | — | — | — | C | — | request only |
| Direct SQL read | — | R controlled | R controlled | R forensic | — | R approved | prohibited by default |
| Direct SQL mutation | — | — | — | break-glass procedure only | — | — | — |
| Change authority identity | — | — | — | C for explicit clone/reinit | — | — | — |

The `ledger runtime` service identity is the only ordinary SQLite mutation
principal. Human convenience does not widen this boundary. Break-glass repair
is future-governed, incident-scoped, offline, evidence-preserving, and cannot be
used as maintenance precedent; restore, replay, rebuild, and append correction
are preferred.

## Failure/response matrix

| Condition | Writes | Reads | Projection | Required response |
|---|---:|---:|---:|---|
| Projection/Mongo unavailable | Yes | Yes | Retry/rebuild | Mark degraded; preserve cursor |
| CAS temporarily unwritable | No artifact commands; other writes policy-gated | Yes | Yes | Diagnose storage; prove writable before readiness |
| Referenced CAS object missing/hash mismatch | No | Forensic/verified unaffected reads | Pause affected | Integrity block; preserve evidence; verified restore |
| SQLite busy transient | Admission retry bounded | Yes | Yes | Resolve receipt; backoff; inspect writer |
| SQLite unwritable/disk full | No | Where safe | Pause | Stop admission; preserve files; storage incident |
| Foreign-key/record/commit hash mismatch | No | Forensic only | Pause | Integrity block; no auto-repair |
| Unsupported schema/profile | No | Compatible forensic read only | No | Supported migration or restore/version correction |
| Backup failure | Yes if authority otherwise healthy | Yes | Yes | Backup unverified; preserve prior backups |
| Restore verification failure | Target inactive | Candidate read-only | No | Reject activation; preserve evidence |
| Disk pressure warning | Yes unless policy threshold reached | Yes | Yes | Capacity action; no arbitrary threshold in spec |
| Writer crash | No until restart readiness | SQLite recovery read after check | Resume later | Lock, quick check, receipt resolution, restart |
| Ambiguous commit response | No duplicate submission | Yes | Yes | Query receipt by original command ID |
| Network filesystem detected | No | Optional read-only | No | Relocate through governed backup/restore |
| Multiple writer detected | Second writer no | Existing service yes | Yes | Reject second process; investigate custody |

## Observability contract

The implementation MUST define the following stable metric/event semantics;
numeric alert thresholds remain measurement/policy decisions:

```text
of01_writer_available, of01_writer_ready, of01_writer_queue_depth,
of01_command_admission_failures_total{code}, of01_commit_latency_seconds,
of01_commits_total, of01_records_total, of01_sqlite_busy_total,
of01_database_bytes, of01_wal_bytes, of01_cas_bytes,
of01_cas_temp_objects, of01_cas_orphan_objects,
of01_integrity_state, of01_integrity_last_success_ns{mode},
of01_backup_state, of01_backup_age_seconds,
of01_restore_verification_state, of01_projection_lag_commits{projection},
of01_projection_cursor{projection}, of01_projection_failures_total{projection,code},
of01_migration_state, of01_database_schema_version
```

Logs/events include operation/command/commit IDs where known but never secrets,
raw artifact content, arbitrary environment variables, or caller-supplied
filesystem paths. Sample counts accompany latency distributions.

## Change control and release/upgrade

Changes to canonicalization, hash profiles, IDs, record/command schema,
authority topology, CAS durability, migration/backup semantics, or writer
transaction ordering require design review, compatibility analysis, migration
and recovery plan, golden-vector changes, and acceptance evidence. Ordinary
implementation refactors that preserve every public byte/contract use normal
review.

Upgrade sequence is: verify current health; create and verify backup; enter
maintenance when required; stop admission; deploy code; apply only the declared
migration path; run post-migration integrity and hash-preservation checks;
verify profiles; start writer; prove readiness; resume commands; verify
projections; exit maintenance; and retain acceptance evidence. A failed step
stops the sequence and follows its declared restore boundary.

## Development and test isolation

Every test uses a temporary SQLite path, temporary CAS root, and unique
`ledger_authority_id`. Test constructors reject known operator/production paths.
Fault injection may corrupt disposable copies only. Fixtures distinguish
`REAL_AUTHORITY`, `DISPOSABLE_TEST_AUTHORITY`, `RESTORED_RECOVERY_AUTHORITY`,
and `ANALYSIS_FORK`; the last two are write-disabled unless explicitly activated
under their procedures.

## Scenario review A–T

| Scenario | Deterministic disposition |
|---|---|
| A Normal start | Startup checks pass -> `READY`; otherwise typed fail-closed mode |
| B Register run | One command, initial transition, one receipt/commit |
| C Response lost after commit | Original command lookup returns existing receipt |
| D Crash before commit | SQLite rolls back; lookup absent; same ID/hash may retry |
| E Referenced artifact missing | Integrity block; writes stop; verified byte restore only |
| F CAS orphan | Housekeeping finding; quarantine/authorized GC only |
| G Disk fills during artifact preparation | No DB reference; temp evidence/cleanup; retry after storage recovery |
| H Disk fills during SQLite transaction | Rollback or ambiguous receipt resolution; no blind retry |
| I Projection down 24 hours | Authority remains ready; lag recorded; replay resumes |
| J Projection stale/corrupt | Reset/rebuild from authority; no ledger mutation |
| K Verified backup needed | Snapshot -> high-water inventory -> CAS coverage -> manifest verify |
| L Machine loss | Offline restore verify -> identity/custody check -> explicit activation -> rebuild projection |
| M Schema upgrade | Verified backup + maintenance + supported migration + integrity/readiness |
| N Record hash mismatch | `INTEGRITY_BLOCKED`; evidence capture; no hash rewrite |
| O Agent attempts mutation SQL | Permission/API denial and policy violation evidence |
| P Agent retries with new IDs | New command semantics, not retry; agent rule violation surfaced |
| Q Same command concurrently | Serialized first commit; second returns same receipt |
| R Second writer starts | Process lock denies second readiness |
| S DB on network filesystem | Startup refuses authoritative writes |
| T Delete old history | Prohibited; retention classification/hold only; no purge capability |

## Adversarial review disposition

| Pass | Result |
|---|---|
| Semantic correctness | All 75 invariants trace to schemas, interfaces, procedures, or acceptance tests. |
| Crash consistency | CAS-before-reference and one SQLite transaction prevent partial authoritative commands under the supported failure model. |
| Identity consistency | Command/domain/ledger/content identities remain distinct. |
| Hash correctness | Profiles, exclusions, ordering, and vectors are frozen. |
| Relational integrity | DDL proves keys/FKs/checks; writer/checker own non-SQL graph and reverse-membership rules. |
| Operational completeness | Status, lifecycle, integrity, recovery, CAS, projection, and migration capabilities have owned procedures. |
| Recovery completeness | Manifest-bound restore and activation are stepwise and fail closed. |
| Agent safety | Typed-only, stable retry identity, evidence, and destructive-action rules are testable. |
| Security | Secret rejection, derived paths, role separation, and read-only forensic access are explicit. |
| OF-03 boundary | Stable static metadata exists; no registry/orchestrator is implemented. |
| EVIDENCE isolation | No EVIDENCE file, dependency, or semantic contract changes. |
| Simplicity | One package, one authority, one writer, one CAS, rebuildable projections; no premature distributed system. |

## Test and acceptance requirements

The runtime suite MUST include unit, contract, repository, transaction,
concurrency, restart, fault-injection, CAS, integrity, backup, restore,
migration, projection, operations, SOP exercise, documentation-conformance,
performance-measurement, and agent-policy negative tests. It MUST prove:

- exact golden bytes/hashes and strict parser rejection;
- same command retry/conflict, domain-ID collision, duplicate races, and lost
  response resolution;
- atomic multi-record rollback at every insertion point;
- all run/attempt transition and closure rules;
- CAS publish, duplicate bytes, missing/mismatch, temp, orphan, traversal, disk,
  and permission failures;
- record/commit/member/FK/schema corruption detection without mutation;
- projection pause/resume/idempotent replay/reset/full rebuild/version upgrade;
- backup high-water/CAS coverage and restore identity/hash/readiness;
- migration source/destination/backup/rollback/hash preservation;
- startup/shutdown/restart/queue-drain/maintenance/readiness modes;
- agents cannot mutate SQL, fabricate success, change retry identity, authorize
  GC, hide corruption, or promote projection state; and
- every documented capability/argument/output/error exists and matches docs.

Operational acceptance MUST exercise the full list in Invariant 75, including
corruption, disk/permission failure, queued shutdown, and disaster recovery, in
a controlled disposable environment. Documentation alone is not evidence.

## Implementation sequence

The detailed task plan is
`docs/superpowers/plans/2026-08-28-imp-of-01-universal-run-artifact-ledger.md`.
Its dependency order is:

1. IDs, errors, canonicalization, and golden vectors;
2. immutable records and typed commands;
3. backend-independent protocols and in-memory contract double;
4. SQLite metadata, DDL, and migrations;
5. commit journal and serialized writer/idempotency;
6. run/attempt transitions, outcomes, dispositions, and relationships;
7. CAS and artifact commands;
8. source attribution and provenance;
9. readers, commit stream, current state, and projections;
10. integrity checker and integrity block;
11. backup, restore, authority activation, and migration;
12. health, startup, shutdown, maintenance, and backpressure;
13. structured operator interfaces and stable outputs;
14. operations docs binding, roles, workflows, and agent-policy tests;
15. deterministic fault injection and performance measurement; and
16. operational drills, full validation, and acceptance evidence.

Each stage has its own focused tests and commit boundary. No later stage may
weaken an earlier invariant to simplify implementation.

## Allowed implementation paths

Runtime implementation may create only the package/tests/acceptance surfaces
listed in the implementation plan plus minimal package exports and validation
manifest changes that receive their required governance. It MUST NOT modify
EVIDENCE, provider, prediction/settlement, risk, execution, or unrelated
platform behavior. No new dependency is authorized; CPython 3.11 standard
library is sufficient for v1.

## Known limitations and legitimate code-level choices

- The configured queue capacity, busy timeout, drain deadline, scan cadence,
  backup cadence, GC cadence, and alert thresholds require measurement and
  deployment policy; safe bounds and measurement are mandatory.
- Windows directory-entry durability remains weaker than a claimed POSIX
  directory-fsync contract and must be fault-tested/documented.
- Exact OS filesystem-type detection uses the narrowest reliable platform API;
  inability to prove local support fails readiness.
- Current-state realization may use typed query logic or disposable SQLite
  views/materialization if tests prove identical semantics.
- Mongo projection implementation may be delivered after core authority behind
  the same acceptance boundary, but its protocol and rebuild tests are not
  optional for OF-01 completion.
- Multiple isolated hosts can still be misactivated by human custody failure;
  v1 offers no consensus or divergent-history merge.

These are implementation choices or declared limits, not reopened invariants.

## Review acceptance

```text
Invariants 1–50 preserved: YES
Invariants 51–75 covered: YES
Subsystem operational control specified: YES
OF-03 global registry implemented: NO
ADAPT-specific records added: NO
EVIDENCE-01C new dependency: NO
EVIDENCE semantics changed: NO
Runtime code changed by this review: NO
```

Next gate:

```text
IMP-OF-01 Clean-Worktree Runtime Implementation
```

IMP_OF_01_SPEC_APPROVED_FOR_IMPLEMENTATION
