# ADR 0035: Published Short-Interest Age Remains Explicit

## Context

The archived-repository research for Phase 2C (`docs/phase-2c-design.md` section 16) found that
the inherited `core/ib_borrow_rate.py` stamps a borrow-fee record's `as_of` from the local fetch
time, discarding the feed's own business-timestamp line entirely — a provenance defect distinct
from a look-ahead defect: it doesn't use future data, it mislabels when the data was true as-of.
Separately, ADR 0011/0012 already establish that a FINRA settlement date is reporting-period
metadata, never an availability boundary, and `evidence/models.py`'s `ObservationAge` already
carries a `reporting_period_age_days` field distinct from `availability_age_ms` at the evidence-
bundle layer. Phase 2C's metrics layer needed its own answer: when a `PressureMetricResult`
compares two point-in-time records, should it report one age or two?

## Decision

Every resolved short-interest observation gets a `SourceAgeMetadata` (`metrics/source_age.py`)
carrying `provider_publication_time`, `local_receipt_time`, `effective_time`,
`availability_age_seconds` (freshness of the *evidence*), and, when a reporting period applies,
`reporting_period_end`, `reporting_period_age_days` (staleness of the *fact itself*), and
`publication_lag_seconds`. The two age concepts are never collapsed into one number: a report
received five minutes ago about a six-month-old settlement period has a small
`availability_age_seconds` and a large `reporting_period_age_days` simultaneously, and both are
visible on the result. `reporting_period_age_days` deliberately reuses the exact name and
`(as_of.date() - settlement_date).days` formula already established by
`evidence/models.py::ObservationAge.reporting_period_age_days` and `evidence/builder.py`, rather
than inventing a second, differently-typed convention for the same fact.

## Consequences

A stale numerator is always visible on `DaysToCoverComponents`/short-interest change results,
never silently treated as fresh and never excluded merely for being old — no staleness threshold
is invented anywhere in Phase 2C. Borrow observations (`BORROW_FEE`/`BORROW_AVAILABILITY`) carry
`reporting_period_end = None` since they have no reporting-period concept at all — this is the
structural fix to the `ib_borrow_rate.py` defect: `provider_publication_time` always reflects the
observation's own `source_timestamp`, which Phase 1B's normalizer already parses from the
provider's own timestamp (never substituting ingestion time except as an explicitly-diagnosed
uncertain placeholder), so no "fetch time standing in for feed time" ambiguity can reach a
Phase 2C result.

## Rejected alternatives

A single generic `age_seconds` field (as the handoff's own suggested field list could be
misread to imply) was rejected: it cannot represent "freshly received, badly stale report" and
"just-published, current report" as two different states, which is exactly the ambiguity ADR
0004/0011 were written to eliminate. Seconds-precision `reporting_period_age_seconds` (the
handoff's literal suggested name) was also considered and rejected in favor of the existing
day-precision `reporting_period_age_days` convention already anchored at the evidence layer —
introducing a second, seconds-precision convention for the identical concept would itself be the
kind of duplicated point-in-time policy ADR 0030 warns against.
