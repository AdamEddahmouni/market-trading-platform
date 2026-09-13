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
finviz.request_manager (5s floor, valid-response cache, 5s/10s HTTP 429 backoff)
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
source or evidence. The tool launcher may optionally inject a `curl_cffi`
Chrome-impersonating cookie session for login/key recovery only; Elite export
requests continue through the governed stdlib client.

## Configuration

| Variable | Purpose |
|---|---|
| `FINVIZ_API_KEY` (or `FINVIZ_AUTH_TOKEN`) | Elite export token |
| `FINVIZ_API_TOKEN` / `FINVIZ_ELITE_TOKEN` / `IMP_FINVIZ_ELITE_TOKEN` / `IMP_FINVIZ_TOKEN` | Additional env aliases recognized by the fail-closed context overlay (presence only; never logged) |
| `IMP_FINVIZ_LIVE=1` | Opt-in live probe / paid Elite HTTP |
| `IMP_FINVIZ_CAPTURE_DIR` | Prospective capture root |
| `IMP_FINVIZ_EVIDENCE_DIR` | Evidence output override |
| `IMP_FINVIZ_SECRET_DIR` | Token/login file store (default `.private/`) |
| `IMP_PROVIDER_ENV` | Optional provider env file (`.private/providers.env`) |
| `IMP_FINVIZ_LOGIN_TRANSPORT` | Login recovery transport: `auto` (default), `urllib`, or optional `curl_cffi` |

See [Finviz capability matrix](../research/finviz-elite-capability-matrix.md)
for the verified API surfaces, rate limits, and fixture-verified fields.

## Canonical pipeline overlay

Finviz Elite is a **context overlay** in the provider composition
(`equity_context`), not a quote/tick hop and not the Paper comparator.

- `providers/finviz_context_discovery.py` always returns
  `finviz.elite.context`. Token absence is `NOT_CONFIGURED`. A present token
  without `IMP_FINVIZ_LIVE` (and without an injected test transport) is
  `CONFIGURED_BLOCKED` / `LIVE_DISABLED`. Classification is never
  `REAL_TIME`, never Yahoo-as-Finviz, and never ES.
- `FinvizEliteContextProvider.fetch_context` is screening/news only. Paid
  Elite HTTP requires the existing live gate; CI uses injected clients.
- `with_finviz_elite_context()` injects the adapter into
  `ProviderComposition.equity_context`. The default composition slot remains
  the unconfigured stub.

### Join into the canonical observational hop

The G6/G7 canonical observational hop (`ObservationalRuntimeComposition` in
`market_data/runtime_composition.py`: quote → admission →
`ObservationalStateStore` → `ObservationalLaneRuntime`) exposes its own
`equity_context` slot, independent of `ProviderComposition`.

- `ObservationalRuntimeComposition.equity_context` defaults to
  `UnconfiguredEquityContextProvider`; `context_for(instrument_id)` and
  `evidence_for(instrument_id)["context"]` fail closed (`PROVIDER_NOT_CONFIGURED`)
  until a provider is attached.
- `with_finviz_elite_observational_context()`
  (`providers/composition.py`) attaches the Finviz Elite adapter to that slot
  the same way `with_finviz_elite_context()` does for `ProviderComposition`.
  Token absence still classifies `NOT_CONFIGURED`; no Elite HTTP runs in CI.
- `ObservationalLaneRuntime.build_context_payload()` is the provider-neutral
  lane builder: it always forces `is_l1=False` and `is_paper_comparator=False`
  on the returned payload, and fails closed to `CONTEXT_TIMELINESS_INVALID`
  if a provider (declared or per-event) ever claims `REAL_TIME` — defense in
  depth beyond the adapter's own `DELAYED` contract. The context lane sits
  alongside `l1`/`cvd`/`ofi`/`book_features` in `evidence_for()`'s bundle and
  is excluded from the L1/L2 `evidence_hash` (a side-channel, not tick
  replay-deterministic state), so it never mutates admission or the canonical
  store. See `tests/market_data/test_finviz_observational_context.py`.

This overlay does not activate Live, start FTEP, or declare
`EMPIRICAL_ACTIVE`.

## Security

- No order, trade, or execution path; `EXECUTION_ROLE` is explicitly NONE.
- Secrets redacted from logs, errors, metrics, and evidence; URL `auth=`
  query values are sanitized (`finviz/redaction.py`).
- Host allowlist for login recovery (`finviz.com` family only); redirects
  outside the allowlist fail closed.
- Requests are rate-limited and cached; credentials are rotated with
  generation tracking (`finviz-auth-meta.json`).

## Automatic operation

- The Mixed Live browser requests a new Finviz universe every 120 seconds
  while visible. Finviz is periodically re-fetched; it is not a stream.
- Exports are serialized with a five-second request floor. HTTP 429 responses
  retry twice with exponential waits of 5 and 10 seconds, or a larger valid
  `Retry-After` value. Rate-limit and authentication responses are not cached.
- On an authentication failure, the credential manager first re-reads the
  secure token/provider file and validates a changed key. If no changed key
  succeeds, stored login credentials drive the current Finviz email-login
  flow, API-key extraction, validation, atomic persistence, and one retry of
  the original export.
- `IMP_FINVIZ_LOGIN_TRANSPORT=auto` uses `curl_cffi` with Chrome impersonation
  when that optional tool-layer package is already installed; otherwise it
  falls back to the stdlib cookie session. `urllib` forces the stdlib path.
- MFA, CAPTCHA, an inactive Elite subscription, or repeated recovery failure
  stops automatic attempts at `AUTH_OPERATOR_ACTION_REQUIRED`. The last valid
  discovery captures remain available as `SNAPSHOT` or `STALE`.
- Run `python tools/finviz/auth.py configure` to store an existing token
  securely. For login-only setup, run
  `python tools/finviz/auth.py configure-login`; it prompts for the email and
  password without echoing the password, stores them in `.private/`, and
  attempts read-only token recovery. Never put credentials in committed files.

## Tooling

```text
tools/finviz/probe.py      # capability report
tools/finviz/auth.py       # credential lifecycle (token / login recovery)
tools/finviz/login_transport.py # optional curl_cffi login-only adapter
tools/discovery/run.py     # run a screen, capture candidates, promote to live analysis
```

## Limitations

- Groups/sectors, correlations, and alerts are UI-only surfaces — never scraped.
- ETF holdings export is NOT_VERIFIED.
- Options export is current-only; analytics are partial.
- Live Finviz screens require a valid Elite token and are prospective only.
