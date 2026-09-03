# Field Semantics

## Phase 2A derived metric fields versus raw evidence

A `MetricResult` (`squeeze_core.metrics.MetricResult`) is a local calculation, not a provider fact
— it is a distinct model, never an `Observation`. It names its own `metric_name`/`metric_version`/
`calculation_policy_version` and retains `input_observation_ids`/`input_bar_boundaries` back to the
exact Phase 1H bars it was computed from. `value` is `None`, never `Decimal("0")`, whenever
`quality.state is not KNOWN_VALUE`. See
[`foundational-market-metric-contract.md`](foundational-market-metric-contract.md).

## Phase 2B normalized metric fields

`NormalizedMetricResult` and `BaselineStatistics` (`squeeze_core.metrics`) follow the identical
missing-versus-zero discipline: a missing target, missing baseline, insufficient history, or zero
denominator/variance is always `value=None`/`mean=None`/`standard_deviation=None` with
`quality.state is not KNOWN_VALUE` — never a silently substituted zero. Neither model is a field
extension of `MetricResult`; both are standalone models so that no Phase 2A result's serialized
bytes change. See
[`normalized-market-activity-contract.md`](normalized-market-activity-contract.md).

## Phase 2C pressure metric fields

`PressureMetricResult` and `DaysToCoverComponents` (`squeeze_core.metrics`) follow the identical
missing-versus-zero discipline: a missing starting/ending observation, a zero starting
denominator (for a relative/percentage-change metric only — a valid input for the matching
absolute-change metric), a cancelled short-interest record, or an unavailable volume baseline is
always `value=None` with `quality.state is not KNOWN_VALUE` — never a silently substituted zero.
`starting_source_age`/`ending_source_age`/`short_interest_source_age`
(`squeeze_core.metrics.SourceAgeMetadata`) keep evidence-freshness
(`availability_age_seconds`) and reporting-period staleness (`reporting_period_age_days`,
`publication_lag_seconds`) as two separate, never-collapsed fields. Neither model is a field
extension of `MetricResult` or `NormalizedMetricResult`; both are standalone models so that no
prior-phase result's serialized bytes change. See
[`short-interest-derived-metric-contract.md`](short-interest-derived-metric-contract.md) and
[`days-to-cover-semantics.md`](days-to-cover-semantics.md).

## Phase 1I trade and quote fields

A trade is a provider-reported transaction, not a bar or buy/sell classification. A quote is a provider-reported bid and/or ask, not depth or an execution promise. Price uses exact `Decimal`; whole size is nullable and non-negative, so missing versus zero is explicit. Venue, exchange, provider, sequence scope, market scope, conditions, and side identity are separate facts. Normal, locked, crossed, and one-sided states carry no directional meaning. No synthetic NBBO, midpoint, spread, aggressor side, order-flow, or liquidity calculation exists.

## Phase 1H market-bar facts versus derived interpretation

OHLC values are exact decimals; volume and trade count are exact non-negative counts. Missing volume means the provider did not supply a usable value, while zero means the provider explicitly reported zero. Interval, boundary, session, status, and availability are source facts. Relative volume, momentum, indicators, trends, signals, ranks, and strategies are not fields inferred or computed in Phase 1H.

## Phase 1G news metadata versus interpretation

Headline and summary are provider-supplied text, not generated analysis. Publication, update, provider availability, capture, receipt, and effective time are separate facts. Associated symbols are explicit only. Canonical URL normalization removes fragments and a small versioned tracking list without resolving or fetching the URL. Lifecycle status and syndication describe provider records; they do not imply sentiment, catalyst direction, relevance, materiality, novelty, ranking, or a trade.

## Missing versus zero

`null` plus an explicit quality state represents missing, unavailable, not applicable, or otherwise non-valued data. Numeric zero with `KNOWN_VALUE` is an observed/published zero. The quality fixture contains both a zero borrow fee and a missing borrow fee; they serialize differently and remain different after round trip.

## Published short interest versus short float

Published short interest is a share count measured for a settlement date and normally published later. `short_float_percent` is short shares relative to a float-share denominator and carries its own methodology/provenance limitations. Neither is broker borrow availability, borrow fee, covering volume, or minute-by-minute market-wide short interest.

Daily short-sale volume is also distinct: it describes transaction volume and cannot be mapped into open published short positions. Finviz short float and a published provider's short-float percentage are compared only if period, scope, meaning, and float methodology are explicitly compatible; Phase 1D does not assume that compatibility.

## Settlement, publication, receipt, and reporting age

Settlement date describes the market period. Publication and receipt establish availability. Effective time is never silently backdated to settlement. `availability_age_ms` and `reporting_period_age_days` remain separate, so a new receipt can still describe an old report.

Corrections are new immutable observations. A later correction may supersede a preserved original in a later bundle, but it cannot alter membership or bytes of an earlier bundle.

## Provider observation versus derived value

Provider-published, direct market observation, application-derived, human annotation, and synthetic fixture records use distinct kinds. A local calculation cannot be labeled as a Schwab, thinkorswim, or other provider observation. Derived records name the calculation/version and retain parent IDs and parameters.

## Snapshot freshness versus field freshness

A recent received or replay time does not make source data live. `data_freshness`, source timestamp, quality state, age, expected delay, and source health remain explicit per observation. Application or fixture freshness must never overwrite field freshness.

A Finviz-shaped capture timestamp is not provider publication time. When provider time is absent, capture may serve only as an explicitly uncertain envelope placeholder and cannot establish live field freshness. One screener timestamp also cannot prove equal update cadence for price, volume, float, short float, classifications, and earnings.

## Candidate snapshot versus borrow evidence

`MARKET_SNAPSHOT.short_float_percent` is a provider-published float-relative descriptive value. `BORROW_FEE.annualized_fee_percent` is lending cost, and `BORROW_AVAILABILITY.available_shares` is provider inventory. They are complementary, not conflicting versions of one field.

Missing candidate or borrow coverage remains an explicit missing domain. Conflicting compatible values remain separate observations and are never averaged or resolved by source priority in Phase 1C.

## Source versus received versus effective time

Source time is the source's assertion. Received time is ingestion. Effective time drives replay state. They can differ and no fallback silently substitutes one for another. Source timezone/text can remain in provenance even though internal time is UTC.

## TTM

TTM volatility compression is a possible future derived indicator based on versioned market inputs and parameters. Phase 1A only proves that such a result can be represented with parent observations, quality, and provenance. It supplies no TTM formula, signal, provider parity claim, or trading interpretation.

## SEC filing metadata versus interpretation

Period of report, filed time, SEC acceptance, publication, receipt, and effective time are distinct. Filed date and period never backdate availability. CIK and accession are string identities. Amendments are new immutable observations and cannot rewrite earlier bundles. Form type is objective metadata; it is not a bullish/bearish, catalyst, dilution, squeeze, or trading label.

## Trading-halt lifecycle metadata versus interpretation

Announcement, halt, quote schedule, quote actual, trade schedule, trade actual, publication, receipt, and effective time are distinct fields. A scheduled time never becomes an actual event merely because the clock passes it. Quote resumption does not imply trading resumption. Halt codes and reason text are objective source metadata only; the core assigns no sentiment, catalyst direction, squeeze meaning, recommendation, score, or trade action.
