# IMP-OF-01 Universal Append-Only Run and Artifact Ledger — Design

| Field | Value |
|---|---|
| Document ID | `IMP-OF-01-DESIGN` |
| Classification | `ACTIVE_SUPPORTING` |
| Truth class | `PROPOSED_IMPLEMENTATION_DESIGN` |
| Review state | `READY_FOR_WRITTEN_SPEC_REVIEW` |
| Version | `1.0` |
| Last verified | `2026-08-28` |
| Establishing milestone | `IMP-OF-01` design closure |
| Approved base | `f4a66becb25a947d3ac789fa16c3af5539d927d5` |
| Runtime implementation | `NOT_STARTED` |

## Disposition

This design closes the architecture for the first runtime milestone that
implements the run, attempt, outcome, disposition, relationship, attribution,
and artifact semantics established by IMP-REBASE-02. It is sufficiently
specific for adversarial written-spec review. It does not create runtime
contracts, database migrations, tables, repositories, CAS directories, or
adapters.

```text
AUTHORITY                  SQLite WAL on a supported local filesystem
WRITE TOPOLOGY             one serialized authoritative writer
DOMAIN REPRESENTATION      typed immutable relational records
ORDERING                   ledger_commits + ledger_commit_items
ARTIFACT BYTES             local content-addressed store (CAS)
MONGO                      optional non-authoritative projection/export
MULTI-HOST WRITERS         unsupported in OF-01 v1
EVIDENCE CHANGE            none
ADAPT-SPECIFIC RECORDS     none
```

## Purpose

OF-01 provides one generic provenance substrate for consequential IMP work. It
must durably answer:

- what logical run was registered and why;
- which bounded technical attempts occurred, in what declared concurrency
  mode, and with which terminal technical results;
- what typed domain outcomes were obtained and whether they were valid;
- what governed dispositions were appended without erasing prior decisions;
- what artifacts were consumed or produced, where their immutable bytes live,
  and how completeness and use restrictions were classified;
- what source, configuration, data, model, policy, environment, time, and
  relationship lineage applied;
- which caller command created each exact atomic mutation; and
- how an incremental consumer can replay committed history in one authoritative
  order without treating that order as event time.

OF-01 is infrastructure. It does not decide domain truth, qualify EVIDENCE,
promote candidates, authorize risk or execution, schedule workflows, or perform
adaptive learning.

## Current program state and verified repository baseline

| Item | Verified state |
|---|---|
| Primary repository | `C:/Users/adame/Desktop/market-trading-platform/integrated-market-platform` |
| Original branch / HEAD | `cloud/build-35-release-governance-operational-acceptance` / `44800d2e210e58ff5759c44cc343dd4578c0b821` |
| Original checkout | Dirty before this campaign; preserved untouched |
| Design worktree | `.worktrees/imp-of-01-design` |
| Design branch | `docs/imp-of-01-design` |
| Design starting HEAD | `f4a66becb25a947d3ac789fa16c3af5539d927d5` |
| REBASE-02 lineage | `9c7ea45 -> bc04d5e -> d899e21 -> b570faf -> f4a66be` |
| REBASE-02 status | `IMP_REBASE_02_COMPLETE` |
| ADAPT-00 current HEAD | `036b631c29cb0573ad26b0d49b62a0a62670744c` |
| ADAPT ancestry | `79ad9dd` and `9cde631` are both ancestors of `036b631c` |
| Baseline validation | `PASSED full: 2956 tests, 39 skipped, 0 failures, 0 errors` |

Canonical authorities reviewed:

- `docs/platform/REPRODUCIBILITY_AND_RUN_STANDARD.md`;
- `docs/platform/OBSERVABILITY_STANDARD.md`;
- `docs/platform/TEST_AND_EVALUATION_STANDARD.md`;
- `docs/platform/MASTER_ARCHITECTURE.md`;
- `docs/platform/MASTER_ROADMAP.md`;
- the REBASE-02 design and accepted implementation specification; and
- the `79ad9dd..036b631c` ADAPT-00 planning delta.

No accepted invariant in this design conflicts with those authorities.

## Scope

OF-01 v1 designs:

- backend-independent typed command and record contracts;
- a local SQLite authority with strong commit durability;
- a global local-authority commit sequence and atomic multi-record manifest;
- immutable run, attempt, transition, outcome, disposition, artifact,
  relationship, source-attribution, and provenance-reference records;
- caller-owned command and domain identities;
- deterministic command, record, and commit hashes;
- a filesystem CAS for immutable artifact bytes;
- typed read/query boundaries and an ordered commit stream;
- rebuildable current-state and Mongo projections;
- integrity, backup, restore, corruption, and fork-control semantics;
- schema evolution and historical interpretation rules;
- retention/redaction hooks without authoritative history deletion;
- legacy/retrospective compatibility targets for later OF-02 adapters; and
- test, fault-injection, performance-measurement, and acceptance requirements.

## Out of scope

OF-01 v1 does not implement or authorize:

- multi-host or multiple-process authoritative writers;
- SQLite authority on SMB, NFS, or another network filesystem;
- PostgreSQL, consensus, leader election, automatic failover, or merge of
  divergent authorities;
- a durable command inbox, job queue, workflow engine, or scheduler;
- a generic event-sourcing JSON payload store;
- external side effects inside ledger transactions;
- authoritative-history TTL, compaction, purge, or semantic repair;
- automatic secret discovery, later secret scrubbing, or credential capture;
- EVIDENCE retrofit or mutation;
- historical adapters, Mongo projection code, or ADAPT-specific tables;
- a general temporal database or precomputed state at every historical cut;
- a blockchain/Merkle chain or tamper-proof claim; or
- runtime code, schemas, migrations, dependencies, or provider behavior in this
  design milestone.

## REBASE-02 contract

OF-01 implements rather than redefines these established distinctions:

```text
RUN              durable logical consequential objective
ATTEMPT          one bounded technical execution of a run
TECHNICAL RESULT execution completion/failure classification
OUTCOME          typed domain result plus validity
DISPOSITION      appended governed decision about outcome/use
ARTIFACT         logical identity separate from immutable content identity
COMMIT ORDER      persistence order, not market/domain/causal time
```

`C2+` runs are durably registered before the first attempt starts. Run states
are `REGISTERED`, `ACTIVE`, `SUSPENDED`, and terminal `CLOSED`. Attempt phases
are `PENDING`, `RUNNING`, and `TERMINAL`; terminal technical results are
`COMPLETED`, `FAILED`, `TIMED_OUT`, `CANCELLED`, `INTERRUPTED`, `LOST`, and
`NOT_STARTED`. Outcome validity is `VALID`, `INVALID`, `INDETERMINATE`, or
`NOT_EVALUATED`. Disposition action categories remain the standard's common
`ACCEPT`, `REJECT`, `DEFER`, `RETRY`, `INVALIDATE`, `CANCEL`, `ABANDON`,
`SUPERSEDE`, and `NO_ACTION`, with domain codes owned by domain authorities.

Consequence (`C0`–`C4`) remains orthogonal to storage/latency shape (`HOT`,
`WARM`, `COLD`). Reproducibility class (`R5`–`R0`) remains separate from
evidence strength. OF-01 records these classifications but does not infer them.

## ADAPT compatibility

The ADAPT-00 delta was classified, not merged. `9cde631` completed the external
ecosystem/license audit. `036b631` recognized BUILD 17–24 research, training,
validation, promotion, drift, and controlled-adaptation authorities as existing
foundations. OF-01 therefore supplies only generic future citation surfaces:

- durable `run_id`, `attempt_id`, `artifact_id`, and relationship references;
- configuration, data, model, policy, graph, and retrieval-snapshot identities;
- ordered commit lineage for later projections; and
- retrospective lineage qualifiers where future adapters need them.

