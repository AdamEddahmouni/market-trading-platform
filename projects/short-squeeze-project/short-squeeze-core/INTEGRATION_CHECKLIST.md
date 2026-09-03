# Integration Checklist — Short Squeeze Research Screener

This document is the authoritative reference for the integration team. Every API endpoint is listed with its method, path, query parameters, key response fields, and a `curl` command to verify it is live.

**Base URL**: `http://127.0.0.1:8787` (local) or the Railway/production URL.

All endpoints return JSON unless otherwise noted.

---

## Quick Smoke Test

Run these five commands first. If they all return valid JSON, the server is operational:

```bash
curl -s http://127.0.0.1:8787/health | python -m json.tool > /dev/null && echo "PASS: health"
curl -s http://127.0.0.1:8787/ready | python -m json.tool > /dev/null && echo "PASS: ready"
curl -s http://127.0.0.1:8787/api/frozen/candidates | python -m json.tool > /dev/null && echo "PASS: frozen/candidates"
curl -s http://127.0.0.1:8787/api/capabilities | python -m json.tool > /dev/null && echo "PASS: capabilities"
curl -s http://127.0.0.1:8787/api/v1/integration/manifest | python -m json.tool > /dev/null && echo "PASS: manifest"
```

---

## 1. Health & Operational

### `GET /health`

Returns a simple liveness check.

**Query params**: none

**Response**:
```json
{
  "server": "alive",
  "methodology_engine": "AVAILABLE",
  "mode": "LOCAL_FULL"
}
```

**Verify**:
```bash
curl -s http://127.0.0.1:8787/health | python -m json.tool
```

---

### `GET /ready`

Returns readiness status including whether the frozen research source is loaded.

**Query params**: none

**Response**:
```json
{
  "application_operational": true,
  "api_available": true,
  "methodology_engine_available": true,
  "selected_frozen_source_loaded": true,
  "frozen_source": "FROZEN_DEMO",
  "optional_ibkr_required": false,
  "mode": "LOCAL_FULL"
}
```

**Verify**:
```bash
curl -s http://127.0.0.1:8787/ready | python -m json.tool
```

---

### `GET /api/health`

Detailed provider health check.

**Query params**: none

**Response**:
```json
{
  "mode": "LOCAL_FULL",
  "data": {
    "providers": [
      {"name": "IB Gateway", "state": "DISCONNECTED", "detail": "..."},
      {"name": "Market Data", "state": "UNAVAILABLE"},
      {"name": "Frozen Research Artifacts", "state": "AVAILABLE"},
      {"name": "NewsAPI", "state": "NOT CONFIGURED"},
      {"name": "Finviz Elite", "state": "NOT CONFIGURED"},
      {"name": "Finnhub", "state": "NOT CONFIGURED"},
      {"name": "SEC EDGAR", "state": "NOT CONFIGURED"},
      {"name": "Sentiment", "state": "NOT CONFIGURED"}
    ],
    "frozen_research_available": true,
    "auto_refresh": false,
    "market_data_mode": "DELAYED"
  }
}
```

**Verify**:
```bash
curl -s http://127.0.0.1:8787/api/health | python -m json.tool
```

---

### `GET /api/readiness`

Demo readiness check. Always available.

**Query params**: none

**Verify**:
```bash
curl -s http://127.0.0.1:8787/api/readiness | python -m json.tool
```

---

### `GET /api/capabilities`

Provider capability matrix — which providers support which data types.

**Query params**: none

**Verify**:
```bash
curl -s http://127.0.0.1:8787/api/capabilities | python -m json.tool
```

---

### `GET /api/coverage`

Field coverage summary showing how many fields are available vs total.

**Query params**: none

**Verify**:
```bash
curl -s http://127.0.0.1:8787/api/coverage | python -m json.tool
```

---

### `GET /api/providers`

Same as `/api/health` — provider status list.

**Verify**:
```bash
curl -s http://127.0.0.1:8787/api/providers | python -m json.tool
```

---

## 2. Screener & Candidate Data

### `GET /api/screener`

Primary screener endpoint. Returns rows with all filter/sort options.

**Query params**:

