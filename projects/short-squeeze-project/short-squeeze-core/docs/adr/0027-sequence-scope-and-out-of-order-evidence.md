# ADR 0027: Sequence Scope and Out-of-Order Evidence

## Context

A sequence number is meaningless without its provider-declared sequence scope. Arrival, event, and sequence order can disagree.

## Decision

Preserve sequence scope as `PROVIDER_GLOBAL`, `SYMBOL`, `VENUE`, `CHANNEL`, `SESSION`, or `UNKNOWN`. Compare only compatible streams. Diagnose missing, duplicate, conflicting, reset, and out-of-order arrival while retaining input arrival index and deterministic event ordering.

## Consequences

No larger-number or cross-scope ordering is invented. Reset begins a new comparison generation; it does not mutate prior records.

## Rejected alternatives

One global sort would compare incompatible feeds and erase the distinction between arrival and event order.