Future experience, lesson, experiment/challenger, graph-snapshot, and retrieval-
snapshot records may cite OF-01 identities. OF-01 does not contain `experience`,
`lesson`, `agent_graph`, or `retrieval_memory` tables. External framework IDs
never become canonical IMP identities merely by being imported.

## EVIDENCE isolation

```text
EVIDENCE-01C new dependency introduced: NO
EVIDENCE semantics changed: NO
```

Existing EVIDENCE JSONL, campaign state, qualification thresholds, settlement,
and frozen records remain under their existing authority. OF-01 does not inject
fabricated run IDs into historical EVIDENCE. A future OF-02 adapter may create
explicit retrospective indexes or relationships that point to existing
EVIDENCE bytes/identities without rewriting them.

## Existing persistence and reuse audit

| Path / component | Verified behavior | Classification | OF-01 use |
|---|---|---|---|
| `src/market_platform_foundation/canonical.py` | Sorted compact UTF-8 JSON with newline; uppercase SHA-256; strict duplicate-key JSON loader | `GENERALIZE` | Preserve encoding/hash convention; add versioned profiles, non-finite-value rejection, schema normalization, and golden vectors |
| `intelligence/contracts/run_manifest.py` `RunManifestV1` | Frozen typed run configuration, validation, source/config/model/environment lineage | `GENERALIZE` | Field and serializer patterns; not universal lifecycle/attempt authority |
| `intelligence/contracts/prediction_ledger.py` `PredictionLedgerEntryV1` | Frozen preregistered settlement plan with immutable identity and temporal/policy fields | `REFERENCE_PATTERN` | Preregistration, typed validation, cutoff, and lineage semantics |
| `intelligence/outcomes/service.py` | Detects already-settled outcomes and returns prior result; separates registration and settlement | `GENERALIZE` | Idempotent outcome behavior; OF-01 command receipt becomes stronger authority |
| `intelligence/persistence/repository.py` | Backend-independent typed `Protocol`; insert/get/query boundary | `GENERALIZE` | Keep domain contracts independent of SQLite/CAS |
| `intelligence/persistence/memory.py` | Lock-protected immutable put; same ID/same canonical content is present; same ID/different content conflicts | `REUSE_DIRECTLY` (semantic pattern) | Domain-ID conflict and test-double behavior |
| `intelligence/persistence/mongo/repository.py` | Unique `_id`, schema-aware codec, immutable duplicate handling, operational queries | `ADAPT` | Non-authoritative idempotent projection target only; never authority API |
| `local_state/connection.py` | SQLite WAL, foreign keys, busy timeout, `BEGIN IMMEDIATE`, `RLock`, integrity check, backup API | `GENERALIZE` | Connection, transaction, integrity, and backup patterns; raise durability from `NORMAL` to `FULL` |
| `local_state/migrations.py` | Ordered versions, rejects newer schema, verifies final version | `GENERALIZE` | Fail-closed schema compatibility; prohibit silent semantic rewrites |
| `shadow/store.py` | SQLite WAL + `synchronous=FULL`, integrity check, insert-once typed rows, record hashes, no update/delete | `GENERALIZE` | Strongest current SQLite durability/immutability pattern; add FKs, atomic command journal, and universal records |
| `shadow/experiment.py` | Immutable run contract, insert-only lifecycle/events, state derived from event order | `REFERENCE_PATTERN` | Transition history and derived state; do not reuse integer row IDs or unjournaled per-row commits |
| `evidence01a/store.py` | JSONL append + flush + fsync; atomic replace for mutable campaign files | `REFERENCE_PATTERN` | Durable append/replace distinctions; do not reuse as universal authority |
| `evidence01b/events.py` / `store.py` | fsynced operational event/invalidation JSONL | `REFERENCE_PATTERN` | Acknowledged durability pattern; preserve EVIDENCE ownership |
| `intelligence/training/identity.py` | Versioned deterministic identities/fingerprints using canonical JSON + SHA-256; artifact byte hash | `GENERALIZE` | Profile versioning and content-hash convention; OF domain IDs remain caller-allocated, not universally content-derived |
| `intelligence/validation/artifacts.py` | Recomputes candidate artifact bytes and fails on mismatch | `REUSE_DIRECTLY` (pattern) | CAS verification before authoritative reference and integrity scans |
| REBASE-02 acceptance hash manifests / validation reports | Exact file surfaces and SHA-256 verification | `REFERENCE_PATTERN` | Backup/export manifests and acceptance evidence |

No existing component supplies all of: one caller-stable command receipt,
multi-record SQLite atomicity, a global commit cursor, typed universal
run/attempt/outcome/disposition records, and CAS metadata linkage. OF-01 must
compose and generalize the foundations rather than wrap one existing store.

## Architecture alternatives and decision

Three record topologies were considered:

1. A generic `type + JSON payload + sequence` event journal makes replay easy
   but moves relational integrity, foreign keys, schema validation, and typed
   queries into application code.
2. Typed immutable tables alone provide relational integrity but lack a single
   atomic transaction identity, global projection cursor, and ordered export
   feed.
3. Typed immutable tables plus a commit journal preserve relational authority
   and add a single transaction/order envelope.

Option 3 is selected. It is one composite authority, not two sources of truth:

```text
typed immutable tables     canonical domain content
ledger_commits             command receipt + transaction identity/order
ledger_commit_items        ordered manifest + universal record index
derived projections        disposable/rebuildable read state
```

The journal does not duplicate typed records as generic JSON.

## Authority and deployment topology

```text
LOCAL PRODUCERS
      |
      v
bounded ephemeral submission path
      |
      v
ONE LOGICAL AUTHORITATIVE WRITER
      |                    artifact command only
      |                          |
      |                          v
      |               temp -> hash -> fsync -> verify
      |                          |
      |                     atomic CAS publish
      |                          |
      +--------------------------+
      |
      v
BEGIN IMMEDIATE SQLite transaction
      |
      +-- revalidate state-dependent preconditions
      +-- insert commit envelope + ordered record index
      +-- insert typed immutable records and references
      +-- verify counts/hashes/constraints
      |
      v
COMMIT (authoritative existence point)
      |
      +--> typed reads / rebuildable current state
      +--> ordered asynchronous projections (Mongo/future)
```

One SQLite database and one CAS root form an authority deployment. Both reside
on supported local filesystems. The CAS temporary and final object locations
must share a filesystem so object publication can use atomic rename. The
SQLite WAL is a physical crash-recovery mechanism, not an authoritative journal
segment and not a portable record identity.

There is no OF-01 physical commit-journal segmentation. Logical consumers page
or export immutable commit ranges by `commit_sequence`; future immutable export
segments may cover declared sequence ranges with manifests. WAL checkpointing
does not change ledger history.

## Accepted invariants 1–50

The following are normative design constraints.

1. One accepted writer command maps to at most one authoritative commit.
2. One authoritative commit is exactly one SQLite transaction.
3. One commit may contain one or more typed immutable authoritative records.
4. Every committed authoritative domain record belongs to exactly one commit.
5. Every commit contains a deterministic ordered record manifest.
6. `commit_sequence` defines only local ledger commit order.
7. Event, available, decision, effective, start/end, and recorded clocks remain
   distinct from ledger ordering.
8. Typed relational tables carry canonical domain content.
9. The commit journal carries transaction, command-receipt, order, and integrity
   lineage, not duplicate domain payloads.
10. Current-state representations are derived and rebuildable.
11. Artifact bytes live outside SQLite in immutable CAS objects.
12. Artifact metadata and references commit atomically in SQLite.
13. Mongo and other external views are non-authoritative and replayable.
14. Idempotent retries cannot create duplicate authoritative history.
15. Authoritative historical records are never silently rewritten.
16. SQLite row IDs and physical keys are not canonical domain identities.
17. Multi-host authoritative writers are outside OF-01 v1.
18. Every writer command has a caller-stable pre-submission `command_id`; the
   same ID/hash returns its existing commit, a different hash conflicts, and
   one command ID has zero or one commits.
