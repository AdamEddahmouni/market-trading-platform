# ADR 0019: Immutable Halt Lifecycle Updates

## Context

Halt codes, resumption schedules, cancellations, and actual resumptions can be published after an initial halt. Replacing the original would rewrite historical evidence.

## Decision

Emit every halt announcement, update, correction, cancellation, and resumption as a separate deterministic observation. Link a revision to a prior source record with parent observation IDs and a deterministic correlation ID when resolvable. Preserve exact duplicates diagnostically and retain same-ID content conflicts without winner selection.

## Consequences

Earlier bundles remain reproducible. Later bundles can show compatible lifecycle progression, revisions, and unresolved conflicts while preserving every raw hash and availability boundary.

## Rejected alternatives

In-place mutation loses point-in-time history. Latest-wins selection embeds hindsight. Averaging resumption times creates a value no provider published.
