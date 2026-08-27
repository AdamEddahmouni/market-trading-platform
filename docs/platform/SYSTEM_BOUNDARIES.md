# IMP system boundaries

| Field | Value |
|---|---|
| Document ID | `IMP-SYSTEM-BOUNDARIES` |
| Classification | `CANONICAL` |
| Lifecycle Status | `CANONICAL` |
| Truth Class | `CURRENT_CANONICAL_TRUTH` with labeled future attachment points |
| Canonical Subject | Program responsibility and integration boundaries |
| Owner Role | IMP program architecture owner |
| Version | `1.0.0` |
| Last Verified | 2026-08-27 |
| Establishing Milestone | `IMP-REBASE-01` |
| Supersedes | Fragmented whole-program boundary descriptions |
| Superseded By | None |

> This document is canonical for program-level interpretation and architecture. Where executable behavior is controlled by a designated schema, policy, gate, manifest, registry, or authority implementation, that executable authority controls within its defined scope.

## Current responsibility map

| Boundary | Current responsibility | Must not imply | Representative authority/reference |
|---|---|---|---|
| Providers | Transport/source-specific access, capabilities, entitlements, pacing, and provenance | Availability or reachability equals admission or execution capability | [`market_data/capabilities.py`](../../src/market_platform_foundation/market_data/capabilities.py) and [provider references](../providers/) |
| Ingestion | Bounded receipt, source envelopes, capture, queueing, and raw references | Receipt equals canonical quality or research admission | [`market_data/live_runtime.py`](../../src/market_platform_foundation/market_data/live_runtime.py), [`market_data/bounded_queue.py`](../../src/market_platform_foundation/market_data/bounded_queue.py), and provider bridges |
| Normalization | Convert source-specific records to versioned contracts while preserving provenance | Normalization erases source or revision semantics | [`intelligence/normalization/`](../../src/market_platform_foundation/intelligence/normalization/) |
| Quality | Multidimensional assessment, codes, conflict and selection behavior | One universal quality score grants authority | [`intelligence/quality/models.py`](../../src/market_platform_foundation/intelligence/quality/models.py) |
| Temporal integrity | Enforce point-in-time clocks, cutoffs, revisions, and anti-lookahead rules | Latest-known data was knowable at decision time | [`intelligence/contracts/common.py`](../../src/market_platform_foundation/intelligence/contracts/common.py) and [Temporal Integrity V1](../engineering/TEMPORAL_INTEGRITY_V1.md) |
| Canonical state | Persist governed events, snapshots, ledgers, and local execution state | A UI projection or cache becomes an independent authority | [`state/`](../../src/market_platform_foundation/state/) and [`storage/`](../../src/market_platform_foundation/storage/) |
| Intelligence | Produce features, hypotheses, forecasts, routing, model and research outputs | Intelligence grants risk or order authority | [`intelligence/`](../../src/market_platform_foundation/intelligence/) |
| Prediction | Freeze cutoff-bound forecast identity and lineage | A prediction is an outcome or permission | [`contracts/prediction_ledger.py`](../../src/market_platform_foundation/intelligence/contracts/prediction_ledger.py) |
| Evidence | Collect scoped observations and campaign records under frozen semantics | Real data automatically qualifies a system | [`forward_qualification/`](../../src/market_platform_foundation/intelligence/forward_qualification/) |
| Settlement | Attach outcomes under settlement timing and policy controls | Outcomes rewrite predictions | [`outcomes/service.py`](../../src/market_platform_foundation/intelligence/outcomes/service.py) |
| Qualification | Evaluate sufficiency against a named, scoped policy | Qualification does not authorize trading | [`EVIDENCE01_POLICY.json`](../../artifacts/forward-qualification/EVIDENCE01_POLICY.json) and executable forward-qualification code |
| Risk | Accept, reject, size, and constrain proposals under executable policy | Risk approval submits an order | [`execution/`](../../src/market_platform_foundation/intelligence/execution/) |
| Execution | Advance paper or supervised execution state only through required gates | Mode selection, research, AI, or release status is order authority | [`live_execution_safety/`](../../src/market_platform_foundation/intelligence/live_execution_safety/) and [`live_canary/`](../../src/market_platform_foundation/intelligence/live_canary/) |
| Reconciliation | Compare broker and ledger reality, preserve mismatches, and update canonical risk/state projections | Differences may be silently absorbed | [`platform/reconciliation/engine.py`](../../src/market_platform_foundation/platform/reconciliation/engine.py) |
| Operations | Health, incidents, recovery, operator control, and supervised-runtime evidence | Operational readiness authorizes a live order | [`live_canary/operational_reliability/`](../../src/market_platform_foundation/intelligence/live_canary/operational_reliability/) |
| Release governance | Evaluate software candidate evidence, change scope, and release eligibility | Release approval is not live-session or order authorization | [`live_canary/release_governance/`](../../src/market_platform_foundation/intelligence/live_canary/release_governance/) |

## `platform/` package classification

`src/market_platform_foundation/platform/` is active
**execution-risk-and-state infrastructure**. Its security and reconciliation
modules support current platform consumers. It is not an empty shell, generic
glue, a universal workflow engine, or the future IMP Operating Fabric.

## Future attachment points

- The IMP Operating Fabric will index existing run, artifact, workflow,
  capability, SOP, incident, and documentation records after REBASE-02 and
  OF-01 establish standards and append-only identity.
- The Real-Time Opportunity Fabric will attach to provider, state, feature,
  signal, opportunity, UI/action-preparation, risk, and broker stages only after
  RT-01 measures the path.
- Cross-asset domains will extend existing event, temporal, provenance, quality,
  capability, and opportunity boundaries after XA-01 defines compatibility.
- Narrative/motive and AI/agent work remains evidence-producing, attributable,
  and non-authorizing. No future attachment bypasses risk, human, execution, or
  reconciliation gates.
