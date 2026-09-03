# ADR 0034: Target Exclusion From Normalization Baselines

## Context

Every Phase 2B metric compares a target (a bar's volume, or a return) against a baseline built
from *other* evidence. If the target were allowed to participate in its own baseline, the
comparison would be partly comparing the target to itself — diluting a small window's mean toward
the target's own value and, in the two-sample case, making a z-score partly self-referential.
Phase 2A's `MEAN_VOLUME_BASELINE` already established this for volume (ADR 0031,
`VOLUME_BASELINE_CURRENT_BAR_EXCLUDED`) with a caller-toggleable `exclude_current_bar` default.

## Decision

Every Phase 2B baseline hard-codes target exclusion — `RelativeVolumeRequest`/`VolumeZScoreRequest`
reuse `TrailingWindow.exclude_current_bar` but Phase 2B never constructs one with it set to
`False`; `ReturnCountWindow.exclude_current_bar` is validated to always be `True`
(`NotImplementedError` otherwise) rather than exposed as a real toggle. Concretely:

- Volume baselines/distributions walk bars with `bar_start` strictly before the target bar's
  `bar_start`.
- Return baselines/distributions walk bars with `bar_start` strictly before the target return's
  *start* bar's `bar_start` — excluding both of the target return's own two boundary bars, not
  just one.

## Consequences

A target's own value can never leak into its baseline's mean or standard deviation, independent of
caller intent — there is no request shape that can accidentally re-include it. This is verified,
not merely asserted: every metric family's test suite includes an explicit "target excluded from
baseline" case, and the target's own `observation_id` is asserted absent from the baseline's
`input_observation_ids`.

## Rejected alternatives

Exposing `exclude_current_bar=False` on the Phase 2B request shapes (as Phase 2A's
`MEAN_VOLUME_BASELINE` does) was rejected: Phase 2A's toggle exists because a mean-volume baseline
has a legitimate, if unusual, "include today" reading; a normalized z-score or ratio's entire
purpose is comparing the target *against* something that does not already contain it, so there is
no non-degenerate use case for the toggle here, and offering it would only invite a caller to build
a self-referential comparison Phase 2B's own boundary is meant to prevent.
