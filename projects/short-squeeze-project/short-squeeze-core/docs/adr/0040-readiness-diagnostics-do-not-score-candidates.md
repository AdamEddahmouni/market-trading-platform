# ADR 0040: Readiness Diagnostics Do Not Score Candidates

## Context

The archived codebase's most damaging pattern, per the Phase 2D read-only audit of
`archived-project-code`, was silent zero/default substitution for absent data: a missing
`Short Float` column became `0`, insufficient RSI history became a fabricated `50.0` "neutral"
reading, insufficient volatility history became `0.0`. Each of these is numerically
indistinguishable from a verified real reading once it reaches downstream code. The same
codebase also contained a correct counter-example worth preserving: `core/ib_api.py`'s per-field
`quality_flags` list (`shares_short_unavailable`, `days_to_cover_unavailable`, ...) --an
explicit, additive ledger of what's missing, never a single collapsed score.

## Decision

Every Phase 2D diagnostic (`ReadinessDiagnostic`, carrying a `ReadinessDiagnosticCode`,
`DiagnosticSeverity`, `message`, optional `domain`, and `observation_ids`) describes one
objective, named fact --a domain's classification, an unresolved conflict, a missing required
metric, insufficient history-- and nothing else. `DiagnosticSeverity` (`INFO`/`WARNING`/`ERROR`,
reused verbatim from `squeeze_core.adapters.diagnostics`) indicates how urgently a fact should be
noticed, never how good or bad the underlying evidence is for trading purposes. No diagnostic
code, model field, or CLI output key anywhere in `squeeze_core.readiness` contains `score`,
`rank`, `recommend`, `prime`, `subprime`, `bullish`, `bearish`, `confidence_percent`, `grade`, or
`tier` --enforced by an AST identifier scan over every file in the package
(`tests/compatibility/test_phase_2d_isolation.py`), not just a style guideline.

## Consequences

A caller of `build_evidence_readiness_snapshot` gets a `structural_state` plus disjoint lists of
`missing_inputs`/`conflicted_inputs`/`incompatible_inputs`/`insufficient_history_inputs` --they
must combine these into a decision themselves; Phase 2D never does it for them. This keeps every
future consumer honest about the difference between "the required data is here" and "this is
worth trading," and makes the boundary enforceable by grep/AST scan rather than relying on every
future contributor remembering not to cross it.

## Rejected alternatives

Adding a `severity_score: int` derived from counting diagnostics (e.g. "3 warnings = medium
risk") was considered, matching a pattern the archived `controller/controller.py`'s
`_apply_corroboration()` used (`CorroboratedBy=[...] if score>=3`). It was rejected outright:
any numeric aggregation of diagnostics is a de facto quality score under a different name,
exactly the pattern ADR 0038 and this ADR exist to keep Phase 2D free of.
