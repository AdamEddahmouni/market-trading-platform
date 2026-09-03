# IMP-REBASE-01 Canonical Program Architecture — Final Implementation Specification

| Field | Value |
|---|---|
| Document ID | `IMP-REBASE-01-SPEC` |
| Classification | `ACTIVE_SUPPORTING` |
| Truth class | `APPROVED_FUTURE_DESIGN` |
| Status | `APPROVED_FOR_IMPLEMENTATION` |
| Version | `1.0` |
| Last verified | `2026-08-27` |
| Establishing milestone | `IMP-REBASE-01 written-spec review` |
| Supersedes | `2026-08-26-imp-rebase-01-canonical-program-architecture-design.md` as the implementation contract only |
| Superseded by | None |

This specification is the sole implementation contract for IMP-REBASE-01. The approved design remains preserved as design history. Where the design and this specification differ, this specification controls implementation scope and acceptance. Its approval is an implementation-readiness judgment; it is not principal approval of an ADR, an executable policy, a provider, a model, a dataset, a qualification decision, or trading authority.

## Purpose

IMP-REBASE-01 converts the accepted IMP-REBASE-00 repository audit into a small current program-documentation layer. That layer must let a reader locate current program truth, historical evidence, executable authority, safety boundaries, program-family maturity, and approved future direction without turning prose into a competitor to code, policies, gates, registries, or frozen evidence.

The milestone is documentation-only. It explains and indexes repository truth; it does not change runtime behavior or authorize future architecture.

## Verified starting state

The written-spec review recovered this state on 2026-08-27:

| Item | Verified value |
|---|---|
| Repository | `C:/Users/adame/Desktop/market-trading-platform/integrated-market-platform` |
| Branch | `cloud/build-35-release-governance-operational-acceptance` |
| Review starting HEAD | `eb36f7ee9b25344f61977fbffedfb1dad8e4e0cc` |
| Upstream | `origin/cloud/build-35-release-governance-operational-acceptance` |
| Ahead / behind | 4 / 0 |
| Upstream ref | `020b64377393c3af1e085b9906e74552a2ca08b9` |
| Tracked modifications | 9 |
| Untracked paths | 16 |

The local planning lineage at review start is:

```text
020b643  EVIDENCE-01B runtime operationalization; upstream tip
  -> 9ee9681  mode-launcher design
  -> 37326d6  mode-launcher implementation plan
  -> c318fef  IMP-REBASE-00 repository truth audit
  -> eb36f7e  approved IMP-REBASE-01 design
  -> written-spec review commit
```

Implementation must use the written-spec review commit, not `c318fef` or `eb36f7e`, as its base.

The original worktree contains unrelated changes to `README.md`, BUILD33 artifacts, `docs/roadmap/REVISION_3_ROADMAP.md`, UI assistant-audit evidence, Cursor/brainstorm state, a Revision 3 effectivity notice, and validation reports. `README.md` and `docs/roadmap/REVISION_3_ROADMAP.md` overlap the intended REBASE-01 path set. A clean implementation may modify their committed forms, but it must record both paths as `REQUIRES_LATER_RECONCILIATION` and must not merge, stage, discard, or overwrite the original local edits.

An additional clean worktree was observed at:

```text
C:/Users/adame/Documents/Codex/2026-08-27/files-pasted-by-the-user-imp/work/imp-rebase-01
branch: docs/imp-rebase-01
HEAD: 6d365031d36a4d1b2f14a80d2690c28cff9c9713
```

That commit contains a premature implementation based on the unreviewed design. It is not an accepted implementation base or source of truth. The implementation phase must leave it untouched and create a new clean branch/worktree from the review-complete HEAD. It may not cherry-pick or treat `6d36503` as authoritative.

## Repository evidence that controls this specification

The implementation must remain grounded in these sources:

- `artifacts/imp-rebase/REBASE00/**` for the accepted audit, its source labels, classifications, migration judgments, gaps, dependency analysis, and limitations;
- `manifests/phase0/canonical-authority.json` and `src/market_platform_foundation/authority.py` for the exact-hash Foundation specification authority only;
- `tools/validation_manifest.json`, `tools/validation_manifest.py`, `tools/validate.py`, and `.github/workflows/imp-validate.yml` for current validation behavior;
- `artifacts/full-system-acceptance/BUILD35_AUTHORITY_MAP.json` and current authority implementations for safety-critical decision ownership;
- `src/market_platform_foundation/intelligence/contracts/common.py`, quality, prediction-ledger, settlement, provider-capability, risk, execution, live-safety, authorization, confirmation, reconciliation, and release-governance code for the behaviors they control;
- `docs/engineering/EVIDENCE_01_LONGER_FORWARD_QUALIFICATION.md`, `docs/engineering/EVIDENCE_01A_REAL_FORWARD_OBSERVATION_CAMPAIGN.md`, `docs/engineering/EVIDENCE_01B_REAL_PROVIDER_RUNTIME_OPERATIONALIZATION.md`, their code, and frozen policy/artifact references for EVIDENCE semantics;
- `AGENTS.md` and `docs/engineering/VALIDATION_ARCHITECTURE.md` for current repository workflow and validation rules;
- `docs/roadmap/REVISION_3_ROADMAP.md` as a Revision 3 projection, not the post-EVIDENCE master roadmap;
- existing ADR and governance records as evidence that accepted ADRs require explicit principal approval and effectivity binding.

Exact counts, thresholds, policy IDs, provider states, model identities, and test inventories remain in their executable or frozen sources. New canonical prose may identify those sources but must not maintain shadow copies of their mutable values.

## Scope

IMP-REBASE-01 may:

- create the ten canonical program documents listed below under `docs/platform/`;
- update the root `README.md` only as a concise current entry point while preserving onboarding, setup, local-run, safety, and developer guidance;
- add actionable documentation and truth-preservation rules to `AGENTS.md` without weakening its validation rules;
- add a short, separated current-planning notice to `docs/roadmap/REVISION_3_ROADMAP.md` without changing its historical projection or effectivity text;
- create the four-file REBASE-01 acceptance package defined below;
- validate links, paths, terminology, hashes, history protection, change isolation, and repository documentation checks;
- commit one coherent documentation-only implementation change.

