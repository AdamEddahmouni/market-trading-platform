# Session Gap Metric Semantics

`metrics.gaps` — `ABSOLUTE_SESSION_GAP`, `PERCENTAGE_SESSION_GAP`. See
[`foundational-market-metric-contract.md`](foundational-market-metric-contract.md) for fields
common to every Phase 2A metric.

## Formulas

```
absolute_gap = current_session_open - prior_session_close
percentage_gap = ((current_session_open - prior_session_close) / prior_session_close) * 100
```

## Policy: `explicit_prior_close_to_current_open.v1`

`docs/market-bar-session-and-lifecycle-timeline.md` already documents that Phase 1H "contains no
exchange calendar and does not invent expected bars." Phase 2A does not add one. The caller
supplies **both** the prior boundary and the current boundary explicitly
(`prior_bar_start`/`prior_bar_end`, `current_bar_start`/`current_bar_end`); the metric never
infers "yesterday's close" or "today's open" from a calendar.

Given two resolved bars, the metric reads each one's `session_date` metadata (never a naive UTC
calendar date — a 23:30 US/Eastern bar and its UTC timestamp can disagree on which calendar date
they belong to) and checks:

- **Same or non-increasing session date** (`current.session_date <= prior.session_date`):
  `GAP_SESSION_DATE_MISMATCH`, quality `INVALID`, no value. A gap is not defined between two bars
  of the same or reversed session.
- **More than one calendar day apart**: `GAP_NONADJACENT_SESSION_POLICY`, an **informational**
  diagnostic only — Phase 2A has no calendar to know whether the intervening days were holidays,
  so it cannot decide "adjacent" and does not try; the gap is still computed.
- Otherwise the gap is computed normally.

Session and interval compatibility for each boundary independently is enforced by
`selection.resolve_bar_at_boundary` (backed by `evidence.bars.build_bar_series`'s own
interval/session filter) — a boundary that resolves to a bar of the wrong interval or session
yields `GAP_PRIOR_SESSION_NOT_FOUND`/`GAP_CURRENT_SESSION_NOT_FOUND`, the same as no bar existing
at all, rather than a separate "wrong interval" code, since the metric never even sees an
incompatible bar to distinguish the two cases.

## Diagnostics

`GAP_PRIOR_SESSION_NOT_FOUND`, `GAP_CURRENT_SESSION_NOT_FOUND`, `GAP_PRIOR_CLOSE_UNAVAILABLE`,
`GAP_CURRENT_OPEN_UNAVAILABLE`, `GAP_SESSION_DATE_MISMATCH`, `GAP_NONADJACENT_SESSION_POLICY`,
plus the general `METRIC_ZERO_DENOMINATOR` (percentage only), `METRIC_PARTIAL_INPUT`,
`METRIC_CANCELLED_INPUT`, `METRIC_CONFLICTED_INPUT`, `METRIC_AMBIGUOUS_PROVIDER`.

## What this is not

Not a gap classification (full/partial gap-fill), not a bullish/bearish label, not a breakout
signal. A signed price difference (or percentage) between two explicitly identified bars.