19. `ledger_commits` is the sole durable authoritative command receipt; rejected,
   failed, interrupted, or rolled-back pre-commit processing is telemetry only.
20. Callers allocate every new domain-record ID before submission; IDs
   participate in command hashing, survive retries/migration, and cannot be
   silently invented or reused by a different command.
21. `record_hash` covers the complete canonical identified authoritative record,
   including type, schema version, ID, and all persisted semantic fields; there
   is no universal identity-excluding semantic hash in v1.
22. Command, record, and commit hashes use deterministic schema-aware versioned
   canonicalization and a repository-compatible SHA-256 profile.
23. `ledger_commit_items` deterministically binds ordinal, record type, ID,
   schema identity, and record hash for every commit member.
24. `commit_hash` covers the complete commit envelope and ordered manifest;
   v1 has no previous-hash chain or tamper-proof claim.
25. A stable `ledger_authority_id` scopes command uniqueness; the writer owns
   collision-resistant `commit_id`, strictly increasing local
   `commit_sequence`, and `recorded_at_ns`. Sequence gaps have no meaning.
26. Domain rows are append-preserving; lifecycle/interpretation changes create
   new typed records, while mutable projections remain non-authoritative.
27. Run and attempt definitions are separate from immutable transition history;
   `CLOSED` is terminal and retry creates a new attempt.
28. Every state-dependent precondition is rechecked inside the committing
   transaction, even if preflight validation already ran.
29. One logical authoritative write coordinator serializes all local producers;
   direct SQL and multiple independent process writers are unsupported.
30. SQLite uses WAL, foreign keys, `synchronous=FULL`, busy timeout, integrity
   checks, and a supported local filesystem; low-consequence telemetry does not
   weaken authoritative durability.
31. CAS content is durably published and verified before an SQLite transaction
   may reference it.
32. CAS objects are immutable and content addressed; an orphan is housekeeping,
   while a missing/mismatched referenced object is authoritative failure.
33. Record schemas and hash interpretation are explicitly versioned; migrations
   fail closed on newer/incompatible schemas and never silently reinterpret old
   hashes or semantic history.
34. Only typed versioned semantic commands reach the authority; adapters cannot
   issue arbitrary JSON inserts or SQL.
35. Command results and failures are typed; ambiguous commit errors are resolved
   by authoritative `command_id` lookup before any retry.
36. Broker/provider/network/Mongo/workflow/LLM/remote-storage side effects never
   run inside the ledger transaction; post-commit projection failure cannot
   undo authority.
37. Projections consume `(commit_sequence, item_ordinal)` and own disposable,
   versioned cursors.
38. Mongo is an idempotent projection/export with source ledger lineage and no
   reverse authority path except a new normal writer command.
39. Current run state, latest valid disposition, attempt summaries, and artifact
   inventories are read models derived from immutable typed records.
40. Integrity checking recomputes structural, relational, record, commit, CAS,
   schema, membership, and cursor invariants and never auto-repairs semantic
   history.
41. Backups use SQLite's consistency-safe backup mechanism and bind DB snapshot,
   authority, high-water sequence, schema, CAS coverage, and manifest hashes;
   restore preserves lineage and divergent histories are not merged.
42. OF-01 v1 performs no ordinary authoritative-history purge or TTL deletion;
   corrections append, and CAS GC is limited to proven-unreferenced objects.
43. Secrets and credentials are rejected before durable write; low-entropy
   secrets are not hashed as redaction, and CAS paths are system-derived.
44. One writer `recorded_at_ns` belongs to the commit envelope; domain clocks
   remain caller-owned semantic fields and wall-clock regression does not alter
   commit order.
45. Every relationship, supersession, and correction is explicit, typed,
   identified, immutable, and references existing or co-committed endpoints;
   universal “latest timestamp wins” semantics are forbidden.
46. Replay streams commits after sequence X, optionally through Y, in sequence
   then item order; consumers reconstruct historical cuts without a general
   temporal database.
47. Submission queues are bounded, ephemeral, and non-authoritative;
   cancellation is only possible before proven commit, and graceful shutdown
   closes admission then drains/rejects and commits/rolls back cleanly.
48. Implementation planning must cover deterministic fault injection at command,
   CAS, transaction, commit-response, restart, integrity, projection, migration,
   and backup/restore boundaries.
49. Capacity is measured through latency, throughput, transaction size, WAL,
   CAS, projection lag, and integrity-check metrics; no invented SLA or premature
   distributed optimization is introduced.
50. Distributed authority requires a separately governed topology migration
   triggered by proven multi-host, failover, throughput, availability, or
   coordination needs; PostgreSQL may then be evaluated while Mongo/network-
   share SQLite/multiple primaries remain prohibited shortcuts.

## Identity and hash model

Four identity layers remain independent:

```text
COMMAND     command_id + command_hash
DOMAIN      run_id / attempt_id / outcome_id / disposition_id /
            artifact_id / relationship_id / transition_id / record_hash
LEDGER      ledger_authority_id / commit_id / commit_sequence / commit_hash
CONTENT     artifact content_hash
```

### Identity matrix

| Identity | Allocator | Stable across retry | Authoritative | Ordering semantics | Hash participation |
|---|---|---:|---:|---|---|
| `ledger_authority_id` | Authority bootstrap | Yes | Yes, ledger mechanic | None | Command uniqueness scope; commit hash |
| `command_id` | Caller before submission | Yes | On successful commit | None | Excluded from semantic command payload hash; included in commit hash |
| `command_hash` | Caller/writer from canonical command | Yes | On successful commit | None | Stored and included in commit hash |
| `run_id` | Caller | Yes | Yes | None | Command hash and run `record_hash` |
| `attempt_id` | Caller | Yes | Yes | None; `attempt_sequence` is domain order | Command hash and attempt `record_hash` |
| `outcome_id` | Caller | Yes | Yes | None | Command hash and outcome `record_hash` |
| `disposition_id` | Caller | Yes | Yes | None | Command hash and disposition `record_hash` |
| `artifact_id` | Caller | Yes | Yes | None | Command hash and artifact `record_hash` |
| `relationship_id` | Caller | Yes | Yes | None | Command hash and relationship `record_hash` |
| `transition_id` | Caller | Yes | Yes | None; transition predecessor is explicit | Command hash and transition `record_hash` |
| `record_hash` | Canonical record builder, verified by writer | Yes | Yes | None | Commit-item and commit hash |
| `content_hash` | Streaming CAS hasher | Yes for same bytes | Yes when referenced by committed artifact | None | Artifact `record_hash` |
| `commit_id` | Writer in transaction | Returned on retry | Yes | None | Commit hash |
| `commit_sequence` | Writer in transaction | Returned on retry | Yes | Strict local commit order | Commit hash |
| `commit_hash` | Writer from final envelope | Returned on retry | Yes | None | Not self-included |

Domain IDs are opaque, collision-resistant, backend-independent, log-safe, and
semantically unordered. A future implementation specification may select a
repository-compatible encoding, but neither UUID/ULID sort order nor a prefix
may become semantic order. Distinct IDs may intentionally identify otherwise
identical records. `artifact_id` is never universally derived from bytes.

### Canonicalization profiles

The design fixes separate logical profiles:

| Purpose | Profile identity | Input |
|---|---|---|
| Command | `imp-of01-command-canonical-json-v1` | command type/version, all proposed IDs, semantic fields, references, and caller preconditions; excludes transport/retry/trace/process metadata and writer results |
| Record | `imp-of01-record-canonical-json-v1` | record type/version, domain ID, and every persisted semantic field; excludes commit/SQLite mechanics |
| Commit | `imp-of01-commit-canonical-json-v1` | authority, commit identity/order/time, command identity/hash/schema, commit profile/version, and ordered item manifests |
| Hash | `imp-sha256-uppercase-hex-v1` | SHA-256 rendered as 64 uppercase hexadecimal characters, matching current IMP canonical utilities |

