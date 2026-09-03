# Outcome Observation Semantics

## Phase 2V historical amendment

`BoundaryOutcomeObservation` is a separate retrospective result using
`first_eligible_trade_bar_close_at_or_after_boundary.v1`. It evaluates both edges of a
bounded detection window and carries explicit missing-data state for each window.
References and extrema are comparison facts only: they are not orders, fills, entries,
exits, P&L, recommendations, or causal short-squeeze classifications.

What Phase 2V records about what happened after a candidate was surfaced — and the
several things it deliberately cannot record.

## 1. What an outcome observation is

A retrospective description of observed price, volume, and halt activity over named
windows following a detection time. It is descriptive: it reports what the bars show.

## 2. What it is not

It is **not a trade, a backtest, or a causal claim.** These are enforced structurally
rather than by convention — `CandidateOutcomeObservation` has no field capable of holding
any of the following, so none can be populated:

fill price, entry, exit, position size, holding period, profit and loss, return on
capital, stop, target, slippage, commission, win/loss, or a "squeeze confirmed" verdict.

Adding one would be a contract change requiring an ADR, and the test suite scans
serialized keys for exactly these names.

## 3. Separation of observation from interpretation

Five things are kept in distinct fields, because collapsing them is how a price movement
silently becomes a causal claim:

| Field | Holds |
| --- | --- |
| `subsequent_windows`, `maximum_observed_*`, `minimum_observed_*` | observed price movement |
| `volume_observations` | observed volume movement |
| `halt_events` | observed halt activity |
| `data_sources`, `limitations` | provenance and known gaps |
| `causal_interpretation` | interpretation — **only ever set from an explicit caller argument** |

Nothing in this module writes `causal_interpretation` from the numbers. A 190% observed
move leaves it `None`, and a test asserts exactly that. A price rise is never
automatically labelled a short squeeze; that would require confirmed short-side pressure
and an explicit validated definition, neither of which this phase provides.

## 4. Missing windows

A window with no bars is recorded as `observed = False` with its limitations, and
`OutcomeWindowObservation` rejects any price or volume value on an unobserved window.

The distinction matters in both directions:

- **Omitting** the window would read as "not asked."
- **Zero-filling** it would read as "no movement."

Neither is true. "We could not measure this" is a third state, and it is the one
recorded. Aggregates (`maximum_observed_price`, `maximum_adverse_move_percent`, and so
on) are computed only over observed windows, and stay `None` when none was observed.

## 5. Windows

`15_MINUTES`, `30_MINUTES`, `1_HOUR`, `SESSION_CLOSE`, `NEXT_SESSION_OPEN`,
`NEXT_SESSION_CLOSE`, `24_HOURS`.

Which of these is meaningful depends on what counts as a successful prediction — a
question for the research objective, not for this module. All seven are requested and
each is reported observed or not.

## 6. Bars are never invented

No interpolation, no forward-fill, no synthesis from adjacent intervals, and no inference
of a price that was not recorded. If a bar is absent, the window is unobserved.

## 7. The BIYA case

No BIYA market bar exists in the workspace at any interval on any date, so
`unobserved_outcome()` records all seven windows as uncomputable, emits
`VALIDATION_OUTCOME_DATA_INCOMPLETE` for each, and computes no aggregate.

This is less limiting than it first appears. **An outcome could not have validated this
case in any event**: no original BIYA value survives, so there is nothing for a
subsequent move to confirm or contradict. Acquiring the price series would produce a
number without producing a validation — which is precisely why the gap is recorded in the
acquisition manifest rather than filled from a public source.

## 8. Relationship to the case conclusion

An outcome observation is an input to `derive_conclusion()`, but a strictly limited one.
It can support `OUTCOME_CONFIRMED_METHODOLOGY_UNVERIFIED` when original values exist but
cannot be assessed. It can **never** upgrade a case whose original values are
unrecoverable — see ADR 0042.