| Param | Type | Default | Description |
|---|---|---|---|
| `mode` | string | `FROZEN_RESEARCH` | `FROZEN_RESEARCH` or `CURRENT` |
| `symbol` | string | — | Filter by symbol substring |
| `detection` | string | — | Filter by research detection label |
| `data_mode` | string | — | Filter by data mode |
| `freshness` | string | — | Filter by freshness category |
| `profile` | string | — | Filter by discovery profile |
| `market_mode` | string | — | Filter by market data mode |
| `sort` | string | `symbol` | Sort key (see `/api/meta` for valid keys) |
| `desc` | string | `false` | Sort descending (`true`/`false`) |
| `min_price` | float | — | Minimum price filter |
| `max_price` | float | — | Maximum price filter |
| `min_change` | float | — | Minimum % change filter |
| `min_relvol` | float | — | Minimum relative volume filter |
| `min_pass` | int | — | Minimum pass count |
| `max_unknown` | int | — | Maximum unknown count |
| `min_coverage` | int | — | Minimum evidence coverage % |
| `refresh` | string | `false` | Force refresh (`true`/`false`) |

**Response**:
```json
{
  "row_count": 13,
  "unfiltered_row_count": 13,
  "rows": [
    {
      "symbol": "BIYA",
      "pressure": 65,
      "ignition": 45,
      "fields": { "last": {"status": "KNOWN", "value": 12.50}, ... },
      "phase3a": { "counts": {"PASS": 7, "FAIL": 2, "UNKNOWN": 16} },
      "methodologies": [{"methodology_id": "adam_evidence_gated_prime.v1", "classification": "PRIME"}],
      "market_data_mode": "DELAYED",
      "freshness": "CURRENT"
    }
  ]
}
```

**Verify**:
```bash
# Frozen mode (default)
curl -s "http://127.0.0.1:8787/api/screener?mode=FROZEN_RESEARCH" | python -m json.tool

# With filters
curl -s "http://127.0.0.1:8787/api/screener?mode=FROZEN_RESEARCH&min_price=5&sort=pressure&desc=true" | python -m json.tool
```

---

### `GET /api/symbol`

Single candidate detail with full rule evaluation.

**Query params**:

| Param | Type | Default | Description |
|---|---|---|---|
| `symbol` | string | *required* | Ticker symbol |
| `mode` | string | `FROZEN_RESEARCH` | `FROZEN_RESEARCH` or `CURRENT` |

**Response** (frozen):
```json
{
  "identity": {"symbol": "BIYA", "contract": {"long_name": "..."}},
  "rules": [...],
  "fields": {...},
  "methodologies": [...],
  "chart": {...}
}
```

**Verify**:
```bash
curl -s "http://127.0.0.1:8787/api/symbol?symbol=BIYA" | python -m json.tool
```

---

### `GET /api/frozen/candidates`

Frozen research candidates (convenience alias for `/api/screener?mode=FROZEN_RESEARCH`). Accepts all filter/sort params from `/api/screener`.

**Verify**:
```bash
curl -s "http://127.0.0.1:8787/api/frozen/candidates" | python -m json.tool
```

---

### `GET /api/frozen/candidate`

Single frozen candidate detail (convenience alias for `/api/symbol?mode=FROZEN_RESEARCH`).

**Query params**: `symbol` (required)

**Verify**:
```bash
curl -s "http://127.0.0.1:8787/api/frozen/candidate?symbol=BIYA" | python -m json.tool
```

---

### `GET /api/frozen/candidate/{symbol}`

REST-style frozen candidate detail.

**Verify**:
```bash
curl -s "http://127.0.0.1:8787/api/frozen/candidate/BIYA" | python -m json.tool
```

---

### `GET /api/live/candidates`

Live screener candidates. Accepts all filter/sort params from `/api/screener`.

**Verify**:
```bash
curl -s "http://127.0.0.1:8787/api/live/candidates" | python -m json.tool
```

---

### `GET /api/live/candidate`

Single live candidate detail.

**Query params**: `symbol` (required)

**Verify**:
```bash
curl -s "http://127.0.0.1:8787/api/live/candidate?symbol=AAPL" | python -m json.tool
```

---

### `GET /api/current/candidates`

Current screener candidates (wrapped with mode envelope).

