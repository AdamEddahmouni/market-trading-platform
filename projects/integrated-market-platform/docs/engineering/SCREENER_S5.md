# Main Screener S5 — multi-universe convergence

S5 turns the Main Screener into one screener over three typed universes: US
Equities, Futures, and US ETFs. The table, filters, views, saved screens, Quick
Preview, and the S4 dock are shared; each universe declares its own identity
source, fields, views, sort, session model, and panel capabilities. Everything
shown comes from a current provider or says it is unavailable; no replay,
fixture, or captured data enters the Screener path. See
[Main Screener S4](SCREENER_S4.md) for the dock and
[Main Screener S3](SCREENER_S3.md) for Preview, bars, and levels.

## Universe registry

`ui_api/screener_universes.py` is the only registry. `universe_spec()` rejects
anything else with `UNSUPPORTED_UNIVERSE`; `/screener/config` publishes it as
`universes` (with an explicit `view_order`, because API JSON sorts object keys).

| Universe | Id | Asset class / kind | Identity source | Session model | Default sort |
|----------|----|--------------------|-----------------|---------------|--------------|
| US Equities | `US_EQUITIES` | `EQUITY` / `TRADABLE_SECURITY` | `FINVIZ_ELITE` (S1) | US equity clock | volume ↓ |
| Futures | `FUTURES` | `FUTURE` / `FUTURE_CONTRACT` | `MOOMOO_OPEND_CONTRACT_CATALOG` | provider market state | root ↑ |
| ETFs | `US_ETFS` | `ETF_FUND` / `TRADABLE_SECURITY` | `MOOMOO_OPEND_ETF_CATALOG` | US equity clock | symbol ↑ |

`ui_api/screener_multi.py` serves Futures and ETFs; US Equities delegates
unchanged to the S1 `ScreenerService`. Catalogs are cached for 15 minutes and
re-projected when the trading date changes. A provider failure keeps the last
good catalog as `DEGRADED`, or returns zero rows with `source_error`; it never
falls back to fixtures.

## Futures

- **Identity.** `fetch_future_contracts` lists OpenD US futures. For each
  `US.<ROOT>main` alias, the existing S3 `resolve_contract` picks the one
  dated lead contract (`US.ES2612` → `ESZ26`). Only `CURRENT`, non-delisted,
  unexpired contracts are admitted; an unresolvable alias is dropped. The
  canonical XA-01 id is per contract (`register_future_contract`, or a
  reference-only registration when IMP has no spec for the root), so root and
  contract never collapse.
- **Lead semantics.** A row is the provider's current main contract for its
  root. It is not a roll model; later months are not listed.
- **DTE** is calendar days from today (America/New_York) to the provider last
  trade date.
- **Exchange** is the provider exchange (`US_CME`, `US_CBOT`, `US_NYMEX`,
  `US_COMEX`); the provider's `N/A` is shown as unavailable.
- **Tick size / multiplier** come from the IMP futures spec registry
  (`IMP_FUTURES_SPEC`) and are unavailable for roots it does not cover.
- **Quotes.** `fetch_future_quotes` is a bounded snapshot for visible rows only.
  A value is `LIVE` only with an explicit realtime mode and a clock ≤ 15 s old,
  `DELAYED` only when the provider says so, otherwise unavailable. A refusal is
  cached for five minutes. The footer names entitlement only when the provider
  refused with `MOOMOO_QUOTE_NOT_ENTITLED`.
- **Session.** `fetch_market_states` maps `FUTURE_OPEN`/`FUTURE_TRADING` →
  trading, `FUTURE_CLOSE` → closed, rest/maintenance → maintenance, anything
  else → unavailable. US equity 09:30–16:00 semantics are never applied.
- **Routing.** Open Instrument uses the contract's canonical id
  (`/workspace/XA01:…/futures`). Direct links survive a restart: the selector
  rehydrates S5 catalog identities from the current provider, never fixtures.
  Reference-only contracts expose no runtime or execution in the Futures page.

## ETFs

- **Identity.** `fetch_etf_catalog` calls OpenD `get_stock_basicinfo(US, ETF)`.
  Only provider-classified, non-delisted `US.` rows are admitted; names and
  tickers are never used to infer fund status. Each row registers an
  `ETF_FUND` canonical id (`register_etf_fund`); `market_data_id` carries the
  ticker for market data.
- **Market data.** ETFs reuse the S1 quote window, S3 bars/levels, and S4
  specialist subscriptions through the ticker — one subscription authority,
  32-instrument window cap, the catalog itself subscribes nothing.
  Panel demand for an ETF is admitted from the ETF catalog, not from the
  Finviz equity snapshot.
- **Fund metadata.** Holdings, expense ratio, AUM, issuer, and holdings count
  are not shown: no authoritative current source is implemented, so there is
  no Fund view.

## Fields, views, filters

| Universe | Views (tab order) | Filters |
|----------|-------------------|---------|
| US Equities | Overview, Performance, Technical, Volume, Short, Fundamentals, Custom (S2) | S2 catalog |
| Futures | Overview, Contract, Performance, Custom | symbol, company, root, exchange, contract month, DTE, lead |
| ETFs | Overview, Performance, Custom | symbol, company, exchange |

Futures Overview: symbol, root, description, exchange, expiry, DTE, lead,
price, change %, volume, open interest. Contract: adds contract month, tick
size, multiplier. ETF Overview: symbol, name, exchange, price, change %,
volume, bid, ask, spread %. A Technical view is not offered for Futures or ETFs
because no technical field exists for them. Market fields are not filterable in
Futures/ETFs because the catalog carries none; they come only from the visible
quote window. `validate_filters(universe=…)` rejects a field from another
universe with `FILTER_UNIVERSE_MISMATCH`.

