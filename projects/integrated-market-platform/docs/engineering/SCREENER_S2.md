# Main Screener S2 — filters, views, columns, saved screens

S3 adds the Quick Preview; see [Main Screener S3](SCREENER_S3.md).

This document describes the S2 Screener implementation on the S1 branch head.
The current normal Screener path remains a real US-equity Finviz snapshot plus
the bounded Moomoo L1 viewport. No replay or fixture source is substituted.

## Canonical filters and execution

`GET /screener` accepts an optional JSON `filters` query parameter. Each rule is
`{id, field, operator, value}`. The backend rejects unknown fields, incompatible
operators, nonfinite numbers, inverted ranges, duplicate IDs, and oversized
lists. Numeric operators are `eq`, `ne`, `gt`, `gte`, `lt`, `lte`, `between`;
text operators are `eq`, `ne`, `in`, `not_in`, `contains`. Missing values never
match a rule, including `ne` and `not_in`. Multiple rules use AND. `between`
is inclusive. Percent values are percentage points, market cap is USD, share
counts are absolute shares, and RVOL is a ratio.

The filter catalog is returned by `GET /screener/config` with labels,
categories, types, units, operators, US-equity support, and snapshot
availability. It includes identity (`symbol`, `company`, `sector`, `industry`,
`country`), price/movement (`price`, `change_pct`, `perf_week`), volume
(`volume`, `avg_volume`, `rel_volume`), size (`float_shares`, `shares_outstanding`,
`market_cap`), short interest (`short_float_pct`, `short_ratio`), fundamentals
(`eps_ttm`, `pe`, `fwd_pe`, `recommendation`), and technical (`rsi_14`).

The provider query remains the broad US-stock export. The backend validates
and applies canonical filters to normalized rows, then applies text search,
sort, and windowing. It returns matching and unfiltered snapshot counts. No
raw Finviz filter token crosses the API. The source cache and quote window are
unchanged by column or view changes. Bid, ask, and spread are display columns
only: the bounded L1 viewport cannot truthfully filter the broad universe.
The raw earnings string is displayed, but no date filter is exposed because
its value is not a reliable canonical date.

## Built-in discovery presets

The backend translates immutable discovery definitions explicitly. Short
Squeeze Discovery maps float <50 million shares, price <$50, short float >20%,
RVOL >1.5. Unusual Volume maps RVOL >2. Momentum Ignition maps change >10%
and RVOL >1.5. The UI loads these as editable filters; edits mark the preset
modified and can be saved as a personal screen without changing the built-in.

Gap / Catalyst, Earnings Movers, Analyst Events, Insider Activity, and
Technical Breakouts are listed as unavailable with an explicit reason.
Their older provider conditions require gap, canonical earnings-date,
recommendation-threshold, insider-transactions, or 52-week-high semantics that
the broad S2 result contract cannot evaluate without misleading substitution.
No empty or approximate preset is presented as equivalent.

## Views and columns

All views use the same active result query and filter set:

| View | Columns in default order |
|---|---|
| Overview | Symbol, Price, Change %, Volume, RVOL, Float, Market Cap, Short %, Bid, Ask, Spread %, RSI (14) |
| Performance | Symbol, Price, Change %, Week %, Volume, RVOL, RSI (14), Market Cap |
| Technical | Symbol, Price, Change %, RSI (14), Week %, Volume, RVOL |
| Volume | Symbol, Price, Volume, Avg Volume, RVOL, Float, Change % |
| Short | Symbol, Price, Change %, Float, Short %, Short Ratio, RVOL, Volume |
| Fundamentals | Symbol, Company, Sector, Industry, Market Cap, EPS TTM, P/E, Fwd P/E, Earnings, Recommendation |
| Custom | Symbol, Price, Change %, Volume initially; user-configured thereafter |

TanStack Table owns visibility, order, widths, and left pinning. The Columns
panel can show/hide, move, pin, and reset columns. Headers resize by pointer
or keyboard arrow keys. Symbol remains visible. A column edit selects Custom.
Switching a view does not refetch the market snapshot or resubscribe L1 when
the visible instrument IDs stay the same.

## Personal screens and restoration

`POST /screener/config` requires `state.write` capability and accepts `save`,
`delete`, or `last` actions. Saved screen version 1 contains an ID, name,
US-equity universe, filters, view, sort, and column state. It contains no
quotes or market observations. The repository uses the existing local SQLite
`operator_preferences` table under `screener.s2.screens` and
`screener.s2.last`; the UI depends on the endpoint rather than the database.
Malformed or unknown-version stored configurations are ignored. Built-in IDs
cannot be overwritten or deleted. User screens can be saved, loaded, renamed,
saved as a copy, and deleted.

The URL represents saved screen ID, view, symbol/company search, and sort.
Explicit URL view/search/sort override a loaded screen; otherwise its saved
state applies, then the last-used configuration, then defaults. Search is
temporary URL state and is never included in a saved screen. The last-used
S2 configuration is written after edits with a short debounce. Back/forward
restores the high-level URL controls. Rich filter/column state is represented
by a saved screen ID or the local last-used configuration, not serialized into
the URL.

## Validation and current limits

Tests cover filter validation/execution, preset status and immutability,
SQLite reopen, route capability, S1 source and quote-window regressions, and
S2 UI controls. Live source availability and L1 state retain the S1 semantics.
The five unavailable older presets and lack of broad L1/date filters are the
material S2 limits. No S3 controls are rendered. No runtime dependency was
added; S2 uses existing TanStack Table/Virtual, React Query, and Zod.
