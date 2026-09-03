# Continuous Evidence Collectors

Background collectors run alongside the live screener auto-refresh loop. They harvest **lawful supplemental evidence** (public FINRA files, SEC/RSS, configured REST APIs) and merge it into row cells through the same `FieldValue` provenance model.

Operational recipes: [how-to-guides.md](how-to-guides.md#operate-collectors). Variable defaults also appear in [CONFIGURATION.md](CONFIGURATION.md).

## Policy

| Tier | Sources | Default |
|------|---------|---------|
| A | FINRA published SI, FINRA daily short volume, RSS/Atom news, SEC RSS, configured Polygon or Alpha Vantage APIs | On when `*_ENABLED` and credentials exist |
| B | yfinance (library only, no HTML scrape), Reddit, Stocktwits | Off; requires the source's current terms and credentials where applicable |
| C | Yahoo/Finviz HTML scrape, Stooq, login automation | **Not implemented** |

Social (Reddit, Stocktwits) uses **official OAuth/API tokens only**.

## Provider terms and plan checks

- [FINRA published short interest](https://www.finra.org/finra-data/browse-catalog/equity-short-interest) is a twice-monthly, point-in-time report; it is not daily short-sale volume. FINRA publishes it on the seventh business day after the reporting settlement date. [Daily short-sale-volume files](https://www.finra.org/finra-data/daily-short-sale-volume-transaction-data) describe reported short-sale volume, not open short interest, and may be revised.
- [yfinance](https://ranaroussi.github.io/yfinance/) is not affiliated with Yahoo and states that Yahoo Finance data is intended for personal use only. Keep it display-only and do not enable it for a commercial or redistributed deployment without an independently licensed source.
- [Polygon stock plans](https://polygon.io/stocks) currently offer a free Basic tier (5 calls/minute, end-of-day data) and paid tiers for delayed or real-time data. This collector calls the previous-day aggregate endpoint, so it must not be presented as a real-time quote feed.
- [Alpha Vantage](https://www.alphavantage.co/premium/) allows most endpoints on the free key up to 25 requests/day. Real-time and 15-minute-delayed US market data require the applicable premium entitlement.
- [Reddit Data API terms](https://redditinc.com/policies/data-api-terms) require authorized access information such as OAuth credentials; commercial use, research above rate limits, and uses not expressly permitted require a separate agreement. Do not use Reddit content to train a model without rightsholder permission.
- Stocktwits remains disabled by default. Enable it only after verifying the account's current official API access, token scope, rate limits, and redistribution terms; this repository makes no free-plan or commercial-use claim for it.

Collector-sourced cells are tagged `research_admissibility=RESEARCH_INADMISSIBLE` except FINRA published short interest normalized through `squeeze_core.adapters.finra` (`RESEARCH_ADMISSIBLE`).

## Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `COLLECTORS_ENABLED` | `true` | Master switch |
| `COLLECTOR_TICK_SECONDS` | `30` | Scheduler wake interval |
| `COLLECTOR_MAX_SYMBOLS_PER_TICK` | `10` | Batch size per tick |
| `COLLECTOR_MAX_REQUESTS_PER_MINUTE` | `60` | Global HTTP cap |
| `COLLECTOR_ORDER` | see `config.py` | Collector run order |
| `COLLECTOR_OVERRIDE_POLICY` | `never` | Set `display_fallback` to fill `NOT_CONFIGURED` only |
| `FINRA_SI_COLLECTOR_ENABLED` | `true` | Published short interest file |
| `FINRA_SI_DATA_URL` | — | Optional live FINRA file URL |
| `FINRA_SI_FIXTURE_PATH` | test fixture if present | Local file for dev/CI |
| `FINRA_DAILY_VOLUME_COLLECTOR_ENABLED` | `true` | Reg SHO daily file |
| `RSS_NEWS_ENABLED` | `true` | Google News RSS per symbol |
| `SEC_RSS_COLLECTOR_ENABLED` | `true` | SEC company Atom feed |
| `YFINANCE_COLLECTOR_ENABLED` | `false` | Opt-in display-only |
| `POLYGON_API_KEY` / `POLYGON_COLLECTOR_ENABLED` | off | Quote stub |
| `ALPHA_VANTAGE_API_KEY` / `ALPHA_VANTAGE_COLLECTOR_ENABLED` | off | Quote stub |
| `REDDIT_CLIENT_ID`, `REDDIT_SECRET`, `REDDIT_COLLECTOR_ENABLED` | off | Mention counts |
| `STOCKTWITS_ACCESS_TOKEN`, `STOCKTWITS_COLLECTOR_ENABLED` | off | Mention counts |
| `COLLECTOR_CACHE_ENABLED` | `true` | JSONL under `data/collector_cache/` |

## HTTP API

- `GET /api/collectors/status` — scheduler health, configured collectors, last tick
- `GET /api/collectors/symbol?symbol=GME` — debug snapshot from the evidence store

## Architecture

- Package: `apps/research_screener/collectors/`
- Scheduler prioritizes symbols with the worst `missing_evidence_buckets` on the current 50-ticker screen
- RSS/SEC headlines register into `NewsOrchestrator.register_external_headlines` (deduped by headline hash)
- Merge rules live in `collectors/merge.py`; KNOWN IBKR/Finviz cells are never overwritten unless override policy allows `NOT_CONFIGURED` fallback only

## Operations

Collectors start with bootstrap auto-refresh (`python -m apps.research_screener`). They stop when auto-refresh stops or the session resets.

CI should set `COLLECTORS_ENABLED=false` or rely on fixtures (`FINRA_SI_FIXTURE_PATH`) with network collectors disabled.
