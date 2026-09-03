# MC10 — Narrative Intelligence (fixture-first, experimental)

**Status:** Implemented  
**Spec date:** 2026-08-19  
**Scope:** Per-theme `NarrativeEvidence` with prevalence, velocity, dispersion, and bull/bear thesis graph on admitted BOXL clusters  
**Prerequisites:** MC3 IMPLEMENTED, MC4 IMPLEMENTED, MC8 IMPLEMENTED, MC9 IMPLEMENTED, Platform P0 PIT

## 1. Purpose

Cluster gated catalyst events into evolving narrative themes (bullish growth vs bearish risk) with measurable prevalence dynamics. Implements the bull/bear thesis graph deferred from MC8. **Experimental** — validate before model decisions (MC-Q8).

## 2. Scoring model (`narrative_clustering_v1`)

### Narrative themes (fixture scope)

| Theme ID | Mapping | Thesis lean |
|---|---|---|
| `bullish_growth_narrative` | MC8 `lean == BULLISH` and `gate_ok` | BULLISH |
| `bearish_risk_narrative` | MC8 `lean == BEARISH` and `gate_ok` | BEARISH |

`NEUTRAL` lean events are excluded from narrative aggregation.

### Prevalence / velocity / acceleration

Chronological PIT-ordered gated catalyst arrivals per entity:

- `prevalence = theme_event_count / total_gated_catalyst_count`
- `velocity = prevalence[t] - prevalence[t-1]` when ≥ 2 theme observations; else `None`
- `acceleration = velocity[t] - velocity[t-1]` when ≥ 3 theme observations; else `None`

### Dispersion

- **Sentiment dispersion** — population stdev of MC4 finbert-or-keyword sentiment scores (−1..1) for events in theme; `None` when < 2 scores
- **Narrative dispersion** — `1 - (max_event_type_count / theme_event_count)` (event-type concentration)

### Thesis graph (display-only)

`NarrativeSummary` exposes `thesis_lean`, `supporting_event_ids`, `opposing_event_ids` (opposite-lean gated events seen at PIT).

## 3. PIT rules

- Score only when `event.available_time <= prediction_cutoff`
- Future clusters produce no evidence rows (fail-closed)

## 4. Quality flags

- `NARRATIVE_HISTORY_INSUFFICIENT` — velocity/acceleration unavailable
- `NARRATIVE_DATA_PARTIAL` — sentiment dispersion unavailable

## 5. Cross-lane boundary

- Publishes `NARRATIVE_SHIFT` when `|velocity| >= 0.10` or `|acceleration| >= 0.05`
- MC10 publishes; Options vol consumers read via SHARED P3 — does not fuse into SHARED P4

## 6. Fixtures

| Fixture | Scope |
|---|---|
| `boxl_raw_documents_slice.json` | MC3 cluster inputs |
| `boxl_catalyst_expected.json` | MC8 catalyst alignment |
| `boxl_narrative_expected.json` | Golden MC10 regression |

## 7. Workspace

- `narrative_evidence`, `narrative_summaries`, `narrative_available`
- `narrative_producer_id`, `narrative_producer_version`
- `research_only: true` with experimental disclaimer

## 8. Out of scope

- Live narrative clustering models / LLM synthesis
- Fusion into SHARED P4 opportunity engine
- Universal narrative rank score in UI
