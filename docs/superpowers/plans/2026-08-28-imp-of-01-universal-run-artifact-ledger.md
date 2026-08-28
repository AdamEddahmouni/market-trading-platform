# IMP-OF-01 Universal Run and Artifact Ledger Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the single-writer SQLite/CAS OF-01 authority and its complete, tested subsystem operations model without widening any domain authority.

**Architecture:** Immutable typed command/record contracts feed one serialized `AuthoritativeLedgerWriter`; each accepted command becomes one SQLite transaction recorded by a commit envelope and ordered item manifest. Artifact bytes publish to a verified local CAS before reference, while readers, current state, Mongo, and operational evidence remain derived or non-authoritative.

**Tech Stack:** CPython 3.11 standard library (`dataclasses`, `enum`, `hashlib`, `json`, `sqlite3`, `pathlib`, `threading`, `queue`, `uuid`, `argparse`, `unittest`), SQLite WAL/STRICT tables, local filesystem CAS, existing validation harness.

## Global Constraints

- Preserve Invariants 1–75 from the controlling implementation specification.
- One supported local SQLite authority, one CAS root, one active writer process; no network-share SQLite or multi-primary behavior.
- Every normal mutation uses a typed command and one `BEGIN IMMEDIATE` transaction; no generic save/update/SQL API.
- Caller-stable command/domain IDs and canonical semantic content survive retries; ambiguous commits resolve by receipt lookup.
- Record hashes include identity; no general semantic-content hash and no previous-commit hash.
- CAS publishes and verifies before SQLite reference; referenced loss/mismatch is fatal, orphan content is housekeeping.
- Mongo/current state are rebuildable projections and never reverse authority.
- No EVIDENCE, provider, prediction/settlement, risk, execution, broker, promotion, or global OF-03 registry changes.
- No new dependency; all tests use disposable SQLite/CAS roots and distinct authority IDs.
- Numeric tuning defaults require measured justification, bounded configuration, and no invented SLA/alert threshold.
- After each task run focused tests then `tools/validate.py changed --explain`; run FULL once at final acceptance if the manifest requires it.

---

### Task 1: IDs, error taxonomy, canonical profiles, and golden vectors

**Files:**
- Create: `src/market_platform_foundation/of01/__init__.py`
- Create: `src/market_platform_foundation/of01/ids.py`
- Create: `src/market_platform_foundation/of01/errors.py`
- Create: `src/market_platform_foundation/of01/canonical.py`
- Create: `tests/of01/__init__.py`
- Create: `tests/of01/test_ids_canonical.py`
- Create: `tests/of01/fixtures/golden_v1.json`

**Interfaces:**
- Produces `validate_uuid(value: str, *, field: str, allowed_versions: frozenset[int] = frozenset({4})) -> str`, `validate_imported_uuid5(value, *, field, namespace_id, provenance_qualifier) -> str`, `new_uuid() -> str`, and `validate_hash`.
- Produces `OF01Error(code: OF01ErrorCode, message: str, details: Mapping[str, JsonValue])` and the exact codes in the spec.
- Produces `canonical_command_bytes`, `canonical_record_bytes`, `canonical_commit_bytes`, and `sha256_upper`.
- Dependencies: existing `market_platform_foundation.canonical`; no database.
- Rollback boundary: remove the new isolated package/tests; no persistent state exists.

- [ ] **Step 1: Write failing strict-identity/profile tests**

```python
def test_uuid_requires_lowercase_canonical_v4() -> None:
    assert validate_uuid("11111111-1111-4111-8111-111111111111", field="run_id").startswith("1111")
    for bad in ("", "{11111111-1111-4111-8111-111111111111}", "11111111111141118111111111111111"):
        with self.assertRaises(OF01Error):
            validate_uuid(bad, field="run_id")

def test_uuid5_requires_declared_import_context() -> None:
    with self.assertRaises(OF01Error):
        validate_uuid("6ba7b811-9dad-51d1-80b4-00c04fd430c8", field="run_id")

def test_command_vector_is_exact() -> None:
    fixture = load_json_strict(FIXTURE)
    self.assertEqual(sha256_upper(canonical_command_bytes(fixture["command"])), fixture["command_hash"])
```

- [ ] **Step 2: Run and observe missing-module failure**

