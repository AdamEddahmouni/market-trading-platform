# IMP glossary

| Field | Value |
|---|---|
| Document ID | `IMP-GLOSSARY` |
| Classification | `CANONICAL` |
| Primary Truth Class | `CURRENT_CANONICAL_TRUTH` |
| Canonical Subject | Controlled program terminology |
| Establishing Milestone | `IMP-REBASE-01` |
| Version | `1.0` |
| Last Verified | `2026-08-27` |
| Supersedes | No single current whole-program controlled vocabulary |
| Superseded By | None |

Use the exact layer or dimension named below. The unqualified term `LIVE` is not
a valid program-status value.

## Market-data and execution layers

| Term | Controlled meaning |
|---|---|
| Observational data | Data received for observation or research; it may be real, replayed, fixture, or synthetic depending on labeled origin |
| Real market data | Observations originating from real market or publisher activity with provenance; not automatically admitted research data or execution input |
| Live provider connectivity | A currently connected provider transport; says nothing by itself about entitlement, quality, admission, qualification, or execution |
| Live execution transport | A transport capable of sending orders to a live brokerage environment |
| Production live execution transport | A live execution transport accepted for production use under the required safety and qualification program; currently absent |
| Operationally accepted live execution | A live execution path whose operational acceptance criteria have passed; distinct from transport existence |
| Authorized live session | A bounded session explicitly authorized by a human under current policy |
| Authorized individual order | One candidate action explicitly confirmed by a human under current policy |
| Broker acceptance/fill | External broker reality acknowledging, rejecting, partially filling, or filling an order |
| Reconciliation | Governed comparison and incorporation of external broker reality into canonical internal state, with mismatches surfaced |
| Replay | Deterministic processing of recorded inputs under a declared cutoff and configuration |
| Simulation | Modeled behavior that does not create broker reality |
| Paper execution | Guarded simulated or broker-sandbox execution with its own ledger semantics; never production live execution |

## Analytical and decision terms

| Term | Controlled meaning |
|---|---|
| Signal | A typed analytical indication; information, not permission |
| Candidate | A proposed action or object eligible for further independent review |
| Opportunity | A candidate enriched with economics, costs, uncertainty, and opportunity-policy treatment |
| Prediction | A decision-time estimate frozen with horizon, cutoff, policy, and source lineage |
| Evidence campaign | A governed process that accumulates and assesses evidence under a named policy |
| Qualification | A policy-bound disposition from accepted evidence; not release, session, or order authorization |
| Provider | An external or fixture-backed source/transport implementation with scoped capabilities and constraints |
| Capability | A typed statement of support or availability within a source, implementation, entitlement, evidence, and environment scope |
| Quality | A multidimensional assessment of fitness or defects under shared and domain-specific contracts |
| Risk authority | An independent authority that may permit or block within risk scope |
| Execution authority | The combined governed authority required to progress an action through the applicable execution path; no single mode flag supplies it |
| Release approval | Approval of a release candidate under release governance; not trading authorization |
| Information | Observations, claims, context, evidence, or outputs that may support a decision but do not authorize it |
| Broker authority | The actual ability of an accepted transport to submit a fully authorized order to a broker; no analytical output grants it |

## Epistemic terms

| Term | Controlled meaning |
|---|---|
| `OBSERVED_FACT` | A direct measurement or event observation within stated provenance and temporal limits |
| `REPORTED_CLAIM` | A source-attributed assertion whose truth may require corroboration |
| `STATED_RATIONALE` | An actor's declared explanation; evidence of what was stated, not proof of actual motive |
| `INFERRED_BEHAVIOR` | Behavior interpreted from observable evidence |
| `INFERRED_MOTIVE` | A structured hypothesis about actor intent |
| `NARRATIVE` | A proposition or story plus its circulation among relevant actors; prevalence is not truth |
| `HYPOTHESIS` | A testable proposition retaining material support, contradictions, alternatives, and falsifiers |
| `MODEL_OUTPUT` | A statistical, ML, or AI result with model/input provenance; neither fact nor authority by origin |

## Documentation and program-state terms

| Term | Controlled meaning |
|---|---|
| Truth class | Whether a claim is `HISTORICAL_TRUTH`, `CURRENT_CANONICAL_TRUTH`, or `APPROVED_FUTURE_DESIGN` |
| Document classification | One of `CANONICAL`, `HISTORICAL`, `ACTIVE_SUPPORTING`, `RUNBOOK`, `REFERENCE`, `GENERATED`, `EXPERIMENTAL`, or `SUPERSEDED` |
| Implementation maturity | Evidence-backed capability state: `PLANNED`, `DESIGNED`, `IMPLEMENTED`, `VALIDATED`, `OPERATIONALLY_ACCEPTED`, `QUALIFIED`, `PRODUCTION_ELIGIBLE`, or `DEPRECATED` |
| Family consolidation | Program-architecture assessment: `ABSENT`, `PARTIAL`, or `CONSOLIDATED` |
| `PARTIAL` | Reusable foundations exist, but the universal program authority or consolidation primitives are incomplete; never a percentage or readiness claim |
| Milestone disposition | State of a named milestone or track: `COMPLETE`, `COMPLETE_WITH_LIMITATIONS`, `IN_PROGRESS`, `BLOCKED`, or `AWAITING_EXTERNAL_EVIDENCE` |
| Canonical | Current explanatory authority for one declared subject; constrained by executable and historical truth |
| Historical | Authoritative evidence about a recorded cutoff, not automatic control of present behavior |
| Future design | Accepted direction that grants no implementation, production, release, or execution authority |

## Fabric and workload terms

| Term | Controlled meaning |
|---|---|
| Operating Fabric | Program-wide operation, run, artifact, workflow, control, and evidence coordination; currently `PARTIAL` |
| Real-Time Opportunity Fabric | Time-sensitive observational state, features, detection, routing, opportunity, and measurement path; currently `PARTIAL` |
| Universal Run Ledger | Future append-only program authority for durable run identity, attribution, artifacts, relationships, attempts, and dispositions; not yet implemented |
| `HOT` | Current time-sensitive bounded workload; no latency guarantee |
| `WARM` | Recent durable/derived workload that tolerates non-immediate processing |
| `COLD` | Historical, immutable, or reproducibility-oriented workload |
