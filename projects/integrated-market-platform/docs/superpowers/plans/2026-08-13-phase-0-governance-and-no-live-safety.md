# Phase 0 Governance and Structural No-Live Safety Plan

**Status:** Draft operational plan; Phase 0 remains `BLOCKED` pending owner decisions and executable evidence  
**Plan date:** 2026-08-13  
**Baseline verified:** 2026-08-14  
**Scope:** Phase 0 only  
**Operating mode:** Documentation and planning; offline replay and simulated execution only  
**Canonical specification:** [Integrated Market Platform: Canonical Foundation Design and Roadmap](../specs/2026-08-13-integrated-market-platform-foundation-design.md)

## 1. Purpose

This plan operationalizes Phase 0 of the canonical specification without
changing that specification or beginning platform implementation. It defines
the governance decisions, structural safety controls, evidence artifacts,
owners, status rules, and exit criteria required before later foundation work
may rely on a repository or runtime boundary.

Phase 0 has two coupled outcomes:

1. Establish one governed source of truth and decide repository ownership while
   preserving all existing prototype paths and local changes.
2. Define and prove a foundation boundary in which broker SDKs, live adapters,
   live-order routes, and undeclared network access are structurally absent.

This plan does not merge Phase 0 with Phase 0A. Phase 0A fixture feasibility,
data capability inspection, and `DF-001`/`DF-002` evidence remain a separate
approval and evidence track.

## 2. Authority and precedence

The canonical specification remains authoritative. This plan may make its Phase
0 requirements more operational, but it may not weaken, replace, reinterpret,
or silently supersede them.

The precedence order is:

1. The canonical specification and any explicitly accepted superseding version.
2. Accepted architecture decision records.
3. This Phase 0 operational plan.
4. Evidence manifests and assertion results produced under this plan.
5. Prototype notes, project documentation, and source code as descriptive
   evidence rather than platform authority.

If an accepted ADR conflicts with the canonical specification, work stops until
the conflict is resolved through an explicit specification revision. An ADR or
evidence result cannot silently override the specification.

The current canonical status says that the foundation specification requires
revision before implementation. Therefore no structural skeleton, dependency
lock implementation, registry implementation, or executable verifier may be
started merely because this operational plan is approved. A named owner must
first accept a specification revision whose status explicitly permits the
applicable Phase 0 implementation work, and the governance verifier must record
that revision as the sole canonical authority.

## 3. Current gate state

Phase 0 is not complete. Its current aggregate state is `BLOCKED`.

| Gate | Current state | Reason |
|---|---|---|
| `GOV-001` canonical authority and implementation readiness | `BLOCKED` | One canonical specification was found and its metadata was verified, but its status still says that the foundation specification requires revision before implementation |
| `ADR-REPO-001` | `BLOCKED` | The collection root is not a Git repository and no owner has selected the repository/remote or prototype path policy |
| `ADR-OFF-001` conformance evidence | `BLOCKED` | The specification resolves the invariant, but no approved foundation skeleton, offline lock, registry snapshot, import graph, or route graph exists |
| `GOV-002` accountable ownership | `BLOCKED` | This is a sole-principal personal project, so all human roles may resolve to one disclosed principal; the formal assignment record and approved `AI-REVIEW-PROCESS-001` procedure do not yet exist |
| `GOV-003` prototype preservation | `BLOCKED` | A handoff inventory exists, but no accepted before/after manifest and review exists |
| `GOV-004` offline boundary and denied-network protocol | `BLOCKED` | No accepted distribution boundary, `ADR-OFF-001` conformance record, or denied-network replay protocol exists |
| `SEC-001` committed-secret and credential-location safety | `BLOCKED` | No approved value-redacted tracked-content scan or path-classification report exists for a governed repository |
| `SAFE-001` | `BLOCKED` | No foundation dependency lock or network-denied offline installation evidence exists |
| `SAFE-002` | `BLOCKED` | No foundation adapter registry or static import-boundary report exists |
| `SAFE-003-STATIC` | `BLOCKED` | No milestone entry-point inventory or live-order-submission reachability report exists |
| Phase 0 final status | `BLOCKED` | Every mandatory assertion must pass and the hash-bound principal approvals, qualifying AI reviews, and acceptance index must validate; prose review cannot waive missing evidence |

The matching specification metadata is an observed planning fact, not a
machine-readable assertion result. It does not imply that specification
readiness, repository governance, structural safety, installation, replay, or
any later phase has passed.

## 4. Scope boundaries

### 4.1 In scope

- Canonical-document inventory, status, ownership, and supersession rules.
- `ADR-REPO-001`: repository-root ownership and prototype path policy.
- Phase 0 conformance record for the `ADR-OFF-001` invariant.
- Preservation rules for the five prototype projects and unrelated local
  changes.
- Definition of the foundation offline distribution and dependency boundary.
- A closed adapter-registry policy for the foundation milestone.
- Static import and dependency direction rules.
- Foundation entry-point inventory and live-route reachability rules.
- Network-denied installation and replay evidence requirements.
- Credential audit procedure that never exposes values to a human or persists
  values in logs or evidence.
- Machine-readable assertion result requirements for `SAFE-001`, `SAFE-002`,
  and the static reachability portion of `SAFE-003`.
- Phase 0 ownership, approval, exception, failure, and exit rules.

### 4.2 Out of scope

- Retrieving Git LFS objects or any provider data.
- Characterizing an ES fixture or claiming trade, quote, depth, MBO, sequence,
  aggressor, correction, or queue capability.
- Designing source-specific canonical mappings.
- Selecting a strategy or inventing thresholds.
- Implementing platform contracts, adapters, replay, features, risk, execution,
  storage, or reporting.
- Installing dependencies or constructing the offline lock in this
  documentation increment.
- Moving, renaming, cleaning, staging, committing, or rewriting prototypes.
- Initializing Git or selecting a remote without the project and release owners.
- Calling brokers, providers, package registries, or other external systems.
- Reading or printing `.env` contents, credentials, tokens, or account
  identifiers.
- Paper operation, live data, live broker routing, or live trading.
- Phase 0A, Phase 1, or any conditional horizon.

## 5. Governing invariants

1. **Structural absence, not configuration disablement.** The foundation
   distribution contains no broker SDK, live market-data adapter, live execution
   adapter, broker credential schema, dynamic live-plugin discovery, or live
   order route. An environment variable cannot activate what is not present.
2. **Closed-world registry.** The foundation registry is an explicit allowlist
   of offline readers, synthetic fixtures, and simulated execution components.
   Unknown adapter identifiers fail closed.
3. **Inward dependencies.** Contracts, reference data, normalization, data
   quality, storage, replay, features, strategies, risk, and the simulator cannot
   import broker modules or prototype application entry points.
4. **No undeclared network use.** Foundation installation and replay must
   succeed with DNS and socket access denied. Any attempted network access fails
   the run and becomes evidence.
5. **No route to live submission.** Static reachability from every foundation
   entry point to any live-order submission symbol or process boundary must be
   empty.
6. **Prototype preservation.** Prototype code and its existing local changes are
   evidence and reference material. Phase 0 does not normalize their working
   trees or make them conform to foundation rules.
