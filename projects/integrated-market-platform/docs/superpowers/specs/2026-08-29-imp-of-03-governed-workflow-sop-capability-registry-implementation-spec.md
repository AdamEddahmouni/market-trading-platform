# IMP-OF-03 — Governed Workflow, SOP & Capability Registry

| Field | Value |
|---|---|
| Document ID | `IMP-OF-03-IMPLEMENTATION-SPEC` |
| Status | `NORMATIVE_IMPLEMENTATION` |
| Date | `2026-08-29` |
| Canonical baseline | `58985ee74d3c5ee634cfe4048355fe30c5f6f2e3` (`IMP_OF_02_COMPLETE_WITH_LIMITATIONS`) |
| System | `IMP-OF-03` |

## Purpose

OF-03 is the machine-readable operating control plane that **registers, validates, discovers, and governs** capabilities, SOPs, and workflows. It answers what exists, which implementation backs it, which procedure governs it, which evidence and authority are required, and which automation/human rules apply.

It is not an execution engine, not a second ledger, and not a source of trading, model, risk, or live-order authority.

## Canonical baseline

- OF-01 runtime: `36cf53b` lineage, invariants 1–75 unchanged.
- VALIDATION-01: `b3e58b0`.
- OF-02 attribution adapters: `58985ee`.
- REBASE-02 standards remain semantic contracts.
- Executable repository truth outranks this spec if they conflict after implementation; this spec must then be corrected.

## Scope

- Versioned JSON registries for capabilities, SOPs, and workflows.
- Deterministic definition hashes and a registry snapshot hash.
- Explicit active-version pointers (no implicit latest).
- Binding verification without invoking destructive or live behavior.
- Runtime availability inspection separate from definition identity.
- Cross-registry integrity, document/binding drift checks.
- Typed OF-01 provenance reference helpers.
- Operator inspection capabilities `OF03.OP.*`.
- Operations pack and agent rules.
- Initial population from existing OF-01/OF-02 IDs and evidenced platform operations.

## Out of scope

- Generic `execute-workflow` / DAG runtime / scheduler / worker pool / job queue.
- Independent workflow-run or SOP-execution history (OF-01 remains history authority).
- Granting or satisfying required authority.
- Rewriting OF-01/OF-02/EVIDENCE/risk/execution/promotion/adaptation semantics.
- Arbitrary expression DSLs, shell-string bindings, untrusted imports.
- Mass-wiring every OF-02 adapter to workflows.

## Audit findings

Existing stable IDs (do not reinvent):

| Family | Count | Source |
|---|---:|---|
| `OF01.OP.*` | 29 | `of01/operations.py` (`CAPABILITY_IDS`) |
| `OF02.OP.*` | 8 | `of02/operations.py` |
| `SOP-OF01-*` | 18 | `docs/operations/of-01/SOPS.md` |
| `SOP-OF02-*` | 8 | `docs/operations/of-02/SOPS.md` |
| `WF-OF01-*` | 18 | `docs/operations/of-01/WORKFLOWS.md` |
| `WF-OF02-*` | 3 | `docs/operations/of-02/WORKFLOWS.md` |
| OF-02 adapter IDs | 10 | `of02/config.py` `ADAPTER_IDS` |

Classification used for initial population:

- `REGISTER_REQUIRED`: all `OF01.OP.*`, `OF02.OP.*`, OF-01/OF-02 SOPs/workflows, OF-03 operator capabilities/SOPs/admin workflows, OF-02 adapter attribution surfaces, `tools/validate.py` validation run.
- `REGISTER_REFERENCE_ONLY`: BUILD 18 `TrainingFactory`, BUILD 20 `PromotionEngine`, BUILD 24 `AdaptationEngine` — describe existing engines; do not become those authorities.
- `DEFER`: BUILD 21–23 engines without a stable OF operator ID; Phase-0 `registry.py` adapter IDs (unrelated).
- `DO_NOT_REGISTER`: live order submission, broker transport, risk override as executable OF-03 capabilities.
- Implemented OF-01 ops today: `STATUS`, `LEDGER_METADATA`, `INTEGRITY_QUICK`, `SHUTDOWN`. Remaining `OF01.OP.*` are declared stubs → `UNBOUND`.
- OF-01 document pack status `NORMATIVE_RUNTIME_DRAFT` → SOP maturity `DRAFT`. Do not upgrade to `EXERCISED`/`ACCEPTED`.
- OF-02 native attribution default-disabled; one canonical domain identity promotion remains an OF-02 limitation. OF-03 definitions use `domain_reference_requirements[]` (zero/one/many). No OF-02 hardening required for OF-03 v1.

## Identity model

