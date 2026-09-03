# Intelligence Contracts V1

BUILD 01 establishes the typed, versioned, serializable contract layer for the
Integrated Market Platform intelligent engine. These records are the shared
vocabulary across data, intelligence, decision, learning, and governance planes.

## Contract hierarchy

```text
EventV1
    ↓
SnapshotV1
    ↓
SignalV1
    ↓
EvidenceV1
    ↓
HypothesisV1
    ↓
ForecastV1
    ↓
OpportunityV1
    ↓
OutcomeV1   (adjudicates ForecastV1)

RunManifestV1   (frozen run configuration)
```

## Separation of meaning

These objects are **not** interchangeable:

| Record | Says | Does not say |
|--------|------|----------------|
| `SignalV1` | 5-minute CVD = +71,220 | Buy NVDA |
| `EvidenceV1` | Aggressive order flow is buy-side skewed | Price will rise |
| `HypothesisV1` | Conditions match emerging squeeze mechanics | P(return > 0) = 0.68 |
| `ForecastV1` | P(midpoint return > 0 over 30m) = 0.68 | Execute long |
| `OpportunityV1` | Candidate long after costs/uncertainty | Broker order |
| `OutcomeV1` | Observed 30m midpoint return = +0.42% | Model failed |

Explicit boundaries:

```text
Signal ≠ Evidence
Evidence ≠ Hypothesis
Hypothesis ≠ Forecast
Forecast ≠ Opportunity
Opportunity ≠ Order
```

## Public API

```python
from market_platform_foundation.intelligence.contracts import (
    EventV1,
    SnapshotV1,
    SignalV1,
    EvidenceV1,
    HypothesisV1,
    ForecastV1,
    OpportunityV1,
    OutcomeV1,
    RunManifestV1,
)
```

Module path: `src/market_platform_foundation/intelligence/contracts/`.

## Immutability

All V1 contracts are `frozen` dataclasses. Once emitted, records are historical
facts. Mutations require new records with new IDs.

## Versioning

Every contract carries `schema_version = "1"`. Serialization preserves this field.
Major-version policy follows `ADR-SCH-001` via `contracts/schema_compat.py`.

Unknown top-level fields are **rejected** on deserialization (strict validation).

## Lineage

Upstream records are referenced via typed `ContractReference` objects:

```json
{
  "kind": "signal",
  "id": "sig-cvd-5m",
  "schema_version": "1"
}
```

Avoid embedding full upstream objects; use references to prevent circular graphs.

## Temporal boundary (BUILD 01 vs BUILD 02)

Contracts expose nanosecond timestamps (`event_time_ns`, `decision_time_ns`,
`available_time_ns`, horizons as `TimeHorizonNs.duration_ns`).

BUILD 01 performs **local** timestamp validation (non-negative integers, required
fields). BUILD 02 enforces global temporal integrity via
`market_platform_foundation.intelligence.temporal` — see
`docs/engineering/TEMPORAL_INTEGRITY_V1.md`. BUILD 03 establishes provider
normalization into `EventV1` — see
`docs/engineering/PROVIDER_NORMALIZATION_V1.md`. The canonical anti-lookahead rule is
`available_time_ns <= decision_time_ns`; availability time is authoritative over
event time for eligibility.

## Quality boundary (BUILD 01 vs BUILD 04)

`QualitySummary` provides minimal interoperable semantics:

```json
{
  "state": "GOOD | DEGRADED | INVALID | UNKNOWN",
  "flags": ["PARTIAL_DATA", "STALE_INFERENCE"]
}
```

Detailed provider/capability quality belongs to BUILD 04 — see
`docs/engineering/QUALITY_CAPABILITY_ENGINE_V1.md`. Domain-specific flag
taxonomies (e.g. `contracts/options_quality.py`) remain separate and may be
referenced in `flags`.

## Forecast boundary

`ForecastEstimate` distinguishes `raw_score`, `probability`, and
`calibrated_probability`. Calibration pipelines are a later build; do not treat
raw LLM confidence as calibrated probability.

