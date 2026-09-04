# IMP-OF-02 Existing-System Run & Artifact Attribution Adapters — Implementation Specification

| Field | Value |
|---|---|
| Document ID | `IMP-OF-02-SPEC` |
| Classification | `ACTIVE_SUPPORTING` |
| Truth class | `APPROVED_FUTURE_DESIGN` |
| Review state | `APPROVED_FOR_IMPLEMENTATION` |
| Version | `1.0` |
| Last verified | `2026-08-28` |
| Establishing milestone | `IMP-OF-02` |
| Canonical base | `b3e58b064dfa98ecc636e5ae45cea150d3c8bf4d` |
| OF-01 runtime | `36cf53b60cfdf1ea48d19312fef1918573ba3375` |
| OF-01 historical status | `IMP_OF_01_COMPLETE_WITH_LIMITATIONS` |

This specification is the controlling implementation authority for IMP-OF-02.
Executable repository truth and the accepted OF-01 implementation specification
outrank this document if they conflict. Existing subsystem authorities remain
authoritative for their domain semantics.

## Purpose

Connect existing IMP subsystems to the OF-01 ledger so consequential work is
attributable through run, attempt, outcome, validity, disposition, artifact,
relationship, and provenance records **without** rewriting those subsystems
around OF-01, changing domain meaning, or fabricating historical provenance.

```text
existing subsystem
       ↓
OF-02 adapter
       ↓
typed OF-01 command
       ↓
AuthoritativeLedgerWriter
       ↓
OF-01
```

## Baseline and precedence

1. Current repository/executable truth
2. Approved OF-01 implementation specification and runtime
3. REBASE-02 canonical standards
4. Existing subsystem authorities
5. Canonical platform architecture/status/roadmap
6. This specification
7. The OF-02 execution prompt

OF-02 starts from VALIDATION-01 (`b3e58b0`), not from OF-01 runtime alone
(`36cf53b`) and not from `1e967613`.

## Scope

- one common attribution contract and ledger gateway
- native adapters for first-wave existing systems that actually exist
- retrospective indexing with dry-run, resume, and conflict handling
- `NATIVE` / `RETROSPECTIVE_INDEX` / `LEGACY_PARTIAL` provenance (OF-01 names)
- consequence-class attribution failure policy
- temporal integrity (no backdated `recorded_at`, no future-information leakage)
- operations pack, CLI/status, tests, validation/closure registration, acceptance

## Out of scope

- workflow/SOP/capability registries and orchestration engines (OF-03)
- a second durable pre-commit command inbox
- direct SQLite or CAS mutation outside OF-01 contracts
- Mongo as authority
- EVIDENCE semantic change, campaign rewrite, or fabricated historical OF IDs
- ADAPT-specific records or autonomous model mutation
- new risk, broker, live-session, or promotion authority
- replacing existing domain IDs with OF IDs

## Target matrix