Run: `$env:PYTHONPATH='src'; .venv\Scripts\python.exe -m unittest tests.of01.test_ids_canonical -v`

Expected: import failure for `market_platform_foundation.of01`.

- [ ] **Step 3: Implement the exact canonical boundary**

```python
COMMAND_PROFILE = "imp-of01-command-canonical-json-v1"
RECORD_PROFILE = "imp-of01-record-canonical-json-v1"
COMMIT_PROFILE = "imp-of01-commit-canonical-json-v1"
HASH_PROFILE = "imp-sha256-uppercase-hex-v1"

def sha256_upper(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()
```

Reject unknown/duplicate fields, floats, non-finite/fractional numbers,
out-of-range integers, invalid control/surrogate strings, unsorted set-like
lists, and unsupported profiles before calling repository-compatible canonical
serialization.

- [ ] **Step 4: Freeze exact command/record/commit vectors from the spec**

The fixture MUST contain the literal Unicode command vector and hashes
`05CA616A...`, `988D0DF7...`, `E52EEB8D...`, and `A08BB047...`; test canonical bytes including
the final LF.

- [ ] **Step 5: Verify and commit**

Run the focused test and changed validation. Commit:

```text
feat(of01): add identities and canonical hash profiles
```

### Task 2: Immutable records and typed command contracts

**Files:**
- Create: `src/market_platform_foundation/of01/records.py`
- Create: `src/market_platform_foundation/of01/commands.py`
- Create: `tests/of01/test_records_commands.py`

**Interfaces:**
- Produces frozen record dataclasses for all ten domain families and closed enums from the spec.
- Produces `CommandEnvelope`, command dataclasses, `validate_command`, `command_record_plan`, and `CommitReceipt` models.
- Consumes Task 1 IDs/profiles/errors.
- Rollback boundary: contracts only; no persistent state.

- [ ] Write failing tests for every field/enum/null pairing, unknown fields,
  secret/control rejection, C2+ registration data, parallel-capacity pairing,
  terminal-result pairing, artifact completeness/use restriction, and
  deterministic composite item order.
- [ ] Run focused tests and confirm missing contracts.
- [ ] Implement enums and frozen/slotted dataclasses. Use explicit serializers;
  never hash `__dict__` or accept arbitrary metadata.

```python
@dataclass(frozen=True, slots=True)
class RegisterRun:
    run: RunRecord
    initial_transition: RunTransitionRecord

@dataclass(frozen=True, slots=True)
class CloseRun:
    disposition: DispositionRecord
    terminal_transition: RunTransitionRecord
```

- [ ] Implement envelope hash verification and command-owned record plan. Test
  that `CloseRun` orders disposition before terminal transition and no public
  arbitrary-record command exists.
- [ ] Run focused/changed validation. Commit `feat(of01): define typed ledger contracts`.

### Task 3: Backend-independent protocols and in-memory contract authority

**Files:**
- Create: `src/market_platform_foundation/of01/protocols.py`
- Create: `src/market_platform_foundation/of01/memory.py`
- Create: `tests/of01/test_protocol_contract.py`

**Interfaces:**
- Produces writer/reader/stream/CAS/integrity/backup/projection protocols exactly as the spec.
- Produces `InMemoryLedger` only as a contract test double with the same retry/conflict semantics.
- Consumes Tasks 1–2; produces fixtures used by later repository tests.
- Rollback boundary: memory state disappears with process.

- [ ] Write a reusable contract test mixin proving same ID/hash retry,
  same ID/different hash conflict, domain-ID collision, ordered multi-record
  receipt, and typed reads/stream order.
- [ ] Confirm failure, then implement protocol signatures and minimal in-memory
  authority without SQLite/CAS path leakage.

```python
class AuthoritativeLedgerWriter(Protocol):
    def submit(self, envelope: CommandEnvelope) -> CommitReceipt: ...
    def resolve_command(self, command_id: str) -> CommitReceipt | None: ...
```

- [ ] Run the contract suite against memory and introspection tests proving
  domain code needs no `sqlite3`/Mongo import.
- [ ] Run changed validation. Commit `feat(of01): add portable ledger protocols`.

### Task 4: SQLite DDL, metadata bootstrap, and ordered migrations