7. **Evidence over assertion.** A requirement without resolvable evidence is
   `BLOCKED`, not `PASS`. Prose, intention, or a disabled Boolean is not evidence
   of structural absence.
8. **No secret disclosure.** Credential audits record only safe classifications,
   opaque path IDs, sanitized locations, ignore coverage, and remediation
   ownership. They never persist raw sensitive path components, values,
   fragments, fingerprints derived from values, or account identifiers.

## 6. Non-gating verified baseline

The following facts were rechecked interactively before this plan was drafted.
They are disclosed for orientation but are not immutable Phase 0 evidence and do
not produce a `PASS`. The governed evidence workflow must reproduce them after
`ADR-REPO-001` selects the subject and publication boundary:

- The workspace root is a collection directory and has no repository governance
  selected for the integrated platform.
- The canonical specification contains 1,380 physical lines and 74,726 bytes.
  Its SHA-256 is
  `B4EAE3240F6F968A6B393263D849013259A00187E209C8632E38DE890996D04D`.
- The nested Short Squeeze repository is on `main` at commit
  `c09e0dc35b65a36ce4aaf96e40394edbe3cb55b1` and retains the unrelated modified
  and untracked state described by the handoff. Phase 0 must preserve it.
- The three named FuturesX data artifacts remain 134-byte Git LFS pointers.
  This plan does not retrieve or interpret their declared payloads.
- No foundation platform skeleton, dependency lock, closed registry, static
  import graph, entry-point inventory, or denied-network run bundle currently
  exists at the collection root.

These observations establish planning context only. They do not satisfy
`GOV-001`, `GOV-003`, or any structural safety assertion.

## 7. Evidence model

Phase 0 follows one evidence flow:

```text
observed fact
  -> immutable evidence artifact
  -> machine-readable assertion result
  -> versioned decision record with explicit status
  -> assertion aggregate
  -> hash-bound approval and final acceptance gate
```

Each evidence artifact must have:

- `evidence_id` and evidence type.
- Creation time and responsible role.
- Tool name and version, when generated.
- Scope, inputs, exclusions, and command or procedure identifier.
- Canonical SHA-256 of the artifact.
- Source revision or source-tree manifest when a Git root is unavailable.
- Sanitization statement confirming that no credential values or account
  identifiers are present.
- References to the requirements and assertions it supports.

Before evaluation, an immutable assertion registry declares the active mandatory
set. Each registry entry contains:

```text
assertion_id
assertion_version
predicate_hash
lifecycle = ACTIVE | RETIRED
effective_from_registry_version
retired_by_registry_version
```

The registry is keyed by
`(assertion_id, assertion_version, predicate_hash)`. A registry version must have
exactly one `ACTIVE` key for every assertion ID in the exact mandatory set of the
approved plan revision, no other active ID, and no duplicate active ID. The
canonical ordered ID list and its `mandatory_set_hash` are fields in the registry
and must equal the plan-derived values. Adding or retiring an assertion ID
requires an approved plan and, where canonical behavior changes, specification
revision. Changing a predicate requires a new version and predicate hash. A new
immutable registry revision marks the old key `RETIRED` and the new key `ACTIVE`;
it does not rewrite or supersede old results. Every acceptance run pins one
approved plan hash, registry hash, and mandatory-set hash.

Before evaluating any predicate, the evaluator writes a run manifest containing
the approved plan hash, active registry hash and keys, `mandatory_set_hash`,
`subject_manifest_hash`, selected evidence hashes, evaluator/tool versions,
canonical configuration hash, and authorization references. `run_id` is the
SHA-256 of the canonical run-manifest bytes with the `run_id` field omitted.

Each assertion result must have:

```text
assertion_result_id
assertion_id
assertion_version
predicate_hash
run_id
status = PASS | FAIL | BLOCKED
evaluated_at
subject_manifest_hash
expected_predicate
observed_values
evidence_refs[]
tool_versions[]
owner_roles[]
approver_roles[]
reviewer_roles[]
reason_codes[]
supersedes_assertion_result_id
```

An assertion may be `PASS` only when every referenced artifact exists, its hash
resolves, and the predicate evaluates true. `FAIL` means executable evidence
contradicts the predicate. `BLOCKED` means the subject, tool, owner decision, or
required evidence does not yet exist or cannot be evaluated.

Canonical registry, run-manifest, result, and index bytes use the canonical JSON
rules in Section 11.3 of the specification: UTF-8, sorted keys, fixed numeric
rendering, UTC timestamps, and LF line endings. `assertion_result_id` is the
SHA-256 of canonical result bytes with that field omitted.

One aggregate evaluation uses exactly one `run_id`, registry hash, and subject
manifest. It must contain exactly one result for every active mandatory key and
no result for a retired or undeclared key. Results from different runs cannot be
carried forward or mixed, although a new run may reference the same immutable
evidence and must reevaluate every predicate.

Every `evidence_refs[]` entry in every result must resolve to an immutable hash
in the run manifest's selected evidence set. Evidence-producing tools run and
finalize their artifacts before the pre-evaluation manifest is written; the
predicate evaluator cannot introduce a new evidence reference afterward. A
missing or extra reference makes that result `BLOCKED` with an integrity reason.

For an assertion mapped from multiple work packages in Section 8.1, each role
array is the lexicographically sorted set union of the corresponding normative
role column in Section 12; duplicate roles are removed. Every human ownership
and approval role resolves to the sole project principal in
`phase0.role_assignment`. Before candidate-root construction, the
independent-review role resolves to the approved `AI-REVIEW-PROCESS-001`
procedure defined in Section 12, not to a fictitious additional team member.
After candidate-root construction, the final gate resolves that procedural role
to the qualifying AI review runs. The verifier rejects a missing, extra,
unordered, or unresolved role binding and independently evaluates the applicable
reviewer-separation rules at each stage.

Within one registry key, reevaluation may link a new immutable result to its
immediate predecessor through `supersedes_assertion_result_id`. The chain must be
acyclic and type-consistent. A new assertion version starts a new chain; the
registry, not timestamps or cross-version supersession, selects the active
version. The result emitted by the selected evaluation run is current for that
acceptance attempt. Broken or ambiguous identity, registry, run-membership, or
supersession data makes the affected result `BLOCKED` with an integrity reason.

## 8. Work packages

### P0-GOV-001: Canonical-document governance

**Objective:** Prove that reviewers can identify exactly one authoritative
foundation specification and distinguish authoritative, operational,
descriptive, experimental, and superseded documents.

**Required work:**

- Inventory foundation-level documents without treating prototype docs as
  platform authority.
- Record document identifier, title, status, owner role, approval state, hash,
  effective date, and supersession links.
- Mark this file as an operational plan subordinate to the canonical
  specification.
- Verify whether the canonical status permits the proposed Phase 0
  implementation. While it says revision is required, coordinate an explicit
  revision and approval rather than treating plan approval as implementation
  readiness.
- Define how a future specification change is proposed, reviewed, accepted, and
  linked without rewriting prior evidence.
- Detect duplicate documents that claim canonical authority.

**Evidence:** Canonical-document inventory, duplicate-authority check, and
resolvable hashes.

