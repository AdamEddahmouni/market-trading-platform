# Documentation Authority and Migration

## Inventory

`REBASE00_DOCUMENTATION_INVENTORY.json` enumerates 621 Markdown/JSON/YAML/TOML documentation and evidence surfaces under root documentation files, `docs/`, `artifacts/`, `manifests/`, and `.github/workflows/`.

The whole-surface heuristic counts are: 149 `ACTIVE_SUPPORTING`, 2 `CANONICAL`, 100 `EXPERIMENTAL`, 144 `GENERATED`, 118 `HISTORICAL`, 104 `REFERENCE`, 2 `RUNBOOK`, and 2 `STALE`. `SUPERSEDED`, `DUPLICATIVE`, and `UNKNOWN` are zero at whole-file level because supersession and duplication are usually claim-level relationships; the consequential cases are listed below. JSON artifact runbooks remain `GENERATED` in the inventory and are separately recognized as runbooks here.

This is a navigation inventory, not automatic authority. Its heuristic classifications must not override the reviewed decisions in this package.

## Proposed precedence

`PROPOSED`, highest to lowest:

1. Executable schemas, policies, gates, registries, and validation manifests for the behavior they directly control.
2. Accepted signed/hashed authority manifests and current explicitly scoped policies.
3. Current canonical master architecture/status documents created by REBASE-01.
4. Active supporting engineering/provider documentation verified against code.
5. Runbooks and operational references, scoped to their runtime and environment.
6. Experimental designs and research proposals.
7. Immutable historical BUILD/Phase/EVIDENCE artifacts, authoritative only for their original subject/cutoff.

When sources at the same level conflict, status is `UNKNOWN` until resolved; recency alone does not override a frozen contract.

## Drift and migration matrix

| Current surface/family | Current class | Alignment | Future disposition | Change risk |
|---|---|---|---|---|
| `README.md` status/roadmap sections | `STALE` | Materially behind Git lineage | Rewrite status layer after REBASE-01; retain useful onboarding/safety content | Medium; baseline user edits exist |
| `docs/roadmap/REVISION_3_ROADMAP.md` | `STALE` as program master | Useful historical/track detail, not post-EVIDENCE master status | Supersede with generated/current roadmap and retain historical copy | Medium; baseline user edits exist |
| `docs/engineering/POST_BUILD35_REPOSITORY_CLOSURE_AUDIT.md` | `HISTORICAL` + supporting | Correct for closure subject | Keep immutable; link from history index | High |
| `artifacts/repository-closure/**` | `GENERATED/HISTORICAL` | Accepted closure evidence | Keep immutable and indexed | High |
| `docs/engineering/EVIDENCE_01*.md` | `ACTIVE_SUPPORTING` | Matches implemented policies at audit | Keep isolated; bind to exact policy/artifact refs | Critical |
| `artifacts/forward-qualification/**` | `GENERATED/HISTORICAL` | Mixed BUILD26 and EVIDENCE cutoffs | Keep immutable; index by campaign and cutoff | Critical |
| BUILD25–35 artifact families | `GENERATED/HISTORICAL` | Strong accepted milestone truth | Keep immutable; never rewrite into current truth | Critical |
| `docs/engineering/*_V1.md` | `ACTIVE_SUPPORTING` or historical by subject | Often strong, but fragmented | Merge references into master docs; executable values remain in code | High for authority docs |
| `docs/providers/**` | `REFERENCE` | Generally candid and provider-specific | Keep; link from generated capability registry | High for entitlement/admission claims |
| `docs/architecture/**` | `EXPERIMENTAL` | Primarily future research/design | Keep as proposals; label non-authoritative | Medium |
| `docs/research/**` | `EXPERIMENTAL` | Research track material | Keep with hypothesis/experiment lineage; do not present as platform truth | Low–medium |
| `docs/superpowers/plans/**` | `HISTORICAL` | Implementation planning record | Retain, exclude from current architecture navigation | Low |
| `docs/superpowers/specs/**` | `ACTIVE_SUPPORTING/EXPERIMENTAL` | Mixed implemented and proposed status | Add explicit lifecycle metadata; merge only accepted content | Medium |
| `docs/superpowers/decisions/**` and ADRs | `ACTIVE_SUPPORTING` | Useful but fragmented ADR practice | Index into one ADR register without renumbering history | High |
| Validation reports under `reports/` | `GENERATED/HISTORICAL` | Exact for a past invocation | Index by source/run; never use as current count | High |