Returns in outcome records use **decimal fractions** (0.05 = 5%).

## Execution boundary

`OpportunityV1` carries no execution authority. Forbidden metadata keys include
`quantity`, `order_id`, and `execution_authority`. `RunManifestV1` may record
`execution_mode` and `execution_authority` for observability but does not grant
live trading permission.

## Shadow P6 compatibility

Existing shadow records map to canonical contracts without replacing shadow storage:

| Shadow record | Intelligence contract | Adapter |
|---------------|----------------------|---------|
| `ShadowPredictionRecord` | `ForecastV1` | `shadow_prediction_to_forecast_v1` |
| `ShadowOutcomeLabel` | `OutcomeV1` | `shadow_label_to_outcome_v1` |
| `ShadowRunManifest` | `RunManifestV1` | `shadow_manifest_to_run_manifest_v1` |

Provider envelope events (`contracts/envelope.py`) remain the normalization
target for ingestion; `EventV1` is the intelligence-plane event contract.

## Example: coherent NVDA lifecycle

```json
{
  "signal": {
    "signal_id": "sig-cvd-5m",
    "schema_version": "1",
    "signal_type": "CVD_5M",
    "scope": {"instrument_ids": ["NVDA"]},
    "as_of_time_ns": 1700000000000000000,
    "value": 71220.0,
    "unit": "shares",
    "direction": "LONG",
    "quality": {"state": "GOOD", "flags": []}
  },
  "evidence": {
    "evidence_id": "ev-micro-1",
    "schema_version": "1",
    "snapshot_id": "snap-nvda-1",
    "expert_id": "microstructure",
    "scope": {"instrument_ids": ["NVDA"]},
    "applicability": "APPLICABLE",
    "assessment": {"interpretation": "buy_side_pressure"},
    "support_strength": 0.74,
    "quality": {"state": "GOOD", "flags": []}
  },
  "hypothesis": {
    "hypothesis_id": "hyp-squeeze-1",
    "schema_version": "1",
    "hypothesis_type": "SHORT_SQUEEZE_FORMATION",
    "scope": {"instrument_ids": ["NVDA"]},
    "generated_at_ns": 1700000000000000000,
    "snapshot_id": "snap-nvda-1",
    "supporting_evidence_ids": ["ev-micro-1"],
    "support_score": 0.61,
    "quality": {"state": "GOOD", "flags": []}
  },
  "forecast": {
    "forecast_id": "fc-midpoint-1",
    "schema_version": "1",
    "scope": {"instrument_ids": ["NVDA"]},
    "decision_time_ns": 1700000000000000000,
    "snapshot_id": "snap-nvda-1",
    "target": {
      "target_kind": "midpoint_return_threshold",
      "instrument_id": "NVDA",
      "parameters": {"threshold": 0.0, "metric": "midpoint_return"}
    },
    "horizon": {"duration_ns": 1800000000000},
    "estimate": {
      "estimate_kind": "classification_probability",
      "probability": 0.68
    },
    "quality": {"state": "GOOD", "flags": []}
  },
  "outcome": {
    "outcome_id": "out-midpoint-1",
    "schema_version": "1",
    "forecast_id": "fc-midpoint-1",
    "adjudicated_at_ns": 1700001800000000000,
    "resolution_status": "SETTLED",
    "realized_return": 0.0042,
    "realized_direction": "LONG",
    "quality": {"state": "GOOD", "flags": []}
  }
}
```

Synthetic fixture values only — not a trading recommendation.

## Related documents

- [INTELLIGENCE_PERSISTENCE_ARCHITECTURE_V1.md](INTELLIGENCE_PERSISTENCE_ARCHITECTURE_V1.md) — BUILD 04.5 durable storage

## Tests

```powershell
$env:PYTHONPATH='src'
.venv\Scripts\python.exe -m unittest discover -s tests/intelligence -v
```
