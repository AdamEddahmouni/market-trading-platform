# Integrated Market Platform: Canonical Foundation Specification Revision 2

**Logical ID:** `foundation.canonical_specification.revision_2`  
**Status before exact-hash approval:** Candidate; ineffective and not implementation authority  
**Status upon attributable principal approval of these exact bytes:** Implementation-ready only for the authorized Phase 0 structural and evidence scope defined below  
**Date:** 2026-08-14  
**Owner:** Architecture lead  
**Approver:** Project owner  
**Operating mode:** Offline replay and simulated execution only; no paper-broker or live operation

## 1. Authority and revision relationship

This document is a linked successor candidate to the approved canonical foundation
specification:

- Logical ID: `foundation.canonical_specification.revision_1`
- Path: `docs/superpowers/specs/2026-08-13-integrated-market-platform-foundation-design.md`
- SHA-256: `B4EAE3240F6F968A6B393263D849013259A00187E209C8632E38DE890996D04D`

It is governed by the controlling Phase 0 plan:

- Logical ID: `phase0.governance_plan`
- Path: `docs/superpowers/plans/2026-08-13-phase-0-governance-and-no-live-safety.md`
- SHA-256: `EE22C688167F5016D7ED1953BB1DAE516BC6AB343655A7D96535C6605D37E904`

Revision 1 is incorporated normatively and byte-for-byte by reference. Every
architecture rule, contract, invariant, non-goal, safety boundary, acceptance
predicate, conditional horizon, and unresolved blocker in Revision 1 remains in
force except for its header-level statement that a revision is required before
implementation. This Revision 2 changes only that readiness state and narrows the
newly permitted work to the Phase 0 structural and evidence subject in Section 3.
If this document and Revision 1 could be read differently on any other point, the
more restrictive offline, no-live, fail-closed, prototype-preserving interpretation
controls and work stops for a new exact-hash revision.

Before exact-hash approval, this candidate has no effect. Upon attributable
approval by `PROJECT-PRINCIPAL-001` acting as project owner, Revision 2 becomes the
sole canonical foundation authority for forward-looking Phase 0 evaluation.
Revision 1 then remains immutable historical authority for evidence already bound
to its hash. Supersession never rewrites, rehashes, relabels, or invalidates prior
artifacts; each artifact continues to state the specification hash under which it
was created.

## 2. Readiness decision

Upon exact-hash approval, the canonical specification permits implementation of
only the minimum Phase 0 structural and evidence work described by Steps 9 through
13 of Section 10 of the controlling plan, and only after all earlier execution-order
conditions are effective and freshly verified:

1. the safe before-operation preservation manifest is frozen;
2. the role assignment and AI-review procedure remain effective at their approved
   hashes;
3. this revision is effective at its approved hash;
4. `ADR-REPO-001` is accepted at its approved hash;
5. the repository-mutation authorization is effective at its approved hash;
6. the governed boundary is established exactly as authorized and the after-state
   preservation difference report has no unauthorized drift;
7. this specification and the controlling plan are registered inside that boundary;
8. the `ADR-OFF-001` conformance design is recorded and effective; and
9. the Phase 0 structural implementation plan and Phase 0 implementation
   authorization are effective at their approved hashes.

Approval of this specification is a readiness decision, not repository-mutation or
implementation authorization. Missing, mismatched, expired, superseded, or
condition-failing authority leaves dependent work `BLOCKED` rather than `FAIL`.

## 3. Newly permitted Phase 0 subject

Subject to Section 2, a separately authorized executor may create and test a
minimal, new, offline-only foundation subject containing:

- a package and repository skeleton that does not copy or import prototype code;
- a closed allowlist registry containing only offline structural readers and a
  simulator identity, with no provider SDK, broker SDK, live adapter, plugin
  discovery, arbitrary module path, or environment-selectable live capability;
- explicit runtime and tooling dependency groups with a network-independent lock
  and local-artifact policy;
- milestone entry-point declarations that perform only structural self-checks and
  deterministic local replay-fixture checks;
- a foundation distribution manifest, registry snapshot, static import graph,
  dynamic-load analysis, prohibited-target catalogue, and entry-point reachability
  report;
- clean, denied-network installation and execution evidence using only the
  authorized local runtime and authorized local artifacts;
- credential-location scans that report only sanitized counts, opaque path IDs,
  classifications, and policy results, never values or account identifiers;
- the active Phase 0 assertion registry, one coherent assertion-evaluation run,
  deterministic governance verifier, assertion aggregate, and immutable candidate
  evidence root required by the controlling plan.

This is a structural and evidence milestone. It does not implement the historical
ES vertical slice described as the eventual first research milestone in Revision 1.
It does not parse, normalize, replay, score, trade, simulate fills from, or make
claims about actual market data. Synthetic local safety fixtures may exercise the
structural verifier only when they contain no provider payload and no strategy
threshold.

## 4. Invariants preserved without exception

The following requirements are cumulative with every requirement in Revision 1:

### 4.1 Offline and no-live boundary

- The Phase 0 distribution has no network dependency at installation or runtime.
- Broker SDKs, provider SDKs, HTTP clients, WebSocket clients, DNS clients, remote
  database drivers, telemetry exporters, and live extras are absent from the
  distribution and dependency lock.
- Live market-data and live execution adapters are absent from the registry and
  source tree. They are not present behind a disabled Boolean, environment variable,
  feature flag, dynamic import, plugin hook, or unreachable branch.
