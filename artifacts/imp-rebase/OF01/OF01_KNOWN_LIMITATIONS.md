# IMP-OF-01 known limitations (Tasks 9–16 worktree)

## Runtime

- Windows lacks portable POSIX directory-fsync; CAS publish relies on reopen/hash verification.
- Corruption injection drills may skip when append-only triggers block direct SQL mutation (expected).
- Several operator capabilities return structured stubs pending full service wiring beyond STATUS/METADATA/INTEGRITY_QUICK/SHUTDOWN.
- Operational evidence envelopes are not persisted to a configured evidence root in v1.

## Operations

- Operations docs remain `NORMATIVE_RUNTIME_DRAFT`; CLI binds `status`, `metadata`, and `integrity-quick` only.
- External authorization issuance is out of scope; tests use `FakeAuthorizationVerifier`.

## Acceptance

- Full `tools/validate.py` ladder not re-run in this worktree slice.
- No live authority, merge, or deployment activation performed.
