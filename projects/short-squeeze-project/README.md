# Short Squeeze Research Screener

Read-only research screener for short-squeeze candidate analysis. The application
lives in **[`short-squeeze-core/`](short-squeeze-core/)**.

| Item | Location |
|---|---|
| Version | `0.16.0` (`short-squeeze-core/pyproject.toml`) |
| Start here | [short-squeeze-core/docs/getting-started.md](short-squeeze-core/docs/getting-started.md) |
| Documentation map | [short-squeeze-core/docs/README.md](short-squeeze-core/docs/README.md) |
| Package README | [short-squeeze-core/README.md](short-squeeze-core/README.md) |

The screener does not place orders, access brokerage accounts, recommend trades, or
claim predictive validation.

### Quick start

```powershell
cd short-squeeze-core
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
Copy-Item .env.example .env
$env:SQUEEZE_APP_MODE = "FROZEN_DEMO"
.\.venv\Scripts\python.exe -m apps.research_screener --no-browser
```

```bash
cd short-squeeze-core
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
cp .env.example .env
export SQUEEZE_APP_MODE=FROZEN_DEMO
python -m apps.research_screener --no-browser
```

Open `http://127.0.0.1:8787/`.

## License

Licensed under the [MIT License](LICENSE).
