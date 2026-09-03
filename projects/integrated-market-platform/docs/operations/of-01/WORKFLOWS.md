# OF-01 Workflows

| Field | Value |
|---|---|
| Document ID | `WORKFLOWS-OF01` |
| Version | `1.0-draft` |
| Status | `NORMATIVE_RUNTIME_DRAFT` |
| System | `IMP-OF-01` |

Workflows describe actor/system orchestration and transaction boundaries. They
refer to SOPs when controlled operator procedure is required. Each authoritative
retry reuses the original command ID, domain IDs, canonical semantic content,
and hash.

Every workflow uses the displayed fields plus this mandatory recovery/evidence
contract: failure stops before any later success-only step; authoritative
uncertainty routes to WF-OF01-009/SOP-OF01-013; an operational failure routes to
the cited owning SOP/runbook condition; projection work preserves the last
fully applied cursor; destructive work preserves its input manifest and stops
at the first mismatch. The actor preserves command/operation IDs, target
authority, structured result/error, verification, timestamps, and evidence
reference. Success is only the condition stated under
`Success/failure/evidence` plus the `Postcondition`; all other outcomes are
failure/incomplete and MUST NOT be reported as success. This inherited
recovery/evidence field is part of each WF-OF01-001..018 definition.

## WF-OF01-001 — Register run

- **Actor/trigger:** Authorized domain caller decides a consequential objective requires a durable run.
- **Preconditions/inputs:** Writer ready; caller allocates command/run/initial-transition IDs; complete immutable run/provenance fields; C2+ work has not started.
- **Steps/boundary:** Build `RegisterRun`; canonicalize/hash; submit; writer revalidates and commits run plus initial `REGISTERED` transition in one transaction.
- **Success/failure/evidence:** Commit receipt and record hashes. Failure is typed rejection with no receipt; projection/telemetry occurs afterward.
- **Retry/idempotency/observability:** Same envelope; resolve receipt before retry; record latency/result IDs. New IDs are new work.
- **Postcondition:** Run exists exactly once in `REGISTERED`; C2+ execution may proceed only after receipt.

## WF-OF01-002 — Start attempt

- **Actor/trigger:** Governed executor begins one bounded technical execution.
- **Preconditions/inputs:** Open run; caller-allocated command/attempt/transition IDs; next attempt sequence; invocation/environment refs; expected predecessor/concurrency; no incompatible active attempt.
- **Steps/boundary:** Commit `RegisterAttempt` plus initial `PENDING`; immediately before execution, commit `AppendAttemptTransition` to `RUNNING`; external work starts only after required receipt.
- **Success/failure/evidence:** Two receipts/transition hashes. Preconditions are rechecked inside each transaction.
- **Retry/idempotency/observability:** Retry each command only with its original identity; technical retry creates a new attempt.
- **Postcondition:** One attempt is authoritatively running; execution side effect remains outside transaction.

## WF-OF01-003 — Finish attempt

- **Actor/trigger:** Executor obtains terminal technical result or reconciler proves `LOST`.
- **Preconditions/inputs:** Nonterminal attempt, exact predecessor transition, terminal result, end time, reason/evidence.
- **Steps/boundary:** Build terminal `AppendAttemptTransition`; commit one immutable transition. Produced artifacts/outcomes use separate or explicitly composite domain commands when atomic semantics require it.
- **Success/failure/evidence:** Receipt and terminal AttemptView. Failure never overwrites prior transitions.
- **Retry/idempotency/observability:** Same command identity; duplicate returns receipt; conflicting terminal predecessor fails.
- **Postcondition:** Attempt is terminal forever; a later retry is a new attempt.

## WF-OF01-004 — Record outcome

- **Actor/trigger:** Domain evaluator produces a typed result and validity judgment.
- **Preconditions/inputs:** Existing run/optional attempt/protocol; outcome ID; result reference; validity/time/limitations; explicit superseded outcome when correcting.
- **Steps/boundary:** Validate domain schema and references; commit `RecordOutcome`; external evaluation/storage is complete before transaction.
- **Success/failure/evidence:** Outcome receipt/hash. Technical completion is not analytical validity.
- **Retry/idempotency/observability:** Resolve original command receipt; correction uses a new outcome/command and explicit lineage.
- **Postcondition:** Immutable outcome exists; no disposition is implied.

## WF-OF01-005 — Append disposition