The implementation should generalize `canonical_bytes()` rather than fork an
incompatible serializer. It must freeze golden vectors and explicitly reject
duplicate/unknown object fields, non-finite numbers, ambiguous numeric forms,
unordered set-valued arrays, non-normalized timestamps, and unrecognized schema
versions. Times are integer nanoseconds where the owning schema uses IMP's
current convention. Decimal domain quantities use an explicit normalized
string/integer representation rather than platform-dependent float rendering.

`command_hash` does not include `command_id`; two caller identities can request
identical semantic content and remain distinct commands. The committed envelope
binds both. Caller-generated domain IDs are semantic command content and do
participate. Writer-generated `commit_id`, sequence, and time do not.

`record_hash` includes record identity. OF-01 v1 has no universal
`semantic_content_hash`. Record families may later introduce a separately named
identity-excluding equivalence hash only under an explicit domain contract.

`commit_hash` includes, in canonical order:

```text
ledger_authority_id
commit_schema_version
commit_canonicalization_profile
hash_profile
commit_id
commit_sequence
command_type
command_schema_version
command_canonicalization_profile
command_id
command_hash
recorded_at_ns
record_count
items[]: item_ordinal, record_type, record_id,
         record_schema_version, record_canonicalization_profile, record_hash
```

There is no `previous_commit_hash` in v1.

## Command model and repository boundaries

Every authoritative mutation is a typed versioned semantic command. The first
implementation specification should map commands such as:

- `RegisterRun`, `RegisterAttempt`, `AppendRunTransition`, and
  `AppendAttemptTransition`;
- `RecordOutcome` and `AppendDisposition`;
- `CloseRun`, as a composite command that binds terminal disposition and the
  terminal run transition atomically;
- `RegisterArtifact`, `AttachArtifact`, and `CreateRelationship`;
- composite commands only when one domain operation legitimately requires
  several identified records to succeed or fail together.

No public `save`, `update`, `write arbitrary record`, or `execute SQL` API is
permitted for authority history.

Conceptual backend-independent boundaries:

| Boundary | Responsibility |
|---|---|
| `AuthoritativeLedgerWriter` | Validate and atomically commit typed commands; resolve idempotent retries |
| `RunLedgerRepository` | Typed run/attempt/outcome/disposition/relationship reads, never generic mutation |
| `ArtifactRepository` | Artifact metadata/reference reads and semantic artifact commands |
| `CASStore` | Prepare, verify, publish, open, and audit immutable bytes |
| `LedgerReader` | Fetch exact records/commits and typed query results |
| `CommitStreamReader` | Stream ordered commit ranges and item manifests |
| `IntegrityChecker` | Structural, relational, hash, schema, CAS, and projection checks |
| `BackupService` | Consistent DB snapshot plus CAS coverage/inventory manifest |
| `ProjectionSource` | Read commits and records for rebuildable downstream views |

Exact module/interface names remain a written-spec decision after package-layout
review. Domain code must not import `sqlite3`, filesystem CAS paths, or Mongo
types directly.

### Command results and error taxonomy

A successful interaction returns the equivalent of:

```text
command_id, command_hash
commit_id, commit_sequence, commit_hash
created record IDs and record hashes
was_existing
```

`was_existing` describes this call, not authoritative history. Stable failure
families include `COMMAND_ID_CONFLICT`, `DOMAIN_ID_CONFLICT`,
`INVALID_COMMAND`, `UNSUPPORTED_SCHEMA`, `PRECONDITION_FAILED`,
`INVALID_TRANSITION`, `MISSING_REFERENCE`, `CAS_FAILURE`,
`TRANSIENT_STORAGE_FAILURE`/`SQLITE_BUSY`, and `INTEGRITY_FAILURE`.

Pre-commit rejection creates no ledger row. Changing a rejected command's
semantic content requires a new caller `command_id`, even though persistence
cannot detect misuse before any receipt exists. Deterministic rejection may be
retried under the same ID/hash after a legitimately external prerequisite
changes, subject to the command's hashed preconditions.

## Record and conceptual table topology

`ledger_commit_items` is both the ordered transaction manifest and the
universal typed record index. Typed rows carry `(record_type, record_id)` and a
deferred composite foreign key to their manifest item. `record_type` is fixed by
a `CHECK` constraint in each typed table. Relationships use the same composite
index for typed endpoint integrity. The writer and integrity checker prove the
reverse invariant that every item resolves to exactly one typed table row;
SQLite cannot express a foreign key from one polymorphic index row to one of
many typed tables without weakening the typed design.

### Ledger mechanics

| Table | Conceptual fields and constraints |
|---|---|
| `ledger_metadata` | Singleton immutable `ledger_authority_id`, authority schema/version profiles, creation time, deployment compatibility; mutable non-domain activation metadata only where restore procedure requires it |
| `ledger_commits` | `commit_sequence` primary/order key; unique `commit_id`; authority-scoped unique `command_id`; command type/schema/profile/hash; `recorded_at_ns`; commit schema/profile; `record_count`; `commit_hash` |
| `ledger_commit_items` | `(commit_sequence, item_ordinal)` primary key; unique `(record_type, record_id)`; record schema/profile/hash; foreign key to commit; item ordinals contiguous from zero by writer/integrity rule |

`ledger_metadata` is ledger bootstrap mechanics, not a domain record. Authority
initialization occurs before the writer accepts commands. It is included in
backup and integrity manifests and may not be silently regenerated on restore.

### Domain records

| Record family | Core semantic content |
|---|---|
| `runs` | `run_id`, schema, immutable objective/operation class, consequence and reproducibility declarations, initiator/trigger, registration time, attempt-concurrency contract, retrospective/legacy qualifier, attribution references, retention/sensitivity classifications |
| `attempts` | `attempt_id`, `run_id`, one-based `attempt_sequence`, invocation and environment context, optional predecessor attempt/checkpoint, declared parallel group when permitted, semantic start/end expectations, retention/sensitivity |
| `run_transitions` | `transition_id`, `run_id`, explicit predecessor transition, from/to state, effective/domain time, actor/policy/reason, terminality facts |
| `attempt_transitions` | `transition_id`, `attempt_id`, explicit predecessor, phase change, terminal technical result when terminal, reason/failure family, domain start/end time, cancellation/interruption/loss evidence |
| `outcomes` | `outcome_id`, run and optional attempt/protocol references, typed domain result reference or bounded payload, validity, evaluation/effective time, limitations, explicit superseded-outcome reference where applicable |
| `dispositions` | `disposition_id`, run/outcome target, decision time, decision authority/policy, action category, domain code, limitations, explicit prior/superseded disposition reference |
| `artifacts` | `artifact_id`, logical role/name, immutable `content_hash`, hash profile, byte size, media/content type, producer run/attempt, completeness, producer terminal state, validation state, use restriction, mutability and retention classes, redaction/sensitivity, system-derived CAS locator profile |
| `relationships` | `relationship_id`, typed source endpoint, relation type, typed target endpoint, domain time, metadata allowed by relation schema, explicit acyclicity class/policy |
| `source_attributions` | caller ID, run, repository/root identity, base revision, `CLEAN_COMMITTED`/`DIRTY_ATTRIBUTABLE`/`UNATTRIBUTABLE`, scoped changed paths manifest, capsule artifact, and outside-scope proof references |
| `provenance_references` | caller ID, run/attempt, typed configuration/data/model/policy/environment/checkpoint/graph/retrieval identity, canonical version/hash, cutoff or coverage fields, optional artifact relationship |

Each row also carries its record schema/profile/hash and manifest-membership
foreign key. Bounded structured metadata is allowed only when its typed schema
defines permitted keys and canonicalization; it is not an escape hatch for
arbitrary JSON authority.

### Record matrix

