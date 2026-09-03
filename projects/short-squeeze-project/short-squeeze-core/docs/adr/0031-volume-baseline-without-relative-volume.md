# ADR 0031: Volume Baseline Without Relative Volume

## Context

The archived-repository research for Phase 2A (`docs/phase-2a-design.md` section 12) found that
the inherited IB/Schwab adapters compute relative volume as `today_volume / avg_volume` with an
unstable, unfloored trailing average and no time-of-day normalization — flagged in Phase 0's own
reconstruction notes as a still-unresolved gap. The handoff explicitly excludes relative volume,
volume ratio, and volume z-score from Phase 2A (handoff section 11).

## Decision

Implement only the denominator: `MEAN_VOLUME_BASELINE`, the arithmetic mean of eligible
completed/corrected bar volumes over an explicit trailing `BAR_COUNT` window, current bar
excluded by default, with an explicit `minimum_samples` floor and `SampleCounts`
(requested/eligible/used/missing) reported on every result. Do not divide any bar's volume by
this baseline anywhere in Phase 2A.

## Consequences

Phase 2B (or later) can implement relative volume as `current_volume / MEAN_VOLUME_BASELINE.value`
using this baseline as an input, with the numerator/denominator eligibility and unit-compatibility
questions already answered here. Phase 2A itself answers only "what was the eligible historical
volume baseline," never "is current volume unusually high" — no qualitative or comparative
judgment is possible from a `MetricResult` whose only numeric field is the baseline itself.

## Rejected alternatives

Computing relative volume alongside the baseline (since the numerator is "just" the current bar's
own volume, already selected) was rejected even though it would have been a small addition: the
handoff explicitly reserves it for Phase 2B, and folding it in now would pre-empt the
Phase 2B design questions the handoff calls out (standardized price/volume comparisons, explicit
baselines) rather than leaving them for that phase's own design step.
