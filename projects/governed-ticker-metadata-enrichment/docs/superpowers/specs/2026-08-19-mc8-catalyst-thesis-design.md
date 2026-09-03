# MC8 — Catalyst + Thesis Intelligence (fixture-first)

**Status:** Implemented  
**Spec date:** 2026-08-19  
**Scope:** Per-event `CatalystEvidence` and entity-level `ShortThesisInvalidationEvidence` on admitted BOXL clusters  
**Prerequisites:** MC2–MC7 IMPLEMENTED, Platform P0 PIT

## 1. Purpose

Fuse MC7 impact components and MC6 surprise into governed catalyst strength with exposed component scores. Produces short-thesis invalidation when bullish catalyst clusters exceed thresholds. Replaces fixture-direct catalyst heuristics in `market_context_adapter.py` (partial D-13 resolution).

## 2. Scoring model (`catalyst_fusion_v1`)

### Component weights

| Component | Weight (with surprise) | Weight (no surprise) |
|---|---|---|
| Materiality | 0.35 | 0.40 |
| Credibility | 0.30 | 0.35 |
| Novelty | 0.20 | 0.25 |
| Surprise (abs standardized) | 0.15 | — |

`catalyst_strength = weighted_mean(available_components)` capped at 1.0.

**Fail-closed:** when novelty, materiality, or credibility is missing → `catalyst_strength = None`, `publication_state = UNAVAILABLE`, quality flag `CATALYST_COMPONENTS_INCOMPLETE`.

Surprise is optional; weights renormalize when absent.

### Catalyst lean

| `canonical_event_type` | Lean |
|---|---|
| `earnings_beat`, `fda_clearance`, `analyst_upgrade` | BULLISH |
| `offering_risk`, `macro_headwind` | BEARISH |
| other | NEUTRAL |

### Gate

`gate_ok = catalyst_strength is not None and catalyst_strength >= 0.40`

### Short thesis invalidation

Entity-level aggregation across gated **BULLISH** catalysts at PIT cutoff:

- `invalidation_strength = max(catalyst_strength)` among gated bullish rows
- Mechanism tags: `bullish_catalyst_cluster`, `earnings_beat_surprise` (when surprise >= 0.65), `fda_clearance_official` (credibility >= 0.90 + official source)

Threshold for cross-lane `SHORT_THESIS_INVALIDATION`: 0.55 (same as adapter).

## 3. PIT rules

- Score only when `event.available_time <= prediction_cutoff`
- Excluded future clusters produce no evidence rows (fail-closed)

## 4. Cross-lane boundary

- Publishes `CATALYST_STRENGTH` when `catalyst_strength >= 0.50`
- Publishes `SHORT_THESIS_INVALIDATION` when bullish invalidation >= 0.55
- Metadata exposes full component breakdown (resolves MC-D07 catalyst path)
- Does not fuse into SHARED P4 directly; fusion consumes envelopes

## 5. Fixtures

| Fixture | Scope |
|---|---|
| `boxl_raw_documents_slice.json` | Primary BOXL golden pipeline |
| `boxl_expectations_slice.json` | MC6 surprise inputs |
| `boxl_impact_components_expected.json` | MC7 component regression |
| `boxl_catalyst_expected.json` | Golden MC8 regression |

## 6. Workspace

- `catalyst_evidence`, `catalyst_summaries`, `thesis_invalidation_evidence`
- `catalyst_available`, `catalyst_producer_id`, `catalyst_producer_version`

## 7. Research (not implemented)

- Bull/bear thesis graph (MC10 experimental track)
