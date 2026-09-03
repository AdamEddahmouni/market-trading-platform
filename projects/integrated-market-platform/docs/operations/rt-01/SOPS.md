# RT-01 Standard Operating Procedures

| Field | Value |
|---|---|
| Document ID | `SOPS-RT01` |
| Version | `1.0` |
| Status | `NORMATIVE` |
| System | `IMP-RT-01` |

## SOP-RT01-001 — Inspect trace status

- **Purpose:** Confirm sampling mode, collector counts, and span volume.
- **Capability:** `RT01.OP.STATUS`
- **Required authority:** `OPERATOR_INSPECT`
- **Procedure:** (1) Invoke status. (2) Record sampling mode and collector counts. (3) Do not treat traces as OF runs.
- **Success:** Structured status with collector counts.
