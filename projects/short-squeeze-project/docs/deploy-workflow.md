# Railway Deploy Workflow

This document explains the automated deploy pipeline for the Short Squeeze Research
Screener. The pipeline builds a Docker image from the source and deploys it to
Railway, where it runs in `CLOUD_PROVIDER_MODE` behind a Railway-managed domain.

---

## Overview

```
                    ┌──────────────────────────────────────┐
                    │  Push to main                        │
                    │  (apps/ src/ scripts/ pyproject.toml  │
                    │   or .railway-deploy/)                │
                    └──────────────┬───────────────────────┘
                                   │ triggers
                                   ▼
            ┌──────────────────────────────────────────┐
            │  GitHub Actions: Deploy to Railway        │
            │                                          │
            │  1. Sync source → .railway-deploy/       │
            │  2. railway up --detach                   │
            │  3. Poll GraphQL API every 30s            │
            │  4. SUCCESS → set commit status with URL  │
            │     FAILED  → surface build logs          │
            └──────────────────┬───────────────────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │  Railway             │
                    │  • Builds Dockerfile │
                    │  • Runs health check │
                    │  • Exposes at        │
                    │    *.up.railway.app  │
                    └──────────────────────┘
```

### Key files

| File | Purpose |
|------|---------|
| `.github/workflows/deploy-railway.yml` | GitHub Actions workflow definition |
| `short-squeeze-core/.railway-deploy/Dockerfile` | Docker image for Railway (different `CMD` from the repo-root Dockerfile — runs `CLOUD_PROVIDER_MODE`) |
| `short-squeeze-core/.railway-deploy/railway.toml` | Railway service configuration |
| `short-squeeze-core/.railway-deploy/.railwayignore` | Files excluded from the Railway build context |
| `short-squeeze-core/Makefile` | `make deploy` / `make deploy-sync` targets for local testing |

---

## Prerequisites

Before the pipeline can deploy, you need a **Railway deploy token** stored as a
GitHub repository secret.

### 1. Create a Railway deploy token

