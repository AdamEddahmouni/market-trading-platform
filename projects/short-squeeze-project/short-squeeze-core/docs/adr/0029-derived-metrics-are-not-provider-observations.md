# ADR 0029: Derived Metrics Are Not Provider Observations

## Context

Phase 2A needs a result type for locally computed return, gap, range, and volume-baseline
values. `contracts.payloads.DerivedIndicatorPayload` and `EventType.DERIVED_INDICATOR` /
`ObservationKind.DERIVED` already exist in the contract but are unused anywhere in `src/`.

## Decision

Do not emit Phase 2A results as `Observation`s. Define a separate, explicitly-typed, frozen
`MetricResult` model in `metrics/models.py` that names every field a derived market metric
needs (window definition, price-field policy, sample counts, input bar boundaries) directly,
rather than folding them into `DerivedIndicatorPayload.parameters: dict[str, Any]`. Reuse,
without wrapping, the existing `Quality` model and `serialization.canonical_json` functions
(both already handle arbitrary Pydantic models), and mirror — not import — the
`contracts.identifiers` deterministic-ID pattern under a distinct namespace UUID.

## Consequences

A `MetricResult` can never be mistaken for provider evidence at the type level, satisfying
`docs/field-semantics.md`'s "a local calculation cannot be labeled as a provider observation."
Metric-specific fields are validated and documented directly instead of living in an untyped
dict. The tradeoff: `metrics/` cannot reuse `Observation`-typed helper functions (e.g.
`replay.observation_order_key`) directly on `MetricResult`; none were needed in Phase 2A.

## Rejected alternatives

Emitting `Observation(event_type=DERIVED_INDICATOR, ...)` directly was rejected: it would force
every metric-specific fact (window, price field, sample counts) into
`Provenance.provider_metadata` or `DerivedIndicatorPayload.parameters`, the same untyped-metadata
pattern already flagged as a Phase 1H compromise, and would blur the "raw evidence vs. derived
metric" boundary this ADR exists to keep sharp.
