# ADR 0021: Explicit News Symbol Association Only

## Context

Archived news paths inferred ticker relevance from title, summary, or request context. Those heuristics can misattribute general or company-name-only stories and are not objective source relationships.

## Decision

Canonical news observations keep `symbol=null` and retain only explicit source- or fixture-supplied associations in `NewsItemPayload.associated_symbols`. Symbol-specific evidence selection tests membership in that tuple. Missing and explicitly empty associations normalize but cannot enter a symbol bundle.

## Consequences

One multi-symbol provider record remains one observation. Phase 1G performs no headline, company-name, URL, query, or prior-observation entity resolution.

## Rejected alternatives

Duplicating one article per symbol changes provider-record identity. Selecting the first symbol privileges an arbitrary association. Text inference exceeds objective metadata normalization.
