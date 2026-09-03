# OF-01 Standard Operating Procedures

| Field | Value |
|---|---|
| Document ID | `SOPS-OF01` |
| Version | `1.0-draft` |
| Status | `NORMATIVE_RUNTIME_DRAFT` |
| System | `IMP-OF-01` |

These procedures invoke stable capability IDs, not imaginary shell commands.
Runtime acceptance MUST bind every capability to the implemented interface and
verify arguments, structured output, errors, and documentation.

Each procedure records an operation evidence envelope. `STOP` means do not
continue to a later step; preserve evidence and follow the stated recovery.

## SOP-OF01-001 — Startup

- **Purpose:** Admit authoritative writes only after all prerequisites are proven.
- **Risk/consequence:** Authority-critical; unsafe startup can fork or corrupt lineage.
- **Required authority:** Ledger runtime under operator-controlled configuration.
- **Prerequisites/inputs:** stopped instance; configured DB/CAS/lock; expected authority ID; supported schema/profile set; service identity.
- **Expected state:** `STOPPED`; no writer lock owner.
- **Procedure:** (1) Create operation evidence. (2) Set `STARTING`. (3) validate configuration and system-derived paths; reject network/unknown filesystem. (4) prove DB/CAS permissions and CAS same-filesystem temp/object roots. (5) read and match authority metadata. (6) set/verify WAL, FULL sync, foreign keys, `trusted_schema=OFF`, and configured positive bounded busy timeout. (7) acquire exclusive writer lock. (8) validate migration state without applying an undeclared path. (9) run `OF01.OP.INTEGRITY_QUICK`. (10) perform a temp-only CAS write/fsync/read/rename probe inside the dedicated operation-owned probe namespace and remove only that owned probe before completion; never publish/delete a final content-addressed object. (11) initialize readers/projectors. (12) emit `READY` only if every mandatory gate passes; otherwise release lock and remain write-disabled.
- **Verification/success:** `OF01.OP.STATUS` reports expected authority, schema/profiles, exclusive writer, quick-integrity success, CAS writable, and `READY_FOR_AUTHORITATIVE_WRITES=true`.
- **Failure/retry:** Return the first stable gate code and complete gate inventory. Retry only after correcting that condition; no restart loop.
- **Rollback/recovery:** Close opened resources, release lock, preserve startup evidence, remain `STOPPED` or `WRITE_DISABLED`.
- **Evidence/postconditions/handoff:** startup operation ID, versions, gate results, authority/latest commit, mode/readiness; hand off integrity failures to SOP-014 and storage failures to SOP-015.

## SOP-OF01-002 — Graceful shutdown

- **Purpose:** Stop without partial or ambiguous authoritative work.
- **Risk/consequence:** Authority-critical around an active command.
- **Required authority:** Ledger operator or runtime shutdown policy.
- **Prerequisites/inputs:** target authority; drain-or-reject policy; bounded deadline; authorization reference when consequential.
- **Expected state:** `READY`, `DEGRADED`, `MAINTENANCE`, or `WRITE_DISABLED`.
- **Procedure:** (1) Capture status/latest commit/active command. (2) call `OF01.OP.SHUTDOWN`; mode becomes `SHUTTING_DOWN`. (3) close new admissions. (4) reject or drain queued envelopes according to declared policy. (5) finish the active transaction or roll it back. (6) if commit acknowledgement is uncertain, execute SOP-013 before continuing. (7) stop projectors/readers. (8) checkpoint WAL only when SQLite reports it safe; never delete WAL/SHM manually. (9) close SQLite and CAS handles. (10) release writer lock and record `STOPPED`.
- **Verification/success:** no active/queued command, every admitted command has receipt or typed rejection, process resources closed, lock free, latest commit identified.
- **Failure/retry:** A deadline expiry rejects remaining queued work but does not interrupt a proven commit. Retry status/shutdown idempotently.
- **Rollback/recovery:** Unexpected process death follows WF-OF01-018; ambiguous command follows SOP-013.
- **Evidence/postconditions/handoff:** shutdown policy, queue counts, active-command resolution, checkpoint result, final commit/mode.

## SOP-OF01-003 — Integrity check

