# IMP-REBASE-00 Executive Truth and Decisions

## Executive conclusion

`VERIFIED` IMP is a mature, safety-oriented research and supervised-execution architecture with strong subsystem contracts. It is not yet governed by a single current program architecture, universal run ledger, global provider registry, durable workflow fabric, end-to-end latency model, or production live broker transport.

`VERIFIED` The Git lineage continues beyond BUILD35 through repository closure, CLEANUP-01, EVIDENCE-01, EVIDENCE-01A, and EVIDENCE-01B. The committed root `README.md` still presents repository closure as next and forward evidence as absent. That is the highest-impact documentation drift.

`VERIFIED` BUILD35 remains immutable historical acceptance: `FULL_SYSTEM_ACCEPTED_WITH_LIMITATIONS`, 29 nonblocking limitations, zero blocking requirements, for its recorded source. It does not prove current production readiness.

`VERIFIED` EVIDENCE-01B is implemented runtime operationalization, not a completed real-provider shakedown or qualification. EVIDENCE-01C remains the next bounded operational-acceptance milestone. None of this grants execution authority.

`INFERRED` The safest re-baseline strategy is to create a small canonical program layer that points to executable authorities and historical evidence, then add missing run/observability foundations before expanding cross-asset or real-time architecture.

## What is canonical now

| Subject | Current authority | Judgment |
|---|---|---|
| Foundation design approval | `manifests/phase0/canonical-authority.json` enforced by `src/market_platform_foundation/authority.py` | `VERIFIED`, Foundation scope only |
| Repository validation | `validation/manifest.json`, `tools/validate.py`, `.github/workflows/imp-validate.yml` | `VERIFIED` executable authority |
| Temporal integrity | `src/market_platform_foundation/intelligence/contracts/common.py`, normalization/provenance contracts, `docs/engineering/TEMPORAL_INTEGRITY_V1.md` | `VERIFIED` executable kernel plus supporting prose |
| Quality | `src/market_platform_foundation/intelligence/quality/models.py` plus domain taxonomies | `VERIFIED`; shared core is extensible, not exhaustive |
| Prediction evidence | `PredictionLedgerEntryV1` and its serialization/persistence consumers | `VERIFIED` |
| Outcome settlement | `OutcomeSettlementService` and frozen settlement policy identity | `VERIFIED` |
| Forward sufficiency | EVIDENCE policy code plus `artifacts/forward-qualification/EVIDENCE01_POLICY.json` | `VERIFIED`; evidence only |
| Execution/risk | Separate risk, proposal, paper execution, live safety, authorization, confirmation, persistence, and reconciliation authorities named by code and BUILD35 authority map | `VERIFIED`; no single environment flag is order authority |
| Release governance | Release-governance code and BUILD35 policy/evidence for its historical candidate | `VERIFIED`, subject-specific |
| Provider capability | `MarketCapability`/`CapabilityState`, adapter code, verified probes, provider-specific docs/evidence | `VERIFIED` but fragmented; no current global registry |
| Whole-program architecture/status | No accepted post-EVIDENCE master source | `UNKNOWN` as one document; recoverable from this audit |

## Historical truth that must remain immutable

- BUILD/Phase acceptance reports, evidence bundles, manifests, file hashes, validation reports, known-limitations registers, and release candidates.
- Post-BUILD35 closure classification and evidence, as statements about their recorded source.
- EVIDENCE-01/01A/01B policies, campaign records, frozen configuration identities, observation/session/checkpoint artifacts, and exclusion rules.
- Earlier provider capability matrices at their own cutoffs. They must not be promoted into current global truth.

## Material conflicts

1. `VERIFIED` Root program status stops before closure/EVIDENCE while Git is through EVIDENCE-01B.
2. `VERIFIED` `resolve_execution_authority(requested_mode="LIVE")` may return `AUTHORIZED` from `IMP_LIVE_EXECUTION=1`, but actual order authority still requires independent provider, risk, session, confirmation, persistence, and reconciliation gates. The term is a readiness projection and can be misread.
3. `VERIFIED` BUILD26 and BUILD33 provider matrices are valid historical/scenario evidence but conflict if treated as current global provider authority.
4. `VERIFIED` Several design documents use future-sounding names for architecture that is only partially implemented or fixture-first. Status must travel with every reference.

## Major underdocumented implementation

- The breadth and separation of executable authorities under `intelligence/`.
- `platform/` as security/reconciliation and execution-risk-state infrastructure, not an empty shell.
- Provider-neutral observational hot state, bounded callback ingestion, and real Moomoo read-only runtime boundaries.
- Strong model/dataset/validation lineage within BUILD18/19.
- Participant, macro, energy, futures, options, and market-context foundations already reusable for cross-asset work.

## Decisions

- `PROPOSED` IMP-REBASE-01 creates canonical documentation and precedence only; it does not refactor runtime code.
- `PROPOSED` Preserve subsystem authorities and generate reference views from them. Do not copy thresholds, policy IDs, capability states, model versions, or test counts into competing prose.
- `PROPOSED` Establish an append-only Universal Run Ledger and operation taxonomy before building a universal Workflow Engine.
- `PROPOSED` Instrument end-to-end latency before redesigning the event bus or selecting a systems-language hot path.
- `PROPOSED` Build cross-asset work by extending temporal/provenance/quality/capability contracts and domain adapters, not by creating a parallel data architecture.
- `PROPOSED` Keep EVIDENCE changes isolated until EVIDENCE-01C disposition is recorded.
