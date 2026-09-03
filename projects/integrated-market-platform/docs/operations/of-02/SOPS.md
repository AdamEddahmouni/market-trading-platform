# OF-02 Standard Operating Procedures

| Field | Value |
|---|---|
| Document ID | `SOPS-OF02` |
| System | `IMP-OF-02` |

## SOP-OF02-001 — Inspect adapter status

- **Purpose:** Prove enablement, mode, and OF writer readiness.
- **Capability:** `OF02.OP.STATUS` / `OF02.OP.ADAPTER_STATUS`
- **Procedure:** (1) Invoke status. (2) Record adapter ID, enabled, native/retrospective support, last error, writer readiness.
- **Success:** Structured status for every adapter.

## SOP-OF02-002 — Retrospective-index dry run

- **Purpose:** Classify candidates without authoritative writes.
- **Capability:** `OF02.OP.RETROSPECTIVE_DRY_RUN`
- **Procedure:** Supply source paths. Review classification, provenance qualifier, known missing fields, potential conflicts.
- **Success:** `dry_run=true` and zero OF writes.

## SOP-OF02-003 — Execute retrospective indexing

- **Purpose:** Create truthful OF references to historical material.
- **Capability:** `OF02.OP.RETROSPECTIVE_EXECUTE`
- **Procedure:** After dry run, execute. Preserve source hashes. Do not fabricate missing provenance.
- **Success:** counters for discovered/eligible/indexed/legacy_partial/failed.

## SOP-OF02-004 — Resume interrupted indexing

- **Purpose:** Restart a batch without duplicates.
- **Capability:** `OF02.OP.RETROSPECTIVE_RESUME`
- **Procedure:** Re-run the same source set. Already-indexed identities return existing receipts.
- **Success:** no duplicate RegisterRun history.

## SOP-OF02-005 — Resolve attribution conflict

- **Purpose:** Handle same identity with different semantic hash or changed source bytes.
- **Capability:** `OF02.OP.RESOLVE_CONFLICT`
- **Procedure:** Do not rewrite. Keep the original OF records. Index new content as a new identity.
- **Success:** original records unchanged.

## SOP-OF02-006 — Investigate missing native attribution

- **Purpose:** Explain domain success without OF records.
- **Procedure:** Check enablement, writer readiness, consequence class. For C3/C4, withhold or fail closed; never hide.
- **Capability:** `OF02.OP.ENABLEMENT_INSPECT`

## SOP-OF02-007 — Reconcile domain result with OF records

- **Purpose:** Compare subsystem output to OF run/attempt/outcome/disposition.
- **Capability:** `OF02.OP.RECONCILE`
- **Procedure:** Domain IDs remain domain IDs. OF IDs are attribution only. Do not change domain results for attribution convenience.

## SOP-OF02-008 — Disable / re-enable adapter safely

- **Purpose:** Change enablement without altering domain semantics.
- **Procedure:** Clear or set `IMP_OF02_ENABLED` and the adapter flag. Re-check `OF02.OP.STATUS`. Domain engines stay authoritative.
- **Success:** disabled adapters emit no OF commands.
