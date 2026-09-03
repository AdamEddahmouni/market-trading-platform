# Research Screener Application

This package contains the read-only HTTP server, dashboard, provider adapters,
frozen demonstration loader, evidence projection, and methodology comparison
engine.

Launch from the repository root:

```bash
python -m apps.research_screener --mode FROZEN_DEMO --no-browser
```

Use `python -m apps.research_screener.config doctor --json` to validate provider
configuration without exposing values. See the root `README.md` and the documents
under `docs/` for the supported modes, endpoints, providers, security boundary,
and integration workflow.
