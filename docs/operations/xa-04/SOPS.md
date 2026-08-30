# XA-04 standard operating procedures

## SOP-XA04-001 — Durable catalog persistence inspection

Inspect durable cross-asset catalog persistence state without mutating XA-01/02/03 semantics.

### Steps

1. Run `xa04 status --json` to confirm repository backend health and collection counts.
2. Run `xa04 validate --json` to verify XA registry validation findings alongside repository health.
3. Run `xa04 list-catalog --json` to inspect persisted instrument IDs and audit matrix coverage.
4. Use `xa04 show-record <record_kind> <record_id> --json` to inspect a persisted instrument, scalar observation, admission envelope, or cross-asset relationship.

### Authority

XA-04 inspection is reference-metadata persistence inspection. It grants no trading, ledger, analytical positioning, or motive-inference authority. MongoDB Atlas or other paid cloud database services are not required for XA-04 acceptance.