## Out of scope

The following are forbidden during implementation:

- runtime code, schemas, providers, adapters, models, predictions, settlement, qualification, risk, execution, release gates, broker transport, workflow engines, run ledgers, tracing, cross-asset runtime, narrative/motive runtime, AI runtime, hot-state optimization, autonomous execution, or automatic broker failover;
- changes to policy thresholds, policy IDs, model identities, dataset identity, provider admission/capability state, validation semantics or inventory, execution gates, release gates, settlement behavior, prediction behavior, EVIDENCE semantics, or accepted historical dispositions;
- broad documentation migration, renames, moves, deletion, or retrospective metadata insertion into the audited corpus;
- an accepted ADR or any claim of new principal authorization;
- live-provider validation, provider credential inspection, or external execution;
- implementation of documentation automation that this specification marks as a future requirement.

Any wording that could reasonably authorize one of these changes must be narrowed before acceptance.

## Truth model

Truth class, document classification, implementation maturity, family consolidation, and milestone disposition are independent dimensions. They must not be collapsed into one `status` field or inferred from one another.

### Truth classes

| Truth class | Meaning | Authority boundary |
|---|---|---|
| `HISTORICAL_TRUTH` | Accepted evidence about a named subject at a recorded cutoff. | Remains authoritative for what occurred or was accepted at that cutoff; does not control current behavior merely because it is immutable. |
| `CURRENT_CANONICAL_TRUTH` | Current program-level explanation accepted through REBASE-01 and bound to current sources. | Explains the program and routes readers to controlling sources; cannot override executable authority or historical evidence. |
| `APPROVED_FUTURE_DESIGN` | Accepted direction or requirement not represented as implemented. | Guides future milestones only; grants no runtime, safety, provider, release, or execution authority. |

A document may contain more than one truth class only when sections or table rows label the class explicitly. Historical labels and exact frozen dispositions must be preserved verbatim when quoted as identifiers.

### Document classification

Use one classification field:

```text
CANONICAL
HISTORICAL
ACTIVE_SUPPORTING
RUNBOOK
REFERENCE
GENERATED
EXPERIMENTAL
SUPERSEDED
```

`STALE` is an audit finding, not a stable target classification. `SUPERSEDED` is the lifecycle terminal for a document displaced as current explanation; supersession does not erase its historical value. A separate mandatory `Lifecycle Status` field is removed because it duplicated this classification.

### Implementation maturity

Use these terms only for a named implementation or capability and cite supporting evidence:

```text
PLANNED
DESIGNED
IMPLEMENTED
VALIDATED
OPERATIONALLY_ACCEPTED
QUALIFIED
PRODUCTION_ELIGIBLE
DEPRECATED
```

These terms do not imply one another unless the controlling subsystem contract says so. In particular, `IMPLEMENTED` does not imply `VALIDATED`, `QUALIFIED`, or `PRODUCTION_ELIGIBLE`.

### Program-family consolidation assessment

Use:

```text
ABSENT
PARTIAL
CONSOLIDATED
```

`PARTIAL` is a program-family architecture assessment: reusable foundations exist, but no universal consolidated authority or system exists. It never means 50 percent implemented, half complete, production capable, operationally accepted, qualified, or production eligible.

Every `PARTIAL` family entry must identify:

1. existing reusable foundations;
2. missing consolidation primitives;
3. the next owning milestone.

### Milestone and track disposition

`COMPLETE`, `COMPLETE_WITH_LIMITATIONS`, `IN_PROGRESS`, `BLOCKED`, and `AWAITING_EXTERNAL_EVIDENCE` describe a named milestone or program track, not implementation maturity.

- `COMPLETE` means that milestone's acceptance criteria passed with no unresolved milestone-execution limitation.
- `COMPLETE_WITH_LIMITATIONS` means the milestone passed but retains one or more explicit nonblocking limitations in its own execution or accepted output.
- `IN_PROGRESS` means work or required evidence for the named track remains open.
- `BLOCKED` means an identified prerequisite prevents safe progress or acceptance.
- `AWAITING_EXTERNAL_EVIDENCE` means completion depends on evidence that cannot be manufactured by documentation or offline validation.

Known platform limitations that REBASE-01 intentionally documents, such as no production live broker transport or no Universal Run Ledger, do not by themselves require `IMP_REBASE_01_COMPLETE_WITH_LIMITATIONS`.

## Documentation architecture

Create one current program layer under `docs/platform/`. Existing `docs/architecture/` material remains primarily experimental/proposed, existing engineering documents remain subsystem-specific, and historical BUILD/EVIDENCE packages remain immutable. The root `README.md` becomes a router, not a second program architecture.

### Canonical document-set review

| Proposed file | Decision | Reason and non-overlap rule |
|---|---|---|
| `docs/platform/README.md` | `KEEP` | Navigation and reading order only; no detailed status, architecture, roadmap, or policy duplication. |
| `docs/platform/MASTER_ARCHITECTURE.md` | `KEEP` | Explains how the program fits together and where future families attach. It does not own responsibilities, decision rights, or mutable policy values. |
| `docs/platform/PROGRAM_STATUS.md` | `KEEP` | Owns mutable current program summary and limitation state. It does not restate architecture or executable configuration. |
| `docs/platform/MASTER_ROADMAP.md` | `KEEP` | Owns post-core milestone dependency semantics and future sequencing. It does not claim implementation or authorization. |
| `docs/platform/CANONICAL_TRUTH_MAP.md` | `KEEP` | A topic-to-source index. It contains paths, scopes, truth class, and conflict disposition, not narrative duplicates of source content. |
| `docs/platform/SYSTEM_BOUNDARIES.md` | `KEEP` | Owns responsibilities, permitted dependency directions, and where authority stops. `MASTER_ARCHITECTURE.md` owns system composition. |
| `docs/platform/AUTHORITY_MODEL.md` | `KEEP` | Explains safety-critical decision relationships and references exact authorities. It is not a policy, gate, or executable registry. |
| `docs/platform/DATA_AND_EPISTEMIC_MODEL.md` | `KEEP` | Owns analytical method and vocabulary, not runtime schemas or a universal ontology. |
| `docs/platform/DOCUMENTATION_STANDARD.md` | `KEEP` | Owns prospective documentation classification, metadata, supersession, anti-shadowing, and drift rules. Automation is explicitly future work. |
| `docs/platform/GLOSSARY.md` | `KEEP` | Owns controlled term meanings and prevents overloaded `LIVE`, authority, maturity, and evidence language. |