**Owner:** Architecture lead.  
**Reviewer:** Release owner.  
**Current state:** `BLOCKED`; the canonical file is known, but the sole
principal's formal role assignment and a governed repository do not yet exist.

### P0-ROLE-001: Sole-principal accountability and AI reviewer independence

**Objective:** Assign the sole human project principal to every required Phase 0
ownership and approval capacity and make independent AI review
machine-checkable.

The assignment record must include the principal's stable public identifier,
every capacity held, effective interval, approved scope, complete overlap
disclosure, and acknowledgement. `PROJECT-PRINCIPAL-001` is the default public
identifier unless the principal approves another stable identifier; the
published evidence bundle need not contain a legal name. Every human owner and
approver in the normative matrix in Section 12 may resolve to that same
principal. This expected overlap is not a governance violation and does not
imply that additional people participate in the project.

Before candidate-root construction, the independent-review role is assigned to
the approved `AI-REVIEW-PROCESS-001` procedure in Section 12. After the root
exists, the final gate requires the qualifying run set produced under that
procedure. A qualifying AI review run may execute an independent reproduction
using approved read-only tools, but it may not author or modify any part of the
reviewed subject, predicate, evaluator implementation, evidence artifact, plan,
or specification.

**Evidence for `GOV-002`:** Sole-principal role-assignment and acknowledgement
record, overlap report, approved AI-review procedure, and preapproval
reviewer-eligibility check. The qualifying AI review-run records and coverage
map are postroot final-gate evidence and cannot be inputs to `GOV-002`.  
**Owner:** Project owner.  
**Reviewer:** Independent reviewer.  
**Assertion:** `GOV-002`.  
**Current state:** `BLOCKED`; the sole-principal model is selected, but no formal
assignment artifact or approved `AI-REVIEW-PROCESS-001` procedure exists. The
review runs are later final-gate evidence produced only after the candidate root
exists.

### P0-GOV-002: Repository ownership and prototype path policy

**Objective:** Accept `ADR-REPO-001` before any platform code migration.

The ADR must compare at least:

1. A new integrated-platform repository rooted at the current collection path,
   with existing projects preserved as excluded external/nested material until
   separately migrated.
2. A new sibling repository containing only the canonical platform and governed
   documents, with explicit references to prototypes outside its root.
3. A governed superproject that references prototypes through a deliberate
   mechanism after their local changes and ownership are reconciled.

Selecting an existing prototype repository as the integrated-platform root must
be treated as a fourth, high-risk alternative and justify why that prototype's
history, licensing, paths, and working tree should own the broader platform.

The decision criteria are:

- Named project and release owners.
- Remote ownership and access control.
- Preservation of every prototype path and local modification.
- Ability to version canonical documents and future foundation code together.
- Clear inclusion/exclusion rules for licensed data, generated artifacts,
  secrets, caches, and nested repositories.
- Clean clone and offline-build feasibility.
- Release provenance and rollback behavior.
- Migration cost and risk of accidental staging or deletion.

**Evidence:** Accepted ADR, opaque `root_id`, relocatable logical root, remote
policy, ownership record, prototype preservation manifest, and sanitized dry-run
path-classification report. Any absolute root mapping is access-restricted
execution data outside the Phase 0 evidence bundle.

**Owner:** Project owner plus release owner.  
**Reviewers:** Architecture lead and prototype maintainers.  
**Current state:** `BLOCKED`; no option is selected by this plan.

### P0-GOV-003: Prototype preservation manifest

**Objective:** Make prototype preservation verifiable before repository or path
operations occur.

The manifest must record, without copying secret values:

- Each prototype's relocatable logical path anchored to an opaque `root_id`.
- Whether it is a Git root, nested repository, plain directory, or generated
  artifact.
- Current branch and commit when applicable.
- Tracked modifications and untracked paths when applicable.
- Excluded credential-like files by opaque path ID and classification only.
- Known large pointer-only data and generated/log paths.
- Owner or maintainer role.
- Explicit operations forbidden until separate authorization.

The Short Squeeze modified/untracked set must be captured before and after any
future repository-governance operation. A changed set halts that operation for
review; it is never auto-restored, staged, cleaned, or normalized.

**Evidence:** Before/after preservation manifests and difference report.  
**Owner:** Release owner.  
**Reviewers:** Relevant prototype maintainers.  
**Current state:** `BLOCKED`; a handoff inventory exists but no accepted manifest
format or owner exists.

### P0-DIST-001: Offline distribution boundary

**Objective:** Record and conform to `ADR-OFF-001` so the foundation milestone
has a separately identifiable offline distribution.

The boundary record must specify:

- Included packages and entry points.
- Excluded broker SDKs, live clients, credential schemas, and live extras.
- Approved local package artifacts and their hashes.
- Dependency groups and transitive-dependency review rules.
- Build, installation, and replay procedures that require no network.
- Failure behavior when an undeclared dependency or network attempt appears.

The existing prototypes may contain broker clients and network integrations.
Their presence outside the approved foundation distribution is not a foundation
failure, but including or importing them from that distribution is.

**Evidence:** Distribution manifest, dependency-boundary decision record, and
path inclusion/exclusion report.  
**Owners:** Architecture lead, security owner, and release owner.  
**Reviewers:** Replay owner and independent reviewer.  
**Current state:** `BLOCKED`; the foundation distribution does not yet exist.

### P0-LOCK-001: Offline dependency lock and installation proof

**Objective:** Produce `SAFE-001` evidence.

The approved lock must be generated for the selected foundation runtime, pin
every direct and transitive dependency, and exclude at minimum:

- Broker SDKs and broker-specific order clients.
- Live market-data clients.
- Network clients not required for approved local file access.
- Packages included only for prototype dashboards or provider acquisition.
- Dynamic plugin packages capable of discovering unapproved adapters.
- Undeclared direct URL, VCS, editable, or mutable local-path dependencies.

The installation proof must begin from a clean environment, use only approved
local artifacts, deny network access, verify all artifact hashes, and preserve
the complete sanitized log. A warm global cache that contains unmanifested
artifacts cannot satisfy the assertion.

**Evidence:** Lock scan, local-artifact manifest, clean-environment description,
network-denial configuration, installation log, and installed-package inventory.

**Owner:** Release owner.  
**Reviewer:** Independent reviewer.  
**Assertion:** `SAFE-001`.  
**Current state:** `BLOCKED`; no lock or installation subject exists.

### P0-REG-001: Closed adapter registry

**Objective:** Prove that the foundation registry cannot resolve a live
market-data or live execution adapter.

The registry policy must:

- Enumerate every allowed adapter identifier and implementation reference.
- Permit only approved offline readers, synthetic fixtures, and the simulator.
- Reject unknown identifiers rather than searching modules, entry points, or
  arbitrary paths.
- Exclude environment-controlled module names and live-enable flags.
- Exclude broker credential configuration from the foundation schema.
- Produce a deterministic registry snapshot suitable for hashing.

**Evidence:** Registry source inventory, canonical registry snapshot, negative
resolution cases, and configuration-schema scan.  
**Owner:** Architecture lead.  
**Reviewers:** Execution owner and independent reviewer.  
**Assertion:** Part of `SAFE-002`.  
**Current state:** `BLOCKED`; no foundation registry exists.