```text
capability_id ≠ definition_version ≠ definition_hash ≠ binding ≠ availability
sop_id ≠ sop_version ≠ sop_definition_hash ≠ procedure text
workflow_id ≠ workflow_version ≠ workflow_definition_hash ≠ OF run_id
registry_snapshot_hash ≠ OF commit_hash ≠ Git commit
```

Human-auditable IDs. No UUID replacement of existing operator/SOP/workflow IDs.

## Version model

- Integer `definition_version` starting at `1`.
- Same ID + version + different semantic content → integrity ERROR.
- Semantic change requires a new version; old versions remain resolvable.
- Deprecated ≠ deleted.
- Active version is only the explicit manifest pointer, never semver/lexical latest.
- Historical OF records must store exact version + definition hash + snapshot hash.

## Capability schema

Required fields:

`schema_version`, `capability_id`, `definition_version`, `title`, `description`, `owner_subsystem`, `consequence_profile` (OF-01 `ConsequenceProfile`), `effect_class`, `binding`, `input_contract_ref`, `output_contract_ref`, `required_authority_refs`, `required_role_refs`, `automation_policy`, `human_approval_policy`, `idempotency_class`, `retry_class`, `of_attribution_requirement`, `required_evidence_classes`, `feature_gates`, `sop_refs`, `domain_reference_requirements`, `deprecation`, `registration_state`.

`definition_hash` is computed at load (not an identity field operators edit).

### Effect class

`READ_ONLY | OBSERVATIONAL | NON_DESTRUCTIVE_MUTATION | AUTHORITATIVE_MUTATION | DESTRUCTIVE_MAINTENANCE | EXTERNAL_SIDE_EFFECT`

Distinct from consequence profile.

### Automation policy

`AUTOMATION_ALLOWED | AUTOMATION_ALLOWED_WITH_GUARD | HUMAN_APPROVAL_REQUIRED | AGENT_PROHIBITED`

Descriptive only. `HUMAN_APPROVAL_REQUIRED` cannot coexist with `AUTOMATION_ALLOWED`.

### Human approval

`NOT_REQUIRED | REQUIRED`

### Binding model

`binding_kind`: `PYTHON_API | CLI_CAPABILITY | DOCUMENTED_MANUAL_OPERATION | UNBOUND`

Python: `module` + `qualname` under `market_platform_foundation.*` only.

CLI: `cli_module` + `cli_subcommand` + `cli_parser_attr` **or** allowlisted `cli_script` relative to repository root (`tools/validate.py` only in v1).

Forbidden: shell strings, dynamic expressions, path traversal, imports outside the foundation package.

### Availability model (runtime, not definition)

`UNBOUND | BOUND | AVAILABLE | DISABLED | UNAVAILABLE | DEPRECATED`

Registration does not imply available. Feature flags and provider presence do not change definition hashes.

## SOP schema

Machine metadata only. Normative procedure text remains in `docs/operations/<subsystem>/SOPS.md`.

Fields: `sop_id`, `definition_version`, `title`, `owner_subsystem`, `document_path`, `document_anchor`, `consequence_profile`, `required_authority_refs`, `automation_policy`, `related_capability_refs`, `related_workflow_refs`, `prerequisites`, `required_evidence_classes`, `maturity`, `deprecation`.

Maturity: `DRAFT | NORMATIVE | BOUND`. `EXERCISED`/`ACCEPTED` are not used in v1 (no operational exercise evidence authority).

Document integrity: path exists; heading `## {sop_id}` exists exactly once; whitespace-normalized section hash is a drift pin, excluded from definition hash.

## Workflow schema

Fields: `workflow_id`, `definition_version`, `title`, `objective`, `owner_subsystem`, `consequence_profile`, `initiator_class`, `required_authority_refs`, `required_role_refs`, `required_inputs`, `domain_reference_requirements`, `required_evidence_classes`, `failure_policy`, `retry_policy`, `terminal_dispositions`, `sop_refs`, `capability_refs`, `of_attribution_requirement`, `automation_policy`, `human_approval_policy`, `document_path`, `document_anchor`, `deprecation`, `entry_step_id`, `steps`.

A workflow definition is not an OF run.

## Workflow graph semantics

Acyclic directed step graph. Step kinds: `CAPABILITY | SOP | GATE | PROCEDURE | TERMINAL`.

Gates (finite typed, no eval/Jinja/SQL): `AUTHORITY | HUMAN_APPROVAL | EVIDENCE_PREREQUISITE | CAPABILITY_AVAILABILITY | INPUT_SCHEMA`.

Retry is per-step policy, not a graph cycle. Cycles, missing terminals, unreachable nodes, and dangling `next` refs are ERROR.

## Gate semantics

Declared requirements only. OF-03 does not satisfy authority, produce evidence, or enable capabilities.

## Retry semantics