**Verify**:
```bash
curl -s "http://127.0.0.1:8787/api/current/candidates" | python -m json.tool
```

---

### `GET /api/current/candidate/{symbol}`

REST-style current candidate detail.

**Verify**:
```bash
curl -s "http://127.0.0.1:8787/api/current/candidate/AAPL" | python -m json.tool
```

---

### `GET /api/methodologies`

Returns all methodology evaluation results for current candidates.

**Verify**:
```bash
curl -s "http://127.0.0.1:8787/api/methodologies" | python -m json.tool
```

---

### `GET /api/methodologies/{symbol}`

Single symbol methodology comparison.

**Verify**:
```bash
curl -s "http://127.0.0.1:8787/api/methodologies/BIYA" | python -m json.tool
```

---

### `GET /api/discovery/profiles`

Returns available discovery profiles and the currently selected one.

**Response**:
```json
{
  "profiles": [
    {"profile_id": "BROAD_MOVERS", "label": "Broad Movers", ...}
  ],
  "selected": "BROAD_MOVERS"
}
```

**Verify**:
```bash
curl -s "http://127.0.0.1:8787/api/discovery/profiles" | python -m json.tool
```

---

### `GET /api/discovery/cadence`

Current market state, refresh cadence timing, and API quota status.

**Response**:
```json
{
  "market": {
    "is_open": false,
    "state": "CLOSED",
    "day": "Sunday",
    "day_type": "Weekend",
    "next_open_at": "2026-07-27T14:30:00Z",
    "cadence_multiplier": 4,
    "cadence_mode": "CONSERVATIVE"
  },
  "refresh": {
    "auto_refresh": false,
    "effective_quote_refresh_s": 60,
    "effective_scanner_refresh_s": 720,
    "last_refresh_at": null,
    "next_refresh_at": null
  },
  "discovery": {
    "profile": "BROAD_MOVERS",
    "last_discovery_at": null,
    "candidate_count": 0
  },
  "api_quota": {
    "ibkr_budget_note": "IBKR allows 60 requests per rolling 10 minutes...",
    "off_hours_multiplier": 4
  }
}
```

**Verify**:
```bash
curl -s "http://127.0.0.1:8787/api/discovery/cadence" | python -m json.tool
```

---

### `GET /api/meta`

Application metadata: title, disclaimer, valid sort keys, export directory.

**Verify**:
```bash
curl -s "http://127.0.0.1:8787/api/meta" | python -m json.tool
```

---

### `GET /api/research-summary` (also at `/api/professor`)

Historical research summary with Phase 3C analysis results.

**Verify**:
```bash
curl -s "http://127.0.0.1:8787/api/research-summary" | python -m json.tool
```

---

## 3. News & Sentiment

### `GET /api/news/feed`

**Aggregated** headlines across all screener candidates in one request. Replaces N separate per-symbol calls.

**Query params**:

| Param | Type | Default | Description |
|---|---|---|---|
| `classification` | string | (all) | Comma-separated filter: `PRIME`, `SUBPRIME`, `WATCH` |
| `limit` | int | `30` | Max headlines (1–100) |

**Response**:
```json
{
  "headlines": [
    {
      "symbol": "GME",
      "classification": "PRIME",
      "headline": "GameStop Reports Q2 Earnings Beat",
      "time": "2026-07-26T14:30:00Z",
      "source": "Reuters",
      "url": "https://..."
    }
  ],
  "count": 30,
  "counts": {"PRIME": 12, "SUBPRIME": 5, "WATCH": 3},
  "symbols_scanned": 13,
  "symbols_fetched": 3,
  "symbols": ["GME", "AMC", ...]
}
```

**Verify**:
```bash
# All headlines
curl -s "http://127.0.0.1:8787/api/news/feed?limit=5" | python -m json.tool

# PRIME only
curl -s "http://127.0.0.1:8787/api/news/feed?classification=PRIME&limit=5" | python -m json.tool
```

---

### `GET /api/news/status`

News orchestrator status — which providers are configured, cache state, rate-limit info.

**Verify**:
```bash
curl -s "http://127.0.0.1:8787/api/news/status" | python -m json.tool
```

---

### `GET /api/news/symbol`

