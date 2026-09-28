# Main Screener S7 — current options context

S7 adds current options intelligence for the **one selected Screener
instrument**: an Options specialist panel in the S4 dock and a compact Options
tab in the S3 Quick Preview. Both read a real current option chain or state
why none is shown. Options are selected-underlying context, not a universe:
the Screener universes remain US Equities, Futures, and ETFs
([Main Screener S5](SCREENER_S5.md)), and no options field is filterable,
sortable, or a table column ([Main Screener S6](SCREENER_S6.md)).

## Source

| Source | Probe (2026-09-27, Sunday, market closed) | S7 role |
|---|---|---|
| Finviz Elite options export (`/export/options?t=`) | Configured; SPY 13,994 rows, AAPL 3,754, BRK-A header only | Current chain for the panel and Preview |
| Moomoo OpenD 10.10.7008 `get_option_chain` / `get_option_expiration_date` | Both refused: "No permission to get quotes for US.AAPL. Please check US MarketOptions quote permissions." | Not used (not entitled) |
| Cboe public options statistics | Market-wide aggregate volume only | Not used: no contract bid/ask, IV, Greeks, or chain OI |

The export is fetched through the existing `FinvizOptionsClient` and the shared
Finviz request manager, so rate spacing (5 s), the 300 s response cache,
single flight, auth recovery, and credential redaction are unchanged. The
credential is never part of a response, log line, or diagnostic. No new
provider or dependency was added.

**Where the provider is resolved.** `FinvizOptionChainProvider`
(`providers/adapters/finviz_option_chain.py`) implements the existing
`OptionChainProvider` protocol. The Screener service resolves it directly
(`screener_options.current_option_chain_provider`) and never reads
`ProviderComposition.option_chain`: that slot is the research/replay chain,
fixture-backed after `bootstrap_default_providers`, and a default composition
must stay stubs only (ADR-PROV-001, `tests/providers/test_providers.py`). The
Options Workspace and its fixture paths are untouched. As defence in depth the
Screener refuses any provider id containing `fixture`, `replay`, or `demo`
(`NON_CURRENT_PROVIDER_REFUSED`).

## Observed provider fields

Columns returned for every probe: `Contract Name, Last Trade, Expiry, Strike,
Last Close, Bid, Ask, Change $, Change %, Volume, Open Int., Type, IV, Delta,
Gamma, Theta, Vega, Rho`. Observed semantics:

- `Type` is `call`/`put`; `Contract Name` is the OCC symbol
  (`SPY270115P00050000`); `Expiry` is `M/D/YYYY`; `Last Trade` is ET
  (`9/18/2026 3:30:10 PM`).
- `IV` is a decimal fraction (SPY median 0.2414 = 24.1 %); `-1` and `0` are
  sentinels for "no IV" (1,658 of SPY's rows had a blank IV and Greeks).
- `Volume` is always supplied; `0` is the provider's own zero. It is the
  latest session's volume (Friday's on a Sunday).
- `Bid`/`Ask` may be blank (SPY: 2,001 blank bids, 1,308 blank asks). No
  crossed markets were observed.
- Expired expiries are included (SPY 9/21–9/25 on 9/27).
- No snapshot-level "as of" time is supplied.

`Change $`/`Change %` are not mapped (`Change %` showed `-50.00%` on unchanged
contracts); they are listed as `unmapped_columns`.

## Normalization

Provider strings are parsed once, in `normalize_row`; the browser never parses
provider text. Blank means unavailable (`null`, shown as `—`), never zero.

| Field | Rule |
|---|---|
| `type` | `CALL`/`PUT`; anything else drops the row (`INVALID_TYPE`) |
| `strike` | positive number, else dropped (`INVALID_STRIKE`) |
| `expiration`, `dte` | ISO date; unparseable → `INVALID_EXPIRY`; `dte` = calendar days from today (ET) |
| expired | `expiration < today`, or today after 16:15 ET → excluded and counted (`expired_excluded`) |
| identity | `option_id` = canonical `OptionContract.option_id` (`AAPL20261002C00250000`, same builder as the O1 fixtures); `provider_symbol` = OCC name. An OCC name whose date, side, or strike disagrees with the columns drops the row (`IDENTITY_MISMATCH`); a repeat is `DUPLICATE_CONTRACT` |
| `bid`, `ask`, `last` | non-negative price; negative → `null` + `INVALID_PRICE_FIELD` |
| `volume`, `open_interest` | non-negative integer; negative/fractional → `null` + `INVALID_VOLUME`/`INVALID_OPEN_INTEREST` |
| `iv` | decimal fraction; ≤ 0 or unparseable → `null` + `IV_INVALID` |
| `delta` | supplied value; \|Δ\| > 1 or sign against the side → `null` + `GREEKS_INCONSISTENT` |
| `gamma`, `theta`, `vega`, `rho` | supplied values only; no Greek is calculated |
| `mid`, `spread`, `spread_pct` | only with both sides and `ask > 0`: `(bid+ask)/2`, `ask−bid`, `spread/mid×100` |