| Subsystem | Existing authority | Entry point | Existing IDs | Existing artifacts | Native | Retrospective | Consequence | Decision |
|---|---|---|---|---|---:|---:|---|---|
| Validation | `tools/validate.py`, manifest | `main` / `execute_selection` | suite IDs, report schema | `reports/*.json` | Yes | Yes | C1 local / C3 when acceptance-bound | `OF02_REQUIRED` |
| Benchmark | `tools/benchmark.py` | `run_benchmarks` | informational report | `--output` JSON | Yes when material | Sparse | C2 informational | `OF02_REQUIRED` |
| Provider smoke | `tools/moomoo`, `tools/ibkr`, live suites | smoke/preflight/probe | capability reports | `evidence/market_data/**` | Observational only | Yes | C2 | `OF02_REQUIRED` |
| Research | decision-research + experiment cards | gate/experiment services | `experiment_id`, DEC-* | `evidence/research/**` | Yes for gated work | Yes | C2 | `OF02_REQUIRED` |
| Dataset/training | BUILD 18 factory | `TrainingFactory` manifests | dataset/candidate IDs | training artifacts | Yes | Partial | C2 | `OF02_REQUIRED` |
| Model evaluation | BUILD 16/19 eval/validation | evaluation/validation services | plan/report IDs | eval reports | Yes | Yes | C2 | `OF02_REQUIRED` |
| Promotion | BUILD 20 promotion engine | `PromotionEngine` | decision/eligibility IDs | promotion JSON | Attribution only | Yes | C3 | `OF02_REQUIRED` |
| Drift / controlled adaptation | BUILD 24 adaptation engine | `AdaptationEngine` | assessment/trigger IDs | adaptation events | Evidence only | Limited | C2 | `OF02_REQUIRED` |
| Operational drills | OF-01 backup/restore; BUILD 34 CC | backup/restore/change-control | backup_id, REL-* | backup manifests | Yes | Yes | C2/C3 | `OF02_REQUIRED` |
| Informal scratch / stdout-only benchmark | none governed | ad-hoc | none | none | No | No | C0/C1 | `DEFER` — not consequential until cited or `--output` |
| Hot-path inference / per-tick replay | spans inside parent | runtime | none | none | No | No | C0 | `DEFER` — not a run |
| Prediction / settlement / qualification | own ledgers + EVIDENCE | prediction/settlement/FQ | forecast/campaign IDs | frozen artifacts | No | Index only | n/a | `DO_NOT_ADAPT` domain; `RETROSPECTIVE_ONLY` index |
| EVIDENCE campaign records | EVIDENCE-01* | campaign tools | campaign IDs | frozen evidence | No | Cite/index only | n/a | `DO_NOT_ADAPT` |
| Live broker / risk / order authority | live-safety / risk | execution gates | session/order IDs | canary evidence | No | No | C4 | `DO_NOT_ADAPT` |
| Auto-recalibrate production | none authorized | none | n/a | n/a | No | No | n/a | `DO_NOT_ADAPT` |

### DEFER / DO_NOT_ADAPT explanations

- **DEFER informal scratch / stdout-only benchmarks:** not consequential under REBASE-02 until cited or a material report is produced.
- **DEFER hot-path inference:** standards treat these as spans inside a parent run.
- **DO_NOT_ADAPT prediction/settlement/qualification semantics:** independent authorities; OF-02 may index frozen artifacts, never rewrite them.
- **DO_NOT_ADAPT EVIDENCE:** isolation is non-negotiable; no fabricated historical OF IDs.
- **DO_NOT_ADAPT live broker/risk/order:** C4 safety program; observational smoke ≠ execution transport.
- **DO_NOT_ADAPT auto-recalibration:** BUILD 24 emits research triggers only.

## Adapter architecture

Package: `src/market_platform_foundation/of02/`.

Adapters observe domain results and emit typed OF-01 commands. They MUST NOT
write SQLite tables, choose CAS object paths, or treat Mongo as authority.

Enablement is explicit (`IMP_OF02_ENABLED` and per-adapter flags). Default is
disabled so current runtime behavior is unchanged.

## Common contract

Conceptual fields (missing values remain missing; never fabricated):

- operation identity, run identity, attempt identity
- initiator, trigger, parent/root context
- source/config/data/model attribution
- artifact references
- technical execution result (`TerminalResult`)
- domain outcome, validity, disposition
- retry semantics, attribution completeness, provenance qualifier
- consequence policy

Result (logical IDs only, never SQLite rowids): `run_id`, `attempt_id`,
`commit_id(s)`, `artifact_ids`, `outcome_id`, `disposition_id`,
`provenance_qualifier`, `attribution_completeness`.

## Identity rules

- Native IDs: caller-allocated UUIDv4 before first submit; retries preserve them.
- Same command identity + same semantic hash → existing receipt.
- Same command identity + changed hash → conflict.
- Existing domain IDs remain domain IDs, linked via `ProvenanceReferenceRecord.canonical_identity`.
- Retrospective/legacy: deterministic UUIDv5 from source identity + content hash
  (OF-01 `validate_imported_uuid5`). Tiny OF-01 hardening allows v5 on command
  and record IDs while native `validate_uuid` remains v4-default.

## Native attribution

Contemporaneous attribution when the operation executes (`ProvenanceQualifier.NATIVE`).
Validation is the vertical slice proving: selection → run → attempt(s) →
report artifact → technical result → outcome → validity → disposition → readback.

## Retrospective attribution

Current indexing operation creates a truthful reference to historical material.
The historical work did not have OF-01 identities. `recorded_at` is the
contemporary OF commit time. Historical event time, if proven, is stored on
semantic fields (`coverage_*`, `effective_at_ns`) and MUST NOT overwrite
`recorded_at`.

## Legacy partial