No existing current document covers any one of these program-wide subjects without the drift or scope problems identified by REBASE-00. All ten are retained, but each must honor the narrow contract below.

## Canonical metadata contract

The ten new canonical documents use compact Markdown tables. Required fields are:

- `Document ID`;
- `Classification`;
- `Primary Truth Class`;
- `Canonical Subject`;
- `Establishing Milestone`;
- `Version`;
- `Last Verified`;
- `Supersedes`;
- `Superseded By`.

`Owner Role` is not mandatory because the repository does not establish a truthful current organization-wide ownership taxonomy. A document may add `Maintainer` only when an existing governed role or path owner supports the claim. No personal owner or invented organization is permitted.

The ten document IDs are semantic navigation identifiers only:

| File | Document ID |
|---|---|
| `README.md` | `IMP-PLATFORM-INDEX` |
| `MASTER_ARCHITECTURE.md` | `IMP-ARCHITECTURE` |
| `PROGRAM_STATUS.md` | `IMP-PROGRAM-STATUS` |
| `MASTER_ROADMAP.md` | `IMP-MASTER-ROADMAP` |
| `CANONICAL_TRUTH_MAP.md` | `IMP-TRUTH-MAP` |
| `SYSTEM_BOUNDARIES.md` | `IMP-SYSTEM-BOUNDARIES` |
| `AUTHORITY_MODEL.md` | `IMP-AUTHORITY-MODEL` |
| `DATA_AND_EPISTEMIC_MODEL.md` | `IMP-EPISTEMIC-MODEL` |
| `DOCUMENTATION_STANDARD.md` | `IMP-DOCUMENTATION-STANDARD` |
| `GLOSSARY.md` | `IMP-GLOSSARY` |

Document IDs do not identify executable authorities. Version begins at `1.0`. Increment it only for an accepted semantic change; spelling, formatting, or repaired links do not require a version increment. Do not embed a current commit SHA in canonical metadata. Acceptance evidence records exact Git and hash identity.

## Canonical document contracts

### `docs/platform/README.md`

Provide the program description, safety posture in one paragraph, truth-class reading rule, canonical document table, and recommended reading order. Link to `PROGRAM_STATUS.md`, `MASTER_ARCHITECTURE.md`, `MASTER_ROADMAP.md`, `CANONICAL_TRUTH_MAP.md`, and the remaining canonical references. Do not maintain status tables, authority inventories, thresholds, or milestone dependencies here.

### `docs/platform/MASTER_ARCHITECTURE.md`

Explain the current end-to-end shape from sources through ingestion, normalization, state, intelligence, prediction/evidence/settlement, opportunity/risk/execution, broker reality, reconciliation, operations, and user surfaces. Visibly distinguish `IMPLEMENTED`, `PARTIAL`, `ABSENT`, and `APPROVED_FUTURE_DESIGN` content.

Show the difference between the Real-Time Opportunity Fabric and Operating Fabric. HOT/WARM/COLD are architectural workload classes only; do not add performance guarantees. State reuse requirements for temporal, provenance, quality, capability, prediction, settlement, risk, and reconciliation foundations. Use diagrams for composition, not as authority definitions.

### `docs/platform/PROGRAM_STATUS.md`

Own the concise current status of BUILD01-35 historical acceptance, repository closure, EVIDENCE-01/01A/01B, EVIDENCE-01C, REBASE-01, future families, autonomous execution, and production broker transport. Current claims must cite exact source paths.

Update this document only for a material accepted program-state change, including:

- milestone acceptance or invalidation;
- family consolidation or implementation maturity change;
- creation, removal, or transfer of a material authority boundary;
- opening or closing a major program limitation;
- qualification or production-eligibility change.

Minor commits, refactors, copy edits, and ordinary test-count changes do not require an update.

### `docs/platform/MASTER_ROADMAP.md`

Represent hard dependencies, soft dependencies, parallel-safe preparation, and later integration dependencies separately. Numbering or display order must not imply a hard dependency. Preserve BUILD01-35 as historical and EVIDENCE as an independent semantic track.

### `docs/platform/CANONICAL_TRUTH_MAP.md`

For each subject, record current source, source type, truth class, controlling scope, and any unresolved conflict. For executable subjects, link to code/manifests/frozen policies. For historical subjects, link to the immutable artifact and cutoff. For future subjects, link to an approved design or roadmap milestone and label it non-implemented.

This file must not copy qualification thresholds, risk limits, provider states, quality enums, policy IDs, model identities, validation counts, execution gates, release gates, settlement behavior, or prediction behavior. It may name a type or authority for navigation while requiring the reader to inspect the source for current values.

### `docs/platform/SYSTEM_BOUNDARIES.md`

Define who owns what, permitted dependency direction, data crossing, and where each authority stops across providers, ingestion, normalization, temporal/provenance, quality, canonical state, intelligence, prediction, evidence, settlement, qualification, opportunity, risk, execution, reconciliation, operations, release, UI, and assistant surfaces.

Classify `src/market_platform_foundation/platform/` as execution-risk-and-state infrastructure based on its current security and reconciliation content. Do not imply it is a universal platform runtime. Avoid a second architecture narrative.

### `docs/platform/AUTHORITY_MODEL.md`

