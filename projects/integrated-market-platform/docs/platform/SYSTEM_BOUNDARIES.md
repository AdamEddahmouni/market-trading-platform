# IMP system boundaries

| Field | Value |
|---|---|
| Document ID | `IMP-SYSTEM-BOUNDARIES` |
| Classification | `CANONICAL` |
| Primary Truth Class | `CURRENT_CANONICAL_TRUTH` |
| Canonical Subject | Subsystem responsibilities, dependency direction, and authority stops |
| Establishing Milestone | `IMP-REBASE-01` |
| Version | `1.0` |
| Last Verified | `2026-08-27` |
| Supersedes | No single current whole-program boundary map |
| Superseded By | None |

This document allocates responsibilities. It does not reproduce the system
composition in [Master Architecture](MASTER_ARCHITECTURE.md) or the decision
rights in [Authority Model](AUTHORITY_MODEL.md).

## Responsibility map

| Boundary | Owns | May consume or emit | Authority stops at |
|---|---|---|---|
| Providers and source adapters | Source-specific transport, rights, pacing, capability, entitlement, and raw/source identity | External observations in; provider envelopes or source records out | Availability is not dataset admission, quality, prediction, risk, or execution authority |
| Ingestion | Bounded receipt, queueing, raw identity, receipt clocks, and fail-closed handoff | Provider output in; normalized candidates out | Cannot improve source quality by assertion or authorize downstream use |
| Normalization | Canonical field mapping, units, source lineage, and versioned event construction | Source records in; versioned events/provenance out | Cannot erase raw lineage, revisions, or temporal uncertainty |
| Temporal and provenance | Event/publication/receipt/availability/decision clocks, revisions, source references, and point-in-time constraints | Normalized records and cutoff context | Cannot decide investment merit or order permission |
| Quality | Multidimensional assessment under shared and domain-specific contracts | Provenance, timing, completeness, and domain checks | Quality is not prediction confidence, qualification, risk approval, or execution permission |
| Canonical state | Durable/current projections whose lineage and update semantics are defined by their subsystem | Accepted normalized events and reconciliation records | A projection cannot widen the authority of its inputs |
| Intelligence and research | Features, hypotheses, forecasts, contextual analysis, evaluation, and research artifacts | Admitted state and evidence in; decision support out | No direct risk, session, order, broker, release, or reconciliation authority |
| Prediction | Immutable prediction identity, cutoff, horizon, policy, and source lineage | Decision-time inputs in; prediction ledger records out | Does not settle its own outcome or authorize action |
| Evidence campaign | Governed accumulation and assessment of forward evidence | Predictions, observations, sessions, checkpoints, and policy refs | Evidence sufficiency does not grant order or release authority |
| Settlement | Maturity checks and idempotent outcome settlement under frozen policy | Prediction records and later outcomes | Cannot rewrite the original prediction or decide qualification outside policy |
| Qualification | Applies its named evidence policy and records disposition | Frozen evidence and policy inputs | Qualification is not release approval, live-session authorization, or an order |
| Opportunity | Candidate economics and opportunity policy | Signals, forecasts, state, costs, and uncertainty | Produces a candidate, not permission to trade |
| Risk | Independent limits, blocks, and risk decisions | Candidate and portfolio/exposure state | May permit or block only within risk scope; cannot create session authorization, confirmation, or broker reality |
| Execution state | Intent, sizing, guarded mode, lifecycle, and paper/mock execution records | Risk-permitted candidates and required authorizations | Cannot bypass live safety, human authorization, confirmation, persistence, or broker response |
| Broker transport | Transmits an authorized request and reports external acceptance/rejection/fill | Fully authorized order request out; broker response in | External response is not canonical state until reconciled; accepted production live transport is currently absent |
| Reconciliation | Compares and incorporates broker/external state under explicit mismatch handling | Broker and internal ledger/state | Cannot silently absorb differences or manufacture a fill |
| Operations | Health, telemetry, controls, alerts, incidents, recovery, deployment procedures, and runbooks | Runtime state and operator actions | A runbook or control-plane mode cannot bypass executable gates |
| Release governance | Candidate eligibility, approval, revocation, promotion history, and release evidence | Build/deployment/evidence records | Governs release eligibility only, not trading authorization |
| UI | Read-only or explicitly guarded projections and operator interactions | Canonical/read-model state in; reviewed commands to existing authorities | Display state, mode labels, or controls do not independently authorize behavior |
| Assistant/AI | Read-only evidence retrieval and non-authoritative synthesis within current permissions | Admitted research sources in; cited research artifacts out | No mutation of canonical state, policy, provider admission, prediction, settlement, qualification, risk, execution, or release state; no order submission |

## Dependency directions

1. Provider-specific behavior feeds shared normalization, temporal, provenance,
   and quality contracts; shared contracts do not pretend all sources have the
   same rights, clocks, or capabilities.
2. Intelligence may read admitted canonical state. It may not reach around
   quality, temporal, prediction, settlement, risk, or execution boundaries.
3. Prediction precedes settlement. Evidence may reference both without changing
   either contract. Qualification consumes frozen evidence under its own policy.
4. Opportunity produces candidates for independent risk review. Risk output is
   necessary but insufficient for live execution.
5. Live execution, if later implemented and accepted, must pass live safety,
   bounded session authorization, per-order confirmation, persistence, broker
   response handling, and reconciliation.
6. Operations and release governance observe and govern their own scopes; they
   cannot convert research or release state into order permission.
7. UI and assistant surfaces consume projections and invoke existing guarded
   authorities only. They are not alternative authorities.

## Data crossing rules

- Every source crossing retains source identity, relevant clocks, revisions, and
  raw or hashed references where the controlling contract requires them.
- Quality and capability travel as separate dimensions. A connected provider
  may still lack entitlement, admission, sufficient quality, or execution
  capability.
- Prediction and later outcome are separate records. Settlement appends later
  evidence; it does not alter decision-time knowledge.
- Broker acceptance/fill crosses back through reconciliation before it becomes
  canonical state.
- Conflicting reports and revisions retain source/time lineage; canonical state
  must not silently rewrite earlier evidence.

## The `platform/` namespace

[`src/market_platform_foundation/platform/`](../../src/market_platform_foundation/platform)
contains security and reconciliation foundations used by UI, tools, and tests.
It is **execution-risk-and-state infrastructure**, consistent with the
[repository-closure audit](../engineering/POST_BUILD35_REPOSITORY_CLOSURE_AUDIT.md).
It is not a universal platform runtime, workflow fabric, or whole-program
authority.

## Future boundaries

Operating Fabric, Real-Time Opportunity Fabric, Cross-Asset, Narrative/Motive,
and AI/Agents remain `PARTIAL` families. Their future milestones must reuse the
boundaries above. New orchestration, cross-asset relations, narratives, models,
or agents may add information and evidence; they may not inherit risk,
execution, release, or broker authority by composition.