Per-symbol headlines from the session detail.

**Query params**:

| Param | Type | Default | Description |
|---|---|---|---|
| `symbol` | string | *required* | Ticker symbol |

**Response**:
```json
{
  "symbol": "GME",
  "headlines": [
    {"headline": "...", "timestamp": "...", "source": "...", "url": "..."}
  ],
  "count": 5,
  "mode": "CURRENT"
}
```

**Verify**:
```bash
curl -s "http://127.0.0.1:8787/api/news/symbol?symbol=GME" | python -m json.tool
```

---

### `GET /api/sentiment/status`

FinBERT sentiment analyzer status.

**Verify**:
```bash
curl -s "http://127.0.0.1:8787/api/sentiment/status" | python -m json.tool
```

---

### `GET /api/sentiment/symbol`

Per-symbol sentiment analysis result.

**Query params**: `symbol` (required)

**Verify**:
```bash
curl -s "http://127.0.0.1:8787/api/sentiment/symbol?symbol=GME" | python -m json.tool
```

---

## 4. Logging & Observability

### `GET /api/logs/status`

Live log file summary with tail lines for real-time monitoring.

**Query params**:

| Param | Type | Default | Description |
|---|---|---|---|
| `lines` | int | `20` | Number of tail lines per file (max 200) |

**Response**:
```json
{
  "logging_enabled": true,
  "session_id": "20260726_152941",
  "log_directory": "/path/to/data/screener_logs",
  "file_count": 187,
  "files": [{
    "name": "screener_20260726.jsonl",
    "size_bytes": 21836,
    "line_count": 53,
    "tail": [{"type": "screener_snapshot", ...}]
  }],
  "rotation": {
    "configured_thresholds": {"max_files": 200, "max_dir_size_mb": 500},
    "current": {"file_count": 187, "total_size_mb": 1.47, "usage_pct_files": 93.5},
    "archive_directory": "/path/to/data/screener_logs/archive",
    "check_interval_writes": 20,
    "rotation_enabled": true
  }
}
```

**Verify**:
```bash
curl -s "http://127.0.0.1:8787/api/logs/status?lines=5" | python -m json.tool
```

---

### `GET /api/logs/replay`

Reconstruct the frozen screener view at a past point in time from full_snapshot archives.

**Query params**:

| Param | Type | Default | Description |
|---|---|---|---|
| `at` | ISO string | (latest) | Target timestamp, e.g. `2026-07-26T15:30:00Z` |
| `session` | string | (all) | Filter by session ID |

**Response**:
```json
{
  "available": true,
  "replay_at": "2026-07-26T14:00:00Z",
  "snapshot_at": "2026-07-26T13:58:00Z",
  "delta_seconds": 120.0,
  "exact_match": false,
  "snapshot_is_after_target": false,
  "source_file": "full_snapshot_20260726.jsonl",
  "snapshot": { "type": "full_snapshot", "rows": [...], "row_count": 13 }
}
```

**Verify**:
```bash
curl -s "http://127.0.0.1:8787/api/logs/replay" | python -m json.tool
curl -s "http://127.0.0.1:8787/api/logs/replay?at=2026-07-26T10:00:00Z" | python -m json.tool
```

---

### `GET /api/logs/replay/raw`

Reconstruct what raw provider data existed at a past point in time. Groups by symbol.

**Query params**: same as `/api/logs/replay`

**Verify**:
```bash
curl -s "http://127.0.0.1:8787/api/logs/replay/raw" | python -m json.tool
```

---

### `GET /api/logs/replay/timeline`

Chronological list of all full_snapshot timestamps available for replay.

**Query params**:

| Param | Type | Default | Description |
|---|---|---|---|
| `session` | string | (all) | Filter by session ID |

**Verify**:
```bash
curl -s "http://127.0.0.1:8787/api/logs/replay/timeline" | python -m json.tool
```

---

### `GET /api/logs/archive`

List all archived `.tar.gz` log files.

**Response**:
```json
{
  "available": true,
  "count": 2,
  "total_size_mb": 1.47,
  "archive_directory": "/path/to/data/screener_logs/archive",
  "archives": [{
    "name": "log_archive_20260726.tar.gz",
    "size_bytes": 1540000,
    "size_mb": 1.47,
    "created_at": "2026-07-26T15:40:52Z"
  }]
}
```

