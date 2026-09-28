# Main Screener S10 — Crypto universe

Status: **implemented on `codex/screener-s10-crypto`, stacked on S9
(`codex/screener-s9-bonds`).**

S10 adds Crypto as the fifth and final core Screener universe
([universe architecture](SCREENER_UNIVERSE_ARCHITECTURE.md)): real, current,
24/7 spot pairs from one venue — Kraken — through the one canonical query,
with the S4 specialist panels running on the venue's own trade and book
streams. Nothing in S10 authenticates, trades, reads account data, or uses
replay, fixture, or captured data at runtime.

## Architecture

| Layer | Module | Role |
|-------|--------|------|
| Registry | `ui_api/screener_universes.py` | `CRYPTO` spec: identity fields `base_asset, quote_asset, venue, product_type`, session model `24_7`, default sort `symbol`, views, panels |
| Universe service | `ui_api/screener_crypto.py` | Kraken REST catalog + all-pair ticker snapshot, canonical query/paging, Preview, Charts |
| Query | `ui_api/screener_query.py`, `screener_filters.py` | unchanged canonical query; universe-aware filter labels |
| Identity | `xa01` `register_crypto_pair` | XA-01 `CRYPTO_PAIR` ids, venue-qualified (`BTC/USD` on `KRAKEN`) |
| WebSocket | `crypto_market/ws_client.py` | stdlib RFC 6455 client (dependency lock forbids third-party WebSocket packages) |
| Venue stream | `crypto_market/kraken_stream.py` | one Kraken WS v2 connection: `trade` + `book` channels, reference-counted demand |
| Book | `crypto_market/kraken_book.py`, `order_flow/order_book/engine.py` | exact-decimal parsing, CRC32 checksum, canonical L2 engine with `CHECKSUM_MISMATCH` invalidation |
| Specialist panels | `ui_api/screener_specialist.py` | the S4 service, instantiated for Crypto with Kraken capabilities |
| UI | `ui/src/api/screenerCrypto.ts`, `components/screener/crypto/` | strict Crypto Preview contract, `CryptoQuickPreview`, Crypto formatting |

