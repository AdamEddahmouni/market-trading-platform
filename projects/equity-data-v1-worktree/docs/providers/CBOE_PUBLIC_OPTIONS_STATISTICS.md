# Cboe Public Options Market Statistics

Official Cboe-hosted **aggregate options activity** and **exchange/reference evidence** for the Integrated Market Platform. This package complements — it does not replace — the existing Options lane (chains, IV, Greeks, surfaces, signed flow, dealer positioning).

The governing question:

> What options-market activity did this specific Cboe public source actually report, for what scope, and when could the platform have known it?

## Evidence labels

- **DOCUMENTED** — stated on official Cboe pages or terms.
- **OBSERVED** — verified from repository fixtures or bounded live probe.
- **INFERRED** — conservative platform interpretation with explicit assumptions.
- **UNTESTED** — designed but not exhaustively live-verified.
- **DEFERRED** — characterized but not canonical ingestion.

## Product role

| Evidence family | What it contributes | What it is NOT |
|---|---|---|
| Existing Options lane | Chains, IV, Greeks, surfaces, execution simulation | Aggregate exchange statistics |
| Cboe daily statistics | Put/call ratios, volume, open interest by product class | Signed order flow, direction |
| Cboe market volume summary | U.S. exchange-group matched volume and share | Cboe-executed volume for all rows |
| Cboe intraday exchange stats | Cumulative call/put activity by time bucket (Central) | Real-time NBBO or OPRA |
| Cboe symbol data | Exchange-specific contract activity snapshots | Consolidated OPRA chain |
| Cboe reference CSVs | Series eligibility, underlying mapping | Trading volume or positions |

## Official source matrix

| Source | URL | Format | Scope | Status |
|---|---|---|---|---|
| Daily Market Statistics | https://www.cboe.com/us/options/market_statistics/daily/ | HTML + embedded JSON | **Cboe exchanges** | **OBSERVED** |
| U.S. Market Volume / Share | https://www.cboe.com/us/options/market_share/market/csv/ | CSV | **U.S. options market** (Cboe publisher) | **OBSERVED** |
| Exchange Intraday Statistics | https://www.cboe.com/us/options/market_statistics/market/ | HTML embedded | **Cboe exchanges**, Central time | **OBSERVED** |
| Symbol Data (C1/BZX/C2/EDGX) | `/us/options/market_statistics/symbol_data/csv/?mkt=` | CSV | **Per exchange** | **OBSERVED** |
| Reference Data | `cdn.cboe.com/data/us/options/market_statistics/symbol_reference/` | CSV | **Cboe-listed reference** | **OBSERVED** |
| Historical P/C archive | `cdn.cboe.com/resources/options/volume_and_call_put_ratios/` | CSV | **Cboe**, archive through ~2019 | **OBSERVED** |
| Historical volume form | https://www.cboe.com/us/options/market_statistics/historical_data/ | Form/HTML | **Cboe exchanges** | **CHARACTERIZED** |
| Net Option Premium Summary | Same market-share CSV with notional bias | CSV | **U.S. market** | **CHARACTERIZED_DEFERRED** |
| Volatility Settlement EOI | https://www.cboe.com/us/options/market_statistics/volatility_settlement_eoi/ | Excel | Specialized settlement | **DEFERRED_SPECIALIZED** |

## Critical scope distinctions

1. **Publisher ≠ execution venue.** Cboe hosts market-wide share tables; a Nasdaq row is not Cboe-executed volume.
2. **Daily statistics ≠ consolidated OPRA.** Daily put/call and volume/OI on the daily page reflect **Cboe exchange aggregates**, not the full U.S. market.
3. **Symbol data ≠ NBBO.** Bid/ask fields are **exchange quotes** on that venue only.
4. **Volume ≠ open interest.** Separate metric families and clocks.
5. **Put/call ratio ≠ direction.** High or low ratios do not imply bearish/bullish labels; opening/closing and aggressor side remain **UNKNOWN**.

## Delay behavior

The market volume / share page states share and notional values are delayed **at least 20 minutes** (**DOCUMENTED**). The platform stores `source_delay_policy`, `source_data_as_of_time`, and `available_time` separately. Delay policy is a bound, not an exact historical publication timestamp.

## Put/call semantics

Where supported:

```text
derived_ratio = put_volume / call_volume
```

Source-published ratio is preserved separately as `source_ratio`. Reconciliation status flags `SOURCE_RATIO_MISMATCH` when incompatible within rounding tolerance. Zero denominator → **UNKNOWN**, not infinity, unless the source explicitly publishes a special zero representation.

## Open interest clock

Open interest on the daily page reflects Cboe's published aggregate snapshot for the referenced trade date. Same-day volume timestamps must not be assumed to represent OI availability without source confirmation (**INFERRED** conservative handling via `available_time`).

## PIT model

| Clock | Meaning |
|---|---|
| `trade_date` / bucket | Market period the statistic describes |
| `source_data_as_of_time` | Source-displayed freshness when known |
| `available_time` | Platform visibility / knowledge time |
| `retrieved_time` | HTTP retrieval instant |

Historical pages retrieved today do not prove exact historical public availability unless documented → `HISTORICAL_PUBLICATION_TIME_UNKNOWN`.

Bitemporal storage uses `ReferenceKind.OPTIONS_OI` with content-hash versioning for corrections and reference file replacement.

## Licensing (**DOCUMENTED**)

Public pages are subject to [Cboe website terms](https://www.cboe.com/terms/). Materials are for personal non-commercial use; redistribution or derivative commercial use requires prior written consent. Market statistics pages request citing **Cboe Global Markets** in published reports. **DataShop paid products are not used** in this package.

Platform use: internal research / platform development unless governance explicitly expands scope. Raw redistribution status: **RESTRICTED_REVIEW_REQUIRED**.

## Options lane interoperability

`OptionsAggregateContext` coexists with `OptionChainSnapshot` and related O1–O11 artifacts. Aggregate statistics feed **options market context** only — not IV surfaces, dealer gamma, or execution quotes.

Live gate: `IMP_CBOE_OPTIONS_LIVE=1`

Probe: `python tools/cboe_options/probe.py`

Capability report: `evidence/cboe_options/capability-report.json`

## Known limitations

- Aggregate activity is not signed flow.
- Put/call is not trade direction.
- Cboe symbol snapshots are not historical chain data.
- Public data can be delayed.
- Historical publication time may be unknown for archived pages.
- Opening/closing classification unknown.
- Multi-leg/spread ambiguity in aggregate counts.
- Net option premium direction semantics remain ambiguous → deferred.
- Pre-2011 market structure breaks documented on Cboe historical pages → `HISTORICAL_COVERAGE_REGIME_CHANGED` when applicable.