- **Purpose:** Detect structural, relational, hash, schema, CAS, and cursor defects without repair.
- **Risk/consequence:** Read-heavy; findings may disable authority.
- **Required authority:** Quick—ledger operator; full/forensic—maintenance or recovery operator.
- **Prerequisites/inputs:** check mode; target authority; scope/high-water; evidence destination. FULL defaults to maintenance.
- **Expected state:** QUICK may run ready; FULL in `MAINTENANCE`; FORENSIC in `INTEGRITY_BLOCKED`/`WRITE_DISABLED`.
- **Procedure:** (1) capture status and high-water. (2) enter maintenance if required. (3) invoke the matching integrity capability. (4) verify SQLite, FKs, uniqueness, membership/reverse membership, ordinals/counts, schema/profiles, record/commit hashes, referenced CAS, and cursors according to mode. (5) classify every finding. (6) on any `AUTHORITATIVE_FATAL`, stop writes and preserve evidence. (7) publish a canonical report; do not mutate authority.
- **Verification/success:** report identifies mode, authority, high-water, check counts, findings, duration, tool version, and overall class; success means no fatal finding.
- **Failure/retry:** The scan is idempotent. Tool interruption retains incomplete state and may rerun; incomplete never means pass.
- **Rollback/recovery:** No semantic rollback exists because the check is read-only. Fatal findings use SOP-014.
- **Evidence/postconditions/handoff:** report/hash/logs; exit maintenance only if readiness prerequisites still pass.

## SOP-OF01-004 — Verified backup

- **Purpose:** Produce a manifest-bound consistent SQLite/CAS recovery set.
- **Risk/consequence:** Recovery-critical; false success creates unrecoverable confidence.
- **Required authority:** Backup/recovery operator; online backup allowed when implementation proves snapshot consistency.
- **Prerequisites/inputs:** healthy authority, destination identity, backup policy/authorization, sufficient destination capacity.
- **Expected state:** ready or maintenance; no unresolved fatal integrity finding.
- **Procedure:** (1) capture status and run `OF01.OP.INTEGRITY_QUICK`; policy may additionally require FULL, but no backup may weaken that policy. (2) allocate backup ID. (3) use `OF01.OP.BACKUP_CREATE`/SQLite backup API for a consistent snapshot. (4) read high-water and authority metadata from the snapshot. (5) enumerate referenced CAS hashes from that snapshot. (6) copy each object or record `VERIFIED_EXTERNAL_IMMUTABLE_OBJECT` coverage exactly as `BackupManifestV1` defines; existing entries are resumable only when backup ID/snapshot/high-water/hash inputs match. (7) hash snapshot and all coverage. (8) build canonical `BackupManifestV1`. (9) call `OF01.OP.BACKUP_VERIFY`. (10) publish manifest by same-filesystem atomic replacement last with state `VERIFIED`; do not label `RESTORE_TESTED`.
- **Verification/success:** snapshot integrity, authority/schema/profiles, high-water commit/hash, every referenced object/size/hash, and manifest hash pass.
- **Failure/retry:** Partial output remains `UNVERIFIED`; rerun under a new backup ID or safely resume only if capability proves identical manifest inputs. Never prune prior backup on failure.
- **Rollback/recovery:** Quarantine incomplete destination; authority remains unchanged.
- **Evidence/postconditions/handoff:** backup ID/manifest/hash/destination/coverage/state and verification report.

## SOP-OF01-005 — Restore and activation

- **Purpose:** Restore one verified authority lineage and activate it safely.
- **Risk/consequence:** Destructive/authority-critical; wrong activation can fork lineage.
- **Required authority:** Recovery operator with explicit activation authorization.
- **Prerequisites/inputs:** stopped target, selected verified backup/manifest, expected authority, custody proof, empty/quarantined target locations, rollback destination.
- **Expected state:** `STOPPED`/inactive; no writer lock owner.
- **Procedure:** (1) preserve/quarantine failed target; never overwrite evidence in place. (2) validate manifest hash, state, tool/profile compatibility; OF-01 v1 does not require a signature. (3) restore SQLite and CAS to staging. (4) call `OF01.OP.RESTORE_VALIDATE` for DB integrity, FKs, record/commit hashes, authority, high-water, receipts, IDs, and full CAS coverage. (5) verify declared custody names only one intended activation lineage. (6) enter activation maintenance control and bind explicit authorization to candidate/manifest. (7) atomically select staged paths by implementation-defined safe mechanism. (8) call `OF01.OP.RESTORE_ACTIVATE`. (9) start through SOP-001. (10) rebuild projections and perform post-restore check.
- **Verification/success:** expected `ledger_authority_id`, highest commit/receipt/record hashes, CAS coverage, full integrity, writer readiness, and projection rebuild all pass.
- **Failure/retry:** Candidate stays inactive/read-only. Correct external prerequisite or select another verified backup; never edit candidate rows/hashes.
- **Rollback/recovery:** Revert activation to preserved prior target when procedure supports it, or remain stopped and restore again.
- **Evidence/postconditions/handoff:** manifest, validation, custody, authorization, path identities, activation, startup, projection results.

