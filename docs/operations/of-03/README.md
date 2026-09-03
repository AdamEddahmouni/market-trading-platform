# OF-03 Operations

| Field | Value |
|---|---|
| Document ID | `OPS-OF03-README` |
| Version | `1.0` |
| Status | `NORMATIVE` |
| System | `IMP-OF-03` |

OF-03 is the governed capability, SOP, and workflow **registry**. It describes
what the platform can do and which procedures apply. It does not execute
arbitrary workflows, does not keep execution history, and does not grant
authority.

Canonical machine-readable files: `config/of03/`. Runtime:
`src/market_platform_foundation/of03/`. History remains OF-01.

Operator capabilities:

- `OF03.OP.STATUS`
- `OF03.OP.VALIDATE`
- `OF03.OP.LIST_CAPABILITIES`
- `OF03.OP.LIST_SOPS`
- `OF03.OP.LIST_WORKFLOWS`
- `OF03.OP.SHOW_DEFINITION`
- `OF03.OP.SNAPSHOT`
- `OF03.OP.VERIFY_BINDINGS`
- `OF03.OP.CHECK_DRIFT`

```text
python -m market_platform_foundation.of03 status --json
```

There is no `OF03.OP.EXECUTE_WORKFLOW`.
