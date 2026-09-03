# ADR 0007: Explicit Provider Units and Missing Values

## Context

Borrow fee inputs can be percent points or decimal fractions. Missing and zero lending values have materially different meanings.

## Decision

Require `PERCENT_POINTS` or `DECIMAL_FRACTION` on a present fee. Never infer scaling from magnitude. Preserve explicit zero as `KNOWN_VALUE`, null as `MISSING`, and reject/omit invalid negative, fractional-share, nonnumeric, or unsupported-unit fields without defaulting them.

## Consequences

Provider transformations are visible in provenance, and partial records retain valid evidence without hiding invalid fields. Negative fee/rebate meaning remains unsupported until provider semantics are established.

## Rejected alternatives

Magnitude heuristics fail near unit boundaries. Converting missing/invalid values to zero contaminates later analysis. Treating negative fees as rebates without evidence invents semantics.