**Verify**:
```bash
curl -s "http://127.0.0.1:8787/api/logs/archive" | python -m json.tool
```

---

### `GET /api/logs/archive/download/{name}`

Download a specific archive file. Returns `application/gzip` binary.

**Verify**:
```bash
# List archives first to get a name
curl -s "http://127.0.0.1:8787/api/logs/archive" | python -m json.tool
# Then download (replace NAME with actual archive name)
curl -s -o /tmp/archive.tar.gz "http://127.0.0.1:8787/api/logs/archive/download/log_archive_20260726.tar.gz"
file /tmp/archive.tar.gz
```

---

### `GET /api/enrichment/policies`

Summary of all three enrichment policy files (Finviz, NewsAPI, Finnhub) with mapping counts and source paths.

**Verify**:
```bash
curl -s "http://127.0.0.1:8787/api/enrichment/policies" | python -m json.tool
```

---

## 5. Mutation (POST)

All POST routes require CSRF protection in `CLOUD_PROVIDER_MODE`. In `LOCAL_FULL` mode, no CSRF token is needed.

### `POST /api/export`

Export a snapshot to the export directory.

**Query params**:

| Param | Type | Default | Description |
|---|---|---|---|
| `mode` | string | `FROZEN_RESEARCH` | `FROZEN_RESEARCH` or `CURRENT` |
| `symbols` | string | — | Comma or space-separated symbol list |

**Response**:
```json
{
  "written": {"json": "snapshot_20260726.json", "csv": "snapshot_20260726.csv"},
  "row_count": 13,
  "mode": "FROZEN_RESEARCH"
}
```

**Verify**:
```bash
curl -s -X POST "http://127.0.0.1:8787/api/export?mode=FROZEN_RESEARCH" | python -m json.tool
```

---

### `POST /api/discovery/refresh`

Trigger a discovery refresh for a specific profile.

**Query params**:

| Param | Type | Default | Description |
|---|---|---|---|
| `profile` | string | — | Discovery profile ID (e.g. `BROAD_MOVERS`) |

**Verify**:
```bash
curl -s -X POST "http://127.0.0.1:8787/api/discovery/refresh?profile=BROAD_MOVERS" | python -m json.tool
```

---

### `POST /api/live/refresh` (alias: `/api/current/refresh`)

Refresh live provider data for all tracked candidates.

**Verify**:
```bash
curl -s -X POST "http://127.0.0.1:8787/api/live/refresh" | python -m json.tool
```

---

### `POST /api/refresh/all`

Launch a background refresh of all provider data. Returns `202 Accepted` immediately.

**Response**:
```json
{
  "accepted": true,
  "total": 13,
  "message": "Background refresh started for 13 symbol(s)...",
  "at": "2026-07-26T16:00:00Z"
}
```

**Verify**:
```bash
curl -s -X POST "http://127.0.0.1:8787/api/refresh/all" | python -m json.tool
```

---

### `POST /api/live/auto`

Enable or disable auto-refresh mode.

**Query params**:

| Param | Type | Default | Description |
|---|---|---|---|
| `enabled` | string | `false` | `true`, `yes`, `on`, `1` to enable |

**Verify**:
```bash
curl -s -X POST "http://127.0.0.1:8787/api/live/auto?enabled=true" | python -m json.tool
```

---

### `POST /api/live/clear`

Clear all current session state and cached provider data.

**Verify**:
```bash
curl -s -X POST "http://127.0.0.1:8787/api/live/clear" | python -m json.tool
```

---

### `POST /api/logs/rotate`

Trigger manual log rotation. Archives oldest files to `.tar.gz` if thresholds exceeded.

**Response** (when thresholds OK):
```json
{
  "rotated": 0,
  "file_count": 187,
  "total_size_mb": 1.47,
  "thresholds_ok": true
}
```

**Response** (when rotation executed):
```json
{
  "rotated": 193,
  "archived_size_mb": 1.47,
  "archive_name": "log_archive_20260726_154052.tar.gz",
  "remaining_files": 2,
  "trigger": "file_count"
}
```