Provide an explanatory map, not a new authority implementation. Reference exact current sources and describe only verified relations:

```text
information and model outputs -> decision support only
risk authority               -> may permit or block within its scope
live safety gate             -> prerequisite gate, not an order
session authorization        -> permits a bounded live session within policy
order confirmation           -> authorizes a specific candidate action
broker                       -> external acceptance/rejection/fill reality
reconciliation               -> incorporates external reality into canonical state
release governance           -> governs release eligibility, not trading authorization
```

Do not invent capabilities or imply that a single mode flag, release approval, forecast, qualification result, provider connection, LLM, or agent can submit an order.

### `docs/platform/DATA_AND_EPISTEMIC_MODEL.md`

Specify the methodological vocabulary and its orthogonal dimensions without defining runtime schemas. Use `REPORTED_CLAIM`, not `REPORTED_FACT`, because a source assertion is not verified by being reported.

| Epistemic role | Required meaning |
|---|---|
| `OBSERVED_FACT` | A direct measurement or event observation with provenance and clocks; observational error remains possible. |
| `REPORTED_CLAIM` | An assertion attributed to a source; the label makes no verification claim. |
| `STATED_RATIONALE` | An actor's declared explanation, treated as a specialized reported claim and evidence of what was stated. |
| `INFERRED_BEHAVIOR` | An interpretation of observed or reported actions/patterns. |
| `INFERRED_MOTIVE` | A causal-intent hypothesis, never a secret true-motive field. |
| `NARRATIVE` | A proposition or story plus dissemination characteristics; prevalence is not truth. |
| `HYPOTHESIS` | A testable analytic proposition with supporting evidence, contradictions, alternatives, and falsifiers where material. |
| `MODEL_OUTPUT` | A model-produced estimate/classification with model and input provenance; not a fact or authority. |

These roles are not a single mutually exclusive truth ladder. One source item may support several separate analytic records, and a hypothesis may reference observations, reported claims, narratives, and model outputs. Do not collapse those roles into one scalar truth score.

Keep the following dimensions separate:

- provenance and source identity;
- event/publication/availability/decision time and revisions;
- direct observation versus source assertion;
- corroboration and contradiction;
- analytic confidence and uncertainty;
- factual support;
- belief prevalence;
- narrative reach and velocity;
- market confirmation and market impact.

Conflicting reports remain represented with their source and timing. Revisions append or supersede with lineage; they do not silently rewrite prior evidence. Confidence belongs to an observation-quality or analytic-assessment context, not to a source label alone.

Source incentives are actor-neutral provenance context. Relevant dimensions may include self-interest, institutional mandate, reporting incentives, legal constraints, methodology, revision practices, timing, jurisdiction, ownership, and self-reporting. None makes a government, private, media, or other source reliable or unreliable by default.

Material motive analysis must support competing hypotheses such as H1/H2/H3 with supporting evidence, contradicting evidence, timing consistency, incentive consistency, market consistency, and falsifiers. No record may claim `actor_secret_true_motive`.

Generalize the gold principle: one canonical instrument or asset identity may participate in multiple analytical domains. Gold is the motivating commodity and monetary/reserve example; the principle may later apply to Treasuries, currencies, stablecoins, crypto, and other instruments without prescribing a universal ontology now.

Future Japan/rates/FX analysis may relate JPY, JGBs, BOJ actions, intervention, reserve activity, Treasury holdings, cross-border capital, and hedging. It must represent competing causal hypotheses and must not encode any user, official, or alternative account as fact.

### `docs/platform/DOCUMENTATION_STANDARD.md`

Define the truth, classification, maturity, metadata, supersession, anti-shadowing, link, and material-status-update rules in this specification. Apply them prospectively to new canonical and supporting documents; do not retrofit historical artifacts.

Mark automatic metadata enforcement, generated current reference views, drift checks, link validation, and documentation CI as `REQUIRED FUTURE STANDARD` unless an existing tool already performs the exact behavior. REBASE-01 must not claim that such automation exists.

### `docs/platform/GLOSSARY.md`

Define controlled meanings for at least observational data, real market data, live provider connectivity, live execution transport, operationally accepted live execution, authorized live session, authorized individual order, broker acceptance/fill, reconciliation, replay, simulation, paper execution, signal, candidate, opportunity, prediction, evidence campaign, qualification, provider, capability, quality, risk authority, execution authority, release approval, truth class, document classification, implementation maturity, `PARTIAL`, and milestone disposition.

The unqualified term `LIVE` must not be used as a program-status value. Every use must identify the exact layer.

## Scoped canonical precedence

There is no single global ranking that applies to every question. Use the question's subject and time scope first.

| Question type | Controlling authority | Required interpretation |
|---|---|---|
| Current behavior, policy, gate, registry, or validation selection | Current executable schema/code/policy/gate/registry/manifest for the behavior it directly controls; then an accepted current hashed binding where applicable | Canonical prose references and explains; it cannot override or shadow values. |
| Current program explanation, maturity, navigation, or future ownership | Current `docs/platform/` document for its declared canonical subject, constrained by current executable and accepted evidence | A conflict with a controlling source is an error or explicit `UNRESOLVED`, never a prose override. |
| What happened or was accepted at a past milestone/cutoff | The immutable accepted BUILD/Phase/EVIDENCE artifact and its hashes for that subject/cutoff | Later prose may interpret or route to it but cannot rewrite what the artifact proves. |
| Approved future direction | The current canonical roadmap plus explicitly accepted design/spec for that future subject | Direction is not implementation, qualification, production eligibility, or authorization. |
| Operational procedure in a named environment | Current scoped runbook, constrained by executable gates and policy | A runbook cannot widen authority or bypass a gate. |

An old BUILD artifact does not control current implementation solely because it is historically authoritative. A current architecture document does not override what a frozen historical artifact proves occurred. Recency alone cannot override a frozen policy. Same-scope conflicts affecting safety or authority block acceptance; other unresolved conflicts may be recorded as `UNRESOLVED` with owner milestone and consequence.

