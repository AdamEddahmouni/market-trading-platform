# Local Development

**Status:** Verified setup commands.

## Prerequisites

- CPython 3.11 (3.11.15 tested)
- Node.js + npm
- Git
- Windows: optional Moomoo OpenD on `127.0.0.1:11111` for live quotes

## One-time setup

### Windows operator setup (recommended)

From File Explorer, double-click `SETUP_PLATFORM.cmd` in the repository root.
The script performs a value-blind preflight, repairs `.venv`, installs the
declared runtime and UI dependencies with `npm ci`, creates `.local` and
`.private`, and validates `.env` syntax. It does not install OS software or
display secret values. Choose **Enter Demo** after setup to start the local
workstation, or **Continue setup** to finish provider configuration first.

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
The canonical browser control center is `http://127.0.0.1:5173/control`.
The launcher supervisor uses `http://127.0.0.1:8767` and is loopback-only.

Use `/control` for lifecycle actions, independent provider readiness,
value-masked provider configuration, asynchronous refresh requests, and
guarded application update checks. Update apply is blocked when the worktree
is dirty and only permits fast-forward pulls.

### With paper + live observational

Set env vars per [CONFIGURATION.md](CONFIGURATION.md), then restart API:

```powershell
powershell -File tools\ui1\restart_ui_api.ps1
```

## Validation

```powershell
$env:PYTHONPATH='src'
python tools\imp.py test affected

cd ui
npm test
npm run build
```

The complete developer command surface, validation pyramid, closure report,
and local telemetry behavior are documented in
[DEVELOPER_OPERATING_SYSTEM.md](DEVELOPER_OPERATING_SYSTEM.md).

## Common issues

| Issue | Fix |
|-------|-----|
| `enum.StrEnum` ImportError | Wrong Python version — use `.venv` 3.11 |
| `zoneinfo` KeyError | Install `tzdata` in venv (Windows) |
| Stale API after env change | Restart API process |
| Port 8766 in use | Kill stale listener; `restart_ui_api.ps1` |
| Moomoo disconnected | Start OpenD separately — UI still works |
| Update is blocked | Resolve tracked worktree changes, then run Check for updates again |

See [RUNBOOK.md](../operations/RUNBOOK.md).

## Cursor Cloud

See [CURSOR_CLOUD_ENVIRONMENT.md](CURSOR_CLOUD_ENVIRONMENT.md).
