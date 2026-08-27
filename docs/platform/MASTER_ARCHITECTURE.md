# IMP master architecture

| Field | Value |
|---|---|
| Document ID | `IMP-MASTER-ARCHITECTURE` |
| Classification | `CANONICAL` |
| Lifecycle Status | `CANONICAL` |
| Truth Class | `CURRENT_CANONICAL_TRUTH` with labeled `APPROVED_FUTURE_DESIGN` sections |
| Canonical Subject | Whole-program architecture and extension boundaries |
| Owner Role | IMP program architecture owner |
| Version | `1.0.0` |
| Last Verified | 2026-08-27 |
| Establishing Milestone | `IMP-REBASE-01` |
| Supersedes | No prior accepted current whole-program architecture |
| Superseded By | None |

This document explains the whole program without replacing subsystem contracts
or frozen milestone evidence.

> This document is canonical for program-level interpretation and architecture. Where executable behavior is controlled by a designated schema, policy, gate, manifest, registry, or authority implementation, that executable authority controls within its defined scope.

## IMPLEMENTED CURRENT FLOW

The implemented architecture is a set of governed, composable subsystem
boundaries rather than one central application service:

```text
EXTERNAL WORLD
  -> sources and providers
  -> provider envelopes / ingestion
  -> normalization + temporal and provenance controls
  -> multidimensional quality assessment
  -> canonical events, snapshots, ledgers, and state
  -> intelligence, detection, routing, modeling, and research
  -> immutable prediction records
  -> evidence collection
  -> outcome settlement
  -> qualification against scoped frozen policy
  -> opportunity and risk authorities
  -> execution-state, live-safety, session, and order-confirmation gates
  -> broker boundary (paper/sandbox today; no production live transport)
  -> reconciliation into canonical state
  -> operations, validation, deployment, and release governance
```

Information can move forward for evaluation, but authority crosses only
explicit gates. Prediction, evidence, and qualification do not become order
authority. Real external observation does not imply execution transport.

Implemented foundations include versioned contracts, point-in-time clocks and
provenance, provider capability types, quality models, prediction and outcome
records, evidence campaigns, opportunity/risk/paper execution, live-safety and
human-control gates, reconciliation, manifest-driven validation, and bounded
operational/release governance. The [Canonical Truth Map](CANONICAL_TRUTH_MAP.md)
routes each subject to its executable source.

## PARTIAL EXISTING FOUNDATIONS

`PARTIAL` means verified reusable pieces exist, but the universal abstraction
named by the family does not. It is not a percentage-complete estimate.

| Program family | Existing reusable foundations | Missing universal program abstraction | Consolidation owner |
|---|---|---|---|
| IMP Operating Fabric — `PARTIAL` | Validation runners; evidence and release manifests; immutable identities and hashes; campaign stores; schedulers, pipelines, orchestrators, runbooks, incidents, and supervised-live telemetry | Append-only program run authority; artifact index; operation lifecycle; workflow, capability, and SOP registries; program logging/metrics/correlation contract | `IMP-REBASE-02`, then `IMP-OF-01` through `IMP-OF-03` |
| Real-Time Opportunity Fabric — `PARTIAL` | Bounded Moomoo callback ingestion, queues, observational hot state, microstructure features, event routing/scheduling, opportunity economics, and UI projections | End-to-end trace and benchmark authority; measured latency budgets; durable multi-speed state and opportunity-transition model; justified incremental-computation plan | `IMP-RT-01`, then measured optimization work |
| Cross-Asset — `PARTIAL` | Temporal/provenance/quality contracts; FRED/ALFRED macro and rates context; CFTC futures positioning; EIA energy; participant, options, market-context, and cross-lane evidence | Canonical cross-asset instrument/release/relationship identity; domain-neutral comparison; admitted sovereign-rates, FX, reserves, and digital-monetary verticals | `IMP-XA-01` and later admitted verticals |
| Narrative/Motive — `PARTIAL` | PIT event clustering, selected sentiment and narrative features, participant actions, hypotheses, evidence, contradictions, and model-version references | Canonical actor/motive/thesis/credibility model; causal evaluation standard; admitted narrative/motive runtime | `IMP-NARRATIVE-01` after identity and attribution foundations |
| AI/Agents — `PARTIAL` | Provider-neutral read-only assistant, bounded evidence packs, abstention, audit records, citations, and versioned fixture-derived labels | Universal AI-run attribution; immutable prompt/evidence/tool lineage; claim-to-source validation; workflow, tool, skill, and approval registries | `IMP-AI-01`, then `IMP-AI-02` after `IMP-OF-03` |

