# Evidence Readiness Contract

Shared model conventions across `src/squeeze_core/readiness/`, mirroring the role
`foundational-market-metric-contract.md`/`normalized-market-activity-contract.md`/
`short-interest-derived-metric-contract.md` play for Phase 2A/2B/2C. See
`docs/phase-2d-design.md` for full rationale; this document is the quick-reference summary.

## Result models

Seven standalone, frozen (`ConfigDict(extra="forbid", frozen=True)`) Pydantic models, each with
its own `*_identity(result) -> dict` builder and `deterministic_id` self-assigned via
`model_validator(mode="after")` reusing `squeeze_core.metrics.identifiers.METRIC_NAMESPACE`/
`deterministic_metric_id` (no new UUID namespace):

| Model | Purpose | Doc |
|---|---|---|
| `DomainCoverageSnapshot` | which requested domains are present/missing/etc as of `as_of` | `domain-coverage-semantics.md` |
| `EvidenceAgeAlignment` | cross-domain availability-age spread | `evidence-age-alignment-semantics.md` |
| `ReportingPeriodAlignment` | cross-domain reporting-period spread | `reporting-period-alignment-semantics.md` |
| `EvidenceConflictSummary` | unresolved-conflict grouping | `conflict-and-missingness-summary-semantics.md` |
| `EvidenceMissingnessSummary` | missing/unknown/insufficient-history taxonomy | `conflict-and-missingness-summary-semantics.md` |
| `InputSufficiencyResult` | operation-scoped structural sufficiency | `input-sufficiency-semantics.md` |
| `EvidenceReadinessSnapshot` | aggregates the above by deterministic ID for one operation | this document |

Every result carries `quality: Quality` (reused verbatim from `squeeze_core.contracts.quality`)
and `diagnostics: tuple[ReadinessDiagnostic, ...]` (reused-shape `ReadinessDiagnosticCode` +
`DiagnosticSeverity`, sorted via `sort_diagnostics`). `quality.state` is `KNOWN_VALUE` whenever
the diagnostic computation itself succeeded — even an `INSUFFICIENT` or `CONFLICTED`
`structural_state` is a successfully computed, known answer; `quality` describes whether *this
Phase 2D computation* resolved, not whether the underlying evidence looks good.

## `EvidenceReadinessSnapshot`

Aggregates `DomainCoverageSnapshot`, `EvidenceAgeAlignment`,
`ReportingPeriodAlignment` (only when the operation's required domains include at least one with
a reporting-period concept), `EvidenceConflictSummary`, `EvidenceMissingnessSummary`, and
`InputSufficiencyResult` **by deterministic ID reference**, not by embedding — keeping the
snapshot small and each component independently anchorable and testable. `structural_state` is
copied from the underlying `InputSufficiencyResult`. `build_evidence_readiness_snapshot(bundle,
operation, *, policy_version=None, metric_results=())` is the single entry point most callers
(including the CLI) use; it internally calls each component builder once.

## What every model omits, deliberately

No `score`, `rank`, `confidence_percent`, `recommendation`, `alert`, or qualitative label
(`prime`/`subprime`/`bullish`/`bearish`/`strong`/`weak`/`grade`/`tier`) field exists anywhere in
this package — see ADR 0038 and ADR 0040. No model defines `schema_version` (that field is
Phase 1's `Observation` contract, pinned at `"1.0.0"`, and is never reused or overloaded here).

## Deterministic identity and serialization

`squeeze_core.readiness.identifiers` provides one `*_identity(result) -> dict` function per
model; every identity dict opens with a literal `"result_type"` string unique to that model
(e.g. `"DOMAIN_COVERAGE_SNAPSHOT"`), so two different result types can never collide even if
every other field coincided. All ID/observation/conflict collections are sorted before hashing;
`quality.state` is included in every identity dict (a structural fact) while `quality.reasons`
text and `diagnostics` are excluded (human-readable, not structural).
`squeeze_core.readiness.serialization` mirrors `metrics/serialization.py`'s
`serialize_*`/`deserialize_*`/`*_hash` triple pattern exactly, built on
`squeeze_core.serialization.canonical_json` — sorted keys, exact Decimal-as-string, no
whitespace.

## No-look-ahead

Every Phase 2D function takes an already-built `PointInTimeEvidenceBundle` as input and performs
no new timestamp comparison against wall-clock time; point-in-time eligibility is inherited
entirely from Phase 1's `build_point_in_time_evidence`, never re-derived.

## Phase 3A consumption

Phase 3A validity rules consume immutable `DomainCoverageSnapshot`,
`EvidenceConflictSummary`, and `InputSufficiencyResult` records. They preserve readiness IDs and
map structural states to independent rule outcomes; they do not recompute coverage, conflicts,
history sufficiency, or point-in-time eligibility.
