# IMP master architecture

| Field | Value |
|---|---|
| Document ID | `IMP-ARCHITECTURE` |
| Classification | `CANONICAL` |
| Primary Truth Class | `CURRENT_CANONICAL_TRUTH` |
| Canonical Subject | Whole-program composition and architectural relationships |
| Establishing Milestone | `IMP-REBASE-01` |
| Version | `1.3` |
| Last Verified | `2026-09-03` |
| Supersedes | No accepted post-EVIDENCE whole-program architecture |
| Superseded By | None |

This document explains how IMP fits together. It does not define policy values
or grant runtime authority. Executable authorities listed in the
[Canonical Truth Map](CANONICAL_TRUTH_MAP.md) control their own behavior.

## State labels

- `IMPLEMENTED`: code or an executable contract exists. The label does not by
  itself imply validation, qualification, or production eligibility.
- `PARTIAL`: reusable foundations exist, but the program family lacks a
  universal consolidated authority or system.
- `ABSENT`: the named program capability is not present.
- `APPROVED_FUTURE_DESIGN`: an accepted direction that is not implemented by
  this document.

## End-to-end shape

```text
[IMPLEMENTED] sources and provider boundaries
       |
       v
[IMPLEMENTED] ingestion, envelopes, clocks, admission and normalization
       |
       v
[IMPLEMENTED] temporal/provenance/quality contracts and canonical state
       |
       +--------------------------+
       |                          |
       v                          v
[IMPLEMENTED] intelligence,   [IMPLEMENTED] prediction ledger
hypotheses and models              |
       |                          v
       |                    [IMPLEMENTED] evidence campaigns
       |                          |
       |                          v
       |                    [IMPLEMENTED] outcome settlement
       +-------------+------------+
                     |
                     v
       [IMPLEMENTED foundations / PARTIAL family]
       opportunity detection and Real-Time Opportunity Fabric
                     |
                     v
       [IMPLEMENTED] risk and execution-state authorities
                     |
                     v
       [IMPLEMENTED guarded paper/mock paths]
       [ABSENT production live broker transport]
                     |
                     v
       [IMPLEMENTED] reconciliation foundations
                     |
                     v
       [IMPLEMENTED standards / PARTIAL family]
       operations, runbooks and Operating Fabric
                     |
                     v
       [IMPLEMENTED] read-only UI and assistant surfaces
```

Broker acceptance, rejection, or fill is external reality. When a broker path is
used, that reality must flow through reconciliation before it becomes canonical
state. A provider connection, signal, forecast, release approval, or UI mode is
never a substitute for that flow.

The P6 Shadow Run 1 forward-observation campaign is deferred, not active.
Its protocol and historical records remain preserved as evidence artifacts and
do not change the current runtime architecture or grant execution authority.

## Two different fabrics

The **Real-Time Opportunity Fabric** is the data-to-decision-support path. It
owns bounded callback ingestion, observational state, feature calculation,
detection, routing, opportunity economics, and the ingest-path timing baseline.
It is `PARTIAL` because accepted tracing covers executable ingest paths only;
no accepted trace spans the unified opportunity→risk→order_ready chain or
broker/reconciliation stages. Follow-on work extends RT-01 rather than replacing
its ingest-path baseline.

The **Operating Fabric** is the operation-to-evidence control plane. OF-01
provides the append-only run/artifact ledger, OF-02 attributes existing
subsystems onto that ledger, and OF-03 indexes governed capabilities, SOPs, and
workflows. RT-01 adds causal trace and latency instrumentation for executable
ingest paths. Existing run manifests, schedulers, pipelines, health controls,
runbooks, and release operations remain reusable. The family is still `PARTIAL`
because unified opportunity-risk-order_ready tracing is not accepted. OF-03 does
not execute workflows or grant domain authority.

Neither fabric grants order authority. Their detailed responsibility boundaries
are in [System Boundaries](SYSTEM_BOUNDARIES.md).

## Workload classes

`HOT`, `WARM`, and `COLD` describe architectural workloads, not performance
guarantees:

- `HOT`: bounded state and processing needed for current observations and
  time-sensitive projections.
- `WARM`: recent durable state, derived features, evaluation, and operator
  context that can tolerate non-immediate processing.