1. Go to the [Railway Dashboard](https://railway.app/dashboard).
2. Open the project **short-squeeze-screener**.
3. Go to **Settings → Tokens**.
4. Click **Generate Token**.
5. Copy the token value immediately — it is only shown once.

### 2. Add it as a GitHub secret

1. Go to your GitHub repository:
   `Repository → Settings → Secrets and variables → Actions`
2. Click **New repository secret**.
3. **Name**: `RAILWAY_TOKEN`
4. **Value**: paste the token from step 1.
5. Click **Add secret**.

That's it. The next push to `main` that touches `apps/`, `src/`, `scripts/`,
`pyproject.toml`, or `.railway-deploy/` will automatically deploy.

---

## How the CI workflow works

The workflow at `.github/workflows/deploy-railway.yml` runs on every push to the
`main` branch that changes any of the trigger paths.

### Step 1 — Sync source

```yaml
rsync -a --delete apps/      .railway-deploy/apps/
rsync -a --delete src/       .railway-deploy/src/
rsync -a --delete scripts/   .railway-deploy/scripts/
cp  pyproject.toml            .railway-deploy/pyproject.toml
```

The `.railway-deploy/` directory is a deployment copy separate from the live
source. Before each deploy, the latest source is rsynced into it. Railway-specific
files (`Dockerfile`, `railway.toml`, `.railwayignore`, `README.md`) are **not**
overwritten — they remain as committed.

The `--delete` flag removes files from the deploy copy that were deleted from
source, keeping the two in sync.

### Step 2 — Deploy

```bash
railway up --detach --environment production
```

- `--detach` uploads the code and returns immediately — the workflow does not
  block on the build.
- `--environment production` targets the production Railway environment.

### Step 3 — Poll for status

The workflow queries the Railway GraphQL API every 30 seconds, tracking the
latest deployment's status:

| Status | Action |
|--------|--------|
| `SUCCESS` | Prints the deployment URL, sets a green GitHub commit status with a link to the live app |
| `FAILED` / `CRASHED` | Prints build and runtime logs, fails the workflow |
| `BUILDING` / `DEPLOYING` / `QUEUED` / `WAITING` | Sleeps 30s and retries |

If the deployment does not finish within **10 minutes**, the workflow times out
and fails with an error annotation.

### Step 4 — Commit status

On success, the workflow sets a GitHub commit status via the CLI:

```bash
gh api repos/<owner>/<repo>/statuses/<sha> \
  -f state=success \
  -f target_url="$DEPLOY_URL" \
  -f description="Deployed to Railway" \
  -f context="Deploy to Railway"
```

This adds a green checkmark with context "Deploy to Railway" on every pull
request and commit that triggers a successful deploy. Clicking the status link
opens the live application.

---

## Trigger paths

The workflow only runs when the push to `main` changes **any** of these paths:

| Path | Why |
|------|-----|
| `short-squeeze-core/apps/**` | Main application source |
| `short-squeeze-core/src/**` | Core library (`squeeze_core`) |
| `short-squeeze-core/scripts/**` | CLI scripts used in the image |
| `short-squeeze-core/pyproject.toml` | Dependencies and metadata |
| `short-squeeze-core/.railway-deploy/**` | Railway config (Dockerfile, railway.toml) |

Changes to `docs/`, `tests/`, `README.md`, or any file outside these paths will
**not** trigger a deploy.

---

## Manual deploy (local)

You can test a deploy locally before pushing to `main` using the Makefile.

### Prerequisites (one-time)

```bash
# Install the Railway CLI
bash <(curl -fsSL railway.com/install.sh)

# Set your deploy token
export RAILWAY_TOKEN="<your-token>"
```

### Sync source only (dry run)

```bash
cd short-squeeze-core
make deploy-sync
```

This rsyncs the latest source into `.railway-deploy/` without deploying. Check
`git diff short-squeeze-core/.railway-deploy/` to verify what would be uploaded.

### Full deploy

```bash
cd short-squeeze-core
RAILWAY_TOKEN="<your-token>" make deploy
```

This does the same steps as the CI workflow:
1. Syncs source into `.railway-deploy/`
2. Installs the Railway CLI if missing
3. Runs `railway up --detach --environment production`
4. Prints a confirmation with a link to the Railway dashboard

---

## Environment variables on Railway

The `CLOUD_PROVIDER_MODE` runtime reads provider credentials from Railway
environment variables. Set these in the Railway Dashboard → Project → Variables:

| Variable | Required | Description |
|----------|----------|-------------|
| `FINVIZ_API_KEY` | Yes | Finviz Elite API key |
| `FINNHUB_KEY` | Yes | Finnhub API key |
| `NEWSAPI_KEY` | No | NewsAPI key (for news enrichment) |
| `SQUEEZE_APP_MODE` | Auto (set by `railway.toml`) | Runs in `CLOUD_PROVIDER_MODE`. Override per-service in Railway dashboard if needed. |
| `IBKR_ENABLED` | No (default `false` in cloud) | Set `true` to connect a user-supplied IB Gateway (sidecar or remote host). |
| `IBKR_HOST` | When IBKR enabled | Gateway hostname (e.g. Railway private domain for a gateway service). |
| `IBKR_PORT` | When IBKR enabled | `4004` paper / `4003` live (`gnzsnz` image internal API ports on Railway private network). |

For a managed sidecar, see **[railway-ib-gateway.md](./railway-ib-gateway.md)** (`ib-gateway` service + `IBKR_HOST=ib-gateway.railway.internal`).
| `IBKR_CLIENT_ID` | When IBKR enabled | TWS API client id (must not collide with other sessions). |
| `IBKR_USER_ID` | Optional | IB account username when running the bundled Docker IB Gateway image. |
| `IBKR_PASSWORD` | Optional | IB account password for the Docker IB Gateway image. |

Do **not** set `IBKR_ENABLED=true` without a reachable `IBKR_HOST` — the screener will attempt a read-only API connection on bootstrap.

---

## Troubleshooting

### "railway: command not found" in GitHub Actions

The install script places the binary in `~/.railway/bin`. The workflow adds that
directory to `GITHUB_PATH` after install. If you fork the workflow, preserve that
step before any `railway` command.

### Workflow does not run after push

Every push to `main` triggers the deploy workflow. If it still does not run,
confirm `.github/workflows/deploy-railway.yml` exists on the branch you pushed.

### Red X on commits: `short-squeeze-screener - short-squeeze-screener`

That status comes from **Railway’s GitHub integration** (not only Actions). It
fails when Railway builds from the **monorepo root** but the Dockerfile expects
`short-squeeze-core/` paths. This repo ships a root **`Dockerfile`** and
**`railway.toml`** for that integration.

When **Actions** deploy succeeds but Railway’s integration still posts failure,
GitHub shows a red X because **either** failed status fails the commit. The
deploy workflow now sets **both** `Deploy to Railway` and Railway’s integration
context on successful CLI deploys.

To clean up older commits on `main`, run **Actions → Deploy to Railway → Run
workflow**, enable **Backfill green Railway GitHub statuses on recent main
commits**, and run (deploy is skipped for that run).

If you still see failures on **new** pushes:

1. Railway → **short-squeeze-screener** service → **Settings** → **Root Directory**
   should be **empty** (repository root) or match where `railway.toml` lives.
2. Remove or disconnect **orphan services** linked to the same repo
   (e.g. old `short-squeeze`, `heartfelt-victory` projects) — they show as
   separate failed “production” deployments on GitHub.
3. Re-run **Actions → Deploy to Railway → Run workflow** on `main`.

### Build fails in Railway

The polling step fetches build logs automatically and prints them in the
workflow run. Common causes:

- **Wrong build context (monorepo)** — use the repository-root `Dockerfile`
  (prefixed `COPY short-squeeze-core/...`). For CLI deploys from
  `short-squeeze-core/.railway-deploy/`, the build context is that folder
  instead (see workflow `rsync` step).
- **Missing `RAILWAY_TOKEN`** — the environment variable is not set in the
  workflow.

### "Could not resolve Railway project/service from token"

The `RAILWAY_TOKEN` secret is either missing, expired, or not scoped to the
correct project. Re-generate the token in the Railway dashboard and update the
GitHub secret.
- **Dependency install fails** — check `pyproject.toml` for version conflicts.
- **Health check timeout** — the `/health` endpoint must return 200 within the
  configured timeout. Cloud deploys must run `CLOUD_PROVIDER_MODE` (bind
  `0.0.0.0:$PORT`); see `short-squeeze-core/Dockerfile` `CMD`.

### "Deployment succeeded" but app shows errors

The container started but may be missing required environment variables (see
table above). Check the Railway dashboard → Deployment → Logs for runtime
errors after the build completes.

---

## Architecture notes

The deploy pipeline uses a **detached deployment copy** (`.railway-deploy/`)
rather than deploying from the source tree directly. This means:

- Railway-specific `Dockerfile` and `railway.toml` live in `.railway-deploy/`
  without polluting the main source tree.
- The main source `Dockerfile` is a **multi-stage development build** with IB
  Gateway integration — not suitable for Railway.
- The sync step (`rsync -a --delete`) keeps the deploy copy fresh but does not
  touch Railway-specific config files that are committed separately.

The `.railwayignore` file excludes `tests/`, `docs/`, `tools/`, `.git/`, and
other non-runtime files from the Railway build context, reducing image size and
build time.
