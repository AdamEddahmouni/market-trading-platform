# Main Screener S1

The first-class `/screener` route is a current US-equity market scan with its
own full-screen workstation layout. It bypasses the existing mode launcher,
product chrome, mode banners, and assistant. Radar and its investigation
contract remain separate and unchanged. The Screener opens an instrument
through the canonical encoded Workspace route; that destination still uses
the existing mode architecture until separately changed.

## Data contract

`GET /screener` accepts `universe=US_EQUITIES`, `search`, `sort`,
`descending`, `offset`, and `limit` (up to 10,000). The response version is
`screener/1.0.0`; it includes generation time, current US-equity session,
universe and screener as-of time, total matching count, provider health, source
error, and rows. Each row carries canonical instrument ID, venue, asset class,
symbol, company, and normalized fields with individual source/state/as-of
metadata. The public contract contains no Finviz filter syntax.

The normal path requests Finviz Elite's US stock export
(`geo_usa,ind_stocksonly`) with explicit columns for company, sector,
industry, market cap, float, short float, RSI, RVOL, price, change, and volume,
and uses the existing normalized CSV parser. The current CSV emits bare
Market Cap and Shares Float values in millions; normalization converts those
to dollars and shares, while suffixed values retain their stated scale. It
does not use discovery candidates, saved captures, replay, or fixtures. A
failed initial source request yields an unavailable response. If a refresh
fails after success, the previous snapshot remains visible with degraded
health and its original as-of time. Requests are cached for 120 seconds. An explicit Retry bypasses the Screener
snapshot cache and asks the real source again. Sorting and search operate on
the broad snapshot before windowing.

Price, change, volume, RVOL, float, market cap, short float, and RSI are
publication-style Finviz snapshot fields. Short float is **not** a live borrow
feed. Missing values remain unavailable. Bid, ask, and spread require an
admitted current L1 quote; missing quotes remain unavailable. A current quote
may update price or volume while its own field state remains LIVE. Stale quotes
are not promoted into current cells. Quote age and source are carried in the
window response. The page gets session wording from the backend's
`us_equity_session_label` authority.

## Bounded quote window

`POST /screener/window` takes a client ID and at most 32 unique canonical
instrument IDs from the current source universe. The backend reconciles
`BASIC_QUOTE` subscriptions for only that client's visible and selected
rows. Scroll/search/sort changes release displaced symbols before acquiring
new ones. The page polls the viewport every three seconds and calls
`POST /screener/window/release` on unmount and makes a keepalive release on
page exit. The backend also expires inactive client windows after 45 seconds.
Other runtime consumers' references are untouched. If the live
runtime or entitlement is unavailable, snapshot fields stay present and quote
fields show unavailable.

## UI and limits

The Overview grid uses TanStack Table and Virtual. It supports dense columns,
sticky headers, click-to-sort, search by symbol/company, selected row,
arrow navigation, Enter handoff, slash search focus, and explicit load,
empty, source error, and quote degradation states. Numerics use tabular
alignment. The footer separates quote state from universe freshness.

S1 has one universe and one view. It has no filter builder, saved screens,
column manager, preview, panels, order controls, or sparkline. The Finviz
source supplies a broad export but does not guarantee every listed US
instrument. Bid/ask/spread sorting uses only currently enriched rows; rows
without admitted quotes sort last. A server process restart loses its
in-memory snapshot and subscription map, then repopulates from the real source.

Focused tests: `tests/platform/test_screener_s1.py`,
`ui/src/components/screener/ScreenerPage.test.tsx`, App routing and NavShell
tests. The normal UI build includes the bundle budget check.
