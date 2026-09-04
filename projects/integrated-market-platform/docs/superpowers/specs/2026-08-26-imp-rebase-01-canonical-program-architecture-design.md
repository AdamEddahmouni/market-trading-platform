# IMP-REBASE-01 Canonical Program Architecture Design

**Date:** 2026-08-26
**Status:** Approved design, pending written-spec review
**Scope:** Canonical program documentation, repository entry points, documentation governance, and REBASE-01 acceptance evidence

## Purpose

IMP-REBASE-01 converts the accepted REBASE-00 repository truth audit into a small, durable program-level documentation layer. The new layer must explain current implementation, historical milestone truth, approved future direction, executable authority, and safety boundaries without changing runtime behavior or creating prose copies of mutable policy.

The milestone is documentation-only. It does not implement the Operating Fabric, cross-asset kernel, real-time tracing, narrative or motive engines, AI workflows, production broker transport, or autonomous execution.

## Verified starting state

The design is based on the repository at `c318fef48e994dbaf2a2dfd7e00198bd4f79f949` on `cloud/build-35-release-governance-operational-acceptance`.

The recovered local lineage is:

```text
020b643  EVIDENCE-01B runtime operationalization
  -> 9ee9681  mode-launcher design
  -> 37326d6  mode-launcher implementation plan
  -> c318fef  IMP-REBASE-00 repository truth audit
  -> IMP-REBASE-01 work
```

The two pre-REBASE-00 local commits concern a frontend mode-launcher design and implementation plan. REBASE-00 inventoried both. They do not change program architecture or execution authority and remain untouched historical/supporting records.

The working tree contains unrelated tracked and untracked changes. REBASE-01 must preserve them and later perform implementation in a clean dedicated worktree based on the REBASE-01 planning commits.

## Architectural approach

Create a dedicated `docs/platform/` namespace for current program truth.

This location is preferred over repository-root documents because the root should remain a concise onboarding surface. It is preferred over `docs/architecture/` because REBASE-00 classifies that existing family primarily as experimental or proposed architecture. A dedicated namespace makes the authority boundary visible without moving historical or experimental documents.

The layer has three responsibilities:

1. Explain the current program without duplicating executable policies.
2. Separate historical truth, current canonical truth, and approved future design.
3. Route future work to the correct subsystem, authority, and milestone.

## Canonical document set

### `docs/platform/README.md`

The documentation front door. It gives a concise description of IMP, current maturity, safety status, truth classes, canonical document map, and reading order.

### `docs/platform/MASTER_ARCHITECTURE.md`

The whole-program architecture. It distinguishes implemented flow from partial foundations and planned consolidation areas. It includes:

- the external-source through reconciliation system shape;
- the distinction between the Real-Time Opportunity Fabric and IMP Operating Fabric;
- multi-speed HOT, WARM, and COLD design classes without invented performance guarantees;
- reusable foundations future work must extend;
- cross-asset, narrative/motive, AI/agent, and operating-fabric extension points;
- the requirements inherited by REBASE-02, OF-01, RT-01, and XA-01.

### `docs/platform/PROGRAM_STATUS.md`

The concise current-status authority. It records the core campaign, repository closure, Evidence track, program re-baseline, partial future families, autonomous-execution state, and absence of accepted production live broker transport. It uses stable milestone identities rather than transient commit SHAs.

### `docs/platform/MASTER_ROADMAP.md`

The current post-core roadmap. BUILD01-35 remains a completed historical campaign. EVIDENCE continues as an independent semantic track. The active dependency graph begins with REBASE-02 and sequences OF-01, OF-02, RT-01, XA-01, OF-03, and AI-01 according to REBASE-00.

### `docs/platform/CANONICAL_TRUTH_MAP.md`

A topic-to-authority index for program architecture, foundation authority, validation, temporal integrity, quality, providers, prediction, settlement, qualification, risk/execution, release governance, documentation lifecycle, and epistemic method. Executable behavior points directly to code, manifests, and frozen policy artifacts.

