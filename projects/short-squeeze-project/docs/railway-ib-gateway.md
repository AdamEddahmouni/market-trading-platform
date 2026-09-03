# Railway IB Gateway sidecar

Run Interactive Brokers Gateway next to the research screener so cloud mode can use live IBKR data with **deployer-supplied credentials**.

## Architecture

```text
┌─────────────────────────────┐     private network      ┌──────────────────────────┐
│  short-squeeze-screener     │  IBKR_HOST + IBKR_PORT   │  ib-gateway              │
│  (CLOUD_PROVIDER_MODE)      │ ───────────────────────► │  ghcr.io/gnzsnz/ib-gateway │
│  public *.up.railway.app    │                          │  TWS_USERID / PASSWORD   │
└─────────────────────────────┘                          └──────────────────────────┘
```

## Prerequisites

- Railway project with **`short-squeeze-screener`** already deployed.
- IBKR account credentials (paper recommended first).
- GitHub `RAILWAY_TOKEN` secret (same as the screener deploy workflow).

## Step 1 — Create the gateway service

In [Railway Dashboard](https://railway.app/dashboard) → your project → **New** → **Empty Service** → name it **`ib-gateway`**.

Set:

| Setting | Value |
|---------|--------|
| Root Directory | `short-squeeze-core/.railway-deploy/ib-gateway` |
| Config file | `railway.toml` (under that root) |

Or link locally:

```bash
cd short-squeeze-core/.railway-deploy/ib-gateway
railway link   # select project + ib-gateway service
```

## Step 2 — Gateway variables

On the **ib-gateway** service → **Variables** (or from repo root after editing `.private/providers.env`):

```bash
cd short-squeeze-core
# Add IBKR_USER_ID=... and IBKR_PASSWORD=... to .private/providers.env
make railway-sync-ib-gateway-vars
```

| Variable | Required | Example |
|----------|----------|---------|
| `TWS_USERID` | Yes | your IB username |
| `TWS_PASSWORD` | Yes | your IB password |
| `TRADING_MODE` | No | `paper` (default in `railway.toml`) |
| `TWS_ACCEPT_INCOMING` | No | `accept` (default) |
| `READ_ONLY_API` | No | `yes` (default) |

## Step 3 — Screener variables

On **short-squeeze-screener** → **Variables**:

| Variable | Value |
|----------|--------|
| `IBKR_ENABLED` | `true` |
| `IBKR_HOST` | `ib-gateway.railway.internal` |
| `IBKR_PORT` | `4004` (paper) or `4003` (live) |
| `IBKR_CLIENT_ID` | `27201` |

Service private DNS is `{service-name}.railway.internal`. If you rename the gateway service, update `IBKR_HOST` to match.

## Step 4 — Deploy

Push changes under `short-squeeze-core/.railway-deploy/ib-gateway/` to `main`, or:

```bash
make deploy-ib-gateway    # from short-squeeze-core/
make deploy               # screener only
```

Deploy **gateway first**, wait until the container is running, then redeploy or restart the screener so bootstrap can connect.

## Verify

1. Screener `/api/providers` — IB Gateway should move off `UNAVAILABLE` once the API socket is up (may take 1–2 minutes after gateway start).
2. `/api/readiness` — `At least one current candidate` may increase when scanner + Finviz are configured.
3. Railway logs for **ib-gateway** — login and API listen messages from the image.

## Security notes

- Do not publish IB API ports on a public Railway domain; use **private networking** only.
- Use **paper** until connectivity and entitlements are confirmed.
- `READ_ONLY_API=yes` is set in `railway.toml` so the gateway image starts in read-only API mode.

## Troubleshooting

| Symptom | Check |
|---------|--------|
| Screener still `IBKR disabled` | `IBKR_ENABLED=true` on screener, redeploy after code on `main` with cloud IBKR support |
| Connection timeout | `IBKR_HOST` matches service name; gateway pod healthy; port `4004`/`4003` matches `TRADING_MODE` |
| Auth failed | `TWS_USERID` / `TWS_PASSWORD` on **ib-gateway** service only |
| Client id in use | Change `IBKR_CLIENT_ID` on screener |

See also [deploy-workflow.md](./deploy-workflow.md).

**Canonical package guide:** [`short-squeeze-core/docs/railway-ib-gateway.md`](../short-squeeze-core/docs/railway-ib-gateway.md)
(Makefile targets and product docs point there).
