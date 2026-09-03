# ADR 0022: Immutable News Updates Without Semantic Deduplication

## Context

Articles can be updated, corrected, withdrawn, deleted, duplicated, or syndicated. Overwriting or fuzzy-merging records would rewrite historical evidence and introduce subjective similarity decisions.

## Decision

Emit every lifecycle record as an immutable observation with its own raw hash, availability, receipt, content snapshot, and provider identity. Link only explicit provider IDs, canonical URLs, or provider-declared relationships. Suppress exact raw duplicates diagnostically, preserve same-ID changed content as conflicted, and keep same-URL cross-provider observations independent with a deterministic syndication relationship.

## Consequences

Earlier bundles remain reproducible. Later bundles can expose lifecycle, conflict, and syndication without a provider winner or semantic merge.

## Rejected alternatives

Latest-wins mutation loses point-in-time history. Headline similarity, embeddings, fuzzy matching, and generated summaries are interpretive and nondeterministic for this phase.
