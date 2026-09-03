# OF-02 Attribution Adapter Operations

| Field | Value |
|---|---|
| Document ID | `OPS-OF02-README` |
| Version | `1.0` |
| Status | `NORMATIVE_RUNTIME` |
| System | `IMP-OF-02` |
| Controlling specification | [OF-02 implementation specification](../../superpowers/specs/2026-08-28-imp-of-02-existing-system-attribution-adapters-implementation-spec.md) |

OF-02 connects existing IMP subsystems to OF-01. It does not replace OF-01
procedures. Use [OF-01 operations](../of-01/README.md) for ledger backup,
restore, integrity, and writer lifecycle.

Capabilities: `OF02.OP.STATUS`, `OF02.OP.ADAPTER_STATUS`,
`OF02.OP.RETROSPECTIVE_DRY_RUN`, `OF02.OP.RETROSPECTIVE_EXECUTE`,
`OF02.OP.RETROSPECTIVE_RESUME`, `OF02.OP.RESOLVE_CONFLICT`,
`OF02.OP.RECONCILE`, `OF02.OP.ENABLEMENT_INSPECT`.

CLI: `python -m market_platform_foundation.of02 status --json`

Enablement is explicit (`IMP_OF02_ENABLED` plus `IMP_OF02_ADAPTER_<ID>`).
Default is disabled.
