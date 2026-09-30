# Main Screener — final completion and closure

This closes the Main Screener program (S1–S16). The last S14, S15, and S11
residuals were fixed where a fix was sound, or given a recorded decision where
it was not. The five universes (US Equities, US ETFs, Futures, Bonds, Crypto)
were then accepted together against live providers on 2026-09-29. Out of scope:
no sixth universe, no Options or Commodities universe, no execution, alerts,
automation, or Workspace work.

Earlier documents: [S11 News](SCREENER_S11_NEWS.md),
[S14 Disclosure Coverage](SCREENER_S14_DISCLOSURE_COVERAGE.md),
[S15 CFTC Coverage](SCREENER_S15_CFTC_COVERAGE.md),
[S16 Fixed Income](SCREENER_S16_FIXED_INCOME_EXPANSION.md),
[Universe architecture](SCREENER_UNIVERSE_ARCHITECTURE.md).

## Residuals closed

| Residual | Before | Final |
|----------|--------|-------|
| Mixed-chamber Congress coverage wording (S14) | One sentence started from the House filing count, but its "have no ticker" figure also counted Senate transactions | Two sentences, one for filings and one for transactions. House counts filings (documents); both chambers count transactions; the figures are never mixed. The counts follow the selected window (`window_counts`), not the loaded one |
| Congressional identity (S14) | Official ids matched only on exact surname plus current seat | Two more registry rules, both anchored on official term data and the given name, never on similarity. A **compound surname** the House index splits resolves: "April McClain" / "Delaney" → Bioguide "McClain Delaney". A **prior seat** also resolves: an index still stating a pre-redistricting district, when exactly one same-name member of that state's delegation held that seat before. That case carries the note `SOURCE_SEAT_IS_AN_EARLIER_TERM`. The official full given name ("Richard" for "Rich") counts as a nickname |
| Release schedule (S15) | Loaded for 2026 only; other dates used Tuesday + 3 days | `ReleaseCalendar`: the vendored official tables, extended by every year on the live CFTC schedule page (cached for 24 h, never blocking). A date no official table covers is inferred: Tuesday + 3 days, or, when a federal holiday falls Tuesday–Friday, the next business day after that Friday (`PUBLICATION_TIME_INFERRED_HOLIDAY_DELAY`; every 2026 holiday delay was exactly that, so the inference is never earlier than the likely release). `release_schedule.state` reports `CURRENT`, `PENDING`, `SOURCE_ERROR`, or `VENDORED_ONLY` |
| Known market not in recent releases (S15) | "Not in recent releases", with no date | `last_report`: one cached grouped Socrata query (`$group`) per report family, for all of that family's mapped codes. It is never per root and never an unbounded scan. The result shows the last report date and its release time ("release time inferred" when inferred). States: `LAST_REPORT_FOUND`, `PENDING`, `NO_REPORT_FOUND` (`NOT_YET_PUBLIC` when the release time is still in the future), `SOURCE_ERROR` |
| Coverage labels (S15) | Lower-casing turned "CFTC" into "cftc" | Only ordinary words are lower-cased, so acronyms keep their case |
| Bonds News index (S11 × S16) | News paged the whole Bonds universe (318k rows since S16) and cut off at 20,000 rows, missing most Treasuries | News reads `treasury_rows()`: every outstanding Treasury from the same cached projection |
| Crypto news false positives (S11) | "exchange", "outage" and "SEC charges" alone put a story in the Crypto group (a Spotify outage was counted as a crypto-exchange story) | `crypto.regulation`, `crypto.exchange`, and `crypto.protocol` also need a crypto anchor term (for example bitcoin, ether, stablecoin, token, Coinbase, MiCA). In the live pass, Crypto went from 27 to 24 stories |
| Stopped OpenD froze Screener reads (found in acceptance) | The vendor `OpenQuoteContext` constructor retries a refused connection indefinitely, and every transport call is serialized. One equity or futures preview could therefore hang for more than 60 s and block the other quote-path reads | `OpendCurrentKlineSession` probes the loopback port first (0.4 s), returns `OPEND_UNAVAILABLE`, and drops a stale context, so a restarted OpenD gets a fresh one. Futures Context no longer caches a provider outage as a contract resolution for 30 minutes |

## Decisions (not implemented, with reasons)

