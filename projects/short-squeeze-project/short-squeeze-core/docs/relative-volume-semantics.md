# Relative Volume and Volume Percent Deviation Semantics

`metrics.relative_volume` — `RELATIVE_VOLUME`, `VOLUME_PERCENT_DEVIATION`. See
[`normalized-market-activity-contract.md`](normalized-market-activity-contract.md) for fields
common to every Phase 2B metric, and [ADR 0031](adr/0031-volume-baseline-without-relative-volume.md)
for why this metric was deferred from Phase 2A.

## Formulas

```
relative_volume = target_volume / mean_volume_baseline

volume_percent_deviation = ((target_volume - mean_volume_baseline) / mean_volume_baseline) * 100
```

## Policy: `trailing_mean_ratio.v1`

- **Target**: resolved via `selection.resolve_bar_at_boundary` — the identical function Phase 2A's
  return/gap/range metrics use.
- **Baseline**: the literal Phase 2A `MEAN_VOLUME_BASELINE` result
  (`volume_baselines.build_volume_baseline_result`), called whole. Its `.value` is the denominator/
  subtrahend, its `.deterministic_id` becomes `baseline_metric_id`, its `.input_observation_ids`/
  `.input_bar_boundaries` are folded into this metric's own. `RELATIVE_VOLUME_BASELINE_UNAVAILABLE`
  is emitted whenever the baseline's own quality is not `KNOWN_VALUE`.
- **Target volume zero**: valid, produces exact `relative_volume = 0` /
  `volume_percent_deviation = -100`.
- **Target volume missing** (`payload.volume is None`): `RELATIVE_VOLUME_TARGET_MISSING_VOLUME`,
  `value=None`, `UNAVAILABLE` — never treated as zero.
- **Baseline mean zero**: `RELATIVE_VOLUME_BASELINE_ZERO`, `value=None`, `INVALID` — division is
  undefined, not silently zero or infinite.
- **Provider/session/interval/unit compatibility**: inherited verbatim from the reused
  `build_volume_baseline_result` call and the shared `MetricSelectionRequest` — see
  `docs/phase-2b-design.md` §10.
- **Target exclusion**: the target bar is a legitimate *input* to the ratio (its own volume is the
  numerator) but is always excluded from the trailing window that forms the baseline denominator
  (ADR 0034; `VOLUME_BASELINE_CURRENT_BAR_EXCLUDED` reused verbatim).
- **Arithmetic**: exact `Decimal` division under `localcontext(prec=28)`, matching Phase 2A's own
  `compute_percentage_return` precision.

## What this is not

Not "RVOL signal," not a threshold classification ("unusual volume"), not a candidate-ranking
input on its own. A result states the ratio/deviation and nothing else — see ADR 0032.

## Inherited-formula note

The archived `core/ib_api.py:497` formula (`rel_volume = today_volume / hist["avg_volume"]`) has
the same shape; its `rel_volume = 0.0` fallback when history is missing is explicitly **not**
reused — see `docs/phase-2b-design.md` §12.
