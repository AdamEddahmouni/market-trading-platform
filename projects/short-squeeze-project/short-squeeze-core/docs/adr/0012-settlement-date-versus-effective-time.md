# ADR 0012: Settlement Date Versus Effective Time

## Context

The canonical payload already stores settlement and publication dates, while the envelope supplies source, receipt, and effective timestamps. Extending the payload would change existing canonical replay serialization and hashes.

## Decision

Keep schema `1.0.0` and `PublishedShortInterestPayload` unchanged. Settlement date remains the described reporting period; publication date retains calendar precision; publication availability drives source time; and effective time is never set from settlement date. Provider timestamp, capture, market scope, and auxiliary reported fields remain explicit provenance metadata.

## Consequences

Existing observations and Phase 1A-1C hashes remain compatible. Reporting-period age must be computed from payload settlement date separately from availability age.

## Rejected alternatives

Adding defaulted canonical fields would alter old replay bytes. Using opaque capture or ingestion time as settlement meaning would conflate market description with operational availability.
