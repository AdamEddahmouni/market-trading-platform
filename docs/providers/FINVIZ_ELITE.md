# Finviz Elite discovery provider

Status: **read-only DISCOVERY / CONTEXT source** under Platformization P3.3
([PLATFORM-PAPER-001](../superpowers/specs/2026-08-21-platform-paper-001-design.md),
[P3.3](../superpowers/specs/2026-08-21-platform-p33-finviz-discovery-research.md)).
Finviz discovers; it never executes. Discovery candidates are `INVESTIGATE`
rows, never buy/sell scores, and `PROMOTE_TO_LIVE_ANALYSIS` never creates
orders.

Live screens are **not** admitted research datasets, and historical research
cannot be reconstructed retroactively: `NO_RETROACTIVE_FINVIZ_SCREEN_RECONSTRUCTION`
means discovery research requires a prospective capture (`tools/discovery/run.py`).

## Architecture

```text
elite.finviz.com exports (screener / news / options)
        ↓
finviz.request_manager (rate limit 5s, cache, single-flight, HTTP 429 retry)
        ↓
finviz.screener / news / options parsers → canonical candidate rows
        ↓
discovery.engine (screens → matched reasons → INVESTIGATE candidates)
        ↓
discovery.capture (prospective file-backed PIT capture + manifest)
        ↓
promote-to-live-analysis (never orders) → Moomoo observational context
```

Phase 0 source invariants apply: the provider is CPython 3.11 stdlib only
(`urllib` transport in `finviz/http_client.py`), with no third-party HTTP
client, no native-OS access, and no process spawn in `src/`. Credentials live
in the gitignored `.private/` file store or provider env file — never in
source or evidence.

## Configuration

| Variable | Purpose |
|---|---|
| `FINVIZ_API_KEY` (or `FINVIZ_AUTH_TOKEN`) | Elite export token |
| `IMP_FINVIZ_LIVE=1` | Opt-in live probe |
| `IMP_FINVIZ_CAPTURE_DIR` | Prospective capture root |
| `IMP_FINVIZ_EVIDENCE_DIR` | Evidence output override |
| `IMP_FINVIZ_SECRET_DIR` | Token/login file store (default `.private/`) |
| `IMP_PROVIDER_ENV` | Optional provider env file (`.private/providers.env`) |

See [Finviz capability matrix](../research/finviz-elite-capability-matrix.md)
for the verified API surfaces, rate limits, and fixture-verified fields.

## Security

- No order, trade, or execution path; `EXECUTION_ROLE` is explicitly NONE.
- Secrets redacted from logs, errors, metrics, and evidence; URL `auth=`
  query values are sanitized (`finviz/redaction.py`).
- Host allowlist for login recovery (`finviz.com` family only); redirects
  outside the allowlist fail closed.
- Requests are rate-limited and cached; credentials are rotated with
  generation tracking (`finviz-auth-meta.json`).

## Tooling

```text
tools/finviz/probe.py      # capability report
tools/finviz/auth.py       # credential lifecycle (token / login recovery)
tools/discovery/run.py     # run a screen, capture candidates, promote to live analysis
```

## Limitations

- Groups/sectors, correlations, and alerts are UI-only surfaces — never scraped.
- ETF holdings export is NOT_VERIFIED.
- Options export is current-only; analytics are partial.
- Live Finviz screens require a valid Elite token and are prospective only.
