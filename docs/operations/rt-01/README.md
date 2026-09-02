# RT-01 Operations

| Field | Value |
|---|---|
| Document ID | `OPS-RT01-README` |
| Version | `1.0` |
| Status | `NORMATIVE` |
| System | `IMP-RT-01` |

IMP-RT-01 provides causal tracing and measured latency baselines for executable
runtime paths. It is observability only — not authority, not a ledger, and not
a workflow executor.

Runtime package: `src/market_platform_foundation/rt01/`.

Operator capabilities (registered in OF-03):

- `RT01.OP.STATUS`
- `RT01.OP.VALIDATE_TRACE`
- `RT01.OP.SHOW_TRACE`
- `RT01.OP.BASELINE`
- `RT01.OP.COMPARE`
- `RT01.OP.SAMPLING_STATUS`
- `RT01.OP.EXPORT`
- `RT01.OP.OVERHEAD`

```text
python -m market_platform_foundation.rt01 status --json
```
