# ADR 0014: SEC Filing Public Availability

## Context

A filing period or filed date does not prove when filing metadata was publicly available. Historical evidence must also respect when the local system received it.

## Decision

For the supported offline SEC-shaped record, `source_timestamp` is explicit publication time when present, otherwise exact SEC acceptance time. Date-only publication requires strict rejection, a timezone-bound conservative end-of-date policy, or an uncertain receipt-time placeholder. `received_timestamp` is explicit context ingestion and `effective_timestamp` is the later boundary.

## Consequences

Point-in-time bundles gate public availability, receipt, and effective time independently. Capture time alone cannot establish availability, and remote filing references are never opened.

## Rejected alternatives

Filed date or period-of-report backdating introduces hindsight. Receipt-only gating can admit metadata before its claimed publication. Midnight UTC invents precision.
