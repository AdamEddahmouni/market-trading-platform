# Main Screener S3 — Quick Preview, Why, automatic S/R, contextual futures

S3 adds a selected-instrument Quick Preview to the S2 Screener. It answers
"is this instrument worth opening?" without becoming a second Workspace. The
table stays the dominant surface. Everything shown comes from current
providers; when a provider cannot answer, the preview says so. See
[Main Screener S2](SCREENER_S2.md) for filters, views, and saved screens.

## Quick Preview contract

`GET /screener/preview?instrument=ID&timeframe=5m&scope=EXTENDED&filters=[...]`
(`state.read`) returns `screener-preview/1.0.0`: identity, current L1 quote,
key snapshot data, current bars, `AUTO_SR_V1` levels, the filter explanation,
classed movement evidence, and contextual futures. `timeframe` is `1m`, `5m`,
or `15m`; `scope` is `EXTENDED` or `RTH`. `filters` uses the S2 canonical rule
shape and is validated by the same validator. An instrument outside the current
snapshot universe is a 404. One request replaces a client fan-out.

Quote, bars, and levels keep separate clocks:

| Clock | Field | Meaning |
|---|---|---|
| Quote | `quote.state`, `age_ms`, field `as_of_ns` | Moomoo L1 from the live runtime; STALE after 5 s |
| Snapshot | `snapshot_as_of`, field `as_of` | Finviz publication snapshot |
| Bars | `bars.received_at`, `latest_complete_bar_end`, `state` | Current 1m klines and their freshness |
| Levels | `levels.calculated_at`, `input_latest_bar_end` | When zones were built and from which bar |

The UI header shows the live L1 price, otherwise the snapshot price labelled
"Snapshot". The S/R marker uses the live L1 price, otherwise the last completed
bar close labelled with its time. The header never shows a bar close as a
snapshot price.

## Current bars

`market_data/current_bars.py` is the provider-neutral contract (`current-bars/1.0.0`):
canonical instrument, timeframe, session scope, OHLC, volume, bar start/end,
session segment, provider/source, received time, latest complete bar, forming
bar, state, and reason. The normal source is Moomoo OpenD subscribed `K_1M`
bars read with `get_cur_kline` through `tools/moomoo/opend_quote_transport.py`
(`OpendCurrentKlineSession`), the same transport family as the L1 adapter.
Production code does not import calibration code. `request_history_kline` is
not used: it consumes the vendor's 30-day distinct-symbol history quota (99
symbols on the current account). The session holds at most 12 `K_1M`
subscriptions and releases the least recently read code after the vendor's
one-minute minimum hold. If all held codes are younger than one minute the
series is unavailable with `MOOMOO_SUBSCRIPTION_BUSY` and the UI retries in
5 s. The preview waits for a selection to settle for 180 ms, so arrowing past
rows does not subscribe to each row.

The vendor `time_key` is the bar end in America/New_York (RTH runs `09:31`
to `16:00`). A bar is complete only when its end is at or before the receive
clock; at most one later bar is reported as `forming` and is shown on the chart
but never used for structure. Malformed rows, overnight rows, future rows, and
negative volume are rejected; duplicate ends keep the last vendor row. Bars are
ordered by end time. 5m/15m bars are aggregated from 1m bars in ET clock
buckets keyed by date and session segment, so they never cross 04:00, 09:30,
16:00, or 20:00. A bucket is complete only when its end has passed. The 1m
series is cached per instrument for 5 s.

Session scope: `get_cur_kline` returns 04:00–20:00 ET bars without overnight
bars (verified against OpenD). `EXTENDED` (default) uses pre-market, regular,
and after-hours bars; `RTH` uses regular-session bars only. The scope is shown
next to the timeframe. The 1000-bar provider window is about one extended
session, so `15m RTH` has about 26 bars.

Bar freshness: `CURRENT` when the scope's session is open and the latest
complete bar is within 3 minutes of the latest bar that could be complete;
`SESSION_CLOSED` when the scope's session is closed and the latest bar is less
than four days old; `STALE` otherwise; `UNAVAILABLE` when the provider refuses
(`BAR_SOURCE_UNAVAILABLE` with the provider reason). No holiday calendar is
applied. Unavailable bars render "Chart unavailable"; no replay or fixture bar
is substituted.