- **Actor/trigger:** Authorized domain authority decides how an outcome/run may be used.
- **Preconditions/inputs:** Run, optional outcome, disposition ID, authority/policy, action/domain code, prior disposition/limitations.
- **Steps/boundary:** Commit `AppendDisposition`; policy-specific current view derives lineage afterward. Run closure uses `CloseRun` to co-commit terminal disposition and transition when needed.
- **Success/failure/evidence:** Receipt/hash; failures do not change current interpretation.
- **Retry/idempotency/observability:** Stable identity; a changed decision is a new disposition, never overwrite.
- **Postcondition:** Decision history is append-preserved.

## WF-OF01-006 — Attach artifact

- **Actor/trigger:** Producer has immutable bytes and semantic artifact metadata.
- **Preconditions/inputs:** Existing/co-committed producer run/attempt; command/artifact IDs; stream; role, completeness, validation/use/retention classifications; expected content hash if known.
- **Steps/boundary:** CAS prepares, hashes, fsyncs, atomically publishes, and verifies bytes; then writer commits artifact metadata/reference in one SQLite transaction. CAS work is outside DB transaction.
- **Success/failure/evidence:** Content hash, artifact record/hash, receipt. Failed DB step may leave a safe orphan.
- **Retry/idempotency/observability:** Reuse verified bytes and original IDs; mismatched bytes fail before reference.
- **Postcondition:** Every committed artifact reference resolves to verified immutable content.

## WF-OF01-007 — Create relationship

- **Actor/trigger:** Caller declares typed lineage/association.
- **Preconditions/inputs:** Relationship/command IDs; typed source/target existing or co-committed; relation schema; effective time/code.
- **Steps/boundary:** Writer validates endpoint vocabulary/existence and acyclicity class using committed plus proposed edges; commits relationship.
- **Success/failure/evidence:** Receipt/hash. Cycle or endpoint failure rolls back wholly.
- **Retry/idempotency/observability:** Stable identity; a different edge needs a new ID.
- **Postcondition:** Immutable explicit edge exists; no implicit latest-time semantics.

## WF-OF01-008 — Submit multi-record atomic command

- **Actor/trigger:** One domain operation requires several identified records to succeed/fail together.
- **Preconditions/inputs:** Supported composite command, all caller IDs, deterministic command-owned item order, all semantic preconditions.
- **Steps/boundary:** Preflight; optional CAS publication; one `BEGIN IMMEDIATE`; revalidate; allocate commit; hash/insert all items/typed rows; verify exact membership; one commit/rollback.
- **Success/failure/evidence:** One receipt containing ordered record refs, or no authoritative mutation.
- **Retry/idempotency/observability:** Command receipt controls; reused domain ID under different command conflicts.
- **Postcondition:** All records exist in exactly one commit or none do.

## WF-OF01-009 — Resolve ambiguous command result

- **Actor/trigger:** Caller loses/does not trust response around commit.
- **Preconditions/inputs:** Original command ID/hash/domain IDs/authority.
- **Steps/boundary:** Stop submission; execute SOP-OF01-013; query receipt; return existing success, conflict, or proven absence; only absence permits exact resubmission.
- **Success/failure/evidence:** Resolution evidence and receipt/absence. No transaction occurs during lookup; resubmission uses normal one-transaction path.
- **Retry/idempotency/observability:** Lookup is idempotent; guessing or new IDs prohibited.
- **Postcondition:** Caller has evidence-backed state.

## WF-OF01-010 — Projection consumption

- **Actor/trigger:** Projector polls/receives available authoritative commits.
- **Preconditions/inputs:** Projection identity/version/source authority and valid durable cursor.
- **Steps/boundary:** Read next complete commit after cursor; fetch typed records in ordinal order; apply idempotently in target transaction; persist target changes and cursor atomically when target supports it; continue.
- **Success/failure/evidence:** Updated derived target/cursor; source unchanged. Failure leaves cursor at last fully applied commit.
- **Retry/idempotency/observability:** Reapply same commit safely; lag/error/cursor emitted.
- **Postcondition:** Cursor never claims unapplied authority.

## WF-OF01-011 — Projection rebuild

- **Actor/trigger:** Projection is stale, corrupt, version-incompatible, or intentionally recreated.
- **Preconditions/inputs:** Projection operator authorization, empty versioned target, source authority/high-water/projector version.
- **Steps/boundary:** Execute SOP-OF01-010; replay commits from zero/safe declared point; validate; switch readers after success.
- **Success/failure/evidence:** Rebuild evidence and valid cursor; old target retained/quarantined per policy.
- **Retry/idempotency/observability:** Fresh-target rebuild is rerunnable; no source mutation.
- **Postcondition:** Derived content matches authoritative cut.

