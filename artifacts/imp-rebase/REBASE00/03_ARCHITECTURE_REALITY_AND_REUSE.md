# Architecture Reality and Reuse

## Actual system shape

`VERIFIED` The repository contains 44 top-level Python package directories under `src/market_platform_foundation` (cache excluded); `intelligence/` alone contains 499 Python files. Architectural authority is distributed across contracts and engines rather than centered in one application service.

| Boundary | Implemented reality | Reuse judgment |
|---|---|---|
| Contracts/normalization | Versioned events, signals, evidence, hypotheses, snapshots, predictions, runs, provider envelopes | Extend; do not create a second ontology |
| Temporal/provenance | Event/provider/received/available clocks, source revisions, raw hashes/refs, anti-lookahead cutoff | Strong kernel; add universal ingest/revision semantics where domain-relevant |
| Quality/capability | Shared assessment/code model plus domain flags; multidimensional provider capability | Extend shared core and register domain extensions |
| Detection/routing/scheduling | Semantic detectors, route templates, inference scheduler, outcome scheduler | Reuse as subsystem workflow primitives, not yet a universal workflow engine |
| Intelligence | Forecast, hypothesis, council, fusion, evaluation, training, validation, promotion, adaptation | Preserve separated authority boundaries |
| Opportunity/execution | Opportunity economics/policy, risk, paper execution, live safety, authorization, confirmation | Preserve; no inference component may bypass these authorities |
| Persistence | Canonical JSON/JSONL, local SQLite/event state, ledgers, campaign stores, optional provider/runtime stores | Useful primitives, but no global operation/artifact index |
| Operations | Live health, telemetry, incidents, alerts, runbooks, control plane, deployment/release governance | Strong supervised-live slice; generalize only after run taxonomy |
| UI/assistant | Read-only workspace projections, explain/inspect refs, audited research assistant | Preserve read-only boundary; strengthen provenance |
| `platform/` | Security and reconciliation consumed by UI/tools/tests | Classify as execution-risk-and-state infrastructure |

## Executable authority separation

`VERIFIED` BUILD35's authority map and current code distinguish Forecast, Outcome Settlement, Evaluation, Research, Training, Validation, Promotion, Opportunity, Risk, Paper Execution, Runtime Governance, Adaptation, Live Safety Gate, Session Authorization, Order Confirmation, Reconciliation, Operator Control, Deployment, and Release Governance.

`PROPOSED` REBASE-01 should document these authorities as a graph with four relations: `produces`, `may_read`, `may_authorize`, and `must_not_authorize`. It should point to types/functions, not duplicate policy values.

## Safety-critical distinctions

- Execution mode is not execution authority.
- Release approval is not order confirmation.
- Provider availability is not entitlement, dataset admission, or execution capability.
- Observational live data is not qualification evidence until frozen policy admits it.
- A forecast is immutable prediction evidence; an outcome is separate settled evidence.
- A model output, narrative, LLM synthesis, or assistant response has no risk/order authority.
- Provider redundancy does not authorize broker failover or resubmission.

## Temporal and epistemic kernel

`VERIFIED` `EventV1` and provider provenance carry the core clocks and source lineage needed for point-in-time reasoning. The hard law is `available_time_ns <= decision_time_ns`. `PredictionLedgerEntryV1` freezes decision/anchor/target/window/cutoff/policy/source/mode lineage. `OutcomeSettlementService` is idempotent, refuses policy mismatch, and prevents early settlement.

`PARTIAL` There is no universal explicit `ingested_time_ns` and `revision_time_ns` pair across all event contracts. Those concepts occur in provider envelopes, participant records, or metadata. Future macro, filings, TIC, COT, reserves, policy, and auction adapters must declare publication, revision, availability, and calendar rules.

## Provider reality

| Provider/source | Current status | Boundary |
|---|---|---|
| Moomoo/OpenD observation | `IMPLEMENTED` | Read-only callbacks, bounded queue, hot state, probe/entitlement evidence; not admitted execution data |
| IBKR Client Portal observation | `PARTIAL` tooling | Loopback HTTPS, allowlisted read endpoints, pacing/redaction; outside `src`, no streaming/orders/funds |
| Tradier paper | `IMPLEMENTED` | Sandbox-only broker-paper adapter |
| Moomoo paper | `PARTIAL` | Deterministic/injectable transport; real OpenD execution wire absent |
| Tastytrade | `UNSUPPORTED` | Explicitly unavailable |
| Databento | `DESIGN/METADATA` | Lawful bytes unavailable; no admitted runtime |
| Alpaca | `PLANNED/NOT_AUTHORIZED` | Identifier/planning surfaces only |
| SEC, Reg SHO, FRED/ALFRED, CFTC, EIA, CBOE stats, weather | `IMPLEMENTED` bounded sources | Fixture/public-source pipelines; live capture/probe opt-in and admission remains separate |
| Production live broker transport | `ABSENT` | Live canary runners use `MockBrokerTransport` |

## Reuse recommendations

1. Extend `EventV1`, provider envelopes, `ProviderProvenance`, quality assessment, and capability state for every new source.
2. Index immutable `RunManifestV1`, dataset manifests, candidate artifacts, validation records, evidence sessions, and release manifests in a new run/artifact ledger; do not replace them.
3. Reuse semantic detections, route templates, scheduler lifecycle, and outcome scheduling as adapters behind a future workflow contract.
4. Reuse opportunity economics and authority separation for every domain. Do not let cross-asset or agent systems create order authority.
5. Preserve live authorization/confirmation/reconciliation/persistence gates and automatic-failover prohibition.
6. Generate capability tables, authority maps, policy references, model listings, and validation inventories from executable sources.

## Anti-patterns to avoid

- A second event/provenance/quality ontology for macro or cross-asset data.
- A universal score that collapses source quality, uncertainty, direction, and authority.
- Calling all scripts “workflows” without durable lifecycle/idempotency/retry semantics.
- Treating an environment flag, UI projection, fixture adapter, or historical matrix as operational authority.
- Replacing tested Python paths with Rust before measurement identifies a binding bottleneck.
- A `SkillSpecV1` or agent registry without a demonstrated lifecycle beyond existing route/scheduler/run primitives.