Live Kraken data is opt-in: `IMP_CRYPTO_LIVE=1`. Without it the universe
reports `CRYPTO_NOT_CONFIGURED` ("Kraken public market data is not enabled for
this workstation") and the panels report `LIVE_RUNTIME_UNAVAILABLE`; no row or
value is shown.

## Provider decision

| Provider | Verified capabilities (public, no credentials) | Decision |
|----------|-------------------------------------------------|----------|
| **Kraken** | REST `AssetPairs` catalog (1,452 entries; status, `wsname`, price/lot decimals, `ordermin`, `costmin`); REST `Ticker` for **all pairs in one call** (last, bid, ask, UTC-day open `o`, rolling-24h volume/VWAP/high/low/trades); REST `OHLC` bars (720 per interval); WS v2 `trade` (native taker side) and `book` (snapshot + deltas with CRC32 checksum) | **USED** — every S10 row, Preview, and panel |
| **Coinbase Exchange** | REST `products` (838 products, 514 online); REST `products/stats` for all products in one call (**rolling** 24h open/high/low/last/volume, 30-day volume, RFQ volume) but no bid/ask in bulk; per-product `ticker` with bid/ask and an exchange event timestamp; per-product candles. Probed read-only 2026-09-28. Its WebSocket channels were not re-verified in this session | **DEFERRED** |

Coinbase has genuine unique value — a rolling 24h open, 30-day volume, and a
ticker event timestamp — but only for **Coinbase's own venue**. Crypto rows are
venue-qualified; Coinbase data cannot enrich a Kraken row without presenting
one venue's number as another's. Using it would mean adding a second venue's
rows (a Coinbase slice of the universe), a separate owner decision. The prior
S10 audit and this probe agree: Kraken alone supplies every capability the
implemented rows and panels need, so a second runtime provider is not added.

## Catalog and pair counts

The catalog lists every Kraken `AssetPairs` entry; only `status == "online"`
spot pairs become rows (status is explicit venue metadata, never inferred
from names). Observed during acceptance (2026-09-28, values vary live):

| Count | Observed |
|-------|----------|
| catalog entries | 1,452 |
| online spot pairs (rows) | 1,354 – 1,355 |
| priced online pairs | 1,328 – 1,330 |
| online pairs without a usable last price | ~25 — shown as missing (`—`), never 0 |

Each row keeps venue identity (`KRAKEN`), base/quote identity, the venue's
provider symbol and `wsname`, and increments derived from the venue's decimal
precision (`price_increment`, `base_increment`, `quote_increment`,
`min_order_size`). Missing fields remain missing.

## Field semantics

| Field | Source | Meaning |
|-------|--------|---------|
| Last | ticker `c[0]` | last trade price in quote units |
| **UTC Day Change %** | `c[0] / o − 1` | Kraken `o` is the **UTC-midnight open**, so this is a UTC-day change — never labelled a rolling 24h change |
| 24h High / Low, 24h Trades | ticker `h[1]`, `l[1]`, `t[1]` | rolling 24h |
| 24h Base Volume | ticker `v[1]` | rolling 24h, base units |
| 24h Quote Volume | `v[1] × p[1]` | derived: rolling 24h base volume × rolling 24h VWAP |
| Bid / Ask / Spread % | ticker `b[0]`, `a[0]` | spread on the mid; absent when either side is missing or crossed |

The ticker carries no event timestamp; the Preview says so and shows the
receipt time instead. Filter labels are universe-aware (Pair, Last (quote
units), UTC Day Change %) without changing any other universe's labels.

## Query, views, filters, paging

Crypto runs through the canonical query (universe, filters, search, sort,
direction, offset/limit) with no Crypto-specific query path.

- **Views:** Overview, Performance, Liquidity, Custom.
- **Filters (15):** Pair, Base Asset, Quote Asset, Venue, Status, Last, UTC Day
  Change %, Bid, Ask, 24h High, 24h Low, Spread %, 24h Base Volume, 24h Quote
  Volume, 24h Trades.
- **Snapshot evaluation:** market filters and sorts evaluate against one
  complete all-pair ticker snapshot (`SNAPSHOT_TTL_S` 20 s; catalog 15 min;
  failures 30 s). If the ticker does not cover the catalog, market filters are
  refused (`MARKET_SNAPSHOT_INCOMPLETE`) instead of silently filtering a
  subset.
- **Result-set consistency:** pages carry a `result_set_id`; a page request for
  a replaced result set is refused with HTTP 409, so pages from two snapshots
  never mix.
- **Search:** pair, base, or quote (`BTC`, `BTC/USD`, `USD`).
- **Saved screens / URL:** the S1 contract unchanged — the URL carries
  `universe, view, q, sort, dir, screen`; filters, view, sort, and columns
  persist in the saved screen (`screen=` id) and last-config. Search is
  URL-only by design.

## 24/7 semantics

Crypto's session model is `24_7`: the session reads **24/7** everywhere,
weekends and overnight are healthy operation, and `MARKET_CLOSED` /
`SESSION_CLOSED` are never used for Crypto. All Crypto clocks — panels,
Preview, chart axes, and the Screener footer — read **UTC**; US universes keep
their ET/local clocks.

## Bars and Charts

Kraken REST `OHLC` (1m / 5m / 15m, 720 bars) feeds the Preview chart and the
Charts panel as a continuous 24/7 series (no RTH/extended scopes). The last
Kraken bar is still forming and is shown as forming, never as complete. Auto
support/resistance (`AUTO_SR_V1`) runs on the pair's own venue bars; without
current bars levels are unavailable. Prices keep the venue's price increment,
so sub-cent assets (SHIB `0.000005739`) are never rounded to `0.00`.

## Order Flow and CVD

Kraken WS v2 `trade` events carry `side`, documented by Kraken as *"the side of
the taker order"*. IMP treats it as an **exchange-native aggressor side**
(`EXCHANGE_NATIVE`): a buy is a taker buy lifting the offer, a sell a taker sell
hitting the bid. It is venue-reported, not inferred, and it says nothing about
who the buyer or seller was.

- Order Flow labels the tiles **Taker buy / sell vol** and states "Direction is
  the venue-reported taker side. Volume in BTC" (base units).
- Trades are subscribed without a snapshot, so both panels are anchored at the
  subscription acknowledgement: **"CVD since subscription HH:MM:SS UTC"** — never
  a session or complete CVD. A reconnect or pair switch re-anchors.
- Fractional base-unit volumes keep four significant digits (`+0.01699` BTC),
  never rounded to `0`; tape sizes keep up to 8 decimals.
- A subscribed pair with no prints yet is state `CURRENT` with reason
  `AWAITING_DATA` ("Subscribed; no trades printed yet"), the S4 contract.

## Level 2

Kraken WS v2 `book`, depth 25 per side, one venue:

- the first message is a full snapshot; updates carry changed levels (`qty` 0
  removes); the local book is truncated to the subscribed depth after every
  message because the venue does not send removals for levels pushed below it;
- prices and quantities are parsed as `Decimal` from the JSON text;
- every message carries a CRC32 of the top 10 asks then top 10 bids; a mismatch
  sets `CHECKSUM_MISMATCH`, the book is never shown or continued, and the
  stream resubscribes for a fresh snapshot (rate-limited per pair);
- the panel says "Kraken order book, top 25 levels per side, snapshot plus
  deltas verified against the venue checksum; one venue, not a consolidated
  crypto market";
- checksum evidence: 2,128/2,128 live checksums (BTC, ETH, XRP, SHIB, PEPE /USD)
  in the prior session and the 41-message captured fixture
  (`tests/fixtures/crypto_market/`) used only by tests.

**Unsubscribe needs the original depth.** Kraken keys a book subscription by
depth; an unsubscribe without `depth` targets depth 10 and leaves the depth-25
subscription alive, and the next subscribe is refused with *"Already
subscribed"*. The stream always sends `depth` on book subscribe and
unsubscribe. Verified live: depth-qualified unsubscribe succeeds and a
resubscribe delivers a fresh snapshot.

## Subscription behavior

- **One connection.** All pairs, panels, and clients share one public
  connection to `wss://ws.kraken.com/v2`; panels hold reference-counted
  consumer demands, never sockets. Measured: 1 venue socket for one client with
  three live panels, still 1 with a second client on the same pair.
- **Release.** A pair switch or universe switch releases the previous pair's
  channels at once; the connection closes after a 30 s idle linger (measured:
  0 sockets after 30 s).
- **No OpenD hold.** The S4 service keeps OpenD's 60 s minimum subscription
  hold for US equities; Kraken acknowledges unsubscribes immediately, so the
  Crypto service uses `provider_hold_seconds=0`. Without this, the seventh
  rapid pair switch inside a minute returned `SUBSCRIPTION_BUSY` (found live in
  this session; regression-tested).
- **Reconnect.** Bounded jittered exponential backoff (1–30 s); a connection
  silent for 15 s is torn down; every demanded channel is resubscribed and
  re-anchored after a reconnect.
- **Universe switch.** A cleared selection yields no instrument to the dock in
  the same render, so a Crypto pair is never demanded or fetched against
  another universe (previously one `400 PANEL_UNAVAILABLE_FOR_UNIVERSE` per
  switch; fixed and tested).

## Source states

`CURRENT`, `AWAITING_DATA` (reason), `STALE`, `DISCONNECTED`, `MAINTENANCE`
(venue `status` channel), `CHECKSUM_MISMATCH`, `UNAVAILABLE`,
`SUBSCRIPTION_BUSY` (only at the six-pair specialist cap), and
`CRYPTO_NOT_CONFIGURED`. The Screener footer labels visible-row quotes as a
REST snapshot, never as live or unavailable.

## Panels

| Panel | Crypto |
|-------|--------|
| Charts | supported — Kraken OHLC + AUTO_SR_V1 |
| Order Flow | supported — Kraken trades, native taker side |
| CVD | supported — since subscription |
| Level 2 | supported — Kraken book, checksum-verified |
| Futures Context, Options, Short Squeeze, Rates & Curve | unavailable for this universe |

## Quick Preview

`CryptoQuickPreview` (never a Workspace): market (last, UTC-day change, 24h
base and quote volume, bid/ask, spread, 24h high/low), the 24/7 chart with
support/resistance, pair structure (status, increments, minimum order), source
clocks, and why the row matched. Long values (SHIB base volume, sub-cent
bid/ask) wrap instead of being ellipsized.

## Real acceptance (2026-09-28, live Kraken, isolated `APPDATA`)

| Check | Result |
|-------|--------|
| Populated universe | 1,354–1,355 rows, 1,328–1,330 priced; source `current · KRAKEN_SPOT_PUBLIC`; session 24/7 |
| BTC/USD | all four panels `CURRENT`; 25×25 checksummed book; real prints with native taker side; CVD since subscription; sub-bps spread shown as `0.012 bps` |
| SHIB/USD | 9-decimal prices in rows, Preview, ladder, and chart axes; `AWAITING_DATA` shown truthfully when no prints |
| USDC/USD (stablecoin) | all panels `CURRENT` |
| Reload regression | after reload and reselect: all four `CURRENT`; no "Provider refused", no "Already subscribed", no stuck checksum |
| Rapid pair switch | BTC → ETH → SHIB → USDC → SOL → XRP → DOGE → ADA → BTC in ~0.6 s steps: no refusal or busy; occupied instruments never above 1; CVD re-anchored; stale responses never rendered (payload identity guard) |
| Universe switch | Crypto → Equities → Crypto and Crypto → Bonds → Crypto: Crypto columns and Overview restored, panels re-activate `CURRENT`, Bonds shows Crypto panels unavailable, zero cross-universe requests, venue socket closed while away |
| Saved screen / URL | Performance view + search + `24h Quote Volume ≥ 1,000,000` + sort UTC day ascending saved; reopened from `?screen=` alone with universe, view, filter, and sort restored; reload / back / forward exercised |
| Not configured | honest unavailable state; no rows or values |

## Visual acceptance

Captured with headless Chromium at 1920×1080, 2560×1440, and 1100×800:
populated Overview, Performance, Liquidity, Custom; BTC/USD, SHIB/USD, and
USDC/USD Preview with all four panels; the not-configured state; the narrow
layout (Preview becomes an overlay; the ladder scrolls horizontally). Defects
found and fixed during acceptance, each with a regression test:

- footer said "Quotes unavailable" for valid REST snapshot quotes;
- Order Flow / L2 sizes, and later Order Flow tiles and CVD totals, rounded
  fractional base units to 0;
- Preview key/value layout, then ellipsized long values;
- `24_7` shown raw (now **24/7**);
- misleading Crypto filter labels;
- SHIB-class price precision truncated;
- L2 spread `0.0 bps` for a real 0.012 bps spread;
- screen-reader captions and column resize handles named the internal id /
  equity label instead of the pair / displayed header;
- CVD chart axis used a fixed 2-decimal format;
- the footer read local time while every other Crypto clock reads UTC.

## Performance (live, same machine, cold API)

| Operation | Measured |
|-----------|----------|
| cold first page (catalog + all-pair ticker) | 898 ms |
| warm first page | 80 ms |
| forced refresh (new snapshot) | 726 ms |
| search `BTC` | 137 ms |
| filter + sort over the complete snapshot | 74 ms |
| page 2 (offset 200) | 61 ms |
| Preview cold (bars fetch) / warm | 452 ms / 147 ms |
| Charts 5m cold | 390 ms |
| panel demand (three live panels) | 40 ms |
| book subscribe → L2 `CURRENT` | 1,487 ms |
| trade subscribe → first print (BTC/USD) | 211 ms |
| pair switch BTC → ETH → L2 `CURRENT` | 239 ms |
| second client, same pair | 4 ms, no new subscription |
| universe switch release | 3 ms |
| venue sockets | 0 idle → 1 active (any number of panels/clients) → 0 after 30 s |

Bundle impact (production build, S9 head built side by side):

| Chunk | S9 | S10 |
|-------|----|-----|
| initial (budget-checked) | 201.37 KiB gzip | 201.39 KiB gzip |
| lazy `ScreenerPage` | 50.07 KiB gzip | 55.28 KiB gzip |
| lazy `ScreenerDock` | 111.64 KiB gzip | 110.52 KiB gzip |

Crypto code lives in the lazy Screener chunks; the initial bundle is
unchanged within 0.02 KiB and inside the budget.

## Tests

| Suite | Coverage | Result |
|-------|----------|--------|
| `tests/crypto_market` (new, manifest suite 71) | WebSocket handshake/`Sec-WebSocket-Accept`, masking, fragmentation, ping/pong, bounded frames, close; Kraken book checksum over the captured fixture; snapshot/delta/truncation; `CHECKSUM_MISMATCH` + resync; reconnect/backoff/re-anchor; depth-qualified unsubscribe and resubscribe; maintenance | 26/26 |
| `tests/platform/test_screener_s10.py` | exact five-universe registry; catalog/ticker projection (UTC-day change, rolling volume, missing stays missing, venue precision); snapshot filters/paging/partial-ticker refusal; weekend bars; preview/chart provenance; panel matrix; not-configured runtime; rapid pair switching without an OpenD hold | 16/16 |
| Screener S1–S10 backend | all ten Screener suites incl. the S4 specialist service and S9 registry pins (`NEWS` added to the forbidden list) | 282/282 |
| `tests/order_flow` | canonical book engine incl. `CHECKSUM_MISMATCH` invalidation | 156/156 |
| `tests/market_data/test_g10_depth_freshness` | depth freshness incl. the Kraken L2 policy | 13/13 |
| `tests/xa01` | identity incl. `CRYPTO_PAIR` venue qualification | 72/72 |
| `Crypto.test.tsx` | URL restore, headers and resize labels, REST snapshot footer, UTC footer, filter labels, Preview, panel matrix, taker-side Order Flow, checksum book, 24/7 chart, cross-universe demand guard, not-configured message, volume/spread formatting helpers | 13/13 |
| Full UI suite | 152 files | 1,111/1,111 |

## Validation

`python tools/imp.py validate changed` ran with isolated `APPDATA` and the
repository venv: **5,906 tests, 35 skipped, 0 failures, 0 errors, exit 0** in
299.202 s. The runner reported `perf=INSUFFICIENT_DATA` and
`core_checkpoint_required=true`; neither is reported as a performance pass or
a completed full-suite checkpoint. The standalone intelligence suite passed
2,181 tests with 27 skips after correcting the runner to use the repository
venv, which provides Windows `tzdata`.

The required full checkpoint then passed with one worker and isolated
`APPDATA`: **7,177 tests, 52 skipped, 0 failures, 0 errors, exit 0** in
652.143 s. Its performance comparator reported `INCOMPATIBLE_BASELINE`,
not a performance pass. An earlier concurrent full attempt was interrupted
after `ui2` reported an error; `ui2` passed 5/5 alone and in the serial full
run. The failed attempt remains distinct from the successful serial run.

The current-source frontend run passed **1,111/1,111 tests across 152 files**;
`npm run typecheck`, `npm run build`, and the bundle budget check passed. The
initial bundle was 201.39 KiB gzip. The earlier live Kraken and visual
acceptance in this document was performed before closure and is not a claim
of a new live probe in this final validation run.


## Security

The Kraken client connects only to the allowlisted `wss://ws.kraken.com/v2`
host over TLS. Its stdlib handshake validates the server accept key; client
frames are masked, incoming frames and messages are bounded, and ping/pong,
close, reconnect, and subscription cleanup are handled by the shared runtime.
The REST and WebSocket paths use public market data only: no credentials,
account state, order submission, custody, or Live trading authority is added.
The provider-off state fails closed and reports unavailable data explicitly.

## Limitations

- One venue. Crypto rows are Kraken's market, not a consolidated crypto price;
  Coinbase is deferred (above).
- UTC-day change only; Kraken publishes no rolling-24h open in its ticker.
- The Kraken ticker has no event timestamp; quotes carry receipt time.
- Visible-row quotes are the REST snapshot (≤ 20 s old), not a streamed
  top-of-book; streaming is limited to the selected pair's panels.
- CVD and Order Flow cover only the time since subscription.
- The specialist panels hold at most six distinct instruments across clients.
- Pre-existing S1 URL behavior, unchanged by S10: navigating back to a URL
  without `view` keeps the current view rather than restoring the saved
  screen's view.