### P0-IMP-001: Static import and dependency boundaries

**Objective:** Prove that core and decision layers have no static dependency path
to broker or live-provider modules.

The import policy must cover the canonical modules named by the specification:

```text
contracts
reference_data
normalization
data_quality
storage
replay
features
strategies
risk
execution.simulator
portfolio
attribution
reporting
```

The prohibited targets include broker SDK namespaces, live adapter namespaces,
prototype broker wrappers, process-spawn helpers that can launch them, dynamic
module import from configuration, and arbitrary plugin discovery.

The analysis must account for direct imports, transitive imports, optional
imports, string-based dynamic imports, package entry points, and subprocess
launch paths. A simple text search may supplement but cannot replace a resolved
dependency graph.

**Evidence:** Import-policy definition, resolved static graph, prohibited-edge
report, dynamic-import scan, and tool/version manifest.  
**Owner:** Architecture lead.  
**Reviewer:** Independent reviewer.  
**Assertion:** Part of `SAFE-002`.  
**Current state:** `BLOCKED`; no foundation source graph exists.

### P0-ROUTE-001: Entry points and live-route reachability

**Objective:** Produce the static reachability portion of canonical `SAFE-003`
and the additional Phase 0 no-live-route assertion `SAFE-P0-001`.

Every foundation milestone entry point must be enumerated, including command-line
interfaces, module runners, scheduled jobs, test harnesses, report builders,
configuration-driven factories, and any user-facing launcher. The reachability
analysis must start from each entry point and search for paths to:

- Broker connection and authentication.
- Live market-data subscription.
- Account discovery or account-state access.
- Order creation intended for external routing.
- Order submission, modification, cancellation, or replacement.
- Dynamic loading or process launch that could reach those operations.

`SAFE-003-STATIC` is the Phase 0 component result for canonical `SAFE-003`. It
passes only when the path set from every milestone entry point to live order
submission is empty. It does not claim that the full runtime assertion has
passed. `SAFE-P0-001` separately requires empty path sets to live market-data
subscription, broker account access, and all other live broker order operations.
A target that is reachable but guarded by a flag fails the applicable assertion.

**Evidence:** Entry-point inventory, prohibited-target catalogue, reachability
graph, empty-path assertion result, and independent review record.  
**Owners:** Replay owner plus security owner.  
**Reviewers:** Architecture lead, execution owner, and independent reviewer.  
**Assertions:** `SAFE-003-STATIC` plus plan-specific `SAFE-P0-001`.  
**Current state:** `BLOCKED`; no foundation entry points exist.

### P0-NET-001: Denied-network replay protocol

**Objective:** Define the later runtime evidence needed to complete `SAFE-003`
without claiming it has run during documentation work.

The protocol must specify:

- The selected isolation mechanism and what network surfaces it denies.
- DNS, IPv4, IPv6, loopback, proxy, subprocess, and package-manager handling.
- The exact offline input and configuration manifests.
- How attempted socket, DNS, HTTP, or provider use becomes a hard failure.
- How the sanitized run log and terminal state are captured and hashed.
- How the test avoids relying on previously running local services.

Static reachability evidence is required in Phase 0. Full network-denied replay
evidence becomes executable when the minimal foundation runtime exists and is
repeated in later phases as required by the canonical roadmap.

**Evidence:** Accepted protocol now; denied-network run bundle when an approved
runtime exists.  
**Owners:** Replay owner plus security owner.  
**Reviewer:** Independent reviewer.  
**Assertion:** Runtime portion of `SAFE-003`.  
**Current state:** `BLOCKED`; protocol approval and executable subject are absent.

### P0-SEC-001: Credential-location audit

**Objective:** Establish safe repository boundaries without exposing secrets.

The audit first inspects filenames, ignore rules, tracked-file lists,
configuration schemas, and known credential-loading code. It must not read or
print private `.env` contents or credential values. A tracked private `.env` or
other credential-container path fails the audit from path metadata alone and is
not opened. If a path component may itself contain a username, account ID, token
fragment, or other sensitive value, all human-visible output replaces the full
path with a random opaque identifier such as `PATH-0001`.

All other files in the accepted current tree and its reachable commit history
must be evaluated by an approved content scanner whose output redacts matches
and context and emits only opaque path ID, revision identifier, rule identifier,
and sanitized location. A private `.env` or credential-container path found anywhere in
reachable history fails by path metadata and is not opened. The scanner process
may inspect other governed historical bytes, but no matched value, fragment,
surrounding line, account identifier, or value-derived fingerprint may be
presented to a human or enter logs or evidence. Results classify paths as:

- Public safe example.
- Private local configuration.
- Generated credential-like state.
- Unknown and requiring owner review.
- Prohibited tracked material.

If a possible secret is discovered through metadata or an already-redacted
scanner result, stop work, restrict shared output to its opaque path ID and
category, and assign remediation to the security owner. A reversible raw-path
map, if remediation requires one, belongs in a separately authorized,
access-restricted security process outside the Phase 0 evidence bundle and must
not contain credential values. Rotation, deletion, history
rewrites, or external changes require separate authorization.

`SEC-001` passes only when the accepted current tree and its reachable history
contain zero prohibited credential-container paths, zero unresolved redacted
scanner findings for committed secrets or account identifiers, public examples
contain placeholders only, and every private local configuration class is
excluded by the governed ignore policy.

**Evidence:** Opaque path-classification report, sanitized current and
reachable-history manifests, redacted scanner configuration and result counts, ignore-policy
report, public example review, and owner acknowledgements.  
**Owner:** Security owner.  
**Reviewers:** Release owner and independent reviewer.  
**Assertion:** `SEC-001`.  
**Current state:** `BLOCKED`; no approved audit has been performed for the future
foundation repository.

### P0-EVID-001: Assertion aggregation and governance verifier

**Objective:** Prevent prose from converting missing or failing evidence into a
pass.

The aggregator must:

- Validate the assertion-result schema.
- Resolve every evidence reference and SHA-256.
- Reject duplicate assertion identities with inconsistent content.
- Validate the active assertion registry, immutable result identifiers,
  content-addressed `run_id`, one-run/one-subject membership, predicate hashes,
  and any same-version supersession chains.
- Require the registry's active ID set and `mandatory_set_hash` to equal the
  approved Section 9 set exactly; missing, extra, or unapproved retired IDs make
  the aggregate `BLOCKED`.
- Require exactly one result from the selected evaluation run for every active
  mandatory Phase 0 key listed by the pinned registry.
- Preserve prior results rather than rewriting history.
- Compute the assertion aggregate and final acceptance status deterministically.
- Report every unresolved decision with owner, evidence requirement, and status.
- Verify that exactly one document claims canonical foundation authority.

Aggregate status rules are:

```text
if any mandatory assertion is FAIL:          assertion_aggregate = FAIL
else if any mandatory assertion is BLOCKED: assertion_aggregate = BLOCKED
else:                                        assertion_aggregate = PASS
```