| Record family | Domain ID | Immutable | Primary references | Hash | Created by | Current state derived from |
|---|---|---:|---|---|---|---|
| Run | `run_id` | Yes | initiator, source/provenance refs | Complete run record | `RegisterRun` | Run transitions + terminal disposition |
| Attempt | `attempt_id` | Yes | run, predecessor/checkpoint | Complete attempt record | `RegisterAttempt` | Attempt transitions |
| Run transition | `transition_id` | Yes | run, prior transition | Complete transition | `AppendRunTransition` | Ordered explicit transition chain |
| Attempt transition | `transition_id` | Yes | attempt, prior transition | Complete transition | `AppendAttemptTransition` | Ordered explicit transition chain |
| Outcome | `outcome_id` | Yes | run, attempt/protocol, superseded outcome | Complete outcome | `RecordOutcome` | Explicit outcome/supersession history |
| Disposition | `disposition_id` | Yes | run/outcome, prior disposition | Complete disposition | `AppendDisposition` | Explicit disposition chain/policy query |
| Artifact | `artifact_id` | Yes | producer run/attempt, CAS content | Complete metadata record | `RegisterArtifact` or composite command | Artifact relationships and validation records |
| Relationship | `relationship_id` | Yes | typed source and target | Complete relationship | `CreateRelationship` | Relationship set; no mutable edge |
| Source attribution | `source_attribution_id` | Yes | run and capsule/proof artifacts | Complete attribution | `RegisterRun`/attribution command | Attribution record set |
| Provenance reference | `provenance_ref_id` | Yes | run/attempt and external canonical identity | Complete reference | Run/attempt registration or attach command | Provenance record set |
| Ledger commit | `commit_id` | Yes after commit | authority and command | Complete commit envelope | Writer | Not a domain state |
| Ledger commit item | commit + ordinal | Yes after commit | commit and typed record | Manifest item included in commit hash | Writer | Not a domain state |

Ledger mechanics and projections are not domain records. Projection rows may be
mutated/rebuilt and do not appear in commit items.

## Run, attempt, outcome, and disposition semantics

Run-defining fields are immutable. Material objective, source, configuration,
data, model/policy, protocol, or authority changes create a new run with an
explicit `RESUMES_FROM` or `SUPERSEDES` relationship where applicable. A closed
run cannot receive attempts or return to an earlier state.

A transition to `CLOSED` is valid only when its terminal disposition already
exists or is co-committed by `CloseRun`; the close command records the exact
disposition reference. A zero-attempt run closes only as cancelled, superseded,
or abandoned, with `NOT_EVALUATED` or an explicitly declared partial outcome.
The close transaction cannot leave the run terminal without its terminal
decision history.

For `C2+`, `RegisterRun` must commit while the run remains `REGISTERED` before
any technical execution starts. An attempt definition may be preregistered as
`PENDING`, but the transition that establishes actual execution start is a
later committed command before the governed executor claims the attempt is
running. This preserves the durable-before-attempt boundary.

Attempts default to `SEQUENTIAL`. A run contract may instead declare
`EXPLICIT_PARALLEL` and the bounded parallel-attempt rules. Under sequential
mode, starting an attempt requires no existing nonterminal attempt. Under
parallel mode, every execution has its own caller ID and state, and the command
declares its parallel group/capacity precondition. Attempt sequence remains
one-based and unique within the run; it is domain order, not commit order.
These checks occur inside the transaction.

An attempt terminal transition records technical result and reason family.
Later success never changes an earlier failed attempt. `LOST` is appended by a
reconciler when termination evidence is missing; it is not guessed by the
original process. Attempt start and end times are authoritative semantic fields
of the first `RUNNING` and terminal transitions respectively; the complete
attempt view joins them to the immutable attempt definition. A pending attempt
therefore has no fabricated end time, and terminalization never updates the
attempt row.

Outcome validity is independent of analytical sign. A valid negative or
underperforming result remains `VALID`. Corrections or reinterpretations append
a new outcome with explicit supersession/correction lineage. Dispositions are
separate records with authority, policy, action, domain code, decision time,
and limitations. “Current disposition” is a policy-specific derived query, not
a mutable column or universal latest-timestamp rule.

Relationship types declare whether cycles are allowed. Parent/root,
`TRIGGERED_BY`, `RESUMES_FROM`, and `SUPERSEDES` classes are acyclic and checked
inside the transaction using the existing graph plus co-committed edges.
`RELATED_TO` may cycle. Typed endpoints may exist before the command or be valid
co-committed records.

## Source attribution and dirty-source capsules

`CLEAN_COMMITTED` records repository identity and revision. A
`DIRTY_ATTRIBUTABLE` source attribution requires:

1. known repository/root and base revision;
2. a normalized scope declaration and changed-path list;
3. a CAS artifact containing a deterministic diff/content manifest sufficient
   to recover or hash every relevant changed file; and
4. a proof manifest showing unrelated dirty paths lie outside the declared
   operation scope.

The capsule is an ordinary immutable artifact with role
`DIRTY_SOURCE_CAPSULE`; its manifest is canonical and contains normalized
repository-relative paths, content hashes, byte lengths, change kinds, and
base revision. It must reject absolute paths, traversal, secrets, and
unbounded environment capture. Binary relevant files are stored or referenced
by CAS content hash, not embedded as lossy textual diffs. If scope closure or
content capture cannot be proved, the source state is `UNATTRIBUTABLE`.

Multiple source roots use multiple attribution records. The run record does not
pretend one Git SHA covers a multi-repository operation.

## Exact transaction lifecycle

The authoritative writer processes one command as follows:

1. Validate the command type/schema, caller IDs, static domain fields,
   canonicalization profile, sensitivity rules, and caller preconditions.
2. Compute/recompute `command_hash`; reject a mismatch in the submitted
   envelope.
3. Look up `command_id`. Existing same hash returns the original result;
   existing different hash fails closed.
4. For new artifact bytes, prepare and publish CAS objects before opening the
   database transaction. Existing objects are byte/hash verified as policy
   requires.
5. Enter the single-writer critical section and execute `BEGIN IMMEDIATE`.
6. Repeat `command_id` lookup to resolve a duplicate race.
7. Revalidate all current-authority preconditions: domain-ID absence,
   references, state/transition legality, expected predecessor, attempt
   concurrency, terminality, and relationship graph rules.
8. Allocate `commit_id`, next local `commit_sequence`, and one UTC
   `recorded_at_ns` for the envelope.
9. Canonicalize all proposed domain records and recompute their hashes.
10. Construct the deterministic item order from the typed command contract,
    not dict iteration or SQL insertion order.
11. Compute the final commit envelope/hash in memory, then insert the final
    commit, items, typed rows, and relationships. Deferred foreign keys allow
    co-committed graphs without weakening referential integrity.
12. Verify item count, contiguous ordinals, exact record membership, hashes,
    and constraints before commit.
13. `COMMIT`. Only now do authoritative records and the command receipt exist.
14. Return the committed result. Projection and telemetry continue outside the
    transaction.

`BEGIN IMMEDIATE` plus the one-writer abstraction makes allocation and
state-dependent checks deterministic without relying on lock contention as the
sequencer. The implementation specification may select `MAX(sequence)+1` or an
equivalent local counter inside the transaction; only committed sequence values
are semantic, and gaps are allowed.

If commit acknowledgement is ambiguous, the writer reopens/queries
`ledger_commits` by `command_id`. A matching receipt returns success with
`was_existing=true`; absence permits same-ID/same-hash retry; a different hash
is conflict. Blind retry is prohibited.

### Command-idempotency matrix

| Situation | Authoritative result |
|---|---|
| No receipt + valid command | Execute once; create one commit |
| Same ID + same hash + committed | Return original commit/result; no mutation |
| Same ID + different hash | `COMMAND_ID_CONFLICT`; no mutation |
| Different ID + reused new-record domain ID | `DOMAIN_ID_CONFLICT`, even when content matches |
| Same ID/hash after pre-commit failure | Eligible to execute again; no prior receipt exists |
| Same ID/hash after COMMIT but response loss | Resolve receipt and return original commit |
| Concurrent duplicate submissions | Serialized first commit wins; duplicate returns it |
| Corrected rejected payload | Caller must allocate a new `command_id` |