## Executable-authority rules

For mutable executable subjects, every canonical document must reference rather than independently maintain:

- qualification thresholds and evidence-sufficiency logic;
- risk limits and decisions;
- provider capability/admission/entitlement state;
- quality enums and domain taxonomies;
- policy, model, dataset, feature-schema, and configuration identities;
- validation suites, domains, invariants, counts, and invalidators;
- prediction, settlement, execution, and release behavior;
- session authorization, order confirmation, kill-switch, reconciliation, and broker state.

If a value is necessary as a historical example, label its historical source and cutoff. If a current mutable value is needed, link to its source and avoid copying it. Generated reference views are future work unless already executable.

## System boundaries and safety invariants

The canonical layer must preserve these distinctions:

```text
real observational market data
!= live provider connectivity
!= live execution transport
!= operationally accepted live execution
!= authorized live session
!= authorized individual order
!= broker acceptance or fill
!= reconciliation
```

Current verified safety statements are:

- autonomous live trading is disabled;
- human live-session authorization is required;
- per-order human confirmation is required;
- automatic broker failover is disabled;
- real observational data is not live execution transport;
- prediction, qualification, research, narrative, hypotheses, model output, LLM output, and agent output do not grant order authority;
- release approval is not live-session authorization or order confirmation;
- broker acceptance/fill is external reality and must reconcile into canonical state.

The verified production-transport statement is precise: no production live broker transport exists in the current repository, and live-canary runners instantiate `MockBrokerTransport`. Broker abstractions, paper execution, mock transport, live-safety gates, session authorization, order confirmation, and reconciliation code do exist. Documentation must not shorten this to “no broker code exists.”

## Epistemic model

The detailed vocabulary and method in the `DATA_AND_EPISTEMIC_MODEL.md` contract are cross-cutting acceptance requirements, not an isolated documentation topic. Every canonical document that discusses facts, official explanations, alternative motives, narratives, hypotheses, or model outputs must preserve provenance and time, retain material contradiction, distinguish source assertion from direct observation, keep factual support separate from narrative reach/market impact, and deny analytic output any execution authority. No canonical document may reintroduce `REPORTED_FACT`, a scalar universal truth score, or a secret-true-motive field.

## Program-family maturity

The canonical status/architecture layer must represent:

| Family | Current assessment | Required explanation |
|---|---|---|
| BUILD01-35 core campaign | Historical disposition `FULL_SYSTEM_ACCEPTED_WITH_LIMITATIONS` for its recorded candidate | Does not prove current production readiness or autonomous trading approval. |
| Repository closure | Historical completion for its recorded source | Preserved and indexed; not the current roadmap endpoint. |
| Evidence maturation | `IN_PROGRESS`; EVIDENCE-01B implemented, EVIDENCE-01C next | Separate semantic track; no order authority. |
| Operating Fabric | `PARTIAL` | Reusable run manifests, schedulers, pipelines, ledgers, operations; missing universal run/operation/artifact authority; next owner `IMP-REBASE-02`, then `IMP-OF-01`. |
| Real-Time Opportunity Fabric | `PARTIAL` | Reusable callback/state/feature/routing/metrics foundations; missing end-to-end trace and accepted benchmark; next owner `IMP-RT-01` after standards/run identity. |
| Cross-Asset | `PARTIAL` | Reusable temporal/provenance/quality plus bounded macro/futures/energy/participant foundations; missing shared identity/relationship/source verticals; next owner `IMP-XA-01`. |
| Narrative/Motive | `PARTIAL` | Reusable event, participant, hypothesis, and bounded narrative features; missing canonical uncertain motive/thesis method and admitted runtime; later owner `IMP-NARRATIVE-01`. |
| AI/Agents | `PARTIAL` | Reusable read-only assistant and versioned fixture outputs; missing universal attribution, prompt/tool provenance, evaluation, workflow/approval lifecycle; next owner `IMP-AI-01`. |
| Production live broker transport | `ABSENT` | Separate future safety/qualification program; no authority is implied by REBASE work. |

## Roadmap and dependency semantics

Use these canonical milestone names:

| ID | Name |
|---|---|
| `IMP-REBASE-02` | Reproducibility, Observability, Evaluation & Operational Standards |
| `IMP-OF-01` | Append-Only Run and Artifact Ledger |
| `IMP-OF-02` | Operation Adapters |
| `IMP-RT-01` | End-to-End Instrumentation |
| `IMP-XA-01` | Cross-Asset Kernel |
| `IMP-OF-03` | Workflow and Control Registry |
| `IMP-AI-01` | Attributable Read-Only AI Research |
| `EVIDENCE-01C` | Bounded Real-Provider Shakedown and Operational Acceptance |

`IMP-REBASE-02` is one standards-design milestone because the listed subjects share cross-cutting identities and failure semantics. Its boundary is exact:

- define reproducibility, operation taxonomy, run/attempt/outcome/disposition semantics, artifact identity/linkage, data/model/config/code provenance, retry-history preservation, retention/redaction, structured logging, correlation/trace identity, evaluation/benchmark reproducibility, documentation validation expectations, and change/evidence workflow;
- reconcile requirements with existing `RunManifestV1`, validation reports, subsystem ledgers, and frozen records;
- do not implement the Universal Run Ledger, adapters, workflow registry, end-to-end tracing, or documentation automation.

The dependency graph is not a single sequence:

