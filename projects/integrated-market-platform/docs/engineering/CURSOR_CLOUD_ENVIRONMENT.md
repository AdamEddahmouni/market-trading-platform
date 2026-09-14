# Cursor Cloud Environment — Integrated Market Platform

This document lists **secret variable names only**. Never commit values. Configure actual secrets through [Cursor Cloud Secrets](https://cursor.com/dashboard?tab=cloud-agents).

## Base image

- Ubuntu (via `.cursor/Dockerfile` → `python:3.11-slim-bookworm` + Node.js 20)
- Python **3.11.15** target (see `phase0-dependency-lock.json`)
- `PYTHONPATH=src`

## Install (idempotent)

```bash
bash .cursor/install-cloud-deps.sh
```

Installs:

- `tzdata` (Windows companion; harmless on Linux)
- `numpy`, `pymongo`, `scikit-learn` (intelligence BUILD 04.5–09)
- UI dependencies via `npm ci` in `ui/`

## Validation commands

Default cloud validation is the `python tools/imp.py` pyramid from current
`main` (FAST → focused/affected → domain/changed → FULL), not
`python -m unittest discover`. `cloud-handoff/full-state-2026-08-25` is
historical; current landing is this monorepo's `origin/main` (`3bb5aa2f`, merged #29 then #30).

```bash
export PYTHONPATH=src
source .venv/bin/activate
python tools/imp.py validate fast
python tools/imp.py test affected
python tools/imp.py validate changed
python tools/imp.py validate full   # Paper-execution-path / release only
```

## Required secrets (names only)

### Intelligence persistence (optional — integration tests skip without Mongo)

| Name | Purpose |
|------|---------|
| `IMP_MONGODB_URI` | Operational intelligence MongoDB |
| `IMP_MONGODB_DATABASE` | Database name |
| `IMP_MONGODB_SERVER_SELECTION_TIMEOUT_MS` | Connection timeout |
| `IMP_TEST_MONGODB_URI` | Test MongoDB |
| `IMP_TEST_MONGODB_DATABASE` | Test database name |

### Live provider boundaries (all default off; not required for BUILD 01–09)

| Name | Purpose |
|------|---------|
| `IMP_MOOMOO_HOST` | Moomoo OpenD host (default `127.0.0.1`) |
| `IMP_MOOMOO_PORT` | Moomoo OpenD port (default `11111`) |
| `IMP_MOOMOO_LIVE` | Enable live Moomoo observational |
| `IMP_IBKR_GATEWAY_URL` | IBKR Client Portal Gateway |
| `IMP_IBKR_LIVE` | Enable live IBKR observational |
| `FINVIZ_API_KEY` | Finviz Elite export token |
| `IMP_FINVIZ_LIVE` | Enable live Finviz |
| `FRED_API_KEY` | FRED/ALFRED API |
| `EIA_API_KEY` | EIA Open Data API |
| `FINRA_CLIENT_ID` | FINRA OAuth client ID |
| `FINRA_CLIENT_SECRET` | FINRA OAuth client secret |
| `ANTHROPIC_API_KEY` | Assistant inference (not used by BUILD 09) |
| `APCA_API_KEY_ID` | Alpaca **Paper** key id (optional; missing → `COMPARATOR_NOT_CONFIGURED`) |
| `APCA_API_SECRET_KEY` | Alpaca **Paper** secret (optional; never commit; live host forbidden) |

See `.env.example` for the complete variable catalog. Paper keys belong in gitignored `.private`. Never set `APCA_API_BASE_URL` to `https://api.alpaca.markets`.

## Local-only services (not available in cloud VM)

| Service | Local endpoint | Cloud fallback |
|---------|----------------|----------------|
| Moomoo OpenD | `127.0.0.1:11111` | Fixtures, replay, mock paths; live gates remain off |
| IBKR TWS / Gateway socket | `127.0.0.1:4001` | One IBKR **transport**; not execution authority; not claimed available now |
| IBKR Client Portal Gateway | `https://127.0.0.1:5000/v1/api` | A **second** IBKR transport, not TWS and not the only path; not execution authority; not claimed available now |
| MongoDB (optional) | `127.0.0.1:27017` | `InMemoryIntelligenceRepository`; integration tests skip |

TWS (`4001`) and Client Portal (`5000`) are two IBKR transports. Neither grants Live execution. Do **not** treat `127.0.0.1:5000` as the only or TWS path. IBKR is not claimed available in cloud.

## Known validation differences

- `test_collector_excludes_generated_environment_paths` may fail locally when `.worktrees/mixed-live-screener/` exists on disk. Cloud checkout typically lacks that physical worktree directory.
- BUILD 09 intelligence tests require `numpy`, `pymongo`, `scikit-learn` in `.venv` (installed by cloud install script).

## Startup

No persistent services required for BUILD 01–09 unit/replay tests. Do **not** start MongoDB, OpenD, or IBKR gateway during environment install.
