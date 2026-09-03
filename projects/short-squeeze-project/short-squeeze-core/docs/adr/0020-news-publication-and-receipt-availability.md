# ADR 0020: News Publication and Receipt Availability

## Context

Original publication, provider availability, capture, and local receipt describe different facts. Backdating a locally received provider record to a headline date or capture time would introduce hindsight.

## Decision

For offline objective news, `source_timestamp` is explicit provider availability when supplied, otherwise the defensible source-declared publication boundary. A lifecycle update may use its explicit update boundary when no distinct availability value exists. `received_timestamp` is adapter-context ingestion and `effective_timestamp` is their maximum. Capture alone never establishes availability. Date-only values require strict rejection, timezone-bound conservative end of day, or an explicitly uncertain receipt placeholder.

## Consequences

Point-in-time bundles gate source availability, receipt, and effective time independently. Original publication remains canonical payload metadata and is not overwritten by an update.

## Rejected alternatives

Midnight fabricates precision. Receipt-only gating can admit evidence before claimed provider availability. Capture time cannot prove provider publication.
