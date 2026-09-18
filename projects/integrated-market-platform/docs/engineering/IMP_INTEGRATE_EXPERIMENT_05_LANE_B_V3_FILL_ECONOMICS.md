# IMP-INTEGRATE-AND-EXPERIMENT-05 — Lane B V3 fill economics (prep only)

**Increment:** `IMP-SIMULATOR-FILL-ECONOMICS-V3`  
**Branch:** `research/opend-fill-economics-v3`  
**Base:** `origin/main` @ `6d6b27de0842b02c57df3bd94c239edf7d6b2e5d`  
**Worktree:** `<repo>/.worktrees/opend-fill-economics-v3`

## Purpose

Prepare a **new** frozen experiment definition for bounded OpenD historical baselines when prediction-conditioned fills receive deterministic historical-research P&L and declared costs. This lane **does not** run performance, Smoke10, or contamination execution.

Authority: **HISTORICAL_DEVELOPMENT** / **BOUNDED_HISTORICAL_OBSERVATION** only.

## Hypothesis and experiment IDs

| Field | Value |
|---|---|
| `HYPOTHESIS_ID` | `LANE-H-HYP-SIMULATOR-FILL-ECONOMICS-V3` |
| `EXPERIMENT_ID` | `imp-integrate-experiment-05-r3-opend-fill-economics-v3` |
| `EXPERIMENT_HASH` | `PENDING_LANE_A_REVIEW` (do not hash until Lane A lands accounting versions) |
| `CODE_SHA` / `research_code_sha` | `PENDING_LANE_A` |

Registered in `evidence/historical-research/imp-integrate-experiment-05-lane-h-findings/hypothesis_queue_v1.json` (rank 1).

## V2 immutability

Do not edit or rerun:

- `evidence/historical-research/imp-integrate-experiment-05-r2-opend-baseline-pack-v2/`
- `HYPOTHESIS_ID` `LANE-E-HYP-OPEND-MULTI-SESSION-V2`
- `EXPERIMENT_HASH` `E8C9ADB9E295EBE913C254FCBBBDDC48A794D9FDE79492CB341138855A67C2A4`

V3 reuses **strategy definitions** from v2 without retune.

## Dataset pin

OpenD AAPL five-session 1-minute RTH corpus (**1950** rows). Normalized fingerprint must equal:

`355FDBB852B94B964B62331839B58C3A336D1B52DB2F17FA05D30BA31389885B`

Verification receipt: `evidence/historical-research/imp-integrate-experiment-05-r3-opend-fill-economics-v3/dataset_fingerprint_verification.json`

## Canonical prep artifacts

| Artifact | Path |
|---|---|
| Pre-execution definition | `evidence/historical-research/imp-integrate-experiment-05-r3-opend-fill-economics-v3/pre_execution_frozen_experiment_definition.json` |
| Freeze field template | `evidence/historical-research/imp-integrate-experiment-05-r3-opend-fill-economics-v3/pre_execution_freeze_template.json` |
| Protocol (metrics + contamination checklist) | `evidence/historical-research/imp-integrate-experiment-05-r3-opend-fill-economics-v3/experiment_protocol_v3.json` |
| Prep receipt | `evidence/historical-research/imp-integrate-experiment-05-r3-opend-fill-economics-v3/pre_execution_freeze_receipt.json` |

## Pending Lane A

Before final freeze hash and execution:

- `SIMULATOR_VERSION`, `ACCOUNTING_VERSION`, `COST_MODEL_VERSION`
- `CODE_SHA` on accounting / simulator harness paths Lane A owns
- Final `experiment_definition_hash` recomputation and optional rename to `frozen_experiment_definition.json`
- Performance run + contamination auditor **execution** (checklist only in Lane B)

## Validation (Lane B)

```powershell
cd <worktree>/projects/integrated-market-platform
python tools/imp.py env
python tools/imp.py test focused tests/platform/test_historical_baseline_pack_v3_prep.py
```

Do **not** run historical baseline pack CLI performance or Smoke10 from this lane.
