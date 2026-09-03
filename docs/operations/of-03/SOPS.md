# OF-03 Standard Operating Procedures

| Field | Value |
|---|---|
| Document ID | `SOPS-OF03` |
| Version | `1.0` |
| Status | `NORMATIVE` |
| System | `IMP-OF-03` |

These procedures inspect and change registry **configuration**. They do not
execute domain capabilities and do not grant authority.

## SOP-OF03-001 — Inspect registry status

- **Purpose:** Obtain structured registry health, snapshot hash, and counts.
- **Capability:** `OF03.OP.STATUS`
- **Required authority:** `REGISTRY_OPERATOR` / inspect.
- **Procedure:** (1) Invoke `OF03.OP.STATUS --json`. (2) Record snapshot hash, counts, errors, warnings. (3) Do not treat registration as availability.
- **Success:** Structured status with `valid` boolean.

## SOP-OF03-002 — Validate registry

- **Purpose:** Fail closed on structural corruption.
- **Capability:** `OF03.OP.VALIDATE`
- **Procedure:** Invoke validate. Any ERROR means the registry is not healthy.
- **Success:** `outcome_code=OK` and zero validation errors.

## SOP-OF03-003 — Register a new capability version

- **Purpose:** Add a new capability identity or version without overwriting history.
- **Procedure:** (1) Add a new object in `config/of03/capabilities.json` with a new `definition_version` if the ID exists. (2) Do not reuse the same ID/version with different semantics. (3) Validate. (4) Optionally update the active pointer. (5) Commit.
- **Success:** Exact version resolvable; previous versions remain resolvable.

## SOP-OF03-004 — Register/version an SOP definition

- **Purpose:** Point the registry at normative procedure text.
- **Procedure:** Ensure `docs/operations/.../SOPS.md` contains `## SOP-...`. Add/version the SOP JSON. Do not copy the procedure into JSON as a second authority.
- **Success:** Document path and anchor validate.

## SOP-OF03-005 — Register/version a workflow

- **Purpose:** Record an acyclic governed workflow definition.
- **Procedure:** Add/version workflow JSON with exact capability/SOP versions on steps. Reject cycles. Do not add an executor.
- **Success:** Graph validation passes; historical versions remain resolvable.

## SOP-OF03-006 — Verify implementation bindings

- **Purpose:** Prove bindings exist without invoking them.
- **Capability:** `OF03.OP.VERIFY_BINDINGS`
- **Procedure:** Run verify-bindings. Confirm `invoked=false`. Do not execute restore, GC, promotion, or live smoke to “prove” a binding.
- **Success:** Bound capabilities resolve to approved surfaces; unbound remain unbound.

## SOP-OF03-007 — Deprecate/supersede a definition

- **Purpose:** Stop new use without deleting history.
- **Procedure:** Set deprecation metadata and `superseded_by` to an existing versioned ID. Keep the old definition. Move active pointer if needed.
- **Success:** Deprecated ID still resolvable by exact version.

## SOP-OF03-008 — Resolve registry integrity conflict

- **Purpose:** Handle duplicate identity, hash mismatch, or invalid active pointer.
- **Procedure:** Do not silently drop records. Identify the conflicting ID/version. Restore or add a new version. Re-validate.
- **Success:** Load succeeds fail-closed with zero ERROR findings.

## SOP-OF03-009 — Reconcile documentation/binding drift

- **Purpose:** Align registry references with documents and implementations.
- **Capability:** `OF03.OP.CHECK_DRIFT`
- **Procedure:** Repair missing docs/anchors or update registry references. Binding moves require a new capability version when the binding identity changes.
- **Success:** Drift check has no ERROR findings.

## SOP-OF03-010 — Produce and verify registry snapshot

- **Purpose:** Bind exact registry configuration identity.
- **Capability:** `OF03.OP.SNAPSHOT`
- **Procedure:** Produce snapshot JSON and hash. Confirm determinism by repeating. Attribute consequential acceptance through OF-01 extras using the snapshot hash. Do not create a second ledger.
- **Success:** Identical logical registry yields identical `registry_snapshot_hash`.
