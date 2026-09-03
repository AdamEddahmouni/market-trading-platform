# Foundational Market Metric Contract

This document specifies the common contract every Phase 2A metric (`squeeze_core.metrics`)
follows. Per-metric formulas are documented separately:
[`return-metric-semantics.md`](return-metric-semantics.md),
[`session-gap-metric-semantics.md`](session-gap-metric-semantics.md),
[`bar-range-metric-semantics.md`](bar-range-metric-semantics.md),
[`volume-baseline-semantics.md`](volume-baseline-semantics.md).

Phase 2B (normalized market-activity metrics: relative volume, volume/return z-scores, return
baselines) builds on this contract by composition rather than modifying it — see
[`normalized-market-activity-contract.md`](normalized-market-activity-contract.md). `MetricResult`
itself, documented below, is unchanged by Phase 2B in every field and byte.

Phase 2C (short-interest and borrow-pressure metrics) reuses `MEAN_VOLUME_BASELINE`'s selection
and arithmetic for `DAYS_TO_COVER`'s denominator only, via its own standalone
`PressureMetricResult`/`DaysToCoverComponents` models — see
[`days-to-cover-semantics.md`](days-to-cover-semantics.md) and
[`phase-2c-design.md`](phase-2c-design.md) §8.3. `MetricResult` itself is unchanged by Phase 2C
in every field and byte.

## Raw evidence versus derived metrics

Phase 1 stores objective, provider-reported observations. Phase 2A derives objective numeric
facts from those observations. A `MetricResult` is a **local calculation**: it names its own
calculation and version, and it retains the `observation_id`s of the bars it was computed from.
It is never serialized or presented as if a provider supplied it directly. See
[ADR 0029](adr/0029-derived-metrics-are-not-provider-observations.md).

## Result fields (`metrics.models.MetricResult`)

| Field | Meaning |
|---|---|
| `metric_name` | One of `ABSOLUTE_RETURN`, `PERCENTAGE_RETURN`, `ABSOLUTE_SESSION_GAP`, `PERCENTAGE_SESSION_GAP`, `ABSOLUTE_BAR_RANGE`, `PERCENTAGE_BAR_RANGE`, `MEAN_VOLUME_BASELINE`. |
| `metric_version` | The formula/contract version (`"1.0.0"` for every Phase 2A metric). A semantic formula change requires a new version; old versions' results are never mutated. |
| `calculation_policy_version` | The *selection policy* version (price-field default, denominator choice, current-bar exclusion) — independent of `metric_version` because the same formula can run under different explicit policies. |
| `symbol`, `asset_class`, `as_of`, `source_interval`, `session_scope`, `provider_scope`, `provider` | The full request identity — every value that could change the result. |
| `price_field` | Returns/gaps only: `OPEN`/`HIGH`/`LOW`/`CLOSE`. `None` for ranges/volume baselines. |
| `window` | Volume baseline only: `TrailingWindow(window_type, requested_count, exclude_current_bar, minimum_samples)`. `None` elsewhere. |
| `value` | The exact `Decimal` result, or `None` iff `quality.state is not KNOWN_VALUE` — a missing value is never `Decimal("0")`. |
| `unit` | `PRICE`, `PERCENT`, `SHARES`, or `UNKNOWN`. |
| `input_observation_ids` | Sorted tuple of every Phase 1H `Observation.observation_id` used. |
| `input_bar_boundaries` | Sorted `BarBoundaryRef(bar_start, bar_end, observation_id)` per contributing bar. |
| `sample_counts` | Volume baseline only: `SampleCounts(requested, eligible, used, missing)`, where `used + missing == eligible`. |
| `quality` | `contracts.quality.Quality`, reused verbatim (see below). |
| `diagnostics` | Sorted tuple of `MetricDiagnostic(code, severity, message, observation_ids)`. |
| `deterministic_id` | UUIDv5 over every identity field above except `value` and `diagnostics` (see below). |

## Quality states

Phase 2A reuses `contracts.enums.QualityState` rather than inventing a metrics-only quality enum:

| Situation | `QualityState` |
|---|---|
| Value computed, no issue | `KNOWN_VALUE` |
| Volume baseline computed below `requested_count` but at/above `minimum_samples` | `KNOWN_VALUE` with `completeness=PARTIAL` |
| Missing input, insufficient history, ambiguous provider, incompatible scope | `UNAVAILABLE` |
| Zero/invalid denominator, invalid request shape, same-session gap pair | `INVALID` |
| Unresolved same-boundary conflicting bars | `CONFLICTED` |

## Diagnostics

`metrics.diagnostics.MetricDiagnosticCode` defines every code Phase 2A actually emits (see that
module for the authoritative list — `tests/metrics/test_diagnostics.py` regression-tests the
exact set). Diagnostics are sorted by `(code.value, observation_ids, message)`, matching the
`evidence.bars.BarSeriesDiagnostic` sort convention.

## Deterministic identity

`metrics.identifiers.deterministic_metric_id` mirrors `contracts.identifiers.deterministic_observation_id`:
a UUIDv5 over a `json.dumps(..., sort_keys=True, separators=(",",":"))`-encoded identity dict,
under `METRIC_NAMESPACE` (distinct from `OBSERVATION_NAMESPACE` — a metric ID can never collide
with an observation ID). The identity includes every field that affects the result and
deliberately **excludes** `value` and `diagnostics`: identical inputs and policy always produce
the same ID, independent of the arithmetic outcome.

## Selection and no-look-ahead

Every metric selects its input bars through `metrics.selection`, which is built directly on
`evidence.bars.build_bar_series` — the same point-in-time (`source_timestamp`/
`received_timestamp`/`effective_timestamp` all `<= as_of`), symbol/interval/session filter Phase
1H already enforces. See [ADR 0030](adr/0030-point-in-time-market-metric-selection.md) and
[`docs/point-in-time-evidence-policy.md`](point-in-time-evidence-policy.md).

Lifecycle resolution: among same-boundary candidates, the latest revision (by `revision_number`)
eligible as of `as_of` wins. `PARTIAL` and `CANCELLED` latest-revisions are excluded with a
specific diagnostic (`METRIC_PARTIAL_INPUT`, `METRIC_CANCELLED_INPUT`); unresolved `CONFLICTED`
groups are excluded with `METRIC_CONFLICTED_INPUT`. A correction or cancellation only affects a
metric once its own `source_timestamp`/`received_timestamp`/`effective_timestamp` are `<= as_of`
— a `MetricResult` computed at an earlier `as_of` is never mutated; recomputing it at the same
`as_of` later is byte-identical.

Provider scope: `SINGLE_PROVIDER` (Phase 2A's only implemented scope) requires an explicit
`provider` when more than one distinct provider publishes at a relevant boundary/window; omitting
it in that case yields `METRIC_AMBIGUOUS_PROVIDER`, not an implicit choice or an average.

## Decimal and rounding

All arithmetic uses Python `Decimal` under an explicit `localcontext(prec=28)` (independent of any
ambient context a caller might have mutated). Canonical values are never quantized for storage;
`serialization.canonical_json` strips trailing zeros consistently with every other domain in this
repository. No `float` appears anywhere in a metric formula.

## Excluded by design

Relative volume, volume ratio/z-score, dollar volume, turnover, any technical indicator (moving
averages, RSI, MACD, ATR, Bollinger/Keltner, TTM Squeeze), momentum/breakout/trend/gap
classification, candidate scoring, ranking, Prime/Subprime, recommendations. See
[ADR 0031](adr/0031-volume-baseline-without-relative-volume.md) for the volume-specific rationale.
