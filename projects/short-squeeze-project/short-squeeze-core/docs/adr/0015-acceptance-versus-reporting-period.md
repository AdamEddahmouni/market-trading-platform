# ADR 0015: SEC Acceptance Versus Reporting Period

## Context

The existing canonical SEC payload stores form, accession, filed time, period, document, and CIK. Adding defaulted acceptance/publication fields would alter old canonical bytes and hashes.

## Decision

Keep schema `1.0.0` and `SecFilingPayload` unchanged. Period of report remains the described period; filed time remains filing metadata; public availability drives source time. Exact acceptance/publication representations and auxiliary objective metadata remain explicit in provenance.

## Consequences

Existing observations remain compatible. Filing, availability, and reporting-period ages are computed separately, and effective time is never the period of report.

## Rejected alternatives

Extending the canonical payload would change old serialization. Hiding accession, form, and CIK entirely in provenance would weaken provider-neutral filing identity.