| From | To | Dependency type | Meaning |
|---|---|---|---|
| `IMP-REBASE-01` | `IMP-REBASE-02` | Hard | Current terminology and ownership precede program-wide standards. |
| `IMP-REBASE-02` | `IMP-OF-01` | Hard | Ledger implementation requires agreed run/artifact/attempt semantics. |
| `IMP-REBASE-02` | `IMP-RT-01` contract/design | Hard | Trace and benchmark implementation must use common correlation and reproducibility standards. |
| `IMP-REBASE-02` | `IMP-XA-01` contract preparation | Hard | Cross-asset contracts must use common provenance/evaluation/documentation standards. |
| `IMP-OF-01` | `IMP-OF-02` | Hard | Operation adapters need the ledger target. |
| `IMP-OF-01` | `IMP-RT-01` runtime integration | Later integration | Instrumented stages must attach to durable run/correlation identity; design work may begin earlier. |
| `IMP-OF-01` | `IMP-XA-02` admitted source runs | Later integration | The first admitted vertical must emit ledgered runs; XA-01 contract work may proceed earlier. |
| `IMP-OF-01` | `IMP-AI-01` | Hard | AI operations require durable attribution before expansion. |
| `IMP-OF-02` | `IMP-OF-03` | Per-operation hard dependency | Registry design may begin after `IMP-REBASE-02`, but an operation class cannot receive an accepted registry entry until its `IMP-OF-02` ledger adapter is demonstrated. Unrelated adapter classes do not block that entry. |
| `IMP-RT-01` | `IMP-RT-02` | Hard | Measure before optimizing. |
| `IMP-RT-02` | `IMP-RT-03` | Hard | Event-bus or native hot-path decisions require measured need. |
| `IMP-XA-01` | `IMP-XA-02` | Hard | Bounded admitted source work requires the shared extension/source template. |
| `IMP-OF-03` | `IMP-AI-02` | Hard | Governed workflow/tool/skill expansion requires the workflow/control registry. |

After `IMP-REBASE-02`, `IMP-OF-01` implementation, `IMP-RT-01` measurement-contract work, and `IMP-XA-01` contract preparation are parallel-safe where they do not cross the later-integration edges above.

`IMP-OF-01` requirements are capability-based, not speculative class names: durable run identity, append-only outcome/disposition, source/code/config/data attribution, artifact identity, parent-child relationships, and retry/attempt traceability. Do not freeze names such as `RunRecordV1` or `ArtifactManifestV1` in REBASE-01.

`IMP-RT-01` owns end-to-end trace semantics implementation, benchmark baselines, stage instrumentation, and provider/network versus internal latency separation. `IMP-REBASE-02` defines the common standards; `IMP-RT-01` measures against them. No optimization language may precede measurement.

`IMP-XA-01` establishes only shared canonical identity participation, temporal compatibility, provenance compatibility, quality compatibility, relationship extension requirements, a source-admission template, and one bounded sovereign/rates reference vertical. It must not create a universal financial ontology in REBASE-01.

`IMP-AI-01` is “read-only first” in an authority sense. It may read repository, admitted market-state, and research-source inputs within existing permissions and may create non-authoritative research artifacts plus audit evidence. It may not mutate canonical runtime/program state, policies, risk, execution, release, provider admission, prediction, settlement, or qualification state; submit orders; or promote its output without a separately governed human decision.

`IMP-OF-03` inherits the requirement to index technical debt, defects, incidents, and known limitations with origin evidence/run, severity, dependency, disposition, and resolution evidence/run. It need not force these concerns into one physical database if repository evidence supports separate registries with one navigational index.

## EVIDENCE isolation

EVIDENCE remains a parallel semantic program track. EVIDENCE-01C does not depend on `IMP-REBASE-02`, `IMP-OF-01`, `IMP-OF-02`, `IMP-RT-01`, `IMP-XA-01`, `IMP-OF-03`, `IMP-AI-01`, or any Narrative milestone. The master roadmap may show temporal parallelism and optional later integration, but it must not introduce a hard or soft dependency for EVIDENCE-01C.

REBASE-01 must not change:

- EVIDENCE-01 sufficiency policy or frozen thresholds;
- EVIDENCE-01A campaign origin, persistence, session, or qualification semantics;
- EVIDENCE-01B provider/runtime configuration, continuity, shakedown, settlement, or safety semantics;
- prediction-ledger, outcome-settlement, cohort, horizon, exclusion, observation, session, checkpoint, or source-manifest records.

EVIDENCE-01C remains the next bounded real-provider shakedown and operational-acceptance record. Its shakedown data remains excluded from qualification unless an independently accepted policy says otherwise.

## Repository entry-point changes

### `README.md`

Preserve useful onboarding, installation, local-run, safety, and developer workflow. Replace only stale program-level status/next-step prose with a compact current summary and links to the canonical program layer. Do not duplicate the master architecture, status matrix, or roadmap. Record `REQUIRES_LATER_RECONCILIATION` because this path is modified in the original worktree.

### `AGENTS.md`

Retain all existing validation and environment instructions. Add only actionable rules for repository-truth recovery, scoped precedence, anti-shadowing, historical integrity, EVIDENCE isolation, authority boundaries, dirty-tree preservation, clean-worktree use, and staged-diff inspection. Future systems must use conditional wording; for example, do not require run-ledger registration before `IMP-OF-01` exists.

### `docs/roadmap/REVISION_3_ROADMAP.md`

Add one clearly separated notice that current post-core planning lives in `docs/platform/MASTER_ROADMAP.md`. Do not change historical rows, projections, authorization language, effectivity wording, or existing links. Record `REQUIRES_LATER_RECONCILIATION` because this path is modified in the original worktree. This file is stale as the whole-program master but is mutable supporting material for this narrow navigational notice; it is not in the protected historical family.

Do not create `CONTRIBUTING.md` or a root `ROADMAP.md`.

## ADR decision

Create no ADR. Current repository ADRs bind accepted decisions to explicit principal approval and authority/effectivity records. REBASE-01 cannot manufacture that approval.

The new `docs/platform/` files receive current program-level explanatory authority only through their `CANONICAL` classification and the accepted, validated REBASE-01 milestone record. They do not alter the exact-hash Foundation specification authority in `manifests/phase0/canonical-authority.json` and do not receive executable authority. If governance later requires principal binding for this program layer, record that as a future governance action, not as completed REBASE-01 work.

## Worktree and Git isolation

Implementation must:

