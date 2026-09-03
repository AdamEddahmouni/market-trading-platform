# ADR 0017: Trading-Halt Public Availability

## Context

A halt-effective time describes market status but does not prove when an announcement was public or locally received. Backdating evidence to the halt or session date would introduce hindsight.

## Decision

For the offline exchange-shaped record, `source_timestamp` is explicit publication time when present, otherwise the explicit public announcement time. `received_timestamp` is adapter-context ingestion and `effective_timestamp` is their maximum. Halt-effective and session-date values never grant availability.

## Consequences

Point-in-time bundles gate public, receipt, and effective time independently. Capture time alone cannot establish availability, and a late announcement can describe an earlier halt without entering earlier bundles.

## Rejected alternatives

Halt-time backdating creates look-ahead. Receipt-only gating can admit a record before its claimed publication. Session-date midnight invents precision.
