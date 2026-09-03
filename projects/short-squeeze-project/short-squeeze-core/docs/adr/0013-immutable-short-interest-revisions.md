# ADR 0013: Immutable Short-Interest Revisions

## Context

Corrections can arrive after an original published record. Overwriting the original would rewrite historical evidence and make an earlier bundle depend on later knowledge.

## Decision

Emit every original, correction, revision, or cancellation as a separate deterministic observation. When a supported source-record link is present in the same batch, use `parent_observation_ids` and a deterministic correlation ID to connect the new observation to its prior record. Preserve both raw hashes, publication times, and receipt times.

## Consequences

Earlier bundles remain reproducible. Later bundles may include both records and an explicit supersession relationship without deleting, averaging, or selecting a provider winner.

## Rejected alternatives

In-place mutation loses point-in-time history. Silent latest-wins selection embeds hindsight. Treating a supported correction as an unresolved value conflict obscures its declared relationship.
