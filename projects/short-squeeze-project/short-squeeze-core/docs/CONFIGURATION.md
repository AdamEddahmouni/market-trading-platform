# Configuration

## Precedence

For each supported setting, the resolver applies:

1. Explicit command-line argument
2. Process environment variable
3. Explicitly supplied configuration file (`--config`)
4. Explicitly supplied private provider file in `LOCAL_FULL` only
5. Safe default (`apps/research_screener/config.py`)

`CLOUD_PROVIDER_MODE` and `FROZEN_DEMO` never load the private provider file.
Library imports never read private paths; only entry points may opt in after mode
resolution.

Template: [../.env.example](../.env.example). Secrets belong in `.env` (gitignored)
or the deployment secret store—not in source.

## Runtime

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `SQUEEZE_APP_MODE` | Recommended | `LOCAL_FULL` | `LOCAL_FULL` \| `CLOUD_PROVIDER_MODE` \| `FROZEN_DEMO` |
| `PORT` | Optional | `8787` | HTTP listen port. Compose/Dockerfile use `8080` inside the container |
| `LOG_LEVEL` | Optional | `INFO` | Application log level |

## Opt-in security (default off)

| Variable | Default | Purpose |
|---|---|---|
| `CSRF_PROTECTION` | off | Enforce CSRF on state-changing methods |
| `LOCK_SENSITIVE_API` | off | In cloud mode, require CSRF pair for export/logs/collectors |

See [SECURITY.md](SECURITY.md). These flags are read by the HTTP server from the
process environment (not only from `KNOWN_KEYS` credential loading).

## Cloud / workstation providers

| Variable | Required | Purpose |
|---|---|---|
| `FINVIZ_ENABLED` | Optional | Enable Finviz Elite |
| `FINVIZ_API_KEY` | When Finviz enabled | Elite export token |
| `NEWSAPI_ENABLED` | Optional | Enable NewsAPI |
| `NEWSAPI_KEY` | When NewsAPI enabled | API key |
| `FINNHUB_ENABLED` | Optional | Enable Finnhub |
| `FINNHUB_KEY` | When Finnhub enabled | API key |
| `SEC_ENABLED` | Optional | Enable SEC EDGAR |
| `SEC_USER_AGENT` | When SEC enabled | `OrgName/1.0 contact@example.invalid` style |
| `SEC_CONTACT_EMAIL` | Optional | Administrative contact |
| `IBKR_ENABLED` | Optional | Enable IBKR configuration |
| `IBKR_HOST` | When IBKR enabled | Gateway host |
| `IBKR_PORT` | When IBKR enabled | Gateway API port |
| `IBKR_CLIENT_ID` | When IBKR enabled | Read-only client id |
| `IBKR_USER_ID` | Gateway container login | Mapped to `TWS_USERID` |
| `IBKR_PASSWORD` | Gateway container login | Mapped to `TWS_PASSWORD` |
| `IBKR_TRADE_MODE` | Optional | `paper` (default) or `live` |

`IBKR_USER_ID` / `IBKR_PASSWORD` are used by Gateway helpers and Compose; they are
intentionally outside the public `KNOWN_KEYS` filter used for generic env-file
loads—keep them in `.private/providers.env` or platform secrets.

## Sentiment and news

| Variable | Default | Purpose |
|---|---|---|
| `SENTIMENT_ENABLED` | `true` | Local sentiment path |
| `SENTIMENT_PROVIDER` | `local_finbert` | `local_finbert` or `keyword` |
| `SENTIMENT_MODEL_PATH` | empty | Optional checkpoint directory |
| `SENTIMENT_BATCH_SIZE` | `8` | Inference batch size |
| `NEWS_PROVIDER_ORDER` | Finviz Elite,Finnhub News,NewsAPI | Comma-separated order |
| `NEWS_CACHE_TTL_SECONDS` | `900` | Headline cache TTL |
| `NEWS_MAX_HEADLINES_PER_SYMBOL` | `30` | Cap per symbol |

## Refresh, screen size, freshness

| Variable | Default | Purpose |
|---|---|---|
| `QUOTE_REFRESH_SECONDS` | `15` | Quote refresh cadence |
| `SCANNER_REFRESH_SECONDS` | `180` | Scanner refresh cadence |
| `CURRENT_SCREEN_CAP` | `50` | Max symbols on current screen |
| `FINVIZ_TOP_N` | `50` | Finviz top-N pull |
| `SCANNER_ROW_LIMIT` | `50` | Row limit |
| `SYMBOLS_PER_CYCLE` | `3` | IBKR round-robin slice |
| `SYMBOLS_PER_CYCLE_MAX` | `6` | Upper bound for slice |
| `TARGET_LIVE_CANDIDATES` | `50` | Live candidate target |
| `FRESHNESS_CURRENT_SECONDS` | `90` | “Current” freshness window |
| `FRESHNESS_DELAYED_SECONDS` | `600` | “Delayed” freshness window |
| `MAX_CHART_POINTS` | `400` | Chart point cap |

## Collectors

Background collectors are documented in [COLLECTORS.md](COLLECTORS.md). Master
switch: `COLLECTORS_ENABLED`. For CI or locked-down demos, set
`COLLECTORS_ENABLED=false`.

## Provider field dependencies

| Methodology field | Requires |
|---|---|
| Published SI % | `FINVIZ_API_KEY` |
| Days to Cover | `FINVIZ_API_KEY` |
| Float Shares | `FINVIZ_API_KEY` |
| Relative Volume | `FINVIZ_API_KEY` |
| Borrow Avail % Float | `IBKR_ENABLED` + `FINVIZ_API_KEY` (both legs) |
| Cost to Borrow | Not currently implemented; requires a verified IBKR API mechanism and applicable entitlement |
| Bar Acceleration | `IBKR_ENABLED` |
| % Change | `IBKR_ENABLED` |
| Catalyst Age | News provider and/or SEC (`filed_at`) |
| News Count | Any news provider |
| Sentiment | Local FinBERT (not a cloud hard dependency) |
| Shortable / Halt | `IBKR_ENABLED` |

## Borrow fee

Borrow-fee retrieval is not currently implemented. It remains unavailable until
the deployment verifies a supported IBKR API mechanism and its applicable
market-data entitlement. Until then, Pressure remains constrained to the
Finviz-supported floor (65/100 weight). Changes require process restart.

## Doctor

```bash
python -m apps.research_screener.config doctor
python -m apps.research_screener.config doctor --json
python -m apps.research_screener.config doctor --config .env --no-ibkr-probe
python -m apps.research_screener.config doctor --mode FROZEN_DEMO
```

The doctor reports presence and compatibility, never secret values or private
absolute paths.
