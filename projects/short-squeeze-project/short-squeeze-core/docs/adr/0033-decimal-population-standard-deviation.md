# ADR 0033: Decimal Population Standard Deviation

## Context

`VOLUME_Z_SCORE` and `PERCENTAGE_RETURN_Z_SCORE` both need a standard deviation over an explicit
trailing distribution. Two open questions: population (`N` denominator) vs. sample (`N-1`), and
`Decimal` vs. `float`. The archived-repository research
(`docs/phase-2b-design.md` §12) found `core/technical_indicators.py:compute_weekly_volatility` and
`compute_ttm_squeeze` both call Python's `statistics.stdev` — sample standard deviation, computed
over `float`.

## Decision

Use exact `Decimal` arithmetic throughout (`metrics/statistics.py`), under a local
`decimal.localcontext()` guard (`prec=50`) that never mutates the ambient context, mirroring Phase
2A's own `compute_percentage_return`/`compute_mean_volume` pattern (`localcontext(prec=28)`).
`Decimal.sqrt()` is called directly for the deterministic square root — no `math.sqrt`, no `float`
conversion anywhere in `metrics/`.

Use **population**, not sample, standard deviation:

```
variance = Σ(xᵢ - mean)² / N       (not N - 1)
standard_deviation = sqrt(variance)
```

## Consequences

Every Phase 2B distribution is an explicit, fully-enumerated, closed trailing window — exactly the
`N` bars/returns the caller asked for and the selector found — not a sample drawn from a larger,
unobserved population the caller is trying to infer something about. A z-score answers "how far is
this point from the mean of the window I was given," a population-statistic question by
construction; nothing in Phase 2B computes a confidence interval, hypothesis test, or forecast that
would call for Bessel's correction. `StandardDeviationPolicy` is still an explicit, versioned enum
(`POPULATION_DECIMAL_V1`) rather than a hardcoded formula, so a future `SAMPLE_DECIMAL_V1` policy
can be added without touching this one's meaning or any anchor computed under it.

The 50-digit calculation guard (up from Phase 2A's 28) accounts for variance's squaring step:
volume samples can be large (billions of shares → an 18-19 digit squared term), and summing several
such terms before a square root needs headroom beyond what a single division requires.

## Rejected alternatives

Sample standard deviation (`statistics.stdev`'s formula) was rejected for the reason above, not
because it is "wrong" in general — it would be the right choice if Phase 2B were estimating a
population parameter from a sample, which it is not. Reusing Python's `statistics` module directly
was rejected because its `pstdev`/`stdev` accept plain `Decimal` without a caller-controlled,
per-call precision guard, making the exact precision behavior implicit rather than an explicit,
tested, documented policy.