### `docs/platform/SYSTEM_BOUNDARIES.md`

A responsibility map for providers, ingestion, normalization, quality, temporal integrity, canonical state, intelligence, prediction, evidence, settlement, qualification, risk, execution, reconciliation, operations, and release governance. It classifies `src/market_platform_foundation/platform/` as execution-risk-and-state infrastructure.

### `docs/platform/AUTHORITY_MODEL.md`

An explanatory authority graph distinguishing information, quality, prediction, evidence, risk, execution state, human session, per-order, release-governance, and broker/reconciliation authority. It explicitly forbids shortcuts from LLMs, agents, research, prediction, qualification, release approval, or provider reconnect to broker authority.

### `docs/platform/DATA_AND_EPISTEMIC_MODEL.md`

The methodological specification for `OBSERVED_FACT`, `REPORTED_FACT`, `STATED_RATIONALE`, `INFERRED_BEHAVIOR`, `INFERRED_MOTIVE`, `NARRATIVE`, `HYPOTHESIS`, and `MODEL_OUTPUT`. It establishes support/contradiction/falsifier rules, source-incentive metadata requirements, narrative reflexivity, and structured competing motive hypotheses without creating runtime schemas.

### `docs/platform/DOCUMENTATION_STANDARD.md`

The documentation lifecycle and precedence standard. It defines document classes, lifecycle metadata, supersession, drift prevention, and rules for referencing executable authority. It applies prospectively to new canonical/supporting documents and does not retrofit the audited corpus.

### `docs/platform/GLOSSARY.md`

Controlled meanings for live, observational, paper, simulation, replay, signal, candidate, opportunity, prediction, campaign, session, qualification, provider, capability, quality, authority, risk authority, execution authority, release approval, and implementation-status vocabulary.

## Truth and status models

Three truth classes are mandatory:

- `HISTORICAL_TRUTH`: correct for an accepted milestone and cutoff.
- `CURRENT_CANONICAL_TRUTH`: authoritative current program explanation.
- `APPROVED_FUTURE_DESIGN`: accepted direction that is not represented as implemented.

Document lifecycle classes are separate:

- `CANONICAL`
- `HISTORICAL`
- `ACTIVE_SUPPORTING`
- `RUNBOOK`
- `REFERENCE`
- `GENERATED`
- `EXPERIMENTAL`
- `SUPERSEDED`

`STALE` is an audit finding, not a desired stable lifecycle state.

Implementation maturity is also separate:

- `PLANNED`
- `DESIGNED`
- `IMPLEMENTED`
- `VALIDATED`
- `OPERATIONALLY_ACCEPTED`
- `QUALIFIED`
- `PRODUCTION_ELIGIBLE`
- `DEPRECATED`

Qualifiers include `WITH_LIMITATIONS`, `BLOCKED`, and `AWAITING_EXTERNAL_EVIDENCE`. Historical milestone labels are not mechanically rewritten into this vocabulary.

## Canonical metadata

New canonical Markdown documents use a compact metadata table rather than YAML front matter, matching the repository's existing Markdown style. Required fields are:

- document ID;
- classification;
- lifecycle status;
- canonical subject;
- owner role;
- version;
- last verified date;
- supersedes and superseded-by references when applicable.

Canonical documents identify their establishing milestone rather than embedding a transient HEAD SHA. Acceptance artifacts retain exact source and commit identities.

## Canonical precedence

For the subject directly controlled, precedence is:

1. Executable schemas, policies, gates, registries, and validation manifests.
2. Accepted hashed authority manifests and explicitly scoped frozen policies.
3. Current canonical program documents under `docs/platform/`.
4. Active supporting subsystem documentation verified against code.
5. Runbooks and environment-scoped operational references.
6. Experimental designs and research proposals.
7. Immutable historical BUILD, Phase, and EVIDENCE artifacts for their original subject and cutoff.