**Verify**:
```bash
curl -s -X POST "http://127.0.0.1:8787/api/logs/rotate" | python -m json.tool
```

---

## 6. Integration & Export

### `GET /api/v1/integration/manifest`

Integration manifest describing the API version, methodology IDs, and permitted operations.

**Verify**:
```bash
curl -s "http://127.0.0.1:8787/api/v1/integration/manifest" | python -m json.tool
```

---

### `GET /api/export`

Export screener data as JSON (same as POST but without writing to disk).

**Query params**: same as `POST /api/export`

**Verify**:
```bash
curl -s "http://127.0.0.1:8787/api/export?mode=FROZEN_RESEARCH" | python -m json.tool
```

---

## 7. Static / UI

### `GET /`

Serves the main scanner UI (`scanner.html`).

**Verify**:
```bash
curl -s "http://127.0.0.1:8787/" | head -5
```

---

### `GET /advanced` (aliases: `/index.html`, `/research`)

Serves the advanced research dashboard (`index.html`).

**Verify**:
```bash
curl -s "http://127.0.0.1:8787/advanced" | head -5
```

---

### `GET /static/{file}`

Serves static assets: `styles.css`, `scanner.js`, `shared.js`, `app.js`.

**Verify**:
```bash
curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:8787/static/styles.css"
echo ""
curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:8787/static/scanner.js"
```

---

## Endpoint Summary

| # | Method | Path | Category |
|---|--------|------|----------|
| 1 | GET | `/` | Static UI |
| 2 | GET | `/advanced` | Static UI |
| 3 | GET | `/health` | Health |
| 4 | GET | `/ready` | Health |
| 5 | GET | `/api/health` | Health |
| 6 | GET | `/api/readiness` | Health |
| 7 | GET | `/api/capabilities` | Health |
| 8 | GET | `/api/coverage` | Health |
| 9 | GET | `/api/providers` | Health |
| 10 | GET | `/api/screener` | Candidates |
| 11 | GET | `/api/symbol` | Candidates |
| 12 | GET | `/api/frozen/candidates` | Candidates |
| 13 | GET | `/api/frozen/candidate` | Candidates |
| 14 | GET | `/api/frozen/candidate/{symbol}` | Candidates |
| 15 | GET | `/api/live/candidates` | Candidates |
| 16 | GET | `/api/live/candidate` | Candidates |
| 17 | GET | `/api/current/candidates` | Candidates |
| 18 | GET | `/api/current/candidate/{symbol}` | Candidates |
| 19 | GET | `/api/methodologies` | Candidates |
| 20 | GET | `/api/methodologies/{symbol}` | Candidates |
| 21 | GET | `/api/discovery/profiles` | Discovery |
| 22 | GET | `/api/discovery/cadence` | Discovery |
| 23 | GET | `/api/meta` | Meta |
| 24 | GET | `/api/research-summary` | Meta |
| 25 | GET | `/api/news/feed` | News |
| 26 | GET | `/api/news/status` | News |
| 27 | GET | `/api/news/symbol` | News |
| 28 | GET | `/api/sentiment/status` | Sentiment |
| 29 | GET | `/api/sentiment/symbol` | Sentiment |
| 30 | GET | `/api/logs/status` | Logging |
| 31 | GET | `/api/logs/replay` | Logging |
| 32 | GET | `/api/logs/replay/raw` | Logging |
| 33 | GET | `/api/logs/replay/timeline` | Logging |
| 34 | GET | `/api/logs/archive` | Logging |
| 35 | GET | `/api/logs/archive/download/{name}` | Logging |
| 36 | GET | `/api/enrichment/policies` | Logging |
| 37 | GET | `/api/export` | Export |
| 38 | GET | `/api/v1/integration/manifest` | Integration |
| 39 | POST | `/api/export` | Mutation |
| 40 | POST | `/api/discovery/refresh` | Mutation |
| 41 | POST | `/api/live/refresh` | Mutation |
| 42 | POST | `/api/current/refresh` | Mutation |
| 43 | POST | `/api/refresh/all` | Mutation |
| 44 | POST | `/api/live/auto` | Mutation |
| 45 | POST | `/api/live/clear` | Mutation |
| 46 | POST | `/api/logs/rotate` | Mutation |