## Crash-boundary matrix

| Failure point | CAS state | SQLite state | Retry result | Repair needed |
|---|---|---|---|---|
| Before CAS write | No object | No receipt/records | Same command may retry | None |
| During CAS temp write | Unpublished temp/partial | No receipt/records | Same command may retry | Temp cleanup |
| After CAS publish, before transaction | Valid unreferenced object | No receipt/records | Retry reuses verified object | Orphan scan only if command never returns |
| During typed/manifest insertion | Published object if applicable | Transaction rolls back wholly | Same command may retry | Possible orphan only |
| During commit-envelope creation | Published object if applicable | No committed receipt | Same command may retry | Possible orphan only |
| Immediately before COMMIT | Published object if applicable | Transaction rolls back on crash recovery | Lookup absent, then retry | Possible orphan only |
| COMMIT succeeds, response lost | Referenced object published | Complete records + receipt | Lookup returns original commit | None |
| After COMMIT, projection fails | Referenced object published | Complete authority | Return success; projector resumes from prior cursor | Rebuild/resume projection |

Under the supported filesystem/SQLite failure model, this ordering prevents a
committed artifact reference to unpublished bytes, duplicate mutation from
retry, and partial multi-record commit. It cannot protect against storage media
that falsely acknowledges durable writes; deployment and backup policy own
that residual risk.

## SQLite durability, concurrency, and constraints

The v1 connection profile is at least:

```text
PRAGMA journal_mode = WAL
PRAGMA synchronous = FULL
PRAGMA foreign_keys = ON
PRAGMA busy_timeout = governed bounded value
```

Writer transactions use `BEGIN IMMEDIATE`. Startup performs schema-compatibility
and `integrity_check`/appropriate quick checks before enabling writes. A newer
or unsupported schema, failed integrity check, or missing authority metadata
opens fail-closed for writes. Read-only forensic access may be separately
provided without claiming a healthy authority.

SQLite constraints prove what they can:

- primary/unique domain and ledger identities;
- authority-scoped unique commands;
- non-null schema/profile/hash fields;
- run-scoped unique one-based attempt sequences;
- commit-scoped unique/valid item ordinals and unique record membership;
- typed record-to-item and ordinary typed foreign keys;
- endpoint existence through the typed record index;
- closed enum/check constraints and nonnegative sizes/times where meaningful.

Application validation supplements, but does not replace, constraints for graph
acyclicity, transition machines, canonical hash recomputation, reverse
polymorphic item resolution, and policy-specific current-state rules.

Many local threads may submit concurrently to a bounded in-process queue.
Exactly one coordinator executes commands. Readers use separate local read
connections and WAL snapshots. Multiple processes may not independently write
the same authority. A process-local/OS file lock provides same-host accidental
double-writer defense, but v1 does not claim distributed split-brain prevention.

Backpressure rejects or times out admission before authority when the queue is
full. Queue admission is not a receipt. C0/C1 high-volume telemetry should
normally use observability buffering rather than one FULL-synchronous OF commit
per event. C3/C4 governing transitions wait for authoritative acknowledgement
where the standard requires durable evidence/authority before acceptance or
side effect.

Cancellation before the writer proves commit may stop a queued command or roll
back an active transaction. After commit, cancellation cannot erase it. A race
is resolved by command receipt lookup. Shutdown stops admissions, drains or
explicitly rejects queued work, finishes or rolls back the active transaction,
checkpoints/closes SQLite according to policy, and leaves no half-authoritative
state.

## Schema versioning and migrations

Three versions remain explicit:

- physical database schema version;
- typed command/record schema version; and
- canonicalization/hash profile version.

Startup migrations are ordered, transactional where SQLite permits, and
reject unknown newer versions. Safe physical additions may add tables, indexes,
nullable/derived columns, or projections. They do not recanonicalize historical
records, change stored record/commit hashes, or silently reinterpret fields.

New writes may use a newer supported record schema while historical v1 records
remain v1. Typed readers dispatch by schema version. Read-side upcasters may
produce a current interpretation but never masquerade it as the original
committed record or hash. A semantic rewrite requires a separately governed
migration that appends explicit migrated/correction records or establishes a
new authority lineage; it is not routine startup migration.

## CAS lifecycle and artifact semantics

The CAS API accepts bytes/stream plus expected metadata, not caller-chosen
paths. A v1 publish operation:

1. creates an exclusive temporary file inside the CAS filesystem;
2. streams bytes while computing SHA-256 and size;
3. flushes and fsyncs the file according to platform policy;
4. verifies any caller-declared content identity;
5. derives a normalized path such as
   `objects/<hash-profile>/<prefix>/<content-hash>`;
6. atomically renames into place, or verifies an already-existing immutable
   object; and
7. performs the SQLite reference transaction only after publish success.

Directory-entry durability differs by platform. The written specification and
acceptance tests must state the exact Windows/POSIX guarantees and must not
claim directory fsync where the runtime cannot perform it. A post-publish
existence/hash verification is required before DB reference.

Artifact metadata records logical role independently from bytes. Two artifact
IDs may share one content hash. Large bytes never become SQLite BLOB authority.
Completeness is `PARTIAL`, `COMPLETE`, or `UNKNOWN`; producer attempt/terminal
state, validation state, and use restrictions prevent partial output from
satisfying accepted-output policy by accident.

An orphan scanner compares CAS inventory to authoritative artifact content
references. Unreferenced objects are `HOUSEKEEPING`, not domain history.
Deletion is disabled by default; a future GC operation may delete only objects
proven unreferenced at a stable ledger high-water mark and outside backup,
restore, quarantine, and retention holds. It never deletes artifact metadata or
referenced content. Missing or hash-mismatched referenced bytes are
`AUTHORITATIVE_FATAL` and trigger write disable/quarantine, not automatic repair.

## Read model, queries, and projections

Primary reads query typed tables; commit replay does not require decoding a
generic payload. Initial indexes should support:

- commit ID, command ID, and commit-sequence ranges;
- record type/ID and commit item order;
- attempts by `(run_id, attempt_sequence)` and active-state derivation;
- transitions by target and predecessor/effective time;
- outcomes/dispositions by run, attempt/outcome target, and explicit lineage;
- artifacts by content hash, producer run/attempt, role, completeness, and
  retention class;
- relationships by typed source, target, and relation type; and
- source/provenance references by run and reference kind/identity.

Current-state queries may be SQLite views, typed query logic, or materialized
projection tables. A materialized projection is clearly named/marked derived,
is excluded from commit items/hashes/backups as authority, and can be dropped
and rebuilt. Authoritative history remains sufficient to reconstruct it.

The portable replay API is `stream_commits(after_sequence, through_sequence?)`.
It emits commits in sequence order and records in item-ordinal order. A
consumer records its own projection identity/version, source authority,
`last_applied_commit_sequence`, and `last_applied_commit_id`. The cursor advances
only after the target projection durably applies the commit. Deleting a cursor
or projection triggers replay from a declared safe point.

Mongo documents preserve source authority, commit ID/sequence, record ID/hash,
and projection version. Projection writes are idempotent. Mongo loss is
`REBUILDABLE`; Mongo never implements the authoritative writer interface. Any
requested reverse change becomes a new typed OF command.

Historical/legacy adapters belong to OF-02. OF-01 only provides explicit
`NATIVE` versus `RETROSPECTIVE_INDEX` provenance and completeness qualifiers.
Adapters must not fabricate unavailable source state, domain time, attempt
history, or run IDs inside frozen artifacts. They create new retrospective
records/relationships whose own recorded time and limitations are truthful.

## Integrity, corruption, and repair boundaries

### Integrity matrix