**Files:**
- Create: `src/market_platform_foundation/of01/sqlite_schema.py`
- Create: `src/market_platform_foundation/of01/migrations.py`
- Create: `src/market_platform_foundation/of01/sqlite_store.py`
- Create: `tests/of01/test_sqlite_schema.py`
- Create: `tests/of01/test_migrations.py`

**Interfaces:**
- Produces `SCHEMA_VERSION = 1`, exact DDL/index/trigger tuples, `bootstrap_authority`, `open_authority`, `apply_migrations`.
- Connection profile: WAL, FULL sync, FKs, trusted schema off, configured positive busy timeout, `BEGIN IMMEDIATE` for writes.
- Consumes Tasks 1–3.
- Rollback boundary: disposable test DB; production migration requires later maintenance/backup task.

- [ ] Write tests asserting every table/column/type/not-null/check/PK/unique/FK,
  exact indexes, append-only triggers, STRICT support, singleton metadata, and
  rejection of malformed/partial/incompatible existing schemas.
- [ ] Write migration tests for fresh v1, idempotent reopen, unknown newer,
  missing path, interrupted transaction, and unchanged metadata identity.
- [ ] Run tests and confirm missing store.
- [ ] Implement exact reviewed DDL and object-definition verification. Do not
  introduce JSON payload or mutable authoritative table.

```python
def write_transaction(self) -> Iterator[sqlite3.Connection]:
    self.connection.execute("BEGIN IMMEDIATE")
    try:
        yield self.connection
    except BaseException:
        self.connection.execute("ROLLBACK")
        raise
    else:
        self.connection.execute("COMMIT")
```

- [ ] Verify `PRAGMA foreign_key_check`, append-only trigger behavior, and no
  authoritative UPDATE/DELETE source strings outside migration/bootstrap tests.
- [ ] Run focused/changed validation. Commit `feat(of01): add SQLite authority schema`.

### Task 5: Commit journal, process lock, serialization, and idempotency

**Files:**
- Create: `src/market_platform_foundation/of01/writer.py`
- Modify: `src/market_platform_foundation/of01/sqlite_store.py`
- Create: `tests/of01/test_writer_atomicity.py`
- Create: `tests/of01/test_writer_concurrency.py`
- Create: `tests/of01/test_process_lock.py`

**Interfaces:**
- Produces `SQLiteAuthoritativeLedgerWriter`, `WriterProcessLock`, bounded admission, `submit`, `resolve_command`, graceful queue close.
- Consumes Tasks 1–4.
- Rollback boundary: each command is one SQLite transaction; CAS orphan handling comes in Task 7.

- [ ] Write the contract suite against SQLite plus tests for exact commit/item
  rows, contiguous ordinal checks, commit hashes, multi-record rollback at each
  insert boundary, and no receipt after rollback.
- [ ] Add concurrent duplicate/different command and multi-producer tests;
  spawn a second process to prove lock denial.
- [ ] Implement the one-coordinator queue and double receipt lookup around
  `BEGIN IMMEDIATE`.

```python
existing = store.receipt(command_id)
if existing:
    return require_same_hash(existing, envelope.command_hash)
with store.write_transaction() as conn:
    existing = store.receipt(command_id, conn=conn)
    if existing:
        return require_same_hash(existing, envelope.command_hash)
    return commit_planned_records(conn, envelope)
```

- [ ] Inject failure immediately before/after COMMIT and prove receipt lookup
  resolves lost responses without duplicate rows.
- [ ] Run focused/changed validation. Commit `feat(of01): implement atomic command journal`.

### Task 6: Run/attempt lifecycle, outcomes, dispositions, and relationships

**Files:**
- Create: `src/market_platform_foundation/of01/state_machine.py`
- Modify: `src/market_platform_foundation/of01/writer.py`
- Create: `tests/of01/test_run_attempt_lifecycle.py`
- Create: `tests/of01/test_outcomes_dispositions.py`
- Create: `tests/of01/test_relationships.py`

**Interfaces:**
- Produces pure validators for expected predecessor, run/attempt transition,
  sequential/parallel attempts, close rules, supersession, endpoint registry,
  and acyclicity.
- Consumes Task 5 transaction/store; validators rerun inside the transaction.
- Rollback boundary: invalid command rolls back with no receipt.

