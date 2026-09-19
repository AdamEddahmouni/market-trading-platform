# IMP-INTEGRATE-EXPERIMENT-06 — Lane F fill-price realism v1 (prep + freeze)

**Increment:** `IMP-SIMULATOR-FILL-PRICE-REALISM-V1`  
**Branch:** `research/fill-price-realism-v1`  
**Base:** `origin/main` @ `2306ff4a0db74d6ed35d9c5d1bb82bf8b3dc7c56`  
**Worktree:** `<repo>/.worktrees/lane-f-fill-realism`

## Purpose

Freeze a **new** bounded experiment that reprices v3 fill schedules under predeclared OHLC fill/MTM references. **Does not** execute cost grids (Lane E) or mutate v3 receipts.

Authority: **HISTORICAL_DEVELOPMENT** / **BOUNDED_HISTORICAL_OBSERVATION** only.

## Hypothesis and experiment IDs

| Field | Value |
|---|---|
| `HYPOTHESIS_ID` | `LANE-E-HYP-SIMULATOR-FILL-PRICE-REALISM-V1` |
| `EXPERIMENT_ID` | `imp-integrate-experiment-06-r1-opend-fill-price-realism-v1` |
| Methodology | [FILL_PRICE_REALISM_V1.md](../research/methodology/fill/FILL_PRICE_REALISM_V1.md) |

Registered follow-up from `evidence/historical-research/imp-integrate-experiment-05-lane-e-v3-findings/hypothesis_queue_v1.json` (rank 4).

## v3 immutability

Do not edit or rerun:

- `evidence/historical-research/imp-integrate-experiment-05-r3-opend-fill-economics-v3/`
- `EXPERIMENT_HASH` `81EFC1B1E2650010962F81F5B58B7E614E1AC1C2232E7862890CBB37BF5F3F61`

Fill schedule source (read-only):

- `evidence/historical-research/imp-integrate-experiment-05-r3-opend-fill-economics-v3/baseline_pack_run_manifest.json`

## Dataset pin

Same OpenD AAPL five-session corpus as v3. Normalized fingerprint:

`355FDBB852B94B964B62331839B58C3A336D1B52DB2F17FA05D30BA31389885B`

Corpus pin: reuse v3 `corpus_pin` path declared in frozen definition (no duplicate download).

## Canonical prep artifacts

| Artifact | Path |
|---|---|
| Frozen definition | `evidence/historical-research/imp-integrate-experiment-06-r1-opend-fill-price-realism-v1/frozen_experiment_definition.json` |
| Protocol | `evidence/historical-research/imp-integrate-experiment-06-r1-opend-fill-price-realism-v1/experiment_protocol_v1.json` |
| Independent review | `evidence/historical-research/imp-integrate-experiment-06-r1-opend-fill-price-realism-v1/independent_review_v1.json` |
| Spec freeze receipt | `evidence/historical-research/imp-integrate-experiment-06-r1-opend-fill-price-realism-v1/spec_freeze_receipt.json` |

## Execution gate

Execution authorized only when:

1. `independent_review_v1.json` records `verdict=APPROVE_FOR_FROZEN_EXECUTION`
2. Harness implements counterfactual repricing per frozen `fill_price_realism_arms` (no simulator semantic change)
3. Contamination auditor checklist passes (same class as v3)

Lane F 2026-09-18: spec frozen; harness execution deferred to follow-up commit on this branch.

## Validation (spec freeze)

```powershell
cd <worktree>/projects/integrated-market-platform
python tools/imp.py env
python -c "from pathlib import Path; import json; from market_platform_foundation.intelligence.historical_research_harness.baseline_pack import verify_frozen_experiment_definition; d=json.loads(Path('evidence/historical-research/imp-integrate-experiment-06-r1-opend-fill-price-realism-v1/frozen_experiment_definition.json').read_text()); print(verify_frozen_experiment_definition(d))"
```

Do **not** run historical baseline pack performance from this lane until harness lands.
