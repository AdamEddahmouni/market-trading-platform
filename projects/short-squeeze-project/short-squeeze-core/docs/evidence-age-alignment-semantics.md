# Evidence Age Alignment Semantics

See ADR 0039 for the rationale behind keeping availability age and reporting-period age
structurally separate. This document covers the mechanics.

## `AgeDimension`

Exactly two members: `AVAILABILITY_AGE` and `REPORTING_PERIOD_AGE`. `EvidenceAgeAlignment`
(built by `build_evidence_age_alignment`) always computes `AVAILABILITY_AGE` — passing any other
dimension raises `ValueError`. Reporting-period age is computed separately by
`build_reporting_period_alignment` (`docs/reporting-period-alignment-semantics.md`); the two are
never combined into one min/max/spread/mean computation.

## Representative age per domain

For a requested domain, `_representative_availability_age` selects the **minimum**
(freshest) `availability_age_seconds` among that domain's point-in-time-eligible observations,
computed by calling `squeeze_core.metrics.source_age.build_source_age(observation, as_of)`
directly (Phase 2C's own, already-tested age function — never reimplemented). Using the freshest
record answers "how current can this domain be treated as of `as_of`," which is the more useful
question for a readiness check than "how old is the oldest thing we still have."

A domain with zero point-in-time-eligible observations contributes no age and appears in
`missing_age_domains`; it is excluded from `youngest_age_seconds`/`oldest_age_seconds`/
`age_spread_seconds`/`mean_age_seconds`.

## Alignment arithmetic

All ages are exact integers (whole seconds, via `int((as_of - effective_time).total_seconds())`
inside `build_source_age`). `age_spread_seconds = oldest - youngest`; a single comparable domain
always yields a spread of exactly `0`
(`AGE_ALIGNMENT_SINGLE_DOMAIN_ONLY` diagnostic); zero comparable domains yields `None`
everywhere (`AGE_ALIGNMENT_NO_COMPARABLE_DOMAINS`). `mean_age_seconds` is a `Decimal`, computed
via `squeeze_core.metrics.statistics.decimal_mean` (the same population-statistics helper Phase
2B uses), never a float.

## No thresholds, no judgments

`EvidenceAgeAlignment` has no `stale`, `fresh`, `acceptable`, or threshold-like field. Age is
reported as plain data; any freshness judgment belongs to a future, explicitly-scoped layer, not
to Phase 2D.