`assertion_aggregate = PASS` is not a published Phase 0 pass. The verifier next
builds a candidate-root manifest containing the lexicographically ordered tuples
`(logical_id, member_sha256, byte_length, media_type)` for every preapproval
artifact, including the registry, run manifest, assertion results, governance
verifier, and `phase0.assertion_aggregate`. It explicitly excludes
`phase0.candidate_evidence_root`, `phase0.approval_records`,
`phase0.ai_review_runs`, `phase0.ai_review_coverage`,
`phase0.acceptance_index`, and `phase0.final_acceptance_result`.

`candidate_evidence_root` is the SHA-256 of the canonical JSON tuple array using
the encoding rules in Section 7. The candidate-root manifest stores that value
and the exact tuple array, but neither the manifest nor its own logical ID is a
member of the array. The human principal then produces the required attributable
approval records, and the independent AI reviewer produces qualifying review-run
records. Every approval and review record is bound to that root, the approved
plan and specification hashes, registry hash, and `run_id`.

The final acceptance gate validates those records and the completed acceptance
index:

```text
if assertion_aggregate is FAIL:                 Phase 0 = FAIL
else if assertion_aggregate is BLOCKED:         Phase 0 = BLOCKED
else if a required approval/review is missing:  Phase 0 = BLOCKED
else if an approval, review, hash, identity, or index is invalid: Phase 0 = FAIL
else:                                           Phase 0 = PASS
```

Only the final gate may publish `Phase 0 = PASS`. Approval cannot change a
failing or blocked assertion, and it cannot be collected against a different
candidate root.

**Evidence:** Assertion registry, run manifest, aggregator specification, schema
and registry-upgrade fixtures, deterministic result, and governance-verifier
output.  
**Owner:** Release owner.  
**Reviewer:** Independent reviewer.  
**Current state:** `BLOCKED`; no executable aggregator exists.

### 8.1 Work-package-to-assertion map

Work-package identifiers describe delivery units; assertion identifiers describe
machine-evaluated outcomes. They are intentionally different and map exactly as
follows:

| Work package(s) | Assertion outcome |
|---|---|
| `P0-GOV-001` | `GOV-001` |
| `P0-ROLE-001` | `GOV-002` |
| `P0-GOV-002`, `P0-GOV-003` | `GOV-003` |
| `P0-DIST-001`, `P0-NET-001` | `GOV-004` |
| `P0-SEC-001` | `SEC-001` |
| `P0-LOCK-001` | `SAFE-001` |
| `P0-REG-001`, `P0-IMP-001` | `SAFE-002` |
| `P0-ROUTE-001` | `SAFE-003-STATIC`, `SAFE-P0-001` |
| `P0-EVID-001` | Validates and aggregates the exact mandatory set; it does not create a self-referential assertion |

## 9. Assertion acceptance matrix

| Assertion | Exact Phase 0 predicate | Required evidence | Current state |
|---|---|---|---|
| `GOV-001` | Exactly one canonical foundation specification resolves, its accepted status explicitly permits the applicable Phase 0 implementation work, and no conflicting authority claim exists | Document inventory, canonical hash, approval record, status, supersession graph | `BLOCKED` |
| `GOV-002` | Every human ownership and approval capacity resolves to the acknowledged sole project principal; all overlaps are disclosed; every unresolved decision has an owner capacity, evidence requirement, and explicit state; `AI-REVIEW-PROCESS-001` is approved for the postroot independent-review role; and the preapproval reviewer-eligibility check has zero violations | Sole-principal role-assignment record, blocker register, approved AI-review procedure, reviewer-eligibility result and violation count | `BLOCKED` |
| `GOV-003` | `ADR-REPO-001` is accepted; repository/remote and inclusion rules resolve; every repository mutation has a matching authorization; before/after prototype manifests show no unauthorized path or working-tree change | Accepted ADR, ownership record, remote policy, mutation authorization, preservation manifests, difference report | `BLOCKED` |
| `GOV-004` | The foundation distribution boundary and `ADR-OFF-001` conformance record are accepted; the denied-network replay protocol covers the required denial/evidence surfaces; and structural/evidence implementation has a matching Phase 0 implementation authorization | Distribution manifest, conformance record, accepted protocol, implementation authorization, owner/approver/reviewer records | `BLOCKED` |
| `SEC-001` | The accepted current tree and reachable history contain no prohibited credential-container path and have zero unresolved findings from value-redacted secret/account-identifier scanning; public examples contain placeholders only; private configuration is ignored | Sanitized current/history manifests with opaque sensitive-path IDs, redacted scan counts/configuration, example review, ignore-policy report | `BLOCKED` |
| `SAFE-001` | Every direct/transitive dependency is exactly pinned and hash-verified; the lock contains no broker SDK, live-only package, or network client not required for approved local file access; no direct URL, VCS, editable, or mutable local-path dependency exists; and a clean installation succeeds with network denied using only the manifest-pinned local artifacts and no unmanifested cache content | Lock-integrity and direct/transitive prohibited-package scans, approved-network-client rationale, local-artifact hashes, clean-environment/cache proof, denied-network installation log, installed inventory | `BLOCKED` |
| `SAFE-002` | The closed registry contains no live market-data or execution adapter, rejects every unknown identifier, permits no environment-controlled module name or dynamic plugin discovery, exposes no broker credential schema, and the protected layers have no static or dynamic import path to broker/live modules | Registry snapshot, unknown-resolution fixtures, configuration-schema scan, resolved import graph, dynamic-import/plugin scan | `BLOCKED` |
| `SAFE-003-STATIC` | No path from any foundation milestone entry point reaches live order submission; this is a component result and not a full runtime `SAFE-003` pass | Entry-point inventory, live-submission target catalogue, reachability graph, empty-path result | `BLOCKED` |
| `SAFE-P0-001` | No path from any foundation milestone entry point reaches live market-data subscription, broker account access, or another live broker order operation | Entry-point inventory, additional prohibited-target catalogue, reachability graph, empty-path result | `BLOCKED` |

The mandatory assertion set is exactly
`{GOV-001, GOV-002, GOV-003, GOV-004, SEC-001, SAFE-001, SAFE-002,
SAFE-003-STATIC, SAFE-P0-001}`. The aggregator computes the assertion aggregate only
from the selected evaluation run's schema-valid results for the pinned active
registry. That computation is the assertion aggregate, not the published Phase
0 status. The hash-bound approvals and acceptance-index verification in Section
8 produce the final status and cannot change a `FAIL` or `BLOCKED` predicate to
`PASS`.

The initial registry assigns assertion version `1.0.0` to every row. Its
`predicate_hash` is the SHA-256 of canonical JSON containing the assertion ID,
version, and exact predicate text from the table. Any semantic predicate change
requires a new assertion version and plan/spec review; formatting-only changes
may not silently change the registered predicate bytes.

Phase 0 may record the denied-network replay protocol, but it must not falsely
claim a runtime replay pass before the minimal replay subject exists. The full
runtime part of `SAFE-003` remains mandatory wherever the canonical roadmap
requires it.

## 10. Required execution order

The work packages are performed in this order because later evidence depends on
earlier boundaries:

1. Reverify the canonical specification hash and freeze a safe workspace
   preservation manifest.
2. Assign project, release, architecture, security, replay, execution, and
   prototype-maintainer capacities to the sole project principal, disclose the
   complete overlap, and approve the independent AI-review procedure in Section
   12.