- No milestone entry point accepts broker credentials, provider credentials,
  account identifiers, remote URLs, arbitrary modules, plugins, or live-mode flags.
- Static and dynamic analyses must fail closed on an undeclared import, dynamic
  load, prohibited token, socket attempt, DNS attempt, HTTP attempt, subprocess
  escape, or reachable prohibited target.
- The only execution concept permitted in the Phase 0 subject is a structurally
  isolated simulator identity. Phase 0 does not implement order placement, broker
  transport, paper-broker transport, account state, or live fill handling.

### 4.2 Data, provider, and strategy boundary

- Phase 0A does not begin automatically and is not authorized by this revision.
- No provider retrieval, broker contact, package-registry contact, Git remote
  contact, Git LFS retrieval, data purchase, entitlement use, or credential use is
  permitted.
- Existing LFS pointer files remain pointer metadata only. They are not market-data
  fixtures and their referenced objects are excluded from the foundation boundary.
- No provider, broker, dataset, strategy, threshold, feature formula, paper mode,
  or live mode is selected or implemented.
- No claim of market-data availability, data quality, trading edge, expected return,
  calibrated probability, execution realism, or profitability may be inferred from
  Phase 0 structural evidence.

### 4.3 Prototype preservation

- Every existing prototype remains outside the governed repository boundary.
- No prototype path may be moved, copied into the boundary, edited, staged,
  committed, reset, cleaned, normalized, or used as an implementation dependency.
- Existing Short Squeeze tracked modifications and untracked files are user-owned
  state and must remain byte- and status-equivalent across repository-boundary work.
- Logs, caches, generated test repositories, local environments, large data, and
  sensitive paths remain excluded. Known background log drift is reported as
  excluded volatile drift and is never claimed to be unchanged or caused by Phase 0.
- Any non-excluded prototype difference stops the operation. Rollback never edits a
  prototype; it removes only a newly created, previously absent boundary when the
  applicable authorization permits that exact rollback.

### 4.4 Credentials and publication

- Credential values, private keys, tokens, account identifiers, and sensitive
  absolute-path mappings are neither published nor copied into the governed root.
- Credential scans are value-blind and produce only opaque path IDs, classifications,
  counts, and pass/block/fail reason codes.
- Published evidence uses opaque root IDs and repository-relative logical paths.
  The absolute root map is separate, access-restricted execution data and is not a
  Phase 0 evidence member.

### 4.5 Evidence and gate semantics

- Evidence artifacts are immutable, hash-addressed, sanitized, and scoped.
- Canonical JSON uses UTF-8 without BOM, LF line endings, recursively sorted object
  keys, stable array semantics, and the numeric and timestamp rules in Revision 1.
- One active assertion registry defines the exact mandatory key set. One evaluation
  run binds one registry, subject manifest, configuration, authorization set, and
  preselected evidence set.
- `BLOCKED` means required subject, authority, tool, decision, access, or evidence is
  absent. It is not converted to `FAIL` merely because work has not occurred.
- `FAIL` is used only when executable evidence contradicts an applicable predicate or
  an integrity rule defines invalid evidence as failure.
- Human approval cannot convert `BLOCKED` or `FAIL` to `PASS`.
- Candidate-root construction excludes the postroot records listed by the controlling
  plan. Final Phase 0 acceptance still requires the two qualifying fresh-context AI
  review classes, attributable principal approvals, completed acceptance index, and
  deterministic final gate.
- Passing Phase 0 never begins Phase 0A, a paper operation, a provider-connected mode,
  or live trading.

## 5. Explicitly unauthorized work

This revision does not authorize:

- creation or initialization of any repository;
- any remote creation, fetch, pull, push, clone, submodule operation, or LFS action;
- dependency download or package-registry contact;
- prototype modification, movement, import, migration, staging, or cleanup;
- schema/fixture/test-vector suite work deferred by the approved AI-review procedure;
- implementation of Phase 0A or Phases 1 through 8;
- real historical-data ingestion or replay;
- strategy selection, parameter selection, signals, orders, risk decisions, fills,
  positions, P&L, or performance analysis;
- provider or broker configuration, credentials, sessions, APIs, paper trading, or
  live trading; or
- publication of a Phase 0 `PASS` before the complete final acceptance sequence.

Each such action requires its own later authority where the canonical roadmap allows
it. No future scope can be inferred from the existence of placeholders, names,
interfaces, or excluded capability catalogues.

## 6. Change and stop rules

Implementation stops and remains `BLOCKED` when:

- an approved hash no longer matches;
- a prerequisite authority is missing or ineffective;
- the selected root cannot be resolved through the protected path map or resolves to
  an existing, linked, reparse-point, or nonempty path;
- a preservation comparison cannot be completed or detects non-excluded drift;
- the offline dependency boundary needs a new third-party package or network access;
- a prohibited import, dynamic-load route, network attempt, credential exposure, or
  prototype dependency appears;
- a required evidence artifact cannot be produced without expanding scope; or
- a material requirement in Revision 1 conflicts with the proposed structural work.

A corrective change creates a new immutable artifact or specification revision. It
does not edit an approved artifact or silently weaken an assertion.

## 7. Approval semantics

The only approval that activates this candidate is an attributable statement naming
the logical ID `foundation.canonical_specification.revision_2` and the exact SHA-256
of these bytes. Vague assent, approval of another document, or approval before a
fresh hash verification has no effect. Activation changes the readiness state only
as stated here and leaves all separate repository-mutation and implementation gates
intact.
