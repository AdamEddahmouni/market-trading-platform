# Short-Interest Derived Metric Contract

`metrics.short_interest_changes` — `PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE`,
`PUBLISHED_SHORT_INTEREST_PERCENTAGE_CHANGE`, `PUBLISHED_SHORT_INTEREST_REVISION_DELTA`. See
the archived `phase-2c-design.md` for the full design and
[ADR 0035](adr/0035-published-short-interest-age-remains-explicit.md) for age-metadata rationale.

## Result model

Every Phase 2C short-interest metric returns a `PressureMetricResult`
(`metrics.pressure_models`) — a wholly separate frozen model from Phase 2A's `MetricResult`
and Phase 2B's `NormalizedMetricResult`, since neither has a place for a required bar interval
that published short interest doesn't have. Fields relevant to this family:
`starting_observation_id`/`ending_observation_id`, `starting_reporting_period`/
`ending_reporting_period` (settlement dates), `starting_source_age`/`ending_source_age`
(`SourceAgeMetadata`), `value`, `unit`.

## Selection: `explicit_reporting_period_pair.v1` / `explicit_revision_link.v1`

- Both change metrics take two **explicit** settlement-date reporting periods and one explicit
  `provider` — never an inferred "nearest" period, never provider ambiguity detection.
- `starting_reporting_period == ending_reporting_period` is rejected
  (`PRESSURE_METRIC_IDENTICAL_INPUT`) before any resolution; `starting > ending` is rejected
  (`PRESSURE_METRIC_START_AFTER_END`).
- Each period is resolved independently by `pressure_selection.resolve_short_interest_at_period`:
  eligible `PUBLISHED_SHORT_INTEREST` observations for `(symbol, provider)` are grouped by
  `payload.settlement_date`; same-period conflicts (`Quality.state=CONFLICTED`) yield no winner
  (`PRESSURE_METRIC_CONFLICTED_INPUT`); otherwise the highest `(revision_number,
  effective_timestamp, observation_id)` record is chosen. A `CANCELLED` chosen record yields
  `SHORT_INTEREST_CANCELLED_INPUT` (unavailable, never falls back to an earlier revision). A
  `None` `payload.short_shares` yields `SHORT_INTEREST_MISSING_VALUE` — missing is never `0`.
- `PUBLISHED_SHORT_INTEREST_REVISION_DELTA` takes **one** reporting period, not two: the
  "ending" side is the latest eligible record for that period; the "starting" side is its
  immediate parent via `Observation.parent_observation_ids` (populated by the FINRA normalizer
  from `supersedes_source_record_id`). No revision yet eligible → the period resolves to the
  original record itself, which has no parent, so the metric correctly reports
  `SHORT_INTEREST_REVISION_NOT_FOUND` rather than a self-comparison.
- `previous_short_shares`/`average_daily_volume` in `Observation.provenance.provider_metadata`
  are **never** read as canonical evidence anywhere in this file — they are unverified provenance
  hints, not validated payload fields. Every comparison independently resolves two full
  observations through the selection function above.

## Formulas

```
PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE  = ending.short_shares - starting.short_shares            (SHARES)
PUBLISHED_SHORT_INTEREST_PERCENTAGE_CHANGE = (ending.short_shares - starting.short_shares)
                                              / starting.short_shares * 100                          (PERCENT)
PUBLISHED_SHORT_INTEREST_REVISION_DELTA    = revision.short_shares - original.short_shares          (SHARES)
```

Exact `Decimal` arithmetic under `localcontext(prec=28)`; `short_shares` (exact `int`) is
promoted to `Decimal` before division. `starting.short_shares == 0` is a valid absolute-change
input but a `SHORT_INTEREST_ZERO_START_DENOMINATOR` (`INVALID`) for the percentage metric.

## What this is not

Not short-float recalculation — `payload.short_float_percent` is never read here. Not the
provider's own published `payload.days_to_cover` — see
[`days-to-cover-semantics.md`](days-to-cover-semantics.md) for Phase 2C's own computed figure.
No directional interpretation is ever attached to the sign of `value`: a positive change is not
labeled "increasing pressure," a negative change is not labeled "covering." No threshold,
no score, no rank.