3. Accept a canonical specification revision whose status explicitly permits
   the applicable Phase 0 structural implementation while preserving every
   foundation and no-live invariant.
4. Accept `ADR-REPO-001` as a decision only; acceptance does not initialize Git,
   create or change a remote, move paths, or modify a repository.
5. Obtain a repository-mutation authorization that names the opaque `root_id`,
   remote operations, inclusion/exclusion rules, preservation manifest,
   rollback, and approving owners. The authorized executor resolves `root_id`
   through a separately access-restricted absolute-path map that is never
   published in the Phase 0 bundle.
6. Establish the governed repository boundary exactly as authorized, without
   moving or modifying prototypes, then produce the after-operation preservation
   difference report.
7. Register the canonical specification and this subordinate plan within that
   boundary.
8. Record the `ADR-OFF-001` conformance design for the selected runtime and
   distribution boundary.
9. Create the minimal structural subject needed for evidence: package boundary,
   closed registry, dependency groups, and milestone entry-point declarations.
10. Produce the preservation, distribution, registry, import, dynamic-load, and
   reachability artifacts.
11. Produce the offline dependency lock and clean denied-network installation
   evidence.
12. Publish the active assertion registry and pre-evaluation run manifest, then
    evaluate every active mandatory key in one coherent run using the
    machine-readable predicates in Section 9.
13. Run the governance verifier, compute the assertion aggregate, and publish the
    immutable `candidate_evidence_root` for the preapproval bundle.
14. Obtain every normative human-principal approval and both qualifying
    independent AI review classes against that exact candidate root.
15. Build and verify the completed acceptance index, run the final acceptance
    gate, and only then publish the immutable Phase 0 status. Do not
    automatically begin Phase 0A or Phase 1.

Steps 9 through 13 are future implementation/evidence work. They require an
implementation authorization record approved by the project owner, release
owner, and security owner and independently reviewed as required by Section 12.
That record must reference an accepted implementation plan, the ready canonical
specification revision from Step 3, accepted `ADR-REPO-001`, the exact
source/evidence scope, and the authorized repository. Their inclusion here
defines acceptance; it does not authorize code changes in this documentation
increment.

## 11. Failure and change handling

### 11.1 Workspace drift

If the canonical specification hash, prototype paths, nested repository status,
or known pointer-only artifact state differs from the frozen baseline:

1. Stop the affected operation.
2. Record the observed difference without overwriting or normalizing it.
3. Identify whether the change is authorized, unrelated, or unknown.
4. Rebaseline only with the appropriate owner and reviewer approval.

### 11.2 Unexpected live capability

If a broker SDK, live adapter, live route, credential schema, or dynamic path to
one is found inside the proposed foundation boundary, the relevant assertion is
`FAIL`. Removing or relocating it is a separately reviewed change followed by a
new assertion result; the original failure remains immutable.

### 11.3 Missing subject or tool

If the foundation skeleton, lock, graph tool, isolation mechanism, or evidence
artifact does not exist, the result is `BLOCKED`. A manual statement that the
system is intended to be offline cannot substitute for executable evidence.

### 11.4 Potential credential exposure

Do not reproduce the value or a sensitive raw path. Record only an opaque path
ID, safe classification, discovery method, sanitized location, and remediation
owner. Keep any authorized reversible path map outside the Phase 0 evidence
bundle under security-owner access. Stop any output that could include the value.
External revocation, rotation, deletion, or Git-history changes require explicit
authorization.

### 11.5 Requested scope expansion

Requests involving data retrieval, provider calls, broker connections, paper or
live operation, prototype relocation, Git initialization, or Phase 0A work are
not absorbed into Phase 0. They require a new explicit authorization and the
applicable design/evidence process.

## 12. Ownership and approval

This is a personal project with one human principal, not a staffed organization.
Role names identify functional accountabilities and review perspectives rather
than separate people. Every human role below may be assigned to
`PROJECT-PRINCIPAL-001`, or another stable public identifier approved by the
principal, with the complete overlap disclosed. The role labels do not grant
permission to proceed, and the assignment does not imply that employees,
partners, or additional maintainers exist.

| Role | Phase 0 accountability |
|---|---|
| Project owner | Selects the integrated-platform ownership model and approves scope |
| Release owner | Owns repository/remote policy, preservation manifests, evidence publication, and aggregate gate |
| Architecture lead | Owns canonical governance, boundaries, registry design, and import policy |
| Security owner | Owns offline/no-live invariants, prohibited-target catalogue, static reachability analysis, credential-location audit, and network-denial review |
| Replay owner | Owns foundation entry-point inventory and denied-network replay protocol |
| Execution owner | Reviews prohibited live-order targets and confirms simulator separation |
| Prototype maintainers | Confirm preservation manifests and approve any later prototype-affecting action |
| Independent reviewer | Qualifying fresh-context AI review runs reproduce or audit safety assertions without authoring or modifying their subject; the human principal remains accountable |

The following matrix is normative. Inline owner/reviewer labels in Section 8 are
summaries and must match this matrix; this matrix controls if a discrepancy is
found.

| Work package or authorization | Owner(s) | Approver(s) | Reviewer(s) |
|---|---|---|---|
| `P0-GOV-001` | Architecture lead | Project owner | Release owner |
| `P0-ROLE-001` | Project owner | Release owner | Independent reviewer |
| `P0-GOV-002` | Project owner plus release owner | Project owner plus release owner | Architecture lead plus prototype maintainers |
| `P0-GOV-003` | Release owner | Project owner | Prototype maintainers |
| `P0-DIST-001` | Architecture lead, security owner, and release owner | Project owner | Replay owner plus independent reviewer |
| `P0-LOCK-001` | Release owner | Security owner | Independent reviewer |
| `P0-REG-001` | Architecture lead | Security owner plus release owner | Execution owner plus independent reviewer |
| `P0-IMP-001` | Architecture lead | Security owner | Independent reviewer |
| `P0-ROUTE-001` | Replay owner plus security owner | Release owner | Architecture lead, execution owner, and independent reviewer |
| `P0-NET-001` | Replay owner plus security owner | Release owner | Independent reviewer |
| `P0-SEC-001` | Security owner | Project owner | Release owner plus independent reviewer |
| `P0-EVID-001` | Release owner | Project owner plus security owner | Independent reviewer |
| Repository-mutation authorization | Release owner | Project owner plus release owner | Prototype maintainers for every affected path |
| Phase 0 implementation authorization | Project owner | Project owner, release owner, and security owner | Independent reviewer |

The sole project principal may hold every human role in the matrix, including
owner, approver, architecture, security, replay, execution, release, and every
prototype-maintainer capacity. Self-review performed in one of those capacities
is useful but is not independent review. All such overlaps must be explicit in
`phase0.role_assignment`.

The independent-review role is an evidence-producing AI review process, not a
claim that another person participates. It is satisfied only by at least two
separately initialized, fresh-context AI review runs:

1. An adversarial requirements-and-conformance audit covering the approved
   specification, plan, predicates, every preapproval artifact, every mandatory
   assertion, and all documented exclusions.