## SOP-OF01-006 — Enter maintenance mode

- **Purpose:** Quiesce authoritative admissions for controlled work.
- **Risk/consequence:** Availability impact; active-command ambiguity if mishandled.
- **Required authority:** Maintenance or recovery operator.
- **Prerequisites/inputs:** purpose, requested operations, authorization, drain policy/deadline, expected runtime revision.
- **Expected state:** ready/degraded/write-disabled, not already shutting down.
- **Procedure:** capture status; invoke `OF01.OP.MAINTENANCE_ENTER` with compare-and-set revision; close admission; drain/reject queue; resolve active transaction/receipt; issue lease containing authority, purpose, initiator, authorization, start time, and revision.
- **Verification/success:** mode `MAINTENANCE`, writes rejected with stable code, no active command, reads/checks permitted as policy declares, lease matches target.
- **Failure/retry:** revision or active-command uncertainty stops entry; refresh status and resolve, never force the state.
- **Rollback/recovery:** If no maintenance action started, exit via SOP-007; otherwise follow owning procedure.
- **Evidence/postconditions/handoff:** pre/post status, queue resolution, lease and authorization.

## SOP-OF01-007 — Exit maintenance mode

- **Purpose:** Re-enable writes only after the maintenance postconditions pass.
- **Risk/consequence:** Authority-critical readiness decision.
- **Required authority:** Lease owner or equally authorized maintenance/recovery operator.
- **Prerequisites/inputs:** maintenance lease, operation results, required integrity/backup/migration verification.
- **Expected state:** `MAINTENANCE`; no active maintenance mutation.
- **Procedure:** verify every owning SOP success criterion; run required quick/full check; validate schema/profiles, lock, CAS, configuration, and authority; call `OF01.OP.MAINTENANCE_EXIT` with lease/revision; invalidate lease; reopen admission only if full readiness is true.
- **Verification/success:** mode `READY` or declared `DEGRADED`, readiness true, authorization/lease closed, status evidence captured.
- **Failure/retry:** Remain maintenance/write-disabled; correct failed prerequisite and rerun verification.
- **Rollback/recovery:** Owning SOP restore boundary applies.
- **Evidence/postconditions/handoff:** lease closure, check reports, readiness gates, latest commit.

## SOP-OF01-008 — CAS orphan scan

- **Purpose:** Identify unreferenced objects without deletion.
- **Risk/consequence:** Read-only housekeeping.
- **Required authority:** Ledger/maintenance operator; scoped automation may scan.
- **Prerequisites/inputs:** target authority, stable high-water, retention/backup/quarantine inventory.
- **Expected state:** any readable safe state; maintenance not required.
- **Procedure:** invoke `OF01.OP.CAS_ORPHAN_SCAN`; snapshot authoritative artifact content references at high-water; inventory final objects and abandoned temps; compare by hash/size; classify referenced missing/mismatch as fatal and unreferenced as housekeeping; emit canonical scan manifest.
- **Verification/success:** every listed orphan is absent from the reference snapshot; referenced-object defects are separately reported and block writes.
- **Failure/retry:** idempotent; incomplete scan may rerun and cannot authorize GC.
- **Rollback/recovery:** none; no deletion occurred.
- **Evidence/postconditions/handoff:** high-water, reference/inventory counts, orphan/temp/fatal findings, manifest hash.

## SOP-OF01-009 — CAS garbage collection

