# OF-03 Workflows

| Field | Value |
|---|---|
| Document ID | `WORKFLOWS-OF03` |
| Version | `1.0` |
| Status | `NORMATIVE` |
| System | `IMP-OF-03` |

These are administrative registry workflows. They are not a generic business
workflow execution system.

## WF-OF03-001 — Register new definition

Edit candidate JSON → `OF03.OP.VALIDATE` → review → commit. Active pointer
unchanged unless explicitly approved.

## WF-OF03-002 — Version existing definition

Copy prior version semantics into a new `definition_version` → apply semantic
edits only on the new version → validate → optional active-pointer change.

## WF-OF03-003 — Validate candidate registry

`OF03.OP.VALIDATE` must be ERROR-free before merge. Fail closed.

## WF-OF03-004 — Verify bindings

`OF03.OP.VERIFY_BINDINGS` without invoking destructive or live capabilities.

## WF-OF03-005 — Approve active-version change

Human review of exact id+version → update `manifest.json` pointer → validate
snapshot hash change → commit. No implicit latest.

## WF-OF03-006 — Deprecate definition

SOP-OF03-007 → keep historical version → retarget active pointer.

## WF-OF03-007 — Reconcile drift

SOP-OF03-009 → repair docs or registry → re-validate.

## WF-OF03-008 — Produce acceptance snapshot

`OF03.OP.SNAPSHOT` → record hash in acceptance artifacts → optional OF-01
attribution of the snapshot identity.
