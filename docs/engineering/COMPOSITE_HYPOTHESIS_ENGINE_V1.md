# Composite Hypothesis Engine V1 (BUILD 13)

> BUILD 13 converts immutable, source-traceable specialist evidence from a sealed BUILD 12 blackboard into falsifiable composite mechanism hypotheses. It does not produce probabilities, forecasts, opportunities, or trades.

## Hypothesis vs forecast

| Concept | Meaning |
|---------|---------|
| **Hypothesis** | The observed mechanism prerequisites are present. |
| **Forecast** | The probability of a future target outcome is X. |

BUILD 13 only does the first.

## Canonical flow

```
BlackboardSnapshot (sealed, blind-pass default)
        │
        ▼
EvidenceRelationReport (BUILD 12 provenance + relations)
        │
        ▼
HypothesisEvidenceAdapterRegistry
        │
        ▼
FactorEvaluator (mechanism prerequisites)
        │
        ▼
ShortSqueezeHypothesisEngine
        │
        ▼
HypothesisV1 | structured non-emission diagnostics
```

## Why short squeeze is composite

A short-squeeze setup requires multiple mechanism parts:

1. **Short positioning / borrow pressure** (`SHORT_PRESSURE`)
2. **Activation / buying pressure** (`POSITIVE_DEMAND_ACTIVATION`)
3. Optional amplifiers: liquidity constraint, derivatives acceleration, regime support

Positive order flow alone is insufficient. Wide spread alone is insufficient. Three correlated microstructure records from one terminal source are not three independent confirmations.

## Current production limitation

The current production specialist inventory contains only **MICROSTRUCTURE**. Therefore the production Short Squeeze engine correctly abstains/fails closed because no production positioning/borrow specialist yet supplies the required `SHORT_PRESSURE` factor.

This is expected behavior, not a defect.

## Required factors (v1)

| Factor | Required? | Purpose |
|--------|-----------|---------|
| `SHORT_PRESSURE` | Yes | Establishes squeeze fuel / constrained short positioning |
| `POSITIVE_DEMAND_ACTIVATION` | Yes | Establishes active demand/covering pressure |
| `LIQUIDITY_CONSTRAINT` | No | Potential move amplifier |
| `DERIVATIVES_ACCELERATION` | No | Potential convexity/gamma amplifier |
| `REGIME_SUPPORT` | No | Contextual support |

## Opposing / invalidation factors

| Factor | Semantics |
|--------|-----------|
| `SHORT_PRESSURE_EASING` | Short pressure normalizing |
| `NEGATIVE_DEMAND_PRESSURE` | Bearish demand / covering absent |
| `LIQUIDITY_ABUNDANT` | Liquidity no longer constraining |
| `DERIVATIVES_OPPOSITION` | Derivatives positioning opposes squeeze amplification |

Opposition is factor-specific. Optional amplifier opposition is preserved but does not automatically invalidate core mechanism unless a required factor is opposed.

## Factor state semantics

| State | Meaning |
|-------|---------|
| `MISSING` | No usable support for a required factor |
| `SUPPORTED` | Required factor satisfied |
| `CONTESTED` | Both support and opposition present |
| `OPPOSED` | Opposition without support for a required factor |

## Domain and independence requirements

- **Minimum distinct expert domains:** 2
- **Minimum independent provenance groups:** 2 (from BUILD 12 `ProvenanceGroup`)
- Each required factor must be supported by at least one domain
- Same terminal source across domains does **not** count as independent

### False consensus protection

Three evidence records sharing one underlying terminal source = one provenance group, not three confirmations.

## Production evidence adapters

| Expert domain | Adapter | Factors produced |
|---------------|---------|------------------|
| MICROSTRUCTURE | `MicrostructureShortSqueezeEvidenceAdapter` | `POSITIVE_DEMAND_ACTIVATION`, `NEGATIVE_DEMAND_PRESSURE`, `LIQUIDITY_CONSTRAINT` (context) |

Synthetic test adapters under `tests/intelligence/hypothesis_fixtures.py` are **not** production adapters.

### Microstructure mapping (BUILD 11)

| Evidence kind | Mapping |
|---------------|---------|
| `ORDER_FLOW_TRANSITION` + `NEGATIVE_TO_POSITIVE` | supports `POSITIVE_DEMAND_ACTIVATION` |
| `ORDER_FLOW_TRANSITION` + `POSITIVE_TO_NEGATIVE` | opposes activation / `NEGATIVE_DEMAND_PRESSURE` |
| `LIQUIDITY_STRESS` | context `LIQUIDITY_CONSTRAINT` (not directional demand) |

## Blackboard phase policy

Default: `BLIND_ONLY` — deliberation-pass evidence is not automatically admissible.

## Hypothesis identity

- Version: `composite-hypothesis-sha256-v1`
- Inputs: hypothesis type, blackboard ID, snapshot ID, engine ID/version, policy identity, scope
- Outputs (support/opposition lists, claim text) are **excluded** from identity
- Same identity + different durable content → `RepositoryConflictError`

## Falsification criteria

Machine-readable criteria are persisted on emitted `HypothesisV1.invalidation_conditions`:

- `SHORT_PRESSURE_NORMALIZES`
- `POSITIVE_DEMAND_ACTIVATION_REVERSES`
- `REQUIRED_FACTOR_DISAPPEARS`
- `MECHANISM_OPPOSITION_DOMINATES`

BUILD 13 defines criteria; BUILD 15 may settle them against future observations.

## BUILD 12 boundary

| BUILD 12 owns | BUILD 13 owns |
|---------------|---------------|
| Blackboard publication | Mechanism composition |
| Provenance groups | Factor prerequisite checks |
| Agreement/conflict relations | Hypothesis emission / abstention |

## BUILD 14 handoff

BUILD 14 may consume immutable `HypothesisV1`, supporting/opposing `EvidenceV1`, BUILD 12 provenance groups, and BUILD 08 baseline forecasts to perform probabilistic fusion and calibration **without** altering BUILD 13 hypothesis semantics.

## Related documents

- [INTELLIGENCE_CONTRACTS_V1.md](./INTELLIGENCE_CONTRACTS_V1.md)
- [EXPERT_BLACKBOARD_BLIND_COUNCIL_V1.md](./EXPERT_BLACKBOARD_BLIND_COUNCIL_V1.md)
- [MICROSTRUCTURE_SPECIALIST_V1.md](./MICROSTRUCTURE_SPECIALIST_V1.md)
- [INFERENCE_SCHEDULER_V1.md](./INFERENCE_SCHEDULER_V1.md)
