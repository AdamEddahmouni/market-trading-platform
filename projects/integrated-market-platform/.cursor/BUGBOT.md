# IMP Bugbot review instructions

Review the complete diff against the repository's authoritative docs. Treat
the following as blocking when violated:

## Trading and authority

- Demo must remain read-only.
- Paper must remain backend-authorized `INTERNAL_SIMULATION` +
  `PAPER_ONLY` behind explicit gates.
- Live must remain observational; `LIVE-001` production execution is blocked.
- Workspace remains the only Paper submit boundary.
- Risk authority must remain upstream of execution; UI capability flags never
  authorize a mutation.

## Identity, time, and persistence

- Account identity and mode must be explicit and isolated in reads, writes,
  caches, query keys, and projections.
- `source_time`, event time, availability, and retrieval time must not be
  conflated or used for look-ahead.
- Persisted decisions and ledger events remain append-only and immutable;
  reconstruction must use authoritative records, not inferred net state.
- Schema changes must preserve legacy records or include an authorized
  migration and tests.

## Frontend state and queries

- The same React Query key must retain the same fetch semantics and response
  shape, including symbol/account/mode dimensions.
- Paper preview must be revalidated after draft or market changes.
- Authority loss must hide or disable mutations while keeping observability
  readable. Demo and Live must not inherit Paper controls.
- Optional API fields must degrade safely; no fabricated market values or
  authority states.

## Review behavior

Prefer high-confidence findings tied to changed lines. Check tests, manifest
ownership, docs, secrets/logging, and failure-closed behavior. Do not request
full-suite execution for every edit; require it for cross-cutting, safety,
validation-infrastructure, or closure changes. Classify dirty-tree failures as
baseline only when current evidence supports that classification.