## Saved screens and URL

- Saved screens are schema version 2 with `universe`. Version-1 screens (and
  version-1 envelopes) without a universe migrate to `US_EQUITIES` on read;
  a version-1 screen claiming another universe is rejected.
- View, sort, columns, widths, pinning, and filters are validated against the
  screen's universe; an incompatible screen is skipped, never reinterpreted.
- Selecting a saved screen switches the universe. Presets are US Equities.
- URL: `?universe=FUTURES|US_ETFS` (absent = US Equities) with the existing
  `screen`, `view`, `sort`, `dir`, `q`. Changing universe clears screen, view,
  sort, and filters (with a notice) and keeps search. Back/forward restore the
  universe, view, and filters; `screen` wins over last-used state.

## Preview and panels

| Capability | US Equities | Futures | ETFs |
|------------|-------------|---------|------|
| Quick Preview identity | S3 | contract, root, exchange, expiry | ticker, name, exchange |
| Preview bars / Auto S/R | S3 | unavailable (`FUTURES_BARS_UNVERIFIED`) | current OpenD bars |
| Key data | S3 equity fields | DTE, lead, tick, multiplier, last, volume, OI | last, volume, bid, ask, spread |
| Order Flow / CVD / Level 2 | yes | unavailable | yes |
| Charts | yes | unavailable | yes |
| Futures Context | yes | unavailable | unavailable |

Futures and ETF previews show no market cap, float, short float, or P/E. The
server refuses panel requests outside a universe's capabilities
(`PANEL_UNAVAILABLE_FOR_UNIVERSE`). The dock keeps its layout when the universe
changes; unsupported panels render as unavailable, and when no open panel is
supported the dock releases its demand (`instrument_id: null`) rather than
re-demanding the previous instrument. The quote window releases on every
universe switch.

## Observed provider state (2026-09-27, Sunday, market closed)

- **Futures:** 178 current lead contracts, 0 expired, 0 priced. Examples:
  `ESZ26` (CME, expiry 2026-12-18, DTE 82), `NQZ26`, `CLX26` (NYMEX, DTE 23),
  `GCZ26` (COMEX, DTE 93), `6AZ26`. Quotes: `MOOMOO_QUOTE_NOT_ENTITLED`.
  Market state: `FUTURE_CLOSE` → closed. Panel demand refused.
- **ETFs:** 6,306 provider-classified ETFs; `SPY`, `QQQ`, `IWM`, `TLT`
  present, `AAPL` absent. SPY preview: 200 current 5m bars
  (`SESSION_CLOSED`), Auto S/R available. SPY Order Flow/Level 2 demand
  accepted with provider subscriptions active; feeds `NO_CURRENT_FEED` and
  quotes `AWAITING_QUOTE` while closed. A direct vendor probe earlier the same
  day returned an SPY snapshot, ticks, depth, and current bars.
- **US Equities** in the isolated acceptance environment: Finviz
  `NOT_CONFIGURED`, shown as source unavailable.
- Warm reads: Futures catalog 30 ms (253 KB); full ETF catalog ≈0.85 s
  (7.2 MB uncompressed); ETF search 7 ms. The table renders ≈33 DOM rows for
  6,306 ETFs.

## Validation evidence

Closure run on 2026-09-27 (`APPDATA` isolated because `powershell.exe`
startup hangs on this host):

| Gate | Command | Result |
|------|---------|--------|
| Screener backend S1–S5 | `python -m unittest tests.platform.test_screener_s1 … test_screener_s5` | 123 passed (S5 13) |
| Screener UI | `npx vitest run src/components/screener` | 44 passed, 3 files |
| Full UI suite | `npm test` | 1,047 passed, 146 files |
| Typecheck | `npm run typecheck` | exit 0 |
| Build + budget | `npm run build` | exit 0; initial 201.35 KiB gzip |
| Format / lint | `python tools/imp.py format` / `lint` | exit 0 / exit 0 |
| Docs links | `python tools/check_docs_links.py` | 268 files OK |
| Changed domain | `python tools/imp.py validate changed` | exit 0 — 5,610 tests, 35 skipped, 0 failures, 0 errors |

Two earlier `validate changed` runs on the same tree each ended with
non-reproducible errors in different suites (`software_fullstack_acceptance`,
then `intelligence` and `ui1`); every affected acceptance module passed when
run alone, and the third run passed cleanly.

## Tests and limits

Backend: `tests/platform/test_screener_s5.py` covers the registry, field/view
compatibility, migration, Futures contract/expiry/DTE/identity, quote-mode
truth, entitlement refusal, market state, ETF classification and identity
mapping, catalog failure without fixtures, Futures preview, and ETF panel
admission. UI: `ScreenerPage.test.tsx` (URL universe, view order, filters,
saved-screen restore, entitlement footer) and `ScreenerPanels.test.tsx`
(capability loss releases demand).

Limits:

- Futures quotes, bars, and panels stay unavailable until the account is
  entitled and a futures bar path is verified.
- Only the provider's lead contract per root is listed.
- The full ETF catalog is sent to the browser (≈7.2 MB uncompressed).
- Market fields cannot be filtered in Futures/ETFs.
- No ETF fund metadata (holdings, expense ratio, AUM, issuer).
