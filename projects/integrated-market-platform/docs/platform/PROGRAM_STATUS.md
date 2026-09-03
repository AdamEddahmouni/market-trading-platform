# IMP program status

| Field | Value |
|---|---|
| Document ID | `IMP-PROGRAM-STATUS` |
| Classification | `CANONICAL` |
| Primary Truth Class | `CURRENT_CANONICAL_TRUTH` |
| Canonical Subject | Mutable current program state and material limitations |
| Establishing Milestone | `IMP-REBASE-01` |
| Version | `1.3` |
| Last Verified | `2026-08-29` |
| Supersedes | Root README as whole-program status authority |
| Superseded By | None |

This is the current program-state authority. It summarizes accepted state and
links to evidence; it does not redefine architecture or executable behavior.

## Current accepted state

| Subject | Current state | Truth class | Controlling evidence |
|---|---|---|---|
| BUILD01-35 core campaign | Historical disposition `FULL_SYSTEM_ACCEPTED_WITH_LIMITATIONS` for the recorded BUILD35 candidate | `HISTORICAL_TRUTH` | [BUILD35 acceptance report](../../artifacts/full-system-acceptance/BUILD35_FULL_ACCEPTANCE_REPORT.json) and [known limitations](../../artifacts/full-system-acceptance/BUILD35_KNOWN_LIMITATIONS.md) |
| Repository closure | `COMPLETE` for its recorded source; the audit passed with no classification-time changes | `HISTORICAL_TRUTH` | [Closure audit](../engineering/POST_BUILD35_REPOSITORY_CLOSURE_AUDIT.md) and [classification](../../artifacts/repository-closure/POST_BUILD35_SUBSYSTEM_CLASSIFICATION.json) |
| EVIDENCE-01 | `COMPLETE` policy and assessment machinery; evidence sufficiency only | `HISTORICAL_TRUTH` / `CURRENT_CANONICAL_TRUTH` | [EVIDENCE-01](../engineering/EVIDENCE_01_LONGER_FORWARD_QUALIFICATION.md) |
| EVIDENCE-01A | `COMPLETE` campaign framework and real-forward origin controls | `HISTORICAL_TRUTH` / `CURRENT_CANONICAL_TRUTH` | [EVIDENCE-01A](../engineering/EVIDENCE_01A_REAL_FORWARD_OBSERVATION_CAMPAIGN.md) |
| EVIDENCE-01B | `IMPLEMENTED` runtime operationalization; not operationally accepted and not qualification closure | `CURRENT_CANONICAL_TRUTH` | [EVIDENCE-01B](../engineering/EVIDENCE_01B_REAL_PROVIDER_RUNTIME_OPERATIONALIZATION.md) |
| EVIDENCE-01C | `IN_PROGRESS` as the next bounded real-provider shakedown and operational-acceptance record; no accepted outcome exists | `APPROVED_FUTURE_DESIGN` | [REBASE-00 limitation 6](../../artifacts/imp-rebase/REBASE00/07_KNOWN_LIMITATIONS.md) and [Master Roadmap](MASTER_ROADMAP.md) |
| IMP-REBASE-01 | `COMPLETE` documentation-only canonicalization | `CURRENT_CANONICAL_TRUTH` | [REBASE-01 acceptance report](../../artifacts/imp-rebase/REBASE01/REBASE01_ACCEPTANCE_REPORT.md) |
| IMP-REBASE-02 | `COMPLETE` reproducibility, observability, and evaluation standards | `CURRENT_CANONICAL_TRUTH` | [REBASE-02 acceptance report](../../artifacts/imp-rebase/REBASE02/REBASE02_ACCEPTANCE_REPORT.md) |
| IMP-OF-01 | `IMP_OF_01_COMPLETE_WITH_LIMITATIONS` — append-only run/artifact ledger runtime | `CURRENT_CANONICAL_TRUTH` | [OF-01 acceptance](../../artifacts/imp-rebase/OF01/README.md) |
| IMP-OF-02 | `IMP_OF_02_COMPLETE_WITH_LIMITATIONS` — existing-system attribution adapters | `CURRENT_CANONICAL_TRUTH` | [OF-02 acceptance](../../artifacts/imp-rebase/OF02/README.md) |
| IMP-OF-03 | `IMP_OF_03_COMPLETE_WITH_LIMITATIONS` — governed capability/SOP/workflow registry | `CURRENT_CANONICAL_TRUTH` | [OF-03 acceptance](../../artifacts/imp-rebase/OF03/README.md) |
| IMP-RT-01 | `IMP_RT_01_COMPLETE_WITH_LIMITATIONS` — causal trace and latency baseline for executable ingest paths | `CURRENT_CANONICAL_TRUTH` | [RT-01 acceptance](../../artifacts/imp-rebase/RT01/RT01_ACCEPTANCE_REPORT.json) |
| IMP-XA-01 | `IMP_XA_01_COMPLETE_WITH_LIMITATIONS` — cross-asset canonical identity and analytical-domain participation kernel | `CURRENT_CANONICAL_TRUTH` | [XA-01 acceptance](../../artifacts/imp-rebase/XA01/XA01_ACCEPTANCE_REPORT.json) |
| IMP-XA-02 | `IMP_XA_02_COMPLETE_WITH_LIMITATIONS` — first admitted FRED rates reference vertical with PIT provenance and typed cross-asset reference relationships | `CURRENT_CANONICAL_TRUTH` | [XA-02 acceptance](../../artifacts/imp-rebase/XA02/XA02_ACCEPTANCE_REPORT.json) |
| IMP-XA-03 | `IMP_XA_03_COMPLETE_WITH_LIMITATIONS` — second admitted CFTC positioning vertical with source-neutral admission envelope and typed market-report-to-XA reference relationships | `CURRENT_CANONICAL_TRUTH` | [XA-03 acceptance](../../artifacts/imp-rebase/XA03/XA03_ACCEPTANCE_REPORT.json) |
| Autonomous live execution | `DISABLED`; no analytical or automation output can grant order authority | `CURRENT_CANONICAL_TRUTH` | [Authority Model](AUTHORITY_MODEL.md) and current live-safety/authorization implementations |
| Accepted production live broker transport | `ABSENT`; mock, paper, broker abstractions, live gates, and reconciliation foundations do exist | `CURRENT_CANONICAL_TRUTH` | [Live-canary runner](../../src/market_platform_foundation/intelligence/live_canary/runner.py), [mock transport](../../src/market_platform_foundation/intelligence/live_canary/submission.py), and [broker inventory](../../src/market_platform_foundation/intelligence/live_execution_safety/broker_inventory.py) |

