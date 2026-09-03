# Research Screener Application

This package contains the read-only HTTP server, dashboard, provider adapters,
frozen demonstration loader, evidence projection, and methodology comparison
engine (product version **0.16.0**).

Launch from `short-squeeze-core/` (repository package root):

```bash
python -m apps.research_screener --mode FROZEN_DEMO --no-browser
```

Open `http://127.0.0.1:8787/`. Use
`python -m apps.research_screener.config doctor --json` to validate provider
configuration without exposing values.

Documentation:

- [Getting Started](../../docs/getting-started.md)
- [Documentation index](../../docs/README.md)
- Package [README](../../README.md)