Per-contract quality flags reuse `OptionQualityFlag` (`CROSSED_OPTION_MARKET`,
`NO_TWO_SIDED_MARKET`, `ZERO_BID`, `WIDE_OPTION_SPREAD` above 25 % of mid as in
the options-lane liquidity gate, `IV_INVALID`, `GREEKS_INCONSISTENT`). One new
chain flag, `OPTION_CHAIN_INCOMPLETE`, is set when any provider row was
dropped. A malformed row never fails the chain.

## Contract: `GET /screener/options`

Query: `instrument` (canonical Screener id), `universe` (`US_EQUITIES` or
`US_ETFS`; `FUTURES` → 400), `view` (`chain` or `summary`), optional
`expiration` (ISO), optional `snapshot` (ETF snapshot id). An instrument not
in the universe → 404. Read-scoped like the other Screener GETs.

```text
screener-options/1.0.0 {
  instrument_id, universe, symbol, view, market_session, capability,
  provider { id, label, delivery: "SNAPSHOT" },
  state, reason,
  clock { fetched_at, age_ms, provider_as_of: null, latest_contract_trade_at,
          refresh_after_s, stale_after_s, provider_latency_ms, provider_cache_hit },
  underlying { price, source, state, as_of } | null,
  completeness { provider_rows, usable, dropped, dropped_reasons, expired_excluded, unmapped_columns },
  quality_flags, fields_supplied { bid, ask, last, volume, open_interest, iv, delta, gamma, theta, vega, rho },
  expirations [{ expiration, dte, contracts, strikes, call_volume, put_volume }],
  selected_expiration, summary, expiry_summary, contracts [row…]
}
```

`contracts` holds only the selected expiry (a full SPY chain is ~12,000
current contracts); `view=summary` returns no contracts. `capability` states
`OPTIONS_UNIVERSE_QUERY: NOT_SUPPORTED` and `OPTIONS_EXECUTION_DATA:
NOT_AUTHORIZED`. The payload passes the API secret-leak audit (tested).

The browser validates it with a strict Zod schema (`api/screenerOptions.ts`):
typed numbers or `null`, IV > 0, |Δ| ≤ 1, non-negative counts, and every
contract in the listed, selected expiry. A response for another instrument,
universe, or view is rejected (`OPTIONS_IDENTITY_MISMATCH`).

## Freshness and state

The chain has its own clock. `fetched_at` is when the provider was actually
asked (a request-manager cache hit keeps the original fetch time via the new
`cache_age_s` meta); `latest_contract_trade_at` is the newest per-contract
`Last Trade`; `provider_as_of` is `null` because Finviz supplies none. The
underlying price has a separate clock: live/delayed Moomoo L1 when available,
else the row's snapshot (Finviz for equities; the latest retained OpenD ETF
snapshot for ETFs — none is built for options).

| State | When | Primary text |
|---|---|---|
| `CURRENT_SNAPSHOT` | chain present, regular session, age < 600 s | Current snapshot |
| `MARKET_CLOSED` | chain present outside 09:30–16:00 ET | Market closed · showing latest available options snapshot |
| `STALE` | age ≥ 600 s, or a refresh failed and the last good chain (≤ 30 min) is shown | Options snapshot stale |
| `NOT_CONFIGURED` | no Finviz credential | Options source not configured for this workstation. |
| `NOT_ENTITLED` | login page or HTTP 401/403 | Finviz Elite rejected the options export credential… |
| `PROVIDER_UNAVAILABLE` | HTTP/network error, rate limit, non-CSV | Current option chain unavailable. |
| `NO_CHAIN` | no contracts, or only expired ones | No current option contracts returned for this instrument. |
| `UNAVAILABLE` | non-current provider refused | Current option chain unavailable. |

Every state is a snapshot state: nothing in S7 is labelled live or streaming.
An urllib `HTTPError` raised inside the request manager is classified by its
status code; exception text (which may hold a URL) is never surfaced.

## Analytics

Computed in `chain_analytics` over current (non-expired) usable contracts,
chain-wide (`summary`) and for the selected expiry (`expiry_summary`), from
supplied fields only. A metric whose inputs are absent is `null`.

