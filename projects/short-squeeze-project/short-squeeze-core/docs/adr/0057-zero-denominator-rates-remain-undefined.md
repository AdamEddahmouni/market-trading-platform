# ADR 0057: Zero-denominator rates remain undefined

## Decision

A rate with denominator zero stores its exact `0/0` fraction, an explicit `ZERO_DENOMINATOR` reason, and no Decimal value, percentage, or interval.

## Consequences

The system never fabricates zero, one, NaN, or infinity for an undefined statistic.
