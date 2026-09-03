# Reporting-Period Alignment Semantics

## Applicable domains

Exactly two domains have a genuine reporting-period concept on their canonical payload model,
and `build_reporting_period_alignment` only ever resolves a period for these:

| Domain | Payload field |
|---|---|
| `PUBLISHED_SHORT_INTEREST` | `PublishedShortInterestPayload.settlement_date` |
| `SEC_FILINGS` | `SecFilingPayload.period_of_report` |

Every other domain is recorded in `missing_reporting_period_domains` with an
`AGE_ALIGNMENT_REPORTING_PERIOD_NOT_APPLICABLE` diagnostic — no reporting period is ever
fabricated for a snapshot-shaped domain (bars, borrow, halts, news, trades, quotes), and
publication time / receipt time are never substituted for a genuine reporting period.

## Representative period per domain

Mirrors the age-alignment "freshest record represents the domain" rule
(`docs/evidence-age-alignment-semantics.md`): among a domain's point-in-time-eligible
observations with a non-null reporting-period field, the one with the latest
`effective_timestamp` is selected. Its exact `reporting_period_end` date is preserved verbatim.

## Reporting-period age

`reporting_period_age_seconds` on each `ReportingPeriodEntry` is
`build_source_age(observation, as_of, reporting_period_end=period_end).reporting_period_age_days
* 86400` — reusing Phase 2C's existing `reporting_period_age_days` computation, converted to
seconds for consistent units with `EvidenceAgeAlignment`, but never merged into the same
min/max/spread computation as availability age.

## Alignment arithmetic

`earliest_reporting_period_end`/`latest_reporting_period_end` are the min/max of every resolved
period across the requested domains; `reporting_period_spread_seconds` is
`(latest - earliest).days * 86400`, exact `date` arithmetic, no float. No alignment score and no
stale/fresh judgment is computed — a policy-specific staleness threshold, if one is ever needed,
belongs to a future, explicitly-versioned policy layer, not to this alignment result.