`retry_kind`: `NONE | SAME_IDENTITY | FRESH_ATTEMPT | UNKNOWN`. Graph loops are invalid.

## Definition hashes

Profile `imp-of03-definition-canonical-json-v1`. Canonical JSON via foundation `canonical_bytes` (sorted keys, compact separators, trailing newline) and `imp-sha256-uppercase-hex-v1`. Floats prohibited. Hash input excludes `definition_hash` and document drift pins.

## Registry snapshot

Profile `imp-of03-registry-snapshot-canonical-json-v1`. Binds schema version, all definitions (sorted by id, version), and active-version maps. `registry_snapshot_hash` is a configuration content ID, not OF-01 `semantic_content_hash`.

Same logical registry → same hash. Enumeration/key order must not affect hash. Semantic or active-pointer changes must.

## Active-version semantics

`config/of03/manifest.json` maps id → version. Pointer to missing id/version is ERROR. `resolve(id)` without version is forbidden except via explicit `active_*` APIs.

## Deprecation

`deprecated: bool`, `superseded_by: {kind, id, version} | null`. Deprecated definitions remain resolvable. Active pointer to deprecated is WARNING. Replacement must exist.

## Authority references

Closed vocabulary in `of03/authorities.py`. Unknown ref → ERROR. Registry membership never yields an authorization object. `authorize_execution_from_registry` always fails closed.

## Automation / human approval

Policy metadata is queryable. Agent invocation of destructive/`AGENT_PROHIBITED` capabilities is rejected by `evaluate_agent_use`. There is no runtime registry mutation API.

## Cross-registry validation

ERROR: duplicate id/version, hash mismatch, unknown required refs, invalid enums, invalid binding, missing docs/anchors, cycles, unreachable steps, missing terminal, invalid active pointer, schema incompatibility, `AUTOMATION_ALLOWED`+`HUMAN_APPROVAL_REQUIRED`, untrusted binding.

WARNING: unbound optional capabilities, deprecated active use, document section drift, feature-disabled bound capability.

INFO: deprecated non-active definitions.

## OF-01 provenance references

Helpers emit:

```text
capability_id, definition_version, definition_hash, registry_snapshot_hash
workflow_id, workflow_version, workflow_definition_hash, registry_snapshot_hash
```

These attach to OF-01 extras / OF-02 `AttributionRequest.extra`. No second ledger.

## Storage / layout

Canonical owner: version-controlled JSON under `config/of03/` (`manifest.json`, `capabilities.json`, `sops.json`, `workflows.json`). Runtime: `src/market_platform_foundation/of03/`. SOP/workflow prose: `docs/operations/`. History: OF-01.

Mutation: edit JSON → validate → test → review → commit. No unaudited write endpoint.

## Loader

Strict JSON (duplicate keys rejected). Fail closed on structural corruption. Do not drop malformed definitions.

## Reader / query API

`LoadedRegistry`: get by exact id+version; list; active lookup; snapshot hash; status; binding verification; drift; agent policy description.

## Status

Structured counts: schema, snapshot hash, definition counts, active/deprecated, bound/unbound/available/disabled/unavailable, errors, warnings, drift.

## Operator capabilities

`OF03.OP.STATUS`, `VALIDATE`, `LIST_CAPABILITIES`, `LIST_SOPS`, `LIST_WORKFLOWS`, `SHOW_DEFINITION`, `SNAPSHOT`, `VERIFY_BINDINGS`, `CHECK_DRIFT`.

CLI: `python -m market_platform_foundation.of03 <verb> --json`. No `EXECUTE_WORKFLOW`.

## Operations / agent rules

See `docs/operations/of-03/`. Agents MUST NOT self-register, loosen policy, treat registration as authorization, invoke untrusted bindings, select implicit latest, rewrite history, fabricate missing definitions, or execute destructive capabilities because they are listed.

## Testing

Parsing, hashes, snapshot determinism, active versions, deprecation, graphs, bindings/security, authority negatives, SOP docs, historical resolution, CLI JSON, OF-01 attribution of a registry snapshot, no domain execution during verify.

## Fault injection

Corrupt JSON, duplicate identity, cycle, missing terminal, path traversal module, shell binding, unknown authority, maturity `EXERCISED` (rejected), pinned hash mismatch.

## Acceptance

`IMP_OF_03_COMPLETE` or `IMP_OF_03_COMPLETE_WITH_LIMITATIONS` after full offline validation with 0 failures / 0 errors. Absence of a generic executor is a boundary, not a limitation.

## Implementation stages

Vertical slice (one capability → load → validate → bind verify → status → hashes → snapshot → query), then SOP/workflow families, then full OF-01/OF-02/platform population, operator CLI, ops pack, registration, acceptance.
