# Explainability Contract

**Status:** `PROPOSED` — UI requirements; backend schema not finalized

## Explanation chain

Every meaningful nontrivial result exposes a discoverable path:

```
RESULT
 ↓ What does this mean?
 ↓ Why does it matter?
 ↓ What supports it?
 ↓ What conflicts with it?
 ↓ How was it derived?
 ↓ What inputs were used?
 ↓ When were they available?
 ↓ What is their quality?
 ↓ Where did they come from?
 ↓ ORIGINAL EVIDENCE
```

Not every layer is visible initially. Progressive disclosure via **Explain** action and Evidence Inspector.

## UI interaction pattern

### Entry points
- `[Explain]` on cards, alerts, table rows, chart selections
- `E` keyboard shortcut on focused item
- AI sidecar: "Explain this" inherits selection
- Inspector opens at appropriate depth

### Explanation drawer (Levels 1–2)

Slide-over or panel; does not replace inspector for depth 3.

```
┌─ EXPLANATION ─────────────────────────────────────┐
│ LARGE BUYING PRESSURE                              │
│ Epistemic: INFERRED                                │
│                                                    │
│ What it means                                      │
│ Aggressive large-trade participation increased     │
│ relative to recent baseline.                       │
│                                                    │
│ Why it matters                                     │
│ Supports bullish flow hypothesis for NVDA.         │
│                                                    │
│ Evidence alignment                                 │
│ Order Flow    ↑ LONG   Strong                      │
│ Options       — AMBIGUOUS                            │
│ Model         ↓ SHORT  Weak  ← conflict            │
│                                                    │
│ Quality: PARTIAL — quote gap 10:31:14–10:31:22     │
│ As of: 10:42:18 ET (LIVE)                          │
│                                                    │
│ [Open in Inspector]  [Show derivation]  [Ask AI]   │
└────────────────────────────────────────────────────┘
```

## Conceptual backend fields (not final schema)

| Field | Purpose |
|---|---|
| `result_id` | Stable reference for UI and API |
| `semantic_type` | Card type, alert type, feature name, etc. |
| `definition` | Human-readable definition |
| `epistemic_class` | OBSERVED, DERIVED, INFERRED, MODEL, STRATEGY, RISK, EXECUTION |
| `as_of_time` | Decision/observation cutoff |
| `source_refs[]` | EvidenceReference list |
| `freshness` | FreshnessSummary |
| `quality` | QualitySummary |
| `derivation_ref` | Method, version, FeatureRunner ID |
| `methodology_version` | Parser, model, strategy version |
| `evidence_refs[]` | Supporting evidence bundle |
| `conflicting_evidence_refs[]` | Opposing evidence |
| `model_ref` | Model identity when applicable |
| `raw_event_refs[]` | Canonical event IDs |
| `attention_reasons[]` | When shown on NOW |
| `state_transition` | Prior → current when applicable |

## ExplanationReference (illustrative)

```json
{
  "result_id": "attn-nvda-flow-20260815-104218",
  "semantic_type": "attention.large_buying_pressure",
  "epistemic_class": "INFERRED",
  "definition": "Large aggressive buy participation vs rolling baseline",
  "as_of": { "time": "2026-08-15T14:42:18.328Z", "mode": "LIVE" },
  "quality": { "state": "PARTIAL", "detail": "quote gap 10:31:14–10:31:22" },
  "derivation": {
    "method": "large_trade_classifier",
    "version": "1.0.0",
    "inputs": ["canonical.trades", "aggressor.v1"]
  },
  "evidence_refs": ["ev-bundle-abc123"],
  "conflicting_evidence_refs": ["ev-model-xyz789"],
  "explain_layers_available": ["summary", "derivation", "provenance", "raw"]
}
```

## Rules

1. **No explanation without resolvable reference** — if backend cannot provide chain, UI shows `EXPLANATION UNAVAILABLE` with reason.
2. **AI explanations must cite ExplanationReference IDs** — or mark uncertainty.
3. **Confidence is not universal** — see [epistemic-states.md](epistemic-states.md).
4. **State transitions include changed/unchanged lists** — see command-center alert pattern.

## Traceability examples

```
CVD card
  → canonical trades
  → aggressor provenance
  → FeatureRunner CVD v1
  → quality state

Squeeze state
  → squeeze engine
  → evidence bundle
  → freshness gates
  → state machine transition
```

Do not design UI implying backend guarantees that do not exist (current: bar OHLCV only for most features).