| Metric | Formula |
|---|---|
| call / put volume | Σ volume over calls / puts reporting volume |
| put/call volume ratio | put volume ÷ call volume (`null` if call volume is 0 or absent) |
| call/put volume ratio | call volume ÷ put volume (same rule) |
| call / put open interest | Σ open interest over calls / puts reporting OI |
| put/call OI ratio | put OI ÷ call OI (`null` if call OI is 0 or absent) |
| contracts, expirations, nearest expiry | counts; earliest current expiry |
| two-sided, median spread % | contracts with a valid mid; median of `spread_pct` |
| most active / largest OI | top 5 by volume / OI (ties by `option_id`), with share of same-side volume |
| volume / OI (per contract) | volume ÷ OI, `null` if OI is 0 or absent |
| nearest strike | listed strike minimizing \|strike − underlying\| (lower on a tie) in the expiry; with its call/put IV and mid; `exact` only when equal |

Volume and OI ratios are never combined. Volume/OI is an attention heuristic:
volume may be opening or closing trades, so it is not called new positions.
No wording attributes activity to participants.

## Options panel

`options` is registered through the S4 capability registry: one launcher
button (Open Panels: Order Flow | CVD | Level 2 | Charts | Futures Context |
Options), one instance (a second click focuses), layout persisted with the
others (`screener_config.PANEL_IDS`). It is lazy-loaded with the dock and
holds no streaming subscription.

- **Header:** Options · symbol · `Finviz Elite · snapshot`, the state badge,
  and `Updated Ns ago` (fetch clock, advanced locally).
- **Controls:** a native expiry `<select>` (`Oct 2, 2026 · 5d · 80 strikes`),
  defaulting to the nearest current expiry and reset on a new instrument; a
  `More columns` toggle (Last, Mid, Spread %, Γ, Θ, Vega); the underlying price
  with its source.
- **Summary:** chain-wide Call Vol, Put Vol, P/C Vol, Call OI, Put OI, P/C OI,
  Contracts, Expiries; one line for the selected expiry with the nearest
  strike's call/put IV and the median spread.
- **Chain:** a semantic table, calls | strike | puts (Δ IV OI Vol Ask Bid |
  Strike | Bid Ask Vol OI IV Δ), with columns only for supplied fields, tabular
  numbers, 19 px rows, and horizontal scroll inside the panel. The nearest
  strike is marked `◆` and centred on load; without an underlying price the
  middle strike is centred.
- **Emphasis (deterministic):** bold volume at or above the expiry's 90th
  percentile of non-zero volumes (≥ 5 samples); `▲` where volume > OI; shaded
  cells for in-the-money sides versus the underlying; italic bid/ask when the
  spread exceeds 25 % of mid. Each has a text equivalent (legend, titles,
  screen-reader labels); none relies on colour alone.
- **Footer:** source, snapshot-not-streaming, fetch and latest-trade clocks,
  and `usable of provider rows (expired excluded, malformed dropped)`; the
  legend is a collapsed `<details>`.

**Capability matrix:** US Equities — available; ETFs — available, `NO_CHAIN`
when the fund has no listed options; Futures — unavailable (the panel keeps its
slot and says so; futures options are out of scope).

## Quick Preview Options tab

A fourth tab for US Equities and ETFs (not Futures) renders only while active,
so selecting rows never requests a chain. It asks for `view=summary` after the
selection settles for 400 ms and shows nearest expiry, expiry count, call/put
volume, P/C volume and OI, total OI, contracts, nearest-strike IV, the most
active contract with its share of same-side volume, and the source line. It
never embeds the chain. **Open Options Panel** opens or focuses the panel.

## Requests and cache

- No request while neither the panel nor the Preview tab is showing; a hidden
  Dockview tab stops polling.
- The panel requests after the dock's 250 ms selection settle; the Preview tab
  after 400 ms. Queries are keyed by universe, canonical instrument, view,
  expiry, and ETF snapshot id; requests carry an `AbortSignal`; responses for
  another instrument are rejected before rendering.
- The browser re-reads the endpoint every 60 s while visible. The backend asks
  Finviz again only after 300 s (`OPTIONS_CACHE_TTL_S`); expiry switches and
  the Preview summary reuse the cached chain.
- The backend keeps normalized chains for at most 6 underlyings (least
  recently used evicted), keyed by provider id and Finviz ticker, with one
  in-flight fetch per key.

## Evidence (real provider, 2026-09-27, market closed)

| Symbol | Provider rows | Usable | Expired excluded | Dropped | Expiries | Provider latency |
|---|---|---|---|---|---|---|
| SPY (ETF) | 13,994 | 12,336 | 1,658 | 0 | 31 | 677 ms |
| AAPL | 3,754 | 3,400 | 354 | 0 | 24 | 297–4,702 ms¹ |
| NVDA | 4,090 | 3,670 | 420 | 0 | 23 | — |
| MSFT | 3,792 | 3,396 | 396 | 0 | 22 | 371 ms |
| BRK-A, CTNT | header only | 0 | 0 | 0 | 0 | → `NO_CHAIN` |

