# ADR 0037: Borrow-Fee Percentage Points Versus Relative Percentage Change

## Context

`BorrowFeePayload.annualized_fee_percent` is already normalized by the Phase 1B IBKR adapter to
one consistent scale (percentage points, e.g. `5.25` means `5.25%` annualized) regardless of
whether the provider reported `PERCENT_POINTS` or `DECIMAL_FRACTION` on input — the unit
ambiguity is resolved once, at normalization time, and `units_modified` is recorded on
`Provenance` when a conversion occurred. Two different, easily-conflated questions can be asked
about a change in this field: "how many percentage points did the fee move" (an absolute
difference of two already-percent values) and "what fraction of the starting fee did that
represent" (a relative/percentage change). The handoff explicitly warns: "do not call
percentage-point change a percentage change."

## Decision

Two separate metric names, two separate `MetricUnit` values, never one metric with a unit flag:
`BORROW_FEE_ABSOLUTE_CHANGE` (`ending - starting`, `unit=PERCENTAGE_POINTS`) and
`BORROW_FEE_RELATIVE_PERCENTAGE_CHANGE` (`(ending - starting) / starting * 100`,
`unit=PERCENT`). `MetricUnit` gains `PERCENTAGE_POINTS` as a new, distinct member from the
existing `PERCENT` — additive, no existing member's meaning changes. The relative metric treats
a zero starting fee as a valid denominator failure (`BORROW_FEE_ZERO_START_DENOMINATOR`,
`INVALID`); the absolute metric treats it as a perfectly valid input (an explicit zero fee is a
known value, never coerced from missing). `BORROW_AVAILABILITY_ABSOLUTE_CHANGE`/
`_PERCENTAGE_CHANGE` mirror the identical two-metric, two-unit shape for
`available_shares` (in `SHARES`, not a percent-like field, so no percentage-point analogue is
needed there — only the zero-denominator asymmetry repeats).

## Consequences

`payload.hard_to_borrow` is read by no Phase 2C code path (verified by
`tests/metrics/test_borrow_fee_changes.py::test_no_hard_to_borrow_classification_anywhere` and
the isolation-test forbidden-substring scan) — it remains raw, provider-labeled evidence on the
source `Observation`, never reinterpreted into a computed signal. A caller reading a Phase 2C
result never has to guess which scale a `value` is on: the `unit` field and the `metric_name`
always agree, and no formula in `borrow_fee_changes.py` ever divides a percentage-point value by
another percentage-point value expecting a fraction result — that division only happens inside
the explicitly-named relative-change branch.

## Rejected alternatives

A single `BORROW_FEE_CHANGE` metric with a `change_kind: "ABSOLUTE" | "RELATIVE"` request field
was considered and rejected: it would require every consumer to branch on a string to know which
`MetricUnit` to expect, reintroducing exactly the ambiguity two separate, self-describing metric
names eliminate structurally. Converting the relative change to `PERCENTAGE_POINTS`-of-a-
percentage-point (a "percent of a percent") was rejected as needlessly confusing; `PERCENT` is
the correct, already-established unit for a relative change regardless of the underlying field's
own units.
