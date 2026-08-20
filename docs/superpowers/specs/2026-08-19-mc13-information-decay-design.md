# MC13 — Information Decay / Priced-In (fixture-first, experimental)

**Status:** Implemented  
**Spec date:** 2026-08-19  
**Scope:** Enrich MC12 `ReactionSummary` rows with information decay class, priced-in probability, and remaining information edge on admitted BOXL fixtures  
**Prerequisites:** MC6 IMPLEMENTED, MC7 IMPLEMENTED, MC9 IMPLEMENTED, MC12 IMPLEMENTED, Platform P0 PIT

## 1. Purpose

Estimate how quickly event information decays, how much was anticipated before the event (priced-in), and residual information edge after observed reaction. Resolves MC12 deferral of `priced_in_probability` and `remaining_information_edge`. **Experimental** — contract-valid outputs are not validated for trading decisions (MC-Q9/Q10 adjacency).

**Post-MC12 enrichment pass** — does not reimplement reaction classification or pre-event price calculations.

## 2. Scoring model (`information_decay_v1`)

### A. Information decay class

| `canonical_event_type` | Default class |
|---|---|
| `offering_risk` | `MINUTES` |
| `earnings_beat`, `earnings_miss` | `HOURS` |
| `fda_clearance` | `DAYS` |
| `analyst_upgrade`, `analyst_downgrade` | `WEEKS` |
| unknown / missing | `DAYS` + `DECAY_CLASS_DEFAULTED` |

Fixture `decay_class_override` wins when present.

### B. Priced-in probability (0..1 or None)

| Signal | Source |
|---|---|
| Pre-event price drift | Fixture `pre_event_abnormal_return` |
| Diffusion at event | MC9 `AttentionSummary.diffusion_score` |
| Surprise magnitude | MC8 `CatalystSummary.surprise_score`; else MC6 standardized surprise |
| Override | Fixture `priced_in_override` |

```
components = [
  (0.40, clamp01(pre_event_abnormal_return / 0.03)),
  (0.35, diffusion_score),
  (0.25, 1 - clamp01(abs(surprise_score))),
]
priced_in = weighted_mean(available_components)
```

- Missing all → `None` + `PRICED_IN_DATA_PARTIAL`
- Partial → renormalize + `PRICED_IN_DATA_PARTIAL`

### C. Remaining information edge (0..1 or None)

```
expected = catalyst.materiality_score or catalyst.catalyst_strength
realized = abs(abnormal_return) / 0.03
raw_edge = max(0, expected - realized)
remaining = min(1, raw_edge * (1 - priced_in) * (1 - 0.5 * diffusion_score))
```

Requires MC12 `abnormal_return` and expected impact; else `None` + `REMAINING_EDGE_DATA_PARTIAL`.

### D. PIT rules

- Enrich only when `reaction_summary.available_time <= prediction_cutoff`
- Do not infer pre-event drift without fixture admission

### E. Quality flags

- `DECAY_CLASS_DEFAULTED`
- `PRICED_IN_DATA_PARTIAL`
- `REMAINING_EDGE_DATA_PARTIAL`
- `INFORMATION_DECAY_EXPERIMENTAL` (always on enriched rows)

## 3. Cross-lane boundary

- MC13 enriches Market Context reaction rows only
- Does not fuse into SHARED P4
- Does not replace Options O3 implied-upside priced-in check

## 4. Fixtures

| Fixture | Scope |
|---|---|
| `boxl_decay_slice.json` | Admitted pre-event drift + optional overrides |
| `boxl_decay_expected.json` | Golden MC13 regression |
| `boxl_reaction_expected.json` | Updated with enriched MC13 fields on reaction rows |

## 5. Workspace

- `information_decay_available`
- `information_decay_producer_id`, `information_decay_producer_version`
- Enriched `reaction_summaries` / `reaction_evidence` with `information_decay_class`, `priced_in_probability`, `remaining_information_edge`
- `research_only: true` (workspace-level, shared with MC10)

## 6. Reference only

Donor `internship-project-main/news_momentum_agent/agent/news_decay.py` exponential half-life is **not** wired into MC13 contracts.

## 7. Out of scope

- Live pre-event price/IV ingest
- Learned decay coefficients (MC-Q10 / MC14)
- Fusion into SHARED P4 opportunity engine