- [ ] Write exhaustive state-table tests, including zero-attempt closure,
  terminal no-reopen, LOST reconciler evidence, one-based sequence, sequential
  overlap rejection, parallel capacity, and C2+ durable-before-start.
- [ ] Write outcome validity/disposition independence and correction lineage
  tests; write acyclic/cyclic relationship graph tests with co-committed endpoints.
- [ ] Implement pure validators returning stable error codes; call them both at
  preflight and inside transaction using current rows.
- [ ] Add TOCTOU races where preflight passes but predecessor/concurrency changes
  before commit; assert one command fails closed.
- [ ] Run focused/changed validation. Commit `feat(of01): enforce ledger domain state machines`.

### Task 7: Immutable CAS and artifact commands

**Files:**
- Create: `src/market_platform_foundation/of01/cas.py`
- Modify: `src/market_platform_foundation/of01/writer.py`
- Create: `tests/of01/test_cas.py`
- Create: `tests/of01/test_artifact_commands.py`

**Interfaces:**
- Produces `LocalCAS.prepare/publish/open_verified/inventory`, `PreparedObject`,
  `PublishedObject`, and artifact writer integration.
- Consumes Tasks 1–6.
- Rollback boundary: DB failure after publish leaves an unreferenced object; DB
  never references unpublished bytes.

- [ ] Write streaming/hash/size, duplicate-content, expected mismatch,
  traversal, temp, same-filesystem, file-fsync, existing-object verification,
  Windows/POSIX acknowledgement, permission, and disk-failure tests.
- [ ] Write crash-point tests before/during/after publish and before/during/after
  transaction; assert only safe temp/orphan or complete reference states.
- [ ] Implement system-derived paths and publish-before-transaction; no caller
  path argument is exposed.
- [ ] Test two artifact IDs sharing bytes, completeness/use restrictions, and
  missing/mismatched referenced objects as fatal.
- [ ] Run focused/changed validation. Commit `feat(of01): add verified artifact CAS`.

### Task 8: Source attribution and provenance references

**Files:**
- Modify: `src/market_platform_foundation/of01/records.py`
- Modify: `src/market_platform_foundation/of01/commands.py`
- Modify: `src/market_platform_foundation/of01/writer.py`
- Create: `tests/of01/test_source_attribution.py`
- Create: `tests/of01/test_provenance.py`

**Interfaces:**
- Implements exact source/provenance fields, dirty-source capsule schema, and
  typed reference-kind validation.
- Consumes CAS/artifact support from Task 7.
- Rollback boundary: attribution records commit atomically; capsule may remain orphan on rollback.

- [ ] Write tests for clean, dirty attributable, unattributable, multi-root,
  normalized scope/changed paths, outside-scope proof, binary content hashes,
  traversal/control/secret rejection, and material environment allowlisting.
- [ ] Implement deterministic capsule manifests and require capsule/proof
  artifacts for `DIRTY_ATTRIBUTABLE`; never capture arbitrary environment.
- [ ] Verify exact canonical hashes and co-committed FK behavior.
- [ ] Run focused/changed validation. Commit `feat(of01): add source and provenance lineage`.

### Task 9: Typed readers, commit stream, current state, and projections

**Files:**
- Create: `src/market_platform_foundation/of01/readers.py`
- Create: `src/market_platform_foundation/of01/projections.py`
- Create: `tests/of01/test_readers_stream.py`
- Create: `tests/of01/test_current_state.py`
- Create: `tests/of01/test_projections.py`

**Interfaces:**
- Produces `SQLiteLedgerReader`, `stream_commits`, `RunView`, `AttemptView`,
  `ProjectionStatus`, `ProjectionConsumer`, and versioned cursor store.
- Consumes Tasks 1–8; does not import writer internals in projector target code.
- Rollback boundary: projection targets/cursors are disposable; authority read-only.

- [ ] Write tests for exact record/commit lookup, sequence ranges, ordinal order,
  snapshot cuts, current run/attempt/disposition/artifact views, and wrong-
  authority/range errors.
- [ ] Write fake projection tests for atomic cursor advance, duplicate replay,
  target failure, pause/resume, invalid/ahead cursor, source mismatch, version
  upgrade, reset, and full rebuild.
