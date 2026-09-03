# ADR 0066: IBKR UNKNOWN bar semantics are accepted with provenance

## Status

Accepted for Phase 3E.

## Context

Batch 05 collected historical 1-minute TRADES bars for 13 symbols via the authenticated
IB Gateway (localhost port 4001). Batch 06 exhaustively resolved the bar semantics by
consulting official Interactive Brokers documentation and the installed `ibapi` contract.

Three fields remain honestly unresolved after this investigation:

1. **Volume adjustment (`volume_adjustment_semantics`).** Official docs state split
   adjustment for TRADES **price** but are silent on volume corporate-action treatment.
   Per project policy, volume adjustment is not inferred from price adjustment.

2. **Bar start/end semantics (`timestamp_semantics`).** Only the daily-bar close-date
   rule is officially documented; intraday bar start/end is absent from both the
   documentation and the installed API contract. Batch 05's `START` assumption is
   withdrawn.

3. **Volume unit (shares vs round lots).** The setting lives in IB Gateway's obfuscated
   binary configuration; it cannot be recovered without guessing or reverse-engineering.
   This field is not in the `IntakeManifest` schema, so it does not gate preflight, but
   it is recorded as provenance.

The existing intake contract (``_manifest_semantic_codes`` in
``local_bar_intake/normalization.py``) treats any `UNKNOWN` declaration for
`volume_adjustment_semantics` or any `timestamp_semantics` value outside
{``START``, ``END``} as a fatal `MISSING_ADJUSTMENT_SEMANTICS` or
`MISSING_TIMESTAMP_SEMANTICS` error, blocking normalization entirely. This is correct
for ordinary provider data where the semantics **should** be known — but for IBKR TRADES
bars the `UNKNOWN` values are an **honest, documented limitation**, not a configuration
error or an omission.

## Decision

Accept `UNKNOWN` declarations for `volume_adjustment_semantics` and
`timestamp_semantics` when the artifact provider is an Interactive Brokers source
(identified by an explicit provider-name match or a `semantic_provenance_source`
field on the manifest). The `UNKNOWN` value is recorded in every normalized bar's
semantic fields, preserving the honest limitation through the entire pipeline.

This acceptance is **provider-scoped** — it applies only to IBKR-sourced artifacts.
For any other provider, `UNKNOWN` for adjustment or timestamp semantics remains a
fatal `MISSING_ADJUSTMENT_SEMANTICS` or `MISSING_TIMESTAMP_SEMANTICS` rejection. No
broader validation is weakened.

## Consequences

### Positive

- The 13 IBKR detection-context bar artifacts can be normalized into the `MARKET_BARS`
  evidence domain, constructing the `NORMALIZED_POINT_IN_TIME_EVIDENCE` layer needed for
  Phase 3A evaluation.
- The IBKR semantics resolver (``ibkr_semantics/resolver.py``) already documents the
  unresolved fields via its `unresolved_fields` tuple; this provenance is preserved.
- The `UNKNOWN` values propagate through the canonical bar records and into any
  downstream metric or evaluation, so the honest limitation is never hidden.

### Negative

- Any downstream consumer of the normalized bars must handle `UNKNOWN` semantic fields
  gracefully. Phase 2A/2B metrics that depend on volume (e.g., relative volume) already
  have `INSUFFICIENT_DATA` paths for cases with insufficient bar history, so this is
  not a new concern.
- The normalized bars carry `UNKNOWN` adjustment semantics, which means any analysis
  that assumes a particular price or volume adjustment regime must explicitly account
  for the uncertainty. This is consistent with the project's principle of preserving
  honest limitations.

### Risks and mitigations

- **Risk:** The provider-name-based scope could be too broad if a non-IBKR provider
  shares the same provider name. **Mitigation:** The provider name is declared in the
  manifest and verified against the artifact hash. A collision would require an
  intentionally misleading manifest, which is independently detectable.
- **Risk:** The `UNKNOWN` timestamp semantics could affect bar boundary calculations.
  **Mitigation:** The bar normalization uses the IBKR-supplied timestamp as the
  event_start_time directly (not as end-of-interval), consistent with the standard
  ＂calendar-bar＂ convention. The `timestamp_semantics` field records `UNKNOWN` as a
  limitation; downstream analyses can apply their own convention-aware handling.

### Compatibility

- Existing Batch 01-06 artifacts are unchanged. No committed fixture bytes are modified.
- Non-IBKR preflights continue to reject `UNKNOWN` semantics as before.
- The `IntakeManifest` schema version stays `1.0.0`. The provider-name check is an
  operational validation rule, not a schema change.
- Phase 3D acquisition tests that verify `PREFLIGHT_REJECTED` for IBKR artifacts will
  need their expected values updated to reflect the new acceptance.
