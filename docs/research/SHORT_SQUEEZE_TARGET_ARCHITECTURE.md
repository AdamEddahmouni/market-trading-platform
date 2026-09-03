# Short Squeeze Target Architecture (Deliverable 3)

## Data flow

```text
RAW MARKET DATA
    → provider adapters (Finviz, IBKR, SEC, FINRA flow, whale fixtures)
    → normalized observations (squeeze_core/contracts)
    → quality + provenance gates
    → shared feature metrics (squeeze_core/metrics)
    → domain intelligence
         ├─ causal state machine (squeeze_core/intelligence)  [NEW]
         ├─ Adam comparative methodology (legacy parallel view)
         └─ Phase 3A canonical rules (research)
    → HTTP donor API (+ causal_intelligence field)
    → IMP donor_bridge projections
    → UI progressive disclosure
```

## Feature flow

Features remain in causal groups; velocity/acceleration slots are **capability-gated** (null when unavailable).

## State machine flow

```text
RuleSnapshot + AdamSnapshot + CrossLaneSnapshot + QualitySnapshot
    → evaluate_squeeze_intelligence()
    → SqueezeIntelligenceResult
    → explanation graph
```

## Model flow (future)

```text
Labeled cohort → FeatureView (PIT) → baseline logistic/hazard
    → calibration → horizon probabilities (status=CALIBRATED)
    → magnitude model (separate)
    → EV layer (IMP strategy module)
```

## Cross-lane dependencies

```text
OrderFlowEngine → NormalizedLaneEvidence → SqueezeIntelligence
OptionsEngine   → NormalizedLaneEvidence → SqueezeIntelligence
CatalystEngine  → NormalizedLaneEvidence → SqueezeIntelligence
```

IMP contract: `market_platform_foundation/cross_lane/evidence.py`

## Quality flow

Stale/missing capabilities reduce **data_confidence**; conflicts → UNEVALUABLE state.

## Explainability flow

Every causal result includes `supporting_evidence`, `contradicting_evidence`, `missing_capabilities`, and nested `explanation.graph`.
