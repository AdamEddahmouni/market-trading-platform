# OF-02 Runbook

| Field | Value |
|---|---|
| Document ID | `RUNBOOK-OF02` |
| System | `IMP-OF-02` |

## Adapter appears disabled

1. Call `OF02.OP.STATUS`.
2. Confirm `IMP_OF02_ENABLED` and the per-adapter flag.
3. Confirm OF writer readiness. Do not enable globally to “see if it works”.

## Native attribution missing after a domain success

Follow SOP-OF02-006. Domain result remains authoritative. C3/C4 failures must
not be hidden.

## Retrospective conflict

Source bytes changed. Do not rewrite the old OF records. Index the new hash as
a new identity (SOP-OF02-005).

## Future-information concern

OF eligibility uses `recorded_at`, not historical event time. A new index
cannot satisfy a historical cutoff.