Historical material exists but full provenance cannot be proven. Missing
metadata stays missing. Completeness is `PARTIAL`. Qualifier is `LEGACY_PARTIAL`.

## Run boundary

One run = one logical consequential objective under stable objective, evaluation
intent, input bundle, temporal policy, and meaningful configuration.

- technical retry → same run, new attempt
- materially changed dataset/protocol/request → new run
- same command after response loss → receipt lookup, not new IDs

## Attempt boundary

Preserve attempt history. Terminal results use OF-01 `TerminalResult`. Do not
collapse attempt-1 fail + attempt-2 pass into first-pass success.

## Outcome / validity / disposition

Remain distinct. Example: attempt `COMPLETED`, outcome “underperformed
baseline”, validity `VALID`, disposition `REJECT`. Unfavorable analysis is not
technical failure. Invalid methodology is not merely poor performance.

## Artifact mapping

Audit existing stores. Prefer external immutable reference + content hash via
`AttachProvenanceReference` when OF-01 permits. Copy bytes into CAS only when
the adapter must capture authoritative contemporaneous bytes (native reports).

## Temporal integrity

```text
historical source/event time  ≠  OF recorded_at
```

OF eligibility at a cutoff uses commit `recorded_at_ns`, never historical
event time. A retrospective index created today MUST NOT become eligible for a
historical decision merely because the source is old.

## Consequence-class failure policy

| Adapter | Consequence | Sync/async | Attribution failure | Acceptance depends on OF commit? |
|---|---|---|---|---:|
| Validation (local/dev) | C1 | sync best-effort | domain result stands; attribution error recorded | No |
| Validation (acceptance-bound) | C3 | sync | missing required attribution withholds governed acceptance | Yes |
| Benchmark | C2 | sync | durable attribution required when enabled + material report | Yes when enabled |
| Provider smoke | C2 | sync | durable when enabled; never fabricate live smoke | Yes when enabled |
| Research | C2 | sync | durable when enabled | Yes when enabled |
| Training | C2 | sync | durable when enabled | Yes when enabled |
| Evaluation | C2 | sync | durable when enabled | Yes when enabled |
| Promotion | C3 | sync | withhold governed acceptance | Yes |
| Drift / adaptation evidence | C2 | sync | durable when enabled; no mutation | Yes when enabled |
| Operational drill | C2/C3 | sync | C3 for restore/activation evidence | Yes for C3 |
| Retrospective indexer | C2 | sync | failed/conflicted counters; no silent rewrite | Yes for indexed rows |

C0/C1 may best-effort. C3/C4 MUST NOT hide attribution failure. Do not globally
fail every operation or globally ignore every attribution failure.

## Operations

CLI/API: adapter status, enable/disable inspection, retrospective dry-run,
execute, resume, conflict handling, reconciliation. No new UI.

## Test plan

Unit, contract, adapter integration, native attribution, retrospective indexing,
legacy partial, idempotency, retry, conflict, temporal integrity, artifact integrity,
consequence policy, restart/resume, agent negative tests, existing-subsystem
regression (adapter disabled vs enabled; domain semantics unchanged).

## Implementation stages

1. Audit + this spec
2. Common contracts + OF-01 v5 import-ID hardening
3. Validation vertical slice
4. Benchmark
5. Provider-smoke
6. Research
7. Training
8. Evaluation
9. Promotion + drift
10. Operational-drill
11. Retrospective indexing
12. Status + operations
13. Cross-adapter integration
14. Fault/temporal tests
15. Operational drills + acceptance

## OF-01 hardening (explicit)

Allow UUIDv5 on `CommandEnvelope.command_id` and domain record IDs so
retrospective indexing can use `validate_imported_uuid5` identities.
`validate_uuid` default remains v4. Native `RunRecord` with
`ProvenanceQualifier.NATIVE` still requires v4 `run_id`. Invariants 1–75
unchanged. Backward compatible.

## Acceptance

- 0 failures / 0 errors on canonical full validation
- no fabricated provenance, backdating, future-information leakage, duplicate
  history, silent C3/C4 ignore, SQLite bypass, Mongo authority, EVIDENCE rewrite,
  promotion/drift authority escalation, or unregistered executable paths
- `ADAPT-specific OF records added: NO`
- `EVIDENCE-01C new dependency: NO`
- `EVIDENCE semantics changed: NO`
- `OF-01 Invariants 1–75 changed: NO`
