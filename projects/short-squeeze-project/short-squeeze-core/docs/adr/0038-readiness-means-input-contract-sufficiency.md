# ADR 0038: Readiness Means Input-Contract Sufficiency, Not Trading Readiness

## Context

The inherited archived codebase's `classify_tier()`/`score_setup()` fused two genuinely
different questions into one label: "is all the data present" and "does this look like an
attractive trade." A "Prime" classification could occur (and, per the advisor-meeting
transcripts, did occur) with zero or missing borrow-fee data, because completeness and
attractiveness were never separated. Phase 2D exists specifically to answer the first question
--structural input-contract sufficiency for one named, already-implemented Phase 2A/2B/2C
operation --without ever touching the second.

## Decision

`StructuralState` has exactly four members: `SUFFICIENT`, `INSUFFICIENT`, `UNKNOWN`,
`CONFLICTED`. Each is scoped to one `operation` (an existing `MetricName`) and one versioned
`OperationRequirementPolicy` --never to a symbol in isolation, and never aggregated across
operations into a single per-symbol readiness verdict. No Phase 2D model has a `score`, `rank`,
`confidence_percent`, `recommendation`, or qualitative-label field; this is enforced by an
AST-based identifier scan in `tests/compatibility/test_phase_2d_isolation.py` and a
field-name scan in `tests/readiness/test_models.py`, not merely documentation.

## Consequences

A `DAYS_TO_COVER` structurally-`SUFFICIENT` result can still carry a short-interest report that
is 30 days stale --the readiness snapshot preserves that age explicitly (via
`EvidenceAgeAlignment`/`ReportingPeriodAlignment` referenced by ID) rather than either hiding it
or downgrading `structural_state` on account of it, since staleness is an age fact, not a
structural-contract fact. Any future phase that wants to combine sufficiency with quality
judgments must do so in its own, clearly-separate layer --Phase 2D's models give it the
building blocks (per-domain state, per-domain age, conflict/missingness detail) but deliberately
stop short of combining them into one verdict.

## Rejected alternatives

A single boolean `is_ready` field was rejected: it cannot distinguish "definitely insufficient"
from "we don't know" (`UNKNOWN`), which the inherited codebase's binary framing repeatedly
conflated. A five-or-more-state enum including something like `MARGINAL` or `DEGRADED` was
rejected as reintroducing a quality judgment under a different name --every state Phase 2D
reports must be justified purely by presence/compatibility/conflict facts, not by how good those
facts look.
