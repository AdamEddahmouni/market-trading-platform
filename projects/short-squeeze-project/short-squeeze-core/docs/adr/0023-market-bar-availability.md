# ADR 0023: Market-Bar Publication, Receipt, and Effective Availability

## Context

An interval boundary, provider publication, and local receipt answer different point-in-time questions.

## Decision

Preserve all three. A bar is eligible only after publication and receipt and when its effective timestamp is not in the future. Never use interval close as a publication proxy.

## Consequences

Historical bundles cannot see late bars or corrections early. Availability, interval, receipt, and correction ages remain auditable.

## Rejected alternatives

Close-time availability creates look-ahead. Receipt-only availability discards provider timing.

