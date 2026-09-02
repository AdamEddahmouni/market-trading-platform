# XA-02 standard operating procedures

## SOP-XA02-001 — Admitted source inspection

Inspect admitted macro indicator observations and cross-asset reference relationships.

### Steps

1. Run `xa02 status --json` to confirm admission registry state.
2. Run `xa02 validate --json` to verify catalog relationships and admitted indicators.
3. Run `xa02 admit-fixture --fixture rates_reference_vertical.json --json` for fixture-backed acceptance admission.
4. Use `xa02 show-indicator <canonical_indicator_id> --json` to inspect observations and provenance.
5. Use `xa02 list-relationships --json` to inspect indicator → XA instrument reference map.

### Authority

XA-02 inspection and fixture admission are reference-metadata operations. They grant no trading, ledger, or analytical authority.
