# System Acceptance — BUILD 25

BUILD 25 does not add a new intelligence capability. It proves that BUILD 01–24 behave as one deterministic, point-in-time-safe, evidence-preserving, governance-controlled system under both nominal and adversarial conditions.

## Purpose

The intelligent-engine architecture closed at BUILD 24 with controlled adaptation and governed research re-entry. BUILD 25 answers:

- Can the whole system be reproduced from fixtures?
- Can the entire scientific lineage be reconstructed?
- Does the system remain fail-closed when assumptions, data, artifacts, providers, and callers are deliberately wrong?

## Five Planes

### Data Plane

Providers → normalization → temporal integrity → quality → persistence → snapshots → signals

Authority: BUILD 02 (temporal), BUILD 04 (quality)

### Intelligence Plane

Detection → routing → scheduling → specialists → blackboard → hypotheses → fusion → calibrated forecasts

Authority: BUILD 06 (signals), BUILD 14 (forecast/calibration)

### Scientific Learning Plane

Ledger → outcomes → evaluation → research → experiments → training → validation → promotion

Authority: BUILD 15 (settlement), BUILD 16 (evaluation), BUILD 17 (research), BUILD 18 (training), BUILD 19 (validation), BUILD 20 (promotion)

### Decision / Paper Execution Plane

Champion → opportunity → deterministic risk → paper execution

Authority: BUILD 21 (opportunity), BUILD 22 (risk/paper)

### Governance / Adaptation Plane

Activation → monitoring → drift → fail-safe → rollback → controlled research re-entry

Authority: BUILD 23 (runtime governance), BUILD 24 (adaptation)

## Authority Graph

| Domain | Build | Module |
| --- | --- | --- |
| Temporal | 02 | `temporal` |
| Quality | 04 | `quality` |
| Signals | 06 | `signals` |
| Forecast | 14 | `fusion` |
| Settlement | 15 | `outcomes` |
| Evaluation | 16 | `evaluation` |
| Research | 17 | `research_experiments` |
| Training | 18 | `training` |
| Validation | 19 | `validation` |
| Promotion | 20 | `promotion` |
| Opportunity | 21 | `opportunity` |
| Risk/Paper | 22 | `execution` |
| Runtime Governance | 23 | `governance` |
| Adaptation | 24 | `adaptation` |

No build may bypass another build's authority.

## Golden Path

Canonical acceptance fixture (BUILD 15–24):

```text
trained candidate
→ validation report
→ champion bootstrap
→ runtime activation
→ governed forecast
→ opportunity assessment
→ trade proposal
→ risk decision
→ adaptation assessment
→ research trigger
→ BUILD 17 monitoring observation finding
```

Earlier BUILD 01–13 pipeline is covered by existing lifecycle tests (`test_build01_13_lifecycle.py` through `test_build01_24_lifecycle.py`).

## Adversarial Matrix

| Scenario | Injected Failure | Containment | Expected State |
| --- | --- | --- | --- |
| A05 | future event | temporal eligibility | excluded |
| A06 | future training label | dataset cutoff | excluded |
| A07 | holdout peek | ValidationDataAccessGuard | ValidationError |
| A08 | modern LLM at historical time | knowledge firewall | ValidationError |
| A09 | corrupted artifact | ActivationEngine | ActivationError |
| A12 | non-champion forecast | OpportunityEngine | suppressed |
| A13 | expired opportunity | PreTradeRiskEngine | rejected |
| A16 | LIVE execution mode | ExecutionPolicyV1 | ValueError |
| A22 | telemetry storm | AdaptationEngine dedup | bounded triggers |
| A23 | self-trigger | adaptation evidence filter | no loop |
| A85 | monitoring→train | adaptation isolation | zero trainer calls |
| A86 | monitoring→promote | adaptation isolation | zero promotion calls |

## Fail-Closed Philosophy

- unknown ≠ healthy
- missing ≠ zero
- unavailable ≠ inferred
- contaminated ≠ valid
- unvalidated ≠ champion
- opportunity ≠ trade
- paper ≠ live
- drift ≠ retraining

## Determinism

Scientific identities exclude wall-clock and operational backend metadata. Same semantic inputs → same IDs. Acceptance spec/report IDs are SHA-256 over canonical JSON excluding pass/fail outputs from report identity inputs.

## Reproducibility

Run acceptance locally:

```powershell
$env:PYTHONPATH='src'
.venv\Scripts\python.exe -m unittest tests.intelligence.test_system_acceptance -v
.venv\Scripts\python.exe tools/system_acceptance/generate_build25_manifests.py
```

Artifacts:

- `artifacts/system-acceptance/BUILD25_RC_MANIFEST.json`
- `artifacts/system-acceptance/BUILD25_FILE_HASHES.json`
- `artifacts/system-acceptance/BUILD25_KNOWN_LIMITATIONS.md`

## Live Execution

**No real-money trading authority has been enabled.** Paper execution only. LIVE mode policies are rejected at construction.

## Post-BUILD 25 Programs

These are separate campaigns, not unfinished BUILD 25 requirements:

- Real forward shadow campaign
- Provider expansion (Finviz Elite, IBKR runtime)
- Production observability infrastructure
- Operator UI
- Scale/performance optimization
- Live-execution authorization program (only if explicitly requested)

## Implementation

- Package: `src/market_platform_foundation/intelligence/system_acceptance/`
- Tests: `tests/intelligence/test_system_acceptance.py`
- Manifest tool: `tools/system_acceptance/generate_build25_manifests.py`
