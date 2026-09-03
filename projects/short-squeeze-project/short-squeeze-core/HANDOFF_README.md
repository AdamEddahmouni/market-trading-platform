# Integration-Team Handoff

Version **0.16.0**. This package contains a read-only research screener,
deterministic demonstration data, an HTTP API, provider adapters, offline tests,
deployment files, and release verification tools.

Full documentation map: [docs/README.md](docs/README.md).  
Step-by-step tutorial: [docs/getting-started.md](docs/getting-started.md).

## First run

1. Create a Python 3.12 virtual environment.
2. Install with `python -m pip install -e ".[test]"`.
3. Copy `.env.example` to a private file (`.env` is gitignored).
4. Start with `python -m apps.research_screener --mode FROZEN_DEMO --no-browser`.
5. Open `http://127.0.0.1:8787/`.
6. Run `python tools/integration_acceptance.py --mode frozen`.
7. Run `python -m pytest -p no:cacheprovider --basetemp .pytest-run`.

Frozen mode needs no provider credentials. To use a private configuration file,
pass `--config <path>`. `LOCAL_FULL` may also receive `--provider-config <path>`;
that private provider file is never loaded in cloud or frozen mode.

## Replacing or disabling providers

Credentials are environment variables. No source edits are required. Set the
corresponding `*_ENABLED=false` value to disable Finviz, NewsAPI, Finnhub, SEC, or
IBKR. A disabled provider reports `DISABLED`, not an error.

Run `python -m apps.research_screener.config doctor --json` after changes. The
doctor reports presence, validity, compatibility, and readiness without values.

## Canonical and experimental behavior

Canonical Phase 3A preserves registered rule semantics and explicit `UNKNOWN`
outcomes. The legacy, peer-reference, and Evidence-Gated Prime methodologies are
separate projections. Provider fields marked display-only do not satisfy canonical
rules merely because their labels appear similar.

No experimental indicator or sentiment output changes the canonical methodology.

## Explicit exclusions

The project has no trading, order submission, position, balance, or account-data
capabilities. It has not completed predictive validation, backtesting, P&L
analysis, or threshold optimization.

Continue with `docs/INTEGRATION.md`, `docs/CONFIGURATION.md`, `docs/API.md`, and
`docs/SECURITY.md`.
