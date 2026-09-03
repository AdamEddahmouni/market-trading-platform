# Input Sufficiency Semantics

## Operation requirement policies

`squeeze_core.readiness.policies.OPERATION_REQUIREMENT_POLICIES` is a versioned
(`policy_version="phase_2d_readiness_policy.v1"`), purely declarative dict mapping each of the 17
already-implemented Phase 2A/2B/2C operations named in the handoff to an
`OperationRequirementPolicy`: `required_domains`, `optional_domains`, `required_metric_names`
(only for operations that structurally build on another named metric, e.g. `RELATIVE_VOLUME`
referencing `MEAN_VOLUME_BASELINE`), `requires_trailing_window`, and forward-compatible-but-
currently-unpopulated fields (`required_units`, `required_provider_scope`,
`required_session_scope`, `required_interval_scope`, `required_age_dimensions`,
`allow_conflicts`, `allow_unknown_availability`). No policy contains formula logic or a trading
threshold; `lookup_policy(operation, policy_version=None)` raises `UnsupportedOperationError` or
`UnsupportedPolicyVersionError` for anything outside this fixed set — there is no generic
"short-squeeze readiness" policy and none is ever added here.

## `InputSufficiencyResult` evaluation

`build_input_sufficiency_result(bundle, operation, *, policy_version=None, metric_results=())`:

1. Resolves the policy via `lookup_policy`.
2. Classifies each `required_domain` via `classify_domain_coverage`
   (`docs/domain-coverage-semantics.md`), routing `MISSING`/`UNAVAILABLE`/`CANCELLED`/`PARTIAL`
   into `missing_inputs`, `CONFLICTED` into `conflicted_inputs`, and `UNKNOWN` into both
   `missing_inputs` and a tracked unknown-domain set that drives the `UNKNOWN` structural state.
3. For each `required_metric_names` entry, looks for a matching `metric_name` in the supplied
   `metric_results` tuple. Absent → `missing_inputs`. Present → checks its `quality.state`
   (`CONFLICTED` → `conflicted_inputs`; `MISSING`/`UNAVAILABLE`/`INVALID` → `missing_inputs`),
   its `unit` against `policy.required_units` when non-empty (→ `incompatible_inputs`), and,
   when `policy.requires_trailing_window`, its `SampleCounts.used < requested` (→
   `insufficient_history_inputs`).
4. **Never recomputes the downstream metric.** Only presence/compatibility of what the metric
   would need is validated; an already-computed result's own `quality`/`SampleCounts` is
   cross-checked only when the caller supplies one.

## Structural-state resolution

```
CONFLICTED   if any required input is conflicted and not policy.allow_conflicts
UNKNOWN      elif any required domain is UNKNOWN and not policy.allow_unknown_availability
INSUFFICIENT elif missing_inputs or incompatible_inputs or insufficient_history_inputs
SUFFICIENT   otherwise
```

`CONFLICTED` is checked before `UNKNOWN` because an active disagreement is a stronger signal
than an availability question that simply couldn't be resolved.

## Unit/scope compatibility — a documented scope boundary

Canonical, normalized payload models (`BorrowFeePayload`, `BorrowAvailabilityPayload`, etc.)
deliberately do not carry a unit field — adapter normalization resolves unit ambiguity once, at
ingestion time (see ADR 0037). This means raw-observation-level "mixed units" cannot occur by
construction for the domains Phase 2D currently covers. `incompatible_inputs` is therefore
populated only when a *referenced metric result*'s `unit` field disagrees with a policy's
`required_units` — demonstrated in `scripts/generate_phase_2d_anchors.py`'s
`incompatible_borrow_fee_units` anchor via a script-local, non-production
`OperationRequirementPolicy` (registered in the shared registry only for the duration of that one
lookup, then removed, verified by `tests/readiness/test_policies.py`'s seventeen-operation
count staying exactly 17 across the whole test session).