- **OCR of scanned PTRs: stays `SCANNED_UNPARSED`.** On real 2026 scanned House
  PTRs, Tesseract read the printed labels (median word confidence about 96). No
  word reached the 0.98 row-admission threshold, and it could not read the
  amount-band check marks or the handwritten entries (document 8221360).
  Guessed disclosures would be worse than a link to the Clerk PDF.
- **House amendment linkage: stays unlinked.** Neither the Clerk index nor the
  PTR form names the report an amendment replaces. Any link would be inferred.
- **Futures venue: stays missing where the provider has none.** 93 of 178 roots
  have no provider exchange. The mapping rests on CME Group product codes, and
  the CFTC market's exchange is shown beside it. No venue is guessed.
- **Universe switch keeps the search term.** This is the S5 contract ("changing
  universe clears screen, view, sort, and filters … and keeps search"). A
  search that has no rows in the new universe shows zero results. That is
  not a defect.
- **FinBERT, NewsAPI, Finnhub, AI synthesis: `NOT_CONFIGURED` or
  `LIVE_DISABLED`.** No local model, keys, or opt-in are on this workstation.
  Each states its reason (`IMP_FINBERT_MODEL_PATH_NOT_SET`,
  `IMP_NEWSAPI_LIVE_NOT_SET`, `IMP_FINNHUB_LIVE_NOT_SET`,
  `ANTHROPIC_API_KEY_NOT_SET`). No model files are committed.
  *Superseded 2026-09-30:* local FinBERT and local AI synthesis are active, and
  NewsAPI (`DELAYED`) and Finnhub need only free owner keys. See
  [SCREENER_FREE_CAPABILITY_ACTIVATION.md](SCREENER_FREE_CAPABILITY_ACTIVATION.md).

## Live acceptance (2026-09-29)

SEC access used a User-Agent set in the API process environment only. It is in
no file, commit, or log. OpenD was stopped from 14:56 to about 20:00 ET and
then restarted by the owner. Both states were observed.

### Universe first page (cold → warm)

| Universe | Rows | Cold | Warm |
|----------|------|------|------|
| US Equities | 4,625 | 1,457 ms | 96 ms |
| US ETFs | 5,738 | 3,015 ms | 93 ms |
| Futures | 178 | 1,149 ms | 88 ms |
| Bonds | 318,388 | 13,254 ms | 145 ms |
| Crypto | 1,355 | 767 ms | 110 ms |

### Institutional and government

- **Futures positioning:** 67 mapped to a CFTC market, 77 single-stock futures
  (no COT market), 33 with no CFTC market, 1 ambiguous (VXM, one VIX market that
  does not state whether Mini VIX is included), 0 unclassified. 61 roots had a
  report in the last 35 days.
- **Last reports:** ALI, MHG, MXP, NKD, QG, and SIL each show their last report.
  Two had an inferred release time: QG 2024-08-27 (Tuesday + 3 days) and MXP
  2025-12-23, released 2025-12-29 (holiday delay). The release schedule moved
  from `PENDING` to `CURRENT` from the CFTC page.
- **Congress (US Equities, 60 days):** 79 House PTRs (67 machine-readable, 12
  scanned) and 762 House plus 34 Senate transactions. Of those, 610 match the
  universe, 67 name other tickers, and 119 have no ticker. Senate identities: 34
  official, 10 unresolved. April McClain Delaney (MD-06) resolves.

### News (universe scope, all `CURRENT`)

| Universe | Stories |
|----------|---------|
| US Equities | 50 shown (95 matched) |
| US ETFs | 17 |
| Futures | 30 |
| Bonds | 5 |
| Crypto | 24 |

- **Providers:** Finviz (100 items) and RSS (SEC press, CNBC, MarketWatch,
  Federal Reserve, CoinDesk, Cointelegraph).
- **Instrument scope:** SEC filings are `CURRENT` (NVDA: 40 filings).
  NewsAPI, Finnhub, FinBERT, and AI synthesis state their not-configured
  reasons.

### Campaign

| Check | Result |
|-------|--------|
| Rapid universe switching (8 switches, 150 ms apart) | Final grid, URL, and preview agree; earlier requests are aborted |
| Rapid instruments: NVDA→AAPL→LMT, SPY→TLT→GLD, ESZ26→CLX26→GCZ26, Treasury 91282CCZ2→corporate 059578AF1→municipal 594712WY3, BTC/USD→ETH/USD→SOL/USD | Every preview settles on the last instrument, with its own bars, levels, or reference terms. A stale fund value is labelled stale; futures bars are labelled unverified |
| Saved screens in all five universes | Saved, restored from another universe (view and columns intact), survived a hard reload and an API restart, then deleted |
| URL / back / forward | Back and forward across five screens restore universe, view, and columns. `screen` wins over a conflicting `universe` |
| Provider disconnect / reconnect | OpenD stopped: catalogs stay `DEGRADED` on the last good copy. After the fix, previews answer in 0.07–1.6 s with `OPEND_UNAVAILABLE` / `BAR_SOURCE_UNAVAILABLE`. OpenD restarted: the next reads reconnected with no IMP restart |
| Bounded stability | 40 browser universe switches: JS heap back to 27 MB after collection (29 MB at start), 989 DOM nodes. API: 30 universe/news cycles and 10 previews moved the working set from 775 to 782 MB, with threads constant at 22 |
| Viewports 1920×1080, 2560×1440, 1100×800 | No page-level horizontal scroll. The grid, panel launcher, and status footer scroll inside their own containers at 1100 px. At 1440 px tall the grid fills the height |
| Accessibility | Named grids and view tablists in every universe, `aria-sort` on the sorted column, labelled inputs, no unnamed buttons. `/` focuses search; arrow keys move the row selection; Enter opens Preview |
| Data truth | Missing values are `UNAVAILABLE`, never zero. Levels use the last-bar close and its own clock (LMT after hours: $513.50 vs the $512.21 snapshot, each labelled). News and positioning show only releases public at the time |

## Validation

| Gate | Command | Result |
|------|---------|--------|
| Screener backend and final closure | `python -m unittest tests.platform.test_screener_* tests.cftc.test_final_closure_release_calendar tests.market_trackers.test_final_closure_congress_identity tests.fixed_income.test_final_closure_bonds_news_index tests.news.test_s11_news_domain` | 481 passed |
| OpenD transport neighbours | `tests.providers.test_moomoo_opend_primary_l1`, `test_opend_history_kline_1m`, `test_opend_hop_interpreter`, `tests.market_data.test_live_p21`, `tests.platform.test_bar_ohlcv_prospective_proof` | 109 passed |
| UI | `npm test` | 1,182 passed, 156 files |
| Typecheck / build | `npm run typecheck` / `npm run build` | exit 0 / exit 0; initial 201.40 KiB gzip |
| Changed domains | `python tools/imp.py validate changed` (isolated `APPDATA`/`LOCALAPPDATA`) | 5,269 tests, 34 skipped, 0 failures, 0 errors |
| Full | `python tools/imp.py validate full` (isolated, sequential) | 7,588 tests, 52 skipped, 0 failures, 0 errors (444 s; flagged against a 2026-09-12 baseline of 199 s with fewer tests. Earlier full runs on this host the same day took 318 s and 709 s) |
| Closure | `python tools/imp.py closure` | exit 0: full 7,588 tests, 0 failures, 0 errors; format and docs links passed; risk `review_required`, no live-execution or paper-authority change. Its UI step matched no `ui/` paths (it compares against repository-relative paths), so the UI gates above were run directly |

## Limitations outside the Screener

- **Live equity quotes.** The live observational runtime's equity quote window
  returned `AWAITING_QUOTE` in the session, although the vendor snapshot and
  subscriptions answered. The Screener shows "Quotes unavailable". The cause is
  in live-runtime admission, not the Screener, and is tracked separately.
- **Provider health view.** `/provider/health` returns
  `UI_SECRET_LEAK_BLOCKED`: a Finviz field name trips the UI secret guard, so
  Live Watch shows Provider/Connection as Unavailable. Also tracked separately.

## Remaining known limits

- Senate eFD still needs the owner to accept the terms and save report pages.
- Scanned PTRs are links only (see Decisions).
- There are no current bond prices (licensing, S16), and futures quotes need a
  futures entitlement.
- Registry-dependent: without `IMP_CONGRESS_LEGISLATORS_PATH`, Senate
  identities stay `UNRESOLVED`. *Superseded 2026-09-30:* a cached CC0
  registry refresh now resolves all 44 Senate transactions to official ids
  ([SCREENER_FREE_CAPABILITY_ACTIVATION.md](SCREENER_FREE_CAPABILITY_ACTIVATION.md)).
