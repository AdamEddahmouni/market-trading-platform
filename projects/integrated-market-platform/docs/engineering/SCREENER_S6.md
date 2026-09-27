# Main Screener S6 — server-side querying, paging, and market-filter truth

S6 moves the Main Screener from "load the whole universe, sort and filter in
the browser" to one canonical query executed on the server, returned in
bounded pages, and enriched with live quotes only for visible rows. It also
makes market fields filterable where — and only where — the server can
evaluate them for every row of the universe. The universes are unchanged from
[Main Screener S5](SCREENER_S5.md): US Equities, Futures, US ETFs.

## Canonical query

`ui_api/screener_query.py` owns the provider-neutral `ScreenerQuery`:
`universe`, validated `filters`, `search`, `sort`, `descending`, `offset`,
`limit`, plus two optional page fields: `result_set` (which result set a later
page continues) and `selected` (report the selection's position).
`parse_query` rejects an unknown universe, field, or operator, a sort or
filter on a field the universe cannot evaluate, `offset < 0`, `limit` outside
1–500, and a search longer than 80 characters. Both services (`ScreenerService`
for US Equities, `MultiUniverseScreener` for Futures/ETFs) execute it.

`GET /screener` parameters: `universe`, `search`, `sort`, `descending`,
`filters` (JSON), `offset`, `limit` (default 200), `result_set`, `selected`,
`refresh`. Provider codes never appear in the query.

## Ordering

`order_rows` is the only Screener ordering, used by every universe: present
values by direction (text case-insensitive), missing values last in both
directions, ties broken by canonical instrument id ascending. The browser no
longer sorts anything, so Python and TypeScript cannot disagree about nulls.

## Pages and counts

Each response carries `result_count` (rows matching the query),
`unfiltered_count` (universe size), `offset`, `limit`, `returned`, `has_more`,
`query_id`, and `result_set_id`. A later page passes `result_set` and is
served from exactly the catalog (and snapshot) the first page was ordered
from, so adjacent pages never duplicate or skip rows. The server retains the
current and previous catalog projection per universe, the current and previous
Finviz export, and the last three ETF snapshots; a page whose result set is
gone gets `409 SCREENER_RESULT_SET_CHANGED`, and the UI restarts the chain at
page 1 while keeping loaded rows on screen. Ordered results are cached as
row references (at most 16 per service), never row copies.

Page size is 200 rows (≈228 KB for ETFs; 100 rows ≈114 KB, 250 ≈285 KB,
500 ≈568 KB). At 34 px per row that is six screens of 1440p scrolling per
request, with the next page requested 60 rows before the loaded end.

The footer distinguishes matched from loaded (`6,306 results · 200 loaded`).
When a query cannot run, the footer shows `— results`, never `0`.

## Field execution modes

Every field declares how the server can evaluate it per universe
(`FIELD_EXECUTION`), and `/screener/config` publishes it per universe as
`fields: {field: {execution, sortable, filterable}}`:

| Mode | Meaning | Sort / filter the universe |
|------|---------|----------------------------|
| `CATALOG` | Complete universe metadata the server holds | yes |
| `SNAPSHOT` | One universe-wide market snapshot at a known time | yes |
| `LIVE_WINDOW` | Current quotes for visible/selected rows only | no — display only |
| `UNAVAILABLE` | No source | no |

| Universe | CATALOG | SNAPSHOT | LIVE_WINDOW |
|----------|---------|----------|-------------|
| US Equities | symbol, company, sector, industry, country, earnings date, recommendation | Finviz export fields (price, change %, volume, RVOL, float, market cap, short float, RSI, …) | bid, ask, spread % |
| Futures | symbol, description, root, exchange, month, expiry, DTE, lead, tick, multiplier | — | price, change %, volume, open interest, bid, ask, spread % |
| ETFs | symbol, name, exchange | price, change %, volume, bid, ask, spread % (OpenD snapshot) | — |

The filter picker offers only catalog entries for the universe, and every
catalog entry is `CATALOG` or `SNAPSHOT` (tested). Column headers are sortable
only when the server says so; a live-window column still renders but shows no
sort affordance and explains why. A saved screen or link that sorts by a
window-only field keeps its configuration and is ordered by the universe
default. Equity bid/ask/spread sorting, which S1–S5 did in the browser over
only the quoted visible rows, is removed for that reason.

## ETF market snapshot

`ui_api/screener_snapshot.py` builds one snapshot of every catalog ETF with
OpenD `get_market_snapshot` (400 codes per call, the vendor maximum). The
provider's ETF catalog includes a few OTC listings that the account may not
quote; the vendor then refuses the whole batch and names the code
(`US OTC market quote is not available for BCHG.`). The transport returns that
as `refused_codes`; the builder removes it and retries, and remembers it so
later builds skip it.

The snapshot is **complete** only when every catalog row was either returned
or refused by name. Any other failure — disconnect, protocol error, rows
silently missing, or more than 50 calls — makes it unusable: a query that
sorts or filters on a snapshot field then returns no rows with
`source_error` (`MARKET_SNAPSHOT_*` or the provider reason) and the UI says the
market snapshot is unavailable. It never evaluates a partial set, and the
visible-row quote window never feeds it. Catalog queries keep working.

Values: price is the last price (> 0), change % against the previous close,
volume, bid, ask, spread % from bid/ask. A row whose provider update time is
older than seven days is treated as unpriced. Refused and unpriced rows fail
every market filter and sort last.

Observed 2026-09-27 (Sunday, market closed), real OpenD: 6,306 ETFs; 6,289
returned, 17 refused (`MOOMOO_QUOTE_NOT_ENTITLED`), 6,264 priced; 33 calls in
3.2–3.9 s on the first build (16 calls once refusals are known). `Price > 100`
matched 407 ETFs.

### Freshness and refresh

- A snapshot is taken only when a query sorts or filters on a snapshot field.
- A new result chain reuses a snapshot younger than 60 s; explicit refresh
  cannot re-snapshot within 15 s; a failed build is not retried for 30 s.
  At most one build runs at a time, below the vendor's 60 snapshot requests
  per 30 s.
- Later pages always use their chain's snapshot. The Screener's existing
  2-minute refetch restarts the chain, which may take a new snapshot.
- Rows keep snapshot order until that refresh; visible-row quote updates change
  the displayed values but never reorder rows.

### Two clocks

The response carries `snapshot` (`id`, `as_of`, coverage counts) and
`screener_as_of` = snapshot time, separately from `universe_as_of` (catalog
time) and from each streaming quote's own clock. Snapshot cells are labeled
`MOOMOO_OPEND_SNAPSHOT · SNAPSHOT` with the provider's per-row update time;
the footer shows `Market snapshot 3:02:08 PM · 6,264 of 6,306 priced`.

### Why it matched

Rows evaluated from a snapshot carry `snapshot_id`. Quick Preview sends it
with the preview request, so "Why it matched" explains the value that was
filtered on — e.g. `Price $1,008.08 is above $100.00 (market snapshot, quote
Sep 25 19:30:06 ET)` — even if a later streaming quote has crossed the
threshold. Finviz equity explanations are unchanged.

## Futures

A fresh probe on 2026-09-27 still returned `MOOMOO_QUOTE_NOT_ENTITLED`
(`Insufficient quote permission`) for ES, NQ, CL, GC. Futures market fields
therefore stay `LIVE_WINDOW`: not sortable, not filterable, and shown as
unavailable. Catalog filters, search (symbol, description, root), and sorts
(DTE, expiry, root, …) run on the server over the 178 lead contracts. Expiry
and lead status are re-derived whenever the trading date changes, including
for pinned pages.

## Frontend

- `useInfiniteQuery` keyed by the canonical query; each page fetch passes the
  abort signal, and responses whose universe or offset differ from the request
  are rejected. A changed search, sort, filter, or universe starts a new chain,
  so a late page from the old query can never be appended to the new one.
- Rows from all pages are merged by instrument id (duplicates dropped). The
  virtualizer adds one in-table row for "Loading more results…" or, after a
  failed later page, "Could not load more results · Retry"; loaded rows stay.
- Keyboard navigation continues into appended rows.

## Selection, Preview, panels, subscriptions

- The first page of a chain reports the selection's position
  (`selected_index`). A selection still matched but not loaded stays selected;
  Preview and the S4 dock use the cached row, not page presence. A selection
  the new query excludes is cleared (S3 rule).
- The quote window is the visible rows plus the selection (cap 32). Loaded
  rows are not subscribed; rows scrolled away leave the window on the next
  update. Universe switches release the window as in S5; panel demand is
  unchanged (reference-counted, released when no open panel is supported).

## Saved screens and URL

No schema change. Saved screens and "Last Used" store configuration only
(universe, filters, view, sort, columns); pages, snapshots, and quotes are
never persisted, and loading a screen starts a fresh server query. S5 screens
load unchanged. The URL keeps `universe`, `screen`, `view`, `sort`, `dir`,
`q`; offsets are not in the URL. Back, forward, and reload restore the query.

A fix made here: an untouched built-in preset no longer reads as modified when
the server publishes universe views (its baseline now uses the same
universe-scoped column set as the live state).

## Performance

Real OpenD, warm, same machine:

| Measure | S5 (3bff1225) | S6 |
|---------|---------------|----|
| ETF first request | 6,306 rows, 7,170,029 B, 0.82–0.85 s HTTP | 200 rows, 227,820 B, 0.028–0.031 s HTTP; 34 ms in browser |
| Server JSON serialize / parse | ≈52 ms / ≈40 ms | 1.2 ms / 0.7 ms |
| Next page | — (everything loaded) | 0.027 s HTTP; 35–47 ms in browser while scrolling |
| Search `spy` | 0.011 s | 0.008 s |
| Sort company desc | 0.84 s (full payload) | 0.033 s |
| Snapshot sort price desc | not possible | 3.6–4.0 s first build, 0.03 s after |
| Filter `Price > 100` | not possible | 0.038 s warm (407 of 6,306) |
| Futures first request | 178 rows, 252,766 B | 178 rows, 252,987 B |

The first ETF request is 96.8% smaller and about 30× faster. Scrolling to
1,200 loaded rows kept about 36 table rows in the DOM.

Server memory (tracemalloc, real catalog): catalog fetch and projection
≈46 MB (S5, unchanged); one ETF snapshot ≈3.9 MB (up to three retained);
eight cached result orders ≈0.5 MB.

## Tests

- `tests/platform/test_screener_s6.py`: query validation and limits;
  live-window fields rejected for sort/filter in every universe; published
  capabilities; one ordering with missing values and id ties; bounded pages,
  no duplicates or gaps across every page, empty page, counts; server search,
  filter, and selection position; stale result sets; partial snapshot never
  filters (400 rows would have matched); no snapshot source with a full quote
  window; named OTC refusal; silently missing rows; pinned pages across a new
  snapshot and eviction; value mapping and staleness; "why" uses the evaluated
  snapshot; Futures catalog queries and pages; Finviz page pinning; responses
  pass the API secret-leak audit; saved-screen compatibility; transport refusal
  parsing.
- `ui/src/components/screener/ScreenerPaging.test.tsx`: bounded first page,
  incremental loading and truthful counts, overlap de-duplication, later-page
  failure and retry, result-set restart, old-query page race, universe-switch
  race and release, sort reset and no sort on a live-window column, quote
  window limited to visible rows plus selection, selection kept and Preview
  intact when its page never loads, selection cleared when excluded, keyboard
  across a page boundary, snapshot footer, and unavailable market snapshot.
- S1–S5 Screener tests updated to the query contract.

## Validation

Closure run on 2026-09-27. `powershell.exe` startup still hangs on this host
(a 25 s `-NoProfile` probe timed out, also with `APPDATA` isolated), so no
PowerShell was used; `APPDATA` was isolated for the Python gates as in S3–S5
so `check_live_environment` never reaches the hanging PowerShell call.

| Gate | Command | Result |
|------|---------|--------|
| Screener backend S1–S6 | `python -m unittest tests.platform.test_screener_s1 … test_screener_s6` | 143 passed (S6 20) |
| Screener UI | `npx vitest run src/components/screener` | 57 passed, 4 files (S6 13) |
| Full UI suite | `npm test` | 1,060 passed, 147 files |
| Typecheck | `npm run typecheck` | exit 0 |
| Build + budget | `npm run build` | exit 0; initial 201.33 KiB gzip |
| Format / lint | `python tools/imp.py format` / `lint` | exit 0 / exit 0 |
| Docs links | `python tools/check_docs_links.py` | 269 files OK |
| Changed domain | `python tools/imp.py validate changed` | exit 0 — 5,039 tests, 34 skipped, 0 failures, 0 errors; 20 suites incl. `providers`, `market_data`, `platform` |

The first full UI run had one S6 paging test time out under suite load (a
three-request restart chain against the 1 s default wait); the test's waits
were given an explicit 5 s budget, the file passed three consecutive isolated
runs, and the full suite then passed.

## Limits

- ETF market filters and sorts need a complete OpenD snapshot; when OpenD is
  down they are unavailable while the catalog still works. The first snapshot
  in a server process takes about 4 s.
- 17 OTC-listed catalog ETFs have no entitled quote and never match a market
  filter.
- The snapshot is not streaming: market filters and order refresh with the
  Screener's 2-minute refetch or an explicit retry, not per tick.
- Futures market fields stay display-only while quote entitlement is absent.
- ETF RVOL and RSI are not offered: no universe-wide source exists.
- The 2-minute refetch reloads every loaded page of the current chain.
