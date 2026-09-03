# OF-02 Workflows

| Field | Value |
|---|---|
| Document ID | `WORKFLOWS-OF02` |
| System | `IMP-OF-02` |

These workflows bind adapters to OF-01. They are not a generic orchestrator.

## WF-OF02-001 — Native attribution

existing subsystem result → adapter request → typed OF-01 commands →
`AuthoritativeLedgerWriter` → receipt. Identity is allocated before first
submit. Retries preserve IDs.

## WF-OF02-002 — Retrospective indexing

discover → classify → dry run (`OF02.OP.RETROSPECTIVE_DRY_RUN`) → execute
(`OF02.OP.RETROSPECTIVE_EXECUTE`) → resume if interrupted.

## WF-OF02-003 — Conflict

detect hash/identity mismatch → `OF02.OP.RESOLVE_CONFLICT` → new identity for
new bytes; never rewrite.
