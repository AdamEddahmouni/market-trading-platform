# Short Squeeze Research Screener

Version **0.16.0**. A read-only research application for comparing transparent
short-squeeze screening methodologies against timestamped provider evidence.

It presents current candidates, a deterministic frozen demonstration, provider
health, explicit missingness, and a versioned integration API.

**This is not trading advice.** The application does not place orders, access
brokerage accounts, recommend trades, or claim predictive validation.

Documentation map: [docs/README.md](docs/README.md)  
First run: [docs/getting-started.md](docs/getting-started.md)

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/new/github/AdamEddahmouni/short-squeeze-screener-internship)

## Capabilities

- Runtime modes: `LOCAL_FULL`, `CLOUD_PROVIDER_MODE`, `FROZEN_DEMO`
- Provider adapters: Finviz Elite, NewsAPI, Finnhub, SEC EDGAR, local/remote IBKR
- Methodologies: Legacy, peer-reference, Evidence-Gated Prime, canonical Phase 3A views
- Field-level provenance, freshness, status, and research admissibility
- Stable API version `1.0.0` and schema `batch14.integration.v1`
- Deterministic frozen dataset (13 candidates) and provider-independent launch
- Allowlisted, privacy-audited handoff release builder
- Opt-in API hardening (`CSRF_PROTECTION`, `LOCK_SENSITIVE_API`; default off)

## Quick start (frozen demo)

Python **3.12** is required. Work from this directory (`short-squeeze-core/`).

### Windows PowerShell

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
Copy-Item .env.example .env
$env:SQUEEZE_APP_MODE = "FROZEN_DEMO"
.\.venv\Scripts\python.exe -m apps.research_screener --no-browser
```

### macOS and Linux

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
cp .env.example .env
export SQUEEZE_APP_MODE=FROZEN_DEMO
python -m apps.research_screener --no-browser
```

Open `http://127.0.0.1:8787/`. Frozen mode does not need provider credentials.
Pass `--config .env` to load an explicit file; otherwise process environment and
safe defaults apply.

Full tutorial with verification and troubleshooting: [docs/getting-started.md](docs/getting-started.md).

## Configuration

Precedence:

1. Command-line arguments
2. Process environment
3. Explicit configuration file
4. Explicit local private provider file (**only** in `LOCAL_FULL`)
5. Safe defaults

```bash
python -m apps.research_screener.config doctor --mode FROZEN_DEMO
python -m apps.research_screener.config doctor --mode CLOUD_PROVIDER_MODE --json
```

See [Configuration](docs/CONFIGURATION.md), [Providers](docs/PROVIDERS.md), and
[.env.example](.env.example).

## Application modes

| Mode | Provider behavior | Network bind | Intended use |
|---|---|---|---|
| `FROZEN_DEMO` | Sanitized bundled data; private file not loaded | `127.0.0.1` | Evaluation and integration |
| `CLOUD_PROVIDER_MODE` | Environment-configured cloud-safe providers; no local IBKR probe | `0.0.0.0:$PORT` | Containers and Railway |
| `LOCAL_FULL` | Explicit local provider file and optional IBKR | `127.0.0.1` | Operator workstation |

## Ports

| Context | Port |
|---|---|
| Native local default | `8787` |
| Docker Compose (browser) | Host `8787` → container `8080` |
| Railway / container listen | `$PORT` (Compose sets `8080` inside the container) |

## API

| Path | Purpose |
|---|---|
| `/health` | Liveness |
| `/ready` | Mode-specific readiness |
| `/api/v1/integration/manifest` | Integration contract |

Full route table: [API](docs/API.md). OpenAPI: [docs/openapi.json](docs/openapi.json).

## Methodologies

Methodology outputs are independent. Missing evidence remains `UNKNOWN` rather
than inferred or treated as zero. Machine identifier `adam_evidence_gated_prime.v1`
is stable; public label is **Evidence-Gated Prime v1**.

As of 0.16.0, the evidence-gated floor aligns to Finviz-supported weight (65%),
SEC catalyst age uses `filed_at`, Finviz mapping conflicts are withheld, and
borrow availability % float is admissible when both IBKR and Finviz legs qualify.

See [Methodologies](docs/METHODOLOGIES.md) and [Reproducibility](docs/reproducibility.md).

## Testing

```bash
python -m pytest -p no:cacheprovider --basetemp .pytest-run
python tools/integration_acceptance.py --mode frozen
```

Normal tests use synthetic fakes and do not call live providers. See
[Testing](docs/TESTING.md).

## Containers and Railway

```bash
docker build -t short-squeeze-research-screener .
docker run --rm -p 8787:8080 -e PORT=8080 -e SQUEEZE_APP_MODE=FROZEN_DEMO short-squeeze-research-screener
```

```bash
make deploy-sync
make check-railway-mirror
make deploy
```

Cloud mode needs provider environment variables such as `FINVIZ_API_KEY` and
`FINNHUB_KEY` (and optionally `NEWSAPI_KEY`). See [Deployment](docs/DEPLOYMENT.md)
and [How-to guides](docs/how-to-guides.md).

## Integration handoff

```bash
python tools/build_handoff_release.py --json
python tools/release_audit.py dist/short-squeeze-research-screener-0.16.0 --json
```

Start with [HANDOFF_README](HANDOFF_README.md), then
[Integration Checklist](INTEGRATION_CHECKLIST.md).

## Security and limitations

Secrets are replaceable environment values and are never required for frozen mode.
Optional locks: `CSRF_PROTECTION`, `LOCK_SENSITIVE_API` (default off). Review
[Security](docs/SECURITY.md) and [Limitations](docs/LIMITATIONS.md).

## License

Licensed under the [MIT License](../LICENSE). See [License Status](LICENSE_STATUS.md).
Third-party packages: [Third-Party Notices](THIRD_PARTY_NOTICES.md).