## WF-OF01-012 — Integrity verification

- **Actor/trigger:** Startup, schedule, operator, backup, restore, migration, or incident requires proof.
- **Preconditions/inputs:** Mode/scope/high-water and role; maintenance when required.
- **Steps/boundary:** Execute SOP-OF01-003; checks use read snapshots/offline candidate and never authoritative mutations.
- **Success/failure/evidence:** Canonical report with classifications/evidence. Fatal finding blocks writes.
- **Retry/idempotency/observability:** Scans rerunnable; interrupted is incomplete, not pass.
- **Postcondition:** Evidence-backed integrity state at a declared cut.

## WF-OF01-013 — Backup

- **Actor/trigger:** Policy/operator requests recovery point.
- **Preconditions/inputs:** Healthy source, destination, backup ID/policy and authority.
- **Steps/boundary:** Execute SOP-OF01-004: consistent DB snapshot, snapshot high-water, exact CAS coverage, hashes, manifest last.
- **Success/failure/evidence:** `VERIFIED` backup or `UNVERIFIED` partial. Source transaction history unchanged.
- **Retry/idempotency/observability:** Verification rerunnable; new logical backup uses new ID.
- **Postcondition:** Recovery set proves declared coverage, not restore-tested state.

## WF-OF01-014 — Restore

- **Actor/trigger:** Disaster recovery, controlled replacement, or exercise selects a backup.
- **Preconditions/inputs:** Stopped/inactive target, verified manifest, custody and activation authority.
- **Steps/boundary:** Execute SOP-OF01-005; stage/verify offline; explicit activation; startup; projection rebuild.
- **Success/failure/evidence:** Active preserved lineage or rejected inactive candidate. No automatic failover/merge.
- **Retry/idempotency/observability:** Validation rerunnable; activation is consequence-controlled and not blindly repeated.
- **Postcondition:** Declared operational custody has activated exactly one verified authority; OF-01 does not claim global consensus against an isolated misactivation.

## WF-OF01-015 — Schema migration

- **Actor/trigger:** Accepted runtime requires a supported physical destination version.
- **Preconditions/inputs:** Reviewed migration, compatible source, verified backup, maintenance lease, recovery plan.
- **Steps/boundary:** Execute SOP-OF01-012; transactional steps commit atomically; nontransactional boundary is explicit; verify hashes/integrity/readiness.
- **Success/failure/evidence:** Exact destination version or write-disabled restored source.
- **Retry/idempotency/observability:** Migration declares retry semantics per step; no assumption.
- **Postcondition:** Semantic history and identities unchanged.

## WF-OF01-016 — CAS GC

- **Actor/trigger:** Capacity/retention process requests safe removal of orphan bytes.
- **Preconditions/inputs:** Maintenance, stable scan/dry-run manifest, holds, exact authorization.
- **Steps/boundary:** Execute SOP-OF01-009; validate unchanged cut; delete only manifest candidates; verify afterward. No SQLite authoritative transaction occurs.
- **Success/failure/evidence:** Deletion result and post-scan; unexpected state stops.
- **Retry/idempotency/observability:** Not generally idempotent; every new execution needs current manifest/authorization.
- **Postcondition:** Referenced CAS coverage remains complete.

## WF-OF01-017 — Controlled shutdown

- **Actor/trigger:** Operator/runtime receives planned stop.
- **Preconditions/inputs:** Drain policy/deadline and authority.
- **Steps/boundary:** Execute SOP-OF01-002; stop admission; resolve queue/active transaction/receipt; close resources/release lock.
- **Success/failure/evidence:** `STOPPED` evidence and resolved command set.
- **Retry/idempotency/observability:** Repeated shutdown on stopped service returns existing state.
- **Postcondition:** No partial command and no held writer lock.

## WF-OF01-018 — Recovery after unexpected process termination

- **Actor/trigger:** Process/host terminated without controlled shutdown.
- **Preconditions/inputs:** Exclusive custody, prior authority/config identity, last known active command IDs if available.
- **Steps/boundary:** Prevent auto-retry storm; confirm no old writer/lock owner; preserve crash logs; allow SQLite WAL recovery through supported open; run startup quick integrity; resolve every ambiguous active command by receipt; verify CAS references/temps; start through SOP-001; resume/rebuild projections from durable cursor.
- **Success/failure/evidence:** Ready recovered authority or write-disabled incident. SQLite recovery is physical; no new commit is invented.
- **Retry/idempotency/observability:** Repeat checks safely; original command identities only.
- **Postcondition:** Restart state is proven, not inferred from process liveness.