- **Purpose:** Delete only proven-unreferenced, retention-safe, recovery-safe content.
- **Risk/consequence:** Destructive and potentially irrecoverable.
- **Required authority:** Maintenance/recovery operator with explicit manifest-bound authorization; AI autonomous execution prohibited.
- **Prerequisites/inputs:** maintenance lease; successful SOP-008 manifest; current holds/backups; `OF01.OP.CAS_GC_DRY_RUN` result; authorization naming exact manifest hash.
- **Expected state:** `MAINTENANCE`; no active artifact publication.
- **Procedure:** rerun/validate dry run; compare current high-water and inventories; invalidate authorization if changed; exclude referenced, temp-active, retained, backed-up-needed, quarantined, or legal-held objects; execute `OF01.OP.CAS_GC_EXECUTE` using immutable candidate manifest; record each deletion/result; rescan CAS, run `OF01.OP.CAS_VERIFY`, then `OF01.OP.INTEGRITY_QUICK`; on success exit only through SOP-OF01-007.
- **Verification/success:** only authorized hashes deleted, zero referenced objects affected, post-scan/integrity pass, freed bytes reported.
- **Failure/retry:** Stop on first unexpected identity/state; rerun requires new scan and authorization. Deletion is not generally idempotent; `already_absent` is evidence, not assumed success.
- **Rollback/recovery:** Restore accidentally missing referenced bytes only from verified backup; integrity block and incident handoff.
- **Evidence/postconditions/handoff:** dry-run/authorization/execution manifests, deleted hashes, post-check, lease.

## SOP-OF01-010 — Projection rebuild

- **Purpose:** Recreate a derived projection solely from authoritative commits.
- **Risk/consequence:** Rebuildable target only; authority must remain unchanged.
- **Required authority:** Projection operator.
- **Prerequisites/inputs:** projection name/version, source authority, target identity, source high-water, compatible projector.
- **Expected state:** projection paused/stopped/rebuild-required; ledger readable.
- **Procedure:** capture cursor/error; pause; create empty versioned target or quarantine old target; initialize cursor at zero/safe declared point; call `OF01.OP.PROJECTION_REBUILD`; replay sequence then ordinal idempotently; advance cursor after durable commit application; verify sample/full projected hashes and source high-water; switch readers to rebuilt version under projection policy.
- **Verification/success:** source authority/version match, cursor equals intended high-water, lag zero at verification cut, no projection error, authority DB hash/commit unchanged.
- **Failure/retry:** rebuild is rerunnable into a fresh target; never mutate authority or skip a failing commit silently.
- **Rollback/recovery:** retain old projection until new validation; revert reader routing or restart fresh rebuild.
- **Evidence/postconditions/handoff:** old/new identities, high-water, applied counts, hashes, duration, failures.

This SOP also governs projection version upgrade: pause the old version, build
a fresh target with the new version from authoritative commits, validate both
source lineage and target schema, switch readers only after success, and retain
the prior target for rollback. It MUST NOT upcast a cursor in place.

## SOP-OF01-011 — Projection resume

- **Purpose:** Safely continue an idempotent projection after pause/outage.
- **Risk/consequence:** Derived-state correctness.
- **Required authority:** Projection operator; scoped automation may resume non-destructively.
- **Prerequisites/inputs:** projection identity/version, source authority, cursor, last commit ID, resolved prior error.
- **Expected state:** `PAUSED`, `STOPPED`, or recoverable `DEGRADED`.
- **Procedure:** invoke status; verify cursor is not ahead, source authority and last commit match, target schema/version compatible; call `OF01.OP.PROJECTION_RESUME`; replay next complete commit; advance cursor only after durable idempotent apply; monitor lag/error.
- **Verification/success:** cursor advances monotonically to current cut and projected records match source lineage.
- **Failure/retry:** same commit replay is idempotent. Cursor mismatch/version/content divergence uses SOP-010.
- **Rollback/recovery:** pause without moving cursor; quarantine partial target transaction if target cannot roll back.
- **Evidence/postconditions/handoff:** before/after cursor, commits applied, last error/result.

Projection start is resume from a validated zero/safe-point cursor.
`OF01.OP.PROJECTION_START` creates the versioned target/cursor and applies the
same checks. `OF01.OP.PROJECTION_PAUSE` stops admission of new projection work,
finishes or rolls back the active target transaction, preserves the last fully
applied cursor, and verifies status `PAUSED` before returning. Version mismatch
routes to SOP-010 and `OF01.OP.PROJECTION_UPGRADE`.

## SOP-OF01-012 — Schema migration

