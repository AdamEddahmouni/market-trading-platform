# Local Development

**Status:** Verified setup commands.

## Prerequisites

- CPython 3.11 (3.11.15 tested)
- Node.js + npm
- Git
- Windows: optional Moomoo OpenD on `127.0.0.1:11111` for live quotes

## One-time setup

### Python venv

```powershell
cd integrated-market-platform
uv venv --python <cpython-3.11-path> .venv
uv pip install --python .venv\Scripts\python.exe tzdata
```

### Frontend

```powershell
cd ui
npm install
```

## Start platform (Windows)

Double-click `START_PLATFORM.cmd` or:

```powershell
# API (repo root)
$env:PYTHONPATH='src'
.venv\Scripts\python.exe tools\ui1\run_ui_api.py --serve --port 8766

# UI (separate terminal)
cd ui
npm run dev
```

Opens `http://127.0.0.1:5173`. API at `http://127.0.0.1:8766`.

### With paper + live observational

Set env vars per [CONFIGURATION.md](CONFIGURATION.md), then restart API:

```powershell
powershell -File tools\ui1\restart_ui_api.ps1
```

## Validation

```powershell
$env:PYTHONPATH='src'
.venv\Scripts\python.exe tools\validate.py changed

cd ui
npm test
npm run build
```

## Common issues

| Issue | Fix |
|-------|-----|
| `enum.StrEnum` ImportError | Wrong Python version — use `.venv` 3.11 |
| `zoneinfo` KeyError | Install `tzdata` in venv (Windows) |
| Stale API after env change | Restart API process |
| Port 8766 in use | Kill stale listener; `restart_ui_api.ps1` |
| Moomoo disconnected | Start OpenD separately — UI still works |

See [RUNBOOK.md](../operations/RUNBOOK.md).

## Cursor Cloud

See [CURSOR_CLOUD_ENVIRONMENT.md](CURSOR_CLOUD_ENVIRONMENT.md).