2. An integrity-and-reproduction audit that independently executes or checks the
   approved verifier, recomputes candidate-root hashes and aggregation, tests
   the acceptance-index construction rules and fixtures, and attempts to falsify
   the candidate status. The deterministic final gate separately verifies the
   completed postreview acceptance index.

Each qualifying run must be read-only over the governed subject and must receive
only the approved review procedure, the exact candidate evidence root, the
sanitized evidence bundle, and the instructions required for its assigned audit.
It must not inherit a project-authoring transcript or prior authoring task, and
it must not have authored or modified any reviewed subject, predicate, evaluator,
evidence artifact, plan, or specification. A run that made a project mutation or
received credential values, sensitive raw paths, or ungoverned evidence is
disqualified.

Every run record contains:

```text
review_run_id
review_class
review_procedure_id_and_hash
candidate_evidence_root
specification_hash
plan_hash
registry_hash
run_id
model_service_and_declared_version
runtime_and_tool_versions[]
canonical_configuration_hash
input_artifact_hashes[]
coverage_logical_ids[]
coverage_assertion_ids[]
findings[]
reproduction_results[]
review_output_hash
started_at
completed_at
```

`review_run_id` is the SHA-256 of the canonical run-record bytes with only that
field omitted. `review_output_hash` binds the complete sanitized review output
and is therefore transitively bound by `review_run_id`. The two runs have
different run IDs and isolated contexts; they may use the same model service
only when that fact is disclosed. The coverage union must contain every
preapproval logical artifact in the candidate evidence root and every active
mandatory assertion, with no unexplained omission.

An unresolved material AI finding makes the affected assertion or final gate
`BLOCKED`; evidence that contradicts a predicate makes it `FAIL`. After any
reviewed artifact changes, prior AI review cannot be carried forward: the
candidate root is recomputed and both review classes run again. AI review cannot
authorize repository mutation, implementation, provider access, secret handling,
or live capability and cannot replace the human principal's approvals. It
supplies independent adversarial evidence while accountability remains with the
principal.

## 13. Phase 0 exit criteria

Phase 0 is complete only when all of the following are true:

1. Exactly one canonical foundation specification is registered and resolvable.
2. Its accepted status explicitly permits the applicable Phase 0 structural
   implementation; the prior "requires revision before implementation" blocker
   is resolved by an approved, linked revision.
3. Every human accountability resolves to the acknowledged sole project
   principal, all overlaps are disclosed, and both qualifying AI review classes
   satisfy the independence, coverage, and hash-binding rules in Section 12.
4. `ADR-REPO-001` is accepted by the sole principal acting in the required owner
   capacities, with a preservation plan for all prototypes and current local
   changes; every repository mutation has a matching authorization and clean
   before/after difference report.
5. The future foundation distribution boundary is explicit and conforms to the
   structural invariants resolved by `ADR-OFF-001`; the denied-network replay
   protocol is accepted with all required denial and evidence surfaces; and the
   structural/evidence work has a matching Phase 0 implementation authorization.
6. The offline dependency lock is pinned, hash-resolvable, and contains no broker
   SDK, live-only package, or network client not required for approved local file
   access; every direct/transitive dependency is exact and no direct URL, VCS,
   editable, or mutable local-path dependency exists.
7. A clean network-denied installation succeeds using only approved local
   manifest-pinned artifacts and no unmanifested cache content.
8. The canonical adapter registry is a closed allowlist with no live market-data
   or execution adapter and no dynamic live-loading path.
9. The resolved static import graph contains no prohibited path from protected
   layers to broker or live-provider modules.
10. Every foundation entry point is inventoried; paths to live order submission
    are empty; and paths to live market data, broker account access, and other
    live broker order operations are separately empty.
11. The credential audit satisfies `SEC-001` without exposing values.
12. Every assertion in the exact mandatory set in Section 9 is `PASS` with
    resolvable evidence hashes.
13. The governance verifier reports no ownerless unresolved decision and no
    competing canonical specification.
14. Before/after prototype preservation manifests show no unauthorized change.
15. The assertion aggregate is `PASS`, all normative principal approvals and
    both qualifying AI review classes bind to the exact
    `candidate_evidence_root`, the acceptance index and root hashes verify, and
    the final acceptance gate publishes `Phase 0 = PASS`.

Until every item passes, Phase 0 remains `BLOCKED` or `FAIL` according to the
machine-readable results.

## 14. Relationship to later work

- Phase 0 completion does not make `DF-001` or `DF-002` pass.
- Phase 0A remains a separate fixture-feasibility track and is currently blocked
  by the absence of a verified lawful non-pointer ES event object.
- Phase 1 cannot accept fixture-dependent ADR choices without Phase 0A evidence.
- Phase 2 implementation cannot begin merely because structural safety passes;
  it remains gated by the canonical roadmap and accepted foundational ADRs.
- Paper operation, live data, and live trading remain conditional horizons with
  separate authorization. They are not enabled by completing Phase 0.

## 15. Deliverables register

The stable identifiers below are path-neutral. After `ADR-REPO-001` selects the
governed repository and publication layout, the acceptance index must map every
identifier except `phase0.acceptance_index` and
`phase0.final_acceptance_result` to one repository-relative logical artifact path
anchored to opaque `root_id`, media type, byte length, and SHA-256.
Published manifests and indexes contain no absolute host path or parent path
outside that root. An unmapped or multiply mapped identifier is unresolved
evidence.

The index contains `index_sha256` and `root_hash` but never maps or hashes itself
as an ordinary member. `index_sha256` is computed from canonical index bytes with
both fields omitted. `root_hash` is then computed from canonical ordered
`(logical_id, member_sha256)` pairs plus `index_sha256`. A verifier repeats these
two steps; no field depends on bytes that already contain its own value. The
final acceptance result is then computed from the verified index and contains a
`final_result_id` equal to the SHA-256 of its canonical bytes with that field
omitted. It is a derived verifier result, not an indexed member.