- [ ] Implement typed SQL readers and projection source. Current-state queries
  MUST cite source IDs and `as_of_commit_sequence`.

```python
def stream_commits(self, after_sequence: int, through_sequence: int | None = None) -> Iterator[CommitBundle]:
    with self.read_snapshot() as conn:
        yield from load_complete_bundles(conn, after_sequence, through_sequence)
```

- [ ] Add an optional Mongo adapter contract test using an in-memory fake unless
  an already-approved Mongo dependency/environment exists; assert no reverse
  writer interface and preserved source lineage.
- [ ] Run focused/changed validation. Commit `feat(of01): add ledger readers and projections`.

### Task 10: Integrity checker and fail-safe integrity block

**Files:**
- Create: `src/market_platform_foundation/of01/integrity.py`
- Create: `tests/of01/test_integrity.py`
- Create: `tests/of01/test_corruption_response.py`

**Interfaces:**
- Produces `IntegrityMode`, `FindingClass`, `IntegrityFinding`,
  `IntegrityReport`, `IntegrityChecker.check`, and runtime integrity-block hook.
- Consumes SQLite/CAS/read/projection components.
- Rollback boundary: checker is read-only; fatal results alter operational mode only.

- [ ] Build a disposable valid authority, copy it per test, and inject structural,
  FK, uniqueness, item/typed reverse membership, ordinal/count, schema/profile,
  record hash, commit hash, missing/mismatched CAS, orphan, and cursor defects.
- [ ] Prove QUICK/FULL/FORENSIC scope, stable classification, report hashing,
  incomplete-scan behavior, original-file preservation, and no repair SQL.
- [ ] Implement independent recomputation using stored schema version dispatch;
  do not reuse writer acceptance as the only verifier.
- [ ] Assert fatal findings reject subsequent writes while projection/orphan
  findings receive rebuildable/housekeeping classifications.
- [ ] Run focused/changed validation. Commit `feat(of01): add fail-safe integrity verification`.

### Task 11: Backup, restore, activation, and migrations

**Files:**
- Create: `src/market_platform_foundation/of01/backup.py`
- Create: `src/market_platform_foundation/of01/restore.py`
- Modify: `src/market_platform_foundation/of01/migrations.py`
- Create: `tests/of01/test_backup_restore.py`
- Create: `tests/of01/test_authority_activation.py`
- Extend: `tests/of01/test_migrations.py`

**Interfaces:**
- Produces `BackupManifestV1`, backup create/verify, restore validate/activate,
  clone modes, and migration descriptors with recovery boundaries.
- Consumes Task 10 full integrity and Task 7 CAS inventory.
- Rollback boundary: manifest published last; restore candidate inactive until activation; migration uses transaction or verified-backup restore.

- [ ] Write online snapshot tests with concurrent post-snapshot writes proving
  high-water/CAS inventory derives from snapshot and excludes harmless extras.
- [ ] Test manifest hash/size/schema/profile/authority/high-water/receipt/record/
  commit/CAS verification and `UNVERIFIED -> VERIFIED -> RESTORE_TESTED` evidence rules.
- [ ] Implement SQLite backup API flow and canonical manifest publication last;
  raw active file copy MUST have no supported code path.
- [ ] Test offline restore verification, authority preservation, single
  activation, wrong identity, failed CAS, read-only analysis fork, and explicit
  reidentified disposable clone.
- [ ] Add migration descriptor tests for exact source/destination, required
  backup/maintenance, unsupported path, transactional failure, and unchanged
  historical hashes.
- [ ] Run focused/changed validation. Commit `feat(of01): add verified ledger recovery`.

### Task 12: Runtime health, startup, shutdown, maintenance, and backpressure

**Files:**
- Create: `src/market_platform_foundation/of01/health.py`
- Create: `src/market_platform_foundation/of01/maintenance.py`
- Modify: `src/market_platform_foundation/of01/writer.py`
- Create: `tests/of01/test_runtime_lifecycle.py`
- Create: `tests/of01/test_maintenance.py`
- Create: `tests/of01/test_backpressure_shutdown.py`

**Interfaces:**
- Produces operational modes, separate liveness/readiness/degradation/integrity
  status, startup gate inventory, maintenance lease/revision, and shutdown result.