BUILD35 acceptance does not prove current production readiness or autonomous
trading approval. EVIDENCE status does not grant risk, session, order, broker,
or release authority.

## Program-family consolidation

`PARTIAL` is a consolidation assessment, never a percentage or readiness claim.

| Family | Assessment | Existing reusable foundations | Missing universal or consolidated capability | Next owning milestone |
|---|---|---|---|---|
| Operating Fabric | `PARTIAL` | OF-01 ledger runtime, OF-02 attribution adapters, OF-03 capability/SOP/workflow registry, IMP-RT-01 trace/latency baseline for executable ingest paths, plus existing run manifests, schedulers, pipelines, operations, and runbooks | Remaining OF-01 operator wiring; unified opportunity-risk live chain tracing | `IMP-RT-01` follow-on |
| Real-Time Opportunity Fabric | `PARTIAL` | Callback ingestion, bounded queues, observational state, RT-01 spans on ingest path, features, routing, opportunity economics, and local metrics | Measured integration on unified order pipeline; real-provider observational campaign | `IMP-RT-01` follow-on |
| Cross-Asset | `PARTIAL` | XA-01 canonical identity kernel, XA-02 first admitted FRED rates reference vertical, XA-03 second admitted CFTC positioning vertical with source-neutral admission envelope, temporal/provenance/quality contracts, and bounded macro, futures, energy, options, and participant foundations | Cross-asset analytics, relationship intelligence engines, durable admitted-source persistence, and additional admitted reference verticals | `IMP-XA-04` |
| Narrative/Motive | `PARTIAL` | Event, participant, hypothesis, contradiction, market-context, and bounded narrative features | Canonical uncertain motive/thesis method, source-treatment standard, and admitted runtime | `IMP-NARRATIVE-01` |
| AI/Agents | `PARTIAL` | Read-only assistant, bounded evidence packs, citation references, and versioned fixture outputs | Universal run attribution, prompt/tool provenance, evaluation, workflow and approval lifecycle | `IMP-AI-01` |

Production live broker transport is `ABSENT`, not `PARTIAL`. Its future work is
a separate safety and qualification program; no REBASE milestone authorizes it.

## Live-readiness state

The current program preserves this non-equivalence:

```text
real observational market data
!= live provider connectivity
!= production live execution transport
!= operationally accepted live execution
!= authorized live session
!= authorized individual order
!= broker acceptance or fill
```

Broker fill then requires reconciliation before canonical state changes.
Human live-session authorization and per-order human confirmation remain
mandatory. Automatic broker failover remains disabled.

## Material current limitations

- OF-01 remains accepted with limitations (declared operator stubs, draft ops pack).
  OF-02 native attribution remains default-disabled. OF-03 registers capabilities,
  SOPs, and workflows but is not an execution engine and does not grant authority.
- IMP-RT-01 provides accepted ingest-path tracing and fixture baseline measurements
  with limitations: no unified opportunity→risk→order_ready chain, no broker or
  reconciliation tracing, queue and signal profiles defined but not acceptance-measured,
  and no real-provider observational trace campaign.
- End-to-end provider-to-user-or-broker trace remains incomplete beyond the RT-01
  ingest-path baseline.
- Cross-asset, Narrative/Motive, Real-Time Opportunity, Operating Fabric, and
  AI/Agent capabilities are not consolidated.
- EVIDENCE-01C has no accepted operational outcome.
- Accepted production live broker transport and operationally accepted live
  execution are absent.

These are program limitations, not defects in REBASE-01 acceptance.

## Update rule

Update this document only for a material accepted state change: milestone
acceptance or invalidation, family-consolidation or implementation-maturity
change, material authority creation/removal/transfer, a major limitation opening
or closing, or a qualification/production-eligibility change. Routine commits,
refactors, wording fixes, and ordinary test-count changes do not require an
update.
