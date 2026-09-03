# Conflict and Missingness Summary Semantics

## Conflict summary

`build_conflict_summary(bundle, domains)` is a thin, deterministic grouping over
`bundle.conflicts` (`squeeze_core.evidence.EvidenceConflict`), which Phase 1's
`evidence/conflicts.py` already computes with revisions, corrections, and cancellations
excluded. Phase 2D adds exactly one further exclusion rule of its own:
**`TEMPORAL_DIFFERENCE`-classified conflicts are never counted.** Phase 1 retains
`TEMPORAL_DIFFERENCE` entries in `bundle.conflicts` for audit purposes, but they represent a
compatible field compared across different reporting/comparison periods — not a real
disagreement — exactly mirroring how Phase 1's own `CoverageState` computation already excludes
them from marking a domain `CONFLICTED`. `EvidenceConflictSummary.conflict_count`,
`conflicts_by_domain`, `conflict_ids`, and `conflict_categories` all apply this exclusion
consistently with `squeeze_core.readiness.coverage.classify_domain_coverage`'s own `CONFLICTED`
check, so a domain's coverage state and its conflict-summary membership never disagree about
what counts as a conflict.

No conflict is ever resolved by this module: there is no provider-preference field, no averaging,
no "winner" — `EvidenceConflictSummary` only counts, groups, and reports `conflict_categories`
(the distinct `ConflictClassification` values seen).

## Missingness summary

`build_missingness_summary(bundle, coverage_snapshot, *, policy=None, metric_results=())`
distinguishes four categories (`MissingnessCategory`):

- `MISSING_DOMAIN` — a required domain's `DomainCoverageState` is `MISSING`.
- `UNKNOWN_AVAILABILITY` — a required domain's `DomainCoverageState` is `UNKNOWN` (the evidence
  bundle never evaluated it — see `docs/domain-coverage-semantics.md`).
- `MISSING_REQUIRED_METRIC` — a policy-required `metric_name` was not found among the supplied
  `metric_results`.
- `INSUFFICIENT_HISTORY` — a policy that `requires_trailing_window` references a supplied metric
  result whose `SampleCounts.used < SampleCounts.requested`.

Rules enforced structurally, not just documented:

- **Zero is never missing.** A `KNOWN_VALUE` observation with a numeric `0` never appears in any
  missingness category — only `Quality.state in {MISSING, UNAVAILABLE}` (at the domain level) or
  an absent/insufficient metric result triggers a category.
- **Conflict is not missingness.** A `CONFLICTED` domain never contributes to
  `missing_domain_count` or `missing_by_domain` — it is reported exclusively through
  `EvidenceConflictSummary`.
- **Unit incompatibility is not missingness.** It is reported through
  `InputSufficiencyResult.incompatible_inputs` instead (`docs/input-sufficiency-semantics.md`).
- **Cancelled is not automatically missing.** A domain whose only eligible evidence is cancelled
  is classified `CANCELLED` at the coverage layer, not folded into `MISSING_DOMAIN` — the two
  facts (missing versus cancelled) remain distinguishable in `coverage_by_domain`.
- **No default-value substitution ever occurs.** Missingness is reported as a category on a
  `DomainMissingnessEntry`/`missing_required_inputs` list; no field anywhere is silently
  populated with a placeholder value.

`MISSING_REQUIRED_FIELD` (per-field, sub-observation missingness — e.g. a specific payload field
being `None`) is intentionally **not** implemented as a distinct category in this phase: Phase
2D's policies operate at domain/metric granularity, not per-field, and per-field value
missingness (e.g. `payload.short_shares is None`) is already the responsibility of each metric's
own builder function (per the Phase 2C precedent, checked directly against `payload` fields, not
inferred from `quality.state`). Adding a general per-field contract is a natural, additive
extension for a future phase, not a silent gap in this one.
