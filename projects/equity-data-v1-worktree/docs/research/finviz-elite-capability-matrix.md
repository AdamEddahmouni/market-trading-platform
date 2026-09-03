# Finviz Elite Capability Matrix (P3.3)

Generated from `tools/finviz/probe.py` and offline fixture characterization.

## Provider role

| Provider | Role | Execution |
|---|---|---|
| FINVIZ_ELITE | DISCOVERY / CONTEXT | **NONE** |
| MOOMOO | MARKET_DATA (L1, trades, L2) | **NONE** (observational) |
| FINRA / SEC | REGULATORY authority | N/A |
| IMP_DERIVED | CVD, reconciliation | INTERNAL only |

## API surfaces (documented vs verified)

| Capability | Endpoint / export | API accessible | PIT caveat |
|---|---|---|---|
| Screener | `elite.finviz.com/export/screener` | Yes (with token) | Prospective capture required |
| News | `elite.finviz.com/news_export.ashx` | Yes (with token) | `published_time` vs `available_time` |
| Options chain | `elite.finviz.com/export/options` | Yes (with token) | Current-only; analytics partial |
| Groups / sectors | UI | UI_ONLY | Not programmatic in P3.3 |
| ETF holdings | Unknown export | NOT_VERIFIED | Requires further probe |
| Correlations | UI | UI_ONLY | Do not scrape |
| Alerts | UI | UI_ONLY | — |

## Rate limits

Official documentation indicates ~1 request / 5 seconds. IMP `FinvizRequestManager` enforces `MIN_REQUEST_INTERVAL_S = 5.0` with cache, coalescing, and HTTP 429 retry.

## Screener fields (fixture-verified sample)

| Finviz field | Category | Canonical | Authority note |
|---|---|---|---|
| Ticker | IDENTITY | instrument_id | FINVIZ_ELITE |
| Short Float | SHORT | short_float_pct | FINVIZ_SHORT_FLOAT — not FINRA |
| Relative Volume | VOLUME | rel_volume | Discovery |
| Shares Float | FLOAT | float_shares | Reconcile with SEC |
| Sector / Industry | GROUP | sector / industry | Market context |

## Hard invariants

- `NO_RETROACTIVE_FINVIZ_SCREEN_RECONSTRUCTION` — historical research requires captured snapshot
- Discovery candidates = `INVESTIGATE` — never `BUY` / trade score
- `PROMOTE_TO_LIVE_ANALYSIS` never creates orders

## Configuration

```text
FINVIZ_API_KEY=...          # Elite export token
IMP_FINVIZ_LIVE=1           # opt-in live probe
IMP_PROVIDER_ENV=...        # optional credential file path
IMP_FINVIZ_CAPTURE_DIR=...  # prospective capture root
IMP_FINVIZ_EVIDENCE_DIR=... # evidence output override
IMP_FINVIZ_SECRET_DIR=...   # token/login file store (default .private/)
```

Run probe: `python tools/finviz/probe.py`

Run discovery: `python tools/discovery/run.py --screen SHORT_SQUEEZE_DISCOVERY`