- Consumes Tasks 4–11.
- Rollback boundary: failed startup releases resources; failed maintenance exit remains quiescent; shutdown resolves each admitted command.

- [ ] Write startup table tests for every prerequisite failure: configuration,
  path/filesystem, permissions, authority identity, schema/profile, WAL/FULL/FK,
  lock, CAS probe, quick integrity, and migration state.
- [ ] Write maintenance CAS-revision/lease/authorization tests and matrix tests
  proving which operations require maintenance.
- [ ] Write bounded queue/full, drain/reject deadline, active command commit/
  rollback, ambiguous commit, crash/restart, and writer-lock-release tests.
- [ ] Implement mode transitions and structured readiness reasons; projection
  outage MUST be degraded without blocking authority by default.
- [ ] Run focused/changed validation. Commit `feat(of01): operationalize ledger runtime lifecycle`.

### Task 13: Structured operator capabilities and CLI adapter

**Files:**
- Create: `src/market_platform_foundation/of01/authorization.py`
- Create: `src/market_platform_foundation/of01/operations.py`
- Create: `src/market_platform_foundation/of01/cli.py`
- Create: `tests/of01/test_authorization.py`
- Create: `tests/of01/test_operations.py`
- Create: `tests/of01/test_cli.py`

**Interfaces:**
- Implements `AuthorizationVerifier`/`AuthorizationGrant` and every `OF01.OP.*` capability ID with canonical JSON result and
  human-readable adapter; stable exit/result codes map to `OF01ErrorCode`.
- Consumes Tasks 10–12 and does not expose direct SQL or caller-selected CAS paths.
- Rollback boundary: each operation delegates to its owning idempotent or explicitly consequence-controlled service.

- [ ] Write capability inventory tests asserting exact IDs, role requirements,
  maintenance/destructive confirmation, target authority binding, and result
  envelope fields.
- [ ] Test trusted issuer/source, capability/authority/input/initiator binding,
  not-before/expiry, revocation version, unavailable trust source, and rejection
  of caller-supplied grant claims using an injected offline verifier.
- [ ] Write parser/output tests for status, metadata/latest commit, receipt
  resolve, explicit write-disable, integrity, backup/restore validation and
  restore-test attestation, maintenance, CAS scan/GC dry run, projection,
  migration, authority clone/reidentification, and shutdown. Keep destructive execution hidden
  behind exact authorization inputs and role checks.
- [ ] Implement a thin adapter around typed services; machine JSON MUST never
  require scraping prose.

```python
@dataclass(frozen=True, slots=True)
class OperationResult:
    operation_id: str
    capability_id: str
    ledger_authority_id: str
    outcome_code: str
    started_at_ns: int
    completed_at_ns: int
    verification: Mapping[str, JsonValue]
    evidence_ref: str | None
```

- [ ] Run focused/changed validation. Commit `feat(of01): add structured operator controls`.

### Task 14: Bind operations documents, roles, workflows, and agent policy

**Files:**
- Modify: `docs/operations/of-01/README.md`
- Modify: `docs/operations/of-01/RUNBOOK.md`
- Modify: `docs/operations/of-01/SOPS.md`
- Modify: `docs/operations/of-01/WORKFLOWS.md`
- Modify: `docs/operations/of-01/AGENT_OPERATING_RULES.md`
- Create: `tests/of01/test_documentation_contract.py`
- Create: `tests/of01/test_agent_policy.py`

**Interfaces:**
- Replaces capability-only invocation lines with verified implemented CLI/API
  syntax while retaining stable capability IDs and metadata.
- Consumes Task 13 capability registry (subsystem-local static map only).
- Rollback boundary: docs/adapter binding only; no global OF-03 registry.

- [ ] Parse docs and assert unique `SOP-OF01-001..018`, unique
  `WF-OF01-001..018`, all required template fields, every capability exists,
  command arguments parse, structured result fields/error codes match, and
  every link resolves.
- [ ] Write negative authorization tests for arbitrary SQL, new retry IDs,
  fabricated success, hidden hash repair, secret persistence, projection as
  authority, autonomous GC/activation/migration, and authority escalation.
- [ ] Update only invocation syntax proven by tests; do not duplicate canonical
  schemas from the spec into runbook prose.
- [ ] Run docs/agent tests and changed validation. Commit `docs(of01): bind executable operations pack`.

