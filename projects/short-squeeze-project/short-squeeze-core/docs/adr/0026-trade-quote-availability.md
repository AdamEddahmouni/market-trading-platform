# ADR 0026: Trade and Quote Availability

## Context

Event time says when a provider-reported trade or quote occurred. It does not prove provider publication or local receipt, and backdating availability to event time creates hindsight.

## Decision

Canonical source time is the defensible provider publication boundary, received time is explicit local ingestion, and effective time is their maximum. Capture and event time remain separate structured provenance. Strict policy rejects unknown publication; capture- or receipt-based placeholders are explicitly uncertain and never relabeled as publication.

## Consequences

Point-in-time bundles require publication, receipt, effective, and non-future event boundaries. Corrections and cancellations cannot enter historical bundles early.

## Rejected alternatives

Event-only, receipt-only, or capture-only availability loses an independent boundary and can introduce look-ahead.

