# XA-05 standard operating procedures

## SOP-XA05-001 — Cross-asset strategic state inspection

Inspect reconstructable cross-asset strategic state without granting trading or adaptation authority.

### Steps

1. Run `xa05 status --json` to confirm ephemeral reconstruction mode and zero-cost infrastructure guardrails.
2. Run `xa05 validate --json` to verify classifier versions and authority audit matrix.
3. Run `xa05 construct-state <decision_time> --json` to reconstruct a point-in-time strategic state snapshot.
4. Run `xa05 compare-states <earlier_decision_time> <later_decision_time> --json` to inspect what changed between two decision times.

### Authority

XA-05 inspection is informational analytical-state inspection only. It grants no trading, ledger, risk-limit, execution, or autonomous adaptation authority. Paid cloud infrastructure is not required.
