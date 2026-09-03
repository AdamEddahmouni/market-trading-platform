# MC7 — Novelty / Materiality / Credibility (fixture-first)

**Status:** Implemented  
**Spec date:** 2026-08-19  
**Scope:** Per-event `NoveltyEvidence`, `MaterialityEvidence`, and `CredibilityEvidence` on admitted BOXL clusters  
**Prerequisites:** MC2–MC6 IMPLEMENTED, Platform P0 PIT

## 1. Purpose

Decompose information impact into governed component evidence objects. Resolves MC-D07 by exposing novelty, materiality, and credibility separately — not a single opaque catalyst scalar.

## 2. Scoring model (`impact_components_v1`)

### Novelty

| Field | Formula |
|---|---|
| `duplicate_probability` | syndicated docs / `document_count` |
| `incremental_information_score` | `independent_source_count / document_count` |
| `novelty_score` | `max(0, 1 - duplicate_probability)` |

Quality: `NOVELTY_UNCERTAIN` when `EVENT_CLUSTER_UNCERTAIN`; `EVENT_DUPLICATE` retained from MC3.

### Materiality

Base weights by `canonical_event_type`:

| Type | Base |
|---|---|
| `fda_clearance` | 0.85 |
| `earnings_beat` | 0.75 |
| `offering_risk` | 0.70 |
| `analyst_upgrade` | 0.45 |
| `macro_headwind` | 0.35 |

Metric boosts (capped at 1.0): revenue +0.15, margin +0.10, price_target +0.05.

`materiality_basis`: e.g. `event_type:earnings_beat+metric:revenue=42.5`

`MATERIALITY_UNKNOWN` when base < 0.40 and no extracted metrics.

### Credibility

Per-document tier score (max across cluster) + corroboration bonus:

| Source profile | Score |
|---|---|
| official + first_party company/regulatory | 0.95 |
| official regulatory filing | 0.90 |
| wire primary | 0.65 |
| analyst | 0.55 |
| media secondary | 0.45 |

Corroboration: `CORROBORATED` +0.05, `PARTIALLY_CORROBORATED` +0.02.

`SOURCE_LOW_CREDIBILITY` when UNVERIFIED, no official source, max score < 0.60.

## 3. PIT rules

- Score only when `event.available_time <= prediction_cutoff`
- Excluded future clusters produce no evidence rows (fail-closed)

## 4. Cross-lane boundary

- Publishes `NOVELTY_HIGH`, `MATERIALITY_HIGH`, `CREDIBILITY_HIGH` when component scores exceed thresholds (0.65 / 0.70 / 0.75)
- Metadata exposes full component breakdown (MC-D07)
- Does not fuse into SHARED P4; does not replace catalyst-lane `CATALYST_STRENGTH` (MC8)

## 5. Fixtures

| Fixture | Scope |
|---|---|
| `boxl_raw_documents_slice.json` | Primary BOXL golden pipeline |
| `boxl_syndication_slice.json` | Syndication adversarial novelty |
| `boxl_impact_components_expected.json` | Golden regression |

## 6. Workspace

- `impact_components_available`, `novelty_evidence`, `materiality_evidence`, `credibility_evidence`, `impact_component_summaries`

## 7. Acceptance

MC7 complete when PIT adversarial tests pass, golden `boxl_impact_components_expected.json` matches, syndication novelty tests pass, and cross-lane component metadata publishes without SHARED P4 fusion.
