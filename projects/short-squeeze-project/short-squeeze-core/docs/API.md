# API

API version is `1.0.0`; integration schema is `batch14.integration.v1`. Responses
use an envelope containing `api_version`, `schema_version`, `mode`, `as_of`,
`data`, `status`, `missingness`, and `provenance`. Legacy top-level fields remain
where required for compatibility.

Default local base URL: `http://127.0.0.1:8787`.

## Application routes

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Default Scanner UI |
| GET | `/advanced` | Advanced Research dashboard |
| GET | `/index.html` | Advanced Research (alias) |
| GET | `/research` | Advanced Research (alias) |

## Health and integration

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness and provider status |
| GET | `/ready` | Mode-specific readiness |
| GET | `/api/health` | Provider health status |
| GET | `/api/readiness` | Demo readiness payload |
| GET | `/api/v1/integration/manifest` | Machine-readable integration contract |
| GET | `/api/meta` | Application metadata (title, disclaimer, sort keys, modes) |
| GET | `/api/csrf-token` | Issues CSRF cookie/token for opt-in hardening |

## Research and screener data

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/providers` | Provider capabilities and health |
| GET | `/api/capabilities` | Provider capability matrix |
| GET | `/api/coverage` | Field coverage summary |
| GET | `/api/frozen/candidates` | Sanitized deterministic candidates |
| GET | `/api/frozen/candidate/<symbol>` | Frozen candidate detail |
| GET | `/api/current/candidates` | Current research candidates |
| GET | `/api/current/candidate/<symbol>` | Current candidate detail |
| GET | `/api/screener?mode=` | Main screener data (`CURRENT` or `FROZEN_RESEARCH`) |
| GET | `/api/symbol?symbol=` | Single symbol detail |
| GET | `/api/methodologies` | Methodology definitions and comparison |
| GET | `/api/methodologies/<symbol>` | Symbol methodology projections |
| GET | `/api/research-summary` | Historical research summary |
| GET | `/api/discovery/profiles` | Discovery profile listing |

## Mutations and live control

When `CSRF_PROTECTION=1`, these require a valid CSRF cookie + `X-CSRF-Token` header.
When `LOCK_SENSITIVE_API=1` in cloud mode, export/logs/collectors also require that
pair. See [SECURITY.md](SECURITY.md).

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/current/refresh` | Refresh due provider evidence |
| POST | `/api/refresh/all` | Refresh all providers for tracked symbols |
| POST | `/api/discovery/refresh` | Refresh read-only discovery |
| POST | `/api/export` | Write a sanitized research export (JSON + CSV) |
| POST | `/api/live/auto` | Toggle auto-refresh |
| POST | `/api/live/clear` | Clear current session |

## News, sentiment, collectors

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/news/status` | News orchestrator status |
| GET | `/api/news/symbol?symbol=` | News headlines for a symbol |
| GET | `/api/sentiment/status` | Sentiment analyzer status |
| GET | `/api/sentiment/symbol?symbol=` | Sentiment analysis for a symbol |
| GET | `/api/collectors/status` | Collector scheduler status |
| GET | `/api/collectors/symbol?symbol=` | Per-symbol collector debug snapshot |

There are no account, position, order, execution, or trading endpoints.

Static OpenAPI 3 description (includes `/api/csrf-token` and collector routes):
[openapi.json](openapi.json).