¹ The upper value includes the request manager's 5 s spacing after another
Finviz request. Every chain read `MARKET_CLOSED`; latest contract trade Fri
15:59:59 ET (SPY 16:14:59 ET). Through the HTTP endpoint: cold first open
0.66 s (MSFT); warm cached chain 11–40 ms; expiry switch 26–40 ms; SPY chain
payload 143 KB for one expiry, summary 7.6 KB.

Browser request counts (real server, 1920×1080): Options closed, eight rapid
row moves → 0 options requests; panel open, five rapid moves → 1 request (the
settled row); Preview Options tab open, five rapid moves → 1 request.

Bundle: initial 201.33 KiB gzip (unchanged from S6); lazy `ScreenerPage`
40.14 → 43.15 KiB gzip; lazy `ScreenerDock` 104.25 → 107.36 KiB gzip.

## Tests

- `tests/platform/test_screener_s7.py` (35): provider — configured chain via
  the request manager, not configured, HTTP/login-page/rate-limit/non-CSV,
  header-only, missing columns, point-in-time refusal, ticker validation,
  redaction; normalization — types, units, identity, DTE, puts, missing
  values, provider zero, IV sentinels, Greeks sign, crossed/wide/zero-bid,
  malformed rows, same-day expiry; analytics — ratios, zero/missing
  denominators, concentration, nearest strike, spread median; service —
  closed/current states, separate clocks, expiry selection and fallback,
  summary view sharing one fetch, every failure state, incomplete chain, TTL,
  last-good STALE and expiry, age STALE, bounded per-underlying cache, fixture
  refusal, leak audit; scope — capability matrix, no options filters/sorts/
  columns, layout ids, route policy, ETF snapshot reuse.
- `ui/src/api/screenerOptions.test.ts` (3): request shape, identity guard,
  malformed-value rejection.
- `ui/src/components/screener/panels/OptionsPanel.test.tsx` (11): emphasis
  threshold, state text, launcher and zero requests while closed, chain
  rendering (summary, expiry selector, calls/puts, unavailable vs zero, More
  columns, keys stay local), AAPL→NVDA race, every error state with other
  panels intact, layout restore without duplicates, ETF request, Futures
  unavailable, Preview tab laziness and handoff, settled-row request count.
- S3 Preview keyboard test updated: Options is now the last tab.

## Validation

Closure run on 2026-09-27 with Git Bash (no PowerShell) and `APPDATA` isolated
for the Python gates, as in S3–S6.

| Gate | Command | Result |
|------|---------|--------|
| Screener backend S1–S7 | `python -m unittest tests.platform.test_screener_s1 … test_screener_s7` | 178 passed (S7 35) |
| Providers / options / contracts / Finviz | `python -m unittest discover -s tests/<suite>` | 512 / OK / OK / 66 passed |
| Screener UI + options API | `npx vitest run src/components/screener src/api/screenerOptions.test.ts` | 71 passed, 6 files (S7 14) |
| Full UI suite | `npm test` | 1,074 passed, 149 files |
| Typecheck | `npm run typecheck` | exit 0 |
| Build + budget | `npm run build` | exit 0; initial 201.33 KiB gzip |
| Format / lint | `python tools/imp.py format` / `lint` | exit 0 / exit 0 |
| Docs links | `python tools/check_docs_links.py` | 270 files OK |
| Changed domain | `python tools/imp.py validate changed --paths-file <S7 paths>` | exit 0 — 5,419 tests, 43 skipped, 0 failures, 0 errors; 22 suites |

The first changed-domain run reported one error in `intelligence`:
`test_agent_enrichment_ingest_http…test_http_put_rejects_oversized_content_length`
raised `ConnectionAbortedError` (WinError 10053) while the 22 suites ran in
parallel. S7 touches nothing on that path; the test passed 6/6 in isolation
on both S7 and the S6 head (13040dc2), and the complete rerun passed.

## Limits

- The chain is a Finviz snapshot refreshed at most every 5 minutes, with no
  provider as-of time; it is never streaming.
- `Volume` is the latest session's; on a closed market it is the prior
  session's, stated by the `MARKET_CLOSED` state.
- One expiry is shown at a time; there is no all-expiries grid.
- An ETF's underlying price exists only once an ETF market snapshot has been
  retained by the Screener (a market-field filter or sort) or L1 is live;
  otherwise nearest strike and ITM shading are unavailable.
- Moomoo options quotes are not entitled on this account; Finviz is the only
  current chain source.