## AUTO_SR_V1

`features/auto_support_resistance.py` is pure and deterministic.

1. Reference volatility is the mean true range of the input's regular-session
   bars when at least 14 exist, otherwise Wilder ATR(14). On real OpenD data,
   Wilder ATR over Extended bars was dominated by quiet after-hours bars (NVDA
   5m: 0.06 versus 0.50 regular-session mean true range), which collapsed zones
   to two ticks. Tolerance is `max(0.25 × ATR, 2 ticks)`.
2. Swing high at bar *i*: high strictly above the 3 prior highs and at or above
   the 3 following highs (mirror for lows). The pivot is confirmed at the end of
   bar *i + 3*; without all three confirming bars it does not exist. Only
   completed bars are input, so no pivot uses a bar that was not yet available.
   A pivot counts only if its rejection (move away within the confirmation
   window) is at least 0.5 ATR.
3. Pivots (highs and lows together) are sorted by price and clustered while
   each is within one tolerance of the previous member and within two
   tolerances of the cluster's lowest member.
4. Zones span member prices, widened symmetrically to at least one tolerance
   and clipped at the midpoint to a neighbour so zones never overlap. The 12
   strongest are kept.
5. Zone strength 0–100 = touches `min(n,4)/4 × 40` + recency
   `30 × 0.5^(age/48 bars)` + rejection `20 × min(mean rejection/ATR, 2)/2` +
   volume `10 × min(mean pivot volume/median volume, 2)/2` (0 without volume).
   It scores structural evidence. It is not a probability that a zone holds and
   is not calibrated.
6. Relative to price, zones wholly below are support, wholly above are
   resistance, and a zone containing price is "testing". Nearest support and
   resistance are the closest zones with strength ≥ 20. Distances are to the
   nearest zone edge as a percent of price.

Failure reasons: `INSUFFICIENT_BARS` (<20 bars), `MALFORMED_BARS`,
`BAR_SOURCE_UNAVAILABLE`, `STALE_BAR_SOURCE`, `INVALID_PRICE`,
`MARKET_DATA_UNAVAILABLE`, plus `NO_SUPPORT_ZONE` / `NO_RESISTANCE_ZONE` in
`reasons`. Stale or unavailable bars produce no zones.

Cadence: zones are built once per (instrument, timeframe, scope, latest bar
end, bar count, method) and cached; they change only when a new completed bar
arrives. The preview refreshes every 15 s. The price marker moves with each L1
update (the S1 quote window polls every 3 s). The UI reclassifies the cached
zones against the live price with `srClassify.ts`, a mirror of the backend
`classify` verified against the shared fixture
`tests/fixtures/screener/auto_sr_classify_cases.json`. "Levels calculated"
shows the zone clock; the price shows its own source and age. Why-panel S/R
sentences are computed server-side and carry the price time they used.

The chart (Lightweight Charts, lazy-loaded) draws the nearest support bounds in
green and resistance bounds in red; the S/R bar uses the same colours, with a
yellow band for a tested zone. The candle last-value label is hidden so green
and red axis labels mean only support and resistance. A screen-reader summary
states the zones and distances.

S/R is not a table column or a filter. It needs a bar subscription per
instrument, which is bounded to the selected row; computing it for visible or
filtered rows would need thousands of provider bar requests. A partial column
or a broad S/R filter would look universe-complete when it is not.

## Why it matched

The backend evaluates each active rule with the S2 predicate
(`screener_filters.rule_matches`, the function `apply_filters` uses) and
returns canonical labels and formatted values, for example
`Float 7.4M is below 20M`. Provider filter tokens never appear. No active
filters returns `NO_ACTIVE_FILTERS`. A missing value states that the rule
cannot match. Presets are their canonical translated filters; the UI appends
the screen name and "(modified)". A randomized test proves the explanation
agrees with `apply_filters`.

## Why it may be moving

