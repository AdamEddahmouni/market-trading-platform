# IB Gateway on Railway

Sidecar service for `short-squeeze-screener` in `CLOUD_PROVIDER_MODE` with `IBKR_ENABLED=true`.

## One-time setup

1. In the **same Railway project** as the screener, add a service named **`ib-gateway`**.
2. Set **Root Directory** to `short-squeeze-core/.railway-deploy/ib-gateway` (monorepo) or deploy with CLI from this folder.
3. On the **ib-gateway** service, set variables:
   - `TWS_USERID` — IB account username
   - `TWS_PASSWORD` — IB account password
   - `TRADING_MODE` — `paper` (default in `railway.toml`) or `live`
4. On **short-squeeze-screener**, set:
   - `IBKR_ENABLED` = `true`
   - `IBKR_HOST` = `ib-gateway.railway.internal` (must match the service name)
   - `IBKR_PORT` = `4004` for paper (`gnzsnz` internal API port); use `4003` for live
   - `IBKR_CLIENT_ID` = `27201` (or any unused client id)

Private networking must be enabled (default within a Railway project). The screener reaches the gateway over the private domain; the API is **not** exposed on the public internet.

## Deploy

```bash
cd short-squeeze-core/.railway-deploy/ib-gateway
railway up --detach --environment production --service ib-gateway
```

Or push to `main` — GitHub Actions runs `deploy-ib-gateway` when this directory changes.

## Local equivalent

See `docker-compose.yml` (`ib-gateway` + `docker-compose.local.yml` for `IBKR_HOST=ib-gateway`).