| Logical ID | Deliverable | Minimum contents | Phase 0 use |
|---|---|---|---|
| `phase0.canonical_inventory` | Canonical-document inventory | Document IDs, authority class, owner, status, hash, supersession links | `GOV-001` and governance verifier |
| `phase0.spec_revision_approval` | Canonical readiness approval | Approved revision, owner/reviewer acknowledgements, implementation-readiness status | `GOV-001` |
| `phase0.role_assignment` | Sole-principal accountability record | Stable principal identifier, all assigned capacities, effective intervals, complete overlaps, acknowledgements | `GOV-002` |
| `phase0.ai_review_procedure` | Independent AI-review procedure | Review classes, isolation rules, read-only boundary, required run fields, coverage and finding semantics | `GOV-002` and final review authority |
| `phase0.adr_repo_001` | `ADR-REPO-001` | Alternatives, decision, owners, consequences, preservation evidence | `GOV-003` |
| `phase0.repository_mutation_authorization` | Repository-mutation authorization | Exact target, allowed operations, preservation input, rollback, approvals | Execution checkpoint for `ADR-REPO-001` |
| `phase0.adr_off_001_conformance` | `ADR-OFF-001` conformance record | Distribution boundary, exclusions, registry/import/network rules | Safety design authority |
| `phase0.denied_network_protocol` | Denied-network replay protocol | Isolation surfaces, failure rules, inputs, sanitized evidence capture, approvals | `GOV-004` |
| `phase0.prototype_preservation` | Prototype preservation manifest | Paths, repo state, exclusions, hashes/status, forbidden operations | `GOV-003` before/after drift control |
| `phase0.distribution_manifest` | Foundation distribution manifest | Included/excluded paths, package groups, entry points | Subject definition |
| `phase0.dependency_lock_report` | Offline dependency lock report | Direct/transitive inventory and prohibited-package scan | `SAFE-001` |
| `phase0.local_artifact_manifest` | Local artifact manifest | Package artifact names and SHA-256 values | `SAFE-001` |
| `phase0.denied_network_install` | Denied-network installation log | Clean environment, denial mechanism, outcome, installed inventory | `SAFE-001` |
| `phase0.registry_snapshot` | Registry snapshot | Allowed identifiers and implementations | `SAFE-002` |
| `phase0.import_boundary_report` | Import-boundary report | Resolved graph, prohibited edges, dynamic-load scan | `SAFE-002` |
| `phase0.entrypoint_route_report` | Entry-point and route report | Entry points, canonical and additional prohibited targets, reachability paths | `SAFE-003-STATIC` and `SAFE-P0-001` |
| `phase0.credential_audit` | Credential safety audit | Opaque path IDs, sanitized locations, redacted scan counts, ignore policy, remediation ownership | `SEC-001` |
| `phase0.assertion_registry` | Assertion registry | Registry version, active/retired keys, predicate hashes, revision lineage | Mandatory-set selection |
| `phase0.assertion_run_manifest` | Gate-evaluation run manifest | `run_id`, registry/subject/config/tool/evidence hashes, authorization references | One-run aggregate coherence |
| `phase0.aggregator_specification` | Aggregator specification | Canonical schemas, validation order, aggregate and final-gate rules, error semantics | `P0-EVID-001` implementation authority |
| `phase0.assertion_schema_fixtures` | Assertion schema fixtures | Positive, missing/extra-key, mixed-run, identity, hash, and approval cases | Aggregator verification |
| `phase0.registry_upgrade_fixtures` | Registry-upgrade fixtures | Predicate-version change, ID addition/retirement, set-equality, and unapproved-shrink cases | Registry verification |
| `phase0.assertion_results` | Assertion results | One versioned `PASS`/`FAIL`/`BLOCKED` record per active key for the selected run | Aggregate Phase 0 gate |
| `phase0.governance_verifier` | Governance-verifier output | Mandatory-set equality, selected-run membership, blocker and authority checks | Aggregate Phase 0 gate |
| `phase0.assertion_aggregate` | Assertion aggregate result | Selected `run_id`, per-key statuses, deterministic aggregate status, reason codes | Candidate-root input |
| `phase0.candidate_evidence_root` | Preapproval evidence root | Ordered preapproval logical-ID/hash pairs and computed root | Approval binding |
| `phase0.approval_records` | Human-principal approval records | Attributable acknowledgements for every required owner/approver capacity tied to artifact hashes | Final approval |
| `phase0.ai_review_runs` | Independent AI review-run records | Separate conformance and integrity/reproduction runs with model, procedure, input, coverage, finding, reproduction, and output hashes | Independent final review |
| `phase0.ai_review_coverage` | AI review coverage result | Exact candidate-root artifact and active-assertion coverage union, isolation checks, unresolved findings, and qualification result | Postroot final-gate reviewer qualification |
| `phase0.implementation_authorization` | Phase 0 implementation authorization | Approved plan/spec/ADR references, repository, source/evidence scope, approvers | Checkpoint before Steps 9–13 |
| `phase0.final_acceptance_result` | Final acceptance result | Assertion aggregate, approval/index validation, final `PASS`/`FAIL`/`BLOCKED`, reasons | Published Phase 0 status |
| `phase0.acceptance_index` | Phase 0 acceptance index | ID-to-path/hash map, decisions, assertions, owners, reviews, and root hash | Final review |

## 16. Reviewer questions

A reviewer should be able to answer these questions using this plan and its
future evidence bundle:

1. Which document is authoritative, and what happens if an ADR conflicts with
   it?
2. Who owns the integrated repository, and how are prototype changes preserved?
3. What exactly belongs to the offline foundation distribution?
4. Can any configuration value, plugin mechanism, import, or entry point reach a
   live provider or broker operation?
5. Does the lock contain any broker SDK or unapproved network client?
6. Did installation succeed with network access denied and only pinned local
   artifacts?
7. Which evidence proves each safety assertion, and do its hashes resolve?
8. Were any secrets or account identifiers exposed during governance checks?
9. Were both AI review classes independently initialized, read-only,
   non-authoring, complete in coverage, and bound to this exact candidate root?
10. Why is Phase 0 currently `PASS`, `FAIL`, or `BLOCKED`?
11. Does completing Phase 0 authorize data retrieval, strategy work, paper
    operation, or live trading? The required answer is no.

## 17. Current decisions and blockers

### Resolved by the canonical specification

- The foundation milestone is offline replay and simulated execution only.
- Broker SDKs and live adapters are absent from the foundation distribution.
- The registry is closed and no live route may be reachable.
- Protected layers cannot import broker modules.
- Installation and replay require network-denied evidence.
- Prototype working trees remain preserved until separately authorized.

### Resolved for this operational plan

- This is a personal project governed by one human principal, not a staffed
  organization.
- The sole principal may hold every human ownership, approval, delivery, and
  prototype-maintainer capacity with the overlap disclosed.
- Rigorous independent review is supplied by the two fresh-context AI review
  classes in Section 12. AI review supplies adversarial evidence but never
  replaces the principal's authority or accountability.

### Still blocked

The owner labels below are functional capacities held by the sole principal;
they do not imply separate people.

| Blocker | Required owner | Required resolution |
|---|---|---|
| Canonical implementation-readiness status | Project owner plus architecture lead | Accept and register a specification revision that explicitly permits the applicable Phase 0 structural implementation |
| Repository and remote ownership | Project owner plus release owner | Accept `ADR-REPO-001` with prototype preservation evidence |
| Sole-principal assignment and AI-review procedure | Project owner | Publish the formal `PROJECT-PRINCIPAL-001` capacity assignment, disclose all overlaps, and approve the two-class AI-review procedure |
| Foundation distribution subject | Architecture lead, security owner, and release owner | Approve the boundary and minimal structural subject |
| Denied-network replay protocol | Replay owner plus security owner | Obtain release-owner approval and independent review for the complete isolation/evidence protocol |
| Offline dependency lock and local artifacts | Release owner plus security owner | Produce and independently review `SAFE-001` evidence |
| Closed registry and import graph | Architecture lead | Produce and independently review `SAFE-002` evidence |
| Entry-point reachability | Replay owner plus security owner | Inventory entry points, produce static reachability evidence, and obtain execution-owner review |
| Credential-location audit | Security owner | Produce a value-free sanitized path report |
| Aggregate Phase 0 result | Release owner | Resolve every assertion, record the principal's required approvals, complete both qualifying AI review classes, and publish the acceptance index |

No blocked item may be converted to a pass by assuming a future implementation
will satisfy it.