### Task 15: Deterministic fault injection and capacity measurement

**Files:**
- Create: `tests/of01/faults.py`
- Create: `tests/of01/test_fault_matrix.py`
- Create: `tests/of01/test_operational_scenarios.py`
- Create: `tools/of01_measure.py`
- Create: `tests/of01/test_measurement.py`

**Interfaces:**
- Produces deterministic fault hooks at command, CAS, transaction, COMMIT
  response, restart, integrity, projection, migration, backup/restore, disk,
  and permission boundaries.
- Produces informational measurements with sample counts and no invented gate.
- Consumes all runtime tasks.
- Rollback boundary: disposable authorities only; measurement output is non-authoritative evidence.

- [ ] Implement named one-shot fault points and prove every crash-boundary row
  yields only no state, safe temp/orphan, or complete commit/reference.
- [ ] Automate scenarios A–T, including second writer, network filesystem
  refusal via deterministic detector fake, direct SQL agent denial, and history
  deletion absence.
- [ ] Measure commit latency distribution/sample count, throughput,
  records/bytes per transaction, queue/backpressure, WAL/CAS growth, projection
  lag, and quick/full integrity duration across declared workloads.
- [ ] Assert the tool labels results informational and accepts bounded config;
  no p95/p99 without justified sample policy and no hard-coded SLA.
- [ ] Run focused/changed validation. Commit `test(of01): exercise fault and capacity boundaries`.

### Task 16: Operational drills, repository validation, and acceptance evidence

**Files:**
- Create: `artifacts/imp-of-01/README.md`
- Create: `artifacts/imp-of-01/OF01_ACCEPTANCE_REPORT.md`
- Create: `artifacts/imp-of-01/OF01_FILE_HASHES.json`
- Create: `artifacts/imp-of-01/OF01_KNOWN_LIMITATIONS.md`
- Modify only implementation files when a newly reproduced failing test proves a defect.

**Interfaces:**
- Produces the complete acceptance evidence surface; no runtime interface changes.
- Consumes all tasks and the repository validation manifest.
- Rollback boundary: acceptance failure leaves milestone unapproved; never rewrite evidence to hide failure.

- [ ] Exercise normal startup/shutdown/restart, lost response, duplicate command,
  multi-record atomicity, artifact attach, orphan detection, quick/full
  integrity, backup/verify, restore, identity preservation, projection replay/
  rebuild/failure recovery, maintenance, migration rehearsal, corruption,
  disk/permission failures, queue-drain shutdown, clone safety, and DR exercise.
- [ ] Run documentation conformance and agent negative tests from a fresh
  process. Re-read Invariants 1–75 and map each to a passing test/evidence item.
- [ ] Run the exact validation ladder:

```powershell
$env:PYTHONPATH='src'
.venv\Scripts\python.exe tools\validate.py changed --explain
.venv\Scripts\python.exe tools\validate.py full
git diff --check
git status --short
```

Expected: zero failures/errors; FULL remains offline. Run no live/provider gate.

- [ ] Generate canonical file hashes only after final accepted content, verify
  every listed path/hash and count, and record source commit/authority/test
  counts/skip counts/limitations accurately.
- [ ] Review source for mutation SQL escape hatches, caller paths, secret
  capture, unsupported topology, projection reverse path, EVIDENCE/risk/
  execution changes, and arbitrary tuning.
- [ ] Commit one coherent acceptance boundary:

```text
feat(of01): implement authoritative run and artifact ledger
```

Do not push, merge, activate an operator ledger, create a live authority, or
claim runtime completion unless the acceptance report and full validation prove
every required item.

## Plan self-review

- Spec coverage: every invariant, package surface, DDL concern, SOP/workflow,
  failure class, scenario, and acceptance drill maps to Tasks 1–16.
- Incomplete-content scan: no deferred semantic field, command, migration, or test
  category remains; only measured operational values are policy/configuration.
- Type consistency: `CommandEnvelope`, `CommitReceipt`, writer/read/stream/CAS
  protocols, record IDs, capability IDs, and projection cursors retain the same
  names and semantics across tasks.
- Scope: the plan builds one OF-01 subsystem; it does not implement OF-02,
  OF-03, ADAPT schemas, EVIDENCE changes, or trading authority.
