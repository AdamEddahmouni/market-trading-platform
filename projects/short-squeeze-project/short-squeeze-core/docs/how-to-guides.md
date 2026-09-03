# How-to guides

Task-oriented recipes. For a first run, use [Getting Started](getting-started.md).
For variable definitions, use [CONFIGURATION.md](CONFIGURATION.md).

## Run frozen demo (offline)

Frozen mode uses bundled sanitized data. No provider credentials are required.

```bash
export SQUEEZE_APP_MODE=FROZEN_DEMO   # PowerShell: $env:SQUEEZE_APP_MODE = "FROZEN_DEMO"
python -m apps.research_screener --no-browser
```

Verify: `GET http://127.0.0.1:8787/health` and `/api/frozen/candidates`.

Docker (image listens on container port from `PORT`; Compose maps **8787→8080**):

```bash
docker build -t short-squeeze-research-screener .
docker run --rm -p 8787:8080 -e PORT=8080 -e SQUEEZE_APP_MODE=FROZEN_DEMO short-squeeze-research-screener
```

Or: `make up` (Compose frozen demo + IB Gateway sidecar; screener still frozen by default).

## Run LOCAL_FULL on a workstation

1. Copy `.env.example` to `.env` and/or create `.private/providers.env`.
2. Set `SQUEEZE_APP_MODE=LOCAL_FULL`.
3. Enable only providers you hold credentials for (`FINVIZ_ENABLED`, `FINNHUB_ENABLED`, etc.).
4. For IBKR: set `IBKR_ENABLED=true`, `IBKR_HOST`, `IBKR_PORT`, `IBKR_CLIENT_ID`, and (for Gateway login) `IBKR_USER_ID` / `IBKR_PASSWORD` in the private file.
5. Start:

```bash
python start_local.py --no-browser
# or with Docker-managed Gateway:
python start_local.py --profile --no-browser
```

```powershell
.\.venv\Scripts\python.exe start_local.py --no-browser
```

Doctor:

```bash
python -m apps.research_screener.config doctor --mode LOCAL_FULL --json
```

Private provider files load only in `LOCAL_FULL`. Cloud and frozen modes never load them.

## Configure cloud providers (no local IBKR probe)

Set environment variables (platform secret store or process env), not a private file:

| Minimum for live cloud screening | Optional |
|---|---|
| `SQUEEZE_APP_MODE=CLOUD_PROVIDER_MODE` | `NEWSAPI_KEY` |
| `FINVIZ_API_KEY` | `SEC_USER_AGENT` (descriptive org + contact) |
| `FINNHUB_KEY` | Remote `IBKR_HOST` if a reachable gateway exists |

```bash
python start_cloud.py
# or
python -m apps.research_screener --mode CLOUD_PROVIDER_MODE --no-browser
```

Cloud binds `0.0.0.0:$PORT`. Local FinBERT sentiment is not a cloud dependency.

## Deploy on Railway

1. Prefer the sanitized deploy tree: sync with `make deploy-sync`, then deploy with `make deploy`, **or** push through the project’s GitHub Action path.
2. Before deploy, ensure the mirror matches source:

```bash
python tools/check_railway_mirror.py
# or
make check-railway-mirror
```

Drift fails the check; fix with `make deploy-sync` (rsync of `apps/`, `src/`, `scripts/`, `tools/`, and `pyproject.toml` into `.railway-deploy/`).

3. In Railway variables, set `SQUEEZE_APP_MODE=CLOUD_PROVIDER_MODE` (or `FROZEN_DEMO`), `PORT` as provided by the platform, and provider secrets. Do not upload `.env` or `.private/`.
4. Optional IB Gateway sidecar: follow [railway-ib-gateway.md](railway-ib-gateway.md)
   (`make deploy-ib-gateway`, set screener `IBKR_HOST` to the internal hostname, sync
   credentials with `make railway-sync-ib-gateway-vars` only after `IBKR_USER_ID` /
   `IBKR_PASSWORD` exist in `.private/providers.env`).
5. Smoke:

```bash
python tools/integration_acceptance.py --url https://your-service.example --json
```

See [DEPLOYMENT.md](DEPLOYMENT.md).

## Enable providers (IBKR / Finviz / News / SEC)

1. Set the `*_ENABLED` flag to `true` and supply the credential named in [PROVIDERS.md](PROVIDERS.md).
2. Restart the process (configuration is immutable after start).
3. Confirm with `doctor` and `GET /api/providers`.

| Need | Configure |
|---|---|
| SI %, DTC, float, relative volume | `FINVIZ_API_KEY` |
| Quote / news fallback | `FINNHUB_KEY` |
| Display news | `NEWSAPI_KEY` and/or Finnhub news |
| Filings / catalyst timestamps | `SEC_ENABLED` + valid `SEC_USER_AGENT` |
| Bars, shortability, borrow fee | Local or remote IBKR (`IBKR_*`) |

Disabled providers report `DISABLED`. Missing credentials report `NOT_CONFIGURED`.

## Operate collectors

See [COLLECTORS.md](COLLECTORS.md). Master switch: `COLLECTORS_ENABLED`. For CI or locked-down demos, set `COLLECTORS_ENABLED=false`. Inspect `GET /api/collectors/status`.

## Enable optional security locks

Default is **off** so a public Railway URL remains usable without CSRF headers.

| Variable | Effect when `1` / `true` |
|---|---|
| `CSRF_PROTECTION` | State-changing requests require `X-CSRF-Token` matching cookie `squeeze_csrf` from `GET /api/csrf-token` |
| `LOCK_SENSITIVE_API` | In cloud mode, `/api/export`, `/api/logs/*`, and `/api/collectors/*` require a valid CSRF cookie/header pair; `LOCAL_FULL` stays open |

If a CSRF cookie is already present, mutating requests validate it even when
`CSRF_PROTECTION` is off (soft-gate for local UI adoption).

Checklist:

1. Set flags in the deployment secret store.
2. Redeploy / restart.
3. Clients: `GET /api/csrf-token`, then send cookie + `X-CSRF-Token` on mutating calls.
4. Confirm unauthenticated mutating calls receive `403` when locks are on.

Details: [SECURITY.md](SECURITY.md).

## Morning repository check

From `short-squeeze-core/`:

```powershell
.\morning_check.ps1
```

The script reports working-tree status, release source commit, and final test report
hooks used by the professional handoff workflow. It does not rotate credentials.

## Sync deploy mirror without uploading

```bash
make deploy-sync
make check-railway-mirror
```

Use this before `make deploy` or CI upload so `.railway-deploy/` matches `apps/`,
`src/`, `scripts/`, and `tools/`.