Historical artifacts remain authoritative for their historical milestone but do not override current program truth. Same-level conflicts remain unresolved until explicitly reconciled; recency alone does not override a frozen contract.

## Authority and safety invariants

The canonical layer must preserve:

- autonomous live trading is disabled;
- human live-session authorization is required;
- per-order human confirmation is required;
- automatic broker failover is disabled;
- no production live broker transport is implemented or operationally accepted;
- real observational data is not live execution transport;
- information may flow broadly, but authority crosses only explicit, narrow, auditable gates;
- release eligibility is not live-session authorization;
- live-session authorization is not order confirmation;
- order confirmation is not a broker fill;
- broker fills must reconcile into canonical state;
- prediction, qualification, research, narrative, hypotheses, LLMs, and agents do not grant order authority.

## Epistemic invariants

The canonical layer must establish:

- an official statement is evidence, not automatic causal truth;
- an alternative motive is a hypothesis, not automatic causal truth;
- supporting and contradicting evidence are both retained;
- hypotheses carry alternatives and falsifiers where practical;
- narrative impact and factual support are separate dimensions;
- source incentives, timing, revisions, and methodological limits are provenance context;
- a narrative may influence positioning and price even when factual support is weak.

These principles are neutral analytical methods and do not encode ideological conclusions.

## Program architecture and future boundaries

The master architecture will mark major families explicitly:

| Family | Current state | REBASE-01 treatment |
|---|---|---|
| Core architecture | `COMPLETE_WITH_LIMITATIONS` historically | Preserve and explain current reusable foundations |
| Evidence maturation | `IN_PROGRESS` | Keep semantically isolated; EVIDENCE-01C remains next |
| Operating Fabric | `PARTIAL` | Define position and future requirements only |
| Real-Time Opportunity Fabric | `PARTIAL` | Require measurement before optimization |
| Cross-Asset | `PARTIAL` | Define shared-kernel extension requirements only |
| Narrative/Motive | `PARTIAL` | Define epistemic and integration requirements only |
| AI/Agents | `PARTIAL` | Require attributable, source-aware, read-only first expansion |
| Production live broker transport | `ABSENT` | State limitation; do not implement |

Gold receives one future canonical asset identity capable of commodity and monetary/reserve roles. Japan/rates/FX relationships are represented as future cross-asset relationships without predetermined causal interpretation.

## Repository entry points

`README.md` will become a concise current entry point while preserving useful onboarding and local-run instructions. Its stale “repository closure is next” statement will be replaced with current post-core status and direct links to `docs/platform/`.

`AGENTS.md` will retain validation instructions and add repository-truth, documentation-precedence, historical-integrity, EVIDENCE-isolation, authority-boundary, dirty-tree, and staged-diff guidance.

`docs/roadmap/REVISION_3_ROADMAP.md` will retain all historical projection detail and receive a short notice that current post-core planning lives in `docs/platform/MASTER_ROADMAP.md`.

`CONTRIBUTING.md` is absent and will not be invented solely for this milestone.

## ADR decision

No accepted ADR will be created during REBASE-01. Existing repository ADRs carry explicit principal approval and effectivity records. This documentation-only milestone must not manufacture principal authorization. The canonical documentation and REBASE-01 acceptance package record the re-baseline; a later principal-approved ADR may bind it if governance requires one.

## Acceptance evidence package

Create `artifacts/imp-rebase/REBASE01/` containing:

- `README.md` — scope, status, and package navigation;
- `REBASE01_ACCEPTANCE_REPORT.md` — repository state, lineage, outputs, validation, Git state, limitations, and final milestone status;
- `REBASE01_DOCUMENT_MAP.md` — canonical documents and their subjects;
- `REBASE01_MIGRATION_CHANGES.md` — every touched path, old/new role, classification, rationale, and preservation judgment;
- `REBASE01_KNOWN_LIMITATIONS.md` — only unresolved current limitations;
- `REBASE01_FILE_HASHES.json` — SHA-256 manifest generated after package content is frozen, excluding itself.

