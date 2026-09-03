# Deployment

## Docker (single image)

The Dockerfile exposes container port **8080**. Set `PORT` accordingly when
publishing ports.

```bash
docker build -t short-squeeze-research-screener .
docker run --rm -p 8787:8080 \
  -e PORT=8080 \
  -e SQUEEZE_APP_MODE=FROZEN_DEMO \
  short-squeeze-research-screener
```

Verify `/health`, `/ready`, and `/api/v1/integration/manifest` on
`http://127.0.0.1:8787`.

## Docker Compose (local stack)

From `short-squeeze-core/`:

```bash
cp .env.example .env   # optional keys; frozen demo works without
docker compose up
# browser: http://127.0.0.1:8787/  (maps 8787→8080)
```

| Service | Role |
|---|---|
| `screener` | App in `CLOUD_PROVIDER_MODE` by default (`PORT=8080`) |
| `ib-gateway` | Optional IB Gateway image; needs `IBKR_USER_ID` / `IBKR_PASSWORD` |

Full local IBKR-consuming mode:

```bash
docker compose -f docker-compose.yml -f docker-compose.local.yml up
# or: make up-full
```

Makefile wrappers: [CLI.md](CLI.md).

## Railway

Deploy the sanitized tree (`.railway-deploy/` or the configured GitHub Action),
not a private configuration directory.

1. Sync and verify mirror:

```bash
make deploy-sync
make check-railway-mirror
```

`python tools/check_railway_mirror.py` fails if `apps/`, `src/`, `scripts/`,
`tools/`, or `pyproject.toml` drift between the working tree and `.railway-deploy/`.

2. Set variables in Railway’s secret store:

| Variable | Notes |
|---|---|
| `SQUEEZE_APP_MODE` | `CLOUD_PROVIDER_MODE` or `FROZEN_DEMO` |
| `PORT` | Usually injected by the platform |
| `FINVIZ_API_KEY` / `FINNHUB_KEY` | For live cloud screening |
| `NEWSAPI_KEY` | Optional |
| `CSRF_PROTECTION` / `LOCK_SENSITIVE_API` | Optional; default off |

Do not configure a local-only IBKR probe. Optional IB Gateway sidecar:
full walkthrough in [railway-ib-gateway.md](railway-ib-gateway.md)
(`make deploy-ib-gateway`, then point `IBKR_HOST` at the internal hostname).

3. Deploy:

```bash
make deploy
```

4. Smoke:

```bash
python tools/integration_acceptance.py --url https://your-service.example --json
```

Review public responses for secret, account, and local-path leakage before
sharing the URL. More recipes: [how-to-guides.md](how-to-guides.md).