Items carry one class: `OBSERVED` (session change, volume, current Finviz
headlines), `DERIVED` (relative volume, published short float, S/R proximity,
live futures moves), `UNAVAILABLE` (news source unavailable), and
`INSUFFICIENT_EVIDENCE`. Headlines come from the Finviz Elite news export,
tagged with the ticker, published between 16:00 ET on the weekday before the
move's session day and now. Finviz export times are read as US Eastern. With
headlines the panel states that headline timing is observed and causation is
not established; without them it states that no verified catalyst or causal
driver was identified. Futures items appear only with a live price and say
they are contextual, not evidence of causation. No AI synthesis is produced
(`ai_synthesis: null`). Tests reject causal wording.

## Contextual futures

`ui_api/screener_futures_context.py` (`FUTURES_CONTEXT_MAP_V1`) maps
canonical metadata to related futures, most specific first: `CL` for
`Oil & Gas *`; `NG` for `Oil & Gas E&P` or natural-gas industries; `GC`/`SI`
for gold, silver, and other precious-metal miners; `HG` for copper; `NQ` for
Technology and Communication Services; `RTY` for market cap below $2B (a size
proxy, not index membership); `ZN` for banks and mortgage finance only with a
live price; `ES` for every US equity. Each entry carries a relationship type
and reason.

Contract identity is the provider's main contract (`US.ESmain` →
`E-mini S&P 500 Futures (DEC6)`) resolved to the dated code (`US.ES2612`) and
validated against its last trade date. Display is `ESZ26`. An expired main
contract is `EXPIRED` and shown without a price; OpenD still lists expired
contracts such as CL OCT6. Prices come from Moomoo snapshots when entitled,
or for ES from the FuturesX depth bridge (mid) when it runs on the same
contract month. Otherwise price is unavailable with a reason. On this account
Moomoo returns "Insufficient quote permission" (`NOT_ENTITLED`) and the bridge
is not running, so related contracts show identity without price. Refusals are
cached for five minutes. The Futures tab ends with the causal note. S3 has no
Futures universe.

## UI and persistence

The preview is a right pane beside the table at 1280 px and wider, resizable
from 320 to 720 px by pointer or keyboard (←/→ 16 px, Home/End) while leaving
the table at least 560 px. Dragging writes the width to the pane directly and
commits on release. Below 1280 px it is a 400 px overlay drawer shown when a
row is selected. Row click selects and opens the pane; Arrow keys move the
selection; Enter opens the canonical Workspace route; Escape in the pane
closes it and returns focus to the grid; Escape in the grid clears the
selection as in S1. The toolbar Preview button toggles the pane. A selection
removed from settled results is cleared. Preview tabs (Why, Key Data, Futures)
use tab semantics with arrow/Home/End keys.

Preview requests are keyed by instrument, timeframe, scope, and filters; key
changes abort the previous request, and a response whose instrument differs
from the request is rejected. A slower older response therefore cannot replace
a newer selection. The pane layout `{open, width}` is stored under
`screener.s3.preview` through `POST /screener/config` action `preview_layout`;
saved screens are unchanged.

Measured on the real product (Sunday, market closed): selection to rendered
preview about 205 ms warm (including the 180 ms settle) and 0.4–1.3 s cold
(first bar subscription); preview API 0.14–0.20 s warm; `AUTO_SR_V1` 0.1–2.3 ms
for 26–1000 bars; timeframe switch about 0.63 s. Tab, timeframe, and resize
interactions caused zero table DOM mutations.

## Tests and limits

Backend: `tests/platform/test_screener_s3.py` covers S/R detection, clustering,
distances, strength, reference volatility, pivot significance, and no lookahead
(including a property test that every prefix's pivots are exactly the full
series' pivots confirmed by then); bar normalization, aggregation, sessions,
and freshness; preview contract, provider failure, stale bars, clock
separation, cache recalculation, and instrument isolation; Why explanations
and evidence classes; futures mapping, expiry, entitlement, bridge, and rates
gating; preview layout persistence. UI: `QuickPreview.test.tsx` plus the S1/S2
`ScreenerPage.test.tsx`.

Limits: L1 quotes in the preview require the live runtime to be attached, as
in S1. Futures prices are unavailable on the current Moomoo account. S/R is
selected-row only. The 1000-bar provider window limits RTH 15m history. No
exchange holiday calendar is applied to bar freshness. Headline tagging is
Finviz's and can include related tickers.
