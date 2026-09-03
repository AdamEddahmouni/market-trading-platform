# CLI and Make targets

Reference for entrypoints and convenience targets. Run from `short-squeeze-core/`.

## Python entrypoints

| Command | Purpose |
|---|---|
| `python -m apps.research_screener` | Canonical HTTP app launcher |
| `python -m apps.research_screener --no-browser` | Headless |
| `python -m apps.research_screener --mode FROZEN_DEMO` | Explicit mode |
| `python -m apps.research_screener --config .env` | Load explicit env file |
| `python start_local.py` | Local workstation helper (`LOCAL_FULL` path, optional `--profile` Gateway) |
| `python start_cloud.py` | Cloud helper (`CLOUD_PROVIDER_MODE`, no private file) |
| `python -m apps.research_screener.config doctor` | Redacted configuration report |
| `python -m apps.research_screener.config doctor --json` | Machine-readable doctor |
| `python tools/integration_acceptance.py --mode frozen` | Frozen acceptance |
| `python tools/integration_acceptance.py --url URL --json` | Remote acceptance |
| `python tools/build_handoff_release.py --json` | Allowlisted release build |
| `python tools/release_audit.py <release-dir> --json` | Privacy audit of a release tree |
| `python tools/check_railway_mirror.py` | Fail if `.railway-deploy` drifts from source |
| `python -m pytest -p no:cacheprovider --basetemp .pytest-run` | Offline tests |

Optional: `squeeze-core` console script from the installed package (`squeeze_core.__main__`) for core library CLI use; the research screener UI/API uses the `apps.research_screener` module path above.

## Make targets

`make help` prints the same list. GNU Make is required (native Linux/macOS; on
Windows use WSL or a Make-compatible environment). PowerShell users can run the
Python commands directly.

| Target | Action |
|---|---|
| `make up` | Docker Compose: frozen demo screener + IB Gateway |
| `make up-full` | Compose with `docker-compose.local.yml` (`LOCAL_FULL`, wait for Gateway health) |
| `make build` | Rebuild screener image |
| `make dev` | `python -m apps.research_screener` without Docker |
| `make logs` / `logs-screener` / `logs-gateway` | Tail logs |
| `make down` / `stop` / `clean` | Stop / remove / remove volumes |
| `make doctor` / `doctor-json` | Configuration doctor |
| `make deploy-sync` | Rsync source into `.railway-deploy/` |
| `make check-railway-mirror` | Verify mirror matches source |
| `make deploy` | Sync + `railway up` for screener service |
| `make deploy-ib-gateway` | Deploy Gateway sidecar ([railway-ib-gateway.md](railway-ib-gateway.md)) |
| `make railway-sync-ib-gateway-vars` | Push IBKR login from `.private/providers.env` to Railway |
| `make precommit` / `precommit-quick` / `test-quick` | Import and smoke checks |
| `make install-hooks` | Install repo pre-commit hook |

## Port reminder

| Context | Port |
|---|---|
| Native local default | `8787` |
| Docker Compose browser URL | `http://127.0.0.1:8787/` |
| Inside Compose/Dockerfile container | `8080` (`PORT=8080`, publish `8787:8080`) |
| Railway | Platform `$PORT` |
