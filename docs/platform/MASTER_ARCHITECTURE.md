# IMP master architecture

| Field | Value |
|---|---|
| Document ID | `IMP-ARCHITECTURE` |
| Classification | `CANONICAL` |
| Primary Truth Class | `CURRENT_CANONICAL_TRUTH` |
| Canonical Subject | Whole-program composition and architectural relationships |
| Establishing Milestone | `IMP-REBASE-01` |
| Version | `1.1` |
| Last Verified | `2026-08-27` |
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

## Two different fabrics

The **Real-Time Opportunity Fabric** is the data-to-decision-support path. It
owns bounded callback ingestion, observational state, feature calculation,
detection, routing, opportunity economics, and the future end-to-end timing
model. It is `PARTIAL` because no accepted trace and benchmark spans provider,
platform, feature, model, risk, UI, human, and broker stages. Its next owner is
`IMP-RT-01` after common standards and durable run identity.

The **Operating Fabric** is the operation-to-evidence control plane. OF-01
provides the append-only run/artifact ledger, OF-02 attributes existing
subsystems onto that ledger, and OF-03 indexes governed capabilities, SOPs, and
workflows. Existing run manifests, schedulers, pipelines, health controls,
runbooks, and release operations remain reusable. The family is still `PARTIAL`
because program-wide end-to-end trace/latency is not accepted. Its next owner
is `IMP-RT-01`. OF-03 does not execute workflows or grant domain authority.

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

No latency target is implied. `IMP-RT-01` must measure end-to-end behavior
before `IMP-RT-02` may optimize it or `IMP-RT-03` may consider an event bus or
native hot path.

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
| Observability | [Observability Standard](OBSERVABILITY_STANDARD.md) defines logs, metrics, traces, and correlation semantics; end-to-end propagation remains future work under `IMP-RT-01` |
| Test and evaluation | [Test and Evaluation Standard](TEST_AND_EVALUATION_STANDARD.md) defines validation, benchmark, backtest, replay, and evaluation semantics; executable validation remains under `tools/validate.py` |

## Family attachment points

- **Cross-Asset — `PARTIAL`.** Existing temporal, provenance, quality, macro,
  energy, futures, options, and participant foundations are reusable. The
  missing shared identity/relationship/source-extension contract belongs to
  `IMP-XA-01`.
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