1. start from the written-spec review commit on `cloud/build-35-release-governance-operational-acceptance`;
2. create a new clean branch and dedicated worktree; do not reuse the observed `docs/imp-rebase-01` worktree/commit;
3. snapshot the original worktree's dirty path list before implementation;
4. stage only the exact allowed paths in the implementation contract;
5. use explicit `git add <path>` commands, never `git add .`;
6. preserve the original dirty worktree without reset, clean, stash, checkout-overwrite, merge, or file copying;
7. make one coherent implementation commit after validation;
8. not amend planning/review commits;
9. not push, merge, force-push, or modify `main` unless separately authorized.

If a clean worktree cannot be created without disturbing existing worktrees, stop with `IMP_REBASE_01_NOT_COMPLETE` and report the exact collision.

## Historical protection

Protected surfaces are derived from both the REBASE-00 inventory and its narrative do-not-touch decisions:

- every inventory row with `proposed_future_disposition = KEEP_IMMUTABLE_AND_INDEX`;
- `artifacts/imp-rebase/REBASE00/**`;
- accepted BUILD/Phase/EVIDENCE reports, manifests, hashes, frozen policies, validation evidence, known-limitations registers, and release candidates;
- repository-closure evidence and classification at its recorded source;
- EVIDENCE policy, code semantics, campaign records, observations, sessions, checkpoints, and configuration identities;
- prediction, settlement, qualification, risk, execution, live-safety, authorization, confirmation, reconciliation, deployment, and release-governance code/policies.

Before acceptance, mechanically compare the implementation-base commit with the final change set and prove zero protected-path modifications. The permitted roadmap notice is not a protected historical modification because REBASE-00 classifies that file `STALE`/`REQUIRES_RECONCILIATION` and explicitly directs supersession after canonical docs. No other historical document receives a navigational edit.

## Acceptance evidence

Create only:

```text
artifacts/imp-rebase/REBASE01/README.md
artifacts/imp-rebase/REBASE01/REBASE01_ACCEPTANCE_REPORT.md
artifacts/imp-rebase/REBASE01/REBASE01_KNOWN_LIMITATIONS.md
artifacts/imp-rebase/REBASE01/REBASE01_FILE_HASHES.json
```

The design's separate `REBASE01_DOCUMENT_MAP.md` and `REBASE01_MIGRATION_CHANGES.md` are merged into the acceptance report to avoid a parallel documentation tree.

The package contracts are:

- `README.md`: milestone scope, disposition, non-authority statement, and package navigation only;
- `REBASE01_ACCEPTANCE_REPORT.md`: implementation-base identity, intended branch and commit subject, full document map, exact path migration table, canonical consistency matrix, dirty-overlap reconciliation, protected-history result, validation attempt history, hash verification, Git disposition, acceptance criteria, and final milestone state;
- `REBASE01_KNOWN_LIMITATIONS.md`: two explicit sections, `Current program limitations documented by REBASE-01` and `Limitations of REBASE-01 execution`; program limitations do not automatically change the milestone completion state;
- `REBASE01_FILE_HASHES.json`: deterministic SHA-256 manifest of the accepted surface, excluding itself.

The hash manifest covers:

- `docs/platform/**`;
- the final implementation specification;
- `README.md`, `AGENTS.md`, and `docs/roadmap/REVISION_3_ROADMAP.md`;
- the three other REBASE-01 acceptance files.

Sort entries by repository-relative POSIX path and include path, byte length, and lowercase SHA-256. The manifest excludes itself to avoid recursion. This intentionally expands the REBASE-00 package-only hash convention so that one manifest binds the complete accepted REBASE-01 documentation surface.

The canonical consistency matrix is stored in `REBASE01_ACCEPTANCE_REPORT.md`, not as a separate generated file. It must cover BUILD status, closure, EVIDENCE status, authority boundaries, production broker transport, family maturity, truth classes, document classification, implementation maturity, milestone names, and dependency semantics, with source references and a consistent/inconsistent result.

## Validation

Run validation from the clean implementation worktree in this order. Record every attempt and exit code in the acceptance report.

1. **Allowed-path check.** Compare implementation-base to working/final state. Fail on any path outside the exact allowed list.
2. **Local link/path check.** Use a temporary, non-committed audit command or script to resolve local Markdown links from every new/modified Markdown file. Ignore external URLs; verify local paths and explicit fragments where practical. There is no existing repository link checker, so do not add a permanent validator in REBASE-01.
3. **JSON parse and hash-schema check.** Parse every new JSON file and confirm the manifest's path, byte length, SHA-256, sorted order, uniqueness, coverage, and self-exclusion.
4. **Canonical consistency check.** Review the single stored matrix and search the accepted surface for contradictory use of BUILD/EVIDENCE status, `LIVE`, `PARTIAL`, authority, broker transport, truth class, document classification, maturity, and milestone names.
5. **Protected-history check.** Derive protected paths from REBASE-00 plus the explicit list above and prove zero protected modifications.
6. **Whitespace check.** Resolve the review-complete SHA into the task-specific PowerShell variable `$rebase01ImplementationBase`, then run `git diff --check $rebase01ImplementationBase --` before staging and `git diff --cached --check` after staging.
7. **Repository changed validation.** Run:

   ```powershell
   $env:PYTHONPATH='src'
   .venv\Scripts\python.exe tools\validate.py changed --explain
   ```

   For the final staged surface, all intended changes are documentation or acceptance JSON. If the mixed Markdown/JSON selection is not documentation-only, record the exact selected checks. Inspect the result's `full_suite_required` field. Run `.venv\Scripts\python.exe tools\validate.py full` only when that field is true or another repository policy explicitly requires FULL. No live suite is warranted.

8. **Staged-diff inspection.** Inspect `git status --short`, `git diff --cached --name-status`, `git diff --cached --stat`, `git diff --cached`, and `git diff --cached --check` before commit.
9. **Post-commit verification.** Verify the commit's exact path list, protected-path count, parent, subject, worktree cleanliness, and hash manifest against committed bytes. Report the final commit SHA in the external execution report; do not place it inside a file contained by that same commit.

