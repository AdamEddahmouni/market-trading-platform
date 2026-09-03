# MC16 → MC7/MC8 Synthesis Enrichment

**Status:** Design complete — implemented (fixture-first, metadata-only)  
**Spec date:** 2026-08-21  
**Scope:** Optional enrichment of MC7 impact and MC8 catalyst summaries from MC16 `consolidated_channels` on admitted BOXL multi-document clusters  
**Prerequisites:** MC7 IMPLEMENTED, MC8 IMPLEMENTED, MC16 IMPLEMENTED

## 1. Purpose

MC16 publishes separate cluster synthesis fields without replacing MC7 impact components or MC8 catalyst fusion. This addendum wires MC16 outputs into MC7/MC8 as **optional metadata enrichment** — not score fusion and not a universal news score.

## 2. Enrichment model (`synthesis_enrichment_v1`)

When an MC16 synthesis row exists for `cluster_id == event_id` and is PIT-visible at cutoff:

```json
{
  "synthesis_id": "uuid",
  "theme_agreement_score": 0.0,
  "contradiction_detected": false,
  "consolidated_channels": ["REVENUE_UP"],
  "synthesis_confidence": 0.88,
  "enrichment_available": true,
  "scoring_method": "synthesis_enrichment_v1"
}
```

Attached to both `ImpactComponentSummary` and `CatalystSummary` workspace rows.

## 3. Gating rules

| Condition | Behavior |
|---|---|
| No synthesis row for event | No enrichment block (fail-closed) |
| Synthesis `available_time` > cutoff | No enrichment (PIT exclusion) |
| `contradiction_detected == true` | Add `CATALYST_SYNTHESIS_CONTRADICTION`; no corroboration flag |
| `theme_agreement_score >= 0.75` and no contradiction | Add informational `SYNTHESIS_THEME_CORROBORATED` |
| All enriched rows | Add `MULTI_DOCUMENT_SYNTHESIS_EXPERIMENTAL` |

**Score invariance:** `catalyst_strength`, novelty, materiality, credibility, and surprise fields are unchanged in v1.

## 4. Pipeline placement

Post-pass in `build_workspace_market_context_payload` after MC16 synthesis:

1. Build MC7 impact summaries
2. Build MC8 catalyst summaries
3. Build MC16 synthesis summaries
4. Apply `apply_synthesis_enrichment_to_impact` / `apply_synthesis_enrichment_to_catalyst`
5. Serialize enriched summaries into workspace payload

Downstream MC9+ modules continue to consume pre-enrichment summaries within the same request (no circular feedback).

## 5. Fixtures

| Fixture | Role |
|---|---|
| `boxl_synthesis_enrichment_expected.json` | Golden enrichment gate expectations |
| Updated `boxl_impact_components_expected.json` | 3 enriched MC7 rows |
| Updated `boxl_catalyst_expected.json` | 3 enriched MC8 rows |

## 6. Gate tool

`tools/market_context/run_mc16_mc78_enrichment_gate_validation.py`:

- `MC16-MC78-ENRICHMENT` — golden enrichment parity on 3 BOXL clusters
- `MC16-MC78-SCORE-INVARIANCE` — fusion scores unchanged
- `MC16-MC78-PIT` — early cutoff yields 1 enriched row
- `MC16-MC78-DOCTRINE` — no universal/fused news score fields

Report: `evidence/market_context/mc16-mc78-enrichment-gate-report.json`

## 7. Out of scope

- Credibility/catalyst score adjustments from synthesis (future gated v2)
- Live LLM synthesis runtime
- SHARED P4 fusion
- Non-BOXL symbols

## 8. Completion definition

Complete when:

- 3 BOXL clusters carry `synthesis_enrichment` on MC7 and MC8 workspace rows
- PIT adversarial enrichment tests pass
- Score invariance gate PASS
- Gate tool aggregate PASS
- `python tools/validate.py domain market_context` remains green