The package references canonical documents rather than copying them.

## Isolation and Git strategy

Implementation uses a clean dedicated worktree created from the planning-complete HEAD. This prevents the existing README, BUILD33, roadmap, UI audit, report, Cursor, and brainstorming changes from entering REBASE-01 diffs or commits.

The original worktree remains untouched except for the explicitly scoped design and implementation-plan commits created before isolation. The implementation worktree stages only enumerated REBASE-01 paths. No reset, clean, broad stash, uncontrolled `git add .`, merge, force-push, or main-branch update is permitted.

## Validation design

Validation proceeds in this order:

1. Verify all relative links and repository paths in new/modified documents.
2. Parse the REBASE-01 hash manifest and all new JSON.
3. Search new canonical documents for contradictory status and authority claims.
4. Compare changed paths against protected historical BUILD, EVIDENCE, release, prediction, settlement, and closure families.
5. Run `git diff --check`.
6. Run `.venv\Scripts\python.exe tools\validate.py changed` using the clean worktree's changed paths.
7. Inspect `full_suite_required`; run `.venv\Scripts\python.exe tools\validate.py full` only if required by repository policy.
8. Inspect unstaged and staged diffs, statistics, name status, and cached whitespace checks before committing.

No live-provider validation is warranted because no provider boundary changes.

Failures are recorded exactly. A failed validation followed by a passing retry remains documented as two attempts.

## Consistency and failure handling

Before acceptance, every canonical document is checked against a single matrix for:

- BUILD01-35 historical status;
- repository-closure status;
- EVIDENCE-01 through EVIDENCE-01C state;
- autonomous-execution state;
- production live broker transport;
- Operating Fabric, Cross-Asset, Real-Time, Narrative/Motive, and AI/Agent maturity;
- truth classes, lifecycle classes, and implementation vocabulary;
- executable authority paths;
- roadmap milestone names and dependency ordering.

A material same-level authority conflict, unverifiable current claim, broken canonical link, protected historical modification, or inability to isolate unrelated work blocks acceptance until resolved. Nonblocking architectural gaps are reported as limitations and produce `IMP_REBASE_01_COMPLETE_WITH_LIMITATIONS` only when the canonical layer itself remains sound.

## Acceptance criteria

IMP-REBASE-01 is accepted when:

1. The canonical program layer answers architecture, status, roadmap, boundaries, authority, epistemic method, source precedence, lifecycle, and terminology questions.
2. Current implementation and future design are visibly distinct in prose, tables, and diagrams.
3. Executable authorities are referenced rather than shadowed.
4. BUILD and EVIDENCE historical artifacts remain unchanged.
5. EVIDENCE semantics and execution/risk/release authority remain unchanged.
6. Root navigation points to current truth without becoming a second architecture specification.
7. The acceptance package records exact lineage, changes, validation, hashes, limitations, and Git disposition.
8. Applicable repository validation passes with retry history preserved.
9. Unrelated dirty-tree state remains preserved.
10. REBASE-02 receives a precise standards handoff, and OF-01, RT-01, XA-01, OF-03, AI-01, and the independent EVIDENCE continuation have explicit dependencies.

## Out of scope

- Runtime or schema changes
- Broad documentation migration or file moves
- Threshold, policy, model, provider, settlement, prediction, campaign, risk, or execution changes
- New data acquisition or provider adapters
- Operating Fabric or workflow-engine implementation
- Universal run-ledger implementation
- Cross-asset implementation
- Real-time tracing or optimization
- Narrative/motive runtime implementation
- AI/agent runtime or authority expansion
- Production broker transport
- Autonomous execution or automatic broker failover