**Total**: 46 endpoints (38 GET + 8 POST)

---

## Full Verification Script

Run this script against a running server to verify every endpoint returns valid JSON (or HTML for static routes):

```bash
#!/bin/bash
BASE="http://127.0.0.1:8787"
FAILS=0

check() {
  local desc="$1" method="$2" path="$3"
  local code
  code=$(curl -s -o /dev/null -w "%{http_code}" -X "$method" "$BASE$path")
  if [ "$code" -ge 400 ]; then
    echo "FAIL: $desc ($method $path) -> HTTP $code"
    FAILS=$((FAILS + 1))
  else
    echo "PASS: $desc ($method $path) -> HTTP $code"
  fi
}

# Health
check "health" GET "/health"
check "ready" GET "/ready"
check "api health" GET "/api/health"
check "readiness" GET "/api/readiness"
check "capabilities" GET "/api/capabilities"
check "coverage" GET "/api/coverage"
check "providers" GET "/api/providers"

# Candidates
check "screener" GET "/api/screener"
check "symbol" GET "/api/symbol?symbol=BIYA"
check "frozen candidates" GET "/api/frozen/candidates"
check "frozen candidate" GET "/api/frozen/candidate/BIYA"
check "live candidates" GET "/api/live/candidates"
check "methodologies" GET "/api/methodologies"
check "methodology symbol" GET "/api/methodologies/BIYA"

# Discovery
check "discovery profiles" GET "/api/discovery/profiles"
check "discovery cadence" GET "/api/discovery/cadence"

# Meta
check "meta" GET "/api/meta"
check "research summary" GET "/api/research-summary"

# News
check "news feed" GET "/api/news/feed?limit=5"
check "news status" GET "/api/news/status"
check "news symbol" GET "/api/news/symbol?symbol=BIYA"

# Sentiment
check "sentiment status" GET "/api/sentiment/status"
check "sentiment symbol" GET "/api/sentiment/symbol?symbol=BIYA"

# Logging
check "logs status" GET "/api/logs/status?lines=1"
check "logs replay" GET "/api/logs/replay"
check "logs replay raw" GET "/api/logs/replay/raw"
check "logs replay timeline" GET "/api/logs/replay/timeline"
check "logs archive" GET "/api/logs/archive"

# Enrichment
check "enrichment policies" GET "/api/enrichment/policies"

# Integration
check "integration manifest" GET "/api/v1/integration/manifest"
check "export GET" GET "/api/export"

# Static
check "scanner UI" GET "/"
check "advanced UI" GET "/advanced"

# POST mutations
check "POST export" POST "/api/export"
check "POST discovery refresh" POST "/api/discovery/refresh?profile=BROAD_MOVERS"
check "POST live refresh" POST "/api/live/refresh"
check "POST refresh all" POST "/api/refresh/all"
check "POST live auto" POST "/api/live/auto?enabled=false"
check "POST live clear" POST "/api/live/clear"
check "POST logs rotate" POST "/api/logs/rotate"

echo ""
echo "Done: $FAILS failures"
```

---

## Configuration

The server reads these environment variables:

| Variable | Default | Description |
|---|---|---|
| `SQUEEZE_APP_MODE` | — | `LOCAL_FULL` or `CLOUD_PROVIDER_MODE` |
| `PORT` | `8787` | Server listen port |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `FINVIZ_API_KEY` | — | Finviz Elite API key |
| `NEWSAPI_KEY` | — | NewsAPI key |
| `FINNHUB_KEY` | — | Finnhub API key |
| `SEC_USER_AGENT` | — | SEC EDGAR user agent |
| `IBKR_HOST` | `127.0.0.1` | IB Gateway host |
| `IBKR_PORT` | `4002` | IB Gateway port |
| `IBKR_CLIENT_ID` | — | IB Gateway client ID |
| `SQUEEZE_DATA_LOG` | `true` | Enable/disable data logging |
| `SQUEEZE_LOG_MAX_FILES` | `200` | Max log files before rotation |
| `SQUEEZE_LOG_MAX_DIR_SIZE_MB` | `500` | Max log dir size (MB) before rotation |
