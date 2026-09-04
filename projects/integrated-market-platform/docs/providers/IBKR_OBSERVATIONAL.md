# IBKR observational market-data provider

Status: **read-only observational boundary** under `ADR-LIVE-002`, extending
`ADR-LIVE-001`. This is not an admitted research dataset, not paper execution,
and not live execution.

Evidence classes used below: **DOCUMENTED**, **OBSERVED**, **INFERRED**, **UNTESTED**.
Observed runtime evidence outranks documentation.

## Architecture

```text
lane request (US_EQUITY_L1 / HISTORY / OPTIONS_CHAIN / SCANNER / PORTFOLIO_STATE)
        ↓
provider router / composition (ADR-PROV-001)
        ↓
optional Client Portal Gateway process (127.0.0.1:5000)
   or optional IB Gateway desktop + TWS socket (127.0.0.1:4001/4002, stage 2)
        ↓
tools/ibkr/* stdlib processes (rate-limited REST client, SRP/TOTP login, watchdog)
        ↓ serialized JSONL captures (CAPTURED_NOT_ADMITTED)
src/market_platform_foundation/market_data/   (CPython 3.11 stdlib, unchanged)
```

No IBKR SDK is a dependency of `market_platform_foundation`. The Client Portal
Web API is plain HTTPS REST, so Stage 1 tooling is pure CPython 3.11 stdlib
(`urllib.request` + `ssl`, `hashlib`, `hmac`). The TWS socket collector uses
`ib_insync` in an out-of-repo venv and is never on the runtime path.

## Free data surface (no paid subscriptions)

| Surface | Endpoint family | Latency / limits |
|---|---|---|
| Delayed L1 quotes/bid/ask/last/volume | `/iserver/marketdata/snapshot` (+ pre-flight re-request pattern) | ~15–20 min delayed; global pacing applies |
| Historical OHLCV bars | `/hmds/history` | Strict pacing (see below); some surfaces entitlement-gated |
| Option chains/strikes/expiries | `/trsrv/secdef`, `/trsrv/secdef/info` | Global pacing |
| Market scanners | `/iserver/scanner` | Global pacing |
| Contract search/conids | `/iserver/secdef/search` | Global pacing |
| Own-account portfolio/positions | `/portfolio/*` | Read-only use only |

**Not available for free:** Level-2 depth (paid), real-time quotes without
entitlements, most news/fundamental analytics. Historical availability can be
entitlement-gated per exchange — the probe records OBSERVED capability only.

## Rate-limit compliance (client-enforced)

IBKR DOCUMENTED pacing (Client Portal Web API):

- Global limit: **10 requests/second** → enforced by a client-side token bucket.
- Violators receive HTTP 429 and enter a **15-minute penalty box** → the client
  stops all traffic on 429 and journals the event before backing off ≥15 min.
- Session keepalive: `/tickle` approximately every 60 s (5-minute session timeout).
- Historical bars (`/hmds/history`): single-flight (one concurrent request),
  ≥15 s spacing between identical bar-size/instrument queries, and a rolling
  ≤50 requests/10-min window cap enforced below IBKR's documented ceiling.

## Automation practices

- `watchdog.py`: `/tickle` every ~60 s; detects
  `connected:true, authenticated:false` and re-initializes the brokerage
  session via `POST /iserver/auth/ssodh/init`.
- Daily restart: IBKR requires re-authentication at least once after midnight
  ET; the watchdog performs a graceful gateway restart cycle after the daily
  reset window.
- Headless login: SRP-6a handshake against the gateway's local
  `/sso/Authenticator` + `/sso/Dispatcher` endpoints with RFC-6238 TOTP second
  factor (SF=4). This protocol is **undocumented/unofficial** and may change;
  manual browser login remains the fallback runbook. IBKR officially
  recommends against automating brokerage-session authentication.
- Weekly mobile 2FA push may still interrupt automation; when TOTP login fails
  the watchdog falls back to prompting for one manual login.

## Env gates (all default off/fail-closed)

`IMP_IBKR_LIVE`, `IMP_IBKR_TRANSPORT`, `IMP_IBKR_GATEWAY_URL` (must be loopback
or refused), `IMP_IBKR_TWS_HOST`, `IMP_IBKR_TWS_PORT`,
`IMP_IBKR_TWS_CLIENT_ID`, `IMP_IBKR_CAPTURE_ROOT`, `IMP_IBKR_PACING_*` knobs,
credential file
`.private/providers.env` (`IBKR_USERNAME`, `IBKR_PASSWORD`, `IBKR_TOTP_SECRET`;
never commit; redacted from every log/journal). See [`.env.example`](../../.env.example).

## Security boundary

Forbidden in this package: order submission/modification/cancellation, any
`/iserver/account/*/orders` write path, fund movement, paid entitlement
purchases, non-loopback hosts, WAN exposure of either gateway, committing
credentials. Captures are observational only and never inputs to execution.

## How to probe (after gateway install + first login)

Client Portal Gateway (the default):

```powershell
.venv\Scripts\python.exe tools\ibkr\probe.py --output evidence/market_data/ibkr/capability-report.json
```

Desktop IB Gateway / TWS socket:

```powershell
$env:IMP_IBKR_LIVE = "1"
$env:IMP_IBKR_TRANSPORT = "tws"
$env:IMP_IBKR_TWS_HOST = "127.0.0.1"
$env:IMP_IBKR_TWS_PORT = "4001"
.venv\Scripts\python.exe -m pip install ib_insync
.venv\Scripts\python.exe tools\ibkr\probe.py --symbol AAPL --output "$env:TEMP\ibkr-tws-capability-report.json"
```

The desktop Gateway must already be logged in and configured to accept local
socket API connections. The TWS adapter is observational only; it does not
expose order, funding, or execution operations. The optional `ib_insync`
dependency is loaded only when `IMP_IBKR_TRANSPORT=tws` is selected.

Bounded snapshot capture:

```powershell
.venv\Scripts\python.exe tools\ibkr\collectors\snapshot_quotes.py --symbols AAPL --seconds 30
```

Live opt-in tests:

```powershell
$env:IMP_IBKR_LIVE = "1"
.venv\Scripts\python.exe -m unittest discover -s tests/live_ibkr -v
```

Ordinary CI does **not** run `tests/live_ibkr`.

## Data admission

```text
OBSERVED → CAPTURED → VALIDATED → QUALITY_CHARACTERIZED → ADMITTED
```

Admission requires a separate ADR. Replay of captured JSONL is research-path
compatibility only (`CAPTURED_REPLAY_NOT_ADMITTED`).

## Related contracts

- Clocks: `event_time`, `provider_time`, `available_time`, `received_time`,
  `ingested_time`; live envelopes populate `live_received_time` and forbid
  `historical_ingested_time` (TC-002).
- Aggressor classification is not derivable from delayed L1; no provider-native
  aggressor claim is made.
- Quality: reuse existing quality flag vocabulary; delayed timestamps are
  annotated, never presented as real time.

## Known limitations

- Delayed L1 is 15–20 minutes behind; unsuitable for intrabar microstructure claims.
- No free depth-of-book anywhere on this surface.
- Headless SRP/TOTP login is unofficial and version-sensitive.
- ES futures acceptance remains blocked per `ADR-DATA-001`; captures are not
  admitted datasets regardless of instrument.
