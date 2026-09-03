# ADR 0028: Crossed and Locked Quotes Without Signals

## Context

Two reported quote prices can be normal, locked, crossed, or incomplete. Structure alone does not prove error, direction, liquidity, or an opportunity.

## Decision

Report `NORMAL` when bid is below ask, `LOCKED` when equal, `CROSSED` when bid is above ask, and `UNKNOWN` when a side is absent. A crossed quote may retain known quality; an explicit provider-invalid label is still preserved. No spread or midpoint value is calculated.

## Consequences

One-sided, zero-size, locked, and crossed evidence is representable without bullish, bearish, execution, or trading signals.

## Rejected alternatives

Forcing every crossed quote invalid or actionable invents meaning not supplied by the record.