- **Purpose:** Apply one reviewed physical schema path without rewriting semantic history.
- **Risk/consequence:** Destructive/authority-critical.
- **Required authority:** Maintenance operator with migration authorization; recovery operator available.
- **Prerequisites/inputs:** supported source/destination, reviewed migration ID/tool version, verified backup ID, rollback/restore plan, maintenance lease, compatibility evidence.
- **Expected state:** `MAINTENANCE`; source integrity passes; no active commands.
- **Procedure:** capture metadata/high-water/hashes; verify backup; validate exact migration path; execute `OF01.OP.MIGRATION_APPLY`; apply ordered transactional steps where SQLite permits; record any nontransactional boundary; verify destination schema, FKs, every preserved record/commit hash, high-water, profiles, CAS references; run full integrity; execute startup/readiness tests; exit maintenance only on success.
- **Verification/success:** destination version exact, no command/domain/commit identity or hash changed, full check and readiness pass.
- **Failure/retry:** unsupported or failed step stops closed. Retry only if migration declares it safe from observed boundary.
- **Rollback/recovery:** transaction rollback before commit; otherwise restore verified backup and verify through SOP-005.
- **Evidence/postconditions/handoff:** migration/backup IDs, source/destination inventories, step results, hash comparison, recovery action.

## SOP-OF01-013 — Ambiguous command commit resolution

- **Purpose:** Determine authoritative command outcome without duplicate history.
- **Risk/consequence:** Command idempotency/authority critical.
- **Required authority:** Original caller, ledger operator, or scoped agent with receipt-read access.
- **Prerequisites/inputs:** original `command_id`, `command_hash`, domain IDs, target authority; unchanged semantic envelope.
- **Expected state:** response/connection/timeout left commit uncertain.
- **Procedure:** stop retries; query `OF01.OP.COMMAND_RESOLVE` by original ID; if same hash receipt exists, return it as success/`was_existing`; if different hash, fail conflict and investigate caller misuse; if proven absent, verify no active unresolved writer operation then resubmit exact same ID/hash/content; resolve again after any repeated ambiguity.
- **Verification/success:** one receipt/commit or proven pre-commit absence; domain IDs unchanged.
- **Failure/retry:** New command/domain IDs are not a retry. Unavailable receipt read stops and escalates; no guessing.
- **Rollback/recovery:** none; authoritative receipt controls.
- **Evidence/postconditions/handoff:** query times/results, original IDs/hash, returned commit or absence proof.

## SOP-OF01-014 — Corruption response

- **Purpose:** Fail safely, preserve evidence, and recover from verified authority.
- **Risk/consequence:** Authoritative fatal.
- **Required authority:** Recovery operator; maintenance operator may contain.
- **Prerequisites/inputs:** fatal finding/error, target authority, access to protected evidence destination and backup inventory.
- **Expected state:** transition to `INTEGRITY_BLOCKED`/writes disabled.
- **Procedure:** call `OF01.OP.WRITE_DISABLE` with the fatal finding and current runtime revision; capture status/lock/active command; preserve DB/WAL/SHM/CAS/logs/config/tool versions using read-only evidence methods after writer shutdown or a consistency-safe snapshot—never an ad-hoc live file-set copy; run bounded `OF01.OP.INTEGRITY_FORENSIC` against preserved/copy as policy permits; classify affected identities/high-water; do not update/delete/recompute; select last verified backup; choose exact-byte CAS restoration when only content is missing and hash proves identity, otherwise perform SOP-005; rebuild projections; run full verification before readiness.
- **Verification/success:** recovered authority matches verified lineage/high-water policy, all hashes/CAS pass, readiness is explicit; original evidence remains preserved.
- **Failure/retry:** forensic scans may rerun. Failed restore remains inactive; try another verified backup or escalate.
- **Rollback/recovery:** no in-place semantic repair; recovery is verified restore/append correction/new governed lineage.
- **Evidence/postconditions/handoff:** full incident handoff fields from runbook, forensic report, backup/restore decisions.

## SOP-OF01-015 — Disk-full / storage-failure response

- **Purpose:** Contain I/O failure without partial commands or unsafe deletion.
- **Risk/consequence:** Authority and availability critical.
- **Required authority:** Maintenance operator; recovery operator if integrity uncertain.
- **Prerequisites/inputs:** storage error codes, affected DB/WAL/CAS/temp path identities, active command ID/hash.
- **Expected state:** admission closed; `WRITE_DISABLED` or `INTEGRITY_BLOCKED` when uncertainty exists.
- **Procedure:** capture free-space/storage/operation evidence; stop new submissions and retry storms; resolve active command receipt; do not delete DB/WAL/referenced CAS/backups; create capacity through infrastructure-approved action or manifest-authorized orphan GC only; verify permissions/filesystem; run quick integrity and referenced-CAS checks; run full check when commit/storage integrity was uncertain; restart through SOP-001.
- **Verification/success:** adequate policy-owned capacity, writable/publish probes pass, receipt resolved, integrity passes, readiness true.
- **Failure/retry:** persistent I/O or failed integrity escalates to SOP-014. Same command retries only with original identities after absence proof.
- **Rollback/recovery:** verified backup restore if storage damaged; no ad-hoc file copy.
- **Evidence/postconditions/handoff:** OS/storage codes, capacity before/after, command resolution, checks, remediation.