| Check | Failure class | Permitted response |
|---|---|---|
| SQLite `integrity_check` / structural health | `AUTHORITATIVE_FATAL` | Disable writes; preserve files; restore/forensic process |
| Foreign keys / typed endpoint integrity | `AUTHORITATIVE_FATAL` | Disable writes; no auto-repair |
| Command/commit/domain uniqueness | `AUTHORITATIVE_FATAL` | Disable writes; investigate authority corruption |
| Every typed record has exactly one item | `AUTHORITATIVE_FATAL` | Disable writes |
| Every item resolves to exactly one typed record | `AUTHORITATIVE_FATAL` | Disable writes |
| Record hash recomputation | `AUTHORITATIVE_FATAL` | Disable writes; no semantic rewrite |
| Item count and contiguous deterministic ordinals | `AUTHORITATIVE_FATAL` | Disable writes |
| Commit hash recomputation | `AUTHORITATIVE_FATAL` | Disable writes |
| Supported schema/profile | `AUTHORITATIVE_FATAL` for write compatibility | Read-only forensic/export if safe |
| Referenced CAS object exists and hashes correctly | `AUTHORITATIVE_FATAL` | Quarantine/restore object from verified backup; never invent bytes |
| Unreferenced CAS object | `HOUSEKEEPING` | Quarantine or later safe GC |
| Projection cursor points beyond/into wrong authority | `REBUILDABLE` | Reset/rebuild projection |
| Projection content stale/missing | `REBUILDABLE` | Replay commits |

Integrity checking has fast startup/periodic and full offline/deep modes. Full
mode recomputes all record and commit hashes plus CAS bytes. Checks themselves
produce operational reports/artifacts; they do not mutate authoritative
history. A verified backup may restore identical missing CAS bytes because the
content hash proves identity, but database semantic repair is a governed
recovery/migration action, not automatic healing.

## Backup, restore, authority lineage, and fork prevention

An active database backup uses Python/SQLite's backup API or a proven equivalent
that captures a consistent snapshot; raw copying of an active DB/WAL pair is not
the authoritative procedure. A complete backup manifest binds:

```text
ledger_authority_id
database schema/version and hash profiles
highest included commit sequence and ID/hash
SQLite snapshot hash/size
CAS inventory and coverage through that high-water mark
each included CAS content hash/size or verified external backup reference
backup time, tool/profile identity, limitations
```

The backup procedure first creates and verifies the consistent SQLite snapshot,
fixing its highest included commit sequence. It enumerates artifact content
hashes from that snapshot—not from the moving live database—and then copies or
verifies exactly those immutable CAS objects. Objects published concurrently
but not referenced by the snapshot are harmless extras and are excluded from
coverage. The final manifest is published only after every snapshot-referenced
object is covered and verified.

Restore verifies the manifest, DB integrity, commit/record hashes, and CAS
coverage before write enable. Recovery of the same authority preserves all
identities and sequences. Analysis/development copies open read-only by default
or receive a new authority identity before any writes. Write activation is an
explicit governed recovery/bootstrap operation and a same-host exclusive lock
prevents accidental concurrent local activation.

OF-01 cannot technically prevent two isolated hosts from both being manually
activated from one backup; operational custody is therefore part of v1's
single-authority safety model. If divergent copies accept writes, automatic
merge/reconciliation is unsupported. One lineage must be selected through a
future governed recovery/migration process; the other remains historical or is
reidentified as a non-authoritative fork.

## Retention, redaction, and secrets

Records carry the REBASE-02 retention classes
`RET_EPHEMERAL`, `RET_BOUNDED_DIAGNOSTIC`, `RET_OPERATIONAL`,
`RET_REPRODUCIBILITY`, `RET_HISTORICAL_EVIDENCE`, and
`RET_AUTHORITY_POLICY`. OF-01 stores classification and legal/operational hold
references but defines no durations and performs no domain-history deletion.

Corrections append. Redaction is schema/boundary validation before hashing and
durable write. Raw credentials, tokens, passwords, private keys, and arbitrary
environment dumps are prohibited. Low-entropy secrets are represented only by
non-sensitive provider/reference identity or a redaction marker, never by a
reversible/guessable hash. If prohibited sensitive content commits despite the
boundary, ordinary deletion is not a permitted silent fix; incident response
and a separately governed redaction/migration procedure decide the authority
consequences.

## Failure taxonomy and operational behavior

| Family | Examples | Authority behavior |
|---|---|---|
| Command contract | invalid schema, unknown fields, ID misuse | Reject pre-commit; telemetry only |
| Preconditions | missing reference, state changed, closed run, parallel attempt forbidden | Reject/rollback; same command may retry only if semantics/preconditions permit |
| Identity | command hash conflict, domain ID collision | Fail closed; never return another command's result |
| CAS | temp/publish/hash/path failure | No DB reference; retry or operator action |
| Transient storage | busy/temporary I/O before commit | Roll back; resolve receipt then retry |
| Ambiguous commit | response/connection failure around COMMIT | Query by `command_id`; never blind retry |
| Authoritative integrity | DB/FK/record/commit/CAS mismatch | Disable writes, preserve evidence, recover from verified backup |
| Projection | Mongo unavailable, cursor stale | Authority remains valid; retry/rebuild asynchronously |
| Capacity/backpressure | bounded queue full, commit latency high | Reject/defer admission; measure; do not weaken durability silently |
| External side effect | response/projector/provider failure after commit | Commit remains authoritative; reconcile in owning subsystem |

## Performance and hot-path protection

OF-01 introduces no latency or throughput SLA. Implementation acceptance records
commit latency distribution, command throughput, records/bytes per transaction,
queue depth/rejection, WAL size/checkpoint behavior, CAS publish cost, DB/CAS
growth, projection lag, and fast/full integrity-check duration.

The serialized writer remains until measurement proves it insufficient. C0/C1
hot telemetry uses the observability path unless an operation contract requires
a durable run record. No per-span database commit, giant synchronous provenance
payload, Mongo call, training, graph traversal, vector indexing, or LLM call is
placed in the authoritative transaction. C4 authority-critical records still
must be durably acknowledged before the owning side effect where canonical
policy requires it.

## Test and fault-injection strategy

The future implementation specification must require:

- canonical command/record/commit golden vectors, unknown/duplicate field and
  non-finite-number rejection;
- typed command schema and domain-ID property tests using existing dependencies
  only;
- same command success/retry/conflict and reused domain-ID tests;
- multi-record atomicity and halfway constraint-failure rollback;
- run/attempt lifecycle, terminal closure, sequential/explicit-parallel rules,
  outcome validity, and append-only disposition tests;
- concurrent local producer serialization and duplicate submission races;
- state-precondition TOCTOU tests inside `BEGIN IMMEDIATE`;
- every crash point in the crash-boundary matrix, including process restart;
- CAS duplicate-content, mismatch, temp, orphan, missing-reference, traversal,
  and partial-output tests;
- record/commit/manifest/FK/schema corruption detection with original files
  preserved;
- migration compatibility and unknown-newer-schema fail-closed tests;
- projection idempotency, lag, failure, resume, reset, and full rebuild;
- backup/restore high-water, identity, hash, CAS coverage, and read-only-fork
  behavior; and
- performance measurement without pass/fail thresholds invented by this design.

No new test dependency is authorized by the design. The implementation plan may
use property-style loops/fixtures in the standard library unless an already
approved dependency provides the capability.

## Backend portability matrix

