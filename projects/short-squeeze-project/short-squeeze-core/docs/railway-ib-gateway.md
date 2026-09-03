# Railway IB Gateway sidecar

Run Interactive Brokers Gateway beside the research screener so
`CLOUD_PROVIDER_MODE` can use live IBKR market data with **deployer-supplied**
credentials. The screener remains read-only: it never places orders or opens
account/trading endpoints.

## Architecture

```text
┌─────────────────────────────┐   private network    ┌──────────────────────────┐
│  short-squeeze-screener     │  IBKR_HOST:PORT      │  ib-gateway              │
│  (CLOUD_PROVIDER_MODE)      │ ───────────────────► │  IB Gateway container    │
│  public Railway URL         │                      │  TWS_USERID / PASSWORD   │
└─────────────────────────────┘                      └──────────────────────────┘
```

Use **private networking only**. Do not publish IB API ports on a public domain.

## Prerequisites

- Railway project with **`short-squeeze-screener`** already deployed
- IBKR account credentials (paper recommended first)
- From this package root (`short-squeeze-core/`): synced `.railway-deploy/` tree
  (`make deploy-sync` then `make check-railway-mirror`)
- Optional: GitHub `RAILWAY_TOKEN` if you deploy via Actions

## Step 1 — Create the gateway service

In the Railway dashboard → your project → **New** → **Empty Service** → name it
exactly **`ib-gateway`**.

| Setting | Value |
|---|---|
| Root Directory | `short-squeeze-core/.railway-deploy/ib-gateway` |
| Config file | `railway.toml` under that root |

Or link locally:

```bash
cd short-squeeze-core/.railway-deploy/ib-gateway
railway link   # select project + ib-gateway service
```

## Step 2 — Gateway variables

Prefer syncing from the local private env file (never commit it):

```bash
cd short-squeeze-core
# Add IBKR_USER_ID=... and IBKR_PASSWORD=... to .private/providers.env
make railway-sync-ib-gateway-vars
```

| Variable | Required | Example |
|---|---|---|
| `TWS_USERID` | Yes | IB username |
| `TWS_PASSWORD` | Yes | IB password |
| `TRADING_MODE` | No | `paper` (default in `railway.toml`) |
| `TWS_ACCEPT_INCOMING` | No | `accept` (default) |
| `READ_ONLY_API` | No | `yes` (default) |

## Step 3 — Screener variables

On **short-squeeze-screener** → **Variables**:

| Variable | Value |
|---|---|
| `IBKR_ENABLED` | `true` |
| `IBKR_HOST` | `ib-gateway.railway.internal` |
| `IBKR_PORT` | `4004` (paper) or `4003` (live) |
| `IBKR_CLIENT_ID` | `27201` (or another unused client id) |

Private DNS is `{service-name}.railway.internal`. If you rename the gateway
service, update `IBKR_HOST` to match.

## Step 4 — Deploy

```bash
cd short-squeeze-core
make deploy-ib-gateway    # gateway first
# wait until the gateway container is healthy
make deploy               # screener, or restart the screener service
```

Deploy **gateway first**, wait until it is running, then redeploy or restart the
screener so bootstrap can connect.

## Verify

1. Screener `GET /api/providers` — IBKR should move off `UNAVAILABLE` once the
   API socket is up (often 1–2 minutes after gateway start).
2. `GET /api/readiness` / live candidate counts may rise when Finviz (and other
   discovery) is also configured.
3. Railway logs for **ib-gateway** — login and API listen messages from the image.

## Security

- Keep IB API ports on the private network only.
- Use **paper** until connectivity and market-data entitlements are confirmed.
- `READ_ONLY_API=yes` is set in the gateway `railway.toml` so the image starts
  in read-only API mode.
- Optional screener locks (`CSRF_PROTECTION`, `LOCK_SENSITIVE_API`) are documented
  in [SECURITY.md](SECURITY.md); they default off so existing cloud URLs stay usable.

## Troubleshooting

| Symptom | Check |
|---|---|
| Screener reports IBKR disabled | `IBKR_ENABLED=true` on screener; redeploy after env change |
| Connection timeout | `IBKR_HOST` matches service name; gateway healthy; port matches `TRADING_MODE` |
| Auth failed | `TWS_USERID` / `TWS_PASSWORD` on the **ib-gateway** service only |
| Client id in use | Change `IBKR_CLIENT_ID` on the screener |

## Related

- [DEPLOYMENT.md](DEPLOYMENT.md) — Docker and Railway overview
- [how-to-guides.md](how-to-guides.md) — operator recipes
- [CLI.md](CLI.md) — `make deploy-ib-gateway`, `make railway-sync-ib-gateway-vars`
- Monorepo ops note (if present): `../docs/deploy-workflow.md` at the repository root
