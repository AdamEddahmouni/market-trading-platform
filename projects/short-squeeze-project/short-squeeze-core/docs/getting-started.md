# Getting Started

Tutorial for a first successful run of the Short Squeeze Research Screener
(**version 0.16.0**) in **frozen demo** mode. No provider credentials are required.

**Audience:** engineers new to this repository.  
**Time:** about 10–15 minutes.  
**Outcome:** a local server answering `/health` and `/ready` on port `8787`.

## Prerequisites

- Git
- Python **3.12** (required; see `requires-python` in `pyproject.toml`)
- Network only for installing packages from PyPI (frozen mode itself is offline)

Confirm Python:

```powershell
py -3.12 --version
```

```bash
python3.12 --version
```

Expected: a line starting with `Python 3.12`.

## 1. Open the package root

All commands below run from `short-squeeze-core/` (the directory that contains
`pyproject.toml` and `apps/`).

If you cloned the monorepo:

```powershell
cd short-squeeze-core
```

```bash
cd short-squeeze-core
```

## 2. Create a virtual environment

### Windows PowerShell

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
```

### macOS / Linux

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[test]'
```

Optional sentiment extras (local FinBERT; not required for frozen demo):

```bash
python -m pip install -e '.[test,sentiment]'
```

## 3. Configure from the template

```powershell
Copy-Item .env.example .env
```

```bash
cp .env.example .env
```

`.env` is gitignored. Leave placeholders as-is for frozen demo, or set:

```text
SQUEEZE_APP_MODE=FROZEN_DEMO
PORT=8787
```

The process environment takes precedence over file defaults. You can also pass
`--config .env` when starting the app.

Validate without printing secret values:

```powershell
.\.venv\Scripts\python.exe -m apps.research_screener.config doctor --mode FROZEN_DEMO
```

```bash
python -m apps.research_screener.config doctor --mode FROZEN_DEMO
```

## 4. Start the application (frozen demo)

### Windows PowerShell

```powershell
$env:SQUEEZE_APP_MODE = "FROZEN_DEMO"
.\.venv\Scripts\python.exe -m apps.research_screener --no-browser
```

Equivalent entrypoint:

```powershell
$env:SQUEEZE_APP_MODE = "FROZEN_DEMO"
.\.venv\Scripts\python.exe start_local.py --no-browser
```

### macOS / Linux

```bash
export SQUEEZE_APP_MODE=FROZEN_DEMO
python -m apps.research_screener --no-browser
```

Open `http://127.0.0.1:8787/` in a browser (Scanner UI). Advanced Research is at
`/advanced`.

## 5. Verify health

### Windows PowerShell

```powershell
Invoke-RestMethod http://127.0.0.1:8787/health
Invoke-RestMethod http://127.0.0.1:8787/ready
Invoke-RestMethod http://127.0.0.1:8787/api/v1/integration/manifest
```

### macOS / Linux

```bash
curl -s http://127.0.0.1:8787/health | python -m json.tool
curl -s http://127.0.0.1:8787/ready | python -m json.tool
curl -s http://127.0.0.1:8787/api/v1/integration/manifest | python -m json.tool
```

Expected: JSON envelopes with `status` / readiness fields and no credential
values. Frozen mode serves a deterministic set of **13** candidates.

Optional acceptance script (from another terminal, with the server running or in
built-in frozen mode):

```bash
python tools/integration_acceptance.py --mode frozen
```

Offline unit tests:

```bash
python -m pytest -p no:cacheprovider --basetemp .pytest-run
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `Python was not found` / wrong version | 3.12 not on PATH | Install 3.12; use `py -3.12` or `python3.12` explicitly |
| Port already in use | Another process on `8787` | Set `PORT=8790` (or free the port) and retry |
| Import errors for `apps` | Wrong working directory or missing editable install | `cd` to `short-squeeze-core` and re-run `pip install -e ".[test]"` |
| Doctor reports missing providers | Expected in frozen demo | Frozen mode does not need live keys |
| Browser cannot connect | Server bound elsewhere or failed to start | Confirm the start command printed the listen address; check firewall only if you changed bind host |
| Docker Compose URL works but `python -m` does not | Different port mapping | Native default is `8787`; Compose maps host `8787` → container `8080` |

## Next steps

- [How-to guides](how-to-guides.md) — local full mode, cloud providers, Railway, security locks
- [CONFIGURATION.md](CONFIGURATION.md) — full environment reference
- [Reproducibility](reproducibility.md) — what runs offline vs what needs credentials
- [Documentation index](README.md) — Diátaxis map of all current-truth docs
