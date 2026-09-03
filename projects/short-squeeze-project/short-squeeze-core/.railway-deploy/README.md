# Short Squeeze Research Screener

A read-only research application for comparing transparent short-squeeze screening
methodologies against timestamped provider evidence. It presents current candidates,
a deterministic frozen demonstration, provider health, explicit missingness, and a
versioned integration API.

The application does not place orders, access brokerage accounts, recommend trades,
or claim predictive validation.

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/new/github/AdamEddahmouni/short-squeeze-screener-internship)

## Capabilities

- Three runtime modes: `LOCAL_FULL`, `CLOUD_PROVIDER_MODE`, and `FROZEN_DEMO`
- Provider adapters for Finviz Elite, NewsAPI, Finnhub, SEC EDGAR, and local IBKR
- Legacy, peer-reference, Evidence-Gated Prime, and canonical research views
- Field-level provenance, freshness, status, and missingness
- Stable API version `1.0.0` and schema `batch14.integration.v1`
- Deterministic frozen dataset with 13 candidates and 325 rule outcomes
- Provider-independent frozen launch and integration acceptance checks
- Allowlisted, privacy-audited handoff release builder

## Quick start

Python 3.12 is required.

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
. .venv/bin/activate
python -m pip install -e '.[test]'
cp .env.example .env
export SQUEEZE_APP_MODE=FROZEN_DEMO
python -m apps.research_screener --no-browser
```

Open `http://127.0.0.1:8787/`. Frozen mode does not need provider credentials.
The application reads process environment variables; pass `--config .env` to read
an explicit file.

## Configuration

Configuration precedence is:

1. command-line arguments;
2. process environment;
3. an explicit configuration file;
4. an explicitly supplied local private provider file in `LOCAL_FULL`;
5. safe defaults.

Copy `.env.example`, replace only the providers you use, and keep the resulting
file private. Validate configuration without printing values:

```bash
python -m apps.research_screener.config doctor --mode FROZEN_DEMO
python -m apps.research_screener.config doctor --mode CLOUD_PROVIDER_MODE --json
```

See [Configuration](docs/CONFIGURATION.md) and [Providers](docs/PROVIDERS.md).

## Application modes

| Mode | Provider behavior | Network bind | Intended use |
|---|---|---|---|
| `FROZEN_DEMO` | Sanitized bundled data; private file not loaded | `127.0.0.1` | Evaluation and integration |
| `CLOUD_PROVIDER_MODE` | Environment-configured cloud-safe providers; no local IBKR probe | `0.0.0.0:$PORT` | Containers and Railway |
| `LOCAL_FULL` | Explicit local provider file and optional local IBKR | `127.0.0.1` | Operator workstation |

## API

Health and readiness are available at `/health` and `/ready`. The integration
manifest is at `/api/v1/integration/manifest`. See [API](docs/API.md) and the
[OpenAPI document](docs/openapi.json).

## Methodologies

Methodology outputs are independent; missing evidence remains `UNKNOWN` rather
than being inferred or treated as zero. The machine identifier
`adam_evidence_gated_prime.v1` remains stable for compatibility, while its public
display label is **Evidence-Gated Prime v1**. See
[Methodologies](docs/METHODOLOGIES.md).

The source distribution also retains the verified Phase 3D acquisition and
point-in-time evidence components required by the canonical research pipeline.
They remain descriptive infrastructure and do not start Phase 3E.

## Testing

```bash
python -m pytest -p no:cacheprovider --basetemp .pytest-run
python tools/integration_acceptance.py --mode frozen
```

Normal tests use synthetic fakes and do not call live providers. See
[Testing](docs/TESTING.md).

## Containers and Railway

Click the button above to deploy directly to Railway, or build locally:

```bash
docker build -t short-squeeze-research-screener .
docker run --rm -p 8787:8787 -e SQUEEZE_APP_MODE=FROZEN_DEMO short-squeeze-research-screener
```

Railway will auto-detect the `railway.toml` and `Dockerfile` in the repo root.
The deployment runs in `CLOUD_PROVIDER_MODE`, binds `0.0.0.0:$PORT`, and serves
the live scanner at the root URL. Requires provider environment variables:
`FINVIZ_API_KEY`, `FINNHUB_KEY`, and optionally `NEWSAPI_KEY`.

See [Deployment](docs/DEPLOYMENT.md) for cloud configuration and smoke checks.

## Integration handoff

Build a clean release from the committed allowlist:

```bash
python tools/build_handoff_release.py --json
python tools/release_audit.py dist/short-squeeze-research-screener-0.15.0 --json
```

Start with [HANDOFF_README](HANDOFF_README.md), then use the
[Integration Checklist](INTEGRATION_CHECKLIST.md).

## Security and limitations

Secrets are replaceable environment values and are never required for frozen mode.
Generated releases exclude Git metadata, private configuration, raw provider data,
local caches, and historical internal documents. Review [Security](docs/SECURITY.md)
and [Limitations](docs/LIMITATIONS.md) before production use.

## License

No redistribution license has been selected. See [License Status](LICENSE_STATUS.md).
Third-party packages retain their own licenses; see
[Third-Party Notices](THIRD_PARTY_NOTICES.md).