## SOP-OF01-016 — Authority clone / development fork

- **Purpose:** Create a safe analysis/development copy that cannot impersonate production authority.
- **Risk/consequence:** Fork/custody critical.
- **Required authority:** Recovery operator for source backup; developer may receive read-only clone.
- **Prerequisites/inputs:** verified backup, clone purpose/owner/destination, explicit choice `READ_ONLY_ANALYSIS` or `REIDENTIFIED_DISPOSABLE`.
- **Expected state:** production unchanged; clone inactive.
- **Procedure:** restore to isolated paths; call `OF01.OP.AUTHORITY_CLONE_VALIDATE`; default to read-only and retain source authority identity only for analysis. If writes are required, obtain exact target authorization and call `OF01.OP.AUTHORITY_REIDENTIFY`, which allocates a new authority ID, removes activation eligibility as source lineage, records source backup/authority as non-authoritative provenance, uses separate lock/CAS/config, and proves production cannot be targeted. Never edit authority ID by SQL.
- **Verification/success:** read-only clone rejects writes; disposable clone reports a different authority and cannot share writer/paths with source.
- **Failure/retry:** identity/path ambiguity stops; destroy only disposable incomplete clone under its authorization, never source.
- **Rollback/recovery:** keep clone read-only or recreate from backup.
- **Evidence/postconditions/handoff:** source backup/authority, clone identity/mode/owner/path identity and write-denial/readiness tests.

## SOP-OF01-017 — Disaster-recovery exercise

- **Purpose:** Prove recovery procedures in a controlled isolated environment.
- **Risk/consequence:** High if target isolation fails; no production activation.
- **Required authority:** Recovery operator plus exercise authorization.
- **Prerequisites/inputs:** selected verified backup, isolated target, expected high-water, exercise plan and success criteria.
- **Expected state:** production remains online/unchanged or deliberately stopped by separate authorization; exercise target inactive.
- **Procedure:** prove isolation; execute restore validation and nonproduction activation under unique custody; verify authority identity/high-water/receipts/domain IDs/record and commit hashes/CAS; start writer safely without connecting producers; submit only an explicitly disposable post-restore probe when plan permits and never against production identity; rebuild projection; exercise shutdown/restart; record recovery-time measurements without declaring SLA; call `OF01.OP.BACKUP_ATTEST_RESTORE_TEST` with the exercise evidence/backup ID; tear down or retain read-only evidence under policy.
- **Verification/success:** every restore-test contract item passes and backup state may advance to `RESTORE_TESTED` with evidence.
- **Failure/retry:** backup remains only `VERIFIED`; preserve failure evidence and repeat with corrected plan/new target.
- **Rollback/recovery:** exercise target remains isolated and inactive; production untouched.
- **Evidence/postconditions/handoff:** plan, isolation proof, manifest, full results/times, projection and restart, teardown/custody.

## SOP-OF01-018 — Release / upgrade

- **Purpose:** Deploy compatible runtime/schema changes with a proven recovery boundary.
- **Risk/consequence:** Authority-critical change control.
- **Required authority:** Release owner plus maintenance/recovery authorization applicable to migration.
- **Prerequisites/inputs:** accepted release ID/source revision, compatibility matrix, migration decision, verified backup, rollback plan, acceptance suite evidence.
- **Expected state:** current authority healthy; release artifacts verified.
- **Procedure:** verify current status/integrity and backup; enter maintenance if code/schema/profile contract requires it; stop admission; deploy exact accepted artifacts; apply SOP-012 when needed; verify canonical profiles/golden vectors; run integrity; start writer; prove readiness; resume commands; verify projection versions/replay; exit maintenance; run documentation/conformance and operational smoke; capture acceptance.
- **Verification/success:** source/tool/schema/profile identities match release, hashes preserved, readiness true, projections compatible, no unauthorized surface changed.
- **Failure/retry:** stop at failing gate; do not partially resume. Reattempt only from declared compatible boundary.
- **Rollback/recovery:** roll back code when schema-compatible or restore verified backup under SOP-005; never down-migrate by unreviewed SQL.
- **Evidence/postconditions/handoff:** release/backup/migration IDs, gates, versions, acceptance, rollback if used.
