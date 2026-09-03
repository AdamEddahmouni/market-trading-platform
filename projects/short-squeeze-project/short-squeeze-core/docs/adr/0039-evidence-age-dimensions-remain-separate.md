# ADR 0039: Evidence-Age Dimensions Remain Separate and Unmixed

## Context

Phase 2C already established two distinct age concepts on `SourceAgeMetadata`:
`availability_age_seconds` (how long ago a piece of evidence became usable, relative to
`as_of`) and `reporting_period_age_days` (how old the underlying reported fact is, independent
of receipt timing). The handoff's own example --"old short-interest reporting period with
recent receipt" versus "recent market bars with old short-interest reporting period"-- exists
specifically because a naive single "freshness" number collapses two answers that must stay
distinct: a report can be received recently while describing a stale period, and vice versa.

## Decision

`AgeDimension` has exactly two members, `AVAILABILITY_AGE` and `REPORTING_PERIOD_AGE`, and
`EvidenceAgeAlignment`/`ReportingPeriodAlignment` are two separate result models with two
separate min/max/spread/mean computations --never combined into one alignment object or one
number. `EvidenceAgeAlignment` always uses `AVAILABILITY_AGE` (`build_evidence_age_alignment`
raises `ValueError` if asked for anything else), computed via
`squeeze_core.metrics.source_age.build_source_age` directly, reusing Phase 2C's existing,
tested age arithmetic rather than reimplementing it. Per domain, the *representative* age is the
minimum (freshest) `availability_age_seconds` among that domain's point-in-time-eligible
observations --documented explicitly in `docs/phase-2d-design.md` Section 6 as "how current can
this domain be treated as of `as_of`," not "how old is the oldest thing we still have."

## Consequences

No threshold, "stale," or "fresh" classification exists anywhere in either alignment model --
`age_spread_seconds` and `reporting_period_spread_seconds` are reported as plain, exact integers
(or `None` when fewer than one comparable domain exists), and callers must supply their own
interpretation if any is needed. `PUBLICATION_LAG`, `EVENT_AGE`, `CAPTURE_AGE`, and
`RECEIPT_AGE` from the handoff's suggested age-dimension list are deliberately not added as
`AgeDimension` members in this phase, since only availability age and reporting-period age have
an existing, cross-domain-comparable, already-tested computation; publication lag remains
available as raw per-domain metadata (`SourceAgeMetadata.publication_lag_seconds`) without being
promoted to a comparable alignment axis.

## Rejected alternatives

A single `EvidenceAgeAlignment.reporting_period_ages` field alongside the existing
`domain_ages` (both dimensions on one model) was considered and rejected: it would make it too
easy for a future caller to average or compare values across dimensions by accident, exactly the
mistake this ADR exists to prevent. Keeping them as two separate, separately-hashed,
separately-anchored result models makes the distinction structural, not just documented.
