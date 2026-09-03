# Borrow-Availability Change Metric Semantics

`metrics.borrow_availability_changes` — `BORROW_AVAILABILITY_ABSOLUTE_CHANGE`,
`BORROW_AVAILABILITY_PERCENTAGE_CHANGE`. Structurally identical selection shape to
[`borrow-fee-change-semantics.md`](borrow-fee-change-semantics.md), applied to
`BorrowAvailabilityPayload.available_shares` instead of `annualized_fee_percent`.

## Formula

```
BORROW_AVAILABILITY_ABSOLUTE_CHANGE     = ending.available_shares - starting.available_shares          (SHARES)
BORROW_AVAILABILITY_PERCENTAGE_CHANGE   = (ending - starting) / starting * 100                          (PERCENT)
```

`available_shares` is an exact nonnegative `int` (Phase 1B payload contract) — Phase 2C consumes
it as-is, with no shorthand-unit scaling (the inherited `clean_float`/`Milli_refitting`
`* 1_000_000` pattern found in the archived scripts is never applied anywhere in this file; the
value is already exact shares).

## Selection: `explicit_observation_pair.v1`

Identical to borrow-fee change: one explicit `provider`, two explicit `effective_timestamp`
boundaries, resolved via `pressure_selection.resolve_borrow_observation_at` against
`event_type=BORROW_AVAILABILITY`. No revision/lifecycle concept exists for IBKR borrow data. A
conflicted group at the requested boundary yields no winner. A resolved observation with
`payload.available_shares is None` yields `BORROW_AVAILABILITY_MISSING_VALUE`.

## Scope

`BorrowAvailabilityPayload` carries no venue/scope field at all — IBKR's short-stock file
reports one indicative inventory number per symbol, not a per-venue breakdown. Phase 2C does not
assume this represents the whole market's borrow supply (handoff §12: "Do not assume availability
from one provider represents the whole market") — it is reported as exactly what it is, one
provider's indicative figure, changing over time.

## Zero-denominator asymmetry

`starting.available_shares == 0` (a legitimate, explicitly-reported "nothing available") is a
valid input for the absolute change but a `BORROW_AVAILABILITY_ZERO_START_DENOMINATOR`
(`INVALID`) for the percentage change.

## What this is not

Not a "tightening" or "loosening" classification — sign is preserved and reported (a negative
absolute change is a legitimate decrease, never relabeled), but no qualitative direction word is
ever attached anywhere in this file, verified by a dedicated unit test and the isolation test's
forbidden-substring scan. Not a hard-to-borrow score — `payload.hard_to_borrow` is never read
here either. No threshold, no rank, no recommendation.
