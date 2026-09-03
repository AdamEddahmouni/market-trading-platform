# ADR 0025: Session-Aware Bar Evidence Without Indicators

## Context

Bar boundaries need explicit interval and session semantics, while expected gaps require calendar knowledge not present offline.

## Decision

Build deterministic series from explicit boundaries, interval, session, lifecycle, and optional fixture expectations. Report duplicates, overlaps, missing expected intervals, closed sessions, and unknown expectations. Do not calculate indicators, relative volume, momentum, scores, signals, or strategy inputs.

## Consequences

The result is auditable evidence suitable for later consumers but contains no trading interpretation. Unknown calendar state remains unknown.

## Rejected alternatives

Embedding an exchange calendar or deriving technical features would expand Phase 1H beyond normalized evidence.

