# ADR 0016: Immutable SEC Amendments

## Context

An amendment can become available after an original filing. Replacing the original would rewrite historical evidence and introduce later knowledge into earlier bundles.

## Decision

Emit originals, amendments, and corrected metadata as separate deterministic observations. When a supported amended accession is present in the same batch, use parent observation IDs and a deterministic correlation ID. Preserve both records, hashes, timestamps, and objective metadata.

## Consequences

Earlier bundles remain reproducible. Later bundles can show both filings and an explicit relationship without selecting a winner or interpreting the amendment.

## Rejected alternatives

In-place mutation loses history. Latest-wins selection embeds hindsight. Treating every declared amendment as an unresolved conflict discards the source-declared relationship.
