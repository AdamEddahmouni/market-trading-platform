# Contributing

Thank you for your interest in this project.

## Getting started

1. Fork the repository and clone your fork.
2. Follow the quick start in [README.md](README.md) or
   [short-squeeze-core/docs/getting-started.md](short-squeeze-core/docs/getting-started.md).
3. Use `FROZEN_DEMO` mode for development — no API keys required.

## Development workflow

```bash
cd short-squeeze-core
python3.12 -m venv .venv
source .venv/bin/activate   # Windows: .\.venv\Scripts\activate
python -m pip install -e ".[test]"
make precommit              # import checks + Makefile validation
make test-quick             # smoke tests
```

Install the pre-commit hook (optional):

```bash
make install-hooks
```

## Pull requests

- Keep changes focused and match existing code style.
- Run `make precommit` before submitting.
- Do not commit `.env`, `.private/`, credentials, or personal correspondence.
- The CI workflow runs `release_audit.py` on `short-squeeze-core/` — PRs must pass.

## Issues

Bug reports and feature requests are welcome via GitHub Issues. For security
concerns, see [SECURITY.md](SECURITY.md).

## Scope

The application is `short-squeeze-core/`. All new work belongs there.
