# ADR 0032: Normalized Metrics Remain Descriptive

## Context

Phase 2B adds relative volume, volume/return standardization, and return baselines — the first
Phase 2 metrics that compare a current value against a historical distribution rather than
computing a fact about one or two bars in isolation. A comparison-against-history metric is one
step away from a classification ("this ratio is unusually high") in a way Phase 2A's return/gap/
range/baseline metrics never were. The handoff (§9, §35) draws a hard line: normalized does not
mean interpreted.

## Decision

Every Phase 2B `NormalizedMetricResult`/`BaselineStatistics` carries only numeric statistics
(`value`, `mean`, `variance`, `standard_deviation`) and structural metadata (window, sample counts,
provider/session/interval scope, quality, diagnostics). No field, diagnostic code, or unit name
encodes a threshold, label, or classification. `tests/metrics/test_isolation.py` enforces this at
the source-text level (`FORBIDDEN_IDENTIFIER_SUBSTRINGS`) and the model-field level
(`test_no_result_field_could_carry_a_ratio_ranking_or_recommendation`, extended in Phase 2B to
also scan `NormalizedMetricResult` and `BaselineStatistics`), not just by convention.

## Consequences

A caller receiving `relative_volume=2.75` learns exactly one fact — the ratio — and must apply any
threshold, label, or squeeze-relevance judgment entirely outside this package. Phase 2C or later
scoring work can consume Phase 2B's numeric outputs as inputs without Phase 2B itself needing to
change, since nothing about "is 2.75 high" is baked into the metric.

## Rejected alternatives

Adding an optional, caller-supplied threshold parameter that would set a boolean "is_elevated"
field was rejected: even an optional, off-by-default field would give the model a place to carry
interpretation, and the isolation tests would then need to special-case it rather than assert its
absence outright. The handoff's own excluded-metrics list (§11/§35) treats "relative-volume
categories" and "'unusual volume' labels" as explicitly out of scope, not merely deprioritized.
