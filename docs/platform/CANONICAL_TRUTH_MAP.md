# IMP canonical truth map

| Field | Value |
|---|---|
| Document ID | `IMP-CANONICAL-TRUTH-MAP` |
| Classification | `CANONICAL` |
| Lifecycle Status | `CANONICAL` |
| Truth Class | `CURRENT_CANONICAL_TRUTH` |
| Canonical Subject | Topic-to-authority routing |
| Owner Role | IMP documentation governance owner |
| Version | `1.0.0` |
| Last Verified | 2026-08-27 |
| Establishing Milestone | `IMP-REBASE-01` |
| Supersedes | Ad hoc selection of whole-program authorities |
| Superseded By | None |

Use this map to find the source that controls a subject. Program documents
explain; executable and accepted frozen sources retain authority in their
declared scopes.

> This document is canonical for program-level interpretation and architecture. Where executable behavior is controlled by a designated schema, policy, gate, manifest, registry, or authority implementation, that executable authority controls within its defined scope.

| Topic | Current canonical explanation | Executable or frozen scoped authority |
|---|---|---|
| Program architecture | [Master Architecture](MASTER_ARCHITECTURE.md) | Subsystem code and authorities listed below |
| Program status | [Program Status](PROGRAM_STATUS.md) | Accepted milestone artifacts for their cutoffs |
| Program roadmap | [Master Roadmap](MASTER_ROADMAP.md) | Separately accepted milestone contracts when created |
| Foundation authority | This map and [Master Architecture](MASTER_ARCHITECTURE.md) | [`manifests/phase0/canonical-authority.json`](../../manifests/phase0/canonical-authority.json) enforced by [`authority.py`](../../src/market_platform_foundation/authority.py), Foundation scope only |
| Validation | [Documentation Standard](DOCUMENTATION_STANDARD.md) plus [Validation Architecture](../engineering/VALIDATION_ARCHITECTURE.md) | [`tools/validation_manifest.json`](../../tools/validation_manifest.json), [`tools/validate.py`](../../tools/validate.py), and [CI workflow](../../.github/workflows/imp-validate.yml) |
| Temporal integrity | [System Boundaries](SYSTEM_BOUNDARIES.md) and [Data and Epistemic Model](DATA_AND_EPISTEMIC_MODEL.md) | [`contracts/common.py`](../../src/market_platform_foundation/intelligence/contracts/common.py), normalization/provenance contracts, and [Temporal Integrity V1](../engineering/TEMPORAL_INTEGRITY_V1.md) |
| Quality | [System Boundaries](SYSTEM_BOUNDARIES.md) | [`quality/models.py`](../../src/market_platform_foundation/intelligence/quality/models.py) and domain-specific executable taxonomies |
| Provider capabilities | [System Boundaries](SYSTEM_BOUNDARIES.md) | [`market_data/capabilities.py`](../../src/market_platform_foundation/market_data/capabilities.py), adapter code, verified probes, and scoped [provider references](../providers/) |
| Prediction ledger | [Authority Model](AUTHORITY_MODEL.md) | [`contracts/prediction_ledger.py`](../../src/market_platform_foundation/intelligence/contracts/prediction_ledger.py) and its persistence/serialization consumers |
| Settlement | [Authority Model](AUTHORITY_MODEL.md) | [`outcomes/service.py`](../../src/market_platform_foundation/intelligence/outcomes/service.py) and the frozen settlement policy identity consumed there |
| Forward qualification | [Program Status](PROGRAM_STATUS.md) | Executable [`forward_qualification/`](../../src/market_platform_foundation/intelligence/forward_qualification/) and frozen [`EVIDENCE01_POLICY.json`](../../artifacts/forward-qualification/EVIDENCE01_POLICY.json) |
| Risk and execution authority | [Authority Model](AUTHORITY_MODEL.md) | [`execution/`](../../src/market_platform_foundation/intelligence/execution/), [`live_execution_safety/`](../../src/market_platform_foundation/intelligence/live_execution_safety/), [`live_canary/authorization.py`](../../src/market_platform_foundation/intelligence/live_canary/authorization.py), and [`live_canary/confirmation.py`](../../src/market_platform_foundation/intelligence/live_canary/confirmation.py) |
| Reconciliation | [Authority Model](AUTHORITY_MODEL.md) | [`platform/reconciliation/engine.py`](../../src/market_platform_foundation/platform/reconciliation/engine.py) and live-canary reconciliation authorities |
| Release governance | [Authority Model](AUTHORITY_MODEL.md) | [`live_canary/release_governance/`](../../src/market_platform_foundation/intelligence/live_canary/release_governance/) and BUILD35 policy/evidence only for its historical candidate |
| Documentation lifecycle | [Documentation Standard](DOCUMENTATION_STANDARD.md) | Milestone acceptance artifacts and generated hash manifests for their declared scope |
| Epistemic method | [Data and Epistemic Model](DATA_AND_EPISTEMIC_MODEL.md) | Existing event, evidence, hypothesis, provenance, quality, prediction, and model contracts within their scopes |

## Use rule

Do not promote a historical provider matrix, validation report, test count,
policy value, model version, or release artifact into current global truth.
Reference the current executable source or generate a view from it. When two
same-level authorities conflict, record the conflict as unresolved and obtain
an explicitly authorized reconciliation.