## Claim-level duplication/supersession

- BUILD26 provider eligibility is superseded for current operations by later provider implementations and EVIDENCE-01B, but remains immutable qualification history.
- BUILD33's fixture pilot provider matrix is scenario-scoped, not a global provider registry.
- README program phase statements are superseded by closure/EVIDENCE Git history.
- Experimental architecture documents describe desired crypto, prediction-market, influence, cross-venue, and other domains that do not yet exist as admitted production subsystems.
- Repeated policy thresholds, provider state, model versions, and validation counts should become generated references to executable sources.

## Proposed master documentation decisions

| Proposed document | Decision | Reason |
|---|---|---|
| `README.md` | `RENAME` its role to entry point, not master truth | Current file mixes onboarding, history, status, and roadmap |
| `PROGRAM_STATUS.md` | `KEEP` | Missing canonical post-EVIDENCE status is the largest drift |
| `ARCHITECTURE.md` | `KEEP` | Needed as the concise whole-program map to executable authorities |
| `AUTHORITY_MODEL.md` | `KEEP` | Authority separation is mature but scattered and safety-critical |
| `DATA_AND_EPISTEMIC_MODEL.md` | `KEEP` | Unifies evidence classes, admission, provenance, models, and uncertainty |
| `TEMPORAL_INTEGRITY.md` | `MERGE` with existing V1 doc | Existing kernel is strong; promote/extend instead of duplicate |
| `CROSS_ASSET_ARCHITECTURE.md` | `DEFER` until kernel milestone | Current support is bounded and domain-specific |
| `REALTIME_ARCHITECTURE.md` | `KEEP` after instrumentation design | Needed to separate callback, polling, state, and latency truth |
| `AI_AND_AGENT_ARCHITECTURE.md` | `KEEP` | Existing assistant/fixture LLM paths need one boundary/provenance standard |
| `EVIDENCE_ARCHITECTURE.md` | `MERGE` current EVIDENCE docs via index | Do not rewrite frozen contracts during active campaign |
| `OPERATING_FABRIC.md` | `KEEP` | Missing program-wide operation/run/workflow model |
| `AUTOMATION_MODEL.md` | `MERGE` into Operating Fabric initially | No separate automation authority yet |
| `DOCUMENTATION_STANDARD.md` | `KEEP` | Needed to enforce status, precedence, generated references, and lifecycle |
| `REPRODUCIBILITY_STANDARD.md` | `KEEP` | Universal run attribution is absent |
| `OBSERVABILITY_STANDARD.md` | `KEEP` | Existing telemetry is live-ops scoped, not program-wide |
| `TEST_AND_EVALUATION_STANDARD.md` | `MERGE` validation architecture + model/evidence evaluation | One evaluation family with domain sections avoids duplication |
| `DEVELOPMENT_WORKFLOW.md` | `KEEP` | Current instructions describe commands but not full change/evidence lifecycle |
| `GLOSSARY.md` | `KEEP` | Terminology conflict around authority/status requires controlled meanings |

## Required lifecycle metadata

`PROPOSED` Every future canonical/supporting document should declare: document ID, status (`CURRENT`, `HISTORICAL`, `PROPOSED`, `SUPERSEDED`), scope, owner, effective source SHA, executable authorities referenced, predecessors/successors, last verification date, and generated/reference-only fields. The metadata must not retroactively alter historical artifacts.