| Concept | IMP-owned | SQLite-specific | CAS-specific | Mongo-specific | Portable to future authority |
|---|---:|---:|---:|---:|---:|
| Command/domain/record schemas and IDs | Yes | No | No | No | Yes |
| Canonicalization and hashes | Yes | No | Byte hashing only | No | Yes |
| Ledger authority/commit identity | Yes | No | No | Source lineage only | Yes |
| Commit sequence semantics | Yes, local-authority order | Allocation/storage in v1 | No | Projection cursor only | Yes with migration rules |
| Typed relations/constraints | Yes | SQL realization | No | Derived documents | Yes |
| `BEGIN IMMEDIATE`, WAL, busy timeout | No | Yes | No | No | No |
| SQLite rowid/WAL frame/page | No | Yes, noncanonical | No | No | No |
| Artifact logical metadata | Yes | Stored in v1 | Locator profile | Projected | Yes |
| Artifact bytes/content hash | Content identity is IMP-owned | No BLOB authority | Physical realization | Optional export only | Yes |
| CAS pathname/inode/temp mechanics | No | No | Yes, noncanonical | No | No |
| Mongo `_id` and indexes | No | No | No | Yes, noncanonical | No |
| Projection identity/cursor contract | Yes | Optional local state | No | Mongo realization | Yes |
| Current-state views | Semantics are IMP-owned | Initial realization | No | Optional realization | Yes/rebuildable |

A future PostgreSQL authority implements the same typed command/domain/stream
contracts. Migration must explicitly preserve authority lineage and decide how
the original commit sequence continues; it cannot silently assign new domain,
command, record, or commit identities.

## REBASE-02 compliance matrix

| Requirement | OF-01 design realization |
|---|---|
| Run | Immutable run definition plus append-only run transitions |
| Attempt/execution | Identified one-based attempts, sequential default, explicit parallel contract, transition-based phase/technical result |
| Outcome/validity | Typed immutable outcomes with independent validity and supersession lineage |
| Disposition | Separate append-only authority/policy/action/domain-code decisions |
| Relationships | Identified typed endpoints; acyclicity by relationship class; related cycles permitted |
| Initiator/trigger/parent/root | Run fields plus typed relationships and derived root traversal |
| Source identity | Multi-root source-attribution records with three standard source states |
| Dirty attribution | CAS capsule + scoped paths/content hashes + outside-scope proof |
| Environment | Declared versus observed, material non-secret typed provenance references |
| Configuration | Canonical identity/hash of effective non-secret fields |
| Data/model/policy | Typed references with IDs, hashes, cutoffs, coverage, versions, limitations |
| Temporal identity | Domain clocks/cutoff bundles separate from writer time and commit order |
| Artifact identity | Logical `artifact_id` separate from byte `content_hash`; completeness/use restriction recorded |
| Mutability/append semantics | Immutable typed history; SQLite logical append; CAS immutable; projections rebuildable |
| Durability/crash consistency | WAL/FULL/transaction plus publish-before-reference CAS asymmetry |
| Retention | Standard class/hold hooks; no v1 authoritative purge |
| Redaction/secrets | Schema rejection before durable write; no secret hashing or later-scrub claim |
| Retry/idempotency | New attempt for technical retry; command receipt prevents duplicate mutation |
| Resume/checkpoint | Typed checkpoint provenance and predecessor attempt; compatibility precondition; new run on material change |
| Cancellation/partial output | Pre/post-commit boundary plus explicit attempt result/artifact completeness |
| Consequence classes | Stored as declared; C2+ preregistration and C3/C4 durability gates preserved |
| Reproducibility/evidence | Records R/E declarations and required attribution without conflating them |
| Observability | Trace/correlation references may attach; telemetry IDs never replace domain/ledger IDs |
| Legacy compatibility | Retrospective records/limitations for later OF-02; no fabricated retrofit |
| EVIDENCE | Reference/index later only; no dependency or semantic change |
| ADAPT | Generic run/artifact/provenance cites only; no domain-specific records |

Unresolved REBASE-02 requirement: none.

## Implementation decomposition for the next specification

The written-spec review should harden and then decompose implementation into
independently testable surfaces:

1. canonical contract vocabulary, IDs, profile registry, and golden vectors;
2. typed commands/records and backend-independent read/write protocols;
3. SQLite schema/migrations, connection profile, writer serialization, and
   transactional command engine;
4. run/attempt transitions, outcomes, dispositions, relationships, and query
   semantics;
5. CAS publish/verify/inventory plus artifact commands;
6. integrity checker and corruption quarantine;
7. commit streaming, current-state views, and projection cursor contract;
8. backup/restore/authority activation and fork-safety procedures;
9. historical adapter boundary stubs only where OF-01 needs a target contract;
10. fault-injection, full validation, performance evidence, and acceptance
    artifacts.

This is decomposition guidance, not implementation approval. The implementation
specification must identify exact modules, schema DDL, transaction APIs, tests,
and validation commands after written-spec hardening.

## Acceptance criteria for future implementation

OF-01 runtime acceptance will require evidence that:

- all accepted invariants 1–50 are implemented without weakening REBASE-02;
- every supported command is atomic, idempotent, typed, and backend independent;
- every authoritative domain row belongs to one manifest and all manifest items
  resolve exactly;
- record and commit hashes reproduce from canonical golden vectors;
- C2+ run preregistration and terminal/no-reopen rules fail closed;
- duplicate, conflict, concurrent, crash, and ambiguous-commit tests pass;
- CAS ordering never commits a missing unpublished object reference;
- integrity failures disable writes without silently rewriting history;
- backup/restore preserves authority, IDs, sequence, hashes, and CAS coverage;
- projections rebuild from the commit stream and remain non-authoritative;
- no runtime dependency, EVIDENCE, prediction/settlement, provider, risk, or
  execution semantic change occurs outside the accepted implementation surface;
- changed validation passes and any manifest-required full suite passes; and
- acceptance artifacts accurately hash the complete accepted implementation
  surface.

## Known limitations

- Single-host operational custody, an OS lock, and explicit activation reduce
  accidental forks but cannot prevent two isolated restored hosts from being
  manually promoted; divergent histories are unsupported.
- SQLite commit order is local to one authority lineage and is not a cross-
  authority total order.
- The exact Windows directory-entry durability guarantee for CAS publication
  must be frozen and fault-tested in the written specification; this design does
  not overclaim POSIX directory fsync semantics on Windows.
- No retention durations or authoritative purge mechanism exist in v1.
- No physical commit-journal segmentation exists beyond SQLite's noncanonical
  WAL; immutable export segmentation is future work.
- Polymorphic manifest-to-typed-row reverse integrity requires writer and
  integrity-check enforcement in addition to typed-row foreign keys.
- No automatic semantic repair or divergent-history merge is provided.
- Performance capacity is intentionally unquantified until implementation
  measurement.
- Historical adapters and Mongo projection are compatible targets, not part of
  this design milestone's runtime output.

## Written-spec review questions

These are hardening checks, not reopened architecture choices:

1. Do the exact typed fields and relation vocabularies cover every mandatory
   REBASE-02 applicability-matrix field without arbitrary JSON escape hatches?
2. Are command/record/commit canonical bytes and golden vectors fully closed,
   especially numbers, timestamps, optional fields, and ordered/set arrays?
3. Does the proposed DDL prove the maximum possible subset of item membership,
   endpoint, attempt-sequence, and transition constraints?
4. Is the Windows/POSIX CAS publish acknowledgement accurately stated and
   fault-tested?
5. Can the backup manifest prove CAS coverage exactly at its SQLite high-water
   mark, including concurrent post-snapshot object publication?
6. Are run closure, zero-attempt closure, sequential/parallel attempts,
   checkpoint resume, lost attempts, outcome correction, and disposition
   supersession represented without mutable status authority?
7. Are integrity/quarantine, read-only forensic mode, and explicit restore
   activation operationally safe and testable?
8. Does the implementation surface remain small enough to accept in one clean
   milestone, or should delivery be staged behind internal noncanonical feature
   gates while preserving one acceptance boundary?

None of these questions authorizes changing Invariants 1–50 without a
demonstrated conflict with a higher canonical authority.

## Next gate

```text
IMP-OF-01 Written-Spec Review & Hardening
```

No runtime implementation begins until the written specification is reviewed,
semantically hardened, and explicitly approved for clean-worktree
implementation.

IMP_OF_01_DESIGN_READY_FOR_WRITTEN_SPEC_REVIEW
