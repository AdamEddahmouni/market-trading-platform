# Point-in-Time Evidence Policy

## Phase 2A derived-metric selection

`squeeze_core.metrics` does not define a second point-in-time policy. Every metric selector
(`metrics.selection.resolve_bar_at_boundary`, `resolve_trailing_window`) builds a `BarSeries`
through `evidence.bars.build_bar_series` first, inheriting the Phase 1H market-bar policy below
unmodified, then layers lifecycle resolution (latest eligible completed/corrected revision per
boundary) and provider-ambiguity detection on top of that already-eligible series. A correction or
cancellation affects a metric result only once its own publication/receipt/effective time makes it
eligible under this same policy; a `MetricResult` computed at an earlier `as_of` is never mutated
when later revisions arrive. See [ADR 0030](adr/0030-point-in-time-market-metric-selection.md).

## Phase 2C pressure-metric selection

Phase 2C introduces no second point-in-time policy either, but it does introduce a second
*implementation* of the eligibility gate: `metrics.selection` (Phase 2A/2B's selector module) is
hard-wired to `MARKET_BARS`/`BarInterval` shapes (`bar_start`/`bar_end`/`status`/`provider`
metadata keys that FINRA and IBKR observations do not populate), so it cannot be reused as-is for
`PUBLISHED_SHORT_INTEREST`/`BORROW_FEE`/`BORROW_AVAILABILITY` observations.
`metrics.pressure_selection` re-executes the identical three-gate rule (`source_timestamp <=
as_of`, `received_timestamp <= as_of`, `effective_timestamp <= as_of`) already documented above
for `PUBLISHED_SHORT_INTEREST`, applied uniformly to borrow observations (whose
`source_timestamp == effective_timestamp` by construction). `DAYS_TO_COVER`'s volume half still
composes Phase 2A's own `selection.resolve_trailing_window` directly — no third policy exists for
market bars either. See the archived `docs/phase-2c-design.md` §3/§12.

## Phase 2B normalized-metric selection

Phase 2B introduces no second point-in-time policy either. Every Phase 2B builder composes the
same Phase 2A selectors above — `resolve_bar_at_boundary` for targets,
`resolve_trailing_window` for volume distributions — or, for return distributions only, a small
price-only trailing-bar walk that reuses `selection.py`'s own private boundary-grouping and
lifecycle-resolution helpers directly (not a fourth reimplementation; see ADR 0030's own
"duplicate a small private helper" precedent). Every Phase 2B target/baseline is additionally
excluded from its own baseline by construction (ADR 0034), never a caller-toggleable option, so
that no request shape can leak a target into what it is being compared against.

## Phase 1I trade and quote policy

`include_trades_domain` and `include_quotes_domain` require independent coverage. Eligibility requires provider publication, local receipt, effective time, and non-future event time at or before `as_of`. Event time alone never grants availability. Capture/receipt placeholder policies remain explicitly uncertain. Correction and cancellation ages remain separate, and later lifecycle rows never rewrite historical bundles.

## Phase 1H market-bar policy

`include_market_bars_domain` requires independent market-bar coverage. Eligibility gates provider publication, local receipt, and effective time against `as_of`. Lifecycle corrections appear only after their own availability. Interval age and correction age are reported independently. Series expectations are explicit policy inputs: expected missing, session closed, and unknown expectation remain different diagnostics, and no exchange calendar is assumed.

## Phase 1G news policy

`include_news_domain` requires independent news coverage. A news row is eligible for a symbol only when the provider supplied that explicit association and source, receipt, and effective timestamps are within `as_of`. Missing or explicitly empty associations remain valid normalized source records but are excluded from symbol evidence. Later updates, corrections, withdrawals, and deletions never rewrite historical bundles.

`PointInTimeEvidencePolicy` is immutable and contains:

- `as_of`: required timezone-aware bundle time, normalized to UTC;
- `maximum_future_skew_ms`: bounded effective-time clock skew only;
- `maximum_age_ms_by_event_type`: explicit event-specific staleness thresholds;
- `allow_stale`, `allow_delayed`, and `allow_unknown_freshness`;
- `conflict_tolerance`: compatible semantic-field absolute tolerances;
- `source_priority_metadata`: informational metadata only, never winner selection.
- `maximum_reporting_period_age_days`: optional short-interest settlement-age threshold;
- `include_published_short_interest_domain`: explicitly require the fourth domain even when no such input exists.

No universal Finviz freshness threshold is built in. A caller must configure maximum age explicitly. A single screener timestamp cannot prove that every field has the same real-world update schedule.

Received time is a strict availability boundary. `maximum_future_skew_ms` does not permit evidence received after `as_of`. Stale, delayed, and unknown states remain visible when retained and are diagnosed when policy excludes them.

For `PUBLISHED_SHORT_INTEREST`, source timestamp is also a strict publication-availability boundary and is never relaxed by future skew. Reporting-period staleness is calculated from settlement date separately from effective-time/availability staleness. A correction published or received after `as_of` remains unavailable and cannot change an earlier bundle.

The CLI can use a local policy JSON file. Its `as_of` value is replaced by the explicit `--as-of` argument so command invocation remains the authoritative bundle point.

Phase 1E adds `include_sec_filings_domain` to require independent SEC filing coverage even when no SEC observation is supplied. For `SEC_FILING`, source time is the strict public-availability boundary and receipt is independently strict. Filed time and period of report satisfy neither gate. Date-only uncertainty remains explicit, and an amendment accepted or received after `as_of` cannot alter an earlier bundle.

Phase 1F adds `include_trading_halts_domain`. A halt row is eligible only after strict public availability, local receipt, and event effectiveness. Event occurrence does not itself prove publication or receipt. Scheduled resumptions remain scheduled, actual quote and trade resumptions remain distinct, and later revisions cannot rewrite an earlier bundle. When the domain is required but absent or incomplete, coverage and diagnostics state that explicitly.
