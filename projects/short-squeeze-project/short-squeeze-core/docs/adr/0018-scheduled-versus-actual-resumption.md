# ADR 0018: Scheduled Versus Actual Resumption

## Context

Quote and trade resumptions are distinct, and a scheduled time is not proof that either activity actually resumed. The existing canonical payload has one `resume_time`; adding defaulted fields would change legacy canonical bytes.

## Decision

Keep schema `1.0.0` and `TradingHaltPayload` unchanged. Preserve scheduled quote, actual quote, scheduled trade, and actual trade values separately in structured provider metadata. Canonical `resume_time` is populated only for an explicit actual quote- or trade-resumption observation.

## Consequences

Scheduled times never become actual state without a later observation. Canonical consumers retain objective halt/resume status; precise lifecycle distinctions use the documented Phase 1F metadata contract. Phase 1A–1E hashes remain compatible.

## Rejected alternatives

Overwriting a schedule loses history. Treating a schedule as actual fabricates market status. Extending the payload changes old serialization even when new fields default to null.