The `src/market_platform_foundation/platform/` package is active
execution-risk-and-state infrastructure: it contains security/readiness and
broker/ledger reconciliation behavior used by current consumers. It is not
generic platform glue and it is not the future IMP Operating Fabric.

## APPROVED FUTURE CONSOLIDATION / EXTENSION

### Two program fabrics

The **Real-Time Opportunity Fabric** targets fast state, incremental features,
signals, opportunity transitions, ranking, routing, and action preparation.

The **IMP Operating Fabric** targets runs, artifacts, workflows, capabilities,
SOPs, data/model/config lineage, incidents, documentation, audit, and automation
governance.

These are program-level consolidation targets with partial foundations, not
fully implemented universal fabrics today. They share run, artifact,
correlation, and authority identities but have different responsibilities and
must not be collapsed into one undifferentiated engine.

### Multi-speed architecture

| Speed class | Intended examples | Architectural rule |
|---|---|---|
| `HOT` | Callback receipt, bounded queueing, current quote/book/trade state, incremental features, immediate opportunity/risk preparation | Minimize blocking work and preserve event, source, and correlation identity. |
| `WARM` | Near-current enrichment, ranking, aggregation, model/signal refresh, UI projection, operational state | Preserve cutoff and freshness semantics while accepting bounded asynchronous work. |
| `COLD` | Replay, settlement, training, evaluation, research, evidence review, audits, release and documentation work | Optimize for reproducibility, complete lineage, and immutable artifacts. |

These are design classes, not latency service levels. Detailed budgets require
measurement under `IMP-RT-01`; no event-bus, persistence, or systems-language
redesign is justified before that evidence exists.

### Cross-asset extension principles

Rates and sovereign bonds, FX, commodities, institutional positioning,
reserves, and digital monetary systems are approved future first-class domains
that must extend the current temporal, provenance, quality, and capability
foundations rather than create parallel ontologies.

Gold will have one future canonical asset identity that can participate in both
commodity intelligence and monetary/reserve intelligence; duplicate gold data
stores are not part of the design.

Future Japan/rates/FX modeling may relate JPY, JGBs, BOJ actions, FX
intervention, reserve mobilization, Treasury holdings, cross-border flows, and
hedging costs. The architecture preserves competing explanations and does not
encode a predetermined causal chain.

## Standards and implementation handoffs

`IMP-REBASE-02` defines, but does not implement as a universal fabric:

- universal run-attribution and artifact-identity standards;
- data, model, configuration, and code provenance;
- retry and attempt preservation;
- structured logging, metrics, trace, and correlation semantics;
- evaluation classes and benchmark reproducibility; and
- documentation validation.

`IMP-OF-01` then implements an append-only run/artifact authority with source,
code, configuration, and data attribution; parent-child relationships; and
immutable outcome/disposition. It must extend existing evidence, validation,
manifest, and artifact patterns first without prematurely freezing class names.

`IMP-RT-01` measures the current path before redesign. Candidate stages include
provider event, receive, normalize, quality, feature, model/signal,
opportunity, UI/action preparation, risk, order-ready, submit, and broker
response. REBASE-01 implements none of that tracing.

`IMP-XA-01` defines canonical cross-asset identity and temporal/provenance
compatibility, then scopes a bounded sovereign-rates vertical by reusing
current provider and data foundations. It does not create schemas or adapters
in REBASE-01.
