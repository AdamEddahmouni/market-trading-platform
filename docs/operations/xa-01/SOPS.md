# XA-01 standard operating procedures

## SOP-XA01-001 — Identity inspection

Inspect canonical instrument identity registry state using XA-01 operator capabilities.

### Steps

1. Run `xa01 status --json` to confirm registry availability.
2. Run `xa01 validate --json` to verify registry integrity.
3. Use `xa01 resolve <provider_id> <alias_value> --json` for alias resolution.
4. Use `xa01 show <canonical_id> --json` to inspect instrument metadata.

### Authority

XA-01 inspection is read-only. Registry membership grants no trading or ledger authority.