- `COLD`: immutable evidence, historical datasets, manifests, reports, and
  reproducibility records.

No latency target is implied. `IMP-RT-01` accepted fixture baseline measurements
for executable ingest paths; `IMP-RT-02` may optimize only after measured need
and `IMP-RT-03` may consider an event bus or native hot path only if measured
need remains.

## Required reuse

New program families must extend rather than fork these foundations:

| Concern | Reusable authority or foundation |
|---|---|
| Event and temporal semantics | [`EventV1`](../../src/market_platform_foundation/intelligence/contracts/event.py), temporal contracts, and point-in-time validation |
| Provenance and normalization | [`ProviderProvenance`](../../src/market_platform_foundation/intelligence/normalization/models.py) and provider envelopes |
| Quality and capability | Shared quality models plus domain extensions and provider capability contracts |
| Prediction | [`PredictionLedgerEntryV1`](../../src/market_platform_foundation/intelligence/contracts/prediction_ledger.py) |
| Settlement | [`OutcomeSettlementService`](../../src/market_platform_foundation/intelligence/outcomes/service.py) |
| Risk and execution state | Risk, execution, live-safety, authorization, and confirmation implementations indexed by the truth map |
| External-state closure | Reconciliation authorities under `portfolio/`, `platform/reconciliation/`, and live-canary reconciliation |
| Reproducibility | [Reproducibility and Run Standard](REPRODUCIBILITY_AND_RUN_STANDARD.md) defines run, attempt, outcome, disposition, artifact, and reproducibility semantics; existing run manifests, frozen policies, hashes, validation reports, and campaign records remain authoritative within their scope; future ledger work indexes them rather than replacing them |
| Observability | [Observability Standard](OBSERVABILITY_STANDARD.md) defines logs, metrics, traces, and correlation semantics; RT-01 provides accepted ingest-path causal tracing and latency profiles; platform-wide propagation beyond ingest remains follow-on work |
| Test and evaluation | [Test and Evaluation Standard](TEST_AND_EVALUATION_STANDARD.md) defines validation, benchmark, backtest, replay, and evaluation semantics; executable validation remains under `tools/validate.py` |

## Family attachment points

- **Cross-Asset — `PARTIAL`.** IMP-XA-01 implemented the cross-asset canonical
  identity and analytical-domain participation kernel
  (`src/market_platform_foundation/xa01`). IMP-XA-02 admitted the first bounded
  FRED rates reference vertical with point-in-time observation provenance and
  typed indicator-to-XA reference relationships (`src/market_platform_foundation/xa02`).
  IMP-XA-03 admitted the second bounded CFTC positioning vertical with
  source-neutral admission and typed market-report-to-XA relationships.
  IMP-XA-04 made the admitted-source and identity catalog durable with
  documented local-integration limitations. IMP-XA-05 added ephemeral,
  reconstructable strategic state and regime inspection. Cross-asset analytics,
  relationship intelligence engines, and additional admitted reference
  verticals remain future work.
- **Narrative/Motive — `PARTIAL`.** Existing events, participants, hypotheses,
  bounded narrative features, and contradiction flags are reusable. The
  uncertain motive/thesis method and admitted runtime remain future work under
  `IMP-NARRATIVE-01`.
- **AI/Agents — `PARTIAL`.** A read-only assistant and versioned fixture outputs
  exist. Universal run attribution, prompt/tool provenance, evaluation, and
  approval lifecycle are missing; `IMP-AI-01` is read-only first.

A canonical instrument identity may participate in multiple analytical domains
without being duplicated into disconnected identities. Gold, for example, may
participate in commodity analysis and monetary/reserve analysis. `IMP-XA-01`
defines extension requirements; REBASE-01 does not implement an identity schema
or universal ontology.

Future Japan/rates/FX work may relate JPY, JGBs, BOJ actions, intervention,
reserve activity, Treasury holdings, cross-border flows, and hedging costs. The
architecture must preserve competing causal hypotheses rather than encode a
predetermined causal chain.

## Time-scoped authority

The current architecture cannot rewrite what BUILD35 historically accepted.
BUILD35's immutable acceptance cannot override current architecture merely
because it is historical. Current behavior, current explanation, historical
evidence, and future design each control only their subject and time scope.