Documentation-only `validate.py changed` currently performs an encoding/readability cheap check and no test workers. Acceptance must report that scope accurately; it must not call zero runtime tests a full regression pass.

## Failure handling

Preserve a failed attempt and its successful retry as two distinct acceptance-report rows. Classify a failure only when evidence supports one of:

- `TEST_FAILURE`;
- `ENVIRONMENT_FAILURE`;
- `VALIDATOR_DEFECT`;
- `FLAKY_FAILURE`;
- `UNCLASSIFIED_FAILURE`.

Do not infer a cause merely because a retry passed.

Hard acceptance blockers are:

- any runtime, policy, schema, provider, EVIDENCE, prediction, settlement, qualification, risk, execution, or release semantic change;
- any protected historical modification or hash corruption;
- any material false current-status claim;
- any safety/authority ambiguity or unresolved high-risk canonical ownership conflict;
- any broken critical local reference from the canonical layer to a controlling source;
- a missing or invalid accepted-surface hash entry;
- inability to isolate unrelated work;
- staged paths outside the allowed list;
- required validation failure.

A non-safety same-level conflict may remain only when `CANONICAL_TRUTH_MAP.md` records `UNRESOLVED`, explains its consequence, and assigns a future owning milestone. Minor wording uncertainty, optional external-link reachability, or a documented nonblocking governance follow-up may be a REBASE-01 acceptance limitation rather than a blocker.

## Acceptance criteria

IMP-REBASE-01 is accepted only when all are true:

1. All ten canonical documents exist and satisfy their separate contracts.
2. Current implementation, historical truth, and approved future design are visibly distinct.
3. Truth class, document classification, implementation maturity, family consolidation, and milestone disposition are not conflated.
4. Every `PARTIAL` family names reusable foundations, missing primitives, and its next owner.
5. Mutable executable subjects are linked, not shadowed in prose.
6. Live-readiness layers and broker-transport reality are stated precisely.
7. System composition, responsibility boundaries, and decision authority are non-duplicative and mutually consistent.
8. Epistemic roles use `REPORTED_CLAIM`, keep factual support separate from narrative market power, and require competing motive hypotheses where material.
9. The roadmap distinguishes hard, soft, parallel-safe, and later-integration dependencies.
10. EVIDENCE-01C remains semantically independent from REBASE/OF/RT/XA/AI milestones.
11. Root navigation preserves onboarding and does not become a second source of program truth.
12. No ADR or principal authorization is manufactured.
13. Zero protected historical paths change.
14. Dirty original state is preserved, and `README.md` plus the Revision 3 roadmap are marked for later reconciliation.
15. The four-file acceptance package contains the document map, migration record, consistency matrix, attempt history, separated limitations, and complete accepted-surface hashes.
16. All critical local links, JSON, hashes, consistency checks, whitespace checks, and applicable repository validation pass.
17. The implementation commit contains only the exact allowed paths and has the review-complete HEAD as its ancestor.

Use `IMP_REBASE_01_COMPLETE` when every criterion passes and no limitation belongs to REBASE-01 execution itself. Use `IMP_REBASE_01_COMPLETE_WITH_LIMITATIONS` only when every hard criterion passes but the canonicalization milestone retains a genuine, explicitly recorded nonblocking limitation. Use `IMP_REBASE_01_NOT_COMPLETE` when any hard blocker remains.

## Implementation handoff

### Exact files to create

```text
docs/platform/README.md
docs/platform/MASTER_ARCHITECTURE.md
docs/platform/PROGRAM_STATUS.md
docs/platform/MASTER_ROADMAP.md
docs/platform/CANONICAL_TRUTH_MAP.md
docs/platform/SYSTEM_BOUNDARIES.md
docs/platform/AUTHORITY_MODEL.md
docs/platform/DATA_AND_EPISTEMIC_MODEL.md
docs/platform/DOCUMENTATION_STANDARD.md
docs/platform/GLOSSARY.md
artifacts/imp-rebase/REBASE01/README.md
artifacts/imp-rebase/REBASE01/REBASE01_ACCEPTANCE_REPORT.md
artifacts/imp-rebase/REBASE01/REBASE01_KNOWN_LIMITATIONS.md
artifacts/imp-rebase/REBASE01/REBASE01_FILE_HASHES.json
```

### Exact existing files allowed to modify

```text
README.md
AGENTS.md
docs/roadmap/REVISION_3_ROADMAP.md
```

No other path is allowed. The approved design and this final specification remain unchanged during implementation.

### Required implementation behavior

- Recover review-complete HEAD and create a new clean worktree from it.
- Use this specification as the only architecture contract.
- Ground every current claim in the controlling repository source.
- Keep canonical prose concise and route mutable details to executable sources.
- Preserve all unrelated and protected state.
- Generate the hash manifest only after all covered content is frozen; regenerate it after any covered-byte change.
- Record exact validation attempts, including failures and retries.
- Stage explicit paths only and make one documentation-only implementation commit.
- Do not push or merge.

### Forbidden implementation behavior

- Reusing or accepting `6d36503` as the implementation base.
- Copying policy values, thresholds, provider matrices, model versions, or validation counts into current prose.
- Treating historical evidence as current runtime control or current prose as historical evidence replacement.
- Introducing runtime/schema/provider/safety/authority changes.
- Editing protected historical artifacts.
- Silently reconciling the original dirty `README.md` or roadmap edits.
- Creating extra canonical, acceptance, ADR, migration, or validation files.
- Claiming documentation automation, production broker transport, qualification, production eligibility, or autonomous authority that does not exist.

### Completion definition

Implementation is complete only when the exact file contract is satisfied, the acceptance criteria pass, the acceptance package binds the committed documentation surface, protected modifications equal zero, the original dirty worktree remains preserved, and the final implementation commit is reported without push or merge.

Until then, the only approved state is:

```text
IMP_REBASE_01_SPEC_APPROVED_FOR_IMPLEMENTATION
```
