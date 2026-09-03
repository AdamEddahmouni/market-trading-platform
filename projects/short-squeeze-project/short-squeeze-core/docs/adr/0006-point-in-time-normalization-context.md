# ADR 0006: Explicit Point-in-Time Normalization Context

## Context

Using wall time or equating source and ingestion timestamps makes offline replay irreproducible and hides timestamp uncertainty.

## Decision

Require an immutable context with explicit timezone assumption, ingestion time, provider/version labels, entitlement, and collection method. Missing source time is diagnosed and represented with ingestion time only as an uncertain placeholder; an unknown timezone on a naive timestamp rejects.

## Consequences

The same record/context yields byte-identical output. Changing ingestion time changes only ingestion-dependent fields and canonical hashes. Callers must make timestamp assumptions visible.

## Rejected alternatives

Calling `datetime.now`, silently copying ingestion time into source time, or assigning UTC to naive values would fabricate point-in-time evidence.
