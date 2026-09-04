# MC9 — Attention / Diffusion (fixture-first)

**Status:** Implemented  
**Spec date:** 2026-08-19  
**Scope:** Per-entity `AttentionEvidence` with separated information value and reflexive impact on admitted BOXL clusters  
**Prerequisites:** MC3 IMPLEMENTED, MC8 IMPLEMENTED, Platform P0 PIT

## 1. Purpose

Measure attention diffusion from MC3 event clusters separately from economic information value (MC8 catalyst components). Resolves MC-D19 (decorative attention UI) and replaces catalyst-confidence proxy attention in `market_context_adapter.py` and `runtime/catalyst_attention.py`.

## 2. Scoring model (`attention_diffusion_v1`)

### Attention level (per cluster)

| Component | Weight | Source |
|---|---|---|
| Document density | 0.40 | `min(1, document_count / 4)` |
| Independent sources | 0.30 | `min(1, independent_source_count / 3)` |
| Corroboration | 0.30 | UNVERIFIED=0.25, PARTIAL=0.60, CORROBORATED=1.0 |

`attention_level = weighted_mean(components)` capped at 1.0.

### Velocity / acceleration

- Chronological series of `attention_level` per entity at PIT
- `attention_velocity = level[t] - level[t-1]` when ≥ 2 observations; else `None` + `ATTENTION_HISTORY_INSUFFICIENT`
- `attention_acceleration = velocity[t] - velocity[t-1]` when ≥ 3 observations; else `None`

### Information value

Weighted mean of available MC8 components:

| Component | Weight |
|---|---|
| `catalyst_strength` | 0.50 |
| `credibility_score` | 0.30 |
| `novelty_score` | 0.20 |

Renormalize when components missing. `None` when no catalyst match.

### Reflexive impact

`reflexive_impact = min(1, attention_velocity × (1 - information_value))` when both available; else `None`.

### Diffusion score

| Component | Weight | Source |
|---|---|---|
| Cluster arrival rate | 0.40 | `min(1, document_count / 2)` |
| Independent source growth | 0.30 | Δ independent sources vs prior cluster |
| Corroboration improvement | 0.30 | Δ corroboration score vs prior cluster |

### Z-score / percentile

Computed from entity attention-level history up to current observation. `None` when < 2 history points.

## 3. PIT rules

- Score only when `event.available_time <= prediction_cutoff`
- Future clusters produce no evidence rows (fail-closed)

## 4. Quality flags

- `ATTENTION_HISTORY_INSUFFICIENT` — velocity/acceleration unavailable
- `SOCIAL_ATTENTION_UNAVAILABLE` — always on fixture scope (no social ingest)
- `ATTENTION_DATA_PARTIAL` — information value missing (no catalyst match)

## 5. Cross-lane boundary

- Publishes `ATTENTION_ACCELERATION` when `attention_acceleration >= 0.05`
- Publishes `INFORMATION_DIFFUSION_ELEVATED` when `diffusion_score >= 0.60` and corroboration improving
- MC9 publishes; SS consumes via `AttentionFeature` adapter — does not own squeeze state

## 6. Fixtures

| Fixture | Scope |
|---|---|
| `boxl_raw_documents_slice.json` | MC3 cluster inputs |
| `boxl_catalyst_expected.json` | MC8 catalyst alignment |
| `boxl_attention_expected.json` | Golden MC9 regression |

## 7. Workspace

- `attention_evidence`, `attention_summaries`, `attention_available`
- `attention_producer_id`, `attention_producer_version`

## 8. Out of scope

- Live social/search attention ingest
- Universal attention rank score in UI
